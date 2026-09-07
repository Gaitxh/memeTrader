"""Read-only recovery of the persisted Round2 chase common-opportunity denominator."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "chain-meme-trader/funding-20260906-v002-final-1000"
CUTOFF = "2026-09-07T13:38:59.399800Z"
COHORT_FRONTIER = 63036
OUT = ROOT / "data/research/alpha_diagnosis_20260907/gate_exit"
REPORT = ROOT / "docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907/GATE_MARGINAL_VALUE.md"
CANDIDATE = "round2_chase_candidate_v1"
CONTROL = "round2_chase_control_v1"


def terminal(row):
    return row and row["status"] in {"closed", "written_off"} and row["closed_at"] and row["closed_at"] <= CUTOFF


def main():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    db = Path(config["database"])
    if not db.is_absolute(): db = ROOT / db
    con = sqlite3.connect("file:" + db.resolve().as_posix() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row; con.execute("PRAGMA query_only=ON")
    try:
        cohorts = con.execute("""
          SELECT id,token_id,decided_at,feature_json FROM chain_meme_trader_v6_cohorts
          WHERE definition_version=? AND id<=? AND decided_at<=?
        """, (VERSION, COHORT_FRONTIER, CUTOFF)).fetchall()
        controls = con.execute("""
          SELECT shadow_cohort_id,token_id,status,realized_pnl_usd,closed_at
          FROM chain_meme_trader_positions
          WHERE definition_version=? AND arm_id=? AND shadow_cohort_id<=?
        """, (VERSION, CONTROL, COHORT_FRONTIER)).fetchall()
    finally:
        con.close()
    by_receipt = defaultdict(list)
    for row in cohorts:
        feature = json.loads(row["feature_json"] or "{}")
        receipt = feature.get("round2_chase_receipt")
        outcomes = receipt.get("outcomes", {}) if isinstance(receipt, dict) else {}
        candidate, control = outcomes.get(CANDIDATE), outcomes.get(CONTROL)
        if not isinstance(candidate, dict) or not isinstance(control, dict):
            continue
        key = (row["token_id"], receipt.get("signal_snapshot_id"), receipt.get("receipt_snapshot_id"))
        by_receipt[key].append({"cohort_id": row["id"], "decided_at": row["decided_at"],
                                "candidate_allowed": candidate.get("allowed"), "control_allowed": control.get("allowed"),
                                "price_drift": candidate.get("price_drift"), "received_at": receipt.get("received_at")})
    controls_by_cohort = {r["shadow_cohort_id"]: dict(r) for r in controls}
    rows = []
    for (token, signal_id, receipt_id), members in by_receipt.items():
        members.sort(key=lambda x: x["cohort_id"])
        control = next((controls_by_cohort.get(x["cohort_id"]) for x in members if controls_by_cohort.get(x["cohort_id"])), None)
        first = members[0]
        outcome = None if not terminal(control) else float(control["realized_pnl_usd"])
        rows.append({"token_id": token, "signal_snapshot_id": signal_id, "receipt_snapshot_id": receipt_id,
                     "cohort_ids": [x["cohort_id"] for x in members], "received_at": first["received_at"],
                     "candidate_allowed": bool(first["candidate_allowed"]), "control_allowed": bool(first["control_allowed"]),
                     "price_drift": first["price_drift"], "control_terminal_pnl_usd": outcome,
                     "control_terminal": outcome is not None})
    veto = [r for r in rows if not r["candidate_allowed"] and r["control_allowed"]]
    complete = [r for r in veto if r["control_terminal"]]
    avoided = [-r["control_terminal_pnl_usd"] for r in complete if r["control_terminal_pnl_usd"] < 0]
    missed = [r["control_terminal_pnl_usd"] for r in complete if r["control_terminal_pnl_usd"] > 0]
    summary = {"scope": "deduplicated round2_chase_receipt by token+signal_snapshot+receipt_snapshot",
               "common_receipt_opportunities": len(rows), "candidate_allowed": sum(r["candidate_allowed"] for r in rows),
               "candidate_vetoed": len(veto), "veto_control_terminal": len(complete),
               "veto_control_unknown_or_open": len(veto) - len(complete),
               "avoided_loss_cases": len(avoided), "avoided_loss_usd": sum(avoided),
               "missed_profit_cases": len(missed), "missed_profit_usd": sum(missed),
               "net_control_pnl_for_vetoes_usd": sum(r["control_terminal_pnl_usd"] for r in complete),
               "special_cases": [r for r in rows if 56861 in r["cohort_ids"] or 57425 in r["cohort_ids"]]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "round2_chase_common_denominator.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    REPORT.write_text(f"""# Gate marginal value: frozen evidence

Fixed boundary: `{CUTOFF}`. The general decision ledger has 149,380 rows, dominated by cash and slot constraints; those are admission/capacity outcomes, not a recoverable marginal hypothesis-gate reject population. No-decision and missing features are not counted as rejects.

## Round2 chase: persisted common-opportunity denominator

The dispatcher writes `round2_chase_receipt` before it removes a vetoed candidate and records `round2_chase_consumed` to prevent replay. This is the recoverable gate denominator. Deduplicating repeated cohort projections by `(token_id, signal_snapshot_id, receipt_snapshot_id)` gives {summary['common_receipt_opportunities']} common receipt opportunities: candidate allowed {summary['candidate_allowed']}, candidate vetoed {summary['candidate_vetoed']}. Of the vetoes, {summary['veto_control_terminal']} have a control terminal by the cutoff and {summary['veto_control_unknown_or_open']} remain unknown/open.

For terminal veto controls, avoided-loss cases={summary['avoided_loss_cases']} / {summary['avoided_loss_usd']:.4f}U, missed-profit cases={summary['missed_profit_cases']} / {summary['missed_profit_usd']:.4f}U, net control outcome={summary['net_control_pnl_for_vetoes_usd']:.4f}U. This is a finite, capacity- and selection-confounded counterfactual ledger, not an alpha estimate or deployable portfolio return.

The required historical records are retained: cohort 56861 (SOL) is a 19.3438% veto with control terminal +24.0510U; cohort 57425 (BSC) is a 6.8094% veto with control terminal -5.0000U. Both are one receipt opportunity each despite duplicate cohort projections.

## Other declared gate directions

Age/flow/pullback/liquidity/wallet/narrative/safety/acceleration/breakout/confirmation mechanisms cannot be given marginal avoided/missed estimates here because they lack a persisted candidate-veto plus same-opportunity control-receipt chain. Their absent `entry_decision` rows can mean no dispatcher invocation, incomplete feature coverage, another admission constraint, or no trigger; they are not rejects. Resource age-rate and cooling controls have common decisions but no candidate rejection at the frozen boundary. Existing exit pairs are not gate evidence: different receipt/exit behavior cannot establish admission marginal value.

Source evidence: `store.py:27153-27169` builds and persists the chase receipt/outcomes before candidate removal; `store.py:27167-27172` persists consumption. The detailed deduplicated rows are in `round2_chase_common_denominator.json`.
""", encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__": main()
