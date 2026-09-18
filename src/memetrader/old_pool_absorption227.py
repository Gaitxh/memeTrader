"""Three observed-frame old-pool sell-pressure absorption Paper experiment."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Mapping

from .activity_tempo193 import ARM as PARENT, _OWNED_FIELDS, _number
from .models import canonical_token_address, iso, parse_time


ARM = "activity227_old_pool_absorption_breakout_v1"
VERSION = "old-pool-absorption227/v1"
MAX_STATES = 1024


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Old-pool sell-pressure absorption breakout",
        feature_contract=VERSION,
        feature_hypothesis="old_pool_sell_pressure_absorbed_then_breakout",
        entry_match_mode="isolated_cohort_observer",
        source_arm_ids=[],
        requires_distinct_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        max_hold_minutes=5,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: after a pool is at least six hours old, observe actual "
            "same-pool sell pressure; a second 15-90s frame must hold price and "
            "liquidity, then a third independent 15-90s frame must break at least "
            "8% above the first price. The normal safety and next-observed Paper "
            "BUY remain mandatory. Maximum hold is five minutes. No extra API."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}),
        "direction": ARM,
        "max_concurrent_positions": 2,
        "single_token_lifetime_entry": True,
    }
    for key in ("entry_alias_of", "excess_return_vs_arm", "signal_origin_clock"):
        result.pop(key, None)
    return result


class Tracker:
    """Bounded restart-local state; never reconstructs older frames as decisions."""

    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.states: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self.fired: OrderedDict[tuple[str, str], None] = OrderedDict()

    def _remember(self, key: tuple[str, str], value: dict[str, Any]) -> None:
        self.states[key] = value
        self.states.move_to_end(key)
        if len(self.states) > MAX_STATES:
            self.states.popitem(last=False)

    def accept(self, frame: Mapping[str, Any], now: Any, *, floor: float) -> dict[str, Any] | None:
        try:
            chain = str(frame["chain"]).lower()
            token_id = str(frame["token_id"])
            address = canonical_token_address(chain, token_id.split(":", 1)[1])
            pool = canonical_token_address(chain, str(frame["pair_address"]))
            if any(not frame.get(key) for key in ("observed_at", "ingested_at", "recorded_at")):
                return None
            observed, ingested, recorded = (
                parse_time(frame[key]) for key in ("observed_at", "ingested_at", "recorded_at")
            )
            decision_at = parse_time(now)
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        provider = str(frame.get("provider") or "")
        price = _number(frame.get("price_usd"))
        liquidity = _number(frame.get("liquidity_usd"))
        volume = _number(frame.get("volume_5m_usd"))
        age = _number(frame.get("pool_age_seconds"))
        buys = _number(frame.get("buys_5m"))
        sells = _number(frame.get("sells_5m"))
        threshold = _number(floor)
        if not (chain in {"solana", "bsc", "robinhood"}
                and token_id.startswith(chain + ":") and address and pool
                and provider.startswith(("dexscreener", "geckoterminal"))
                and self.started_at <= observed <= ingested <= recorded <= decision_at
                and (decision_at - observed).total_seconds() <= 30
                and price is not None and price > 0
                and liquidity is not None and threshold is not None and threshold > 0
                and liquidity >= max(2000.0, threshold)
                and volume is not None and volume >= 0
                and age is not None and age >= 6 * 3600
                and buys is not None and buys >= 0
                and sells is not None and sells >= 1):
            return None
        key = (token_id, pool)
        if key in self.fired:
            return None
        first_candidate = sells >= max(3, buys) and buys + sells >= 8 and volume >= 500
        current = self.states.get(key)
        if current is not None and (
            current["provider"] != provider or observed <= current["last_at"]
        ):
            return None
        if current is not None:
            since = (observed - current["last_at"]).total_seconds()
            if 15 <= since <= 90 and price >= current["first_price"] and liquidity >= current["first_liquidity"]:
                if current["stage"] == 1:
                    self._remember(key, {**current, "stage": 2, "second_at": observed,
                                         "last_at": observed})
                    return None
                if price >= current["first_price"] * 1.08:
                    self.states.pop(key, None)
                    self.fired[key] = None
                    if len(self.fired) > MAX_STATES:
                        self.fired.popitem(last=False)
                    return {
                        "episode_id": f"{VERSION}:{token_id}:{pool}",
                        "decision_key": f"{VERSION}:{token_id}:{pool}:{iso(observed)}",
                        "selected": {"token_id": token_id, "pair_address": pool},
                        "observed_at": iso(observed), "recorded_at": iso(recorded),
                        "decision_evidence": {
                            "version": VERSION, "chain": chain, "provider": provider,
                            "token_id": token_id, "pair_address": pool,
                            "first_observed_at": iso(current["first_at"]),
                            "second_observed_at": iso(current["second_at"]),
                            "breakout_observed_at": iso(observed),
                            "first_price_usd": current["first_price"],
                            "breakout_price_usd": price,
                            "first_liquidity_usd": current["first_liquidity"],
                            "breakout_liquidity_usd": liquidity,
                            "first_buys_5m": current["first_buys"],
                            "first_sells_5m": current["first_sells"],
                            "pool_age_seconds": age,
                        },
                    }
            self.states.pop(key, None)
        if first_candidate:
            self._remember(key, {
                "stage": 1, "provider": provider, "first_at": observed,
                "last_at": observed, "first_price": price,
                "first_liquidity": liquidity, "first_buys": buys,
                "first_sells": sells,
            })
        return None
