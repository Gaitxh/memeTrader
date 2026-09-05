import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from solders.pubkey import Pubkey

from memetrader.collectors import (PumpSwapVaultFlowTracker, SolanaHeldAccountCollector,
    PUMP_AMM_PROGRAM_ID, PUMPSWAP_GLOBAL_CONFIG_PDA, SPL_TOKEN_PROGRAM_ID,
    SPL_TOKEN_2022_PROGRAM_ID)
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


def participation_fixture(track_volume=b"\x01"):
    pool = dict(pool_address="pool", base_mint="base", quote_mint="quote", base_vault="bv",
        quote_vault="qv", base_token_program="bp", quote_token_program="qp", resolved_slot=50)
    raw = bytes((102,6,61,18,1,218,235,234)) + (100).to_bytes(8, "little") + (200).to_bytes(8, "little") + track_volume
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
@pytest.mark.parametrize("track_volume", [b"", b"\x01"])
def test_participation_exact_signers_not_balance_volume(near_miss, track_volume):
    pool, signature, tx = participation_fixture(track_volume)
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


def amountful_participation_fixture(side="BUY", checked=False):
    pool, signature, tx = participation_fixture()
    pool.update(base_token_program=SPL_TOKEN_2022_PROGRAM_ID, quote_token_program=SPL_TOKEN_PROGRAM_ID)
    ix = tx["transaction"]["message"]["instructions"][0]
    ix["accounts"][11:13] = [pool["base_token_program"], pool["quote_token_program"]]
    tx["blockTime"] = signature["blockTime"] = 100
    keys = tx["transaction"]["message"]["accountKeys"]
    for address, mint, owner in (("ub", "base", "user"), ("uq", "quote", "user"),
                                 ("bv", "base", "pool"), ("qv", "quote", "pool")):
        keys.append({"pubkey": address, "signer": False})
        tx["meta"].setdefault("preTokenBalances", []).append(dict(
            accountIndex=len(keys) - 1, mint=mint, owner=owner,
            uiTokenAmount={"amount": "999999999", "decimals": 9}))
    def transfer(source, destination, mint, amount, program):
        info = dict(source=source, destination=destination, authority="user")
        if checked:
            info.update(mint=mint, tokenAmount={"amount": str(amount), "decimals": 9})
        else:
            info["amount"] = str(amount)
        return dict(programId=program, program="spl-token", stackHeight=2,
                    parsed=dict(type="transferChecked" if checked else "transfer", info=info))
    base = transfer("bv" if side == "BUY" else "ub", "ub" if side == "BUY" else "bv",
                    "base", 7, pool["base_token_program"])
    quote = transfer("uq" if side == "BUY" else "qv", "qv" if side == "BUY" else "uq",
                     "quote", 123, pool["quote_token_program"])
    fee = transfer("uq", "fee_ata", "quote", 9, pool["quote_token_program"])
    event = dict(programId=PUMP_AMM_PROGRAM_ID, accounts=["event_authority"], data="event", stackHeight=2)
    tx["meta"]["innerInstructions"] = [dict(index=0, instructions=[base, quote, fee, event])]
    return pool, signature, tx


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("checked", [False, True])
def test_actual_spl_transfer_mints_amounts_and_sell_direction(side, checked):
    pool, signature, tx = amountful_participation_fixture(side, checked)
    amounts = SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(tx, "user", pool, side, "outer:0")
    assert amounts == {"base_amount_raw": 7, "quote_amount_raw": 123}
    if side == "BUY":
        trades, complete = SolanaHeldAccountCollector._pumpswap_participation_instructions(tx, signature, pool)
        assert complete and trades[0]["amount_complete"]
        assert trades[0]["quote_amount_raw"] == 123  # maxQuoteIn in instruction is 200.
        assert trades[0]["block_time"] == 100
    tx["meta"]["innerInstructions"][0]["instructions"][1]["programId"] = "fake-token-program"
    assert SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(tx, "user", pool, side, "outer:0") is None


@pytest.mark.parametrize("track_volume,valid", [(b"", True), (b"\x00", True), (b"\x01", True),
                                               (b"\x02", False), (b"\x00\x00", False)])
def test_buy_optional_track_volume_has_only_legal_encodings(track_volume, valid):
    pool, signature, tx = participation_fixture(track_volume)
    trades, complete = SolanaHeldAccountCollector._pumpswap_participation_instructions(tx, signature, pool)
    assert complete is valid
    assert bool(trades) is valid


def test_observed_24_byte_buy_uses_actual_transfer_not_quote_limit():
    # Observed mainnet scan 2950 frontier, successful slot 444576018 BUY:
    # discriminator + base_out=336067 + max_quote_in=21500, no OptionBool.
    pool, signature, tx = amountful_participation_fixture(checked=True)
    tx["transaction"]["message"]["instructions"][0]["data"] = "AJTQ2h9DXrC3EfEBX5hGGuf79oqJ5wVyH"
    transfers = tx["meta"]["innerInstructions"][0]["instructions"]
    transfers[0]["parsed"]["info"]["tokenAmount"] = {"amount": "336067", "decimals": 6}
    transfers[1]["parsed"]["info"]["tokenAmount"] = {"amount": "21224", "decimals": 9}
    trades, complete = SolanaHeldAccountCollector._pumpswap_participation_instructions(tx, signature, pool)
    assert complete and trades[0]["amount_complete"]
    assert trades[0]["base_amount_raw"] == 336067
    assert trades[0]["quote_amount_raw"] == 21224  # Not the 21500 instruction limit.


@pytest.mark.parametrize("checked", [False, True])
@pytest.mark.parametrize("near_miss", [None, "unknown_fee_destination", "wrong_fee_owner", "wrong_fee_mint"])
def test_observed_sell_vault_fee_legs_do_not_discard_user_recovery(checked, near_miss):
    from copy import deepcopy
    pool, signature, tx = amountful_participation_fixture("SELL", checked)
    swap = tx["transaction"]["message"]["instructions"][0]
    # Mainnet successful SELL 3tbqfV...Aka9q9C, slot 444579388.
    swap["data"] = "5jRcjdixRUDKHJsWJ2FdEp4FoqQFkBDVy"
    swap["accounts"].extend(["system", "ata_program", "event", PUMP_AMM_PROGRAM_ID,
        "creator_ata", "creator_owner", "fee_config", "fee_program", "pool_v2", "buyback_owner", "buyback_ata"])
    transfers = tx["meta"]["innerInstructions"][0]["instructions"]
    def set_amount(ix, value):
        info = ix["parsed"]["info"]
        if checked:
            info["tokenAmount"]["amount"] = str(value)
        else:
            info["amount"] = str(value)
    set_amount(transfers[0], 3387307562)
    set_amount(transfers[1], 215752775)
    for ata, owner, value in (("fee_ata", "fee", 54199),
                              ("creator_ata", "creator_owner", 498625),
                              ("buyback_ata", "buyback_owner", 54198)):
        keys = tx["transaction"]["message"]["accountKeys"]
        keys.append({"pubkey": ata, "signer": False})
        tx["meta"]["preTokenBalances"].append(dict(accountIndex=len(keys)-1,
            mint="quote", owner=owner, uiTokenAmount={"amount": "0", "decimals": 9}))
        fee = deepcopy(transfers[1])
        fee["parsed"]["info"].update(source="qv", destination=ata)
        set_amount(fee, value)
        transfers.append(fee)
    if near_miss == "unknown_fee_destination":
        transfers[-1]["parsed"]["info"]["destination"] = "unknown"
    elif near_miss == "wrong_fee_owner":
        tx["meta"]["preTokenBalances"][-1]["owner"] = "unrelated"
    elif near_miss == "wrong_fee_mint":
        tx["meta"]["preTokenBalances"][-1]["mint"] = "wrong"
    trades, complete = SolanaHeldAccountCollector._pumpswap_participation_instructions(tx, signature, pool)
    assert complete
    assert trades[0]["amount_complete"] is (near_miss is None)
    if near_miss is None:
        assert trades[0]["base_amount_raw"] == 3387307562
        assert trades[0]["quote_amount_raw"] == 215752775  # User receipt, not fees or minOut.


def test_inner_swaps_use_actual_cpi_stack_scope_and_reject_ambiguous_amounts():
    from copy import deepcopy
    pool, _, tx = amountful_participation_fixture()
    swap = tx["transaction"]["message"]["instructions"][0]
    swap["stackHeight"] = 2
    transfers = tx["meta"]["innerInstructions"][0]["instructions"]
    for ix in transfers:
        ix["stackHeight"] = 3
    tx["transaction"]["message"]["instructions"] = [{"programId": "router"}]
    group = [swap, *transfers, deepcopy(swap), *deepcopy(transfers)]
    tx["meta"]["innerInstructions"][0]["instructions"] = group
    for path in ("inner:0:0", "inner:0:5"):
        assert SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(
            tx, "user", pool, "BUY", path) == {"base_amount_raw": 7, "quote_amount_raw": 123}
    group[1].pop("stackHeight")
    assert SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(tx, "user", pool, "BUY", "inner:0:0") is None


def test_temporary_wrapped_quote_account_owner_comes_from_prior_spl_initialization():
    pool, _, tx = amountful_participation_fixture(checked=True)
    tx["meta"]["preTokenBalances"] = [b for b in tx["meta"]["preTokenBalances"] if b["accountIndex"] != 2]
    init = dict(programId=SPL_TOKEN_PROGRAM_ID,
                parsed=dict(type="initializeAccount3", info=dict(account="uq", mint="quote", owner="user")))
    tx["transaction"]["message"]["instructions"].insert(0, init)
    tx["meta"]["innerInstructions"][0]["index"] = 1
    assert SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(
        tx, "user", pool, "BUY", "outer:1") == {"base_amount_raw": 7, "quote_amount_raw": 123}
    init["parsed"]["info"]["owner"] = "other"
    assert SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(tx, "user", pool, "BUY", "outer:1") is None


def test_scan_preserves_block_frontier_and_actual_local_receipts():
    async def scenario():
        pool, signature, tx = amountful_participation_fixture()
        responses = [[signature], tx]
        class Http:
            async def post(self, url, *, json):
                return httpx.Response(200, json={"result": responses.pop(0)}, request=httpx.Request("POST", url))
        collector = SolanaHeldAccountCollector("https://rpc.invalid")
        await collector.http.aclose()
        collector.http = Http()
        scan = await collector.sample_pumpswap_participation(pool, dict(signature="prior", slot=51, block_time=90))
        assert scan["complete"] and scan["coverage_complete"]
        assert scan["coverage_start"] == 90 and scan["coverage_end"] == 100
        assert scan["frontier"]["block_time"] == 100
        assert scan["trades"][0]["observed_at"] <= scan["observed_at"]
        assert scan["trades"][0]["recorded_at"] <= scan["recorded_at"]
    asyncio.run(scenario())


def test_runtime_amountful_flow_requires_real_adjacent_scans_and_reference_time(tmp_path, monkeypatch):
    from memetrader.collectors import SOLANA_WRAPPED_SOL_MINT
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "flow-inputs.sqlite3", initial_cash_usd=1000)
    runtime._pattern_pool_targets = {"pool": dict(pool_address="pool", token_id="solana:base",
        base_mint="base", quote_mint=SOLANA_WRAPPED_SOL_MINT)}
    runtime._pattern_participation_frontiers = {}
    runtime._pattern_participation_cursor = 0
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    surface = dict(complete=True, base_decimals=6, quote_decimals=9,
                   observed_at=iso(now - timedelta(seconds=5)), recorded_at=iso(now - timedelta(seconds=4)),
                   evidence_id=123, pool_creator="not_token_creator")
    runtime._pattern_surface_cache = {"pool": surface}
    runtime._pattern_origin_cache = {"pool": dict(
        status="verified", creator_address="token-creator",
        creator_identity_kind="token_creator", creator_identity_verified=True,
        evidence_id=321, proof={"proof_version": "pump-create-origin/v1"},
    )}
    runtime._wsol_usdc_conversion = dict(input_amount_raw=1_000_000_000,
        minimum_output_amount_raw=150_000_000, completed_at=iso(now - timedelta(seconds=2)))
    start = int(now.timestamp()) - 30
    scans = []
    for number in range(4):
        left, right = start + number * 5, start + (number + 1) * 5
        when = iso(now + timedelta(seconds=number))
        scan = dict(complete=True, coverage_complete=True, coverage_start=left, coverage_end=right,
                    started_at=when, completed_at=when, observed_at=when, recorded_at=when,
                    status="COMPLETE", trades=[dict(signature=str(number), instruction_path="outer:0",
                        side="BUY", signer_address="buyer", block_time=right,
                        observed_at=when, recorded_at=when, base_amount_raw=1_000_000,
                        quote_amount_raw=2_000_000_000, amount_complete=True, amount_source="parsed_spl_transfer",
                        pool_address="pool", base_mint="base", quote_mint=SOLANA_WRAPPED_SOL_MINT),
                        dict(signature=f"creator-{number}", instruction_path="outer:1",
                        side="SELL", signer_address="token-creator", block_time=right,
                        observed_at=when, recorded_at=when, base_amount_raw=500_000,
                        quote_amount_raw=1_000_000_000, amount_complete=True, amount_source="parsed_spl_transfer",
                        pool_address="pool", base_mint="base", quote_mint=SOLANA_WRAPPED_SOL_MINT)])
        scans.append(scan)
    scans[2].update(coverage_complete=False, complete=False, status="TRUNCATED_INCOMPLETE")
    async def sample(pool, frontier):
        return scans.pop(0)
    runtime.held_accounts = SimpleNamespace(sample_pumpswap_participation=sample)
    async def scenario():
        nonlocal now
        outcomes = []
        for number in range(4):
            await runtime.chain_meme_pattern_participation_once()
            row = runtime.store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence "
                "WHERE kind='amountful_flow' ORDER BY id DESC LIMIT 1").fetchone()
            outcomes.append(runtime.store._json_object(row[0]))
            now += timedelta(seconds=1)
        assert [row["complete"] for row in outcomes] == [False, True, False, False]
        second = outcomes[1]
        assert second["buy_quote_notional"] == 2 and second["buy_quote_notional_usd"] == 300
        assert second["repeat_buyer_notional_share"] == 1
        assert second["creator_sell_quote_notional_raw"] == 1_000_000_000
        assert second["creator_identity_kind"] == "token_creator"
        assert second["creator_identity_verified"] is True
        assert second["creator_origin_evidence_id"] == 321
        assert "reference_quote_estimate" in second["conversion_basis"]
        assert second["conversion_is_execution_evidence"] is False
        assert len(second["source_evidence_ids"]) == 2
        assert len(runtime._pattern_amountful_windows["pool"]) == 2
    asyncio.run(scenario())
    runtime.store.close()


def test_runtime_origin_verifies_known_create_signature_once_per_pool(tmp_path, monkeypatch):
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "origin.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    mint, pair = str(Pubkey.new_unique()), str(Pubkey.new_unique())
    token = TokenCandidate("solana", mint, "Origin", "ORG", first_seen_at=now,
        source="pumpportal:create", raw={"pump_event_type": "create", "txType": "create",
        "signature": "known-create", "traderPublicKey": "unverified-feed-value"})
    runtime.store.record_token_launch_fact(token, ingested_at=now)
    pool = dict(token_id=token.token_id, pool_address=pair, base_mint=mint)
    runtime._pattern_pool_targets = {pair: pool}
    runtime._pattern_origin_cache = {}
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    runtime.held_accounts = SimpleNamespace()
    calls = []

    async def verify(collector, expected_mint, signature, **kwargs):
        calls.append((expected_mint, signature))
        return dict(status="verified", reason="verified", mint=expected_mint,
            create_signature=signature, creator_address="chain-creator",
            creator_identity_kind="token_creator", creator_identity_verified=True,
            proof={"proof_version": "pump-create-origin/v1", "program_id": "pump"})

    monkeypatch.setattr("memetrader.runtime.verify_creator_from_known_signature", verify)

    async def scenario():
        await runtime._chain_meme_pattern_origin_once(pool)
        await runtime._chain_meme_pattern_origin_once(pool)

    asyncio.run(scenario())
    assert calls == [(mint, "known-create")]
    row = runtime.store.db.execute(
        "SELECT payload_json FROM chain_meme_pattern_evidence WHERE kind='token_origin'"
    ).fetchone()
    payload = runtime.store._json_object(row[0])
    assert payload["creator_address"] == "chain-creator"
    assert runtime._pattern_origin_cache[pair]["evidence_id"] is not None
    runtime.store.close()


def test_runtime_wsol_reference_is_independent_shared_and_bounded():
    from memetrader.collectors import SOLANA_WRAPPED_SOL_MINT
    runtime = Runtime.__new__(Runtime)
    runtime.store = SimpleNamespace(heartbeat=lambda *args, **kwargs: None)
    runtime._pattern_pool_targets = {"pool": {"quote_mint": SOLANA_WRAPPED_SOL_MINT}}
    runtime._wsol_usdc_conversion = None
    runtime._wsol_usdc_conversion_at = 0
    runtime._wsol_usdc_reference_next_at = 0
    runtime._jupiter_background_dispatch_lock = asyncio.Lock()
    runtime._jupiter_quote_lock = asyncio.Lock()
    runtime._jupiter_background_epoch_started = 0
    runtime._jupiter_background_epoch_requests = 0
    runtime._jupiter_background_epoch_seconds = 5
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    calls = []

    async def quote(*args, **kwargs):
        calls.append((args, kwargs))
        return {"other_amount_threshold": "150000000", "completed_at": iso()}

    runtime.jupiter = SimpleNamespace(quote=quote)

    async def scenario():
        await runtime.chain_meme_wsol_reference_once()
        await runtime.chain_meme_wsol_reference_once()
        runtime._chain_meme_active_idle_event.clear()
        runtime._wsol_usdc_conversion["completed_at"] = iso(utcnow() - timedelta(seconds=31))
        runtime._wsol_usdc_reference_next_at = 0
        pending = asyncio.create_task(runtime.chain_meme_wsol_reference_once())
        await asyncio.sleep(0)
        assert not pending.done() and len(calls) == 1
        runtime._chain_meme_active_idle_event.set()
        await pending

    asyncio.run(scenario())
    assert len(calls) == 2
    assert runtime._wsol_usdc_conversion["minimum_output_amount_raw"] == 150_000_000
    assert runtime._jupiter_background_epoch_requests == 2


def test_runtime_authoritative_event_records_once_before_pending_hydration(tmp_path, monkeypatch):
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "authoritative.sqlite3", initial_cash_usd=1000)
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    runtime.http = SimpleNamespace()
    now = utcnow()
    address = str(Pubkey.new_unique())
    event = dict(source="okx", source_kind="first_party", trusted=True,
        event_type="official_listing", title="OKX will list ORG",
        url="https://www.okx.com/help/official-origin", chain="solana",
        contract_address=address, published_at=iso(now - timedelta(seconds=5)),
        observed_at=iso(now), ingested_at=iso(now), source_host="www.okx.com",
        next_frame_trade_required=True)

    async def collect(http, **kwargs):
        return {"events": [event], "diagnostics": []}

    monkeypatch.setattr("memetrader.runtime.collect_okx_listing_events", collect)

    async def scenario():
        await runtime.chain_meme_authoritative_events_once()
        await runtime.chain_meme_authoritative_events_once()

    asyncio.run(scenario())
    assert runtime.store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE kind='authoritative_event'"
    ).fetchone()[0] == 1
    token_id = f"solana:{address}"
    token = runtime.store.db.execute("SELECT source,url FROM tokens WHERE token_id=?", (token_id,)).fetchone()
    assert (token["source"], token["url"]) == ("okx:official_listing", event["url"])
    assert runtime.store.token_detail_hydration(token_id)["status"] == "pending"
    runtime.store.close()


def test_runtime_surface_cache_is_low_frequency_and_held_pool_survives_watch_expiry(tmp_path, monkeypatch):
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "surface-inputs.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "M", "M")
    now = utcnow()
    pool = dict(token_id=token.token_id, pool_address="pool", base_mint=token.address, evidence_id=1)
    runtime._pattern_pool_targets = {"pool": pool}
    runtime._pattern_pool_retry = {}
    runtime._pattern_vault_tracker = PumpSwapVaultFlowTracker(summary_seconds=10)
    runtime._pattern_watch = {token.token_id: dict(token=token, pair_address="pool",
        expires_at=now - timedelta(seconds=1), quote=SimpleNamespace(observed_at=now), bucket="early")}
    runtime._pattern_held_tokens = {token.token_id}
    runtime.held_accounts = SimpleNamespace()
    calls = []
    async def surface(collector, candidate):
        calls.append(candidate)
        return dict(status="RESOLVED", complete=True, surface="NORMAL_DIRECT", observed_at=iso(now), recorded_at=iso(now))
    monkeypatch.setattr("memetrader.runtime.collect_pumpswap_pool_surface", surface)
    async def scenario():
        runtime._remember_pattern_quotes({})
        assert token.token_id in runtime._pattern_watch
        await runtime.chain_meme_pattern_pools_once()
        await runtime.chain_meme_pattern_pools_once()
        assert len(calls) == 1 and "pool" in runtime._pattern_pool_targets
        assert runtime._pattern_surface_cache["pool"]["surface"] == "NORMAL_DIRECT"
        runtime._pattern_watch = {}
        await runtime.chain_meme_pattern_pools_once()
        assert "pool" in runtime._pattern_pool_targets
        runtime._pattern_held_tokens.clear()
        await runtime.chain_meme_pattern_pools_once()
        assert runtime._pattern_pool_targets == {} and runtime._pattern_surface_cache == {}
    asyncio.run(scenario())
    runtime.store.close()


@pytest.mark.parametrize("case", ["empty", "real_amount", "budget", "unsupported", "missing_raw", "no_route", "timeout"])
def test_capital_quote_background_uses_real_raw_shared_budget_and_cancels_timeout(case):
    from memetrader.collectors import SOLANA_USDC_MINT, JupiterNoRouteError
    runtime = Runtime.__new__(Runtime)
    task = dict(token_id="solana:" + str(Pubkey.new_unique()), pair_address="pool", arm_id="arm",
                shadow_cohort_id=1, mark_id=7, input_amount_raw=12_345,
                requested_synthetic_amount_raw=999_000_000_000, mint_decimals=6, kind="exit")
    if case == "unsupported":
        task["token_id"] = "bsc:0x123"
    elif case == "missing_raw":
        del task["input_amount_raw"]
    calls, recorded, cancellations = [], [], []
    expected_quote = dict(input_mint=task["token_id"].partition(":")[2], in_amount="12345",
        output_mint=SOLANA_USDC_MINT, out_amount="1100000", other_amount_threshold="1000000",
        slippage_bps=400, route_plan=[dict(amm_key="pool")])
    async def quote(*args, **kwargs):
        calls.append((args, kwargs))
        if case == "no_route":
            raise JupiterNoRouteError("No route")
        if case == "timeout":
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellations.append(True)
                raise
        return expected_quote
    runtime.jupiter = SimpleNamespace(quote=quote)
    runtime.store = SimpleNamespace(due_capital_quote=lambda **kwargs: None if case == "empty" else task,
        record_capital_quote=lambda *args, **kwargs: recorded.append((args, kwargs)), heartbeat=lambda *args, **kwargs: None)
    async def scenario():
        runtime._jupiter_background_dispatch_lock = asyncio.Lock()
        runtime._jupiter_quote_lock = asyncio.Lock()
        runtime._jupiter_background_epoch_started = asyncio.get_running_loop().time()
        runtime._jupiter_background_epoch_seconds = 5
        runtime._jupiter_background_epoch_requests = 3 if case == "budget" else 0
        await runtime.capital_quote_once()
        if case != "timeout":
            await runtime.capital_quote_once()
        if case in {"empty", "budget"}:
            assert not calls and not recorded
            return
        assert len(recorded) == 1 and recorded[0][0][0] is task
        if case in {"unsupported", "missing_raw"}:
            assert not calls and recorded[0][0][1] is None
            return
        assert calls == [((task["token_id"].partition(":")[2], SOLANA_USDC_MINT, 12_345), {"slippage_bps": 400})]
        assert runtime._jupiter_background_epoch_requests == 1
        if case == "real_amount":
            assert recorded[0][0][1] is expected_quote
            assert recorded[0][1]["error_code"] == ""
        else:
            assert recorded[0][0][1] is None
            assert recorded[0][1]["error_code"] == ("QUOTE_TIMEOUT" if case == "timeout" else "NO_ROUTE")
        if case == "timeout":
            assert cancellations == [True]
        assert not runtime._jupiter_quote_lock.locked()
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
