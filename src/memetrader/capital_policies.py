"""Pure capital-entry policy definitions and two evidence-bound signals.

These are preregistered hypotheses.  They do not imply profitability or
trading eligibility and intentionally have no Store/runtime dependencies.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping, Sequence
from .capital_exits import (EARN_THE_HOLD_POLICY, FAILED_CONTINUATION_POLICY,
    PRICE_TO_FLOW_POLICY, CREATOR_DISTRIBUTION_POLICY, VAULT_HAZARD_POLICY,
    EXECUTABLE_RECOVERY_POLICY, HIGH_RECALL_EXIT_POLICY)


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _asof(evidence: Mapping[str, Any], decision: datetime, activated: datetime,
          *, fresh: bool = True, max_age_seconds: float = 30) -> bool:
    observed = _time(evidence.get("observed_at"))
    recorded = _time(evidence.get("recorded_at") or evidence.get("available_at"))
    return bool(observed and recorded and activated <= observed <= recorded <= decision
                and (not fresh or (decision - observed).total_seconds() <= max_age_seconds))


def direct_lp_float_constrained_signal(
    history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any],
    decision_at: str, activated_at: str, context: Mapping[str, Any],
) -> tuple[bool, str]:
    """Classify only an exact NORMAL_DIRECT bundle, not missing migration history.

    LP custody is a sizing observation, never asserted to be locked.  The
    caller must apply the returned ``soft_low_size`` treatment when custody
    risk is not demonstrably low.
    """
    decision, activated = _time(decision_at), _time(activated_at)
    snap = context.get("snapshot")
    permission = context.get("mint_permission")
    if not decision or not activated or not isinstance(snap, Mapping) or not isinstance(permission, Mapping):
        return False, "wait_direct_lp_missing_asof_or_permission"
    if not _asof(snap, decision, activated, max_age_seconds=120) or not _asof(permission, decision, activated):
        return False, "wait_direct_lp_noncausal_or_stale_snapshot"
    surface = snap.get("pool_surface")
    if not isinstance(surface, Mapping) or surface.get("status") != "RESOLVED" or surface.get("complete") is not True or surface.get("surface") != "NORMAL_DIRECT":
        return False, "direct_lp_not_normal_direct"
    if permission.get("known") is not True or not isinstance(permission.get("status"), str):
        return False, "wait_direct_lp_mint_permission_unknown"
    share = _finite(snap.get("pool_supply_share"))
    cfg = policy.get("entry_filter") if isinstance(policy, Mapping) else None
    minimum = _finite(cfg.get("min_pool_supply_share")) if isinstance(cfg, Mapping) else None
    if share is None or minimum is None or not 0 <= share <= 1:
        return False, "wait_direct_lp_supply_share"
    if share < minimum:
        return False, "direct_lp_pool_supply_share_below_hypothesis"
    risk = str(snap.get("lp_custody_risk") or "").lower()
    if risk not in {"low", "medium", "high", "unknown"}:
        return False, "wait_direct_lp_custody_risk"
    return True, "direct_lp_float_confirmed" if risk == "low" else "direct_lp_float_soft_low_size"


def authoritative_event_shock_signal(
    history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any],
    decision_at: str, activated_at: str, context: Mapping[str, Any],
) -> tuple[bool, str]:
    """Accept only a first-party exact-contract event; trades are next-frame input."""
    decision, activated = _time(decision_at), _time(activated_at)
    event = context.get("event")
    if not decision or not activated or not isinstance(event, Mapping):
        return False, "wait_authoritative_event"
    if not _asof(event, decision, activated, max_age_seconds=300):
        return False, "wait_authoritative_event_provenance"
    if event.get("source_kind") != "first_party" or event.get("trusted") is not True:
        return False, "wait_authoritative_event_source"
    event_type = event.get("event_type")
    allowed = (policy.get("entry_filter") or {}).get("event_types")
    if not isinstance(event_type, str) or not isinstance(allowed, list) or event_type not in allowed:
        return False, "wait_authoritative_event_type"
    address = event.get("contract_address")
    token = str(context.get("token_id") or "")
    token_address = token.rsplit(":", 1)[-1]
    same_address = token_address == str(address) if token.lower().startswith("solana:") else token_address.lower() == str(address).lower()
    if not address or not token or not same_address:
        return False, "wait_authoritative_event_contract_identity"
    return True, "authoritative_event_shock_confirmed"


_POLICY_SPECS = (
    ("vault_hazard_v1", "vault_hazard", {"capital_exit_kind": "vault_hazard"}),
    ("earn_the_hold_v1", "earn_the_hold", {"capital_exit_kind": "earn_the_hold"}),
    ("failed_continuation_profit_lock_v1", "failed_continuation_profit_lock", {"capital_exit_kind": "failed_continuation_profit_lock"}),
    ("wave_reset_reentry_v1", "wave_reset_reentry", {"min_gap_seconds": 600, "max_gap_seconds": 14400}),
    ("migration_absorption_v1", "migration_absorption", {"min_absorption_frames": 2}),
    ("executable_recovery_decay_v1", "executable_recovery_decay", {"capital_exit_kind": "executable_recovery_decay"}),
    ("capital_velocity_v1", "capital_velocity", {"min_capital_velocity_usd_per_second": 1, "min_effective_breadth": 2, "max_top3_notional_share": .8}),
    ("effective_breadth_v1", "effective_breadth", {"min_effective_breadth": 3, "max_top1_notional_share": .5}),
    ("price_to_flow_fragility_v1", "price_to_flow_fragility", {"capital_exit_kind": "price_to_flow_fragility"}),
    ("churn_resistant_v1", "churn_resistant", {"min_median_trade_notional_usd": 1, "max_dust_notional_share": .1}),
    ("creator_early_holder_distribution_v1", "creator_early_holder_distribution", {"capital_exit_kind": "creator_early_holder_distribution"}),
    ("bundle_adjusted_breadth_v1", "bundle_adjusted_breadth", {"min_adjusted_effective_breadth": 2}),
    ("finite_capital_ranker_v1", "finite_capital_ranker", {"max_selected_rank": 3}),
    ("market_regime_throttle_v1", "market_regime_throttle", {"min_breadth": .5, "min_depth_health": .5}),
    ("competing_risk_v1", "competing_risk", {"min_sealed_samples": 20}),
    ("high_recall_exit_pipeline_v1", "high_recall_exit_pipeline", {"capital_exit_kind": "high_recall_exit_pipeline"}),
    ("direct_lp_float_constrained_v1", "direct_lp_float_constrained", {"min_pool_supply_share": .5}),
    ("authoritative_event_shock_v1", "authoritative_event_shock", {"event_types": ["official_listing", "official_launch", "migration", "contract_upgrade"]}),
)


def capital_policies() -> list[dict[str, Any]]:
    """Return 18 independent frozen hypothesis records in forward-policy shape."""
    required = {
        "direct_lp_float_constrained": ["snapshot", "pool_surface", "pool_supply_share", "mint_permission", "lp_custody_risk"],
        "authoritative_event_shock": ["event", "source_kind", "event_type", "contract_address", "next_frame_trade"],
        "capital_velocity": ["amountful_flow", "postgraduation_status"],
    }
    policies = []
    exit_rules = {"vault_hazard": VAULT_HAZARD_POLICY, "earn_the_hold": EARN_THE_HOLD_POLICY,
        "failed_continuation_profit_lock": FAILED_CONTINUATION_POLICY,
        "executable_recovery_decay": EXECUTABLE_RECOVERY_POLICY,
        "price_to_flow_fragility": PRICE_TO_FLOW_POLICY,
        "creator_early_holder_distribution": CREATOR_DISTRIBUTION_POLICY,
        "high_recall_exit_pipeline": HIGH_RECALL_EXIT_POLICY}
    for arm_id, direction, thresholds in _POLICY_SPECS:
        exit_kind = thresholds.get("capital_exit_kind")
        policy = {
            "arm_id": arm_id, "canonical_id": arm_id, "family": "capital_entry_hypothesis",
            "name": direction, "capital_experiment": True,
            "description": "资金与生命周期独立前向假设，尚未证明盈利。",
            "entry_family": direction, "entry_filter": {"direction": direction, **thresholds},
            "entry_match_mode": "isolated_pattern_observer", "entry_gate": "broad_start",
            "required_inputs": required.get(direction, [direction, "asof_snapshot"]),
            "entry_contract": "strict_forward_asof_v1", "exit_family": "capital_exit_existing_v1",
            "capital_exit_kind": exit_kind,
            "capital_exit_policy": dict(exit_rules[exit_kind]) if exit_kind else {},
            "hard_stop_return": -.2, "trailing_activate_return": .3,
            "trailing_drawdown": .15, "max_hold_minutes": 15.0,
            "notional_usd": 5.0 if direction == "direct_lp_float_constrained" else 20.0,
            "take_profit": [], "source_arm_ids": [],
            "execution_profile": "dexscreener-market-paper/v2-before-after",
            "forward_enabled": True, "fidelity_status": "HYPOTHESIS_ONLY",
            "no_historical_backfill": True,
        }
        if direction in {"failed_continuation_profit_lock", "high_recall_exit_pipeline"}:
            policy.update(trailing_activate_return=1.0, max_hold_minutes=240.0)
        if direction == "failed_continuation_profit_lock":
            policy["take_profit"] = [{"return": 1.0, "fraction_of_remaining": .5}]
        if direction == "direct_lp_float_constrained":
            policy.update(capital_exit_kind="vault_hazard", capital_exit_policy=dict(VAULT_HAZARD_POLICY),
                          max_hold_minutes=10.0, hard_stop_return=-.15)
        if direction == "competing_risk":
            policy["entry_filter"]["label_scope"] = "observed_profit_writeoff_ordinary_loss"
        if direction == "capital_velocity":
            policy["description"] = "已毕业池真实资金流速率实验；毕业前逐笔流因付费输入未接通，不作等价声明。"
        if direction == "bundle_adjusted_breadth":
            policy["description"] = "按实际同一交易原子组调整参与广度；无法覆盖未公开的跨交易bundle。"
        policies.append(policy)
    return policies


def second_discussion_policies() -> list[dict[str, Any]]:
    """Separate second-discussion mechanisms, never revisions of the first 18."""
    import copy
    parent = next(p for p in capital_policies() if p["arm_id"] == "high_recall_exit_pipeline_v1")
    result = []
    for direction, name in (("event_reawakening", "官方事件后复苏"),
                            ("surface_lifecycle_pipeline", "按池类型分流的生命周期")):
        p = copy.deepcopy(parent)
        arm = direction + "_v1"
        p.update(arm_id=arm, canonical_id=arm, name=name, entry_family=direction,
                 source_arm_ids=[parent["arm_id"]],
                 description="第二次独立讨论新增方向；实际来源和池身份确认后下一帧入场，尚未证明盈利。",
                 entry_filter={"direction": direction, "min_mature_age_seconds": 3600,
                               "min_effective_breadth": 2, "min_pool_supply_share": .5,
                               "min_absorption_frames": 2,
                               "event_types": ["official_listing", "official_launch", "migration", "contract_upgrade"]},
                 notional_usd=5.0 if direction == "surface_lifecycle_pipeline" else 20.0)
        result.append(p)
    parents = {p["arm_id"]: p for p in capital_policies()}
    for kind in ("vault_hazard", "earn_the_hold", "failed_continuation_profit_lock"):
        for control in (False, True):
            p = copy.deepcopy(parents[kind + "_v1"])
            arm = f"paired_{kind}_{'control' if control else 'candidate'}_v1"
            p.update(arm_id=arm, canonical_id=arm, name=kind + ("·同入场对照" if control else "·同入场候选"),
                     paired_entry_group=kind, source_arm_ids=[kind + "_v1"])
            p["entry_filter"]["paired_entry_kind"] = kind
            if control:
                p.update(capital_exit_kind=None, capital_exit_policy={})
            result.append(p)
    return result
