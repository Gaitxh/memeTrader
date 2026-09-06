"""Bounded read-only historical research; never imports Store or rewrites history.

Run once: .venv/Scripts/python.exe scripts/analyze_strategy_history_20260907.py
Offline: add --replay data/research/20260907/extract.json.gz
Each SQLite SELECT is fetched and released before the next 2,000-row chunk.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
import time


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/20260907"
PREFIX = "chain_meme_trader_"
CHUNK = 2000
ROW_LIMIT = 500_000
STATEMENT_SECONDS = 2.0


def dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc) if value else None


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def eligible(row, cutoff):
    # Require both economic and local availability timestamps where present.
    for name in ("recorded_at", "created_at", "registered_at", "code_registered_at", "opened_at",
                 "evaluated_at", "assessed_at", "completed_at", "enrolled_at", "activated_at"):
        if row.get(name) and dt(row[name]) > cutoff:
            return False
    return True


def qname(name):
    return '"' + name.replace('"', '""') + '"'


def extract():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    path = Path(config["database"])
    if not path.is_absolute():
        path = ROOT / path
    cutoff = utcnow()
    cutoff_dt = dt(cutoff)
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    deadline = [0.0]
    con.set_progress_handler(lambda: int(time.monotonic() > deadline[0]), 10000)
    query_log = []

    def query(sql, params=()):
        began = time.monotonic()
        deadline[0] = began + STATEMENT_SECONDS
        try:
            cursor = con.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            return rows
        finally:
            query_log.append({"seconds": time.monotonic() - began, "rows_sql": sql[:160]})

    schema = query("SELECT name,type,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index')")
    names = {row["name"] for row in schema if row["type"] == "table"}
    columns = {}
    desired = {n for n in names if n.endswith(("_registrations", "_positions", "_trades"))}
    desired |= {"positions", "trades", "paper_account", "onchain_paper_exploration_account",
                "onchain_paper_narrative_runner_account", "token_information_confirmation_paper_account"}
    desired |= {PREFIX + n for n in (
        "policy_additions", "v6_activations", "primary_stops", "paper_funding_activations",
        "fixed_funding_restorations", "capital_credits", "accounting_contaminations",
        "accounting_contamination_resolutions", "market_fill_corrections",
        "market_fill_correction_supersessions", "market_fill_correction_resolutions", "position_voids")}
    desired |= {"shadow_event_cohorts", "shadow_event_outcomes", "information_first_shadow_cohorts",
                "information_first_shadow_outcomes", "onchain_only_shadow_cohorts", "onchain_only_shadow_results",
                "solana_holder_shadow_cohorts", "solana_holder_shadow_results",
                "route_preflight_deferred_retry_shadow_results", "agent_shadow_review_results",
                "token_universe_fixed_target_execution_results"}
    # Existing maximum/minimum return fields are coverage only. No new path calculation.
    desired |= {n for n in names if "backtest" in n}
    tables, coverage, frontiers = {}, {}, {}
    for n in sorted(desired & names):
        columns[n] = query("PRAGMA table_info(" + qname(n) + ")")
        frontiers[n] = query("SELECT max(rowid) AS max_rowid FROM " + qname(n))[0]["max_rowid"] or 0
    snapshot_frontier = query("SELECT max(id) AS max_id FROM token_snapshots")[0]["max_id"] if "token_snapshots" in names else None
    for n in sorted(desired):
        if n not in names:
            coverage[n] = {"status": "absent", "rows": 0}
            continue
        selected = [x["name"] for x in columns[n] if not x["name"].endswith("_json")]
        if n.endswith("_registrations"):
            selected += [x["name"] for x in columns[n] if x["name"] == "definition_json"]
        if n == PREFIX + "policy_additions":
            selected += ["policy_json"]
        sqlcols = ",".join(qname(x) for x in selected)
        rows, last, read, status = [], 0, 0, "complete"
        try:
            while last < frontiers[n]:
                batch = query("SELECT rowid AS _rowid," + sqlcols + " FROM " + qname(n)
                              + " WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?", (last, frontiers[n], CHUNK))
                if not batch:
                    break
                last = batch[-1]["_rowid"]
                read += len(batch)
                rows.extend(row for row in batch if eligible(row, cutoff_dt))
                if read >= ROW_LIMIT and last < frontiers[n]:
                    status = "incomplete_row_cap"
                    break
                time.sleep(0.01)
        except sqlite3.OperationalError as exc:
            status = "incomplete_resource_limit:" + str(exc)
        tables[n] = rows
        coverage[n] = {"status": status, "rows": len(rows), "rows_read": read,
                       "max_rowid_at_start": frontiers[n], "last_rowid_read": last,
                       "projection": selected}
        print(json.dumps({"table": n, "rows": len(rows), "status": status}), flush=True)
    activations = query("SELECT key,value_json,updated_at FROM kv WHERE key >= ? AND key < ?",
                        ("chain-paper-execution:activation:", "chain-paper-execution:activation;")) if "kv" in names else []
    tables["execution_setting_activations"] = [r for r in activations if dt(json.loads(r["value_json"])["activated_at"]) <= cutoff_dt]

    # Indexed newest account snapshots, never scan the large snapshot history.
    policies = set()
    for row in tables.get(PREFIX + "registrations", []):
        definition = json.loads(row["definition_json"])
        policies.update((row["definition_version"], p["arm_id"]) for p in definition.get("policies", []))
    policies.update((r["definition_version"], r["arm_id"]) for r in tables.get(PREFIX + "policy_additions", []))
    latest = []
    if PREFIX + "account_snapshots" in names:
        for version, arm in sorted(policies):
            latest.extend(query("SELECT id,definition_version,arm_id,recorded_at,cash_usd,realized_pnl_usd,"
                                "open_position_count,closed_position_count,written_off_position_count,valuation_status,"
                                "ledger_trade_frontier_id FROM chain_meme_trader_account_snapshots "
                                "WHERE definition_version=? AND arm_id=? AND recorded_at<=? ORDER BY recorded_at DESC,id DESC LIMIT 1",
                                (version, arm, cutoff)))
    tables["latest_chain_account_snapshots"] = latest
    con.close()
    archives = []
    for archive_path in sorted((ROOT / "data").glob("*.sqlite3")):
        if archive_path == path:
            continue
        con = sqlite3.connect(archive_path.as_uri() + "?mode=ro", uri=True, timeout=1, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.set_progress_handler(lambda: int(time.monotonic() > deadline[0]), 10000)
        archive_schema = query("SELECT name,type,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index')")
        archive_names = {r["name"] for r in archive_schema if r["type"] == "table"}
        archive_tables, archive_coverage = {}, {}
        for n in sorted(archive_names):
            if n not in ("positions", "trades", "paper_account") and not n.endswith(("_positions", "_trades", "_registrations")):
                continue
            cols = [r["name"] for r in query("PRAGMA table_info(" + qname(n) + ")") if not r["name"].endswith("_json")]
            frontier = query("SELECT max(rowid) AS frontier FROM " + qname(n))[0]["frontier"] or 0
            last, rows, status = 0, [], "complete"
            try:
                while last < frontier:
                    batch = query("SELECT rowid AS _rowid," + ",".join(qname(x) for x in cols) + " FROM " + qname(n)
                                  + " WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?", (last, frontier, CHUNK))
                    if not batch:
                        break
                    last = batch[-1]["_rowid"]
                    rows.extend(r for r in batch if eligible(r, cutoff_dt))
                    if len(rows) >= ROW_LIMIT and last < frontier:
                        status = "incomplete_row_cap"
                        break
                    time.sleep(.01)
            except sqlite3.OperationalError as exc:
                status = "incomplete_resource_limit:" + str(exc)
            archive_tables[n] = rows
            archive_coverage[n] = {"status": status, "rows": len(rows), "frontier_rowid": frontier}
        archives.append({"database": archive_path.name, "bytes": archive_path.stat().st_size, "schema": archive_schema,
                         "rejected_r5_false_positive_paper": archive_path.name.endswith("_r5.sqlite3"),
                         "tables": archive_tables, "coverage": archive_coverage})
        con.close()
    return {"cutoff_utc": cutoff, "extraction_completed_utc": utcnow(), "database": str(path),
            "database_size_bytes": path.stat().st_size, "snapshot_max_id_at_extraction_start": snapshot_frontier,
            "tables": tables, "coverage": coverage, "schema": schema, "columns": columns,
            "frontiers": frontiers, "query_count": len(query_log),
            "max_query_seconds": max(r["seconds"] for r in query_log),
            "sum_query_seconds": sum(r["seconds"] for r in query_log),
            "archive_databases": archives}


def pct(values, quantile):
    if not values:
        return None
    s = sorted(values)
    z = (len(s) - 1) * quantile
    return s[int(z)] + (s[min(int(z) + 1, len(s) - 1)] - s[int(z)]) * (z - int(z))


def metrics(episodes, field="raw_realized_pnl_usd"):
    closed = [r for r in episodes if r["is_full_roundtrip"]]
    values = [r[field] for r in closed]
    wins = [x for x in values if x > 1e-9]
    losses = [x for x in values if x < -1e-9]
    sorted_values = sorted(values, reverse=True)
    token = defaultdict(float)
    hour = defaultdict(float)
    for r in closed:
        token[r["token_id"]] += r[field]
        hour[r["opened_at"][:13]] += r[field]
    token_gains = sorted([x for x in token.values() if x > 0], reverse=True)
    token_ranked = sorted(token.values(), reverse=True)
    holds = [r["hold_minutes"] for r in closed if r["hold_minutes"] is not None]
    trimmed = sorted(values)
    trim_n = int(len(values) * 0.1)
    if trim_n:
        trimmed = trimmed[trim_n:-trim_n]
    return {"positions": len(episodes), "buys": sum(r["buy_count"] for r in episodes),
            "sells": sum(r["sell_count"] for r in episodes), "writeoffs": sum(r["writeoff_count"] for r in episodes),
            "full_roundtrips": len(closed), "open_at_cutoff": sum(r["status_at_cutoff"] == "open" for r in episodes),
            "positions_missing_buy": sum(r["buy_count"] == 0 for r in episodes),
            "unique_tokens": len({r["token_id"] for r in episodes}), "closed_unique_tokens": len(token),
            "raw_realized_pnl_all_positions_usd": sum(r[field] for r in episodes),
            "closed_pnl_usd": sum(values), "wins": len(wins), "losses": len(losses),
            "win_rate": len(wins) / len(values) if values else None,
            "expectancy_usd": statistics.mean(values) if values else None,
            "median_pnl_usd": statistics.median(values) if values else None,
            "trimmed10_mean_pnl_usd": statistics.mean(trimmed) if trimmed else None,
            "profit_factor": sum(wins) / -sum(losses) if losses else None,
            "profit_factor_status": "finite" if losses else "no_losses_denominator" if wins else "no_closed_outcomes",
            "pnl_p05_usd": pct(values, .05), "pnl_p95_usd": pct(values, .95),
            "worst_pnl_usd": min(values) if values else None, "best_pnl_usd": max(values) if values else None,
            "remove_best1_pnl_usd": sum(sorted_values[1:]) if len(values) > 1 else None,
            "remove_best3_pnl_usd": sum(sorted_values[3:]) if len(values) > 3 else None,
            "remove_best1_token_pnl_usd": sum(token_ranked[1:]) if len(token_ranked) > 1 else None,
            "remove_best3_token_pnl_usd": sum(token_ranked[3:]) if len(token_ranked) > 3 else None,
            "top1_trade_share_of_positive_pnl": max(wins) / sum(wins) if wins else None,
            "top1_token_share_of_positive_token_pnl": max(token_gains) / sum(token_gains) if token_gains else None,
            "top3_token_share_of_positive_token_pnl": sum(token_gains[:3]) / sum(token_gains) if token_gains else None,
            "hold_minutes_median": statistics.median(holds) if holds else None,
            "hold_minutes_p95": pct(holds, .95), "entry_hour_blocks": len(hour),
            "positive_entry_hour_blocks": sum(x > 0 for x in hour.values()),
            "worst_entry_hour_pnl_usd": min(hour.values()) if hour else None,
            "exit_types": dict(Counter(r["close_reason"] or "unknown" for r in closed))}


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def analyze(data, *, preserve_positions=False):
    t = data["tables"]
    cutoff = dt(data["cutoff_utc"])
    registry, policies = {}, {}
    activations = {r["definition_version"]: r for r in t.get(PREFIX + "v6_activations", [])}
    stops = {r["definition_version"]: r for r in t.get(PREFIX + "primary_stops", [])}
    for r in t.get(PREFIX + "registrations", []):
        definition = json.loads(r["definition_json"])
        v = r["definition_version"]
        registry[v] = {"registered_at": r["registered_at"], "definition": definition}
        for p in definition.get("policies", []):
            policies[(v, p["arm_id"])] = {**p, "activated_at": activations.get(v, {}).get("activated_at", r["registered_at"]),
                "_activation_basis": "activation_table" if v in activations else "registration_time_proxy_only"}
    for r in t.get(PREFIX + "policy_additions", []):
        policies[(r["definition_version"], r["arm_id"])] = {**json.loads(r["policy_json"]),
            "activated_at": r["activated_at"], "behavior_contract_hash": r["behavior_contract_hash"], "_activation_basis": "addition_activation"}
    key = lambda r: (r["definition_version"], r["arm_id"], r["shadow_cohort_id"])
    contamin = {key(r): {**r, "resolution_status": "ACTIVE", "revision": 0} for r in t.get(PREFIX + "accounting_contaminations", [])}
    for r in t.get(PREFIX + "accounting_contamination_resolutions", []):
        if key(r) in contamin and r["revision"] > contamin[key(r)]["revision"]:
            contamin[key(r)].update(r)
    voids = {key(r) for r in t.get(PREFIX + "position_voids", [])}
    corrections = {r["source_trade_id"]: {**r, "revision": 0} for r in t.get(PREFIX + "market_fill_corrections", [])}
    for r in t.get(PREFIX + "market_fill_correction_supersessions", []):
        if r["source_trade_id"] in corrections:
            corrections[r["source_trade_id"]].update({**r, "revision": 1})
    for r in t.get(PREFIX + "market_fill_correction_resolutions", []):
        if r["source_trade_id"] in corrections and r["revision"] > corrections[r["source_trade_id"]]["revision"]:
            corrections[r["source_trade_id"]].update(r)
    correction_by_episode = defaultdict(list)
    for r in corrections.values():
        correction_by_episode[key(r)].append(r)
    trades = defaultdict(list)
    for r in t.get(PREFIX + "trades", []):
        trades[key(r)].append(r)
    positions = {key(r): r for r in t.get(PREFIX + "positions", [])}
    execution_activations = sorted([json.loads(r["value_json"]) for r in t.get("execution_setting_activations", [])], key=lambda r: r["activated_at"])

    def cost_at(at):
        result = "legacy_activation_not_recorded"
        for a in execution_activations:
            if dt(a["activated_at"]) <= dt(at):
                result = a["activation_key"]
        return result

    episodes = []
    for k in sorted(positions.keys() | trades.keys()):
        pos = positions.get(k, {})
        fills = sorted(trades.get(k, []), key=lambda r: (r["created_at"], r["id"]))
        buys = [r for r in fills if r["side"] == "BUY"]
        sells = [r for r in fills if r["side"] == "SELL"]
        writeoffs = [r for r in fills if r["side"] == "WRITEOFF"]
        opened = pos.get("opened_at") or (buys[0]["created_at"] if buys else fills[0]["created_at"])
        closed = pos.get("closed_at")
        closed_by_cutoff = bool(closed and dt(closed) <= cutoff and pos.get("status") in ("closed", "written_off"))
        raw = sum(float(r["realized_pnl_usd"] or 0) for r in fills)
        issues = []
        if contamin.get(k, {}).get("resolution_status") == "ACTIVE":
            issues.append("recorded_active_accounting_contamination")
        if k in voids:
            issues.append("recorded_position_void")
        if k in correction_by_episode:
            issues.append("recorded_market_fill_correction_history")
        # Exclusion is conservative and descriptive; never declare remaining rows clean.
        net_cash = sum(float(r["net_cash_flow_usd"] or 0) for r in fills)
        full = bool(closed_by_cutoff and len(buys) == 1 and (sells or writeoffs))
        correction = sum(float(r["realized_adjustment_usd"] or 0) for r in correction_by_episode[k])
        exits = sells + writeoffs
        costs = sorted({cost_at(r["created_at"]) for r in fills})
        episodes.append({"definition_version": k[0], "arm_id": k[1], "shadow_cohort_id": k[2],
            "token_id": pos.get("token_id") or fills[0]["token_id"], "source_buy_trade_id": pos.get("source_buy_trade_id"),
            "ledger_buy_trade_id": buys[0]["id"] if buys else None, "first_trade_id": fills[0]["id"] if fills else None,
            "last_trade_id": fills[-1]["id"] if fills else None, "entry_snapshot_id": pos.get("entry_snapshot_id"),
            "entry_signal_price_usd": pos.get("entry_signal_price_usd"), "entry_execution_price_usd": pos.get("entry_execution_price_usd"),
            "stake_usd": pos.get("stake_usd"), "opened_at": opened, "closed_at": closed if closed_by_cutoff else None,
            "status_at_cutoff": pos.get("status") if closed_by_cutoff else "open" if pos else "position_missing",
            "is_full_roundtrip": full, "buy_count": len(buys), "sell_count": len(sells), "writeoff_count": len(writeoffs),
            "raw_realized_pnl_usd": raw, "roundtrip_net_cash_usd": net_cash if full else None,
            "closed_ledger_reconciliation_error_usd": raw - net_cash if full else None,
            "recorded_correction_adjustment_usd": correction, "raw_plus_recorded_adjustment_usd": raw + correction,
            "known_history_issue": bool(issues), "known_history_issue_flags": issues,
            "recorded_contamination_status": contamin.get(k, {}).get("resolution_status", "no_record"),
            "correction_outcomes": [r["replacement_outcome"] for r in correction_by_episode[k]],
            "entry_reason": pos.get("entry_reason") or (buys[0]["reason"] if buys else "unknown"),
            "close_reason": pos.get("close_reason", "") if closed_by_cutoff else "",
            "last_exit_reason": exits[-1]["reason"] if exits else "",
            "hold_minutes": (dt(closed) - dt(opened)).total_seconds() / 60 if closed_by_cutoff else None,
            "open_age_hours": (cutoff - dt(opened)).total_seconds() / 3600,
            "entry_cost_activation": cost_at(opened), "fill_cost_activations": costs,
            "mixed_recorded_execution_activations": len(costs) > 1})

    grouped = defaultdict(list)
    for r in episodes:
        grouped[(r["definition_version"], r["arm_id"])].append(r)
    account = {(r["definition_version"], r["arm_id"]): r for r in t.get("latest_chain_account_snapshots", [])}
    arms = []
    for k in sorted(policies.keys() | grouped.keys()):
        p = policies.get(k, {})
        reg = registry.get(k[0], {})
        start = p.get("activated_at") or reg.get("registered_at")
        stop = stops.get(k[0], {}).get("stopped_at")
        activation_proven = p.get("_activation_basis") in ("activation_table", "addition_activation")
        age = (cutoff - dt(start)).total_seconds() / 3600 if start and activation_proven else None
        latest_registered_version = max(registry, key=lambda v: registry[v]["registered_at"])
        active_age = max(0, ((min(dt(stop), cutoff) if stop else cutoff) - dt(start)).total_seconds() / 3600) if start and activation_proven and (stop or k[0] == latest_registered_version) else None
        rows = grouped[k]
        raw = metrics(rows)
        no_recorded_issue = metrics([r for r in rows if not r["known_history_issue"]])
        horizon = p.get("max_hold_minutes")
        matured = [r for r in rows if horizon is not None and r["open_age_hours"] * 60 >= float(horizon)]
        mature_closed = [r for r in matured if r["is_full_roundtrip"]]
        maturity = ("zero_buy" if not raw["buys"] else "few_buys_1_2" if raw["buys"] <= 2
                    else "descriptive_20_roundtrips_10_tokens" if raw["full_roundtrips"] >= 20 and raw["closed_unique_tokens"] >= 10
                    else "sparse_closed_or_clustered")
        evidence_label = "insufficient_or_confounded"
        if no_recorded_issue["full_roundtrips"] >= 20 and no_recorded_issue["closed_unique_tokens"] >= 10:
            if no_recorded_issue["closed_pnl_usd"] > 0 and (no_recorded_issue["remove_best3_pnl_usd"] or 0) > 0:
                evidence_label = "positive_descriptive_candidate_not_validated"
            elif no_recorded_issue["closed_pnl_usd"] <= 0:
                evidence_label = "negative_descriptive_sample_not_causal_failure"
        definition = reg.get("definition", {})
        arms.append({"definition_version": k[0], "arm_id": k[1], "canonical_id": p.get("canonical_id"),
            "name": p.get("name"), "strategy_number": p.get("strategy_number"), "strategy_revision": p.get("strategy_revision", 1),
            "family": p.get("family"), "entry_family": p.get("entry_family"), "exit_family": p.get("exit_family"),
            "contract_hash": p.get("behavior_contract_hash"),
            "research_policy_content_hash": hashlib.sha256(json.dumps({n:v for n,v in p.items() if not n.startswith("_") and n != "activated_at"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16],
            "registered_at": reg.get("registered_at"), "activated_at": start, "entry_stopped_at": stop,
            "activation_evidence_basis": p.get("_activation_basis", "unknown"),
            "registration_age_hours": (cutoff - dt(reg["registered_at"])).total_seconds() / 3600 if reg.get("registered_at") else None,
            "deployment_age_hours": age, "documented_active_entry_hours": active_age, "max_hold_minutes": horizon,
            "entries_old_enough_for_max_hold": len(matured), "mature_full_roundtrips": len(mature_closed),
            "execution_profile": definition.get("execution_profile", definition.get("execution")),
            "maturity": maturity, "evidence_label": evidence_label, "raw": raw,
            "exclude_known_recorded_issues_descriptive": no_recorded_issue,
            "known_history_issue_positions": sum(r["known_history_issue"] for r in rows),
            "account_latest": account.get(k), "cost_activations_seen": sorted({c for r in rows for c in r["fill_cost_activations"]})})

    versions = []
    for version, reg in registry.items():
        rows = [r for r in episodes if r["definition_version"] == version]
        version_arms = [r for r in arms if r["definition_version"] == version]
        versions.append({"definition_version": version, "registered_at": reg["registered_at"],
            "policy_arm_count": len(version_arms), "execution_profile": version_arms[0]["execution_profile"] if version_arms else None,
            "zero_buy_arms": sum(a["raw"]["buys"] == 0 for a in version_arms),
            "one_or_two_buy_arms": sum(1 <= a["raw"]["buys"] <= 2 for a in version_arms),
            "known_history_issue_positions": sum(r["known_history_issue"] for r in rows),
            "arm_projection_multiplier": len(rows) / len({r["token_id"] for r in rows}) if rows else None,
            **metrics(rows)})
    segments = []
    cost_groups = defaultdict(list)
    for r in episodes:
        cost_groups[(r["definition_version"], r["arm_id"], r["entry_cost_activation"], r["mixed_recorded_execution_activations"])].append(r)
    for (v, a, cost, mixed), rows in sorted(cost_groups.items()):
        segments.append({"definition_version": v, "arm_id": a, "entry_cost_activation": cost,
                         "mixed_execution_activations": mixed, **metrics(rows)})

    ancillary = []
    cohort_links = {
        "shadow_event_outcomes": ("shadow_event_cohorts", "cohort_id"),
        "information_first_shadow_outcomes": ("information_first_shadow_cohorts", "cohort_id"),
        "onchain_only_shadow_results": ("onchain_only_shadow_cohorts", "cohort_id"),
        "solana_holder_shadow_results": ("solana_holder_shadow_cohorts", "shadow_cohort_id"),
    }
    for name, rows in t.items():
        if name in (PREFIX + "positions", PREFIX + "trades") or name.startswith("latest_"):
            continue
        if not any(word in name for word in ("shadow", "paper", "backtest")) and name not in ("positions", "trades", "token_universe_fixed_target_execution_results"):
            continue
        if name.endswith("registrations") or name.endswith("activations"):
            continue
        if name in cohort_links:
            cohort_name, fk = cohort_links[name]
            cohort_rows = {r["id"]: r for r in t.get(cohort_name, [])}
            rows = [{**r, "definition_version": r.get("definition_version") or cohort_rows.get(r[fk], {}).get("definition_version")
                     or cohort_rows.get(r[fk], {}).get("version", "unknown_cohort_version"),
                     "token_id": r.get("token_id") or cohort_rows.get(r[fk], {}).get("token_id")} for r in rows]
        buckets = defaultdict(list)
        for r in rows:
            buckets[(r.get("definition_version", r.get("version", "unversioned")), r.get("horizon_minutes", "NA"))].append(r)
        if not rows:
            buckets[("no_rows", "NA")] = []
        for (v, h), group in buckets.items():
            vals = [float(r["realized_pnl_usd"]) for r in group if r.get("realized_pnl_usd") is not None]
            returns = [float(r["modeled_net_return"]) for r in group if r.get("modeled_net_return") is not None]
            raw_returns = [float(r["raw_return"]) for r in group if r.get("raw_return") is not None]
            ancillary.append({"table": name, "definition_version": v, "horizon_minutes": h, "rows": len(group),
                "coverage_status": data["coverage"].get(name, {}).get("status", "subset"),
                "status_counts": dict(Counter(str(r.get("terminal_status", r.get("status", r.get("terminal_state", "unknown")))) for r in group)),
                "side_counts": dict(Counter(r.get("side", "NA") for r in group)),
                "unique_tokens_directly_recorded": len({r["token_id"] for r in group if r.get("token_id")}),
                "realized_pnl_field_sum_usd": sum(vals) if vals else None,
                "modeled_net_return_count": len(returns), "modeled_net_return_median": statistics.median(returns) if returns else None,
                "modeled_net_return_mean": statistics.mean(returns) if returns else None,
                "modeled_net_return_p05": pct(returns, .05), "modeled_net_return_p95": pct(returns, .95),
                "raw_return_count": len(raw_returns), "raw_return_median": statistics.median(raw_returns) if raw_returns else None,
                "existing_maximum_return_nonnull": sum(r.get("maximum_return") is not None for r in group),
                "existing_minimum_return_nonnull": sum(r.get("minimum_return") is not None for r in group),
                "warning": "Separate contract/table view; never sum position and trade ledgers or treat shadow returns as fills."})

    legacy_paper = []
    for position_table, trade_table in [("onchain_paper_exploration_positions", "onchain_paper_exploration_trades"),
                                      ("onchain_paper_narrative_runner_positions", "onchain_paper_narrative_runner_trades")]:
        ledger = defaultdict(list)
        for r in t.get(trade_table, []):
            ledger[(r["definition_version"], r["shadow_cohort_id"])].append(r)
        legacy_groups = defaultdict(list)
        for p in t.get(position_table, []):
            fills = ledger.get((p["definition_version"], p["shadow_cohort_id"]), [])
            closed = bool(p.get("closed_at") and dt(p["closed_at"]) <= cutoff and p["status"] in ("closed", "written_off"))
            buys = sum(r["side"] == "BUY" for r in fills)
            legacy_groups[p["definition_version"]].append({"token_id": p["token_id"], "opened_at": p["opened_at"],
                "is_full_roundtrip": closed and buys == 1, "status_at_cutoff": p["status"] if closed else "open",
                "buy_count": buys, "sell_count": sum(r["side"] == "SELL" for r in fills),
                "writeoff_count": sum(r["side"] == "WRITEOFF" for r in fills),
                "raw_realized_pnl_usd": sum(float(r.get("realized_pnl_usd") or 0) for r in fills),
                "close_reason": p.get("close_reason", "unknown"),
                "hold_minutes": (dt(p["closed_at"]) - dt(p["opened_at"])).total_seconds() / 60 if closed else None})
        for v, rows in legacy_groups.items():
            legacy_paper.append({"table": position_table, "definition_version": v,
                                 "interpretation": "Separate historical execution contract; contamination completeness unknown.", **metrics(rows)})

    paired = []
    for (v, arm), rows in grouped.items():
        if "_candidate_" not in arm:
            continue
        control = arm.replace("_candidate_", "_control_")
        if (v, control) not in grouped:
            continue
        left = {(r["token_id"], r["shadow_cohort_id"], r["entry_cost_activation"]): r for r in rows if r["is_full_roundtrip"] and not r["known_history_issue"]}
        right = {(r["token_id"], r["shadow_cohort_id"], r["entry_cost_activation"]): r for r in grouped[(v, control)] if r["is_full_roundtrip"] and not r["known_history_issue"]}
        matched = left.keys() & right.keys()
        differences = [left[x]["raw_realized_pnl_usd"] - right[x]["raw_realized_pnl_usd"] for x in matched]
        paired.append({"definition_version": v, "candidate_arm": arm, "control_arm": control, "matched_closed_cohorts": len(matched),
            "matched_unique_tokens": len({x[0] for x in matched}), "candidate_closed_only": len(left.keys() - right.keys()),
            "control_closed_only": len(right.keys() - left.keys()), "mean_pnl_difference_usd": statistics.mean(differences) if differences else None,
            "median_pnl_difference_usd": statistics.median(differences) if differences else None,
            "sum_pnl_difference_usd": sum(differences), "warning": "Matched closed subset has exit-selection bias; not a randomized causal estimate."})
    reconciliation = [abs(r["closed_ledger_reconciliation_error_usd"]) for r in episodes if r["closed_ledger_reconciliation_error_usd"] is not None]
    archive_summary = []
    for archive in data.get("archive_databases", []):
        for name, rows in archive["tables"].items():
            groups = defaultdict(list)
            for r in rows:
                groups[(r.get("definition_version", "unversioned"), r.get("arm_id", "NA"))].append(r)
            if not rows:
                groups[("no_rows", "NA")] = []
            for (v, a), values in groups.items():
                timestamps = [r.get("created_at", r.get("opened_at", r.get("registered_at"))) for r in values]
                timestamps = [x for x in timestamps if x]
                pnl = [float(r["realized_pnl_usd"]) for r in values if r.get("realized_pnl_usd") is not None]
                archive_summary.append({"database": archive["database"], "table": name, "definition_version": v, "arm_id": a,
                    "rows": len(values), "min_record_time": min(timestamps) if timestamps else None,
                    "max_record_time": max(timestamps) if timestamps else None,
                    "side_counts": dict(Counter(r.get("side", "NA") for r in values)),
                    "status_counts": dict(Counter(r.get("status", "not_recorded") for r in values)),
                    "unique_tokens": len({r["token_id"] for r in values if r.get("token_id")}),
                    "raw_realized_pnl_field_sum_usd": sum(pnl) if pnl else None,
                    "raw_pnl_status": "ledger_field_only" if pnl else "field_absent_or_no_rows_not_inferred",
                    "coverage": archive["coverage"][name], "rejected_r5_false_positive_paper": archive["rejected_r5_false_positive_paper"],
                    "interpretation": "Database-isolated historical description; duplicate lineage unverified; never pool with r6 or claim effectiveness."})
    summary = {"cutoff_utc": data["cutoff_utc"], "database": data["database"],
        "extraction_completed_utc": data["extraction_completed_utc"],
        "snapshot_max_id_at_extraction_start": data["snapshot_max_id_at_extraction_start"],
        "frontiers": data["frontiers"], "query_count": data["query_count"], "max_query_seconds": data["max_query_seconds"],
        "sum_query_seconds": data["sum_query_seconds"], "coverage": data["coverage"],
        "registered_versions": len(registry), "version_arm_contracts": len(arms), "positions_evidence_rows": len(episodes),
        "max_closed_ledger_reconciliation_error_usd": max(reconciliation, default=None),
        "closed_ledger_error_above_1cent": sum(x > .01 for x in reconciliation),
        "effective_correction_count": len(corrections), "active_accounting_contamination_count": sum(r["resolution_status"] == "ACTIVE" for r in contamin.values()),
        "void_count": len(voids), "execution_setting_activations": execution_activations,
        "archive_database_statistics": archive_summary,
        "no_backtest_named_tables": not any("backtest" in r["name"] for r in data["schema"] if r["type"] == "table"),
        "versions": versions, "ancillary": ancillary, "legacy_paper_statistics": legacy_paper, "paired_candidate_controls": paired}
    if not preserve_positions or not (OUT / "positions_evidence.csv").exists():
        write_csv(OUT / "positions_evidence.csv", episodes)
    write_csv(OUT / "version_statistics.csv", versions)
    write_csv(OUT / "arm_statistics.csv", [{**{k:v for k,v in a.items() if k not in ("raw", "exclude_known_recorded_issues_descriptive")},
        **{"raw_"+k:v for k,v in a["raw"].items()}, **{"excluded_"+k:v for k,v in a["exclude_known_recorded_issues_descriptive"].items()}} for a in arms])
    write_csv(OUT / "cost_segment_statistics.csv", segments)
    write_csv(OUT / "ancillary_history_coverage.csv", ancillary)
    write_csv(OUT / "paired_candidate_controls.csv", paired)
    write_csv(OUT / "archive_database_statistics.csv", archive_summary)
    write_csv(OUT / "legacy_paper_statistics.csv", legacy_paper)
    (OUT / "arm_statistics.json").write_text(json.dumps(arms, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, help="Analyze saved extract without opening production DB")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.replay:
        with gzip.open(args.replay, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
    else:
        data = extract()
        with gzip.open(OUT / "extract.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
    summary = analyze(data, preserve_positions=bool(args.replay))
    print(json.dumps({k: summary[k] for k in ("cutoff_utc", "registered_versions", "version_arm_contracts", "positions_evidence_rows",
        "max_query_seconds", "sum_query_seconds", "closed_ledger_error_above_1cent")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
