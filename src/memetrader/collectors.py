from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import math
import re
import socket
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from email.utils import parsedate_to_datetime
from statistics import median
from typing import Any, AsyncIterator, Callable, Iterable, Mapping

import httpx
import websockets

from .models import (
    Observation, TokenCandidate, TokenSnapshot, canonical_token_address, iso,
    parse_time, utcnow,
)


RSS_CACHE_KEY_PREFIX = "rss_http_cache:v1:"
RSS_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RSS_XML_MEDIA_TYPES = {
    "application/atom+xml",
    "application/rdf+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
}
RSS_GENERIC_MEDIA_TYPES = {"", "application/octet-stream", "binary/octet-stream", "text/plain"}
METADATA_HOSTS = {
    "instance-data.ec2.internal",
    "metadata",
    "metadata.aws.internal",
    "metadata.google.internal",
    "metadata.google",
}

PUMPSWAP_POOL_DISCRIMINATOR = bytes((241, 154, 109, 4, 17, 177, 109, 188))
PUMPSWAP_POOL_DECODER_V2 = "pump-amm-pool/v2-idl-6b5c7e-sdk-1.19.0"
PUMPSWAP_POOL_IDL_DEFINED_SIZE = 261
PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD = 300
PUMPSWAP_POOL_OBSERVED_ALLOCATION = 301
PUMPSWAP_GLOBAL_CONFIG_DISCRIMINATOR = bytes((149, 8, 156, 202, 160, 252, 176, 217))
PUMPSWAP_FEE_CONFIG_DISCRIMINATOR = bytes((143, 52, 146, 187, 219, 123, 76, 155))
PUMPSWAP_GLOBAL_CONFIG_DECODER_V1 = "pump-amm-global-config/v1-idl-6b5c7e-sdk-1.19.0"
PUMPSWAP_FEE_CONFIG_DECODER_V1 = "pump-fee-config/v1-idl-6b5c7e-sdk-1.19.0"
PUMPSWAP_SELL_BASE_INPUT_V1 = "pump-amm-sell-base-input/v1-sdk-1.19.0"
PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_AMM_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PUMP_FEE_PROGRAM_ID = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
PUMP_GLOBAL_PDA = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
PUMP_FEE_CONFIG_PDA = "8Wf5TiAheLUqBrKXeYg2JtAFFMWtKdG2BSFgqUcPVwTt"
PUMP_BONDING_CURVE_DISCRIMINATOR = bytes((23, 183, 248, 55, 96, 216, 172, 96))
PUMP_GLOBAL_DISCRIMINATOR = bytes((167, 232, 232, 177, 200, 108, 114, 127))
PUMP_BONDING_CURVE_DECODER_V1 = "pump-bonding-curve/v1-idl-sdk-1.36.0"
PUMP_GLOBAL_DECODER_V1 = "pump-global/v1-idl-sdk-1.36.0"
PUMP_BONDING_CURVE_SELL_V1 = "pump-bonding-curve-sell/v1-sdk-1.36.0"
SOLANA_SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
SOLANA_WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PUMPSWAP_GLOBAL_CONFIG_PDA = "ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw"
PUMPSWAP_FEE_CONFIG_PDA = "5PHirr8joyTMp9JMm6nW7hNDVyEYdkzDqazxPD7RaTjx"
PUMPSWAP_DISABLE_SELL_MASK = 1 << 4
SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def token_quantity_to_raw_floor(quantity_tokens: Any, mint_decimals: int) -> int:
    """Convert a verified token quantity to mint raw units without inventing dust."""
    if isinstance(mint_decimals, bool) or not isinstance(mint_decimals, int):
        raise ValueError("mint_decimals_unknown")
    if not 0 <= mint_decimals <= 255:
        raise ValueError("mint_decimals_invalid")
    quantity = Decimal(str(quantity_tokens))
    if not quantity.is_finite() or quantity < 0:
        raise ValueError("token_quantity_invalid")
    return int(
        (quantity * (Decimal(10) ** mint_decimals)).to_integral_value(
            rounding=ROUND_DOWN
        )
    )


class PumpSwapVaultFlowTracker:
    """Bounded, observer-only reserve-flow summaries keyed by unique pool."""

    def __init__(
        self, *, window_seconds: float = 60.0, max_points: int = 2048,
        summary_seconds: float = 30.0,
    ):
        self.window_seconds = max(1.0, float(window_seconds))
        self.max_points = max(8, int(max_points))
        self.summary_seconds = max(1.0, float(summary_seconds))
        self._latest: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._points: dict[int, deque[dict[str, Any]]] = {}
        self._last_pair_key: dict[int, tuple[Any, ...]] = {}
        self._last_state: dict[int, str] = {}
        self._last_emitted_at: dict[int, datetime] = {}

    def retain(self, pool_target_ids: Iterable[int]) -> None:
        keep = {int(item) for item in pool_target_ids}
        for mapping in (
            self._latest, self._points, self._last_pair_key,
            self._last_state, self._last_emitted_at,
        ):
            for key in set(mapping) - keep:
                mapping.pop(key, None)

    @staticmethod
    def _ratio(after: int, before: int) -> float | None:
        return after / before - 1.0 if before > 0 else None

    @staticmethod
    def _mad_ratio(values: list[float]) -> float | None:
        if not values:
            return None
        center = float(median(values))
        if center <= 0.0:
            return None
        return float(median(abs(item - center) for item in values)) / center

    def _frame(
        self, pool_id: int, *, state: str, observed_at: datetime,
        base_amount: int | None, quote_amount: int | None,
        effective_quote: int | None, slot_min: int, slot_max: int,
        features: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        previous = self._last_state.get(pool_id, "")
        prior_emit = self._last_emitted_at.get(pool_id)
        state_changed = state != previous
        periodic_due = (
            prior_emit is None
            or (observed_at - prior_emit).total_seconds() >= self.summary_seconds
        )
        self._last_state[pool_id] = state
        if not state_changed and not periodic_due:
            return None
        self._last_emitted_at[pool_id] = observed_at
        points = self._points.get(pool_id) or ()
        started_at = points[0]["observed_at"] if points else observed_at
        return {
            "observer_version": str(features.get("observer_version") or ""),
            "pool_target_id": pool_id,
            "frame_kind": "state_change" if state_changed else "periodic_30s",
            "observer_state": state,
            "previous_state": previous,
            "window_started_at": iso(started_at),
            "observed_at": iso(observed_at),
            "slot_min": int(slot_min),
            "slot_max": int(slot_max),
            "base_amount_raw": str(base_amount) if base_amount is not None else None,
            "quote_amount_raw": str(quote_amount) if quote_amount is not None else None,
            "effective_quote_reserve_raw": (
                str(effective_quote) if effective_quote is not None else None
            ),
            "features": dict(features),
            "decision_eligible": False,
            "affects": "none",
        }

    def push(self, update: Mapping[str, Any]) -> dict[str, Any] | None:
        pool_id = int(update.get("pool_target_id") or 0)
        kind = str(update.get("account_kind") or "")
        slot = int(update.get("slot") or 0)
        data_hash = str(update.get("data_hash") or "")
        observed_at = parse_time(update.get("observed_at") or utcnow())
        decoded = dict(update.get("decoded") or {})
        observer_version = str(update.get("observer_version") or "")
        if pool_id <= 0 or slot <= 0 or not data_hash:
            return None
        if str(decoded.get("status") or "") != "verified":
            if kind == "pool":
                self._latest[pool_id].pop("pool", None)
            return self._frame(
                pool_id, state="IDENTITY_INVALID", observed_at=observed_at,
                base_amount=None, quote_amount=None, effective_quote=None,
                slot_min=slot, slot_max=slot,
                features={
                    "observer_version": observer_version,
                    "missing_reason": str(
                        decoded.get("reason") or decoded.get("status") or "unverified"
                    ),
                    "sample_count": len(self._points.get(pool_id) or ()),
                },
            )
        latest = self._latest[pool_id]
        if kind == "pool":
            if (
                bool(decoded.get("needs_sdk_extend"))
                or int(decoded.get("account_data_length") or 0)
                < PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD
            ):
                return self._frame(
                    pool_id, state="IDENTITY_INVALID", observed_at=observed_at,
                    base_amount=None, quote_amount=None, effective_quote=None,
                    slot_min=slot, slot_max=slot,
                    features={
                        "observer_version": observer_version,
                        "missing_reason": "pumpswap_current_fields_unavailable",
                        "sample_count": len(self._points.get(pool_id) or ()),
                    },
                )
            prior_pool = latest.get("pool")
            if prior_pool is not None and slot < int(prior_pool["slot"]):
                return None
            if (
                prior_pool is not None
                and slot == int(prior_pool["slot"])
                and data_hash == str(prior_pool["data_hash"])
            ):
                return None
            latest["pool"] = {
                "slot": slot,
                "data_hash": data_hash,
                "observed_at": observed_at,
                "virtual_quote_reserves_raw": int(
                    decoded["virtual_quote_reserves_raw"]
                ),
            }
        elif kind not in {"base_vault", "quote_vault"}:
            return None
        else:
            prior_same = latest.get(kind)
            if prior_same is not None and slot < int(prior_same["slot"]):
                return None
            if (
                prior_same is not None and int(prior_same["slot"]) == slot
                and str(prior_same["data_hash"]) == data_hash
            ):
                return None
            latest[kind] = {
                "slot": slot, "data_hash": data_hash, "observed_at": observed_at,
                "amount_raw": int(decoded.get("amount_raw") or 0),
            }
        base = latest.get("base_vault")
        quote = latest.get("quote_vault")
        if base is None or quote is None:
            if kind == "pool":
                return None
            amount = int(decoded.get("amount_raw") or 0)
            return self._frame(
                pool_id, state="PARTIAL_PAIR", observed_at=observed_at,
                base_amount=amount if kind == "base_vault" else None,
                quote_amount=amount if kind == "quote_vault" else None,
                effective_quote=None, slot_min=slot, slot_max=slot,
                features={
                    "observer_version": observer_version,
                    "missing_reason": "counterpart_not_observed",
                    "sample_count": len(self._points.get(pool_id) or ()),
                },
            )
        slot_min = min(int(base["slot"]), int(quote["slot"]))
        slot_max = max(int(base["slot"]), int(quote["slot"]))
        coherent = slot_min == slot_max
        if not coherent:
            return None
        pair_key = (
            int(base["slot"]), str(base["data_hash"]),
            int(quote["slot"]), str(quote["data_hash"]),
        )
        prior_pair_key = self._last_pair_key.get(pool_id)
        base_amount = int(base["amount_raw"])
        quote_amount = int(quote["amount_raw"])
        pool_fact = latest.get("pool")
        if pool_fact is not None:
            virtual_quote = int(pool_fact["virtual_quote_reserves_raw"])
            virtual_slot = int(pool_fact["slot"])
            virtual_known = True
        elif update.get("virtual_quote_reserves_raw") is not None:
            virtual_quote = int(update["virtual_quote_reserves_raw"])
            virtual_slot = int(update.get("resolved_slot") or 0)
            virtual_known = True
        else:
            virtual_quote = 0
            virtual_slot = 0
            virtual_known = False
        effective_known = virtual_known and virtual_slot == slot_max
        pair_at = max(
            base["observed_at"], quote["observed_at"],
            pool_fact["observed_at"] if effective_known else base["observed_at"],
        )
        effective_quote = (
            quote_amount + virtual_quote if effective_known else quote_amount
        )
        points = self._points.setdefault(pool_id, deque(maxlen=self.max_points))
        upgrades_latest = bool(
            prior_pair_key == pair_key
            and effective_known
            and points
            and not bool(points[-1].get("effective_quote_known"))
            and int(points[-1]["slot_min"]) == slot_min
            and int(points[-1]["slot_max"]) == slot_max
        )
        if prior_pair_key == pair_key and not upgrades_latest:
            return None
        if prior_pair_key is not None and prior_pair_key != pair_key:
            if slot_max <= int(prior_pair_key[2]):
                return None
            if (
                str(base["data_hash"]) == str(prior_pair_key[1])
                or str(quote["data_hash"]) == str(prior_pair_key[3])
            ):
                return None
        if not upgrades_latest:
            self._last_pair_key[pool_id] = pair_key
        if upgrades_latest:
            previous_point = points[-2] if len(points) >= 2 else None
        else:
            previous_point = points[-1] if points else None
        direction = "UNKNOWN_INCOHERENT"
        normalized_gross = 0.0
        if previous_point is not None:
            base_delta = base_amount - int(previous_point["base_amount_raw"])
            quote_delta = quote_amount - int(previous_point["quote_amount_raw"])
            if base_delta > 0 and quote_delta < 0:
                direction = "SELL_LIKE_NET"
            elif base_delta < 0 and quote_delta > 0:
                direction = "BUY_LIKE_NET"
            elif base_delta > 0 and quote_delta > 0:
                direction = "LP_ADD_LIKE"
            elif base_delta < 0 and quote_delta < 0:
                direction = "LP_REMOVE_LIKE"
            normalized_gross = (
                abs(base_delta) / max(1, int(previous_point["base_amount_raw"]))
                + abs(quote_delta) / max(1, int(previous_point["effective_quote_raw"]))
            )
        point = {
            "observed_at": pair_at,
            "slot_min": slot_min,
            "slot_max": slot_max,
            "base_amount_raw": base_amount,
            "quote_amount_raw": quote_amount,
            "effective_quote_raw": effective_quote,
            "effective_quote_known": effective_known,
            "direction": direction,
            "normalized_gross": normalized_gross,
        }
        if upgrades_latest:
            points[-1] = point
        else:
            points.append(point)
        cutoff = pair_at - timedelta(seconds=self.window_seconds)
        while points and points[0]["observed_at"] < cutoff:
            points.popleft()
        point_list = list(points)
        trade_points = [
            item for item in point_list
            if item["direction"] in {"BUY_LIKE_NET", "SELL_LIKE_NET"}
        ]
        intervals = [
            max(0.0, (after["observed_at"] - before["observed_at"]).total_seconds())
            for before, after in zip(trade_points, trade_points[1:])
        ]
        sizes = [float(item["normalized_gross"]) for item in trade_points]
        directions = [
            str(item["direction"]) for item in point_list
            if item["direction"] in {"BUY_LIKE_NET", "SELL_LIKE_NET"}
        ]
        alternation = (
            sum(left != right for left, right in zip(directions, directions[1:]))
            / (len(directions) - 1)
            if len(directions) >= 2 else None
        )
        direction_entropy = None
        if directions:
            buy_share = directions.count("BUY_LIKE_NET") / len(directions)
            direction_entropy = -sum(
                share * math.log2(share)
                for share in (buy_share, 1.0 - buy_share) if share > 0.0
            )
        implied_prices = [
            float(item["effective_quote_raw"]) / int(item["base_amount_raw"])
            for item in point_list
            if bool(item.get("effective_quote_known"))
            and int(item["base_amount_raw"]) > 0
        ]
        price_variation = (
            max(implied_prices) / min(implied_prices) - 1.0
            if implied_prices and min(implied_prices) > 0.0 else None
        )
        windows: dict[str, Any] = {}
        for horizon in (1, 3, 10, 30):
            boundary = pair_at - timedelta(seconds=horizon)
            before = [item for item in point_list if item["observed_at"] <= boundary]
            baseline = before[-1] if before else point_list[0]
            covered = max(
                0.0, (pair_at - baseline["observed_at"]).total_seconds()
            )
            base_change = self._ratio(base_amount, int(baseline["base_amount_raw"]))
            baseline_effective_known = bool(baseline.get("effective_quote_known"))
            quote_change = (
                self._ratio(effective_quote, int(baseline["effective_quote_raw"]))
                if effective_known and baseline_effective_known else None
            )
            depth_ratio = (
                effective_quote / max(1, int(baseline["effective_quote_raw"]))
                if effective_known and baseline_effective_known else None
            )
            raw_quote_change = self._ratio(
                quote_amount, int(baseline["quote_amount_raw"])
            )
            windows[str(horizon)] = {
                "coverage_seconds": covered,
                "base_change_ratio": base_change,
                "effective_quote_change_ratio": quote_change,
                "base_slope_per_second": base_change / covered if covered and base_change is not None else None,
                "effective_quote_slope_per_second": quote_change / covered if covered and quote_change is not None else None,
                "effective_depth_ratio": depth_ratio,
                "raw_quote_change_ratio": raw_quote_change,
                "raw_quote_slope_per_second": raw_quote_change / covered if covered and raw_quote_change is not None else None,
            }
        interval_mad_ratio = self._mad_ratio(intervals)
        size_mad_ratio = self._mad_ratio(sizes)
        gross_turnover = sum(sizes)
        span_seconds = max(
            0.0, (pair_at - point_list[0]["observed_at"]).total_seconds()
        )
        regularity = (
            len(trade_points) >= 6 and span_seconds >= 3.0
            and interval_mad_ratio is not None and interval_mad_ratio <= 0.25
            and size_mad_ratio is not None and size_mad_ratio <= 0.25
        )
        ten = windows["10"]
        unwind = (
            ten["coverage_seconds"] >= 3.0
            and direction in {"SELL_LIKE_NET", "LP_REMOVE_LIKE"}
            and (
                (ten["effective_quote_change_ratio"] is not None
                 and ten["effective_quote_change_ratio"] <= -0.15)
                or (
                    ten["effective_depth_ratio"] is not None
                    and ten["effective_depth_ratio"] <= 0.70
                )
            )
        )
        synthetic_support = (
            regularity and alternation is not None and alternation >= 0.60
            and price_variation is not None and price_variation <= 0.03
            and gross_turnover >= 0.02
        )
        if virtual_known and effective_quote <= 0:
            state = "EFFECTIVE_RESERVE_NONPOSITIVE"
        elif len(point_list) < 3 or span_seconds < 3.0:
            state = "INSUFFICIENT_EVENTS"
        elif unwind:
            state = "UNWIND_HAZARD_PRECURSOR_RECOVERY_UNKNOWN"
        elif synthetic_support:
            state = "SYNTHETIC_SUPPORT_PATTERN"
        elif regularity:
            state = "REGULARITY_PATTERN"
        else:
            state = "OBSERVED_NORMAL"
        features = {
            "observer_version": observer_version,
            "pair_key": ":".join(str(item) for item in pair_key),
            "source_hashes": {
                "base_vault": str(base["data_hash"]),
                "quote_vault": str(quote["data_hash"]),
                "pool": str(pool_fact["data_hash"]) if pool_fact is not None else None,
            },
            "flow_granularity": "confirmed_slot_net_not_transaction_identity",
            "sample_count": len(point_list),
            "span_seconds": span_seconds,
            "latest_direction": direction,
            "median_interval_seconds": float(median(intervals)) if intervals else None,
            "interval_mad_ratio": interval_mad_ratio,
            "size_mad_ratio": size_mad_ratio,
            "alternation_rate": alternation,
            "direction_entropy": direction_entropy,
            "gross_turnover_ratio": gross_turnover,
            "reserve_price_variation": price_variation,
            "virtual_quote_reserve_known": virtual_known,
            "effective_quote_reserve_known": effective_known,
            "virtual_quote_reserve_raw": virtual_quote if virtual_known else None,
            "virtual_quote_reserve_slot": virtual_slot if virtual_known else None,
            "virtual_component_temporal_status": (
                "SAME_SLOT" if effective_known
                else "LAST_CONFIRMED_ASOF" if virtual_known
                else "UNKNOWN"
            ),
            "regularity_pattern": regularity,
            "synthetic_support_pattern": synthetic_support,
            "unwind_hazard_precursor": unwind,
            "recovery_status": "UNKNOWN_NOT_MEASURED",
            "windows": windows,
        }
        return self._frame(
            pool_id, state=state, observed_at=pair_at,
            base_amount=base_amount, quote_amount=quote_amount,
            effective_quote=effective_quote if effective_known else None,
            slot_min=slot_min, slot_max=slot_max,
            features=features,
        )


def decode_pump_bonding_curve_account(raw: bytes) -> dict[str, Any]:
    """Decode the current Pump BondingCurve while zero-padding legacy accounts."""
    if len(raw) < 49 or raw[:8] != PUMP_BONDING_CURVE_DISCRIMINATOR:
        raise ValueError("invalid_pump_bonding_curve_layout")
    from solders.pubkey import Pubkey

    padded = raw[:115].ljust(115, b"\0")
    return {
        "decoder_version": PUMP_BONDING_CURVE_DECODER_V1,
        "account_data_length": len(raw),
        "virtual_token_reserves_raw": int.from_bytes(padded[8:16], "little"),
        "virtual_quote_reserves_raw": int.from_bytes(padded[16:24], "little"),
        "real_token_reserves_raw": int.from_bytes(padded[24:32], "little"),
        "real_quote_reserves_raw": int.from_bytes(padded[32:40], "little"),
        "token_total_supply_raw": int.from_bytes(padded[40:48], "little"),
        "complete": bool(padded[48]),
        "creator": str(Pubkey.from_bytes(padded[49:81])),
        "is_mayhem_mode": bool(padded[81]),
        "is_cashback_coin": bool(padded[82]),
        "quote_mint": str(Pubkey.from_bytes(padded[83:115])),
    }


def decode_pump_global_account(raw: bytes) -> dict[str, Any]:
    """Decode the Pump Global fields used by official SDK 1.36.0 sell math."""
    if len(raw) < 162 or raw[:8] != PUMP_GLOBAL_DISCRIMINATOR:
        raise ValueError("invalid_pump_global_layout")
    return {
        "decoder_version": PUMP_GLOBAL_DECODER_V1,
        "account_data_length": len(raw),
        "fee_basis_points": int.from_bytes(raw[105:113], "little"),
        "creator_fee_basis_points": int.from_bytes(raw[154:162], "little"),
    }


def pump_bonding_curve_sell_quote_v1(
    *,
    token_amount_raw: int,
    slippage_bps: int,
    bonding_curve: Mapping[str, Any],
    global_config: Mapping[str, Any],
    fee_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Exact integer port of @pump-fun/pump-sdk 1.36.0 bonding-curve sell."""
    from solders.pubkey import Pubkey

    amount = int(token_amount_raw)
    slippage = int(slippage_bps)
    virtual_token = int(bonding_curve["virtual_token_reserves_raw"])
    virtual_quote = int(bonding_curve["virtual_quote_reserves_raw"])
    real_quote = int(bonding_curve["real_quote_reserves_raw"])
    if amount <= 0 or not 0 <= slippage <= 10_000:
        raise ValueError("invalid_pump_sell_input")
    if bool(bonding_curve.get("complete")) or virtual_token <= 0:
        raise ValueError("bonding_curve_complete_migrated")
    if virtual_quote <= 0:
        raise ValueError("invalid_pump_virtual_quote_reserve")

    fee_tier_index: int | None = None
    if fee_config is not None:
        tiers = list(fee_config.get("fee_tiers") or [])
        if not tiers:
            raise ValueError("invalid_pump_fee_tiers")
        supply = (
            int(bonding_curve["token_total_supply_raw"])
            if bool(bonding_curve.get("is_mayhem_mode"))
            else 1_000_000_000_000_000
        )
        market_cap = virtual_quote * supply // virtual_token
        fee_tier_index = 0
        if market_cap >= int(tiers[0]["market_cap_lamports_threshold"]):
            for index in range(len(tiers) - 1, -1, -1):
                if market_cap >= int(tiers[index]["market_cap_lamports_threshold"]):
                    fee_tier_index = index
                    break
        selected = dict(tiers[fee_tier_index]["fees"])
        fee_source = "pump_fee_config_tier"
    else:
        market_cap = virtual_quote * int(
            bonding_curve["token_total_supply_raw"]
        ) // virtual_token
        selected = {
            "lp_fee_bps": 0,
            "protocol_fee_bps": int(global_config["fee_basis_points"]),
            "creator_fee_bps": int(global_config["creator_fee_basis_points"]),
        }
        fee_source = "pump_global"

    def fee(value: int, bps: int) -> int:
        return (value * bps + 9_999) // 10_000

    gross = amount * virtual_quote // (virtual_token + amount)
    protocol_fee_bps = int(selected.get("protocol_fee_bps") or 0)
    creator_fee_bps = int(selected.get("creator_fee_bps") or 0)
    creator_present = str(bonding_curve.get("creator") or "") != str(Pubkey.default())
    protocol_fee = fee(gross, protocol_fee_bps)
    creator_fee = fee(gross, creator_fee_bps) if creator_present else 0
    if gross > real_quote:
        raise ValueError("insufficient_real_quote_reserves")
    received = gross - protocol_fee - creator_fee
    if received <= 0:
        raise ValueError("pump_fees_exceed_output")
    minimum = received * (10_000 - slippage) // 10_000
    return {
        "calculation_version": PUMP_BONDING_CURVE_SELL_V1,
        "fee_source": fee_source,
        "fee_tier_index": fee_tier_index,
        "market_cap_quote_raw": market_cap,
        "internal_quote_amount_out_raw": gross,
        "lp_fee_bps": 0,
        "protocol_fee_bps": protocol_fee_bps,
        "creator_fee_bps": creator_fee_bps if creator_present else 0,
        "lp_fee_raw": 0,
        "protocol_fee_raw": protocol_fee,
        "creator_fee_raw": creator_fee,
        "real_reserve_coverage_raw": gross,
        "ui_quote_raw": received,
        "min_quote_raw": minimum,
    }


def decode_pumpswap_pool_account(
    raw: bytes, *, include_current_fields: bool = True
) -> dict[str, Any]:
    """Decode official PumpSwap Pool fields; allocation padding is not data."""
    if len(raw) < 211 or raw[:8] != PUMPSWAP_POOL_DISCRIMINATOR:
        raise ValueError("invalid_pumpswap_pool_layout")
    from solders.pubkey import Pubkey

    def pubkey(offset: int) -> str:
        return str(Pubkey.from_bytes(raw[offset:offset + 32]))

    decoded: dict[str, Any] = {
        "index": int.from_bytes(raw[9:11], "little"),
        "creator": pubkey(11),
        "base_mint": pubkey(43),
        "quote_mint": pubkey(75),
        "lp_mint": pubkey(107),
        "base_vault": pubkey(139),
        "quote_vault": pubkey(171),
        "lp_supply_recorded_raw": int.from_bytes(raw[203:211], "little"),
    }
    if not include_current_fields:
        return decoded

    padded = raw[:PUMPSWAP_POOL_IDL_DEFINED_SIZE].ljust(
        PUMPSWAP_POOL_IDL_DEFINED_SIZE, b"\0"
    )
    if padded[243] not in (0, 1) or padded[244] not in (0, 1):
        raise ValueError("invalid_pumpswap_pool_bool")
    coin_creator = str(Pubkey.from_bytes(padded[211:243]))
    decoded.update({
        "decoder_version": PUMPSWAP_POOL_DECODER_V2,
        "account_data_length": len(raw),
        "idl_defined_size": PUMPSWAP_POOL_IDL_DEFINED_SIZE,
        "sdk_extend_threshold": PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD,
        "observed_current_allocation": PUMPSWAP_POOL_OBSERVED_ALLOCATION,
        "needs_sdk_extend": len(raw) < PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD,
        "coin_creator": coin_creator,
        "coin_creator_is_default": coin_creator == str(Pubkey.default()),
        "is_mayhem_mode": bool(padded[243]),
        "is_cashback_coin": bool(padded[244]),
        "virtual_quote_reserves_raw": int.from_bytes(
            padded[245:261], "little", signed=True
        ),
        "allocation_padding_length": max(0, len(raw) - PUMPSWAP_POOL_IDL_DEFINED_SIZE),
    })
    return decoded


def decode_pumpswap_global_config_account(raw: bytes) -> dict[str, Any]:
    """Decode the fixed-size PumpSwap GlobalConfig from the official IDL."""
    if len(raw) < 940 or raw[:8] != PUMPSWAP_GLOBAL_CONFIG_DISCRIMINATOR:
        raise ValueError("invalid_pumpswap_global_config_layout")
    if raw[417] not in (0, 1) or raw[642] not in (0, 1) or raw[939] not in (0, 1):
        raise ValueError("invalid_pumpswap_global_config_bool")
    from solders.pubkey import Pubkey

    def pubkey(offset: int) -> str:
        return str(Pubkey.from_bytes(raw[offset:offset + 32]))

    return {
        "decoder_version": PUMPSWAP_GLOBAL_CONFIG_DECODER_V1,
        "account_data_length": len(raw),
        "borsh_used_size": 940,
        "admin": pubkey(8),
        "lp_fee_basis_points": int.from_bytes(raw[40:48], "little"),
        "protocol_fee_basis_points": int.from_bytes(raw[48:56], "little"),
        "disable_flags": raw[56],
        "protocol_fee_recipients": [pubkey(57 + 32 * index) for index in range(8)],
        "coin_creator_fee_basis_points": int.from_bytes(raw[313:321], "little"),
        "admin_set_coin_creator_authority": pubkey(321),
        "whitelist_pda": pubkey(353),
        "reserved_fee_recipient": pubkey(385),
        "mayhem_mode_enabled": bool(raw[417]),
        "reserved_fee_recipients": [pubkey(418 + 32 * index) for index in range(7)],
        "is_cashback_enabled": bool(raw[642]),
        "buyback_fee_recipients": [pubkey(643 + 32 * index) for index in range(8)],
        "buyback_basis_points": int.from_bytes(raw[899:907], "little"),
        "boost_authority": pubkey(907),
        "boost_enabled": bool(raw[939]),
        "allocation_padding_length": len(raw) - 940,
    }


def decode_pumpswap_fee_config_account(raw: bytes) -> dict[str, Any]:
    """Decode Pump fee tiers and retain the IDL's stable tiers and padding."""
    if len(raw) < 73 or raw[:8] != PUMPSWAP_FEE_CONFIG_DISCRIMINATOR:
        raise ValueError("invalid_pumpswap_fee_config_layout")
    from solders.pubkey import Pubkey

    def fees(offset: int) -> dict[str, int]:
        return {
            "lp_fee_bps": int.from_bytes(raw[offset:offset + 8], "little"),
            "protocol_fee_bps": int.from_bytes(raw[offset + 8:offset + 16], "little"),
            "creator_fee_bps": int.from_bytes(raw[offset + 16:offset + 24], "little"),
        }

    def tiers(offset: int, count: int) -> list[dict[str, Any]]:
        return [
            {
                "market_cap_lamports_threshold": int.from_bytes(
                    raw[offset + 40 * index:offset + 40 * index + 16], "little"
                ),
                "fees": fees(offset + 40 * index + 16),
            }
            for index in range(count)
        ]

    fee_tier_count = int.from_bytes(raw[65:69], "little")
    stable_count_offset = 69 + 40 * fee_tier_count
    if stable_count_offset + 4 > len(raw):
        raise ValueError("invalid_pumpswap_fee_config_layout")
    stable_fee_tier_count = int.from_bytes(
        raw[stable_count_offset:stable_count_offset + 4], "little"
    )
    stable_tier_offset = stable_count_offset + 4
    borsh_used_size = stable_tier_offset + 40 * stable_fee_tier_count
    if borsh_used_size > len(raw):
        raise ValueError("invalid_pumpswap_fee_config_layout")
    return {
        "decoder_version": PUMPSWAP_FEE_CONFIG_DECODER_V1,
        "account_data_length": len(raw),
        "borsh_used_size": borsh_used_size,
        "bump": raw[8],
        "admin": str(Pubkey.from_bytes(raw[9:41])),
        "flat_fees": fees(41),
        "fee_tiers": tiers(69, fee_tier_count),
        "stable_fee_tiers": tiers(stable_tier_offset, stable_fee_tier_count),
        "allocation_padding_length": len(raw) - borsh_used_size,
    }


def pumpswap_sell_base_input_v1(
    *,
    base_amount_raw: int,
    slippage_bps: int,
    base_reserve_raw: int,
    quote_reserve_raw: int,
    virtual_quote_reserves_raw: int,
    base_mint_supply_raw: int,
    base_mint: str,
    creator: str,
    coin_creator: str,
    global_config: Mapping[str, Any],
    fee_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Exact integer port of pump-swap-sdk 1.19.0 sellBaseInput."""
    from solders.pubkey import Pubkey

    base = int(base_amount_raw)
    base_reserve = int(base_reserve_raw)
    real_quote_reserve = int(quote_reserve_raw)
    virtual_quote_reserve = int(virtual_quote_reserves_raw)
    supply = int(base_mint_supply_raw)
    slippage = int(slippage_bps)
    if base < 0 or base_reserve < 0 or real_quote_reserve < 0 or supply < 0:
        raise ValueError("invalid_pumpswap_sell_unsigned_input")
    if base_reserve == 0 or real_quote_reserve == 0:
        raise ValueError("invalid_pumpswap_sell_zero_reserve")
    if not 0 <= slippage <= 10_000:
        raise ValueError("invalid_pumpswap_sell_slippage")

    def trunc_div(numerator: int, denominator: int) -> int:
        if denominator == 0:
            raise ZeroDivisionError
        sign = -1 if (numerator < 0) != (denominator < 0) else 1
        return sign * (abs(numerator) // abs(denominator))

    def fee(amount: int, basis_points: int) -> int:
        return trunc_div(amount * basis_points + 9_999, 10_000)

    effective_quote_reserve = real_quote_reserve + virtual_quote_reserve
    quote_amount_out = trunc_div(
        effective_quote_reserve * base, base_reserve + base
    )
    market_cap_lamports = trunc_div(
        effective_quote_reserve * supply, base_reserve
    )

    base_key = Pubkey.from_string(str(base_mint))
    pump_program = Pubkey.from_string(PUMP_PROGRAM_ID)
    pump_creator = Pubkey.find_program_address(
        [b"pool-authority", bytes(base_key)], pump_program
    )[0]
    is_pump_pool = Pubkey.from_string(str(creator)) == pump_creator
    fee_tier_index: int | None = None
    if fee_config is None:
        selected_fees = {
            "lp_fee_bps": int(global_config["lp_fee_basis_points"]),
            "protocol_fee_bps": int(global_config["protocol_fee_basis_points"]),
            "creator_fee_bps": int(global_config["coin_creator_fee_basis_points"]),
        }
        fee_source = "global_config"
    elif is_pump_pool:
        fee_tiers = list(fee_config["fee_tiers"])
        if not fee_tiers:
            raise ValueError("invalid_pumpswap_fee_tiers")
        fee_tier_index = 0
        if market_cap_lamports >= int(fee_tiers[0]["market_cap_lamports_threshold"]):
            for index in range(len(fee_tiers) - 1, -1, -1):
                if market_cap_lamports >= int(
                    fee_tiers[index]["market_cap_lamports_threshold"]
                ):
                    fee_tier_index = index
                    break
        selected_fees = fee_tiers[fee_tier_index]["fees"]
        fee_source = "fee_config_tier"
    else:
        selected_fees = fee_config["flat_fees"]
        fee_source = "fee_config_flat"

    lp_fee_bps = int(selected_fees["lp_fee_bps"])
    protocol_fee_bps = int(selected_fees["protocol_fee_bps"])
    creator_fee_bps = int(selected_fees["creator_fee_bps"])
    lp_fee = fee(quote_amount_out, lp_fee_bps)
    protocol_fee = fee(quote_amount_out, protocol_fee_bps)
    coin_creator_key = Pubkey.from_string(str(coin_creator))
    creator_fee = (
        0 if coin_creator_key == Pubkey.default()
        else fee(quote_amount_out, creator_fee_bps)
    )
    real_reserve_coverage_raw = quote_amount_out - lp_fee
    if real_quote_reserve < real_reserve_coverage_raw:
        raise ValueError("insufficient_real_quote_reserves")
    final_quote = quote_amount_out - lp_fee - protocol_fee - creator_fee
    if final_quote < 0:
        raise ValueError("pumpswap_fees_exceed_output")
    min_quote = final_quote * (10_000 - slippage) // 10_000
    return {
        "calculation_version": PUMPSWAP_SELL_BASE_INPUT_V1,
        "is_pump_pool": is_pump_pool,
        "fee_source": fee_source,
        "fee_tier_index": fee_tier_index,
        "effective_quote_reserve_raw": effective_quote_reserve,
        "market_cap_lamports": market_cap_lamports,
        "internal_quote_amount_out_raw": quote_amount_out,
        "lp_fee_bps": lp_fee_bps,
        "protocol_fee_bps": protocol_fee_bps,
        "creator_fee_bps": creator_fee_bps,
        "lp_fee_raw": lp_fee,
        "protocol_fee_raw": protocol_fee,
        "creator_fee_raw": creator_fee,
        "real_reserve_coverage_raw": real_reserve_coverage_raw,
        "ui_quote_raw": final_quote,
        "min_quote_raw": min_quote,
    }


class UnsafeFeedURL(ValueError):
    pass


class JupiterQuoteError(RuntimeError):
    pass


class JupiterNoRouteError(JupiterQuoteError):
    pass


class JupiterQuoteProtocolError(JupiterQuoteError):
    pass


class EvmRouteQuoteError(RuntimeError):
    pass


class EvmRouteQuoteProtocolError(EvmRouteQuoteError):
    pass


class EvmRouteRpcError(EvmRouteQuoteError):
    pass


class EvmRouteExecutionReverted(EvmRouteRpcError):
    pass


class FeedRedirectError(RuntimeError):
    pass


class FeedResponseTooLarge(RuntimeError):
    pass


class InvalidFeedContentType(RuntimeError):
    pass


class InvalidPublicDocumentContentType(RuntimeError):
    pass


class UnsupportedFeedContentEncoding(RuntimeError):
    pass


def _public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
        and not address.is_multicast
        and not address.is_unspecified
    )


def _canonical_ip(value: str) -> str:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return str(address)


def normalize_public_http_url(value: str) -> str:
    """Validate the non-DNS portion of a public HTTP(S) feed URL."""
    raw = str(value or "").strip()
    if not raw or any(ord(char) <= 32 or ord(char) == 127 for char in raw):
        raise UnsafeFeedURL("feed URL contains whitespace or control characters")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise UnsafeFeedURL("invalid feed URL") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise UnsafeFeedURL("feed URL must use public http or https")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeFeedURL("feed URL credentials are forbidden")
    if "#" in raw or parsed.fragment:
        raise UnsafeFeedURL("feed URL fragments are forbidden")
    host = parsed.hostname.lower().rstrip(".")
    if (
        host in {"localhost", "localhost.localdomain", *METADATA_HOSTS}
        or host.endswith(".local")
        or host.endswith(".ec2.internal")
    ):
        raise UnsafeFeedURL("feed URL host is not public")
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None and not _public_ip(str(literal)):
        raise UnsafeFeedURL("feed URL address is not public")
    netloc = host
    if ":" in netloc and not netloc.startswith("["):
        netloc = f"[{netloc}]"
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, "")
    )


def normalize_loopback_socks5_proxy_url(value: str) -> str:
    """Accept only an unauthenticated SOCKS5 proxy at a literal loopback IP."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if any(ord(char) <= 32 or ord(char) == 127 for char in raw):
        raise ValueError("RSS proxy URL contains whitespace or control characters")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid RSS proxy URL") from exc
    if parsed.scheme.lower() != "socks5":
        raise ValueError("RSS proxy must use socks5")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("RSS proxy credentials are forbidden")
    if parsed.path or parsed.query or parsed.fragment or "?" in raw or "#" in raw:
        raise ValueError("RSS proxy URL cannot contain a path, query, or fragment")
    if not parsed.hostname or port is None or not 1 <= port <= 65_535:
        raise ValueError("RSS proxy requires a literal loopback IP and valid port")
    if "%" in parsed.hostname:
        raise ValueError("RSS proxy requires an unscoped literal loopback IP")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError("RSS proxy host must be a literal loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("RSS proxy host must be loopback")
    host = f"[{address}]" if isinstance(address, ipaddress.IPv6Address) else str(address)
    return f"socks5://{host}:{port}"


async def public_destination_addresses(url: str) -> set[str]:
    """Resolve one request hop and reject it if any destination is non-public."""
    normalized = normalize_public_http_url(url)
    host = urllib.parse.urlsplit(normalized).hostname or ""
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        addresses = {_canonical_ip(str(literal))}
    else:
        try:
            rows = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeFeedURL("feed URL host did not resolve") from exc
        addresses = {
            _canonical_ip(str(row[4][0]))
            for row in rows
            if row and row[4]
        }
    if not addresses or any(not _public_ip(value) for value in addresses):
        raise UnsafeFeedURL("feed URL resolved to a non-public destination")
    return addresses


def rss_cache_key(url: str) -> str:
    normalized = normalize_public_http_url(url)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{RSS_CACHE_KEY_PREFIX}{digest}"


def _looks_like_feed_xml(content: bytes) -> bool:
    sample = content[:4096].lstrip(b"\xef\xbb\xbf\x00\t\r\n ")
    sample = re.sub(br"^<\?xml[^>]*>\s*", b"", sample, count=1, flags=re.I)
    sample = re.sub(br"^(?:<!--.*?-->\s*)+", b"", sample, count=1, flags=re.I | re.S)
    return bool(re.match(br"<(?:rss|feed|rdf:RDF)(?:\s|>)", sample, flags=re.I))


def _validate_feed_content_type(headers: httpx.Headers, content: bytes) -> None:
    media_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if media_type in RSS_XML_MEDIA_TYPES or media_type.endswith("+xml"):
        return
    if media_type in RSS_GENERIC_MEDIA_TYPES and _looks_like_feed_xml(content):
        return
    raise InvalidFeedContentType("response is not a conservatively identifiable RSS/Atom XML feed")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _published(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return parse_time(str(value))
    except Exception:
        try:
            return parsedate_to_datetime(str(value)).astimezone()
        except Exception:
            return None


class HttpClient:
    """Small host-aware client for free public endpoints."""

    MAX_CACHE_ENTRIES = 512

    def __init__(
        self,
        *,
        timeout: float = 12.0,
        min_host_interval: float = 0.6,
        user_agent: str = "memeTrader/0.6",
        feed_max_response_bytes: int = 1_048_576,
        feed_max_redirects: int = 5,
        feed_proxy_url: str = "",
        conditional_store: Any | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json,text/xml,application/xml,text/html,*/*"},
            transport=transport,
        )
        self.feed_proxy_url = normalize_loopback_socks5_proxy_url(feed_proxy_url)
        proxy_host = urllib.parse.urlsplit(self.feed_proxy_url).hostname if self.feed_proxy_url else None
        self.feed_proxy_ip = _canonical_ip(proxy_host) if proxy_host else None
        self._require_feed_peer = transport is None
        self.feed_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
            headers={"User-Agent": user_agent},
            proxy=(self.feed_proxy_url or None) if transport is None else None,
            transport=transport,
        )
        self.min_host_interval = min_host_interval
        self.feed_max_response_bytes = max(1, int(feed_max_response_bytes))
        self.feed_max_redirects = max(0, int(feed_max_redirects))
        self.conditional_store = conditional_store
        self._last: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cache: dict[str, tuple[float, Any]] = {}

    def _prune_cache(self, now: float) -> None:
        if len(self._cache) < self.MAX_CACHE_ENTRIES:
            return
        expired = [
            key for key, (expires_at, _) in self._cache.items()
            if expires_at <= now
        ]
        for key in expired:
            self._cache.pop(key, None)
        overflow = len(self._cache) - self.MAX_CACHE_ENTRIES
        if overflow > 0:
            for key, _ in sorted(
                self._cache.items(), key=lambda item: item[1][0]
            )[:overflow]:
                self._cache.pop(key, None)

    async def close(self) -> None:
        await self.client.aclose()
        await self.feed_client.aclose()

    async def _reserve_host_request_start(
        self, host: str, *, not_before: float = 0.0,
    ) -> None:
        """Space request starts without serializing normal response time."""
        async with self._locks[host]:
            await self._reserve_locked_host_request_start(
                host, not_before=not_before,
            )

    async def _reserve_locked_host_request_start(
        self, host: str, *, not_before: float = 0.0,
    ) -> None:
        now = time.monotonic()
        wait = max(
            0.0,
            self.min_host_interval - (now - self._last[host]),
            float(not_before) - now,
        )
        if wait > 0:
            await asyncio.sleep(wait)
        self._last[host] = time.monotonic()

    async def get(self, url: str, *, params: dict[str, Any] | None = None, ttl: float = 0, headers: dict[str, str] | None = None) -> httpx.Response:
        key = url + "?" + urllib.parse.urlencode(sorted((params or {}).items()), doseq=True)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached is not None and cached[0] <= now:
            self._cache.pop(key, None)
            cached = None
        self._prune_cache(now)
        if ttl and cached and cached[0] > now:
            response = httpx.Response(200, request=httpx.Request("GET", url), json=cached[1])
            return response
        host = urllib.parse.urlparse(url).netloc.lower()
        await self._reserve_host_request_start(host)
        response = await self.client.get(url, params=params, headers=headers)
        if response.status_code == 429:
            retry = min(15.0, float(response.headers.get("Retry-After", "2") or 2))
            async with self._locks[host]:
                await self._reserve_locked_host_request_start(
                    host, not_before=time.monotonic() + retry,
                )
                response = await self.client.get(url, params=params, headers=headers)
        response.raise_for_status()
        if ttl:
            try:
                now = time.monotonic()
                self._prune_cache(now)
                self._cache[key] = (now + ttl, response.json())
                self._prune_cache(now)
            except Exception:
                pass
        return response

    def _feed_cache(self, url: str) -> dict[str, Any]:
        if self.conditional_store is None:
            return {}
        value = self.conditional_store.get_kv(rss_cache_key(url), {})
        return value if isinstance(value, dict) else {}

    def _set_feed_cache(self, url: str, value: dict[str, Any]) -> None:
        if self.conditional_store is not None:
            self.conditional_store.set_kv(rss_cache_key(url), value)

    @staticmethod
    def _peer_address(response: httpx.Response) -> str | None:
        stream = response.extensions.get("network_stream")
        if stream is None or not hasattr(stream, "get_extra_info"):
            return None
        for key in ("server_addr", "peername"):
            try:
                value = stream.get_extra_info(key)
            except Exception:
                continue
            if isinstance(value, (tuple, list)) and value:
                try:
                    return _canonical_ip(str(value[0]))
                except ValueError:
                    return None
            if isinstance(value, str) and value:
                try:
                    return _canonical_ip(value)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _pinned_url(url: str, address: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        host = address
        if ":" in host:
            host = f"[{host}]"
        port = parsed.port
        netloc = f"{host}:{port}" if port is not None else host
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))

    @staticmethod
    def _host_header(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        default_port = 443 if parsed.scheme == "https" else 80
        return f"{host}:{parsed.port}" if parsed.port is not None and parsed.port != default_port else host

    @asynccontextmanager
    async def _pinned_feed_response(
        self,
        logical_url: str,
        approved_addresses: set[str],
        headers: dict[str, str],
    ) -> AsyncIterator[httpx.Response]:
        parsed = urllib.parse.urlsplit(logical_url)
        original_host = parsed.hostname or ""
        last_error: Exception | None = None
        ordered_addresses = sorted(approved_addresses, key=lambda value: (":" in value, value))
        for address in ordered_addresses:
            pinned_url = self._pinned_url(logical_url, address)
            request = self.feed_client.build_request(
                "GET",
                pinned_url,
                headers={**headers, "Host": self._host_header(logical_url)},
                extensions={
                    "sni_hostname": original_host,
                    "feed_original_url": logical_url,
                    "feed_approved_ip": address,
                },
            )
            try:
                response = await self.feed_client.send(request, stream=True, follow_redirects=False)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError) as exc:
                last_error = exc
                continue
            try:
                yield response
            finally:
                await response.aclose()
            return
        if last_error is not None:
            raise last_error
        raise UnsafeFeedURL("feed URL has no approved destination")

    async def get_public_feed(self, url: str) -> httpx.Response:
        """Fetch a bounded public feed with manual, independently checked redirects."""
        original_url = normalize_public_http_url(url)
        cache = self._feed_cache(original_url)
        conditional_url = str(cache.get("final_url") or original_url)
        try:
            conditional_url = normalize_public_http_url(conditional_url)
        except UnsafeFeedURL:
            conditional_url = original_url
        etag = str(cache.get("etag") or "")[:1024]
        last_modified = str(cache.get("last_modified") or "")[:256]
        current_url = original_url
        seen: set[str] = set()
        redirects = 0

        while True:
            current_url = normalize_public_http_url(current_url)
            if current_url in seen:
                raise FeedRedirectError("feed redirect loop detected")
            seen.add(current_url)
            approved_addresses = await public_destination_addresses(current_url)
            request_headers = {
                "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "identity",
            }
            if current_url == conditional_url:
                if etag:
                    request_headers["If-None-Match"] = etag
                if last_modified:
                    request_headers["If-Modified-Since"] = last_modified

            host = urllib.parse.urlsplit(current_url).netloc.lower()
            async with self._locks[host]:
                wait = self.min_host_interval - (time.monotonic() - self._last[host])
                if wait > 0:
                    await asyncio.sleep(wait)
                async with self._pinned_feed_response(
                    current_url,
                    approved_addresses,
                    request_headers,
                ) as upstream:
                    self._last[host] = time.monotonic()
                    peer = self._peer_address(upstream)
                    expected_peers = {self.feed_proxy_ip} if self.feed_proxy_ip else approved_addresses
                    if peer is None:
                        if self._require_feed_peer:
                            raise UnsafeFeedURL("feed connection destination could not be verified")
                    elif peer not in expected_peers or (not self.feed_proxy_ip and not _public_ip(peer)):
                        raise UnsafeFeedURL("feed connection reached an unapproved destination")

                    if upstream.status_code in RSS_REDIRECT_STATUSES:
                        location = upstream.headers.get("Location", "")
                        if not location:
                            raise FeedRedirectError("feed redirect omitted Location")
                        if redirects >= self.feed_max_redirects:
                            raise FeedRedirectError("feed redirect limit exceeded")
                        current_url = normalize_public_http_url(
                            urllib.parse.urljoin(current_url, location)
                        )
                        redirects += 1
                        continue

                    content_encoding = upstream.headers.get("Content-Encoding", "").strip().lower()
                    if content_encoding not in {"", "identity"}:
                        raise UnsupportedFeedContentEncoding(
                            "compressed feed responses are not accepted"
                        )
                    if upstream.status_code == 304:
                        not_modified_headers = httpx.Headers(upstream.headers)
                        not_modified_headers.pop("Content-Encoding", None)
                        not_modified_headers.pop("Content-Length", None)
                        self._set_feed_cache(
                            original_url,
                            {
                                "url": original_url,
                                "final_url": current_url,
                                "etag": str(upstream.headers.get("ETag") or etag)[:1024],
                                "last_modified": str(
                                    upstream.headers.get("Last-Modified") or last_modified
                                )[:256],
                                "last_checked_at": iso(),
                                "last_status": 304,
                            },
                        )
                        return httpx.Response(
                            304,
                            headers=not_modified_headers,
                            request=upstream.request,
                        )

                    upstream.raise_for_status()
                    content_length = upstream.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = -1
                        if declared_size > self.feed_max_response_bytes:
                            raise FeedResponseTooLarge("feed response exceeds configured byte limit")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in upstream.aiter_raw():
                        size += len(chunk)
                        if size > self.feed_max_response_bytes:
                            raise FeedResponseTooLarge("feed response exceeds configured byte limit")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    _validate_feed_content_type(upstream.headers, content)
                    safe_headers = httpx.Headers(upstream.headers)
                    safe_headers.pop("Content-Encoding", None)
                    safe_headers.pop("Content-Length", None)
                    response = httpx.Response(
                        upstream.status_code,
                        content=content,
                        headers=safe_headers,
                        request=upstream.request,
                    )
                    response.headers.pop("Content-Encoding", None)
                    response.headers.pop("Content-Length", None)
                    self._set_feed_cache(
                        original_url,
                        {
                            "url": original_url,
                            "final_url": current_url,
                            "etag": str(upstream.headers.get("ETag") or "")[:1024],
                            "last_modified": str(upstream.headers.get("Last-Modified") or "")[:256],
                            "last_checked_at": iso(),
                            "last_status": int(upstream.status_code),
                        },
                    )
                    return response

    async def get_public_document(
        self,
        url: str,
        *,
        maximum_bytes: int = 524_288,
        maximum_redirects: int = 3,
        forbidden_host_suffixes: set[str] | None = None,
    ) -> httpx.Response:
        """Fetch one bounded public text document with DNS pinning and checked redirects."""
        current_url = normalize_public_http_url(url)
        forbidden = {str(value).lower().strip(".") for value in (forbidden_host_suffixes or set())}
        seen: set[str] = set()
        redirects = 0
        maximum_bytes = max(1, int(maximum_bytes))
        maximum_redirects = max(0, int(maximum_redirects))
        while True:
            current_url = normalize_public_http_url(current_url)
            host_name = (urllib.parse.urlsplit(current_url).hostname or "").lower().rstrip(".")
            if any(host_name == suffix or host_name.endswith(f".{suffix}") for suffix in forbidden):
                raise UnsafeFeedURL("document URL host is not allowed")
            if current_url in seen:
                raise FeedRedirectError("document redirect loop detected")
            seen.add(current_url)
            approved_addresses = await public_destination_addresses(current_url)
            request_headers = {
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain,application/xml;q=0.8,*/*;q=0.1",
                "Accept-Encoding": "identity",
            }
            host = urllib.parse.urlsplit(current_url).netloc.lower()
            async with self._locks[host]:
                wait = self.min_host_interval - (time.monotonic() - self._last[host])
                if wait > 0:
                    await asyncio.sleep(wait)
                async with self._pinned_feed_response(
                    current_url, approved_addresses, request_headers
                ) as upstream:
                    self._last[host] = time.monotonic()
                    peer = self._peer_address(upstream)
                    expected_peers = {self.feed_proxy_ip} if self.feed_proxy_ip else approved_addresses
                    if peer is None:
                        if self._require_feed_peer:
                            raise UnsafeFeedURL("document connection destination could not be verified")
                    elif peer not in expected_peers or (not self.feed_proxy_ip and not _public_ip(peer)):
                        raise UnsafeFeedURL("document connection reached an unapproved destination")
                    if upstream.status_code in RSS_REDIRECT_STATUSES:
                        location = upstream.headers.get("Location", "")
                        if not location:
                            raise FeedRedirectError("document redirect omitted Location")
                        if redirects >= maximum_redirects:
                            raise FeedRedirectError("document redirect limit exceeded")
                        current_url = normalize_public_http_url(
                            urllib.parse.urljoin(current_url, location)
                        )
                        redirects += 1
                        continue
                    content_encoding = upstream.headers.get("Content-Encoding", "").strip().lower()
                    if content_encoding not in {"", "identity"}:
                        raise UnsupportedFeedContentEncoding(
                            "compressed document responses are not accepted"
                        )
                    upstream.raise_for_status()
                    media_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    if not (
                        media_type.startswith("text/")
                        or media_type in {"application/json", "application/xml", "application/xhtml+xml"}
                        or media_type.endswith("+json")
                        or media_type.endswith("+xml")
                    ):
                        raise InvalidPublicDocumentContentType(
                            "response is not a text document"
                        )
                    content_length = upstream.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = -1
                        if declared_size > maximum_bytes:
                            raise FeedResponseTooLarge("document response exceeds byte limit")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in upstream.aiter_raw():
                        size += len(chunk)
                        if size > maximum_bytes:
                            raise FeedResponseTooLarge("document response exceeds byte limit")
                        chunks.append(chunk)
                    safe_headers = httpx.Headers(upstream.headers)
                    safe_headers.pop("Content-Encoding", None)
                    safe_headers.pop("Content-Length", None)
                    return httpx.Response(
                        upstream.status_code,
                        content=b"".join(chunks),
                        headers=safe_headers,
                        request=httpx.Request("GET", current_url),
                        extensions={"logical_url": current_url},
                    )


class RSSCollector:
    def __init__(self, http: HttpClient, name: str, url: str, source_kind: str = "news"):
        self.http, self.name, self.url, self.source_kind = http, name, url, source_kind
        self.last_not_modified = False

    async def poll(self) -> list[Observation]:
        self.last_not_modified = False
        response = await self.http.get_public_feed(self.url)
        self.last_not_modified = response.status_code == 304
        if self.last_not_modified:
            return []
        observed_at = utcnow()
        root = ET.fromstring(response.content)
        root_name = root.tag.rsplit("}", 1)[-1].lower()
        if root_name not in {"rss", "feed", "rdf"}:
            raise InvalidFeedContentType("XML root is not RSS, Atom, or RDF")
        items = root.findall(".//item")
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//a:entry", ns)
        out: list[Observation] = []
        for item in items[:80]:
            def text(*names: str) -> str:
                for name in names:
                    node = item.find(name)
                    if node is not None and node.text:
                        return node.text.strip()
                return ""
            title = text("title", "{http://www.w3.org/2005/Atom}title")
            if not title:
                continue
            link = text("link")
            if not link:
                node = item.find("{http://www.w3.org/2005/Atom}link")
                link = node.attrib.get("href", "") if node is not None else ""
            description = text("description", "summary", "{http://www.w3.org/2005/Atom}summary", "content", "{http://www.w3.org/2005/Atom}content")
            published = text("pubDate", "published", "{http://www.w3.org/2005/Atom}published")
            updated = text("updated", "{http://www.w3.org/2005/Atom}updated")
            updated_at = _published(updated)
            source_item_id = text("guid", "id", "{http://www.w3.org/2005/Atom}id") or link
            author = text("author", "creator", "{http://www.w3.org/2005/Atom}author")
            source_node = item.find("source")
            publisher = (source_node.text or "").strip() if source_node is not None and source_node.text else ""
            publisher_url = source_node.attrib.get("url", "") if source_node is not None else ""
            out.append(
                Observation(
                    source=self.name,
                    source_kind=self.source_kind,
                    title=title,
                    text=description,
                    url=link,
                    author=author or publisher,
                    published_at=_published(published or updated),
                    observed_at=observed_at,
                    availability_proof="local_poll",
                    source_item_id=source_item_id,
                    raw={
                        "feed_url": self.url,
                        "publisher": publisher,
                        "publisher_url": publisher_url,
                        "source_item_state": "present",
                        **({
                            "source_reported_revision_at": iso(updated_at),
                            "source_item_state_evidence": "api_revision",
                        } if updated_at else {}),
                    },
                )
            )
        for tombstone in root.findall(".//{http://purl.org/atompub/tombstones/1.0}deleted-entry")[:80]:
            source_item_id = str(tombstone.attrib.get("ref") or "").strip()
            deleted_at = str(tombstone.attrib.get("when") or "").strip()
            deleted_time = _published(deleted_at)
            if not source_item_id:
                continue
            out.append(
                Observation(
                    source=self.name,
                    source_kind=self.source_kind,
                    title="Source item deletion marker",
                    text="",
                    url=source_item_id if source_item_id.startswith(("http://", "https://")) else "",
                    observed_at=observed_at,
                    availability_proof="local_poll",
                    role="identity",
                    source_item_id=source_item_id,
                    raw={
                        "feed_url": self.url,
                        "source_item_state": "deleted",
                        "source_item_state_evidence": "publisher_deleted_marker",
                        **({"source_reported_revision_at": iso(deleted_time)} if deleted_time else {}),
                    },
                )
            )
        return out


class BlueskySearchCollector:
    def __init__(self, http: HttpClient, query: str):
        self.http, self.query = http, query

    async def poll(self) -> list[Observation]:
        response = await self.http.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": self.query, "limit": 50, "sort": "latest"},
        )
        out: list[Observation] = []
        for post in response.json().get("posts", []):
            record = post.get("record") or {}
            text = str(record.get("text") or "").strip()
            if not text:
                continue
            author = post.get("author") or {}
            handle = str(author.get("handle") or "")
            uri = str(post.get("uri") or "")
            rkey = uri.rsplit("/", 1)[-1] if uri else ""
            url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else ""
            out.append(
                Observation(
                    source=f"bluesky:{self.query}", source_kind="social", title=text[:240], text=text,
                    url=url, author=handle, published_at=_published(record.get("createdAt")), observed_at=utcnow(),
                    availability_proof="local_poll", source_item_id=uri or url,
                    raw={
                        "like_count": post.get("likeCount"),
                        "repost_count": post.get("repostCount"),
                        "source_revision_id": post.get("cid"),
                        "source_item_state": "present",
                    },
                )
            )
        return out


class MastodonCollector:
    """Poll a public Mastodon-compatible account or tag timeline."""

    def __init__(self, http: HttpClient, name: str, url: str):
        self.http, self.name, self.url = http, name, url

    async def poll(self) -> list[Observation]:
        response = await self.http.get(self.url)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("statuses") or payload.get("items") or []
        out: list[Observation] = []
        for status in payload[:80] if isinstance(payload, list) else []:
            content = str(status.get("content") or status.get("text") or "")
            title = str(status.get("spoiler_text") or content)[:240]
            account = status.get("account") or {}
            author = str(account.get("acct") or status.get("username") or "")
            url = str(status.get("url") or status.get("uri") or "")
            if title.strip():
                out.append(
                    Observation(
                        source=self.name, source_kind="social", title=title, text=content, url=url, author=author,
                        published_at=_published(status.get("created_at")), observed_at=utcnow(),
                        availability_proof="local_poll",
                        source_item_id=str(status.get("id") or status.get("uri") or url),
                        raw={
                            "platform": "mastodon",
                            "reblogs_count": status.get("reblogs_count"),
                            "favourites_count": status.get("favourites_count"),
                            "source_item_state": "present",
                            **({
                                "source_reported_revision_at": status.get("edited_at"),
                                "source_item_state_evidence": "api_revision",
                            } if status.get("edited_at") else {}),
                        },
                    )
                )
        return out


class GeckoNewPoolsCollector:
    def __init__(self, http: HttpClient, network: str):
        self.http, self.network = http, network

    async def poll(self) -> list[TokenCandidate]:
        response = await self.http.get(
            f"https://api.geckoterminal.com/api/v2/networks/{self.network}/new_pools",
            params={"include": "base_token,quote_token,dex", "page": 1}, ttl=20,
        )
        payload = response.json()
        from .market_api import normalize_gecko_pool
        received_at = utcnow()
        included = {item.get("id"): item for item in payload.get("included", [])}
        out: list[TokenCandidate] = []
        for pool in payload.get("data", [])[:40]:
            attrs = pool.get("attributes") or {}
            rel = (((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {})
            token_data = included.get(rel.get("id"), {})
            token_attrs = token_data.get("attributes") or {}
            address = str(token_attrs.get("address") or rel.get("id", "").split("_", 1)[-1])
            if not address:
                continue
            chain = "solana" if self.network == "solana" else ("bsc" if self.network in {"bsc", "binance-smart-chain"} else self.network)
            out.append(
                TokenCandidate(
                    chain=chain, address=address, name=str(token_attrs.get("name") or attrs.get("name") or ""),
                    symbol=str(token_attrs.get("symbol") or ""), created_at=_published(attrs.get("pool_created_at")),
                    source=f"geckoterminal:{self.network}", url=f"https://www.geckoterminal.com/{self.network}/pools/{attrs.get('address','')}",
                    raw={"pool": attrs, "pool_address": attrs.get("address"),
                         "market_pair": normalize_gecko_pool(pool, payload.get("included", []),
                             chain, received_at, provider="geckoterminal")},
                )
            )
        return out


class DexScreenerClient:
    BASE = "https://api.dexscreener.com"
    DISCOVERY_SURFACES = {
        "token_profiles": ("/token-profiles/latest/v1", "identity"),
        "community_takeovers": ("/community-takeovers/latest/v1", "identity"),
        "ads": ("/ads/latest/v1", "promotion"),
        "boosts_latest": ("/token-boosts/latest/v1", "promotion"),
        "boosts_top": ("/token-boosts/top/v1", "promotion"),
    }
    SOCIAL_HOSTS = {
        "bsky.app": "bluesky",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "linkedin.com": "linkedin",
        "reddit.com": "reddit",
        "threads.com": "threads",
        "threads.net": "threads",
        "tiktok.com": "tiktok",
        "truthsocial.com": "truth",
        "twitter.com": "x",
        "x.com": "x",
        "youtube.com": "youtube",
        "youtu.be": "youtube",
    }

    @staticmethod
    def metadata_is_usable(name: str, symbol: str) -> bool:
        """Reject provider payloads that concatenate an asset catalogue into one token."""
        return len(str(name or "").strip()) <= 160 and len(str(symbol or "").strip()) <= 64
    TELEGRAM_HOSTS = {"t.me", "telegram.me"}

    def __init__(self, http: HttpClient):
        self.http = http

    @staticmethod
    def _chain(chain_id: str) -> str:
        return {"bsc": "bsc", "solana": "solana", "base": "base", "ethereum": "ethereum"}.get(chain_id, chain_id)

    @staticmethod
    def _normalized_link_url(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = urllib.parse.urlsplit(raw)
            without_fragment = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
            )
            return normalize_public_http_url(without_fragment)
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _classify_link(cls, value: Any, *, label: str = "", platform: str = "") -> tuple[str, str, str]:
        normalized = cls._normalized_link_url(value)
        if not normalized:
            return "invalid", "", ""
        parsed = urllib.parse.urlsplit(normalized)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        if any(host == root or host.endswith(f".{root}") for root in cls.TELEGRAM_HOSTS):
            return "telegram_manual", "telegram", normalized
        if host == "dexscreener.com" or host.endswith(".dexscreener.com"):
            return "dex_page", "dexscreener", normalized
        label_hint = f"{label} {platform}".casefold()
        if host in {"twitter.com", "x.com"} and path.casefold().startswith("/search"):
            return "search", "x", normalized
        if "search" in label_hint or (
            host in {"bing.com", "google.com"} and path.casefold().startswith("/search")
        ):
            return "search", "", normalized
        detected_platform = str(platform or "").strip().lower()
        detected_platform = {
            "twitter": "x",
            "truthsocial": "truth",
            "telegram": "telegram",
        }.get(detected_platform, detected_platform)
        if not detected_platform:
            detected_platform = next(
                (
                    name
                    for root, name in cls.SOCIAL_HOSTS.items()
                    if host == root or host.endswith(f".{root}")
                ),
                "",
            )
        lowered_path = path.casefold()
        post_markers = {
            "x": "/status/",
            "truth": "/posts/",
            "bluesky": "/post/",
            "reddit": "/comments/",
            "threads": "/post/",
            "tiktok": "/video/",
        }
        marker = post_markers.get(detected_platform)
        is_post = bool(marker and marker in lowered_path)
        if detected_platform == "truth":
            segments = [part for part in path.split("/") if part]
            is_post = "/statuses/" in lowered_path or (
                len(segments) >= 2 and segments[0].startswith("@") and segments[-1].isdigit()
            )
        if detected_platform == "instagram":
            is_post = lowered_path.startswith(("/p/", "/reel/", "/reels/"))
        elif detected_platform == "youtube":
            is_post = host == "youtu.be" or lowered_path.startswith(("/watch", "/shorts/", "/live/"))
        if detected_platform:
            return ("social_post" if is_post else "social_profile"), detected_platform, normalized
        return "website", "", normalized

    @classmethod
    def _source_link_rows(
        cls,
        *,
        chain: str,
        address: str,
        surface: str,
        role: str,
        raw: dict[str, Any],
        primary_url: Any = "",
        links: list[Any] | tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        token_id = f"{chain.lower()}:{address}"
        candidates: list[tuple[Any, str, str]] = [(primary_url, surface, "")]
        for item in links:
            if isinstance(item, dict):
                candidates.append(
                    (
                        item.get("url"),
                        str(item.get("label") or item.get("type") or item.get("platform") or ""),
                        str(item.get("platform") or item.get("type") or ""),
                    )
                )
            elif item:
                candidates.append((item, "", ""))
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for original_url, label, platform in candidates:
            link_kind, detected_platform, normalized_url = cls._classify_link(
                original_url,
                label=label,
                platform=platform,
            )
            if not normalized_url:
                continue
            key = (normalized_url, link_kind, detected_platform)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "token_id": token_id,
                    "chain": chain.lower(),
                    "address": address,
                    "provider": "dexscreener",
                    "discovery_surface": surface,
                    "role": role,
                    "original_url": str(original_url or "")[:4000],
                    "normalized_url": normalized_url[:4000],
                    "link_kind": link_kind,
                    "label": str(label or "")[:200],
                    "platform": detected_platform[:80],
                    "verification_status": "manual_only" if link_kind == "telegram_manual" else "provider_metadata",
                    "raw": raw,
                }
            )
        if not rows:
            rows.append(
                {
                    "token_id": token_id,
                    "chain": chain.lower(),
                    "address": address,
                    "provider": "dexscreener",
                    "discovery_surface": surface,
                    "role": role,
                    "original_url": "",
                    "normalized_url": "",
                    "link_kind": "metadata",
                    "label": surface,
                    "platform": "",
                    "verification_status": "provider_metadata",
                    "raw": raw,
                }
            )
        return rows

    @classmethod
    def _pair_source_links(cls, pair: dict[str, Any], chain: str, address: str) -> list[dict[str, Any]]:
        info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
        links = [*(info.get("websites") or []), *(info.get("socials") or [])]
        return cls._source_link_rows(
            chain=chain,
            address=address,
            surface="pair_info",
            role="identity",
            raw={"pair": pair},
            primary_url=pair.get("url"),
            links=links,
        )

    @staticmethod
    def _candidate(pair: dict[str, Any]) -> TokenCandidate | None:
        base = pair.get("baseToken") or {}
        address = str(base.get("address") or "")
        chain = DexScreenerClient._chain(str(pair.get("chainId") or ""))
        name = str(base.get("name") or "")
        symbol = str(base.get("symbol") or "")
        if not address or not chain or not DexScreenerClient.metadata_is_usable(name, symbol):
            return None
        info = pair.get("info") or {}
        source_links = DexScreenerClient._pair_source_links(pair, chain, address)
        social_urls = [
            str(row["normalized_url"])
            for row in source_links
            if row["normalized_url"] and row["link_kind"] not in {"dex_page", "metadata"}
        ]
        created = pair.get("pairCreatedAt")
        created_at = None
        if created:
            try:
                created_at = datetime.fromtimestamp(float(created) / 1000, tz=utcnow().tzinfo)
            except Exception:
                pass
        return TokenCandidate(
            chain=chain, address=address, name=name, symbol=symbol,
            created_at=created_at, source="dexscreener", url=str(pair.get("url") or ""),
            social_urls=list(dict.fromkeys(social_urls)), raw={"pair": pair, "token_source_links": source_links},
        )

    @staticmethod
    def _snapshot(pair: dict[str, Any]) -> TokenSnapshot | None:
        candidate = DexScreenerClient._candidate(pair)
        if not candidate:
            return None
        tx = (pair.get("txns") or {}).get("m5") or {}
        volume = (pair.get("volume") or {}).get("m5")
        liquidity = (pair.get("liquidity") or {}).get("usd")
        return TokenSnapshot(
            chain=candidate.chain, address=candidate.address, price_usd=_float(pair.get("priceUsd")),
            liquidity_usd=_float(liquidity), market_cap_usd=_float(pair.get("marketCap") or pair.get("fdv")),
            volume_5m_usd=_float(volume), buys_5m=_int(tx.get("buys")), sells_5m=_int(tx.get("sells")),
            observed_at=utcnow(), provider="dexscreener", raw={"pair": pair},
        )

    async def search(self, query: str, limit: int = 30) -> list[tuple[TokenCandidate, TokenSnapshot]]:
        response = await self.http.get(f"{self.BASE}/latest/dex/search", params={"q": query}, ttl=12)
        by_token: dict[str, tuple[TokenCandidate, TokenSnapshot]] = {}
        for pair in response.json().get("pairs", [])[:limit]:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if candidate and snap:
                current = by_token.get(candidate.token_id)
                if current is None or (snap.liquidity_usd or 0.0) > (current[1].liquidity_usd or 0.0):
                    by_token[candidate.token_id] = (candidate, snap)
        return list(by_token.values())

    async def quote(self, chain: str, address: str) -> tuple[TokenCandidate, TokenSnapshot] | None:
        response = await self.http.get(f"{self.BASE}/token-pairs/v1/{chain}/{address}", ttl=8)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("pairs") or []
        ranked: list[tuple[float, TokenCandidate, TokenSnapshot]] = []
        for pair in payload if isinstance(payload, list) else []:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if (
                candidate
                and snap
                and candidate.chain.lower() == self._chain(chain).lower()
                and canonical_token_address(candidate.chain, candidate.address)
                == canonical_token_address(self._chain(chain), address)
            ):
                ranked.append(((snap.liquidity_usd or 0.0), candidate, snap))
        if not ranked:
            return None
        _, candidate, snap = max(ranked, key=lambda row: row[0])
        return candidate, snap

    async def batch_quote(
        self,
        chain: str,
        addresses: list[str] | tuple[str, ...],
        *,
        ttl: float = 8,
    ) -> dict[str, tuple[TokenCandidate, TokenSnapshot]]:
        """Hydrate up to many token details through DexScreener's documented 30-address endpoint."""
        normalized_chain = self._chain(str(chain)).lower()
        unique = list(dict.fromkeys(str(value).strip() for value in addresses if str(value).strip()))
        by_token: dict[str, tuple[TokenCandidate, TokenSnapshot]] = {}
        pools_by_token: dict[str, list[dict[str, Any]]] = {}
        for offset in range(0, len(unique), 30):
            chunk = unique[offset : offset + 30]
            requested = {
                canonical_token_address(normalized_chain, value): value
                for value in chunk
            }
            joined = urllib.parse.quote(",".join(chunk), safe=",")
            response = await self.http.get(
                f"{self.BASE}/tokens/v1/{normalized_chain}/{joined}",
                ttl=ttl,
            )
            payload = response.json()
            if isinstance(payload, dict):
                payload = payload.get("pairs") or []
            for pair in payload if isinstance(payload, list) else []:
                candidate, snap = self._candidate(pair), self._snapshot(pair)
                if not candidate or not snap or candidate.chain.lower() != normalized_chain:
                    continue
                requested_address = requested.get(
                    canonical_token_address(normalized_chain, candidate.address)
                )
                if requested_address is None:
                    continue
                canonical_address = canonical_token_address(
                    normalized_chain, requested_address,
                )
                candidate.address = canonical_address
                snap.address = canonical_address
                pools_by_token.setdefault(candidate.token_id, []).append(pair)
                current = by_token.get(candidate.token_id)
                if current is None or (snap.liquidity_usd or 0.0) > (current[1].liquidity_usd or 0.0):
                    by_token[candidate.token_id] = (candidate, snap)
        for token_id, (_, snapshot) in by_token.items():
            snapshot.raw["pairs"] = pools_by_token.get(token_id, [])
        return by_token

    async def batch_quote_fresh(
        self,
        chain: str,
        addresses: list[str] | tuple[str, ...],
    ) -> dict[str, tuple[TokenCandidate, TokenSnapshot]]:
        """Fetch current held-token marks without reusing the hydration cache."""
        return await self.batch_quote(chain, addresses, ttl=0)


    async def discover_surface(
        self,
        surface: str,
        allowed_chains: set[str] | list[str] | tuple[str, ...],
        *,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        if surface not in self.DISCOVERY_SURFACES:
            raise ValueError(f"unknown DexScreener discovery surface: {surface}")
        path, role = self.DISCOVERY_SURFACES[surface]
        response = await self.http.get(f"{self.BASE}{path}", ttl=45)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("items") if isinstance(payload.get("items"), list) else [payload]
        if not isinstance(payload, list):
            raise ValueError("DexScreener discovery response must be a list or object")
        allowed = {self._chain(str(chain).lower()) for chain in allowed_chains}
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in payload[: max(1, int(limit))]:
            if not isinstance(item, dict):
                continue
            chain = self._chain(str(item.get("chainId") or "").lower())
            address = str(item.get("tokenAddress") or "").strip()
            if not chain or chain not in allowed or not address:
                continue
            item_rows = self._source_link_rows(
                chain=chain,
                address=address,
                surface=surface,
                role=role,
                raw={"item": item},
                primary_url=item.get("url"),
                links=item.get("links") or [],
            )
            for row in item_rows:
                key = (row["token_id"], row["normalized_url"], row["link_kind"], row["role"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows


class JupiterQuoteClient:
    """Read-only Jupiter Swap API V2 quote client."""

    BASE = "https://api.jup.ag/swap/v2/order"

    def __init__(self, http: HttpClient, api_key: str = ""):
        self.http = http
        self._api_key = str(api_key or "").strip()

    async def quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        *,
        slippage_bps: int = 50,
    ) -> dict[str, Any]:
        input_mint, output_mint = str(input_mint).strip(), str(output_mint).strip()
        amount, slippage_bps = int(amount), int(slippage_bps)
        if not input_mint or not output_mint or amount <= 0:
            raise ValueError("input/output mint and amount are required")
        if slippage_bps < 0 or slippage_bps > 10000:
            raise ValueError("slippage_bps must be between 0 and 10000")
        requested_at = iso(utcnow())
        try:
            response = await self.http.get(
                self.BASE,
                params={
                    "inputMint": input_mint, "outputMint": output_mint,
                    "amount": amount, "slippageBps": slippage_bps,
                },
                headers={"x-api-key": self._api_key} if self._api_key else None,
            )
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                try:
                    exc.response.read()
                    message = exc.response.content.decode("utf-8", errors="replace").casefold()
                except Exception:
                    message = ""
                message = (message + " " + str(exc)).casefold()
                if exc.response.status_code == 400 and (
                    "no route" in message or "no_route" in message or "no route found" in message
                    or "find any route" in message or "failed to get quotes" in message
                ):
                    raise JupiterNoRouteError("Jupiter returned no route") from exc
            raise JupiterQuoteError(f"Jupiter quote failed with HTTP {exc.response.status_code}") from exc
        completed_at = iso(utcnow())
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Jupiter quote response must be an object")
        if any(payload.get(key) for key in ("transaction", "swapTransaction")):
            raise JupiterQuoteProtocolError("Jupiter quote response contains a transaction")
        if (
            str(payload.get("inputMint") or "") != input_mint
            or str(payload.get("outputMint") or "") != output_mint
            or str(payload.get("inAmount") or "") != str(amount)
            or int(payload.get("slippageBps") if payload.get("slippageBps") is not None else -1) != slippage_bps
            or str(payload.get("swapMode") or "ExactIn") != "ExactIn"
            or int(payload.get("outAmount") or 0) <= 0
            or int(payload.get("otherAmountThreshold") or 0) <= 0
            or int(payload.get("otherAmountThreshold") or 0) > int(payload.get("outAmount") or 0)
            or not isinstance(payload.get("routePlan"), list)
            or not payload.get("routePlan")
        ):
            raise JupiterQuoteError("Jupiter quote response does not match the requested route")

        def text(value: Any) -> str | None:
            return str(value) if value is not None else None

        price_impact_bps: float | None = None
        price_impact_source = ""
        raw_price_impact = payload.get("priceImpact")
        raw_price_impact_pct = payload.get("priceImpactPct")
        try:
            if raw_price_impact is not None:
                parsed_impact = float(raw_price_impact)
                if not math.isfinite(parsed_impact):
                    raise ValueError("non-finite price impact")
                # Swap V2 priceImpact is expressed in percentage points.
                price_impact_bps = parsed_impact * 100.0
                price_impact_source = "priceImpact_percentage_points"
            elif raw_price_impact_pct is not None:
                parsed_impact = float(raw_price_impact_pct)
                if not math.isfinite(parsed_impact):
                    raise ValueError("non-finite price impact")
                # Deprecated priceImpactPct is a decimal ratio.
                price_impact_bps = parsed_impact * 10_000.0
                price_impact_source = "priceImpactPct_decimal_ratio"
        except (TypeError, ValueError, OverflowError) as exc:
            raise JupiterQuoteProtocolError("Jupiter price impact is invalid") from exc

        route_plan: list[dict[str, Any]] = []
        for item in payload.get("routePlan") or []:
            if not isinstance(item, dict) or not isinstance(item.get("swapInfo"), dict):
                continue
            swap = item["swapInfo"]
            route_plan.append({
                "percent": item.get("percent"),
                "amm_key": text(swap.get("ammKey")), "label": text(swap.get("label")),
                "input_mint": text(swap.get("inputMint")), "output_mint": text(swap.get("outputMint")),
                "in_amount": text(swap.get("inAmount")), "out_amount": text(swap.get("outAmount")),
                "fee_amount": text(swap.get("feeAmount")), "fee_mint": text(swap.get("feeMint")),
            })
        return {
            "provider": "jupiter", "requested_at": requested_at, "completed_at": completed_at,
            "input_mint": text(payload.get("inputMint")), "in_amount": text(payload.get("inAmount")),
            "output_mint": text(payload.get("outputMint")), "out_amount": text(payload.get("outAmount")),
            "other_amount_threshold": text(payload.get("otherAmountThreshold")),
            "mode": text(payload.get("mode") or payload.get("swapMode")),
            "router": text(payload.get("router")),
            "slippage_bps": payload.get("slippageBps"),
            "price_impact_pct": text(
                raw_price_impact if raw_price_impact is not None else raw_price_impact_pct
            ),
            "price_impact_bps": price_impact_bps,
            "price_impact_source": price_impact_source,
            "fee_bps": payload.get("feeBps"),
            "signature_fee_lamports": payload.get("signatureFeeLamports"),
            "prioritization_fee_lamports": payload.get("prioritizationFeeLamports"),
            "rent_fee_lamports": payload.get("rentFeeLamports"),
            "platform_fee_bps": (
                (payload.get("platformFee") or {}).get("feeBps")
                if isinstance(payload.get("platformFee"), dict) else None
            ),
            "output_amount_raw": text(payload.get("outAmount")),
            "route_plan": route_plan,
            "context_slot": payload.get("contextSlot"),
            "time_taken_ms": payload.get("totalTime")
            if payload.get("totalTime") is not None
            else ((float(payload["timeTaken"]) * 1000) if payload.get("timeTaken") is not None else None),
        }


class RobinhoodStockTokenRegistryClient:
    """Read the official Robinhood Stock Token address registry."""

    SOURCE_URL = "https://api.robinhood.com/rhj/assets"
    CHAIN_ID = 4663

    def __init__(self, http: HttpClient):
        self.http = http

    async def fetch(self) -> dict[str, Any]:
        requested_at = utcnow()
        response = await self.http.get(self.SOURCE_URL, ttl=3_600)
        completed_at = utcnow()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
            raise ValueError("Robinhood Stock Token registry payload is invalid")
        entries: list[dict[str, Any]] = []
        for asset in payload["assets"]:
            if not isinstance(asset, dict):
                continue
            for deployment in asset.get("deployments") or []:
                if not isinstance(deployment, dict) or int(deployment.get("chainId") or 0) != self.CHAIN_ID:
                    continue
                address = str(deployment.get("contractAddress") or "").strip().lower()
                if not re.fullmatch(r"0x[0-9a-f]{40}", address):
                    continue
                entries.append({
                    "asset_id": str(asset.get("id") or "")[:80],
                    "token_symbol": str(asset.get("tokenSymbol") or "")[:40],
                    "token_name": str(asset.get("tokenName") or "")[:200],
                    "contract_address": address,
                    "chain_id": self.CHAIN_ID,
                    "asset_status": str(asset.get("status") or "")[:60],
                })
        if not entries:
            raise ValueError("Robinhood Stock Token registry contains no chain-4663 deployments")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {
            "source_url": self.SOURCE_URL,
            "requested_at": iso(requested_at),
            "completed_at": iso(completed_at),
            "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "asset_count": len(payload["assets"]),
            "entries": entries,
        }


class EvmZeroXPriceClient:
    """Amount-specific 0x Swap v2 observer; never signs or submits transactions."""

    URL = "https://api.0x.org/swap/allowance-holder/price"
    CHAIN_IDS = {"bsc": 56, "base": 8453, "robinhood": 4663}

    def __init__(self, http: HttpClient, api_key: str):
        self.http = http
        self._api_key = str(api_key or "").strip()
        if not self._api_key:
            raise ValueError("0x API key is required")

    @staticmethod
    def _address(value: Any) -> str:
        address = str(value or "").strip().lower()
        if not re.fullmatch(r"0x[0-9a-f]{40}", address):
            raise ValueError("valid EVM address required")
        return address

    @staticmethod
    def _uint(value: Any, field: str, *, allow_zero: bool = False) -> int:
        try:
            number = int(str(value))
        except (TypeError, ValueError) as exc:
            raise EvmRouteQuoteProtocolError(f"0x {field} is invalid") from exc
        if number < 0 or (number == 0 and not allow_zero):
            raise EvmRouteQuoteProtocolError(f"0x {field} is non-positive")
        return number

    @staticmethod
    def _tax_bps(metadata: Any, side: str) -> dict[str, int | None]:
        item = metadata.get(side) if isinstance(metadata, dict) else None
        if not isinstance(item, dict):
            return {"buy_tax_bps": None, "sell_tax_bps": None}
        parsed: dict[str, int | None] = {}
        for source, target in (("buyTaxBps", "buy_tax_bps"), ("sellTaxBps", "sell_tax_bps")):
            try:
                value = int(str(item[source])) if item.get(source) is not None else None
            except (TypeError, ValueError) as exc:
                raise EvmRouteQuoteProtocolError(f"0x {source} is invalid") from exc
            if value is not None and not 0 <= value <= 10_000:
                raise EvmRouteQuoteProtocolError(f"0x {source} is outside bps range")
            parsed[target] = value
        return parsed

    async def price(
        self,
        chain: str,
        sell_token: str,
        buy_token: str,
        sell_amount_raw: int | str,
        *,
        slippage_bps: int = 400,
    ) -> dict[str, Any]:
        chain = str(chain).strip().lower()
        if chain not in self.CHAIN_IDS:
            raise ValueError("unsupported 0x chain")
        sell = self._address(sell_token)
        buy = self._address(buy_token)
        amount = int(sell_amount_raw)
        slippage = int(slippage_bps)
        if amount <= 0 or not 0 <= slippage < 10_000 or sell == buy:
            raise ValueError("valid amount, slippage and distinct tokens required")
        requested_at = iso(utcnow())
        try:
            response = await self.http.client.get(
                self.URL,
                params={
                    "chainId": str(self.CHAIN_IDS[chain]),
                    "sellToken": sell,
                    "buyToken": buy,
                    "sellAmount": str(amount),
                    "slippageBps": str(slippage),
                },
                headers={"0x-api-key": self._api_key, "0x-version": "v2"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise EvmRouteQuoteError("0x price request failed") from exc
        completed_at = iso(utcnow())
        if not isinstance(payload, dict):
            raise EvmRouteQuoteProtocolError("0x price response is not an object")
        if payload.get("liquidityAvailable") is not True:
            return {
                "provider": "0x_swap_v2_price",
                "chain": chain,
                "chain_id": self.CHAIN_IDS[chain],
                "requested_at": requested_at,
                "completed_at": completed_at,
                "status": "no_route",
                "sell_token": sell,
                "buy_token": buy,
                "sell_amount_raw": str(amount),
                "slippage_bps": slippage,
                "decision_eligible": False,
                "affects": "none",
            }
        if self._address(payload.get("sellToken")) != sell or self._address(payload.get("buyToken")) != buy:
            raise EvmRouteQuoteProtocolError("0x token identity mismatch")
        sell_amount = self._uint(payload.get("sellAmount"), "sellAmount")
        buy_amount = self._uint(payload.get("buyAmount"), "buyAmount")
        minimum = self._uint(payload.get("minBuyAmount"), "minBuyAmount")
        if sell_amount != amount or minimum > buy_amount:
            raise EvmRouteQuoteProtocolError("0x amount identity mismatch")
        route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
        fills = route.get("fills") if isinstance(route.get("fills"), list) else []
        clean_fills = [
            {
                "from": self._address(item.get("from")),
                "to": self._address(item.get("to")),
                "source": str(item.get("source") or "")[:80],
                "proportion_bps": self._uint(item.get("proportionBps"), "proportionBps", allow_zero=True),
            }
            for item in fills if isinstance(item, dict)
        ]
        issues = payload.get("issues") if isinstance(payload.get("issues"), dict) else {}
        allowance = issues.get("allowance") if isinstance(issues.get("allowance"), dict) else None
        return {
            "provider": "0x_swap_v2_price",
            "chain": chain,
            "chain_id": self.CHAIN_IDS[chain],
            "requested_at": requested_at,
            "completed_at": completed_at,
            "status": "priced",
            "sell_token": sell,
            "buy_token": buy,
            "sell_amount_raw": str(sell_amount),
            "buy_amount_raw": str(buy_amount),
            "minimum_buy_amount_raw": str(minimum),
            "slippage_bps": slippage,
            "block_number": self._uint(payload.get("blockNumber"), "blockNumber"),
            "gas": self._uint(payload.get("gas"), "gas"),
            "gas_price_raw": str(self._uint(payload.get("gasPrice"), "gasPrice")),
            "total_network_fee_native_raw": str(
                self._uint(payload.get("totalNetworkFee"), "totalNetworkFee", allow_zero=True)
            ),
            "sell_token_tax": self._tax_bps(payload.get("tokenMetadata"), "sellToken"),
            "buy_token_tax": self._tax_bps(payload.get("tokenMetadata"), "buyToken"),
            "allowance_required": allowance is not None,
            "allowance_spender": self._address(allowance.get("spender")) if allowance else None,
            "simulation_incomplete": bool(issues.get("simulationIncomplete")),
            "route": clean_fills,
            "execution_scope": "amount_specific_aggregator_indicative_price",
            "firm_quote": False,
            "transaction_built": False,
            "transaction_submitted": False,
            "decision_eligible": False,
            "affects": "none",
        }


class EvmUniswapV3QuoteClient:
    """Read-only exact-input Uniswap V3 QuoterV2 observer for EVM research lanes."""

    QUOTE_EXACT_INPUT_SELECTOR = "cdca1753"
    GET_POOL_SELECTOR = "1698ee82"
    NETWORKS = {
        "bsc": {
            "chain_id": 56,
            "rpc_url": "https://bsc-dataseed.bnbchain.org",
            "factory": "0xdB1d10011AD0Ff90774D0C6Bb92e5C5c8b4461F7",
            "quoter": "0x78D78E420Da98ad378D7799bE8f4AF69033EB077",
            "accounting_token": "0x55d398326f99059ff775485246999027b3197955",
            "accounting_symbol": "USDT",
            "accounting_decimals": 18,
            "wrapped_native": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "native_symbol": "BNB",
        },
        "base": {
            "chain_id": 8453,
            "rpc_url": "https://mainnet.base.org",
            "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
            "quoter": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
            "accounting_token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "accounting_symbol": "USDC",
            "accounting_decimals": 6,
            "wrapped_native": "0x4200000000000000000000000000000000000006",
            "native_symbol": "ETH",
        },
        "robinhood": {
            "chain_id": 4663,
            "rpc_url": "https://rpc.mainnet.chain.robinhood.com",
            "factory": "0x1f7d7550b1b028f7571e69a784071f0205fd2efa",
            "quoter": "0x33e885ed0ec9bf04ecfb19341582aadcb4c8a9e7",
            "accounting_token": "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168",
            "accounting_symbol": "USDG",
            "accounting_decimals": 6,
            "wrapped_native": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
            "native_symbol": "ETH",
        },
    }
    FEE_TIERS = (100, 500, 3000, 10000)

    def __init__(self, http: HttpClient):
        self.http = http
        self._lock = asyncio.Lock()
        self._request_id = 0
        self._last_request_started = 0.0

    @classmethod
    def public_network_definitions(cls) -> dict[str, dict[str, Any]]:
        return {
            chain: {**values, "fee_tiers": list(cls.FEE_TIERS)}
            for chain, values in cls.NETWORKS.items()
        }

    @staticmethod
    def _address(value: Any) -> str:
        address = str(value or "").strip()
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
            raise ValueError("valid EVM address required")
        return "0x" + address[2:].lower()

    @staticmethod
    def _word(value: int) -> str:
        number = int(value)
        if number < 0 or number >= 2**256:
            raise ValueError("ABI integer outside uint256")
        return f"{number:064x}"

    @classmethod
    def _get_pool_data(cls, token_a: str, token_b: str, fee: int) -> str:
        return "0x" + cls.GET_POOL_SELECTOR + token_a[2:].rjust(64, "0") + token_b[2:].rjust(64, "0") + cls._word(fee)

    @classmethod
    def _quote_data(cls, path: bytes, amount_in: int) -> str:
        encoded_path = path.hex()
        padded_length = ((len(encoded_path) + 63) // 64) * 64
        return (
            "0x" + cls.QUOTE_EXACT_INPUT_SELECTOR
            + cls._word(64) + cls._word(amount_in) + cls._word(len(path))
            + encoded_path.ljust(padded_length, "0")
        )

    @staticmethod
    def _path_bytes(edges: list[tuple[str, int, str]]) -> bytes:
        if not edges:
            raise ValueError("at least one route edge required")
        raw = bytes.fromhex(edges[0][0][2:])
        current = edges[0][0]
        for token_in, fee, token_out in edges:
            if token_in != current or int(fee) < 0 or int(fee) >= 2**24:
                raise ValueError("invalid contiguous Uniswap V3 path")
            raw += int(fee).to_bytes(3, "big") + bytes.fromhex(token_out[2:])
            current = token_out
        return raw

    async def _rpc(self, network: dict[str, Any], method: str, params: list[Any]) -> Any:
        async with self._lock:
            interval = max(0.0, float(self.http.min_host_interval))
            wait = interval - (time.monotonic() - self._last_request_started)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_started = time.monotonic()
            self._request_id += 1
            request_id = self._request_id
            try:
                response = await self.http.client.post(
                    str(network["rpc_url"]),
                    json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
                )
                response.raise_for_status()
            except Exception as exc:
                raise EvmRouteQuoteError(f"EVM RPC {method} failed") from exc
            try:
                payload = response.json()
            except Exception as exc:
                raise EvmRouteQuoteProtocolError("EVM RPC returned malformed JSON") from exc
        if not isinstance(payload, dict) or payload.get("id") != request_id:
            raise EvmRouteQuoteProtocolError("EVM RPC response identity mismatch")
        if isinstance(payload.get("error"), dict):
            error = payload["error"]
            message = str(error.get("message") or "EVM RPC error")
            normalized = message.lower()
            if method == "eth_call" and (
                "revert" in normalized or "execution reverted" in normalized
            ):
                raise EvmRouteExecutionReverted(message)
            raise EvmRouteRpcError(message)
        if "result" not in payload:
            raise EvmRouteQuoteProtocolError("EVM RPC result missing")
        return payload["result"]

    async def _call(
        self,
        network: dict[str, Any],
        to: str,
        data: str,
        block_tag: str,
        *,
        allow_revert: bool = False,
    ) -> str | None:
        try:
            result = await self._rpc(network, "eth_call", [{"to": to, "data": data}, block_tag])
        except EvmRouteExecutionReverted:
            if allow_revert:
                return None
            raise
        if not isinstance(result, str) or not result.startswith("0x"):
            raise EvmRouteQuoteProtocolError("eth_call returned invalid data")
        return result

    async def _pool(
        self,
        network: dict[str, Any],
        token_a: str,
        token_b: str,
        fee: int,
        block_tag: str,
    ) -> str | None:
        result = await self._call(
            network,
            str(network["factory"]),
            self._get_pool_data(token_a, token_b, fee),
            block_tag,
        )
        assert result is not None
        body = result[2:]
        if len(body) < 64:
            raise EvmRouteQuoteProtocolError("factory getPool result too short")
        address = "0x" + body[-40:].lower()
        return None if int(address, 16) == 0 else address

    async def _quote_path(
        self,
        network: dict[str, Any],
        edges: list[tuple[str, int, str]],
        amount_in: int,
        block_tag: str,
    ) -> tuple[int, int] | None:
        result = await self._call(
            network,
            str(network["quoter"]),
            self._quote_data(self._path_bytes(edges), amount_in),
            block_tag,
            allow_revert=True,
        )
        if result is None:
            return None
        body = result[2:]
        if len(body) < 256 or len(body) % 64:
            raise EvmRouteQuoteProtocolError("QuoterV2 result shape invalid")
        amount_out = int(body[0:64], 16)
        gas_estimate = int(body[192:256], 16)
        if amount_out <= 0 or gas_estimate <= 0:
            raise EvmRouteQuoteProtocolError("QuoterV2 returned non-positive output")
        return amount_out, gas_estimate

    async def quote_round_trip(
        self,
        chain: str,
        token_address: str,
        input_amount_raw: int,
        *,
        slippage_bps: int = 400,
    ) -> dict[str, Any]:
        chain = str(chain).strip().lower()
        if chain not in self.NETWORKS:
            raise ValueError("unsupported EVM route research chain")
        network = dict(self.NETWORKS[chain])
        token = self._address(token_address)
        stable = self._address(network["accounting_token"])
        wrapped = self._address(network["wrapped_native"])
        amount_in = int(input_amount_raw)
        slippage = int(slippage_bps)
        if amount_in <= 0 or slippage < 0 or slippage >= 10_000:
            raise ValueError("positive amount and valid slippage required")
        if token in {stable, wrapped}:
            raise ValueError("target token must differ from route base assets")

        requested_at = iso(utcnow())
        chain_id = int(await self._rpc(network, "eth_chainId", []), 16)
        if chain_id != int(network["chain_id"]):
            raise EvmRouteQuoteProtocolError("EVM RPC chain mismatch")
        block_tag = str(await self._rpc(network, "eth_blockNumber", []))
        block = await self._rpc(network, "eth_getBlockByNumber", [block_tag, False])
        if not isinstance(block, dict) or not block.get("hash") or not block.get("timestamp"):
            raise EvmRouteQuoteProtocolError("EVM block context missing")
        for address in (network["factory"], network["quoter"]):
            code = await self._rpc(network, "eth_getCode", [address, block_tag])
            if not isinstance(code, str) or code in {"0x", "0x0"}:
                raise EvmRouteQuoteProtocolError("official Uniswap contract code missing")

        pool_cache: dict[tuple[str, str, int], str | None] = {}

        async def route_pools(edges: list[tuple[str, int, str]]) -> list[str] | None:
            pools: list[str] = []
            for token_in, fee, token_out in edges:
                key = (token_in, token_out, int(fee))
                if key not in pool_cache:
                    pool_cache[key] = await self._pool(
                        network, token_in, token_out, int(fee), block_tag
                    )
                if pool_cache[key] is None:
                    return None
                pools.append(str(pool_cache[key]))
            return pools

        paired: list[dict[str, Any]] = []
        buy_pool_seen = False
        buy_quote_seen = False
        candidates: list[list[tuple[str, int, str]]] = [
            [(stable, fee, token)] for fee in self.FEE_TIERS
        ]
        candidates.extend(
            [(stable, first_fee, wrapped), (wrapped, second_fee, token)]
            for first_fee in self.FEE_TIERS
            for second_fee in self.FEE_TIERS
        )
        for edges in candidates:
                pools = await route_pools(edges)
                if pools is None:
                    continue
                buy_pool_seen = True
                buy = await self._quote_path(network, edges, amount_in, block_tag)
                if buy is None:
                    continue
                buy_quote_seen = True
                buy_output, buy_gas = buy
                minimum = buy_output * (10_000 - slippage) // 10_000
                if minimum <= 0:
                    continue
                reverse = [(out_token, edge_fee, in_token) for in_token, edge_fee, out_token in reversed(edges)]
                sell = await self._quote_path(network, reverse, minimum, block_tag)
                if sell is None:
                    continue
                sell_output, sell_gas = sell
                sell_minimum = sell_output * (10_000 - slippage) // 10_000
                if sell_minimum <= 0:
                    continue
                paired.append({
                    "buy_output_raw": str(buy_output),
                    "buy_minimum_output_raw": str(minimum),
                    "sell_output_raw": str(sell_output),
                    "sell_minimum_output_raw": str(sell_minimum),
                    "buy_quoter_gas_estimate": buy_gas,
                    "sell_quoter_gas_estimate": sell_gas,
                    "buy_path": [
                        {"token_in": a, "token_out": b, "fee_tier": f, "pool": pools[index]}
                        for index, (a, f, b) in enumerate(edges)
                    ],
                    "sell_path": [
                        {"token_in": a, "token_out": b, "fee_tier": f, "pool": pools[-1-index]}
                        for index, (a, f, b) in enumerate(reverse)
                    ],
                })

        final_block = await self._rpc(network, "eth_getBlockByNumber", [block_tag, False])
        if (
            not isinstance(final_block, dict)
            or str(final_block.get("hash") or "").lower()
            != str(block["hash"]).lower()
        ):
            raise EvmRouteQuoteProtocolError("EVM fixed block hash changed during quote")
        completed_at = iso(utcnow())
        best = max(paired, key=lambda item: int(item["sell_output_raw"])) if paired else None
        status = (
            "quoted" if best is not None
            else "sell_quote_unavailable" if buy_quote_seen
            else "buy_quote_unavailable" if buy_pool_seen
            else "no_official_pool"
        )
        return {
            "provider": "uniswap_v3_quoter_v2",
            "chain": chain,
            "chain_id": chain_id,
            "requested_at": requested_at,
            "completed_at": completed_at,
            "block_number": int(block_tag, 16),
            "block_hash": str(block["hash"]),
            "block_timestamp": iso(datetime.fromtimestamp(int(str(block["timestamp"]), 16), tz=utcnow().tzinfo)),
            "input_token": stable,
            "accounting_symbol": str(network["accounting_symbol"]),
            "accounting_decimals": int(network["accounting_decimals"]),
            "output_token": token,
            "input_amount_raw": str(amount_in),
            "slippage_bps": slippage,
            "status": status,
            "buy_output_raw": best["buy_output_raw"] if best else None,
            "buy_minimum_output_raw": best["buy_minimum_output_raw"] if best else None,
            "sell_output_raw": best["sell_output_raw"] if best else None,
            "sell_minimum_output_raw": best["sell_minimum_output_raw"] if best else None,
            "buy_quoter_gas_estimate": best["buy_quoter_gas_estimate"] if best else None,
            "sell_quoter_gas_estimate": best["sell_quoter_gas_estimate"] if best else None,
            "buy_path": best["buy_path"] if best else [],
            "sell_path": best["sell_path"] if best else [],
            "immediate_round_trip_stable_ratio": (
                int(best["sell_minimum_output_raw"]) / amount_in if best else None
            ),
            "venue_fee_semantics": "uniswap_v3_fee_tier_embedded_in_amount_out",
            "fee_completeness": "quote_only_no_full_transaction_network_fee",
            "economic_status": "cost_unknown",
            "execution_scope": "pool_math_quote_only",
            "transfer_semantics_checked": False,
            "router_transaction_simulated": False,
            "decision_eligible": False,
            "affects": "none",
        }


class SolanaHeldAccountCollector:
    """Subscribe only to exact accounts of currently held canonical PumpSwap positions."""

    MAX_MULTIPLE_ACCOUNTS = 100

    def __init__(self, rpc_url: str, *, refresh_seconds: float = 5.0):
        self.rpc_url = str(rpc_url)
        parsed = urllib.parse.urlparse(str(rpc_url))
        scheme = "wss" if parsed.scheme == "https" else "ws"
        self.url = urllib.parse.urlunparse(
            (scheme, parsed.netloc, parsed.path or "/", "", parsed.query, "")
        )
        # PublicNode rejects getMultipleAccounts requests containing more than
        # ten keys with HTTP 403.  Keep the upstream limit for other RPCs.
        self.max_multiple_accounts = (
            10 if parsed.netloc.casefold().endswith("publicnode.com")
            else self.MAX_MULTIPLE_ACCOUNTS
        )
        self.refresh_seconds = max(1.0, float(refresh_seconds))
        self.http = httpx.AsyncClient(timeout=15.0)

    @staticmethod
    def _rpc_error_reason(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTPStatusError:{exc.response.status_code}"
        return type(exc).__name__

    async def close(self) -> None:
        await self.http.aclose()

    async def sample_pumpswap_participation(
        self, pool: Mapping[str, Any], frontier: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Bounded confirmed signer sampling plus actual SPL transfer evidence."""
        address = str(pool["pool_address"])
        started = utcnow()
        result: dict[str, Any] = {"started_at": iso(started), "complete": False,
            "status": "UNKNOWN_RPC", "trades": [], "frontier": dict(frontier or {}),
            "identity_unit": "signer_address_not_human", "decoder": "pump-amm-participation/v2",
            "coverage_complete": False, "truncated": False,
            "coverage_start": (frontier or {}).get("block_time"), "coverage_end": None}

        async def rpc(method, params):
            response = await self.http.post(self.rpc_url, json={
                "jsonrpc": "2.0", "id": 50_001, "method": method, "params": params,
            })
            response.raise_for_status()
            payload = response.json()
            if payload.get("error") or "result" not in payload:
                raise ValueError("participation_rpc_error")
            return payload["result"]

        try:
            options = {"limit": 1 if frontier is None else 10, "commitment": "confirmed",
                "minContextSlot": max(int(pool["resolved_slot"]), int((frontier or {}).get("slot") or 0))}
            if frontier and frontier.get("signature"):
                options["until"] = frontier["signature"]
            signatures = await rpc("getSignaturesForAddress", [address, options])
            if not isinstance(signatures, list):
                raise ValueError("participation_signature_shape")
            head = signatures[0] if signatures else frontier or {"signature": None, "slot": pool["resolved_slot"]}
            result["frontier"] = {"signature": head.get("signature"), "slot": int(head["slot"]),
                                  "block_time": head.get("blockTime", head.get("block_time"))}
            result["coverage_end"] = result["frontier"]["block_time"]
            if frontier is None:
                result["status"] = "SEEDED_NO_WINDOW"
            elif len(signatures) >= 10:
                # Advance explicitly over a discarded interval, never fabricate its breadth.
                result["status"] = "TRUNCATED_INCOMPLETE"
                result["truncated"] = True
            else:
                trades = []
                complete = True
                for item in reversed(signatures):
                    if item.get("err") is not None:
                        continue  # Observed failed transaction, not a missing trade.
                    if not frontier.get("signature") and int(item["slot"]) <= int(frontier["slot"]):
                        continue
                    tx = await rpc("getTransaction", [item["signature"], {
                        "commitment": "confirmed", "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
                    }])
                    parsed, valid = self._pumpswap_participation_instructions(tx, item, pool)
                    received_at = iso(utcnow())
                    for trade in parsed:
                        trade.update(observed_at=received_at, recorded_at=received_at)
                    complete = complete and valid
                    trades.extend(parsed)
                result.update(complete=complete, status="COMPLETE" if complete else "INCOMPLETE_DISCARDED",
                    trades=trades if complete else [])
                coverage_start, coverage_end = result["coverage_start"], result["coverage_end"]
                result["coverage_complete"] = (complete and type(coverage_start) is int
                    and type(coverage_end) is int and coverage_start < coverage_end
                    and all(type(trade.get("block_time")) is int
                            and coverage_start < trade["block_time"] <= coverage_end for trade in trades))
        except Exception as exc:
            result.update(status="UNKNOWN_RPC", complete=False, trades=[], reason=self._rpc_error_reason(exc))
        result["completed_at"] = iso(utcnow())
        result.update(observed_at=result["completed_at"], recorded_at=result["completed_at"])
        return result

    @staticmethod
    def _pumpswap_participation_instructions(tx, signature, pool):
        """Count exact verified BUY instructions; balances are not per-instruction fills."""
        if (not isinstance(tx, Mapping) or not isinstance(tx.get("meta"), Mapping)
                or tx["meta"].get("err") is not None or tx.get("slot") != signature.get("slot")):
            return [], False
        transaction = tx.get("transaction") or {}
        if not transaction.get("signatures") or transaction["signatures"][0] != signature["signature"]:
            return [], False
        message = transaction.get("message") or {}
        signers = {k["pubkey"] for k in message.get("accountKeys", []) if isinstance(k, Mapping) and k.get("signer") is True}
        instructions = [(f"outer:{i}", ix) for i, ix in enumerate(message.get("instructions", []))]
        instructions.extend((f"inner:{group['index']}:{i}", ix)
            for group in tx["meta"].get("innerInstructions") or [] for i, ix in enumerate(group.get("instructions", [])))
        # BUY's trailing OptionBool(track_volume) may be absent on legacy
        # successful calls (e.g. mainnet 3QD3KZ...HXCgrAN, slot 444576018).
        # Official pump_amm IDL encodes the present OptionBool as one bool.
        types = {bytes((102,6,61,18,1,218,235,234)): ("BUY", (24, 25)),
            bytes((198,46,21,82,180,217,232,112)): ("BUY", (24, 25)),
            bytes((51,230,133,164,1,127,131,173)): ("SELL", (24,))}
        liquidity_ops = {bytes((242,35,198,137,82,225,242,182)), bytes((183,18,70,156,148,109,161,34))}
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        trades, lp_seen = [], False
        expected = {0: pool["pool_address"], 2: PUMPSWAP_GLOBAL_CONFIG_PDA, 3: pool["base_mint"],
            4: pool["quote_mint"], 7: pool["base_vault"], 8: pool["quote_vault"],
            11: pool["base_token_program"], 12: pool["quote_token_program"]}
        for path, ix in instructions:
            accounts = ix.get("accounts") or []
            if ix.get("programId") != PUMP_AMM_PROGRAM_ID or pool["pool_address"] not in accounts:
                continue
            try:
                encoded = ix["data"]
                number = 0
                for char in encoded:
                    number = number * 58 + alphabet.index(char)
                raw = bytes(len(encoded) - len(encoded.lstrip("1"))) + number.to_bytes((number.bit_length() + 7) // 8, "big")
            except (KeyError, ValueError, TypeError):
                return [], False
            if raw[:8] in liquidity_ops:
                lp_seen = True
                continue
            operation = types.get(raw[:8])
            if (operation is None or len(raw) not in operation[1]
                    or (len(raw) == 25 and raw[24] not in (0, 1)) or len(accounts) < 13
                    or any(accounts[i] != value for i, value in expected.items())
                    or accounts[1] not in signers or accounts[1] in expected.values()):
                return [], False
            trade = {"signature": signature["signature"], "slot": signature["slot"],
                "block_time": tx.get("blockTime", signature.get("blockTime")),
                "instruction_path": path, "side": operation[0], "signer_address": accounts[1],
                "amount_complete": False, "pool_address": pool["pool_address"],
                "base_mint": pool["base_mint"], "quote_mint": pool["quote_mint"]}
            # Instruction amounts are limits (maxQuoteIn/minQuoteOut), not fills.
            # Only attach actual amounts when the transaction contains one
            # unambiguous pair of parsed SPL transfers for this swap.
            actual = SolanaHeldAccountCollector._pumpswap_actual_transfer_amounts(
                tx, accounts[1], pool, operation[0], path)
            if actual is not None:
                trade.update(actual, amount_complete=True,
                    amount_source="parsed_spl_transfer")
            trades.append(trade)
        return ([], False) if lp_seen and trades else (trades, True)

    @staticmethod
    def _pumpswap_actual_transfer_amounts(tx, signer, pool, side, instruction_path):
        """Exact vault-to-user SPL transfers, never limits or net balance deltas."""
        transaction = tx.get("transaction") or {}
        message = transaction.get("message") or {}
        meta = tx.get("meta") or {}
        outer = message.get("instructions", [])
        try:
            path = instruction_path.split(":")
            outer_index = int(path[1])
            group = next((group["instructions"] for group in meta.get("innerInstructions") or []
                          if group.get("index") == outer_index), [])
            if path[0] == "outer" and len(path) == 2:
                if outer[outer_index].get("programId") != PUMP_AMM_PROGRAM_ID:
                    return None
                # A nested PumpSwap call would make attribution ambiguous.
                if any(ix.get("programId") == PUMP_AMM_PROGRAM_ID
                       and pool["pool_address"] in (ix.get("accounts") or []) for ix in group):
                    return None
                selected = group
            elif path[0] == "inner" and len(path) == 3:
                index = int(path[2])
                swap = group[index]
                height = swap.get("stackHeight")
                if swap.get("programId") != PUMP_AMM_PROGRAM_ID or type(height) is not int:
                    return None
                selected = []
                for ix in group[index + 1:]:
                    depth = ix.get("stackHeight")
                    if type(depth) is not int:
                        return None
                    if depth <= height:
                        break
                    if (ix.get("programId") == PUMP_AMM_PROGRAM_ID
                            and pool["pool_address"] in (ix.get("accounts") or [])):
                        return None
                    selected.append(ix)
            else:
                return None
        except (ValueError, IndexError, KeyError, TypeError):
            return None

        base, quote = str(pool["base_mint"]), str(pool["quote_mint"])
        bv, qv = str(pool["base_vault"]), str(pool["quote_vault"])
        mints, owners = {bv: base, qv: quote}, {}
        keys = message.get("accountKeys", [])
        for balance in list(meta.get("preTokenBalances") or []) + list(meta.get("postTokenBalances") or []):
            try:
                key = keys[int(balance["accountIndex"])]
                address = key.get("pubkey") if isinstance(key, Mapping) else key
                mint, owner = balance["mint"], balance.get("owner")
                if address in mints and mints[address] != mint:
                    return None
                if owner is not None and address in owners and owners[address] != owner:
                    return None
                mints[address] = mint
                if owner is not None:
                    owners[address] = owner
            except (KeyError, IndexError, TypeError, ValueError):
                return None
        # Wrapped SOL accounts created and closed within this transaction are
        # absent from pre/post balances. Their earlier SPL initialization is
        # direct mint/owner evidence, unlike a guessed signer ATA relationship.
        prior_instructions = list(outer[:outer_index])
        prior_instructions.extend(ix for prior in meta.get("innerInstructions") or []
                                  if prior.get("index", outer_index) < outer_index
                                  for ix in prior.get("instructions", []))
        if path[0] == "inner":
            prior_instructions.extend(group[:index])
        for ix in prior_instructions:
            parsed = ix.get("parsed") or {}
            if (ix.get("programId") not in {SPL_TOKEN_PROGRAM_ID, SPL_TOKEN_2022_PROGRAM_ID}
                    or parsed.get("type") not in {"initializeAccount", "initializeAccount2", "initializeAccount3"}):
                continue
            info = parsed.get("info") or {}
            address, mint, owner = info.get("account"), info.get("mint"), info.get("owner")
            if not address or not mint or not owner:
                return None
            expected_program = pool.get("base_token_program" if mint == base else "quote_token_program")
            if mint not in {base, quote}:
                continue
            if (ix["programId"] != expected_program or mints.get(address, mint) != mint
                    or owners.get(address, owner) != owner):
                return None
            mints[address], owners[address] = mint, owner
        def is_user(address):
            return owners.get(address) == signer

        base_hits, quote_hits = [], []
        for ix in selected:
            parsed = ix.get("parsed") if isinstance(ix, Mapping) else None
            if not isinstance(parsed, Mapping) or parsed.get("type") not in {
                    "transfer", "transferChecked"}:
                continue
            info = parsed.get("info") or {}
            source, destination = info.get("source"), info.get("destination")
            if not ({source, destination} & {bv, qv}):
                continue  # Separate fee transfers are not pool quote notional.
            program = ix.get("programId")
            if program not in {SPL_TOKEN_PROGRAM_ID, SPL_TOKEN_2022_PROGRAM_ID}:
                return None
            mint = info.get("mint") or mints.get(source) or mints.get(destination)
            if not mint or any(mints.get(address, mint) != mint for address in (source, destination)):
                return None
            expected_program = pool.get("base_token_program" if mint == base else "quote_token_program")
            if expected_program != program:
                return None
            amount = info.get("amount", (info.get("tokenAmount") or {}).get("amount"))
            if isinstance(amount, bool) or not isinstance(amount, (int, str)):
                return None
            if isinstance(amount, str) and (not amount.isascii() or not amount.isdigit()):
                return None
            amount = int(amount)
            if not 0 < amount <= 2**64 - 1:
                return None
            if mint == base:
                valid = ((source == bv and is_user(destination)) if side == "BUY"
                         else (is_user(source) and destination == bv))
                if not valid:
                    return None
                base_hits.append(amount)
            elif mint == quote:
                valid = ((is_user(source) and destination == qv) if side == "BUY"
                         else (source == qv and is_user(destination)))
                if not valid:
                    return None
                quote_hits.append(amount)
            else:
                return None
        if side not in {"BUY", "SELL"} or len(base_hits) != 1 or len(quote_hits) != 1:
            return None
        return {"base_amount_raw": base_hits[0], "quote_amount_raw": quote_hits[0]}

    async def resolve_pumpswap_shadow_pools(
        self, candidates: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Resolve exact PumpSwap identities and baselines without creating a quote."""
        outcomes: list[dict[str, Any]] = []
        for offset in range(0, len(candidates), self.max_multiple_accounts):
            batch = candidates[offset:offset + self.max_multiple_accounts]
            pool_keys = [str(item["pool_address"]) for item in batch]
            try:
                response = await self.http.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0", "id": offset + 30_000,
                        "method": "getMultipleAccounts",
                        "params": [
                            pool_keys,
                            {"encoding": "base64", "commitment": "confirmed"},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("result") if isinstance(payload, Mapping) else None
                values = result.get("value") if isinstance(result, Mapping) else None
                if not isinstance(values, list) or len(values) != len(batch):
                    raise ValueError("vault_shadow_pool_bundle_invalid")
            except Exception as exc:
                outcomes.extend({
                    **dict(item), "status": "UNKNOWN_RPC",
                    "reason": self._rpc_error_reason(exc),
                } for item in batch)
                continue
            for candidate, value in zip(batch, values):
                try:
                    pool = self.decode_account({
                        **dict(candidate),
                        "account_kind": "pool",
                        "decoder_version": PUMPSWAP_POOL_DECODER_V2,
                        "expected_program_owner": PUMP_AMM_PROGRAM_ID,
                    }, value if isinstance(value, Mapping) else None)
                    if pool.get("status") != "verified":
                        raise PermissionError(
                            str(pool.get("reason") or "pool_identity_invalid")
                        )
                    if (
                        bool(pool.get("needs_sdk_extend"))
                        or int(pool.get("account_data_length") or 0)
                        < PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD
                    ):
                        raise PermissionError("pumpswap_current_fields_unavailable")
                    base_mint = str(pool["base_mint"])
                    if base_mint != str(candidate.get("base_mint") or ""):
                        raise PermissionError("pool_base_mint_mismatch")
                    quote_mint = str(pool["quote_mint"])
                    lp_mint = str(pool["lp_mint"])
                    base_vault = str(pool["base_vault"])
                    quote_vault = str(pool["quote_vault"])
                    keys = [
                        str(candidate["pool_address"]), base_vault, quote_vault,
                        base_mint, quote_mint,
                    ]
                    bundle_response = await self.http.post(
                        self.rpc_url,
                        json={
                            "jsonrpc": "2.0", "id": offset + 40_000,
                            "method": "getMultipleAccounts",
                            "params": [
                                keys,
                                {"encoding": "base64", "commitment": "confirmed"},
                            ],
                        },
                    )
                    bundle_response.raise_for_status()
                    bundle_payload = bundle_response.json()
                    bundle_result = (
                        bundle_payload.get("result")
                        if isinstance(bundle_payload, Mapping) else None
                    )
                    bundle_values = (
                        bundle_result.get("value")
                        if isinstance(bundle_result, Mapping) else None
                    )
                    resolved_slot = int(
                        (bundle_result.get("context") or {}).get("slot") or 0
                    ) if isinstance(bundle_result, Mapping) else 0
                    if (
                        not isinstance(bundle_values, list)
                        or len(bundle_values) != len(keys)
                        or resolved_slot <= 0
                    ):
                        raise ValueError("vault_shadow_identity_bundle_invalid")
                    accounts = dict(zip(keys, bundle_values))
                    base_mint_fact = self.decode_account(
                        {"account_kind": "token_mint"}, accounts[base_mint]
                    )
                    quote_mint_fact = self.decode_account(
                        {"account_kind": "token_mint"}, accounts[quote_mint]
                    )
                    allowed_programs = {
                        SPL_TOKEN_PROGRAM_ID, SPL_TOKEN_2022_PROGRAM_ID,
                    }
                    if (
                        base_mint_fact.get("status") != "verified"
                        or quote_mint_fact.get("status") != "verified"
                        or str(base_mint_fact.get("owner") or "") not in allowed_programs
                        or str(quote_mint_fact.get("owner") or "") not in allowed_programs
                    ):
                        raise PermissionError("mint_identity_invalid")
                    base_program = str(base_mint_fact["owner"])
                    quote_program = str(quote_mint_fact["owner"])
                    exact_pool = self.decode_account({
                        "account_kind": "pool",
                        "decoder_version": PUMPSWAP_POOL_DECODER_V2,
                        "expected_program_owner": PUMP_AMM_PROGRAM_ID,
                        "base_mint": base_mint,
                        "quote_mint": quote_mint,
                        "lp_mint": lp_mint,
                        "base_vault": base_vault,
                        "quote_vault": quote_vault,
                    }, accounts[str(candidate["pool_address"])])
                    base_vault_fact = self.decode_account({
                        "account_kind": "base_vault",
                        "expected_mint": base_mint,
                        "expected_program_owner": base_program,
                        "pool_address": str(candidate["pool_address"]),
                    }, accounts[base_vault])
                    quote_vault_fact = self.decode_account({
                        "account_kind": "quote_vault",
                        "expected_mint": quote_mint,
                        "expected_program_owner": quote_program,
                        "pool_address": str(candidate["pool_address"]),
                    }, accounts[quote_vault])
                    required = (exact_pool, base_vault_fact, quote_vault_fact)
                    if any(item.get("status") != "verified" for item in required):
                        raise PermissionError("pool_or_vault_identity_invalid")
                    if (
                        bool(exact_pool.get("needs_sdk_extend"))
                        or int(exact_pool.get("account_data_length") or 0)
                        < PUMPSWAP_POOL_SDK_EXTEND_THRESHOLD
                    ):
                        raise PermissionError("pumpswap_current_fields_unavailable")
                    from solders.pubkey import Pubkey
                    creator = Pubkey.from_string(str(exact_pool["creator"]))
                    base_key = Pubkey.from_string(base_mint)
                    canonical_creator = Pubkey.find_program_address(
                        [b"pool-authority", bytes(base_key)], Pubkey.from_string(PUMP_PROGRAM_ID),
                    )[0]
                    pool_pda = Pubkey.find_program_address([
                        b"pool", int(exact_pool["index"]).to_bytes(2, "little"),
                        bytes(creator), bytes(base_key), bytes(Pubkey.from_string(quote_mint)),
                    ], Pubkey.from_string(PUMP_AMM_PROGRAM_ID))[0]
                    outcomes.append({
                        **dict(candidate),
                        "status": "RESOLVED",
                        "reason": "",
                        "canonical_migration_pool": (
                            int(exact_pool["index"]) == 0 and creator == canonical_creator
                            and str(pool_pda) == str(candidate["pool_address"])
                        ),
                        "base_mint": base_mint,
                        "quote_mint": quote_mint,
                        "lp_mint": lp_mint,
                        "base_vault": base_vault,
                        "quote_vault": quote_vault,
                        "base_token_program": base_program,
                        "quote_token_program": quote_program,
                        "base_mint_decimals": int(base_mint_fact["decimals"]),
                        "virtual_quote_reserves_raw": int(
                            exact_pool.get("virtual_quote_reserves_raw") or 0
                        ),
                        "baseline_base_raw": int(base_vault_fact["amount_raw"]),
                        "baseline_quote_raw": int(quote_vault_fact["amount_raw"]),
                        "resolved_slot": resolved_slot,
                        "resolved_at": iso(utcnow()),
                    })
                except PermissionError as exc:
                    outcomes.append({
                        **dict(candidate), "status": "UNKNOWN_IDENTITY",
                        "reason": str(exc),
                    })
                except Exception as exc:
                    outcomes.append({
                        **dict(candidate), "status": "UNKNOWN_RPC",
                        "reason": self._rpc_error_reason(exc),
                    })
        return outcomes

    async def _initial_updates(
        self, targets: list[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        grouped: list[list[Mapping[str, Any]]] = []
        by_pool: dict[int, list[Mapping[str, Any]]] = {}
        for target in targets:
            pool_target_id = int(target.get("pool_target_id") or 0)
            if pool_target_id:
                by_pool.setdefault(pool_target_id, []).append(target)
            else:
                grouped.append([target])
        grouped.extend(by_pool[key] for key in sorted(by_pool))
        batches: list[list[Mapping[str, Any]]] = []
        for group in grouped:
            if len(group) > self.max_multiple_accounts:
                raise ValueError("held_account_identity_group_exceeds_rpc_batch")
            if not batches or len(batches[-1]) + len(group) > self.max_multiple_accounts:
                batches.append([])
            batches[-1].extend(group)
        for batch_index, batch in enumerate(batches):
            response = await self.http.post(
                self.rpc_url,
                json={
                    "jsonrpc": "2.0", "id": batch_index + 1,
                    "method": "getMultipleAccounts",
                    "params": [
                        [str(target["pubkey"]) for target in batch],
                        {"encoding": "base64", "commitment": "confirmed"},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") if isinstance(payload, Mapping) else None
            values = result.get("value") if isinstance(result, Mapping) else None
            if not isinstance(values, list) or len(values) != len(batch):
                raise ValueError("held account baseline response is invalid")
            slot = int((result.get("context") or {}).get("slot") or 0)
            observed_at = iso(utcnow())
            for target, value in zip(batch, values):
                decoded = self.decode_account(
                    target, value if isinstance(value, Mapping) else None
                )
                encoded = value.get("data") if isinstance(value, Mapping) else None
                digest_payload = encoded[0] if isinstance(encoded, list) and encoded else ""
                updates.append({
                    **dict(target),
                    "slot": slot,
                    "data_hash": hashlib.sha256(str(digest_payload).encode()).hexdigest(),
                    "decoded": decoded,
                    "observed_at": observed_at,
                })
        return updates

    async def bonding_curve_quotes(
        self,
        surfaces: list[Mapping[str, Any]],
        *,
        slippage_bps: int = 400,
        wsol_usdc_conversion: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Quote exact current Pump bonding-curve exits from one coherent RPC read."""
        if not surfaces:
            return []
        from solders.pubkey import Pubkey

        results: list[dict[str, Any]] = []
        pump_program = Pubkey.from_string(PUMP_PROGRAM_ID)
        surface_batch_size = max(1, self.max_multiple_accounts - 2)
        for offset in range(0, len(surfaces), surface_batch_size):
            batch = surfaces[offset:offset + surface_batch_size]
            requested_at = utcnow()
            pubkeys = list(dict.fromkeys([
                PUMP_GLOBAL_PDA,
                PUMP_FEE_CONFIG_PDA,
                *(str(surface["curve_address"]) for surface in batch),
            ]))
            try:
                response = await self.http.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0", "id": offset // surface_batch_size + 20_000,
                        "method": "getMultipleAccounts",
                        "params": [pubkeys, {"encoding": "base64", "commitment": "confirmed"}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("result") if isinstance(payload, Mapping) else None
                values = result.get("value") if isinstance(result, Mapping) else None
                slot = int((result.get("context") or {}).get("slot") or 0) if isinstance(result, Mapping) else 0
                if not isinstance(values, list) or len(values) != len(pubkeys) or slot <= 0:
                    raise ValueError("pump_curve_account_bundle_invalid")
                accounts = dict(zip(pubkeys, values))
            except Exception as exc:
                completed_at = utcnow()
                for surface in batch:
                    results.append({
                        **dict(surface), "context_slot": 0,
                        "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                        "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                        "status": "LOCAL_UNKNOWN_RPC", "reason": self._rpc_error_reason(exc),
                        "source_hashes": {}, "surface_type": "pump_bonding_curve",
                    })
                continue

            def decode(pubkey: str, target: Mapping[str, Any]) -> dict[str, Any]:
                return self.decode_account(target, accounts.get(pubkey))

            global_config = decode(PUMP_GLOBAL_PDA, {
                "account_kind": "pump_global",
                "expected_program_owner": PUMP_PROGRAM_ID,
            })
            fee_config = decode(PUMP_FEE_CONFIG_PDA, {
                "account_kind": "fee_config",
                "expected_program_owner": PUMP_FEE_PROGRAM_ID,
            })
            for surface in batch:
                completed_at = utcnow()
                quote_mint = SOLANA_WRAPPED_SOL_MINT
                curve_address = str(surface["curve_address"])
                source_hashes: dict[str, str] = {}
                for pubkey in (curve_address, PUMP_GLOBAL_PDA, PUMP_FEE_CONFIG_PDA):
                    value = accounts.get(pubkey)
                    encoded = value.get("data") if isinstance(value, Mapping) else None
                    body = encoded[0] if isinstance(encoded, list) and encoded else ""
                    source_hashes[pubkey] = hashlib.sha256(str(body).encode()).hexdigest()
                common = {
                    **dict(surface), "pool_address": curve_address,
                    "surface_type": "pump_bonding_curve", "context_slot": slot,
                    "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                    "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                    "source_hashes": source_hashes,
                }
                try:
                    mint = Pubkey.from_string(str(surface["base_mint"]))
                    expected_curve = str(Pubkey.find_program_address(
                        [b"bonding-curve", bytes(mint)], pump_program,
                    )[0])
                    if curve_address != expected_curve or (
                        str(surface.get("source_pair_address") or "")
                        and str(surface.get("source_pair_address")) != expected_curve
                    ):
                        raise PermissionError("bonding_curve_identity_mismatch")
                    curve = decode(curve_address, {
                        "account_kind": "bonding_curve",
                        "expected_program_owner": PUMP_PROGRAM_ID,
                    })
                    required = (curve, global_config)
                    if any(item.get("status") == "missing" for item in required):
                        raise LookupError("required_account_missing")
                    if any(item.get("status") != "verified" for item in required):
                        raise PermissionError("required_account_identity_invalid")
                    if fee_config.get("status") not in {"verified", "missing"}:
                        raise RuntimeError("fee_config_identity_invalid")
                    quote_mint = str(curve.get("quote_mint") or SOLANA_SYSTEM_PROGRAM_ID)
                    if quote_mint in {SOLANA_SYSTEM_PROGRAM_ID, SOLANA_WRAPPED_SOL_MINT}:
                        quote_mint = SOLANA_WRAPPED_SOL_MINT
                    quote = pump_bonding_curve_sell_quote_v1(
                        token_amount_raw=int(surface["remaining_amount_raw"]),
                        slippage_bps=int(slippage_bps), bonding_curve=curve,
                        global_config=global_config,
                        fee_config=fee_config if fee_config.get("status") == "verified" else None,
                    )
                    estimate = None
                    conversion_source = ""
                    conversion_min_usdc_raw = None
                    conversion_input_raw = None
                    conversion_completed_at = None
                    if quote_mint == SOLANA_USDC_MINT:
                        estimate = int(quote["min_quote_raw"]) / 1_000_000.0
                        conversion_source = "direct_usdc_curve_minimum"
                    elif quote_mint == SOLANA_WRAPPED_SOL_MINT and wsol_usdc_conversion:
                        conversion_input_raw = int(wsol_usdc_conversion.get("input_amount_raw") or 0)
                        conversion_min_usdc_raw = int(
                            wsol_usdc_conversion.get("minimum_output_amount_raw") or 0
                        )
                        conversion_completed_at = str(
                            wsol_usdc_conversion.get("completed_at") or ""
                        )
                        if conversion_input_raw > 0 and conversion_min_usdc_raw > 0:
                            estimate = (
                                int(quote["min_quote_raw"]) * conversion_min_usdc_raw
                                / conversion_input_raw / 1_000_000.0
                            )
                            conversion_source = "shared_jupiter_wsol_usdc_minimum"
                    results.append({
                        **common, **quote, "quote_mint": quote_mint,
                        "status": "LOCAL_SURFACE_CURRENT", "reason": "",
                        "direct_estimated_recovery_usd": estimate,
                        "conversion_source": conversion_source,
                        "conversion_min_usdc_raw": conversion_min_usdc_raw,
                        "conversion_input_raw": conversion_input_raw,
                        "conversion_completed_at": conversion_completed_at,
                    })
                except LookupError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_MISSING_ACCOUNT", "reason": str(exc)})
                except PermissionError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_IDENTITY", "reason": str(exc)})
                except RuntimeError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_FEE_CONFIG", "reason": str(exc)})
                except ValueError as exc:
                    reason = str(exc)
                    status = (
                        "LOCAL_NO_DIRECT_CAPACITY"
                        if reason in {"insufficient_real_quote_reserves", "bonding_curve_complete_migrated"}
                        else "LOCAL_UNKNOWN_MATH"
                    )
                    results.append({
                        **common, "status": status, "reason": reason,
                        "quote_mint": quote_mint,
                    })
        return results

    async def pumpswap_route_surface_quotes(
        self, candidates: list[Mapping[str, Any]], *, slippage_bps: int = 400,
    ) -> list[dict[str, Any]]:
        """Verify Jupiter/Dex route pool keys, then quote their exact PumpSwap surface."""
        verified: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for offset in range(0, len(candidates), self.max_multiple_accounts):
            batch = candidates[offset:offset + self.max_multiple_accounts]
            requested_at = utcnow()
            pool_keys = list(dict.fromkeys(str(item["pool_address"]) for item in batch))
            try:
                response = await self.http.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0", "id": offset // self.max_multiple_accounts + 9_000,
                        "method": "getMultipleAccounts",
                        "params": [pool_keys, {"encoding": "base64", "commitment": "confirmed"}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("result") if isinstance(payload, Mapping) else None
                values = result.get("value") if isinstance(result, Mapping) else None
                slot = int((result.get("context") or {}).get("slot") or 0) if isinstance(result, Mapping) else 0
                if not isinstance(values, list) or len(values) != len(pool_keys) or slot <= 0:
                    raise ValueError("route_surface_pool_bundle_invalid")
                accounts = dict(zip(pool_keys, values))
            except Exception as exc:
                completed_at = utcnow()
                for candidate in batch:
                    results.append({
                        **dict(candidate), "quote_mint": "", "context_slot": 0,
                        "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                        "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                        "status": "LOCAL_UNKNOWN_RPC", "reason": self._rpc_error_reason(exc),
                        "source_hashes": {},
                    })
                continue
            completed_at = utcnow()
            for candidate in batch:
                pool_address = str(candidate["pool_address"])
                value = accounts.get(pool_address)
                common = {
                    **dict(candidate), "quote_mint": "", "context_slot": slot,
                    "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                    "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                }
                encoded = value.get("data") if isinstance(value, Mapping) else None
                body = encoded[0] if isinstance(encoded, list) and encoded else ""
                source_hashes = {pool_address: hashlib.sha256(str(body).encode()).hexdigest()}
                try:
                    pool = self.decode_account({
                        **dict(candidate), "account_kind": "pool",
                        "decoder_version": PUMPSWAP_POOL_DECODER_V2,
                        "expected_program_owner": PUMP_AMM_PROGRAM_ID,
                    }, value)
                    if pool.get("status") == "missing":
                        raise LookupError("route_surface_pool_missing")
                    if pool.get("status") != "verified":
                        raise PermissionError(str(pool.get("reason") or "route_surface_pool_invalid"))
                    verified.append({
                        **dict(candidate),
                        "pool_address": pool_address,
                        "base_mint": str(pool["base_mint"]),
                        "quote_mint": str(pool["quote_mint"]),
                        "lp_mint": str(pool["lp_mint"]),
                        "base_vault": str(pool["base_vault"]),
                        "quote_vault": str(pool["quote_vault"]),
                        "surface_type": "pumpswap_route_pool",
                        "route_verification_slot": slot,
                    })
                except LookupError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_MISSING_ACCOUNT", "reason": str(exc), "source_hashes": source_hashes})
                except (PermissionError, KeyError, ValueError) as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_IDENTITY", "reason": str(exc), "source_hashes": source_hashes})
        if verified:
            results.extend(await self.local_surface_quotes(verified, slippage_bps=slippage_bps))
        return results

    async def local_surface_quotes(
        self, surfaces: list[Mapping[str, Any]], *, slippage_bps: int = 400,
    ) -> list[dict[str, Any]]:
        """Read coherent PumpSwap account bundles and quote exact remaining amounts."""
        results: list[dict[str, Any]] = []
        surface_batch_size = 1 if self.max_multiple_accounts <= 10 else 24
        for offset in range(0, len(surfaces), surface_batch_size):
            batch = surfaces[offset:offset + surface_batch_size]
            requested_at = utcnow()
            pubkeys: list[str] = []
            for surface in batch:
                pubkeys.extend([
                    str(surface["pool_address"]), str(surface["base_vault"]),
                    str(surface["quote_vault"]), str(surface["base_mint"]),
                    str(surface["quote_mint"]),
                ])
            pubkeys.extend([PUMPSWAP_GLOBAL_CONFIG_PDA, PUMPSWAP_FEE_CONFIG_PDA])
            pubkeys = list(dict.fromkeys(pubkeys))
            try:
                response = await self.http.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0", "id": offset // surface_batch_size + 10_000,
                        "method": "getMultipleAccounts",
                        "params": [pubkeys, {"encoding": "base64", "commitment": "confirmed"}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("result") if isinstance(payload, Mapping) else None
                values = result.get("value") if isinstance(result, Mapping) else None
                slot = int((result.get("context") or {}).get("slot") or 0) if isinstance(result, Mapping) else 0
                if not isinstance(values, list) or len(values) != len(pubkeys) or slot <= 0:
                    raise ValueError("local_surface_account_bundle_invalid")
                accounts = dict(zip(pubkeys, values))
                completed_at = utcnow()
            except Exception as exc:
                completed_at = utcnow()
                for surface in batch:
                    results.append({
                        **dict(surface), "context_slot": 0,
                        "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                        "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                        "status": "LOCAL_UNKNOWN_RPC", "reason": self._rpc_error_reason(exc),
                        "source_hashes": {},
                    })
                continue

            def decode(pubkey: str, target: Mapping[str, Any]) -> dict[str, Any]:
                return self.decode_account(target, accounts.get(pubkey))

            global_config = decode(PUMPSWAP_GLOBAL_CONFIG_PDA, {
                "account_kind": "global_config",
                "expected_program_owner": PUMP_AMM_PROGRAM_ID,
            })
            fee_config = decode(PUMPSWAP_FEE_CONFIG_PDA, {
                "account_kind": "fee_config",
                "expected_program_owner": PUMP_FEE_PROGRAM_ID,
            })
            for surface in batch:
                completed_at = utcnow()
                common = {
                    **dict(surface), "context_slot": slot,
                    "requested_at": iso(requested_at), "completed_at": iso(completed_at),
                    "age_ms": max(0, round((completed_at - requested_at).total_seconds() * 1000)),
                }
                source_hashes = {}
                for pubkey in (
                    str(surface["pool_address"]), str(surface["base_vault"]),
                    str(surface["quote_vault"]), str(surface["base_mint"]),
                    str(surface["quote_mint"]),
                    PUMPSWAP_GLOBAL_CONFIG_PDA, PUMPSWAP_FEE_CONFIG_PDA,
                ):
                    value = accounts.get(pubkey)
                    encoded = value.get("data") if isinstance(value, Mapping) else None
                    body = encoded[0] if isinstance(encoded, list) and encoded else ""
                    source_hashes[pubkey] = hashlib.sha256(str(body).encode()).hexdigest()
                common["source_hashes"] = source_hashes
                try:
                    pool = decode(str(surface["pool_address"]), {
                        **dict(surface), "account_kind": "pool",
                        "decoder_version": PUMPSWAP_POOL_DECODER_V2,
                        "expected_program_owner": PUMP_AMM_PROGRAM_ID,
                    })
                    base_mint = decode(str(surface["base_mint"]), {
                        **dict(surface), "account_kind": "token_mint",
                    })
                    quote_mint = decode(str(surface["quote_mint"]), {
                        **dict(surface), "account_kind": "token_mint",
                    })
                    if base_mint.get("status") != "verified" or quote_mint.get("status") != "verified":
                        raise PermissionError("mint_identity_invalid")
                    base_token_program = str(base_mint.get("owner") or "")
                    quote_token_program = str(quote_mint.get("owner") or "")
                    if (
                        surface.get("base_token_program")
                        and str(surface["base_token_program"]) != base_token_program
                    ) or (
                        surface.get("quote_token_program")
                        and str(surface["quote_token_program"]) != quote_token_program
                    ):
                        raise PermissionError("token_program_identity_changed")
                    base_vault = decode(str(surface["base_vault"]), {
                        **dict(surface), "account_kind": "base_vault",
                        "expected_mint": str(surface["base_mint"]),
                        "expected_program_owner": base_token_program,
                    })
                    quote_vault = decode(str(surface["quote_vault"]), {
                        **dict(surface), "account_kind": "quote_vault",
                        "expected_mint": str(surface["quote_mint"]),
                        "expected_program_owner": quote_token_program,
                    })
                    required = (
                        pool, base_vault, quote_vault, base_mint, quote_mint,
                        global_config,
                    )
                    if any(item.get("status") == "missing" for item in required):
                        raise LookupError("required_account_missing")
                    if any(item.get("status") != "verified" for item in required):
                        raise PermissionError("required_account_identity_invalid")
                    if fee_config.get("status") not in {"verified", "missing"}:
                        raise RuntimeError("fee_config_identity_invalid")
                    from solders.pubkey import Pubkey
                    pump_program = Pubkey.from_string(PUMP_PROGRAM_ID)
                    canonical_creator = str(Pubkey.find_program_address(
                        [b"pool-authority", bytes(Pubkey.from_string(str(surface["base_mint"])))],
                        pump_program,
                    )[0])
                    if (
                        str(pool.get("creator")) != canonical_creator
                        or str(pool.get("base_mint")) != str(surface["base_mint"])
                        or str(pool.get("quote_mint")) != str(surface["quote_mint"])
                        or str(pool.get("base_vault")) != str(surface["base_vault"])
                        or str(pool.get("quote_vault")) != str(surface["quote_vault"])
                    ):
                        raise PermissionError("canonical_surface_identity_mismatch")
                    if int(global_config.get("disable_flags") or 0) & PUMPSWAP_DISABLE_SELL_MASK:
                        results.append({
                            **common, "status": "LOCAL_SELL_DISABLED",
                            "reason": "global_config_sell_disabled",
                        })
                        continue
                    quote = pumpswap_sell_base_input_v1(
                        base_amount_raw=int(surface["remaining_amount_raw"]),
                        slippage_bps=int(slippage_bps),
                        base_reserve_raw=int(base_vault["amount_raw"]),
                        quote_reserve_raw=int(quote_vault["amount_raw"]),
                        virtual_quote_reserves_raw=int(pool["virtual_quote_reserves_raw"]),
                        base_mint_supply_raw=int(base_mint["supply_raw"]),
                        base_mint=str(surface["base_mint"]), creator=str(pool["creator"]),
                        coin_creator=str(pool["coin_creator"]), global_config=global_config,
                        fee_config=fee_config if fee_config.get("status") == "verified" else None,
                    )
                    results.append({
                        **common, **quote, "status": "LOCAL_SURFACE_CURRENT", "reason": "",
                    })
                except LookupError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_MISSING_ACCOUNT", "reason": str(exc)})
                except PermissionError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_IDENTITY", "reason": str(exc)})
                except RuntimeError as exc:
                    results.append({**common, "status": "LOCAL_UNKNOWN_FEE_CONFIG", "reason": str(exc)})
                except ValueError as exc:
                    reason = str(exc)
                    status = (
                        "LOCAL_NO_DIRECT_CAPACITY"
                        if reason in {"insufficient_real_quote_reserves", "invalid_pumpswap_sell_zero_reserve"}
                        else "LOCAL_UNKNOWN_MATH"
                    )
                    results.append({**common, "status": status, "reason": reason})
        return results

    @staticmethod
    def _pubkey(raw: bytes, offset: int) -> str:
        from solders.pubkey import Pubkey

        return str(Pubkey.from_bytes(raw[offset:offset + 32]))

    @classmethod
    def decode_account(
        cls, target: Mapping[str, Any], value: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {"status": "missing", "reason": "account_missing"}
        encoded = value.get("data")
        if not isinstance(encoded, list) or not encoded or not isinstance(encoded[0], str):
            return {"status": "rejected", "reason": "account_data_missing"}
        try:
            raw = base64.b64decode(encoded[0], validate=True)
        except Exception:
            return {"status": "rejected", "reason": "account_data_invalid"}
        owner = str(value.get("owner") or "")
        kind = str(target.get("account_kind") or "")
        facts: dict[str, Any] = {
            "status": "verified",
            "owner": owner,
            "lamports": int(value.get("lamports") or 0),
            "data_length": len(raw),
        }
        try:
            if kind == "pool":
                if str(target.get("decoder_version") or "") != PUMPSWAP_POOL_DECODER_V2:
                    raise ValueError("pumpswap_pool_decoder_version_missing")
                facts.update(decode_pumpswap_pool_account(raw))
                expected = {
                    "base_mint": str(target.get("base_mint") or ""),
                    "quote_mint": str(target.get("quote_mint") or ""),
                    "lp_mint": str(target.get("lp_mint") or ""),
                    "base_vault": str(target.get("base_vault") or ""),
                    "quote_vault": str(target.get("quote_vault") or ""),
                }
                if owner != str(target.get("expected_program_owner") or ""):
                    raise ValueError("pool_program_owner_mismatch")
                if any(expected[name] and facts[name] != expected[name] for name in expected):
                    raise ValueError("pool_identity_changed")
            elif kind in {"base_vault", "quote_vault"}:
                if len(raw) < 72:
                    raise ValueError("invalid_token_account_layout")
                facts.update({
                    "mint": cls._pubkey(raw, 0),
                    "authority": cls._pubkey(raw, 32),
                    "amount_raw": int.from_bytes(raw[64:72], "little"),
                })
                if facts["mint"] != str(target.get("expected_mint") or ""):
                    raise ValueError("vault_mint_mismatch")
                if facts["authority"] != str(target.get("pool_address") or ""):
                    raise ValueError("vault_authority_mismatch")
            elif kind in {"token_mint", "lp_mint"}:
                if len(raw) < 82:
                    raise ValueError("invalid_mint_layout")
                mint_authority_option = int.from_bytes(raw[0:4], "little")
                freeze_authority_option = int.from_bytes(raw[46:50], "little")
                facts.update({
                    "mint_authority": cls._pubkey(raw, 4) if mint_authority_option else None,
                    "supply_raw": int.from_bytes(raw[36:44], "little"),
                    "decimals": int(raw[44]),
                    "initialized": bool(raw[45]),
                    "freeze_authority": cls._pubkey(raw, 50) if freeze_authority_option else None,
                })
            elif kind == "global_config":
                facts.update(decode_pumpswap_global_config_account(raw))
            elif kind == "pump_global":
                facts.update(decode_pump_global_account(raw))
            elif kind == "bonding_curve":
                facts.update(decode_pump_bonding_curve_account(raw))
            elif kind == "fee_config":
                facts.update(decode_pumpswap_fee_config_account(raw))
            else:
                raise ValueError("unsupported_held_account_kind")
            expected_program_owner = str(target.get("expected_program_owner") or "")
            if expected_program_owner and owner != expected_program_owner:
                raise ValueError("account_program_owner_mismatch")
        except ValueError as exc:
            return {**facts, "status": "rejected", "reason": str(exc)}
        return facts

    @staticmethod
    def _target_fingerprint(targets: list[Mapping[str, Any]]) -> tuple[tuple[int, str], ...]:
        return tuple(sorted(
            (int(item["id"]), str(item["pubkey"])) for item in targets
        ))

    async def stream(
        self, target_provider: Callable[[], list[dict[str, Any]]]
    ) -> AsyncIterator[dict[str, Any]]:
        while True:
            targets = target_provider()
            if not targets:
                await asyncio.sleep(self.refresh_seconds)
                continue
            fingerprint = self._target_fingerprint(targets)
            try:
                async with websockets.connect(
                    self.url, ping_interval=20, ping_timeout=20, max_size=2_000_000
                ) as ws:
                    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
                    for target in targets:
                        grouped[str(target["pubkey"])].append(target)
                    requests: dict[int, list[dict[str, Any]]] = {}
                    subscriptions: dict[int, list[dict[str, Any]]] = {}
                    for request_id, (pubkey, grouped_targets) in enumerate(
                        grouped.items(), start=1
                    ):
                        requests[request_id] = grouped_targets
                        await ws.send(json.dumps({
                            "jsonrpc": "2.0", "id": request_id,
                            "method": "accountSubscribe",
                            "params": [pubkey, {
                                "encoding": "base64", "commitment": "confirmed",
                            }],
                        }))
                    while len(subscriptions) < len(grouped):
                        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                        if "error" in message:
                            raise RuntimeError("held_account_subscription_rejected")
                        if "id" in message and isinstance(message.get("result"), int):
                            matched = requests.get(int(message["id"]))
                            if matched is not None:
                                subscriptions[int(message["result"])] = matched
                    for update in await self._initial_updates(targets):
                        yield update
                    last_target_refresh = time.monotonic()
                    while True:
                        try:
                            raw_message = await asyncio.wait_for(
                                ws.recv(), timeout=self.refresh_seconds
                            )
                        except TimeoutError:
                            last_target_refresh = time.monotonic()
                            if self._target_fingerprint(target_provider()) != fingerprint:
                                break
                            continue
                        message = json.loads(raw_message)
                        if "id" in message and isinstance(message.get("result"), int):
                            matched = requests.get(int(message["id"]))
                            if matched is not None:
                                subscriptions[int(message["result"])] = matched
                            continue
                        params = message.get("params") if isinstance(message, Mapping) else None
                        if not isinstance(params, Mapping):
                            continue
                        matched_targets = subscriptions.get(
                            int(params.get("subscription") or -1)
                        )
                        result = params.get("result")
                        if matched_targets is None or not isinstance(result, Mapping):
                            continue
                        context = result.get("context") if isinstance(result.get("context"), Mapping) else {}
                        value = result.get("value") if isinstance(result.get("value"), Mapping) else None
                        digest_payload = None
                        if isinstance(value, Mapping):
                            encoded = value.get("data")
                            digest_payload = encoded[0] if isinstance(encoded, list) and encoded else ""
                        observed_at = iso(utcnow())
                        data_hash = hashlib.sha256(
                            str(digest_payload or "").encode()
                        ).hexdigest()
                        for target in matched_targets:
                            yield {
                                **dict(target),
                                "slot": int(context.get("slot") or 0),
                                "data_hash": data_hash,
                                "decoded": self.decode_account(target, value),
                                "observed_at": observed_at,
                            }
                        if time.monotonic() - last_target_refresh >= self.refresh_seconds:
                            last_target_refresh = time.monotonic()
                            if self._target_fingerprint(target_provider()) != fingerprint:
                                break
            except asyncio.CancelledError:
                raise
            except Exception:
                raise


class PumpPortalCollector:
    """Free launch/migration metadata only; paid transaction subscriptions are not used."""

    URL = "wss://pumpportal.fun/api/data"

    def __init__(self, url: str | None = None):
        self.url = url or self.URL

    async def stream(self) -> AsyncIterator[TokenCandidate]:
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    async for raw in ws:
                        item = json.loads(raw)
                        received_at = utcnow()
                        address = str(item.get("mint") or item.get("tokenAddress") or "")
                        if not address:
                            continue
                        event_type = str(
                            item.get("txType") or item.get("eventType") or item.get("type") or "create"
                        ).lower()
                        source = "pumpportal:migration" if "migrat" in event_type else "pumpportal:create"
                        yield TokenCandidate(
                            chain="solana",
                            address=address,
                            name=str(item.get("name") or ""),
                            symbol=str(item.get("symbol") or ""),
                            first_seen_at=received_at,
                            source=source,
                            url=f"https://pump.fun/coin/{address}",
                            raw={**item, "pump_event_type": event_type},
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
