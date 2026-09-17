"""Manually pause failed migration Paper entries without changing trade history."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
ARMS = ("migration209_first_tradable_v1", "migration214_pool_persistence_v1")


def run(apply: bool = False) -> dict:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("migration convergence is Paper-only")
    path = Path(config["database"])
    if not path.is_absolute():
        path = ROOT / path
    uri = path.resolve().as_uri() + ("?mode=rw" if apply else "?mode=ro")
    db = sqlite3.connect(uri, uri=True, timeout=3)
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
        raw = db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,)
        ).fetchone()[0]
        policies = {p["arm_id"]: p for p in
                    Store.chain_meme_trader_effective_definition_from_connection(
                        db, version, raw)["policies"]}
        if any(arm not in policies for arm in ARMS):
            raise RuntimeError("migration arm missing")
        evidence = {}
        for arm in ARMS:
            result = db.execute(
                "SELECT COUNT(*) AS n, COUNT(DISTINCT token_id) AS tokens, "
                "COALESCE(SUM(realized_pnl_usd),0) AS pnl "
                "FROM chain_meme_trader_positions WHERE definition_version=? "
                "AND arm_id=? AND status IN ('closed','written_off')", (version, arm)
            ).fetchone()
            evidence[arm] = dict(result)
        if evidence[ARMS[0]]["tokens"] < 30 or evidence[ARMS[0]]["pnl"] > -100:
            raise RuntimeError("209 failure threshold not met")
        if evidence[ARMS[1]]["tokens"] < 25 or evidence[ARMS[1]]["pnl"] > -50:
            raise RuntimeError("214 failure threshold not met")
        result = {"status": "preview", "version": version, "terminal": evidence,
                  "already_paused": {arm: bool(policies[arm].get("entry_paused")) for arm in ARMS}}
        if not apply or all(result["already_paused"].values()):
            return result
        key = "chain-meme-account-convergence/v1:" + version
        old_row = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(old_row[0]) if old_row else {"arms": {}}
        new = copy.deepcopy(old)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for arm in ARMS:
            new.setdefault("arms", {})[arm] = {
                "state": "FAILED_FORWARD_EXPECTANCY", "assessment_status": "FAILED",
                "representative": None,
                "reason": "migration219: independent terminal Paper tokens show material net loss; pause new entries only",
                "assessment_evidence": "docs/PROJECT_CONTEXT/MIGRATION_CONVERGENCE219_20260917.md",
                "terminal_at_pause": evidence[arm],
            }
        new["updated_at"] = now
        db.execute(
            "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now),
        )
        after = {p["arm_id"]: p for p in
                 Store.chain_meme_trader_effective_definition_from_connection(
                     db, version, raw)["policies"]}
        if not all(after[arm].get("entry_paused") for arm in ARMS):
            raise RuntimeError("pause overlay did not take effect")
        receipt_key = "migration219:convergence:" + now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)", (
            receipt_key, json.dumps({"at": now, "version": version,
                                     "previous_control": old, "terminal": evidence},
                                    ensure_ascii=False, sort_keys=True), now,
        ))
        db.commit()
        return {**result, "status": "applied", "at": now, "receipt_key": receipt_key}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))
