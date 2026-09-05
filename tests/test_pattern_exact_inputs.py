import asyncio
from datetime import timedelta
from types import SimpleNamespace

from solders.pubkey import Pubkey

from memetrader.collectors import PumpSwapVaultFlowTracker
from memetrader.forward_patterns import experiment_policies, pattern_signal
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
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
