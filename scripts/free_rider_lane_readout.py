"""Free-rider observation lane readout: the fastest trajectory source in the system, and its intake.

Why this exists
---------------
Round 86 showed the quote path reaches ~9x more tokens than the 30 candidate slots, and round 87
located where that surplus goes. `shared_batch148` is a free-rider lane: it appends extra token
identities to DEX batches another lane is ALREADY fetching, under the contract
`extras_only_in_existing_nonempty_batch_spare_capacity`, so `additional_http_batches` is 0 -- the extra
frames cost no additional HTTP request.

Measured on 2026-09-13, its output is the best in the system: among its finished leases the 30-second
window was OBSERVED for 16 of 16, with frame2 delay p50 5.71 s, against the primary observer's 11 of 25
and frame2 p50 30.82 s. Yet it runs 0-6 leases at a time and its whole process generation recorded
`OFFERED 39`.

What this readout answers
-------------------------
`shared_batch148.offer` refuses a token unless nine conditions hold and keeps NO counter for the
reason, so the runtime can say that few were offered but not why. This script reconstructs the gate
offline from the same fields it reads, on the population it is actually called with (a freshly quoted,
never-held token the 30-slot watch refused), and reports each condition separately plus the first
refusal -- the counter the module does not keep.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/free_rider_lane_readout.py [--minutes 60] [--max-age 45] [--json]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "memetrader_forward.sqlite3"
STATUS_KEY = "coverage145:status"

# The gate's own constants, read from src/memetrader/shared_batch148.py so the two cannot drift
# silently. MAX_ACTIVE_PER_CHAIN and MAX_WAITING_PER_CHAIN bound the lane; POOL_MAX_AGE mirrors the
# module's `0 <= observed_at - created/1000 <= 900`.
MAX_ACTIVE_PER_CHAIN = 2
MAX_WAITING_PER_CHAIN = 12
POOL_MAX_AGE_SECONDS = 900
FRESH_SECONDS = 30

# Evaluation order matches shared_batch148.offer lines 84-89.
CONDITIONS = (
    "pair_address_present",
    "chain_id_matches",
    "base_token_is_token",
    "pool_created_known",
    "pool_age_le_900s",
    "provider_dexscreener",
    "price_positive",
    "liquidity_ge_floor",
    "activity_3tx_or_200usd",
)


def parse(ts):
    if ts is None:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def percentile(values, q):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    return vals[min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))]


def gate_checks(*, provider, price, liquidity, volume, buys, sells, created_ms, observed_at,
                pair_address_present, chain_id_matches, base_token_is_token, floor=1000.0):
    """Reproduce `shared_batch148.offer`'s nine refusals on one snapshot.

    The three identity tests are passed in as booleans rather than re-derived here, so each one keeps
    its own line in the output: collapsing them into a single "valid" flag would hide which identity
    test refused and would make the per-condition table unimpeachable-looking but wrong.

    The provider test is a SUBSTRING match on the provider NAME, so it accepts
    `strategy-observer:dexscreener` and refuses `strategy-observer:geckoterminal` even when every
    data-quality condition passes.
    """
    count = (buys + sells) if (buys is not None and sells is not None) else None
    return [
        ("pair_address_present", bool(pair_address_present)),
        ("chain_id_matches", bool(chain_id_matches)),
        ("base_token_is_token", bool(base_token_is_token)),
        ("pool_created_known", created_ms is not None),
        ("pool_age_le_900s", created_ms is not None and observed_at is not None
         and 0 <= observed_at.timestamp() - created_ms / 1000.0 <= POOL_MAX_AGE_SECONDS),
        ("provider_dexscreener", "dexscreener" in str(provider or "").lower()),
        ("price_positive", price is not None and price > 0),
        ("liquidity_ge_floor", liquidity is not None and liquidity >= floor),
        ("activity_3tx_or_200usd", (count is not None and count >= 3)
         or (volume is not None and volume >= 200)),
    ]


def first_refusal(checks):
    """The first failing condition, by the gate's own evaluation order."""
    for name, ok in checks:
        if not ok:
            return name
    return None


def row_checks(row, *, floor=1000.0):
    """Build gate checks from one `token_snapshots` row (dict-like with the columns this readout reads)."""
    token_id = str(row["token_id"])
    chain, _, address = token_id.partition(":")
    try:
        raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
    except (ValueError, TypeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    pair = raw.get("pair") if isinstance(raw.get("pair"), dict) else raw
    if not isinstance(pair, dict):
        pair = {}
    base = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
    created = _num(pair.get("pairCreatedAt"))
    observed = parse(row["observed_at"])
    buys, sells = _num(row["buys_5m"]), _num(row["sells_5m"])

    # The gate reads a parsed pair object; these two identity tests are evaluated separately so a
    # reshaped payload shows up as the specific failure it is instead of a generic one.
    pair_ok = bool(pair.get("pairAddress"))
    chain_ok = pair.get("chainId") == chain
    base_ok = bool(base.get("address")) and str(base.get("address")).lower() == address.lower()
    checks = gate_checks(
        provider=row["provider"], price=_num(row["price_usd"]),
        liquidity=_num(row["liquidity_usd"]), volume=_num(row["volume_5m_usd"]),
        buys=buys, sells=sells, created_ms=created, observed_at=observed,
        pair_address_present=pair_ok, chain_id_matches=chain_ok, base_token_is_token=base_ok,
        floor=floor)
    return dict(checks)


def lane_summary(block):
    """Derive the free-rider lane's intake picture from its own counters."""
    counts = dict(block.get("counts") or {})
    alpha = dict(block.get("alpha149") or {})
    recent = list(block.get("recent") or [])
    tally = collections.Counter()
    for r in recent:
        for window, result in (r.get("windows") or {}).items():
            tally[f"{window}:{result}"] += 1
    return {
        "enabled": block.get("enabled"),
        "disabled_reason": block.get("disabled_reason"),
        "contract": block.get("request_contract"),
        "additional_http_batches": block.get("additional_http_batches"),
        "active": block.get("active"),
        "waiting": block.get("waiting"),
        "max_active": block.get("max_active"),
        "max_active_per_chain": block.get("max_active_per_chain"),
        "offered": counts.get("OFFERED"),
        "admitted": counts.get("ADMITTED"),
        "batch_extra_identities": counts.get("BATCH_EXTRA_IDENTITIES"),
        "eligible_batch": alpha.get("eligible_batch"),
        "no_spare": alpha.get("no_spare"),
        "selected_extra": alpha.get("selected_extra"),
        "finished_leases": len(recent),
        "window_results": dict(sorted(tally.items())),
        "idle": (block.get("active") or 0) == 0 and (block.get("waiting") or 0) == 0,
    }


def reconstruct(rows, *, ever_held, now, max_age_seconds=45.0, floor=1000.0):
    """Evaluate the gate on the call-time population: fresh quotes for never-held tokens.

    The population is bounded by quote age because the gate reads `now - observed_at <= 30 s`. Without
    that bound the set is dominated by tokens last quoted half an hour ago and the pass rate is
    inflated -- the error the first version of this measurement made (quote age p50 1,888 s).
    """
    newest = {}
    for row in rows:
        tid = str(row["token_id"])
        if tid in ever_held:
            continue
        newest[tid] = row
    ages = {t: (now - parse(r["observed_at"])).total_seconds() for t, r in newest.items()
            if parse(r["observed_at"]) is not None}
    fresh = {t: r for t, r in newest.items() if ages.get(t, 1e9) <= max_age_seconds}

    per_condition = collections.Counter()
    first_failures = collections.Counter()
    accepted, near_miss = [], []
    for tid, row in fresh.items():
        checks = row_checks(row, floor=floor)
        for name, ok in checks.items():
            if ok:
                per_condition[name] += 1
        bad = first_refusal(list(checks.items()))
        if bad is None:
            accepted.append(tid)
        else:
            first_failures[bad] += 1
            if [n for n, ok in checks.items() if not ok] == ["provider_dexscreener"]:
                near_miss.append(tid)
    total = len(fresh)
    return {
        "never_held_seen": len(newest),
        "quote_age_p50_seconds": percentile(list(ages.values()), 0.5),
        "population": total,
        "per_condition": dict(per_condition),
        "first_refusal": dict(first_failures),
        "accepted": len(accepted),
        "provider_only_near_miss": len(near_miss),
        "pass_rate": (len(accepted) / total) if total else None,
        "pass_rate_without_provider_condition": ((len(accepted) + len(near_miss)) / total)
        if total else None,
    }


def hourly_opportunities(rows, *, ever_held, floor=1000.0):
    """Per-token check of the newest quote in the window: how many were valid but for the provider name?

    This is the RATE question and it uses a different population from `reconstruct` on purpose. The
    gate's call-time clock (`now - observed_at <= 30 s`) cannot be replayed, but every one of these
    quotes was fresh when it was FETCHED, so evaluating each token on its own newest row counts the
    tokens that were genuine near-misses at their own moment. `reconstruct` answers the other question:
    what share of the currently fresh population would pass.
    """
    newest = {}
    for row in rows:
        tid = str(row["token_id"])
        if tid not in ever_held:
            newest[tid] = row
    accepted, near_miss, refused = 0, 0, 0
    first_refusals = collections.Counter()
    for row in newest.values():
        checks = row_checks(row, floor=floor)
        failed = [n for n, ok in checks.items() if not ok]
        if not failed:
            accepted += 1
        elif failed == ["provider_dexscreener"]:
            near_miss += 1
        else:
            refused += 1
        bad = first_refusal(list(checks.items()))
        if bad is not None:
            first_refusals[bad] += 1
    return {"tokens": len(newest), "accepted": accepted, "provider_only_near_miss": near_miss,
            "refused_elsewhere": refused, "first_refusal": dict(first_refusals)}


def fetch(db=DB, *, minutes=60.0, max_age_seconds=45.0, floor=1000.0):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    now = parse(conn.execute("select max(observed_at) m from token_snapshots").fetchone()["m"])
    if now is None:
        return None, None, None
    cut = now - timedelta(minutes=minutes)
    ever_held = {str(r["token_id"]) for r in conn.execute(
        "select distinct token_id from chain_meme_trader_positions")}
    rows = list(conn.execute(
        "select token_id, observed_at, provider, price_usd, liquidity_usd, volume_5m_usd, "
        "buys_5m, sells_5m, raw_json from token_snapshots where observed_at >= ? "
        "order by observed_at", (iso(cut),)))
    status_row = conn.execute("select value_json from kv where key=?", (STATUS_KEY,)).fetchone()
    status = json.loads(status_row["value_json"]) if status_row else {}
    recon = reconstruct(rows, ever_held=ever_held, now=now, max_age_seconds=max_age_seconds,
                        floor=floor)
    hourly = hourly_opportunities(rows, ever_held=ever_held, floor=floor)
    return recon, status, hourly


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--max-age", type=float, default=45.0,
                    help="freshness bound (s) defining the gate's call-time population; gate limit 30")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    recon, status, hourly = fetch(minutes=args.minutes, max_age_seconds=args.max_age)
    if recon is None:
        print("token_snapshots is empty")
        return 1
    block = (status or {}).get("shared_batch148") or {}
    lane = lane_summary(block)

    if args.json:
        print(json.dumps({"lane": lane, "gate": recon, "window": hourly},
                         indent=2, default=str, sort_keys=True))
        return 0

    print("=" * 92)
    print("FREE-RIDER OBSERVATION LANE  (shared_batch148)")
    print("=" * 92)
    print(f"enabled {lane['enabled']}   contract {lane['contract']!r}")
    print(f"additional HTTP batches {lane['additional_http_batches']}  <- zero by contract")
    print(f"active {lane['active']}  waiting {lane['waiting']}  "
          f"caps: {lane['max_active_per_chain']}/chain (module constant), "
          f"waiting {MAX_WAITING_PER_CHAIN}/chain")
    if lane["idle"]:
        print("   *** LANE IS IDLE: nothing active and nothing waiting ***")
    print()
    print("its own funnel (whole process generation):")
    for key in ("offered", "admitted", "batch_extra_identities", "eligible_batch", "no_spare",
                "selected_extra"):
        print(f"   {key:<26} {lane[key]}")
    print(f"   finished leases recorded   {lane['finished_leases']}")
    print(f"   their window results       {lane['window_results']}")
    print()
    print("WHAT THE LANE'S OUTPUT LOOKS LIKE (finished leases only, so a survivor share):")
    recent = list(block.get("recent") or [])
    f2 = [r.get("frame2_delay_seconds") for r in recent]
    f3 = [r.get("frame3_delay_seconds") for r in recent]
    fr = [r.get("frames") for r in recent]
    for label, vals in (("frame2_delay_seconds", f2), ("frame3_delay_seconds", f3), ("frames", fr)):
        have = [v for v in vals if v is not None]
        if have:
            print(f"   {label:<22} n={len(have):>3}  p50 {percentile(have,.5):>7.2f}  "
                  f"max {max(have):>7.2f}")

    print()
    print("=" * 92)
    print("WHY SO FEW ENTER: the gate reconstructed offline")
    print("=" * 92)
    print(f"never-held tokens with a snapshot in {args.minutes:.0f} min : {recon['never_held_seen']:,}")
    print(f"   quote age p50 of that set        : "
          f"{(recon['quote_age_p50_seconds'] or 0):,.0f} s")
    print(f"   CALL-TIME population (<= {args.max_age:.0f} s)   : {recon['population']:,}")
    print()
    print("per-condition pass rate on the call-time population:")
    for name in CONDITIONS:
        n = recon["per_condition"].get(name, 0)
        tot = max(1, recon["population"])
        print(f"   {name:<26} {n:>5}/{recon['population']:<5} ({100.0*n/tot:5.1f}%)")
    print()
    print(f"PASS ALL NINE                      : {recon['accepted']} "
          f"({100.0*(recon['pass_rate'] or 0):.2f}%)")
    print(f"refused ONLY by provider name      : {recon['provider_only_near_miss']}")
    print(f"=> pass rate without that one test : "
          f"{100.0*(recon['pass_rate_without_provider_condition'] or 0):.2f}%")
    print()
    print("WHICH CONDITION REFUSES FIRST (the counter the module does not keep):")
    for name, n in sorted(recon["first_refusal"].items(), key=lambda kv: -kv[1]):
        print(f"   {name:<28} {n:>5}")
    print()
    print(f"RATE OVER {args.minutes:.0f} MIN (newest quote per token, evaluated at its own moment):")
    print(f"   never-held tokens seen            : {hourly['tokens']:,}")
    print(f"   passed every condition            : {hourly['accepted']:,}")
    print(f"   refused ONLY by the provider name : {hourly['provider_only_near_miss']:,}")
    print(f"   refused on something else         : {hourly['refused_elsewhere']:,}")
    if hourly["accepted"]:
        print(f"   => the provider test alone removes "
              f"{hourly['provider_only_near_miss']/hourly['accepted']:.0f}x the lane's current intake")
    elif hourly["provider_only_near_miss"]:
        print("   => the lane admitted NOTHING in this window while near-misses existed")
    print("""
   READING RULES
     * The provider test is a substring match on the provider NAME. `strategy-observer:dexscreener`
       passes it and `strategy-observer:geckoterminal` does not, although GeckoTerminal pools are
       normalized into the same pair shape (collectors.py:2227) and carry the same pairAddress /
       chainId / pairCreatedAt / baseToken fields this gate tests.
     * The near-miss figure is the SIZE of what that one test removes, not a recommendation to drop a
       provenance rule.
     * `now - observed_at <= 30 s` is a call-time clock and is not replayed here; the population is
       bounded by --max-age instead, so this is an UPPER bound on the true pass rate.
     * More observed tokens is more EVIDENCE, not more profit: round 85 measured 6 profitable of 94.
   NOTHING IS CHANGED by this readout.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
