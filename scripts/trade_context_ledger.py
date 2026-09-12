"""Per-trade context ledger + periodic arm review (read-only, deterministic).

Answers the user requirement "every trade records its full context (why it was
discovered, which filters it passed, signal strength, final result, why it was
washed out)" and the periodic-review requirement (win rate, profit factor, drawdown,
washout frequency, exit mix) without writing to the runtime database.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\trade_context_ledger.py --minutes 360
    .\\.venv\\Scripts\\python.exe scripts\\trade_context_ledger.py --minutes 60 --quiet

Outputs:
    data/reports/trade_context/trades_<stamp>.jsonl   one record per position
    data/reports/trade_context/review_<stamp>.json    aggregated review
    stdout: the review as Markdown

Time windows use julianday(): stored timestamps are 'T'-separated while SQLite's
datetime() is space-separated, and a text comparison would silently widen the window
to a whole calendar day (measured 2.1x-5.5x inflation on 4-hour windows).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRICTION = 1.04 / 0.96 - 1.0
WASHOUT_MFE = 0.50          # ran at least +50% at some point
WASHOUT_FLOOR = -0.05       # and still closed at a loss


def connect():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    assert not (config.get("live") or {}).get("enabled"), "live must stay locked"
    database = Path(config["database"])
    database = database if database.is_absolute() else ROOT / database
    con = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=180)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=1")
    return con


def arm_mechanisms(con, version):
    """arm_id -> the entry mechanism it declares (from the append-only registry)."""
    result = {}
    for row in con.execute(
            "SELECT arm_id, policy_json FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=?", (version,)):
        try:
            policy = json.loads(row["policy_json"])
        except (TypeError, ValueError):
            continue
        result[str(row["arm_id"])] = {
            "mechanism": policy.get("feature_hypothesis"),
            "notional_usd": policy.get("notional_usd"),
            "max_hold_minutes": policy.get("max_hold_minutes"),
            "hard_stop_return": policy.get("hard_stop_return"),
            "trailing": [policy.get("trailing_activate_return"), policy.get("trailing_drawdown")],
            "take_profit": policy.get("take_profit") or [],
            "excess_return_vs_arm": policy.get("excess_return_vs_arm"),
        }
    return result


def discovery_context(con, token_id):
    row = con.execute(
        "SELECT role, chain, first_local_discovery, MIN(COALESCE(recorded_at,observed_at)) first_at "
        "FROM token_discovery_exposures WHERE token_id=? LIMIT 1", (token_id,)).fetchone()
    return dict(row) if row else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=360)
    parser.add_argument("--limit", type=int, default=4000)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    window = f"-{args.minutes} minute"

    con = connect()
    try:
        version = con.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1").fetchone()[0]
        mechanisms = arm_mechanisms(con, version)
        positions = [dict(row) for row in con.execute(
            "SELECT arm_id, token_id, status, opened_at, closed_at, close_reason, stake_usd, "
            "realized_pnl_usd, realized_proceeds_usd, entry_execution_price_usd, "
            "highest_signal_price_usd, entry_snapshot_id, entry_reason, next_tp_index, "
            "principal_recovered, initial_amount_raw, amount_raw "
            "FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND julianday(opened_at)>=julianday('now',?) ORDER BY opened_at DESC LIMIT ?",
            (version, window, args.limit))]
        # Decisions in the same window: small table, used to name the entry reason and
        # the filter outcome that admitted the position.
        decisions = defaultdict(list)
        for row in con.execute(
                "SELECT arm_id, token_id, decided_at, status, reason "
                "FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
                "AND julianday(decided_at)>=julianday('now',?) LIMIT ?",
                (version, window, args.limit)):
            decisions[(row["arm_id"], row["token_id"])].append(dict(row))
        for items in decisions.values():
            items.sort(key=lambda item: item["decided_at"])
    finally:
        con.close()

    con = connect()
    records = []
    try:
        for position in positions:
            entry_price = position["entry_execution_price_usd"] or 0.0
            high = position["highest_signal_price_usd"] or 0.0
            mfe = (high / entry_price - 1.0) if entry_price > 0 and high > 0 else None
            hold_minutes = None
            if position["closed_at"] and position["opened_at"]:
                hold_minutes = round((
                    datetime.fromisoformat(position["closed_at"].replace("Z", "+00:00"))
                    - datetime.fromisoformat(position["opened_at"].replace("Z", "+00:00"))
                ).total_seconds() / 60.0, 2)
            candidates = [item for item in decisions.get(
                (position["arm_id"], position["token_id"]), [])
                if item["decided_at"] <= position["opened_at"]]
            decision = candidates[-1] if candidates else {}
            record = {
                "arm_id": position["arm_id"],
                "token_id": position["token_id"],
                "chain": str(position["token_id"]).split(":", 1)[0],
                "mechanism": (mechanisms.get(position["arm_id"]) or {}).get("mechanism"),
                "status": position["status"],
                "opened_at": position["opened_at"],
                "closed_at": position["closed_at"],
                "hold_minutes": hold_minutes,
                "stake_usd": position["stake_usd"],
                "entry_execution_price_usd": entry_price,
                "highest_signal_price_usd": high,
                "max_favourable_excursion": None if mfe is None else round(mfe, 4),
                "realized_pnl_usd": position["realized_pnl_usd"],
                "realized_proceeds_usd": position["realized_proceeds_usd"],
                "close_reason": position["close_reason"],
                "entry_reason": position["entry_reason"] or decision.get("reason"),
                "decision_status": decision.get("status"),
                "decision_reason": decision.get("reason"),
                "next_tp_index": position["next_tp_index"],
                "principal_recovered": position["principal_recovered"],
                "partial_filled": bool(
                    position["initial_amount_raw"] and position["amount_raw"] is not None
                    and int(position["amount_raw"]) < int(position["initial_amount_raw"])),
                "discovery": discovery_context(con, position["token_id"]),
            }
            # "Washed out": it ran hard, then closed at a loss anyway.
            pnl = position["realized_pnl_usd"] or 0.0
            stake = position["stake_usd"] or 0.0
            record["washed_out"] = bool(
                mfe is not None and mfe >= WASHOUT_MFE and stake > 0
                and pnl / stake <= WASHOUT_FLOOR)
            records.append(record)
    finally:
        con.close()

    out_dir = ROOT / "data" / "reports" / "trade_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    ledger = out_dir / f"trades_{stamp}.jsonl"
    with ledger.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    closed = [r for r in records if r["status"] == "closed"]
    written = [r for r in records if r["status"] == "written_off"]
    groups = defaultdict(list)
    for record in records:
        family = ("alpha149" if record["arm_id"].startswith("alpha149")
                  else "trajectory144" if record["arm_id"].startswith("trajectory144")
                  else "trajectory145/146" if record["arm_id"].startswith(("trajectory145", "trajectory146"))
                  else "dex_" if record["arm_id"].startswith("dex_")
                  else "pump_" if record["arm_id"].startswith("pump_")
                  else "other")
        groups[family].append(record)

    def stats(items):
        settled = [r for r in items if r["status"] in ("closed", "written_off")]
        pnls = [float(r["realized_pnl_usd"] or 0.0) for r in settled]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        curve, running, drawdown = 0.0, 0.0, 0.0
        for value in sorted(pnls):
            running += value
            curve = min(curve, running)
            drawdown = min(drawdown, running - (running - curve))
        return {
            "positions": len(items), "settled": len(settled),
            "write_offs": sum(1 for r in items if r["status"] == "written_off"),
            "win_rate": round(100.0 * len(wins) / max(1, len(settled)), 1),
            "mean_pnl": round(sum(pnls) / max(1, len(pnls)), 3),
            "total_pnl": round(sum(pnls), 2),
            "profit_factor": (round(sum(wins) / abs(sum(losses)), 2) if losses else None),
            "washed_out": sum(1 for r in items if r["washed_out"]),
            "washout_rate": round(100.0 * sum(1 for r in items if r["washed_out"]) / max(1, len(items)), 1),
            "mean_hold_minutes": round(sum(r["hold_minutes"] or 0 for r in settled) / max(1, len(settled)), 1),
        }

    review = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "definition_version": version, "window_minutes": args.minutes,
        "positions": len(records), "ledger": str(ledger),
        "overall": stats(records),
        "by_family": {name: stats(items) for name, items in sorted(groups.items())},
        "exit_reasons": [
            {"reason": reason, "n": len(items),
             "pnl": round(sum(float(r["realized_pnl_usd"] or 0.0) for r in items), 2)}
            for reason, items in sorted(
                ((reason, [r for r in records if (r["close_reason"] or "") == reason])
                 for reason in {(r["close_reason"] or "") for r in records}),
                key=lambda kv: -len(kv[1]))[:12]],
        "by_hold_bucket": {},
        "by_chain": {},
        "washed_out_examples": [
            {"arm_id": r["arm_id"], "token_id": r["token_id"], "mfe": r["max_favourable_excursion"],
             "pnl": r["realized_pnl_usd"], "close_reason": r["close_reason"]}
            for r in sorted((r for r in records if r["washed_out"]),
                            key=lambda r: -(r["max_favourable_excursion"] or 0))[:10]],
    }
    buckets = ((0, 1), (1, 5), (5, 15), (15, 30), (30, 60), (60, 10 ** 6))
    for low, high in buckets:
        items = [r for r in records if r["hold_minutes"] is not None and low <= r["hold_minutes"] < high]
        if items:
            review["by_hold_bucket"][f"{low}-{high if high < 10**6 else '+'}m"] = stats(items)
    for chain in {r["chain"] for r in records}:
        review["by_chain"][chain] = stats([r for r in records if r["chain"] == chain])
    (out_dir / f"review_{stamp}.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.quiet:
        print(f"## Trade-context review {review['generated_at']} "
              f"({args.minutes} min window, epoch `{version}`)")
        print(f"\n- positions {review['positions']} · settled {review['overall']['settled']} · "
              f"write-offs {review['overall']['write_offs']} · win rate {review['overall']['win_rate']}% · "
              f"total {review['overall']['total_pnl']}U · PF {review['overall']['profit_factor']}")
        print(f"- washed out (ran >= +50% then closed at a loss): "
              f"**{review['overall']['washed_out']}** ({review['overall']['washout_rate']}%)")
        print(f"- ledger: `{ledger.relative_to(ROOT)}`")
        print("\n| family | positions | settled | win % | total U | PF | washout % | mean hold m |")
        print("|---|---|---|---|---|---|---|---|")
        for name, data in review["by_family"].items():
            print(f"| {name} | {data['positions']} | {data['settled']} | {data['win_rate']} | "
                  f"{data['total_pnl']} | {data['profit_factor']} | {data['washout_rate']} | "
                  f"{data['mean_hold_minutes']} |")
        print("\n| hold bucket | settled | win % | total U | washout % |")
        print("|---|---|---|---|---|")
        for name, data in review["by_hold_bucket"].items():
            print(f"| {name} | {data['settled']} | {data['win_rate']} | {data['total_pnl']} | "
                  f"{data['washout_rate']} |")
        print("\n| exit reason | n | PnL U |")
        print("|---|---|---|")
        for row in review["exit_reasons"][:8]:
            print(f"| {str(row['reason'])[:52]} | {row['n']} | {row['pnl']} |")
        if review["washed_out_examples"]:
            print("\n**Worst washouts (highest excursion that still closed red)**")
            for row in review["washed_out_examples"][:5]:
                print(f"- {row['arm_id']} {str(row['token_id'])[:38]} peak "
                      f"{100.0*(row['mfe'] or 0):.0f}% → {row['pnl']}U ({row['close_reason']})")


if __name__ == "__main__":
    main()
