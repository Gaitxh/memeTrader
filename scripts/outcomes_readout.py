"""Outcomes readout: the per-arm PASS/FAIL distribution the engine already records but nobody reads.

Why this exists
---------------
`chain_meme_trader_v6_entry_evaluations.feature_json['outcomes']` is written by the live admission
loop at `store.py:28225` and persisted at `store.py:28283`. It holds ONE REASON PER ARM for every
candidate frame the engine considered -- 5.9M verdicts across 74 distinct reasons in the current
epoch. The `reason` COLUMN of the same table holds only a single summary string per row, so until
now the real distribution was unreachable without an ad-hoc script, and the whole diagnosis kept
re-deriving it (round 72 read it for the first time).

This makes it a repeatable readout, at the same level as `scripts/gate_readout.py`.

What it reports, and why each choice is deliberate
--------------------------------------------------
  * VERDICTS vs TOKENS. A reason's verdict count is per (row, arm); its reach is per TOKEN. Both are
    printed side by side because quoting one as the other is a standing error in this project
    (rule 26: a merged count must be divided by distinct entities). In the current epoch
    `strategy_token_lifetime_entry_consumed` has 515,748 verdicts but touches only 57 tokens.
  * FINAL-STATE SHARE. A reason can dominate the verdict count while being a transient state every
    candidate passes through, or it can be where flow TERMINATES. The share of (token, arm) pairs
    whose LAST recorded reason is this one separates the two. In the current epoch
    `await_distinct_dex_trajectory_frame` is 46.4% of verdicts AND 86.9% of final states, i.e. it is
    a terminal wait, not a filter.
  * TERMINAL SHARE, NOT "ESCAPE RATE". For each reason, the share of the pairs that touch it whose
    FINAL recorded reason is still that one. This is the quantity that needs no arbitrary choice: a
    pair can oscillate (gate -> other -> gate -> ...), so "did it escape?" depends on whether you
    ask about the first occurrence or all of them. Measured on the current epoch for
    `await_distinct_dex_trajectory_frame`: 2.6% of gate-touching pairs ever record a different
    reason after their first gate row, and 98.9% END on the gate. An earlier version of this script
    printed an "escape %" that divided by VERDICT count instead of pair count and therefore reported
    40.6% for the same gate; that figure was wrong and is not reported.
  * NO PRICE DATA. This readout deliberately uses only the engine's own records. Grading gates by
    forward price move was attempted in round 72 and FAILED: only ~1,231 tokens have a usable mark
    series, their running-high p10..p75 are all exactly -0.0400, and their implied touch rate is
    7.05% against the engine's measured 41.08% for positions -- a position-driven sample that is not
    representative of refused candidates. Nothing price-based is reported here.

Usage
-----
    python scripts/outcomes_readout.py [--hours N] [--top N] [--reason SUBSTRING]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Reasons that are not strategy refusals. `cohort_frozen_opportunity_ready` is the admission signal
# (it means the candidate WAS accepted), so it must never be read as a refusal.
ADMISSION_REASONS = {"cohort_frozen_opportunity_ready"}


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load(c, where, params):
    """Return (verdicts, token_sets, pair_sequences), all keyed by reason."""
    verdicts = Counter()
    tokens = defaultdict(set)
    pairs = defaultdict(list)          # (token, arm) -> [reason, ...] in time order
    rows_with = 0
    for r in c.execute(
            "select token_id, evaluated_at, feature_json "
            f"from chain_meme_trader_v6_entry_evaluations {where} order by evaluated_at", params):
        raw = r["feature_json"]
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except (ValueError, TypeError):
            continue
        oc = d.get("outcomes")
        if not isinstance(oc, dict) or not oc:
            continue
        rows_with += 1
        tok = str(r["token_id"])
        for arm, reason in oc.items():
            rs = str(reason)
            verdicts[rs] += 1
            tokens[rs].add(tok)
            pairs[(tok, str(arm))].append(rs)
    return verdicts, tokens, pairs, rows_with


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=0.0,
                    help="only evaluations in the last N hours; 0 = the whole epoch")
    ap.add_argument("--top", type=int, default=25, help="rows to print")
    ap.add_argument("--reason", default="", help="only reasons containing this substring")
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
        where = "where evaluated_at >= ?"
        params = [cut.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"]

    print(f"db     : {db}")
    print(f"window : {'whole epoch' if not args.hours else f'last {args.hours:g}h'}")
    print("source : feature_json['outcomes'] (store.py:28225 writes it, :28283 persists it)")

    verdicts, tokens, pairs, rows_with = load(c, where, params)
    total = sum(verdicts.values())
    if not total:
        print("\nno outcomes recorded in this window")
        return 0

    pos_tokens = {r[0] for r in c.execute(
        "select distinct token_id from chain_meme_trader_positions")}
    eval_tokens = {r[0] for r in c.execute(
        "select distinct token_id from chain_meme_trader_v6_entry_evaluations")}
    base = len(pos_tokens) / max(1, len(eval_tokens))

    # final state per pair, and how many pairs touch each reason at all
    final = Counter()
    for _k, seq in pairs.items():
        if seq:
            final[seq[-1]] += 1
    total_pairs = sum(final.values())
    touch_pairs = Counter()
    end_on = Counter()
    for _k, seq in pairs.items():
        for rs in set(seq):
            touch_pairs[rs] += 1
            if seq[-1] == rs:
                end_on[rs] += 1

    print(f"\nrows with outcomes : {rows_with}")
    print(f"per-arm verdicts   : {total}")
    print(f"distinct reasons   : {len(verdicts)}")
    print(f"(token, arm) pairs : {total_pairs}")
    print(f"tokens evaluated   : {len(eval_tokens)}    tokens with a position: {len(pos_tokens)}"
          f"    base rate: {100*base:.2f}%")

    print(f"\n{'reason':<44} {'verdicts':>10} {'v%':>7} {'tokens':>7} {'tok%':>6} "
          f"{'w/pos':>6} {'rate':>7} {'pairs':>9} {'ends%':>7} {'final%':>7}")
    print("-" * 120)
    shown = 0
    for rs, n in verdicts.most_common():
        if args.reason and args.reason not in rs:
            continue
        toks = tokens[rs]
        hit = len(toks & pos_tokens)
        tp = touch_pairs.get(rs, 0)
        tag = " [admission]" if rs in ADMISSION_REASONS else ""
        print(f"{rs[:42]:<44} {n:>10} {100.0*n/total:>6.2f}% {len(toks):>7} "
              f"{100.0*len(toks)/max(1,len(eval_tokens)):>5.1f}% {hit:>6} "
              f"{100.0*hit/max(1,len(toks)):>6.2f}% {tp:>9} "
              f"{100.0*end_on.get(rs,0)/max(1,tp):>6.1f}% "
              f"{100.0*final.get(rs,0)/max(1,total_pairs):>6.2f}%{tag}")
        shown += 1
        if shown >= args.top:
            break

    print("\nHOW TO READ THIS")
    print("  verdicts   per (evaluation row, arm); tokens is per DISTINCT token - never quote one")
    print("             as the other (rule 26).")
    print("  rate       share of THIS reason's tokens that ever reached a position.")
    print("             Above the base rate means the reason is not discarding good candidates;")
    print("             ~100% means the reason only applies to already-positioned tokens, i.e. it")
    print("             is a duplicate-entry guard, not a filter.")
    print("  pairs      (token, arm) pairs that record this reason AT LEAST ONCE.")
    print("  ends%      of those pairs, the share whose LAST recorded reason is still this one.")
    print("             Near 100% means candidate flow TERMINATES in this state: pairs do not fail")
    print("             the gate and move on, they stop advancing. This is the load-bearing column.")
    print("  final%     share of ALL pairs whose last reason is this one (population view).")
    print("\n  No price-based outcome is reported: the mark series is position-driven (only ~1,231")
    print("  tokens have one, running-high p10..p75 all exactly -0.0400), so it is not")
    print("  representative of refused candidates. See ROUND120_72_RECORD.md section 4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
