"""Manual Paper-only pause of the losing delayed washout entry arm."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
ARM = "alpha222_washout_half_reclaim_v1"
REPORT = "docs/PROJECT_CONTEXT/WASHOUT_AND_OLD_POOL224_20260918.md"


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("washout convergence is Paper-only")
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
                    Store.chain_meme_trader_effective_definition_from_connection(db, version, raw)["policies"]}
        if ARM not in policies:
            raise RuntimeError("washout arm missing")
        row = db.execute(
            "SELECT COUNT(*) AS terminals, COUNT(DISTINCT token_id) AS tokens, "
            "COALESCE(SUM(realized_pnl_usd),0) AS net_usd, "
            "SUM(CASE WHEN status='written_off' THEN 1 ELSE 0 END) AS writeoffs "
            "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? "
            "AND status IN ('closed','written_off')", (version, ARM),
        ).fetchone()
        evidence = {key: row[key] for key in row.keys()}
        if (evidence["terminals"] < 40 or evidence["tokens"] < 40
                or evidence["net_usd"] > -150 or evidence["writeoffs"] < 5):
            raise RuntimeError("natural terminal loss threshold not met")
        result = {"status": "preview", "version": version, "arm": ARM,
                  "evidence": evidence, "already_paused": bool(policies[ARM].get("entry_paused"))}
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
            "state": "FAILED_FORWARD_EXPECTANCY", "assessment_status": "FAILED",
            "reason": "washout224: 40+ independent natural terminal losses and 5+ full pool writeoffs; pause new entries only",
            "assessment_evidence": REPORT, "terminal_at_pause": evidence,
        }
        new["updated_at"] = now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                   (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now))
        after = {p["arm_id"]: p for p in
                 Store.chain_meme_trader_effective_definition_from_connection(db, version, raw)["policies"]}
        if not after[ARM].get("entry_paused"):
            raise RuntimeError("pause overlay did not take effect")
        receipt = "washout224:convergence:" + now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)", (
            receipt, json.dumps({"at": now, "version": version,
                                 "previous_control": old, "evidence": evidence},
                                ensure_ascii=False, sort_keys=True), now))
        db.commit()
        return {**result, "status": "applied", "at": now, "receipt_key": receipt}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))
