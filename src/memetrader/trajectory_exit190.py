"""Forward-only first-mark trailing challenger over the existing runner signal."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "trajectory-exit190/v1"
ARM = "trajectory190_first_mark_trail_v1"
PARENT = "trajectory144_trend_runner_v1"
CONTROL = "trajectory187_armed_runner_v1"

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
        name="Early impulse runner, trailing from first valid mark",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="trajectory190_first_mark_trail",
        excess_return_vs_arm=CONTROL,
        trailing_activate_return=-1.0,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: identical post-frontier {PARENT} entry, stop, trailing distance "
            "and holding contract; only the trailing activation changes from break-even "
            "to the first valid original-pool economic mark. Shared frames, no extra API."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": ARM}
    result.pop("signal_origin_clock", None)
    return result


def alias_signals(signals: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(signals)
    source = signals.get(PARENT)
    if not isinstance(source, Mapping) or not source.get("decision_key"):
        return result
    signal = deepcopy(dict(source))
    signal["decision_key"] = f"{source['decision_key']}|{ARM}"
    evidence = signal.setdefault("decision_evidence", {})
    evidence["trajectory_exit190_source_decision_key"] = source["decision_key"]
    evidence["trajectory_exit190_source_arm"] = evidence.get("mode")
    evidence["mode"] = ARM
    result[ARM] = signal
    return result
