"""Bounded, I/O-free launch watch; reserve growth is not gross trading flow."""
from datetime import datetime, timedelta
from copy import deepcopy
import math
from collections.abc import Mapping

from solders.pubkey import Pubkey

from .collectors import PUMP_PROGRAM_ID, SOLANA_SYSTEM_PROGRAM_ID, SOLANA_WRAPPED_SOL_MINT


def _time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except ValueError:
        return None


def bonding_curve_identity(token: Mapping) -> dict:
    """Derive the official mint-bound PDA; reject a supplied different address."""
    token_id = str(token.get("token_id") or "")
    mint = str(token.get("base_mint") or token.get("address") or "")
    if token.get("chain", "solana") != "solana" or token_id != "solana:" + mint:
        raise ValueError("pregrad_token_identity_mismatch")
    curve = str(Pubkey.find_program_address(
        [b"bonding-curve", bytes(Pubkey.from_string(mint))],
        Pubkey.from_string(PUMP_PROGRAM_ID),
    )[0])
    supplied = token.get("curve_address") or token.get("bonding_curve_key")
    if supplied and str(supplied) != curve:
        raise ValueError("pregrad_curve_pda_mismatch")
    return dict(token_id=token_id, chain="solana", base_mint=mint, curve_address=curve)


class PregradWatch:
    """Three launch seeds, five-minute TTL anchored to first local launch receipt.

    All methods require explicit as-of time. Returned records never authorize BUY.
    Migration handoff is an instruction for the caller, not an I/O side effect.
    """
    MAX_TOKENS = 3
    TTL_SECONDS = 300

    def __init__(self):
        self._items = {}

    def _expire(self, now):
        cutoff = _time(now)
        if cutoff is None:
            raise ValueError("pregrad_now_requires_timezone")
        self._items = {k: v for k, v in self._items.items()
                       if _time(v["expires_at"]) > cutoff}
        return cutoff

    @staticmethod
    def _priority(item):
        growth = item.get("net_reserve_growth_quote_per_second")
        return (item["stage"] == "PREGRAD", growth is not None and growth > 0,
                growth if growth is not None else 0, item["initial_quote_amount"] or 0,
                item["launch_observed_at"], item["token_id"])

    def observe_launch(self, launch: Mapping, *, now):
        cutoff = self._expire(now)
        observed, ingested, recorded = (_time(launch.get(k)) for k in
                                       ("source_observed_at", "ingested_at", "recorded_at"))
        if not observed or not ingested or not recorded or not observed <= ingested <= recorded <= cutoff:
            return None
        token_id = str(launch.get("token_id") or "")
        if launch.get("launch_event_type") == "migration":
            item = self._items.get(token_id)
            if (item is None or item["stage"] == "MIGRATED"
                    or observed < _time(item["launch_observed_at"])
                    or launch.get("address") != item["base_mint"]):
                return None
            item.update(stage="MIGRATED", migration_fact_id=launch.get("id"),
                        migration_observed_at=observed.isoformat(),
                        net_reserve_growth_quote_per_second=None)
            return {**deepcopy(item), "requeue_hydration": True}
        if launch.get("launch_event_type") != "create" or (cutoff - observed).total_seconds() >= self.TTL_SECONDS:
            return None
        try:
            identity = bonding_curve_identity(launch)
        except ValueError:
            return None
        if token_id in self._items:
            return deepcopy(self._items[token_id])
        seed = launch.get("initial_quote_amount")
        try:
            seed = float(seed) if seed is not None else None
        except (ValueError, TypeError):
            seed = None
        if seed is not None and (not math.isfinite(seed) or seed < 0):
            seed = None
        item = dict(**identity, launch_fact_id=launch.get("id"), stage="PREGRAD",
                    launch_observed_at=observed.isoformat(),
                    expires_at=(observed + timedelta(seconds=self.TTL_SECONDS)).isoformat(),
                    initial_quote_amount=seed, priority_basis="launch_seed_size",
                    net_reserve_growth_quote_per_second=None, reserve_frames=[],
                    decision_eligible=False, affects="watch_priority_only")
        ranked = sorted([*self._items.values(), item], key=self._priority, reverse=True)
        self._items = {v["token_id"]: v for v in ranked[:self.MAX_TOKENS]}
        return deepcopy(item) if token_id in self._items else None

    def targets(self, *, now):
        return [{k: item[k] for k in ("token_id", "chain", "base_mint", "curve_address")}
                for item in self.ranked(now=now) if item["stage"] == "PREGRAD"]

    def ranked(self, *, now):
        self._expire(now)
        return [deepcopy(v) for v in sorted(self._items.values(), key=self._priority, reverse=True)]

    def apply_observation(self, frame: Mapping, *, now):
        cutoff = self._expire(now)
        item = self._items.get(frame.get("token_id"))
        if item is None or item["stage"] != "PREGRAD":
            return None
        observed, recorded = _time(frame.get("observed_at")), _time(frame.get("recorded_at"))
        slot = frame.get("slot")
        raw = frame.get("real_quote_reserves_raw")
        valid = (frame.get("status") == "verified" and frame.get("identity_verified") is True
                 and frame.get("curve_address") == item["curve_address"]
                 and frame.get("base_mint") == item["base_mint"]
                 and observed and recorded and _time(item["launch_observed_at"]) <= observed <= recorded <= cutoff
                 and isinstance(slot, int) and slot > 0
                 and isinstance(raw, int) and raw >= 0
                 and isinstance(frame.get("curve_complete"), bool))
        if not valid:
            return None
        previous = item["reserve_frames"][-1] if item["reserve_frames"] else None
        if previous and (slot <= previous["slot"] or observed <= _time(previous["observed_at"])):
            return None
        current = {k: frame.get(k) for k in ("slot", "observed_at", "recorded_at", "data_hash",
                   "real_quote_reserves_raw", "real_token_reserves_raw", "quote_mint", "curve_complete")}
        item["reserve_frames"] = ([previous] if previous else []) + [current]
        item["net_reserve_growth_quote_per_second"] = None
        item["priority_basis"] = "curve_reserve_seed"
        if frame["curve_complete"]:
            item["stage"] = "CURVE_COMPLETE"
        elif previous and current["quote_mint"] == previous["quote_mint"] and current["quote_mint"] in {
                SOLANA_SYSTEM_PROGRAM_ID, SOLANA_WRAPPED_SOL_MINT}:
            seconds = (observed - _time(previous["observed_at"])).total_seconds()
            item["net_reserve_growth_quote_per_second"] = (raw - previous["real_quote_reserves_raw"]) / 1e9 / seconds
            item["priority_basis"] = "observed_net_reserve_growth_not_gross_flow"
        return deepcopy(item)
