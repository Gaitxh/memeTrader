"""BSC trend signal followed by an independent 30-60 second survival confirmation."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping, MutableMapping

from .models import parse_time


ARM = "bsc_post_signal_survival_v1"
PARENT = "trajectory144_trend_runner_v1"
CONTRACT = "bsc-post-signal-survival253/v1"


def _num(value: Any):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact trend parent required")
    out = deepcopy(dict(parent))
    for key in ("behavior_contract_hash", "forward_activation_snapshot_id",
                "forward_started_at", "original_forward_started_at", "runtime_addition_id",
                "paired_entry_group", "paired_entry_size", "excess_return_vs_arm"):
        out.pop(key, None)
    out.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="BSC post-signal survival confirmation", revision_of=PARENT,
        source_arm_ids=[PARENT], entry_alias_of=PARENT,
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        comparison_semantics=(
            "Same parent exits; entry waits for a fresh 30-60 second BSC survival "
            "confirmation and then still requires the normal next observed fill frame."
        ),
        description=(
            "BSC-only trend continuation. After a parent signal, require price and "
            "liquidity retention, non-declining reported activity and >=58% buy share "
            "on an independent 30-60 second frame. No extra request."
        ),
    )
    out["entry_filter"] = {**(out.get("entry_filter") or {}), "direction": ARM,
                           "chains": ["bsc"], "confirmation_min_seconds": 30,
                           "confirmation_max_seconds": 60, "minimum_buy_share": 0.58}
    return out


def update(parent_signal: Mapping[str, Any] | None, current: Mapping[str, Any],
           state: MutableMapping[str, Any], *, now: Any) -> dict[str, Any]:
    signals = state.setdefault("signals", {})
    existing = signals.get(ARM)
    if isinstance(existing, Mapping):
        age = (parse_time(now) - parse_time(existing["recorded_at"])).total_seconds()
        if 0 <= age <= 60:
            return {ARM: deepcopy(dict(existing))}
    if not isinstance(parent_signal, Mapping) or not parent_signal.get("decision_key"):
        return {}
    seed = (parent_signal.get("decision_evidence") or {}).get("feature_vector") or {}
    if seed.get("chain") != "bsc" or current.get("chain") != "bsc":
        return {}
    try:
        delta = (parse_time(current["observed_at"]) - parse_time(parent_signal["observed_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        return {}
    seed_now, confirmation = seed.get("current") or {}, current.get("current") or {}
    seed_price, price = _num(seed_now.get("price_usd")), _num(confirmation.get("price_usd"))
    seed_liq, liquidity = _num(seed_now.get("liquidity_usd")), _num(confirmation.get("liquidity_usd"))
    seed_activity = sum(_num(seed_now.get(k)) or 0 for k in ("buys_5m", "sells_5m"))
    activity = sum(_num(confirmation.get(k)) or 0 for k in ("buys_5m", "sells_5m"))
    buy_share = _num(current.get("buy_count_share"))
    if (not 30 <= delta <= 60 or None in (seed_price, price, seed_liq, liquidity, buy_share)
            or price < seed_price or liquidity < max(1000.0, seed_liq)
            or activity < seed_activity or buy_share < 0.58):
        return {}
    value = deepcopy(dict(parent_signal))
    value.update(decision_key=f"{parent_signal['decision_key']}|{ARM}",
                 observed_at=current["observed_at"], recorded_at=current["recorded_at"])
    value.setdefault("decision_evidence", {}).update(
        bsc_survival_contract=CONTRACT, seed_observed_at=parent_signal["observed_at"],
        confirmation_observed_at=current["observed_at"], confirmation_delay_seconds=delta,
        price_retention=price / seed_price, liquidity_retention=liquidity / seed_liq,
        confirmation_buy_share=buy_share, extra_market_requests=0)
    signals[ARM] = deepcopy(value)
    return {ARM: value}
