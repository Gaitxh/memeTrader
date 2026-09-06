"""Pure S03 state machine for a bounded 5U probe and 15U Shadow second leg."""
from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Mapping

from .capital_exits import _as_time, _begin, _number, _policy_snapshot
from .l0_experiments import l0_experiment_policies
from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD


WAIT = "WAIT"
HOLD = "HOLD"
SHADOW_QUALIFIED = "SHADOW_QUALIFIED"
SHADOW_BUY = "SHADOW_BUY"
SHADOW_EXIT = "SHADOW_EXIT"
ACTIONS = frozenset({WAIT, HOLD, SHADOW_QUALIFIED, SHADOW_BUY, SHADOW_EXIT})

ProbeResult = tuple[str, str, dict[str, Any], dict[str, Any]]

STAGED_PROBE_POLICY = MappingProxyType({
    "version": "staged-probe-5u-shadow-15u/v1",
    "checkpoint_60_seconds": 60.0,
    "checkpoint_120_seconds": 120.0,
    "checkpoint_tolerance_seconds": 15.0,
    "maximum_frame_age_seconds": 15.0,
    "shadow_notional_usd": 15.0,
    "entry_slippage_bps": 400,
})


def staged_probe_policies() -> list[dict[str, Any]]:
    """Return the three same-entry S03 risk baselines."""
    parent = next(
        policy for policy in l0_experiment_policies()
        if policy["arm_id"] == "l0_continuation_failure_control_v1"
    )
    specs = (
        ("staged_probe_20u_once_control_v1", "20u_once_control", 20.0),
        ("staged_probe_5u_only_control_v1", "5u_only_control", 5.0),
        (
            "staged_probe_5u_conditional_15u_shadow_v1",
            "bounded_5u_then_shadow_15u",
            5.0,
        ),
    )
    policies = []
    for arm_id, probe_kind, notional in specs:
        policy = copy.deepcopy(parent)
        candidate = probe_kind == "bounded_5u_then_shadow_15u"
        policy.update({
            "arm_id": arm_id,
            "canonical_id": arm_id,
            "name": arm_id,
            "description": (
                "S03 Broad同入场风险基准；5U正式Paper，确认后的15U仅作有限Shadow。"
                if candidate else "S03 Broad同入场风险基准对照。"
            ),
            "entry_family": "broad_launch",
            "source_entry_family": "broad_launch",
            "entry_match_mode": "isolated_cohort_observer",
            "entry_gate": "v6_asof_family",
            "paired_opportunity_group": "staged_probe_s03",
            "paired_opportunity_semantics": "same_passive_broad_signal_different_notional_fills",
            "capital_experiment": False,
            "probe_kind": probe_kind,
            "notional_usd": notional,
            "shadow_notional_usd": 15.0 if candidate else 0.0,
            "shadow_affects_formal_pnl": False,
            "probe_policy": dict(STAGED_PROBE_POLICY) if candidate else {},
            "source_arm_ids": ["l0_continuation_failure_control_v1"],
            "required_inputs": ["broad_launch", "original_pool_l0_frames"],
            "no_historical_backfill": True,
        })
        policy.pop("paired_entry_group", None)
        policy["entry_filter"] = {
            "direction": "broad_launch",
            "paired_entry_kind": "staged_probe_s03",
        }
        policies.append(policy)
    return policies


def _result(
    action: str,
    reason: str,
    state: dict[str, Any],
    evidence: Mapping[str, Any],
) -> ProbeResult:
    if action not in ACTIONS:
        raise ValueError("invalid_probe_action")
    return action, reason, state, dict(evidence)


def _market_values(frame: Mapping[str, Any]) -> tuple[float | None, float | None]:
    price = _number(frame.get("price_usd"))
    liquidity = _number(frame.get("liquidity_usd"))
    return (
        price if price is not None and price > 0.0 else None,
        liquidity if liquidity is not None and liquidity >= 0.0 else None,
    )


def evaluate_staged_probe(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = STAGED_PROBE_POLICY,
) -> ProbeResult:
    """Advance S03 from L0 confirmation through bounded Shadow BUY/exit markers.

    A normal frame supplies original-pool ``price_usd`` and ``liquidity_usd``;
    the 120-second frame also supplies the formal 5U ``net_recovery_usd``.
    A later formal close uses ``event_kind='formal_exit_quote'`` plus its actual
    sold token quantity and net recovery, allowing the Shadow leg to reuse the
    same net per-token exit marker without entering the formal ledger.
    """
    policy = _policy_snapshot(policy)
    execution = dict(policy.get("_execution", {}))
    new_state, evidence, error = _begin(
        "staged_probe_5u_shadow_15u", {k: v for k, v in policy.items() if k != "_execution"},
        position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if frame.get("original_pool") is not True:
        return _result(WAIT, "original_pool_identity_required", new_state, evidence)

    event_kind = str(frame.get("event_kind") or "market_frame")
    if event_kind == "formal_exit_quote":
        return _record_shadow_exit(new_state, evidence, frame)
    if event_kind != "market_frame":
        return _result(WAIT, "unsupported_probe_event", new_state, evidence)

    status = str(new_state.get("status") or "MONITORING")
    if status == "SHADOW_OPEN":
        return _result(HOLD, "shadow_leg_already_open", new_state, evidence)
    if status == "SHADOW_CLOSED":
        return _result(HOLD, "shadow_leg_already_closed", new_state, evidence)
    if status in {"COMPLETE_NO_SHADOW", "EXPIRED"}:
        return _result(HOLD, "probe_review_finished", new_state, evidence)

    price, liquidity = _market_values(frame)
    evidence.update({"price_usd": price, "liquidity_usd": liquidity})
    if status == "QUALIFIED":
        if price is None or liquidity is None:
            return _result(WAIT, "shadow_entry_frame_missing", new_state, evidence)
        minimum_liquidity = float(execution.get("min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD))
        if liquidity < minimum_liquidity:
            evidence["minimum_pool_liquidity_usd"] = minimum_liquidity
            return _result(
                WAIT, "shadow_entry_pool_liquidity_below_shared_floor",
                new_state, evidence,
            )
        qualified_at = _as_time(new_state.get("qualified_at_observed_at"))
        observed_at = _as_time(frame.get("observed_at"))
        if qualified_at is None or observed_at is None or observed_at <= qualified_at:
            return _result(WAIT, "independent_post_confirmation_frame_required", new_state, evidence)
        shadow_cost = float(policy["shadow_notional_usd"])
        buy_slippage = int(execution.get("buy_slippage_bps", policy["entry_slippage_bps"]))
        fee = float(execution.get("additional_fee_usd_each_fill", 0.0))
        adverse_price = price * (
            1.0 + buy_slippage / 10_000.0
        )
        shadow_fill = {
            "frame_id": str(frame["frame_id"]),
            "observed_at": frame["observed_at"],
            "recorded_at": frame["recorded_at"],
            "market_price_usd": price,
            "execution_price_usd": adverse_price,
            "notional_usd": shadow_cost,
            "total_cost_usd": shadow_cost + fee,
            "fee_usd": fee,
            "quantity_tokens": shadow_cost / adverse_price,
            "entry_slippage_bps": buy_slippage,
        }
        new_state["status"] = "SHADOW_OPEN"
        new_state["shadow_fill"] = shadow_fill
        evidence.update({
            "shadow_fill": shadow_fill,
            "affects_formal_pnl": False,
            "formal_quantity_unchanged": True,
        })
        return _result(SHADOW_BUY, "shadow_second_leg_recorded", new_state, evidence)

    elapsed = float(evidence["elapsed_seconds"])
    target_60 = float(policy["checkpoint_60_seconds"])
    target_120 = float(policy["checkpoint_120_seconds"])
    tolerance = float(policy["checkpoint_tolerance_seconds"])
    if elapsed < target_60 - tolerance:
        return _result(WAIT, "probe_60_checkpoint_not_due", new_state, evidence)
    if elapsed <= target_60 + tolerance and "checkpoint_60" not in new_state:
        if price is None or liquidity is None:
            return _result(WAIT, "probe_60_checkpoint_missing", new_state, evidence)
        new_state["checkpoint_60"] = {
            "frame_id": str(frame["frame_id"]),
            "observed_at": frame["observed_at"],
            "recorded_at": frame["recorded_at"],
            "price_usd": price,
            "liquidity_usd": liquidity,
        }
        return _result(HOLD, "probe_60_checkpoint_recorded", new_state, evidence)
    if "checkpoint_60" not in new_state:
        new_state["status"] = "EXPIRED"
        return _result(WAIT, "probe_60_checkpoint_expired", new_state, evidence)
    if elapsed < target_120 - tolerance:
        return _result(HOLD, "probe_120_checkpoint_not_due", new_state, evidence)
    if elapsed > target_120 + tolerance:
        new_state["status"] = "EXPIRED"
        return _result(WAIT, "probe_120_checkpoint_expired", new_state, evidence)

    net_recovery = _number(frame.get("net_recovery_usd"))
    probe_cost = _number(position.get("probe_cost_usd"))
    if probe_cost is None:
        probe_cost = _number(position.get("stake_usd"))
    if (
        price is None
        or liquidity is None
        or net_recovery is None
        or probe_cost is None
        or probe_cost <= 0.0
    ):
        return _result(WAIT, "probe_120_checkpoint_missing", new_state, evidence)
    checkpoint_60 = new_state["checkpoint_60"]
    cost_covered = net_recovery >= probe_cost
    market_improved = bool(
        price > float(checkpoint_60["price_usd"])
        and liquidity >= float(checkpoint_60["liquidity_usd"])
    )
    qualified = cost_covered or market_improved
    checkpoint_120 = {
        "frame_id": str(frame["frame_id"]),
        "observed_at": frame["observed_at"],
        "recorded_at": frame["recorded_at"],
        "price_usd": price,
        "liquidity_usd": liquidity,
        "net_recovery_usd": net_recovery,
        "probe_cost_usd": probe_cost,
        "cost_covered": cost_covered,
        "market_improved": market_improved,
    }
    new_state["checkpoint_120"] = checkpoint_120
    evidence.update(checkpoint_120)
    if not qualified:
        new_state["status"] = "COMPLETE_NO_SHADOW"
        return _result(HOLD, "shadow_second_leg_not_qualified", new_state, evidence)
    new_state["status"] = "QUALIFIED"
    new_state["qualified_at_observed_at"] = frame["observed_at"]
    new_state["qualification_frame_id"] = str(frame["frame_id"])
    evidence.update({
        "shadow_notional_usd": float(policy["shadow_notional_usd"]),
        "required_fill": "next_fresh_original_pool_frame",
        "affects_formal_pnl": False,
    })
    return _result(
        SHADOW_QUALIFIED, "shadow_second_leg_qualified", new_state, evidence
    )


def _record_shadow_exit(
    state: dict[str, Any],
    evidence: dict[str, Any],
    marker: Mapping[str, Any],
) -> ProbeResult:
    status = str(state.get("status") or "MONITORING")
    if status == "SHADOW_CLOSED":
        return _result(HOLD, "shadow_leg_already_closed", state, evidence)
    shadow_fill = state.get("shadow_fill")
    if status != "SHADOW_OPEN" or not isinstance(shadow_fill, Mapping):
        return _result(WAIT, "shadow_leg_not_open", state, evidence)
    if marker.get("formal_exit_closes_position") is not True:
        return _result(WAIT, "formal_closing_exit_required", state, evidence)
    formal_quantity = _number(marker.get("formal_exit_quantity_tokens"))
    formal_recovery = _number(marker.get("formal_exit_net_recovery_usd"))
    shadow_quantity = _number(shadow_fill.get("quantity_tokens"))
    shadow_cost = _number(shadow_fill.get("total_cost_usd", shadow_fill.get("notional_usd")))
    if (
        formal_quantity is None
        or formal_quantity <= 0.0
        or formal_recovery is None
        or formal_recovery < 0.0
        or shadow_quantity is None
        or shadow_quantity <= 0.0
        or shadow_cost is None
        or shadow_cost <= 0.0
    ):
        return _result(WAIT, "formal_exit_quote_values_required", state, evidence)
    # A fixed fee cannot be scaled by the formal/shadow quantity ratio.
    exit_fee = _number(marker.get("formal_exit_fee_usd")) or 0.0
    net_unit_price = (formal_recovery + exit_fee) / formal_quantity
    shadow_recovery = max(0.0, shadow_quantity * net_unit_price - exit_fee)
    shadow_pnl = shadow_recovery - shadow_cost
    shadow_exit = {
        "marker_id": str(marker["frame_id"]),
        "observed_at": marker["observed_at"],
        "recorded_at": marker["recorded_at"],
        "formal_exit_quantity_tokens": formal_quantity,
        "formal_exit_net_recovery_usd": formal_recovery,
        "net_exit_price_per_token_usd": net_unit_price,
        "shadow_net_recovery_usd": shadow_recovery,
        "shadow_net_pnl_usd": shadow_pnl,
        "shadow_return": shadow_pnl / shadow_cost,
        "affects_formal_pnl": False,
        "formal_quantity_unchanged": True,
    }
    state["status"] = "SHADOW_CLOSED"
    state["shadow_exit"] = shadow_exit
    evidence["shadow_exit"] = shadow_exit
    return _result(SHADOW_EXIT, "shadow_exit_recorded_from_formal_quote", state, evidence)


__all__ = [
    "STAGED_PROBE_POLICY",
    "ProbeResult",
    "WAIT",
    "HOLD",
    "SHADOW_QUALIFIED",
    "SHADOW_BUY",
    "SHADOW_EXIT",
    "staged_probe_policies",
    "evaluate_staged_probe",
]
