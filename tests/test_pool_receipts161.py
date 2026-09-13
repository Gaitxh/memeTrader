"""Immutable receipts for cross-arm pool-concentration refusals."""

from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, utcnow
from memetrader.store import Store
from test_paper_execution import _snapshot


def _prepared_projection(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "pool-receipts161.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    registration = store._chain_meme_trader_registration(version)
    definition = store._chain_meme_trader_effective_definition(
        version, registration["definition_json"])
    arms = [p["arm_id"] for p in definition["policies"] if not p.get("entry_paused")][:2]
    assert len(arms) == 2
    definition = {**definition, "max_arms_per_pool": 1}
    token = TokenCandidate("bsc", "0x" + "16" * 20, "Receipt", "RCP", source="fixture")
    pool = "0x" + "61" * 20
    store.upsert_token(token, seen_at=clock[0])
    snapshot_id = store.add_snapshot(_snapshot(token, pool, clock[0], price=1.0, liquidity=5000))
    clock[0] += timedelta(seconds=30)
    with store.db:
        cohort = int(store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (version, token.token_id, "broad_launch", snapshot_id, pool, clock[0].isoformat()),
        ).lastrowid)
        for arm in arms:
            store.db.execute(
                "INSERT INTO chain_meme_trader_entry_decisions("
                "definition_version,arm_id,shadow_cohort_id,token_id,baseline_quote_result_id,"
                "decided_at,status,reason) VALUES(?,?,?,?,?,?,'admitted','fixture')",
                (version, arm, cohort, token.token_id, snapshot_id, clock[0].isoformat()),
            )
    return store, clock, version, definition, token, pool, snapshot_id, cohort, arms


def _project(store, clock, version, definition, token, snapshot_id, cohort):
    return store._project_chain_meme_trader_market_entry(
        version=version, cohort_id=cohort, token_id=token.token_id, snapshot_id=snapshot_id,
        market_price=1.0, filled_at=clock[0].isoformat(), reason="fixture",
        definition=definition, funding_mode="paper", signal_price_usd=1.0,
    )


def test_same_cohort_fanout_captures_cap_refusal_but_projects_only_one(tmp_path, monkeypatch):
    store, clock, version, definition, token, pool, snapshot_id, cohort, arms = _prepared_projection(
        tmp_path, monkeypatch)
    assert _project(store, clock, version, definition, token, snapshot_id, cohort) == 1
    projected = store.db.execute(
        "SELECT arm_id FROM chain_meme_trader_positions WHERE shadow_cohort_id=?", (cohort,)
    ).fetchall()
    receipt = store.db.execute(
        "SELECT * FROM chain_meme_trader_entry_gate_refusals WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()
    assert [row["arm_id"] for row in projected] == [arms[0]]
    assert receipt["arm_id"] == arms[1]
    assert receipt["definition_version"] == version
    assert receipt["entry_decision_id"]
    assert receipt["entry_fill_id"]
    assert receipt["token_id"] == token.token_id
    assert receipt["pair_address"] == pool.lower()
    assert receipt["gate"] == "pool_concentration"
    assert receipt["reason"]
    assert receipt["attempted_at"] == clock[0].isoformat()
    assert receipt["recorded_at"]
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_entry_participant_outcomes WHERE shadow_cohort_id=?",
        (cohort,),
    ).fetchone()[0] == 1
    store.close()


def test_refusal_receipt_is_idempotent_and_immutable(tmp_path, monkeypatch):
    store, clock, version, definition, token, _, snapshot_id, cohort, _ = _prepared_projection(
        tmp_path, monkeypatch)
    _project(store, clock, version, definition, token, snapshot_id, cohort)
    first = store.db.execute(
        "SELECT id,entry_decision_id FROM chain_meme_trader_entry_gate_refusals WHERE shadow_cohort_id=?",
        (cohort,),
    ).fetchone()
    _project(store, clock, version, definition, token, snapshot_id, cohort)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_entry_gate_refusals "
        "WHERE shadow_cohort_id=? AND entry_decision_id=?",
        (cohort, first["entry_decision_id"]),
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_entry_gate_refusals WHERE shadow_cohort_id=?",
        (cohort,),
    ).fetchone()[0] == 1
    projected_arm = store.db.execute(
        "SELECT arm_id FROM chain_meme_trader_positions WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()["arm_id"]
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_entry_gate_refusals "
        "WHERE shadow_cohort_id=? AND arm_id=?",
        (cohort, projected_arm),
    ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()[0] == 1
    with pytest.raises(Exception, match="immutable"):
        store.db.execute(
            "UPDATE chain_meme_trader_entry_gate_refusals SET reason='changed' WHERE id=?",
            (first["id"],),
        )
    store.close()


def test_projection_rollback_leaves_no_refusal_receipt(tmp_path, monkeypatch):
    store, clock, version, definition, token, _, snapshot_id, cohort, _ = _prepared_projection(
        tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="rollback"):
        with store.db:
            assert _project(store, clock, version, definition, token, snapshot_id, cohort) == 1
            raise RuntimeError("rollback")
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_entry_gate_refusals WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE shadow_cohort_id=?", (cohort,)
    ).fetchone()[0] == 0
    store.close()
