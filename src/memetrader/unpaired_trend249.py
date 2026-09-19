"""Strict-forward continuation of the successful trend control after its pair retired.

The original control was created only to compare one exit variant at identical
fills.  Once that variant was retired, the pair-size invariant permanently
removed otherwise-ready control signals.  This revision preserves the control's
entry, exit and execution contract and removes only that obsolete experiment
coupling.  It does not backfill missed opportunities.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


ARM = "revision249_unpaired_trend_control_v1"
PARENT = "trajectory169_trend_runner_control_v1"
SIGNAL_PARENT = "trajectory144_trend_runner_v1"
CONTRACT = "unpaired-trend-control249/v1"


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact retired-pair control required")
    out = deepcopy(dict(parent))
    for key in (
        "account_lifecycle", "assessment_evidence", "assessment_note",
        "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
        "forward_started_at", "original_forward_started_at", "runtime_addition_id",
        "stage", "paired_entry_group", "paired_entry_size", "excess_return_vs_arm",
    ):
        out.pop(key, None)
    out.update(
        arm_id=ARM,
        canonical_id=ARM,
        entry_family=ARM,
        name="Trend runner control after pair retirement",
        revision_of=PARENT,
        source_arm_ids=[PARENT, SIGNAL_PARENT],
        entry_alias_of=SIGNAL_PARENT,
        assessment_status="INSUFFICIENT",
        decision_eligible=True,
        observer_only=False,
        affects="paper_only",
        live=False,
        no_historical_backfill=True,
        unpaired_continuation_contract=CONTRACT,
        comparison_semantics=(
            "Exact parent entry and exit behavior; only the obsolete paired-entry "
            "dependency is removed after the failed mate retired."
        ),
        description=(
            "Strict-forward continuation of trajectory169 control after its paired "
            "moonbag exit variant retired. Preserves the same trajectory144 signal, "
            "next-frame execution, exits, Paper costs and risk limits; removes only "
            "the two-arm simultaneous-entry requirement. No historical backfill."
        ),
    )
    out["entry_filter"] = {
        **(out.get("entry_filter") or {}),
        "direction": ARM,
    }
    return out


def alias(parent_signal: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parent_signal, Mapping) or not parent_signal.get("decision_key"):
        return {}
    value = deepcopy(dict(parent_signal))
    value["decision_key"] = f"{parent_signal['decision_key']}|{ARM}"
    value.setdefault("decision_evidence", {}).update(
        unpaired_trend249_contract=CONTRACT,
        unpaired_trend249_source_arm=SIGNAL_PARENT,
    )
    return {ARM: value}


def snapshot() -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "arm": ARM,
        "parent": PARENT,
        "signal_parent": SIGNAL_PARENT,
        "changed_dimension": "remove_retired_pair_dependency_only",
        "extra_requests": 0,
        "effects": "paper_only",
        "no_historical_backfill": True,
    }
