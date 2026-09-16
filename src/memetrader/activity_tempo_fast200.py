"""Five-minute exit contrast for the existing old-pool tempo signal."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "activity-tempo-fast200/v1"
ARM = "activity200_old_pool_tempo_fast5_v1"
PARENT = "activity193_old_pool_tempo_v1"
_OWNED_FIELDS = {
    "account_lifecycle", "assessment_evidence", "assessment_note",
    "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
    "forward_started_at", "original_forward_started_at", "retirement_representative",
    "runtime_addition_id", "stage", "_execution",
}


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Old-pool activity tempo, fast 5m",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="activity193_same_entry",
        excess_return_vs_arm=PARENT,
        max_hold_minutes=5,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: identical fresh old-pool tempo signal, pool floor, "
            f"safety, entry and other exits as {PARENT}; only maximum hold is "
            "5 rather than 30 minutes. Compare cost-inclusive matched fills."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": ARM}
    result.pop("signal_origin_clock", None)
    return result


def alias_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(signal))
    result["decision_key"] = f"{signal['decision_key']}|{ARM}"
    evidence = result.setdefault("decision_evidence", {})
    evidence["activity_fast200_source_decision_key"] = signal["decision_key"]
    evidence["mode"] = ARM
    return result
