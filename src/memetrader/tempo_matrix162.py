"""Strictly-forward entry/exit tempo pairs for two mature alpha149 signals."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


VERSION = "tempo-matrix162/v2"

ACTIVITY_PAIR_GROUP = "tempo162_mature_two_step_t30_5m_90m_v1"
ACTIVITY_PAIR = (
    "alpha149_mature_two_step_t30_fast5_pair_v1",
    "alpha149_mature_two_step_t30_hold90_pair_v1",
)

EXPERIMENTS: dict[str, dict[str, Any]] = {
    "alpha149_df_mature_price_up_fast5_pair_v2": {
        "parent": "alpha149_df_mature_price_up_fast_v1",
        "name": "Mature two-frame paired 5-minute horizon",
        "max_hold_minutes": 5.0,
    },
    "alpha149_df_mature_price_up_fast5_control_v1": {
        "parent": "alpha149_df_mature_price_up_fast_v1",
        "name": "Mature two-frame entry with fresh 5-minute control",
        "max_hold_minutes": 5.0,
    },
    "alpha149_df_mature_price_up_hold90_v1": {
        "parent": "alpha149_df_mature_price_up_fast_v1",
        "name": "Mature two-frame entry with 90-minute horizon",
        "max_hold_minutes": 90.0,
    },
    "alpha149_df_mature_price_up_hold90_pair_v2": {
        "parent": "alpha149_df_mature_price_up_fast_v1",
        "name": "Mature two-frame paired 90-minute horizon",
        "max_hold_minutes": 90.0,
    },
    "alpha149_mature_two_step_fast5_v1": {
        "parent": "alpha149_mature_two_step_slow_v1",
        "name": "Mature three-frame entry with 5-minute horizon",
        "max_hold_minutes": 5.0,
    },
    "alpha149_mature_two_step_slow90_control_v1": {
        "parent": "alpha149_mature_two_step_slow_v1",
        "name": "Mature three-frame entry with fresh 90-minute control",
        "max_hold_minutes": 90.0,
    },
    ACTIVITY_PAIR[0]: {
        "parent": "alpha149_mature_two_step_slow_v1",
        "name": "Active mature three-frame entry with 5-minute horizon",
        "max_hold_minutes": 5.0,
        "activity_floor": {"min_trades": 30.0},
        "paired_entry_group": ACTIVITY_PAIR_GROUP,
    },
    ACTIVITY_PAIR[1]: {
        "parent": "alpha149_mature_two_step_slow_v1",
        "name": "Active mature three-frame entry with 90-minute horizon",
        "max_hold_minutes": 90.0,
        "activity_floor": {"min_trades": 30.0},
        "paired_entry_group": ACTIVITY_PAIR_GROUP,
    },
}

PAIRS = (
    (
        "alpha149_df_mature_price_up_fast5_pair_v2",
        "alpha149_df_mature_price_up_hold90_pair_v2",
    ),
    (
        "alpha149_mature_two_step_fast5_v1",
        "alpha149_mature_two_step_slow90_control_v1",
    ),
    ACTIVITY_PAIR,
)


def install() -> None:
    """Teach the existing alpha149 engine the fresh paired arm mappings."""
    from . import alpha149

    for arm, spec in EXPERIMENTS.items():
        parent = str(spec["parent"])
        kind = alpha149.SPECS[parent][0]
        alpha149.SPECS[arm] = (kind, str(spec["name"]), int(spec["max_hold_minutes"]))
        override = deepcopy(alpha149.OVERRIDES.get(parent) or {})
        override.update(
            max_hold_minutes=float(spec["max_hold_minutes"]),
            description=(
                f"{VERSION}: same point-in-time entry signal and exit contract as {parent}; "
                f"fresh-account paired horizon={float(spec['max_hold_minutes']):g} minutes."
            ),
        )
        alpha149.OVERRIDES[arm] = override
    alpha149.ALL_ARMS = tuple(alpha149.SPECS) + tuple(alpha149.EXIT_ARMS)
    alpha149.KINDS = tuple(kind for kind, _, _ in alpha149.SPECS.values())


def policy(parent: Mapping[str, Any], arm: str) -> dict[str, Any]:
    """Clone a registered parent while changing only identity and hold horizon."""
    spec = EXPERIMENTS[arm]
    result = deepcopy(dict(parent))
    result.update(
        arm_id=arm,
        canonical_id=arm,
        name=str(spec["name"]),
        entry_family=arm,
        max_hold_minutes=float(spec["max_hold_minutes"]),
        description=(
            f"{VERSION}: same point-in-time entry predicate, notional, stop and trailing "
            f"contract as {spec['parent']}; fresh paired horizon is "
            f"{float(spec['max_hold_minutes']):g} minutes."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}), "direction": arm,
    }
    if spec.get("activity_floor"):
        result["entry_filter"]["activity_floor"] = deepcopy(spec["activity_floor"])
    if spec.get("paired_entry_group"):
        result.update(
            paired_entry_group=str(spec["paired_entry_group"]),
            paired_entry_size=2,
        )
        peer = next(candidate for candidate in ACTIVITY_PAIR if candidate != arm)
        result["excess_return_vs_arm"] = peer
    result.pop("behavior_contract_hash", None)
    result.pop("forward_activation_snapshot_id", None)
    result.pop("forward_started_at", None)
    result.pop("runtime_addition_id", None)
    result.pop("stage", None)
    # A parent's process-start clock can predate this arm's append-only frontier and
    # would make the fresh clone permanently unreachable. Signal and record timestamps
    # remain subject to the arm's own forward_started_at checks in Store.
    result.pop("signal_origin_clock", None)
    return result


def snapshot() -> dict[str, Any]:
    return {
        "version": VERSION,
        "arms": list(EXPERIMENTS),
        "parents": {arm: spec["parent"] for arm, spec in EXPERIMENTS.items()},
        "pairs": [list(pair) for pair in PAIRS],
        "changed_dimension": "max_hold_minutes_only",
        "activity_conditioned_pair": {
            "arms": list(ACTIVITY_PAIR),
            "min_trades_5m": 30.0,
            "paired_entry_group": ACTIVITY_PAIR_GROUP,
        },
        "effects": "paper_only",
        "extra_requests": 0,
        "no_historical_backfill": True,
    }
