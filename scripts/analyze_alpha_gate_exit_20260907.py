"""Frozen, read-only marginal-value accounting for registered Gate and Exit pairs.

This script never instantiates Store, writes the SQLite database, fetches data, or
uses post-cutoff marks.  It deliberately distinguishes rejected Gate opportunities
from matched Exit fills: only the latter require the same actual source entry fill,
notional, and execution price.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


VERSION = "chain-meme-trader/funding-20260906-v002-final-1000"
BOUNDARY = "2026-09-07T09:19:47Z"
CUTOFF = "2026-09-07T13:38:59.399800Z"
TRADE_FRONTIER = 481693
COHORT_FRONTIER = 63036

# These are the candidate/control contracts exported by research_round2.py and
# resource_bound_research.py.  The first is deployed; zero coverage is retained.
GATE_PAIRS = (
    ("round2_chase", "round2_chase_candidate_v1", "round2_chase_control_v1"),
    ("resource_age_rate", "resource_age_rate_candidate_v1", "resource_age_rate_control_v1"),
    ("resource_cooling_hold", "resource_cooling_hold_candidate_v1", "resource_cooling_hold_control_v1"),
)
EXIT_PAIRS = (
    ("finalist_profit_budget", "finalist_profit_budget_v1", "finalist_baseline_v1"),
    ("finalist_progress_clock", "finalist_progress_clock_v1", "finalist_baseline_v1"),
    ("finalist_depth_divergence", "finalist_depth_divergence_v1", "finalist_baseline_v1"),
    ("finalist_activity_failure", "finalist_activity_failure_v1", "finalist_baseline_v1"),
    ("round2_slow_grace", "round2_slow_grace_candidate_v1", "round2_slow_grace_control_v1"),
    ("round2_giveback_duration", "round2_giveback_duration_candidate_v1", "round2_giveback_duration_control_v1"),
    ("round2_response_exhaustion", "round2_response_exhaustion_candidate_v1", "round2_response_exhaustion_control_v1"),
    ("round2_runner_requalification", "round2_runner_requalification_candidate_v1", "round2_runner_requalification_control_v1"),
    ("resource_profit_structure", "resource_profit_structure_candidate_v1", "resource_profit_structure_control_v1"),
)


def iso(value: str) -> str:
    return value.replace("Z", "+00:00")


def terminal(status: str, closed_at: str | None) -> bool:
    return status in {"closed", "written_off"} and bool(closed_at) and closed_at <= CUTOFF


def ci_token_mean(rows: list[dict]) -> dict:
    by_token: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_token[row["token_id"]].append(row["delta_pnl_usd"])
    values = [sum(v) / len(v) for v in by_token.values()]
    if len(values) < 2:
        return {"token_independent_n": len(values), "mean_delta_pnl_usd": None if not values else values[0],
                "ci95": None, "status": "INSUFFICIENT_LT_2_INDEPENDENT_TOKENS"}
    rng = random.Random(20260907)
    samples = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(10000))
    return {"token_independent_n": len(values), "mean_delta_pnl_usd": sum(values) / len(values),
            "ci95": [samples[249], samples[9749]], "status": "BOOTSTRAP_TOKEN_MEAN_10000"}


def gate_rows(conn: sqlite3.Connection, candidate: str, control: str, partition: str) -> list[dict]:
    where = "c.decided_at>=? AND c.decided_at<=?" if partition == "post_repair_clean" else "c.decided_at<?"
    params = [VERSION, candidate, control, BOUNDARY, CUTOFF] if partition == "post_repair_clean" else [VERSION, candidate, control, BOUNDARY]
    query = f"""
    SELECT c.shadow_cohort_id,c.token_id,c.status candidate_decision,k.status control_decision,
           c.decided_at candidate_decided_at,k.decided_at control_decided_at,
           cp.status candidate_status,cp.realized_pnl_usd candidate_pnl,cp.closed_at candidate_closed_at,
           kp.status control_status,kp.realized_pnl_usd control_pnl,kp.closed_at control_closed_at
    FROM chain_meme_trader_entry_decisions c
    JOIN chain_meme_trader_entry_decisions k
      ON k.definition_version=c.definition_version AND k.shadow_cohort_id=c.shadow_cohort_id
       AND k.token_id=c.token_id AND k.arm_id=?
    LEFT JOIN chain_meme_trader_positions cp
      ON cp.definition_version=c.definition_version AND cp.arm_id=c.arm_id
       AND cp.shadow_cohort_id=c.shadow_cohort_id
       AND cp.source_buy_trade_id<=?
    LEFT JOIN chain_meme_trader_positions kp
      ON kp.definition_version=k.definition_version AND kp.arm_id=k.arm_id
       AND kp.shadow_cohort_id=k.shadow_cohort_id
       AND kp.source_buy_trade_id<=?
    WHERE c.definition_version=? AND c.arm_id=? AND c.shadow_cohort_id<=? AND {where}
    ORDER BY c.shadow_cohort_id
    """
    # control arm comes first because it appears before the common version filter.
    return [dict(r) for r in conn.execute(query, [control, TRADE_FRONTIER, TRADE_FRONTIER,
                                                    VERSION, candidate, COHORT_FRONTIER, *params[3:]])]


def summarize_gate(conn: sqlite3.Connection, name: str, candidate: str, control: str, partition: str) -> dict:
    rows = gate_rows(conn, candidate, control, partition)
    rejected_complete, rejected_unknown = [], 0
    candidate_complete, candidate_unknown = 0, 0
    for row in rows:
        row["control_terminal"] = terminal(row.get("control_status") or "", row.get("control_closed_at"))
        row["candidate_terminal"] = terminal(row.get("candidate_status") or "", row.get("candidate_closed_at"))
        if row["candidate_decision"] == "rejected":
            if row["control_terminal"]:
                rejected_complete.append(row)
            else:
                rejected_unknown += 1
        elif row["candidate_decision"] == "admitted":
            if row["candidate_terminal"] and row["control_terminal"]:
                candidate_complete += 1
            else:
                candidate_unknown += 1
    avoided = sum(-float(r["control_pnl"] or 0) for r in rejected_complete if float(r["control_pnl"] or 0) < 0)
    missed = sum(float(r["control_pnl"] or 0) for r in rejected_complete if float(r["control_pnl"] or 0) > 0)
    return {
        "mechanism": name, "candidate_arm": candidate, "control_arm": control, "partition": partition,
        "common_decision_pairs": len(rows), "tokens": len({r["token_id"] for r in rows}),
        "candidate_accepted": sum(r["candidate_decision"] == "admitted" for r in rows),
        "candidate_rejected": sum(r["candidate_decision"] == "rejected" for r in rows),
        "control_accepted": sum(r["control_decision"] == "admitted" for r in rows),
        "control_rejected": sum(r["control_decision"] == "rejected" for r in rows),
        "rejected_with_complete_control_outcome": len(rejected_complete),
        "rejected_control_unknown_or_unfinished": rejected_unknown,
        "accepted_both_terminal": candidate_complete,
        "accepted_pair_unknown_or_unfinished": candidate_unknown,
        "avoided_loss_usd": avoided, "missed_profit_usd": missed,
        "net_rejected_control_outcome_usd": sum(float(r["control_pnl"] or 0) for r in rejected_complete),
        "evidence_status": "COMPLETE_REJECTION_OUTCOMES" if rejected_complete else "NO_COMPLETE_REJECTION_OUTCOMES",
        "rows": rows,
    }


def exit_rows(conn: sqlite3.Connection, candidate: str, control: str, partition: str) -> list[dict]:
    start = BOUNDARY if partition == "post_repair_clean" else "0000-01-01T00:00:00Z"
    end_clause = "p.opened_at>=? AND p.opened_at<=?" if partition == "post_repair_clean" else "p.opened_at<?"
    params = [control, VERSION, candidate, start, CUTOFF] if partition == "post_repair_clean" else [control, VERSION, candidate, BOUNDARY]
    query = f"""
    SELECT p.shadow_cohort_id,p.token_id,p.source_entry_fill_id,p.stake_usd,p.initial_amount_raw,
           p.entry_execution_price_usd,p.status candidate_status,p.realized_pnl_usd candidate_pnl,
           p.realized_proceeds_usd candidate_proceeds,p.opened_at candidate_opened_at,p.closed_at candidate_closed_at,
           p.close_reason candidate_reason,q.status control_status,q.realized_pnl_usd control_pnl,
           q.realized_proceeds_usd control_proceeds,q.opened_at control_opened_at,q.closed_at control_closed_at,
           q.close_reason control_reason,q.source_entry_fill_id control_entry_fill_id,q.stake_usd control_stake_usd,
           q.initial_amount_raw control_initial_amount_raw,q.entry_execution_price_usd control_entry_execution_price_usd
    FROM chain_meme_trader_positions p
    JOIN chain_meme_trader_positions q
      ON q.definition_version=p.definition_version AND q.shadow_cohort_id=p.shadow_cohort_id
       AND q.token_id=p.token_id AND q.arm_id=?
       AND q.source_buy_trade_id<=?
    WHERE p.definition_version=? AND p.arm_id=? AND p.source_buy_trade_id<=?
      AND p.shadow_cohort_id<=? AND {end_clause}
    ORDER BY p.shadow_cohort_id
    """
    return [dict(r) for r in conn.execute(query, [control, TRADE_FRONTIER, VERSION, candidate,
                                                    TRADE_FRONTIER, COHORT_FRONTIER, *params[3:]])]


def summarize_exit(conn: sqlite3.Connection, name: str, candidate: str, control: str, partition: str) -> dict:
    raw = exit_rows(conn, candidate, control, partition)
    valid, invalid, unfinished = [], 0, 0
    for row in raw:
        same_entry = (row["source_entry_fill_id"] is not None and row["source_entry_fill_id"] == row["control_entry_fill_id"]
                      and row["stake_usd"] == row["control_stake_usd"]
                      and row["initial_amount_raw"] == row["control_initial_amount_raw"]
                      and row["entry_execution_price_usd"] == row["control_entry_execution_price_usd"])
        row["same_actual_entry_contract"] = same_entry
        row["candidate_terminal"] = terminal(row["candidate_status"], row["candidate_closed_at"])
        row["control_terminal"] = terminal(row["control_status"], row["control_closed_at"])
        if not same_entry:
            invalid += 1
        elif not (row["candidate_terminal"] and row["control_terminal"]):
            unfinished += 1
        else:
            row["delta_pnl_usd"] = float(row["candidate_pnl"]) - float(row["control_pnl"])
            row["candidate_holding_seconds"] = (datetime.fromisoformat(iso(row["candidate_closed_at"])) - datetime.fromisoformat(iso(row["candidate_opened_at"]))).total_seconds()
            row["control_holding_seconds"] = (datetime.fromisoformat(iso(row["control_closed_at"])) - datetime.fromisoformat(iso(row["control_opened_at"]))).total_seconds()
            row["holding_duration_delta_seconds"] = row["candidate_holding_seconds"] - row["control_holding_seconds"]
            row["tail_retention_ratio"] = None if not row["control_proceeds"] else float(row["candidate_proceeds"]) / float(row["control_proceeds"])
            row["behavior_divergence"] = any((row["candidate_closed_at"] != row["control_closed_at"], row["candidate_reason"] != row["control_reason"], abs(row["delta_pnl_usd"]) > 1e-12))
            valid.append(row)
    improved = sum(r["delta_pnl_usd"] > 1e-12 for r in valid)
    worse = sum(r["delta_pnl_usd"] < -1e-12 for r in valid)
    identical = len(valid) - improved - worse
    return {
        "mechanism": name, "candidate_arm": candidate, "control_arm": control, "partition": partition,
        "same_token_cohort_pairs": len(raw), "same_entry_contract_terminal_pairs": len(valid),
        "identity_or_entry_contract_mismatch": invalid, "unknown_or_unfinished": unfinished,
        "tokens": len({r["token_id"] for r in valid}),
        "behavior_divergence": sum(r["behavior_divergence"] for r in valid),
        "candidate_better": improved, "control_better": worse, "identical": identical,
        "delta_pnl_usd": sum(r["delta_pnl_usd"] for r in valid),
        "mean_holding_duration_delta_seconds": None if not valid else sum(r["holding_duration_delta_seconds"] for r in valid) / len(valid),
        "mean_tail_retention_ratio": None if not valid else sum(
            r["tail_retention_ratio"] for r in valid if r["tail_retention_ratio"] is not None
        ) / sum(r["tail_retention_ratio"] is not None for r in valid),
        "candidate_writeoffs": sum(r["candidate_status"] == "written_off" for r in valid),
        "control_writeoffs": sum(r["control_status"] == "written_off" for r in valid),
        "time_blocks_utc_hour": dict(sorted({
            h: sum(r["candidate_opened_at"][:13] == h for r in valid)
            for h in {r["candidate_opened_at"][:13] for r in valid}
        }.items())),
        "token_ci": ci_token_mean(valid), "rows": valid,
    }


def compact(summary: dict, kind: str) -> dict:
    omit = {"rows"}
    return {k: v for k, v in summary.items() if k not in omit}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    uri = f"file:{Path(args.database).resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    boundary = {"version": VERSION, "repair_boundary": BOUNDARY, "cutoff": CUTOFF,
                "trade_frontier_max_id": TRADE_FRONTIER, "cohort_frontier_max_id": COHORT_FRONTIER,
                "rules": {"database_mode": "ro", "gate": "paired decisions; rejected outcomes require terminal control",
                          "exit": "same token+cohort+source entry fill+stake+initial amount+execution price; both terminal"}}
    (args.out_dir / "BOUNDARY.json").write_text(json.dumps(boundary, indent=2), encoding="utf-8")
    gate = {p: [summarize_gate(conn, *pair, p) for pair in GATE_PAIRS] for p in ("post_repair_clean", "earlier_isolated")}
    exit_ = {p: [summarize_exit(conn, *pair, p) for pair in EXIT_PAIRS] for p in ("post_repair_clean", "earlier_isolated")}
    (args.out_dir / "gate.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")
    (args.out_dir / "exit.json").write_text(json.dumps(exit_, indent=2), encoding="utf-8")
    print(json.dumps({"gate": {p: [compact(x, "gate") for x in rows] for p, rows in gate.items()},
                      "exit": {p: [compact(x, "exit") for x in rows] for p, rows in exit_.items()}}, indent=2))


if __name__ == "__main__":
    main()
