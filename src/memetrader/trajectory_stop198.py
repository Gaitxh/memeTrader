"""A fresh-frame stop confirmation experiment for the Solana runner."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "trajectory-stop198/v1"
ARM = "trajectory198_solana_confirmed_stop_v1"
PARENT = "trajectory187_solana_runner_v1"
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
        name="Solana runner, fresh-frame confirmed stop",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="trajectory198_solana_stop",
        excess_return_vs_arm=PARENT,
        fresh_stop_confirm_marks=2,
        fresh_stop_catastrophe_return=-0.35,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: same Solana runner source and exit rules as {PARENT}. "
            "The first fresh -20% economic mark waits for a distinct fresh pool frame; "
            "a fresh -35% loss exits immediately. No additional market request."
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
    evidence["trajectory_stop198_source_decision_key"] = source["decision_key"]
    evidence["mode"] = ARM
    result[ARM] = signal
    return result
