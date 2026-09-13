"""Lease-panel readout: the observation scheduler's OWN record of what it did and why.

Why this exists
---------------
The runtime checkpoints its per-token observation state into the `kv` table:

    chain-meme-pattern-watch:leases145   the live lease items + mature_window_counts
    chain-meme-pattern-watch             watch bookkeeping (borrows, mover reservations, buckets)
    coverage145:status                   the runtime's own coverage accounting

Each lease item carries `frame_count`, `frame2_delay_seconds`, `frame3_delay_seconds`,
`admitted_at`, `min_observe_until`, `next_due_at`, `last_useful_at`, `coverage_gap`, `phase`,
`window_counted`, `window_expired` and `window_results`.

Rounds 64-73 reconstructed observation behaviour from `token_snapshots` -- what happened to be
stored -- because this panel was not known to exist. That reconstruction could only reach "too few
frames arrive". The panel reaches the NEXT distinction, which matters because the two have opposite
fixes:

    SOURCE_NO_UPDATE  (observation_leases145.py:163)  fewer than 3 frames existed by the window
        deadline + 30 s grace  ->  the SOURCE did not answer, so no amount of path repair helps
    UNKNOWN_PATH_GAP  (observation_leases145.py:162)  the frames DID arrive but a requirement
        failed: a coverage gap, or the last frame came >30 s after the deadline, or <3 frames
        ->  a continuity/path problem, not a source problem

Why the window length matters here: `dex_trajectory.window(rows, 30)` requires THREE frames inside
30 seconds (dex_trajectory.py:50-55), and that is exactly what store.py:27784 tests when it sets the
dominant gate `await_distinct_dex_trajectory_frame`. The panel's own frame3 delay has p50 49.67 s.

UNIT CAVEAT THAT MUST TRAVEL WITH THE WINDOW TABLE: `mature_window_counts` tallies distinct
(token, window) PHASE TRANSITIONS, counted once each when a window matures -- these are NOT distinct
tokens, and the panel covers only tokens admitted to the observer. Column sums are therefore not a
token population, so only WITHIN-ROW shares are comparable. Quoting a column total as "how many
tokens" would be a unit error of exactly the kind this project has made repeatedly.

SECOND CAVEAT, about the lease list itself: the persisted lease count is a LOWER BOUND, not a
population. `observation_leases145.dump_state(watch, now, *, limit: int = 30)` caps the checkpoint at
30 rows and `bounded_summary()` defaults to the same limit. Round 86 first printed "live leases: 9"
as though it were how many tokens the scheduler held; it is a truncated window whose tightness cannot
be judged from the panel alone. For a count that IS a direct read of runtime state, use
`non_held_by_chain_bucket` from `chain-meme-pattern-watch`: it is computed in memory from the same
counter that gates admission (runtime.py:8148-8150 against runtime.py:7894-7898) and reports
occupancy against `base_caps`.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/lease_panel_readout.py [--top N] [--json]
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

LEASE_KEY = "chain-meme-pattern-watch:leases145"
WATCH_KEY = "chain-meme-pattern-watch"
COVERAGE_KEY = "coverage145:status"
WINDOWS = (30, 120, 300)


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def percentile(values, q):
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=12, help="rows to print per table")
    ap.add_argument("--json", action="store_true", help="emit the summary as JSON instead")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db = root / "data" / "memetrader_forward.sqlite3"
    if not db.is_file():
        print(f"database not found: {db}")
        return 2
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    def kv(key):
        row = c.execute("select value_json, updated_at from kv where key=?", (key,)).fetchone()
        if row is None:
            return None, None
        try:
            return json.loads(row["value_json"]), row["updated_at"]
        except (ValueError, TypeError):
            return None, row["updated_at"]

    leases_obj, leases_at = kv(LEASE_KEY)
    if leases_obj is None:
        print(f"{LEASE_KEY} absent or unparseable; the observer may not have started")
        return 0

    # `leases` is a LIST of items. An earlier probe assumed a dict and reported zero items, so the
    # shape is asserted rather than duck-typed.
    leases = leases_obj.get("leases")
    if not isinstance(leases, list):
        print(f"unexpected shape: leases is {type(leases).__name__}, expected list")
        return 0

    # Field names carry the caveat too: an earlier version emitted `live_leases: 9`, which reads as a
    # population in machine form even though the panel is truncated. Rows + an explicit flag cannot be
    # misread the same way.
    summary = {
        "as_of": leases_at,
        "lease_rows_persisted": len(leases),
        "count_is_lower_bound": True,
        "panel_truncation_limit": 30,
    }

    print(f"db        : {db}")
    print(f"panel as of: {leases_at}")
    print(f"rows persisted: {len(leases)}")
    print("""
   *** THIS COUNT IS A LOWER BOUND, NOT A POPULATION ***
   observation_leases145.dump_state(watch, now, *, limit: int = 30) caps the checkpoint at 30 rows,
   and bounded_summary() defaults to the same limit. So the panel shows at most 30 leases and may show
   far fewer while the runtime holds many more. Round 86 printed 'live leases: 9' as if it were the
   population; it is a truncated window whose tightness cannot be judged from the panel alone.
   For a count that IS a direct read of the runtime state, use `non_held_by_chain_bucket` from
   chain-meme-pattern-watch: it is computed in memory from the same counter that gates admission
   (runtime.py:8148-8150 against runtime.py:7894-7898) and reports occupancy against base_caps.""")

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    print("\n" + "=" * 84)
    print("1. LIVE LEASES: frame_count of the tokens under observation right now")
    print("=" * 84)
    fc = collections.Counter(int(it.get("frame_count") or 0) for it in leases if isinstance(it, dict))
    for k in sorted(fc):
        print(f"   {k:>5} frames : {fc[k]:>4}")
    ge3 = sum(n for k, n in fc.items() if k >= 3)
    print(f"   tokens with >= 3 frames : {ge3}/{len(leases)} "
          f"({100.0*ge3/max(1,len(leases)):.1f}%)  <- the trajectory window needs 3")

    print("\n" + "=" * 84)
    print("2. FRAME DELAYS: how long the 2nd and 3rd frame actually took")
    print("=" * 84)
    for field in ("frame2_delay_seconds", "frame3_delay_seconds"):
        vals = [float(it[field]) for it in leases
                if isinstance(it, dict) and it.get(field) is not None]
        if not vals:
            print(f"   {field}: none recorded")
            continue
        summary[field] = {f"p{int(q*100)}": percentile(vals, q)
                          for q in (0.10, 0.25, 0.50, 0.75, 0.90)}
        print(f"   {field}  (n={len(vals)})")
        print("      " + "   ".join(
            f"p{int(q*100)} {percentile(vals, q):.2f}s" for q in (0.10, 0.25, 0.50, 0.75, 0.90)))
    print("\n   The trajectory window requires 3 frames INSIDE 30 s (dex_trajectory.py:50-55), and")
    print("   store.py:27784 tests exactly that when it sets await_distinct_dex_trajectory_frame.")
    print("   Compare frame3_delay_seconds above against 30 s.")

    print("\n" + "=" * 84)
    print("3. MATURE WINDOW OUTCOMES, cumulative -- the next distinction after 'too few frames'")
    print("=" * 84)
    counts = leases_obj.get("mature_window_counts") or {}
    if not counts:
        print("   mature_window_counts absent")
    else:
        per = collections.defaultdict(dict)
        for k, v in counts.items():
            if ":" in str(k):
                w, outcome = str(k).split(":", 1)
                per[w][outcome] = v
        print(f"   {'window':>8} {'attempts':>10} {'OBSERVED':>18} {'SOURCE_NO_UPDATE':>20} "
              f"{'UNKNOWN_PATH_GAP':>20}")
        print("   " + "-" * 80)
        for w in sorted(per, key=lambda x: int(x) if x.isdigit() else 0):
            d = per[w]
            tot = sum(d.values())
            o = d.get("OBSERVED", 0)
            s = d.get("SOURCE_NO_UPDATE", 0)
            g = d.get("UNKNOWN_PATH_GAP", 0)
            print(f"   {w+'s':>8} {tot:>10} {o:>9} ({100.0*o/tot:>4.1f}%) "
                  f"{s:>9} ({100.0*s/tot:>4.1f}%) {g:>9} ({100.0*g/tot:>4.1f}%)")
            summary.setdefault("mature_windows", {})[w] = {
                "attempts": tot, "observed": o, "source_no_update": s, "unknown_path_gap": g}
        print("\n   CAVEAT THAT TRAVELS WITH THIS TABLE: these are distinct (token, window) PHASE")
        print("   TRANSITIONS the panel counted once each -- NOT distinct tokens -- and the panel")
        print("   covers only tokens admitted to the observer. Column sums are therefore not a")
        print("   token population. Only the WITHIN-ROW shares are comparable.")
        print("\n   WHAT THE OUTCOMES MEAN (observation_leases145.py:162-163):")
        print("      SOURCE_NO_UPDATE  fewer than 3 frames by deadline + 30 s grace -> the SOURCE")
        print("                        did not answer; no path repair helps")
        print("      UNKNOWN_PATH_GAP  frames DID arrive but a requirement failed (coverage gap,")
        print("                        late last frame, or <3 frames) -> a continuity problem")

    print("\n" + "=" * 84)
    print("4. WATCH / COVERAGE COUNTERS")
    print("=" * 84)
    watch, watch_at = kv(WATCH_KEY)
    if isinstance(watch, dict):
        print(f"   {WATCH_KEY}  ({watch_at})")
        nhb = watch.get("non_held_by_chain_bucket") or {}
        if nhb:
            # This one IS a direct read of the runtime's admission counter, unlike the truncated
            # lease list above - see the caveat printed at the top of this output.
            caps = {"early": 3, "growth": 4, "mature": 3}
            print("   CANDIDATE SLOT OCCUPANCY (non_held_by_chain_bucket vs base_caps):")
            full = total = 0
            for chain, buckets in nhb.items():
                for bucket, occ in (buckets or {}).items():
                    cap = caps.get(bucket, 0)
                    isfull = occ >= cap
                    full += 1 if isfull else 0
                    total += 1
                    print(f"      {str(chain):<11} {str(bucket):<8} {occ:>3}/{cap:<3} "
                          f"{'FULL' if isfull else ''}")
            print(f"      -> {full} of {total} buckets at cap. Held positions do NOT consume these")
            print(f"         slots (runtime.py:7894 gates only `if key not in held`), so FULL here means")
            print(f"         candidates are waiting behind the candidate cap.")
        for k in ("borrows_since_start", "mover_watching", "mover_reserved_admissions",
                  "mover_reserved_injections", "other_pool_quote_skips_since_start"):
            if k in watch:
                v = watch[k]
                print(f"      {k:<38} {str(v)[:60]}")
    cov, cov_at = kv(COVERAGE_KEY)
    if isinstance(cov, dict):
        print(f"\n   {COVERAGE_KEY}  ({cov_at})")
        for k in ("as_of", "denominator", "target_cadence_seconds", "truncated",
                  "extra_request_budget", "protection_basis"):
            if k in cov:
                print(f"      {k:<38} {str(cov[k])[:60]}")
        for k in ("opportunities", "priority_targets", "membership"):
            v = cov.get(k)
            if isinstance(v, (list, dict)):
                print(f"      {k:<38} {type(v).__name__} of {len(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
