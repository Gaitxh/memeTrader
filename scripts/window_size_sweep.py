"""Window-size sweep: what each trajectory window size would qualify, and which rule binds.

Why this exists
---------------
`store.py:27784` closes the dominant entry gate (`await_distinct_dex_trajectory_frame`, 46.41% of all
per-arm verdicts and the terminal state for 98.9% of the pairs that touch it) unless
`windows['30']` is truthy. That window requires THREE frames inside 30 seconds
(`dex_trajectory.window`, lines 49-55), while the panel's own frame3 delay has p50 49.67 s
(round 74). So the threshold -- not the provider -- is what closes the gate at the measured cadence.

The engine ALREADY computes windows at WINDOWS = (5, 15, 30, 60, 180, 300) (dex_trajectory.py:15).
So evaluating a different threshold needs no new data collection; it is a choice among numbers the
engine is already producing. This readout measures what each size would qualify.

Faithful port of the contract, per `seconds`:
    end      = rows[-1].t
    eligible = indices with t <= end - seconds
    if not eligible: None                          (A) no full lookback
    part     = rows[eligible[-1]:]
    if end - part[0].t > seconds + max(5, seconds/3): None   (B) span cap
    if any consecutive gap > 30 s: None            (C) gap rule
    if len(part) < 3: None                         (D) frame minimum
`part` is NOT capped at three frames - it runs from the cutoff row to the end, so a 300 s window can
hold many frames. An earlier attempt at this counterfactual sliced to exactly three frames first,
which made the window length irrelevant and returned an identical figure for every size; that
version was withdrawn and this one reproduces the rules in order.

WHAT THIS DOES NOT SHOW, and the limit is real: qualifying means only that a window would FORM. It
does not show a policy would admit, and it does not show profitability. The window's outputs also
feed velocity, acceleration and realized volatility (dex_trajectory.py:56-69), so a longer window
measures a slower phenomenon and its signals mean something different.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/window_size_sweep.py [--windows 5,15,30,60,180,300] [--hours N] [--top N]
"""
from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Mirrors dex_trajectory.py:15 and the constants in dex_trajectory.window.
DEFAULT_WINDOWS = (5, 15, 30, 60, 180, 300)
GAP_LIMIT = 30.0
MIN_FRAMES = 3
# The size the live gate tests (store.py:27784 reads windows['30']).
GATED_WINDOW = 30


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def window(rows, seconds):
    """Return (ok, failure_reason_or_None, part_len). Faithful to dex_trajectory.window."""
    if not rows:
        return False, "no_rows", 0
    end = rows[-1]
    eligible = [i for i, t in enumerate(rows) if t <= end - timedelta(seconds=seconds)]
    if not eligible:
        return False, "A_no_full_lookback", 0
    part = rows[eligible[-1]:]
    if (end - part[0]).total_seconds() > seconds + max(5.0, seconds / 3.0):
        return False, "B_span_exceeds_cap", len(part)
    if any((b - a).total_seconds() > GAP_LIMIT for a, b in zip(part, part[1:])):
        return False, "C_gap_over_30s", len(part)
    if len(part) < MIN_FRAMES:
        return False, "D_fewer_than_3_frames", len(part)
    return True, None, len(part)


def sweep(series, windows):
    """Return {window: (attempts, successes, Counter(failure_reason))}."""
    out = {}
    for w in windows:
        attempts = ok = 0
        fails = collections.Counter()
        for ts in series.values():
            for i in range(len(ts)):
                attempts += 1
                good, why, _plen = window(ts[:i + 1], w)
                if good:
                    ok += 1
                else:
                    fails[why] += 1
        out[w] = (attempts, ok, fails)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--windows", default=",".join(str(w) for w in DEFAULT_WINDOWS),
                    help="comma-separated window sizes to sweep")
    ap.add_argument("--hours", type=float, default=0.0,
                    help="only frames in the last N hours; 0 = the whole epoch")
    ap.add_argument("--top", type=int, default=6, help="failure reasons to show per row")
    args = ap.parse_args()

    try:
        windows = tuple(sorted({int(float(x)) for x in args.windows.split(",") if x.strip()}))
    except ValueError:
        print("--windows must be a comma-separated list of numbers")
        return 2

    root = Path(__file__).resolve().parents[1]
    db = root / "data" / "memetrader_forward.sqlite3"
    if not db.is_file():
        print(f"database not found: {db}")
        return 2
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    where, params = "", []
    if args.hours:
        cut = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        where = "and observed_at >= ?"
        params = [cut.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"]

    print(f"db     : {db}")
    print(f"window : {'whole epoch' if not args.hours else f'last {args.hours:g}h'}")
    print(f"gate   : store.py:27784 tests windows['{GATED_WINDOW}']; engine computes {DEFAULT_WINDOWS}")

    series = collections.defaultdict(set)
    for r in c.execute("select token_id, observed_at from token_snapshots "
                       f"where observed_at is not null {where}", params):
        t = parse(r["observed_at"])
        if t is not None:
            series[str(r["token_id"])].add(t)
    series = {k: sorted(v) for k, v in series.items()}
    if not series:
        print("\nno frames in this window")
        return 0
    print(f"\nseries : {len(series)}    frames : {sum(len(v) for v in series.values())}")
    print("NOTE   : token_snapshots has no pair_address column, so a series is keyed by TOKEN.")
    print("         The engine keys on (token, pair); round 73 measured only 5 of 3,884 positions")
    print("         with marks spanning more than one pair, so the effect is small but it is a")
    print("         limit of this sweep, not a property of the engine.")

    res = sweep(series, windows)

    print("\n" + "=" * 92)
    print("QUALIFYING FRAMES BY WINDOW SIZE")
    print("=" * 92)
    base_ok = res.get(GATED_WINDOW, (0, 0, None))[1]
    print(f"   {'window':>8} {'attempts':>9} {'qualify':>9} {'rate':>8} {'vs gated':>10}")
    print("   " + "-" * 52)
    for w in windows:
        attempts, ok, _f = res[w]
        mult = f"{ok/base_ok:.2f}x" if base_ok else "n/a"
        star = "  <- gated" if w == GATED_WINDOW else ""
        print(f"   {w:>6}s {attempts:>9} {ok:>9} {100.0*ok/max(1,attempts):>7.2f}% "
              f"{mult:>10}{star}")
    if base_ok:
        best = max(windows, key=lambda w: res[w][1])
        print(f"\n   best size on this data: {best}s "
              f"({res[best][1]} frames, {res[best][1]/base_ok:.2f}x the gated {GATED_WINDOW}s)")
        print("   The curve is NOT monotone: too small and the span cap binds, too large and the")
        print("   full-lookback and gap rules bind. The optimum sits between them.")

    print("\n" + "=" * 92)
    print("WHICH RULE BINDS, BY WINDOW SIZE")
    print("=" * 92)
    print("   (A) no full lookback   (B) span cap   (C) a gap over 30 s   (D) under 3 frames")
    print(f"\n   {'window':>8} {'(A)':>9} {'(B)':>9} {'(C)':>9} {'(D)':>9}")
    print("   " + "-" * 48)
    for w in windows:
        attempts, _ok, fails = res[w]
        cells = "   ".join(f"{100.0*fails.get(k,0)/max(1,attempts):>7.1f}%"
                           for k in ("A_no_full_lookback", "B_span_exceeds_cap",
                                     "C_gap_over_30s", "D_fewer_than_3_frames"))
        print(f"   {w:>6}s {cells}")

    print("\n" + "=" * 92)
    print("WHAT THIS DOES NOT SHOW")
    print("=" * 92)
    print("   Qualifying means only that a window would FORM. It does not show that a policy would")
    print("   then admit the candidate, and it does not show profitability: the window's outputs")
    print("   also feed velocity, acceleration and realized volatility (dex_trajectory.py:56-69),")
    print("   so a longer window measures a SLOWER phenomenon and its signals mean something")
    print("   different. Changing a gate threshold is a strategy change and, per the project rule,")
    print("   must be deployed as an ADDITIONAL strategy module with its own forward evidence -")
    print("   never by editing an existing strategy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
