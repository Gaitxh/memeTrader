from datetime import timedelta

import pytest

from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from memetrader.washout_confirm222 import ARM, Tracker, policy
from memetrader.washout_reclaim212 import PARENT, frozen_anchor, policy as exit_policy
from test_l0_store import _snapshot


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def frame(at, *, price=.009, liquidity=5000, sells=2, provider="dexscreener"):
    return {"chain": "solana", "token_id": TOKEN, "pair_address": POOL,
            "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
            "provider": provider, "price_usd": price, "liquidity_usd": liquidity,
            "sells_5m": sells}


def source(at):
    return {"decision_key": f"source:{iso(at)}", "selected": {
        "token_id": TOKEN, "pair_address": POOL},
        "observed_at": iso(at), "recorded_at": iso(at),
        "decision_evidence": {"feature_vector": {
            "observed_at": iso(at), "ingested_at": iso(at),
            "drawdown": -.20, "current": {"price_usd": .009},
            "prev": {"observed_at": iso(at - timedelta(seconds=10)),
                     "price_usd": .008},
        }}}


def test_delayed_half_reclaim_requires_later_fresh_original_pool_frame():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=20))
    tracker.begin(source(at), frame(at), at)
    assert tracker.accept(frame(at, price=.01), at) is None
    assert tracker.accept(frame(at + timedelta(seconds=10), price=.01,
                                provider="geckoterminal"), at + timedelta(seconds=10)) is None
    assert tracker.accept(frame(at + timedelta(seconds=20), price=.01,
                                sells=0), at + timedelta(seconds=20)) is None
    assert tracker.accept(frame(at + timedelta(seconds=30), price=.01,
                                liquidity=4900), at + timedelta(seconds=30)) is None
    confirmation_at = at + timedelta(seconds=40)
    result = tracker.accept(frame(confirmation_at, price=.010), confirmation_at)
    assert result is not None
    assert result["observed_at"] == iso(confirmation_at)
    assert result["decision_evidence"]["half_reclaim_threshold_usd"] == pytest.approx(.009625)
    assert frozen_anchor(result, confirmation_at + timedelta(seconds=1))["price_usd"] == .008
    assert tracker.accept(frame(confirmation_at, price=.010), confirmation_at) is None


def test_stale_future_cross_pool_and_pre_activation_triggers_refused():
    at = utcnow()
    tracker = Tracker(at)
    tracker.begin(source(at - timedelta(seconds=1)), frame(at - timedelta(seconds=1)), at)
    assert not tracker.pending
    wrong_feature = source(at)
    wrong_feature["decision_evidence"]["feature_vector"]["observed_at"] = iso(
        at + timedelta(seconds=1))
    tracker.begin(wrong_feature, frame(at), at)
    assert not tracker.pending
    tracker.begin(source(at), frame(at), at)
    cross = {**frame(at + timedelta(seconds=20), price=.010), "pair_address": "another"}
    assert tracker.accept(cross, at + timedelta(seconds=20)) is None
    stale = frame(at + timedelta(seconds=20), price=.010)
    assert tracker.accept(stale, at + timedelta(seconds=60)) is None
    future = frame(at + timedelta(seconds=30), price=.010)
    assert tracker.accept(future, at + timedelta(seconds=20)) is None
    assert tracker.accept(frame(at + timedelta(seconds=181), price=.010),
                          at + timedelta(seconds=181)) is None
    assert not tracker.pending


def test_policy_and_store_registration_are_append_only(tmp_path):
    store = Store(tmp_path / "washout222.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        assert store.register_chain_meme_washout_reclaim212() == 2
        assert store.register_chain_meme_washout_confirm222() == 1
        assert store.register_chain_meme_washout_confirm222() == 0
        result = policy(exit_policy(parent))
        assert result["arm_id"] == ARM and result["notional_usd"] == 20
        assert result["reclaim_anchor_exit212"]
        assert not result["requires_distinct_trajectory_frame"]
        assert not result.get("entry_alias_of") and result["source_arm_ids"] == []
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        definition = store._chain_meme_trader_effective_definition(
            version, store._chain_meme_trader_registration(version)["definition_json"])
        assert sum(p["arm_id"] == ARM for p in definition["policies"]) == 1
    finally:
        store.close()


def test_confirmed_signal_enters_existing_next_observation_path(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "fill222.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        store.register_chain_meme_washout_reclaim212()
        store.register_chain_meme_washout_confirm222()
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Wash", "W")
        store.upsert_token(token, seen_at=clock[0])
        trigger_at = clock[0] + timedelta(seconds=1)
        tracker = Tracker(clock[0])
        tracker.begin(source(trigger_at), frame(trigger_at), trigger_at)
        clock[0] = trigger_at + timedelta(seconds=10)
        signal = tracker.accept(frame(clock[0], price=.010), clock[0])
        assert signal is not None
        store.observe_chain_meme_pattern(token, _snapshot(token, POOL, clock[0],
            price=.010, liquidity=5000), recorded_at=clock[0], cohort_signals={ARM: signal})
        assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?",
                                (ARM,)).fetchone()[0] == 0
        clock[0] += timedelta(seconds=7)
        store.observe_chain_meme_pattern(token, _snapshot(token, POOL, clock[0],
            price=.011, liquidity=5000), recorded_at=clock[0], cohort_signals={ARM: signal})
        position = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?",
                                    (ARM,)).fetchone()
        assert position is not None
        assert position["opened_at"] > signal["observed_at"]
        assert store._json_object(position["capital_exit_state_json"])[
            "reclaim_anchor212_frozen"]["price_usd"] == .008
    finally:
        store.close()
