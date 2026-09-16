"""Forward-only first tradable quote after a locally received migration."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import canonical_token_address, iso, parse_time


VERSION = "migration-first209/v1"
ARM = "migration209_first_tradable_v1"
PARENT = "trajectory187_solana_runner_v1"
MAX_FACTS = 1024
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
        name="Migration first tradable quote",
        feature_contract=VERSION,
        feature_hypothesis="fresh_migration_first_tradable_pool",
        entry_match_mode="isolated_cohort_observer",
        source_arm_ids=[], notional_usd=20.0,
        requires_distinct_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: locally received PumpPortal migration followed within five minutes "
            "by the first fresh DexScreener Pumpswap token-side quote on a pool at most "
            "five minutes old, with two buys, one sell and executable original-pool depth. "
            "The migration pool label is not trusted as pool identity. Normal safety, "
            "next-observed Paper fill and parent runner exit apply; no extra request."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}), "direction": ARM,
        "max_concurrent_positions": 2, "single_token_lifetime_entry": True,
    }
    for key in ("entry_alias_of", "excess_return_vs_arm", "signal_origin_clock"):
        result.pop(key, None)
    return result


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


class Tracker:
    """Restart-local bounded receipts: never reconstruct pre-activation migrations."""

    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.facts: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.seen: OrderedDict[str, None] = OrderedDict()

    def observe_fact(self, fact: Mapping[str, Any], now: Any) -> None:
        if fact.get("launch_event_type") != "migration" or fact.get("chain") != "solana":
            return
        try:
            observed = parse_time(fact["source_observed_at"])
            ingested = parse_time(fact["ingested_at"])
            recorded = parse_time(fact["recorded_at"])
            at = parse_time(now)
            token_id = str(fact["token_id"])
            address = canonical_token_address("solana", token_id.split(":", 1)[1])
        except (KeyError, IndexError, TypeError, ValueError):
            return
        if not (token_id == f"solana:{address}" and
                observed <= ingested <= recorded <= at and
                self.started_at <= recorded and
                (at - recorded).total_seconds() <= 30 and token_id not in self.seen):
            return
        self.facts[token_id] = {"observed_at": observed, "ingested_at": ingested,
                                "recorded_at": recorded, "fact_id": fact.get("id")}
        self.facts.move_to_end(token_id)
        while len(self.facts) > MAX_FACTS:
            self.facts.popitem(last=False)

    def accept(self, frame: Mapping[str, Any], now: Any, *, floor: float) -> dict[str, Any] | None:
        token_id = str(frame.get("token_id") or "")
        fact = self.facts.get(token_id)
        if fact is None or token_id in self.seen:
            return None
        try:
            observed = parse_time(frame["observed_at"])
            ingested = parse_time(frame["ingested_at"])
            recorded = parse_time(frame["recorded_at"])
            decision = parse_time(now)
            address = canonical_token_address("solana", token_id.split(":", 1)[1])
            pool = canonical_token_address("solana", str(frame["pair_address"]))
            base = canonical_token_address("solana", str(frame["provider_base_address"]))
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        price, liquidity, age = (_number(frame.get(key)) for key in
                                 ("price_usd", "liquidity_usd", "pool_age_seconds"))
        buys, sells, threshold = (_number(value) for value in
                                  (frame.get("buys_5m"), frame.get("sells_5m"), floor))
        if not (frame.get("chain") == frame.get("provider_chain_id") == "solana"
                and str(frame.get("provider") or "").split(":")[-1] == "dexscreener"
                and str(frame.get("provider_dex_id") or "").lower() == "pumpswap"
                and token_id == f"solana:{address}" and base == address and pool
                and self.started_at <= fact["recorded_at"] <= observed <= ingested <= recorded <= decision
                and (observed - fact["recorded_at"]).total_seconds() <= 300
                and (decision - observed).total_seconds() <= 30
                and price is not None and price > 0
                and liquidity is not None and threshold is not None and threshold > 0
                and liquidity >= threshold and age is not None and 0 <= age <= 300
                and buys is not None and buys >= 2 and sells is not None and sells >= 1):
            return None
        self.seen[token_id] = None
        while len(self.seen) > MAX_FACTS:
            self.seen.popitem(last=False)
        self.facts.pop(token_id, None)
        return {
            "episode_id": f"{VERSION}:{token_id}:{pool}",
            "decision_key": f"{VERSION}:{token_id}:{pool}:{iso(observed)}",
            "selected": {"token_id": token_id, "pair_address": pool},
            "observed_at": iso(observed), "recorded_at": iso(recorded),
            "decision_evidence": {
                "version": VERSION, "migration_fact_id": fact["fact_id"],
                "migration_recorded_at": iso(fact["recorded_at"]),
                "quote_observed_at": iso(observed), "quote_recorded_at": iso(recorded),
                "token_id": token_id, "pair_address": pool,
                "price_usd": price, "liquidity_usd": liquidity,
                "pool_age_seconds": age, "buys_5m": buys, "sells_5m": sells,
                "effective_pool_floor_usd": threshold,
            },
        }
