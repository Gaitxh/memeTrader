"""Liquidity-lead entry intersected with fresh amountful participation breadth."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


ARM = "liquidity_lead_breadth_confirmed_v1"
PARENT = "liquidity_leads_price_v1"
CONTRACT = "liquidity-lead-breadth254/v1"


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact liquidity-lead parent required")
    out = deepcopy(dict(parent))
    base_filter = deepcopy(dict(out.get("entry_filter") or {}))
    for key in ("behavior_contract_hash", "forward_activation_snapshot_id",
                "forward_started_at", "original_forward_started_at", "runtime_addition_id",
                "entry_revision_kind"):
        out.pop(key, None)
    out.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Liquidity lead with real participation breadth", revision_of=PARENT,
        source_arm_ids=[PARENT], capital_experiment=True,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        comparison_semantics=(
            "Parent liquidity-lead L0 rule plus fresh amountful-flow breadth; exits and "
            "Paper execution remain unchanged."
        ),
        description=(
            "Require the existing three-frame liquidity lead without price chase, then "
            "fresh observed effective breadth >=2, top-one notional share <=50% and "
            "positive net quote flow. Missing flow remains WAIT; no extra request."
        ),
    )
    out["entry_filter"] = {
        "direction": ARM, "base_liquidity_filter": base_filter,
        "min_effective_breadth": 2.0, "max_top1_notional_share": 0.5,
        "min_net_quote_flow_usd": 0.0,
    }
    return out


def signal(history: Sequence[Mapping[str, Any]], policy_: Mapping[str, Any], *,
           decision_at: Any, activated_at: Any, context: Mapping[str, Any]):
    from .strategy_revisions import revision_entry_signal
    proxy = deepcopy(dict(policy_))
    proxy["entry_revision_kind"] = "evidence_extension_l0"
    proxy["entry_filter"] = deepcopy(dict(policy_["entry_filter"]["base_liquidity_filter"]))
    base_ok, base_reason = revision_entry_signal(
        history, proxy, decision_at=decision_at, activated_at=activated_at)
    if not base_ok:
        return False, "breadth254_parent_" + base_reason
    from .capital_entry import _evidence_ok, _finite, _time
    decision, activated = _time(decision_at), _time(activated_at)
    flow = context.get("amountful_flow")
    if (not isinstance(flow, Mapping) or not decision or not activated
            or not _evidence_ok(flow, decision, activated)):
        return False, "breadth254_wait_fresh_amountful_flow"
    breadth = _finite(flow.get("effective_breadth"))
    top1 = _finite(flow.get("top1_notional_share"))
    net = _finite(flow.get("net_quote_flow_usd"))
    filt = policy_["entry_filter"]
    if None in (breadth, top1, net):
        return False, "breadth254_wait_complete_amountful_flow"
    allowed = (breadth >= float(filt["min_effective_breadth"])
               and top1 <= float(filt["max_top1_notional_share"])
               and net > float(filt["min_net_quote_flow_usd"]))
    return allowed, ("breadth254_confirmed" if allowed else "breadth254_below_hypothesis")
