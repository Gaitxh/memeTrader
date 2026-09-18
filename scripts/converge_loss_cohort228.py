"""Manual Paper entry pause for a frozen, materially losing arm cohort."""

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
    "alpha149_nonbsc_flow_v1",
    "alpha149_shallow_band_flow_v1",
    "alpha149_moonbag_steady_v1",
    "alpha149_washout_reclaim_v1",
    "alpha149_score_gate_band_v1",
    "alpha149_friction_multiple_escape_v1",
    "alpha149_mid_deep_band_nonbsc_v1",
    "alpha149_smooth_organic_trend_v1",
    "alpha149_depth_first_mature_v1",
    "dex_hot_impulse_v1",
    "dex_liquidity_divergence_exit_v1",
    "recipe145_6c89c7f9e7f33d0a_v1",
    "trajectory190_first_mark_trail_v1",
    "dex_profit_velocity_exit_v1",
    "trajectory187_nonsol_fast_v1",
    "alpha212_washout_reclaim_hold_control_v1",
    "alpha149_sf_extreme_buy_pressure_hold_v1",
    "alpha212_washout_reclaim_anchor_v1",
    "organic_short_observed_flow_v1",
    "dex_blowoff_exit_v1",
)
REPORT = "docs/PROJECT_CONTEXT/LOSS_COHORT_CONVERGENCE228_20260918.md"


def run(apply: bool = False, *, root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise RuntimeError("loss cohort convergence is Paper-only")
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
        version = row["definition_version"]
        row = db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,),
        ).fetchone()
        if row is None:
            raise RuntimeError("active Paper registration missing")
        raw = row["definition_json"]
        effective = {item["arm_id"]: item for item in
                     Store.chain_meme_trader_effective_definition_from_connection(
                         db, version, raw)["policies"]}
        evidence: dict[str, dict] = {}
        for arm in ARMS:
            if arm not in effective:
                raise RuntimeError(f"required arm missing: {arm}")
            row = db.execute(
                "SELECT COUNT(*) AS terminals,COUNT(DISTINCT token_id) AS tokens,"
                "COALESCE(SUM(realized_pnl_usd),0) AS net_usd,"
                "COALESCE(SUM(CASE WHEN status='written_off' THEN 1 ELSE 0 END),0) AS writeoffs "
                "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? "
                "AND status IN ('closed','written_off')", (version, arm),
            ).fetchone()
            evidence[arm] = dict(row)
            values = evidence[arm]
            if values["tokens"] < 50 or values["net_usd"] > -200:
                raise RuntimeError(f"frozen loss threshold not met: {arm}")
        pending = [arm for arm in ARMS if not effective[arm].get("entry_paused")]
        result = {"status": "preview", "version": version,
                  "evidence": evidence, "pending_arms": pending}
        if not apply:
            return result
        if not pending:
            db.rollback()
            return {**result, "status": "already_applied"}
        key = "chain-meme-account-convergence/v1:" + version
        row = db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        old = json.loads(row["value_json"]) if row else {"arms": {}}
        new = copy.deepcopy(old)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new["activated_at"] = old.get("activated_at") or now
        for arm in pending:
            new.setdefault("arms", {})[arm] = {
                "state": "FAILED_FORWARD_EXPECTANCY", "assessment_status": "FAILED",
                "reason": "loss228: >=50 independent terminal tokens and <=-200U net; entry pause only",
                "assessment_evidence": REPORT, "terminal_at_pause": evidence[arm],
            }
        new["updated_at"] = now
        db.execute(
            "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
            (key, json.dumps(new, ensure_ascii=False, sort_keys=True), now),
        )
        after = {item["arm_id"]: item for item in
                 Store.chain_meme_trader_effective_definition_from_connection(
                     db, version, raw)["policies"]}
        if any(not after[arm].get("entry_paused") for arm in pending):
            raise RuntimeError("pause overlay did not take effect")
        receipt = "loss228:convergence:" + now
        db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)", (
            receipt, json.dumps({"at": now, "version": version, "previous_control": old,
                                 "evidence": evidence, "paused_arms": pending},
                                ensure_ascii=False, sort_keys=True), now,
        ))
        db.commit()
        return {**result, "status": "applied", "at": now, "receipt_key": receipt}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.apply), ensure_ascii=False, indent=2))
