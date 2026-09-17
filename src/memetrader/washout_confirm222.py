"""Delayed washout-reclaim entry using a later original-pool observation."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import iso, parse_time
from .washout_reclaim212 import ARM as EXIT_PARENT, PARENT, _OWNED_FIELDS


VERSION = "washout-confirm222/v1"
ARM = "alpha222_washout_half_reclaim_v1"
MAX_PENDING = 1024


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Washout, half-reclaim confirmation",
        feature_contract=VERSION,
        feature_hypothesis="washout_recovers_half_of_prior_drawdown_before_buy",
        entry_match_mode="isolated_cohort_observer", source_arm_ids=[],
        requires_distinct_trajectory_frame=False,
        conditional_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        reclaim_anchor_exit212=True, notional_usd=20.0,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: after a fresh {PARENT} washout trigger, wait up to 180s "
            "for a distinct fresh same-provider original-pool frame recovering "
            "halfway from the frozen pre-uptick low to the then-known episode high. "
            "Require reported sells and nondecreasing pool liquidity. Execute only "
            "on a subsequent observed quote, with normal safety, 20U sizing, costs, "
            "120m hold and the two-mark structural failure exit. No new API."
        ),
    )
    result["entry_filter"] = {**(result.get("entry_filter") or {}), "direction": ARM,
                              "max_concurrent_positions": 8,
                              "single_token_lifetime_entry": True}
    for key in ("entry_alias_of", "excess_return_vs_arm", "signal_origin_clock"):
        result.pop(key, None)
    return result


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


class Tracker:
    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.pending: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self.seen: OrderedDict[tuple[str, str], None] = OrderedDict()

    def begin(self, signal: Mapping[str, Any], frame: Mapping[str, Any], now: Any) -> None:
        selected = signal.get("selected") or {}
        key = (str(selected.get("token_id") or ""), str(selected.get("pair_address") or ""))
        feature = (signal.get("decision_evidence") or {}).get("feature_vector") or {}
        previous = feature.get("prev") or {}
        current = feature.get("current") or {}
        try:
            observed = parse_time(signal["observed_at"])
            feature_at = parse_time(feature["observed_at"])
            ingested = parse_time(feature["ingested_at"])
            recorded = parse_time(signal["recorded_at"])
            prior_at = parse_time(previous["observed_at"])
            frame_at = parse_time(frame["observed_at"])
            frame_ingested = parse_time(frame["ingested_at"])
            frame_recorded = parse_time(frame["recorded_at"])
            at = parse_time(now)
            low = _positive(previous.get("price_usd"))
            price = _positive(current.get("price_usd"))
            liquidity = _positive(frame.get("liquidity_usd"))
            drawdown = float(feature["drawdown"])
            peak = price / (1 + drawdown) if price is not None else None
        except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            return
        if not (signal.get("decision_key") and all(key)
                and key == (frame.get("token_id"), frame.get("pair_address"))
                and key not in self.pending and key not in self.seen
                and prior_at < observed and self.started_at <= observed == feature_at == frame_at
                and observed <= ingested <= recorded <= at
                and observed <= frame_ingested <= frame_recorded <= at
                and (at - observed).total_seconds() <= 30
                and low is not None and price is not None and price > low
                and peak is not None and isfinite(peak) and peak > price
                and isfinite(drawdown) and drawdown <= -.12
                and liquidity is not None and liquidity >= 2000
                and str(frame.get("provider") or "").startswith(("dexscreener", "geckoterminal"))):
            return
        threshold = (low + peak) / 2
        if threshold <= price:
            return
        self.pending[key] = {
            "observed": observed, "recorded": recorded, "prior_at": prior_at,
            "low": low, "peak": peak, "threshold": threshold,
            "liquidity": liquidity, "provider": str(frame["provider"]),
            "source_decision_key": str(signal["decision_key"]),
        }
        while len(self.pending) > MAX_PENDING:
            self.pending.popitem(last=False)

    def accept(self, frame: Mapping[str, Any], now: Any) -> dict[str, Any] | None:
        key = (str(frame.get("token_id") or ""), str(frame.get("pair_address") or ""))
        first = self.pending.get(key)
        if first is None:
            return None
        try:
            observed, ingested, recorded = (parse_time(frame[field]) for field in
                                            ("observed_at", "ingested_at", "recorded_at"))
            at = parse_time(now)
            price = _positive(frame.get("price_usd"))
            liquidity = _positive(frame.get("liquidity_usd"))
            sells = float(frame["sells_5m"])
        except (KeyError, TypeError, ValueError):
            return None
        delay = (observed - first["observed"]).total_seconds()
        if delay > 180:
            self.pending.pop(key, None)
            return None
        if not (0 < delay <= 180 and first["recorded"] <= observed <= ingested <= recorded <= at
                and (at - observed).total_seconds() <= 30
                and str(frame.get("provider") or "") == first["provider"]
                and price is not None and price >= first["threshold"]
                and liquidity is not None and liquidity >= first["liquidity"]
                and isfinite(sells) and sells >= 1):
            return None
        self.pending.pop(key, None)
        self.seen[key] = None
        while len(self.seen) > MAX_PENDING:
            self.seen.popitem(last=False)
        return {
            "episode_id": f"{VERSION}:{key[0]}:{key[1]}",
            "decision_key": f"{VERSION}:{key[0]}:{key[1]}:{iso(observed)}",
            "selected": {"token_id": key[0], "pair_address": key[1]},
            "observed_at": iso(observed), "recorded_at": iso(recorded),
            "decision_evidence": {
                "version": VERSION, "provider": first["provider"],
                "trigger_decision_key": first["source_decision_key"],
                "trigger_observed_at": iso(first["observed"]),
                "trigger_recorded_at": iso(first["recorded"]),
                "confirmation_observed_at": iso(observed),
                "price_usd": price, "liquidity_usd": liquidity,
                "sells_5m": sells, "half_reclaim_threshold_usd": first["threshold"],
                "reclaim_anchor212": {
                    "price_usd": first["low"], "observed_at": iso(first["prior_at"]),
                    "signal_observed_at": iso(observed), "source": VERSION,
                },
            },
        }
