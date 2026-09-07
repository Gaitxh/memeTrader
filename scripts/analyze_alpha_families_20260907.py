"""Read-only strategy-behavior family map for the current Paper funding period.

It deliberately reads the frozen 20260907 extract only for its cutoff/frontier,
then queries the current-period delta through a SQLite ``mode=ro`` connection.
No Store object, model, market scan, or runtime operation is used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "chain-meme-trader/funding-20260906-v002-final-1000"
MAP = ROOT / "docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/RESOURCE_BOUND_STRATEGY_MAP.json"
FROZEN = ROOT / "data/research/20260907/summary.json"
BOUNDARY = ROOT / "data/research/alpha_diagnosis_20260907/BOUNDARY.json"
OUT = ROOT / "data/research/alpha_diagnosis_20260907/families"
CSV_OUT = ROOT / "docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/STRATEGY_BEHAVIOR_FAMILIES.csv"
METHOD_OUT = ROOT / "docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/FAMILIES_METHOD.md"

# Fields that can alter admission/dispatch, liquidation, or Paper economics.
ENTRY_KEYS = frozenset({
    "entry_family", "entry_gate", "entry_match_mode", "entry_filter",
    "entry_contract", "replacement_input_contract", "required_inputs", "entry_revision_kind",
    "wallet_entry_policy", "wallet_entry_role", "probe_kind", "probe_policy", "paired_entry_group",
    "paired_entry_size", "paired_opportunity_group", "paired_opportunity_semantics",
    "opportunity_control_arm_id", "require_post_decision_observation", "no_historical_backfill",
})
EXIT_KEYS = frozenset({
    "exit_family", "exit_mode", "hard_stop_return", "max_hold_minutes", "take_profit",
    "take_profit_return", "trailing_activate_return", "trailing_drawdown", "conditional_exit",
    "capital_exit_kind", "capital_exit_policy", "capital_experiment", "capital_revision_kind",
    "revision_exit_kind", "revision_exit_policy", "wallet_exit_kind", "wallet_exit_policy",
    "runner_epoch_after_partial", "runner_review_minutes", "zero_activity_grace_minutes",
    "flow_grace_minutes", "dex_positive_trailing_drawdown", "dex_research_delay_minutes",
    "dex_research_min_buy_ratio", "dex_research_min_volume_5m_usd", "emergency_liquidity_usd",
    "minimum_buy_ratio", "exact_risk_alerts",
})
EXECUTION_KEYS = frozenset({"execution_profile", "notional_usd", "shadow_notional_usd", "_execution"})


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:16]


def picked(policy, keys):
    return {k: policy[k] for k in sorted(keys) if k in policy and policy[k] is not None}


def dispatch_shape(policy):
    """Name the code path, rather than trusting a display family/name."""
    filt = policy.get("entry_filter") or {}
    mode = policy.get("entry_match_mode") or "main_snapshot_dispatch"
    contract = filt.get("contract")
    if contract == "resource-bound/20260907-v1":
        return {"path": "resource_bound_isolated_pattern", "contract": contract,
                "direction": filt.get("direction"), "control": filt.get("control"),
                "mode": mode}
    if mode == "isolated_pattern_observer":
        return {"path": "forward_pattern_isolated", "contract": contract,
                "direction": filt.get("direction"), "control": filt.get("control"), "mode": mode}
    if mode == "isolated_cohort_observer":
        return {"path": "cohort_isolated", "contract": contract,
                "direction": filt.get("direction"), "mode": mode}
    if mode == "dex_visible":
        return {"path": "main_snapshot_dex_visible", "mode": mode,
                "entry_family": policy.get("entry_family")}
    return {"path": "main_snapshot_exact_family", "mode": mode,
            "entry_family": policy.get("entry_family"), "entry_gate": policy.get("entry_gate")}


def policy_fingerprints(policy):
    entry = {"dispatch": dispatch_shape(policy), "fields": picked(policy, ENTRY_KEYS)}
    exit_ = picked(policy, EXIT_KEYS)
    execution = picked(policy, EXECUTION_KEYS)
    return digest(entry), digest(exit_), digest(execution), entry, exit_, execution


def connect_database():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    database = config["database"]
    path = Path(database)
    if not path.is_absolute():
        path = ROOT / path
    uri = "file:" + path.resolve().as_posix() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only=ON")
    return con, path


def load_policies(con, as_of):
    source = json.loads(MAP.read_text(encoding="utf-8"))
    policies = {p["arm_id"]: {**p, "_origin": "frozen_map", "_activated_at": p.get("forward_started_at")}
                for p in source["policies"]}
    # The only intended frozen-map delta is the six explicitly marked resource arms.
    rows = con.execute("""
        SELECT arm_id, activated_at, activation_snapshot_id, behavior_contract_hash, policy_json
        FROM chain_meme_trader_policy_additions
        WHERE definition_version=? AND activated_at<=?
        ORDER BY id
    """, (VERSION, as_of)).fetchall()
    for arm, activated, activation_snapshot, contract_hash, text in rows:
        p = json.loads(text)
        if p.get("resource_bound_research") != "resource-bound/20260907-v1":
            continue
        p.update(behavior_contract_hash=contract_hash, forward_activation_snapshot_id=activation_snapshot,
                 forward_started_at=activated, _origin="resource_delta", _activated_at=activated)
        policies[arm] = p
    return list(policies.values()), source


def delta_metrics(con, arms, frozen_frontier, boundary):
    """Small current-period aggregate queries; historic rows are delegated to frozen evidence."""
    placeholders = ",".join("?" for _ in arms)
    as_of = boundary["cutoff_utc"]
    params = [VERSION, *arms, as_of]
    decisions = con.execute(f"""
        SELECT arm_id, COUNT(*), COUNT(DISTINCT token_id || ':' || shadow_cohort_id)
        FROM chain_meme_trader_entry_decisions
        WHERE definition_version=? AND arm_id IN ({placeholders}) AND id>? AND decided_at<=?
        GROUP BY arm_id
    """, [VERSION, *arms, frozen_frontier.get("chain_meme_trader_entry_decisions", 0), as_of]).fetchall()
    buys = con.execute(f"""
        SELECT arm_id, COUNT(*), COUNT(DISTINCT token_id || ':' || shadow_cohort_id)
        FROM chain_meme_trader_trades
        WHERE definition_version=? AND arm_id IN ({placeholders}) AND id>? AND id<=? AND side='BUY' AND created_at<=?
        GROUP BY arm_id
    """, [VERSION, *arms, frozen_frontier.get("chain_meme_trader_trades", 0),
          boundary["frontiers"]["chain_meme_trader_trades"], as_of]).fetchall()
    contamination = con.execute(f"""
        SELECT arm_id, COUNT(*) FROM chain_meme_trader_accounting_contaminations
        WHERE definition_version=? AND arm_id IN ({placeholders}) AND recorded_at<=?
        GROUP BY arm_id
    """, params).fetchall()
    result = defaultdict(lambda: {"delta_decisions": 0, "delta_opportunities": 0,
                                  "delta_buys": 0, "delta_buy_opportunities": 0, "contaminations": 0})
    for arm, n, k in decisions:
        result[arm].update(delta_decisions=n, delta_opportunities=k)
    for arm, n, k in buys:
        result[arm].update(delta_buys=n, delta_buy_opportunities=k)
    for arm, n in contamination:
        result[arm]["contaminations"] = n
    return result


def frozen_metrics():
    rows = json.loads((ROOT / "data/research/20260907/arm_statistics.json").read_text(encoding="utf-8"))
    out = {}
    for row in rows:
        if row.get("definition_version") != VERSION:
            continue
        raw = row.get("raw") or {}
        out[row["arm_id"]] = {"frozen_buys": raw.get("buys", 0), "frozen_positions": raw.get("positions", 0),
                               "frozen_tokens": raw.get("unique_tokens", 0)}
    return out


def write_method(as_of, map_generated, frozen_cutoff, count):
    METHOD_OUT.parent.mkdir(parents=True, exist_ok=True)
    METHOD_OUT.write_text(f"""# Strategy behavior families method

Scope: {count} current effective Paper arms in `{VERSION}` as of `{as_of}`. This is a read-only diagnostic; it does not claim alpha, create strategies, or interpret zero trades as invalidity.

## Sources and frontier

The base contract map is `RESOURCE_BOUND_STRATEGY_MAP.json` generated `{map_generated}`. The frozen economics extract ends at `{frozen_cutoff}`. The immutable diagnostic boundary fixes the as-of point and the trade frontier. Only `chain_meme_trader_policy_additions` marked `resource-bound/20260907-v1` and activated by the boundary are merged after that map. DB access uses SQLite `mode=ro` and `query_only=ON`; no Store constructor is used. Post-freeze observations are bounded by the frozen `entry_decisions` / `trades` row frontiers, the fixed trade frontier, and the same as-of timestamp.

## Definitions

* **Contract exact group**: same declared behavior-contract hash and normalized entry, exit, and Paper-execution fingerprints. It proves identical declared contract, not observed economic identity.
* **Actual dispatch fingerprint**: a normalized code-path classification (`main_snapshot_exact_family`, `main_snapshot_dex_visible`, isolated pattern/cohort, or the resource-bound isolated path), plus the admission fields consumed by that path. This prevents labels from substituting for dispatch evidence.
* **Economic family**: equal dispatch path/admission mechanism plus exit mechanism and execution economics. Exact groups can contain several arms; one family is one testable mechanism, not one independent sample.
* **Near duplicate**: same dispatch path, admission family and exit family but distinct one-or-more contract parameters. It is a structural warning, not proof that their realized outcomes match.
* **Same entry / different exit** and **different entry / same exit** compare full respective fingerprints. **Distinct** means neither structural relation holds in this map.
* **active** means forward-enabled and activated by the cutoff. **active_no_buy** means a recorded decision opportunity but no BUY. **dormant_coverage_unknown** means no decision record: it may be no trigger, no feature coverage, or an unobserved dispatcher path; it is never silently merged with another empty arm. **contaminated** requires a current-period accounting-contamination row.

Opportunity counts are unique `(token_id, shadow_cohort_id)` records. A Token/underlying opportunity observed by several arms remains one common opportunity when comparing arms; arm count must never be used as sample size. The CSV has both frozen evidence and post-freeze delta columns, preserving the coverage boundary.
""", encoding="utf-8")


def main():
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    default_cutoff = boundary["cutoff_utc"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=default_cutoff, help="must equal the saved diagnostic boundary")
    args = parser.parse_args()
    as_of = args.as_of
    if as_of != default_cutoff:
        raise SystemExit("--as-of must equal data/research/alpha_diagnosis_20260907/BOUNDARY.json cutoff_utc")
    con, database = connect_database()
    try:
        policies, source = load_policies(con, as_of)
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        delta = delta_metrics(con, [p["arm_id"] for p in policies], frozen["frontiers"], boundary)
    finally:
        con.close()
    historic = frozen_metrics()
    rows = []
    for p in policies:
        entry_fp, exit_fp, exec_fp, entry_detail, exit_detail, exec_detail = policy_fingerprints(p)
        row = {"arm_id": p["arm_id"], "canonical_id": p.get("canonical_id", p["arm_id"]),
               "stage": p.get("stage"), "origin": p["_origin"], "activated_at": p.get("_activated_at"),
               "contract_hash": p.get("behavior_contract_hash"), "entry_fingerprint": entry_fp,
               "exit_fingerprint": exit_fp, "execution_fingerprint": exec_fp,
               "economic_fingerprint": digest({"entry": entry_fp, "exit": exit_fp, "execution": exec_fp}),
               "dispatch_path": entry_detail["dispatch"]["path"], "entry_family": p.get("entry_family"),
               "exit_family": p.get("exit_family"), "entry_detail": canonical(entry_detail),
               "exit_detail": canonical(exit_detail), "execution_detail": canonical(exec_detail),
               "revision_equivalence_group": p.get("revision_equivalence_group") or ""}
        row.update(historic.get(p["arm_id"], {"frozen_buys": 0, "frozen_positions": 0, "frozen_tokens": 0}))
        row.update(delta[p["arm_id"]])
        rows.append(row)
    declared = defaultdict(list); exact = defaultdict(list); entry = defaultdict(list); exit_ = defaultdict(list); near = defaultdict(list); econ = defaultdict(list)
    for r in rows:
        declared[r["contract_hash"]].append(r)
        exact[(r["contract_hash"], r["entry_fingerprint"], r["exit_fingerprint"], r["execution_fingerprint"])].append(r)
        entry[(r["entry_fingerprint"], r["execution_fingerprint"])].append(r)
        exit_[(r["exit_fingerprint"], r["execution_fingerprint"])].append(r)
        near[(r["dispatch_path"], r["entry_family"], r["exit_family"], r["execution_fingerprint"])].append(r)
        econ[r["economic_fingerprint"]].append(r)
    for r in rows:
        exact_group = exact[(r["contract_hash"], r["entry_fingerprint"], r["exit_fingerprint"], r["execution_fingerprint"])]
        entry_group = entry[(r["entry_fingerprint"], r["execution_fingerprint"])]
        exit_group = exit_[(r["exit_fingerprint"], r["execution_fingerprint"])]
        near_group = near[(r["dispatch_path"], r["entry_family"], r["exit_family"], r["execution_fingerprint"])]
        if len(exact_group) > 1:
            relation = "exact_duplicate"
        elif len(entry_group) > 1 and len({x["exit_fingerprint"] for x in entry_group}) > 1:
            relation = "same_entry_different_exit"
        elif len(exit_group) > 1 and len({x["entry_fingerprint"] for x in exit_group}) > 1:
            relation = "different_entry_same_exit"
        elif len(near_group) > 1:
            relation = "near_duplicate"
        else:
            relation = "distinct"
        r["relation"] = relation
        r["contract_exact_group_size"] = len(exact_group)
        r["economic_family_size"] = len(econ[r["economic_fingerprint"]])
        if r["contaminations"]:
            r["status"] = "contaminated"
        elif r["delta_buys"] or r["frozen_buys"]:
            r["status"] = "active_with_buy"
        elif r["delta_decisions"]:
            r["status"] = "active_no_buy"
        else:
            r["status"] = "dormant_coverage_unknown"
    rows.sort(key=lambda r: (int(r["stage"] or 10**9), r["arm_id"]))
    OUT.mkdir(parents=True, exist_ok=True)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    columns = ["arm_id", "canonical_id", "stage", "origin", "activated_at", "status", "relation",
               "contract_hash", "contract_exact_group_size", "economic_fingerprint", "economic_family_size",
               "dispatch_path", "entry_family", "exit_family", "entry_fingerprint", "exit_fingerprint",
               "execution_fingerprint", "revision_equivalence_group", "frozen_buys", "frozen_positions",
               "frozen_tokens", "delta_decisions", "delta_opportunities", "delta_buys",
               "delta_buy_opportunities", "contaminations", "entry_detail", "exit_detail", "execution_detail"]
    with CSV_OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)
    summary = {"as_of_utc": as_of, "base_map_generated_at": source["generated_at"],
               "frozen_cutoff_utc": frozen["cutoff_utc"], "definition_version": VERSION, "arms": len(rows),
               "declared_contract_hash_groups": len(declared),
               "verified_contract_exact_groups": len(exact), "economic_families": len(econ),
               "actual_dispatch_entry_groups": len(entry), "actual_exit_groups": len(exit_),
               "relations": dict(sorted(Counter(r["relation"] for r in rows).items())),
               "statuses": dict(sorted(Counter(r["status"] for r in rows).items())),
               "delta_frontiers": {k: frozen["frontiers"].get(k, 0) for k in
                                   ("chain_meme_trader_entry_decisions", "chain_meme_trader_trades")},
               "diagnostic_boundary": boundary,
               "note": "zero decision/BUY is coverage unknown, never proof of identical behavior"}
    (OUT / "family_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "family_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_method(as_of, source["generated_at"], frozen["cutoff_utc"], len(rows))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
