import json
from datetime import timedelta

import pytest

from memetrader.models import iso, utcnow
from memetrader.store import Store


def test_contamination_replay_respects_unconstrained_and_restored_funding_boundaries(
    tmp_path,
):
    store = Store(tmp_path / "funding-contamination.sqlite3", initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v20()
    version = Store.CHAIN_MEME_TRADER_V20_VERSION
    arm_id = "funding-boundary-arm"
    started = utcnow() - timedelta(seconds=10)

    def add_cohort(target_version, snapshot_id):
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (
                target_version, f"solana:token-{target_version}-{snapshot_id}",
                "broad_launch", snapshot_id, f"pair-{snapshot_id}", iso(started),
            ),
        )
        return int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])

    def add_buy(target_version, cohort_id, amount, created_at):
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,reason,created_at,recorded_at) "
            "VALUES(?,?,?,?, 'BUY',?,?,'fixture',?,?)",
            (
                target_version, arm_id, cohort_id, f"solana:token-{cohort_id}",
                amount, -amount, iso(created_at), iso(created_at),
            ),
        )
        return int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])

    with store.db:
        pre = add_cohort(version, 5)
        unconstrained = add_cohort(version, 20)
        restored = add_cohort(version, 30)
        pre_trade = add_buy(version, pre, 1000.0, started + timedelta(seconds=1))
        store.db.execute(
            "INSERT INTO chain_meme_trader_paper_funding_activations("
            "definition_version,mode,activated_at,activation_snapshot_id,"
            "activation_evaluation_id,activation_cohort_id,activation_entry_fill_id,"
            "activation_trade_id) VALUES(?,'unconstrained_research_notional',?,10,0,0,0,?)",
            (version, iso(started + timedelta(seconds=2)), pre_trade),
        )
        unconstrained_trade = add_buy(
            version, unconstrained, 20.0, started + timedelta(seconds=3),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_fixed_funding_restorations("
            "definition_version,activated_at,activation_snapshot_id,activation_trade_id,"
            "starting_cash_usd) VALUES(?,?,25,?,1000)",
            (version, iso(started + timedelta(seconds=4)), unconstrained_trade),
        )
        restored_trade = add_buy(
            version, restored, 20.0, started + timedelta(seconds=5),
        )

    assert store._record_chain_meme_trader_accounting_contaminations(
        version=version, historical_cash_gate_through=iso(started + timedelta(seconds=6)),
    ) == 1
    active = Store._chain_meme_trader_accounting_contaminations_from_connection(
        store.db, version,
    )
    assert [row["source_buy_trade_id"] for row in active] == [restored_trade]
    evidence = json.loads(active[0]["evidence_json"])
    assert evidence["available_cash_before_usd"] == pytest.approx(-20.0)

    funded_version = "test/funded-period"
    definition = json.loads(registration["definition_json"])
    definition.update({
        "version": funded_version,
        "capital_model": "legacy_cash_limited",
        "starting_cash_usd_each_arm": 1000.0,
    })
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_registrations("
            "definition_version,registered_at,activation_exploration_buy_trade_id,"
            "definition_json) VALUES(?,?,0,?)",
            (funded_version, iso(started), json.dumps(definition)),
        )
        funded_cohort = add_cohort(funded_version, 1)
        funded_trade = add_buy(
            funded_version, funded_cohort, 1020.0, started + timedelta(seconds=7),
        )
    assert store._record_chain_meme_trader_accounting_contaminations(
        version=funded_version,
        historical_cash_gate_through=iso(started + timedelta(seconds=8)),
    ) == 1
    funded_active = Store._chain_meme_trader_accounting_contaminations_from_connection(
        store.db, funded_version,
    )
    assert [row["source_buy_trade_id"] for row in funded_active] == [funded_trade]
    store.close()
