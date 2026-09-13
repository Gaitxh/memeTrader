"""Bounded, read-only discovery -> hydration -> evaluation diagnostic.

The database is append-only and can be large.  Each fact below is restricted to
the newest ID frontier of its table; this deliberately reports *recent* flow,
not an all-history denominator.  It never opens SQLite read-write.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTIER = 200_000


def chain(token_id: str) -> str:
    return (token_id or "unknown").split(":", 1)[0].lower()


def q(con, sql, args=()):
    return [dict(x) for x in con.execute(sql, args)]


def one(con, sql, args=()):
    return dict(con.execute(sql, args).fetchone())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=3)
    ap.add_argument("--frontier", type=int, default=FRONTIER)
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    db = Path(cfg["database"])
    db = db if db.is_absolute() else ROOT / db
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=1")
    con.execute("PRAGMA busy_timeout=20000")
    version = con.execute("SELECT definition_version FROM chain_meme_trader_v6_activations WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1").fetchone()[0]
    cutoff = f"-{args.hours} hour"

    # ID predicates make every scan bounded even if ISO timestamp formatting varies.
    max_exposure = con.execute("SELECT COALESCE(MAX(id),0) FROM token_discovery_exposures").fetchone()[0]
    max_snapshot = con.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
    max_eval = con.execute("SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_v6_entry_evaluations").fetchone()[0]
    exposure_floor, snap_floor, eval_floor = (max_exposure - args.frontier, max_snapshot - args.frontier, max_eval - args.frontier)

    discovered = q(con, """
      SELECT chain, COUNT(DISTINCT token_id) tokens, COUNT(*) rows
      FROM token_discovery_exposures
      WHERE id>? AND first_local_discovery=1 AND julianday(COALESCE(recorded_at,observed_at))>=julianday('now',?)
      GROUP BY chain ORDER BY tokens DESC""", (exposure_floor, cutoff))
    snapshots = q(con, """
      SELECT substr(token_id,1,instr(token_id,':')-1) chain,
             COUNT(DISTINCT token_id) tokens, COUNT(*) rows,
             SUM(liquidity_usd>=1000) depth_rows
      FROM token_snapshots WHERE id>? AND julianday(observed_at)>=julianday('now',?)
      GROUP BY 1 ORDER BY tokens DESC""", (snap_floor, cutoff))
    evaluations = q(con, """
      SELECT substr(token_id,1,instr(token_id,':')-1) chain, status, reason,
             COUNT(*) rows, COUNT(DISTINCT token_id) tokens
      FROM chain_meme_trader_v6_entry_evaluations
      WHERE id>? AND definition_version=? AND julianday(evaluated_at)>=julianday('now',?)
      GROUP BY 1,status,reason ORDER BY rows DESC LIMIT 80""", (eval_floor, version, cutoff))
    decisions = q(con, """
      SELECT substr(token_id,1,instr(token_id,':')-1) chain, status,
             COUNT(*) rows, COUNT(DISTINCT token_id) tokens, COUNT(DISTINCT arm_id) arms
      FROM chain_meme_trader_entry_decisions
      WHERE definition_version=? AND julianday(decided_at)>=julianday('now',?)
      GROUP BY 1,status ORDER BY rows DESC""", (version, cutoff))

    # Queue is indexed by due state.  Report only nonterminal work and terminal errors separately.
    hydration = q(con, """
      SELECT chain,status,COUNT(*) rows,MAX(attempts) max_attempts,
       ROUND(MAX(0,(julianday('now')-julianday(enqueued_at))*86400),1) oldest_age_seconds,
       MIN(next_attempt_at) oldest_next_attempt_at
      FROM token_detail_hydration WHERE status IN ('pending','error')
      GROUP BY chain,status ORDER BY rows DESC""")
    failures = q(con, """
      SELECT chain, status, COALESCE(NULLIF(last_error,''),'(none)') error,
             COUNT(*) rows, MAX(attempts) max_attempts
      FROM token_detail_hydration WHERE status IN ('error','no_pair')
      GROUP BY chain,status,error ORDER BY rows DESC LIMIT 40""")

    # First recent arrival -> first recent snapshot/evaluation latency, only when both events exist.
    timing = q(con, """
      WITH d AS (
       SELECT token_id, MIN(COALESCE(recorded_at,observed_at)) t
       FROM token_discovery_exposures WHERE id>? AND first_local_discovery=1
        AND julianday(COALESCE(recorded_at,observed_at))>=julianday('now',?) GROUP BY token_id),
      s AS (SELECT token_id,MIN(observed_at) t FROM token_snapshots WHERE id>? GROUP BY token_id),
      e AS (SELECT token_id,MIN(evaluated_at) t FROM chain_meme_trader_v6_entry_evaluations
            WHERE id>? AND definition_version=? GROUP BY token_id)
      SELECT substr(d.token_id,1,instr(d.token_id,':')-1) chain,
       COUNT(*) discovered, SUM(s.t IS NOT NULL) with_snapshot, SUM(e.t IS NOT NULL) with_evaluation,
       ROUND(AVG(CASE WHEN s.t IS NOT NULL THEN (julianday(s.t)-julianday(d.t))*86400 END),2) avg_discovery_to_snapshot_s,
       ROUND(AVG(CASE WHEN e.t IS NOT NULL THEN (julianday(e.t)-julianday(d.t))*86400 END),2) avg_discovery_to_evaluation_s,
       ROUND(MAX(CASE WHEN e.t IS NOT NULL THEN (julianday(e.t)-julianday(d.t))*86400 END),2) max_discovery_to_evaluation_s
      FROM d LEFT JOIN s USING(token_id) LEFT JOIN e USING(token_id)
      GROUP BY 1 ORDER BY discovered DESC""", (exposure_floor, cutoff, snap_floor, eval_floor, version))

    errors = q(con, """
      SELECT component,error_type,occurrence_count,last_seen_at
      FROM system_error_cases WHERE julianday(last_seen_at)>=julianday('now',?)
      ORDER BY occurrence_count DESC LIMIT 20""", (cutoff,))
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "window_hours": args.hours,
              "definition_version": version, "frontiers": {"exposure": exposure_floor, "snapshot": snap_floor, "evaluation": eval_floor},
              "discovered_by_chain": discovered, "snapshots_by_chain": snapshots,
              "evaluation_reason_by_chain": evaluations, "decisions_by_chain": decisions,
              "pending_or_error_hydration": hydration, "hydration_failure_distribution": failures,
              "recent_arrival_timing_by_chain": timing, "recent_error_cases": errors,
              "method_note": "All event stages are newest-ID-frontier bounded. Timing joins a token's first event in each retained frontier; it is not a full-history lifecycle reconstruction."}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
