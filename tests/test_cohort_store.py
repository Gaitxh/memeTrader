from datetime import timedelta
import json

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_l0_store import _snapshot


def test_cohort_namespace_next_fill_and_old_primary_frontier(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "cohort.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    assert store.register_chain_meme_cohort_experiments() == 5
    assert store.register_chain_meme_cohort_experiments() == 0
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "Cohort", "C")
    pair = str(Pubkey.new_unique())
    clock[0] += timedelta(seconds=1)
    at = clock[0]
    store.upsert_token(token)
    primary = store.add_snapshot(_snapshot(token, pair, at))
    store.observe_chain_meme_pattern(token, _snapshot(token, pair, at), recorded_at=at)
    old = dict(store.db.execute("SELECT * FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE reason='pattern_observation' ORDER BY id DESC LIMIT 1").fetchone())
    arm = "clone_liquidity_leader_v1"
    signal = {arm: {"episode_id": "episode1", "decision_key": "episode1|" + arm,
        "selected": {"token_id": token.token_id, "pair_address": pair},
        "observed_at": iso(at), "recorded_at": iso(at), "decision_evidence": {}}}
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, at),
        recorded_at=at, cohort_signals=signal) == 0
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, at),
        recorded_at=at, cohort_signals=signal) == 0
    # A new observer row cannot jump the ordinary discovery cursor past primary.
    assert store.enroll_chain_meme_trader_v6(definition_version=version)["evaluated"] == 1
    assert store.db.execute("SELECT 1 FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE source_snapshot_id=? AND reason NOT IN ('pattern_observation','cohort_observation')", (primary,)).fetchone()
    clock[0] += timedelta(seconds=6)
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]),
        recorded_at=clock[0], cohort_signals={}) == 1
    pos = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (arm,)).fetchone()
    assert pos["stake_usd"] == 5
    assert pos["paper_quantity_tokens"] == pytest.approx(5 / (2 * 1.04))
    assert store.db.execute("SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?", (arm,)).fetchone()[0] == -5
    assert dict(store.db.execute("SELECT * FROM chain_meme_trader_v6_entry_evaluations WHERE id=?", (old["id"],)).fetchone()) == old
    clock[0] += timedelta(seconds=6)
    assert store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]),
        recorded_at=clock[0], cohort_signals=signal) == 0
    # Same-original-pool shared mark closes independently and accounts two 4% sides.
    for step in (6, 12):
        clock[0] += timedelta(seconds=step)
        store.upsert_chain_meme_trader_market_mark(token, _snapshot(token, pair, clock[0], price=.5), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=clock[0], token_ids=[token.token_id])
    closed = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (arm,)).fetchone()
    assert closed["status"] == "closed"
    pnl = store.db.execute("SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?", (arm,)).fetchone()[0]
    assert pnl == pytest.approx(5 / (2 * 1.04) * .5 * .96 - 5)
    store.close()


def test_passive_broad_arms_cannot_leak_into_regular_twenty_dollar_lane(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "isolated-broad.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_staged_probe()
    store.register_chain_meme_wallet_observers()
    token, pair = TokenCandidate("solana", str(Pubkey.new_unique()), "Broad", "BRD"), str(Pubkey.new_unique())
    clock[0] += timedelta(seconds=5)
    store.upsert_token(token, seen_at=clock[0])
    store.add_snapshot(_snapshot(token, pair, clock[0]))
    store.enroll_chain_meme_trader_v6(definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_entry_decisions WHERE "
        "arm_id LIKE 'staged_probe_%' OR arm_id LIKE 'watched_wallet_%'").fetchone()[0] == 0
    store.close()


def test_runtime_passive_cohort_consumes_received_batches_without_requests(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from memetrader.runtime import Runtime
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
    calls = []
    runtime = Runtime.__new__(Runtime)
    runtime._cohort_started_at = clock[0]
    runtime._cohort_state = {}
    runtime._paper_quote_rejections = lambda *args: []
    idle = asyncio.Event()
    idle.set()
    runtime._chain_meme_active_idle = lambda: idle
    runtime.store = SimpleNamespace(
        CHAIN_MEME_TRADER_ACTIVE_VERSION="test",
        chain_meme_cohort_receipts=lambda episodes: ({}, []),
        observe_chain_meme_pattern=lambda token, snap, **kw: calls.append((token, snap, kw)) or 0,
        set_kv=lambda *args: None, heartbeat=lambda *args, **kw: None,
    )
    tokens = [TokenCandidate("solana", str(Pubkey.new_unique()), "Group", f"G{i}") for i in range(3)]
    # Stable deterministic ordering for the observed-set selector.
    tokens.sort(key=lambda t: t.token_id)
    pairs = [str(Pubkey.new_unique()) for _ in tokens]
    for step in range(5):
        clock[0] += timedelta(seconds=6)
        quotes = {t.token_id: (t, _snapshot(t, p, clock[0],
            price=1 + .01 * step if i == 0 else 1 - .06 * step,
            liquidity=1000 + 10 * step if i == 0 else 1000 - 20 * step))
            for i, (t, p) in enumerate(zip(tokens, pairs))}
        runtime._remember_pattern_quotes(quotes)
        asyncio.run(runtime.chain_meme_cohort_observer_once())
        if step == 2:
            runtime._pattern_held_tokens = {tokens[0].token_id}
    signals = {arm for _, _, kw in calls for arm in kw["cohort_signals"]}
    assert "observed_set_relative_resilience_control_v1" in signals
    assert "observed_set_relative_resilience_candidate_v1" in signals


@pytest.mark.parametrize("projection_busy", [False, True])
@pytest.mark.parametrize("delay", [2, 31, 61])
def test_deferred_one_shot_keeps_original_quote_and_drains_without_new_batch(
    monkeypatch, projection_busy, delay,
):
    import asyncio
    from collections import deque
    from types import SimpleNamespace
    from memetrader.runtime import Runtime

    observed = utcnow()
    received = observed + timedelta(milliseconds=50)
    clock = [received]
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
    tokens = [TokenCandidate("solana", str(Pubkey.new_unique()), f"One shot {i}") for i in range(9)]
    pairs = [str(Pubkey.new_unique()) for _ in tokens]
    values = [(token, _snapshot(token, pair, observed)) for token, pair in zip(tokens, pairs)]
    calls = []
    consume_calls = []

    def consume(frames, state, **kwargs):
        consume_calls.append(frames)
        return state, {(t.token_id, p): {"one_shot": {
            "episode_id": f"once:{p}", "decision_key": f"once:{p}|one_shot",
            "selected": {"token_id": t.token_id, "pair_address": p},
            "decision_evidence": {"first_receipt": iso(received)},
        }} for t, p in zip(tokens, pairs)}

    monkeypatch.setattr("memetrader.cohort_experiments.consume_passive_cohort_batch", consume)
    runtime = Runtime.__new__(Runtime)
    runtime._cohort_started_at = observed - timedelta(seconds=1)
    runtime._cohort_batches = deque([(received, values)], maxlen=16)
    runtime._paper_quote_rejections = lambda *args: []
    runtime.store = SimpleNamespace(
        CHAIN_MEME_TRADER_ACTIVE_VERSION="test",
        chain_meme_cohort_receipts=lambda episodes: ({}, []),
        observe_chain_meme_pattern=lambda token, snap, **kw: calls.append((token, snap, kw)) or 0,
        set_kv=lambda *args: None, heartbeat=lambda *args, **kw: None,
    )

    async def scenario():
        idle = runtime._chain_meme_active_idle()
        if projection_busy:
            idle.clear()
        await asyncio.wait_for(runtime.chain_meme_cohort_observer_once(), timeout=1)
        assert not runtime._cohort_batches
        assert len(calls) == (0 if projection_busy else 8)
        target = (tokens[-1].token_id, pairs[-1])
        original = runtime._cohort_pending[target]
        assert original["quote"][1] is values[-1][1]
        assert original["quote"][2] == received
        clock[0] += timedelta(seconds=delay)
        idle.set()
        await runtime.chain_meme_cohort_observer_once()
        await runtime.chain_meme_cohort_observer_once()
        assert len(consume_calls) == 1  # No invented or refetched source batch.
        if delay == 2:
            assert len(calls) == 9
            assert len({t.token_id for t, _, _ in calls}) == 9
            token, snap, kwargs = next(row for row in calls if row[0].token_id == tokens[-1].token_id)
            assert snap is values[-1][1]
            assert snap.observed_at == snap.ingested_at == observed
            assert kwargs["recorded_at"] == clock[0]
            signal = kwargs["cohort_signals"]["one_shot"]
            assert signal["observed_at"] == iso(observed)
            assert signal["recorded_at"] == iso(received)
            assert signal["decision_evidence"] == {"first_receipt": iso(received)}
            assert all("quote" not in item for item in runtime._cohort_pending.values())
        else:
            assert all(t.token_id != tokens[-1].token_id for t, _, _ in calls)
            assert all("quote" not in item for item in runtime._cohort_pending.values())
            if delay == 61:
                assert not runtime._cohort_pending
    asyncio.run(scenario())
