"""Writeoff readout: for the liquidity-floor cohort, was there a moment worth exiting into?

Why this exists
---------------
`dex_pool_liquidity_below_configured_floor` is the largest single loss path in the book (round 76:
1,150 settled positions, capture -436.6%, 1% win rate), and round 76's surprise was that its MEDIAN
running high was +0.171 -- these are not tokens that never moved. Round 77 then established the shape
directly and this script makes that repeatable:

  * at the moment each position set its running high, was the pool still above the floor?
    (a healthy pool at the high means a real moment existed; an already-dying pool means the high
    and the death coincide and there was nothing to capture)
  * how long from that high to the write-off, and how many marks did the engine hold in between?
  * did the peak reach THE ARM'S OWN `trailing_activate_return`?
    If it did not, that arm's trailing exit could not have fired by construction, so the write-off is
    a COVERAGE gap rather than a missed trigger. This is the distinction the whole readout exists for.

A necessary caveat, stated here so it travels with any number this prints: the engine stores the
running high's VALUE but not its TIME, so the high's time is recovered from the token's own mark
series as the first mark within 1% of the recorded high. That is a LOWER bound on when the high was
reached, which makes the measured high-to-writeoff gap an UNDER-estimate.

WHAT THIS DOES NOT SHOW: that changing any level would have captured the gain. The running high is
only knowable after it is exceeded, and a real-time rule acts on the frame it sees. Round 43 already
showed the take-profit's in-sample marginal value on the KEPT book was about zero once entry filters
were applied. Nothing here is a counterfactual.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/writeoff_readout.py [--floor 1000] [--top 20] [--json]
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

WRITEOFF_PREFIX = "dex_pool_liquidity_below_configured_floor"
DEFAULT_FLOOR = 1000.0
HIGH_TOLERANCE = 0.99          # a mark within 1% of the recorded high counts as reaching it


def parse(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def econ(ratio):
    """The deployed kernel, established in round 69 and not to be re-derived."""
    return 0.96 * float(ratio) - 1.0


def percentile(values, q):
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR,
                    help="pool liquidity floor in USD used to call a pool ALIVE at the high")
    ap.add_argument("--top", type=int, default=20, help="arms to print")
    ap.add_argument("--json", action="store_true", help="emit the summary as JSON")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    db = root / "data" / "memetrader_forward.sqlite3"
    if not db.is_file():
        print(f"database not found: {db}")
        return 2
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    rows = list(c.execute("""
        select arm_id, token_id, opened_at, closed_at, stake_usd, realized_pnl_usd,
               entry_execution_price_usd ex, entry_signal_price_usd en, highest_signal_price_usd hi
        from chain_meme_trader_positions
        where status in ('closed','written_off') and closed_at is not null
          and close_reason like ?""", (WRITEOFF_PREFIX + "%",)))
    print(f"db     : {db}")
    print(f"cohort : {len(rows)} positions ending in {WRITEOFF_PREFIX}")

    pos = []
    for r in rows:
        try:
            ep = float(r["ex"] or r["en"])
            hi = float(r["hi"])
            stake = float(r["stake_usd"] or 0)
            if ep <= 0 or stake <= 0 or hi <= 0:
                continue
            pos.append({"arm": str(r["arm_id"]), "tok": str(r["token_id"]),
                        "opened": parse(r["opened_at"]), "closed": parse(r["closed_at"]),
                        "peak": econ(hi / ep), "hi": hi, "ep": ep})
        except (TypeError, ValueError):
            continue
    if not pos:
        print("\nno usable positions")
        return 0

    summary = {"positions": len(pos)}

    print("\n" + "=" * 84)
    print("1. SHAPE: did these positions ever have a gain?")
    print("=" * 84)
    peaks = [p["peak"] for p in pos]
    lifes = [(p["closed"] - p["opened"]).total_seconds() / 60.0
             for p in pos if p["opened"] and p["closed"]]
    print(f"   peak econ: p25 {percentile(peaks,.25):+.4f}  p50 {percentile(peaks,.5):+.4f}  "
          f"p75 {percentile(peaks,.75):+.4f}  p90 {percentile(peaks,.9):+.4f}")
    pos_share = sum(1 for x in peaks if x > 0) / len(peaks)
    print(f"   peak positive        : {100.0*pos_share:.1f}%")
    print(f"   peak >= +10%         : {100.0*sum(1 for x in peaks if x>=0.10)/len(peaks):.1f}%")
    print(f"   peak >= +25%         : {100.0*sum(1 for x in peaks if x>=0.25)/len(peaks):.1f}%")
    if lifes:
        print(f"   life to write-off(min): p50 {percentile(lifes,.5):.1f}  "
              f"p75 {percentile(lifes,.75):.1f}  p90 {percentile(lifes,.9):.1f}")
    summary["peak_positive_share"] = pos_share

    print("\n" + "=" * 84)
    print("2. WAS THE POOL ALIVE WHEN THE HIGH WAS SET?")
    print("=" * 84)
    marks = collections.defaultdict(list)
    for r in c.execute("""select token_id, observed_at, price_usd, liquidity_usd
                          from chain_meme_trader_market_mark_history
                          where price_usd is not null and price_usd > 0
                          order by token_id, observed_at"""):
        t = parse(r["observed_at"])
        if t is not None:
            marks[str(r["token_id"])].append(
                (t, float(r["price_usd"]), float(r["liquidity_usd"] or 0)))
    alive = dying = unknown = 0
    gaps = []
    for p in pos:
        series = marks.get(p["tok"])
        if not series or not p["opened"] or not p["closed"]:
            continue
        inlife = [x for x in series if p["opened"] <= x[0] <= p["closed"]]
        hit = next((x for x in inlife if x[1] >= p["hi"] * HIGH_TOLERANCE), None)
        if hit is None:
            continue
        gaps.append((p["closed"] - hit[0]).total_seconds() / 60.0)
        if hit[2] <= 0:
            unknown += 1
        elif hit[2] >= args.floor:
            alive += 1
        else:
            dying += 1
    tot = alive + dying + unknown
    print(f"   traceable highs: {tot}")
    print(f"      pool ALIVE at the high (>= {args.floor:.0f} USD) : {alive} "
          f"({100.0*alive/max(1,tot):.1f}%)")
    print(f"      pool already below the floor                    : {dying} "
          f"({100.0*dying/max(1,tot):.1f}%)")
    print(f"      no liquidity number on that mark                : {unknown}")
    if gaps:
        print(f"\n   high -> write-off (minutes; a LOWER bound, see the docstring):")
        print("      " + "   ".join(f"p{int(q*100)} {percentile(gaps,q):.1f}"
                                   for q in (0.10, 0.25, 0.50, 0.75, 0.90)))
    summary["pool_alive_at_high"] = alive
    summary["pool_alive_share"] = alive / max(1, tot)

    print("\n" + "=" * 84)
    print("3. COULD ANY RULE HAVE FIRED? -- against THE ARM'S OWN contract")
    print("=" * 84)
    contract = {}
    # Resolve the version the POSITIONS belong to, then load THAT registration. An unqualified
    # `limit 1` on the registrations table picks an arbitrary epoch whose definition_json has no
    # "policies" key, which silently yields an empty contract and makes section 3 vacuous.
    vrow = c.execute("select definition_version from chain_meme_trader_positions limit 1").fetchone()
    if vrow is None:
        print("   no positions yet; skipping this section")
        reg = None
    else:
        reg = c.execute("select definition_json from chain_meme_trader_registrations "
                        "where definition_version=?", (vrow["definition_version"],)).fetchone()
    if reg is not None:
        try:
            from memetrader.store import Store
            eff = Store.chain_meme_trader_effective_definition_from_connection(
                c, vrow["definition_version"], json.loads(reg["definition_json"]))
            contract = {str(p.get("arm_id")): p for p in eff.get("policies", [])}
        except Exception as exc:
            print(f"   could not load the effective definition ({exc}); skipping this section")
    elif reg is None:
        print("   no registration row for the positions' version; skipping this section")

    if contract:
        reached = not_reached = 0
        for p in pos:
            act = (contract.get(p["arm"]) or {}).get("trailing_activate_return")
            if act is None:
                not_reached += 1
                continue
            if p["peak"] >= float(act):
                reached += 1
            else:
                not_reached += 1
        print(f"   positions whose peak reached their OWN trailing activation : {reached} "
              f"({100.0*reached/len(pos):.1f}%)")
        print(f"   positions that never reached it (trailing CANNOT fire)     : {not_reached} "
              f"({100.0*not_reached/len(pos):.1f}%)")
        print("\n   A high 'cannot fire' share means the cohort is a COVERAGE gap - the activation")
        print("   levels sit above where these pools actually peak - and NOT a missed trigger.")
        summary["reached_own_activation"] = reached
        summary["never_reached_activation"] = not_reached

        print(f"\n   {'arm':<42} {'n':>5} {'med peak':>9} {'trail_act':>10} {'hard_stop':>10}")
        print("   " + "-" * 80)
        per = collections.defaultdict(list)
        for p in pos:
            per[p["arm"]].append(p["peak"])
        for arm, ps in sorted(per.items(), key=lambda kv: -len(kv[1]))[:args.top]:
            pol = contract.get(arm) or {}
            act = pol.get("trailing_activate_return")
            hs = pol.get("hard_stop_return")
            print(f"   {arm[:40]:<42} {len(ps):>5} {percentile(ps,.5):>+9.3f} "
                  f"{('-' if act is None else f'{float(act):.2f}'):>10} "
                  f"{('-' if hs is None else f'{float(hs):.2f}'):>10}")

    print("\n" + "=" * 84)
    print("4. THE EVIDENCE THE WRITE-OFF ACTUALLY RESTED ON")
    print("=" * 84)
    print("   store.py:34676-34704 shows the write-off does NOT act on the mark history: it performs a")
    print("   POST-CONFIRMATION re-quote, accepts it only if fresh (<=15 s, line 34680) and still below")
    print("   the floor (line 34693), and stores it as terminal_dust_pool. Round 79 read only the mark")
    print("   history, found no collapse there, and wrongly concluded write-offs were unauditable.")
    ev_rows = list(c.execute(
        """select trigger_evidence_json from chain_meme_trader_marks
           where reason like '%dex_pool_liquidity_below_configured_floor%'"""))
    liq, lags, with_ev, neither = [], [], 0, 0
    for r in ev_rows:
        try:
            ev = json.loads(r["trigger_evidence_json"] or "{}")
        except (ValueError, TypeError):
            ev = {}
        td = ev.get("terminal_dust_pool") if isinstance(ev.get("terminal_dust_pool"), dict) else None
        pc = ev.get("post_confirmation") if isinstance(ev.get("post_confirmation"), dict) else None
        src = td or pc
        if src is None:
            neither += 1
            continue
        with_ev += 1
        try:
            if src.get("liquidity_usd") is not None:
                liq.append(float(src["liquidity_usd"]))
        except (TypeError, ValueError):
            pass
        o, rec = parse(src.get("observed_at")), parse(src.get("recorded_at"))
        if o and rec:
            lags.append((rec - o).total_seconds())
    print(f"\n   write-off marks examined            : {len(ev_rows)}")
    print(f"   carrying the confirming evidence    : {with_ev} "
          f"({100.0*with_ev/max(1,len(ev_rows)):.1f}%)")
    print(f"   carrying none                       : {neither}")
    if liq:
        print(f"\n   CONFIRMED liquidity at the write-off (n={len(liq)}):")
        print("      " + "   ".join(f"p{int(q*100)} {percentile(liq,q):,.2f}"
                                   for q in (0.10, 0.25, 0.50, 0.75, 0.90)))
        print(f"      min {min(liq):,.2f}   max {max(liq):,.2f}")
        below = sum(1 for x in liq if x < args.floor)
        print(f"      below the {args.floor:.0f} floor: {below}/{len(liq)} "
              f"= {100.0*below/len(liq):.1f}%")
        print("      A median far BELOW the floor is the signature of a genuine dust pool, i.e. a")
        print("      correct write-off; a cluster just under the floor would suggest premature exits.")
        summary["confirmed_liquidity_p50"] = percentile(liq, 0.5)
        summary["confirmed_below_floor_share"] = below / len(liq)
    if lags:
        print(f"\n   confirmation freshness observed_at -> recorded_at (n={len(lags)}):")
        print("      " + "   ".join(f"p{int(q*100)} {percentile(lags,q):.3f}s"
                                   for q in (0.10, 0.50, 0.90)))
        over = sum(1 for x in lags if x > 15)
        print(f"      exceeding the 15 s confirmation window: {over} "
              f"({100.0*over/len(lags):.2f}%)")

    print("\n" + "=" * 84)
    print("5. THE HEALTHY WINDOW -- how long the pool stayed tradeable, and what was seen")
    print("=" * 84)
    print("   This is the measurement that decides whether an exit COULD have acted. Note carefully:")
    print("   the gap from the LAST healthy mark to the write-off is a few seconds (the final sliver),")
    print("   but the SUSTAINED period above the floor is minutes. Confusing the two turns 'ample time")
    print("   with no action' into 'no time to act'.")
    marks2 = collections.defaultdict(list)
    for r in c.execute("""select token_id, observed_at, price_usd, liquidity_usd
                          from chain_meme_trader_market_mark_history
                          where price_usd is not null and price_usd > 0
                          order by token_id, observed_at"""):
        t = parse(r["observed_at"])
        if t is not None:
            marks2[str(r["token_id"])].append(
                (t, float(r["price_usd"]),
                 (float(r["liquidity_usd"]) if r["liquidity_usd"] is not None else None)))
    spans, nmarks, peak_h, peak_l = [], [], [], []
    for r in c.execute("""select token_id, opened_at, closed_at, entry_execution_price_usd ex,
                                 entry_signal_price_usd en
                          from chain_meme_trader_positions
                          where status in ('closed','written_off') and closed_at is not null
                            and close_reason like ?""", (WRITEOFF_PREFIX + "%",)):
        op, cl = parse(r["opened_at"]), parse(r["closed_at"])
        if op is None or cl is None:
            continue
        try:
            ep = float(r["ex"] or r["en"])
        except (TypeError, ValueError):
            continue
        if ep <= 0:
            continue
        inlife = [x for x in marks2.get(str(r["token_id"]), []) if op <= x[0] <= cl]
        healthy = [x for x in inlife if x[2] is not None and x[2] >= args.floor]
        if len(healthy) < 3:
            continue
        spans.append((healthy[-1][0] - healthy[0][0]).total_seconds())
        nmarks.append(len(healthy))
        peak_h.append(max(econ(x[1] / ep) for x in healthy))
        peak_l.append(max(econ(x[1] / ep) for x in inlife))
    if spans:
        m2 = len(spans)
        print(f"\n   positions with a measurable healthy window: {m2}")
        print("   span above the floor:      " +
              "   ".join(f"p{int(q*100)} {percentile(spans,q):,.0f}s" for q in (0.25, 0.50, 0.75)))
        print("   known-liquidity marks in it: " +
              "   ".join(f"p{int(q*100)} {percentile(nmarks,q):,.0f}" for q in (0.25, 0.50)))
        print(f"   span >= 300 s : {100.0*sum(1 for x in spans if x>=300)/m2:.1f}%"
              f"    marks >= 5 : {100.0*sum(1 for x in nmarks if x>=5)/m2:.1f}%")
        ph = percentile(peak_h, 0.5)
        pl = percentile(peak_l, 0.5)
        print(f"\n   peak econ WHILE healthy: p50 {ph:+.4f}      peak over the whole life: p50 "
              f"{pl:+.4f}")
        if pl is not None and ph is not None and abs(ph - pl) < 1e-9:
            print("   (identical on this data: every gain the position ever had was visible while the")
            print("    pool was still tradeable - so the exit rules were not starved of information.)")
        summary["healthy_span_p50_s"] = percentile(spans, 0.5)
        summary["healthy_marks_p50"] = percentile(nmarks, 0.5)
        summary["peak_while_healthy_p50"] = ph

    print("\n" + "=" * 84)
    print("WHAT THIS DOES NOT SHOW")
    print("=" * 84)
    print("""   THIS COHORT ONLY. Every figure above describes positions that ENDED in a dust write-off. A
   more aggressive exit rule also acts on positions that would have recovered or run on to large
   gains, and that cost is NOT measured here. Whether acting earlier helps the BOOK depends on how
   many eventual winners it sacrifices, which is unknown and could decide the sign.
   Also: an upper bound by construction if you simulate selling at the last healthy mark, 4% adverse
   slippage is not modelled, and it is a single-epoch in-sample reading. Changing an exit level is a
   strategy change: per the project rule it must be an ADDITIONAL strategy module with its own forward
   evidence, never an edit to an existing strategy.""")
    if args.json:
        print("\n" + json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
