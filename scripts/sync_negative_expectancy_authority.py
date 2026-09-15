"""Latch clearly negative forward Paper arms before their accounts are fully depleted.

The sampling unit is one token, not one position. Existing positions keep their original exits;
the generated authority only pauses future entries and is applied explicitly with ``--apply``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sqlite3
import statistics
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = Path("data/authority/negative_expectancy_arms_r168.json")


def bootstrap_interval(
    values: Sequence[float], *, confidence: float, iterations: int, seed: str,
) -> tuple[float, float]:
    if not values:
        raise ValueError("values must not be empty")
    rng = random.Random(seed)
    count = len(values)
    means = sorted(
        sum(values[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(iterations)
    )
    tail = (1.0 - confidence) / 2.0

    def index(probability: float) -> int:
        return max(0, min(iterations - 1, math.ceil(probability * iterations) - 1))

    return means[index(tail)], means[index(1.0 - tail)]


def summarize_arm(
    arm_id: str,
    token_pnls: Sequence[float],
    *,
    min_tokens: int,
    min_total_loss_usd: float,
    confidence: float,
    iterations: int,
) -> dict[str, Any] | None:
    values = [float(value) for value in token_pnls]
    if len(values) < min_tokens:
        return None
    total = sum(values)
    median = statistics.median(values)
    if total > -abs(min_total_loss_usd) or median >= 0.0:
        return None
    low, high = bootstrap_interval(
        values, confidence=confidence, iterations=iterations, seed=f"negative-r168:{arm_id}",
    )
    leave_one_means = [(total - value) / (len(values) - 1) for value in values]
    worst_leave_one_mean = max(leave_one_means)
    if high >= 0.0 or worst_leave_one_mean >= 0.0:
        return None
    return {
        "arm_id": arm_id,
        "independent_token_count": len(values),
        "realized_pnl_usd": total,
        "mean_pnl_per_token_usd": statistics.mean(values),
        "median_pnl_per_token_usd": median,
        "cluster_bootstrap_confidence": confidence,
        "cluster_bootstrap_interval_usd": [low, high],
        "worst_leave_one_token_mean_usd": worst_leave_one_mean,
    }


def load_candidates(
    connection: sqlite3.Connection,
    definition_version: str,
    controlled_arms: Iterable[str],
    *,
    min_tokens: int,
    min_total_loss_usd: float,
    confidence: float,
    iterations: int,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    blocked = set(controlled_arms)
    rows = connection.execute(
        "SELECT arm_id,token_id,COUNT(*) settled_positions,"
        "SUM(COALESCE(realized_pnl_usd,0)) token_pnl,MAX(closed_at) evidence_through "
        "FROM chain_meme_trader_positions WHERE definition_version=? AND status<>'open' "
        "GROUP BY arm_id,token_id ORDER BY arm_id,token_id",
        (definition_version,),
    ).fetchall()
    by_arm: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        arm = str(row["arm_id"])
        if arm not in blocked:
            by_arm.setdefault(arm, []).append(row)

    latest_accounts = {
        str(row["arm_id"]): row
        for row in connection.execute(
            "SELECT s.* FROM chain_meme_trader_account_snapshots s JOIN ("
            " SELECT arm_id,MAX(id) id FROM chain_meme_trader_account_snapshots "
            " WHERE definition_version=? GROUP BY arm_id"
            ") latest ON latest.id=s.id",
            (definition_version,),
        )
    }
    candidates: list[dict[str, Any]] = []
    for arm, arm_rows in by_arm.items():
        summary = summarize_arm(
            arm,
            [float(row["token_pnl"]) for row in arm_rows],
            min_tokens=min_tokens,
            min_total_loss_usd=min_total_loss_usd,
            confidence=confidence,
            iterations=iterations,
        )
        if summary is None:
            continue
        account = latest_accounts.get(arm)
        summary.update(
            settled_position_count=sum(int(row["settled_positions"]) for row in arm_rows),
            evidence_through=max(str(row["evidence_through"] or "") for row in arm_rows),
            cash_usd=(float(account["cash_usd"]) if account is not None else None),
            open_position_count=(int(account["open_position_count"]) if account is not None else 0),
            reason=(
                "forward per-token after-cost PnL remains negative at the configured clustered "
                "confidence and after deleting any one token; pause entries, preserve exits"
            ),
        )
        candidates.append(summary)
    return sorted(candidates, key=lambda item: (item["mean_pnl_per_token_usd"], item["arm_id"]))


def merge_candidates(
    authority: Mapping[str, Any], candidates: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = dict(authority)
    existing = [dict(item) for item in authority.get("arms") or []]
    known = {str(item.get("arm_id")) for item in existing if item.get("arm_id")}
    added = []
    for candidate in candidates:
        arm = str(candidate.get("arm_id") or "")
        if not arm or arm in known:
            continue
        item = dict(candidate)
        existing.append(item)
        added.append(item)
        known.add(arm)
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
        raise SystemExit("negative-expectancy sync requires Paper mode with Live disabled")
    database = Path(str(config["database"]))
    if not database.is_absolute():
        database = args.config.resolve().parent / database
    authority_path = args.authority.resolve()
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    settings = authority["selection"]

    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=60) as con:
        manifest_row = con.execute(
            "SELECT value_json FROM kv WHERE key='runtime-loaded-manifest'"
        ).fetchone()
        if manifest_row is None:
            raise SystemExit("runtime-loaded-manifest is missing")
        version = str(json.loads(manifest_row[0])["definition_version"])
        if authority.get("definition_version") != version:
            raise SystemExit("authority definition_version does not match the running period")
        controlled: set[str] = set()
        for key in (
            f"chain-meme-account-convergence/v1:{version}",
            f"chain-meme-account-loss-retirement/v1:{version}",
        ):
            row = con.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
            if row:
                controlled.update((json.loads(row[0]).get("arms") or {}).keys())
        candidates = load_candidates(
            con,
            version,
            controlled,
            min_tokens=int(settings["minimum_independent_tokens"]),
            min_total_loss_usd=float(settings["minimum_total_loss_usd"]),
            confidence=float(settings["cluster_bootstrap_confidence"]),
            iterations=int(settings["bootstrap_iterations"]),
        )

    updated, added = merge_candidates(authority, candidates)
    if args.apply and added:
        _atomic_json_write(authority_path, updated)
    result = {
        "definition_version": version,
        "mode": "apply" if args.apply else "dry_run",
        "selection": settings,
        "candidate_count": len(candidates),
        "added_count": len(added),
        "added_realized_pnl_usd": sum(float(item["realized_pnl_usd"]) for item in added),
        "added": added,
        "authority_count_after": int(updated["count"]),
        "restart_required": bool(args.apply and added),
    }
    print(json.dumps(result, ensure_ascii=not args.json, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
