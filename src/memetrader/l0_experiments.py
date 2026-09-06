"""Pure L0-only exit experiments for broad-entry paired Paper arms.

The evaluators deliberately do not consume amountful flow.  They return the
same ``(action, reason, new_state, evidence)`` tuple as ``capital_exits`` and
leave persistence, the common trailing stop, and execution to the caller.
"""
from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Mapping

from .capital_exits import (
    HOLD,
    SELL,
    WAIT,
    ExitResult,
    _as_time,
    _begin,
    _number,
    _policy_snapshot,
    _result,
)
from .capital_policies import capital_policies


L0_CONTINUATION_FAILURE_POLICY = MappingProxyType({
    "version": "l0-continuation-failure/v1",
    "checkpoint_60_seconds": 60.0,
    "checkpoint_120_seconds": 120.0,
    "checkpoint_tolerance_seconds": 15.0,
    "maximum_frame_age_seconds": 15.0,
})

L0_PROFIT_LOCK_POLICY = MappingProxyType({
    "version": "l0-profit-lock/v1",
    "minimum_bad_frames": 2,
    "minimum_frame_span_seconds": 5.0,
    "maximum_frame_age_seconds": 15.0,
})


def l0_experiment_policies() -> list[dict[str, Any]]:
    """Return two Broad-entry candidate/control pairs without registering them."""
    parents = {policy["arm_id"]: policy for policy in capital_policies()}
    specs = (
        (
            "l0_continuation_failure",
            "earn_the_hold_v1",
            L0_CONTINUATION_FAILURE_POLICY,
            "L0 120秒延续失败",
        ),
        (
            "l0_profit_lock",
            "failed_continuation_profit_lock_v1",
            L0_PROFIT_LOCK_POLICY,
            "L0 回本后连续恶化锁利",
        ),
    )
    result: list[dict[str, Any]] = []
    for kind, parent_id, exit_policy, name in specs:
        for control in (False, True):
            policy = copy.deepcopy(parents[parent_id])
            arm_id = f"{kind}_{'control' if control else 'candidate'}_v1"
            policy.update({
                "arm_id": arm_id,
                "canonical_id": arm_id,
                "name": name + ("·同入场对照" if control else "·候选"),
                "description": (
                    "复用Broad严格前向入场的20U配对实验；唯一候选差异是纯L0退出，"
                    "不要求amountful flow。"
                ),
                "entry_family": "broad_launch",
                "source_entry_family": "broad_launch",
                "entry_gate": "v6_asof_family",
                "entry_match_mode": "exact_entry_family",
                "paired_entry_group": kind,
                "notional_usd": 20.0,
                "source_arm_ids": [parent_id],
                "required_inputs": ["broad_launch", "original_pool_l0_frames"],
                "capital_exit_kind": None if control else kind,
                "capital_exit_policy": {} if control else dict(exit_policy),
                "exit_family": "capital_exit_existing_v1" if control else kind,
                "no_historical_backfill": True,
            })
            policy["entry_filter"] = {
                "direction": "broad_launch",
                "paired_entry_kind": kind,
            }
            result.append(policy)
    return result


def _l0_values(frame: Mapping[str, Any]) -> tuple[float | None, float | None]:
    price = _number(frame.get("price_usd"))
    liquidity = _number(frame.get("liquidity_usd"))
    if price is None or price <= 0.0:
        price = None
    if liquidity is None or liquidity < 0.0:
        liquidity = None
    return price, liquidity


def _original_pool_required(
    new_state: dict[str, Any], evidence: dict[str, Any], frame: Mapping[str, Any]
) -> ExitResult | None:
    if frame.get("original_pool") is True:
        return None
    return _result(WAIT, "original_pool_identity_required", new_state, evidence)


def evaluate_l0_continuation_failure(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = L0_CONTINUATION_FAILURE_POLICY,
) -> ExitResult:
    """Arm a full exit from fixed 60/120-second original-pool L0 checkpoints.

    ``position`` supplies ``opened_at``, identities and ``remaining_cost_usd``.
    Frames supply the common provenance fields, ``original_pool=True``,
    ``price_usd``, ``liquidity_usd`` and, at the 120-second checkpoint,
    ``net_recovery_usd`` after the configured sell costs. ``SELL`` is a trigger
    only; the existing runtime settles on a later independent original-pool frame.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "l0_continuation_failure", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    pool_error = _original_pool_required(new_state, evidence, frame)
    if pool_error:
        return pool_error

    if new_state.get("status") in {"COMPLETE", "EXPIRED", "EXIT_TRIGGERED"}:
        return _result(HOLD, "l0_continuation_review_finished", new_state, evidence)

    elapsed = float(evidence["elapsed_seconds"])
    target_60 = float(policy["checkpoint_60_seconds"])
    target_120 = float(policy["checkpoint_120_seconds"])
    tolerance = float(policy["checkpoint_tolerance_seconds"])
    price, liquidity = _l0_values(frame)
    evidence.update({"price_usd": price, "liquidity_usd": liquidity})

    if elapsed < target_60 - tolerance:
        return _result(WAIT, "l0_60_checkpoint_not_due", new_state, evidence)
    if elapsed <= target_60 + tolerance and "checkpoint_60" not in new_state:
        if price is None or liquidity is None:
            return _result(WAIT, "l0_60_checkpoint_missing", new_state, evidence)
        new_state["checkpoint_60"] = {
            "frame_id": str(frame["frame_id"]),
            "observed_at": frame["observed_at"],
            "recorded_at": frame["recorded_at"],
            "price_usd": price,
            "liquidity_usd": liquidity,
        }
        return _result(HOLD, "l0_60_checkpoint_recorded", new_state, evidence)
    if "checkpoint_60" not in new_state:
        new_state["status"] = "EXPIRED"
        return _result(WAIT, "l0_60_checkpoint_expired", new_state, evidence)
    if elapsed < target_120 - tolerance:
        return _result(HOLD, "l0_120_checkpoint_not_due", new_state, evidence)
    if elapsed > target_120 + tolerance:
        new_state["status"] = "EXPIRED"
        return _result(WAIT, "l0_120_checkpoint_expired", new_state, evidence)

    net_recovery = _number(frame.get("net_recovery_usd"))
    remaining_cost = _number(position.get("remaining_cost_usd"))
    evidence.update({
        "net_recovery_usd": net_recovery,
        "remaining_cost_usd": remaining_cost,
    })
    if (
        price is None
        or liquidity is None
        or net_recovery is None
        or remaining_cost is None
        or remaining_cost < 0.0
    ):
        return _result(WAIT, "l0_120_checkpoint_missing", new_state, evidence)

    checkpoint_60 = new_state["checkpoint_60"]
    trigger = bool(
        net_recovery < remaining_cost
        and price < float(checkpoint_60["price_usd"])
        and liquidity <= float(checkpoint_60["liquidity_usd"])
    )
    new_state["checkpoint_120"] = {
        "frame_id": str(frame["frame_id"]),
        "observed_at": frame["observed_at"],
        "recorded_at": frame["recorded_at"],
        "price_usd": price,
        "liquidity_usd": liquidity,
        "net_recovery_usd": net_recovery,
        "remaining_cost_usd": remaining_cost,
    }
    evidence["continuation_failed"] = trigger
    if trigger:
        new_state["status"] = "EXIT_TRIGGERED"
        new_state["armed_at_observed_at"] = frame["observed_at"]
        new_state["armed_at_frame_id"] = str(frame["frame_id"])
        evidence.update(sell_fraction=1.0, required_fill="next_original_pool_frame")
        return _result(SELL, "l0_continuation_failure_armed", new_state, evidence)
    new_state["status"] = "COMPLETE"
    return _result(HOLD, "l0_continuation_review_passed", new_state, evidence)


def evaluate_l0_profit_lock(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = L0_PROFIT_LOCK_POLICY,
) -> ExitResult:
    """Exit a cost-covered remainder after two spaced L0 deterioration frames.

    The caller establishes ``principal_recovered`` from actual ledger proceeds.
    Each frame supplies ``economic_value_usd`` (realized proceeds plus the
    remaining position's net recoverable value), price and pool liquidity.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "l0_profit_lock", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    pool_error = _original_pool_required(new_state, evidence, frame)
    if pool_error:
        return pool_error
    if not bool(position.get("principal_recovered") or position.get("cost_covered")):
        return _result(WAIT, "cost_not_yet_recovered", new_state, evidence)
    if new_state.get("status") == "EXIT_TRIGGERED":
        return _result(HOLD, "l0_profit_lock_exit_already_triggered", new_state, evidence)

    price, liquidity = _l0_values(frame)
    economic_value = _number(frame.get("economic_value_usd"))
    evidence.update({
        "price_usd": price,
        "liquidity_usd": liquidity,
        "economic_value_usd": economic_value,
    })
    if price is None or liquidity is None or economic_value is None:
        return _result(WAIT, "missing_l0_profit_lock_evidence", new_state, evidence)

    prior = new_state.get("accepted_frame")
    if not isinstance(prior, Mapping):
        new_state["economic_running_high_usd"] = economic_value
        new_state["accepted_frame"] = {
            "frame_id": str(frame["frame_id"]),
            "observed_at": frame["observed_at"],
            "price_usd": price,
            "liquidity_usd": liquidity,
        }
        new_state["bad_streak"] = 0
        return _result(HOLD, "l0_profit_lock_baseline_recorded", new_state, evidence)

    observed_at = _as_time(frame.get("observed_at"))
    prior_at = _as_time(prior.get("observed_at"))
    if observed_at is None or prior_at is None:
        return _result(WAIT, "missing_l0_profit_lock_span", new_state, evidence)
    span = (observed_at - prior_at).total_seconds()
    evidence["accepted_frame_span_seconds"] = span
    if span < float(policy["minimum_frame_span_seconds"]):
        return _result(WAIT, "l0_profit_lock_frame_too_close", new_state, evidence)

    running_high = _number(new_state.get("economic_running_high_usd"))
    if running_high is None:
        running_high = economic_value
    new_high = economic_value > running_high
    bad = bool(
        not new_high
        and price < float(prior["price_usd"])
        and liquidity <= float(prior["liquidity_usd"])
    )
    streak = int(new_state.get("bad_streak") or 0) + 1 if bad else 0
    new_state["economic_running_high_usd"] = max(running_high, economic_value)
    new_state["bad_streak"] = streak
    new_state["accepted_frame"] = {
        "frame_id": str(frame["frame_id"]),
        "observed_at": frame["observed_at"],
        "price_usd": price,
        "liquidity_usd": liquidity,
    }
    evidence.update({
        "prior_economic_running_high_usd": running_high,
        "economic_running_high_usd": new_state["economic_running_high_usd"],
        "new_economic_high": new_high,
        "l0_deterioration": bad,
        "deterioration_streak": streak,
    })
    if streak >= int(policy["minimum_bad_frames"]):
        new_state["status"] = "EXIT_TRIGGERED"
        evidence["sell_fraction"] = 1.0
        return _result(SELL, "l0_two_frame_profit_lock", new_state, evidence)
    return _result(HOLD, "l0_profit_lock_monitoring", new_state, evidence)


__all__ = [
    "L0_CONTINUATION_FAILURE_POLICY",
    "L0_PROFIT_LOCK_POLICY",
    "l0_experiment_policies",
    "evaluate_l0_continuation_failure",
    "evaluate_l0_profit_lock",
]
