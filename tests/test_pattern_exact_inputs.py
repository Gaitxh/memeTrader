import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from solders.pubkey import Pubkey

from memetrader.collectors import (PumpSwapVaultFlowTracker, SolanaHeldAccountCollector,
    PUMP_AMM_PROGRAM_ID, PUMPSWAP_GLOBAL_CONFIG_PDA)
from memetrader.forward_patterns import experiment_policies, pattern_signal
from memetrader.models import TokenCandidate, TokenSnapshot, Observation, iso, utcnow
from memetrader.autonomous_search import _source_contract_mentions
from memetrader.runtime import Runtime
from memetrader.store import Store


def test_migration_and_reserve_context_require_actual_asof_identity(tmp_path, monkeypatch):
    store = Store(tmp_path / "evidence.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    start = utcnow()
    now = start + timedelta(seconds=1)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.models.utcnow", lambda: now)
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "M", "M",
                           source="pumpportal:migration", first_seen_at=now,
                           raw={"pump_event_type": "migration", "signature": "actual-source-signature"})
    store.upsert_token(token)
    store.record_token_launch_fact(token, ingested_at=now)
    pair = str(Pubkey.new_unique())
    now += timedelta(seconds=1)
    store.record_chain_meme_pattern_evidence(token.token_id, pair, "pool_resolution",
        {"status": "RESOLVED", "canonical_migration_pool": True}, observed_at=now, source_key="verified-pool")
    history = []
    for _ in range(2):
        now += timedelta(seconds=16)
        history.append(dict(token_id=token.token_id, pair_address=pair, price=1, liquidity=10000,
            buys=6, sells=3, volume=500, pool_age_seconds=90,
            observed_at=iso(now), ingested_at=iso(now), recorded_at=iso(now)))
    context = store.chain_meme_pattern_context(token.token_id, pair, history, now)
    p = next(p for p in experiment_policies() if p["arm_id"] == "experiment_migration_candidate_v1")
    assert context["migration"]["post_migration_samples"] == 2
    assert pattern_signal(history, p, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    context["migration"]["canonical_migration_pool"] = False
    assert not pattern_signal(history, p, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    assert not pattern_signal(history, p, decision_at=iso(now), activated_at=iso(now), context=context)[0]
    assert not store.chain_meme_pattern_context(token.token_id, "other-pool", history, now)
    assert "migration_signature" not in store.chain_meme_pattern_context(token.token_id, pair, history[:1], now)["migration"]

    def vault(change, state="OBSERVED_NORMAL"):
        return dict(observer_state=state, slot_min=100, slot_max=100,
            features=dict(sample_count=6, latest_direction="SELL_LIKE_NET",
                unwind_hazard_precursor=False, synthetic_support_pattern=False,
                windows={"10": {"coverage_seconds": 8, "raw_quote_change_ratio": change}}))
    store.record_chain_meme_pattern_evidence(token.token_id, pair, "vault_frame", vault(-.3),
        observed_at=now, source_key="drain")
    context = store.chain_meme_pattern_context(token.token_id, pair, history, now)
    candidate = next(p for p in experiment_policies() if p["arm_id"] == "experiment_support_risk_candidate_v1")
    control = next(p for p in experiment_policies() if p["arm_id"] == "experiment_support_risk_control_v1")
    assert context["support_risk"]["unwind_hazard"] == "HIGH"
    assert not pattern_signal(history, candidate, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    assert pattern_signal(history, control, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    store.record_chain_meme_pattern_evidence(token.token_id, pair, "vault_frame", vault(-.01),
        observed_at=now, source_key="normal")
    context = store.chain_meme_pattern_context(token.token_id, pair, history, now)
    assert pattern_signal(history, candidate, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades").fetchone()[0] == 0
    assert store.record_chain_meme_pattern_evidence(token.token_id, pair, "vault_frame", vault(0),
        observed_at=now + timedelta(seconds=1), source_key="future") is None
    store.close()


def test_preentry_pool_targets_share_existing_stream_without_fake_holders(tmp_path):
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "targets.sqlite3", initial_cash_usd=1000)
    runtime.store.activate_chain_meme_trader_funded_period()
    runtime.store.register_chain_meme_pattern_experiments()
    runtime._pattern_pool_targets = {}
    runtime._pattern_pool_retry = {}
    runtime._pattern_vault_tracker = PumpSwapVaultFlowTracker(summary_seconds=10)
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "M", "M")
    runtime.store.upsert_token(token)
    pair = str(Pubkey.new_unique())
    now = utcnow()
    runtime._pattern_watch = {token.token_id: dict(token=token, pair_address=pair,
        expires_at=now + timedelta(minutes=15), quote=TokenSnapshot("solana", token.address, 1, 10000, 100000, 500, 6, 3,
        observed_at=now, raw={"pair": {"pairAddress": pair, "dexId": "pumpswap"}}))}
    async def resolve(candidates):
        assert len(candidates) == 1
        return [{**candidates[0], "status": "RESOLVED", "base_vault": "base-vault", "quote_vault": "quote-vault",
                 "quote_mint": "quote", "lp_mint": "lp", "base_token_program": "token-program",
                 "quote_token_program": "token-program", "virtual_quote_reserves_raw": 0, "resolved_slot": 100}]
    runtime.held_accounts = SimpleNamespace(resolve_pumpswap_shadow_pools=resolve)
    asyncio.run(runtime.chain_meme_pattern_pools_once())
    targets = runtime.chain_meme_combined_vault_targets()
    assert len(targets) == 3
    assert len({t["pubkey"] for t in targets}) == 3
    assert all(t["id"] < 0 and t["observer_version"] == "chain-pattern-exact/v1" for t in targets)
    assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions").fetchone()[0] == 0
    assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_v21_vault_shadow_frames").fetchone()[0] == 0
    runtime.store.close()


def participation_fixture():
    pool = dict(pool_address="pool", base_mint="base", quote_mint="quote", base_vault="bv",
        quote_vault="qv", base_token_program="bp", quote_token_program="qp", resolved_slot=50)
    raw = bytes((102,6,61,18,1,218,235,234)) + (100).to_bytes(8, "little") + (200).to_bytes(8, "little") + b"\x01"
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number, encoded = int.from_bytes(raw, "big"), ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    ix = dict(programId=PUMP_AMM_PROGRAM_ID, accounts=["pool", "user", PUMPSWAP_GLOBAL_CONFIG_PDA,
        "base", "quote", "ub", "uq", "bv", "qv", "fee", "fee_ata", "bp", "qp"], data=encoded)
    tx = dict(slot=52, meta={"err": None, "innerInstructions": []}, transaction=dict(signatures=["sig2"],
        message=dict(accountKeys=[{"pubkey": "user", "signer": True}], instructions=[ix])))
    return pool, {"signature": "sig2", "slot": 52, "err": None}, tx


@pytest.mark.parametrize("near_miss", [None, "inner", "pool", "base", "qv", "signer", "unknown", "missing"])
def test_participation_exact_signers_not_balance_volume(near_miss):
    pool, signature, tx = participation_fixture()
    ix = tx["transaction"]["message"]["instructions"][0]
    if near_miss == "inner":
        tx["transaction"]["message"]["instructions"] = []
        tx["meta"]["innerInstructions"] = [{"index": 0, "instructions": [ix]}]
    elif near_miss in {"pool", "base", "qv"}:
        # Keep the exact pool present even when the IDL account order is wrong.
        index = {"pool": 0, "base": 3, "qv": 8}[near_miss]
        ix["accounts"][index] = "wrong"
        ix["accounts"].append("pool")
    elif near_miss == "signer":
        tx["transaction"]["message"]["accountKeys"][0]["signer"] = False
    elif near_miss == "unknown":
        ix["data"] = "11111111"
    elif near_miss == "missing":
        tx = None
    trades, complete = SolanaHeldAccountCollector._pumpswap_participation_instructions(tx, signature, pool)
    assert complete is (near_miss in {None, "inner"})
    if complete:
        assert trades[0]["signer_address"] == "user"
        assert trades[0]["side"] == "BUY"
        assert "amount" not in trades[0]
    else:
        assert trades == []


def test_participation_seed_and_truncated_windows_never_create_false_breadth():
    async def scenario():
        pool, signature, tx = participation_fixture()
        methods = []
        responses = [[signature], [signature], tx, [signature] * 10]
        class Http:
            async def post(self, url, *, json):
                methods.append(json["method"])
                return httpx.Response(200, json={"result": responses.pop(0)}, request=httpx.Request("POST", url))
        collector = SolanaHeldAccountCollector("https://rpc.invalid")
        await collector.http.aclose()
        collector.http = Http()
        seed = await collector.sample_pumpswap_participation(pool, None)
        assert seed["status"] == "SEEDED_NO_WINDOW" and methods == ["getSignaturesForAddress"]
        scan = await collector.sample_pumpswap_participation(pool, {"signature": "sig1", "slot": 51})
        assert scan["complete"] and len(scan["trades"]) == 1
        truncated = await collector.sample_pumpswap_participation(pool, scan["frontier"])
        assert truncated["status"] == "TRUNCATED_INCOMPLETE" and not truncated["trades"]
        assert methods.count("getTransaction") == 1
    asyncio.run(scenario())


def test_participation_two_complete_windows_and_count_share(tmp_path, monkeypatch):
    store = Store(tmp_path / "participation.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    start = utcnow()
    now = start + timedelta(seconds=1)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    store.record_chain_meme_pattern_evidence("solana:base", "pool", "pool_resolution", {"status": "RESOLVED"},
        observed_at=now, source_key="pool")
    for number, names in enumerate((["a", "b", "a"], ["c", "d", "e"])):
        began = now
        now += timedelta(seconds=16)
        store.record_chain_meme_pattern_evidence("solana:base", "pool", "participation_scan", dict(
            complete=True, started_at=iso(began), completed_at=iso(now),
            trades=[dict(side="BUY", signer_address=n) for n in names]), observed_at=now, source_key=str(number))
    context = store.chain_meme_pattern_context("solana:base", "pool", [], now)["participation"]
    assert context["unique_buyers"] == 5
    assert context["new_buyers_second_window"] == 3
    assert context["largest_buyer_share"] == pytest.approx(2 / 6)
    now += timedelta(seconds=16)
    store.record_chain_meme_pattern_evidence("solana:base", "pool", "participation_scan", {"complete": False},
        observed_at=now, source_key="gap")
    assert "participation" not in store.chain_meme_pattern_context("solana:base", "pool", [], now)
    store.close()


def test_narrative_original_text_not_script_or_chain_ambiguous_address():
    sol = str(Pubkey.new_unique())
    evm = "0x" + "aB" * 20
    assert _source_contract_mentions(f"<script>{sol}</script><p>No contract</p>") == []
    assert _source_contract_mentions(f"<p>Solana {sol} and {evm}</p>") == ["solana:" + sol]
    assert _source_contract_mentions(f"<p>BNB Chain {evm}</p>") == ["bsc:" + evm.lower()]
    assert _source_contract_mentions(f"<p>BNB Chain and Robinhood Chain {evm}</p>") == []


@pytest.mark.parametrize("bad", [None, "shared_origin", "one_mention", "future", "promotion"])
def test_narrative_fact_support_and_exact_source_relation(tmp_path, monkeypatch, bad):
    store = Store(tmp_path / "narrative.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    start = utcnow()
    now = start + timedelta(seconds=1)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    token_id = "bsc:0x" + "12" * 20
    sources = [Observation(source=f"publisher-{i}.example", source_kind="news", title="Original event",
        url=f"https://publisher-{i}.example/article", published_at=now, observed_at=now, ingested_at=now,
        raw={"source_contract_mentions": [] if bad == "one_mention" and i == 1 else [token_id]}) for i in range(2)]
    completed = now + timedelta(seconds=1) if bad == "future" else now
    record_id = store.add_agent_fact_verification(dict(verification_run_id="test", parent_task="trend_scout",
        parent_run_id="test", subject_id="event", subject_kind="event", subject_title="Original event",
        claim_sha256="test", requested_at=iso(now), completed_at=iso(completed), status="cross_source_supported",
        claim_status="promotion" if bad == "promotion" else "confirmed_fact", confidence=.95,
        support_source_count=2, contradiction_source_count=0, context_source_count=0, distinct_support_domain_count=2,
        evidence={"distinct_origin_support_domain_count": 1 if bad == "shared_origin" else 2,
            "sources": [{"url": o.url, "domain": o.source, "stance": "supports", "origin_relationship": "distinct_origin"} for o in sources]},
        model="fixture", reasoning_effort="low", tokens_used=0, error_code=""))
    ids = store.record_chain_meme_pattern_narrative(record_id, sources)
    assert bool(ids) is (bad is None)
    context = store.chain_meme_pattern_context(token_id, "evm-pool", [], now)
    if bad is None:
        f = dict(token_id=token_id, pair_address="evm-pool", price=1, liquidity=10000, buys=3, sells=4,
            pool_age_seconds=60, observed_at=iso(now), ingested_at=iso(now), recorded_at=iso(now))
        candidate = next(p for p in experiment_policies() if p["arm_id"] == "experiment_narrative_candidate_v1")
        control = next(p for p in experiment_policies() if p["arm_id"] == "experiment_narrative_control_v1")
        assert pattern_signal([f], candidate, decision_at=iso(now), activated_at=iso(start), context=context)[0]
        assert not pattern_signal([f], control, decision_at=iso(now), activated_at=iso(start), context=context)[0]
    else:
        assert "narrative" not in context
    store.close()
