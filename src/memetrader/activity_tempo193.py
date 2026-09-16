"""One-frame old-pool activity acceleration trial for Paper cohorts."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

from .models import canonical_token_address, iso, parse_time


VERSION = "activity-tempo193/v1"
ARM = "activity193_old_pool_tempo_v1"
PARENT = "alpha149_wide_decorr_young_v1"
MAX_SEEN = 1024
_OWNED_FIELDS = {
    "account_lifecycle", "assessment_evidence", "assessment_note",
    "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
    "forward_started_at", "original_forward_started_at", "retirement_representative",
    "runtime_addition_id", "stage", "_execution",
}


def interval_fields(pair: Mapping[str, Any]) -> dict[str, Any]:
    """Read the same as-of intervals from Dex and normalized Gecko payloads."""
    raw = pair.get("raw") if isinstance(pair.get("raw"), dict) else {}
    attributes = ((raw.get("pool") or {}).get("attributes") or {})
    txns = pair.get("txns") or attributes.get("transactions") or {}
    changes = pair.get("priceChange") or attributes.get("price_change_percentage") or {}
    volume = pair.get("volume") or attributes.get("volume_usd") or {}
    hour = txns.get("h1") or {}
    return {
        "volume_1h_usd": volume.get("h1"),
        "buys_1h": hour.get("buys"),
        "sells_1h": hour.get("sells"),
        "price_change_5m_pct": changes.get("m5"),
    }


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in parent.items()
              if key not in _OWNED_FIELDS}
    result.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Old-pool activity tempo, 30m",
        feature_contract=VERSION,
        feature_hypothesis="old_pool_five_minute_activity_acceleration",
        entry_match_mode="isolated_cohort_observer",
        source_arm_ids=[],
        requires_distinct_trajectory_frame=False,
        requires_distinct_wide_frame=False,
        notional_usd=20.0, max_hold_minutes=30,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        description=(
            f"{VERSION}: a pool at least one hour old shows >=3x five-minute trade "
            "tempo versus the preceding 55 minutes, >=15 recent trades, >=55% buys "
            "with a real sell, >=1000U five-minute volume, nonnegative five-minute "
            "price change and >=2000U same-pool depth. One as-of frame; normal "
            "safety and next-observed Paper fill remain mandatory. No extra API."
        ),
    )
    result["entry_filter"] = {
        **(result.get("entry_filter") or {}),
        "direction": ARM,
        "max_concurrent_positions": 6,
        "single_token_lifetime_entry": True,
    }
    result.pop("entry_alias_of", None)
    result.pop("excess_return_vs_arm", None)
    result.pop("signal_origin_clock", None)
    return result


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


class Tracker:
    """Bounded restart-local signal dedupe, not a reconstructed market history."""

    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.seen: OrderedDict[tuple[str, str], None] = OrderedDict()

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
        price_change = _number(frame.get("price_change_5m_pct"))
        buys5 = _number(frame.get("buys_5m"))
        sells5 = _number(frame.get("sells_5m"))
        buys1 = _number(frame.get("buys_1h"))
        sells1 = _number(frame.get("sells_1h"))
        threshold = _number(floor)
        if not (chain in {"solana", "bsc", "robinhood"}
                and token_id.startswith(chain + ":") and address and pool
                and provider.startswith(("dexscreener", "geckoterminal"))
                and self.started_at <= observed <= ingested <= recorded <= decision_at
                and (decision_at - observed).total_seconds() <= 30
                and price is not None and price > 0
                and liquidity is not None and threshold is not None and threshold > 0
                and liquidity >= max(2000.0, threshold)
                and volume is not None and volume >= 1000
                and age is not None and age >= 3600
                and price_change is not None and price_change >= 0
                and all(value is not None and value >= 0
                        for value in (buys5, sells5, buys1, sells1))):
            return None
        recent = buys5 + sells5
        prior = buys1 + sells1 - recent
        if not (recent >= 15 and sells5 >= 1 and buys5 / recent >= .55
                and prior >= 11 and recent * 11 / prior >= 3):
            return None
        identity = (token_id, pool)
        if identity in self.seen:
            return None
        self.seen[identity] = None
        if len(self.seen) > MAX_SEEN:
            self.seen.popitem(last=False)
        evidence = {
            "version": VERSION, "provider": provider, "chain": chain,
            "token_id": token_id, "pair_address": pool,
            "pool_age_seconds": age, "price_usd": price,
            "liquidity_usd": liquidity, "volume_5m_usd": volume,
            "price_change_5m_pct": price_change,
            "buys_5m": buys5, "sells_5m": sells5,
            "buys_1h": buys1, "sells_1h": sells1,
            "prior_55m_trades": prior, "tempo_ratio": recent * 11 / prior,
            "effective_pool_floor_usd": threshold,
        }
        return {
            "episode_id": f"{VERSION}:{token_id}:{pool}",
            "decision_key": f"{VERSION}:{token_id}:{pool}:{iso(observed)}",
            "selected": {"token_id": token_id, "pair_address": pool},
            "observed_at": iso(observed), "recorded_at": iso(recorded),
            "decision_evidence": evidence,
        }
