"""Audit and optionally latch newly depleted Paper arms into the authority file.

An arm is eligible only when its latest account snapshot has cash below the configured uniform
entry size and zero open positions. The decision is latched into the existing reviewable JSON file;
it does not follow later transient snapshots automatically and does not mutate the trading DB.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = Path("data/authority/failed_arms_r39.json")


def latest_depleted_rows(
    connection: sqlite3.Connection,
    definition_version: str,
    cash_floor: float,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "WITH latest AS ("
        " SELECT arm_id,MAX(id) AS id FROM chain_meme_trader_account_snapshots"
        " WHERE definition_version=? GROUP BY arm_id"
        ") SELECT s.id,s.arm_id,s.cash_usd,s.open_position_count,s.closed_position_count,"
        "s.realized_pnl_usd,s.recorded_at FROM latest l"
        " JOIN chain_meme_trader_account_snapshots s ON s.id=l.id"
        " WHERE s.cash_usd<? AND s.open_position_count=0 ORDER BY s.cash_usd,s.arm_id",
        (definition_version, float(cash_floor)),
    ).fetchall()
    return [dict(row) for row in rows]


def merge_candidates(
    authority: Mapping[str, Any],
    candidates: Iterable[Mapping[str, Any]],
    controlled_arms: Iterable[str] = (),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = dict(authority)
    existing = [dict(item) for item in authority.get("arms") or []]
    blocked = {str(item.get("arm_id")) for item in existing if item.get("arm_id")}
    blocked.update(str(arm) for arm in controlled_arms)
    added: list[dict[str, Any]] = []
    for row in candidates:
        arm = str(row.get("arm_id") or "")
        if not arm or arm in blocked:
            continue
        item = {
            "arm_id": arm,
            "cash_usd": float(row["cash_usd"]),
            "observed_at": str(row["recorded_at"]),
        }
        existing.append(item)
        added.append(item)
        blocked.add(arm)
    result["arms"] = existing
    result["count"] = len(existing)
    return result, added


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--authority", type=Path, default=ROOT / DEFAULT_AUTHORITY)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if config.get("mode") != "paper" or bool((config.get("live") or {}).get("enabled")):
        raise SystemExit("depleted-arm authority sync requires Paper mode with Live disabled")
    database = Path(str(config["database"]))
    if not database.is_absolute():
        database = args.config.resolve().parent / database
    authority_path = args.authority.resolve()
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    cash_floor = float(authority.get("cash_floor_usdc") or 20.0)

    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as connection:
        manifest = connection.execute(
            "SELECT value_json FROM kv WHERE key='runtime-loaded-manifest'"
        ).fetchone()
        if manifest is None:
            raise SystemExit("runtime-loaded-manifest is missing")
        definition_version = str(json.loads(manifest[0])["definition_version"])
        if authority.get("definition_version") != definition_version:
            raise SystemExit("authority definition_version does not match the running period")
        controls: set[str] = set()
        for key in (
            f"chain-meme-account-convergence/v1:{definition_version}",
            f"chain-meme-account-loss-retirement/v1:{definition_version}",
        ):
            row = connection.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
            if row:
                controls.update((json.loads(row[0]).get("arms") or {}).keys())
        candidates = latest_depleted_rows(connection, definition_version, cash_floor)

    updated, added = merge_candidates(authority, candidates, controls)
    if args.apply and added:
        _atomic_json_write(authority_path, updated)
    result = {
        "definition_version": definition_version,
        "cash_floor_usdc": cash_floor,
        "mode": "apply" if args.apply else "dry_run",
        "candidate_count": len(candidates),
        "added_count": len(added),
        "added": added,
        "authority_count_after": int(updated["count"]),
        "restart_required": bool(args.apply and added),
    }
    print(json.dumps(result, ensure_ascii=not args.json, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
