"""Fresh same-signal control for a trend runner with principal recovery."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "trend-moonbag169/v1"
PARENT_ARM = "trajectory144_trend_runner_v1"
CONTROL_ARM = "trajectory169_trend_runner_control_v1"
ARM = "trajectory169_trend_runner_moonbag_v1"
ARMS = (CONTROL_ARM, ARM)
PAIR_GROUP = "trajectory169_trend_runner_moonbag_pair_v1"
RECOVERY_CONTRACT = "minimum_net_debit_keep_half_next_frame/v3"


def policies(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Clone the runner at one fresh frontier; recovery is the only exit difference."""
    result = []
    for arm in ARMS:
        policy = deepcopy(dict(parent))
        policy.update(
            arm_id=arm,
            canonical_id=arm,
            entry_family=arm,
            name=(
                "Trend runner fresh control"
                if arm == CONTROL_ARM
                else "Trend runner principal recovery moonbag"
            ),
            source_arm_ids=[PARENT_ARM],
            entry_alias_of=PARENT_ARM,
            paired_entry_group=PAIR_GROUP,
            paired_entry_size=2,
            assessment_status="INSUFFICIENT",
            decision_eligible=True,
            observer_only=False,
            affects="paper_only",
            live=False,
            description=(
                f"{VERSION}: fresh same-signal control; preserves the parent entry and every "
                "exit field without principal recovery."
                if arm == CONTROL_ARM
                else f"{VERSION}: same fresh signal, trend extension, stop, trailing and horizon "
                "as the control; on a fresh executable mark, recover actual net debit only when "
                "at least half the position can remain as a moonbag."
            ),
        )
        policy["entry_filter"] = {
            **(policy.get("entry_filter") or {}), "direction": arm,
        }
        # The parent's activation_at belongs to an older engine lifetime. The signal's own
        # observed/recorded clocks and the append frontier remain mandatory in Store.
        policy.pop("signal_origin_clock", None)
        for field in (
            "behavior_contract_hash", "forward_activation_snapshot_id",
            "forward_started_at", "runtime_addition_id", "stage",
        ):
            policy.pop(field, None)
        if arm == ARM:
            policy["dynamic_principal_recovery"] = RECOVERY_CONTRACT
            policy["excess_return_vs_arm"] = CONTROL_ARM
        else:
            policy.pop("dynamic_principal_recovery", None)
            policy.pop("minimum_principal_recovery_multiple", None)
            policy["excess_return_vs_arm"] = ARM
        result.append(policy)
    return result


def alias_signals(signals: Mapping[str, Any]) -> dict[str, Any]:
    """Give both fresh arms the exact parent envelope with distinct decision keys."""
    result = dict(signals)
    parent = signals.get(PARENT_ARM)
    if not isinstance(parent, Mapping) or not parent.get("decision_key"):
        return result
    for arm in ARMS:
        signal = deepcopy(dict(parent))
        signal["decision_key"] = f"{parent['decision_key']}|{arm}"
        evidence = signal.setdefault("decision_evidence", {})
        evidence["trend_moonbag169_source_arm"] = PARENT_ARM
        evidence["trend_moonbag169_source_decision_key"] = parent["decision_key"]
        result[arm] = signal
    return result


def snapshot() -> dict[str, Any]:
    return {
        "version": VERSION,
        "parent": PARENT_ARM,
        "arms": list(ARMS),
        "paired_entry_group": PAIR_GROUP,
        "changed_dimension": "dynamic_principal_recovery_only",
        "recovery_contract": RECOVERY_CONTRACT,
        "effects": "paper_only",
        "extra_requests": 0,
        "no_historical_backfill": True,
    }
