"""Apply reviewed evidence37 pause manifest through existing convergence controls."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    evidence = json.loads(Path(a.evidence).read_text())
    selected = {r["arm_id"] for r in evidence["arms"] if r["eligible"]}
    for group in evidence["groups"].values():
        if selected.intersection(group) and not set(group) <= selected:
            selected.difference_update(group)
    duplicates = {"early_impulse_profit_lock_control_v1", "early_impulse_profit_lock_40_v1"}
    root = Path(__file__).resolve().parents[1]
    dbpath = Path(json.loads((root / "config.json").read_text(encoding="utf-8"))["database"])
    if not dbpath.is_absolute():
        dbpath = root / dbpath
    db = sqlite3.connect(dbpath.as_uri() + ("?mode=rw" if a.apply else "?mode=ro"), uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN IMMEDIATE" if a.apply else "BEGIN")
    v = evidence["version"]
    active = db.execute("SELECT definition_version FROM chain_meme_trader_v6_activations WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1").fetchone()[0]
    assert v == active
    for arm in selected:
        r = db.execute("SELECT count(distinct token_id) n,sum(realized_pnl_usd) pnl,avg(realized_pnl_usd) expectancy FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND status IN ('closed','written_off')", (v, arm)).fetchone()
        assert r["n"] >= 100 and r["pnl"] <= -200 and r["expectancy"] <= -1, arm
        for table in ("chain_meme_trader_accounting_contaminations", "chain_meme_trader_position_voids"):
            assert db.execute("SELECT count(*) FROM " + table + " WHERE definition_version=? AND arm_id=?", (v,arm)).fetchone()[0] == 0, arm
    paired = db.execute("SELECT count(*),sum(b.realized_pnl_usd-a.realized_pnl_usd) FROM chain_meme_trader_positions a JOIN chain_meme_trader_positions b ON a.definition_version=b.definition_version AND a.token_id=b.token_id AND a.source_entry_fill_id=b.source_entry_fill_id AND a.source_entry_fill_id>0 WHERE a.definition_version=? AND a.arm_id='early_impulse_profit_lock_control_v1' AND b.arm_id='early_impulse_profit_lock_40_v1' AND a.status IN ('closed','written_off') AND b.status IN ('closed','written_off')", (v,)).fetchone()
    assert paired[0] >= 40 and paired[1] < 0
    selected |= duplicates
    key = "chain-meme-account-convergence/v1:" + v
    previous = json.loads(db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()[0])
    updated = json.loads(json.dumps(previous))
    now = datetime.now(timezone.utc).isoformat()
    for arm in sorted(selected):
        updated["arms"].setdefault(arm, dict(state="PAUSED_NEW_ENTRY", representative=arm,
            reason="convergence37: " + ("end failed profit-lock paired experiment; retain original trailing group" if arm in duplicates else "100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records")))
    def digest():
        h = hashlib.sha256()
        for table in ("chain_meme_trader_registrations", "chain_meme_trader_v6_registrations", "chain_meme_trader_v6_activations", "chain_meme_trader_policy_additions"):
            for row in db.execute("SELECT * FROM " + table + " ORDER BY rowid"):
                h.update(json.dumps(tuple(row)).encode())
        for arm in sorted(selected):
            for table in ("chain_meme_trader_positions", "chain_meme_trader_trades"):
                for row in db.execute("SELECT * FROM " + table + " WHERE definition_version=? AND arm_id=? ORDER BY rowid", (v,arm)):
                    h.update(json.dumps(tuple(row)).encode())
        return h.hexdigest()
    before = digest()
    if a.apply and updated != previous:
        updated["activated_at"] = now
        db.execute("UPDATE kv SET value_json=?,updated_at=? WHERE key=?", (json.dumps(updated,sort_keys=True),now,key))
    assert digest() == before
    db.commit()
    result = dict(applied=a.apply,cutoff=now,freeze=sorted(selected),previous_control=previous,new_control=updated,unchanged_ledger_contract_digest=before,paired_terminals=paired[0],paired_delta=paired[1])
    Path(a.evidence).with_name("applied.json" if a.apply else "preview.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(applied=a.apply,cutoff=now,count=len(selected),digest=before)))


if __name__ == "__main__":
    main()
