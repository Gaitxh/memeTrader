"""Old-pool tempo continuation after a distinct fresh confirmation frame."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Mapping

from .activity_tempo193 import Tracker as TempoTracker, _number
from .models import iso, parse_time


VERSION = "activity-confirm211/v1"
ARM = "activity211_old_pool_confirmed_fast5_v1"
PARENT = "activity200_old_pool_tempo_fast5_v1"
MAX_PENDING = 1024
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
        name="Old-pool confirmed tempo, fast 5m",
        feature_contract=VERSION,
        feature_hypothesis="old_pool_tempo_persists_one_fresh_frame",
        entry_match_mode="isolated_cohort_observer",
        source_arm_ids=[],
        requires_distinct_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        notional_usd=20.0, max_hold_minutes=5,
        paired_opportunity_group="activity193_trigger_then_confirmation",
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: freeze the first 193 old-pool tempo trigger, then require "
            "a distinct 15-60s later same-provider/same-pool fresh frame that still "
            "meets the 193 predicate with nondecreasing price and liquidity. Normal "
            "safety and another next-observed Paper quote precede any BUY. Preserve "
            "the 200 five-minute exit and all ordinary execution costs. No new API."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}), "direction": ARM,
        "max_concurrent_positions": 6, "single_token_lifetime_entry": True,
    }
    for key in ("entry_alias_of", "excess_return_vs_arm", "signal_origin_clock"):
        result.pop(key, None)
    return result


class Tracker:
    """Only post-activation, restart-local triggers can be confirmed."""

    def __init__(self, started_at: Any):
        self.predicate = TempoTracker(started_at)
        self.pending: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self.seen: OrderedDict[tuple[str, str], None] = OrderedDict()

    def begin(self, signal: Mapping[str, Any], frame: Mapping[str, Any], now: Any) -> None:
        selected = signal.get("selected") or {}
        key = (str(selected.get("token_id") or ""), str(selected.get("pair_address") or ""))
        if key in self.pending or key in self.seen or key != (frame.get("token_id"), frame.get("pair_address")):
            return
        try:
            observed = parse_time(signal["observed_at"])
            recorded = parse_time(signal["recorded_at"])
            at = parse_time(now)
            price, liquidity = _number(frame.get("price_usd")), _number(frame.get("liquidity_usd"))
        except (KeyError, TypeError, ValueError):
            return
        if not (observed <= recorded <= at and price is not None and price > 0
                and liquidity is not None and liquidity > 0):
            return
        self.pending[key] = {
            "observed": observed, "recorded": recorded,
            "price": price, "liquidity": liquidity,
            "provider": str(frame.get("provider") or ""),
            "source_decision_key": str(signal.get("decision_key") or ""),
        }
        while len(self.pending) > MAX_PENDING:
            self.pending.popitem(last=False)

    def accept(self, frame: Mapping[str, Any], now: Any, *, floor: float) -> dict[str, Any] | None:
        key = (str(frame.get("token_id") or ""), str(frame.get("pair_address") or ""))
        first = self.pending.get(key)
        if first is None or key in self.seen:
            return None
        try:
            observed = parse_time(frame["observed_at"])
            ingested = parse_time(frame["ingested_at"])
            recorded = parse_time(frame["recorded_at"])
            at = parse_time(now)
        except (KeyError, TypeError, ValueError):
            return None
        delay = (observed - first["observed"]).total_seconds()
        if delay > 60:
            self.pending.pop(key, None)
            return None
        price, liquidity = _number(frame.get("price_usd")), _number(frame.get("liquidity_usd"))
        if not (15 <= delay <= 60
                and first["recorded"] <= observed <= ingested <= recorded <= at
                and (at - observed).total_seconds() <= 30
                and str(frame.get("provider") or "") == first["provider"]
                and price is not None and price >= first["price"]
                and liquidity is not None and liquidity >= first["liquidity"]):
            return None
        candidate = self.predicate.accept(frame, at, floor=floor)
        if candidate is None:
            return None
        self.pending.pop(key, None)
        self.seen[key] = None
        while len(self.seen) > MAX_PENDING:
            self.seen.popitem(last=False)
        candidate["episode_id"] = f"{VERSION}:{key[0]}:{key[1]}"
        candidate["decision_key"] = f"{VERSION}:{key[0]}:{key[1]}:{iso(observed)}"
        candidate["decision_evidence"].update({
            "version": VERSION,
            "trigger_decision_key": first["source_decision_key"],
            "trigger_observed_at": iso(first["observed"]),
            "trigger_recorded_at": iso(first["recorded"]),
            "confirmation_observed_at": iso(observed),
            "trigger_price_usd": first["price"],
            "trigger_liquidity_usd": first["liquidity"],
        })
        return candidate
