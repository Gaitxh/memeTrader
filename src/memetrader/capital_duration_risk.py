"""Bounded, immutable duration competing-risk research helpers.

This module is deliberately separate from ``competing_risk_v1``.  It describes
observable Paper terminal outcomes, not market death or a trading claim.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3
from typing import Any, Mapping, Sequence


def duration_risk_policy() -> dict:
    from copy import deepcopy
    from .capital_policies import capital_policies
    parent = next(p for p in capital_policies() if p["arm_id"] == "competing_risk_v1")
    policy = deepcopy(parent)
    policy.update(arm_id="duration_competing_risk_v1", canonical_id="duration_competing_risk_v1",
        name="时长竞争风险·小额试验", entry_family="duration_competing_risk",
        source_arm_ids=[parent["arm_id"]], notional_usd=5.0,
        description="按链及入场流动性分组，封存含右删失的5分钟Paper终局概率；不是市场死亡或获利保证。",
        entry_filter={"direction": "duration_competing_risk", "min_sealed_samples": 20,
                      "horizon_seconds": 300, "gap_assumption": "adverse_sensitivity_not_realized_loss"},
        required_inputs=["sealed_duration_model", "asof_snapshot"])
    return policy


def _time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def _bin(token: str, liquidity: Any) -> str | None:
    try:
        value = float(liquidity)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    chain = str(token).split(":", 1)[0].lower()
    band = "lt10k" if value < 10_000 else "10k_100k" if value < 100_000 else "ge100k"
    return f"{chain}:{band}"


def _rows(db: sqlite3.Connection, sql: str, args: Sequence[Any]) -> list[dict]:
    cur = db.execute(sql, args)
    keys = [c[0] for c in cur.description]
    return [dict(zip(keys, row)) for row in cur]


def load_duration_risk_samples(db: sqlite3.Connection, definition_version: str,
                               deployment_cutoff: str, *, max_cohorts: int = 1024,
                               max_samples: int = 256) -> dict:
    """Load a bounded first-episode sample with explicit terminal/censor labels."""
    cutoff = _time(deployment_cutoff)
    if cutoff is None or not 1 <= max_cohorts <= 1024 or not 1 <= max_samples <= 256:
        raise ValueError("valid UTC cutoff and bounded limits required")
    cutoff_sql = cutoff.isoformat().replace("+00:00", "Z")
    cohorts = _rows(db, "SELECT id FROM chain_meme_trader_v6_cohorts "
                    "WHERE definition_version=? AND decided_at<=? ORDER BY id DESC LIMIT ?",
                    (definition_version, cutoff_sql, max_cohorts))
    result = dict(samples=[], excluded={}, scanned_cohorts=len(cohorts),
                  cutoff_at=deployment_cutoff, definition_version=definition_version,
                  max_cohorts=max_cohorts, max_samples=max_samples)
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
                        WHERE p2.definition_version=p.definition_version
                          AND p2.shadow_cohort_id=c.id AND p2.opened_at<=?)
        ORDER BY c.id DESC LIMIT ?
        """, (definition_version, low, high, cutoff_sql, max_cohorts))
    excluded: Counter = Counter()
    seen: set[str] = set()
    for row in candidates:
        if len(result["samples"]) >= max_samples:
            break
        token = row.get("token_id")
        opened = _time(row.get("opened_at"))
        decided = _time(row.get("decided_at"))
        observed = _time(row.get("feature_observed_at"))
        ingested = _time(row.get("feature_ingested_at"))
        recorded = _time(row.get("feature_recorded_at"))
        if (row.get("episode_no") != 1 or not token or token in seen):
            excluded["duplicate_or_nonfirst_episode"] += 1
            continue
        seen.add(token)
        if (not all((opened, decided, observed, ingested, recorded))
                or not observed <= ingested <= recorded <= decided <= opened <= cutoff
                or row.get("feature_token_id") != token):
            excluded["noncausal_or_missing_entry_feature"] += 1
            continue
        try:
            pair = json.loads(row.get("feature_raw_json") or "{}").get("pair", {}).get("pairAddress")
        except (TypeError, ValueError, AttributeError):
            pair = None
        bin_key = _bin(token, row.get("liquidity_usd"))
        if not pair or pair != row.get("pair_address") or not bin_key:
            excluded["entry_pair_identity"] += 1
            continue
        key = (definition_version, row["arm_id"], row["shadow_cohort_id"])
        polluted = False
        for table in ("chain_meme_trader_accounting_contaminations",
                      "chain_meme_trader_market_fill_corrections",
                      "chain_meme_trader_capital_credits"):
            if db.execute(f"SELECT 1 FROM {table} WHERE definition_version=? AND arm_id=? "
                          "AND shadow_cohort_id=? AND recorded_at<=? LIMIT 1",
                          (*key, cutoff_sql)).fetchone():
                polluted = True
                break
        if polluted:
            excluded["engineering_pollution"] += 1
            continue
        trades = _rows(db, "SELECT id,token_id,side,net_cash_flow_usd,realized_pnl_usd,created_at,recorded_at "
                       "FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? "
                       "AND shadow_cohort_id=? AND recorded_at<=? ORDER BY created_at,id LIMIT 65", (*key, cutoff_sql))
        if len(trades) >= 65:
            excluded["ledger_truncated"] += 1
            continue
        times = [(_time(t.get("created_at")), _time(t.get("recorded_at"))) for t in trades]
        if (not trades or len(trades) >= 65 or trades[0]["side"] != "BUY" or sum(t["side"] == "BUY" for t in trades) != 1
                or any(t.get("token_id") != token for t in trades)
                or any(not a or not b or not opened <= a <= cutoff or not a <= b <= cutoff for a, b in times)):
            excluded["incomplete_or_noncausal_ledger"] += 1
            continue
        # Mutable position status/closed_at never determines an as-of label.
        # A SELL is terminal only when its immutable released cost closes BUY.
        buy_cost = -float(trades[0]["net_cash_flow_usd"])
        released_cost = sum(float(t["net_cash_flow_usd"]) - float(t.get("realized_pnl_usd") or 0)
                            for t in trades[1:] if t["side"] == "SELL")
        pnl = sum(float(t["net_cash_flow_usd"]) for t in trades)
        if not all(map(math.isfinite, (buy_cost, released_cost, pnl))) or buy_cost <= 0:
            excluded["invalid_ledger_cash"] += 1
            continue
        terminal_sell = trades[-1]["side"] == "SELL" and math.isclose(
            released_cost, buy_cost, rel_tol=1e-7, abs_tol=1e-7)
        if trades[-1]["side"] == "WRITEOFF":
            event_type = "writeoff_exit"
            end_at, censor_type = times[-1][0], None
        elif terminal_sell:
            event_type = "profit_exit" if pnl > 0 else "loss_exit"
            end_at, censor_type = times[-1][0], None
        else:
            mark_rows = _rows(db, "SELECT token_id,observed_at,recorded_at,raw_json,price_usd "
                                  "FROM token_snapshots WHERE token_id=? AND observed_at<=? "
                                  "AND recorded_at<=? ORDER BY observed_at DESC LIMIT 64",
                                  (token, cutoff_sql, cutoff_sql))
            valid_marks = []
            for mark in mark_rows:
                try:
                    mark_pair = json.loads(mark.get("raw_json") or "{}").get("pair", {}).get("pairAddress")
                except (TypeError, ValueError, AttributeError):
                    mark_pair = None
                try:
                    price = float(mark.get("price_usd"))
                except (TypeError, ValueError):
                    price = 0
                mark_time, available = _time(mark.get("observed_at")), _time(mark.get("recorded_at"))
                if (mark_pair == row.get("pair_address") and math.isfinite(price) and price > 0
                        and mark_time and available and opened <= mark_time <= available <= cutoff):
                    valid_marks.append(mark)
            latest_mark = valid_marks[0] if valid_marks else None
            mark_at = _time(latest_mark.get("observed_at")) if latest_mark else None
            partial_at = max((a for a, _ in times[1:] if a), default=opened)
            if not mark_at:
                excluded["open_no_asof_pool_price"] += 1
                continue
            end_at = max(mark_at, partial_at, opened)
            event_type = None
            censor_type = "administrative_cutoff" if (cutoff - mark_at).total_seconds() <= 30 else "data_gap"
            if censor_type == "administrative_cutoff":
                end_at = cutoff
        duration = (end_at - opened).total_seconds()
        if duration < 0:
            excluded["negative_duration"] += 1
            continue
        result["samples"].append(dict(
            sample_id=f"duration:{definition_version}:{row['shadow_cohort_id']}:{token}",
            definition_version=definition_version, token_id=token, arm_id=row["arm_id"],
            shadow_cohort_id=row["shadow_cohort_id"], episode_no=row["episode_no"],
            feature_snapshot_id=row["feature_snapshot_id"], feature_observed_at=row["feature_observed_at"],
            feature_recorded_at=row["feature_recorded_at"], entry_at=row["opened_at"],
            event_at=end_at.isoformat().replace("+00:00", "Z"), event_type=event_type,
            censor_type=censor_type, duration_seconds=duration,
            bin_key=bin_key,
            ledger_ids=[t["id"] for t in trades],
            available_at=(cutoff if censor_type else max(b for _, b in times if b)).isoformat().replace("+00:00", "Z"),
        ))
    result["excluded"] = dict(excluded)
    result["cohort_bounds"] = [low, high]
    return result


def _cif(samples: Sequence[Mapping[str, Any]], horizons: Sequence[int]) -> dict[str, dict[str, float]]:
    event_rows = [(float(s["duration_seconds"]), str(s["event_type"])) for s in samples if s.get("event_type")]
    censor_rows = [float(s["duration_seconds"]) for s in samples if not s.get("event_type")]
    times = sorted({t for t, _ in event_rows} | set(censor_rows))
    survival, cif = 1.0, Counter()
    out: dict[float, dict[str, float]] = {}
    for t in times:
        risk = sum(float(s["duration_seconds"]) >= t for s in samples)
        if risk <= 0:
            continue
        events = Counter(kind for duration, kind in event_rows if duration == t)
        total = sum(events.values())
        if total:
            for kind, n in events.items():
                cif[kind] += survival * n / risk
            survival *= 1.0 - total / risk
        out[t] = dict(cif)
    result = {}
    for horizon in horizons:
        latest = max((t for t in out if t <= horizon), default=None)
        values = out.get(latest, {}) if latest is not None else {}
        result[str(horizon)] = {k: float(values.get(k, 0.0)) for k in sorted({s.get("event_type") for s in samples if s.get("event_type")})}
    return result


def seal_duration_risk_model(source: Mapping[str, Any], *, trained_at: str,
                             minimum_samples: int = 20) -> dict:
    cutoff, trained = _time(source.get("cutoff_at")), _time(trained_at)
    if not cutoff or not trained or cutoff > trained or not 1 <= minimum_samples <= 256:
        raise ValueError("training must follow bounded deployment cutoff")
    sealed, seen, seen_tokens = [], set(), set()
    for sample in source.get("samples", []):
        vals = [_time(sample.get(k)) for k in ("feature_observed_at", "feature_recorded_at", "entry_at", "event_at", "available_at")]
        if (not all(vals) or not vals[0] <= vals[1] <= vals[2] <= vals[3]
                or vals[3] > cutoff or vals[4] > cutoff
                or sample.get("sample_id") in seen or sample.get("token_id") in seen_tokens
                or not sample.get("bin_key")
                or (sample.get("event_type") is None) == (sample.get("censor_type") is None)):
            continue
        seen.add(sample["sample_id"])
        seen_tokens.add(sample["token_id"])
        sealed.append(dict(sample))
    model = dict(schema="observable-terminal-competition-duration/v1", model_id=None, sealed=True,
                 cutoff_at=source["cutoff_at"], trained_at=trained_at,
                 definition_version=source.get("definition_version"), samples=sealed,
                 sealed_sample_ids=[s["sample_id"] for s in sealed],
                 sample_status="sufficient_sample" if len(sealed) >= minimum_samples else "insufficient_sample",
                 minimum_samples=minimum_samples, horizons_seconds=[300, 900, 3600],
                 cumulative_incidence={key: _cif([s for s in sealed if s.get("bin_key") == key], (300, 900, 3600))
                                      for key in sorted({s["bin_key"] for s in sealed})},
                 bins=sorted({s["bin_key"] for s in sealed}),
                 bin_sample_status={key: ("sufficient_sample" if sum(s.get("bin_key") == key for s in sealed) >= minimum_samples else "insufficient_sample")
                                    for key in sorted({s["bin_key"] for s in sealed})},
                 event_counts=dict(Counter(s.get("event_type") for s in sealed if s.get("event_type"))),
                 right_censored=sum(not s.get("event_type") for s in sealed),
                 excluded=dict(source.get("excluded", {})), scanned_cohorts=source.get("scanned_cohorts"),
                 cohort_bounds=source.get("cohort_bounds"),
                 outcome_basis="observable Paper ledger terminal outcomes with administrative/data-gap censoring",
                 limitation="not market death or causal alpha; bounded mixed-exit sample; data-gap censoring may be informative")
    model["data_gap_fraction_by_bin"] = {
        key: sum(s.get("censor_type") == "data_gap" for s in sealed if s["bin_key"] == key)
             / sum(s["bin_key"] == key for s in sealed) for key in model["bins"]}
    # Separate stress calculation: a lost observation is an adverse competitor,
    # not a fabricated writeoff. Ordinary CIF remains available for comparison.
    model["gap_sensitivity"] = {key: _cif([
        {**s, "event_type": "observation_gap"} if s.get("censor_type") == "data_gap" else s
        for s in sealed if s["bin_key"] == key], (300, 900, 3600)) for key in model["bins"]}
    digest = dict(model)
    digest["model_id"] = None
    model["model_id"] = hashlib.sha256(json.dumps(digest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return model


def duration_risk_context(model: Mapping[str, Any], *, token_id: str, liquidity_usd: Any,
                          observed_at: str, recorded_at: str, decision_at: str) -> dict:
    cutoff, trained, observed, recorded, decision = map(_time, (model.get("cutoff_at"), model.get("trained_at"), observed_at, recorded_at, decision_at))
    if (model.get("sealed") is not True or not all((cutoff, trained, observed, recorded, decision))
            or not cutoff <= trained <= decision or not trained <= observed <= recorded <= decision
            or (decision - observed).total_seconds() > 30):
        return {"sample_status": "noncausal_or_stale_model", "token_id": token_id}
    key = _bin(token_id, liquidity_usd)
    bucket = model.get("cumulative_incidence", {}).get(key)
    maturity = model.get("bin_sample_status", {}).get(key, "insufficient_sample")
    if not key or bucket is None:
        return {"sample_status": "insufficient_bin_sample", "token_id": token_id, "bin_key": key}
    return {"model_id": model.get("model_id"), "token_id": token_id, "bin_key": key, "sealed": True,
            "cutoff_at": model["cutoff_at"], "trained_at": model["trained_at"],
            "observed_at": observed_at, "recorded_at": recorded_at,
            "sample_status": maturity,
            "cumulative_incidence": bucket,
            "gap_sensitivity": model["gap_sensitivity"][key],
            "data_gap_fraction": model["data_gap_fraction_by_bin"][key],
            "event_counts": model.get("event_counts", {}),
            "right_censored": model.get("right_censored", 0)}
