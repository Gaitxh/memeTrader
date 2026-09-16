from datetime import timedelta

from memetrader.activity_confirm211 import ARM, PARENT, Tracker, policy
from memetrader.activity_tempo193 import Tracker as TempoTracker
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_activity_tempo193 import TOKEN, POOL, frame
from test_l0_store import _snapshot


def trigger(at):
    source = TempoTracker(at - timedelta(seconds=1)).accept(frame(at), at, floor=1000)
    assert source is not None
    tracker = Tracker(at - timedelta(seconds=1))
    tracker.begin(source, frame(at), at)
    return tracker, source


def test_confirmation_requires_distinct_fresh_persistent_same_pool_frame():
    at = utcnow()
    tracker, source = trigger(at)
    assert tracker.accept(frame(at), at, floor=1000) is None
    delayed = at + timedelta(seconds=20)
    for values in (
        {"provider": "geckoterminal"}, {"pair_address": "other-pool"},
        {"price_usd": .009}, {"liquidity_usd": 4999},
        {"buys_5m": 1}, {"sells_5m": 0},
        {"recorded_at": iso(delayed + timedelta(seconds=1))},
    ):
        assert tracker.accept(frame(delayed, **values), delayed, floor=1000) is None
    confirmed = tracker.accept(frame(delayed), delayed, floor=1000)
    assert confirmed is not None
    assert confirmed["decision_evidence"]["trigger_decision_key"] == source["decision_key"]
    assert confirmed["observed_at"] > source["observed_at"]
    assert tracker.accept(frame(delayed + timedelta(seconds=1)), delayed + timedelta(seconds=1), floor=1000) is None


def test_short_long_stale_and_future_confirmation_refused():
    at = utcnow()
    tracker, _ = trigger(at)
    assert tracker.accept(frame(at + timedelta(seconds=14)), at + timedelta(seconds=14), floor=1000) is None
    assert tracker.accept(frame(at + timedelta(seconds=20)), at + timedelta(seconds=51), floor=1000) is None
    assert tracker.accept(frame(at + timedelta(seconds=61)), at + timedelta(seconds=61), floor=1000) is None
    assert tracker.accept(frame(at + timedelta(seconds=21)), at + timedelta(seconds=21), floor=1000) is None
    tracker, _ = trigger(at)
    assert tracker.accept(frame(at + timedelta(seconds=20), ingested_at=iso(at + timedelta(seconds=22))),
                          at + timedelta(seconds=21), floor=1000) is None


def test_append_only_parent_exit_and_next_quote_fill(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "confirm211.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        seed = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == "alpha149_wide_decorr_young_v1")
        store.append_chain_meme_trader_policy(seed)
        store.register_chain_meme_activity_tempo193()
        store.register_chain_meme_activity_tempo_fast200()
        registration = store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
        definition = store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION, registration["definition_json"])
        parent = next(p for p in definition["policies"] if p["arm_id"] == PARENT)
        assert store.register_chain_meme_activity_confirm211() == 1
        assert store.register_chain_meme_activity_confirm211() == 0
        trial = policy(parent)
        assert trial["max_hold_minutes"] == parent["max_hold_minutes"] == 5
        assert trial["hard_stop_return"] == parent["hard_stop_return"]
        assert trial["entry_match_mode"] == "isolated_cohort_observer"
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Tempo", "TMP")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        tracker, _ = trigger(clock[0])
        clock[0] += timedelta(seconds=20)
        signal = tracker.accept(frame(clock[0]), clock[0], floor=1000)
        assert signal is not None
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 0
        clock[0] += timedelta(seconds=7)
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 1
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,),
        ).fetchone()
        assert position["opened_at"] > signal["observed_at"]
        assert position["source_entry_fill_id"] is not None
    finally:
        store.close()
