from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.capital_policies import capital_policies
from memetrader.l0_experiments import l0_experiment_policies
from memetrader.staged_probe import (
    HOLD,
    SHADOW_BUY,
    SHADOW_EXIT,
    SHADOW_QUALIFIED,
    WAIT,
    evaluate_staged_probe,
    staged_probe_policies,
)


UTC = timezone.utc


def _position(opened):
    return {
        "opened_at": opened.isoformat(),
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "stake_usd": 5.0,
        "probe_cost_usd": 5.0,
        "formal_quantity_tokens": 4.0,
    }


def _frame(opened, seconds, frame_id, *, price=1.0, liquidity=1_000.0, **extra):
    observed = opened + timedelta(seconds=seconds)
    return {
        "frame_id": frame_id,
        "event_kind": "market_frame",
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "original_pool": True,
        "observed_at": observed.isoformat(),
        "recorded_at": (observed + timedelta(seconds=1)).isoformat(),
        "price_usd": price,
        "liquidity_usd": liquidity,
        **extra,
    }


def _evaluate(position, frame, state=None):
    return evaluate_staged_probe(
        position,
        frame,
        state,
        now=datetime.fromisoformat(frame["recorded_at"]),
    )


def _open_shadow(opened):
    position = _position(opened)
    _, _, state, _ = _evaluate(position, _frame(opened, 60, "f60"))
    action, _, state, _ = _evaluate(
        position,
        _frame(opened, 120, "f120", price=0.95, liquidity=900, net_recovery_usd=5),
        state,
    )
    assert action == SHADOW_QUALIFIED
    action, _, state, _ = _evaluate(
        position,
        _frame(opened, 126, "shadow-buy", price=1.2, liquidity=1_100),
        state,
    )
    assert action == SHADOW_BUY
    return position, state


def test_staged_probe_policies_are_three_unique_same_entry_risk_baselines():
    policies = staged_probe_policies()
    assert [policy["arm_id"] for policy in policies] == [
        "staged_probe_20u_once_control_v1",
        "staged_probe_5u_only_control_v1",
        "staged_probe_5u_conditional_15u_shadow_v1",
    ]
    assert [policy["notional_usd"] for policy in policies] == [20.0, 5.0, 5.0]
    assert all(policy["entry_family"] == "broad_launch" for policy in policies)
    assert all(
        policy["entry_match_mode"] == "isolated_cohort_observer" for policy in policies
    )
    assert {policy["paired_opportunity_group"] for policy in policies} == {
        "staged_probe_s03"
    }
    assert all("paired_entry_group" not in policy for policy in policies)
    candidate = policies[-1]
    assert candidate["probe_kind"] == "bounded_5u_then_shadow_15u"
    assert candidate["shadow_notional_usd"] == 15.0
    assert candidate["shadow_affects_formal_pnl"] is False
    existing_ids = {
        policy["arm_id"]
        for policy in capital_policies() + l0_experiment_policies()
    }
    assert existing_ids.isdisjoint(policy["arm_id"] for policy in policies)


def test_staged_probe_qualifies_at_120_and_buys_shadow_only_on_next_frame():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    action, reason, state, _ = _evaluate(
        position, _frame(opened, 60, "f60", price=1.0, liquidity=1_000)
    )
    assert (action, reason) == (HOLD, "probe_60_checkpoint_recorded")

    at_120 = _frame(
        opened,
        120,
        "f120",
        price=0.9,
        liquidity=900,
        net_recovery_usd=5.0,
    )
    action, reason, state, evidence = _evaluate(position, at_120, state)
    assert (action, reason) == (SHADOW_QUALIFIED, "shadow_second_leg_qualified")
    assert evidence["cost_covered"] is True
    assert evidence["required_fill"] == "next_fresh_original_pool_frame"
    assert "shadow_fill" not in state

    action, reason, duplicate_state, evidence = _evaluate(position, at_120, state)
    assert (action, reason) == (WAIT, "duplicate_frame")
    assert evidence["duplicate"] is True
    assert duplicate_state == state

    next_frame = _frame(
        opened, 126, "f126", price=1.2, liquidity=1_050
    )
    action, reason, state, evidence = _evaluate(position, next_frame, state)
    assert (action, reason) == (SHADOW_BUY, "shadow_second_leg_recorded")
    fill = state["shadow_fill"]
    assert fill["notional_usd"] == pytest.approx(15.0)
    assert fill["execution_price_usd"] == pytest.approx(1.2 * 1.04)
    assert fill["quantity_tokens"] == pytest.approx(15.0 / (1.2 * 1.04))
    assert evidence["affects_formal_pnl"] is False
    assert evidence["formal_quantity_unchanged"] is True

    later = _frame(opened, 132, "f132", price=1.3, liquidity=1_100)
    action, reason, repeated, _ = _evaluate(position, later, state)
    assert (action, reason) == (HOLD, "shadow_leg_already_open")
    assert repeated["shadow_fill"] == fill


def test_staged_probe_does_not_buy_shadow_below_shared_liquidity_floor():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    _, _, state, _ = _evaluate(
        position, _frame(opened, 60, "low-floor-60", price=1.0, liquidity=1_000)
    )
    action, _, state, _ = _evaluate(
        position,
        _frame(opened, 120, "low-floor-120", price=1.1, liquidity=1_000,
               net_recovery_usd=5.0),
        state,
    )
    assert action == SHADOW_QUALIFIED

    action, reason, state, evidence = _evaluate(
        position, _frame(opened, 126, "low-floor-buy", price=1.2, liquidity=99),
        state,
    )
    assert (action, reason) == (
        WAIT, "shadow_entry_pool_liquidity_below_shared_floor"
    )
    assert "shadow_fill" not in state
    assert evidence["minimum_pool_liquidity_usd"] == 100.0


def test_staged_probe_accepts_market_improvement_but_not_partial_improvement():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    _, _, state, _ = _evaluate(
        position, _frame(opened, 60, "improve-60", price=1.0, liquidity=1_000)
    )
    action, _, qualified, evidence = _evaluate(
        position,
        _frame(
            opened,
            120,
            "improve-120",
            price=1.1,
            liquidity=1_000,
            net_recovery_usd=4.0,
        ),
        state,
    )
    assert action == SHADOW_QUALIFIED
    assert evidence["cost_covered"] is False
    assert evidence["market_improved"] is True

    _, _, state, _ = _evaluate(
        position, _frame(opened, 60, "weak-60", price=1.0, liquidity=1_000)
    )
    action, reason, rejected, evidence = _evaluate(
        position,
        _frame(
            opened,
            120,
            "weak-120",
            price=1.1,
            liquidity=999,
            net_recovery_usd=4.99,
        ),
        state,
    )
    assert (action, reason) == (HOLD, "shadow_second_leg_not_qualified")
    assert evidence["market_improved"] is False
    assert rejected["status"] == "COMPLETE_NO_SHADOW"


def test_staged_probe_rejects_wrong_pool_future_and_missed_checkpoint():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    wrong = _frame(opened, 60, "wrong")
    wrong["original_pool"] = False
    action, reason, _, _ = _evaluate(position, wrong)
    assert (action, reason) == (WAIT, "original_pool_identity_required")

    future = _frame(opened, 60, "future")
    action, reason, _, _ = evaluate_staged_probe(
        position,
        future,
        now=datetime.fromisoformat(future["observed_at"]) - timedelta(seconds=1),
    )
    assert (action, reason) == (WAIT, "noncausal_or_future_frame")

    action, reason, state, _ = _evaluate(
        position,
        _frame(opened, 120, "missing-60", net_recovery_usd=6.0),
    )
    assert (action, reason) == (WAIT, "probe_60_checkpoint_expired")
    action, reason, _, _ = _evaluate(
        position,
        _frame(opened, 126, "too-late", net_recovery_usd=6.0),
        state,
    )
    assert (action, reason) == (HOLD, "probe_review_finished")


def test_staged_probe_shadow_exit_reuses_formal_quote_without_formal_mutation():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position, state = _open_shadow(opened)
    original_position = copy.deepcopy(position)
    exit_marker = _frame(opened, 180, "formal-exit", price=1.5, liquidity=1_200)
    exit_marker.update({
        "event_kind": "formal_exit_quote",
        "formal_exit_closes_position": True,
        "formal_exit_quantity_tokens": 4.0,
        "formal_exit_net_recovery_usd": 6.0,
    })
    action, reason, state, evidence = _evaluate(position, exit_marker, state)
    assert (action, reason) == (
        SHADOW_EXIT,
        "shadow_exit_recorded_from_formal_quote",
    )
    shadow_exit = state["shadow_exit"]
    expected_recovery = state["shadow_fill"]["quantity_tokens"] * 1.5
    assert shadow_exit["marker_id"] == "formal-exit"
    assert shadow_exit["net_exit_price_per_token_usd"] == pytest.approx(1.5)
    assert shadow_exit["shadow_net_recovery_usd"] == pytest.approx(expected_recovery)
    assert shadow_exit["shadow_net_pnl_usd"] == pytest.approx(
        expected_recovery - 15.0
    )
    assert evidence["shadow_exit"]["affects_formal_pnl"] is False
    assert evidence["shadow_exit"]["formal_quantity_unchanged"] is True
    assert position == original_position

    action, reason, duplicate, _ = _evaluate(position, exit_marker, state)
    assert (action, reason) == (WAIT, "duplicate_frame")
    assert duplicate == state
