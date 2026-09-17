from memetrader.trend_anchor220 import ARM, PARENT, alias_signal, policy
from memetrader.washout_reclaim212 import advance, frozen_anchor


def test_forward_position_freezes_breakout_origin(tmp_path, monkeypatch):
    from datetime import timedelta
    from types import SimpleNamespace
    from memetrader.cohort_experiments import cohort_experiment_policies
    from memetrader.models import TokenCandidate, iso, utcnow
    from memetrader.store import Store
    from memetrader.trajectory144 import policies as trajectory_policies
    from test_l0_store import _snapshot

    token_id = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
    pool = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "trend220.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent = next(p for p in trajectory_policies(cohort_experiment_policies()[2])
                      if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent)
        assert store.register_chain_meme_trend_anchor220() == 1
        assert store.register_chain_meme_trend_anchor220() == 0
        token = TokenCandidate("solana", token_id.split(":", 1)[1], "Trend", "T")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        at = clock[0]
        parent_signal = {
            "decision_key": "trend220:test", "episode_id": "trend220:test",
            "selected": {"token_id": token_id, "pair_address": pool},
            "observed_at": iso(at), "recorded_at": iso(at),
            "decision_evidence": {"feature_vector": {
                "observed_at": iso(at), "ingested_at": iso(at), "pair_address": pool,
                "current": {"price_usd": 1.2},
                "window_30": {"start_at": iso(at - timedelta(seconds=30)),
                              "end_at": iso(at), "return_fraction": .2},
            }},
        }
        signal = alias_signal(parent_signal)
        assert signal is not None
        features = {"observed_at": iso(at),
                    "continuity_started_at": iso(at - timedelta(seconds=30)),
                    "windows": {"30": {"frames": 3}}}
        engine = SimpleNamespace(pools={(token_id, pool): {"features": features}})
        monkeypatch.setattr(store, "_trajectory_engine_for", lambda _: engine)
        store.observe_chain_meme_pattern(
            token, _snapshot(token, pool, at, liquidity=5000),
            recorded_at=at, cohort_signals={PARENT: parent_signal, ARM: signal},
        )
        clock[0] += timedelta(seconds=7)
        features["observed_at"] = iso(clock[0])
        store.observe_chain_meme_pattern(
            token, _snapshot(token, pool, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={PARENT: parent_signal, ARM: signal},
        )
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)
        ).fetchone()
        assert position is not None
        frozen = store._json_object(position["capital_exit_state_json"])[
            "reclaim_anchor212_frozen"]
        assert abs(frozen["price_usd"] - 1.0) < 1e-12
        assert position["opened_at"] > signal["observed_at"]
    finally:
        store.close()


def source():
    return {
        "decision_key": "trend:token:pool", "episode_id": "trend:token:pool",
        "observed_at": "2026-09-17T00:01:00Z",
        "recorded_at": "2026-09-17T00:01:01Z",
        "selected": {"token_id": "solana:token", "pair_address": "pool"},
        "decision_evidence": {"feature_vector": {
            "observed_at": "2026-09-17T00:01:00Z",
            "ingested_at": "2026-09-17T00:01:00.500Z",
            "current": {"price_usd": 1.2},
            "window_30": {"start_at": "2026-09-17T00:00:30Z",
                          "end_at": "2026-09-17T00:01:00Z",
                          "return_fraction": .2},
        }},
    }


def test_trend_anchor_uses_only_frozen_pre_signal_window():
    signal = alias_signal(source())
    assert signal is not None
    assert signal["decision_key"].endswith("|" + ARM)
    anchor = frozen_anchor(signal, "2026-09-17T00:01:05Z")
    assert anchor is not None
    assert abs(anchor["price_usd"] - 1.0) < 1e-12
    state = {"reclaim_anchor212_frozen": anchor}
    state, exit_now = advance(state, anchor=1.0, price=.99, sequence=1,
                              observed_at="2026-09-17T00:01:10Z",
                              opened_at="2026-09-17T00:01:05Z", pair_address="pool")
    assert not exit_now
    _, exit_now = advance(state, anchor=1.0, price=.98, sequence=2,
                          observed_at="2026-09-17T00:01:20Z",
                          opened_at="2026-09-17T00:01:05Z", pair_address="pool")
    assert exit_now


def test_trend_anchor_rejects_missing_or_future_window():
    item = source()
    item["decision_evidence"]["feature_vector"]["window_30"]["end_at"] = "2026-09-17T00:01:02Z"
    assert alias_signal(item) is None
    item = source()
    del item["decision_evidence"]["feature_vector"]["window_30"]
    assert alias_signal(item) is None
    item = source()
    item["decision_evidence"]["feature_vector"]["ingested_at"] = "2026-09-17T00:01:02Z"
    assert alias_signal(item) is None


def test_trend_anchor_policy_keeps_parent_exit_and_adds_structural_exit():
    parent = {"arm_id": PARENT, "max_hold_minutes": 30,
              "trajectory_trend_runner": True, "notional_usd": 20.0,
              "entry_filter": {"max_concurrent_positions": 8}}
    child = policy(parent)
    assert child["arm_id"] == ARM
    assert child["entry_alias_of"] == PARENT
    assert child["reclaim_anchor_exit212"]
    assert child["trajectory_trend_runner"]
    assert child["notional_usd"] == 20.0
