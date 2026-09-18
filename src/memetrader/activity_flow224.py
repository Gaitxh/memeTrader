"""Same-entry old-pool short hold with earlier flow and pool-depth exits."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .activity_tempo_fast200 import PARENT, _OWNED_FIELDS


ARM = "activity224_old_pool_flow_floor_fast_v1"
VERSION = "activity-flow224/v1"


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Old-pool tempo, fast flow and depth exit",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="activity193_same_entry",
        excess_return_vs_arm=PARENT,
        max_hold_minutes=5,
        flow_grace_minutes=1,
        minimum_buy_ratio=0.5,
        emergency_liquidity_usd=1600,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        feature_contract=VERSION,
        feature_hypothesis="old_pool_short_hold_flow_or_depth_decay",
        description=(
            f"{VERSION}: share {PARENT}'s as-of old-pool activity entry and "
            "next-observed Paper BUY. After one minute, request a next-observed "
            "SELL if the fresh original-pool five-minute buy share falls below "
            "50%; also exit if fresh original-pool liquidity falls below 1600U "
            "before the shared 1000U writeoff floor. Maximum hold is five "
            "minutes. Missing/stale marks do not trigger these exits. Existing "
            "safety, hard stop, trailing, slippage and fees remain. No new API."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}),
        "direction": ARM,
        "max_concurrent_positions": 8,
        "single_token_lifetime_entry": True,
    }
    result.pop("signal_origin_clock", None)
    return result


def alias_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(signal))
    result["decision_key"] = f"{signal['decision_key']}|{ARM}"
    evidence = result.setdefault("decision_evidence", {})
    evidence["activity_flow224_source_decision_key"] = signal["decision_key"]
    evidence["mode"] = ARM
    return result
