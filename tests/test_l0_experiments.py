from datetime import datetime, timedelta, timezone

from memetrader.l0_experiments import (
    evaluate_l0_continuation_failure,
    evaluate_l0_profit_lock,
    l0_experiment_policies,
)


UTC = timezone.utc


def _frame(opened, seconds, frame_id, *, price=1.0, liquidity=1_000.0, **extra):
    observed = opened + timedelta(seconds=seconds)
    return {
        "frame_id": frame_id,
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "original_pool": True,
        "observed_at": observed.isoformat(),
        "recorded_at": (observed + timedelta(seconds=1)).isoformat(),
        "price_usd": price,
        "liquidity_usd": liquidity,
        **extra,
    }


def _position(opened, **extra):
    return {
        "opened_at": opened.isoformat(),
        "token_id": "solana:TOKEN",
        "pair_address": "POOL",
        "remaining_cost_usd": 20.0,
        **extra,
    }


def _evaluate(evaluator, position, frame, state=None):
    observed = datetime.fromisoformat(frame["observed_at"])
    return evaluator(
        position,
        frame,
        state,
        now=observed + timedelta(seconds=2),
    )


def test_l0_policies_are_broad_paired_20u_candidate_controls():
    policies = l0_experiment_policies()
    assert {policy["arm_id"] for policy in policies} == {
        "l0_continuation_failure_candidate_v1",
        "l0_continuation_failure_control_v1",
        "l0_profit_lock_candidate_v1",
        "l0_profit_lock_control_v1",
    }
    assert all(policy["entry_family"] == "broad_launch" for policy in policies)
    assert all(policy["source_entry_family"] == "broad_launch" for policy in policies)
    assert all(policy["notional_usd"] == 20.0 for policy in policies)
    for group in {policy["paired_entry_group"] for policy in policies}:
        pair = [policy for policy in policies if policy["paired_entry_group"] == group]
        assert len(pair) == 2
        assert sum(policy["capital_exit_kind"] is not None for policy in pair) == 1


def test_l0_continuation_failure_triggers_at_120_without_claiming_a_fill():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    action, reason, state, _ = _evaluate(
        evaluate_l0_continuation_failure,
        position,
        _frame(opened, 60, "f60", price=1.0, liquidity=1_000.0),
    )
    assert (action, reason) == ("HOLD", "l0_60_checkpoint_recorded")

    action, reason, state, evidence = _evaluate(
        evaluate_l0_continuation_failure,
        position,
        _frame(
            opened,
            120,
            "f120",
            price=0.9,
            liquidity=1_000.0,
            net_recovery_usd=19.0,
        ),
        state,
    )
    assert (action, reason) == ("SELL", "l0_continuation_failure_armed")
    assert evidence["continuation_failed"] is True
    assert evidence["sell_fraction"] == 1.0
    assert evidence["required_fill"] == "next_original_pool_frame"

    action, reason, state, evidence = _evaluate(
        evaluate_l0_continuation_failure,
        position,
        _frame(opened, 126, "next", price=0.88, liquidity=990.0),
        state,
    )
    assert (action, reason) == ("HOLD", "l0_continuation_review_finished")


def test_l0_continuation_missing_checkpoint_expires_without_later_backfill():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened)
    action, reason, state, _ = _evaluate(
        evaluate_l0_continuation_failure,
        position,
        _frame(opened, 120, "late", price=0.8, liquidity=900.0, net_recovery_usd=15),
    )
    assert (action, reason) == ("WAIT", "l0_60_checkpoint_expired")
    action, reason, _, _ = _evaluate(
        evaluate_l0_continuation_failure,
        position,
        _frame(opened, 126, "later", price=0.7, liquidity=800.0, net_recovery_usd=14),
        state,
    )
    assert (action, reason) == ("HOLD", "l0_continuation_review_finished")


def test_l0_profit_lock_needs_recovered_principal_and_two_spaced_bad_frames():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    unrecovered = _position(opened)
    first = _frame(opened, 200, "base", economic_value_usd=30.0)
    action, reason, _, _ = _evaluate(evaluate_l0_profit_lock, unrecovered, first)
    assert (action, reason) == ("WAIT", "cost_not_yet_recovered")

    position = _position(opened, principal_recovered=True)
    action, reason, state, _ = _evaluate(evaluate_l0_profit_lock, position, first)
    assert (action, reason) == ("HOLD", "l0_profit_lock_baseline_recorded")

    too_close = _frame(
        opened, 203, "noise", price=0.99, liquidity=999.0, economic_value_usd=29.0
    )
    action, reason, state, _ = _evaluate(
        evaluate_l0_profit_lock, position, too_close, state
    )
    assert (action, reason) == ("WAIT", "l0_profit_lock_frame_too_close")

    bad1 = _frame(
        opened, 206, "bad1", price=0.99, liquidity=1_000.0, economic_value_usd=29.0
    )
    action, reason, state, evidence = _evaluate(
        evaluate_l0_profit_lock, position, bad1, state
    )
    assert (action, reason) == ("HOLD", "l0_profit_lock_monitoring")
    assert evidence["deterioration_streak"] == 1

    bad2 = _frame(
        opened, 212, "bad2", price=0.98, liquidity=999.0, economic_value_usd=28.0
    )
    action, reason, _, evidence = _evaluate(
        evaluate_l0_profit_lock, position, bad2, state
    )
    assert (action, reason) == ("SELL", "l0_two_frame_profit_lock")
    assert evidence["sell_fraction"] == 1.0


def test_l0_evaluators_reject_future_or_wrong_pool_identity():
    opened = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    position = _position(opened, principal_recovered=True)
    wrong_pool = _frame(opened, 60, "wrong")
    wrong_pool["original_pool"] = False
    action, reason, _, _ = _evaluate(
        evaluate_l0_continuation_failure, position, wrong_pool
    )
    assert (action, reason) == ("WAIT", "original_pool_identity_required")

    future = _frame(opened, 200, "future", economic_value_usd=30.0)
    observed = datetime.fromisoformat(future["observed_at"])
    action, reason, _, _ = evaluate_l0_profit_lock(
        position, future, now=observed - timedelta(seconds=1)
    )
    assert (action, reason) == ("WAIT", "noncausal_or_future_frame")
