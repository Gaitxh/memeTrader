"""Forward-only DEX-continuity revision of the synthetic harvest arm."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .righttail_recovery152 import SAFETY_PROXY


ARM = "revision255_synthetic_dex_continuity_v1"
PARENT = "synthetic_fast_harvest_v1"
CONTRACT = "synthetic-dex-continuity255/v1"


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    """Clone the exact parent opportunity and exits, changing only safety evidence."""
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact synthetic parent required")
    out = deepcopy(dict(parent))
    for key in (
        "behavior_contract_hash", "forward_activation_snapshot_id",
        "forward_started_at", "original_forward_started_at", "runtime_addition_id",
        "requires_exact_pool_sell_simulation", "paired_opportunity_group",
    ):
        out.pop(key, None)
    out.update(
        arm_id=ARM,
        canonical_id=ARM,
        entry_family=ARM,
        name="Synthetic building · causal DEX continuity",
        revision_of=PARENT,
        source_arm_ids=[PARENT],
        feature_contract=CONTRACT,
        paper_safety_proxy=SAFETY_PROXY,
        assessment_status="INSUFFICIENT",
        decision_eligible=True,
        observer_only=False,
        affects="paper_only",
        live=False,
        no_historical_backfill=True,
        comparison_semantics=(
            "Same synthetic BUILDING signal, 1U stake and exits as the parent. The only "
            "change is an opt-in two-frame exact-pool DEX-continuity Paper proxy when "
            "optional security providers cannot establish sellability."
        ),
        description=(
            "BSC synthetic BUILDING revision. Explicit danger still rejects; otherwise "
            "requires two causal frames on the same original pool with identity, >=1000U "
            "liquidity, retained price/liquidity and current trade activity. This is a "
            "Paper approximation, not a sell simulation or safety claim."
        ),
    )
    out["entry_filter"] = {
        **deepcopy(dict(out.get("entry_filter") or {})),
        "direction": ARM,
        "max_concurrent_positions": 1,
        "single_token_lifetime_entry": True,
    }
    return out


def alias(parent_signal: Mapping[str, Any] | None) -> dict[str, Any]:
    """Give the same frozen parent opportunity an independent forward receipt."""
    if not isinstance(parent_signal, Mapping) or not parent_signal.get("decision_key"):
        return {}
    value = deepcopy(dict(parent_signal))
    value["decision_key"] = f"{parent_signal['decision_key']}|{ARM}"
    evidence = deepcopy(dict(value.get("decision_evidence") or {}))
    evidence.update(
        synthetic_proxy_contract=CONTRACT,
        synthetic_proxy_source_arm=PARENT,
        extra_market_requests=0,
    )
    value["decision_evidence"] = evidence
    return {ARM: value}
