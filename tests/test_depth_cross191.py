from datetime import timedelta

from memetrader.depth_cross191 import ARM, ARMS, FAST_ARM, PARENT, Tracker, policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import iso, utcnow
from memetrader.models import TokenCandidate
from memetrader.store import Store
from test_l0_store import _snapshot


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def frame(at, liquidity, *, price=1.0, pool=POOL, buys=7, sells=4):
    return {
        "chain": "solana", "token_id": TOKEN, "pair_address": pool,
        "provider": "geckoterminal", "observed_at": iso(at),
        "ingested_at": iso(at), "recorded_at": iso(at),
        "pool_age_seconds": 170, "price_usd": price,
        "liquidity_usd": liquidity, "buys_5m": buys, "sells_5m": sells,
    }


def test_same_pool_depth_crossing_can_signal_before_price_momentum():
    start = utcnow()
    tracker = Tracker(start - timedelta(seconds=1))
    assert tracker.accept(frame(start, 779.48), start, floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=30), 1300),
                          start + timedelta(seconds=30), floor=1000) is None
    signal = tracker.accept(frame(start + timedelta(seconds=90), 11196.3, price=.9),
                            start + timedelta(seconds=90), floor=1000)
    assert signal["decision_evidence"]["low_liquidity_usd"] == 779.48
    assert signal["decision_evidence"]["cross_liquidity_usd"] == 11196.3
    assert signal["decision_evidence"]["cross_price_usd"] == .9
    assert signal["selected"] == {"token_id": TOKEN, "pair_address": POOL}
    assert tracker.accept(frame(start + timedelta(seconds=91), 12000),
                          start + timedelta(seconds=91), floor=1000) is None


def test_missing_low_other_pool_stale_or_buy_only_never_crosses():
    start = utcnow()
    tracker = Tracker(start - timedelta(seconds=1))
    missing = frame(start, None)
    assert tracker.accept(missing, start, floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=20), 3000),
                          start + timedelta(seconds=20), floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=30), 500),
                          start + timedelta(seconds=30), floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=50), 3000, pool=TOKEN.split(":", 1)[1]),
                          start + timedelta(seconds=50), floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=60), 3000, buys=5, sells=0),
                          start + timedelta(seconds=60), floor=1000) is None
    tracker = Tracker(start - timedelta(seconds=1))
    assert tracker.accept(frame(start, 500), start, floor=1000) is None
    assert tracker.accept(frame(start + timedelta(seconds=301), 3000),
                          start + timedelta(seconds=301), floor=1000) is None
    future = frame(start + timedelta(seconds=310), 400)
    assert tracker.accept(future, start + timedelta(seconds=309), floor=1000) is None
    missing_time = frame(start + timedelta(seconds=311), 400)
    missing_time["ingested_at"] = None
    assert tracker.accept(missing_time, start + timedelta(seconds=311), floor=1000) is None


def test_policy_is_small_forward_only_and_registers_once(tmp_path):
    store = Store(tmp_path / "depth191.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent_seed = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                           if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent_seed)
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        registration = store._chain_meme_trader_registration(version)
        definition = store._chain_meme_trader_effective_definition(
            version, registration["definition_json"])
        parent = next(p for p in definition["policies"] if p["arm_id"] == PARENT)
        trial = policy(parent)
        assert trial["notional_usd"] == 20.0
        assert trial["entry_filter"]["max_concurrent_positions"] == 8
        assert trial["entry_filter"]["single_token_lifetime_entry"]
        assert not trial["requires_distinct_wide_frame"]
        assert trial["hard_stop_return"] == parent["hard_stop_return"]
        fast = policy(parent, FAST_ARM)
        assert fast["max_hold_minutes"] == 5
        assert trial["max_hold_minutes"] == 30
        assert fast["hard_stop_return"] == trial["hard_stop_return"]
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_depth_cross191() == 2
        assert store.register_chain_meme_depth_cross191() == 0
        for arm in ARMS:
            row = store.db.execute(
                "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions "
                "WHERE definition_version=? AND arm_id=?", (version, arm),
            ).fetchone()
            assert row["activation_snapshot_id"] == frontier
    finally:
        store.close()


def test_signal_reaches_cohort_and_only_next_observed_quote_buys(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "depth191-entry.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent_seed = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                           if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent_seed)
        assert store.register_chain_meme_depth_cross191() == 2
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Depth", "DEP")
        store.upsert_token(token, seen_at=clock[0])
        tracker = Tracker(clock[0])
        clock[0] += timedelta(seconds=1)
        assert tracker.accept(frame(clock[0], 500), clock[0], floor=1000) is None
        clock[0] += timedelta(seconds=20)
        signal = tracker.accept(frame(clock[0], 3000), clock[0], floor=1000)
        assert signal is not None
        signals = {arm: {**signal, "decision_key": signal["decision_key"] + ":" + arm}
                   for arm in ARMS}
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=3000),
            recorded_at=clock[0], cohort_signals=signals,
        ) == 0
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)
        ).fetchone()[0] == 0
        clock[0] += timedelta(seconds=7)
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=3000),
            recorded_at=clock[0], cohort_signals=signals,
        ) == 2
        positions = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id IN (?,?) ORDER BY arm_id",
            ARMS,
        ).fetchall()
        assert len(positions) == 2
        assert {row["arm_id"] for row in positions} == set(ARMS)
        assert {row["source_entry_fill_id"] for row in positions} == {
            positions[0]["source_entry_fill_id"]
        }
        assert all(row["stake_usd"] == 20 and row["opened_at"] > signal["observed_at"]
                   for row in positions)
    finally:
        store.close()


def test_research_review_is_manual_by_default():
    import inspect
    from memetrader import runtime

    source = inspect.getsource(runtime.Runtime)
    assert ".get('review_enabled', False)" in source
