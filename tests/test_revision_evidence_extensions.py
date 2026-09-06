from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from memetrader.capital_common_funding import common_funding_policy
from memetrader.capital_policies import (
    capital_policies,
    direct_lp_amount_specific_policy,
    event_actual_flow_policy,
    opportunity_policies,
    second_discussion_policies,
)
from memetrader.forward_patterns import experiment_policies
from memetrader.migration_absorption import migration_amount_absorption_policy
from memetrader.revision_evidence_extensions import (
    ENTRY_REVISION_KIND,
    SPECS,
    evaluate_evidence_extension_entry,
    revise_evidence_extension,
)


def _actual_policies():
    policies = [
        *experiment_policies(), *capital_policies(), *second_discussion_policies(),
        *opportunity_policies(), direct_lp_amount_specific_policy(),
        event_actual_flow_policy(), migration_amount_absorption_policy(),
        common_funding_policy(),
    ]
    return {policy["arm_id"]: policy for policy in policies}


def _passing_history(policy):
    cfg = policy["entry_filter"]
    kind = cfg["direction"]
    count = int(cfg.get("min_frames", 1))
    span = float(cfg.get("min_span", 0.0))
    step = max(15.0, span / max(1, count - 1))
    decision = datetime(2026, 9, 6, 12, 5, tzinfo=timezone.utc)
    start = decision - timedelta(seconds=step * max(0, count - 1) + 1)
    age = max(120.0, float(cfg.get("min_age", 0.0)) + 60.0)
    trades = max(20.0, float(cfg.get("min_trades", 0.0)))
    buy_ratio = max(.7, float(cfg.get("min_buy_ratio", 0.0)))
    frames = []
    for index in range(count):
        observed = start + timedelta(seconds=step * index)
        frames.append({
            "token_id": "solana:token", "pair_address": "pool",
            "price": 100.0, "liquidity": 10_000.0, "volume": 1_000.0,
            "buys": trades * buy_ratio, "sells": trades * (1 - buy_ratio),
            "pool_age_seconds": age,
            "observed_at": observed.isoformat(),
            "ingested_at": (observed + timedelta(milliseconds=100)).isoformat(),
            "recorded_at": (observed + timedelta(milliseconds=200)).isoformat(),
        })
    last = frames[-1]
    last["volume"] = max(float(cfg.get("min_volume", 0.0)), 1_000.0)
    if kind in {"early_quality", "quality_gate"}:
        last["volume"] = max(
            last["volume"], trades * float(cfg.get("min_average_trade", 0.0))
        )
        last["liquidity"] = max(last["liquidity"], float(cfg.get("min_liquidity", 0.0)))
    elif kind == "continuation":
        last["price"] = frames[0]["price"] * (
            float(cfg["min_price_ratio"]) + .01
        )
        last["liquidity"] = frames[0]["liquidity"] * max(
            1.0, float(cfg["min_liquidity_retention"])
        )
        last["volume"] = max(
            last["volume"], frames[0]["volume"] * float(cfg["min_volume_acceleration"])
        )
    elif kind == "liquidity_lead":
        last["liquidity"] = frames[0]["liquidity"] * float(cfg["min_liquidity_growth"])
        last["price"] = frames[0]["price"] * max(1.0, float(cfg["min_price_ratio"]))
    elif kind == "compression_breakout":
        baseline_volume = 500.0
        for frame in frames[:-1]:
            frame["price"] = 100.0
            frame["volume"] = baseline_volume
        last["price"] = 100.0 * (float(cfg["min_breakout"]) + .005)
        last["volume"] = baseline_volume * float(cfg["min_volume_acceleration"])
    elif kind == "reawakening":
        for frame in frames[:-1]:
            quiet_trades = min(2.0, float(cfg["quiet_max_trades"]))
            frame["buys"], frame["sells"] = quiet_trades / 2, quiet_trades / 2
            frame["volume"] = min(100.0, float(cfg["quiet_max_volume"]))
        last["price"] = 100.0 * float(cfg["min_price_ratio"])
    elif kind == "young_absorption":
        last["price"] = 100.0 * (float(cfg["min_price_ratio"]) + .01)
        retention = float(cfg["min_liquidity_retention"])
        for frame in frames:
            frame["liquidity"] = 10_000.0 * max(1.0, retention)
    return frames, decision


def test_all_17_actual_policies_become_explicit_l0_replacements():
    actual = _actual_policies()
    assert set(SPECS) <= set(actual)
    assert len(SPECS) == 17
    forbidden = {"event", "creator", "wallet", "amountful_flow", "pool_surface"}
    names = set()
    for arm_id in SPECS:
        original = actual[arm_id]
        revised = revise_evidence_extension(original)
        assert revised["arm_id"] == original["arm_id"]
        assert revised["canonical_id"] == original["canonical_id"]
        assert revised.get("notional_usd") == original.get("notional_usd")
        if arm_id not in {"event_reawakening_v1", "surface_lifecycle_pipeline_v1"}:
            assert revised.get("capital_exit_kind") == original.get("capital_exit_kind")
        assert revised["strategy_revision"] == int(original.get("strategy_revision") or 1) + 1
        assert revised["entry_family"] == "evidence_extension_l0"
        assert revised["entry_revision_kind"] == ENTRY_REVISION_KIND
        assert revised["replacement_of_entry_family"] == original["entry_family"]
        assert revised["replacement_input_contract"] == "existing_same_pool_l0_no_new_api/v1"
        assert forbidden.isdisjoint(revised["required_inputs"])
        assert revised["revision_reason"] and revised["revision_changes"] and revised["revision_basis"]
        assert revised.get("paired_entry_group") is None
        if int(revised["entry_filter"].get("min_frames", 1)) > 1:
            assert float(revised["entry_filter"]["min_span"]) <= (
                10 * (int(revised["entry_filter"]["min_frames"]) - 1)
            )
        names.add(revised["name"])
    assert len(names) == 17


@pytest.mark.parametrize(
    "arm_id",
    [
        "experiment_narrative_candidate_v1", "experiment_narrative_control_v1",
        "finite_capital_ranker_v1", "market_regime_throttle_v1",
        "direct_lp_float_constrained_v1", "no_ca_event_flow_leader_v1",
        "migration_amount_rate_absorption_v1",
    ],
)
def test_each_l0_mechanism_has_a_strictly_causal_passing_shape(arm_id):
    policy = revise_evidence_extension(_actual_policies()[arm_id])
    history, decision = _passing_history(policy)
    assert evaluate_evidence_extension_entry(
        history, policy, decision_at=decision.isoformat(),
        activated_at=(decision - timedelta(hours=2)).isoformat(),
    )[0]


def test_replacement_rejects_future_stale_and_below_floor():
    policy = revise_evidence_extension(
        _actual_policies()["experiment_narrative_candidate_v1"]
    )
    history, decision = _passing_history(policy)
    for mutation, expected in (
        (lambda rows: rows[-1].update(recorded_at=(decision + timedelta(seconds=1)).isoformat()),
         "latest_l0_frame_noncausal_or_invalid"),
        (lambda rows: rows[-1].update(observed_at=(decision - timedelta(seconds=31)).isoformat(),
                                      ingested_at=(decision - timedelta(seconds=30)).isoformat(),
                                      recorded_at=(decision - timedelta(seconds=29)).isoformat()),
         "latest_l0_frame_stale"),
        (lambda rows: rows[-1].update(liquidity=999), "replacement_pool_liquidity_below_floor"),
    ):
        changed = [dict(frame) for frame in history]
        mutation(changed)
        assert evaluate_evidence_extension_entry(
            changed, policy, decision_at=decision.isoformat(),
            activated_at=(decision - timedelta(hours=2)).isoformat(),
        )[1] == expected

    continuation = revise_evidence_extension(
        _actual_policies()["experiment_narrative_control_v1"]
    )
    rows, decision = _passing_history(continuation)
    rows[0]["pair_address"] = "other"
    assert evaluate_evidence_extension_entry(
        rows, continuation, decision_at=decision.isoformat(),
        activated_at=(decision - timedelta(hours=2)).isoformat(),
    )[1] == "awaiting_replacement_l0_sequence"


def test_unowned_policy_is_unchanged():
    policy = {"arm_id": "unowned", "entry_family": "broad_launch", "value": [1]}
    revised = revise_evidence_extension(policy)
    assert revised == policy and revised is not policy


def _with_observation_time(frame, observed):
    return {**frame, "observed_at": observed.isoformat(),
            "ingested_at": (observed + timedelta(milliseconds=100)).isoformat(),
            "recorded_at": (observed + timedelta(milliseconds=200)).isoformat()}


def test_denser_confirmation_keeps_elapsed_window_without_lowering_minimum_span():
    policy = revise_evidence_extension(_actual_policies()["capital_velocity_v1"])
    rows, decision = _passing_history(policy)
    start = datetime.fromisoformat(rows[0]["observed_at"])
    middle = _with_observation_time(rows[0], start + timedelta(seconds=10))
    middle.update(price=100.5, volume=1200)
    for history in (rows, [rows[0], middle, rows[1]]):
        assert evaluate_evidence_extension_entry(
            history, policy, decision_at=decision.isoformat(),
            activated_at=(decision - timedelta(hours=2)).isoformat(),
        ) == (True, "replacement_continuation_confirmed")
    assert evaluate_evidence_extension_entry(
        [middle, rows[1]], policy, decision_at=decision.isoformat(),
        activated_at=(decision - timedelta(hours=2)).isoformat(),
    )[1] == "replacement_l0_span_not_met"


def test_time_selected_quiet_window_keeps_intermediate_counterexample():
    policy = revise_evidence_extension(_actual_policies()["event_reawakening_v1"])
    rows, decision = _passing_history(policy)
    start = decision - timedelta(seconds=31)
    rows = [_with_observation_time(frame, start + timedelta(seconds=10 * i))
            for i, frame in enumerate(rows)]
    active = _with_observation_time(rows[0], start + timedelta(seconds=15))
    active.update(buys=20, volume=2000)
    for history, expected in (
        (rows, (True, "replacement_reawakening_confirmed")),
        (rows[:2] + [active] + rows[2:],
         (False, "replacement_reawakening_conditions_not_met")),
    ):
        assert evaluate_evidence_extension_entry(
            history, policy, decision_at=decision.isoformat(),
            activated_at=(decision - timedelta(hours=2)).isoformat(),
        ) == expected


@pytest.mark.parametrize("arm_id", ["event_reawakening_v1", "surface_lifecycle_pipeline_v1"])
def test_l0_replacements_exit_on_available_frames_without_actual_flow(arm_id):
    from memetrader.strategy_revisions import evaluate_l0_loss_deterioration, revision_spec

    original = _actual_policies()[arm_id]
    policy = revision_spec(original)
    assert original["capital_exit_kind"] == "high_recall_exit_pipeline"
    assert policy["capital_exit_kind"] == "l0_loss_deterioration"
    assert policy["max_hold_minutes"] == 15
    assert policy["hard_stop_return"] == original["hard_stop_return"]
    opened = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    position = {"opened_at": opened.isoformat(), "token_id": "solana:token",
                "pair_address": "pool", "remaining_cost_usd": 20.0}
    state = None
    for seconds, price, expected in ((60, 1.0, "HOLD"), (65, .99, "HOLD"), (70, .98, "SELL")):
        observed = opened + timedelta(seconds=seconds)
        frame = {"frame_id": str(seconds), "token_id": position["token_id"],
                 "pair_address": position["pair_address"], "original_pool": True,
                 "observed_at": observed.isoformat(), "recorded_at": observed.isoformat(),
                 "price_usd": price, "liquidity_usd": 10_000.0, "net_recovery_usd": 19.0}
        action, reason, state, evidence = evaluate_l0_loss_deterioration(
            position, frame, state, now=observed, policy=policy["capital_exit_policy"],
        )
        assert action == expected
    assert reason == "l0_loss_deterioration_armed"
    assert evidence["required_fill"] == "next_original_pool_frame"
