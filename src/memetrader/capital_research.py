"""Bounded, read-only forward terminal-outcome frequencies, not a survival model.

Call the loader with an existing read-only SQLite connection, seal its result once,
and persist the returned JSON under its model_id. Never regenerate old decisions.
Bins are frozen chain x entry liquidity; one first episode and one lexically
preselected arm per token prevents duplicated strategy arms inflating maturity.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3
from typing import Any, Mapping, Sequence


def _time(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def _bin(token_id: str, liquidity: Any) -> str | None:
    try:
        amount = float(liquidity)
    except (TypeError, ValueError):
        return None
    chain, _, mint = token_id.partition(":")
    if not mint or not math.isfinite(amount) or amount < 1:
        return None
    return chain + (":1-10000" if amount < 10000 else ":10000-100000" if amount < 100000 else ":100000+")


def _rows(db: sqlite3.Connection, sql: str, args: Sequence[Any]) -> list[dict]:
    cursor = db.execute(sql, args)
    keys = [c[0] for c in cursor.description]
    return [dict(zip(keys, row)) for row in cursor]


def load_competing_risk_samples(db: sqlite3.Connection, definition_version: str,
                               cutoff_at: str, *, max_cohorts: int = 1024,
                               max_samples: int = 256) -> dict:
    """No writes/network. At most 1024 cohort rows, 256 samples, 65 trades/case.

    Current mutable position status alone is never a label: complete recorded
    BUY/SELL/WRITEOFF ledger and as-of entry snapshot are required. Polluted rows
    are excluded even if subsequently repaired. Missing route probes stay unknown.
    The bounded recent-cohort tail and closed-only selection are reported, not
    represented as a population survival estimate.
    """
    cutoff = _time(cutoff_at)
    if cutoff is None or not 1 <= max_cohorts <= 1024 or not 1 <= max_samples <= 256:
        raise ValueError("valid UTC cutoff and bounded limits required")
    cutoff_sql = cutoff.isoformat().replace("+00:00", "Z")
    cohorts = _rows(db, "SELECT id FROM chain_meme_trader_v6_cohorts WHERE definition_version=? "
                    "AND decided_at<=? ORDER BY id DESC LIMIT ?", (definition_version, cutoff_sql, max_cohorts))
    result = dict(samples=[], excluded={}, scanned_cohorts=len(cohorts), cutoff_at=cutoff_at,
                  definition_version=definition_version, max_cohorts=max_cohorts, max_samples=max_samples)
    if not cohorts:
        return result
    low, high = min(r["id"] for r in cohorts), max(r["id"] for r in cohorts)
    candidates = _rows(db, """
        SELECT p.*, c.episode_no, c.decided_at, c.pair_address,
               s.token_id feature_token_id, s.liquidity_usd, s.id feature_snapshot_id,
               s.observed_at feature_observed_at, s.ingested_at feature_ingested_at,
               s.recorded_at feature_recorded_at, s.raw_json feature_raw_json
        FROM chain_meme_trader_v6_cohorts c
        JOIN chain_meme_trader_positions p ON p.definition_version=c.definition_version
             AND p.shadow_cohort_id=c.id
        JOIN token_snapshots s ON s.id=c.source_snapshot_id
        WHERE c.definition_version=? AND c.id BETWEEN ? AND ?
          AND p.arm_id=(SELECT MIN(p2.arm_id) FROM chain_meme_trader_positions p2
                        WHERE p2.definition_version=p.definition_version AND p2.shadow_cohort_id=c.id AND p2.opened_at<=?)
        ORDER BY c.id DESC LIMIT ?
        """, (definition_version, low, high, cutoff_sql, max_cohorts))
    excluded: Counter = Counter()
    seen: set[str] = set()
    for row in candidates:
        if len(result["samples"]) >= max_samples:
            break
        token = row["token_id"]
        if row["episode_no"] != 1 or token in seen:
            excluded["duplicate_episode"] += 1
            continue
        seen.add(token)
        opened, closed, decided = (_time(row[k]) for k in ("opened_at", "closed_at", "decided_at"))
        observed, ingested, recorded = (_time(row[k]) for k in
                                       ("feature_observed_at", "feature_ingested_at", "feature_recorded_at"))
        if (row["status"] not in {"closed", "written_off"} or not all((opened, closed, decided, observed, ingested, recorded))
                or not observed <= ingested <= recorded <= decided <= opened <= closed <= cutoff):
            excluded["not_closed_asof_or_missing_timing"] += 1
            continue
        bin_key = _bin(token, row["liquidity_usd"])
        try:
            pair = json.loads(row["feature_raw_json"]).get("pair", {}).get("pairAddress")
        except (ValueError, TypeError, AttributeError):
            pair = None
        if not bin_key or row["feature_token_id"] != token or not pair or pair != row["pair_address"]:
            excluded["entry_feature_identity_or_liquidity"] += 1
            continue
        key = (definition_version, row["arm_id"], row["shadow_cohort_id"])
        polluted = False
        for table in ("chain_meme_trader_accounting_contaminations", "chain_meme_trader_market_fill_corrections",
                      "chain_meme_trader_capital_credits"):
            if db.execute(f"SELECT 1 FROM {table} WHERE definition_version=? AND arm_id=? "
                          "AND shadow_cohort_id=? AND recorded_at<=? LIMIT 1", (*key, cutoff_sql)).fetchone():
                polluted = True
                break
        if polluted:
            excluded["engineering_pollution"] += 1
            continue
        trades = _rows(db, "SELECT id,token_id,side,net_cash_flow_usd,created_at,recorded_at "
                       "FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? "
                       "AND shadow_cohort_id=? ORDER BY created_at,id LIMIT 65", key)
        times = [(_time(t["created_at"]), _time(t["recorded_at"])) for t in trades]
        if (not 2 <= len(trades) <= 64 or trades[0]["side"] != "BUY"
                or sum(t["side"] == "BUY" for t in trades) != 1
                or any(t["token_id"] != token for t in trades)
                or any(not a or not b or not opened <= a <= closed or not a <= b <= cutoff for a, b in times)
                or times[-1][0] != closed
                or (row["status"] == "written_off") != (trades[-1]["side"] == "WRITEOFF")):
            excluded["incomplete_or_noncausal_ledger"] += 1
            continue
        pnl = sum(float(t["net_cash_flow_usd"]) for t in trades)
        if not math.isfinite(pnl):
            excluded["invalid_ledger_cash"] += 1
            continue
        # Legacy protocol-valid route observations only. Never infer NO_ROUTE
        # from a Dex writeoff, missing pair, HTTP timeout, or absent response.
        quotes = _rows(db, "SELECT id,quote_terminal_status,requested_at,completed_at,recorded_at "
                       "FROM chain_meme_trader_quote_results WHERE definition_version=? AND shadow_cohort_id=? "
                       "AND validity_status='valid' ORDER BY recorded_at DESC LIMIT 8", (definition_version, key[2]))
        route = [q for q in quotes if all(_time(q[k]) for k in ("requested_at", "completed_at", "recorded_at"))
                 and opened <= _time(q["requested_at"]) <= _time(q["completed_at"]) <= closed
                 and _time(q["completed_at"]) <= _time(q["recorded_at"]) <= cutoff
                 and q["quote_terminal_status"] in {"quoted", "no_route"}]
        result["samples"].append(dict(
            sample_id=f"{definition_version}:{key[2]}:{key[1]}", token_id=token, bin_key=bin_key,
            arm_id=key[1], shadow_cohort_id=key[2], feature_snapshot_id=row["feature_snapshot_id"],
            feature_observed_at=row["feature_observed_at"], feature_recorded_at=row["feature_recorded_at"],
            entry_at=row["opened_at"], closed_at=row["closed_at"],
            available_at=max(b for _, b in times).isoformat(), ledger_ids=[t["id"] for t in trades],
            outcome="death" if row["status"] == "written_off" else "profit" if pnl > 0 else "ordinary_loss",
            net_pnl_usd=pnl, route_observed=bool(route), no_route_observed=any(q["quote_terminal_status"] == "no_route" for q in route),
            route_evidence_ids=[q["id"] for q in route]))
    result["excluded"] = dict(excluded)
    result["cohort_bounds"] = [low, high]
    return result


def seal_competing_risk_model(source: Mapping[str, Any], *, trained_at: str) -> dict:
    """Freeze available outcomes; caller retains this exact JSON, never updates it."""
    cutoff, trained = _time(source.get("cutoff_at")), _time(trained_at)
    if not cutoff or not trained or cutoff > trained:
        raise ValueError("training must follow the data cutoff")
    samples = source.get("samples", [])
    if len(samples) > 256:
        raise ValueError("sample bound exceeded")
    sealed, seen = [], set()
    for sample in samples:
        times = [_time(sample.get(k)) for k in
                 ("feature_observed_at", "feature_recorded_at", "entry_at", "closed_at", "available_at")]
        if (not all(times) or times != sorted(times) or times[-1] > cutoff
                or sample.get("outcome") not in {"profit", "death", "ordinary_loss"}
                or sample["token_id"] in seen):
            continue
        seen.add(sample["token_id"])
        sealed.append(dict(sample))
    bins = {}
    for key in sorted({s["bin_key"] for s in sealed}):
        rows = [s for s in sealed if s["bin_key"] == key]
        counts = Counter(s["outcome"] for s in rows)
        route_n = sum(s["route_observed"] for s in rows)
        bins[key] = dict(n=len(rows), counts=dict(counts),
                         p_profit=counts["profit"] / len(rows), p_death=counts["death"] / len(rows),
                         p_ordinary_loss=counts["ordinary_loss"] / len(rows),
                         p_no_route=sum(s["no_route_observed"] for s in rows) / route_n if route_n else None,
                         route_observed_samples=route_n, route_coverage=route_n / len(rows),
                         sealed_sample_ids=[s["sample_id"] for s in rows])
    model = dict(schema="observable-terminal-competition/v1", sealed=True,
                 cutoff_at=source["cutoff_at"], trained_at=trained_at,
                 definition_version=source.get("definition_version"), bins=bins, samples=sealed,
                 excluded=dict(source.get("excluded", {})), scanned_cohorts=source.get("scanned_cohorts"),
                 cohort_bounds=source.get("cohort_bounds"), minimum_bin_samples=20,
                 outcome_basis="closed Paper ledger: profit, protocol WRITEOFF, ordinary loss including zero",
                 limitation="closed-only bounded sample; mixed preselected exit policies; not causal alpha or survival hazard")
    model["model_id"] = hashlib.sha256(json.dumps(model, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return model


def competing_risk_context(model: Mapping[str, Any], *, token_id: str, liquidity_usd: Any,
                           observed_at: str, recorded_at: str, decision_at: str) -> dict:
    """Fresh inference availability, immutable training time; no cross-bin fallback."""
    cutoff, trained, observed, recorded, decision = map(_time, (
        model.get("cutoff_at"), model.get("trained_at"), observed_at, recorded_at, decision_at))
    if (not all((cutoff, trained, observed, recorded, decision)) or model.get("sealed") is not True
            or not cutoff <= trained <= decision or not trained <= recorded or not observed <= recorded <= decision
            or (decision - observed).total_seconds() > 30):
        return dict(sample_status="noncausal_or_stale_model")
    key = _bin(token_id, liquidity_usd)
    b = model.get("bins", {}).get(key, {})
    return dict(b, bin_key=key, model_id=model.get("model_id"), sealed=True,
                cutoff_at=model["cutoff_at"], trained_at=model["trained_at"],
                observed_at=observed_at, recorded_at=recorded_at,
                sample_status="sufficient_sample" if b.get("n", 0) >= 20 else "insufficient_sample",
                probability_basis="observable_closed_Paper_terminal_outcomes",
                route_probability_basis="observed_protocol_quote_failure_only")
