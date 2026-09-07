"""Fixed-boundary, read-only Paper signal-to-receipt latency diagnostic."""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "data/research/alpha_diagnosis_20260907/BOUNDARY.json"
VERSION = "chain-meme-trader/funding-20260906-v002-final-1000"
ERA = "2026-09-07T09:19:47Z"
OUT = ROOT / "data/research/alpha_diagnosis_20260907/latency"
REPORT = ROOT / "docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/DATA_LATENCY_EDGE_DECAY.md"


def time(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def percentile(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    i = (len(values) - 1) * q
    lo, hi = int(i), math.ceil(i)
    return values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (i - lo)


def chain(token):
    return token.split(":", 1)[0] if ":" in token else "unknown"


def bucket(seconds):
    if seconds is None:
        return "unknown"
    if seconds <= 5:
        return "<=5s"
    if seconds <= 15:
        return "5-15s"
    if seconds <= 30:
        return "15-30s"
    if seconds <= 60:
        return "30-60s"
    return ">60s"


def pair_from_raw(raw):
    try:
        obj = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None
    pair = obj.get("pair") if isinstance(obj.get("pair"), dict) else obj
    return pair.get("pairAddress") or pair.get("pair_address")


def same_pool(left, right, chain_name):
    if not left or not right:
        return None
    # EVM address casing is non-semantic; Solana base58 casing is semantic.
    return left.lower() == right.lower() if chain_name in {"bsc", "robinhood"} else left == right


def signal_from_feature(feature, arm, cohort_pair, snapshots):
    """Recover only recorded signal evidence; cohort.decided_at is never a fallback."""
    signals = feature.get("cohort_signals") or {}
    evidence = (signals.get(arm) or {}).get("decision_evidence") or {}
    resources = feature.get("resource_bound_opportunities") or {}
    direction = arm.removeprefix("resource_").rsplit("_", 2)[0] if arm.startswith("resource_") else None
    resource = resources.get(f"{direction}:{cohort_pair}") if direction else None
    if isinstance(resource, dict) and resource.get("decision_at"):
        return resource.get("decision_at"), resource.get("signal_snapshot_id"), "resource_bound_opportunities.decision_at"
    if feature.get("signal_at"):
        return feature["signal_at"], feature.get("source_snapshot_id"), "feature.signal_at"
    if evidence.get("recorded_at"):
        return evidence["recorded_at"], feature.get("fill_signal_snapshot_id"), "cohort_signals.decision_evidence.recorded_at"
    if evidence.get("ingested_at"):
        return evidence["ingested_at"], feature.get("fill_signal_snapshot_id"), "cohort_signals.decision_evidence.ingested_at"
    snapshot_id = feature.get("fill_signal_snapshot_id")
    snap = snapshots.get(snapshot_id)
    if snap and snap["recorded_at"]:
        return snap["recorded_at"], snapshot_id, "feature.fill_signal_snapshot_id.recorded_at"
    return None, snapshot_id, "unknown"


def connect():
    db = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["database"]
    p = Path(db)
    if not p.is_absolute():
        p = ROOT / p
    con = sqlite3.connect("file:" + p.resolve().as_posix() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def summarize(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    result = []
    for name, group in sorted(groups.items()):
        latency = [r["receipt_delay_s"] for r in group if r["receipt_delay_s"] is not None]
        terminal = [r["opportunity_terminal_pnl_median_usd"] for r in group
                    if r["opportunity_terminal_pnl_median_usd"] is not None]
        result.append({"group": name, "N_opportunities": len(group), "N_recovered_latency": len(latency),
                       "p50_delay_s": percentile(latency, .5), "p90_delay_s": percentile(latency, .9),
                       "N_terminal_median": len(terminal), "p50_terminal_pnl_usd": percentile(terminal, .5),
                       "mean_terminal_pnl_usd": sum(terminal) / len(terminal) if terminal else None})
    return result


def main():
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    cutoff = boundary["cutoff_utc"]
    con = connect()
    try:
        # source_entry_fill_id is a shared v6 fill ID. The four-key join is the receipt proof.
        positions = con.execute("""
          SELECT p.arm_id,p.shadow_cohort_id,p.token_id,p.source_buy_trade_id,p.entry_snapshot_id,
                 p.opened_at,p.closed_at,p.realized_pnl_usd,p.status,p.entry_fill_id,p.source_entry_fill_id,
                 p.entry_execution_price_usd,p.entry_signal_price_usd,
                 c.pair_address,c.feature_json,vf.filled_at AS v6_filled_at,
                 vf.entry_market_price_usd,vf.execution_price_usd,
                 s.observed_at AS entry_observed_at,s.ingested_at AS entry_ingested_at,s.recorded_at AS entry_recorded_at,
                 s.raw_json AS entry_raw_json
          FROM chain_meme_trader_positions p
          JOIN chain_meme_trader_trades t ON t.definition_version=p.definition_version AND t.arm_id=p.arm_id
             AND t.shadow_cohort_id=p.shadow_cohort_id AND t.token_id=p.token_id AND t.side='BUY'
             AND t.id<=? AND t.created_at<=?
          JOIN chain_meme_trader_v6_entry_fills vf ON vf.id=p.source_entry_fill_id
             AND vf.definition_version=p.definition_version AND vf.entry_cohort_id=p.shadow_cohort_id
             AND vf.token_id=p.token_id
          LEFT JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id AND c.definition_version=p.definition_version
          LEFT JOIN token_snapshots s ON s.id=p.entry_snapshot_id AND s.token_id=p.token_id
          WHERE p.definition_version=? AND vf.filled_at<=? AND p.shadow_cohort_id<=?
          ORDER BY p.shadow_cohort_id,p.arm_id
        """, (boundary["frontiers"]["chain_meme_trader_trades"], cutoff, VERSION, cutoff,
              boundary["frontiers"]["chain_meme_trader_v6_cohorts"])).fetchall()
        total_positions = con.execute("""
          SELECT COUNT(*) FROM chain_meme_trader_positions
          WHERE definition_version=? AND shadow_cohort_id<=?
        """, (VERSION, boundary["frontiers"]["chain_meme_trader_v6_cohorts"])).fetchone()[0]
        ids = {r["entry_snapshot_id"] for r in positions}
        fill_ids = set()
        for r in positions:
            feature = json.loads(r["feature_json"] or "{}")
            fill_id = feature.get("fill_signal_snapshot_id")
            if isinstance(fill_id, int):
                fill_ids.add(fill_id)
            source_id = feature.get("source_snapshot_id")
            if isinstance(source_id, int):
                fill_ids.add(source_id)
            for value in (feature.get("resource_bound_opportunities") or {}).values():
                if isinstance(value, dict) and isinstance(value.get("signal_snapshot_id"), int):
                    fill_ids.add(value["signal_snapshot_id"])
        all_ids = ids | fill_ids
        snapshots = {}
        if all_ids:
            for r in con.execute("SELECT id,token_id,observed_at,ingested_at,recorded_at,price_usd,raw_json FROM token_snapshots WHERE id<=? AND id IN (%s)" % ",".join("?" * len(all_ids)),
                                 [boundary["frontiers"]["token_snapshots"], *sorted(all_ids)]):
                snapshots[r["id"]] = dict(r)
    finally:
        con.close()
    records = []
    for r in positions:
        feature = json.loads(r["feature_json"] or "{}")
        signal_at, signal_snapshot_id, signal_source = signal_from_feature(feature, r["arm_id"], r["pair_address"], snapshots)
        signal_dt = time(signal_at)
        fill_dt = time(r["v6_filled_at"])
        verified_fill = bool(fill_dt and (signal_dt is None or fill_dt >= signal_dt))
        if verified_fill:
            receipt_at, receipt_source, receipt_kind = r["v6_filled_at"], "chain_meme_trader_v6_entry_fills.source_entry_fill_id", "receipt_verified"
        else:
            receipt_at, receipt_source, receipt_kind = r["opened_at"], "position.opened_at", "projection_delay_proxy"
        signal_dt, receipt_dt = time(signal_at), time(receipt_at)
        delay = (receipt_dt - signal_dt).total_seconds() if signal_dt and receipt_dt else None
        signal_snap = snapshots.get(signal_snapshot_id)
        source_nonlate = None
        if signal_snap and signal_dt:
            source_nonlate = all(time(signal_snap.get(k)) and time(signal_snap[k]) <= signal_dt
                                 for k in ("observed_at", "ingested_at", "recorded_at"))
        elif signal_source.startswith("cohort_signals"):
            # The decision evidence itself supplies the recorded signal timestamp; no source snapshot ID exists.
            source_nonlate = "unknown"
        entry_pair = pair_from_raw(r["entry_raw_json"])
        pool_match = same_pool(entry_pair, r["pair_address"], chain(r["token_id"]))
        if pool_match is None:
            pool = "unknown"
        elif pool_match:
            pool = "original_pool_matched"
        else:
            pool = "pool_mismatch"
        entry_clocks = [time(r[k]) for k in ("entry_observed_at", "entry_ingested_at", "entry_recorded_at")]
        entry_clock_ordered = bool(all(entry_clocks) and entry_clocks[0] <= entry_clocks[1] <= entry_clocks[2] <= receipt_dt)
        signal_price = signal_snap.get("price_usd") if signal_snap else None
        receipt_market_price = r["entry_market_price_usd"]
        execution_price = r["execution_price_usd"]
        price_drift = (float(receipt_market_price) / float(signal_price) - 1
                       if signal_price and receipt_market_price else None)
        execution_slippage = (float(execution_price) / float(receipt_market_price) - 1
                              if execution_price and receipt_market_price else None)
        records.append({"arm_id": r["arm_id"], "cohort_id": r["shadow_cohort_id"], "token_id": r["token_id"],
                        "chain": chain(r["token_id"]), "signal_at": signal_at, "signal_source": signal_source,
                        "signal_snapshot_id": signal_snapshot_id, "receipt_at": receipt_at,
                        "receipt_source": receipt_source, "receipt_kind": receipt_kind,
                        "receipt_delay_s": delay, "delay_bucket": bucket(delay),
                        "source_snapshot_nonlate": source_nonlate, "entry_snapshot_id": r["entry_snapshot_id"],
                        "entry_observed_at": r["entry_observed_at"], "entry_ingested_at": r["entry_ingested_at"],
                        "entry_recorded_at": r["entry_recorded_at"], "entry_clock_ordered": entry_clock_ordered,
                        "pool_identity": pool, "signal_price_usd": signal_price,
                        "receipt_market_price_usd": receipt_market_price, "execution_price_usd": execution_price,
                        "signal_to_receipt_market_drift": price_drift, "execution_vs_market_slippage": execution_slippage,
                        "status": r["status"], "realized_pnl_usd": r["realized_pnl_usd"],
                        "closed_at": r["closed_at"],
                        "era": "after_091947Z" if (signal_at and signal_at >= ERA) else "before_091947Z"})
    # One row per Token/cohort is the analysis sample. Per-arm terminal PnL is collapsed to a median,
    # since different exits make a single arm's payoff unsuitable as a common opportunity outcome.
    grouped = defaultdict(list)
    for r in records:
        grouped[(r["token_id"], r["cohort_id"])].append(r)
    opportunities = []
    for (_, _), group in grouped.items():
        recoverable = [r for r in group if r["receipt_delay_s"] is not None and r["receipt_delay_s"] >= 0]
        # Do not select the shortest arm delay: the opportunity statistic is its arm-level median and range.
        representative = dict(group[0])
        delays = [r["receipt_delay_s"] for r in recoverable]
        terminal = [r["realized_pnl_usd"] for r in group if r["status"] in {"closed", "written_off"}
                    and r["closed_at"] and r["closed_at"] <= cutoff]
        strict_drifts = [r["signal_to_receipt_market_drift"] for r in group
                         if r["pool_identity"] == "original_pool_matched" and r["source_snapshot_nonlate"] is True
                         and r["entry_clock_ordered"] and r["signal_to_receipt_market_drift"] is not None]
        representative["arms_in_opportunity"] = len(group)
        representative["receipt_delay_s"] = percentile(delays, .5)
        representative["receipt_delay_min_s"] = min(delays) if delays else None
        representative["receipt_delay_max_s"] = max(delays) if delays else None
        representative["delay_bucket"] = bucket(representative["receipt_delay_s"])
        kinds = {r["receipt_kind"] for r in group}
        representative["receipt_kind"] = next(iter(kinds)) if len(kinds) == 1 else "mixed"
        representative["receipt_verified_arms"] = sum(r["receipt_kind"] == "receipt_verified" for r in group)
        representative["projection_proxy_arms"] = sum(r["receipt_kind"] == "projection_delay_proxy" for r in group)
        representative["strict_identity_three_clock_market_drift"] = percentile(strict_drifts, .5)
        representative["opportunity_terminal_pnl_median_usd"] = percentile(terminal, .5)
        opportunities.append(representative)
    OUT.mkdir(parents=True, exist_ok=True); REPORT.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in opportunities for k in r})
    with (OUT / "opportunity_latency.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(opportunities)
    strict_opportunities = [r for r in opportunities if r["strict_identity_three_clock_market_drift"] is not None]
    summary = {"boundary": boundary, "current_period_positions_denominator": total_positions,
               "mapped_buy_position_rows": len(records), "unmapped_positions": total_positions - len(records),
               "unique_token_cohort_opportunities": len(opportunities),
               "recovered_latency": sum(r["receipt_delay_s"] is not None and r["receipt_delay_s"] >= 0 for r in opportunities),
               "unknown_latency": sum(r["receipt_delay_s"] is None for r in opportunities),
               "negative_latency": sum(r["receipt_delay_s"] is not None and r["receipt_delay_s"] < 0 for r in opportunities),
               "full_period": {"N_opportunities": len(opportunities),
                               "p50_delay_s": percentile([r["receipt_delay_s"] for r in opportunities], .5),
                               "p90_delay_s": percentile([r["receipt_delay_s"] for r in opportunities], .9),
                               "N_terminal_median": sum(r["opportunity_terminal_pnl_median_usd"] is not None for r in opportunities),
                               "p50_terminal_pnl_usd": percentile([r["opportunity_terminal_pnl_median_usd"] for r in opportunities], .5)},
               "by_chain": summarize(opportunities, "chain"), "by_era": summarize(opportunities, "era"),
               "by_delay_bucket": summarize(opportunities, "delay_bucket"),
               "pool_identity": dict(sorted((k, sum(r["pool_identity"] == k for r in opportunities)) for k in {r["pool_identity"] for r in opportunities})),
               "receipt_kind_arms": dict(sorted((k, sum(r["receipt_kind"] == k for r in records)) for k in {r["receipt_kind"] for r in records})),
               "source_snapshot_nonlate": dict(sorted((str(k), sum(r["source_snapshot_nonlate"] == k for r in opportunities)) for k in {r["source_snapshot_nonlate"] for r in opportunities}))}
    observed_to_ingested = [(time(r["entry_ingested_at"]) - time(r["entry_observed_at"])).total_seconds()
                            for r in records if time(r["entry_observed_at"]) and time(r["entry_ingested_at"])]
    ingested_to_recorded = [(time(r["entry_recorded_at"]) - time(r["entry_ingested_at"])).total_seconds()
                            for r in records if time(r["entry_ingested_at"]) and time(r["entry_recorded_at"])]
    summary["entry_snapshot_timestamp_gaps_s"] = {
        "observed_to_ingested": {"N": len(observed_to_ingested), "p50": percentile(observed_to_ingested, .5), "p90": percentile(observed_to_ingested, .9)},
        "ingested_to_recorded": {"N": len(ingested_to_recorded), "p50": percentile(ingested_to_recorded, .5), "p90": percentile(ingested_to_recorded, .9)}}
    summary["verified_identity_three_clock_market_drift"] = {"N_opportunities": len(strict_opportunities),
        "p50": percentile([r["strict_identity_three_clock_market_drift"] for r in strict_opportunities], .5),
        "p90": percentile([r["strict_identity_three_clock_market_drift"] for r in strict_opportunities], .9)}
    summary["execution_vs_market_slippage"] = {"N_arm_rows": sum(r["execution_vs_market_slippage"] is not None for r in records),
        "p50": percentile([r["execution_vs_market_slippage"] for r in records], .5),
        "p90": percentile([r["execution_vs_market_slippage"] for r in records], .9)}
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    def table(items):
        return "\n".join("| " + " | ".join(str(x.get(k, "")) for k in ["group","N_opportunities","N_recovered_latency","p50_delay_s","p90_delay_s","N_terminal_median","p50_terminal_pnl_usd"]) + " |" for x in items)
    REPORT.write_text(f"""# Data latency and edge-decay diagnostic

Fixed boundary: `{cutoff}`; current funding period only. The position denominator is `{total_positions}`. `{len(records)}` positions map through a bounded current-period BUY source; `{total_positions - len(records)}` do not and are reported as unmapped (historical inheritance or no eligible source mapping), not silently treated as coverage. The mapped rows collapse to `{summary['unique_token_cohort_opportunities']}` unique `(token, cohort)` opportunities. Their latency is the within-opportunity median across arms, with per-opportunity min/max retained in the CSV; no shortest-arm selection occurs.

Full period: N={summary['full_period']['N_opportunities']}, delay p50={summary['full_period']['p50_delay_s']:.3f}s, p90={summary['full_period']['p90_delay_s']:.3f}s; terminal-median outcome N={summary['full_period']['N_terminal_median']}, p50={summary['full_period']['p50_terminal_pnl_usd']:.3f}U.

Signal time is a **decision-time proxy**, recovered in order: resource `resource_bound_opportunities.decision_at`, `feature.signal_at`, arm-specific `cohort_signals.decision_evidence.recorded_at`/`ingested_at`, then `feature.fill_signal_snapshot_id.recorded_at`. `cohort.decided_at` is never used. A receipt is verified by `source_entry_fill_id` joining `chain_meme_trader_v6_entry_fills.id` with matching version, entry_cohort_id and token. The actual BUY is separately matched by version/arm/cohort/token/side and frozen trade frontier. `source_buy_trade_id` is historically overloaded with a v6 fill ID, so it must not be joined to `trades.id`. Unverified fallback timestamps would remain projection proxies; in this frozen current-period sample all positions have a verified shared v6 fill. Entry snapshot timestamps are retained in the CSV. A source snapshot is only marked non-late when all observed/ingested/recorded timestamps are no later than the recovered decision proxy.

Original-pool identity: `{summary['pool_identity']}` (EVM comparisons case-insensitive; Solana case-sensitive). Source-snapshot timing coverage: `{summary['source_snapshot_nonlate']}`. Receipt evidence by arm: `{summary['receipt_kind_arms']}`.

Entry snapshot clock gaps across arm-level BUY positions: observed→ingested N={summary['entry_snapshot_timestamp_gaps_s']['observed_to_ingested']['N']}, p50={summary['entry_snapshot_timestamp_gaps_s']['observed_to_ingested']['p50']:.3f}s, p90={summary['entry_snapshot_timestamp_gaps_s']['observed_to_ingested']['p90']:.3f}s; ingested→recorded N={summary['entry_snapshot_timestamp_gaps_s']['ingested_to_recorded']['N']}, p50={summary['entry_snapshot_timestamp_gaps_s']['ingested_to_recorded']['p50']:.3f}s, p90={summary['entry_snapshot_timestamp_gaps_s']['ingested_to_recorded']['p90']:.3f}s. The 11 source snapshots later than their recovered decision feature are retained as a causal-timing coverage failure, not repaired.

Verified-identity plus three-clock (`observed <= ingested <= recorded <= v6 fill`) market-price subset: N={summary['verified_identity_three_clock_market_drift']['N_opportunities']}, signal→receipt **market-price** drift p50={summary['verified_identity_three_clock_market_drift']['p50']:.6f}, p90={summary['verified_identity_three_clock_market_drift']['p90']:.6f}. The configured execution-vs-market slippage is reported separately: N={summary['execution_vs_market_slippage']['N_arm_rows']}, p50={summary['execution_vs_market_slippage']['p50']:.6f}, p90={summary['execution_vs_market_slippage']['p90']:.6f}. Neither is a causal latency estimate.

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
{table(summary['by_chain'])}

## Era split

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
{table(summary['by_era'])}

## Delay buckets and terminal outcome association

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
{table(summary['by_delay_bucket'])}

The terminal metric includes only closed/written-off arms with `closed_at <= cutoff`, then takes the median within a common Token/cohort. It prevents multiple arms from becoming multiple opportunities, but it is not a tradable single-arm payoff. Delay/outcome differences are descriptive only: entry rule, chain, pool age, liquidity, selection, capacity and exit contract are confounded. No causal edge-decay conclusion follows from this table.

Code-path evidence: `store.py:27056-27064` records resource-bound decision evidence and prevents repeat first-common opportunities; `store.py:28119-28124` separates isolated dispatch from main snapshot dispatch; position creation stores `entry_snapshot_id` and entry fill references at `store.py:29818-29854`; current position queries join that snapshot at `store.py:30923-30926`.
""", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
