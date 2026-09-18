"""Manual Paper-only pause for four loss-making goldendog entry experiments."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
ARMS = (
    "alpha149_goldendog_early_impulse_v1",
    "alpha149_goldendog_revival_control_v1",
    "alpha149_goldendog_low_recovery20_control_v1",
    "alpha149_goldendog_low_recovery20_v1",
)
REPORT = "docs/PROJECT_CONTEXT/GOLDENDOG_LOSS_CONVERGENCE225_20260918.md"


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("goldendog convergence is Paper-only")
    path = Path(config["database"])
    if not path.is_absolute():
        path = root / path
    db = sqlite3.connect(path.resolve().as_uri() + ("?mode=rw" if apply else "?mode=ro"),
                         uri=True, timeout=3)
    db.row_factory = sqlite3.Row
    try:
        if apply:
            db.execute("BEGIN IMMEDIATE")
        activation = db.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if activation is None:
            raise RuntimeError("no active Paper definition")
        version = activation["definition_version"]
        registration = db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,),
        ).fetchone()
        if registration is None:
            raise RuntimeError("active Paper registration missing")
        raw = registration["definition_json"]
        policies = {policy["arm_id"]: policy for policy in
                    Store.chain_meme_trader_effective_definition_from_connection(
                        db, version, raw)["policies"]}
        evidence = {}
        for arm in ARMS:
            if arm not in policies:
                raise RuntimeError(f"required arm missing: {arm}")
            row = db.execute(
                "SELECT COUNT(*) AS terminals, COUNT(DISTINCT token_id) AS tokens, "
                "COALESCE(SUM(realized_pnl_usd),0) AS net_usd, "
                "COALESCE(SUM(CASE WHEN status='written_off' THEN 1 ELSE 0 END),0) AS writeoffs "
                "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? "
                "AND status IN ('closed','written_off')", (version, arm),
            ).fetchone()
            evidence[arm] = {key: row[key] for key in row.keys()}
            if (evidence[arm]["tokens"] < 30 or evidence[arm]["net_usd"] > -150
                    or evidence[arm]["writeoffs"] < 10):
                raise RuntimeError(f"natural terminal loss threshold not met: {arm}")
        pending = [arm for arm in ARMS if not policies[arm].get("entry_paused")]
        result = {"status": "preview", "version": version, "evidence": evidence,
                  "pending_arms": pending}
        if not apply:
            return result
        if not pending:
            db.rollback()
            return {**result, "status": "already_applied"}
        key = "chain-meme-account-convergence/v1:" + version
        old_row = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(old_row["value_json"]) if old_row else {"arms": {}}
        new = copy.deepcopy(old)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new["activated_at"] = old.get("activated_at") or now
        for arm in pending:
            new.setdefault("arms", {})[arm] = {
                "state": "FAILED_FORWARD_EXPECTANCY", "assessment_status": "FAILED",
                "reason": "goldendog225: >=30 independent terminal tokens, <=-150U net and >=10 full writeoffs; new entry only",
                "assessment_evidence": REPORT, "terminal_at_pause": evidence[arm],
            }
        new["updated_at"] = now
        db.execute(
            "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now),
        )
        after = {policy["arm_id"]: policy for policy in
                 Store.chain_meme_trader_effective_definition_from_connection(
                     db, version, raw)["policies"]}
        if any(not after[arm].get("entry_paused") for arm in pending):
            raise RuntimeError("pause overlay did not take effect")
        receipt = "goldendog225:convergence:" + now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)", (
            receipt, json.dumps({"at": now, "version": version, "previous_control": old,
                                 "evidence": evidence, "paused_arms": pending},
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
