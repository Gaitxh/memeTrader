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


# A dust read is only terminal when nothing contradicts it. Measured on 2026-09-12: of the 24h
# written-off tokens, 19 were real rugs whose price had collapsed by 3-6 orders of magnitude,
# and one was a Solana pool whose reported `liquidity.usd` fell to exactly 0.0 while its price
# held at -3.9% of the pre-read value and it kept printing 19k-63k USD of 5-minute volume.
# That single contradicted read wrote off 48 positions across 48 arms (-120U).
DUST_PRICE_HELD_FRACTION = 0.5
DUST_LIVE_VOLUME_USD = 200.0
# Only a reported liquidity of exactly zero (or negative, which is equally impossible) is
# contradictory for a pool that is still trading. Anything above zero - including 0.05 and
# 999.99 - is a genuinely drained pool and keeps the frozen immediate-writeoff rule untouched,
# which is what the existing execution tests pin.
DUST_IMPOSSIBLE_LIQUIDITY_USD = 0.0


# Physically impossible position outcomes. Measured on 2026-09-12 across all 260,326 recorded
# positions: 161 closed positions booked a realized profit above 100x their own stake, totalling
# +8,218,961U against a stake sum of about 3,220U, and every one of them belongs to two RETIRED
# epochs (`v22-additive-first-mover-...`: 9 positions incl. one 20U stake booked at +2,162,979U from
# `market_mark_zero_5m_activity`, and `v19-dexscreener-successors-...`: 152 positions). The current
# funding epoch is clean (largest is 518.2U on a 20U stake = 25.9x, on a real token via
# `market_mark_take_profit_1`). A meme runner can multiply a position many times over, so the
# threshold is deliberately far outside anything a real path produces, and it exists to keep any
# cross-strategy aggregate from being dominated by a broken mark instead of by strategy behaviour.
IMPLAUSIBLE_PNL_MULTIPLE = 100.0


def plausible_position_pnl(*, stake_usd: Any, realized_pnl_usd: Any) -> bool:
    """False when a recorded profit is impossible against its own stake.

    Comparison and review layers must exclude such rows instead of rewriting them: the recorded value
    is the historical evidence of an old mark defect, and the append-only rule keeps it. Aggregates
    that ignore this get ranked by the defect rather than by the strategies.
    """
    try:
        stake = float(stake_usd or 0.0)
        pnl = float(realized_pnl_usd or 0.0)
    except (TypeError, ValueError):
        return True
    if stake <= 0:
        return True
    return pnl <= IMPLAUSIBLE_PNL_MULTIPLE * stake


def dust_read_contradicted_by_live_trading(
    *, liquidity_usd: Any, price_usd: Any, entry_price_usd: Any,
    volume_5m_usd: Any, buys_5m: Any = None, sells_5m: Any = None,
    definition: Mapping[str, Any] | None = None,
) -> bool:
    """True when a sub-floor liquidity read is contradicted by live trading at a held price.

    Paper must not turn a single failed observation into a total write-off, so this is the
    corroboration test in front of the dust-pool terminal fact. It returns True only on
    positive evidence of a live pool: the reported liquidity is exactly zero (impossible for a
    trading pool), the observed price has NOT collapsed against the entry price (a real rug
    loses orders of magnitude), and the SAME observation still reports material trading volume.
    Any missing field, or any positive liquidity value, leaves the existing rule untouched.
    """
    definition = definition or {}
    if not pool_is_below_floor(liquidity_usd, definition):
        return False
    try:
        liquidity = _number(liquidity_usd, "liquidity_usd")
    except ValueError:
        return False
    if liquidity > DUST_IMPOSSIBLE_LIQUIDITY_USD:
        return False  # a genuinely drained pool keeps the existing immediate-writeoff rule
    try:
        price = _number(price_usd, "price_usd")
        entry = _number(entry_price_usd, "entry_price_usd")
        volume = _number(volume_5m_usd, "volume_5m_usd") if volume_5m_usd is not None else None
    except ValueError:
        return False
    if price <= 0.0 or entry <= 0.0:
        return False
    if price < entry * DUST_PRICE_HELD_FRACTION:
        return False  # a collapsed price corroborates the dead pool; do not interfere
    return bool(volume is not None and volume >= DUST_LIVE_VOLUME_USD)
