"""Manually pause a losing same-source-BUY exit variant in Paper only."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
ARM = "trajectory169_trend_runner_moonbag_v1"
CONTROL = "trajectory169_trend_runner_control_v1"
REPORT = "docs/PROJECT_CONTEXT/WASHOUT_CONFIRM_AND_MOONBAG223_20260917.md"


def paired_outcomes(db: sqlite3.Connection, version: str) -> dict:
    row = db.execute(
        "SELECT COUNT(*) AS pairs, COUNT(DISTINCT m.token_id) AS tokens, "
        "COALESCE(SUM(m.realized_pnl_usd),0) AS arm_net_usd, "
        "COALESCE(SUM(c.realized_pnl_usd),0) AS control_net_usd, "
        "COALESCE(SUM(m.realized_pnl_usd-c.realized_pnl_usd),0) AS delta_usd, "
        "SUM(CASE WHEN m.realized_pnl_usd>c.realized_pnl_usd+0.000001 THEN 1 ELSE 0 END) AS better, "
        "SUM(CASE WHEN m.realized_pnl_usd<c.realized_pnl_usd-0.000001 THEN 1 ELSE 0 END) AS worse "
        "FROM chain_meme_trader_positions m JOIN chain_meme_trader_positions c "
        "ON c.definition_version=m.definition_version AND c.token_id=m.token_id "
        "AND c.shadow_cohort_id=m.shadow_cohort_id "
        "AND c.source_buy_trade_id=m.source_buy_trade_id "
        "WHERE m.definition_version=? AND m.arm_id=? AND c.arm_id=? "
        "AND m.status IN ('closed','written_off') AND c.status IN ('closed','written_off') "
        "AND m.source_buy_trade_id IS NOT NULL",
        (version, ARM, CONTROL),
    ).fetchone()
    return {key: row[key] for key in row.keys()}


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("moonbag convergence is Paper-only")
    path = Path(config["database"])
    if not path.is_absolute():
        path = root / path
    db = sqlite3.connect(path.resolve().as_uri() + ("?mode=rw" if apply else "?mode=ro"),
                         uri=True, timeout=3)
    db.row_factory = sqlite3.Row
    try:
        if apply:
            db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("no active Paper definition")
        version = row[0]
        raw = db.execute("SELECT definition_json FROM chain_meme_trader_v6_registrations "
                         "WHERE definition_version=?", (version,)).fetchone()[0]
        policies = {p["arm_id"]: p for p in
                    Store.chain_meme_trader_effective_definition_from_connection(
                        db, version, raw)["policies"]}
        if ARM not in policies or CONTROL not in policies:
            raise RuntimeError("paired policies missing")
        evidence = paired_outcomes(db, version)
        if (evidence["pairs"] < 100 or evidence["tokens"] < 100
                or evidence["delta_usd"] > -100):
            raise RuntimeError("exact-source terminal evidence threshold not met")
        result = {"status": "preview", "version": version, "paired": evidence,
                  "already_paused": bool(policies[ARM].get("entry_paused"))}
        if not apply:
            return result
        if result["already_paused"]:
            db.rollback()
            return {**result, "status": "already_applied"}
        key = "chain-meme-account-convergence/v1:" + version
        old_row = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(old_row[0]) if old_row else {"arms": {}}
        new = copy.deepcopy(old)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new["activated_at"] = old.get("activated_at") or now
        new.setdefault("arms", {})[ARM] = {
            "state": "FAILED_SAME_SOURCE_EXIT_VARIANT", "assessment_status": "FAILED",
            "representative": CONTROL,
            "reason": "moonbag223: exact-source terminal Paper pairs underperform control; pause new entries only",
            "assessment_evidence": REPORT, "terminal_at_pause": evidence,
        }
        new["updated_at"] = now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                   (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now))
        after = {p["arm_id"]: p for p in
                 Store.chain_meme_trader_effective_definition_from_connection(
                     db, version, raw)["policies"]}
        if not after[ARM].get("entry_paused"):
            raise RuntimeError("pause overlay did not take effect")
        receipt_key = "moonbag223:convergence:" + now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)", (
            receipt_key, json.dumps({"at": now, "version": version,
                                     "previous_control": old, "paired": evidence},
                                    ensure_ascii=False, sort_keys=True), now))
        db.commit()
        return {**result, "status": "applied", "at": now, "receipt_key": receipt_key}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))
