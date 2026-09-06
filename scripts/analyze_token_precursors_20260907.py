"""Frozen point-in-time token precursor review; this is not a backtest.

Research contract (frozen before the first formal calculation on 2026-09-07):

* t0 is the exact recorded baseline snapshot for ``token_universe_forward`` and
  the exact source snapshot for ``chain_meme_fixed_outcome``.  Features come
  only from that immutable snapshot, including its then-visible rolling fields.
* The primary label is the fixed 60-minute target.  The 0/15/60/240-minute
  chain outcomes and 15/60/240-minute universe outcomes remain coverage rows.
* Same-pair return >= +100% is SURGE; (-20%, +100%) is ORDINARY;
  (-80%, -20%] is FAILURE; <= -80% is CRASH.  Missing baseline, missing or
  pending outcome, invalid chronology, and incomparable route are separate.
* The broad universe feature sample is the 12,000 smallest unsigned SHA-256
  ranks of ``definition_version|cohort_id|token_id`` at a frozen ID frontier.
  This is deterministic simple random sampling without replacement, not winner
  sampling.  The much smaller chain outcome frame is kept in full.
* Frozen strata are chain, UTC 12-hour t0 block, pool age (<15m, 15-60m,
  1-6h, 6-24h, >=24h, unknown), and t0 liquidity (<1k, 1-5k, 5-25k,
  25-100k, >=100k, unknown).

SQLite is opened URI ``mode=ro`` and query-only.  Every statement has a
two-second progress-handler deadline.  Large logical reads use bounded ID/IN
chunks; each cursor is fetched and closed in autocommit mode before the next
chunk, so no read transaction is held across chunks.  ``token_snapshots`` is
never scanned: only exact primary-key IDs already recorded by cohort/baseline
tables are fetched.  No maximum/minimum path-excursion metric is calculated and
no Store/runtime code loads.

Run once:
    .venv/Scripts/python.exe scripts/analyze_token_precursors_20260907.py
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import heapq
import json
import math
from pathlib import Path
import sqlite3
import statistics
import time


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/memetrader_forward_20260830_r6.sqlite3"
OUT = ROOT / "data/research/20260907"
POSITIONS = OUT / "positions_evidence.csv"
STATEMENT_SECONDS = 2.0
ID_CHUNK = 2_000
IN_CHUNK = 400
UNIVERSE_SAMPLE_N = 12_000
PRIMARY_HORIZON_MINUTES = 60
SURGE_RETURN = 1.0
FAILURE_RETURN = -0.20
CRASH_RETURN = -0.80
FEATURES = (
    "log10_liquidity_usd",
    "log10_market_cap_usd",
    "liquidity_to_market_cap",
    "log10_volume_5m_usd",
    "volume_5m_to_liquidity",
    "volume_5m_annualized_share_of_h1",
    "buy_ratio_5m",
    "transactions_5m",
    "price_change_5m_pct",
    "price_change_1h_pct",
    "pool_age_minutes",
    "snapshot_recording_delay_seconds",
)


def parse_dt(value):
    if value in (None, ""):
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def iso_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def first_number(*values):
    for value in values:
        result = finite(value)
        if result is not None:
            return result
    return None


def nested(obj, *keys):
    value = obj
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


class ReadOnlyDb:
    def __init__(self, path):
        self.connection = sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=2, isolation_level=None
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only=ON")
        self.connection.execute("PRAGMA busy_timeout=2000")
        self.deadline = 0.0
        self.query_log = []
        self.connection.set_progress_handler(
            lambda: int(time.monotonic() > self.deadline), 10_000
        )

    def query(self, sql, params=()):
        began = time.monotonic()
        self.deadline = began + STATEMENT_SECONDS
        cursor = None
        try:
            cursor = self.connection.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if cursor is not None:
                cursor.close()
            self.query_log.append({
                "seconds": time.monotonic() - began,
                "sql_prefix": " ".join(sql.split())[:160],
            })

    def close(self):
        self.connection.close()


def batches(values, size=IN_CHUNK):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def frontier(db, table, column="id"):
    return int(db.query(f'SELECT max("{column}") AS x FROM "{table}"')[0]["x"] or 0)


def paged(db, table, columns, maximum, key="id"):
    last = 0
    while last < maximum:
        rows = db.query(
            f'SELECT {columns} FROM "{table}" '
            f'WHERE "{key}">? AND "{key}"<=? ORDER BY "{key}" LIMIT ?',
            (last, maximum, ID_CHUNK),
        )
        if not rows:
            break
        yield from rows
        last = int(rows[-1][key])


def select_universe_sample(db, maximum):
    heap = []
    version = "token-universe-forward-outcomes/v1"
    for row in paged(
        db,
        "token_universe_forward_cohorts",
        "id,definition_version,token_id,chain,provider,surface,discovery_role,"
        "discovery_observed_at,discovery_recorded_at,baseline_deadline_at",
        maximum,
    ):
        key = f'{row["definition_version"]}|{row["id"]}|{row["token_id"]}'
        rank = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest(), "big")
        item = (-rank, int(row["id"]), row)
        if len(heap) < UNIVERSE_SAMPLE_N:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    sample = [item[2] for item in heap]
    sample.sort(key=lambda row: int(row["id"]))
    return sample, version


def lookup_universe_evidence(db, ids, outcome_frontier, quality_frontier):
    result = {}
    for group in batches(ids):
        marks = ",".join("?" for _ in group)
        sql = f"""
            SELECT c.id AS cohort_id,b.status AS baseline_status,b.snapshot_id AS baseline_snapshot_id,
                   b.observed_at AS baseline_observed_at,b.ingested_at AS baseline_ingested_at,
                   b.recorded_at AS baseline_recorded_at,b.evaluated_at AS baseline_evaluated_at,
                   o.id AS outcome_id,o.status AS outcome_status,o.target_at,o.outcome_snapshot_id,
                   o.raw_return,o.evaluated_at AS outcome_evaluated_at,
                   q.id AS quality_id,q.quality_status,q.route_class,q.raw_fixed_horizon_return,
                   q.baseline_pair_address,q.target_pair_address,q.assessed_at AS quality_assessed_at
            FROM token_universe_forward_cohorts c
            LEFT JOIN token_universe_forward_baselines b ON b.cohort_id=c.id
            LEFT JOIN token_universe_forward_outcomes o
              ON o.cohort_id=c.id AND o.horizon_minutes=? AND o.id<=?
            LEFT JOIN token_universe_outcome_quality q ON q.outcome_id=o.id AND q.id<=?
            WHERE c.id IN ({marks})
        """
        params = [PRIMARY_HORIZON_MINUTES, outcome_frontier, quality_frontier, *group]
        for row in db.query(sql, params):
            result[int(row["cohort_id"])] = row
    return result


def load_chain_frame(db, cohort_frontier, outcome_frontier):
    cohorts = {}
    for row in paged(
        db,
        "chain_meme_trader_v6_cohorts",
        "id,definition_version,token_id,entry_family,source_snapshot_id,pair_address,decided_at",
        cohort_frontier,
    ):
        cohorts[int(row["id"])] = row
    outcomes = defaultdict(dict)
    for row in paged(
        db,
        "chain_meme_universe_outcomes",
        "id,observer_version,source_cohort_id,horizon_minutes,target_at,status,"
        "outcome_snapshot_id,outcome_observed_at,outcome_ingested_at,outcome_recorded_at,"
        "outcome_price_usd,outcome_liquidity_usd,reason,evaluated_at",
        outcome_frontier,
    ):
        horizon = int(row["horizon_minutes"])
        if horizon in (0, 15, 60, 240):
            outcomes[int(row["source_cohort_id"])][horizon] = row
    frame = []
    for cohort_id, by_horizon in outcomes.items():
        if 0 in by_horizon and cohort_id in cohorts:
            row = dict(cohorts[cohort_id])
            row["outcomes"] = by_horizon
            frame.append(row)
    return frame


def load_snapshots(db, snapshot_ids, snapshot_frontier):
    output = {}
    ids = sorted({int(value) for value in snapshot_ids if value and int(value) <= snapshot_frontier})
    for group in batches(ids):
        marks = ",".join("?" for _ in group)
        rows = db.query(
            "SELECT id,token_id,observed_at,ingested_at,recorded_at,provider,price_usd,"
            "liquidity_usd,market_cap_usd,volume_5m_usd,buys_5m,sells_5m,raw_json "
            f"FROM token_snapshots WHERE id IN ({marks})",
            group,
        )
        output.update((int(row["id"]), row) for row in rows)
    return output


def load_funnel(db, ids, transition_frontier):
    stages = defaultdict(set)
    for group in batches(ids):
        marks = ",".join("?" for _ in group)
        rows = db.query(
            "SELECT cohort_id,stage FROM token_universe_funnel_transitions "
            f"WHERE cohort_id IN ({marks}) AND id<=? GROUP BY cohort_id,stage",
            [*group, transition_frontier],
        )
        for row in rows:
            stages[int(row["cohort_id"])].add(row["stage"])
    return stages


def load_position_index():
    exact = Counter()
    token = Counter()
    distinct_entries = set()
    row_count = 0
    with POSITIONS.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            row_count += 1
            token_id = row.get("token_id") or ""
            snapshot_id = int(row["entry_snapshot_id"]) if row.get("entry_snapshot_id") else None
            cohort_id = int(row["shadow_cohort_id"]) if row.get("shadow_cohort_id") else None
            token[token_id] += 1
            if snapshot_id is not None:
                exact[(token_id, snapshot_id)] += 1
                distinct_entries.add((token_id, cohort_id, snapshot_id))
    return exact, token, distinct_entries, row_count


def raw_pair(snapshot):
    try:
        raw = json.loads(snapshot.get("raw_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}, False
    pair = raw.get("pair") if isinstance(raw, dict) else None
    return (pair if isinstance(pair, dict) else {}), bool(pair)


def snapshot_features(snapshot, t0):
    pair, raw_ok = raw_pair(snapshot)
    liquidity = first_number(snapshot.get("liquidity_usd"), nested(pair, "liquidity", "usd"))
    market_cap = first_number(snapshot.get("market_cap_usd"), pair.get("marketCap"), pair.get("fdv"))
    volume_5m = first_number(snapshot.get("volume_5m_usd"), nested(pair, "volume", "m5"))
    volume_1h = first_number(nested(pair, "volume", "h1"))
    buys = first_number(snapshot.get("buys_5m"), nested(pair, "txns", "m5", "buys"))
    sells = first_number(snapshot.get("sells_5m"), nested(pair, "txns", "m5", "sells"))
    transactions = buys + sells if buys is not None and sells is not None else None
    created_ms = first_number(pair.get("pairCreatedAt"))
    created_at = datetime.fromtimestamp(created_ms / 1000, timezone.utc) if created_ms else None
    observed_at = parse_dt(snapshot.get("observed_at"))
    recorded_at = parse_dt(snapshot.get("recorded_at"))
    pool_age = (observed_at - created_at).total_seconds() / 60 if observed_at and created_at else None
    delay = (recorded_at - observed_at).total_seconds() if observed_at and recorded_at else None
    values = {
        "log10_liquidity_usd": math.log10(liquidity) if liquidity and liquidity > 0 else None,
        "log10_market_cap_usd": math.log10(market_cap) if market_cap and market_cap > 0 else None,
        "liquidity_to_market_cap": liquidity / market_cap if liquidity is not None and market_cap and market_cap > 0 else None,
        "log10_volume_5m_usd": math.log10(volume_5m) if volume_5m and volume_5m > 0 else None,
        "volume_5m_to_liquidity": volume_5m / liquidity if volume_5m is not None and liquidity and liquidity > 0 else None,
        "volume_5m_annualized_share_of_h1": volume_5m * 12 / volume_1h if volume_5m is not None and volume_1h and volume_1h > 0 else None,
        "buy_ratio_5m": buys / transactions if transactions and transactions > 0 else None,
        "transactions_5m": transactions,
        "price_change_5m_pct": first_number(nested(pair, "priceChange", "m5")),
        "price_change_1h_pct": first_number(nested(pair, "priceChange", "h1")),
        "pool_age_minutes": pool_age if pool_age is None or pool_age >= 0 else None,
        "snapshot_recording_delay_seconds": delay if delay is None or delay >= 0 else None,
    }
    return values, {
        "liquidity_usd": liquidity,
        "market_cap_usd": market_cap,
        "volume_5m_usd": volume_5m,
        "buys_5m": buys,
        "sells_5m": sells,
        "raw_pair_available": raw_ok,
        "snapshot_observed_at": snapshot.get("observed_at"),
        "snapshot_ingested_at": snapshot.get("ingested_at"),
        "snapshot_recorded_at": snapshot.get("recorded_at"),
        "snapshot_provider": snapshot.get("provider"),
    }


def label_return(value):
    value = finite(value)
    if value is None:
        return "RETURN_MISSING"
    if value >= SURGE_RETURN:
        return "SURGE"
    if value <= CRASH_RETURN:
        return "CRASH"
    if value <= FAILURE_RETURN:
        return "FAILURE"
    return "ORDINARY"


def age_bin(value):
    if value is None:
        return "unknown"
    if value < 15:
        return "lt15m"
    if value < 60:
        return "15m_to_1h"
    if value < 360:
        return "1h_to_6h"
    if value < 1440:
        return "6h_to_24h"
    return "ge24h"


def liquidity_bin(value):
    if value is None:
        return "unknown"
    if value < 1_000:
        return "lt1k"
    if value < 5_000:
        return "1k_to_5k"
    if value < 25_000:
        return "5k_to_25k"
    if value < 100_000:
        return "25k_to_100k"
    return "ge100k"


def time_bin(value):
    stamp = parse_dt(value)
    return f"{stamp:%Y-%m-%d}_{'00-11' if stamp.hour < 12 else '12-23'}" if stamp else "unknown"


def chronology_status(feature_snapshot, t0, target_at, outcome_evaluated_at=None):
    target = parse_dt(target_at)
    t0_dt = parse_dt(t0)
    times = [parse_dt(feature_snapshot.get(name)) for name in ("observed_at", "ingested_at", "recorded_at")]
    if not target or not t0_dt or any(value is None for value in times):
        return "TIME_ORDER_UNKNOWN"
    if any(value > t0_dt for value in times) or t0_dt >= target:
        return "TIME_ORDER_INVALID"
    # Outcome evaluation may occur later than target; it is a label, never a feature.
    return "VALID"


def build_rows(universe, universe_evidence, chain_frame, snapshots, funnel, exact_positions, token_positions):
    rows = []
    for cohort in universe:
        cohort_id = int(cohort["id"])
        evidence = universe_evidence.get(cohort_id, {})
        snapshot_id = evidence.get("baseline_snapshot_id")
        snapshot = snapshots.get(int(snapshot_id)) if snapshot_id else None
        t0 = evidence.get("baseline_evaluated_at") or evidence.get("baseline_recorded_at")
        outcome_status = evidence.get("outcome_status") or "NOT_REGISTERED_OR_UNMATURED"
        chronology = "NO_BASELINE"
        outcome_class = (
            "BASELINE_MISSING" if evidence.get("baseline_status") == "missing"
            else "BASELINE_NOT_REGISTERED"
        )
        return_value = None
        if snapshot is not None:
            chronology = chronology_status(snapshot, t0, evidence.get("target_at"), evidence.get("outcome_evaluated_at"))
            if outcome_status == "missing":
                outcome_class = "OUTCOME_MISSING"
            elif outcome_status != "observed":
                outcome_class = "NOT_REGISTERED_OR_UNMATURED"
            elif chronology != "VALID":
                outcome_class = chronology
            elif not evidence.get("baseline_pair_address") or evidence.get("baseline_pair_address") != evidence.get("target_pair_address"):
                outcome_class = "ROUTE_INCOMPARABLE_OR_UNASSESSED"
            else:
                # raw_fixed_horizon_return is the exact target mark.  Do not use
                # quality.same_pair_return: that field is the maximum same-pair
                # path return and would silently turn this into a
                # path-maximum-return analysis rather than a fixed-target review.
                return_value = finite(evidence.get("raw_fixed_horizon_return"))
                outcome_class = label_return(return_value)
        features, context = snapshot_features(snapshot, t0) if snapshot else ({name: None for name in FEATURES}, {
            "liquidity_usd": None, "market_cap_usd": None, "volume_5m_usd": None,
            "buys_5m": None, "sells_5m": None, "raw_pair_available": False,
            "snapshot_observed_at": None, "snapshot_ingested_at": None,
            "snapshot_recorded_at": None, "snapshot_provider": None,
        })
        stages = funnel.get(cohort_id, set())
        row = {
            "frame": "token_universe_forward",
            "cohort_id": cohort_id,
            "observer_version": cohort["definition_version"],
            "token_id": cohort["token_id"],
            "chain": str(cohort["chain"]).lower(),
            "t0": t0,
            "snapshot_id": snapshot_id,
            "baseline_status": evidence.get("baseline_status") or "not_registered",
            "h60_status": outcome_status,
            "chronology_status": chronology,
            "quality_status": evidence.get("quality_status") or "not_assessed",
            "route_class": evidence.get("route_class") or "not_assessed",
            "h60_same_pair_return": return_value,
            "outcome_class": outcome_class,
            "exact_position_rows": exact_positions.get((cohort["token_id"], int(snapshot_id)), 0) if snapshot_id else 0,
            "same_token_position_rows": token_positions.get(cohort["token_id"], 0),
            "candidate_evaluation_ever": int("candidate_evaluation" in stages),
            "decision_final_ever": int("decision_final" in stages),
            "paper_fill_ever": int("paper_fill" in stages),
            "funnel_stage_count_ever": len(stages),
            **context,
            **features,
        }
        row["pool_age_bin"] = age_bin(row["pool_age_minutes"])
        row["liquidity_bin"] = liquidity_bin(row["liquidity_usd"])
        row["utc_12h_bin"] = time_bin(t0)
        row["stratum"] = "|".join((row["chain"], row["utc_12h_bin"], row["pool_age_bin"], row["liquidity_bin"]))
        rows.append(row)

    for cohort in chain_frame:
        outcomes = cohort["outcomes"]
        h0 = outcomes[0]
        h60 = outcomes.get(60)
        snapshot_id = int(cohort["source_snapshot_id"])
        snapshot = snapshots.get(snapshot_id)
        t0 = cohort["decided_at"]
        outcome_status = h60["status"] if h60 else "NOT_REGISTERED"
        chronology = "NO_SOURCE_SNAPSHOT"
        outcome_class = "SOURCE_SNAPSHOT_MISSING"
        return_value = None
        if snapshot:
            chronology = chronology_status(snapshot, t0, h60.get("target_at") if h60 else None)
            if not h60 or outcome_status == "PENDING":
                outcome_class = "NOT_REGISTERED_OR_UNMATURED"
            elif outcome_status == "UNKNOWN":
                outcome_class = "OUTCOME_MISSING"
            elif h0["status"] != "OBSERVED":
                outcome_class = "H0_MISSING"
            elif chronology != "VALID":
                outcome_class = chronology
            else:
                baseline_price = finite(h0.get("outcome_price_usd"))
                target_price = finite(h60.get("outcome_price_usd"))
                if baseline_price and baseline_price > 0 and target_price is not None:
                    return_value = target_price / baseline_price - 1
                outcome_class = label_return(return_value)
        features, context = snapshot_features(snapshot, t0) if snapshot else ({name: None for name in FEATURES}, {
            "liquidity_usd": None, "market_cap_usd": None, "volume_5m_usd": None,
            "buys_5m": None, "sells_5m": None, "raw_pair_available": False,
            "snapshot_observed_at": None, "snapshot_ingested_at": None,
            "snapshot_recorded_at": None, "snapshot_provider": None,
        })
        row = {
            "frame": "chain_meme_fixed_outcome",
            "cohort_id": cohort["id"],
            "observer_version": h0["observer_version"],
            "token_id": cohort["token_id"],
            "chain": str(cohort["token_id"]).split(":", 1)[0].lower(),
            "t0": t0,
            "snapshot_id": snapshot_id,
            "baseline_status": h0["status"],
            "h60_status": outcome_status,
            "chronology_status": chronology,
            "quality_status": "same_pair_by_observer_contract",
            "route_class": "same_pair_by_observer_contract",
            "h60_same_pair_return": return_value,
            "outcome_class": outcome_class,
            "exact_position_rows": exact_positions.get((cohort["token_id"], snapshot_id), 0),
            "same_token_position_rows": token_positions.get(cohort["token_id"], 0),
            "candidate_evaluation_ever": "",
            "decision_final_ever": "",
            "paper_fill_ever": "",
            "funnel_stage_count_ever": "",
            **context,
            **features,
        }
        row["pool_age_bin"] = age_bin(row["pool_age_minutes"])
        row["liquidity_bin"] = liquidity_bin(row["liquidity_usd"])
        row["utc_12h_bin"] = time_bin(t0)
        row["stratum"] = "|".join((row["chain"], row["utc_12h_bin"], row["pool_age_bin"], row["liquidity_bin"]))
        rows.append(row)
    return rows


def feature_comparisons(rows):
    labeled = [row for row in rows if row["outcome_class"] in {"SURGE", "ORDINARY", "FAILURE", "CRASH"}]
    output = []
    for frame in sorted({row["frame"] for row in labeled}):
        frame_rows = [row for row in labeled if row["frame"] == frame]
        for other in ("ORDINARY", "FAILURE", "CRASH"):
            for feature in FEATURES:
                surge = [finite(row[feature]) for row in frame_rows if row["outcome_class"] == "SURGE"]
                comparison = [finite(row[feature]) for row in frame_rows if row["outcome_class"] == other]
                surge = [value for value in surge if value is not None]
                comparison = [value for value in comparison if value is not None]
                strata = defaultdict(lambda: defaultdict(list))
                for row in frame_rows:
                    value = finite(row[feature])
                    if value is not None and row["outcome_class"] in ("SURGE", other):
                        strata[row["stratum"]][row["outcome_class"]].append(value)
                directions = []
                for values in strata.values():
                    if len(values["SURGE"]) >= 3 and len(values[other]) >= 3:
                        directions.append(statistics.median(values["SURGE"]) - statistics.median(values[other]))
                output.append({
                    "frame": frame,
                    "contrast": f"SURGE_vs_{other}",
                    "feature": feature,
                    "surge_n": len(surge),
                    "other_n": len(comparison),
                    "surge_median": statistics.median(surge) if surge else None,
                    "other_median": statistics.median(comparison) if comparison else None,
                    "median_difference": statistics.median(surge) - statistics.median(comparison) if surge and comparison else None,
                    "eligible_strata": len(directions),
                    "strata_positive_difference": sum(value > 0 for value in directions),
                    "strata_negative_difference": sum(value < 0 for value in directions),
                    "strata_zero_difference": sum(value == 0 for value in directions),
                })
    return output


def strata_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        if row["outcome_class"] in {"SURGE", "ORDINARY", "FAILURE", "CRASH"}:
            grouped[(row["frame"], row["stratum"], row["outcome_class"])].append(row)
    output = []
    for (frame, stratum, label), group in sorted(grouped.items()):
        item = {"frame": frame, "stratum": stratum, "outcome_class": label, "n": len(group)}
        for feature in FEATURES:
            values = [finite(row[feature]) for row in group]
            values = [value for value in values if value is not None]
            item[feature + "_n"] = len(values)
            item[feature + "_median"] = statistics.median(values) if values else None
        output.append(item)
    return output


def funnel_rows(rows):
    output = []
    sample = [row for row in rows if row["frame"] == "token_universe_forward"]
    for label in sorted({row["outcome_class"] for row in sample}):
        group = [row for row in sample if row["outcome_class"] == label]
        for stage in ("candidate_evaluation_ever", "decision_final_ever", "paper_fill_ever"):
            output.append({
                "frame": "token_universe_forward",
                "outcome_class": label,
                "audit_marker": stage,
                "denominator": len(group),
                "count": sum(int(row[stage]) for row in group),
                "rate": sum(int(row[stage]) for row in group) / len(group) if group else None,
                "causal_feature": False,
                "note": "post-t0 ever marker; selection audit only",
            })
    return output


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    began = time.monotonic()
    cutoff = iso_now()
    OUT.mkdir(parents=True, exist_ok=True)
    db = ReadOnlyDb(DB)
    tables = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {
        "token_universe_forward_cohorts", "token_universe_forward_baselines",
        "token_universe_forward_outcomes", "token_universe_outcome_quality",
        "token_universe_funnel_transitions", "token_snapshots",
        "chain_meme_trader_v6_cohorts", "chain_meme_universe_outcomes",
    }
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("required tables absent: " + ", ".join(missing))
    frontiers = {
        "universe_cohort_id": frontier(db, "token_universe_forward_cohorts"),
        "universe_outcome_id": frontier(db, "token_universe_forward_outcomes"),
        "outcome_quality_id": frontier(db, "token_universe_outcome_quality"),
        "funnel_transition_id": frontier(db, "token_universe_funnel_transitions"),
        "snapshot_id": frontier(db, "token_snapshots"),
        "chain_cohort_id": frontier(db, "chain_meme_trader_v6_cohorts"),
        "chain_outcome_id": frontier(db, "chain_meme_universe_outcomes"),
    }
    coverage = {
        "universe_cohorts_by_chain": db.query(
            "SELECT lower(chain) AS chain,count(*) AS n,min(id) AS min_id,max(id) AS max_id "
            "FROM token_universe_forward_cohorts WHERE id<=? GROUP BY lower(chain) ORDER BY lower(chain)",
            (frontiers["universe_cohort_id"],),
        ),
        "universe_baseline_status": db.query(
            "SELECT status,count(*) AS n FROM token_universe_forward_baselines "
            "WHERE cohort_id<=? GROUP BY status ORDER BY status",
            (frontiers["universe_cohort_id"],),
        ),
        "universe_outcome_status": db.query(
            "SELECT horizon_minutes,status,count(*) AS n,min(evaluated_at) AS first_evaluated_at,"
            "max(evaluated_at) AS last_evaluated_at FROM token_universe_forward_outcomes "
            "WHERE id<=? GROUP BY horizon_minutes,status ORDER BY horizon_minutes,status",
            (frontiers["universe_outcome_id"],),
        ),
        "chain_outcome_status": db.query(
            "SELECT observer_version,horizon_minutes,status,count(*) AS n FROM chain_meme_universe_outcomes "
            "WHERE id<=? GROUP BY observer_version,horizon_minutes,status "
            "ORDER BY observer_version,horizon_minutes,status",
            (frontiers["chain_outcome_id"],),
        ),
    }
    universe_total = sum(int(row["n"]) for row in coverage["universe_cohorts_by_chain"])
    baseline_registered = sum(int(row["n"]) for row in coverage["universe_baseline_status"])
    coverage["universe_baseline_not_registered"] = universe_total - baseline_registered
    universe, hash_version = select_universe_sample(db, frontiers["universe_cohort_id"])
    universe_ids = [int(row["id"]) for row in universe]
    universe_evidence = lookup_universe_evidence(
        db, universe_ids, frontiers["universe_outcome_id"], frontiers["outcome_quality_id"]
    )
    chain_frame = load_chain_frame(db, frontiers["chain_cohort_id"], frontiers["chain_outcome_id"])
    snapshot_ids = [row.get("baseline_snapshot_id") for row in universe_evidence.values()]
    snapshot_ids.extend(int(row["source_snapshot_id"]) for row in chain_frame)
    snapshots = load_snapshots(db, snapshot_ids, frontiers["snapshot_id"])
    funnel = load_funnel(db, universe_ids, frontiers["funnel_transition_id"])
    exact_positions, token_positions, distinct_entries, position_rows = load_position_index()
    rows = build_rows(
        universe, universe_evidence, chain_frame, snapshots, funnel,
        exact_positions, token_positions,
    )
    comparisons = feature_comparisons(rows)
    strata = strata_rows(rows)
    funnel_audit = funnel_rows(rows)
    write_csv(OUT / "token_precursor_cohorts.csv", rows)
    write_csv(OUT / "token_precursor_feature_comparison.csv", comparisons)
    write_csv(OUT / "token_precursor_strata.csv", strata)
    write_csv(OUT / "token_precursor_funnel.csv", funnel_audit)
    class_counts = defaultdict(Counter)
    for row in rows:
        class_counts[row["frame"]][row["outcome_class"]] += 1
    summary = {
        "research_contract": {
            "frozen_before_formal_calculation": True,
            "cutoff_utc": cutoff,
            "primary_horizon_minutes": PRIMARY_HORIZON_MINUTES,
            "labels": {
                "SURGE": f"return >= {SURGE_RETURN}",
                "ORDINARY": f"{FAILURE_RETURN} < return < {SURGE_RETURN}",
                "FAILURE": f"{CRASH_RETURN} < return <= {FAILURE_RETURN}",
                "CRASH": f"return <= {CRASH_RETURN}",
            },
            "universe_sample": {
                "method": "smallest unsigned SHA-256 ranks without replacement",
                "key": "definition_version|cohort_id|token_id",
                "n_cap": UNIVERSE_SAMPLE_N,
                "definition_version_literal": hash_version,
            },
            "strata": ["chain", "UTC 12-hour t0 block", "pool-age bin", "liquidity bin"],
            "feature_boundary": "exact t0 snapshot and then-visible rolling fields only",
            "future_fields_excluded": ["maximum_return", "minimum_return", "peak_return_tier"],
        },
        "database": str(DB),
        "database_bytes_at_start": DB.stat().st_size,
        "positions_evidence": {
            "path": str(POSITIONS),
            "rows": position_rows,
            "distinct_token_cohort_snapshot_entries": len(distinct_entries),
            "note": "used only as audit markers; not as precursor features or sample inclusion",
        },
        "frontiers": frontiers,
        "coverage": coverage,
        "sample_rows": len(rows),
        "sample_by_frame": dict(Counter(row["frame"] for row in rows)),
        "class_counts_by_frame": {key: dict(value) for key, value in class_counts.items()},
        "exact_position_matches_by_frame": {
            frame: sum(row["exact_position_rows"] > 0 for row in rows if row["frame"] == frame)
            for frame in sorted(class_counts)
        },
        "feature_availability_by_frame": {
            frame: {
                feature: sum(finite(row[feature]) is not None for row in rows if row["frame"] == frame)
                for feature in FEATURES
            }
            for frame in sorted(class_counts)
        },
        "query_diagnostics": {
            "count": len(db.query_log),
            "max_seconds": max(item["seconds"] for item in db.query_log),
            "sum_seconds": sum(item["seconds"] for item in db.query_log),
            "statement_limit_seconds": STATEMENT_SECONDS,
            "all_queries_within_limit": all(item["seconds"] <= STATEMENT_SECONDS + 0.1 for item in db.query_log),
        },
        "collection": {
            "started_utc": cutoff,
            "completed_utc": iso_now(),
            "elapsed_seconds": time.monotonic() - began,
            "universe_frame_min_discovery_recorded_at": min(row["discovery_recorded_at"] for row in universe),
            "universe_frame_max_discovery_recorded_at": max(row["discovery_recorded_at"] for row in universe),
            "chain_frame_min_decided_at": min(row["decided_at"] for row in chain_frame) if chain_frame else None,
            "chain_frame_max_decided_at": max(row["decided_at"] for row in chain_frame) if chain_frame else None,
        },
        "interpretation_boundary": "descriptive associations only; not alpha, a backtest, parameter selection, or Paper/Live eligibility",
    }
    (OUT / "token_precursor_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    db.close()
    print(json.dumps({
        "summary": str(OUT / "token_precursor_summary.json"),
        "rows": len(rows),
        "elapsed_seconds": summary["collection"]["elapsed_seconds"],
        "classes": summary["class_counts_by_frame"],
        "max_query_seconds": summary["query_diagnostics"]["max_seconds"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
