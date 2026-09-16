"""Compact forward experiments over the existing trajectory144 signal supply."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "trajectory-regime187/v1"
FAST_PARENT = "trajectory144_early_activity_fast_v1"
RUNNER_PARENT = "trajectory144_trend_runner_v1"
SOLANA_RUNNER_ARM = "trajectory187_solana_runner_v1"
NONSOL_FAST_ARM = "trajectory187_nonsol_fast_v1"
ARMED_RUNNER_ARM = "trajectory187_armed_runner_v1"
ARMS = (SOLANA_RUNNER_ARM, NONSOL_FAST_ARM, ARMED_RUNNER_ARM)
ARMED_CONTROL = "trajectory169_trend_runner_control_v1"

_OWNED_FIELDS = {
    "account_lifecycle", "assessment_evidence", "assessment_note",
    "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
    "forward_started_at", "original_forward_started_at", "retirement_representative",
    "runtime_addition_id", "stage", "_execution",
}


def _clone(parent: Mapping[str, Any], arm: str, name: str) -> dict[str, Any]:
    policy = {
        key: deepcopy(value) for key, value in parent.items()
        if key not in _OWNED_FIELDS
    }
    policy.update(
        arm_id=arm,
        canonical_id=arm,
        entry_family=arm,
        name=name,
        entry_alias_of=str(parent["arm_id"]),
        source_arm_ids=[str(parent["arm_id"])],
        assessment_status="INSUFFICIENT",
        decision_eligible=True,
        observer_only=False,
        affects="paper_only",
        live=False,
        no_historical_backfill=True,
    )
    policy["entry_filter"] = {
        **(policy.get("entry_filter") or {}), "direction": arm,
    }
    policy.pop("signal_origin_clock", None)
    return policy


def policies(fast_parent: Mapping[str, Any], runner_parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    solana = _clone(runner_parent, SOLANA_RUNNER_ARM, "Solana early impulse runner")
    solana.update(
        paired_opportunity_group="trajectory187_solana_tempo",
        excess_return_vs_arm=FAST_PARENT,
        description=(
            f"{VERSION}: only post-frontier Solana signals from {RUNNER_PARENT}; preserves "
            "the parent runner exit. Existing shared frames only, no additional request."
        ),
    )
    nonsol = _clone(fast_parent, NONSOL_FAST_ARM, "EVM early impulse fast exit")
    nonsol.update(
        paired_opportunity_group="trajectory187_nonsol_tempo",
        excess_return_vs_arm=RUNNER_PARENT,
        description=(
            f"{VERSION}: only post-frontier BSC/Robinhood signals from {FAST_PARENT}; "
            "preserves the five-minute exit. Existing shared frames only."
        ),
    )
    armed = _clone(
        runner_parent, ARMED_RUNNER_ARM,
        "Early impulse runner, trailing armed after break-even",
    )
    armed.update(
        paired_opportunity_group="trajectory187_armed_runner",
        trailing_activate_return=0.0,
        excess_return_vs_arm=ARMED_CONTROL,
        description=(
            f"{VERSION}: same post-frontier signal, stop and horizon as {RUNNER_PARENT}; "
            "the sole exit change is a 15% trailing drawdown armed after the running "
            "economic return first reaches break-even."
        ),
    )
    return [solana, nonsol, armed]


def _chain(signal: Mapping[str, Any]) -> str:
    evidence = signal.get("decision_evidence") or {}
    features = evidence.get("feature_vector") or {}
    return str(features.get("chain") or "").lower()


def _alias(result: dict[str, Any], parent: Mapping[str, Any], arm: str) -> None:
    signal = deepcopy(dict(parent))
    signal["decision_key"] = f"{parent['decision_key']}|{arm}"
    evidence = signal.setdefault("decision_evidence", {})
    evidence["trajectory_regime187_source_decision_key"] = parent["decision_key"]
    evidence["trajectory_regime187_source_arm"] = evidence.get("mode")
    evidence["mode"] = arm
    result[arm] = signal


def alias_signals(signals: Mapping[str, Any]) -> dict[str, Any]:
    """Alias exact parent signals; chain routing occurs before Store admission."""
    result = dict(signals)
    fast = signals.get(FAST_PARENT)
    runner = signals.get(RUNNER_PARENT)
    if isinstance(runner, Mapping) and runner.get("decision_key"):
        if _chain(runner) == "solana":
            _alias(result, runner, SOLANA_RUNNER_ARM)
        _alias(result, runner, ARMED_RUNNER_ARM)
    if isinstance(fast, Mapping) and fast.get("decision_key"):
        if _chain(fast) in {"bsc", "robinhood"}:
            _alias(result, fast, NONSOL_FAST_ARM)
    return result


def snapshot() -> dict[str, Any]:
    return {
        "version": VERSION,
        "arms": list(ARMS),
        "parents": [FAST_PARENT, RUNNER_PARENT],
        "extra_requests": 0,
        "effects": "paper_only",
        "no_historical_backfill": True,
    }
