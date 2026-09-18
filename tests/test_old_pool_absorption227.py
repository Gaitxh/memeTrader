from datetime import timedelta

from memetrader.activity_tempo193 import ARM as PARENT, policy as tempo_policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import iso, utcnow
from memetrader.old_pool_absorption227 import ARM, Tracker, policy
from memetrader.store import Store


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def frame(at, **overrides):
    value = {
        "chain": "solana", "token_id": TOKEN, "pair_address": POOL,
        "provider": "dexscreener", "observed_at": iso(at),
        "ingested_at": iso(at), "recorded_at": iso(at),
        "price_usd": .01, "liquidity_usd": 5000,
        "volume_5m_usd": 900, "pool_age_seconds": 7 * 3600,
        "buys_5m": 5, "sells_5m": 8,
    }
    value.update(overrides)
    return value


def test_three_distinct_asof_frames_emit_only_after_breakout():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=1))
    assert tracker.accept(frame(at), at, floor=1000) is None
    second = at + timedelta(seconds=30)
    assert tracker.accept(frame(second, buys_5m=8, sells_5m=3), second, floor=1000) is None
    third = second + timedelta(seconds=30)
    signal = tracker.accept(frame(third, price_usd=.0109, buys_5m=9, sells_5m=2),
                            third, floor=1000)
    assert signal is not None
    assert signal["selected"] == {"token_id": TOKEN, "pair_address": POOL}
    assert signal["decision_evidence"]["first_sells_5m"] == 8
    assert signal["decision_evidence"]["first_observed_at"] == iso(at)
    assert tracker.accept(frame(third + timedelta(seconds=30), price_usd=.02),
                          third + timedelta(seconds=30), floor=1000) is None


def test_invalid_or_future_first_frame_never_starts_signal():
    at = utcnow()
    bad = [
        {"sells_5m": 0}, {"buys_5m": None}, {"liquidity_usd": None},
        {"liquidity_usd": 1500}, {"pool_age_seconds": 3599},
        {"volume_5m_usd": None}, {"volume_5m_usd": 100},
        {"ingested_at": iso(at + timedelta(seconds=1))},
        {"recorded_at": None},
    ]
    for fields in bad:
        tracker = Tracker(at - timedelta(seconds=1))
        assert tracker.accept(frame(at, **fields), at, floor=1000) is None
        second = at + timedelta(seconds=30)
        assert tracker.accept(frame(second, buys_5m=8, sells_5m=3), second, floor=1000) is None
        third = second + timedelta(seconds=30)
        assert tracker.accept(frame(third, price_usd=.0109), third, floor=1000) is None, fields
    assert Tracker(at - timedelta(seconds=1)).accept(frame(at),
                                                       at + timedelta(seconds=31), floor=1000) is None


def test_broken_depth_or_wrong_pool_cannot_complete_sequence():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=1))
    assert tracker.accept(frame(at), at, floor=1000) is None
    second = at + timedelta(seconds=30)
    assert tracker.accept(frame(second, liquidity_usd=4900, buys_5m=8, sells_5m=3),
                          second, floor=1000) is None
    third = second + timedelta(seconds=30)
    assert tracker.accept(frame(third, price_usd=.011), third, floor=1000) is None
    other = Tracker(at - timedelta(seconds=1))
    assert other.accept(frame(at), at, floor=1000) is None
    assert other.accept(frame(second, pair_address="3RTC33FgYgtbhEzXdRgNb2oaVuGPTSyUMkwWPJLx7NBX"),
                        second, floor=1000) is None
    assert other.accept(frame(third, price_usd=.011), third, floor=1000) is None


def test_policy_registers_append_only_with_small_budget(tmp_path):
    store = Store(tmp_path / "absorption227.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        seed = next(item for item in alpha149_policies(cohort_experiment_policies()[2])
                    if item["arm_id"] == "alpha149_wide_decorr_young_v1")
        store.append_chain_meme_trader_policy(seed)
        store.append_chain_meme_trader_policy(tempo_policy(seed))
        parent = store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)["definition_json"],
        )["policies"]
        trial = policy(next(item for item in parent if item["arm_id"] == PARENT))
        assert trial["entry_match_mode"] == "isolated_cohort_observer"
        assert trial["max_hold_minutes"] == 5
        assert trial["entry_filter"]["max_concurrent_positions"] == 2
        assert trial["hard_stop_return"] == next(item for item in parent if item["arm_id"] == PARENT)["hard_stop_return"]
        assert store.register_chain_meme_old_pool_absorption227() == 1
        assert store.register_chain_meme_old_pool_absorption227() == 0
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id=?", (ARM,),
        ).fetchone()[0] == 1
        effective = store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)["definition_json"],
        )["policies"]
        assert next(item for item in effective if item["arm_id"] == ARM)["entry_filter"][
            "max_concurrent_positions"] == 8
    finally:
        store.close()
