"""Same-entry trend runner with an as-of breakout-origin failure exit."""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import iso, parse_time


VERSION = "trend-anchor220/v1"
ARM = "trajectory220_breakout_anchor_v1"
PARENT = "trajectory144_trend_runner_v1"
_OWNED = {
    "account_lifecycle", "assessment_evidence", "assessment_note",
    "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
    "forward_started_at", "original_forward_started_at", "retirement_representative",
    "runtime_addition_id", "stage", "_execution",
}


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items() if key not in _OWNED}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Trend runner, confirmed breakout-origin failure",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="trajectory220_same_source",
        excess_return_vs_arm=PARENT,
        reclaim_anchor_exit212=True,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: share the frozen {PARENT} buy signal and next-observed Paper fill. "
            "Freeze the actual 30-second price-window origin at signal time. After buying, "
            "two distinct fresh original-pool marks below that origin within 60 seconds "
            "request a next-observed exit. Existing runner, stop, trailing and pool-loss "
            "rules remain. Uses no new API or hindsight peak."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": ARM}
    result.pop("signal_origin_clock", None)
    return result


def alias_signal(source: Mapping[str, Any]) -> dict[str, Any] | None:
    feature = ((source.get("decision_evidence") or {}).get("feature_vector") or {})
    window = feature.get("window_30") or {}
    current = feature.get("current") or {}
    try:
        signal_at = parse_time(source["observed_at"])
        start_at = parse_time(window["start_at"])
        end_at = parse_time(window["end_at"])
        receipt_at = parse_time(source["recorded_at"])
        price = float(current["price_usd"])
        change = float(window["return_fraction"])
        anchor = price / (1 + change)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if not (source.get("decision_key") and start_at < end_at == signal_at <= receipt_at
            and 30 <= (end_at - start_at).total_seconds() <= 90
            and isfinite(anchor) and anchor > 0 and isfinite(price) and price > anchor):
        return None
    signal = deepcopy(dict(source))
    signal["decision_key"] = f"{source['decision_key']}|{ARM}"
    signal.setdefault("decision_evidence", {})["reclaim_anchor212"] = {
        "price_usd": anchor, "observed_at": iso(start_at),
        "signal_observed_at": iso(signal_at), "source": VERSION,
    }
    return signal
