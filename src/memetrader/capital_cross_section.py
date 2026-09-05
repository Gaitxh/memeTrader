"""Bounded, strict-as-of cross-section contexts for capital entry policies.

The caller supplies one item per token for one evaluation round::

    {"token_id", "pair_address", "history", "amountful_flow"}

``history`` contains post-activation market rows with exact identity, positive
``price``/``liquidity`` (``*_usd`` aliases are accepted), and
``observed_at <= ingested_at <= recorded_at <= decision_at``.
``amountful_flow`` is a decoded ``chain_meme_pattern_evidence`` row produced
from actual transfer amounts, including its resolver and quote conversion.
Transaction counts are never consumed by this module.

The returned mapping is keyed by canonical token id.  Each value can be merged
directly into ``capital_context_from_observations(..., cross_section=value)``.
Invalid or ambiguous inputs are omitted; fewer than two eligible tokens yields
no cross-section rather than a one-token market claim.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from itertools import islice
from typing import Any, Iterable, Mapping

from .models import canonical_token_address


MAX_TOKENS = 256
MAX_HISTORY_PER_TOKEN = 16
MAX_FRESH_AGE_SECONDS = 30.0
MAX_HISTORY_AGE_SECONDS = 300.0
MIN_CROSS_SECTION_SIZE = 2
SCORE_METHOD = "equal_weight_cross_section_percentile_price_depth_actual_net_flow_v1"


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _signed_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _identity(token_id: Any, pair_address: Any) -> tuple[str, str] | None:
    text = str(token_id or "").strip()
    if ":" not in text:
        return None
    chain, address = text.split(":", 1)
    chain = chain.strip().lower()
    token = canonical_token_address(chain, address)
    pair = canonical_token_address(chain, str(pair_address or ""))
    return (f"{chain}:{token}", pair) if chain and token and pair else None


def _same_identity(row: Mapping[str, Any], token_id: str, pair_address: str) -> bool:
    return _identity(row.get("token_id"), row.get("pair_address")) == (token_id, pair_address)


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("payload", row.get("payload_json"))
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(decoded) if isinstance(decoded, Mapping) else {}
    return {}


def _receipt(row: Mapping[str, Any], decision: datetime, activated: datetime,
             *, require_ingested: bool, fresh: bool) -> tuple[datetime, datetime] | None:
    observed = _time(row.get("observed_at"))
    ingested = _time(row.get("ingested_at")) if require_ingested else observed
    recorded = _time(row.get("recorded_at", row.get("available_at")))
    if not observed or not ingested or not recorded:
        return None
    if not activated <= observed <= ingested <= recorded <= decision:
        return None
    if fresh and not 0.0 <= (decision - observed).total_seconds() <= MAX_FRESH_AGE_SECONDS:
        return None
    return observed, recorded


def _market_history(item: Mapping[str, Any], token_id: str, pair_address: str,
                    decision: datetime, activated: datetime) -> dict[str, Any] | None:
    supplied = list(islice(item.get("history") or (), MAX_HISTORY_PER_TOKEN + 1))
    if len(supplied) < 2 or len(supplied) > MAX_HISTORY_PER_TOKEN:
        return None
    ordered: list[tuple[datetime, datetime, Mapping[str, Any], float, float]] = []
    for row in supplied:
        if not isinstance(row, Mapping) or not _same_identity(row, token_id, pair_address):
            return None
        receipt = _receipt(row, decision, activated, require_ingested=True, fresh=False)
        price = _number(row.get("price", row.get("price_usd")))
        liquidity = _number(row.get("liquidity", row.get("liquidity_usd")))
        if receipt is None or price is None or price <= 0.0 or liquidity is None or liquidity <= 0.0:
            return None
        ordered.append((receipt[0], receipt[1], row, price, liquidity))
    ordered.sort(key=lambda value: value[0])
    if len({value[0] for value in ordered}) != len(ordered):
        return None
    first, latest = ordered[0], ordered[-1]
    if first[0] >= latest[0]:
        return None
    if (decision - first[0]).total_seconds() > MAX_HISTORY_AGE_SECONDS:
        return None
    if (decision - latest[0]).total_seconds() > MAX_FRESH_AGE_SECONDS:
        return None
    return {
        "observed": latest[0], "recorded": latest[1],
        "first_price": first[3], "latest_price": latest[3],
        "first_liquidity": first[4], "latest_liquidity": latest[4],
        "first_observed_at": _stamp(first[0]),
        "latest_sample_id": latest[2].get("sample_sequence", latest[2].get("id")),
    }


def _actual_flow(row: Any, token_id: str, pair_address: str,
                 decision: datetime, activated: datetime) -> dict[str, Any] | None:
    if not isinstance(row, Mapping) or row.get("id") is None:
        return None
    receipt = _receipt(row, decision, activated, require_ingested=False, fresh=True)
    if receipt is None or not _same_identity(row, token_id, pair_address):
        return None
    payload = _payload(row)
    resolver, conversion = payload.get("resolver"), payload.get("quote_conversion")
    if not isinstance(resolver, Mapping) or not isinstance(conversion, Mapping):
        return None
    chain, token_address = token_id.split(":", 1)
    resolver_identity = _identity(token_id, resolver.get("pool_address"))
    base = canonical_token_address(chain, str(resolver.get("base_mint") or ""))
    quote = str(resolver.get("quote_mint") or "")
    decimals = resolver.get("quote_decimals")
    raw = _signed_int(payload.get("net_quote_flow_raw"))
    rate = _number(conversion.get("usd_per_quote"))
    max_age = _number(conversion.get("max_age_seconds"))
    flow_decision = _time(payload.get("decision_at")) or receipt[1]
    conversion_observed = _time(conversion.get("observed_at"))
    conversion_recorded = _time(conversion.get("recorded_at", conversion.get("ingested_at")))
    resolver_observed = _time(resolver.get("observed_at"))
    resolver_recorded = _time(resolver.get("recorded_at", resolver.get("ingested_at")))
    valid = bool(
        payload.get("complete") is True
        and payload.get("scan_complete") is True
        and payload.get("future_data_rejected") is not True
        and payload.get("usd_conversion_complete") is True
        and str(payload.get("conversion_basis") or "")
        and resolver.get("status") == "verified"
        and resolver_identity == (token_id, pair_address)
        and base == token_address
        and quote
        and str(conversion.get("quote_mint") or "") == quote
        and type(decimals) is int and 0 <= decimals <= 18
        and raw is not None and rate is not None and rate > 0.0
        and max_age is not None and max_age >= 0.0
        and flow_decision is not None and flow_decision <= decision
        and conversion_observed is not None and conversion_recorded is not None
        and resolver_observed is not None and resolver_recorded is not None
        and conversion_observed <= conversion_recorded <= flow_decision
        and resolver_observed <= resolver_recorded <= flow_decision
        and 0.0 <= (flow_decision - conversion_observed).total_seconds() <= max_age
    )
    if not valid:
        return None
    native = raw / 10 ** decimals
    return {
        "observed": receipt[0], "recorded": receipt[1],
        "evidence_id": row["id"], "net_quote_flow_raw": raw,
        "net_quote_flow_native": native, "net_quote_flow_usd": native * rate,
        "conversion_basis": payload["conversion_basis"],
    }


def _percentiles(values: list[float]) -> list[float]:
    """Return stable average-rank percentiles; equal values receive equal rank."""
    if len(values) == 1:
        return [1.0]
    ordered = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        percentile = ((cursor + end - 1) / 2.0) / (len(values) - 1)
        for _, index in ordered[cursor:end]:
            result[index] = percentile
        cursor = end
    return result


def build_capital_cross_section(
    items: Iterable[Mapping[str, Any]], *, round_id: str,
    decision_at: Any, activated_at: Any, remaining_slots: Any,
    regime_min_breadth: float = 0.5, regime_min_depth_health: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Build per-token ranker/regime contexts from one bounded as-of round.

    Ranking score is the equal-weight average of cross-sectional percentiles
    for price return, liquidity return, and actual net-flow/current-liquidity.
    Regime breadth is the share with both positive price return and positive
    actual net flow; depth health is the non-declining-liquidity share.
    """
    decision, activated = _time(decision_at), _time(activated_at)
    slots = _number(remaining_slots)
    min_breadth, min_depth = _number(regime_min_breadth), _number(regime_min_depth_health)
    supplied = list(islice(items, MAX_TOKENS + 1))
    if (not str(round_id or "").strip() or not decision or not activated or decision < activated
            or slots is None or slots < 0.0 or min_breadth is None or min_depth is None
            or not 0.0 <= min_breadth <= 1.0 or not 0.0 <= min_depth <= 1.0
            or len(supplied) > MAX_TOKENS):
        return {}

    identities: list[tuple[str, str]] = []
    for item in supplied:
        if not isinstance(item, Mapping):
            continue
        identity = _identity(item.get("token_id"), item.get("pair_address"))
        if identity:
            identities.append(identity)
    if len(set(identities)) != len(identities) or len({pair for _, pair in identities}) != len(identities):
        return {}

    candidates: list[dict[str, Any]] = []
    for item in supplied:
        if not isinstance(item, Mapping):
            continue
        identity = _identity(item.get("token_id"), item.get("pair_address"))
        if not identity:
            continue
        token_id, pair_address = identity
        market = _market_history(item, token_id, pair_address, decision, activated)
        flow = _actual_flow(item.get("amountful_flow"), token_id, pair_address, decision, activated)
        if market is None or flow is None:
            continue
        price_return = market["latest_price"] / market["first_price"] - 1.0
        liquidity_return = market["latest_liquidity"] / market["first_liquidity"] - 1.0
        flow_depth = flow["net_quote_flow_usd"] / market["latest_liquidity"]
        observed = max(market["observed"], flow["observed"])
        recorded = max(market["recorded"], flow["recorded"])
        candidates.append({
            "token_id": token_id, "pair_address": pair_address,
            "observed_at": _stamp(observed), "recorded_at": _stamp(recorded),
            "price_return": price_return, "liquidity_return": liquidity_return,
            "actual_net_flow_usd": flow["net_quote_flow_usd"],
            "actual_net_flow_to_liquidity": flow_depth,
            "amountful_evidence_id": flow["evidence_id"],
            "market_latest_sample_id": market["latest_sample_id"],
            "history_start_at": market["first_observed_at"],
            "flow_semantics": "actual_notional",
            "conversion_basis": flow["conversion_basis"],
        })
    if len(candidates) < MIN_CROSS_SECTION_SIZE:
        return {}

    dimensions = [
        _percentiles([candidate[field] for candidate in candidates])
        for field in ("price_return", "liquidity_return", "actual_net_flow_to_liquidity")
    ]
    for index, candidate in enumerate(candidates):
        candidate["score"] = sum(dimension[index] for dimension in dimensions) / len(dimensions)
    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["token_id"]))

    breadth = sum(
        candidate["price_return"] > 0.0 and candidate["actual_net_flow_usd"] > 0.0
        for candidate in candidates
    ) / len(candidates)
    depth_health = sum(candidate["liquidity_return"] >= 0.0 for candidate in candidates) / len(candidates)
    observed = max(_time(candidate["observed_at"]) for candidate in candidates)
    recorded = max(_time(candidate["recorded_at"]) for candidate in candidates)
    common = {
        "round_id": str(round_id), "observed_at": _stamp(observed),
        "recorded_at": _stamp(recorded), "all_asof": True,
        "candidate_count": len(candidates),
    }
    ranker = {
        **common, "remaining_slots": slots, "score_method": SCORE_METHOD,
        "candidates": candidates,
    }
    regime = {
        **common, "cross_section_breadth": breadth, "depth_health": depth_health,
        "breadth_basis": "positive_price_return_and_positive_actual_net_flow_share",
        "depth_basis": "nondeclining_exact_pool_liquidity_share",
        "throttle": "allow" if breadth >= min_breadth and depth_health >= min_depth else "throttle",
    }
    return {
        candidate["token_id"]: {
            "ranker": {**ranker, "candidates": [dict(value) for value in candidates]},
            "regime": dict(regime),
        }
        for candidate in candidates
    }


__all__ = [
    "MAX_TOKENS", "MAX_HISTORY_PER_TOKEN", "MAX_FRESH_AGE_SECONDS",
    "MAX_HISTORY_AGE_SECONDS", "MIN_CROSS_SECTION_SIZE", "SCORE_METHOD",
    "build_capital_cross_section",
]
