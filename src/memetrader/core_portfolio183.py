"""Compact same-entry fast/runner pair over the shared market-data core."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .composite_exit151 import CONTRACT as COMPOSITE_EXIT_CONTRACT


VERSION = "core-portfolio183/v1"
PARENT_ARM = "mv_quiet_depth_wide_v1"
FAST_ARM = "core183_market_fast5_v1"
RUNNER_ARM = "core183_market_runner30_v1"
ARMS = (FAST_ARM, RUNNER_ARM)
PAIR_GROUP = "core183_market_fast_runner_pair_v1"

_OWNED_FIELDS = {
    "account_lifecycle", "assessment_evidence", "assessment_note",
    "behavior_contract_hash", "concurrency_cap_revision", "entry_paused",
    "forward_activation_snapshot_id", "forward_started_at", "original_forward_started_at",
    "retirement_representative", "runtime_addition_id", "stage", "_execution",
}


def policies(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Clone one selective first-frame entry and isolate only the exit tempo."""
    base = {key: deepcopy(value) for key, value in parent.items() if key not in _OWNED_FIELDS}
    result = []
    for arm in ARMS:
        policy = deepcopy(base)
        policy.update(
            arm_id=arm,
            canonical_id=arm,
            source_arm_ids=[PARENT_ARM],
            entry_alias_of=PARENT_ARM,
            paired_entry_group=PAIR_GROUP,
            paired_entry_size=2,
            assessment_status="INSUFFICIENT",
            decision_eligible=True,
            observer_only=False,
            affects="paper_only",
            live=False,
        )
        if arm == FAST_ARM:
            policy.update(
                name="Shared-core selective momentum, fast 5-minute exit",
                exit_family="fast_escape",
                hard_stop_return=-0.15,
                take_profit=[],
                trailing_activate_return=0.20,
                trailing_drawdown=0.10,
                max_hold_minutes=5.0,
                excess_return_vs_arm=RUNNER_ARM,
                description=(
                    f"{VERSION}: first valid shared Dex frame enters through the parent's "
                    "market-visible activity and anti-churn filter. Exit is a five-minute "
                    "capital-recycling control with a -15% stop and +20%/-10% trailing rule."
                ),
            )
            for field in (
                "composite_exit151", "dynamic_principal_recovery",
                "minimum_principal_recovery_multiple", "trajectory_exit",
            ):
                policy.pop(field, None)
        else:
            policy.update(
                name="Shared-core selective momentum, 30-minute adaptive moonbag runner",
                exit_family="principal_lock_runner",
                hard_stop_return=-0.50,
                take_profit=[],
                trailing_activate_return=0.30,
                trailing_drawdown=0.25,
                max_hold_minutes=30.0,
                runner_review_minutes=15.0,
                composite_exit151=deepcopy(COMPOSITE_EXIT_CONTRACT),
                trajectory_exit="alpha149_vol_scaled_stop",
                dynamic_principal_recovery="minimum_net_debit_after_economic_floor/v4",
                minimum_principal_recovery_multiple=1.20,
                excess_return_vs_arm=FAST_ARM,
                description=(
                    f"{VERSION}: identical shared-data entry to {FAST_ARM}. Exit allows "
                    "realized-volatility protection and confirmed decay, then at 1.20x net "
                    "economic value sells only enough to recover principal and keeps the "
                    "remainder under a wider 30-minute runner contract."
                ),
            )
        result.append(policy)
    return result


def snapshot() -> dict[str, Any]:
    return {
        "version": VERSION,
        "parent": PARENT_ARM,
        "arms": list(ARMS),
        "paired_entry_group": PAIR_GROUP,
        "entry_difference": "none",
        "changed_dimension": "exit_tempo_and_runner_protection",
        "effects": "paper_only",
        "extra_requests": 0,
        "no_historical_backfill": True,
    }
