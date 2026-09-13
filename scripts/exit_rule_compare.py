"""Exit-rule comparison on the WHOLE settled book -- with the truncation control built in.

Why this exists
---------------
Rounds 76-81 established what the exit side costs: the trailing exit captures only ~34.9% of its
median peak (round 76), 78% of the written-off positions never reached their own arm's activation
level (round 77), every gain was visible while the pool was still tradeable for a median 493 seconds
with a median 45 marks (round 81). Round 81's own stated limit was that it had looked ONLY at
positions that ultimately died, so the cost of acting earlier - on positions that would have recovered
- was unmeasured, and that cost decides the sign of its result.

This script measures it on every settled position with usable marks, so winners are included.

RULES COMPARED, all causal - the running high uses only marks at or before t, the exit executes at the
NEXT mark, and the value uses the engine's own kernel 0.96*R - 1 (round 69):
    ACTUAL                     what the deployed contracts realised
    ARM FROM ENTRY, dd d       the rule round 81 proposed
    ARM AT LEVEL l, dd d       the deployed shape, for reference

THE TRUNCATION CONTROL IS NOT OPTIONAL. ACTUAL is scored at each position's last mark while an
early-exiting rule is scored at its own exit mark, so if marks stop early for some positions the
comparison is biased toward early exit. Round 82 measured that it does not bind - the last in-life
mark sits p50 4 s before the close with zero cases over 60 s - and this script re-runs on a restricted
dense subset as the control rather than asserting the bias away.

WHAT IT DOES NOT SETTLE: live profitability. The mark stream is repeat-heavy (round 79: p50 0.24
distinct prices per mark), so movement between marks is invisible and both trigger and fill can
differ; 4% adverse slippage is not modelled beyond the engine's haircut; and it is one epoch
in-sample. A change here is a STRATEGY change: per the project rule it must be an ADDITIONAL strategy
module with its own forward evidence, never an edit to an existing strategy.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/exit_rule_compare.py [--min-marks 3] [--control-seconds 60] [--top 12]
"""
from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

DEFAULT_DRAWDOWNS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
DEFAULT_ARM_LEVELS = (0.20, 0.30, 0.45)
DEFAULT_ARM_DRAWDOWN = 0.25


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def econ(ratio):
    """The deployed kernel, established in round 69 and not to be re-derived."""
    return 0.96 * float(ratio) - 1.0


def trailing(marks, entry_price, drawdown, arm_level=None):
    """Causal trailing exit over `marks` (list of (t, price)).

    `arm_level` None means armed from the first mark (round 81's proposal); a float means the rule
    arms only after the running max reaches 1 + arm_level, which is the deployed shape.
    Returns the economic outcome. A rule that never triggers exits at the final mark.
    """
    peak = None
    armed = arm_level is None
    for i, (_t, p) in enumerate(marks):
        ratio = p / entry_price
        if peak is None:
            peak = ratio
            continue
        if not armed and peak >= 1.0 + arm_level:
            armed = True
        if armed and peak > 0 and ratio / peak - 1.0 <= -drawdown:
            nxt = marks[i + 1][1] if i + 1 < len(marks) else marks[-1][1]
            return econ(nxt / entry_price)
        peak = max(peak, ratio)
    return econ(marks[-1][1] / entry_price)


def load(c, min_marks):
    series = collections.defaultdict(list)
    for r in c.execute("""select token_id, observed_at, price_usd
                          from chain_meme_trader_market_mark_history
                          where price_usd is not null and price_usd > 0
                          order by token_id, observed_at"""):
        t = parse(r["observed_at"])
        if t is not None:
            series[str(r["token_id"])].append((t, float(r["price_usd"])))
    cases, excluded = [], 0
    for r in c.execute("""
            select token_id, opened_at, closed_at, stake_usd, realized_pnl_usd, close_reason,
                   entry_execution_price_usd ex, entry_signal_price_usd en
            from chain_meme_trader_positions
            where status in ('closed','written_off') and closed_at is not null"""):
        op, cl = parse(r["opened_at"]), parse(r["closed_at"])
        if op is None or cl is None:
            excluded += 1
            continue
        try:
            ep = float(r["ex"] or r["en"])
            stake = float(r["stake_usd"] or 0)
        except (TypeError, ValueError):
            excluded += 1
            continue
        if ep <= 0 or stake <= 0:
            excluded += 1
            continue
        marks = [x for x in series.get(str(r["token_id"]), []) if op <= x[0] <= cl]
        if len(marks) < min_marks:
            excluded += 1
            continue
        cases.append({
            "marks": marks, "ep": ep, "cl": cl, "tok": str(r["token_id"]),
            "actual": float(r["realized_pnl_usd"] or 0) / stake,
            "reason": str(r["close_reason"] or "").split(":")[0][:34],
        })
    return cases, excluded


def cluster(cases, value_key):
    """Aggregate a per-position value to the TOKEN, then bootstrap the token-clustered mean.

    WHY THIS EXISTS. The fleet runs 188 arms over a shared discovery stream, so thousands of positions
    are the SAME underlying outcome recorded many times: round 84 measured 4,643 settled positions
    covering only 94 distinct tokens, a median of 59 positions per token. A per-position interval
    therefore treats copies as independent draws and is far too narrow. The independent unit is the
    TOKEN, and the interval below is built by resampling tokens.
    """
    import random
    by_tok = collections.defaultdict(float)
    for x in cases:
        by_tok[x["tok"]] += x[value_key]
    deltas = sorted(by_tok.values())
    m = len(deltas)
    if m == 0:
        return None
    rng = random.Random(20260913)
    draws = []
    for _ in range(2000):
        pick = [deltas[rng.randrange(m)] for _ in range(m)]
        draws.append(sum(pick) / m)
    draws.sort()
    return {
        "tokens": m,
        "mean": sum(deltas) / m,
        "median": deltas[m // 2],
        "lo": draws[int(0.05 * len(draws))],
        "hi": draws[int(0.95 * len(draws))],
        "improved": sum(1 for d in deltas if d > 1e-9),
        "worsened": sum(1 for d in deltas if d < -1e-9),
    }


def report(cases, label, drawdowns, arm_levels):
    actual = sum(x["actual"] for x in cases)
    n = len(cases)
    print(f"\n   {label}: n={n}   ACTUAL {actual:+.1f} ({actual/n:+.3f}/pos)")
    print(f"      {'rule':<38} {'sum':>10} {'mean':>9} {'vs actual':>11}")
    print("      " + "-" * 70)
    for dd in drawdowns:
        s = sum(trailing(x["marks"], x["ep"], dd) for x in cases)
        print(f"      {'ARM FROM ENTRY, dd ' + f'{dd:.0%}':<38} {s:>+10.1f} {s/n:>+9.3f} "
              f"{s-actual:>+11.1f}")
    for lvl in arm_levels:
        s = sum(trailing(x["marks"], x["ep"], DEFAULT_ARM_DRAWDOWN, arm_level=lvl) for x in cases)
        print(f"      {'ARM AT +' + f'{lvl:.0%}' + f', dd {DEFAULT_ARM_DRAWDOWN:.0%}':<38} "
              f"{s:>+10.1f} {s/n:>+9.3f} {s-actual:>+11.1f}")
    return actual, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-marks", type=int, default=3,
                    help="minimum in-life marks for a position to be included")
    ap.add_argument("--control-seconds", type=float, default=60.0,
                    help="restrict the control run to positions whose last mark is this close to close")
    ap.add_argument("--top", type=int, default=12, help="exit paths to print")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db = root / "data" / "memetrader_forward.sqlite3"
    if not db.is_file():
        print(f"database not found: {db}")
        return 2
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    cases, excluded = load(c, args.min_marks)
    if not cases:
        print("no usable positions")
        return 0
    print(f"db      : {db}")
    print(f"usable  : {len(cases)}")
    print(f"excluded: {excluded}   (reported, never silently filtered)")

    print("\n" + "=" * 90)
    print("1. WHAT ACTUALLY HAPPENED, BY EXIT PATH")
    print("=" * 90)
    toks = {x["tok"] for x in cases}
    print(f"   THE DENOMINATOR THAT MATTERS: {len(cases)} positions over {len(toks)} DISTINCT TOKENS"
          f"  ({len(cases)/max(1,len(toks)):.1f} positions per token)")
    print("   The fleet runs many arms over a shared discovery stream, so positions are the same")
    print("   underlying outcome recorded repeatedly. The independent unit is the TOKEN, and every")
    print("   interval below is token-clustered; a per-position interval would be far too narrow.")
    by = collections.defaultdict(list)
    for x in cases:
        by[x["reason"]].append(x["actual"])
    print(f"   {'exit reason':<36} {'n':>5} {'sum':>10} {'mean':>9}")
    print("   " + "-" * 64)
    for k, v in sorted(by.items(), key=lambda kv: sum(kv[1]))[:args.top]:
        print(f"   {k:<36} {len(v):>5} {sum(v):>+10.1f} {sum(v)/len(v):>+9.3f}")
    total = sum(x["actual"] for x in cases)
    print(f"   {'TOTAL':<36} {len(cases):>5} {total:>+10.1f} {total/len(cases):>+9.3f}")

    print("\n" + "=" * 90)
    print("2. RULE COMPARISON")
    print("=" * 90)
    report(cases, "WHOLE BOOK", DEFAULT_DRAWDOWNS, DEFAULT_ARM_LEVELS)

    print("\n" + "=" * 90)
    print("3. WINNERS vs LOSERS -- does acting earlier sacrifice the winners?")
    print("=" * 90)
    for label, pred in (("actual WINNERS (realised > 0)", lambda a: a > 0),
                        ("actual LOSERS  (realised <= 0)", lambda a: a <= 0)):
        sel = [x for x in cases if pred(x["actual"])]
        if not sel:
            continue
        a = sum(x["actual"] for x in sel)
        print(f"\n   {label}: n={len(sel)}  actual {a:+.1f}")
        for dd in (0.15, 0.25, 0.35):
            s = sum(trailing(x["marks"], x["ep"], dd) for x in sel)
            print(f"      {'arm from entry, dd ' + f'{dd:.0%}':<38} {s:>+10.1f} "
                  f"{s-a:>+11.1f} vs actual")

    print("\n" + "=" * 90)
    print("4. THE TRUNCATION CONTROL -- is the gain an artifact of where marks stop?")
    print("=" * 90)
    gaps = sorted((x["cl"] - x["marks"][-1][0]).total_seconds() for x in cases)
    m = len(gaps)
    print("   ACTUAL is scored at the position's LAST mark; an early-exiting rule is scored at its")
    print("   own exit mark. If marks stop early, that biases the comparison toward early exit.")
    print(f"\n   last in-life mark -> close: p50 {gaps[m//2]:.0f}s  p75 {gaps[3*m//4]:.0f}s  "
          f"p90 {gaps[int(.9*m)]:.0f}s")
    over = sum(1 for g in gaps if g > args.control_seconds)
    print(f"   exceeding {args.control_seconds:.0f}s: {over} ({100.0*over/m:.1f}%)")
    sel = [x for x in cases if (x["cl"] - x["marks"][-1][0]).total_seconds() <= args.control_seconds]
    if len(sel) < 100:
        print(f"   control subset too small ({len(sel)}); reporting without it")
    else:
        report(sel, f"CONTROL: last mark within {args.control_seconds:.0f}s of close",
               DEFAULT_DRAWDOWNS[:4], DEFAULT_ARM_LEVELS[:2])

    print("\n" + "=" * 90)
    print("5. TOKEN-CLUSTERED VIEW -- the interval the real sample supports")
    print("=" * 90)
    for x in cases:
        x["rule25"] = trailing(x["marks"], x["ep"], DEFAULT_ARM_DRAWDOWN)
        x["delta"] = x["rule25"] - x["actual"]
    st = cluster(cases, "delta")
    if st is None:
        print("   not enough tokens")
    else:
        print(f"   distinct tokens            : {st['tokens']} "
              f"(versus {len(cases)} positions)")
        print(f"   mean per-TOKEN delta       : {st['mean']:+.3f} U")
        print(f"   median per-TOKEN delta     : {st['median']:+.3f} U")
        print(f"   90% CI (token-clustered)   : [{st['lo']:+.3f}, {st['hi']:+.3f}]")
        print(f"   EXCLUDES ZERO              : {st['lo'] > 0 or st['hi'] < 0}")
        print(f"   tokens IMPROVED / WORSENED : {st['improved']} / {st['worsened']}")
        print("\n   READ THE MEDIAN AS WELL AS THE MEAN. If the mean is much larger than the median, the")
        print("   gain is carried by a tail of tokens rather than being typical - round 31's concentration")
        print("   rule. And quote the effect PER TOKEN: the position-level figure is this one multiplied")
        print("   by the duplication factor, which is not additional evidence.")
        if abs(st["mean"]) > 3 * max(1e-9, abs(st["median"])):
            print("\n   NOTE: mean is more than 3x the median here, so the effect IS tail-driven.")

    print("\n" + "=" * 90)
    print("WHAT THIS DOES NOT SETTLE")
    print("=" * 90)
    print("""   Live profitability. The mark stream is repeat-heavy (round 79: p50 0.24 distinct prices per
   mark), so movement between marks is invisible and both the trigger and the fill can differ; 4%
   adverse slippage is not modelled beyond the engine's own 0.96 haircut; and this is one epoch
   in-sample. Parameter insensitivity across the drawdown sweep weakens but does not remove the
   round-26 selection risk.
   ALSO DO NOT read the arm-level rows as 'a lower activation would help': round 81 measured the arm's
   OWN contract at +122.8 versus +114 to +120 for arm-from-entry, i.e. the activation choice is worth
   only a few units while whether a trailing exit APPLIES AT ALL is worth an order of magnitude more.
   A change here is a STRATEGY change: per the project rule it must be an ADDITIONAL strategy module
   with its own forward evidence, never an edit to an existing strategy.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
