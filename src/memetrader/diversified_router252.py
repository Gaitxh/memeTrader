"""One-position router requiring agreement from distinct observed signal families."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


ARM = "single_token_diversified_router_v1"
PARENT = "cohort_opportunity_router_v1"
CONTRACT = "single-token-diversified-router252/v1"

FAMILIES = (
    ("reawakening", ("organic_reawakening_flow_v1", "event_clone_narrative_reawakening_v1",
                     "trajectory144_second_wave_v1")),
    ("trend", ("trajectory144_trend_runner_v1", "revision249_unpaired_trend_control_v1",
               "trajectory187_solana_runner_v1", "trajectory187_armed_runner_v1")),
    ("absorption", ("trajectory144_absorption_reclaim_v1", "dex_first_dip_resilience_v1")),
    ("clone", ("clone_consensus_leader_v2",)),
    ("early_flow", ("organic_early_flow_v1", "organic_short_observed_flow_v1",
                    "trajectory144_early_activity_fast_v1")),
)


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact cohort router parent required")
    out = deepcopy(dict(parent))
    for key in ("behavior_contract_hash", "forward_activation_snapshot_id",
                "forward_started_at", "original_forward_started_at", "runtime_addition_id"):
        out.pop(key, None)
    out.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Single-token diversified signal router", revision_of=PARENT,
        source_arm_ids=sorted({arm for _, arms in FAMILIES for arm in arms}),
        notional_usd=20.0, max_hold_minutes=15.0,
        paired_opportunity_group=ARM,
        paired_opportunity_semantics="one_position_after_two_distinct_signal_families",
        signal_origin_clock="router_source_origin_at",
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            "One 20U position per token only when at least two predeclared, distinct "
            "signal families are simultaneously current. Existing research arms remain "
            "unchanged; no queue, backfill or extra market request."
        ),
    )
    out["entry_filter"] = {"direction": ARM, "max_concurrent_positions": 16,
                           "single_token_open_or_reserved": True,
                           "single_token_lifetime_entry": True}
    return out


def alias(signals: Mapping[str, Any]) -> dict[str, Any]:
    present = []
    for family, arms in FAMILIES:
        hits = [arm for arm in arms if isinstance(signals.get(arm), Mapping)
                and signals[arm].get("decision_key")]
        if hits:
            present.append((family, hits))
    if len(present) < 2:
        return {}
    selected_arm = present[0][1][0]
    value = deepcopy(dict(signals[selected_arm]))
    origin = value.get("observed_at")
    evidence = dict(value.get("decision_evidence") or {})
    evidence.update(diversified_router_contract=CONTRACT,
                    contributing_families=[family for family, _ in present],
                    contributing_arms=[arm for _, arms in present for arm in arms],
                    router_source_arm=selected_arm,
                    router_source_origin_at=origin,
                    extra_market_requests=0)
    value.update(decision_key=f"{value['decision_key']}|{ARM}", decision_evidence=evidence)
    return {ARM: value}
