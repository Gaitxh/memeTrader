"""Consolidated readout for the additive strategy experiments.

Why this exists
---------------
`paired_arm_ab.py` answers one question well: two EXIT carriers share a cohort, so their
within-cohort difference is a clean paired comparison. But it is the wrong instrument for the
ENTRY floors added in rounds 120-19/120-20. A floor arm enters a SUBSET of the control's
cohorts, so within-cohort pairing silently drops exactly the cohorts the floor rejected - which
are the ones the hypothesis is about. Pairing would hide the effect it is meant to measure.

This script therefore applies a DIFFERENT design per experiment kind:

  exit  - paired within-cohort differences against the control (same opportunity, different
          exit contract), identical to paired_arm_ab.
  floor - set-difference design. The floor's value is what it AVOIDS, so it reports the
          control's own settled positions on the cohorts the floor arm rejected with a
          recorded floor reason, versus the floor arm's own book.

Both kinds use a TOKEN-CLUSTERED bootstrap, because positions cluster inside a token and that
has repeatedly destroyed apparent effects in this project.

It REFUSES to render a verdict below the settled threshold rather than printing a spurious one.

Usage:  python scripts/experiment_readout.py [--hours N] [--min-settled N]
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR_REASONS = {
    "activity_floor_trades_not_met",
    "activity_floor_volume_not_met",
    "runup_floor_exceeded",
    "runup_floor_window_unknown",
}

# label, arm, control, kind, the hypothesis being tested
EXPERIMENTS = (
    ("EXIT150  +15%: full capture vs 50% partial", "exit150_full15_v1", "exit150_bank15_v1",
     "exit", "banking the whole position at +15% beats leaving 50% riding"),
    ("EXIT150  +25%: full capture vs 50% partial", "exit150_full25_v1", "exit150_bank25_v1",
     "exit", "the capture fraction also dominates at a +25% level"),
    ("EXIT150  stop width: wide vs bank15", "exit150_widestop_v1", "exit150_bank15_v1",
     "exit", "a wider stop survives noise better"),
    ("ACTIVITY-FLOOR  trades>=30", "activity_floor150_t30_v1",
     "alpha149_merged_multi_setup_fast_v1", "floor",
     "the skip-rate/quiet pools it rejects carry a much higher write-off rate"),
    ("ACTIVITY-FLOOR  volume>=5000", "activity_floor150_v5k_v1",
     "alpha149_merged_multi_setup_fast_v1", "floor",
     "volume is the better activity measure than trade count"),
    ("RUNUP-FLOOR  run-up<=15%", "runup_floor150_r15_v1",
     "alpha149_merged_multi_setup_fast_v1", "floor",
     "pools already run up 15% in 20 minutes are the ones that die"),
    ("RUNUP-FLOOR  run-up<=15% and trades>=30", "runup_floor150_r15a30_v1",
     "alpha149_merged_multi_setup_fast_v1", "floor",
     "the conjunction of both floors is the best configuration"),
)


def resolve_db() -> Path:
    cfg = ROOT / "config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            db = data.get("database")
            if db:
                p = Path(db)
                return p if p.is_absolute() else ROOT / p
        except (ValueError, OSError):
            pass
    return ROOT / "data" / "memetrader_forward.sqlite3"


def active_version(cur) -> str:
    """The epoch the live positions actually belong to (not merely the newest registration)."""
    row = cur.execute(
        "SELECT definition_version, count(*) n FROM chain_meme_trader_positions "
        "GROUP BY definition_version ORDER BY n DESC LIMIT 1").fetchone()
    return row[0] if row else ""


def clustered_interval(diffs, iterations=4000, seed=20260913, lo_pct=0.05, hi_pct=0.95):
    """Bootstrap over TOKENS: positions cluster inside a token."""
    by_token = defaultdict(list)
    for d in diffs:
        by_token[d["token_id"]].append(d["value"])
    tokens = list(by_token)
    if len(tokens) < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        picked = [tokens[rng.randrange(len(tokens))] for _ in tokens]
        vals = [v for t in picked for v in by_token[t]]
        if vals:
            means.append(sum(vals) / len(vals))
    means.sort()
    n = len(means)
    return (round(means[int(lo_pct * n)], 3), round(means[int(hi_pct * n)], 3))


def book_stats(rows):
    settled = [r for r in rows if r["status"] != "open"]
    if not settled:
        return None
    pnl = sum(float(r["realized_pnl_usd"] or 0) for r in settled)
    wo = sum(1 for r in settled if r["status"] == "written_off")
    wins = sum(1 for r in settled if float(r["realized_pnl_usd"] or 0) > 0)
    return {
        "settled": len(settled),
        "tokens": len({r["token_id"] for r in settled}),
        "pnl": pnl,
        "pnl_per_pos": pnl / len(settled),
        "win_rate": 100.0 * wins / len(settled),
        "writeoff_rate": 100.0 * wo / len(settled),
    }


def load_rows(cur, version, arm, hours):
    return cur.execute(
        """SELECT arm_id, shadow_cohort_id, token_id, status, realized_pnl_usd, opened_at
           FROM chain_meme_trader_positions
           WHERE definition_version=? AND arm_id=? AND julianday(opened_at)>=julianday('now',?)""",
        (version, arm, "-%d hour" % hours)).fetchall()


def floor_rejected_cohort_ids(cur, version, arm):
    """Cohort ids where this arm was refused BY ITS OWN FLOOR, from the recorded outcomes.

    This is what makes the floor testable. Inferring "rejected" from a missing position would
    be wrong - a missing position can also come from concurrency limits or a consumed
    single-token lifetime entry. Reading the recorded outcome attributes it precisely, so the
    control's positions on these cohorts are exactly what the hypothesis claims the floor
    avoided.
    """
    out = set()
    for row in cur.execute(
        "SELECT id, feature_json FROM chain_meme_trader_v6_cohorts WHERE definition_version=?",
        (version,),
    ):
        try:
            data = json.loads(row["feature_json"] or "{}")
        except (ValueError, TypeError):
            continue
        if (data.get("outcomes") or {}).get(arm) in FLOOR_REASONS:
            out.add(row["id"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--min-settled", type=int, default=20)
    args = ap.parse_args(argv)

    db = resolve_db()
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    version = active_version(cur)
    print(f"db       : {db}")
    print(f"epoch    : {version}")
    print(f"window   : last {args.hours}h    settled threshold: {args.min_settled} per side")
    print()

    for label, arm, control, kind, hypothesis in EXPERIMENTS:
        rows_a = load_rows(cur, version, arm, args.hours)
        rows_c = load_rows(cur, version, control, args.hours)
        sa, sc = book_stats(rows_a), book_stats(rows_c)
        print(f"=== {label}")
        print(f"    hypothesis: {hypothesis}")
        if sa is None or sc is None:
            print(f"    NOT READY - no settled positions yet "
                  f"(arm {0 if sa is None else sa['settled']}, "
                  f"control {0 if sc is None else sc['settled']})")
            print()
            continue
        print(f"    arm     {arm:<38} settled={sa['settled']:<4} "
              f"{sa['pnl_per_pos']:>7.2f}U/pos  win {sa['win_rate']:>5.1f}%  "
              f"write-off {sa['writeoff_rate']:>5.1f}%  ({sa['tokens']} tokens)")
        print(f"    control {control:<38} settled={sc['settled']:<4} "
              f"{sc['pnl_per_pos']:>7.2f}U/pos  win {sc['win_rate']:>5.1f}%  "
              f"write-off {sc['writeoff_rate']:>5.1f}%  ({sc['tokens']} tokens)")

        ready = sa["settled"] >= args.min_settled and sc["settled"] >= args.min_settled

        if kind == "floor":
            rejected = floor_rejected_cohort_ids(cur, version, arm)
            avoided = [r for r in rows_c if r["shadow_cohort_id"] in rejected]
            sb = book_stats(avoided)
            print(f"    floor rejected {len(rejected)} cohort(s) of this arm; the control itself "
                  f"traded {0 if sb is None else sb['settled']} of them")
            if sb:
                print(f"    => what the floor AVOIDED (control on rejected cohorts): "
                      f"settled={sb['settled']:<4} {sb['pnl_per_pos']:>7.2f}U/pos  "
                      f"win {sb['win_rate']:>5.1f}%  write-off {sb['writeoff_rate']:>5.1f}%  "
                      f"({sb['tokens']} tokens)")
                print(f"    => arm's own kept book:                                  "
                      f"settled={sa['settled']:<4} {sa['pnl_per_pos']:>7.2f}U/pos  "
                      f"win {sa['win_rate']:>5.1f}%  write-off {sa['writeoff_rate']:>5.1f}%")
                if sa["settled"] >= args.min_settled and sb["settled"] >= args.min_settled:
                    diffs = ([{"token_id": r["token_id"], "value": float(r["realized_pnl_usd"] or 0)}
                              for r in rows_a if r["status"] != "open"]
                             + [{"token_id": r["token_id"],
                                 "value": -float(r["realized_pnl_usd"] or 0)} for r in avoided
                                if r["status"] != "open"])
                    ci = clustered_interval(diffs)
                    gap = sa["pnl_per_pos"] + sb["pnl_per_pos"]
                    print(f"    kept-minus-avoided per position: {gap:+.3f}U"
                          + (f"   90% token-clustered CI [{ci[0]:+.3f}, {ci[1]:+.3f}]"
                             f"  excludes zero: {ci[0] > 0 or ci[1] < 0}" if ci else ""))
                else:
                    print(f"    NOT READY for the counterfactual - needs >={args.min_settled} "
                          f"settled on BOTH the kept book ({sa['settled']}) and the avoided set "
                          f"({sb['settled']}).")

        if not ready:
            print(f"    NOT READY - needs >={args.min_settled} settled per side "
                  f"(have arm {sa['settled']} / control {sc['settled']}). No verdict.")
            print()
            continue

        if kind == "exit":
            by_cohort = defaultdict(dict)
            for r in rows_a + rows_c:
                by_cohort[r["shadow_cohort_id"]][r["arm_id"]] = r
            diffs = []
            for _cohort, arms in by_cohort.items():
                if arm not in arms or control not in arms:
                    continue
                ra, rc = arms[arm], arms[control]
                if ra["status"] == "open" or rc["status"] == "open":
                    continue
                diffs.append({"token_id": ra["token_id"],
                              "value": float(ra["realized_pnl_usd"] or 0)
                                       - float(rc["realized_pnl_usd"] or 0)})
            print(f"    paired on {len(diffs)} shared settled cohort(s)")
            if diffs:
                mean = sum(d["value"] for d in diffs) / len(diffs)
                ci = clustered_interval(diffs)
                print(f"    within-cohort difference: {mean:+.3f}U"
                      + (f"   90% token-clustered CI [{ci[0]:+.3f}, {ci[1]:+.3f}]"
                         f"  excludes zero: {ci[0] > 0 or ci[1] < 0}" if ci else ""))
                # the check that catches one trade driving the result
                by_tok = defaultdict(float)
                for d in diffs:
                    by_tok[d["token_id"]] += d["value"]
                for k in (1, 2):
                    worst = sorted(by_tok, key=lambda t: -by_tok[t])[:k]
                    rem = [d for d in diffs if d["token_id"] not in worst]
                    if rem:
                        print(f"    drop top {k} token(s): "
                              f"{sum(d['value'] for d in rem)/len(rem):+.3f}U over {len(rem)}")
            else:
                print("    no shared settled cohorts yet")
        else:
            diffs = [{"token_id": r["token_id"],
                      "value": float(r["realized_pnl_usd"] or 0) - sc["pnl_per_pos"]}
                     for r in rows_a if r["status"] != "open"]
            ci = clustered_interval(diffs)
            print(f"    arm - control per position: {sa['pnl_per_pos'] - sc['pnl_per_pos']:+.3f}U"
                  + (f"   90% token-clustered CI [{ci[0]:+.3f}, {ci[1]:+.3f}]"
                     f"  excludes zero: {ci[0] > 0 or ci[1] < 0}" if ci else ""))
        print()

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
