"""Pure forward helpers for the age-rate revision-90 proposals.

These functions neither register policies nor write strategy state.  Callers own
the parent-runner delegation, mark persistence, and settlement receipt.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .capital_exits import HOLD, SELL, WAIT, _as_time, _begin, _number, _policy_snapshot, _result
from .paper_execution import sell_terms


AGE_RATE_CHECKPOINT_POLICY = MappingProxyType({
    "version": "age-rate-checkpoint-runner/v2",
    "checkpoint_seconds": 15.0 * 60.0,
    "maximum_frame_age_seconds": 15.0,
})


def age_rate_revision_policies(parent):
    from copy import deepcopy
    result=[]
    for arm,name in (('age_rate_checkpoint_runner_v2','池龄归一化·成本覆盖检查'),
                     ('dynamic_principal_recovery_runner_v2','池龄归一化·动态本金回收')):
        p=deepcopy(parent)
        p.update(arm_id=arm,canonical_id=arm,name=name,
                 source_arm_ids=[parent['arm_id']],notional_usd=5.0,
                 description=name+'；相同入场与母策略比较，5U/最多4仓，未验证盈利。',
                 evidence_review='docs/PROJECT_CONTEXT/STRATEGY_SYSTEM_SAFETY_90.md')
        p.pop('paired_entry_group',None);p.pop('paired_entry_size',None)
        if arm=='age_rate_checkpoint_runner_v2':
            p.update(revision_exit_kind=arm,revision_exit_policy=dict(AGE_RATE_CHECKPOINT_POLICY))
        else:
            p['dynamic_principal_recovery']='minimum_net_debit_next_frame/v2'
        result.append(p)
    return result


def _economic_value(position: Mapping[str, Any], frame: Mapping[str, Any]) -> float | None:
    realized = _number(position.get("realized_proceeds_usd"))
    remaining = _number(frame.get("net_market_position_value_usd"))
    if realized is None or remaining is None or realized < 0.0 or remaining < 0.0:
        return None
    return realized + remaining


def _market_point(frame: Mapping[str, Any]) -> dict[str, Any] | None:
    price = _number(frame.get("market_price_usd"))
    liquidity = _number(frame.get("market_liquidity_usd"))
    if price is None or liquidity is None or price <= 0.0 or liquidity < 0.0:
        return None
    return {
        "frame_id": str(frame["frame_id"]),
        "price_usd": price,
        "liquidity_usd": liquidity,
        "observed_at": frame["observed_at"],
        "recorded_at": frame["recorded_at"],
    }


def evaluate_age_rate_checkpoint(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = AGE_RATE_CHECKPOINT_POLICY,
):
    """Retain diagnostic checkpoint values for the withdrawn 90-A experiment.

    Never initiate a checkpoint sale; existing positions retain parent exits.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "age_rate_checkpoint_runner_v2", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if new_state.get("checkpoint_status") in {"EXIT_TRIGGERED", "PASSED_TO_PARENT"}:
        return _result(HOLD, "checkpoint_already_evaluated", new_state, evidence)

    elapsed = float(evidence["elapsed_seconds"])
    current_point = _market_point(frame)
    if elapsed < float(policy["checkpoint_seconds"]):
        if current_point is not None:
            new_state["prior_market_point"] = current_point
        return _result(HOLD, "checkpoint_not_due", new_state, evidence)

    debit = _number(position.get("stake_usd"))
    economic_value = _economic_value(position, frame)
    prior_point = new_state.get("prior_market_point")
    deterioration: bool | None = None
    if isinstance(prior_point, Mapping) and current_point is not None:
        prior_price = _number(prior_point.get("price_usd"))
        prior_liquidity = _number(prior_point.get("liquidity_usd"))
        if (
            prior_price is not None and prior_liquidity is not None
            and prior_price > 0.0 and prior_liquidity >= 0.0
            and _as_time(prior_point.get('recorded_at')) is not None
            and _as_time(prior_point['recorded_at']) < _as_time(frame['observed_at'])
            and (_as_time(frame['observed_at'])-_as_time(prior_point['observed_at'])).total_seconds() <= 60
        ):
            deterioration = bool(
                current_point["price_usd"] < prior_price
                and current_point["liquidity_usd"] < prior_liquidity
            )
    uncovered = (
        economic_value < debit
        if debit is not None and debit > 0.0 and economic_value is not None
        else None
    )
    evidence.update({
        "checkpoint_elapsed_seconds": elapsed,
        "original_debit_usd": debit,
        "economic_value_usd": economic_value,
        "economic_coverage": (
            "UNCOVERED" if uncovered is True else "COVERED" if uncovered is False else "UNKNOWN"
        ),
        "deterioration": deterioration if deterioration is not None else "UNKNOWN",
        "prior_market_frame_id": prior_point.get("frame_id") if isinstance(prior_point, Mapping) else None,
    })
    # 90-A: uncovered is not decay. Neither this rule nor a replacement
    # structural classifier is authorized for execution. Existing positions
    # retain parent exits; these values are diagnostic only.
    evidence['decision_eligible'] = False
    new_state["checkpoint_status"] = "WITHDRAWN_90_A"
    return _result(HOLD, "checkpoint_withdrawn_continue_parent", new_state, evidence)


def minimum_principal_recovery_sell_amount_raw(
    *,
    remaining_amount_raw: Any,
    remaining_quantity_tokens: Any,
    market_price_usd: Any,
    definition: Mapping[str, Any],
    debit_gap_usd: Any,
) -> int | None:
    """Return the smallest strictly partial raw amount covering an actual debit gap.

    Every candidate is evaluated through the current Paper sell-cost contract.
    ``None`` means the gap is already covered, invalid, or not coverable without
    selling the entire remaining amount.
    """
    try:
        remaining_raw = int(remaining_amount_raw)
    except (TypeError, ValueError):
        return None
    quantity = _number(remaining_quantity_tokens)
    price = _number(market_price_usd)
    gap = _number(debit_gap_usd)
    if remaining_raw <= 1 or quantity is None or quantity <= 0.0 or price is None or price <= 0.0:
        return None
    if gap is None or gap <= 0.0:
        return None

    def net_for(raw: int) -> float:
        return sell_terms(quantity * raw / remaining_raw, price, definition)["net_usd"]

    upper = remaining_raw - 1
    if net_for(upper) < gap:
        return None
    lower = 1
    while lower < upper:
        middle = (lower + upper) // 2
        if net_for(middle) >= gap:
            upper = middle
        else:
            lower = middle + 1
    return lower


def next_frame_minimum_principal_recovery_raw(
    position: Mapping[str, Any], frame: Mapping[str, Any], definition: Mapping[str, Any]
) -> int | None:
    """Recompute the earliest minimally coverable sale from the current frame.

    This intentionally has no state and never sets ``principal_recovered``;
    settlement remains the sole authority for actual recovery.
    """
    debit = _number(position.get("stake_usd"))
    realized = _number(position.get("realized_proceeds_usd"))
    if debit is None or debit <= 0.0 or realized is None or realized < 0.0:
        return None
    return minimum_principal_recovery_sell_amount_raw(
        remaining_amount_raw=position.get("amount_raw"),
        remaining_quantity_tokens=position.get("remaining_quantity_tokens"),
        market_price_usd=frame.get("market_price_usd"),
        definition=definition,
        debit_gap_usd=debit - realized,
    )


__all__ = [
    "AGE_RATE_CHECKPOINT_POLICY",
    "evaluate_age_rate_checkpoint",
    "minimum_principal_recovery_sell_amount_raw",
    "next_frame_minimum_principal_recovery_raw",
]
