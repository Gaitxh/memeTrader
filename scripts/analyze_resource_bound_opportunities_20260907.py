"""Read-only, bounded current-period opportunity audit; no strategy backtest."""
import collections
import json
import pathlib
import sqlite3
import statistics
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = "chain-meme-trader/funding-20260906-v002-final-1000"
REPAIR = "2026-09-07T09:19:47Z"


def run():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    path = pathlib.Path(config["database"])
    if not path.is_absolute():
        path = ROOT / path
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
    db.row_factory = sqlite3.Row
    deadline = time.monotonic() + 60
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    cutoff = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    query = """SELECT id,token_id,source_snapshot_id,decided_at,feature_json
      FROM chain_meme_trader_v6_cohorts WHERE definition_version=?
      AND entry_family='flow_burst' AND decided_at<=? ORDER BY id DESC LIMIT 10001"""
    rows = list(db.execute(query, (VERSION, cutoff)))
    truncated = len(rows) > 10000
    rows = rows[:10000]
    groups = collections.defaultdict(list)
    ids = []
    for row in rows:
        f = json.loads(row["feature_json"])
        age = f.get("age_seconds")
        values = [f.get(k) for k in ("m5_trades", "prior55_trades", "m5_volume_usd", "prior55_volume_usd")]
        if age is None or any(v is None for v in values):
            label = "missing_comparable_baseline"
            normalized = None
        elif values[1] <= 0 or values[3] <= 0:
            label = "zero_prior_baseline"
            normalized = None
        else:
            minutes = min(55.0, age / 60 - 5)
            normalized = max(values[0] / 5 / (values[1] / minutes), values[2] / 5 / (values[3] / minutes))
            label = "normalized_pass" if normalized >= 3 else "age_amplified_reject"
        item = {"cohort_id": row["id"], "token_id": row["token_id"], "decided_at": row["decided_at"],
                "source_snapshot_id": row["source_snapshot_id"], "age_seconds": age,
                "label": label, "normalized_max_rate": normalized,
                "old_max_rate": max(f.get("tx_rate_acceleration") or 0, f.get("volume_rate_acceleration") or 0),
                "counts_volume": values}
        groups["current_period"].append(item)
        if row["decided_at"] >= REPAIR:
            groups["after_latest_repair"].append(item)
        ids.append(row["id"])
    position_query = """SELECT p.arm_id,p.shadow_cohort_id,p.token_id,p.opened_at,p.closed_at,
      p.status,p.close_reason,p.stake_usd,p.realized_pnl_usd
      FROM chain_meme_trader_positions p JOIN chain_meme_trader_v6_cohorts c
      ON c.id=p.shadow_cohort_id AND c.definition_version=p.definition_version
      WHERE p.definition_version=? AND c.entry_family='flow_burst' AND c.decided_at<=?"""
    positions = [dict(r) for r in db.execute(position_query, (VERSION, cutoff))]
    allowed_ids = set(ids)
    positions = [p for p in positions if p["shadow_cohort_id"] in allowed_ids]
    arm_counts = collections.Counter(p["arm_id"] for p in positions)
    # Coverage-selected representative, never best-return selected.
    representative = sorted(arm_counts, key=lambda a: (-arm_counts[a], a))[0] if arm_counts else None
    evidence = {"generated_at": cutoff, "version": VERSION, "repair_boundary": REPAIR,
                "cohort_query": query, "position_query": position_query,
                "cohort_limit": 10000, "limit_hit": truncated,
                "representative_arm": representative,
                "representative_selection": "largest observed flow-burst position count; alphabetical ties, no PnL selection",
                "limitations": ["Descriptive replay of existing decision features, not hypothetical executable PnL.",
                    "Old period spans execution repairs; post-repair cohort subset is reported separately.",
                    "Two positive prior baselines required to isolate duration rather than zero-baseline policy.",
                    "Rate interpretation assumes provider h1 covers pool lifetime when younger than one hour.",
                    "Underlying provider activity is aggregate reporting, not independent people or net money inflow."],
                "windows": {}}
    for name, opportunities in groups.items():
        by_id = {o["cohort_id"]: o for o in opportunities}
        selected = [p for p in positions if p["arm_id"] == representative and p["shadow_cohort_id"] in by_id]
        summaries = {}
        for label in sorted({o["label"] for o in opportunities}):
            opp = [o for o in opportunities if o["label"] == label]
            samples = [p for p in selected if by_id[p["shadow_cohort_id"]]["label"] == label]
            terminal = [p for p in samples if p["status"] in ("closed", "written_off")]
            returns = [p["realized_pnl_usd"] / p["stake_usd"] for p in terminal]
            summaries[label] = {"cohorts": len(opp), "tokens": len({o["token_id"] for o in opp}),
                "representative_positions": len(samples), "terminal": len(terminal),
                "open": sum(p["status"] == "open" for p in samples),
                "terminal_net_pnl_usd": sum(p["realized_pnl_usd"] for p in terminal),
                "terminal_median_return": statistics.median(returns) if returns else None,
                "terminal_positive": sum(p["realized_pnl_usd"] > 0 for p in terminal),
                "terminal_written_off": sum(p["status"] == "written_off" for p in terminal),
                "terminal_tokens": len({p["token_id"] for p in terminal})}
        examples = sorted([p for p in selected if p["status"] in ("closed", "written_off")],
                          key=lambda p: p["realized_pnl_usd"])
        evidence["windows"][name] = {"cohorts": len(opportunities),
            "first_decided_at": min((o["decided_at"] for o in opportunities), default=None),
            "last_decided_at": max((o["decided_at"] for o in opportunities), default=None),
            "groups": summaries,
            "examples": [{**p, "features": by_id[p["shadow_cohort_id"]]} for p in examples[:4] + examples[-4:]]}
    db.close()
    return evidence


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
