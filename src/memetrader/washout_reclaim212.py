"""Same-entry washout reclaim with a point-in-time structural failure exit."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .models import iso, parse_time


VERSION = "washout-reclaim212/v1"
ARM = "alpha212_washout_reclaim_anchor_v1"
CONTROL = "alpha212_washout_reclaim_hold_control_v1"
PARENT = "alpha149_washout_reclaim_hold_v1"
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
        name="Washout reclaim, confirmed anchor failure",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="washout212_same_source",
        excess_return_vs_arm=PARENT,
        reclaim_anchor_exit212=True,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: same frozen {PARENT} entry and ordinary 2U sizing. "
            "The pre-uptick observed price is frozen at signal time; after BUY, "
            "two distinct fresh original-pool marks below it trigger a next-observed "
            "Paper SELL. Recovery or a >60s observation gap clears the streak. "
            "Existing stop, trailing, liquidity and 120m timeout remain. No extra API."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": ARM}
    result.pop("signal_origin_clock", None)
    return result


def control_policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=CONTROL, canonical_id=CONTROL, entry_family=CONTROL,
        name="Washout reclaim, original hold control",
        entry_alias_of=PARENT, source_arm_ids=[PARENT],
        paired_opportunity_group="washout212_same_source",
        excess_return_vs_arm=ARM,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: new-frontier account using the same frozen {PARENT} "
            "entry and its unchanged 120-minute exit contract. The old parent "
            "account is depleted and paused; this control permits a contemporary "
            "comparison with 212 without altering or refunding that account."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": CONTROL}
    result.pop("signal_origin_clock", None)
    return result


def alias_signal(source: Mapping[str, Any], arm: str = ARM) -> dict[str, Any] | None:
    if not source.get("decision_key"):
        return None
    signal = deepcopy(dict(source))
    evidence = signal.setdefault("decision_evidence", {})
    prior = (evidence.get("feature_vector") or {}).get("prev") or {}
    try:
        anchor = float(prior.get("price_usd"))
        prior_at = parse_time(prior["observed_at"])
        signal_at = parse_time(signal["observed_at"])
    except (TypeError, ValueError, KeyError):
        return None
    if not (0 < anchor < float("inf") and prior_at < signal_at):
        return None
    signal["decision_key"] = f"{source['decision_key']}|{arm}"
    evidence["reclaim_anchor212"] = {"price_usd": anchor,
                                     "observed_at": iso(prior_at),
                                     "signal_observed_at": iso(signal_at)}
    return signal


def frozen_anchor(signal: Mapping[str, Any], filled_at: Any) -> dict[str, Any] | None:
    evidence = (signal.get("decision_evidence") or {}).get("reclaim_anchor212") or {}
    try:
        price = float(evidence["price_usd"])
        prior_at = parse_time(evidence["observed_at"])
        signal_at = parse_time(evidence["signal_observed_at"])
        receipt_at = parse_time(signal["recorded_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 < price < float("inf") and prior_at < signal_at <= receipt_at
            <= parse_time(filled_at)):
        return None
    return {"price_usd": price, "observed_at": iso(prior_at),
            "signal_observed_at": iso(signal_at), "recorded_at": iso(receipt_at)}


def advance(state: Mapping[str, Any], *, anchor: float, price: float,
            sequence: int, observed_at: Any, opened_at: Any,
            pair_address: str) -> tuple[dict[str, Any], bool]:
    """Return restart-safe state and whether this distinct mark confirms failure."""
    result = dict(state)
    observed = parse_time(observed_at)
    if not (anchor > 0 and price > 0 and observed > parse_time(opened_at)
            and pair_address and sequence > 0):
        return result, False
    previous = result.get("reclaim_anchor212")
    if isinstance(previous, dict):
        try:
            prior_at = parse_time(previous["observed_at"])
            if (previous.get("pair_address") == pair_address
                    and sequence <= int(previous["sequence"])):
                return result, False
            if observed <= prior_at:
                return result, False
        except (KeyError, TypeError, ValueError):
            previous = None
    if price >= anchor:
        result.pop("reclaim_anchor212", None)
        return result, False
    if (isinstance(previous, dict) and previous.get("pair_address") == pair_address
            and 0 < (observed - prior_at).total_seconds() <= 60):
        return result, True
    result["reclaim_anchor212"] = {
        "pair_address": pair_address, "sequence": sequence, "observed_at": iso(observed),
    }
    return result, False
