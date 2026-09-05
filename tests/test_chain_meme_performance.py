from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from memetrader.chain_web import ChainWebData
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store


def _open_v22(tmp_path: Path, name: str) -> tuple[Store, dict, dict]:
    store = Store(tmp_path / name, initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v22()
    definition = json.loads(registration["definition_json"])
    policy = next(
        item for item in definition["policies"]
        if item["arm_id"] == "broad_mature_continuity_control_v1"
    )
    return store, definition, policy


def _insert_position(
    store: Store,
    *,
    version: str,
    arm_id: str,
    opened_at,
    status: str = "open",
    sell_gross_usd: float | None = None,
    highest_economic_value_usd: float | None = None,
) -> tuple[TokenCandidate, int, int, int | None]:
    token = TokenCandidate(
        chain="solana", address=uuid4().hex, name="Performance fixture",
        symbol="PERF", source="fixture",
    )
    store.upsert_token(token, seen_at=opened_at)
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
                version, token.token_id, "broad_launch", source_snapshot_id,
                "pair-A", iso(opened_at),
            ),
        )
        cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
            "VALUES(?,?,?,?, 'BUY',20,-20,NULL,'fixture',?)",
            (version, arm_id, cohort_id, token.token_id, iso(opened_at)),
        )
        buy_trade_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        sell_trade_id = None
        if status != "open":
            gross = float(sell_gross_usd or 0.0)
            side = "SELL" if status == "closed" else "WRITEOFF"
            store.db.execute(
                "INSERT INTO chain_meme_trader_trades("
                "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    version, arm_id, cohort_id, token.token_id, side, gross, gross,
                    gross - 20.0, "fixture", iso(opened_at + timedelta(seconds=1)),
                ),
            )
            sell_trade_id = int(
                store.db.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
        gross = float(sell_gross_usd or 0.0)
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,realized_proceeds_usd,"
            "allocated_cost_usd,highest_signal_price_usd,highest_economic_value_usd,"
            "status,realized_pnl_usd,opened_at,closed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                version, arm_id, cohort_id, token.token_id, buy_trade_id, 1, 1,
                1.0, 1.0, 20.0, 20.0 if status == "open" else 0.0,
                "20" if status == "open" else "0", "20", 20.0, gross,
                0.0 if status == "open" else 20.0, 1.0,
                highest_economic_value_usd, status,
                0.0 if status == "open" else gross - 20.0, iso(opened_at),
                None if status == "open" else iso(opened_at + timedelta(seconds=1)),
            ),
        )
    return token, cohort_id, buy_trade_id, sell_trade_id


def test_dust_principal_credit_is_idempotent_cash_only_and_preserves_evidence(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    definition = store._chain_meme_trader_effective_definition(
        version, store._chain_meme_trader_registration(version)["definition_json"])
    arm = definition["policies"][0]["arm_id"]
    now = utcnow() + timedelta(seconds=20)
    fixtures = []
    for index, liquidity in enumerate([.5, .5, .5, .5, .5, .5, 1.0, None]):
        token, cohort, buy, sell = _insert_position(
            store, version=version, arm_id=arm, opened_at=now-timedelta(seconds=5),
            status="written_off", sell_gross_usd=0)
        snapshot = store.add_snapshot(TokenSnapshot(
            "solana", token.address, 1, liquidity, 1000, 100, 3, 2,
            observed_at=now-timedelta(seconds=6), ingested_at=now-timedelta(seconds=6),
            raw={"pair": {"pairAddress": "pair-A"}}))
        with store.db:
            store.db.execute("UPDATE chain_meme_trader_positions SET entry_snapshot_id=? "
                             "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
                             (snapshot, version, arm, cohort))
            if index == 5:
                store.db.execute("INSERT INTO chain_meme_trader_accounting_contaminations("
                    "definition_version,arm_id,shadow_cohort_id,source_buy_trade_id,reason,evidence_json,recorded_at) "
                    "VALUES(?,?,?,?,'fixture','{}',?)", (version, arm, cohort, buy, iso(now)))
        fixtures.append((token, cohort, buy, sell))
    raw_trades = [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_trades ORDER BY id")]
    store.record_chain_meme_trader_account_snapshots(definition_version=version, now=now)
    before = store._chain_meme_trader_effective_net_flows(version)[arm]
    config = initial_config()
    config["database"] = "db.sqlite3"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    web = ChainWebData(config_path)
    with web._connect() as connection:
        prior_curve = web._account_curves(connection, version, None, 1000)[arm]
    credited_at = now + timedelta(seconds=20)
    result = store.credit_chain_meme_dust_entries(recorded_at=credited_at)
    assert (result["new_credits"], result["new_amount_usd"]) == (5, 100)
    assert store.credit_chain_meme_dust_entries(recorded_at=credited_at)["new_credits"] == 0
    assert store._chain_meme_trader_effective_net_flows(version)[arm] == pytest.approx(before+100)
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_trades ORDER BY id")] == raw_trades
    final_at = credited_at + timedelta(seconds=20)
    monkeypatch.setattr("memetrader.chain_web.utcnow", lambda: final_at)
    store.record_chain_meme_trader_account_snapshots(definition_version=version, now=final_at)
    snapshot = store.db.execute("SELECT * FROM chain_meme_trader_account_snapshots "
        "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1", (version, arm)).fetchone()
    assert snapshot["cash_usd"] == pytest.approx(960)
    assert snapshot["indicative_equity_usd"] == pytest.approx(960)
    assert snapshot["realized_pnl_usd"] == pytest.approx(-140)
    assert snapshot["indicative_total_pnl_usd"] == pytest.approx(-140)
    live = next(s for s in web.state(compact=True)["strategies"] if s["arm_id"] == arm)["account"]
    assert live["cash_usd"] == pytest.approx(960)
    assert live["capital_credit_usd"] == 100
    assert live["capital_credit_count"] == 5
    assert live["indicative_total_pnl_usd"] == pytest.approx(-140)
    assert live["max_drawdown_usd"] == prior_curve["max_drawdown_usd"]
    full = Store.chain_meme_trader_summary_from_connection(store.db, arm_id=arm)["strategies"][0]["account"]
    assert full["cash_usd"] == pytest.approx(960)
    assert full["capital_credit_usd"] == 100
    with web._connect() as connection:
        curve = web._account_curves(connection, version, None, 1000)[arm]
    assert curve["points"][-1]["total_pnl_usd"] == -140
    assert curve["max_drawdown_usd"] == prior_curve["max_drawdown_usd"]

    # The same null must explain unresolved historical execution, not promise a new quote.
    token, cohort, buy, sell = fixtures[-1]
    with store.db:
        store.db.execute("INSERT INTO chain_meme_trader_market_fill_corrections("
            "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,source_fill_id,source_mark_id,"
            "original_gross_usd,post_liquidity_usd,max_market_gross_usd,replacement_outcome,"
            "cash_adjustment_usd,realized_adjustment_usd,reason,evidence_json,recorded_at) "
            "VALUES(?,?,?,?,?,0,0,0,1000,1000,'UNRESOLVED',0,20,'fixture','{}',?)",
            (sell,version,arm,cohort,token.token_id,iso(final_at)))
    unresolved = next(s for s in ChainWebData(config_path).state(compact=True)["strategies"] if s["arm_id"] == arm)["account"]
    assert unresolved["valuation_status"] == "historical_execution_unresolved"
    assert unresolved["unresolved_corrected_position_count"] == 1
    assert unresolved["current_equity_usd"] is None
    store.close()


def test_confirmed_update_delay_credit_uses_closed_net_loss_and_never_duplicates(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    definition = store._chain_meme_trader_effective_definition(
        version, store._chain_meme_trader_registration(version)["definition_json"])
    arm = definition["policies"][0]["arm_id"]
    now = utcnow() + timedelta(seconds=20)
    cases = []
    for status, proceeds, liquidity in [("closed", 12, 1000), ("closed", 30, 1000),
                                        ("open", 0, 1000), ("written_off", 0, .5)]:
        token, cohort, buy, _ = _insert_position(store, version=version, arm_id=arm,
            opened_at=now-timedelta(seconds=5), status=status, sell_gross_usd=proceeds)
        snapshot = store.add_snapshot(TokenSnapshot("solana", token.address, 1, liquidity, 1000, 100, 3, 2,
            observed_at=now-timedelta(seconds=6), ingested_at=now-timedelta(seconds=6)))
        with store.db:
            # Market projection stores the shared entry-fill ID in the legacy source field, not ledger BUY ID.
            store.db.execute("UPDATE chain_meme_trader_positions SET entry_snapshot_id=?,source_buy_trade_id=90000+source_buy_trade_id WHERE source_buy_trade_id=?",
                             (snapshot, buy))
        cases.append((token, buy))
    # Missing catalog identities remain visible in monitoring instead of disappearing from its denominator.
    with store.db:
        store.db.execute("DELETE FROM tokens WHERE token_id=?", (cases[2][0].token_id,))
    config = initial_config()
    config["database"] = "db.sqlite3"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    coverage = ChainWebData(config_path).performance_state()["held_by_chain"]["solana"]
    assert (coverage["tokens"], coverage["missing"]) == (1, 1)
    assert store.credit_chain_meme_dust_entries(recorded_at=now)["new_amount_usd"] == 20
    original = [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_trades ORDER BY id")]
    cash_before = store._chain_meme_trader_effective_net_flows(version)[arm]
    ids = [buy for _, buy in cases]
    result = store.credit_chain_meme_update_delay_losses(ids, evidence={"cause": "confirmed orphan catalog"}, recorded_at=now)
    assert (result["new_credits"], result["new_amount_usd"]) == (1, 8)
    assert result["pending_buy_ids"] == [ids[2]]
    assert store.credit_chain_meme_update_delay_losses(ids, evidence={"cause": "same failure"}, recorded_at=now)["new_credits"] == 0
    assert store._chain_meme_trader_effective_net_flows(version)[arm] == pytest.approx(cash_before+8)
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_trades ORDER BY id")] == original
    store.record_chain_meme_trader_account_snapshots(definition_version=version, now=now)
    monkeypatch.setattr("memetrader.chain_web.utcnow", lambda: now+timedelta(seconds=1))
    account = next(s for s in ChainWebData(config_path).state(compact=True)["strategies"] if s["arm_id"] == arm)["account"]
    assert account["update_delay_loss_position_count"] == 1
    assert account["engineering_anomaly_position_count"] == 2
    assert account["research_metrics_eligible"] is False
    store.close()


def test_unchanged_market_and_equity_evaluations_do_not_update_positions(
    tmp_path: Path,
):
    store, definition, policy = _open_v22(tmp_path, "no-op-updates.sqlite3")
    now = utcnow()
    token, cohort_id, _, _ = _insert_position(
        store, version=definition["version"], arm_id=policy["arm_id"],
        opened_at=now - timedelta(seconds=1),
        highest_economic_value_usd=19.2,
    )
    store.upsert_chain_meme_trader_market_mark(
        token,
        TokenSnapshot(
            "solana", token.address, 1.0, 100_000, 100_000, 100, 5, 2,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"pairAddress": "pair-A"}},
        ),
        recorded_at=now,
    )
    before = store.db.total_changes
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=definition["version"], now=now,
    ) == 0
    assert store.db.total_changes == before

    store.db.execute(
        "INSERT INTO chain_meme_trader_position_equity_frames("
        "frame_version,definition_version,shadow_cohort_id,quote_result_id,"
        "input_amount_raw,valuation_status,remaining_min_executable_recovery_usd,"
        "arm_values_json,requested_at,completed_at,decision_at,recorded_at) "
        "VALUES(?,?,?,?,?,'UNKNOWN_NO_ROUTE',NULL,?,?,?,?,?)",
        (
            Store.CHAIN_MEME_TRADER_POSITION_EQUITY_FRAME_VERSION,
            definition["version"], cohort_id, 999, "20",
            json.dumps({policy["arm_id"]: {
                "total_entry_debit_usd": 20.0,
                "total_executable_equity_usd": None,
                "economic_return": None,
            }}),
            iso(now), iso(now), iso(now), iso(now),
        ),
    )
    frame_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
    before = store.db.total_changes
    assert store.evaluate_chain_meme_trader_stage4_v2_frame(
        frame_id, definition_version=definition["version"],
    ) == 0
    assert store.db.total_changes == before
    position = store.db.execute(
        "SELECT last_evaluated_at FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (definition["version"], policy["arm_id"], cohort_id),
    ).fetchone()
    assert position["last_evaluated_at"] is None
    store.close()


def test_market_exit_evaluation_can_be_scoped_to_refreshed_tokens(tmp_path: Path):
    store, definition, policy = _open_v22(tmp_path, "scoped-market-exit.sqlite3")
    version = definition["version"]
    now = utcnow()
    first, _, _, _ = _insert_position(
        store, version=version, arm_id=policy["arm_id"],
        opened_at=now - timedelta(minutes=300),
    )
    second, _, _, _ = _insert_position(
        store, version=version, arm_id=policy["arm_id"],
        opened_at=now - timedelta(minutes=300),
    )
    for token in (first, second):
        store.upsert_chain_meme_trader_market_mark(
            token,
            TokenSnapshot(
                "solana", token.address, 1.0, 100_000, 100_000, 100, 5, 2,
                observed_at=now, ingested_at=now, provider="dexscreener",
                raw={"pair": {"pairAddress": f"pair-{token.address}"}},
            ),
            recorded_at=now,
        )

    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=now, token_ids=[first.token_id],
    ) == 1
    marks = store.db.execute(
        "SELECT token_id FROM chain_meme_trader_positions p JOIN "
        "chain_meme_trader_marks m ON m.id=p.pending_mark_id "
        "WHERE p.definition_version=?",
        (version,),
    ).fetchall()
    assert [row["token_id"] for row in marks] == [first.token_id]
    store.close()


def test_market_account_snapshot_sql_aggregation_preserves_effective_results(
    tmp_path: Path,
):
    store, definition, policy = _open_v22(tmp_path, "snapshot-aggregation.sqlite3")
    version = definition["version"]
    arm_id = policy["arm_id"]
    now = utcnow()
    open_token, _, _, _ = _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=4),
    )
    _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=6), status="closed", sell_gross_usd=30.0,
    )
    corrected_token, corrected_cohort, _, corrected_sell = _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=8), status="closed", sell_gross_usd=2.0,
    )
    _, contaminated_cohort, contaminated_buy, _ = _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=10), status="closed", sell_gross_usd=5.0,
    )
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_market_fill_corrections("
            "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
            "source_fill_id,source_mark_id,original_gross_usd,post_liquidity_usd,"
            "max_market_gross_usd,replacement_outcome,replacement_gross_usd,"
            "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
            "reason,evidence_json,recorded_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,'SELL',?,?,?,?,?,'{}',?)",
            (
                corrected_sell, version, arm_id, corrected_cohort,
                corrected_token.token_id, 1, 1, 2.0, 100_000.0, 25.0, 25.0,
                23.0, 23.0, iso(now), "fixture correction", iso(now),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_accounting_contaminations("
            "definition_version,arm_id,shadow_cohort_id,source_buy_trade_id,"
            "reason,evidence_json,recorded_at) VALUES(?,?,?,?,?,'{}',?)",
            (
                version, arm_id, contaminated_cohort, contaminated_buy,
                "fixture contamination", iso(now),
            ),
        )
    store.upsert_chain_meme_trader_market_mark(
        open_token,
        TokenSnapshot(
            "solana", open_token.address, 2.0, 100_000, 100_000, 100, 5, 2,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"pairAddress": "pair-open"}},
        ),
        recorded_at=now,
    )
    traced: list[str] = []
    store.db.set_trace_callback(traced.append)
    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=now,
    )
    store.db.set_trace_callback(None)
    account = store.db.execute(
        "SELECT * FROM chain_meme_trader_account_snapshots WHERE "
        "definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1",
        (version, arm_id),
    ).fetchone()
    assert account["cash_usd"] == pytest.approx(995.0)
    assert account["realized_pnl_usd"] == pytest.approx(15.0)
    assert account["open_position_count"] == 1
    assert account["closed_position_count"] == 2
    assert account["written_off_position_count"] == 0
    assert account["indicative_unrealized_pnl_usd"] == pytest.approx(18.4)
    assert account["indicative_total_pnl_usd"] == pytest.approx(33.4)
    assert any("SUM(CASE WHEN status='open'" in query for query in traced)
    assert not any(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=" in query
        and "status!='ineligible'" in query
        for query in traced
    )
    store.close()


def test_summary_excludes_contaminated_corrections_from_formal_counts(
    tmp_path: Path,
):
    store, definition, policy = _open_v22(
        tmp_path, "summary-contaminated-corrections.sqlite3"
    )
    store.activate_chain_meme_trader_v22()
    version = definition["version"]
    arm_id = policy["arm_id"]
    now = utcnow()
    held_token, _, _, _ = _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=2),
    )
    corrected = []
    for offset, outcome in enumerate(("UNRESOLVED", "SELL", "WRITEOFF"), start=3):
        token, cohort_id, buy_trade_id, sell_trade_id = _insert_position(
            store, version=version, arm_id=arm_id,
            opened_at=now - timedelta(seconds=offset), status="closed",
            sell_gross_usd=30.0,
        )
        corrected.append((token, cohort_id, buy_trade_id, sell_trade_id, outcome))
    with store.db:
        for index, (token, cohort_id, buy_trade_id, sell_trade_id, outcome) in enumerate(
            corrected, start=1,
        ):
            replacement_gross = 25.0 if outcome == "SELL" else None
            cash_adjustment = -5.0 if outcome == "SELL" else -30.0
            realized_adjustment = -5.0 if outcome == "SELL" else (
                -10.0 if outcome == "UNRESOLVED" else -30.0
            )
            store.db.execute(
                "INSERT INTO chain_meme_trader_market_fill_corrections("
                "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
                "source_fill_id,source_mark_id,original_gross_usd,post_liquidity_usd,"
                "max_market_gross_usd,replacement_outcome,replacement_gross_usd,"
                "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
                "reason,evidence_json,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    sell_trade_id, version, arm_id, cohort_id, token.token_id,
                    index, index, 30.0, 100_000.0, 25.0, outcome,
                    replacement_gross, cash_adjustment, realized_adjustment,
                    iso(now), "fixture correction", "{}", iso(now),
                ),
            )
            store.db.execute(
                "INSERT INTO chain_meme_trader_accounting_contaminations("
                "definition_version,arm_id,shadow_cohort_id,source_buy_trade_id,"
                "reason,evidence_json,recorded_at) VALUES(?,?,?,?,?,'{}',?)",
                (
                    version, arm_id, cohort_id, buy_trade_id,
                    "fixture contamination", iso(now),
                ),
            )

    summary = Store.chain_meme_trader_summary_from_connection(
        store.db, arm_id=arm_id,
    )
    strategy = summary["strategies"][0]
    account = strategy["account"]
    assert account["open_position_count"] == 1
    assert account["unresolved_corrected_position_count"] == 0
    assert account["closed_position_count"] == 0
    assert account["written_off_position_count"] == 0
    assert account["terminal_position_count"] == 0
    assert account["win_count"] == 0
    assert account["win_rate_fraction"] is None
    assert account["realized_pnl_usd"] == pytest.approx(0.0)
    assert account["market_fill_correction_count"] == 3
    assert account["accounting_contaminated_position_count"] == 3
    assert summary["open_position_count"] == 1
    assert summary["unique_held_token_count"] == 1
    assert held_token.token_id in {
        position["token_id"] for position in strategy["positions"]
        if position["status"] == "open"
        and position.get("formal_metrics_eligible") is not False
    }
    contaminated_positions = [
        position for position in strategy["positions"]
        if position.get("accounting_status") == "ACCOUNTING_CONTAMINATED"
    ]
    assert len(contaminated_positions) == 3
    assert all(
        position["formal_metrics_eligible"] is False
        for position in contaminated_positions
    )
    assert {position["status"] for position in contaminated_positions} == {
        "open", "closed", "written_off",
    }
    store.close()


def test_multiple_sell_corrections_accumulate_per_position_in_store_and_web(
    tmp_path: Path,
):
    config = initial_config()
    config["database"] = "multiple-sell-corrections.sqlite3"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    store, definition, policy = _open_v22(
        tmp_path, config["database"],
    )
    store.activate_chain_meme_trader_v22()
    version = definition["version"]
    arm_id = policy["arm_id"]
    now = utcnow()
    token, cohort_id, _, first_sell_id = _insert_position(
        store, version=version, arm_id=arm_id,
        opened_at=now - timedelta(seconds=3), status="closed", sell_gross_usd=8.0,
    )
    assert first_sell_id is not None
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
            "VALUES(?,?,?,?, 'SELL',22,22,32,'fixture_second_sell',?)",
            (version, arm_id, cohort_id, token.token_id, iso(now - timedelta(seconds=1))),
        )
        second_sell_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "UPDATE chain_meme_trader_positions SET realized_proceeds_usd=30,"
            "realized_pnl_usd=20 WHERE definition_version=? AND arm_id=? "
            "AND shadow_cohort_id=?", (version, arm_id, cohort_id),
        )
        for source_trade_id, gross, realized in (
            (first_sell_id, 8.0, -12.0),
            (second_sell_id, 22.0, 32.0),
        ):
            store.db.execute(
                "INSERT INTO chain_meme_trader_market_fill_corrections("
                "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
                "source_fill_id,source_mark_id,original_gross_usd,post_liquidity_usd,"
                "max_market_gross_usd,replacement_outcome,replacement_gross_usd,"
                "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
                "reason,evidence_json,recorded_at) "
                "VALUES(?,?,?,?,?,?,?,?,100000,0,'UNRESOLVED',NULL,?,?,NULL,"
                "'fixture_unresolved','{}',?)",
                (
                    source_trade_id, version, arm_id, cohort_id, token.token_id,
                    source_trade_id, source_trade_id, gross, -gross, -realized,
                    iso(now),
                ),
            )
    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=now,
    )

    summary = Store.chain_meme_trader_summary_from_connection(
        store.db, arm_id=arm_id,
    )
    strategy = summary["strategies"][0]
    position = next(
        row for row in strategy["positions"]
        if int(row["shadow_cohort_id"]) == cohort_id
    )
    assert position["status"] == "open"
    assert position["realized_pnl_usd"] == pytest.approx(0.0)
    assert position["market_fill_correction"]["correction_count"] == 2
    assert strategy["account"]["realized_pnl_usd"] == pytest.approx(0.0)
    assert strategy["account"]["cash_usd"] == pytest.approx(980.0)
    store.close()

    web_state = ChainWebData(config_path).state(compact=True, arm_id=arm_id)
    web_strategy = next(
        row for row in web_state["strategies"] if row["arm_id"] == arm_id
    )
    web_position = next(
        row for row in web_state["open_positions"]
        if int(row["shadow_cohort_id"]) == cohort_id
    )
    assert web_position["realized_pnl_usd"] == pytest.approx(0.0)
    assert web_strategy["account"]["realized_pnl_usd"] == pytest.approx(0.0)
    assert web_strategy["account"]["cash_usd"] == pytest.approx(980.0)


def test_current_strategy_queries_use_targeted_indexes(tmp_path: Path):
    store = Store(tmp_path / "query-plan.sqlite3", initial_cash_usd=1000)
    decision_plan = " ".join(
        str(row["detail"]) for row in store.db.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM chain_meme_trader_entry_decisions "
            "WHERE definition_version=? AND status='admitted' ORDER BY id DESC LIMIT 120",
            (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
        )
    )
    snapshot_plan = " ".join(
        str(row["detail"]) for row in store.db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1",
            (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, "arm"),
        )
    )
    assert "chain_meme_trader_entry_decisions_status_idx" in decision_plan
    assert "chain_meme_trader_account_snapshots_latest_idx" in snapshot_plan
    store.close()
