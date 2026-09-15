"""Forward-only low-threshold principal recovery for the deep goldendog entry."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "goldendog-recovery164/v1"
ARM = "alpha149_goldendog_low_recovery20_v1"
CONTROL_ARM = "alpha149_goldendog_low_recovery20_control_v1"
ARMS = (CONTROL_ARM, ARM)
PARENT_ARM = "alpha149_goldendog_deep_hold_v1"
MINIMUM_ECONOMIC_MULTIPLE = 1.20


def install() -> None:
    """Route the challenger through the parent's existing entry predicate."""
    from . import alpha149

    kind, _, hold = alpha149.SPECS[PARENT_ARM]
    alpha149.SPECS[CONTROL_ARM] = (
        kind, "Goldendog low principal recovery 20 control", hold,
    )
    alpha149.SPECS[ARM] = (kind, "Goldendog low principal recovery 20", hold)
    control = deepcopy(alpha149.OVERRIDES[PARENT_ARM])
    control.update(
        excess_return_vs_arm=ARM,
        description=(
            f"{VERSION}: fresh-capital same-entry control for {ARM}; it preserves every exit "
            f"field from {PARENT_ARM} and intentionally has no low principal-recovery branch."
        ),
    )
    alpha149.OVERRIDES[CONTROL_ARM] = control
    override = deepcopy(alpha149.OVERRIDES[PARENT_ARM])
    override.update(
        dynamic_principal_recovery="minimum_net_debit_after_economic_floor/v4",
        minimum_principal_recovery_multiple=MINIMUM_ECONOMIC_MULTIPLE,
        excess_return_vs_arm=PARENT_ARM,
        description=(
            f"{VERSION}: same point-in-time entry, stop, trailing and horizon as "
            f"{PARENT_ARM}; after a fresh visible mark reaches {MINIMUM_ECONOMIC_MULTIPLE:.2f}x "
            "stake net of configured Paper sell costs, sell only the minimum quantity needed "
            "to recover principal and leave the remainder on the parent exit contract."
        ),
    )
    alpha149.OVERRIDES[ARM] = override
    alpha149.GUARD_ARMS = alpha149.GUARD_ARMS | set(ARMS)
    alpha149.ALL_ARMS = tuple(alpha149.SPECS) + tuple(alpha149.EXIT_ARMS)
    alpha149.KINDS = tuple(kind for kind, _, _ in alpha149.SPECS.values())


def policy(parent: Mapping[str, Any], arm: str = ARM) -> dict[str, Any]:
    """Clone the frozen parent into the fresh control or principal-recovery challenger."""
    if arm not in ARMS:
        raise KeyError(arm)
    result = deepcopy(dict(parent))
    result.update(arm_id=arm, canonical_id=arm, entry_family=arm)
    if arm == ARM:
        result.update(
            name="Goldendog low principal recovery 20",
            dynamic_principal_recovery="minimum_net_debit_after_economic_floor/v4",
            minimum_principal_recovery_multiple=MINIMUM_ECONOMIC_MULTIPLE,
            excess_return_vs_arm=CONTROL_ARM,
            description=(
                f"{VERSION}: same strictly-forward entry and parent exits as {PARENT_ARM}; "
                f"principal recovery becomes eligible only at {MINIMUM_ECONOMIC_MULTIPLE:.2f}x "
                "stake net of configured Paper sell costs."
            ),
        )
    else:
        result.update(
            name="Goldendog low principal recovery 20 control",
            excess_return_vs_arm=ARM,
            description=(
                f"{VERSION}: fresh-capital same-entry control for {ARM}; every exit field is "
                f"copied from {PARENT_ARM} and low principal recovery remains disabled."
            ),
        )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}), "direction": arm,
    }
    result.pop("behavior_contract_hash", None)
    result.pop("forward_activation_snapshot_id", None)
    result.pop("forward_started_at", None)
    result.pop("runtime_addition_id", None)
    result.pop("stage", None)
    return result


def snapshot() -> dict[str, Any]:
    return {
        "version": VERSION,
        "arm": ARM,
        "control_arm": CONTROL_ARM,
        "arms": list(ARMS),
        "parent": PARENT_ARM,
        "minimum_principal_recovery_multiple": MINIMUM_ECONOMIC_MULTIPLE,
        "changed_dimension": "fresh_mark_minimum_principal_recovery_only",
        "effects": "paper_only",
        "extra_requests": 0,
        "no_historical_backfill": True,
    }
