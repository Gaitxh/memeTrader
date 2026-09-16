"""Manual read-only inventory of every V6 policy version in the configured Paper DB."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]


def inventory(db: sqlite3.Connection) -> dict:
    db.row_factory = sqlite3.Row
    registrations = db.execute(
        "SELECT definition_version,code_registered_at,definition_json "
        "FROM chain_meme_trader_v6_registrations ORDER BY rowid"
    ).fetchall()
    if not registrations:
        raise ValueError("no V6 Paper registration found")
    versions = []
    for registration in registrations:
        version = registration["definition_version"]
        base = json.loads(registration["definition_json"])
        added = db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=?", (version,),
        ).fetchone()[0]
        versions.append({
            "definition_version": version,
            "database_registration_at": registration["code_registered_at"],
            "base_policy_count": len(base.get("policies", [])),
            "added_policy_count": added,
            "base_policies": [{
                "arm_id": policy.get("arm_id"),
                "canonical_id": policy.get("canonical_id"),
                "registered_behavior_hash": policy.get("behavior_contract_hash"),
                "entry_match_mode": policy.get("entry_match_mode"),
            } for policy in base.get("policies", [])],
        })

    current = registrations[-1]
    version = current["definition_version"]
    effective = Store.chain_meme_trader_effective_definition_from_connection(
        db, version, current["definition_json"]
    )
    arms = []
    for policy in effective["policies"]:
        arm = policy["arm_id"]
        account = db.execute(
            "SELECT recorded_at,cash_usd,realized_pnl_usd,executable_equity_usd,"
            "open_position_count,closed_position_count,written_off_position_count,"
            "valuation_status,ledger_trade_frontier_id "
            "FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1",
            (version, arm),
        ).fetchone()
        decisions = db.execute(
            "SELECT status,COUNT(*) FROM chain_meme_trader_entry_decisions "
            "WHERE definition_version=? AND arm_id=? GROUP BY status",
            (version, arm),
        ).fetchall()
        positions = db.execute(
            "SELECT COUNT(*),COUNT(DISTINCT token_id),MIN(opened_at),MAX(opened_at) "
            "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?",
            (version, arm),
        ).fetchone()
        arms.append({
            "arm_id": arm,
            "canonical_id": policy.get("canonical_id"),
            "effective_behavior_hash": policy.get("behavior_contract_hash"),
            "registered_behavior_hash": (
                policy.get("notional_revision", {}).get("registered_behavior_contract_hash")
                or policy.get("concurrency_cap_revision", {}).get("registered_behavior_contract_hash")
                or policy.get("behavior_contract_hash")
            ),
            "activated_at": policy.get("forward_started_at"),
            "activation_snapshot_id": policy.get("forward_activation_snapshot_id"),
            "entry_match_mode": policy.get("entry_match_mode"),
            "entry_family": policy.get("entry_family"),
            "lifecycle": policy.get("account_lifecycle") or "ACTIVE_FORWARD",
            "entry_paused": bool(policy.get("entry_paused")),
            "assessment_status": policy.get("assessment_status"),
            "assessment_note": policy.get("assessment_note"),
            "effective_notional_usd": policy.get("notional_usd"),
            "registered_notional_usd": policy.get("notional_revision", {}).get("registered"),
            "decision_counts": {row["status"]: row[1] for row in decisions},
            "positions": positions[0],
            "distinct_position_tokens": positions[1],
            "first_position_at": positions[2],
            "last_position_at": positions[3],
            "latest_account": dict(account) if account is not None else None,
        })

    behavior_groups = defaultdict(list)
    for arm in arms:
        behavior_groups[arm["effective_behavior_hash"]].append(arm["arm_id"])
    return {
        "scope": "configured DB; all V6 base contracts listed; current funding-period policies detailed",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registration_clock_caveat": "database registration may be a migrated import time, not original deployment",
        "historical_versions": versions,
        "current_definition_version": version,
        "current_policy_count": len(arms),
        "lifecycle_counts": dict(Counter(arm["lifecycle"] for arm in arms)),
        "entry_mode_counts": dict(Counter(str(arm["entry_match_mode"]) for arm in arms)),
        "distinct_effective_behavior_hashes": len(behavior_groups),
        "duplicate_behavior_groups": [ids for ids in behavior_groups.values() if len(ids) > 1],
        "arms": arms,
    }


def summarize(result: dict) -> dict:
    summary = {key: value for key, value in result.items()
               if key not in {"arms", "duplicate_behavior_groups"}}
    summary["duplicate_behavior_group_count"] = len(result["duplicate_behavior_groups"])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.database is None:
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        database = ROOT / config["database"]
    else:
        database = args.database
    if not database.is_absolute():
        database = ROOT / database
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        result = inventory(db)
    if args.summary:
        result = summarize(result)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
