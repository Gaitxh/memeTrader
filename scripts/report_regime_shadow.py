"""Bounded, read-only S4 components. Never used for trading or outcome fitting."""
import argparse
import collections
import json
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path


def summarize(rows, cutoff):
    tokens = {}
    rejected = 0
    for row in rows:
        try:
            obs, ing, rec = [datetime.fromisoformat(row[k].replace("Z", "+00:00"))
                             for k in ("observed_at", "ingested_at", "recorded_at")]
            if not obs <= ing <= rec <= cutoff or (rec - obs).total_seconds() > 15:
                rejected += 1
                continue
            raw = json.loads(row["raw_json"])
            pair = raw.get("pair", raw)
            age = obs.timestamp() - float(pair["pairCreatedAt"]) / 1000
            liq, price = row["liquidity_usd"], row["price_usd"]
            if not pair.get("pairAddress") or not price or not math.isfinite(price) or price <= 0 or age < 0:
                rejected += 1
                continue
            volume = row["volume_5m_usd"] or 0
            active = (row["buys_5m"] or 0) + (row["sells_5m"] or 0) >= 3 or volume >= 200
            tokens[row["token_id"]] = dict(chain=row["token_id"].split(":")[0], age=age,
                liquidity=liq, turnover=volume / liq if liq and liq > 0 else None,
                active=active, provider=raw.get("upstream_provider") or row["provider"])
        except (KeyError, TypeError, ValueError):
            rejected += 1
    result = {}
    for chain in sorted({t["chain"] for t in tokens.values()}):
        cohort = [t for t in tokens.values() if t["chain"] == chain]
        early = [t for t in cohort if t["age"] < 900]
        liquid = [t for t in early if t["liquidity"] is not None and t["liquidity"] >= 1000]
        active = [t for t in liquid if t["active"]]
        median = lambda key: statistics.median([t[key] for t in early if t[key] is not None]) if any(t[key] is not None for t in early) else None
        result[chain] = dict(unique_observed_tokens=len(cohort), early_tokens=len(early),
            early_valid_activity_tokens=len(active),
            valid_activity_share=len(active) / len(early) if early else None,
            median_early_liquidity=median("liquidity"), median_early_turnover_5m=median("turnover"),
            provider_mix=dict(collections.Counter(t["provider"] for t in early)))
    return dict(chains=result, rejected_frames=rejected)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    cutoff = datetime.now(timezone.utc)
    with sqlite3.connect(Path(args.database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        hi = db.execute("SELECT MAX(id) FROM chain_meme_trader_v6_entry_evaluations").fetchone()[0] or 0
        rows = db.execute("SELECT e.token_id,s.* FROM chain_meme_trader_v6_entry_evaluations e JOIN token_snapshots s ON s.id=e.source_snapshot_id AND s.token_id=e.token_id WHERE e.id>? AND e.id<=? AND e.reason='pattern_observation' ORDER BY e.id", (max(0, hi-4000), hi)).fetchall()
    result = dict(schema="regime-components-shadow-v1", cutoff=cutoff.isoformat(),
        evaluation_frontier=hi, max_evaluation_span=4000, frames=len(rows),
        decision_eligible=False, outcomes_read=False, **summarize(rows, cutoff),
        limitations=["Watch-selected denominator; not chain-wide discovery or survival rate.",
            "Latest valid causal frame per token; provider missingness is not market weakness.",
            "No scalar ranking or entry/sizing modification; prospective outcome validation required."])
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
