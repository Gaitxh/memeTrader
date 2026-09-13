"""Frame-window readout: per token, could the trajectory window EVER have formed, and why not.

Why this exists
---------------
`await_distinct_dex_trajectory_frame` is 46.4% of all per-arm admission verdicts and is the terminal
state for 98.9% of the (token, arm) pairs that touch it (round 72). It is set at store.py:27781-27785,
and it passes only when `dex_trajectory.window(rows, 30)` is truthy -- which requires ALL of:

    dex_trajectory.py:50  at least one row with t <= end - seconds   (a FULL 30 s lookback)
    dex_trajectory.py:53  end - part[0].t <= seconds + max(5, seconds/3)   (span <= 40 s)
    dex_trajectory.py:54  no consecutive gap > 30 s
    dex_trajectory.py:55  len(part) >= 3

Answering "why did this token not open a position" therefore needs per-token frame counts and the
exact rule that failed. Round 73 answered it with five ad-hoc scripts; this makes it one command.

What it reports
---------------
  * the frame-count distribution (the numbers that matter: p50 is 1 frame, and the window needs 3)
  * per token, whether the window could EVER form, and which rule failed at the last frame
  * the observed inter-frame gap distribution
  * the ingestion lag, so "frames are being dropped" can be confirmed or refuted rather than assumed
  * a fixed-cadence counterfactual: what a faster poll would buy, given the frames actually obtained

The counterfactual is included because it is the difference between two opposite fixes. Round 73
measured that compressing the cadence from 15 s to 5 s moves the number of window-capable series by
+0.9%, because cadence changes WHEN frames land, not HOW MANY arrive. Without that check, "the
provider updates every ~30 s" invites the wrong conclusion.

Read-only: this script opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/frame_window_readout.py [--hours N] [--top N] [--cadences 5,15,30]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# The window's own constants, mirroring dex_trajectory.window().
WINDOW_SECONDS = 30.0
SLACK = max(5.0, WINDOW_SECONDS / 3.0)
MIN_FRAMES = 3
MAX_GAP = 30.0


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def window_ok(part) -> bool:
    """The three span/gap/count rules of dex_trajectory.window, on an already-sliced part."""
    if len(part) < MIN_FRAMES:
        return False
    if (part[-1] - part[0]).total_seconds() > WINDOW_SECONDS + SLACK:
        return False
    return not any((b - a).total_seconds() > MAX_GAP for a, b in zip(part, part[1:]))


def slice_like_window(ts, end_index):
    """Reproduce dex_trajectory.window's row selection for the frame at `end_index`."""
    end = ts[end_index]
    upto = ts[:end_index + 1]
    eligible = [j for j, t in enumerate(upto)
                if t <= end - timedelta(seconds=WINDOW_SECONDS)]
    if not eligible:
        return None, "no_full_lookback"
    part = upto[eligible[-1]:]
    if (part[-1] - part[0]).total_seconds() > WINDOW_SECONDS + SLACK:
        return None, "span_exceeds_limit"
    if any((b - a).total_seconds() > MAX_GAP for a, b in zip(part, part[1:])):
        return None, "gap_exceeds_30s"
    if len(part) < MIN_FRAMES:
        return None, "fewer_than_3_frames"
    return part, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=0.0,
                    help="only frames in the last N hours; 0 = the whole epoch")
    ap.add_argument("--top", type=int, default=8, help="rows in the frame-count table")
    ap.add_argument("--cadences", default="5,10,15,20,30,60",
                    help="comma-separated fixed cadences for the counterfactual")
    args = ap.parse_args()

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
        where = "where observed_at >= ?"
        params = [cut.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"]

    print(f"db     : {db}")
    print(f"window : {'whole epoch' if not args.hours else f'last {args.hours:g}h'}")
    print("gate   : store.py:27781-27785, passing only when dex_trajectory.window(rows, 30) is truthy")

    series = defaultdict(set)
    lag = []
    for r in c.execute(f"select token_id, observed_at, recorded_at from token_snapshots "
                       f"where observed_at is not null {where.replace('where', 'and') if where else ''}",
                       params):
        t = parse(r["observed_at"])
        if t is None:
            continue
        series[str(r["token_id"])].add(t)
        rec = parse(r["recorded_at"])
        if rec is not None:
            lag.append((rec - t).total_seconds())
    series = {k: sorted(v) for k, v in series.items()}
    if not series:
        print("\nno frames in this window")
        return 0

    print("\n" + "=" * 78)
    print("1. FRAME COUNT PER TOKEN  (the window needs >=3)")
    print("=" * 78)
    lens = sorted(len(v) for v in series.values())
    n = len(lens)
    buckets = Counter()
    for L in lens:
        buckets["1" if L == 1 else "2" if L == 2 else "3-4" if L <= 4 else
                "5-9" if L <= 9 else "10-29" if L <= 29 else "30+"] += 1
    for k in ("1", "2", "3-4", "5-9", "10-29", "30+"):
        print(f"   {k:>6} frames : {buckets.get(k,0):>7}  ({100.0*buckets.get(k,0)/n:5.1f}%)")
    print(f"   p50 {lens[n//2]}   p75 {lens[3*n//4]}   p90 {lens[int(.9*n)]}   max {lens[-1]}")
    ge3 = sum(1 for L in lens if L >= MIN_FRAMES)
    print(f"\n   tokens with >= {MIN_FRAMES} frames : {ge3} / {n} = {100.0*ge3/n:.1f}%")
    print(f"   tokens with exactly 1 frame  : {buckets.get('1',0)} "
          f"({100.0*buckets.get('1',0)/n:.1f}%) - these can NEVER pass the gate")

    print("\n" + "=" * 78)
    print("2. COULD THE WINDOW EVER FORM, AND IF NOT WHICH RULE FAILED")
    print("=" * 78)
    frames_total = ok_frames = 0
    series_ok = 0
    reasons = Counter()
    for ts in series.values():
        any_ok = False
        for i in range(len(ts)):
            frames_total += 1
            part, why = slice_like_window(ts, i)
            if part is None:
                reasons[why] += 1
            else:
                ok_frames += 1
                any_ok = True
        if any_ok:
            series_ok += 1
    print(f"   frames examined                        : {frames_total}")
    print(f"   frames where the 30s window could form : {ok_frames} "
          f"= {100.0*ok_frames/max(1,frames_total):.2f}%")
    print(f"   tokens with at least one such frame    : {series_ok} / {n} "
          f"= {100.0*series_ok/n:.2f}%")
    print("\n   why it failed, counted per frame:")
    for k, v in reasons.most_common():
        print(f"      {k:<24} {v:>8}  ({100.0*v/max(1,frames_total):5.1f}%)")

    print("\n" + "=" * 78)
    print("3. INTER-FRAME ARRIVAL GAPS")
    print("=" * 78)
    gaps = []
    for ts in series.values():
        gaps.extend((b - a).total_seconds() for a, b in zip(ts, ts[1:]))
    gaps.sort()
    m = len(gaps)
    if m:
        for q in (0.10, 0.25, 0.50, 0.75, 0.90):
            print(f"   p{int(q*100):<3} {gaps[min(m-1,int(q*m))]:>9.2f} s")
        print(f"   gaps <= {MAX_GAP:g}s : {sum(1 for g in gaps if g <= MAX_GAP)}/{m} "
              f"= {100.0*sum(1 for g in gaps if g<=MAX_GAP)/m:.1f}%")

    print("\n" + "=" * 78)
    print("4. IS ANYTHING BEING DROPPED AT INGESTION?")
    print("=" * 78)
    lag.sort()
    k = len(lag)
    if k:
        for q in (0.10, 0.50, 0.90, 0.99):
            print(f"   observed_at -> recorded_at p{int(q*100):<3} {lag[min(k-1,int(q*k))]:>8.3f} s")
        over = sum(1 for x in lag if x > 30)
        print(f"   exceeding 30 s: {over} ({100.0*over/k:.3f}%)")
        print("   => a near-zero share here means the ingestion ceiling is NOT the constraint.")

    print("\n" + "=" * 78)
    print("5. COUNTERFACTUAL: what would a fixed cadence buy, given the frames we actually got?")
    print("=" * 78)
    print("   Frames are generated over each series' OBSERVED lifetime at a fixed cadence, then the")
    print("   window rules are applied. This separates 'frames land too slowly' (cadence) from")
    print("   'too few frames exist' (supply) - two problems with opposite fixes.")
    multi = [ts for ts in series.values() if len(ts) >= 2]
    print(f"\n   {'cadence':>9} {'window OK':>11} {'series':>9} {'vs 15s':>9}")
    try:
        cadences = [float(x) for x in args.cadences.split(",") if x.strip()]
    except ValueError:
        cadences = [5.0, 15.0, 30.0]
    results = {}
    for cad in sorted(cadences):
        okc = 0
        for ts in multi:
            span = (ts[-1] - ts[0]).total_seconds()
            if span <= 0:
                continue
            count = int(span // cad) + 1
            if count < MIN_FRAMES:
                continue
            sim = [ts[0] + timedelta(seconds=i * cad) for i in range(count)]
            if window_ok(sim[-MIN_FRAMES:]):
                okc += 1
        results[cad] = okc
    # The reference cadence is 15 s: the observer's fast path before any back-off. It is looked up
    # explicitly rather than taken from whichever cadence happened to be evaluated first, which is
    # what an earlier version did and it printed every row as 0.0% off its own baseline.
    reference = results.get(15.0)
    for cad in sorted(results):
        okc = results[cad]
        if reference:
            delta = f"{100.0*(okc-reference)/reference:+.1f}%"
        else:
            delta = "n/a"
        print(f"   {cad:>7.0f}s {okc:>11} {len(multi):>9} {delta:>9}")
    if reference:
        print(f"\n   reference cadence = 15 s ({reference} window-capable series).")
    print("   => a flat column means cadence is NOT the lever; the frame COUNT is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
