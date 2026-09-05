from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from memetrader.chain_web import ChainWebData
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store


def _config(tmp_path: Path) -> Path:
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["lock_file"] = "robot.lock"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_account_curves_preserve_full_range_mdd_and_incremental_frontier(
    tmp_path: Path,
):
    config_path = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    version = "chain-web-curve-regression"
    arm_id = "curve-arm"
    started_at = utcnow()
    rows = []
    for offset in range(650):
        equity = 1000.0 + (offset % 20)
        if offset == 100:
            equity = 1300.0
        elif offset == 101:
            equity = 700.0
        total_pnl = equity - 1000.0
        rows.append((
            version, arm_id, iso(started_at + timedelta(seconds=offset)),
            equity, total_pnl, total_pnl, equity,
        ))
    with store.db:
        store.db.executemany(
            "INSERT INTO chain_meme_trader_account_snapshots("
            "definition_version,arm_id,recorded_at,cash_usd,realized_pnl_usd,"
            "indicative_unrealized_pnl_usd,indicative_total_pnl_usd,"
            "indicative_equity_usd,indicative_position_count,indicative_is_complete,"
            "open_position_count,closed_position_count,written_off_position_count,"
            "priced_position_count,valuation_status,ledger_trade_frontier_id) "
            "VALUES(?,?,?,?,?,0,?,?,0,1,0,0,0,0,'complete_market_mark',0)",
            rows,
        )
    store.close()

    web = ChainWebData(config_path)
    connection = sqlite3.connect(tmp_path / "db.sqlite3")
    connection.row_factory = sqlite3.Row
    try:
        curve = web._account_curves(
            connection, version, None, starting_cash=1000.0,
        )[arm_id]
        first_id = rows and connection.execute(
            "SELECT MIN(id) FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=?", (version,),
        ).fetchone()[0]
        last_id = connection.execute(
            "SELECT MAX(id) FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=?", (version,),
        ).fetchone()[0]
        assert len(curve["points"]) <= ChainWebData.LIVE_DETAIL_CURVE_POINTS
        assert curve["points"][0]["id"] == first_id
        assert curve["points"][-1]["id"] == last_id
        assert curve["valid_points"] == 650
        assert curve["max_drawdown_usd"] == pytest.approx(600.0)
        assert curve["max_drawdown_fraction"] == pytest.approx(600.0 / 1300.0)

        next_at = iso(started_at + timedelta(seconds=650))
        connection.execute(
            "INSERT INTO chain_meme_trader_account_snapshots("
            "definition_version,arm_id,recorded_at,cash_usd,realized_pnl_usd,"
            "indicative_unrealized_pnl_usd,indicative_total_pnl_usd,"
            "indicative_equity_usd,indicative_position_count,indicative_is_complete,"
            "open_position_count,closed_position_count,written_off_position_count,"
            "priced_position_count,valuation_status,ledger_trade_frontier_id) "
            "VALUES(?,?,?,?,?,0,?,?,0,1,0,0,0,0,'complete_market_mark',0)",
            (version, arm_id, next_at, 1011.0, 11.0, 11.0, 1011.0),
        )
        connection.commit()
        next_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        traced: list[str] = []
        connection.set_trace_callback(traced.append)
        updated = web._account_curves(
            connection, version, None, starting_cash=1000.0,
        )[arm_id]
        connection.set_trace_callback(None)

        curve_select = next(
            statement for statement in traced
            if "FROM chain_meme_trader_account_snapshots" in statement
        )
        assert f"id>{last_id}" in curve_select.replace(" ", "")
        assert updated["points"][0]["id"] == first_id
        assert updated["points"][-1]["id"] == next_id
        assert updated["valid_points"] == 651
        assert updated["max_drawdown_usd"] == pytest.approx(600.0)
    finally:
        connection.close()


def test_chain_discovery_filters_before_limit_and_reports_actual_decision_funnel(
    tmp_path: Path,
):
    config_path = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader()
    registration = store.register_chain_meme_trader_v6()
    store.activate_chain_meme_trader_v6()
    version = Store.CHAIN_MEME_TRADER_V6_VERSION
    arm_id = Store._json_object(registration["definition_json"])["policies"][0]["arm_id"]
    observed_at = utcnow()

    bsc_token = TokenCandidate(
        chain="bsc", address="0x00000000000000000000000000000000000000b5",
        name="BSC Earlier", symbol="BSCE", source="geckoterminal:bsc",
    )
    store.upsert_token(bsc_token, seen_at=observed_at)
    bsc_round = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll",
        chain_scope="bsc", started_at=observed_at,
    )
    store.add_token_discovery_exposure(
        bsc_round, token_id=bsc_token.token_id, chain="bsc",
        observed_at=observed_at,
    )
    store.finish_token_discovery_round(
        bsc_round, status="completed", requested_count=1, returned_count=1,
        completed_at=observed_at,
    )

    solana_round = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream",
        chain_scope="solana", started_at=observed_at + timedelta(seconds=1),
    )
    for index in range(65):
        store.add_token_discovery_exposure(
            solana_round, token_id=f"solana:later-{index:02d}", chain="solana",
            observed_at=observed_at + timedelta(seconds=index + 1),
        )
    store.finish_token_discovery_round(
        solana_round, status="completed", requested_count=65, returned_count=65,
        completed_at=observed_at + timedelta(seconds=66),
    )

    with store.db:
        store.db.executemany(
            "INSERT INTO chain_meme_trader_entry_decisions("
            "definition_version,arm_id,shadow_cohort_id,token_id,"
            "baseline_quote_result_id,decided_at,status,reason) "
            "VALUES(?,?,?,?,0,?,?,?)",
            [
                (version, arm_id, 8101, bsc_token.token_id, iso(observed_at), "admitted", "fixture"),
                (version, arm_id, 8102, bsc_token.token_id, iso(observed_at), "admitted", "fixture"),
                (version, arm_id, 8103, bsc_token.token_id, iso(observed_at), "rejected", "fixture"),
                (version, arm_id, 8104, "solana:later-64", iso(observed_at), "admitted", "fixture"),
            ],
        )
    store.heartbeat("chain-meme-trader", item=True)
    store.close()

    web = ChainWebData(config_path)
    bsc = web.discovery_state("bsc")
    assert [item["token_id"] for item in bsc["tokens"]] == [bsc_token.token_id]
    assert [item["chain_scope"] for item in bsc["rounds"]] == ["bsc"]
    assert bsc["funnel"] == [{"arm_id": arm_id, "admitted": 2, "rejected": 1}]

    all_chains = web.discovery_state("all")
    all_funnel = next(item for item in all_chains["funnel"] if item["arm_id"] == arm_id)
    assert all_funnel == {"arm_id": arm_id, "admitted": 3, "rejected": 1}
