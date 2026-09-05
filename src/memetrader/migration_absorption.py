"""Strict-forward migration absorption based on actual quote amounts.

The legacy ``migration_absorption_v1`` uses DEX transaction counts for its
sell-pressure check.  This module defines a separate 5 USDC hypothesis and
does not reinterpret that contract.  Its input is the already-collected pair
surface plus exactly two adjacent amountful-flow windows; no RPC is performed.

Executable recovery is deliberately not claimed here.  The available shared
recovery shadow values open positions, while this is a pre-entry signal.
"""
from __future__ import annotations

import copy
from datetime import datetime
import math
from typing import Any, Mapping, Sequence

from .capital_policies import capital_policies


ARM_ID = "migration_amount_rate_absorption_v1"


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _raw(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 and str(value).strip() == str(result) else None


def _signed_raw(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if str(value).strip() == str(result) else None


def _payload(row: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    value = row.get("payload")
    return value if isinstance(value, Mapping) else row


def _receipt(row: Mapping[str, Any], decision: datetime, activated: datetime) -> bool:
    observed = _time(row.get("observed_at"))
    recorded = _time(row.get("recorded_at") or row.get("available_at"))
    return bool(observed and recorded and activated <= observed <= recorded <= decision)


def migration_amount_absorption_policy() -> dict[str, Any]:
    """Return a fresh append-only policy without mutating its legacy parent."""
    parent = next(policy for policy in capital_policies()
                  if policy["arm_id"] == "migration_absorption_v1")
    policy = copy.deepcopy(parent)
    policy.update(
        arm_id=ARM_ID,
        canonical_id=ARM_ID,
        name="migration_amount_rate_absorption",
        entry_family="migration_amount_rate_absorption",
        source_arm_ids=[parent["arm_id"]],
        notional_usd=5.0,
        description=(
            "canonical migration后先确认价格flush，再用两段相邻真实quote金额窗口确认"
            "SELL金额速率下降、有效买方广度扩张和同池报告流动性重建；不使用交易次数。"
        ),
        required_inputs=[
            "canonical_migration_fact", "canonical_migration_pool_surface",
            "two_adjacent_complete_amountful_flow_windows",
            "post_flush_same_pool_reported_liquidity_frames", "next_frame_trade",
        ],
        entry_filter={
            "direction": "migration_amount_rate_absorption",
            "min_flush_drawdown": 0.15,
            "max_sell_amount_rate_ratio": 1.0,
            "min_effective_breadth": 2.0,
            "min_breadth_growth": 0.0,
            "max_amountful_flow_age_seconds": 30.0,
        },
        fidelity_status="HYPOTHESIS_ONLY",
        no_historical_backfill=True,
    )
    return policy


def build_migration_amount_absorption_context(
    history: Sequence[Mapping[str, Any]],
    amountful_flow: Mapping[str, Any] | None,
    migration_fact: Mapping[str, Any] | None,
    pool_surface: Mapping[str, Any] | None,
    *,
    decision_at: Any,
    activated_at: Any,
) -> dict[str, Any]:
    """Build one causal context from decoded existing rows.

    ``history`` items require token/pair identity, price, liquidity and
    observed/recorded timestamps. ``amountful_flow`` and ``pool_surface`` may
    be decoded evidence rows (``payload`` plus DB timestamps) or merged
    payloads. ``migration_fact`` is a ``token_launch_facts`` row.
    """
    decision, activated = _time(decision_at), _time(activated_at)
    base = {"status": "WAIT", "reason": "migration_amount_inputs_missing"}
    if not decision or not activated or decision < activated or not history:
        return {"migration_amount_absorption": base}
    token_id = str(history[-1].get("token_id") or "")
    pair_address = str(history[-1].get("pair_address") or "")
    token_address = token_id.partition(":")[2]
    if not token_id.startswith("solana:") or not token_address or not pair_address:
        return {"migration_amount_absorption": {**base, "reason": "migration_identity_missing"}}

    ordered = sorted(history, key=lambda row: _time(row.get("observed_at")) or decision)
    market = []
    for row in ordered:
        price, liquidity = _number(row.get("price")), _number(row.get("liquidity"))
        if (row.get("token_id") != token_id or row.get("pair_address") != pair_address
                or not _receipt(row, decision, activated) or price is None or price <= 0
                or liquidity is None or liquidity < 1):
            return {"migration_amount_absorption": {**base, "reason": "market_identity_time_or_value_invalid"}}
        market.append({**dict(row), "price": price, "liquidity": liquidity})

    fact = migration_fact if isinstance(migration_fact, Mapping) else {}
    migration_observed = _time(fact.get("source_observed_at") or fact.get("observed_at"))
    migration_ingested = _time(fact.get("ingested_at"))
    migration_recorded = _time(fact.get("recorded_at"))
    if (fact.get("launch_event_type") != "migration" or fact.get("token_id") != token_id
            or fact.get("address") != token_address or not migration_observed
            or not migration_ingested or not migration_recorded
            or not activated <= migration_observed <= migration_ingested <= migration_recorded <= decision):
        return {"migration_amount_absorption": {**base, "reason": "migration_fact_not_strict_forward"}}

    surface_row = pool_surface if isinstance(pool_surface, Mapping) else {}
    surface = _payload(surface_row)
    if (not _receipt(surface_row, decision, activated)
            or surface_row.get("token_id", token_id) != token_id
            or surface_row.get("pair_address", pair_address) != pair_address
            or surface.get("status") != "RESOLVED" or surface.get("complete") is not True
            or surface.get("canonical_migration_pool") is not True
            or surface.get("pool_address") != pair_address
            or surface.get("base_mint") != token_address):
        return {"migration_amount_absorption": {**base, "reason": "canonical_migration_pool_unconfirmed"}}

    flow_row = amountful_flow if isinstance(amountful_flow, Mapping) else {}
    flow = _payload(flow_row)
    flow_observed = _time(flow_row.get("observed_at"))
    if (not _receipt(flow_row, decision, activated) or not flow_observed
            or (decision - flow_observed).total_seconds() > 30
            or flow_row.get("token_id", token_id) != token_id
            or flow_row.get("pair_address", pair_address) != pair_address
            or flow.get("complete") is not True or flow.get("scan_complete") is not True
            or flow.get("future_data_rejected") is True or flow.get("adjacent") is not True
            or flow.get("nonoverlap") is not True):
        return {"migration_amount_absorption": {**base, "reason": "amountful_flow_incomplete_or_stale"}}
    resolver = flow.get("resolver") or {}
    resolver_observed = _time(resolver.get("observed_at"))
    resolver_recorded = _time(resolver.get("recorded_at"))
    flow_recorded = _time(flow_row.get("recorded_at"))
    if (resolver.get("status") != "verified" or resolver.get("pool_address") != pair_address
            or resolver.get("base_mint") != token_address or not resolver.get("quote_mint")
            or not resolver_observed or not resolver_recorded or not flow_recorded
            or not resolver_observed <= resolver_recorded <= flow_recorded):
        return {"migration_amount_absorption": {**base, "reason": "amountful_flow_identity_unverified"}}
    windows = flow.get("windows")
    if not isinstance(windows, list) or len(windows) != 2:
        return {"migration_amount_absorption": {**base, "reason": "two_amountful_windows_required"}}

    normalized = []
    for window in windows:
        if not isinstance(window, Mapping):
            return {"migration_amount_absorption": {**base, "reason": "amountful_window_invalid"}}
        start, end = _time(window.get("window_start")), _time(window.get("window_end"))
        observed = _time(window.get("observed_at"))
        recorded = _time(window.get("recorded_at"))
        sells = _raw(window.get("sell_quote_notional_raw"))
        buys = _raw(window.get("buy_quote_notional_raw"))
        net = _signed_raw(window.get("net_quote_flow_raw"))
        breadth = _number(window.get("effective_breadth"))
        if (window.get("complete") is not True or not start or not end or start >= end
                or not observed or not recorded or end > observed or observed > recorded > decision
                or start < migration_recorded or None in (sells, buys, net, breadth)
                or buys - sells != net or breadth < 0):
            return {"migration_amount_absorption": {**base, "reason": "amountful_window_invalid"}}
        normalized.append({"start": start, "end": end, "duration": (end-start).total_seconds(),
            "sell_raw": sells, "buy_raw": buys, "net_raw": net, "breadth": breadth})
    previous, current = normalized
    if previous["end"] != current["start"]:
        return {"migration_amount_absorption": {**base, "reason": "amountful_windows_not_adjacent"}}

    pre_absorption = [row for row in market if _time(row["observed_at"]) <= previous["start"]]
    peak = None
    trough = None
    for row in pre_absorption:
        if peak is None or row["price"] > peak["price"]:
            peak, trough = row, None
        elif peak and row["price"] < peak["price"]:
            if trough is None or row["price"] < trough["price"]:
                trough = row
    if peak is None or trough is None or _time(peak["observed_at"]) >= _time(trough["observed_at"]):
        return {"migration_amount_absorption": {**base, "reason": "post_migration_flush_unconfirmed"}}
    recovery = [row for row in market if _time(row["observed_at"]) > _time(trough["observed_at"])]
    if len(recovery) < 2:
        return {"migration_amount_absorption": {**base, "reason": "post_flush_market_frames_missing"}}
    before_market, current_market = recovery[-2:]

    previous_rate = previous["sell_raw"] / previous["duration"]
    current_rate = current["sell_raw"] / current["duration"]
    rate_ratio = current_rate / previous_rate if previous_rate > 0 else None
    breadth_growth = current["breadth"] - previous["breadth"]
    evidence = {
        "status": "READY",
        "reason": "migration_amount_context_ready",
        "token_id": token_id, "pair_address": pair_address,
        "observed_at": current_market["observed_at"],
        "recorded_at": max(str(current_market["recorded_at"]), str(flow_row["recorded_at"]),
                           str(surface_row["recorded_at"]), str(fact["recorded_at"])),
        "signal_frame_id": current_market.get("id"),
        "migration_fact_id": fact.get("id"),
        "surface_evidence_id": surface_row.get("id") or surface.get("evidence_id"),
        "amountful_evidence_id": flow_row.get("id") or flow.get("evidence_id"),
        "canonical_migration_pool": True,
        "flush_drawdown": trough["price"] / peak["price"] - 1.0,
        "sell_amount_rate_previous_raw_per_second": previous_rate,
        "sell_amount_rate_current_raw_per_second": current_rate,
        "sell_amount_rate_ratio": rate_ratio,
        "effective_breadth_previous": previous["breadth"],
        "effective_breadth_current": current["breadth"],
        "effective_breadth_growth": breadth_growth,
        "current_net_quote_flow_raw": current["net_raw"],
        "depth_rebuilt": current_market["liquidity"] >= before_market["liquidity"],
        "depth_semantics": "dex_reported_liquidity_usd_not_executable_recovery",
        "price_absorption": current_market["price"] > before_market["price"] > trough["price"],
        "pressure_unit": "quote_mint_raw_per_second",
        "quote_mint": resolver.get("quote_mint"),
        "uses_trade_counts": False,
        "recovery_status": "NOT_MEASURED_PRE_ENTRY",
    }
    return {"migration_amount_absorption": evidence}


def migration_amount_absorption_signal(
    history: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    decision_at: Any,
    activated_at: Any,
    context: Mapping[str, Any],
) -> tuple[bool, str]:
    """Evaluate only the new amount-rate policy; execution remains next-frame."""
    decision, activated = _time(decision_at), _time(activated_at)
    evidence = context.get("migration_amount_absorption")
    config = policy.get("entry_filter") if isinstance(policy, Mapping) else None
    if (policy.get("arm_id") != ARM_ID or not decision or not activated or not history
            or not isinstance(config, Mapping)
            or config.get("direction") != "migration_amount_rate_absorption"):
        return False, "wait_migration_amount_policy"
    if not isinstance(evidence, Mapping) or evidence.get("status") != "READY":
        return False, str((evidence or {}).get("reason") or "migration_amount_inputs_missing")
    if (evidence.get("token_id") != history[-1].get("token_id")
            or evidence.get("pair_address") != history[-1].get("pair_address")
            or evidence.get("canonical_migration_pool") is not True
            or evidence.get("uses_trade_counts") is not False
            or not _receipt(evidence, decision, activated)):
        return False, "migration_amount_evidence_identity_or_time_invalid"
    values = tuple(_number(evidence.get(key)) for key in (
        "flush_drawdown", "sell_amount_rate_ratio", "effective_breadth_current",
        "effective_breadth_growth", "current_net_quote_flow_raw"))
    limits = tuple(_number(config.get(key)) for key in (
        "min_flush_drawdown", "max_sell_amount_rate_ratio",
        "min_effective_breadth", "min_breadth_growth"))
    if any(value is None for value in values + limits):
        return False, "migration_amount_metrics_missing"
    flush, rate_ratio, breadth, breadth_growth, net = values
    min_flush, max_rate, min_breadth, min_growth = limits
    passed = bool(
        flush <= -min_flush and rate_ratio < max_rate
        and breadth >= min_breadth and breadth_growth > min_growth and net > 0
        and evidence.get("depth_rebuilt") is True and evidence.get("price_absorption") is True
    )
    return (passed, "migration_amount_rate_absorption_confirmed" if passed
            else "migration_amount_rate_absorption_below_hypothesis")


__all__ = [
    "ARM_ID", "migration_amount_absorption_policy",
    "build_migration_amount_absorption_context", "migration_amount_absorption_signal",
]
