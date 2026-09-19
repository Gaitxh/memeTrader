from copy import deepcopy
from datetime import timedelta
import sqlite3

from memetrader import solana_regime250 as revision
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import iso, utcnow
from memetrader.store import Store
from memetrader.trajectory144 import ARMS as TRAJECTORY_ARMS, policies as trajectory_policies
from memetrader.trajectory_regime187 import policies as regime_policies


def parent_policy():
    trajectory = {item["arm_id"]: item for item in
                  trajectory_policies(cohort_experiment_policies()[2])}
    return next(item for item in regime_policies(
        trajectory[TRAJECTORY_ARMS[0]], trajectory[TRAJECTORY_ARMS[3]])
        if item["arm_id"] == revision.PARENT)


def terminal(token, at, pnl, status="closed"):
    return {
        "token_id": token,
        "closed_at": iso(at),
        "realized_pnl_usd": pnl,
        "status": status,
    }


def test_assess_uses_unique_strictly_prior_solana_terminals():
    now = utcnow()
    good = [terminal("solana:" + str(i), now - timedelta(minutes=i + 1), 2.0)
            for i in range(10)]
    ok, reason, evidence = revision.assess(good, decision_at=now)
    assert ok and reason == "regime250_favorable"
    assert evidence["terminal_tokens"] == 10 and evidence["net_pnl_usd"] == 20
    mixed = [terminal("bsc:x", now - timedelta(seconds=1), 999), *good]
    assert revision.assess(mixed, decision_at=now)[2]["terminal_tokens"] == 10
    bad = [*good[:8], terminal("solana:x", now - timedelta(seconds=1), -20, "written_off"),
           terminal("solana:y", now - timedelta(seconds=2), -20, "written_off")]
    assert not revision.assess(bad, decision_at=now)[0]


def test_evaluate_excludes_future_close():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE chain_meme_trader_positions("
               "definition_version TEXT,arm_id TEXT,token_id TEXT,status TEXT,"
               "realized_pnl_usd REAL,closed_at TEXT,shadow_cohort_id INTEGER)")
    now = utcnow()
    rows = [("v", revision.PARENT, "solana:" + str(i), "closed", 2.0,
             iso(now - timedelta(minutes=i + 1)), i) for i in range(10)]
    rows.append(("v", revision.PARENT, "solana:future", "closed", 500.0,
                 iso(now + timedelta(seconds=1)), 99))
    db.executemany("INSERT INTO chain_meme_trader_positions VALUES(?,?,?,?,?,?,?)", rows)
    ok, _, evidence = revision.evaluate(db, version="v", decision_at=now)
    assert ok and evidence["terminal_tokens"] == 10 and evidence["net_pnl_usd"] == 20
    db.close()


def test_policy_preserves_parent_entry_exit_and_aliases_signal():
    parent = parent_policy()
    before = deepcopy(parent)
    candidate = revision.policy(parent)
    assert parent == before and candidate["revision_of"] == revision.PARENT
    for key in ("hard_stop_return", "take_profit", "max_hold_minutes",
                "trailing_activate_return", "trailing_drawdown", "notional_usd"):
        assert candidate[key] == parent[key]
    assert candidate["entry_filter"]["regime250"] == revision.RULES
    source = {"decision_key": "s", "selected": {"token_id": "solana:a"},
              "decision_evidence": {}}
    alias = revision.alias(source)[revision.ARM]
    assert alias["decision_key"] == "s|" + revision.ARM
    assert alias["selected"] == source["selected"]


def test_registration_is_append_only_and_idempotent(tmp_path):
    store = Store(tmp_path / "regime250.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        before = store._chain_meme_trader_registration(version)["definition_json"]
        assert store.register_chain_meme_solana_regime250() == 1
        assert store.register_chain_meme_solana_regime250() == 0
        assert store._chain_meme_trader_registration(version)["definition_json"] == before
        effective = store._chain_meme_trader_effective_definition(version, before)
        current = next(p for p in effective["policies"] if p["arm_id"] == revision.ARM)
        assert current["entry_filter"]["regime250"] == revision.RULES
    finally:
        store.close()
