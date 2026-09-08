"""Pause evidenced losing NEW entries using existing controls; preserve all ledgers."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = (
    "runner_capture_v1", "runner_capture_legacy_exit_control_v1",
    "lifecycle_baseline_v1", "lifecycle_failed_rebound_v1", "lifecycle_giveback_area_v1",
    "lifecycle_renewal_v1", "lifecycle_risk_trim_v1", "lifecycle_probe_v1",
    "inventory_cost_space_v1",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = Path(json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["database"])
    path = path if path.is_absolute() else ROOT / path
    db = sqlite3.connect(path.as_uri() + ("?mode=rw" if args.apply else "?mode=ro"), uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN IMMEDIATE" if args.apply else "BEGIN")
    version = db.execute("SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1").fetchone()[0]
    key = "chain-meme-account-convergence/v1:" + version
    old = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
    previous = json.loads(old[0]) if old else {"definition_version": version, "arms": {}}
    updated = json.loads(json.dumps(previous))
    evidence = {}
    for arm in ARMS:
        row = db.execute("SELECT COUNT(DISTINCT token_id) AS tokens, "
            "SUM(status IN ('closed','written_off')) AS terminals, SUM(status='open') AS open_positions, "
            "SUM(CASE WHEN status IN ('closed','written_off') THEN realized_pnl_usd ELSE 0 END) AS pnl "
            "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?", (version, arm)).fetchone()
        evidence[arm] = dict(row)
        if not row["terminals"] or row["terminals"] < 50 or row["pnl"] >= 0:
            raise ValueError("Current evidence does not support freeze: " + arm)
        if arm not in updated["arms"]:
            updated["arms"][arm] = {"state": "PAUSED_NEW_ENTRY", "representative": arm,
                "reason": "convergence33: replicated >=50 terminals and negative costed realized PnL"}
    changed = updated != previous
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if changed:
        updated["activated_at"] = now
    # Same transaction fingerprints prove this operation does not alter selected positions/trades.
    def ledger_digest():
        digest = hashlib.sha256()
        for arm in ARMS:
            for table, order in (("chain_meme_trader_positions", "shadow_cohort_id"), ("chain_meme_trader_trades", "id")):
                for row in db.execute(f"SELECT * FROM {table} WHERE definition_version=? AND arm_id=? ORDER BY {order}", (version, arm)):
                    digest.update(json.dumps(tuple(row), ensure_ascii=True).encode())
        return digest.hexdigest()
    before = ledger_digest()
    if args.apply and changed:
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) "
            "DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(updated, ensure_ascii=False, sort_keys=True), now))
    assert before == ledger_digest()
    db.commit()
    result = dict(applied=args.apply, changed=changed, cutoff=now, version=version, evidence=evidence,
                  previous_control=previous, new_control=updated, unchanged_ledger_sha256=before)
    out = ROOT / "data/research/strategy_convergence_20260909"
    out.mkdir(parents=True, exist_ok=True)
    (out / ("freeze_applied.json" if args.apply else "freeze_preview.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("applied", "changed", "cutoff", "version", "evidence", "unchanged_ledger_sha256")}))


if __name__ == "__main__":
    main()
