"""Strictly-forward, side-effect-free capital exit evaluators.

Every public evaluator returns ``(action, reason, new_state, evidence)`` where
``action`` is one of ``WAIT``, ``HOLD``, ``SELL`` or ``SELL_PARTIAL``.  Callers
own persistence and execution.  In particular, a Vault/Recovery ``SELL`` is a
trigger only: its evidence requires a later amount-specific quote and never
claims a DEX fill, rug, or dead surface.

Common position fields:
    ``opened_at`` (UTC timestamp), ``token_id`` and ``pair_address``.

Common frame fields:
    ``frame_id``, ``observed_at``, ``recorded_at``, ``token_id`` and
    ``pair_address``.  Both timestamps must be strictly after ``opened_at``, no
    later than caller-supplied ``now``, and the observation may be at most 15s
    old. Frames must advance the observation watermark.

Flow-based evaluators additionally require ``flow_semantics='actual_notional'``
and ``net_quote_flow_usd``.  Count-only or inferred flow is never promoted to
actual capital evidence.

Strategy-specific required fields are documented on each evaluator.  State is
JSON-serializable and is copied before use; neither input mappings nor frames
are mutated.  A valid immutable frame id is processed at most once per state.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping


WAIT = "WAIT"
HOLD = "HOLD"
SELL = "SELL"
SELL_PARTIAL = "SELL_PARTIAL"
ACTIONS = frozenset({WAIT, HOLD, SELL, SELL_PARTIAL})
POST_TRIGGER_AMOUNT_QUOTE = "post_trigger_amount_specific_quote"

ExitResult = tuple[str, str, dict[str, Any], dict[str, Any]]


EARN_THE_HOLD_POLICY = MappingProxyType({
    "version": "earn-the-hold/v1",
    "review_start_seconds": 60.0,
    "review_deadline_seconds": 120.0,
    "minimum_position_value_ratio": 1.0,
    "minimum_price_return": 0.0,
    "minimum_effective_depth_ratio": 0.90,
    "minimum_net_quote_flow_usd": 0.0,
    "maximum_frame_age_seconds": 15.0,
})

FAILED_CONTINUATION_POLICY = MappingProxyType({
    "version": "failed-continuation-profit-lock/v1",
    "minimum_positive_economic_return": 0.0,
    "minimum_bad_frames": 2,
    "maximum_depth_change_ratio": -0.10,
    "maximum_liquidity_change_ratio": -0.15,
    "maximum_breadth_change_ratio": -0.25,
    "maximum_frame_age_seconds": 15.0,
})

PRICE_TO_FLOW_POLICY = MappingProxyType({
    "version": "price-to-flow-fragility/v1",
    "minimum_price_change_ratio": 0.30,
    "maximum_net_quote_flow_usd": 0.0,
    "maximum_depth_change_ratio": -0.10,
    "maximum_breadth_change_ratio": -0.25,
    "minimum_top3_buy_notional_share": 0.70,
    "maximum_frame_age_seconds": 15.0,
})

CREATOR_DISTRIBUTION_POLICY = MappingProxyType({
    "version": "creator-early-holder-distribution/v1",
    "minimum_distribution_notional_usd": 100.0,
    "minimum_distribution_sell_share": 0.35,
    "maximum_net_quote_flow_usd": 0.0,
    "maximum_depth_change_ratio": -0.10,
    "maximum_breadth_change_ratio": -0.20,
    "minimum_bad_frames": 2,
    "maximum_frame_age_seconds": 15.0,
})

VAULT_HAZARD_POLICY = MappingProxyType({
    "version": "vault-hazard-exit/v1",
    "minimum_bad_frames": 2,
    "extreme_red_raw_quote_change_ratio": -0.35,
    "extreme_red_effective_quote_change_ratio": -0.35,
    "maximum_frame_age_seconds": 15.0,
    "maximum_confirmation_gap_seconds": 15.0,
})

EXECUTABLE_RECOVERY_POLICY = MappingProxyType({
    "version": "executable-recovery-decay/v1",
    "arm_recovery_ratio": 1.40,
    "drawdown_from_running_high": 0.15,
    "maximum_frame_age_seconds": 15.0,
})

HIGH_RECALL_EXIT_POLICY = MappingProxyType({
    "version": "high-recall-earn-harvest-dead-wave-exit/v1",
    "review_start_seconds": 60.0,
    "review_deadline_seconds": 120.0,
    "minimum_position_value_ratio": 1.0,
    "minimum_price_return": 0.0,
    "minimum_effective_depth_ratio": 0.90,
    "minimum_net_quote_flow_usd": 0.0,
    "harvest_economic_return": 0.12,
    "minimum_dead_wave_frames": 2,
    "maximum_depth_change_ratio": -0.10,
    "maximum_liquidity_change_ratio": -0.15,
    "maximum_breadth_change_ratio": -0.25,
    "maximum_frame_age_seconds": 15.0,
})

VALUE_KINDS = frozenset({"market", "economic", "amount_specific_net"})


def _as_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _copy_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    return copy.deepcopy(dict(state or {}))


def _policy_snapshot(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    snapshot = copy.deepcopy(dict(policy))
    if not str(snapshot.get("version") or "").strip():
        raise ValueError("exit_policy_version_required")
    return MappingProxyType(snapshot)


def _policy_fingerprint(policy: Mapping[str, Any]) -> str:
    return "|".join(f"{key}={policy[key]!r}" for key in sorted(policy))


def _result(
    action: str,
    reason: str,
    state: dict[str, Any],
    evidence: Mapping[str, Any],
) -> ExitResult:
    if action not in ACTIONS:
        raise ValueError("invalid_exit_action")
    return action, reason, state, dict(evidence)


def _begin(
    strategy: str,
    policy: Mapping[str, Any],
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    now: Any,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    new_state = _copy_state(state)
    frame_id = str(frame.get("frame_id") or "").strip()
    opened_at = _as_time(position.get("opened_at"))
    observed_at = _as_time(frame.get("observed_at"))
    recorded_at = _as_time(frame.get("recorded_at"))
    decision_now = _as_time(now)
    evidence = {
        "strategy": strategy,
        "policy_version": str(policy["version"]),
        "frame_id": frame_id or None,
        "observed_at": frame.get("observed_at"),
        "recorded_at": frame.get("recorded_at"),
    }
    fingerprint = _policy_fingerprint(policy)
    prior_fingerprint = str(new_state.get("policy_fingerprint") or "")
    if prior_fingerprint and prior_fingerprint != fingerprint:
        return new_state, evidence, "policy_changed_for_existing_state"
    if not frame_id:
        return new_state, evidence, "missing_frame_id"
    if None in {opened_at, observed_at, recorded_at, decision_now}:
        return new_state, evidence, "missing_or_invalid_timestamp"
    assert opened_at is not None and observed_at is not None
    assert recorded_at is not None and decision_now is not None
    if not (opened_at < observed_at <= recorded_at <= decision_now):
        return new_state, evidence, "noncausal_or_future_frame"
    frame_age = (decision_now - observed_at).total_seconds()
    evidence["frame_age_seconds"] = frame_age
    if frame_age > float(policy["maximum_frame_age_seconds"]):
        return new_state, evidence, "stale_frame"
    position_token = str(position.get("token_id") or "").strip()
    position_pair = str(position.get("pair_address") or "").strip()
    frame_token = str(frame.get("token_id") or "").strip()
    frame_pair = str(frame.get("pair_address") or "").strip()
    evidence.update({"token_id": frame_token or None, "pair_address": frame_pair or None})
    if not position_token or not position_pair or not frame_token or not frame_pair:
        return new_state, evidence, "missing_position_or_frame_identity"
    if position_token != frame_token or position_pair != frame_pair:
        return new_state, evidence, "frame_position_mismatch"
    prior_frame_id = str(new_state.get("last_frame_id") or "")
    prior_observed_at = _as_time(new_state.get("last_observed_at"))
    if frame_id == prior_frame_id:
        evidence["duplicate"] = True
        return new_state, evidence, "duplicate_frame"
    if prior_observed_at is not None and observed_at <= prior_observed_at:
        return new_state, evidence, "out_of_order_frame"
    new_state.pop("processed_frame_ids", None)
    new_state["policy_fingerprint"] = fingerprint
    new_state["last_frame_id"] = frame_id
    new_state["last_observed_at"] = observed_at.isoformat()
    evidence["elapsed_seconds"] = (observed_at - opened_at).total_seconds()
    return new_state, evidence, None


def _actual_flow(frame: Mapping[str, Any]) -> tuple[float | None, str | None]:
    if str(frame.get("flow_semantics") or "") != "actual_notional":
        return None, "actual_notional_flow_required"
    flow = _number(frame.get("net_quote_flow_usd"))
    if flow is None:
        return None, "missing_actual_net_quote_flow"
    return flow, None


def _value_kind(frame: Mapping[str, Any]) -> tuple[str, str | None]:
    kind = str(frame.get("value_kind") or "").strip()
    if kind not in VALUE_KINDS:
        return kind, "explicit_value_kind_required"
    return kind, None


def _marked_value(frame: Mapping[str, Any]) -> tuple[float | None, str | None, str]:
    kind, kind_error = _value_kind(frame)
    if kind_error:
        return None, kind_error, kind
    value = _number(frame.get("position_value_ratio"))
    if value is None or value < 0.0:
        return None, "missing_or_invalid_position_value_ratio", kind
    return value, None, kind


def _structure_bad(
    frame: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[bool | None, dict[str, float | None]]:
    depth = _number(frame.get("effective_depth_change_ratio"))
    liquidity = _number(frame.get("liquidity_change_ratio"))
    breadth = _number(frame.get("effective_buyer_breadth_change_ratio"))
    facts = {
        "effective_depth_change_ratio": depth,
        "liquidity_change_ratio": liquidity,
        "effective_buyer_breadth_change_ratio": breadth,
    }
    if depth is None and liquidity is None and breadth is None:
        return None, facts
    return bool(
        (depth is not None and depth <= float(policy["maximum_depth_change_ratio"]))
        or (
            liquidity is not None
            and liquidity <= float(policy["maximum_liquidity_change_ratio"])
        )
        or (
            breadth is not None
            and breadth <= float(policy["maximum_breadth_change_ratio"])
        )
        or str(frame.get("vault_direction") or "") == "SELL_LIKE_NET"
    ), facts


def _update_running_peak(
    state: dict[str, Any], *, prefix: str, epoch: str, unit: str, value: float
) -> tuple[float | None, float, bool, bool]:
    key = f"{epoch}:{unit}"
    old_key = str(state.get(f"{prefix}_peak_key") or "")
    reset = old_key != key
    prior = None if reset else _number(state.get(f"{prefix}_running_peak"))
    is_new_high = prior is None or value > prior
    peak = value if prior is None else max(prior, value)
    state[f"{prefix}_peak_key"] = key
    state[f"{prefix}_running_peak"] = peak
    return prior, peak, is_new_high, reset


def validate_sell_fraction(value: Any, *, partial: bool) -> float:
    """Validate a full or partial fraction without silently clipping quantity."""
    fraction = _number(value)
    if fraction is None or fraction <= 0.0 or fraction > 1.0:
        raise ValueError("sell_fraction_out_of_range")
    if partial and fraction >= 1.0:
        raise ValueError("partial_sell_fraction_must_be_below_one")
    return fraction


def evaluate_earn_the_hold(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = EARN_THE_HOLD_POLICY,
) -> ExitResult:
    """Qualify a 60-120s probation using recovery, price, depth and actual flow.

    Frame fields: ``position_value_ratio``, explicit ``value_kind``, ``price_return``,
    ``effective_depth_ratio``, ``flow_semantics``, ``net_quote_flow_usd``.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "earn_the_hold", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if new_state.get("qualification") == "EARNED_HOLD":
        return _result(HOLD, "hold_already_earned", new_state, evidence)
    elapsed = float(evidence["elapsed_seconds"])
    if elapsed < float(policy["review_start_seconds"]):
        new_state.setdefault("qualification", "PROBATION")
        return _result(WAIT, "probation_window_not_started", new_state, evidence)
    flow, flow_error = _actual_flow(frame)
    value_ratio, value_error, value_kind = _marked_value(frame)
    price_return = _number(frame.get("price_return"))
    depth = _number(frame.get("effective_depth_ratio"))
    evidence.update({
        "position_value_ratio": value_ratio,
        "value_kind": value_kind or None,
        "price_return": price_return,
        "effective_depth_ratio": depth,
        "net_quote_flow_usd": flow,
    })
    if flow_error or value_error or None in {value_ratio, price_return, depth}:
        return _result(
            WAIT,
            flow_error or value_error or "missing_probation_evidence",
            new_state,
            evidence,
        )
    healthy = bool(
        value_ratio >= float(policy["minimum_position_value_ratio"])
        and price_return >= float(policy["minimum_price_return"])
        and depth >= float(policy["minimum_effective_depth_ratio"])
        and flow >= float(policy["minimum_net_quote_flow_usd"])
    )
    evidence["healthy_continuation"] = healthy
    if healthy:
        new_state["qualification"] = "EARNED_HOLD"
        new_state["earned_at_frame_id"] = str(frame["frame_id"])
        return _result(HOLD, "probation_earned_hold", new_state, evidence)
    if elapsed < float(policy["review_deadline_seconds"]):
        new_state["qualification"] = "PROBATION"
        return _result(HOLD, "probation_continues", new_state, evidence)
    new_state["qualification"] = "FAILED_CONTINUATION"
    evidence["sell_fraction"] = 1.0
    return _result(SELL, "earn_the_hold_deadline_failed", new_state, evidence)


def evaluate_failed_continuation_profit_lock(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = FAILED_CONTINUATION_POLICY,
) -> ExitResult:
    """Exit a cost-covered profitable remainder after two deteriorating frames.

    Position fields: ``principal_recovered`` (or ``cost_covered``).
    Frame fields: ``position_value_ratio``, explicit ``value_kind``,
    ``economic_return`` and actual flow plus at
    least one structural change ratio accepted by :func:`_structure_bad`.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "failed_continuation_profit_lock", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if not bool(position.get("principal_recovered") or position.get("cost_covered")):
        return _result(WAIT, "cost_not_yet_recovered", new_state, evidence)
    flow, flow_error = _actual_flow(frame)
    value_ratio, value_error, value_kind = _marked_value(frame)
    economic_return = _number(frame.get("economic_return"))
    structure_bad, structure = _structure_bad(frame, policy)
    evidence.update({
        "net_quote_flow_usd": flow,
        "position_value_ratio": value_ratio,
        "value_kind": value_kind or None,
        "economic_return": economic_return,
        **structure,
    })
    if flow_error or value_error or economic_return is None:
        return _result(
            WAIT,
            flow_error or value_error or "missing_profit_lock_evidence",
            new_state,
            evidence,
        )
    if structure_bad is None:
        return _result(WAIT, "missing_structural_evidence", new_state, evidence)
    prior, peak, new_high, reset = _update_running_peak(
        new_state,
        prefix="profit_lock",
        epoch="position",
        unit=value_kind,
        value=value_ratio,
    )
    bad = bool(
        economic_return > float(policy["minimum_positive_economic_return"])
        and not new_high
        and flow < 0.0
        and structure_bad
    )
    streak = 0 if reset or not bad else int(new_state.get("profit_lock_bad_streak") or 0) + 1
    new_state["profit_lock_bad_streak"] = streak
    evidence.update({
        "prior_running_peak": prior,
        "running_peak": peak,
        "new_high": new_high,
        "peak_reset": reset,
        "deterioration_streak": streak,
    })
    if streak >= int(policy["minimum_bad_frames"]):
        new_state["profit_lock_status"] = "FAILED_CONTINUATION"
        evidence["sell_fraction"] = 1.0
        return _result(SELL, "two_frame_failed_continuation", new_state, evidence)
    return _result(HOLD, "profit_lock_monitoring", new_state, evidence)


def evaluate_price_to_flow_fragility(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = PRICE_TO_FLOW_POLICY,
) -> ExitResult:
    """Exit a blowoff whose price rise is unsupported by actual capital flow."""
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "price_to_flow_fragility", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    flow, flow_error = _actual_flow(frame)
    value_kind, value_error = _value_kind(frame)
    price = _number(frame.get("price_change_ratio_60s"))
    depth = _number(frame.get("effective_depth_change_ratio"))
    breadth = _number(frame.get("effective_buyer_breadth_change_ratio"))
    concentration = _number(frame.get("top3_buy_notional_share"))
    evidence.update({
        "price_change_ratio_60s": price,
        "net_quote_flow_usd": flow,
        "effective_depth_change_ratio": depth,
        "effective_buyer_breadth_change_ratio": breadth,
        "top3_buy_notional_share": concentration,
        "value_kind": value_kind or None,
    })
    if flow_error or value_error or None in {price, depth, breadth, concentration}:
        return _result(
            WAIT,
            flow_error or value_error or "missing_price_flow_evidence",
            new_state,
            evidence,
        )
    fragile = bool(
        price >= float(policy["minimum_price_change_ratio"])
        and flow <= float(policy["maximum_net_quote_flow_usd"])
        and depth <= float(policy["maximum_depth_change_ratio"])
        and breadth <= float(policy["maximum_breadth_change_ratio"])
        and concentration >= float(policy["minimum_top3_buy_notional_share"])
    )
    evidence["fragile_blowoff"] = fragile
    if fragile:
        evidence["sell_fraction"] = 1.0
        return _result(SELL, "price_rise_without_capital_support", new_state, evidence)
    return _result(HOLD, "price_flow_not_fragile", new_state, evidence)


def evaluate_creator_early_holder_distribution(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = CREATOR_DISTRIBUTION_POLICY,
) -> ExitResult:
    """Use dynamic creator/early-holder selling, never a static address label.

    ``creator_or_early_holder_sell_notional_usd`` must be a de-duplicated actual
    notional subset of ``total_sell_notional_usd``.  Two independent bad frames
    are required.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "creator_early_holder_distribution", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    flow, flow_error = _actual_flow(frame)
    distributed = _number(frame.get("creator_or_early_holder_sell_notional_usd"))
    total_sell = _number(frame.get("total_sell_notional_usd"))
    depth = _number(frame.get("effective_depth_change_ratio"))
    breadth = _number(frame.get("effective_buyer_breadth_change_ratio"))
    if (
        flow_error
        or None in {distributed, total_sell, depth, breadth}
        or distributed < 0.0
        or total_sell <= 0.0
        or distributed > total_sell
    ):
        return _result(
            WAIT,
            flow_error or "missing_or_invalid_distribution_evidence",
            new_state,
            evidence,
        )
    share = distributed / total_sell
    bad = bool(
        distributed >= float(policy["minimum_distribution_notional_usd"])
        and share >= float(policy["minimum_distribution_sell_share"])
        and flow <= float(policy["maximum_net_quote_flow_usd"])
        and depth <= float(policy["maximum_depth_change_ratio"])
        and breadth <= float(policy["maximum_breadth_change_ratio"])
    )
    streak = int(new_state.get("distribution_bad_streak") or 0) + 1 if bad else 0
    new_state["distribution_bad_streak"] = streak
    evidence.update({
        "creator_or_early_holder_sell_notional_usd": distributed,
        "total_sell_notional_usd": total_sell,
        "distribution_sell_share": share,
        "net_quote_flow_usd": flow,
        "effective_depth_change_ratio": depth,
        "effective_buyer_breadth_change_ratio": breadth,
        "deterioration_streak": streak,
    })
    if streak >= int(policy["minimum_bad_frames"]):
        evidence["sell_fraction"] = 1.0
        return _result(SELL, "dynamic_distribution_confirmed", new_state, evidence)
    return _result(HOLD, "distribution_monitoring", new_state, evidence)


def evaluate_vault_hazard(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = VAULT_HAZARD_POLICY,
) -> ExitResult:
    """Require two increasing coherent confirmed SELL-like Vault frames.

    Frame fields: ``pool_target_id``, ``slot_min``, ``slot_max``,
    ``commitment='confirmed'``, ``effective_quote_reserve_known``,
    ``latest_direction``, ``base_change_ratio``, ``raw_quote_change_ratio`` and
    ``effective_quote_change_ratio``.  ``LP_REMOVE_LIKE`` is retained as
    separate evidence and cannot satisfy SELL-like flow.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "vault_hazard", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    pool = str(frame.get("pool_target_id") or "").strip()
    slot_min = frame.get("slot_min")
    slot_max = frame.get("slot_max")
    try:
        slot_min_int, slot_max_int = int(slot_min), int(slot_max)
    except (TypeError, ValueError):
        slot_min_int = slot_max_int = 0
    coherent = bool(
        pool
        and pool == str(position.get("pair_address") or "").strip()
        and slot_min_int > 0
        and slot_min_int == slot_max_int
        and str(frame.get("commitment") or "") == "confirmed"
        and frame.get("effective_quote_reserve_known") is True
    )
    direction = str(frame.get("latest_direction") or "")
    base_change = _number(frame.get("base_change_ratio"))
    raw_quote_change = _number(frame.get("raw_quote_change_ratio"))
    effective_change = _number(frame.get("effective_quote_change_ratio"))
    evidence.update({
        "pool_target_id": pool or None,
        "slot": slot_max_int or None,
        "coherent_confirmed": coherent,
        "latest_direction": direction or None,
        "base_change_ratio": base_change,
        "raw_quote_change_ratio": raw_quote_change,
        "effective_quote_change_ratio": effective_change,
        "lp_remove_observed": direction == "LP_REMOVE_LIKE",
    })
    if not coherent or None in {base_change, raw_quote_change, effective_change}:
        new_state["vault_qualifying_slots"] = []
        new_state.pop("vault_last_qualifying_observed_at", None)
        return _result(WAIT, "invalid_or_incomplete_vault_frame", new_state, evidence)
    prior_pool = str(new_state.get("vault_pool_target_id") or "")
    prior_seen_slot = int(new_state.get("vault_last_seen_slot") or 0)
    if prior_pool and prior_pool != pool:
        new_state["vault_qualifying_slots"] = []
        new_state.pop("vault_last_qualifying_observed_at", None)
        prior_seen_slot = 0
    new_state["vault_pool_target_id"] = pool
    if slot_max_int <= prior_seen_slot:
        new_state["vault_qualifying_slots"] = []
        new_state.pop("vault_last_qualifying_observed_at", None)
        return _result(WAIT, "vault_slot_not_strictly_increasing", new_state, evidence)
    new_state["vault_last_seen_slot"] = slot_max_int
    sell_like = bool(
        direction == "SELL_LIKE_NET"
        and base_change > 0.0
        and raw_quote_change < 0.0
        and effective_change < 0.0
    )
    if not sell_like:
        new_state["vault_qualifying_slots"] = []
        new_state.pop("vault_last_qualifying_observed_at", None)
        reason = "lp_remove_is_separate_evidence" if direction == "LP_REMOVE_LIKE" else "vault_sell_flow_not_confirmed"
        return _result(HOLD, reason, new_state, evidence)
    extreme = bool(
        raw_quote_change
        <= float(policy["extreme_red_raw_quote_change_ratio"])
        and effective_change
        <= float(policy["extreme_red_effective_quote_change_ratio"])
    )
    observed_at = _as_time(frame.get("observed_at"))
    prior_qualifying_at = _as_time(new_state.get("vault_last_qualifying_observed_at"))
    contiguous = bool(
        observed_at is not None
        and prior_qualifying_at is not None
        and 0.0 < (observed_at - prior_qualifying_at).total_seconds()
        <= float(policy["maximum_confirmation_gap_seconds"])
    )
    slots = [int(value) for value in new_state.get("vault_qualifying_slots") or []]
    slots = slots[-1:] if contiguous else []
    slots.append(slot_max_int)
    slots = slots[-2:]
    new_state["vault_qualifying_slots"] = slots
    new_state["vault_last_qualifying_observed_at"] = frame.get("observed_at")
    evidence.update({
        "qualifying_slots": list(slots),
        "extreme_exact_red": extreme,
        "risk_state": "RED",
    })
    if len(slots) >= int(policy["minimum_bad_frames"]):
        evidence.update({
            "sell_fraction": 1.0,
            "required_fill": POST_TRIGGER_AMOUNT_QUOTE,
            "dead_surface_claimed": False,
        })
        return _result(
            SELL,
            "two_frame_extreme_exact_red" if extreme else "two_frame_vault_unwind",
            new_state,
            evidence,
        )
    return _result(HOLD, "vault_unwind_needs_independent_confirmation", new_state, evidence)


def evaluate_executable_recovery_decay(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = EXECUTABLE_RECOVERY_POLICY,
) -> ExitResult:
    """Track the running high of a net amount-specific executable recovery ratio.

    Frame fields: ``amount_epoch``, ``amount_unit``, ``input_amount_raw``,
    ``executable_recovery_ratio``, ``recovery_semantics='amount_specific_net'``,
    ``fees_included=True`` and ``slippage_included=True``.  A unit or amount
    epoch change resets the peak before the frame is evaluated.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "executable_recovery_decay", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    epoch = str(frame.get("amount_epoch") or "").strip()
    unit = str(frame.get("amount_unit") or "").strip()
    input_raw = frame.get("input_amount_raw")
    try:
        input_raw_int = int(input_raw)
    except (TypeError, ValueError):
        input_raw_int = 0
    recovery = _number(frame.get("executable_recovery_ratio"))
    semantics_ok = bool(
        str(frame.get("recovery_semantics") or "") == "amount_specific_net"
        and frame.get("fees_included") is True
        and frame.get("slippage_included") is True
    )
    evidence.update({
        "amount_epoch": epoch or None,
        "amount_unit": unit or None,
        "input_amount_raw": input_raw_int or None,
        "executable_recovery_ratio": recovery,
        "amount_specific_net": semantics_ok,
    })
    if not epoch or not unit or input_raw_int <= 0 or recovery is None or recovery < 0.0:
        return _result(WAIT, "missing_or_invalid_amount_epoch", new_state, evidence)
    if not semantics_ok:
        return _result(WAIT, "net_amount_specific_recovery_required", new_state, evidence)
    prior, peak, new_high, reset = _update_running_peak(
        new_state,
        prefix="executable_recovery",
        epoch=epoch,
        unit=unit,
        value=recovery,
    )
    armed = prior is not None and peak >= float(policy["arm_recovery_ratio"])
    triggered = bool(
        armed
        and not new_high
        and recovery
        <= peak * (1.0 - float(policy["drawdown_from_running_high"]))
    )
    evidence.update({
        "prior_running_peak": prior,
        "running_peak": peak,
        "new_high": new_high,
        "peak_reset": reset,
        "armed": armed,
        "drawdown_from_running_high": recovery / peak - 1.0 if peak > 0 else None,
    })
    if triggered:
        evidence.update({
            "sell_fraction": 1.0,
            "required_fill": POST_TRIGGER_AMOUNT_QUOTE,
            "dead_surface_claimed": False,
        })
        return _result(SELL, "amount_specific_recovery_decay", new_state, evidence)
    return _result(HOLD, "executable_recovery_monitoring", new_state, evidence)


def evaluate_high_recall_exit_pipeline(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = HIGH_RECALL_EXIT_POLICY,
) -> ExitResult:
    """Exit-only High Recall -> Earn Hold -> Harvest -> Dead Wave state machine.

    Re-entry is deliberately absent.  Probation uses the Earn-the-Hold fields.
    Harvest additionally needs ``economic_return`` and an explicit
    ``proposed_sell_fraction``; it remains pending until later position state
    proves both sold fraction and realized proceeds increased enough to recover
    numeric principal. After harvest, dead-wave monitoring uses marked value,
    actual flow and structural change evidence.
    """
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "high_recall_exit_pipeline", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    phase = str(new_state.get("phase") or "PROBATION")
    elapsed = float(evidence["elapsed_seconds"])
    flow, flow_error = _actual_flow(frame)
    if phase == "PROBATION":
        if elapsed < float(policy["review_start_seconds"]):
            new_state["phase"] = phase
            return _result(WAIT, "probation_window_not_started", new_state, evidence)
        value_ratio, value_error, value_kind = _marked_value(frame)
        price_return = _number(frame.get("price_return"))
        depth_ratio = _number(frame.get("effective_depth_ratio"))
        evidence.update({
            "position_value_ratio": value_ratio,
            "value_kind": value_kind or None,
        })
        if flow_error or value_error or None in {value_ratio, price_return, depth_ratio}:
            return _result(
                WAIT,
                flow_error or value_error or "missing_probation_evidence",
                new_state,
                evidence,
            )
        healthy = bool(
            value_ratio >= float(policy["minimum_position_value_ratio"])
            and price_return >= float(policy["minimum_price_return"])
            and depth_ratio >= float(policy["minimum_effective_depth_ratio"])
            and flow >= float(policy["minimum_net_quote_flow_usd"])
        )
        evidence["healthy_continuation"] = healthy
        if healthy:
            new_state["phase"] = "EARNED_HOLD"
            return _result(HOLD, "probation_earned_hold", new_state, evidence)
        if elapsed < float(policy["review_deadline_seconds"]):
            return _result(HOLD, "probation_continues", new_state, evidence)
        new_state["phase"] = "FAILED_CONTINUATION"
        evidence["sell_fraction"] = 1.0
        return _result(SELL, "earn_the_hold_deadline_failed", new_state, evidence)

    if phase == "HARVEST_PENDING":
        realized = _number(position.get("realized_proceeds_usd"))
        sold_fraction = _number(position.get("sold_fraction"))
        principal = _number(position.get("principal_usd"))
        baseline_realized = _number(new_state.get("harvest_baseline_realized_proceeds_usd"))
        baseline_sold = _number(new_state.get("harvest_baseline_sold_fraction"))
        evidence.update({
            "realized_proceeds_usd": realized,
            "sold_fraction": sold_fraction,
            "principal_usd": principal,
            "baseline_realized_proceeds_usd": baseline_realized,
            "baseline_sold_fraction": baseline_sold,
        })
        confirmed = bool(
            None not in {realized, sold_fraction, principal, baseline_realized, baseline_sold}
            and principal > 0.0
            and realized > baseline_realized
            and sold_fraction > baseline_sold
            and sold_fraction <= 1.0
            and realized >= principal
        )
        if not confirmed:
            if (None not in {realized, sold_fraction, principal, baseline_realized, baseline_sold}
                    and realized > baseline_realized and sold_fraction > baseline_sold and sold_fraction < 1):
                # The next-frame price can change the proceeds. An actual
                # partial fill below principal must allow another fresh review.
                new_state["phase"] = "EARNED_HOLD"
                return _result(HOLD, "partial_harvest_below_principal_reassess", new_state, evidence)
            return _result(WAIT, "harvest_fill_not_confirmed", new_state, evidence)
        new_state["phase"] = "HARVESTED"
        new_state["harvested"] = True
        new_state["harvest_confirmed_realized_proceeds_usd"] = realized
        new_state["harvest_confirmed_sold_fraction"] = sold_fraction
        return _result(HOLD, "harvest_fill_confirmed", new_state, evidence)

    if phase == "EARNED_HOLD" and not bool(new_state.get("harvested")):
        economic_return = _number(frame.get("economic_return"))
        proposed_fraction = frame.get("proposed_sell_fraction")
        baseline_realized = _number(position.get("realized_proceeds_usd"))
        baseline_sold = _number(position.get("sold_fraction"))
        evidence.update({
            "economic_return": economic_return,
            "proposed_sell_fraction": proposed_fraction,
            "baseline_realized_proceeds_usd": baseline_realized,
            "baseline_sold_fraction": baseline_sold,
        })
        if None in {economic_return, baseline_realized, baseline_sold}:
            return _result(WAIT, "missing_harvest_evidence", new_state, evidence)
        if economic_return >= float(policy["harvest_economic_return"]):
            try:
                fraction = validate_sell_fraction(proposed_fraction, partial=True)
            except ValueError:
                return _result(WAIT, "invalid_harvest_sell_fraction", new_state, evidence)
            new_state["phase"] = "HARVEST_PENDING"
            new_state["harvest_baseline_realized_proceeds_usd"] = baseline_realized
            new_state["harvest_baseline_sold_fraction"] = baseline_sold
            new_state["harvest_requested_fraction"] = fraction
            evidence.update({
                "sell_fraction": fraction,
                "fill_status": "pending",
            })
            return _result(SELL_PARTIAL, "harvest_trigger_pending_fill", new_state, evidence)
        return _result(HOLD, "earned_hold_awaiting_harvest", new_state, evidence)

    if phase not in {"HARVESTED", "EARNED_HOLD"}:
        return _result(HOLD, "exit_pipeline_terminal_or_waiting", new_state, evidence)
    value_ratio, value_error, value_kind = _marked_value(frame)
    economic_return = _number(frame.get("economic_return"))
    structure_bad, structure = _structure_bad(frame, policy)
    if (
        flow_error
        or value_error
        or economic_return is None
        or structure_bad is None
    ):
        return _result(
            WAIT,
            flow_error or value_error or "missing_dead_wave_evidence",
            new_state,
            evidence,
        )
    _, peak, new_high, reset = _update_running_peak(
        new_state,
        prefix="dead_wave",
        epoch="position",
        unit=value_kind,
        value=value_ratio,
    )
    bad = bool(economic_return > 0.0 and not new_high and flow < 0.0 and structure_bad)
    streak = 0 if reset or not bad else int(new_state.get("dead_wave_bad_streak") or 0) + 1
    new_state["dead_wave_bad_streak"] = streak
    evidence.update({
        "running_peak": peak,
        "new_high": new_high,
        "peak_reset": reset,
        "dead_wave_streak": streak,
        "net_quote_flow_usd": flow,
        "position_value_ratio": value_ratio,
        "value_kind": value_kind,
        **structure,
    })
    if streak >= int(policy["minimum_dead_wave_frames"]):
        new_state["phase"] = "DEAD_WAVE_EXITED"
        evidence.update({
            "sell_fraction": 1.0,
            "reentry_action": None,
        })
        return _result(SELL, "two_frame_dead_wave_exit", new_state, evidence)
    return _result(HOLD, "dead_wave_monitoring", new_state, evidence)


_EVALUATORS: Mapping[str, Callable[..., ExitResult]] = MappingProxyType({
    "earn_the_hold": evaluate_earn_the_hold,
    "failed_continuation_profit_lock": evaluate_failed_continuation_profit_lock,
    "price_to_flow_fragility": evaluate_price_to_flow_fragility,
    "creator_early_holder_distribution": evaluate_creator_early_holder_distribution,
    "vault_hazard": evaluate_vault_hazard,
    "executable_recovery_decay": evaluate_executable_recovery_decay,
    "high_recall_exit_pipeline": evaluate_high_recall_exit_pipeline,
})


def evaluate_exit(
    strategy: str,
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] | None = None,
) -> ExitResult:
    """Dispatch one frozen exit policy by its stable strategy key."""
    evaluator = _EVALUATORS.get(str(strategy))
    if evaluator is None:
        raise ValueError("unknown_capital_exit_strategy")
    if policy is None:
        return evaluator(position, frame, state, now=now)
    return evaluator(position, frame, state, now=now, policy=policy)


__all__ = [
    "WAIT", "HOLD", "SELL", "SELL_PARTIAL", "POST_TRIGGER_AMOUNT_QUOTE",
    "EARN_THE_HOLD_POLICY", "FAILED_CONTINUATION_POLICY",
    "PRICE_TO_FLOW_POLICY", "CREATOR_DISTRIBUTION_POLICY",
    "VAULT_HAZARD_POLICY", "EXECUTABLE_RECOVERY_POLICY",
    "HIGH_RECALL_EXIT_POLICY", "validate_sell_fraction", "evaluate_exit",
    "evaluate_earn_the_hold", "evaluate_failed_continuation_profit_lock",
    "evaluate_price_to_flow_fragility",
    "evaluate_creator_early_holder_distribution", "evaluate_vault_hazard",
    "evaluate_executable_recovery_decay", "evaluate_high_recall_exit_pipeline",
]
