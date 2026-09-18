"""Manual Paper-only pause of a same-entry exit variant dominated by its runner."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
FAST = "trajectory144_early_activity_fast_v1"
RUNNER = "trajectory144_trend_runner_v1"
REPORT = "docs/PROJECT_CONTEXT/TRAJECTORY_FAST_PAIR_CONVERGENCE226_20260918.md"


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("trajectory convergence is Paper-only")
    path = Path(config["database"])
    if not path.is_absolute():
        path = root / path
    db = sqlite3.connect(path.resolve().as_uri() + ("?mode=rw" if apply else "?mode=ro"),
                         uri=True, timeout=3)
    db.row_factory = sqlite3.Row
    try:
        if apply:
            db.execute("BEGIN IMMEDIATE")
        active = db.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if active is None:
            raise RuntimeError("no active Paper definition")
        version = active["definition_version"]
        registration = db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,),
        ).fetchone()
        if registration is None:
            raise RuntimeError("active Paper registration missing")
        raw = registration["definition_json"]
        policies = {p["arm_id"]: p for p in
                    Store.chain_meme_trader_effective_definition_from_connection(
                        db, version, raw)["policies"]}
        if FAST not in policies or RUNNER not in policies:
            raise RuntimeError("paired trajectory arms missing")
        row = db.execute(
            "SELECT COUNT(*) AS pairs, COUNT(DISTINCT fast.token_id) AS tokens, "
            "COALESCE(SUM(fast.realized_pnl_usd),0) AS fast_net_usd, "
            "COALESCE(SUM(runner.realized_pnl_usd),0) AS runner_net_usd, "
            "SUM(CASE WHEN runner.realized_pnl_usd>fast.realized_pnl_usd+0.000001 "
            "THEN 1 ELSE 0 END) AS runner_better, "
            "SUM(CASE WHEN fast.realized_pnl_usd>runner.realized_pnl_usd+0.000001 "
            "THEN 1 ELSE 0 END) AS fast_better "
            "FROM chain_meme_trader_positions fast "
            "JOIN chain_meme_trader_positions runner "
            "ON runner.definition_version=fast.definition_version "
            "AND runner.source_buy_trade_id=fast.source_buy_trade_id "
            "AND runner.token_id=fast.token_id "
            "WHERE fast.definition_version=? AND fast.arm_id=? AND runner.arm_id=? "
            "AND fast.status IN ('closed','written_off') "
            "AND runner.status IN ('closed','written_off')",
            (version, FAST, RUNNER),
        ).fetchone()
        evidence = {key: row[key] for key in row.keys()}
        evidence["runner_minus_fast_usd"] = (
            evidence["runner_net_usd"] - evidence["fast_net_usd"])
        if (evidence["pairs"] < 100 or evidence["tokens"] < 100
                or evidence["fast_net_usd"] > -150
                or evidence["runner_minus_fast_usd"] < 300):
            raise RuntimeError("same-source terminal loss threshold not met")
        result = {"status": "preview", "version": version, "evidence": evidence,
                  "already_paused": bool(policies[FAST].get("entry_paused"))}
        if not apply:
            return result
        if result["already_paused"]:
            db.rollback()
            return {**result, "status": "already_applied"}
        key = "chain-meme-account-convergence/v1:" + version
        old_row = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(old_row["value_json"]) if old_row else {"arms": {}}
        new = copy.deepcopy(old)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new["activated_at"] = old.get("activated_at") or now
        new.setdefault("arms", {})[FAST] = {
            "state": "DOMINATED_IN_PAIRED_TEST", "assessment_status": "FAILED",
            "reason": "trajectory226: >=100 terminal exact-source tokens; runner exceeds fast by >=300U and fast loses >=150U",
            "assessment_evidence": REPORT, "terminal_at_pause": evidence,
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
        if not after[FAST].get("entry_paused") or after[RUNNER].get("entry_paused"):
            raise RuntimeError("paired arm control did not take effect")
        receipt = "trajectory226:convergence:" + now
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
