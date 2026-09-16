"""Forward-only second-frame confirmation of a new migration pool."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import canonical_token_address, iso, parse_time


VERSION = "migration-confirm214/v1"
ARM = "migration214_pool_persistence_v1"
PARENT = "migration209_first_tradable_v1"
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
        name="Migration pool persistence, second frame",
        feature_contract=VERSION,
        feature_hypothesis="migration_first_pool_survives_fresh_second_frame",
        entry_match_mode="isolated_cohort_observer", source_arm_ids=[],
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: after 209's locally observed first tradable migration quote, "
            "wait 8-90 seconds for a distinct fresh DexScreener frame from the same "
            "Pumpswap original pool. Require price >=85% and <=150% of the trigger, "
            "liquidity >=70% of trigger and the shared pool floor, at least two "
            "additional m5 buys and an observed sell. Normal safety and a further "
            "next-observed Paper fill apply. Parent runner exit and 20U size remain. "
            "The delay may miss the fastest winners; no additional market request."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}), "direction": ARM,
        "max_concurrent_positions": 2, "single_token_lifetime_entry": True,
    }
    for key in ("entry_alias_of", "excess_return_vs_arm", "signal_origin_clock"):
        result.pop(key, None)
    return result


def _positive(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


class Tracker:
    """Bounded restart-local trigger receipts, never reconstructed from history."""

    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.pending: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self.seen: OrderedDict[tuple[str, str], None] = OrderedDict()

    def begin(self, signal: Mapping[str, Any], frame: Mapping[str, Any], now: Any) -> None:
        selected = signal.get("selected") or {}
        key = (str(selected.get("token_id") or ""), str(selected.get("pair_address") or ""))
        if key in self.pending or key in self.seen or key != (
            frame.get("token_id"), frame.get("pair_address")
        ):
            return
        try:
            observed = parse_time(signal["observed_at"])
            recorded = parse_time(signal["recorded_at"])
            at = parse_time(now)
        except (KeyError, TypeError, ValueError):
            return
        price = _positive(frame.get("price_usd"))
        liquidity = _positive(frame.get("liquidity_usd"))
        buys = _positive(frame.get("buys_5m"))
        sells = _positive(frame.get("sells_5m"))
        if not (self.started_at <= observed <= recorded <= at and
                price is not None and liquidity is not None and
                buys is not None and sells is not None):
            return
        self.pending[key] = {
            "observed": observed, "recorded": recorded, "price": price,
            "liquidity": liquidity, "buys": buys, "sells": sells,
            "provider": str(frame.get("provider") or ""),
            "trigger_key": str(signal.get("decision_key") or ""),
            "migration_fact_id": (signal.get("decision_evidence") or {}).get("migration_fact_id"),
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
            chain, address = key[0].split(":", 1)
            base = canonical_token_address(chain, str(frame["provider_base_address"]))
            pool = canonical_token_address(chain, key[1])
        except (KeyError, TypeError, ValueError):
            return None
        delay = (observed - first["observed"]).total_seconds()
        if delay > 90:
            self.pending.pop(key, None)
            return None
        price = _positive(frame.get("price_usd"))
        liquidity = _positive(frame.get("liquidity_usd"))
        buys = _positive(frame.get("buys_5m"))
        sells = _positive(frame.get("sells_5m"))
        age = _positive(frame.get("pool_age_seconds"))
        threshold = _positive(floor)
        if not (
            8 <= delay <= 90 and first["recorded"] <= observed <= ingested <= recorded <= at
            and (at - observed).total_seconds() <= 30
            and chain == frame.get("chain") == frame.get("provider_chain_id") == "solana"
            and canonical_token_address(chain, address) == base and pool
            and frame.get("pair_address") == key[1]
            and str(frame.get("provider") or "") == first["provider"]
            and str(frame.get("provider") or "").split(":")[-1] == "dexscreener"
            and str(frame.get("provider_dex_id") or "").lower() == "pumpswap"
            and price is not None and .85 * first["price"] <= price <= 1.5 * first["price"]
            and liquidity is not None and threshold is not None
            and liquidity >= max(threshold, .7 * first["liquidity"])
            and buys is not None and buys >= first["buys"] + 2
            and sells is not None and sells >= 1
            and age is not None and age <= 390
        ):
            return None
        self.pending.pop(key, None)
        self.seen[key] = None
        while len(self.seen) > MAX_PENDING:
            self.seen.popitem(last=False)
        return {
            "episode_id": f"{VERSION}:{key[0]}:{pool}",
            "decision_key": f"{VERSION}:{key[0]}:{pool}:{iso(observed)}",
            "selected": {"token_id": key[0], "pair_address": pool},
            "observed_at": iso(observed), "recorded_at": iso(recorded),
            "decision_evidence": {
                "version": VERSION, "trigger_decision_key": first["trigger_key"],
                "migration_fact_id": first["migration_fact_id"],
                "trigger_observed_at": iso(first["observed"]),
                "confirmation_observed_at": iso(observed),
                "trigger_price_usd": first["price"], "price_usd": price,
                "trigger_liquidity_usd": first["liquidity"], "liquidity_usd": liquidity,
                "trigger_buys_5m": first["buys"], "buys_5m": buys,
                "sells_5m": sells, "effective_pool_floor_usd": threshold,
            },
        }
