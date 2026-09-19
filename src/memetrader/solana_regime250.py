"""Solana-runner continuation gated by strictly prior parent outcomes."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from math import isfinite
from typing import Any, Mapping, Sequence

from .models import iso, parse_time
from .trajectory_regime187 import _clone


ARM = "revision250_solana_runner_regime_guard_v1"
PARENT = "trajectory187_solana_runner_v1"
CONTRACT = "solana-runner-regime250/v1"
RULES = {
    "contract": CONTRACT,
    "lookback_hours": 6.0,
    "query_limit": 64,
    "max_terminals": 20,
    "min_terminals": 10,
    "min_net_pnl_usd": 0.0,
    "max_writeoff_fraction": 0.15,
}


def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get("arm_id") != PARENT:
        raise ValueError("Exact Solana runner parent required")
    out = _clone(parent, ARM, "Solana runner with recent-regime guard")
    out.pop("paired_opportunity_group", None)
    out.pop("excess_return_vs_arm", None)
    out["entry_filter"] = {
        **(out.get("entry_filter") or {}),
        "direction": ARM,
        "regime250": deepcopy(RULES),
    }
    out.update(
        revision_of=PARENT,
        source_arm_ids=[PARENT],
        comparison_semantics=(
            "Same Solana parent signal and exits; admission alone depends on strictly "
            "earlier terminal outcomes of the still-running parent."
        ),
        description=(
            "Exact trajectory187 Solana runner signal and exits. Admit only when the "
            "latest <=20 unique parent terminal tokens closed in the prior 6h include "
            ">=10 samples, positive net Paper PnL and <=15% writeoffs. No future data, "
            "historical backfill or extra market request; hypothesis only."
        ),
    )
    return out


def alias(parent_signal: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parent_signal, Mapping) or not parent_signal.get("decision_key"):
        return {}
    value = deepcopy(dict(parent_signal))
    value["decision_key"] = f"{parent_signal['decision_key']}|{ARM}"
    value.setdefault("decision_evidence", {}).update(
        regime250_contract=CONTRACT,
        regime250_source_arm=PARENT,
    )
    return {ARM: value}


def _number(value: Any) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("unknown number")
    value = float(value)
    if not isfinite(value):
        raise ValueError("nonfinite number")
    return value


def assess(rows: Sequence[Mapping[str, Any]], *, decision_at: Any,
           config: Mapping[str, Any] = RULES):
    now = parse_time(decision_at)
    evidence = {
        "contract": CONTRACT,
        "decision_at": iso(now),
        "source_arm": PARENT,
        "basis": "unique Solana-parent terminal tokens closed strictly before decision",
    }
    try:
        if config["contract"] != CONTRACT:
            raise ValueError("wrong contract")
        maximum = int(config["max_terminals"])
        minimum = int(config["min_terminals"])
        limit = int(config["query_limit"])
        if not 0 < minimum <= maximum <= limit:
            raise ValueError("invalid sample bounds")
        seen, selected = set(), []
        for raw in rows:
            row = dict(raw)
            token = str(row.get("token_id") or "")
            closed = parse_time(row["closed_at"])
            status = str(row.get("status") or "")
            if (not token.startswith("solana:") or token in seen or not closed < now
                    or status not in {"closed", "written_off"}):
                continue
            seen.add(token)
            selected.append((token, closed, _number(row["realized_pnl_usd"]), status))
            if len(selected) >= maximum:
                break
        net = sum(x[2] for x in selected)
        writeoffs = sum(x[3] == "written_off" for x in selected)
        fraction = writeoffs / len(selected) if selected else None
        evidence.update(
            terminal_tokens=len(selected),
            net_pnl_usd=net,
            writeoff_count=writeoffs,
            writeoff_fraction=fraction,
            newest_terminal_at=iso(selected[0][1]) if selected else None,
            oldest_terminal_at=iso(selected[-1][1]) if selected else None,
        )
        allowed = (
            len(selected) >= minimum
            and net > _number(config["min_net_pnl_usd"])
            and fraction is not None
            and fraction <= _number(config["max_writeoff_fraction"])
        )
        return allowed, ("regime250_favorable" if allowed else "regime250_unfavorable"), evidence
    except (KeyError, TypeError, ValueError, OverflowError):
        evidence["invalid_or_unknown"] = True
        return False, "regime250_invalid_or_unknown", evidence


def evaluate(connection, *, version: str, decision_at: Any,
             config: Mapping[str, Any] = RULES):
    now = parse_time(decision_at)
    low = now - timedelta(hours=_number(config["lookback_hours"]))
    rows = connection.execute(
        "SELECT token_id,status,realized_pnl_usd,closed_at,shadow_cohort_id "
        "FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id=? "
        "AND status IN ('closed','written_off') AND closed_at>=? AND closed_at<? "
        "ORDER BY closed_at DESC,shadow_cohort_id DESC LIMIT ?",
        (version, PARENT, iso(low), iso(now), int(config["query_limit"])),
    ).fetchall()
    allowed, reason, evidence = assess(rows, decision_at=now, config=config)
    evidence.update(
        lookback_hours=float(config["lookback_hours"]),
        query_rows=len(rows),
        max_terminals=int(config["max_terminals"]),
        min_terminals=int(config["min_terminals"]),
        min_net_pnl_usd=float(config["min_net_pnl_usd"]),
        max_writeoff_fraction=float(config["max_writeoff_fraction"]),
        extra_market_requests=0,
    )
    return allowed, reason, evidence
