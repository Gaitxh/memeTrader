"""Deterministic supervision snapshot for the ChainMemeTrader Paper runtime.

This is the measurement half of the supervise -> review -> optimise loop. It is
read-only, bounded and has no trading authority: it prints the per-step funnel
(discovery -> collection -> evaluation -> risk/size -> position), the latency of
each step, the rejection-reason histogram, exit-family economics, capacity, and
stability counters, then turns them into explicit REVIEW TRIGGERS so a human (or
the next agent round) can decide a threshold change from evidence instead of
intuition. Nothing here edits a strategy, a threshold or the database.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\supervise_metrics.py
    .\\.venv\\Scripts\\python.exe scripts\\supervise_metrics.py --minutes 180
    .\\.venv\\Scripts\\python.exe scripts\\supervise_metrics.py --json-only

Every query is bounded by a time window or an id frontier: the database is ~39 GB.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_ID_WINDOW = 300_000
MARKETS = ("solana", "bsc", "robinhood")


def quantile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def connect():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert not (config.get("live") or {}).get("enabled"), "live must stay locked"
    database = Path(config["database"])
    database = database if database.is_absolute() else ROOT / database
    con = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=180)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=1")
    return con


def active_version(con):
    return con.execute(
        "SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
    ).fetchone()[0]


def funnel(con, version, minutes):
    window = f"-{int(minutes)} minute"
    out = {"window_minutes": int(minutes)}
    out["discovered"] = [
        dict(row) for row in con.execute(
            "SELECT chain, COUNT(DISTINCT token_id) n FROM token_discovery_exposures "
            "WHERE COALESCE(recorded_at,observed_at)>=datetime('now',?) AND first_local_discovery=1 "
            "GROUP BY chain ORDER BY n DESC", (window,))]
    out["discovered_total"] = sum(row["n"] for row in out["discovered"])
    row = con.execute(
        "WITH d AS (SELECT DISTINCT token_id, MIN(COALESCE(recorded_at,observed_at)) f0 "
        "           FROM token_discovery_exposures WHERE COALESCE(recorded_at,observed_at)>=datetime('now',?) "
        "           AND first_local_discovery=1 GROUP BY token_id) "
        "SELECT COUNT(*) n, "
        "SUM(EXISTS(SELECT 1 FROM token_snapshots s WHERE s.token_id=d.token_id AND s.observed_at>=d.f0)) got_snap, "
        "SUM(EXISTS(SELECT 1 FROM token_snapshots s WHERE s.token_id=d.token_id AND s.observed_at>=d.f0 "
        "           AND s.liquidity_usd>=1000)) got_tradable, "
        "SUM(EXISTS(SELECT 1 FROM token_snapshots s WHERE s.token_id=d.token_id AND s.observed_at>=d.f0 "
        "           AND s.liquidity_usd IS NULL)) liquidity_unknown "
        "FROM d", (window,)).fetchone()
    out["collection"] = dict(row)
    latency = [row["dt"] for row in con.execute(
        "WITH d AS (SELECT token_id, MIN(COALESCE(recorded_at,observed_at)) f0 "
        "           FROM token_discovery_exposures WHERE COALESCE(recorded_at,observed_at)>=datetime('now',?) "
        "           AND first_local_discovery=1 GROUP BY token_id), "
        "     s AS (SELECT token_id, MIN(observed_at) f1 FROM token_snapshots "
        "           WHERE observed_at>=datetime('now','-6 hour') GROUP BY token_id) "
        "SELECT (julianday(s.f1)-julianday(d.f0))*86400 dt FROM d JOIN s USING(token_id) "
        "WHERE dt IS NOT NULL AND dt>=0 AND dt<=7200", (f"-{max(int(minutes), 180)} minute",))]
    out["discovery_to_first_snapshot_seconds"] = {
        key: (round(quantile(latency, frac), 1) if latency else None)
        for key, frac in (("n", .5), ("p25", .25), ("p50", .5), ("p75", .75), ("p90", .9))}
    out["discovery_to_first_snapshot_seconds"]["n"] = len(latency)
    top = con.execute("SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_v6_entry_evaluations").fetchone()[0]
    floor = top - EVAL_ID_WINDOW
    sample = con.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_v6_entry_evaluations WHERE id>?", (floor,)).fetchone()[0]
    out["evaluation"] = {"sampled_rows": sample, "id_floor": floor, "reasons": [
        dict(row) for row in con.execute(
            "SELECT reason, status, COUNT(*) n FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? AND id>? GROUP BY reason, status ORDER BY n DESC LIMIT 20",
            (version, floor))]}
    out["decisions"] = [
        dict(row) for row in con.execute(
            "SELECT status, COUNT(*) n, COUNT(DISTINCT arm_id) arms FROM chain_meme_trader_entry_decisions "
            "WHERE definition_version=? AND decided_at>=datetime('now',?) GROUP BY status ORDER BY n DESC",
            (version, window))]
    out["positions_opened"] = dict(con.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT arm_id) arms, COUNT(DISTINCT token_id) tokens "
        "FROM chain_meme_trader_positions WHERE definition_version=? AND opened_at>=datetime('now',?)",
        (version, window)).fetchone())
    return out


def economics(con, version, hours):
    window = f"-{int(hours)} hour"
    closed = [dict(row) for row in con.execute(
        "SELECT close_reason, COUNT(*) n, ROUND(SUM(realized_pnl_usd),2) pnl, "
        "ROUND(AVG(realized_pnl_usd),3) mean_pnl FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND closed_at>=datetime('now',?) AND status='closed' "
        "GROUP BY close_reason ORDER BY pnl ASC LIMIT 25", (version, window))]
    writeoffs = dict(con.execute(
        "SELECT COUNT(*) n, ROUND(SUM(realized_pnl_usd),2) pnl FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND status='written_off' AND COALESCE(closed_at,opened_at)>=datetime('now',?)",
        (version, window)).fetchone())
    open_rows = dict(con.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT arm_id) arms, COUNT(DISTINCT token_id) tokens, "
        "ROUND(SUM(stake_usd),2) stake FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND status='open'", (version,)).fetchone())
    return {"closed_by_reason": closed, "write_offs": writeoffs, "open": open_rows,
            "hours": int(hours)}


def capacity(con, version):
    rows = [dict(row) for row in con.execute(
        "SELECT s.arm_id, s.cash_usd, s.open_position_count, s.recorded_at "
        "FROM chain_meme_trader_account_snapshots s JOIN ("
        "  SELECT arm_id, MAX(id) mid FROM chain_meme_trader_account_snapshots "
        "  WHERE definition_version=? GROUP BY arm_id) m ON m.mid=s.id", (version,))]
    cash = [row["cash_usd"] for row in rows if row["cash_usd"] is not None]
    return {"arms_with_snapshot": len(rows),
            "cash_p10": round(quantile(cash, .10), 2) if cash else None,
            "cash_p50": round(quantile(cash, .50), 2) if cash else None,
            "arms_below_2usd": sum(1 for value in cash if value < 2.0),
            "arms_below_20usd": sum(1 for value in cash if value < 20.0),
            "open_positions": sum(int(row["open_position_count"] or 0) for row in rows)}


def stability(con, hours):
    unresolved = [dict(row) for row in con.execute(
        "SELECT area, component, error_type, message_safe, occurrence_count, first_seen_at, last_seen_at "
        "FROM system_error_cases WHERE status!='resolved' ORDER BY last_seen_at DESC LIMIT 15")]
    fresh = [dict(row) for row in con.execute(
        "SELECT component, error_type, occurrence_count, first_seen_at, last_seen_at "
        "FROM system_error_cases WHERE last_seen_at>=datetime('now',?) ORDER BY last_seen_at DESC LIMIT 10",
        (f"-{int(hours)} hour",))]
    active = [dict(row) for row in con.execute(
        "SELECT component, error_type, occurrence_count, first_seen_at, last_seen_at "
        "FROM system_error_cases WHERE last_seen_at>=datetime('now','-15 minute') "
        "ORDER BY last_seen_at DESC LIMIT 10")]
    sources = [dict(row) for row in con.execute(
        "SELECT source, last_ok_at, last_error_at, last_error FROM source_health "
        "ORDER BY COALESCE(last_ok_at,'') DESC LIMIT 12")]
    hydration = [dict(row) for row in con.execute(
        "SELECT status, COUNT(*) n, MIN(next_attempt_at) oldest_due, MAX(attempts) max_attempts "
        "FROM token_detail_hydration GROUP BY status ORDER BY n DESC")]
    return {"unresolved_errors": unresolved, "new_error_cases": fresh,
            "active_error_cases": active,
            "sources": sources, "hydration_queue": hydration}


def reviews(metrics):
    """Deterministic review triggers; each one names the measurement behind it."""
    flags = []
    collection = metrics["funnel"]["collection"]
    discovered = max(1, collection["n"] or 0)
    tradable = collection["got_tradable"] or 0
    if tradable / discovered < 0.20:
        flags.append(dict(level="warn", code="collection_coverage_low",
                          detail=f"only {100.0*tradable/discovered:.1f}% of discovered tokens reached a "
                                 f"tradable snapshot in the window"))
    unknown = collection["liquidity_unknown"] or 0
    if unknown / discovered > 0.30:
        flags.append(dict(level="warn", code="liquidity_unknown_high",
                          detail=f"{100.0*unknown/discovered:.1f}% of discovered tokens still have no "
                                 f"liquidity reading"))
    latency = metrics["funnel"]["discovery_to_first_snapshot_seconds"].get("p50")
    if latency is not None and latency > 300:
        flags.append(dict(level="warn", code="discovery_to_snapshot_slow",
                          detail=f"median discovery -> first snapshot {latency:.0f}s"))
    for row in metrics["funnel"]["evaluation"]["reasons"]:
        share = row["n"] / max(1, metrics["funnel"]["evaluation"]["sampled_rows"])
        if share > 0.20:
            flags.append(dict(level="info", code="dominant_rejection_reason",
                              detail=f"{row['reason']} = {100.0*share:.1f}% of sampled evaluations"))
    for row in metrics["economics"]["closed_by_reason"]:
        if row["n"] >= 20 and (row["pnl"] or 0) < 0 and "hard_stop" in str(row["close_reason"]):
            flags.append(dict(level="warn", code="stop_family_loss_dominant",
                              detail=f"{row['close_reason']}: n={row['n']} pnl={row['pnl']}U "
                                     f"mean={row['mean_pnl']}U"))
    writeoffs = metrics["economics"]["write_offs"]["n"] or 0
    if writeoffs >= 5:
        flags.append(dict(level="warn", code="write_offs_present",
                          detail=f"{writeoffs} write-offs for {metrics['economics']['write_offs']['pnl']}U "
                                 f"in {metrics['economics']['hours']}h"))
    if metrics["economics"]["open"]["n"] and not metrics["economics"]["closed_by_reason"]:
        flags.append(dict(level="warn", code="no_exits_in_window",
                          detail="positions are open but nothing closed inside the window"))
    if (metrics["capacity"]["cash_p10"] or 0) < 5.0:
        flags.append(dict(level="warn", code="capacity_floor",
                          detail=f"p10 arm cash {metrics['capacity']['cash_p10']}U"))
    for row in metrics["stability"]["active_error_cases"]:
        flags.append(dict(level="error", code="error_case_active_in_last_15_min",
                          detail=f"{row.get('component')} {row.get('error_type')} "
                                 f"x{row.get('occurrence_count')} last seen {row.get('last_seen_at')}"))
    for row in metrics["stability"]["new_error_cases"]:
        if row in metrics["stability"]["active_error_cases"]:
            continue
        flags.append(dict(level="info", code="error_case_seen_in_window_but_quiet",
                          detail=f"{row.get('component')} {row.get('error_type')} "
                                 f"x{row.get('occurrence_count')} last seen {row.get('last_seen_at')}"))
    return flags


def markdown(metrics):
    funnel = metrics["funnel"]
    latency = funnel["discovery_to_first_snapshot_seconds"]
    lines = [
        f"## Supervision snapshot {metrics['generated_at']} "
        f"({funnel['window_minutes']} min window, epoch `{metrics['definition_version']}`)",
        "",
        f"- discovered (first local): **{funnel['discovered_total']}** "
        + " ".join(f"{row['chain']}={row['n']}" for row in funnel["discovered"]),
        f"- reached a snapshot: {funnel['collection']['got_snap']} "
        f"({100.0*(funnel['collection']['got_snap'] or 0)/max(1,funnel['collection']['n']):.1f}%) · "
        f"tradable (liq>=1000U): {funnel['collection']['got_tradable']} · "
        f"liquidity unknown: {funnel['collection']['liquidity_unknown']}",
        f"- discovery -> first snapshot: p50 {latency.get('p50')}s "
        f"p90 {latency.get('p90')}s (n={latency.get('n')})",
        f"- evaluations sampled: {funnel['evaluation']['sampled_rows']} · "
        + " ".join(f"{row['status']}={row['n']}" for row in funnel["decisions"]),
        f"- positions opened: {funnel['positions_opened']['n']} over "
        f"{funnel['positions_opened']['arms']} arms / {funnel['positions_opened']['tokens']} tokens",
        "",
        "| exit reason (24h) | n | PnL U | mean U |",
        "|---|---|---|---|",
    ]
    for row in metrics["economics"]["closed_by_reason"][:12]:
        lines.append(f"| {str(row['close_reason'])[:48]} | {row['n']} | {row['pnl']} | {row['mean_pnl']} |")
    lines += [
        "",
        f"- write-offs: {metrics['economics']['write_offs']['n']} "
        f"({metrics['economics']['write_offs']['pnl']}U) · "
        f"open: {metrics['economics']['open']['n']} positions / "
        f"{metrics['economics']['open']['tokens']} tokens / {metrics['economics']['open']['stake']}U",
        f"- arm cash p10 {metrics['capacity']['cash_p10']}U p50 {metrics['capacity']['cash_p50']}U · "
        f"below 2U: {metrics['capacity']['arms_below_2usd']} · "
        f"below 20U: {metrics['capacity']['arms_below_20usd']}",
        f"- unresolved error cases: {len(metrics['stability']['unresolved_errors'])} · "
        f"new in window: {len(metrics['stability']['new_error_cases'])}",
        "",
        "**Review triggers**",
    ]
    if metrics["review"]:
        lines += [f"- `{flag['level']}` **{flag['code']}** — {flag['detail']}" for flag in metrics["review"]]
    else:
        lines.append("- none: every measured step is inside its expected band")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "reports" / "supervise"))
    args = parser.parse_args()

    con = connect()
    try:
        version = active_version(con)
        metrics = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "definition_version": version,
            "funnel": funnel(con, version, args.minutes),
            "economics": economics(con, version, args.hours),
            "capacity": capacity(con, version),
            "stability": stability(con, args.hours),
        }
    finally:
        con.close()
    metrics["review"] = reviews(metrics)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = metrics["generated_at"].replace(":", "").replace("-", "")[:15]
    (out_dir / f"supervise_{stamp}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": metrics["generated_at"], "minutes": args.minutes,
            "discovered": metrics["funnel"]["discovered_total"],
            "tradable": metrics["funnel"]["collection"]["got_tradable"],
            "opened": metrics["funnel"]["positions_opened"]["n"],
            "open_now": metrics["economics"]["open"]["n"],
            "write_offs": metrics["economics"]["write_offs"]["n"],
            "cash_p10": metrics["capacity"]["cash_p10"],
            "flags": [flag["code"] for flag in metrics["review"]],
        }, ensure_ascii=False) + "\n")
    if args.json_only:
        print(json.dumps(metrics, ensure_ascii=False))
        return
    print(markdown(metrics))


if __name__ == "__main__":
    main()
