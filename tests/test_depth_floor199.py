from datetime import timedelta

from memetrader.depth_cross191 import Tracker as OldTracker
from memetrader.depth_floor199 import ARM, Tracker, policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenCandidate, utcnow
from memetrader.store import Store
from test_depth_cross191 import PARENT, POOL, TOKEN, frame
from test_l0_store import _snapshot


def test_first_floor_cross_is_earlier_than_old_depth_signal():
    start = utcnow()
    early = Tracker(start - timedelta(seconds=1))
    old = OldTracker(start - timedelta(seconds=1))
    for tracker in (early, old):
        assert tracker.accept(frame(start, 800), start, floor=1000) is None
    at = start + timedelta(seconds=15)
    signal = early.accept(frame(at, 1100), at, floor=1000)
    assert signal is not None
    assert signal["decision_evidence"]["mode"] == ARM
    assert signal["decision_evidence"]["effective_pool_floor_usd"] == 1000
    assert old.accept(frame(at, 1100), at, floor=1000) is None


def test_floor_cross_refuses_cross_provider_stale_and_buy_only():
    start = utcnow()
    tracker = Tracker(start - timedelta(seconds=1))
    low = frame(start, 700)
    low["provider"] = "dexscreener"
    assert tracker.accept(low, start, floor=1000) is None
    at = start + timedelta(seconds=15)
    assert tracker.accept(frame(at, 1200), at, floor=1000) is None
    high = frame(at, 1200, sells=0)
    high["provider"] = "dexscreener"
    assert tracker.accept(high, at, floor=1000) is None
    at += timedelta(seconds=1)
    stale = frame(at, 1200)
    stale["provider"] = "dexscreener"
    assert tracker.accept(stale, at + timedelta(seconds=46), floor=1000) is None
    assert tracker.accept(stale, at, floor=1000) is not None


def test_floor_policy_adds_one_account_without_changing_shared_floor(tmp_path):
    store = Store(tmp_path / "depth199.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        seed = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(seed)
        parent = next(p for p in store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            store._chain_meme_trader_registration(
                store.CHAIN_MEME_TRADER_ACTIVE_VERSION)["definition_json"],
        )["policies"] if p["arm_id"] == PARENT)
        candidate = policy(parent)
        assert candidate["notional_usd"] == 20
        assert candidate["hard_stop_return"] == parent["hard_stop_return"]
        assert candidate["entry_filter"]["max_concurrent_positions"] == 8
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_depth_floor199() == 1
        assert store.register_chain_meme_depth_floor199() == 0
        row = store.db.execute(
            "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM),
        ).fetchone()
        assert row[0] == frontier
    finally:
        store.close()


def test_floor_signal_waits_for_independent_post_signal_quote(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "depth199-entry.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        assert store.register_chain_meme_depth_floor199() == 1
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Depth", "DEP")
        store.upsert_token(token, seen_at=clock[0])
        tracker = Tracker(clock[0])
        clock[0] += timedelta(seconds=1)
        assert tracker.accept(frame(clock[0], 700), clock[0], floor=1000) is None
        clock[0] += timedelta(seconds=20)
        signal = tracker.accept(frame(clock[0], 1100), clock[0], floor=1000)
        assert signal is not None
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=1100),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 0
        clock[0] += timedelta(seconds=7)
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=1100),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 1
        row = store.db.execute("SELECT stake_usd,opened_at FROM chain_meme_trader_positions "
                               "WHERE arm_id=?", (ARM,)).fetchone()
        assert row["stake_usd"] == 20 and row["opened_at"] > signal["observed_at"]
    finally:
        store.close()
