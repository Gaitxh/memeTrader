"""Reversible Paper-only pause for the dominated quiet-renewal exit variant.

This is a manual, evidence-bound operation.  It does not select arms by a rolling
leaderboard and it deliberately excludes account-depletion handling.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "quiet_renewal_v1"
CONTROL = "quiet_renewal_legacy_exit_control_v1"
REPORT = "docs/PROJECT_CONTEXT/DORMANT_SPARSE_STRATEGY_REVIEW_20260919.md"
PREFIX = "sparse255:quiet-renewal-pause:"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connection(root: Path, write: bool) -> sqlite3.Connection:
    config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("Paper-only; Live must remain disabled")
    path = Path(config["database"])
    if not path.is_absolute():
        path = root / path
    con = sqlite3.connect(path.resolve().as_uri() + ("?mode=rw" if write else "?mode=ro"),
                          uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    if not write:
        con.execute("PRAGMA query_only=ON")
    return con


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    con = connection(root, apply)
    try:
        at = now()
        active = con.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if not active:
            raise RuntimeError("active Paper period missing")
        version = active[0]
        raw = con.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,)
        ).fetchone()[0]
        policies = {p["arm_id"]: p for p in
                    Store.chain_meme_trader_effective_definition_from_connection(
                        con, version, raw)["policies"]}
        if CANDIDATE not in policies or CONTROL not in policies:
            raise RuntimeError("quiet-renewal pair missing")
        if policies[CANDIDATE].get("account_lifecycle") == "RETIRED_DEPLETED":
            raise RuntimeError("account-depleted strategies are outside this operation")

        rows = con.execute(
            "SELECT a.token_id,a.opened_at,a.realized_pnl_usd candidate_pnl,"
            "b.realized_pnl_usd control_pnl,a.status candidate_status,b.status control_status "
            "FROM chain_meme_trader_positions a JOIN chain_meme_trader_positions b "
            "ON b.definition_version=a.definition_version AND b.token_id=a.token_id "
            "AND b.opened_at=a.opened_at AND b.arm_id=? "
            "WHERE a.definition_version=? AND a.arm_id=? ORDER BY a.opened_at",
            (CONTROL, version, CANDIDATE),
        ).fetchall()
        if len(rows) < 4 or any(r["candidate_status"] == "open" for r in rows):
            raise RuntimeError("paired terminal evidence is not complete")
        candidate_pnl = sum(float(r["candidate_pnl"] or 0) for r in rows)
        control_pnl = sum(float(r["control_pnl"] or 0) for r in rows)
        delta = candidate_pnl - control_pnl
        worse = sum(float(r["candidate_pnl"] or 0) < float(r["control_pnl"] or 0) for r in rows)
        ties = sum(float(r["candidate_pnl"] or 0) == float(r["control_pnl"] or 0) for r in rows)
        if delta > -20 or worse < 3:
            raise RuntimeError("frozen dominance condition not met")

        result = {
            "status": "preview", "at": at, "version": version,
            "candidate": CANDIDATE, "control": CONTROL, "paired_entries": len(rows),
            "candidate_pnl_usd": candidate_pnl, "control_pnl_usd": control_pnl,
            "candidate_minus_control_usd": delta, "candidate_worse": worse, "ties": ties,
        }
        if not apply:
            return result
        if policies[CANDIDATE].get("entry_paused"):
            con.rollback()
            return {**result, "status": "already_applied"}

        key = "chain-meme-account-convergence/v1:" + version
        existing = con.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(existing[0]) if existing else {"arms": {}}
        new = copy.deepcopy(old)
        receipt_key = PREFIX + at
        written = {
            "state": "PAUSED_NEW_ENTRY",
            "assessment_status": "INSUFFICIENT",
            "reason": (
                "255: same-entry quiet-renewal exit variant underperformed its legacy-exit "
                "control on 3 of 4 completed pairs and tied once; pause new entry, preserve "
                "history/exits; small sample is not permanent alpha proof"
            ),
            "assessment_evidence": REPORT,
            "control_receipt": receipt_key,
            "paired_result": result,
        }
        previous = copy.deepcopy(old.get("arms", {}).get(CANDIDATE))
        new.setdefault("arms", {})[CANDIDATE] = written
        new["updated_at"] = at
        con.execute(
            "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(new, ensure_ascii=False, sort_keys=True), at),
        )
        effective = {p["arm_id"]: p for p in
                     Store.chain_meme_trader_effective_definition_from_connection(
                         con, version, raw)["policies"]}
        if not effective[CANDIDATE].get("entry_paused"):
            raise RuntimeError("pause did not become effective")
        if effective[CONTROL].get("entry_paused") != policies[CONTROL].get("entry_paused"):
            raise RuntimeError("control arm changed unexpectedly")
        receipt = {**result, "status": "applied", "receipt_key": receipt_key,
                   "control_key": key, "previous": previous, "written": written}
        con.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)",
                    (receipt_key, json.dumps(receipt, ensure_ascii=False, sort_keys=True), at))
        con.commit()
        return receipt
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
