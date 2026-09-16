from datetime import timedelta

from memetrader.migration_confirm214 import ARM, PARENT, Tracker, policy
from memetrader.migration_first209 import Tracker as FirstTracker
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_l0_store import _snapshot
from test_migration_first209 import POOL, TOKEN, fact, frame


def first_signal(at):
    first = FirstTracker(at - timedelta(seconds=1))
    first.observe_fact(fact(at), at)
    signal = first.accept(frame(at), at, floor=1000)
    assert signal is not None
    return signal


def test_confirmation_uses_distinct_fresh_same_pool_frame():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=1))
    signal = first_signal(at)
    tracker.begin(signal, frame(at), at)
    second = frame(at + timedelta(seconds=15), buys_5m=6, sells_5m=2,
                   price_usd=.009, liquidity_usd=4200, pool_age_seconds=75)
    assert tracker.accept(frame(at, buys_5m=6), at, floor=1000) is None
    for change in (
        {"pair_address": "another"}, {"provider_base_address": "other"},
        {"provider": "geckoterminal"}, {"provider_dex_id": "pumpfun"},
        {"sells_5m": 0}, {"buys_5m": 4}, {"price_usd": .008},
        {"price_usd": .016}, {"liquidity_usd": 3000},
        {"ingested_at": iso(at + timedelta(seconds=16))},
    ):
        assert tracker.accept({**second, **change}, at + timedelta(seconds=15), floor=1000) is None
    accepted = tracker.accept(second, at + timedelta(seconds=15), floor=1000)
    assert accepted is not None
    assert accepted["decision_evidence"]["trigger_decision_key"] == signal["decision_key"]
    assert accepted["observed_at"] == iso(at + timedelta(seconds=15))
    assert tracker.accept(second, at + timedelta(seconds=15), floor=1000) is None


def test_stale_and_future_frame_never_confirms():
    at = utcnow()
    tracker = Tracker(at)
    tracker.begin(first_signal(at), frame(at), at)
    assert tracker.accept(frame(at + timedelta(seconds=91), buys_5m=6),
                          at + timedelta(seconds=91), floor=1000) is None
    tracker.begin(first_signal(at), frame(at), at)
    assert tracker.accept(frame(at + timedelta(seconds=15), buys_5m=6,
                                recorded_at=iso(at + timedelta(seconds=16))),
                          at + timedelta(seconds=15), floor=1000) is None
    assert tracker.accept(frame(at + timedelta(seconds=15), buys_5m=6,
                                ingested_at=iso(at + timedelta(seconds=14))),
                          at + timedelta(seconds=15), floor=1000) is None


def test_register_and_enter_only_after_next_quote(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "migration214.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        assert store.register_chain_meme_migration_first209() == 1
        assert store.register_chain_meme_migration_confirm214() == 1
        assert store.register_chain_meme_migration_confirm214() == 0
        definition = store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            store._chain_meme_trader_registration(
                store.CHAIN_MEME_TRADER_ACTIVE_VERSION)["definition_json"],
        )
        parent = next(p for p in definition["policies"] if p["arm_id"] == PARENT)
        trial = policy(parent)
        assert trial["max_hold_minutes"] == parent["max_hold_minutes"]
        assert trial["entry_filter"]["max_concurrent_positions"] == 2
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Migration", "MIG")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        tracker = Tracker(clock[0] - timedelta(seconds=1))
        signal = first_signal(clock[0])
        tracker.begin(signal, frame(clock[0]), clock[0])
        clock[0] += timedelta(seconds=15)
        second = tracker.accept(frame(clock[0], buys_5m=6, sells_5m=2), clock[0], floor=1000)
        assert second is not None
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: second},
        ) == 0
        clock[0] += timedelta(seconds=7)
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: second},
        ) == 1
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,),
        ).fetchone()
        assert position["source_entry_fill_id"] is not None
        assert position["opened_at"] > second["observed_at"]
    finally:
        store.close()
