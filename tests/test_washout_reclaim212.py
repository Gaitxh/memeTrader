from datetime import timedelta
from types import SimpleNamespace

from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from memetrader.washout_reclaim212 import (
    ARM, PARENT, advance, alias_signal, frozen_anchor, policy,
)
from test_l0_store import _snapshot
from test_core import _seed_chain_market_position


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def source_signal(at):
    return {
        "decision_key": f"washout:{iso(at)}", "episode_id": f"washout:{iso(at)}",
        "selected": {"token_id": TOKEN, "pair_address": POOL},
        "observed_at": iso(at), "recorded_at": iso(at),
        "decision_evidence": {"feature_vector": {
            "pair_address": POOL, "observed_at": iso(at), "ingested_at": iso(at),
            "prev": {"price_usd": .009, "observed_at": iso(at - timedelta(seconds=10))},
        }},
    }


def test_alias_freezes_pre_reclaim_observation_without_future_data():
    at = utcnow()
    alias = alias_signal(source_signal(at))
    assert alias["decision_evidence"]["reclaim_anchor212"]["price_usd"] == .009
    assert frozen_anchor(alias, at + timedelta(seconds=1)) is not None
    assert frozen_anchor(alias, at - timedelta(seconds=1)) is None
    assert alias_signal({**source_signal(at), "decision_evidence": {"feature_vector": {
        "prev": {"price_usd": .009, "observed_at": iso(at + timedelta(seconds=1))},
    }}}) is None


def test_anchor_exit_requires_two_distinct_ordered_marks_and_recovery_resets():
    at = utcnow()
    opened = at - timedelta(seconds=1)
    state, exit_now = advance({}, anchor=.009, price=.008, sequence=1,
                              observed_at=at, opened_at=opened, pair_address=POOL)
    assert not exit_now
    assert not advance(state, anchor=.009, price=.008, sequence=1,
                       observed_at=at, opened_at=opened, pair_address=POOL)[1]
    assert not advance(state, anchor=.009, price=.008, sequence=2,
                       observed_at=at, opened_at=opened, pair_address="wrong-pool")[1]
    assert advance(state, anchor=.009, price=.008, sequence=2,
                   observed_at=at + timedelta(seconds=20),
                   opened_at=opened, pair_address=POOL)[1]
    assert not advance(state, anchor=.009, price=.008, sequence=2,
                       observed_at=at + timedelta(seconds=61),
                       opened_at=opened, pair_address=POOL)[1]
    recovered, exit_now = advance(state, anchor=.009, price=.01, sequence=2,
                                  observed_at=at + timedelta(seconds=20),
                                  opened_at=opened, pair_address=POOL)
    assert not exit_now and "reclaim_anchor212" not in recovered
    assert not advance(recovered, anchor=.009, price=.008, sequence=3,
                       observed_at=at + timedelta(seconds=30),
                       opened_at=opened, pair_address=POOL)[1]


def test_append_and_forward_position_freezes_anchor(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "washout212.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        assert store.register_chain_meme_washout_reclaim212() == 1
        assert store.register_chain_meme_washout_reclaim212() == 0
        trial = policy(parent)
        assert trial["hard_stop_return"] == parent["hard_stop_return"]
        assert trial["max_hold_minutes"] == parent["max_hold_minutes"] == 120
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Wash", "W")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        signal = alias_signal(source_signal(clock[0]))
        assert signal is not None
        features = {"observed_at": iso(clock[0]), "continuity_started_at": iso(clock[0] - timedelta(seconds=10)),
                    "windows": {"30": {"frames": 2}}}
        engine = SimpleNamespace(pools={(TOKEN, POOL): {"features": features}})
        monkeypatch.setattr(store, "_trajectory_engine_for", lambda policy: engine)
        store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        )
        clock[0] += timedelta(seconds=7)
        features["observed_at"] = iso(clock[0])
        store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        )
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,),
        ).fetchone()
        assert position is not None, [
            store._json_object(r[0]).get("outcomes") for r in store.db.execute(
                "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 3"
            )
        ]
        assert position["opened_at"] > signal["observed_at"]
        assert store._json_object(position["capital_exit_state_json"])[
            "reclaim_anchor212_frozen"]["price_usd"] == .009
    finally:
        store.close()


def test_confirmed_anchor_exit_waits_for_next_fresh_fill(tmp_path):
    path = tmp_path / "anchor-exit.sqlite3"
    store = Store(path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        store.register_chain_meme_washout_reclaim212()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        definition = store._chain_meme_trader_effective_definition(
            version, store._chain_meme_trader_registration(version)["definition_json"])
        trial = next(p for p in definition["policies"] if p["arm_id"] == ARM)
        opened = utcnow() - timedelta(minutes=2)
        token, cohort = _seed_chain_market_position(
            store, version=version, policy=trial, opened_at=opened)
        store.db.execute(
            "UPDATE chain_meme_trader_positions SET capital_exit_state_json=? "
            "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
            (store._json({"reclaim_anchor212_frozen": {"price_usd": .98,
                "observed_at": iso(opened - timedelta(seconds=10)),
                "signal_observed_at": iso(opened - timedelta(seconds=5))}}),
             version, ARM, cohort),
        )

        def mark(at, price):
            store.upsert_chain_meme_trader_market_mark(token, _snapshot(
                token, "pair-A", at, price=price, liquidity=50_000), recorded_at=at)
            store.evaluate_chain_meme_trader_market_marks(
                definition_version=version, now=at)

        first = opened + timedelta(seconds=60)
        mark(first, .97)
        assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_marks WHERE arm_id=?",
                                (ARM,)).fetchone()[0] == 0
    finally:
        store.close()

    store = Store(path, initial_cash_usd=1000)
    try:
        second = first + timedelta(seconds=5)
        store.upsert_chain_meme_trader_market_mark(token, _snapshot(
            token, "pair-A", second, price=.96, liquidity=50_000), recorded_at=second)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=second)
        pending = store.db.execute("SELECT status,action FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1", (version, ARM)).fetchone()
        assert tuple(pending) == ("pending", "RECLAIM_FAILURE_EXIT")
        assert store.db.execute("SELECT status FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
            (version, ARM, cohort)).fetchone()[0] == "open"
        third = second + timedelta(seconds=5)
        store.upsert_chain_meme_trader_market_mark(token, _snapshot(
            token, "pair-A", third, price=.95, liquidity=50_000), recorded_at=third)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=third)
        assert store.db.execute("SELECT status FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
            (version, ARM, cohort)).fetchone()[0] != "open"
    finally:
        store.close()
