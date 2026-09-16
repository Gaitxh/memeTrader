from datetime import timedelta

from memetrader.migration_first209 import ARM, PARENT, Tracker, policy
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_l0_store import _snapshot


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def fact(at):
    return {"id": 7, "chain": "solana", "token_id": TOKEN,
            "launch_event_type": "migration", "source_observed_at": iso(at),
            "ingested_at": iso(at), "recorded_at": iso(at)}


def frame(at, **changes):
    result = {"chain": "solana", "provider_chain_id": "solana",
              "provider_dex_id": "pumpswap", "provider_base_address": TOKEN.split(":")[1],
              "provider": "strategy-observer:dexscreener", "token_id": TOKEN, "pair_address": POOL,
              "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
              "price_usd": .01, "liquidity_usd": 5000, "pool_age_seconds": 60,
              "buys_5m": 3, "sells_5m": 1}
    result.update(changes)
    return result


def test_first_new_pool_signal_requires_locally_received_fact_and_exact_identity():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=1))
    assert tracker.accept(frame(at), at, floor=1000) is None
    tracker.observe_fact(fact(at), at)
    bad = [
        {"provider_base_address": "other"}, {"provider_dex_id": "pumpfun"},
        {"provider_chain_id": "ethereum"}, {"provider": "geckoterminal"},
        {"sells_5m": 0}, {"liquidity_usd": 900}, {"pool_age_seconds": 301},
        {"observed_at": iso(at - timedelta(seconds=1))},
        {"ingested_at": iso(at + timedelta(seconds=1))},
    ]
    for values in bad:
        assert tracker.accept(frame(at, **values), at, floor=1000) is None
    signal = tracker.accept(frame(at), at, floor=1000)
    assert signal is not None and signal["selected"]["pair_address"] == POOL
    assert signal["decision_evidence"]["migration_fact_id"] == 7
    assert tracker.accept(frame(at + timedelta(seconds=1)), at + timedelta(seconds=1), floor=1000) is None


def test_stale_future_and_pre_activation_facts_never_create_hindsight_entry():
    at = utcnow()
    tracker = Tracker(at)
    tracker.observe_fact(fact(at - timedelta(seconds=1)), at)
    assert tracker.accept(frame(at), at, floor=1000) is None
    tracker.observe_fact(fact(at + timedelta(seconds=1)), at)
    assert tracker.accept(frame(at), at, floor=1000) is None
    tracker.observe_fact(fact(at), at)
    assert tracker.accept(frame(at + timedelta(seconds=301)), at + timedelta(seconds=301), floor=1000) is None
    assert tracker.accept(frame(at + timedelta(seconds=1), recorded_at=iso(at + timedelta(seconds=2))),
                          at + timedelta(seconds=1), floor=1000) is None


def test_policy_registers_and_requires_next_observed_paper_fill(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "migration209.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        registration = store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
        definition = store._chain_meme_trader_effective_definition(
            store.CHAIN_MEME_TRADER_ACTIVE_VERSION, registration["definition_json"])
        parent = next(p for p in definition["policies"] if p["arm_id"] == PARENT)
        assert store.register_chain_meme_migration_first209() == 1
        assert store.register_chain_meme_migration_first209() == 0
        row = store.db.execute(
            "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions WHERE arm_id=?",
            (ARM,),
        ).fetchone()
        assert row is not None
        trial = policy(parent)
        assert trial["entry_match_mode"] == "isolated_cohort_observer"
        assert trial["max_hold_minutes"] == parent["max_hold_minutes"]
        assert trial["entry_filter"]["max_concurrent_positions"] == 2
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Migration", "MIG")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        tracker = Tracker(clock[0] - timedelta(seconds=1))
        tracker.observe_fact(fact(clock[0]), clock[0])
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
        assert position["source_entry_fill_id"] is not None
        assert position["opened_at"] > signal["observed_at"]
    finally:
        store.close()
