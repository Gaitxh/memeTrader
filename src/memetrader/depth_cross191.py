"""Small Paper trial for a pool's first observed move into tradable depth."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import canonical_token_address, iso, parse_time


VERSION = "depth-cross191/v1"
ARM = "depth191_first_tradable_v1"
PARENT = "alpha149_wide_decorr_young_v1"
MAX_POOLS = 256
MAX_CROSS_SECONDS = 300
MAX_POOL_AGE_SECONDS = 600

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
        name="First tradable original-pool depth",
        feature_contract=VERSION,
        feature_hypothesis="first_tradable_depth",
        entry_match_mode="isolated_cohort_observer",
        source_arm_ids=[],
        requires_distinct_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        notional_usd=20.0,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: one fresh same-pool numeric below-floor frame followed within "
            "300s by the first >=2x-floor frame, pool age <=600s, positive price "
            "and buy share >=50% with at least one sell. The independent tracker "
            "requires distinct causal frames; ordinary safety and next-frame Paper "
            "execution remain mandatory. Existing shared data, no extra request."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}),
        "direction": ARM,
        "max_concurrent_positions": 8,
        "single_token_lifetime_entry": True,
    }
    result.pop("entry_alias_of", None)
    result.pop("paired_opportunity_group", None)
    result.pop("excess_return_vs_arm", None)
    result.pop("signal_origin_clock", None)
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
    """Bounded, restart-local memory; a restart cannot invent an earlier low frame."""

    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.pools: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    def accept(self, frame: Mapping[str, Any], now: Any, *, floor: float) -> dict[str, Any] | None:
        try:
            chain = str(frame["chain"]).lower()
            token_id = str(frame["token_id"])
            pool = canonical_token_address(chain, str(frame["pair_address"]))
            address = canonical_token_address(chain, token_id.split(":", 1)[1])
            if any(not frame.get(key) for key in ("observed_at", "ingested_at", "recorded_at")):
                return None
            observed, ingested, recorded = (
                parse_time(frame[key]) for key in ("observed_at", "ingested_at", "recorded_at")
            )
            decision_at = parse_time(now)
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        price = _number(frame.get("price_usd"))
        liquidity = _number(frame.get("liquidity_usd"))
        age = _number(frame.get("pool_age_seconds"))
        threshold = _number(floor)
        if not (chain in {"solana", "bsc", "robinhood"}
                and token_id.startswith(chain + ":") and address and pool
                and str(frame.get("provider") or "").startswith(("dexscreener", "geckoterminal"))
                and self.started_at <= observed <= ingested <= recorded <= decision_at
                and (decision_at - observed).total_seconds() <= 45
                and price is not None and price > 0
                and liquidity is not None and liquidity >= 0
                and age is not None and 0 <= age <= MAX_POOL_AGE_SECONDS
                and threshold is not None and threshold > 0):
            return None
        identity = (token_id, pool)
        for key, state in list(self.pools.items()):
            if (decision_at - state["last_at"]).total_seconds() > MAX_CROSS_SECONDS:
                del self.pools[key]
        state = self.pools.get(identity)
        if state and observed <= state["last_at"]:
            return None
        if liquidity < threshold:
            if state is None:
                if len(self.pools) >= MAX_POOLS:
                    self.pools.popitem(last=False)
                self.pools[identity] = {
                    "low_at": observed, "last_at": observed,
                    "low_liquidity_usd": liquidity,
                }
            else:
                state["last_at"] = observed
                self.pools.move_to_end(identity)
            return None
        if state is None:
            return None
        crossing_depth = max(2000.0, 2 * threshold)
        if liquidity < crossing_depth:
            state["last_at"] = observed
            self.pools.move_to_end(identity)
            return None
        self.pools.pop(identity)
        elapsed = (observed - state["low_at"]).total_seconds()
        buys = _number(frame.get("buys_5m"))
        sells = _number(frame.get("sells_5m"))
        if not (0 < elapsed <= MAX_CROSS_SECONDS
                and liquidity >= crossing_depth
                and buys is not None and sells is not None
                and buys >= 2 and sells >= 1 and buys >= sells):
            return None
        evidence = {
            "version": VERSION, "mode": ARM,
            "low_observed_at": iso(state["low_at"]),
            "low_liquidity_usd": state["low_liquidity_usd"],
            "cross_observed_at": iso(observed),
            "cross_liquidity_usd": liquidity,
            "cross_price_usd": price,
            "pool_age_seconds": age,
            "elapsed_seconds": elapsed,
            "buys_5m": int(buys), "sells_5m": int(sells),
            "effective_pool_floor_usd": threshold,
            "provider": str(frame["provider"]),
            "chain": chain, "token_id": token_id, "pair_address": pool,
        }
        return {
            "episode_id": f"{VERSION}:{token_id}:{pool}",
            "decision_key": f"{VERSION}:{token_id}:{pool}:{iso(observed)}",
            "selected": {"token_id": token_id, "pair_address": pool},
            "observed_at": iso(observed), "recorded_at": iso(recorded),
            "decision_evidence": evidence,
        }
