"""Immutable ChainMemeTrader Paper execution-setting helpers."""
from __future__ import annotations

import json
import math
import sqlite3
from typing import Any, Mapping


CURRENT_EXECUTION_SETTINGS_KEY = "chain-paper-execution:current"
EXECUTION_SETTINGS_KEY_PREFIX = "chain-paper-execution:activation:"

DEFAULT_EXECUTION_SETTINGS = {
    "buy_slippage_pct": 4.0,
    "sell_slippage_pct": 4.0,
    "additional_fee_usd_each_fill": 0.0,
    "min_pool_liquidity_usd": 1000.0,
}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def normalize_execution_settings(raw: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Validate and normalize the four public UI fields."""
    supplied = dict(raw or {})
    unknown = set(supplied) - set(DEFAULT_EXECUTION_SETTINGS)
    if unknown:
        raise ValueError("unsupported execution setting: " + ", ".join(sorted(unknown)))
    values = {**DEFAULT_EXECUTION_SETTINGS, **supplied}
    result = {name: _number(value, name) for name, value in values.items()}
    for name in ("buy_slippage_pct", "sell_slippage_pct"):
        if not 0.0 <= result[name] <= 50.0:
            raise ValueError(f"{name} must be between 0 and 50")
        if not math.isclose(result[name] * 100.0, round(result[name] * 100.0), abs_tol=1e-9):
            raise ValueError(f"{name} must use 0.01 percent precision")
    if result["additional_fee_usd_each_fill"] < 0.0:
        raise ValueError("additional_fee_usd_each_fill must be non-negative")
    if result["min_pool_liquidity_usd"] < 0.0:
        raise ValueError("min_pool_liquidity_usd must be non-negative")
    return result


def execution_definition_fields(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Translate public percentages into the explicit frozen Store fields."""
    normalized = normalize_execution_settings(settings)
    return {
        "buy_slippage_bps": round(normalized["buy_slippage_pct"] * 100.0),
        "sell_slippage_bps": round(normalized["sell_slippage_pct"] * 100.0),
        "additional_fee_usd_each_fill": normalized["additional_fee_usd_each_fill"],
        "min_pool_liquidity_usd": normalized["min_pool_liquidity_usd"],
    }


def effective_execution_settings(connection: sqlite3.Connection) -> dict[str, float] | None:
    """Read the current immutable activation through its mutable pointer."""
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kv'"
    ).fetchone() is None:
        return None
    pointer = connection.execute(
        "SELECT value_json FROM kv WHERE key=?", (CURRENT_EXECUTION_SETTINGS_KEY,)
    ).fetchone()
    if pointer is None:
        return None
    try:
        pointer_value = json.loads(str(pointer[0]))
        activation_key = str(pointer_value["activation_key"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not activation_key.startswith(EXECUTION_SETTINGS_KEY_PREFIX):
        return None
    activation = connection.execute(
        "SELECT value_json FROM kv WHERE key=?", (activation_key,)
    ).fetchone()
    if activation is None:
        return None
    try:
        value = json.loads(str(activation[0]))
        return normalize_execution_settings(value["settings"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def buy_terms(notional_usd: float, market_price_usd: float,
              definition: Mapping[str, Any]) -> dict[str, float]:
    """Return quantity and total cash cost for one adverse Paper BUY."""
    notional = _number(notional_usd, "notional_usd")
    price = _number(market_price_usd, "market_price_usd")
    bps = int(definition.get("buy_slippage_bps", definition.get("slippage_bps", 400)))
    fee = _number(definition.get("additional_fee_usd_each_fill", 0.0), "additional_fee_usd_each_fill")
    if notional <= 0.0 or price <= 0.0 or not 0 <= bps < 10_000 or fee < 0.0:
        raise ValueError("invalid Paper BUY terms")
    execution_price = price * (1.0 + bps / 10_000.0)
    return {"execution_price_usd": execution_price, "quantity_tokens": notional / execution_price,
            "notional_usd": notional, "fee_usd": fee, "total_cost_usd": notional + fee}


def sell_terms(quantity_tokens: float, market_price_usd: float,
               definition: Mapping[str, Any], *, exact_gross_usd: float | None = None) -> dict[str, float]:
    """Return one-fill net proceeds; exact quotes already include slippage."""
    quantity = _number(quantity_tokens, "quantity_tokens")
    price = _number(market_price_usd, "market_price_usd")
    bps = int(definition.get("sell_slippage_bps", definition.get("slippage_bps", 400)))
    fee = _number(definition.get("additional_fee_usd_each_fill", 0.0), "additional_fee_usd_each_fill")
    if quantity < 0.0 or price < 0.0 or not 0 <= bps < 10_000 or fee < 0.0:
        raise ValueError("invalid Paper SELL terms")
    gross = (_number(exact_gross_usd, "exact_gross_usd") if exact_gross_usd is not None
             else quantity * price * (1.0 - bps / 10_000.0))
    return {"gross_usd": gross, "fee_usd": fee, "net_usd": max(0.0, gross - fee)}


def pool_is_below_floor(liquidity_usd: Any, definition: Mapping[str, Any]) -> bool:
    """Missing liquidity is unknown, never a dust-pool terminal fact."""
    if liquidity_usd is None:
        return False
    liquidity = _number(liquidity_usd, "liquidity_usd")
    floor = _number(definition.get("min_pool_liquidity_usd", 1000.0), "min_pool_liquidity_usd")
    return 0.0 <= liquidity < floor


def pool_has_trade_liquidity(liquidity_usd: Any, definition: Mapping[str, Any]) -> bool:
    """Affirm usable liquidity; unknown/invalid is not the inverse of dust."""
    if liquidity_usd is None:
        return False
    try:
        liquidity = _number(liquidity_usd, "liquidity_usd")
    except ValueError:
        return False
    return liquidity >= max(0.0, float(definition.get("min_pool_liquidity_usd", 1000.0)))
