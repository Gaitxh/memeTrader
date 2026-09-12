"""Gate readout: for each rejection REASON, did the refusal turn out to be right?

Why this exists
---------------
The entry-evaluation log records WHY the system refused 60,000+ times and is never revisited. So the
question the whole diagnosis keeps returning to - "which threshold, logic or risk rule is
systematically blocking tradeable candidates?" - had to be re-answered from scratch every time, with
a fresh ad-hoc query. This makes it a repeatable readout instead.

Method. For every evaluation, take the candidate's own snapshot price and look FORWARD on that
token's ALREADY-COLLECTED frames, asking whether it reached the +15% economic level the deployed
take-profit targets. If a reason's refused population touches MORE often than the baseline, that gate
is discarding candidates that would have moved.

The look-ahead direction is deliberate and is not the defect that was caught elsewhere in this
project: a FILTER may not use the future, but EVALUATING a filter must. The rule that a feature must
be computed only from pre-decision data applies to features, not to scoring.

Two design decisions that matter more than the arithmetic:

  * OBSERVER BOOKKEEPING IS NOT A DECISION. `cohort_observation` and `pattern_observation` record
    that a frame entered an observation sequence; they are not refusals by the strategy. They are
    reported separately and excluded from the verdict, because lumping them in makes ~61% of the log
    read as strategy refusals.

  * CENSORING IS PART OF THE TABLE, NOT A FOOTNOTE. A rejected candidate only has an outcome if the
    observation policy kept watching its token, so a large share of rejections have NO outcome at
    all. "No later frame" is UNKNOWN, never "did not move". A reason whose censoring rate is too high
    is reported as UNDETERMINABLE rather than as clean.

Usage
-----
    python scripts/gate_readout.py [--hours N] [--min-outcome N] [--max-censored PCT]
"""
from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# The deployed economic-return kernel, established from two independent sources and NOT to be
# re-derived (rounds 120-52/53):
#   store.py:25359-25363 declares the corrected kernel as
#       stake_usd*remaining_raw/initial_raw*current_price/entry_execution_price_usd*0.96
#   whose per-stake return is exactly 0.96*R - 1, and `chain_meme_trader_marks`
#   `trigger_evidence_json.pre_trigger.economic_return` - the value the ENGINE computed at each
#   decision - matches it EXACTLY in 1,265 of 1,300 marks, while the intuitive
#   "(1-BUY)/(1+SELL)*R - 1 - fees" form matches 0 of 1,300. That form charges the 4% buy slippage
#   twice (entry_execution_price_usd already contains it) and adds a fee the settings do not carry.
TARGET = 0.15
BOOKKEEPING = {"cohort_observation", "pattern_observation"}


def economic_return(price_ratio: float) -> float:
    return 0.96 * float(price_ratio) - 1.0


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def clustered_ci(items, iters=1500, seed=20260913):
    """Token-clustered 90% interval: positions/evaluations cluster inside a token."""
    rng = random.Random(seed)
    by_tok = defaultdict(list)
    for x in items:
        by_tok[x["tok"]].append(x["touch"])
    toks = list(by_tok)
    point = sum(x["touch"] for x in items) / len(items)
    draws = []
    for _ in range(iters):
        pick = [rng.choice(toks) for _ in toks]
        vals = [v for t in pick for v in by_tok[t]]
        draws.append(sum(vals) / len(vals))
    draws.sort()
    return point, draws[int(.05 * len(draws))], draws[int(.95 * len(draws))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=0.0,
                    help="only evaluations in the last N hours; 0 = the whole epoch")
    ap.add_argument("--min-outcome", type=int, default=30,
                    help="minimum evaluations with a KNOWN outcome before a reason is reported")
    ap.add_argument("--max-censored", type=float, default=90.0,
                    help="censoring %% above which a reason is reported as UNDETERMINABLE")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db = root / "data" / "memetrader_forward.sqlite3"
    if not db.is_file():
        print(f"database not found: {db}")
        return 2
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row

    print(f"db     : {db}")
    print(f"window : {'whole epoch' if not args.hours else f'last {args.hours:g}h'}"
          f"    target: +{TARGET*100:.0f}% economic    min outcome: {args.min_outcome}"
          f"    max censored: {args.max_censored:g}%")

    snap = {}
    series = defaultdict(list)
    for r in c.execute("select id, token_id, observed_at, price_usd from token_snapshots "
                       "where observed_at is not null order by id"):
        t = parse(r["observed_at"])
        if t is None:
            continue
        snap[r["id"]] = (r["token_id"], t, r["price_usd"])
        if r["price_usd"] and r["price_usd"] > 0:
            series[r["token_id"]].append((t, float(r["price_usd"])))
    for k in series:
        series[k].sort()

    where, params = "", []
    if args.hours:
        cut = (datetime.now(timezone.utc) - timedelta(hours=args.hours))
        where = "where evaluated_at >= ?"
        params = [cut.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"]

    seen, rows = set(), []
    for e in c.execute(f"select token_id, evaluated_at, reason, status, source_snapshot_id "
                       f"from chain_meme_trader_v6_entry_evaluations {where}", params):
        t = parse(e["evaluated_at"])
        if t is None or not e["source_snapshot_id"]:
            continue
        s = snap.get(e["source_snapshot_id"])
        if s is None or not s[2] or s[2] <= 0:
            continue
        # one evaluation per (token, minute): the 779-evals/3min cadence would otherwise
        # pseudo-replicate the same decision hundreds of times
        key = (e["token_id"], t.strftime("%Y-%m-%dT%H:%M"))
        if key in seen:
            continue
        seen.add(key)
        p0 = float(s[2])
        peak = None
        for (tt, px) in series.get(e["token_id"], ()):
            if tt <= t:
                continue
            if (tt - t) > timedelta(minutes=60):
                break
            peak = px if peak is None else max(peak, px)
        rows.append(dict(reason=str(e["reason"]), status=str(e["status"]), tok=e["token_id"],
                         touch=None if peak is None
                         else (1 if economic_return(peak / p0) >= TARGET else 0)))

    if not rows:
        print("\nno evaluations matched.")
        return 0
    known = [r for r in rows if r["touch"] is not None]
    if not known:
        print("\nNOT READY: no evaluation had a later frame to score.")
        return 0
    base = sum(r["touch"] for r in known) / len(known)
    print(f"\nunique (token, minute) evaluations: {len(rows):,}   "
          f"with an outcome: {len(known):,} ({100*len(known)/len(rows):.1f}%)")
    print(f"BASE +{TARGET*100:.0f}% touch rate: {base:.4f}")

    by = defaultdict(list)
    for r in rows:
        by[r["reason"]].append(r)

    print("\n" + "=" * 104)
    print("PER-REJECTION-REASON GATE QUALITY")
    print("  a reason whose refused population touches ABOVE baseline is discarding movers")
    print("=" * 104)
    print(f"   {'reason':<40} {'n':>7} {'cens%':>6} {'touch%':>8} {'vs base':>9} {'90% CI':>19}  note")
    blocking, undetermined = [], []
    for reason, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        k = [x for x in items if x["touch"] is not None]
        cens = 100 * (len(items) - len(k)) / len(items)
        if len(k) < args.min_outcome:
            print(f"   {reason[:40]:<40} {len(items):>7,} {cens:>5.1f}% "
                  f"{'':>8} {'':>9} {'':>19}  NOT ENOUGH OUTCOMES")
            undetermined.append(reason)
            continue
        p, lo, hi = clustered_ci(k)
        note = ""
        if cens > args.max_censored:
            note = "UNDETERMINABLE (censored)"
            undetermined.append(reason)
        elif reason in BOOKKEEPING:
            note = "observer bookkeeping, not a decision"
        elif lo > base:
            note = "<== ABOVE BASELINE"
            blocking.append(reason)
        elif hi < base:
            note = "below baseline (filtering correctly)"
        print(f"   {reason[:40]:<40} {len(items):>7,} {cens:>5.1f}% {p:>8.4f} {p-base:>+9.4f} "
              f"[{lo:>7.4f},{hi:>7.4f}]  {note}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    decisions = [r for r in by if r not in BOOKKEEPING]
    if blocking:
        print("   DECISION REASONS WHOSE REFUSED POPULATION TOUCHES ABOVE BASELINE:")
        for r in blocking:
            print(f"      {r}")
        print("   -> these may be over-strict; investigate before adding rules.")
    else:
        print("   NO decision reason refuses a population that touches +15% more often than")
        print("   baseline. No threshold, logic or risk rule is systematically discarding movers.")
        print(f"   ({len(decisions)} decision reasons examined.)")
    if undetermined:
        print(f"\n   NOT MEASURABLE from existing frames ({len(undetermined)}): "
              f"{', '.join(sorted(undetermined))}")
        print("   'cannot be measured' is reported separately from 'no problem' on purpose: a")
        print("   96%-censored reason next to a 40%-censored one would otherwise look equally sound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
