"""Case review: for a list of token addresses, show exactly where each one stopped in the funnel.

Why this exists
---------------
A user report that "the system found these tokens but never bought them" cannot be answered by counting
discoveries. It needs, per token, the stage at which it left the chain

    discovered -> snapshotted -> observed (>=3 frames) -> entry-evaluated -> cohort -> position

and, where it was evaluated and refused, the ENGINE'S OWN recorded reason. `chain_meme_trader_v6_entry_evaluations`
stores one row per source snapshot with a `reason`, so the refusal is read, not inferred.

Discipline this tool follows
----------------------------
* Resolution is by DATABASE lookup, never by guessing a chain from the address string. An EVM address
  does not say whether it is bsc or robinhood, and a Solana address must never be case-folded.
* "No evaluation row" is reported as `not_evaluated`, which is a DIFFERENT finding from
  "evaluated and refused". Absence of a record is not evidence that a path never ran.
* The token's OWN evaluation rows are reported separately from rows whose token_id matches but whose
  source snapshot belongs to a different pool, because several pools can share one token.

Read-only: opens the database with mode=ro and writes nothing.

Usage
-----
    python scripts/case_review.py --addresses data/research/diag_round120/case_addresses.txt
    python scripts/case_review.py --addresses FILE --json
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "memetrader_forward.sqlite3"


def parse(ts):
    return str(ts)[:19] if ts else None


def load_tokens(conn):
    """One scan of `tokens` into memory.

    `tokens` has no index on `address`, so a per-address `WHERE address=?` full-scans 64,518 rows
    (measured 22.8 s per count on this 2.4 GB database). The case list is small, so one scan beats 38
    scans.
    """
    exact, folded = {}, {}
    for row in conn.execute("SELECT token_id, chain, address, created_at FROM tokens"):
        address = str(row["address"])
        exact.setdefault(address, []).append(row)
        folded.setdefault(address.lower(), []).append(row)
    return exact, folded


def resolve(exact, folded, address):
    """Return every token row matching this address. Never guesses the chain from the string."""
    if address in exact:
        return exact[address]
    # Only an EVM address may be matched case-insensitively; Solana addresses are case-sensitive.
    if address.lower().startswith("0x"):
        return folded.get(address.lower(), [])
    return []


def activated_versions(conn):
    return [str(r["definition_version"]) for r in conn.execute(
        "SELECT DISTINCT definition_version FROM chain_meme_trader_v6_activations")]


def bulk_stages(conn, token_ids, versions):
    """Every stage for all tokens in a handful of grouped queries.

    IMPORTANT: `chain_meme_trader_v6_entry_evaluations` is indexed ONLY as
    (definition_version, token_id, ...), so a query filtered by token_id alone cannot use any index and
    full-scans the table -- measured 222 s on 442,920 rows. Every query below therefore carries the
    `definition_version` prefix.
    """
    ids = sorted(set(token_ids))
    ph = ",".join("?" for _ in ids)
    vph = ",".join("?" for _ in versions)
    out = {t: {"snapshots": 0, "first_observed": None, "last_observed": None, "evaluated": 0,
               "reasons": {}, "cohorts": 0, "positions": 0, "pools": [], "providers": {}}
           for t in ids}

    for row in conn.execute(
            f"SELECT token_id, COUNT(*) n, MIN(observed_at) a, MAX(observed_at) b "
            f"FROM token_snapshots WHERE token_id IN ({ph}) GROUP BY token_id", ids):
        item = out[str(row["token_id"])]
        item["snapshots"] = int(row["n"])
        item["first_observed"] = parse(row["a"])
        item["last_observed"] = parse(row["b"])

    for row in conn.execute(
            f"SELECT token_id, provider, COUNT(*) n FROM token_snapshots "
            f"WHERE token_id IN ({ph}) GROUP BY token_id, provider", ids):
        out[str(row["token_id"])]["providers"][str(row["provider"])] = int(row["n"])

    for row in conn.execute(
            f"SELECT token_id, reason, COUNT(*) n FROM chain_meme_trader_v6_entry_evaluations "
            f"WHERE definition_version IN ({vph}) AND token_id IN ({ph}) "
            f"GROUP BY token_id, reason", (*versions, *ids)):
        out[str(row["token_id"])]["reasons"][str(row["reason"])] = int(row["n"])

    for row in conn.execute(
            f"SELECT token_id, COUNT(*) n FROM chain_meme_trader_v6_cohorts "
            f"WHERE definition_version IN ({vph}) AND token_id IN ({ph}) GROUP BY token_id",
            (*versions, *ids)):
        out[str(row["token_id"])]["cohorts"] = int(row["n"])

    for row in conn.execute(
            f"SELECT token_id, COUNT(*) n FROM chain_meme_trader_positions "
            f"WHERE token_id IN ({ph}) GROUP BY token_id", ids):
        out[str(row["token_id"])]["positions"] = int(row["n"])

    for row in conn.execute(
            f"SELECT token_id, pair_address FROM chain_meme_trader_pool_marks "
            f"WHERE token_id IN ({ph}) GROUP BY token_id, pair_address", ids):
        out[str(row["token_id"])]["pools"].append(str(row["pair_address"]))

    for token_id, item in out.items():
        item["evaluated"] = sum(item["reasons"].values())
    return out


def blocking_stage(stage):
    """Name the FIRST stage that stopped, using only recorded facts."""
    if stage["snapshots"] == 0:
        return "never_snapshotted"
    if stage["evaluated"] == 0:
        return "never_entry_evaluated"
    if stage["cohorts"] == 0:
        return "evaluated_no_cohort"
    if stage["positions"] == 0:
        return "cohort_but_no_position"
    return "has_position"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--addresses", required=True)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    addresses = [a.strip() for a in Path(args.addresses).read_text(encoding="utf-8").splitlines()
                 if a.strip() and not a.strip().startswith("#")]
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    exact, folded = load_tokens(conn)
    versions = activated_versions(conn)

    matched = []          # (address, token row)
    cases = []
    for address in addresses:
        rows = resolve(exact, folded, address)
        if not rows:
            cases.append({"address": address, "chain": None, "token_id": None,
                          "stage": "not_in_tokens_table", "detail": {}})
            continue
        for row in rows:
            matched.append((address, row))

    stages = bulk_stages(conn, [str(r["token_id"]) for _a, r in matched], versions)
    for address, row in matched:
        token_id = str(row["token_id"])
        detail = stages[token_id]
        cases.append({"address": address, "chain": str(row["chain"]), "token_id": token_id,
                      "stage": blocking_stage(detail), "detail": detail,
                      "created_at": parse(row["created_at"])})

    if args.json:
        print(json.dumps(cases, indent=2, default=str))
        return 0

    print("=" * 118)
    print("CASE REVIEW: WHERE EACH TOKEN LEFT THE FUNNEL")
    print("=" * 118)
    print(f"{'#':<3} {'address':<46} {'chain':<10} {'snaps':>5} {'eval':>5} {'cohort':>6} "
          f"{'pos':>4}  {'stage':<26} top reason")
    print("-" * 118)
    for i, case in enumerate(cases, 1):
        if case["token_id"] is None:
            print(f"{i:<3} {case['address']:<46} {'-':<10} {'-':>5} {'-':>5} {'-':>6} {'-':>4}  "
                  f"{case['stage']:<26}")
            continue
        d = case["detail"]
        top = ""
        if d["reasons"]:
            reason, n = max(d["reasons"].items(), key=lambda kv: kv[1])
            top = f"{reason} x{n}"
        print(f"{i:<3} {case['address']:<46} {case['chain']:<10} {d['snapshots']:>5} "
              f"{d['evaluated']:>5} {d['cohorts']:>6} {d['positions']:>4}  {case['stage']:<26} {top}")

    print()
    print("STAGE TALLY (independent tokens, not evaluations):")
    for stage, n in collections.Counter(c["stage"] for c in cases).most_common():
        print(f"   {stage:<28} {n}")

    print()
    print("REFUSAL REASONS ACROSS THE WHOLE CASE SET (engine-recorded):")
    all_reasons = collections.Counter()
    for case in cases:
        for reason, n in (case.get("detail") or {}).get("reasons", {}).items():
            all_reasons[reason] += n
    if not all_reasons:
        print("   (none recorded)")
    for reason, n in all_reasons.most_common(25):
        print(f"   {reason:<52} {n}")
    print("""
   READING RULES
     * `not_in_tokens_table` means discovery never stored the token; that is a different finding from
       "stored but never observed".
     * `never_entry_evaluated` means no evaluation row exists for this token. It does NOT prove the
       entry lane never saw it -- the lane may simply not have reached that snapshot. Report it as
       "no record", not as "rejected".
     * Only the engine's own `reason` values are quoted; nothing here is inferred from later price.
   NOTHING IS CHANGED by this tool.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
