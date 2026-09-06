import json
from datetime import timedelta

import pytest

from memetrader.chain_web import ChainWebData
from memetrader.models import iso, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store


def _funded_store(tmp_path):
    store = Store(tmp_path / "chain-position-voids.sqlite3", initial_cash_usd=1000)
    activation = store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    registration = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?",
        (version,),
    ).fetchone()
    policies = json.loads(registration["definition_json"])["policies"]
    return store, version, [str(policy["arm_id"]) for policy in policies], dict(activation)


def _seed_position(
    store,
    *,
    version,
    arm_id,
    opened_at,
    suffix,
    sell_proceeds_usd=None,
    partial=False,
    pending=False,
):
    token_id = f"solana:void-fixture-{suffix}"
    with store.db:
        source_snapshot_id = int(store.db.execute(
            "SELECT COALESCE(MAX(source_snapshot_id),0)+1 FROM "
            "chain_meme_trader_v6_cohorts WHERE definition_version=?",
            (version,),
        ).fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (
                version, token_id, "broad_launch", source_snapshot_id,
                f"pair-{suffix}", iso(opened_at),
            ),
        )
        cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        buy_fill_id = int(store.db.execute(
            "INSERT INTO chain_meme_trader_fills("
            "definition_version,intent_id,result_id,attempt_id,execution_mode,adapter,"
            "arm_id,shadow_cohort_id,token_id,side,input_amount_raw,output_amount_raw,"
            "gross_usd,filled_at) VALUES(?,?,?,?,'paper','fixture',?,?,?,'BUY',"
            "'20000000','20000000000',20,?)",
            (
                version, -(cohort_id * 10 + 1), -(cohort_id * 10 + 1),
                -(cohort_id * 10 + 1), arm_id, cohort_id, token_id, iso(opened_at),
            ),
        ).lastrowid)
        buy_trade_id = int(store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at,"
            "execution_fill_id) VALUES(?,?,?,?, 'BUY',20,-20,NULL,'fixture',?,?,?)",
            (version, arm_id, cohort_id, token_id, iso(opened_at), iso(opened_at), buy_fill_id),
        ).lastrowid)
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "source_entry_fill_id,baseline_quote_result_id,entry_snapshot_id,"
            "entry_signal_price_usd,entry_execution_price_usd,paper_quantity_tokens,"
            "remaining_quantity_tokens,amount_raw,initial_amount_raw,stake_usd,"
            "highest_signal_price_usd,status,opened_at) "
            "VALUES(?,?,?,?,?,?,1,1,1,1,20,20,'20000000000','20000000000',20,1,'open',?)",
            (version, arm_id, cohort_id, token_id, buy_trade_id, buy_fill_id, iso(opened_at)),
        )

        sell_trade_id = None
        if sell_proceeds_usd is not None:
            sold_raw = 10_000_000_000 if partial else 20_000_000_000
            allocated_cost = 10.0 if partial else 20.0
            realized_pnl = float(sell_proceeds_usd) - allocated_cost
            sold_at = opened_at + timedelta(seconds=10)
            store.db.execute(
                "INSERT INTO chain_meme_trader_marks("
                "definition_version,arm_id,shadow_cohort_id,recorded_at,action,reason,"
                "sell_amount_raw,status) VALUES(?,?,?,?, 'FIXTURE_EXIT','fixture',?,'filled')",
                (version, arm_id, cohort_id, iso(sold_at), str(sold_raw)),
            )
            mark_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
            sell_fill_id = int(store.db.execute(
                "INSERT INTO chain_meme_trader_fills("
                "definition_version,intent_id,result_id,attempt_id,execution_mode,adapter,"
                "arm_id,shadow_cohort_id,token_id,side,input_amount_raw,output_amount_raw,"
                "gross_usd,filled_at) VALUES(?,?,?,?,'paper','fixture',?,?,?,'SELL',?,?,?,?)",
                (
                    version, -(cohort_id * 10 + 2), -(cohort_id * 10 + 2),
                    -(cohort_id * 10 + 2), arm_id, cohort_id, token_id,
                    str(sold_raw), str(round(float(sell_proceeds_usd) * 1_000_000)),
                    float(sell_proceeds_usd), iso(sold_at),
                ),
            ).lastrowid)
            sell_trade_id = int(store.db.execute(
                "INSERT INTO chain_meme_trader_trades("
                "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at,"
                "execution_fill_id) VALUES(?,?,?,?, 'SELL',?,?,?,?,?,?,?)",
                (
                    version, arm_id, cohort_id, token_id, float(sell_proceeds_usd),
                    float(sell_proceeds_usd), realized_pnl, "fixture", iso(sold_at),
                    iso(sold_at), sell_fill_id,
                ),
            ).lastrowid)
            store.db.execute(
                "UPDATE chain_meme_trader_positions SET realized_proceeds_usd=?,"
                "allocated_cost_usd=?,realized_pnl_usd=?,remaining_quantity_tokens=?,"
                "amount_raw=?,status=?,closed_at=?,last_fill_id=? WHERE "
                "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
                (
                    float(sell_proceeds_usd), allocated_cost, realized_pnl,
                    10.0 if partial else 0.0,
                    "10000000000" if partial else "0", "open" if partial else "closed",
                    None if partial else iso(sold_at), sell_fill_id,
                    version, arm_id, cohort_id,
                ),
            )
        pending_mark_id = None
        if pending:
            store.db.execute(
                "INSERT INTO chain_meme_trader_marks("
                "definition_version,arm_id,shadow_cohort_id,recorded_at,action,reason,"
                "sell_amount_raw,status) VALUES(?,?,?,?, 'FIXTURE_PENDING','fixture',"
                "'10000000000','pending')",
                (version, arm_id, cohort_id, iso(opened_at + timedelta(seconds=20))),
            )
            pending_mark_id = int(store.db.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0])
            store.db.execute(
                "UPDATE chain_meme_trader_positions SET pending_mark_id=? WHERE "
                "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
                (pending_mark_id, version, arm_id, cohort_id),
            )
    return {
        "arm_id": arm_id,
        "cohort_id": cohort_id,
        "token_id": token_id,
        "buy_trade_id": buy_trade_id,
        "sell_trade_id": sell_trade_id,
        "pending_mark_id": pending_mark_id,
    }


def _latest_account(store, version, arm_id):
    return store.db.execute(
        "SELECT * FROM chain_meme_trader_account_snapshots WHERE "
        "definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1",
        (version, arm_id),
    ).fetchone()


def _chain_web_data(tmp_path):
    config = initial_config()
    config["database"] = "chain-position-voids.sqlite3"
    config["lock_file"] = "robot.lock"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return ChainWebData(config_path)


def test_void_positions_excludes_complete_lifecycles_and_preserves_raw_audit(tmp_path):
    store, version, arms, activation_before = _funded_store(tmp_path)
    target_arm, other_arm = arms[:2]
    started = utcnow() - timedelta(minutes=5)
    profitable = _seed_position(
        store, version=version, arm_id=target_arm, opened_at=started,
        suffix="profit", sell_proceeds_usd=30.0,
    )
    losing = _seed_position(
        store, version=version, arm_id=target_arm,
        opened_at=started + timedelta(seconds=30), suffix="loss",
        sell_proceeds_usd=5.0,
    )
    partial = _seed_position(
        store, version=version, arm_id=target_arm,
        opened_at=started + timedelta(seconds=60), suffix="partial",
        sell_proceeds_usd=8.0, partial=True, pending=True,
    )
    untouched = _seed_position(
        store, version=version, arm_id=other_arm,
        opened_at=started + timedelta(seconds=90), suffix="other", pending=True,
    )
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_capital_credits("
            "source_buy_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
            "entry_snapshot_id,amount_usd,reason,recorded_at,evidence_json) "
            "VALUES(?,?,?,?,?,1,4,'fixture_prior_credit',?,'{}')",
            (
                partial["buy_trade_id"], version, target_arm, partial["cohort_id"],
                partial["token_id"], iso(started + timedelta(seconds=70)),
            ),
        )

    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=started + timedelta(minutes=3),
    )
    assert _latest_account(store, version, target_arm)["cash_usd"] == pytest.approx(987.0)
    assert _latest_account(store, version, other_arm)["cash_usd"] == pytest.approx(980.0)

    raw_trades_before = [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_trades ORDER BY id"
    ).fetchall()]
    raw_fills_before = [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_fills ORDER BY id"
    ).fetchall()]
    raw_credits_before = [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_capital_credits ORDER BY source_buy_trade_id"
    ).fetchall()]
    evidence = {"incident": "amount-independent-paper-fill", "ticket": 417315}
    target_ids = [
        profitable["buy_trade_id"], losing["buy_trade_id"], partial["buy_trade_id"],
    ]

    result = store.void_chain_meme_trader_positions(
        target_ids, definition_version=version,
        reason="manual_amount_specific_execution_audit", evidence=evidence,
    )

    assert result["requested"] == 3
    assert result["voided"] == 3
    assert result["already_voided"] == 0
    assert result["cash_adjustment_usd"] == pytest.approx(13.0)
    positions = store.db.execute(
        "SELECT source_buy_trade_id,status FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? ORDER BY source_buy_trade_id",
        (version, target_arm),
    ).fetchall()
    assert {int(row["source_buy_trade_id"]): row["status"] for row in positions} == {
        source_id: "ineligible" for source_id in target_ids
    }
    assert store.db.execute(
        "SELECT status FROM chain_meme_trader_marks WHERE id=?",
        (partial["pending_mark_id"],),
    ).fetchone()[0] == "exhausted"

    voids = store.db.execute(
        "SELECT * FROM chain_meme_trader_position_voids WHERE definition_version=? "
        "AND arm_id=? ORDER BY source_buy_trade_id",
        (version, target_arm),
    ).fetchall()
    assert len(voids) == 3
    assert {int(row["source_buy_trade_id"]) for row in voids} == set(target_ids)
    assert all(row["reason"] == "manual_amount_specific_execution_audit" for row in voids)
    assert all(json.loads(row["evidence_json"]) == evidence for row in voids)
    assert all(isinstance(json.loads(row["archive_json"]), dict) for row in voids)

    assert [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_trades ORDER BY id"
    ).fetchall()] == raw_trades_before
    assert [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_fills ORDER BY id"
    ).fetchall()] == raw_fills_before
    assert [tuple(row) for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_capital_credits ORDER BY source_buy_trade_id"
    ).fetchall()] == raw_credits_before
    assert dict(store.db.execute(
        "SELECT * FROM chain_meme_trader_v6_activations WHERE definition_version=?",
        (version,),
    ).fetchone()) == activation_before
    assert store.db.execute(
        "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, other_arm, untouched["cohort_id"]),
    ).fetchone()[0] == "open"
    assert store.db.execute(
        "SELECT status FROM chain_meme_trader_marks WHERE id=?",
        (untouched["pending_mark_id"],),
    ).fetchone()[0] == "pending"

    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=started + timedelta(minutes=4),
    )
    assert _latest_account(store, version, target_arm)["cash_usd"] == pytest.approx(1000.0)
    assert _latest_account(store, version, target_arm)["realized_pnl_usd"] == pytest.approx(0.0)
    assert _latest_account(store, version, other_arm)["cash_usd"] == pytest.approx(980.0)

    repeated = store.void_chain_meme_trader_positions(
        target_ids, definition_version=version,
        reason="manual_amount_specific_execution_audit", evidence=evidence,
    )
    assert repeated["requested"] == 3
    assert repeated["voided"] == 0
    assert repeated["already_voided"] == 3
    assert repeated["cash_adjustment_usd"] == pytest.approx(0.0)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_position_voids"
    ).fetchone()[0] == 3
    store.close()


def test_void_positions_rejects_missing_or_wrong_version_buy_atomically(tmp_path):
    store, version, arms, _ = _funded_store(tmp_path)
    started = utcnow() - timedelta(minutes=2)
    valid = _seed_position(
        store, version=version, arm_id=arms[0], opened_at=started, suffix="valid",
    )
    wrong_version = _seed_position(
        store, version="fixture/other-version", arm_id=arms[0],
        opened_at=started + timedelta(seconds=1), suffix="wrong-version",
    )

    for invalid_source_id in (999_999_999, wrong_version["buy_trade_id"]):
        with pytest.raises(ValueError):
            store.void_chain_meme_trader_positions(
                [valid["buy_trade_id"], invalid_source_id],
                definition_version=version, reason="fixture_invalid_batch",
                evidence={"fixture": True},
            )
        assert store.db.execute(
            "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND source_buy_trade_id=?",
            (version, valid["buy_trade_id"]),
        ).fetchone()[0] == "open"
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_position_voids"
        ).fetchone()[0] == 0
    store.close()


def test_manual_void_remains_active_after_legacy_contamination_recompute(tmp_path):
    store, version, arms, _ = _funded_store(tmp_path)
    started = utcnow() - timedelta(minutes=2)
    position = _seed_position(
        store, version=version, arm_id=arms[0], opened_at=started,
        suffix="manual-contamination",
    )
    store.void_chain_meme_trader_positions(
        [position["buy_trade_id"]], definition_version=version,
        reason="manual_invalid_execution_lifecycle", evidence={"manual": True},
    )
    active_before = Store._chain_meme_trader_accounting_contaminations_from_connection(
        store.db, version,
    )
    assert [int(row["source_buy_trade_id"]) for row in active_before] == [
        position["buy_trade_id"]
    ]

    store._record_chain_meme_trader_accounting_contaminations(
        version=version,
        historical_cash_gate_through=iso(started + timedelta(hours=1)),
    )

    active_after = Store._chain_meme_trader_accounting_contaminations_from_connection(
        store.db, version,
    )
    assert [int(row["source_buy_trade_id"]) for row in active_after] == [
        position["buy_trade_id"]
    ]
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_accounting_contamination_resolutions "
        "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, arms[0], position["cohort_id"]),
    ).fetchone()[0] == 0
    store.close()


def test_voided_fill_correction_disappears_from_public_snapshot_and_full_summary(tmp_path):
    store, version, arms, _ = _funded_store(tmp_path)
    target_arm, other_arm = arms[:2]
    started = utcnow() - timedelta(minutes=10)
    voided_profit = _seed_position(
        store, version=version, arm_id=target_arm, opened_at=started,
        suffix="summary-void-profit", sell_proceeds_usd=30.0,
    )
    voided_loss = _seed_position(
        store, version=version, arm_id=target_arm,
        opened_at=started + timedelta(seconds=30), suffix="summary-void-loss",
        sell_proceeds_usd=5.0,
    )
    retained_closed = _seed_position(
        store, version=version, arm_id=target_arm,
        opened_at=started + timedelta(seconds=60), suffix="summary-retained-closed",
        sell_proceeds_usd=22.0,
    )
    retained_open = _seed_position(
        store, version=version, arm_id=target_arm,
        opened_at=started + timedelta(seconds=90), suffix="summary-retained-open",
    )
    other_profit = _seed_position(
        store, version=version, arm_id=other_arm,
        opened_at=started + timedelta(seconds=120), suffix="summary-other-profit",
        sell_proceeds_usd=26.0,
    )
    other_loss = _seed_position(
        store, version=version, arm_id=other_arm,
        opened_at=started + timedelta(seconds=150), suffix="summary-other-loss",
        sell_proceeds_usd=16.0,
    )
    corrected_sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE id=?",
        (voided_profit["sell_trade_id"],),
    ).fetchone()
    source_mark_id = int(store.db.execute(
        "SELECT id FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND status='filled'",
        (version, target_arm, voided_profit["cohort_id"]),
    ).fetchone()[0])
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_market_fill_corrections("
            "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
            "source_fill_id,source_mark_id,original_gross_usd,post_liquidity_usd,"
            "max_market_gross_usd,replacement_outcome,replacement_gross_usd,"
            "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
            "reason,evidence_json,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                voided_profit["sell_trade_id"], version, target_arm,
                voided_profit["cohort_id"], voided_profit["token_id"],
                int(corrected_sell["execution_fill_id"]), source_mark_id, 30.0,
                100.0, 24.0, "SELL", 24.0, -6.0, -6.0,
                corrected_sell["created_at"], "fixture_existing_fill_correction", "{}",
                iso(started + timedelta(minutes=3)),
            ),
        )

    result = store.void_chain_meme_trader_positions(
        [voided_profit["buy_trade_id"], voided_loss["buy_trade_id"]],
        definition_version=version, reason="manual_summary_regression",
        evidence={"regression": "void_and_fill_correction"},
    )
    # The corrected profit contributed +4 and the loss -15, so excluding both
    # raises effective cash by 11 without changing either raw record.
    assert result["cash_adjustment_usd"] == pytest.approx(11.0)
    assert store.db.execute(
        "SELECT cash_adjustment_usd,realized_adjustment_usd FROM "
        "chain_meme_trader_market_fill_corrections WHERE source_trade_id=?",
        (voided_profit["sell_trade_id"],),
    ).fetchone()[:] == pytest.approx((-6.0, -6.0))

    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=started + timedelta(minutes=5),
    )
    target_snapshot = _latest_account(store, version, target_arm)
    other_snapshot = _latest_account(store, version, other_arm)
    assert target_snapshot["cash_usd"] == pytest.approx(982.0)
    assert target_snapshot["realized_pnl_usd"] == pytest.approx(2.0)
    assert target_snapshot["open_position_count"] == 1
    assert target_snapshot["closed_position_count"] == 1
    assert other_snapshot["cash_usd"] == pytest.approx(1002.0)
    assert other_snapshot["realized_pnl_usd"] == pytest.approx(2.0)
    assert other_snapshot["open_position_count"] == 0
    assert other_snapshot["closed_position_count"] == 2

    summary = Store.chain_meme_trader_summary_from_connection(store.db)
    strategies = {item["arm_id"]: item for item in summary["strategies"]}
    target = strategies[target_arm]
    other = strategies[other_arm]
    assert summary["open_position_count"] == 1
    assert target["account"]["cash_usd"] == pytest.approx(target_snapshot["cash_usd"])
    assert target["account"]["realized_pnl_usd"] == pytest.approx(
        target_snapshot["realized_pnl_usd"]
    )
    assert target["account"]["capital_neutral_realized_pnl_usd"] == pytest.approx(2.0)
    assert target["account"]["open_position_count"] == 1
    assert target["account"]["closed_position_count"] == 1
    assert target["account"]["terminal_position_count"] == 1
    assert target["account"]["win_count"] == 1
    assert target["account"]["expectancy_usd"] == pytest.approx(2.0)
    assert target["account"]["total_pnl_is_complete"] is False
    assert target["account"]["capital_neutral_total_pnl_usd"] is None

    assert other["account"]["cash_usd"] == pytest.approx(other_snapshot["cash_usd"])
    assert other["account"]["realized_pnl_usd"] == pytest.approx(2.0)
    assert other["account"]["open_position_count"] == 0
    assert other["account"]["closed_position_count"] == 2
    assert other["account"]["terminal_position_count"] == 2
    assert other["account"]["win_count"] == 1
    assert other["account"]["expectancy_usd"] == pytest.approx(1.0)
    assert other["account"]["capital_neutral_total_pnl_usd"] == pytest.approx(2.0)
    assert other["account"]["account_return_fraction"] == pytest.approx(0.002)

    target_positions = {
        int(row["source_buy_trade_id"]): row for row in target["positions"]
    }
    assert target_positions[retained_closed["buy_trade_id"]]["status"] == "closed"
    assert target_positions[retained_open["buy_trade_id"]]["status"] == "open"
    assert voided_profit["buy_trade_id"] not in target_positions
    assert voided_loss["buy_trade_id"] not in target_positions
    assert all(
        int(trade["shadow_cohort_id"])
        not in {voided_profit["cohort_id"], voided_loss["cohort_id"]}
        for trade in target["trades"]
    )
    assert target["account"]["market_fill_correction_count"] == 1
    assert {position["source_buy_trade_id"] for position in other["positions"]} == {
        other_profit["buy_trade_id"], other_loss["buy_trade_id"],
    }
    store.close()


def test_strategy_history_defaults_exclude_voids_but_archive_keeps_complete_legs(tmp_path):
    store, version, arms, _ = _funded_store(tmp_path)
    arm_id = arms[0]
    started = utcnow() - timedelta(minutes=5)
    voided = _seed_position(
        store, version=version, arm_id=arm_id, opened_at=started,
        suffix="history-voided", sell_proceeds_usd=24.0,
    )
    retained_closed = _seed_position(
        store, version=version, arm_id=arm_id,
        opened_at=started + timedelta(seconds=30), suffix="history-retained-closed",
        sell_proceeds_usd=22.0,
    )
    retained_open = _seed_position(
        store, version=version, arm_id=arm_id,
        opened_at=started + timedelta(seconds=60), suffix="history-retained-open",
    )
    store.void_chain_meme_trader_positions(
        [voided["buy_trade_id"]], definition_version=version,
        reason="manual_history_archive", evidence={"archive": True},
    )
    store.close()

    data = _chain_web_data(tmp_path)
    periods = data.strategy_history_periods(arm_id=arm_id, version=version)
    assert periods["periods"][0]["trade_count"] == 3
    first = data.strategy_history(arm_id, version=version, limit=2)
    assert first["total"] == 3
    assert len(first["trades"]) == 2
    assert first["next_before_id"] is not None
    second = data.strategy_history(
        arm_id, version=version, limit=2, before_id=first["next_before_id"],
        through_id=first["through_id"],
    )
    default_rows = first["trades"] + second["trades"]
    assert second["total"] == 3
    assert len(default_rows) == 3
    assert {int(row["shadow_cohort_id"]) for row in default_rows} == {
        retained_closed["cohort_id"], retained_open["cohort_id"],
    }
    assert all(row["accounting_status"] != "VOIDED" for row in default_rows)

    archive = data.strategy_history(
        arm_id, version=version, limit=10, include_voided=True,
    )
    assert archive["total"] == 5
    assert archive["next_before_id"] is None
    archived_legs = [
        row for row in archive["trades"]
        if int(row["shadow_cohort_id"]) == voided["cohort_id"]
    ]
    assert len(archived_legs) == 2
    assert {row["side"] for row in archived_legs} == {"BUY", "SELL"}
    assert all(row["accounting_status"] == "VOIDED" for row in archived_legs)
    assert all(row["void_reason"] == "manual_history_archive" for row in archived_legs)
