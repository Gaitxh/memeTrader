"""Pure adapters from persisted market evidence to capital exit evaluators.

The caller supplies already-bounded Store rows.  This module performs no I/O
and never promotes transaction counts to capital flow.  ``amountful_rows`` and
``vault_rows`` are ``chain_meme_pattern_evidence`` rows with either a decoded
``payload`` mapping or ``payload_json``.  Rows must include ``id``, ``token_id``,
``pair_address``, ``observed_at`` and ``recorded_at``.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .capital_exits import SELL, SELL_PARTIAL, evaluate_exit
from .models import canonical_token_address


MAX_EVIDENCE_AGE_SECONDS = 15.0
CONFIRMED_VAULT_GRANULARITY = "confirmed_slot_net_not_transaction_identity"


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


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _uint(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 and str(value).strip().lstrip("+").isdigit() else None


def _signed_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("payload")
    if isinstance(value, Mapping):
        return dict(value)
    value = row.get("payload_json")
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return dict(decoded) if isinstance(decoded, Mapping) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _pair(token_id: str, value: Any) -> str:
    chain = token_id.split(":", 1)[0]
    return canonical_token_address(chain, str(value or ""))


def _identity(row: Mapping[str, Any], token_id: str, pair_address: str) -> bool:
    return (
        str(row.get("token_id") or "") == token_id
        and _pair(token_id, row.get("pair_address")) == pair_address
    )


def _receipt(row: Mapping[str, Any], now: datetime, *, fresh: bool) -> bool:
    observed = _time(row.get("observed_at"))
    recorded = _time(row.get("recorded_at"))
    if observed is None or recorded is None or not observed <= recorded <= now:
        return False
    return not fresh or 0.0 <= (now - observed).total_seconds() <= MAX_EVIDENCE_AGE_SECONDS


def _ratio(after: float | None, before: float | None) -> float | None:
    return after / before - 1.0 if after is not None and before is not None and before > 0.0 else None


def _flow_values(
    row: Mapping[str, Any], token_id: str, pair_address: str, now: datetime,
) -> dict[str, Any] | None:
    """Return actual transfer flow converted by its recorded quote reference."""
    if not _identity(row, token_id, pair_address) or not _receipt(row, now, fresh=True):
        return None
    payload = _payload(row)
    resolver = payload.get("resolver")
    conversion = payload.get("quote_conversion")
    if not isinstance(resolver, Mapping) or not isinstance(conversion, Mapping):
        return None
    quote_mint = str(payload.get("quote_mint") or resolver.get("quote_mint") or "")
    decimals = resolver.get("quote_decimals")
    # Signed net flow is the sole raw amount that may be negative.
    signed_raw = _signed_int(payload.get("net_quote_flow_raw"))
    rate = _number(conversion.get("usd_per_quote"))
    conversion_observed = _time(conversion.get("observed_at"))
    conversion_recorded = _time(conversion.get("recorded_at", conversion.get("ingested_at")))
    resolver_observed = _time(resolver.get("observed_at"))
    resolver_recorded = _time(resolver.get("recorded_at", resolver.get("ingested_at")))
    decision = _time(payload.get("decision_at")) or _time(row.get("recorded_at"))
    max_age = _number(conversion.get("max_age_seconds"))
    valid = bool(
        payload.get("complete") is True
        and payload.get("scan_complete") is True
        and payload.get("future_data_rejected") is not True
        and payload.get("usd_conversion_complete") is True
        and str(payload.get("conversion_basis") or "")
        and resolver.get("status") == "verified"
        and str(resolver.get("pool_address") or "") == str(payload.get("pool_address") or "")
        and _pair(token_id, resolver.get("pool_address")) == pair_address
        and str(resolver.get("base_mint") or "") == token_id.split(":", 1)[-1]
        and quote_mint
        and str(resolver.get("quote_mint") or "") == quote_mint
        and str(conversion.get("quote_mint") or "") == quote_mint
        and type(decimals) is int and 0 <= decimals <= 18
        and signed_raw is not None
        and rate is not None and rate > 0.0
        and conversion_observed is not None and conversion_recorded is not None
        and resolver_observed is not None and resolver_recorded is not None
        and decision is not None and max_age is not None and max_age >= 0.0
        and conversion_observed <= conversion_recorded <= decision <= now
        and 0.0 <= (decision - conversion_observed).total_seconds() <= max_age
        and resolver_observed <= resolver_recorded <= decision
    )
    if not valid:
        return None
    native = signed_raw / 10 ** decimals
    return {
        "evidence_id": int(row["id"]),
        "observed_at": row.get("observed_at"),
        "recorded_at": row.get("recorded_at"),
        "net_quote_flow_raw": signed_raw,
        "net_quote_flow_native": native,
        "net_quote_flow_usd": native * rate,
        "effective_breadth": _number(payload.get("effective_breadth")),
        "top3_buy_notional_share": _number(payload.get("top3_notional_share")),
        "creator_sell_notional_usd": (
            _number(payload.get("creator_sell_quote_notional_usd"))
            if payload.get("creator_identity_kind") == "token_creator"
            and payload.get("creator_identity_verified") is True
            else None
        ),
        "total_sell_notional_usd": _number(payload.get("sell_quote_notional_usd")),
        "quote_mint": quote_mint,
        "quote_usd_rate": rate,
        "conversion_basis": str(payload["conversion_basis"]),
    }


def _ordered_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        list(rows)[-2:],
        key=lambda row: (_time(row.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc), int(row.get("id") or 0)),
    )


def _adapt_position(position: Mapping[str, Any]) -> dict[str, Any]:
    token_id = str(position.get("token_id") or "")
    pair_address = _pair(token_id, position.get("entry_pair_address", position.get("pair_address")))
    stake = _number(position.get("stake_usd"))
    realized = _number(position.get("realized_proceeds_usd"))
    allocated = _number(position.get("allocated_cost_usd"))
    amount = _uint(position.get("amount_raw"))
    initial = _uint(position.get("initial_amount_raw"))
    sold_fraction = (
        1.0 - amount / initial
        if amount is not None and initial is not None and initial > 0 and amount <= initial
        else None
    )
    recovered = bool(
        position.get("principal_recovered")
        or (
            stake is not None and stake > 0.0
            and realized is not None and realized >= stake
        )
    )
    return {
        "opened_at": position.get("opened_at"),
        "token_id": token_id,
        "pair_address": pair_address,
        "principal_recovered": recovered,
        "cost_covered": recovered,
        "principal_usd": stake,
        "stake_usd": stake,
        "realized_proceeds_usd": realized,
        "allocated_cost_usd": allocated,
        "remaining_cost_usd": max(0.0, stake - allocated) if stake is not None and allocated is not None else None,
        "sold_fraction": sold_fraction,
        "amount_raw": amount,
        "initial_amount_raw": initial,
    }


def build_capital_exit_frame(
    position_row: Mapping[str, Any], market_mark: Mapping[str, Any],
    entry_snapshot: Mapping[str, Any], amountful_rows: Iterable[Mapping[str, Any]],
    vault_rows: Iterable[Mapping[str, Any]], *, kind: str, now: Any,
    state: Mapping[str, Any] | None = None,
    previous_market: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one evaluator frame without changing caller inputs."""
    decision = _time(now)
    position = _adapt_position(position_row)
    token_id, pair_address = position["token_id"], position["pair_address"]
    vault_rows = list(vault_rows)
    if kind == "vault_hazard" and vault_rows:
        return position, _vault_frame(
            _ordered_rows(vault_rows)[-1], token_id, pair_address,
        )
    context_state = dict((state or {}).get("capital_context") or {})
    market_ok = bool(decision and _identity(market_mark, token_id, pair_address)
                     and _receipt(market_mark, decision, fresh=True)
                     and str(market_mark.get("status") or "VISIBLE") == "VISIBLE")
    price = _number(market_mark.get("price_usd")) if market_ok else None
    liquidity = _number(market_mark.get("liquidity_usd")) if market_ok else None
    if price is not None and price <= 0.0:
        price = None
    if liquidity is not None and liquidity < 0.0:
        liquidity = None

    opened_at = _time(position.get("opened_at"))
    entry_pair = entry_snapshot.get("entry_pair_address", entry_snapshot.get("pair_address"))
    entry_ok = bool(
        decision and opened_at and str(entry_snapshot.get("token_id") or "") == token_id
        and _pair(token_id, entry_pair) == pair_address
        and _receipt(entry_snapshot, decision, fresh=False)
        and _time(entry_snapshot.get("recorded_at")) <= opened_at
    )
    entry_price = _number(entry_snapshot.get("price_usd")) if entry_ok else None
    entry_liquidity = _number(entry_snapshot.get("liquidity_usd")) if entry_ok else None
    if entry_price is not None and entry_price <= 0.0:
        entry_price = None
    if entry_liquidity is not None and entry_liquidity <= 0.0:
        entry_liquidity = None

    quantity = _number(position_row.get("remaining_quantity_tokens"))
    if quantity is None:
        total_quantity = _number(position_row.get("paper_quantity_tokens"))
        amount, initial = position["amount_raw"], position["initial_amount_raw"]
        if total_quantity is not None and amount is not None and initial:
            quantity = total_quantity * amount / initial
    market_value = quantity * price if quantity is not None and quantity >= 0.0 and price is not None else None
    slippage_bps = _number(market_mark.get("slippage_bps", 400))
    if slippage_bps is not None and not 0.0 <= slippage_bps < 10_000.0:
        slippage_bps = None
    net_market_value = (
        market_value * (1.0 - slippage_bps / 10_000.0)
        if market_value is not None and slippage_bps is not None else None
    )
    stake, realized, remaining_cost = (
        position["stake_usd"], position["realized_proceeds_usd"], position["remaining_cost_usd"]
    )

    flow_rows = _ordered_rows(amountful_rows)
    flow_values = [_flow_values(row, token_id, pair_address, decision) for row in flow_rows] if decision else []
    current_flow = flow_values[-1] if flow_values and flow_values[-1] is not None else None
    previous_flow = next((item for item in reversed(flow_values[:-1]) if item is not None), None)
    driver = flow_rows[-1] if flow_rows else market_mark
    observed_values = [_time(market_mark.get("observed_at"))]
    recorded_values = [_time(market_mark.get("recorded_at"))]
    if flow_rows:
        observed_values.append(_time(driver.get("observed_at")))
        recorded_values.append(_time(driver.get("recorded_at")))
    observed = max((item for item in observed_values if item is not None), default=None)
    recorded = max((item for item in recorded_values if item is not None), default=None)
    driver_id = (
        f"amountful:{driver.get('id')}" if flow_rows
        else f"market:{market_mark.get('sample_sequence', market_mark.get('id', 'missing'))}"
    )
    previous_observed = _time(previous_market.get("observed_at")) if previous_market else None
    market_observed = _time(market_mark.get("observed_at"))
    previous_ok = bool(
        previous_market and decision
        and _identity(previous_market, token_id, pair_address)
        and _receipt(previous_market, decision, fresh=False)
        and previous_observed is not None and market_observed is not None
        and previous_observed < market_observed
    )
    state_observed = _time(context_state.get("market_observed_at"))
    state_previous_ok = bool(
        not previous_ok and state_observed is not None and market_observed is not None
        and state_observed < market_observed
    )
    prior_price = (_number(previous_market.get("price_usd")) if previous_ok else
                   _number(context_state.get("market_price_usd")) if state_previous_ok else None)
    prior_liquidity = (_number(previous_market.get("liquidity_usd")) if previous_ok else
                       _number(context_state.get("liquidity_usd")) if state_previous_ok else None)
    prior_observed = previous_observed if previous_ok else state_observed if state_previous_ok else None
    market_change_seconds = (
        (market_observed - prior_observed).total_seconds()
        if market_observed is not None and prior_observed is not None else None
    )
    breadth = current_flow.get("effective_breadth") if current_flow else None
    prior_breadth = previous_flow.get("effective_breadth") if previous_flow else _number(context_state.get("effective_breadth"))
    current_flow_at = _time(current_flow.get("observed_at")) if current_flow else None
    previous_flow_at = _time(previous_flow.get("observed_at")) if previous_flow else None
    breadth_change_seconds = (
        (current_flow_at - previous_flow_at).total_seconds()
        if current_flow_at is not None and previous_flow_at is not None
        and previous_flow_at < current_flow_at else None
    )
    residual_principal = (
        stake - realized if stake is not None and realized is not None else None
    )
    proposed_fraction = (
        residual_principal / net_market_value
        if residual_principal is not None and residual_principal > 0.0
        and net_market_value is not None and net_market_value > residual_principal
        else None
    )
    latest_vault = next(
        (item for item in reversed(_ordered_rows(vault_rows))
         if _valid_vault_row(item, token_id, pair_address, decision)),
        None,
    ) if decision else None
    vault_payload = _payload(latest_vault) if latest_vault else {}
    vault_direction = ((vault_payload.get("features") or {}).get("latest_direction")
                       if isinstance(vault_payload.get("features"), Mapping) else None)

    frame = {
        "frame_id": driver_id,
        "observed_at": observed.isoformat() if observed else None,
        "recorded_at": recorded.isoformat() if recorded else None,
        "token_id": token_id,
        "pair_address": pair_address,
        "value_kind": "economic",
        "market_price_usd": price,
        "market_liquidity_usd": liquidity,
        "market_observed_at": market_mark.get("observed_at") if market_ok else None,
        "market_position_value_usd": market_value,
        "net_market_position_value_usd": net_market_value,
        "sell_slippage_bps": slippage_bps,
        "position_value_ratio": _ratio(net_market_value, remaining_cost) + 1.0
        if net_market_value is not None and remaining_cost is not None and remaining_cost > 0.0 else None,
        "economic_return": (realized + net_market_value) / stake - 1.0
        if realized is not None and net_market_value is not None and stake is not None and stake > 0.0 else None,
        "proposed_sell_fraction": proposed_fraction,
        "price_return": _ratio(price, entry_price),
        "price_change_ratio_60s": (
            _ratio(price, prior_price)
            if market_change_seconds is not None and 45.0 <= market_change_seconds <= 75.0
            else None
        ),
        "market_change_window_seconds": market_change_seconds,
        "effective_depth_ratio": _ratio(liquidity, entry_liquidity) + 1.0
        if liquidity is not None and entry_liquidity is not None else None,
        "effective_depth_change_ratio": _ratio(liquidity, prior_liquidity),
        "effective_depth_change_window_seconds": market_change_seconds,
        "liquidity_change_ratio": _ratio(liquidity, prior_liquidity),
        "liquidity_change_window_seconds": market_change_seconds,
        "effective_buyer_breadth_change_ratio": _ratio(breadth, prior_breadth),
        "breadth_change_window_seconds": breadth_change_seconds,
        "effective_buyer_breadth": breadth,
        "flow_semantics": "actual_notional" if current_flow else None,
        "net_quote_flow_usd": current_flow.get("net_quote_flow_usd") if current_flow else None,
        "net_quote_flow_native": current_flow.get("net_quote_flow_native") if current_flow else None,
        "net_quote_flow_raw": current_flow.get("net_quote_flow_raw") if current_flow else None,
        "top3_buy_notional_share": current_flow.get("top3_buy_notional_share") if current_flow else None,
        "creator_or_early_holder_sell_notional_usd": current_flow.get("creator_sell_notional_usd") if current_flow else None,
        "total_sell_notional_usd": current_flow.get("total_sell_notional_usd") if current_flow else None,
        "vault_direction": vault_direction,
        "context_provenance": {
            "market_sample_sequence": market_mark.get("sample_sequence"),
            "amountful_evidence_id": current_flow.get("evidence_id") if current_flow else None,
            "amountful_previous_evidence_id": previous_flow.get("evidence_id") if previous_flow else None,
            "flow_basis": current_flow.get("conversion_basis") if current_flow else None,
            "flow_is_actual_transfer_notional": current_flow is not None,
            "creator_scope": "token_creator" if current_flow and current_flow.get("creator_sell_notional_usd") is not None else None,
            "bundle_status": "unknown",
            "depth_semantics": "visible_exact_pool_liquidity_usd",
        },
    }
    return position, frame


def _valid_vault_row(
    row: Mapping[str, Any], token_id: str, pair_address: str, now: datetime,
) -> bool:
    payload = _payload(row)
    features = payload.get("features")
    payload_observed = _time(payload.get("observed_at"))
    return bool(
        _identity(row, token_id, pair_address)
        and _receipt(row, now, fresh=True)
        and isinstance(features, Mapping)
        and str(payload.get("observer_version") or "") == "chain-pattern-exact/v1"
        and str(features.get("flow_granularity") or "") == CONFIRMED_VAULT_GRANULARITY
        and payload_observed is not None
        and payload_observed == _time(row.get("observed_at"))
    )


def _vault_frame(row: Mapping[str, Any], token_id: str, pair_address: str) -> dict[str, Any]:
    payload = _payload(row)
    features = payload.get("features") if isinstance(payload.get("features"), Mapping) else {}
    windows = features.get("windows") if isinstance(features.get("windows"), Mapping) else {}
    ten = windows.get("10") if isinstance(windows.get("10"), Mapping) else {}
    row_token = str(row.get("token_id") or "")
    row_pair = _pair(row_token, row.get("pair_address")) if row_token else ""
    return {
        "frame_id": f"vault:{row.get('id')}",
        "observed_at": row.get("observed_at"),
        "recorded_at": row.get("recorded_at"),
        "token_id": row_token,
        "pair_address": row_pair,
        "pool_target_id": row_pair,
        "slot_min": payload.get("slot_min"),
        "slot_max": payload.get("slot_max"),
        "commitment": "confirmed" if features.get("flow_granularity") == CONFIRMED_VAULT_GRANULARITY else None,
        "effective_quote_reserve_known": features.get("effective_quote_reserve_known"),
        "latest_direction": features.get("latest_direction"),
        "base_change_ratio": ten.get("base_change_ratio"),
        "raw_quote_change_ratio": ten.get("raw_quote_change_ratio"),
        "effective_quote_change_ratio": ten.get("effective_quote_change_ratio"),
        "context_provenance": {
            "vault_evidence_id": row.get("id"),
            "observer_version": payload.get("observer_version"),
            "confirmation_basis": features.get("flow_granularity"),
            "original_pool_target_id": payload.get("pool_target_id"),
        },
    }


def evaluate_capital_exit_context(
    strategy: str, position_row: Mapping[str, Any], market_mark: Mapping[str, Any],
    entry_snapshot: Mapping[str, Any], *,
    amountful_rows: Iterable[Mapping[str, Any]] = (),
    vault_rows: Iterable[Mapping[str, Any]] = (),
    state: Mapping[str, Any] | None = None, now: Any,
    policy: Mapping[str, Any] | None = None,
    previous_market: Mapping[str, Any] | None = None,
):
    """Adapt bounded Store rows and dispatch the frozen capital exit policy."""
    amountful_rows = list(amountful_rows)
    vault_rows = list(vault_rows)
    position = _adapt_position(position_row)
    decision = _time(now)
    if strategy == "vault_hazard":
        rows = _ordered_rows(vault_rows)
        valid = [row for row in rows if decision and _valid_vault_row(
            row, position["token_id"], position["pair_address"], decision
        )]
        candidates = valid or rows[-1:]
        if not candidates:
            _, missing = build_capital_exit_frame(
                position_row, market_mark, entry_snapshot, amountful_rows, (),
                kind="vault_hazard", state=state, now=now,
            )
            candidates = [{"id": "missing", "token_id": position["token_id"],
                           "pair_address": position["pair_address"],
                           "observed_at": missing["observed_at"], "recorded_at": missing["recorded_at"],
                           "payload": {}}]
        result = None
        working = copy.deepcopy(dict(state or {}))
        prior_at = _time(working.get("last_observed_at"))
        unseen = [row for row in candidates if prior_at is None or (
            _time(row.get("observed_at")) is not None and _time(row.get("observed_at")) > prior_at
        )]
        for row in unseen or candidates[-1:]:
            frame = _vault_frame(row, position["token_id"], position["pair_address"])
            result = evaluate_exit(strategy, position, frame, working, now=now, policy=policy)
            working = result[2]
            result[3].update(frame["context_provenance"])
            if result[0] in {SELL, SELL_PARTIAL}:
                break
        assert result is not None
        return result

    position, frame = build_capital_exit_frame(
        position_row, market_mark, entry_snapshot, amountful_rows, vault_rows,
        kind=strategy, state=state, now=now, previous_market=previous_market,
    )
    result = evaluate_exit(strategy, position, frame, state, now=now, policy=policy)
    action, reason, new_state, evidence = result
    evidence.update(frame["context_provenance"])
    if new_state.get("last_frame_id") == frame["frame_id"] and (
        not state or state.get("last_frame_id") != frame["frame_id"]
    ):
        new_state["capital_context"] = {
            "market_price_usd": frame.get("market_price_usd"),
            "liquidity_usd": frame.get("market_liquidity_usd"),
            "market_observed_at": frame.get("market_observed_at"),
            "effective_breadth": frame.get("effective_buyer_breadth"),
            "amountful_evidence_id": evidence.get("amountful_evidence_id"),
        }
    return action, reason, new_state, evidence


__all__ = [
    "MAX_EVIDENCE_AGE_SECONDS", "build_capital_exit_frame",
    "evaluate_capital_exit_context",
]
