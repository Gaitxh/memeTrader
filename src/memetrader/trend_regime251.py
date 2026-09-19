"""Unpaired trend continuation with a strictly-prior same-chain regime guard."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from math import isfinite
from typing import Any, Mapping, Sequence

from .models import iso, parse_time


ARM = "revision251_unpaired_trend_regime_guard_v1"
PARENT = "revision249_unpaired_trend_control_v1"
REGIME_SOURCE = "trajectory144_trend_runner_v1"
CONTRACT = "unpaired-trend-regime251/v1"
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
        raise ValueError("Exact unpaired trend parent required")
    out = deepcopy(dict(parent))
    for key in ("behavior_contract_hash", "forward_activation_snapshot_id",
                "forward_started_at", "original_forward_started_at", "runtime_addition_id"):
        out.pop(key, None)
    out.update(
        arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name="Unpaired trend runner with same-chain regime guard",
        revision_of=PARENT, source_arm_ids=[PARENT, REGIME_SOURCE],
        assessment_status="INSUFFICIENT", decision_eligible=True,
        observer_only=False, affects="paper_only", live=False,
        no_historical_backfill=True,
        comparison_semantics=(
            "Same unpaired trend signal and exits as revision249; admission alone uses "
            "strictly prior same-chain terminal outcomes of the still-running signal parent."
        ),
        description=(
            "Strict-forward revision249 continuation. Admit only when the latest <=20 "
            "unique same-chain trajectory144 parent tokens closed in the prior 6h include "
            ">=10 samples, positive net Paper PnL and <=15% writeoffs. No extra request."
        ),
    )
    out["entry_filter"] = {
        **(out.get("entry_filter") or {}), "direction": ARM,
        "regime251": deepcopy(RULES),
    }
    return out


def alias(parent_signal: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parent_signal, Mapping) or not parent_signal.get("decision_key"):
        return {}
    value = deepcopy(dict(parent_signal))
    value["decision_key"] = f"{parent_signal['decision_key']}|{ARM}"
    value.setdefault("decision_evidence", {}).update(
        regime251_contract=CONTRACT, regime251_source_arm=REGIME_SOURCE)
    return {ARM: value}


def _number(value: Any) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("unknown number")
    value = float(value)
    if not isfinite(value):
        raise ValueError("nonfinite number")
    return value


def assess(rows: Sequence[Mapping[str, Any]], *, decision_at: Any, chain: str,
           config: Mapping[str, Any] = RULES):
    now = parse_time(decision_at)
    chain = str(chain or "").lower()
    evidence = {"contract": CONTRACT, "decision_at": iso(now), "chain": chain,
                "source_arm": REGIME_SOURCE,
                "basis": "unique same-chain parent terminal tokens closed strictly before decision"}
    try:
        if config["contract"] != CONTRACT or chain not in {"solana", "bsc", "robinhood"}:
            raise ValueError("invalid contract or chain")
        maximum, minimum, limit = (int(config[k]) for k in
                                   ("max_terminals", "min_terminals", "query_limit"))
        if not 0 < minimum <= maximum <= limit:
            raise ValueError("invalid sample bounds")
        seen, selected = set(), []
        for raw in rows:
            row = dict(raw); token = str(row.get("token_id") or "")
            closed = parse_time(row["closed_at"]); status = str(row.get("status") or "")
            if (not token.startswith(chain + ":") or token in seen or not closed < now
                    or status not in {"closed", "written_off"}):
                continue
            seen.add(token)
            selected.append((token, closed, _number(row["realized_pnl_usd"]), status))
            if len(selected) >= maximum:
                break
        net = sum(x[2] for x in selected)
        writeoffs = sum(x[3] == "written_off" for x in selected)
        fraction = writeoffs / len(selected) if selected else None
        evidence.update(terminal_tokens=len(selected), net_pnl_usd=net,
                        writeoff_count=writeoffs, writeoff_fraction=fraction,
                        newest_terminal_at=iso(selected[0][1]) if selected else None,
                        oldest_terminal_at=iso(selected[-1][1]) if selected else None)
        allowed = (len(selected) >= minimum
                   and net > _number(config["min_net_pnl_usd"])
                   and fraction is not None
                   and fraction <= _number(config["max_writeoff_fraction"]))
        return allowed, ("regime251_favorable" if allowed else "regime251_unfavorable"), evidence
    except (KeyError, TypeError, ValueError, OverflowError):
        evidence["invalid_or_unknown"] = True
        return False, "regime251_invalid_or_unknown", evidence


def evaluate(connection, *, version: str, decision_at: Any, chain: str,
             config: Mapping[str, Any] = RULES):
    now = parse_time(decision_at)
    low = now - timedelta(hours=_number(config["lookback_hours"]))
    rows = connection.execute(
        "SELECT token_id,status,realized_pnl_usd,closed_at,shadow_cohort_id "
        "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? "
        "AND token_id LIKE ? AND status IN ('closed','written_off') "
        "AND closed_at>=? AND closed_at<? ORDER BY closed_at DESC,shadow_cohort_id DESC LIMIT ?",
        (version, REGIME_SOURCE, chain.lower() + ":%", iso(low), iso(now),
         int(config["query_limit"])),
    ).fetchall()
    allowed, reason, evidence = assess(rows, decision_at=now, chain=chain, config=config)
    evidence.update(lookback_hours=float(config["lookback_hours"]), query_rows=len(rows),
                    max_terminals=int(config["max_terminals"]),
                    min_terminals=int(config["min_terminals"]), extra_market_requests=0)
    return allowed, reason, evidence
