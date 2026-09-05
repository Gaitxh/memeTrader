"""Pure, evidence-bound common-funding adjustment for a separate 5U hypothesis.

An observed funding transfer links wallets only as an on-chain relation.  It
does not identify a common human/controller and is never inferred from counts.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any, Mapping, Sequence


POLICY = {
    "arm_id": "common_funding_adjusted_breadth_5u_v1",
    "notional_usd": 5.0,
    "min_adjusted_effective_breadth": 2.0,
    "max_common_funding_share": 0.5,
    "min_windows": 2,
    "entry_match_mode": "isolated_pattern_observer",
    "entry_gate": "broad_start",
    "no_historical_backfill": True,
    "fidelity_status": "HYPOTHESIS_ONLY",
}


def common_funding_policy():
    import copy
    from .capital_policies import capital_policies
    p = copy.deepcopy(next(p for p in capital_policies() if p["arm_id"] == "bundle_adjusted_breadth_v1"))
    p.update(arm_id=POLICY["arm_id"], canonical_id=POLICY["arm_id"], notional_usd=5.0,
             name="已观察资金关联·广度调整", entry_family="common_funding_adjusted_breadth",
             source_arm_ids=["bundle_adjusted_breadth_v1"],
             description="同批已取得交易中的真实转账关系调整买方金额广度；不是同一控制人识别。")
    p["entry_filter"] = {"direction": "common_funding_adjusted_breadth", **POLICY}
    return p


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else None


def _breadth(values: Sequence[float]) -> float | None:
    total = sum(values)
    squares = sum(value * value for value in values)
    return total * total / squares if squares else None


def adjusted_flow_breadth(flow_windows: Mapping[str, Mapping[str, Any]],
                          funding_edges: Sequence[Mapping[str, Any]], *,
                          decision_at: str, activated_at: str) -> dict:
    """Return amountful breadth after only explicit, as-of funding links."""
    decision, activated = _time(decision_at), _time(activated_at)
    if not decision or not activated or decision < activated:
        return {"status": "wait_noncausal_time"}
    if not isinstance(flow_windows, Mapping) or len(flow_windows) < 2:
        return {"status": "wait_two_flow_windows"}
    for window in flow_windows.values():
        if not isinstance(window, Mapping) or window.get("complete") is not True:
            return {"status": "wait_incomplete_amountful_flow"}
        observed, recorded = _time(window.get("observed_at")), _time(window.get("recorded_at"))
        if not observed or not recorded or not activated <= observed <= recorded <= decision:
            return {"status": "wait_flow_provenance"}
    if not funding_edges:
        return {"status": "wait_unsealed_funding_evidence"}
    buyers: defaultdict[str, float] = defaultdict(float)
    for trade in (flow_windows.get("current") or {}).get("trades", []):
        if (not isinstance(trade, Mapping) or trade.get("side") != "BUY"
                or not isinstance(trade.get("signer_address"), str)
                or trade.get("amount_complete") is not True
                or trade.get("amount_source") != "parsed_spl_transfer"):
            continue
        try:
            amount = float(trade["quote_amount_raw"])
        except (TypeError, ValueError):
            return {"status": "wait_invalid_amountful_trade"}
        if not math.isfinite(amount) or amount <= 0:
            return {"status": "wait_invalid_amountful_trade"}
        buyers[trade["signer_address"]] += amount
    if not buyers:
        return {"status": "wait_no_amountful_buyers"}
    links: defaultdict[str, set[str]] = defaultdict(set)
    recipient_sources: defaultdict[str, set[str]] = defaultdict(set)
    seen_edges = set()
    for edge in funding_edges:
        if not isinstance(edge, Mapping) or edge.get("relation_type") != "observed_funding_transfer":
            return {"status": "wait_unsealed_funding_evidence"}
        observed = _time(edge.get("observed_at")); recorded = _time(edge.get("recorded_at"))
        sealed = _time(edge.get("sealed_at"))
        amount = edge.get("amount_raw")
        edge_key = (edge.get("signature"), edge.get("instruction_path"))
        if (not observed or not recorded or not sealed or not activated <= observed <= recorded <= sealed <= decision
                or not edge.get("signature") or not edge.get("source") or not edge.get("destination")):
            return {"status": "wait_unsealed_funding_evidence"}
        if edge_key in seen_edges:
            return {"status": "wait_duplicate_funding_evidence"}
        seen_edges.add(edge_key)
        if edge.get("destination") not in buyers:
            continue
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"status": "wait_invalid_funding_amount"}
        if not math.isfinite(amount) or amount <= 0:
            return {"status": "wait_invalid_funding_amount"}
        source, recipient = str(edge["source"]), str(edge["destination"])
        recipient_sources[recipient].add(source)
    for recipient, sources in recipient_sources.items():
        if len(sources) == 1:
            links[next(iter(sources))].add(recipient)
    adjusted: defaultdict[str, float] = defaultdict(float)
    for buyer, amount in buyers.items():
        source = next((source for source, members in links.items() if buyer in members), buyer)
        adjusted[source] += amount
    raw = _breadth(list(buyers.values()))
    result = {"status": "ok", "raw_effective_breadth": raw,
              "adjusted_effective_breadth": _breadth(list(adjusted.values())),
              "buyer_count": len(buyers), "adjusted_group_count": len(adjusted),
              "total_buyer_notional": sum(buyers.values()),
              "linked_buyer_count": sum(len(v) for v in links.values()),
              "linked_buyer_notional": sum(buyers[r] for r, sources in recipient_sources.items() if len(sources) == 1),
              "funding_sources": sorted(links),
              "identity_semantics": "observed_onchain_funding_relation_not_common_controller",
              "observed_at": (flow_windows["current"] or {}).get("observed_at"),
              "recorded_at": (flow_windows["current"] or {}).get("recorded_at"),
              "evidence_complete": True}
    return result


def common_funding_adjusted_breadth_signal(flow_windows: Mapping[str, Mapping[str, Any]],
                                           funding_edges: Sequence[Mapping[str, Any]],
                                           decision_at: str, activated_at: str,
                                           policy: Mapping[str, Any] | None = None) -> tuple[bool, str]:
    policy = policy or POLICY
    result = adjusted_flow_breadth(flow_windows, funding_edges,
                                    decision_at=decision_at, activated_at=activated_at)
    if result.get("status") != "ok":
        return False, str(result.get("status", "wait_common_funding_evidence"))
    minimum = float(policy.get("min_adjusted_effective_breadth", 2.0))
    maximum = float(policy.get("max_common_funding_share", 0.5))
    adjusted = result["adjusted_effective_breadth"]
    linked_share = result["linked_buyer_notional"] / result["total_buyer_notional"]
    if adjusted < minimum or linked_share > maximum:
        return False, "common_funding_adjusted_breadth_below_hypothesis"
    return True, "common_funding_adjusted_breadth_confirmed"
