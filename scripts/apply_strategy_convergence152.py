"""Pause five redundant negative EXIT150 entry carriers, preserving all history/exits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
ARMS = {
    "exit150_bank15_v1": "exit_ladder150_t15_v1",
    "exit150_bank25_v1": "exit_ladder150_t25_v1",
    "exit150_full15_v1": "exit_ladder150_t15_v1",
    "exit150_full25_v1": "exit_ladder150_t25_v1",
    "exit150_widestop_v1": "exit_ladder150_t20_v1",
}
OUTPUT = ROOT / "data" / "research" / "righttail152" / "convergence_applied.json"


def digest(connection: sqlite3.Connection, version: str) -> str:
    result = hashlib.sha256()
    for table in (
        "chain_meme_trader_v6_registrations", "chain_meme_trader_v6_activations",
        "chain_meme_trader_policy_additions", "chain_meme_trader_positions",
        "chain_meme_trader_trades", "chain_meme_trader_marks",
    ):
        clause = " WHERE definition_version=?" if table != "chain_meme_trader_v6_activations" else " WHERE definition_version=?"
        for row in connection.execute(f"SELECT * FROM {table}{clause} ORDER BY rowid", (version,)):
            result.update(json.dumps(tuple(row), default=str).encode())
    return result.hexdigest()


def database_path() -> Path:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if config.get("live", {}).get("enabled"):
        raise RuntimeError("refuse convergence mutation while Live is enabled")
    path = Path(config["database"])
    return path if path.is_absolute() else ROOT / path


def apply() -> None:
    from memetrader.store import Store

    path = database_path()
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("BEGIN IMMEDIATE")
    version = connection.execute(
        "SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
    ).fetchone()[0]
    raw = connection.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations WHERE definition_version=?",
        (version,),
    ).fetchone()[0]
    effective = Store.chain_meme_trader_effective_definition_from_connection(
        connection, version, raw,
    )
    policies = {p["arm_id"]: p for p in effective["policies"]}
    if not ARMS.keys() <= policies.keys():
        raise RuntimeError("expected EXIT150 arms are missing")
    if any(policies[arm].get("entry_paused") for arm in ARMS):
        connection.rollback()
        print(json.dumps({"status": "already_applied", "version": version}))
        return
    before_digest = digest(connection, version)
    key = "chain-meme-account-convergence/v1:" + version
    old_row = connection.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
    old = json.loads(old_row[0]) if old_row else {"arms": {}}
    new = json.loads(json.dumps(old))
    now = datetime.now(timezone.utc).isoformat()
    for arm, representative in ARMS.items():
        new.setdefault("arms", {})[arm] = {
            "state": "PAUSED_NEW_ENTRY",
            "representative": representative,
            "assessment_status": "FAILED",
            "assessment_note": (
                "EXIT150同一共享入场的参数扇出已形成49-94个终局，成本后均为负；"
                "保留更干净的t10/t15/t20/t25少量对照，暂停本臂新入场。"
            ),
            "assessment_evidence": "data/research/righttail152/convergence_applied.json",
            "reason": (
                "convergence152: redundant negative EXIT150 parameter fanout; "
                "preserve positions, exits, trades and immutable policy history"
            ),
        }
    new["activated_at"] = now
    payload = json.dumps(new, ensure_ascii=False)
    connection.execute(
        "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
        (key, payload, now),
    )
    after_effective = Store.chain_meme_trader_effective_definition_from_connection(
        connection, version, raw,
    )
    assert all(
        p.get("entry_paused") and p.get("account_lifecycle") == "PAUSED_NEW_ENTRY"
        for p in after_effective["policies"] if p["arm_id"] in ARMS
    )
    after_digest = digest(connection, version)
    assert before_digest == after_digest
    terminal = {}
    for arm in ARMS:
        row = connection.execute(
            "SELECT COUNT(*) AS n,COUNT(DISTINCT token_id) AS tokens,"
            "SUM(COALESCE(realized_pnl_usd,0)) AS pnl FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=? AND status IN ('closed','written_off')",
            (version, arm),
        ).fetchone()
        terminal[arm] = dict(row)
    connection.commit()
    connection.close()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "status": "applied", "applied_at": now, "version": version,
        "paused_new_entry": ARMS, "terminal_evidence": terminal,
        "immutable_history_digest": before_digest,
        "previous_control": old,
        "rollback": (
            "Run this script with --rollback; it restores only the saved convergence KV. "
            "Immutable policies, positions, trades, marks and existing exits are never changed."
        ),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "applied", "version": version, "paused": sorted(ARMS)}))


def rollback() -> None:
    if not OUTPUT.exists():
        raise RuntimeError("no saved convergence control to restore")
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
    path = database_path()
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
    version = saved["version"]
    key = "chain-meme-account-convergence/v1:" + version
    now = datetime.now(timezone.utc).isoformat()
    with connection:
        connection.execute(
            "UPDATE kv SET value_json=?,updated_at=? WHERE key=?",
            (json.dumps(saved["previous_control"], ensure_ascii=False), now, key),
        )
    connection.close()
    print(json.dumps({"status": "rolled_back", "version": version}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    rollback() if args.rollback else apply()
