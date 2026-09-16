"""Read-only, bounded Paper cohort terminal audit for a manually chosen window."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def classify(decisions: list[sqlite3.Row], filled: bool, safety: list[dict],
             positions: int = 0) -> str:
    if filled:
        return "source_buy_filled"
    if positions:
        return "position_without_v6_source_fill"
    if any(row["status"] == "admitted" for row in decisions):
        states = [str(row.get("safety_status") or "") for row in safety]
        if "REJECT" in states or "CHECKED_REJECT" in states:
            return "safety_reject"
        if "WAIT_DEX_BUY_ONLY" in states:
            return "buy_only_no_sell"
        if "CHECKED_WEAK" in states or "WAIT_WEAK" in states:
            return "weak_sellability_evidence"
        if "CHECKED_UNKNOWN" in states:
            allowed = [row.get("assessment", {}).get("allow") for row in safety
                       if row.get("safety_status") == "CHECKED_UNKNOWN"]
            if allowed and allowed[-1] is False:
                return "safety_unknown_not_allowed"
            return "unknown_safety_or_next_frame"
        if "EXPIRED_SECURITY_OR_NEXT_FRAME" in states:
            return "expired_cause_unresolved"
        return "admitted_pending_or_unresolved"
    if decisions and all(row["reason"] == "entry_cash_below_order_size" for row in decisions):
        return "no_funded_arm_cash"
    if decisions:
        return "no_arm_admitted_other"
    return "no_arm_decision_or_native_path"


def audit(db: sqlite3.Connection, version: str, start: str, end: str,
          as_of: str, max_cohorts: int = 500, details: bool = False) -> dict:
    db.row_factory = sqlite3.Row
    cohorts = db.execute(
        "SELECT id,token_id,pair_address,entry_family,decided_at "
        "FROM chain_meme_trader_v6_cohorts WHERE definition_version=? "
        "AND decided_at>=? AND decided_at<? ORDER BY id LIMIT ?",
        (version, start, end, max_cohorts + 1),
    ).fetchall()
    if len(cohorts) > max_cohorts:
        raise ValueError(f"window exceeds {max_cohorts} cohorts; narrow the interval")

    terminals = Counter()
    terminal_tokens: dict[str, set[str]] = defaultdict(set)
    chain_counts: dict[str, Counter] = defaultdict(Counter)
    decision_counts = Counter()
    rows = []
    filled_cohorts: set[int] = set()
    filled_tokens: set[str] = set()
    position_count = 0
    position_tokens: set[str] = set()
    for cohort in cohorts:
        cohort_id = cohort["id"]
        token_id = cohort["token_id"]
        decisions = db.execute(
            "SELECT status,reason FROM chain_meme_trader_entry_decisions "
            "WHERE definition_version=? AND shadow_cohort_id=? AND decided_at<=?",
            (version, cohort_id, as_of),
        ).fetchall()
        decision_counts.update(row["status"] for row in decisions)
        fill = db.execute(
            "SELECT id FROM chain_meme_trader_v6_entry_fills "
            "WHERE definition_version=? AND entry_cohort_id=? AND filled_at<=?",
            (version, cohort_id, as_of),
        ).fetchone()
        safety = []
        for evidence in db.execute(
            "SELECT payload_json FROM chain_meme_pattern_evidence "
            "WHERE definition_version=? AND token_id=? AND pair_address=? "
            "AND kind='preentry_obvious_scam_v1' AND recorded_at<=? ORDER BY id",
            (version, token_id, cohort["pair_address"], as_of),
        ):
            try:
                payload = json.loads(evidence["payload_json"])
            except (TypeError, ValueError):
                continue
            if payload.get("cohort_id") == cohort_id:
                safety.append(payload)
        positions = db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND shadow_cohort_id=? AND opened_at<=?",
            (version, cohort_id, as_of),
        ).fetchone()[0]
        terminal = classify(decisions, fill is not None, safety, positions)
        terminals[terminal] += 1
        terminal_tokens[terminal].add(token_id)
        chain_counts[token_id.split(":", 1)[0]][terminal] += 1
        if fill is not None:
            filled_cohorts.add(cohort_id)
            filled_tokens.add(token_id)
        position_count += positions
        if positions:
            position_tokens.add(token_id)
        if details:
            rows.append({
                "cohort_id": cohort_id,
                "token_id": token_id,
                "pair_address": cohort["pair_address"],
                "decided_at": cohort["decided_at"],
                "entry_family": cohort["entry_family"],
                "terminal": terminal,
                "arm_decisions": dict(Counter(row["status"] for row in decisions)),
                "safety_states": [row.get("safety_status") for row in safety],
                "source_fill": fill is not None,
                "projected_positions": positions,
            })
    result = {
        "version": version,
        "window_start_inclusive": start,
        "window_end_exclusive": end,
        "as_of": as_of,
        "units": "cohorts and distinct token IDs; arm decisions and positions are separate",
        "cohorts": len(cohorts),
        "tokens": len({row["token_id"] for row in cohorts}),
        "arm_decisions": dict(decision_counts),
        "source_buy_filled_cohorts": len(filled_cohorts),
        "source_buy_filled_tokens": len(filled_tokens),
        "projected_positions": position_count,
        "position_tokens": len(position_tokens),
        "terminal_cohorts": dict(terminals),
        "terminal_distinct_tokens": {key: len(value) for key, value in terminal_tokens.items()},
        "chain_terminal_cohorts": {key: dict(value) for key, value in chain_counts.items()},
    }
    if details:
        result["details"] = rows
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="inclusive UTC ISO timestamp")
    parser.add_argument("--end", required=True, help="exclusive UTC ISO timestamp")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--max-cohorts", type=int, default=500)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    if not args.start < args.end or args.max_cohorts < 1:
        parser.error("start must precede end and max-cohorts must be positive")
    if args.database is None:
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        database = ROOT / config["database"]
    else:
        database = args.database
    if not database.is_absolute():
        database = ROOT / database
    as_of = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        version = db.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_cohorts "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        result = audit(db, version, args.start, args.end, as_of,
                       args.max_cohorts, args.details)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
