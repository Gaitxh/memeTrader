"""SCORE149: a deterministic, as-of multi-dimension candidate score.

Purpose (user request, round 2): put a real-time multi-dimension score in front of
full strategy judgement, built from on-chain and risk facts the engine already
observes - without inventing data it does not have.

Design rules
------------
1. **Pure and as-of.** The score reads only the trajectory feature vector that the
   engine already derived from observed frames. No I/O, no database, no request,
   no future value, no cross-candidate normalisation.
2. **Missing never counts as good.** A dimension whose inputs are absent is
   excluded from both the numerator and the denominator, and the coverage share is
   reported. Callers that want a gate must require coverage as well as score, so a
   mostly-unobserved candidate can never pass on a couple of favourable fields.
3. **Measured bands, not opinions.** The structure dimension uses the measured
   write-off bands (FDV/depth and pool age); the risk dimension uses the measured
   stop-overshoot drivers (drawdown, trend fit, liquidity withdrawal).
4. **Explicit evidence gaps.** The user's requested social and holder dimensions
   have no collector in the current on-chain-first mode, so they are listed in
   `UNAVAILABLE` and never silently scored as neutral. `participation` is the
   documented on-chain PROXY for new-participant growth, not holder data.

The score is an observation. Nothing in this module can open, size or close a
position; the arms that consume it declare their own threshold and are measured
against a same-entry control on the other side of that threshold.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

VERSION = "score149/v1"

# dimension -> weight. Weights are re-normalised over the dimensions that are
# actually available for a given candidate.
WEIGHTS = {
    "flow": 0.20,
    "depth": 0.18,
    "structure": 0.16,
    "momentum": 0.16,
    "participation": 0.15,
    "risk": 0.15,
}

# Requested dimensions with no live evidence source in the current deployment.
# Kept explicit so a report can state the gap instead of implying coverage.
UNAVAILABLE = (
    "top_holder_change",       # token_snapshots.holders is never written
    "holder_concentration",    # computed nowhere; deliberately not a hard gate
    "new_holder_growth",       # buyers_5m column is never written
    "large_trade_direction",   # no signed trade tape; only a size-share proxy exists
    "bundling",                # always 'unknown'
    "social_mention_velocity", # RSS/Mastodon lane paused since 2026-09-03 (user decision)
    "kol_mentions",            # include_kol disabled in on-chain-first mode
    "sentiment",               # no social collector
    "historical_rug_links",    # no creator/rug linkage table with rows
)

FRICTION = 1.04 / 0.96 - 1.0
SCORE_MIN = 55.0
COVERAGE_MIN = 0.60
# Dimensions that must be present for a gated candidate. They are exactly the ones
# the engine can supply without a formed 30-second window (measured reality: p50 =
# 1 frame per pool, so requiring the window dimensions would starve the gate the
# same way the strict-rise requirement starved the band arms in wave 21).
REQUIRED_DIMENSIONS = ("flow", "depth", "structure", "risk")


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _ramp(value: float | None, low: float, high: float) -> float | None:
    """Linear 0..1 ramp; None in, None out (never a substituted zero)."""
    if value is None:
        return None
    if high == low:
        return 1.0 if value >= high else 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _window(feature: Mapping[str, Any], seconds: str) -> Mapping[str, Any] | None:
    windows = feature.get("windows")
    if not isinstance(windows, Mapping):
        return None
    window = windows.get(seconds)
    return window if isinstance(window, Mapping) else None


def _current(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    current = feature.get("current")
    return current if isinstance(current, Mapping) else {}


def dimensions(feature: Mapping[str, Any]) -> dict[str, float | None]:
    """Per-dimension 0..1 readings; None means 'no evidence for this dimension'."""
    if not isinstance(feature, Mapping):
        return {name: None for name in WEIGHTS}
    current = _current(feature)
    window = _window(feature, "30")
    window = window or {}
    liquidity = _num(current.get("liquidity_usd"))
    if liquidity is None:
        liquidity = _num(feature.get("liquidity_usd"))
    buy_share = _num(feature.get("buy_count_share"))
    volume_ratio = _num(window.get("rolling_volume_change_ratio"))
    tx_ratio = _num(window.get("rolling_tx_change_ratio"))
    liquidity_change = _num(window.get("liquidity_change_fraction"))
    retention = _num(feature.get("liquidity_retention"))
    drawdown = _num(feature.get("drawdown"))
    r2 = _num(feature.get("log_price_r2"))
    fdv_liq = _num(feature.get("fdv_liquidity"))
    pool_age = _num(feature.get("pool_age_seconds"))
    volume_accel = _num(feature.get("volume_acceleration_age_normalized"))
    tx_accel = _num(feature.get("tx_acceleration_age_normalized"))
    velocity_30 = _num(window.get("log_velocity"))
    window_60 = _window(feature, "60") or {}
    velocity_60 = _num(window_60.get("log_velocity"))

    # 1. flow: who is doing the trading, and is activity expanding at all.
    flow = _mean([
        _ramp(buy_share, 0.35, 0.75),
        _ramp(volume_accel, 0.8, 2.0),
        _ramp(tx_accel, 0.8, 2.0),
    ])

    # 2. depth: can the position be exited at all.
    log_liquidity = None if liquidity is None or liquidity <= 0 else math.log10(liquidity)
    depth = _mean([
        _ramp(log_liquidity, 3.0, 4.7),
        None if retention is None else _ramp(retention, 0.90, 1.0),
    ])

    # 3. structure: the measured write-off bands (FDV/depth, pool age).
    structure = _mean([
        None if fdv_liq is None else max(
            _ramp(fdv_liq, 0.50, 1.0) * (1.0 - _ramp(fdv_liq, 20.0, 50.0)),
            0.0),
        None if pool_age is None else max(
            _ramp(pool_age, 300.0, 1800.0) * (1.0 - 0.4 * _ramp(pool_age, 21600.0, 86400.0)),
            0.0),
    ])

    # 4. momentum: multi-horizon agreement, not a single print.
    momentum = _mean([
        _ramp(velocity_30, 0.0, 3.0 * FRICTION),
        None if velocity_60 is None else _ramp(velocity_30 - velocity_60 if velocity_30 is not None else None,
                                               -FRICTION, 2.0 * FRICTION),
    ])

    # 5. participation: the documented on-chain PROXY for new-participant growth -
    #    volume growing faster than the trade count means larger average size,
    #    and a high buy share means the marginal participant is a buyer.
    average_size = None
    if volume_ratio is not None and tx_ratio is not None and tx_ratio > 0:
        average_size = volume_ratio / tx_ratio
    participation = _mean([
        _ramp(average_size, 0.9, 1.5),
        _ramp(buy_share, 0.45, 0.70),
    ])

    # 6. risk: shallowness of the drawdown, trend integrity, and an explicit
    #    liquidity-withdrawal veto (any confirmed withdrawal zeroes the dimension).
    risk = _mean([
        _ramp(drawdown, -0.20, 0.0),
        None if r2 is None else _ramp(r2, 0.30, 0.80),
    ])
    if liquidity_change is not None and liquidity_change <= -2 * FRICTION:
        risk = 0.0

    return {"flow": flow, "depth": depth, "structure": structure,
            "momentum": momentum, "participation": participation, "risk": risk}


def score(feature: Mapping[str, Any]) -> dict[str, Any]:
    """Return the weighted score (0..100), its parts, coverage and known gaps."""
    parts = dimensions(feature)
    total_weight = 0.0
    weighted = 0.0
    for name, weight in WEIGHTS.items():
        value = parts.get(name)
        if value is None:
            continue
        total_weight += weight
        weighted += weight * value
    coverage = total_weight / sum(WEIGHTS.values())
    value = None if total_weight <= 0 else round(100.0 * weighted / total_weight, 2)
    return {
        "version": VERSION,
        "score": value,
        "coverage": round(coverage, 3),
        "parts": {name: (None if parts.get(name) is None else round(parts[name], 3))
                  for name in WEIGHTS},
        "unavailable": list(UNAVAILABLE),
        "missing_dimensions": [name for name in WEIGHTS if parts.get(name) is None],
        "missing_required": [name for name in REQUIRED_DIMENSIONS if parts.get(name) is None],
    }


def passes(feature: Mapping[str, Any], *, minimum: float = SCORE_MIN,
           minimum_coverage: float = COVERAGE_MIN) -> tuple[bool, dict[str, Any]]:
    """Gate helper: score, coverage and the required dimensions must all clear."""
    result = score(feature)
    value = result["score"]
    ok = (value is not None and value >= minimum
          and result["coverage"] >= minimum_coverage
          and not result["missing_required"])
    return ok, result


def snapshot() -> dict[str, Any]:
    return {"version": VERSION, "weights": dict(WEIGHTS), "score_min": SCORE_MIN,
            "coverage_min": COVERAGE_MIN, "unavailable": list(UNAVAILABLE),
            "affects": "observation_only"}
