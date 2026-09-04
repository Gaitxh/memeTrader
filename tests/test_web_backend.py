from __future__ import annotations

import json
import shutil
import socket
import sqlite3
import threading
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey

import memetrader.live_wallets as live_module
from memetrader.autonomous_search import (
    REGISTRY_KEY,
    TREND_LANE_SELECTION_KEY,
    TREND_RESULT_KEY,
    TREND_RUN_KEY,
    TREND_WATCH_SELECTION_KEY,
)
from memetrader.chain_web import ChainWebData, create_server as create_chain_server
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store
from memetrader.strategy import EventEngine
from memetrader.web import APIError, WebData, create_server


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _config(tmp_path: Path) -> tuple[Path, dict]:
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["lock_file"] = "robot.lock"
    config["bridge"]["enabled"] = False
    config["bridge"]["token"] = "bridge-secret-must-never-be-returned"
    config["notifications"]["telegram_bot_token"] = "telegram-secret-must-never-be-returned"
    config["notifications"]["telegram_chat_id"] = "secret-chat-id"
    config["notifications"]["jsonl"] = "notifications.jsonl"
    config["sources"]["rss"] = [
        {"name": "example-news", "url": "https://example.com/feed.xml", "kind": "news", "enabled": True}
    ]
    config["sources"]["mastodon"] = []
    config["sources"]["bluesky_queries"] = []
    config["sources"]["gecko_networks"] = []
    config["sources"]["pumpportal"]["enabled"] = False
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def test_token_detail_exposes_forward_creator_launch_shadow_without_raw_payload(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    observed_at = utcnow()
    token = TokenCandidate(
        chain="solana",
        address="CreatorRiskWebMint",
        name="Creator Risk Web",
        symbol="CRW",
        source="pumpportal:create",
        first_seen_at=observed_at,
        raw={
            "mint": "CreatorRiskWebMint",
            "txType": "create",
            "pump_event_type": "create",
            "traderPublicKey": "CreatorRiskWebWallet",
            "signature": "CreatorRiskWebSignature",
            "bondingCurveKey": "CreatorRiskWebCurve",
            "pool": "pump",
            "initialBuy": 50,
            "solAmount": 0.1,
            "marketCapSol": 20,
            "must_not_be_returned": "raw-launch-secret",
        },
    )
    store.upsert_token(token, seen_at=observed_at)
    store.record_token_launch_fact(token, ingested_at=observed_at)
    store.close()

    payload = WebData(config_path).token_detail(token.token_id)
    shadow = payload["creator_launch_risk"]
    assert shadow["status"] == "observed"
    assert shadow["launch"]["creator_address"] == "CreatorRiskWebWallet"
    assert shadow["launch"]["provider_verified"] is False
    assert shadow["risk_shadow"]["prior_launch_count"] == 0
    serialized = json.dumps(shadow)
    assert "raw-launch-secret" not in serialized
    assert "raw_payload_hash" not in serialized
    assert shadow["decision_eligible"] is False and shadow["affects"] == "none"


def test_chain_meme_trader_api_and_static_page_preserve_forward_contract(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader()
    store.register_chain_meme_trader_v19()
    store.activate_chain_meme_trader_v19()
    observed_at = utcnow()
    store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V19_VERSION,
    )
    for offset in range(1, 15):
        store.record_chain_meme_trader_account_snapshots(
            now=observed_at + timedelta(seconds=offset * 61),
            definition_version=Store.CHAIN_MEME_TRADER_V19_VERSION,
        )
    store.heartbeat("chain-meme-trader", item=True)
    store.close()

    source_universe = (
        Path(__file__).parents[1] / "docs" / "PROJECT_CONTEXT" /
        "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
    )
    target_universe = (
        tmp_path / "docs" / "PROJECT_CONTEXT" /
        "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
    )
    target_universe.parent.mkdir(parents=True)
    shutil.copy2(source_universe, target_universe)

    web_data = ChainWebData(config_path)
    payload = web_data.state()
    assert payload["system"]["runtime_status"] == "running"
    assert len(payload["strategies"]) == 124
    assert payload["definition"]["strategy_count"] == 124
    assert payload["leaderboard"] == []
    assert [item["stage"] for item in payload["strategies"]] == list(range(1, 125))
    assert payload["definition"]["policy_notional_usd"] == 20.0
    assert payload["definition"]["slippage_bps"] == 400
    assert payload["definition"]["additional_fee_usd_each_fill"] == 0.0
    assert payload["definition"]["no_historical_backfill"] is True
    assert payload["definition"]["confirmed_pool_removed_and_no_route"] == (
        "writeoff_remaining_position"
    )

    static = Path(__file__).parents[1] / "src" / "memetrader" / "chain_web_static"
    index = (static / "index.html").read_text(encoding="utf-8")
    app = (static / "app.js").read_text(encoding="utf-8")
    assert "ChainMemeTrader" in index
    assert 'id="canonical-universe"' in index
    assert 'id="strategy-detail"' in index
    assert 'id="universe-summary"' in index
    assert "历史策略与实时结果" in index
    assert 'data-page="overview"' in index
    assert 'data-page="trading"' in index
    assert 'data-page="wallets"' in index
    assert "一个钱包绑定一个策略" in index
    assert "只有成交后才形成持仓" in index
    assert payload["system"]["execution_kernel"] == "order-intent-fill/v1"
    assert payload["system"]["paper_only"] is True
    assert payload["system"]["live_locked"] is True
    assert payload["system"]["live_adapter_status"] == "locked_by_config"
    assert payload["system"]["open_position_count"] == 0
    assert payload["system"]["unique_held_token_count"] == 0
    assert payload["system"]["held_account_states"] == 0
    assert payload["system"]["held_account_alerts"] == 0
    assert payload["system"]["storage"]["database_bytes"] > 0
    assert payload["system"]["storage"]["free_bytes"] > 0
    assert payload["postbuy_research"]["affects_trading"] is False
    assert payload["postbuy_research"]["cases"] == 0
    assert payload["exit_challenger"]["status"] == "not_registered"
    assert payload["trading"]["intent_counts"] == {}
    assert "fetch(`/api/live${query}`" in app
    assert "fetch('/api/strategy-universe'" in app
    assert "function renderUniverse()" in app
    assert "document.visibilityState==='visible'?5000:30000" in app
    assert "fullTimer=setTimeout(refreshFull" not in app
    assert "池与持仓监控" in app
    assert "页面可见时 5 秒刷新" in index
    assert "可见 5 秒 / 隐藏 30 秒" in index
    assert "后台持仓行情优先" in app
    assert "同一个 Token 不会按 ${families.length} 个策略重复访问" in app
    assert "连续无池/价格超过 1 分钟才全损" in app
    assert 'id="overview-strategies"' in index
    assert "PNL 曲线" in index
    assert "capital_neutral_total_pnl_usd" in app
    assert "profit_loss_ratio" in app
    assert "profit_factor" in app
    assert "收益因子" in app
    assert "实时曲线最大回撤" in app
    assert "strategyMetrics" in app
    assert "总资产实时曲线" not in index
    assert "UNKNOWN" in app
    strategy_universe = web_data.strategy_universe()
    assert strategy_universe["status"] == "ok"
    assert len(strategy_universe["families"]) == 124
    assert strategy_universe["provider_requests_triggered"] == 0
    assert strategy_universe["summary"]["active_forward_families"] == 124
    assert strategy_universe["summary"]["frozen_history_families"] == 0

    port = _free_port()
    server = create_chain_server(config_path, "127.0.0.1", port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/api/state")
        assert response.status_code == 200
        assert len(response.json()["strategies"]) == 124
        live_response = httpx.get(f"http://127.0.0.1:{port}/api/live")
        assert live_response.status_code == 200
        live = live_response.json()
        assert "strategy_registry" not in live
        assert "positions" not in live["strategies"][0]
        assert "open_positions" not in live
        assert len(live["strategies"][0]["curve"]) == (
            ChainWebData.LIVE_SPARKLINE_POINTS
        )
        assert live["strategies"][0]["account"]["metric_sample_status"] == "no_closed_results"
        assert live["strategies"][0]["account"]["expectancy_usd"] is None
        assert live["strategies"][0]["account"]["profit_factor"] is None
        assert live["strategies"][0]["account"]["profit_factor_status"] == "no_closed_results"
        assert live["strategies"][0]["account"]["max_drawdown_usd"] == 0.0
        assert len(live_response.content) < len(response.content)
        focused_live = httpx.get(
            f"http://127.0.0.1:{port}/api/live",
            params={"arm_id": live["strategies"][0]["arm_id"]},
        ).json()
        assert focused_live["requested_arm_id"] == live["strategies"][0]["arm_id"]
        assert focused_live["open_positions"] == []
        focused_strategy = next(
            item for item in focused_live["strategies"]
            if item["arm_id"] == live["strategies"][0]["arm_id"]
        )
        assert len(focused_strategy["curve"]) == 15
        assert len(focused_strategy["curve"]) > len(live["strategies"][0]["curve"])
        universe_response = httpx.get(f"http://127.0.0.1:{port}/api/strategy-universe")
        assert universe_response.status_code == 200
        assert len(universe_response.json()["families"]) == 124
        wallet_response = httpx.get(f"http://127.0.0.1:{port}/api/wallets")
        assert wallet_response.status_code == 200
        assert wallet_response.json()["wallets"] == []
        live_enable = httpx.post(
            f"http://127.0.0.1:{port}/api/wallets/live",
            json={"wallet_id": "missing-wallet", "enabled": True},
        )
        assert live_enable.status_code == 400
        assert "全局配置锁定" in live_enable.json()["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_chain_web_state_cache_prunes_expired_entries_and_has_a_fixed_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = ChainWebData(config_path)
    monkeypatch.setattr(
        web,
        "_compact_state_uncached",
        lambda *, arm_id=None: {"arm_id": arm_id},
    )

    for index in range(web.STATE_CACHE_MAX_ENTRIES + 5):
        web.state(compact=True, arm_id=f"arm-{index}")
    assert len(web._state_cache) == web.STATE_CACHE_MAX_ENTRIES

    with web._cache_lock:
        for key, (_, payload) in list(web._state_cache.items()):
            web._state_cache[key] = (0.0, payload)
    web.state(compact=True, arm_id="fresh-arm")
    assert list(web._state_cache) == [(True, "fresh-arm")]


def test_chain_web_profit_factor_and_drawdown_use_effective_results_and_own_curve(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v20()
    store.activate_chain_meme_trader_v20()
    version = Store.CHAIN_MEME_TRADER_V20_VERSION
    arm_id = Store._json_object(registration["definition_json"])["policies"][0]["arm_id"]
    observed = utcnow()
    with store.db:
        for offset, pnl in enumerate((8.0, -5.0), start=1):
            store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
                "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
                "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
                "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
                "realized_pnl_usd,opened_at,closed_at,close_reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,'0','1000',20,1,'closed',?,?,?,?)",
                (
                    version, arm_id, 992_000 + offset,
                    f"solana:metric-{offset}", -992_000 - offset, -1, -1,
                    1.0, 1.04, 20.0 / 1.04, 0.0, pnl,
                    iso(observed), iso(observed + timedelta(microseconds=offset)),
                    "fixture",
                ),
            )
        for offset, total_pnl in enumerate((0.0, 10.0, 4.0, 12.0, 3.0), start=1):
            recorded_at = iso(observed + timedelta(microseconds=10 + offset))
            store.db.execute(
                "INSERT INTO chain_meme_trader_account_snapshots("
                "definition_version,arm_id,recorded_at,cash_usd,realized_pnl_usd,"
                "indicative_unrealized_pnl_usd,indicative_total_pnl_usd,"
                "indicative_position_count,indicative_is_complete,open_position_count,"
                "closed_position_count,written_off_position_count,priced_position_count,"
                "valuation_status,ledger_trade_frontier_id) "
                "VALUES(?,?,?,?,?,0,?,0,1,0,2,0,0,'complete_market_mark',0)",
                (version, arm_id, recorded_at, 1000.0 + total_pnl, total_pnl, total_pnl),
            )
    store.close()

    live = ChainWebData(config_path).state(compact=True, arm_id=arm_id)
    account = next(
        item["account"] for item in live["strategies"] if item["arm_id"] == arm_id
    )
    assert account["profit_factor"] == pytest.approx(1.6)
    assert account["profit_factor_status"] == "available"
    assert account["max_drawdown_usd"] == pytest.approx(9.0)
    assert account["max_drawdown_fraction"] == pytest.approx(0.75)


def test_strategy_universe_refreshes_for_additive_strategy_versions(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v20()
    store.activate_chain_meme_trader_v20()
    store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V20_VERSION,
    )
    store.close()

    source_universe = (
        Path(__file__).parents[1] / "docs" / "PROJECT_CONTEXT" /
        "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
    )
    target_universe = (
        tmp_path / "docs" / "PROJECT_CONTEXT" /
        "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
    )
    target_universe.parent.mkdir(parents=True)
    shutil.copy2(source_universe, target_universe)

    web_data = ChainWebData(config_path)
    assert len(web_data.strategy_universe()["families"]) == 124

    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v21()
    store.activate_chain_meme_trader_v21()
    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V21_VERSION,
    ) == 125
    store.close()

    payload = web_data.state()
    universe = web_data.strategy_universe()
    assert payload["definition"]["strategy_count"] == 125
    assert len(payload["strategies"]) == 125
    assert universe["summary"]["historical_behavior_contract_families"] == 124
    assert universe["summary"]["behavior_contract_families"] == 125
    assert universe["summary"]["active_forward_families"] == 125
    assert len(universe["families"]) == 125
    additive = universe["families"][-1]
    assert additive["display_index"] == 125
    assert additive["active_arm_ids"] == ["broad_principal_lock_runner_v1"]
    assert additive["fidelity_status"] == "ADDITIVE_FORWARD"
    assert universe["provider_requests_triggered"] == 0

    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v22()
    store.activate_chain_meme_trader_v22()
    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V22_VERSION,
    ) == 127
    store.close()

    web_data = ChainWebData(config_path)
    payload = web_data.state()
    universe = web_data.strategy_universe()
    assert payload["definition"]["strategy_count"] == 127
    assert len(payload["strategies"]) == 127
    assert universe["summary"]["behavior_contract_families"] == 127
    assert universe["summary"]["active_forward_families"] == 127
    assert [item["display_index"] for item in universe["families"][-2:]] == [126, 127]
    assert [item["active_arm_ids"] for item in universe["families"][-2:]] == [
        ["broad_flash_tail_first_mover_v1"],
        ["broad_mature_continuity_control_v1"],
    ]

    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    registration = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?", (Store.CHAIN_MEME_TRADER_V22_VERSION,),
    ).fetchone()
    source = Store._json_object(registration["definition_json"])["policies"][-1]
    appended = dict(source)
    for field in ("stage", "behavior_contract_hash"):
        appended.pop(field, None)
    appended.update({
        "arm_id": "web_additive_forward_v1",
        "canonical_id": "web-additive-forward-v1",
        "name": "Web additive forward",
    })
    store.append_chain_meme_trader_policy(appended)
    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V22_VERSION,
    ) == 1
    store.close()

    universe = web_data.strategy_universe()
    assert universe["summary"]["behavior_contract_families"] == 128
    assert universe["families"][-1]["active_arm_ids"] == ["web_additive_forward_v1"]
    live = ChainWebData(config_path).state(compact=True)
    appended_live = next(
        item for item in live["strategies"]
        if item["arm_id"] == "web_additive_forward_v1"
    )
    assert len(live["strategies"]) == 128
    assert appended_live["maturity"] == "waiting"
    assert appended_live["account"]["capital_neutral_total_pnl_usd"] == 0.0
    assert appended_live["account"]["account_return_fraction"] is None


def test_chain_web_reports_distinct_tokens_holding_duration_and_trade_markers(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v20()
    store.activate_chain_meme_trader_v20()
    version = Store.CHAIN_MEME_TRADER_V20_VERSION
    observed = utcnow()
    token = TokenCandidate(
        chain="solana", address=str(Pubkey.new_unique()), name="Web Marker",
        symbol="WEBM", source="dexscreener",
    )
    store.upsert_token(token, seen_at=observed)
    store.add_snapshot(TokenSnapshot(
        "solana", token.address, 1.0, 10_000, 100_000, 250, 2, 1,
        observed_at=observed, ingested_at=observed, provider="dexscreener",
        raw={"pair": {
            "chainId": "solana", "dexId": "pumpfun", "pairAddress": "web-pair",
            "pairCreatedAt": round((observed - timedelta(minutes=1)).timestamp() * 1000),
            "priceUsd": "1.0",
            "baseToken": {
                "address": token.address, "name": token.name, "symbol": token.symbol,
            },
            "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
            "txns": {
                "m5": {"buys": 2, "sells": 1},
                "h1": {"buys": 2, "sells": 1},
            },
            "volume": {"m5": 250.0, "h1": 250.0},
        }},
    ))
    assert store.enroll_chain_meme_trader_v6(
        definition_version=version,
    )["admitted"] == 1
    store.upsert_chain_meme_trader_market_mark(
        token,
        TokenSnapshot(
            "solana", token.address, 1.0, 10_000, 100_000, 250, 2, 1,
            observed_at=observed, ingested_at=observed, provider="dexscreener",
            raw={"pair": {"pairAddress": "web-pair"}},
        ),
        recorded_at=observed,
    )
    positions = store.db.execute(
        "SELECT arm_id,shadow_cohort_id FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND token_id=? ORDER BY arm_id",
        (version, token.token_id),
    ).fetchall()
    assert len(positions) > 1
    first_buy = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND token_id=? AND side='BUY' ORDER BY id LIMIT 1",
        (version, token.token_id),
    ).fetchone()
    sold_at = iso(observed)
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                version, first_buy["arm_id"], first_buy["shadow_cohort_id"],
                token.token_id, "BUY", first_buy["gross_usd"],
                first_buy["net_cash_flow_usd"], first_buy["realized_pnl_usd"],
                first_buy["reason"], first_buy["created_at"],
            ),
        )
        for index, position in enumerate(positions[:2]):
            store.db.execute(
                "INSERT INTO chain_meme_trader_trades("
                "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
                "VALUES(?,?,?,?, 'SELL',?,?,?,'fixture_sell',?)",
                (
                    version, position["arm_id"], position["shadow_cohort_id"],
                    token.token_id, 10.0 + index, 10.0 + index, -10.0 + index,
                    sold_at,
                ),
            )
    store.heartbeat("chain-meme-trader", item=True)
    store.close()

    web = ChainWebData(config_path)
    state = web.state()
    assert state["system"]["open_position_count"] == len(positions)
    assert state["system"]["unique_held_token_count"] == 1
    assert len(state["open_positions"]) == len(positions)
    assert all(item["holding_seconds"] >= 0.0 for item in state["open_positions"])
    compact = web.state(compact=True)
    assert "open_positions" not in compact
    assert compact["system"]["open_position_count"] == len(positions)
    focused = web.state(compact=True, arm_id=positions[0]["arm_id"])
    assert focused["requested_arm_id"] == positions[0]["arm_id"]
    assert len(focused["open_positions"]) == 1
    assert focused["open_positions"][0]["arm_id"] == positions[0]["arm_id"]
    assert focused["open_positions"][0]["status"] == "open"
    assert focused["open_positions"][0]["indicative_value_usd"] == pytest.approx(
        20.0 * 0.96 / 1.04
    )
    assert focused["open_positions"][0]["indicative_unrealized_pnl_usd"] == pytest.approx(
        20.0 * 0.96 / 1.04 - 20.0
    )
    assert focused["open_positions"][0]["market_is_fresh"] is True

    detail = web.token_detail(token.token_id)
    assert len(detail["positions"]) == len(positions)
    assert all(item["holding_seconds"] >= 0.0 for item in detail["positions"])
    assert detail["positions"][0]["indicative_value_usd"] == pytest.approx(
        20.0 * 0.96 / 1.04
    )
    buy_markers = [item for item in detail["trade_markers"] if item["side"] == "BUY"]
    sell_markers = [item for item in detail["trade_markers"] if item["side"] == "SELL"]
    assert len(buy_markers) == 1
    assert buy_markers[0]["strategy_count"] == len(positions)
    assert set(buy_markers[0]["arm_ids"]) == {item["arm_id"] for item in positions}
    assert buy_markers[0]["gross_usd_total"] == pytest.approx(20.0 * len(positions))
    assert len(sell_markers) == 1
    assert sell_markers[0]["strategy_count"] == 2
    assert sell_markers[0]["gross_usd_total"] == pytest.approx(21.0)

    for observed_offset in (-60, 60):
        received = utcnow()
        market_observed = received + timedelta(seconds=observed_offset)
        mark_store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
        with mark_store.db:
            mark_store.db.execute(
                "DELETE FROM chain_meme_trader_market_marks WHERE token_id=?",
                (token.token_id,),
            )
        mark_store.upsert_chain_meme_trader_market_mark(
            token,
            TokenSnapshot(
                "solana", token.address, 1.0, 10_000, 100_000, 250, 2, 1,
                observed_at=market_observed, ingested_at=received,
                provider="dexscreener", raw={"pair": {"pairAddress": "web-pair"}},
            ),
            recorded_at=received,
        )
        mark_store.close()
        stale_web = ChainWebData(config_path)
        stale_position = stale_web.state(
            compact=True, arm_id=positions[0]["arm_id"],
        )["open_positions"][0]
        assert stale_position["market_is_fresh"] is False
        assert stale_position["indicative_value_usd"] is None
        stale_detail = stale_web.token_detail(token.token_id)
        assert stale_detail["market"]["is_fresh"] is False
        assert all(
            item["indicative_value_usd"] is None
            for item in stale_detail["positions"]
        )


def test_chain_web_wallet_views_join_paper_state_without_live_signer_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(live_module, "_dpapi_protect", lambda value: bytes(reversed(value)))
    monkeypatch.setattr(live_module, "_dpapi_unprotect", lambda value: bytes(reversed(value)))
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v20()
    store.activate_chain_meme_trader_v20()
    version = Store.CHAIN_MEME_TRADER_V20_VERSION
    observed = utcnow()
    token = TokenCandidate(
        chain="solana", address=str(Pubkey.new_unique()), name="Wallet Web",
        symbol="WWEB", source="dexscreener",
    )
    snapshot = TokenSnapshot(
        "solana", token.address, 1.0, 10_000, 100_000, 250, 2, 1,
        observed_at=observed, ingested_at=observed, provider="dexscreener",
        raw={"pair": {
            "chainId": "solana", "dexId": "pumpfun", "pairAddress": "wallet-web-pair",
            "pairCreatedAt": round((observed - timedelta(minutes=1)).timestamp() * 1000),
            "priceUsd": "1.0",
            "baseToken": {"address": token.address, "name": token.name, "symbol": token.symbol},
            "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
            "txns": {"m5": {"buys": 2, "sells": 1}, "h1": {"buys": 2, "sells": 1}},
            "volume": {"m5": 250.0, "h1": 250.0},
        }},
    )
    store.upsert_token(token, seen_at=observed)
    store.add_snapshot(snapshot)
    assert store.enroll_chain_meme_trader_v6(definition_version=version)["admitted"] == 1
    store.upsert_chain_meme_trader_market_mark(token, snapshot, recorded_at=observed)
    store.record_chain_meme_trader_account_snapshots(definition_version=version, now=observed)
    strategy_id = str(store.db.execute(
        "SELECT arm_id FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND token_id=? ORDER BY arm_id LIMIT 1", (version, token.token_id),
    ).fetchone()["arm_id"])
    store.heartbeat("chain-meme-trader", item=True)
    store.close()

    web = ChainWebData(config_path)
    monkeypatch.setattr(
        web.wallets, "_balances",
        lambda wallet, refresh=False: {"status": "ok", "sol": 1.0, "usdc": 100.0},
    )
    keypair = Keypair()
    web.wallets.connect(str(keypair), "Wallet overview", strategy_id)
    wallet_id = web.wallets.snapshot()["wallets"][0]["id"]
    vault_ciphertext = web.wallets._vault_path(wallet_id).read_text(encoding="ascii")
    web.wallets._append_execution({
        "wallet_id": wallet_id, "paper_trade_id": 11, "side": "BUY",
        "status": "confirmed", "amount_raw": 20_000_000,
        "signature": "must-not-reach-wallet-detail",
    })

    overview = web.wallet_state()
    wallet = overview["wallets"][0]
    assert wallet["strategy"]["arm_id"] == strategy_id
    assert wallet["strategy"]["open_position_count"] >= 1
    detail = web.wallet_detail(wallet_id)
    assert detail["wallet"]["strategy_id"] == strategy_id
    assert detail["paper"]["open_positions"]
    assert detail["paper"]["trades"]
    assert detail["live_executions"] == [{
        "recorded_at": detail["live_executions"][0]["recorded_at"],
        "paper_trade_id": 11, "side": "BUY", "status": "confirmed",
        "amount_raw": 20_000_000,
    }]
    serialized = json.dumps(detail)
    assert str(keypair) not in serialized
    assert vault_ciphertext not in serialized
    assert "must-not-reach-wallet-detail" not in serialized
    assert "signature" not in serialized


def test_chain_web_error_views_expose_safe_case_lifecycle_only(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    case_id = store.record_system_error(
        area="runtime", component="chain-meme-market-marks", error_type="TimeoutError",
        message_safe="secret=must-not-reach-web", severity="high",
        context_safe={"source": "chain-meme-market-marks", "operation": "batch_quote"},
    )
    assert store.record_system_error(
        area="runtime", component="chain-meme-market-marks", error_type="TimeoutError",
        message_safe="secret=must-not-reach-web", severity="high",
        context_safe={"source": "chain-meme-market-marks", "operation": "batch_quote"},
    ) == case_id
    store.close()

    web = ChainWebData(config_path)
    errors = web.error_state()
    assert errors["summary"] == {
        "open": 1, "high": 1, "new": 1, "in_progress": 0,
        "latest_at": errors["summary"]["latest_at"],
    }
    assert errors["cases"][0]["id"] == case_id
    assert errors["cases"][0]["occurrence_count"] == 2
    assert "fingerprint" not in json.dumps(errors)
    assert "must-not-reach-web" not in json.dumps(errors)

    before = web.error_detail(case_id)
    assert before["status"] == "ok"
    assert len(before["occurrences"]) == 2
    assert before["occurrences"][0]["context"]["operation"] == "batch_quote"
    web.record_web_error(
        "/api/live", ConnectionAbortedError(10053, "client cancelled request")
    )
    assert web.error_state()["summary"]["open"] == 1
    updated = web.update_error({
        "id": case_id, "status": "fixed", "note": "signature=must-not-reach-web",
        "evidence": "private_key=must-not-reach-web", "report_path": "reports/fix.md",
    })
    assert updated["case"]["status"] == "fixed"
    assert updated["repair_reports"][0]["action"] == "fixed"
    assert updated["repair_reports"][0]["report_path"] == "reports/fix.md"
    assert "must-not-reach-web" not in json.dumps(updated)
    with pytest.raises(ValueError, match="invalid error case status"):
        web.update_error({"id": case_id, "status": "auto_fix"})


def test_chain_web_leaderboard_contains_only_current_active_forward_strategies(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader_v19()
    store.activate_chain_meme_trader_v19()
    v20 = json.loads(store.register_chain_meme_trader_v20()["definition_json"])
    store.activate_chain_meme_trader_v20()

    historical = json.loads(store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_registrations "
        "WHERE definition_version=?", (Store.CHAIN_MEME_TRADER_V18_VERSION,),
    ).fetchone()[0])
    historical_policy = next(
        policy for policy in historical["policies"]
        if policy.get("forward_enabled") is False
    )
    with store.db:
        now = iso(utcnow())
        for version, policy, pnl, source_id in (
            (Store.CHAIN_MEME_TRADER_V18_VERSION, historical_policy, 500.0, 1),
            (Store.CHAIN_MEME_TRADER_V20_VERSION, v20["policies"][0], 1.0, 2),
        ):
            store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
                "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
                "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
                "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
                "realized_pnl_usd,opened_at,closed_at,close_reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,'0','1000000000',20,1,'closed',?,?,?,?)",
                (
                    version, policy["arm_id"], source_id,
                    f"solana:leaderboard-{source_id}", source_id, source_id, source_id,
                    1.0, 1.04, 20.0 / 1.04, 0.0, pnl, now, now, "fixture",
                ),
            )
    store.close()

    leaderboard = ChainWebData(config_path).state()["leaderboard"]
    assert leaderboard
    assert all(item["current"] is True for item in leaderboard)
    assert all(item["status"] == "ACTIVE_FORWARD" for item in leaderboard)
    assert all(
        item["definition_version"] == Store.CHAIN_MEME_TRADER_V20_VERSION
        for item in leaderboard
    )
    assert len({item["arm_id"] for item in leaderboard}) == len(leaderboard)


def test_compact_chain_web_excludes_contaminated_pnl_and_pre_correction_curve(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v22()
    store.activate_chain_meme_trader_v22()
    version = Store.CHAIN_MEME_TRADER_V22_VERSION
    arm_id = Store._json_object(registration["definition_json"])["policies"][0]["arm_id"]
    cohort_id = 991_001
    token_id = "solana:compact-contamination"
    opened_at = utcnow() - timedelta(seconds=120)
    closed_at = opened_at + timedelta(seconds=5)
    raw_pnl = 2_000_000.0
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,reason,created_at,recorded_at) "
            "VALUES(?,?,?,?, 'BUY',20,-20,'fixture',?,?)",
            (version, arm_id, cohort_id, token_id, iso(opened_at), iso(opened_at)),
        )
        buy_trade_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at) "
            "VALUES(?,?,?,?, 'SELL',?,?,?,?,?,?)",
            (
                version, arm_id, cohort_id, token_id, raw_pnl + 20.0,
                raw_pnl + 20.0, raw_pnl, "fixture", iso(closed_at), iso(closed_at),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
            "realized_pnl_usd,opened_at,closed_at,close_reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,'0','1000',20,1,'closed',?,?,?,?)",
            (
                version, arm_id, cohort_id, token_id, buy_trade_id, -1, -1, 1.0,
                1.04, 20.0 / 1.04, 0.0, raw_pnl, iso(opened_at), iso(closed_at),
                "fixture",
            ),
        )
    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=opened_at + timedelta(seconds=10),
    ) == 127
    contamination_at = opened_at + timedelta(seconds=20)
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_accounting_contaminations("
            "definition_version,arm_id,shadow_cohort_id,source_buy_trade_id,reason,"
            "evidence_json,recorded_at) VALUES(?,?,?,?,?,'{}',?)",
            (
                version, arm_id, cohort_id, buy_trade_id,
                "fixture_contaminated_descendant", iso(contamination_at),
            ),
        )
    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=opened_at + timedelta(seconds=40),
    ) == 1
    store.close()

    live = ChainWebData(config_path).state(compact=True)
    strategy = next(item for item in live["strategies"] if item["arm_id"] == arm_id)
    assert strategy["account"]["capital_neutral_realized_pnl_usd"] == 0.0
    assert strategy["account"]["capital_neutral_total_pnl_usd"] == 0.0
    assert strategy["account"]["terminal_position_count"] == 0
    assert strategy["maturity"] == "waiting"
    assert strategy["curve"]
    assert all(point["total_pnl_usd"] == 0.0 for point in strategy["curve"])
    assert live["recent_activity"] == []


def test_chain_web_uses_latest_append_only_market_fill_resolution(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v22()
    store.activate_chain_meme_trader_v22()
    version = Store.CHAIN_MEME_TRADER_V22_VERSION
    arm_id = Store._json_object(registration["definition_json"])["policies"][0]["arm_id"]
    token = TokenCandidate("solana", "EffectiveWebMint", "Effective", "EFF")
    opened_at = utcnow() - timedelta(minutes=2)
    raw_closed_at = opened_at + timedelta(seconds=60)
    effective_closed_at = opened_at + timedelta(seconds=5)
    store.upsert_token(token, seen_at=opened_at)
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,reason,created_at) VALUES(?,?,?,?, 'BUY',20,-20,'fixture',?)",
            (version, arm_id, 991_002, token.token_id, iso(opened_at)),
        )
        buy_trade_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
            "VALUES(?,?,?,?, 'SELL',25,25,5,'fixture_raw_sell',?)",
            (version, arm_id, 991_002, token.token_id, iso(raw_closed_at)),
        )
        sell_trade_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
            "realized_pnl_usd,opened_at,closed_at,close_reason) "
            "VALUES(?,?,?,?,?,-1,-1,1,1.04,19.230769,0,'0','1000',20,1,'closed',5,?,?,?)",
            (
                version, arm_id, 991_002, token.token_id, buy_trade_id,
                iso(opened_at), iso(raw_closed_at), "fixture_raw_sell",
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_market_fill_corrections("
            "source_trade_id,definition_version,arm_id,shadow_cohort_id,token_id,"
            "source_fill_id,source_mark_id,original_gross_usd,post_liquidity_usd,"
            "max_market_gross_usd,replacement_outcome,replacement_gross_usd,"
            "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
            "reason,evidence_json,recorded_at) "
            "VALUES(?,?,?,?,?,-1,-1,25,10,10,'WRITEOFF',0,-25,-25,?,?,?,?)",
            (
                sell_trade_id, version, arm_id, 991_002, token.token_id,
                iso(raw_closed_at), "legacy_capacity", "{}", iso(raw_closed_at),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_market_fill_correction_supersessions("
            "source_trade_id,replacement_outcome,replacement_gross_usd,cash_adjustment_usd,"
            "realized_adjustment_usd,replacement_observed_at,reason,evidence_json,recorded_at) "
            "VALUES(?,'UNRESOLVED',NULL,-25,-5,NULL,'legacy_unresolved','{}',?)",
            (sell_trade_id, iso(raw_closed_at + timedelta(seconds=1))),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_market_fill_correction_resolutions("
            "source_trade_id,revision,replacement_outcome,replacement_gross_usd,"
            "cash_adjustment_usd,realized_adjustment_usd,replacement_observed_at,"
            "reason,evidence_json,recorded_at) "
            "VALUES(?,2,'SELL',25,0,0,?,'capacity_rule_retracted','{}',?)",
            (
                sell_trade_id, iso(effective_closed_at),
                iso(raw_closed_at + timedelta(seconds=2)),
            ),
        )
    store.close()

    web = ChainWebData(config_path)
    compact = web.state(compact=True, arm_id=arm_id)
    strategy = next(item for item in compact["strategies"] if item["arm_id"] == arm_id)
    assert strategy["account"]["capital_neutral_realized_pnl_usd"] == 5.0
    assert strategy["account"]["terminal_position_count"] == 1
    assert strategy["curve"][-1]["synthetic_effective_point"] is True
    assert strategy["curve"][-1]["total_pnl_usd"] == 5.0

    detail = web.token_detail(token.token_id)
    assert detail["positions"][0]["status"] == "closed"
    assert detail["positions"][0]["closed_at"] == iso(effective_closed_at)
    sell = next(item for item in detail["trades"] if item["id"] == sell_trade_id)
    assert sell["side"] == "SELL"
    assert sell["gross_usd"] == 25.0
    assert sell["created_at"] == iso(effective_closed_at)
    assert next(item for item in detail["trade_markers"] if item["side"] == "SELL")[
        "created_at"
    ] == iso(effective_closed_at)

    full = web.state()
    registry = next(
        item for item in full["strategy_registry"]
        if item["definition_version"] == version and item["arm_id"] == arm_id
    )
    assert registry["terminal_count"] == 1
    assert registry["realized_pnl_usd"] == 5.0


def test_chain_meme_trader_web_switches_to_active_v6_matrix(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_chain_meme_trader()
    store.register_chain_meme_trader_v6()
    store.activate_chain_meme_trader_v6()
    store.register_chain_meme_trader_immediate_reverseability()
    store.record_chain_meme_trader_account_snapshots(
        definition_version=Store.CHAIN_MEME_TRADER_V6_VERSION,
    )
    store.heartbeat("chain-meme-trader", item=True)
    store.close()

    payload = ChainWebData(config_path).state()
    assert payload["version"] == Store.CHAIN_MEME_TRADER_V6_VERSION
    assert len(payload["strategies"]) == 12
    assert len(payload["strategy_registry"]) == 24
    assert payload["strategy_registry_stats"]["raw_strategy_count"] == 24
    assert all(item["behavior_hash"] for item in payload["strategy_registry"])
    assert all(item["family_hash"] for item in payload["strategy_registry"])
    assert {item["entry_family"] for item in payload["strategies"]} == {
        "broad_launch", "flow_burst", "reawakening",
    }
    assert {item["exit_family"] for item in payload["strategies"]} == {
        "fast_escape", "balanced_harvest", "peak_guard", "postbuy_research",
    }
    assert payload["definition"]["additional_fee_usd_each_fill"] == 0.0
    assert payload["definition"]["no_historical_backfill"] is True
    assert payload["trading"]["intent_counts"] == {}
    assert payload["trading"]["entry_participant_outcomes"] == []
    assert payload["strategies"][0]["entry_participation"] == {
        "projected": 0,
        "skipped_cash_unavailable_at_fill": 0,
    }
    assert payload["immediate_reverseability"]["eligible_entry_fills"] == 0
    assert payload["immediate_reverseability"]["decision_eligible"] is False
    assert payload["immediate_reverseability"]["affects"] == "none"
    assert [row["seconds"] for row in payload["immediate_reverseability"]["horizons"]] == [15, 30, 60]
    static = Path(__file__).parents[1] / "src" / "memetrader" / "chain_web_static"
    assert 'id="reverseability-table"' in (static / "index.html").read_text(encoding="utf-8")
    app = (static / "app.js").read_text(encoding="utf-8")
    assert "renderReverseability(data)" in app
    assert "实际参与 / 历史现金门跳过" in app
    assert "renderStrategyPool(data)" in app
    assert "renderStages(strategies)" not in app
    assert "renderStrategyRegistry(data)" in app


def test_bridge_health_tolerates_a_responsive_local_bridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_path, config = _config(tmp_path)
    config["bridge"].update({"enabled": True, "host": "127.0.0.1", "port": 8765})
    config_path.write_text(json.dumps(config), encoding="utf-8")
    observed: dict[str, object] = {}

    class FakeResponse:
        status = 200

        @staticmethod
        def read(_limit: int) -> bytes:
            return b'{"ok": true}'

    class FakeConnection:
        def __init__(self, host: str, port: int, timeout: float):
            observed.update(host=host, port=port, timeout=timeout)

        def request(self, method: str, path: str) -> None:
            observed.update(method=method, path=path)

        @staticmethod
        def getresponse() -> FakeResponse:
            return FakeResponse()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr("memetrader.web.http.client.HTTPConnection", FakeConnection)

    health = WebData(config_path)._bridge_health()

    assert health["reachable"] is True
    assert health["status"] == "not_observed"
    assert health["collector_active"] is False
    assert observed == {
        "host": "127.0.0.1",
        "port": 8765,
        "timeout": 3.0,
        "method": "GET",
        "path": "/health",
    }


def test_bridge_health_distinguishes_service_reachability_from_fresh_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path, config = _config(tmp_path)
    config["bridge"].update({"enabled": True, "host": "127.0.0.1", "port": 8765})
    config_path.write_text(json.dumps(config), encoding="utf-8")
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.set_kv(
        "browser_platform_heartbeat:x",
        {
            "observed_at": iso(), "platform": "x", "access_state": "content_visible",
            "extension_version": "0.6.6",
        },
    )

    class FakeResponse:
        status = 200

        @staticmethod
        def read(_limit: int) -> bytes:
            return b'{"ok": true}'

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        def request(self, *_args, **_kwargs) -> None:
            pass

        @staticmethod
        def getresponse() -> FakeResponse:
            return FakeResponse()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr("memetrader.web.http.client.HTTPConnection", FakeConnection)

    health = WebData(config_path)._bridge_health()

    assert health["reachable"] is True
    assert health["status"] == "healthy"
    assert health["collector_active"] is True
    assert health["latest_collector_heartbeat_at"] is not None
    assert health["collector_extension_version"] == "0.6.6"

    store.set_kv(
        "browser_platform_heartbeat:x",
        {"observed_at": iso(utcnow() - timedelta(minutes=10)), "platform": "x"},
    )
    stale = WebData(config_path)._bridge_health()
    assert stale["reachable"] is True
    assert stale["status"] == "stale"
    assert stale["collector_active"] is False

    store.add_observation(
        Observation(
            source="x:collector",
            source_kind="social",
            title="Fresh browser capture",
            text="Visible content proves the collector is active.",
            url="https://x.com/collector/status/1",
            availability_proof="local_receive",
            raw={"browser": {"platform": "x"}},
        )
    )
    active_from_observation = WebData(config_path)._bridge_health()
    assert active_from_observation["reachable"] is True
    assert active_from_observation["status"] == "healthy"
    assert active_from_observation["collector_active"] is True
    assert active_from_observation["latest_collector_activity_source"] == (
        "browser_observation"
    )

    class BusyConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        @staticmethod
        def request(*_args, **_kwargs):
            raise TimeoutError

    monkeypatch.setattr("memetrader.web.http.client.HTTPConnection", BusyConnection)
    active_while_probe_busy = WebData(config_path)._bridge_health()
    assert active_while_probe_busy["reachable"] is True
    assert active_while_probe_busy["status"] == "healthy"
    assert active_while_probe_busy["reachability_basis"] == (
        "recent_collector_activity"
    )


def _seed(path: Path) -> tuple[int, str]:
    store = Store(path, initial_cash_usd=1000)
    now = utcnow()
    event_id = store.create_event("Viral otter becomes an internet mascot", ["otter", "mascot"], 72, now)
    observations = [
        Observation(
            source="news-a",
            source_kind="news",
            title="Viral otter becomes an internet mascot",
            text="x" * 2100,
            url="https://news-a.example/story",
            published_at=now - timedelta(minutes=2),
            observed_at=now,
            ingested_at=now,
            role="feature",
            source_item_id="feature-1",
            author="Otter Daily",
            raw={
                "account_type": "publisher",
                "authority_tier": "established",
                "is_verified": True,
                "trend_lane_id": "culture_entertainment",
                "trend_lane_run_id": "seed-lane-run",
                "trend_lane_taxonomy": "trend-lanes/v1",
                "view_count": 125_000,
                "like_count": 8_500,
            },
        ),
        Observation(
            source="browser:x:otter",
            source_kind="social",
            title="Older otter identity page",
            url="https://x.com/otter/status/1",
            published_at=now - timedelta(hours=2),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="identity-1",
            author="otter",
            raw={
                "original_role": "confirmation",
                "stale_first_observation": True,
                "source_entity_id": "otter_daily",
                "bridge_token": "must-never-be-returned",
            },
        ),
        Observation(
            source="promotion-list",
            source_kind="news",
            title="Top coins to buy after viral otter",
            url="https://promotion.example/list",
            observed_at=now,
            ingested_at=now,
            role="promotion",
            source_item_id="promotion-1",
            author="Token Promotions",
            raw={"non_event_market_promotion": True},
        ),
        Observation(
            source="future-clock",
            source_kind="news",
            title="Future timestamp cannot be evidence",
            url="https://future.example/story",
            published_at=now + timedelta(hours=1),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="future-1",
            raw={"original_role": "feature", "published_time_in_future": True},
        ),
    ]
    observation_ids = []
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
        observation_ids.append(observation_id)

    token = TokenCandidate(
        chain="solana",
        address="A" * 32,
        name="Viral Otter",
        symbol="OTTER",
        created_at=now - timedelta(minutes=1),
        first_seen_at=now,
        source="geckoterminal",
        url="https://www.geckoterminal.com/solana/pools/example",
        social_urls=["https://x.com/otter"],
    )
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana",
            address=token.address,
            price_usd=0.01,
            liquidity_usd=50_000,
            market_cap_usd=500_000,
            volume_5m_usd=12_000,
            buys_5m=30,
            sells_5m=10,
            observed_at=now,
            ingested_at=now,
            provider="dexscreener",
        )
    )
    for role, url, kind, platform, surface in (
        ("identity", "https://x.com/otter", "social_profile", "x", "pair_info"),
        ("promotion", "https://dexscreener.com/solana/example", "dex_page", "dexscreener", "boosts_top"),
    ):
        store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "dexscreener",
                "discovery_surface": surface,
                "role": role,
                "original_url": url,
                "normalized_url": url,
                "link_kind": kind,
                "platform": platform,
                "verification_status": "provider_metadata",
                "raw": {"must_not_be_returned": "raw-provider-payload"},
            }
        )
    store.add_token_context_assessment(
        token.token_id,
        trigger="high_momentum_reverse_context",
        status="insufficient_verified_sources",
        snapshot_observed_at=now,
        momentum_score=84,
        assessment={
            "version": "token-context-assessment/v1",
            "decision_eligible": False,
            "affects": "context_display_and_verified_reporting_only",
            "project_claims": {
                "status": "project_attached_unverified",
                "items": [{"url": "https://x.com/otter", "platform": "x", "decision_eligible": False}],
            },
            "community_amplification": {
                "status": "project_channels_only", "platforms": ["x"],
                "summary": "Project-attached channel only.", "decision_eligible": False,
            },
            "public_figure_linkage": {
                "status": "unverified_candidates", "endorsement_inferred": False,
                "decision_eligible": False, "items": [],
            },
            "independent_reporting": {
                "status": "not_decision_eligible", "domains": ["news-a.example"],
                "confirmation_ingested": False, "items": [],
            },
            "onchain_momentum": {
                "snapshot_observed_at": iso(now), "momentum_score": 84,
                "liquidity_usd": 50000, "volume_5m_usd": 12000,
                "buys_5m": 30, "sells_5m": 10, "decision_eligible": False,
            },
        },
        agent_metadata={
            "task": "token_context", "model": "gpt-5.6-luna", "reasoning_effort": "low",
            "tokens_used": 321, "contains_credentials": False,
        },
        audit=[{"url": "https://news-a.example/story", "verified": True, "domain": "news-a.example"}],
        assessed_at=now,
    )
    decision = CandidateDecision(
        event_id=event_id,
        token_id=token.token_id,
        action="WAIT",
        score=65,
        match_score=88,
        canonical_margin=2,
        reasons=["match=88.0"],
        rejected_reasons=["canonical_token_ambiguous"],
        created_at=now,
    )
    decision_id = store.add_decision(decision)
    store.create_shadow_event_cohort(
        decision,
        decision_id=decision_id,
        source_observation_ids=observation_ids,
    )
    store.paper_buy(
        event_id=event_id,
        token=token,
        price=0.01,
        gross_usd=10,
        fee_bps=60,
        reason="test-paper-only",
    )
    store.heartbeat("example-news", item=True)
    day = now.date().isoformat()
    store.set_kv(f"autonomous_search_quota:{day}:trend_scout", 3)
    store.set_kv(f"autonomous_search_tokens:{day}:trend_scout", 12345)
    store.set_kv(TREND_RUN_KEY, iso(now - timedelta(minutes=3)))
    store.set_kv(
        TREND_RESULT_KEY,
        {
            "status": "completed",
            "run_at": iso(now - timedelta(minutes=3)),
            "events": [],
            "metadata": {"model": "fallback-model", "reasoning_effort": "low", "tokens_used": 12345},
        },
    )
    store.start_trend_lane_run(
        run_id="seed-lane-run",
        taxonomy_version="trend-lanes/v1",
        prompt_version="trend-scout/v2-lane-attribution",
        selection_mode="baseline_round_robin",
        surge=False,
        max_web_searches=4,
        started_at=now - timedelta(minutes=3),
        lanes=[
            {
                "id": "culture_entertainment",
                "prompt": "viral animals, internet culture, celebrities and entertainment",
                "event_topics": ["animals_internet_culture", "celebrity_entertainment"],
                "selection_role": "baseline_round_robin",
                "total_lane_count": 5,
            }
        ],
        watch_accounts=[
            {
                "platform": "x", "handle": "otter", "entity_id": "otter_daily",
                "priority": 4, "watch_cadence": "normal", "selection_role": "exploration",
                "learning_basis": "baseline", "learning_multiplier": 1.0,
            }
        ],
    )
    store.finish_trend_lane_run(
        "seed-lane-run",
        status="completed",
        model="gpt-5.3-codex-spark",
        reasoning_effort="low",
        accepted_by_lane={"culture_entertainment": 1},
        observations_by_lane={"culture_entertainment": 2},
        account_results={
            ("x", "otter"): {
                "exact_source_hits": 1, "accepted_event_count": 1, "observation_count": 1,
            }
        },
        finished_at=now - timedelta(minutes=2),
    )
    store.set_kv(
        TREND_LANE_SELECTION_KEY,
        {
            "run_id": "seed-lane-run",
            "mode": "baseline_round_robin",
            "actual_schedule_changed_by_learning": False,
            "selected_lanes": [{"lane_id": "culture_entertainment"}],
        },
    )
    store.set_kv(
        TREND_WATCH_SELECTION_KEY,
        {
            "selected_at": iso(now - timedelta(minutes=3)),
            "policy": {
                "mode": "curated_plus_exploration",
                "attention_activation_available": False,
                "actual_rotation_changed_by_learning": False,
            },
            "accounts": [
                {
                    "platform": "x", "handle": "otter", "entity_id": "otter_daily",
                    "selection_role": "exploration", "learning_basis": "baseline",
                    "learning_multiplier": 1.0,
                }
            ],
            "contains_credentials": False,
        },
    )
    store.set_kv(
        REGISTRY_KEY,
        [
            {
                "name": "paused-dynamic",
                "url": "https://dynamic.example/feed.xml",
                "kind": "rss",
                "status": "paused",
                "pause_reason": "consecutive_poll_failures",
            }
        ],
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 0,
            "task": "trend_scout",
            "model": "gpt-5.3-codex-spark",
            "reasoning_effort": "low",
            "started_at": iso(now - timedelta(minutes=4)),
            "finished_at": iso(now - timedelta(minutes=3)),
            "status": "failed",
            "returncode": 1,
            "fallback": 0,
            "input_tokens": 600,
            "cached_input_tokens": 100,
            "cache_write_input_tokens": 20,
            "output_tokens": 200,
            "reasoning_output_tokens": 80,
            "total_tokens": 1000,
            "accounting_source": "codex_json",
        }
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 1,
            "task": "trend_scout",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
            "started_at": iso(now - timedelta(minutes=3)),
            "finished_at": iso(now - timedelta(minutes=2)),
            "status": "valid_output",
            "returncode": 0,
            "fallback": 1,
            "input_tokens": 300,
            "cached_input_tokens": 50,
            "cache_write_input_tokens": 10,
            "output_tokens": 100,
            "reasoning_output_tokens": 40,
            "total_tokens": 500,
            "accounting_source": "codex_json",
        }
    )
    store.close()
    return event_id, token.token_id


def test_event_attention_trajectory_api_reports_local_scope_without_fake_mentions(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    common = dict(
        source_kind="news",
        title="Viral llama becomes a meme mascot",
        text="Viral llama becomes a meme mascot",
        observed_at=now,
        ingested_at=now,
    )
    event_id, _, _ = engine.ingest(Observation(source="news-one", source_item_id="one", **common))
    engine.ingest(Observation(source="news-two", source_item_id="two", role="confirmation", **common))
    store.close()

    web = WebData(config_path)
    summary = next(item for item in web.events({})["items"] if item["id"] == event_id)
    assert len(summary["attention_history"]) == 2
    assert summary["attention_trajectory"]["status"] == "observed"
    assert summary["attention_trajectory"]["affects"] == "none"
    assert summary["attention_trajectory"]["scope"] == "local_new_observation_arrivals_only"
    assert summary["attention_trajectory"]["unavailable_metrics"]["mention_velocity"]["status"] == "unavailable"
    assert "points" not in summary["attention_trajectory"]
    detail = web.event_detail(event_id)
    assert len(detail["attention_trajectory"]["points"]) == 2
    serialized = json.dumps(detail)
    assert "raw_json" not in serialized and "bridge-secret" not in serialized


def test_event_fact_propagation_and_correction_are_separate_and_agent_assessment_is_context_only(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    common = dict(
        source_kind="news",
        title="Viral alpaca claim spreads online",
        text="Viral alpaca claim spreads online",
        observed_at=now,
        ingested_at=now,
        role="identity",
    )
    event_id, _, _ = engine.ingest(
        Observation(
            source="agent-scout:publisher-a.example",
            source_item_id="report",
            raw={
                "agent_task": "trend_scout",
                "claim_status": "unverified_rumor",
                "factual_confidence": 0.35,
                "attention_confidence": 0.88,
                "decision_eligible": False,
                "affects": "audit_context_only",
            },
            **common,
        )
    )
    engine.ingest(
        Observation(
            source="agent-scout:publisher-b.example",
            source_item_id="correction",
            raw={
                "agent_task": "trend_scout",
                "claim_status": "correction",
                "factual_confidence": 0.8,
                "correction_risk": 0.1,
                "decision_eligible": False,
                "affects": "audit_context_only",
            },
            **common,
        )
    )
    store.close()

    web = WebData(config_path)
    summary = next(item for item in web.events({})["items"] if item["id"] == event_id)
    assert summary["factuality"]["current"]["claim_status"] == "correction"
    assert summary["factuality"]["correction_state"] == "locally_observed"
    assert summary["factuality"]["affects"] == "none"
    assert summary["factuality"]["historical_backfill"] is False
    assert "points" not in summary["factuality"]
    assert summary["attention_trajectory"]["status"] == "context_only"
    detail = web.event_detail(event_id)
    assert [point["claim_status"] for point in detail["factuality"]["points"]] == [
        "unverified_rumor", "correction"
    ]
    assert all(item["decision_eligible"] is False for item in detail["observations"])
    serialized = json.dumps(detail)
    assert "bridge-secret" not in serialized and "raw_json" not in serialized


def test_event_source_revision_timeline_is_safe_forward_only_and_semantically_separate(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    common = dict(
        source="browser:x:publisher",
        source_kind="social",
        title="Publisher shares a viral animal story",
        url="https://x.com/publisher/status/77?token=must-not-return&utm_source=test",
        author="publisher",
        source_item_id="private-origin-item-id",
        observed_at=now,
        ingested_at=now,
        availability_proof="local_receive",
    )
    event_id, _, _ = engine.ingest(
        Observation(text="First version", raw={"source_item_state": "present"}, **common)
    )
    engine.ingest(
        Observation(text="Second version", raw={"source_item_state": "present"}, **common)
    )
    engine.ingest(
        Observation(
            text="Second version",
            role="identity",
            raw={
                "source_item_state": "retracted",
                "source_item_state_evidence": "publisher_retraction_marker",
            },
            **common,
        )
    )
    anchor_observation_id = int(store.db.execute(
        "SELECT id FROM observations WHERE source=? ORDER BY id LIMIT 1", (common["source"],)
    ).fetchone()["id"])
    second_event_id = store.create_event(
        "Second local cluster sharing the exact source item",
        ["shared exact source item"],
        0,
        now,
    )
    store.link_event_observation(second_event_id, anchor_observation_id)
    store.close()

    web = WebData(config_path)
    summary = next(item for item in web.events({})["items"] if item["id"] == event_id)
    assert summary["source_revision_summary"]["revision_count"] == 3
    assert summary["source_revision_summary"]["locally_observed_retractions"] == 1
    assert summary["source_revision_summary"]["affects"] == "none"
    assert "source_item_histories" not in summary["source_revision_summary"]
    assert summary["claim_relation_graph"]["forward_node_count"] == 3
    assert summary["claim_relation_graph"]["relation_count"] == 3
    assert summary["claim_relation_graph"]["resolved_relation_count"] == 3
    assert summary["claim_relation_graph"]["relation_types"] == {
        "supersedes": 2, "corrects": 0, "retracts": 1,
    }
    assert "relations" not in summary["claim_relation_graph"]
    detail = web.event_detail(event_id)
    history = detail["source_revision_summary"]["source_item_histories"][0]
    assert history["availability_state"] == "retracted_locally_observed"
    assert history["origin"]["status"] == "unknown"
    assert [item["kind"] for item in history["revisions"]] == [
        "baseline", "content_edit", "explicit_retracted"
    ]
    assert all(item["decision_eligible"] is False and item["affects"] == "none" for item in history["revisions"])
    relations = detail["claim_relation_graph"]["relations"]
    assert [item["relation_type"] for item in relations] == [
        "supersedes", "supersedes", "retracts"
    ]
    assert all(item["decision_eligible"] is False and item["affects"] == "none" for item in relations)
    assert all(item["source"]["node_id"].startswith("claim-") for item in relations)
    assert detail["claim_relation_graph"]["factual_verification_state"] == "not_verified_by_relation_graph"
    second_detail = web.event_detail(second_event_id)
    assert second_detail["claim_relation_graph"]["relation_count"] == 3
    assert all(
        second_event_id in item["source"]["event_ids"]
        for item in second_detail["claim_relation_graph"]["relations"]
    )
    serialized = json.dumps(detail)
    assert "private-origin-item-id" not in serialized
    assert "must-not-return" not in serialized
    assert '"source_item_id":' not in serialized
    assert "content_sha256" not in serialized
    assert "snapshot_json" not in serialized
    assert "target_url_fingerprint" not in serialized
    assert "previous_assessment_id" not in serialized


def test_claim_relation_web_coverage_excludes_pre_registration_captures(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3")
    source_registered = parse_time(store.db.execute(
        "SELECT registered_at FROM source_item_revision_registrations WHERE definition_version=?",
        (Store.SOURCE_ITEM_REVISION_VERSION,),
    ).fetchone()["registered_at"])
    relation_registered = parse_time(store.db.execute(
        "SELECT registered_at FROM event_claim_relation_registrations WHERE definition_version=?",
        (Store.EVENT_CLAIM_RELATION_VERSION,),
    ).fetchone()["registered_at"])
    old_capture = source_registered + (relation_registered - source_registered) / 2
    event_id, _, _ = EventEngine(store, similarity=0.1).ingest(
        Observation(
            source="boundary-source", source_kind="news", title="Boundary claim",
            text="Old capture", url="https://publisher.example/boundary",
            source_item_id="boundary-1", observed_at=old_capture, ingested_at=old_capture,
        )
    )
    store.close()

    summary = next(item for item in WebData(config_path).events({})["items"] if item["id"] == event_id)
    assert summary["claim_relation_graph"]["coverage_status"] == "not_observed_in_forward_relation_ledger"
    assert summary["claim_relation_graph"]["forward_node_count"] == 0


def _start_server(config: Path, static_dir: Path, access_token_file: Path | None = None):
    server = create_server(
        config,
        "127.0.0.1",
        _free_port(),
        static_dir=static_dir,
        access_token_file=access_token_file,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def test_web_api_empty_database_is_safe_and_live_is_locked(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    health = web.health()
    overview = web.overview()
    assert health["ok"] is True
    assert health["sqlite"]["schema_complete"] is True
    assert health["sqlite"]["quick_check"] == "doctor_only"
    assert health["sqlite"]["hot_path_check"] == "readable_schema_and_journal"
    assert health["live"] == {"enabled": False, "locked": True, "available": False}
    assert {key: overview["counts"][key] for key in ("observations", "events", "tokens", "decisions", "trades")} == {
        "observations": 0,
        "events": 0,
        "tokens": 0,
        "decisions": 0,
        "trades": 0,
    }
    assert overview["counts"]["open_positions"] == 0
    assert overview["account"]["equity_usd"] == 1000
    assert overview["account"]["quote_as_of"] is None
    assert overview["account"]["activity_status"] == "no_trades"
    assert overview["account"]["performance_status"] == "not_observed"
    assert overview["account"]["valuation_status"] == "cash_only"
    assert overview["account"]["equity_curve"][-1]["equity_usd"] == 1000
    assert overview["account"]["equity_curve"][-1]["persisted"] is False
    assert overview["account"]["execution_costs"]["configured_slippage_rate"] == pytest.approx(0.04)
    assert overview["account"]["execution_costs"]["configured_fee_bps"] == pytest.approx(60)
    assert overview["account"]["execution_costs"]["pump_swap_fee_bps"] == pytest.approx(125)
    activity = overview["ingestion_activity"]
    assert activity["truth_source"] == "persisted_sqlite_activity"
    assert activity["status"] == "waiting"
    assert activity["information"]["status"] == "waiting"
    assert activity["information"]["observations_60s"] == 0
    assert activity["tokens"]["status"] == "waiting"
    assert activity["tokens"]["snapshot_updates_5m"] == 0
    assert overview["learning_state"]["status"] == "not_observed"
    assert overview["learning_state"]["shadow"]["current_version_cohorts"] == 0
    assert overview["learning_state"]["token_context"]["independent_tokens"] == 0
    assert overview["learning_state"]["phase_2"]["ready"] is False
    assert overview["learning_state"]["phase_2"]["automatic_activation"] is False
    assert web.events({})["items"] == []
    assert web.tokens({})["items"] == []
    assert web.decisions({})["items"] == []
    empty_sources = web.sources()
    telegram = empty_sources["telegram"]
    assert telegram["status"] == "blocked_by_platform_terms"
    assert telegram["automated_capture"] is False
    assert telegram["agent_processing"] is False
    assert telegram["trade_effect"] is False
    assert telegram["messages_ingested"] == 0
    assert telegram["candidate_count"] == 13
    assert all(item["active_collection"] is False for item in telegram["items"])
    assert all(item["agent_processing"] is False for item in telegram["items"])
    assert telegram["handoff"]["version"] == "telegram-manual-external-origin-handoff/v1"
    assert telegram["handoff"]["summary"]["attempts"] == 0
    assert telegram["handoff"]["write_available"] is False
    assert empty_sources["source_poll_learning"]["status"] == "not_observed"
    assert empty_sources["source_poll_learning"]["affects"] == "review_only_no_schedule_or_trading_effect"
    assert empty_sources["token_discovery_learning"]["status"] == "not_observed"
    assert empty_sources["token_discovery_learning"]["affects"] == "review_only_no_schedule_or_trading_effect"
    assert empty_sources["token_quote_attempts"]["status"] == "not_observed"
    assert empty_sources["token_quote_attempts"]["decision_eligible"] is False
    assert empty_sources["token_quote_attempts"]["affects"] == "quote_scheduling_only"
    assert empty_sources["shadow_followup"]["status"] == "not_observed"
    assert empty_sources["shadow_followup"]["summary"]["cohorts"] == 0
    assert empty_sources["shadow_followup"]["horizons_minutes"] == [15, 60, 240]
    assert empty_sources["token_context_followup"]["status"] == "not_observed"
    assert empty_sources["token_context_followup"]["summary"]["assessments"] == 0
    assert empty_sources["token_context_followup"]["activation"] is False
    assert empty_sources["token_context_followup"]["affects"] == "none"
    assert empty_sources["information_first_shadow"]["status"] == "not_observed"
    assert empty_sources["information_first_shadow"]["summary"]["cohorts"] == 0
    assert empty_sources["information_first_shadow"]["affects"] == "none"
    assert empty_sources["information_first_shadow"]["ilg"]["status"] == "not_observed"
    assert empty_sources["information_first_shadow"]["ilg"]["affects"] == "none"
    assert empty_sources["information_first_shadow"]["ilg"]["definition"]["same_surface_only"] is True
    assert empty_sources["information_first_shadow"]["ilg"]["definition"]["activity"]["market_cap_excluded"] is True
    assert empty_sources["watch_account_learning"]["status"] == "not_observed"
    assert empty_sources["watch_account_learning"]["summary"]["account_exposures"] == 0
    assert empty_sources["learning_closure"]["status"] == "not_observed"
    assert empty_sources["learning_closure"]["breakpoint"] == "browser_exposure"
    assert [item["count"] for item in empty_sources["learning_closure"]["stages"]] == [0, 0, 0, 0, 0]
    assert empty_sources["learning_closure"]["conversion_rates_available"] is False
    assert empty_sources["watch_attention_policy"]["version"] == "watch-attention/v3-experiment-gated"
    assert empty_sources["watch_attention_policy"]["status"] == "not_configured"
    assert empty_sources["watch_attention_policy"]["items"] == []
    assert empty_sources["attention_experiment"]["status"] == "not_registered"
    assert empty_sources["attention_experiment"]["actual_multiplier"] == 1.0
    assert empty_sources["attention_experiment"]["automatic_promotion"] is False
    audit = web.audit()
    assert audit["status"] == "policy_only"
    assert audit["policy_enforced"] is True
    assert audit["future_data_rejected"] is None
    assert all(item["status"] != "pass" for item in audit["cases"])
    assert audit["missed_opportunity"]["status"] == "not_observed"
    assert audit["missed_opportunity"]["summary"]["audited_outcomes"] == 0
    assert audit["missed_opportunity"]["decision_eligible"] is False
    assert audit["missed_opportunity"]["affects"] == "none"
    attribution = audit["missed_opportunity_no_decision_attribution"]
    assert attribution["status"] == "registered_waiting"
    assert attribution["summary"]["attributions"] == 0
    assert attribution["decision_eligible"] is False
    assert attribution["affects"] == "none"
    jupiter_quote = audit["token_universe_jupiter_quote"]
    assert jupiter_quote["status"] == "not_observed"
    assert jupiter_quote["summary"]["results"] == 0
    assert jupiter_quote["decision_eligible"] is False
    assert jupiter_quote["affects"] == "none"
    onchain_jupiter = audit["onchain_only_jupiter_quote"]
    assert onchain_jupiter["status"] == "not_observed"
    assert onchain_jupiter["summary"]["valid_round_trips"] == 0
    assert onchain_jupiter["decision_eligible"] is False
    assert onchain_jupiter["affects"] == "none"
    addressability = audit["kol_token_addressability"]
    assert addressability["status"] == "registered_waiting"
    assert addressability["version"] == Store.KOL_TOKEN_ADDRESSABILITY_VERSION
    assert addressability["summary"]["cohorts"] == 0
    assert addressability["summary"]["route_results"] == 0
    assert addressability["route_status"] == "registered_waiting"
    assert addressability["route_disposition"] is None
    assert addressability["route_versions"][-1]["version"] == (
        Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION
    )
    assert addressability["route_versions"][-1]["status"] == "registered_waiting"
    assert addressability["versions"][-1]["version"] == Store.KOL_TOKEN_ADDRESSABILITY_VERSION
    assert addressability["versions"][-1]["summary"]["cohorts"] == 0
    assert addressability["decision_eligible"] is False
    assert addressability["affects"] == "none"
    holder_shadow = audit["solana_holder_shadow"]
    assert holder_shadow["status"] == "registered"
    assert holder_shadow["summary"]["cohorts"] == 0
    assert holder_shadow["decision_eligible"] is False
    assert holder_shadow["affects"] == "none"
    assert holder_shadow["definition"]["stored_data"].endswith("no_owner_addresses")
    shadow_review = audit["agent_shadow_review"]
    assert shadow_review["status"] == "registered_waiting"
    assert shadow_review["summary"]["inputs"] == 0
    assert shadow_review["summary"]["dispatch_count"] == 0
    assert shadow_review["decision_eligible"] is False
    assert shadow_review["affects"] == "none"
    substitutions = audit["constraint_substitutions"]
    assert substitutions["version"] == "constraint-substitution-matrix/v1"
    assert substitutions["illegal_or_unsafe_bypass_allowed"] is False
    assert any(item["id"] == "telegram_content_ingestion" for item in substitutions["items"])


def test_web_audit_keeps_kol_addressability_versions_separate(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    legacy_version = "kol-token-addressability-lag/v1-addressability-first"
    now = iso()
    with store.db:
        store.db.execute(
            "INSERT INTO kol_token_addressability_registrations("
            "definition_version,registered_at,activation_observation_id,definition_json) "
            "VALUES(?,?,0,?)",
            (legacy_version, now, json.dumps({"version": legacy_version})),
        )
        store.db.execute(
            """
            INSERT INTO kol_token_addressability_cohorts(
                cohort_key,definition_version,observation_id,event_id,platform,handle,
                source_entity_id,configured_priority,signal_available_at,source_published_at,
                source_observed_at,source_ingested_at,event_attention,seed_status,
                identifiers_json,frozen_queries_json,definition_hash,
                decision_eligible,affects,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'no_seed_at_signal','[]','[]','',0,'none',?)
            """,
            (
                "legacy-cohort", legacy_version, 9000, 9000, "x", "@legacy", "legacy",
                5, now, now, now, now, 22.0, now,
            ),
        )
    store.close()

    addressability = WebData(config_path).audit()["kol_token_addressability"]
    assert addressability["version"] == Store.KOL_TOKEN_ADDRESSABILITY_VERSION
    assert addressability["status"] == "registered_waiting"
    assert addressability["summary"]["cohorts"] == 0
    by_version = {item["version"]: item for item in addressability["versions"]}
    assert by_version[legacy_version]["summary"]["cohorts"] == 1
    assert by_version[Store.KOL_TOKEN_ADDRESSABILITY_VERSION]["summary"]["cohorts"] == 0


def test_web_audit_jupiter_quote_is_aggregate_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()

    def summary(_connection):
        return {
            "status": "collecting",
            "version": Store.TOKEN_UNIVERSE_JUPITER_QUOTE_VERSION,
            "summary": {
                "results": 4, "quoted": 2, "avg_quote_delay_seconds": 1.25,
                "max_quote_delay_seconds": 3.5,
                "avg_round_trip_min_return": 0.08,
                "min_round_trip_min_return": -0.04,
                "max_round_trip_min_return": 0.20,
                "api_key": "secret",
            },
            "phases": [
                {"phase": "baseline_buy", "terminal_status": "quoted", "count": 2,
                 "requestId": "hidden"},
                {"phase": "baseline_buy", "terminal_status": "no_route", "count": 1},
                {"phase": "target_sell", "terminal_status": "error", "count": 1},
            ],
            "recent": [{
                "token_id": "solana:CA123", "phase": "baseline_buy",
                "terminal_status": "quoted", "source_observed_at": "2026-09-01T01:00:00Z",
                "requested_at": "2026-09-01T01:00:01Z",
                "completed_at": "2026-09-01T01:00:02Z", "quote_delay_seconds": 2.0,
                "router": "metis", "mode": "ExactIn",
                "other_amount_threshold_raw": "39000000", "slippage_bps": 100,
                "round_trip_min_return": 0.114285714,
                "route_plan": [{
                    "amm_key": "amm", "label": "Raydium", "input_mint": "USDC",
                    "output_mint": "CA123", "in_amount_raw": "35000000",
                    "out_amount_raw": "123", "fee_amount_raw": "1",
                    "fee_mint": "USDC", "percent": 100,
                    "transaction": "hidden", "requestId": "hidden", "taker": "hidden",
                }],
                "raw": {"transaction": "hidden"}, "api_key": "hidden",
            }],
            "decision_eligible": True,
            "affects": "decision",
        }

    def validity_summary(_connection):
        return {
            "status": "collecting",
            "version": Store.TOKEN_UNIVERSE_JUPITER_QUOTE_VALIDITY_VERSION,
            "registered_at": "2026-09-01T01:00:00Z",
            "activation_cohort_id": 12,
            "activation_quote_result_id": 4,
            "definition": {
                "baseline_anchor": "baseline_source_recorded_at",
                "target_anchor": "fixed_forward_outcome_target_at",
                "max_queue_delay_seconds": 30,
                "max_total_delay_seconds": 45,
                "round_trip_requires": "both_legs_time_valid_and_quoted",
                "legacy_v1_semantics": "raw_quote_only_validity_unknown",
                "api_key": "hidden",
            },
            "summary": {
                "results": 2, "time_valid": 1, "time_valid_quoted": 1,
                "valid_round_trips": 0, "legacy_validity_unknown": 4,
                "avg_queue_delay_seconds": 10, "max_queue_delay_seconds": 31,
                "avg_total_delay_seconds": 12, "max_total_delay_seconds": 46,
                "avg_round_trip_min_return": None,
                "min_round_trip_min_return": None,
                "max_round_trip_min_return": None,
                "transaction": "hidden",
            },
            "statuses": [{
                "phase": "baseline_buy", "validity_status": "queue_delay_expired",
                "quote_terminal_status": "not_requested", "count": 1,
                "requestId": "hidden",
            }],
            "recent": [{
                "token_id": "solana:CA123", "phase": "baseline_buy",
                "validity_status": "valid", "quote_terminal_status": "quoted",
                "target_at": None, "anchor_at": "2026-09-01T01:00:00Z",
                "source_observed_at": "2026-09-01T01:00:00Z",
                "source_ingested_at": "2026-09-01T01:00:00Z",
                "source_recorded_at": "2026-09-01T01:00:00Z",
                "requested_at": "2026-09-01T01:00:10Z",
                "completed_at": "2026-09-01T01:00:12Z",
                "source_ready_delay_seconds": 0, "queue_delay_seconds": 10,
                "request_duration_seconds": 2, "total_delay_seconds": 12,
                "max_queue_delay_seconds": 30, "max_total_delay_seconds": 45,
                "round_trip_min_return": None, "included_in_round_trip": False,
                "raw": {"transaction": "hidden"},
            }],
            "decision_eligible": True, "affects": "decision",
        }

    monkeypatch.setattr(
        Store, "token_universe_jupiter_quote_summary_from_connection",
        staticmethod(summary), raising=False,
    )
    monkeypatch.setattr(
        Store, "token_universe_jupiter_quote_validity_summary_from_connection",
        staticmethod(validity_summary), raising=False,
    )
    quote = WebData(config_path).audit()["token_universe_jupiter_quote"]

    assert quote["summary"] == {
        "results": 4, "quoted": 2, "no_route": 1, "errors": 1,
        "quote_only_protocol_invalid": 0, "avg_quote_delay_seconds": 1.25,
        "max_quote_delay_seconds": 3.5, "avg_round_trip_min_return": 0.08,
        "min_round_trip_min_return": -0.04, "max_round_trip_min_return": 0.20,
    }
    assert quote["phases"][0] == {
        "phase": "baseline_buy", "terminal_status": "quoted", "count": 2,
    }
    assert quote["terminal_statuses"] == [
        {"terminal_status": "error", "count": 1},
        {"terminal_status": "no_route", "count": 1},
        {"terminal_status": "quoted", "count": 2},
    ]
    assert quote["recent"] == [{
        "token_id": "solana:CA123", "phase": "baseline_buy",
        "terminal_status": "quoted", "source_observed_at": "2026-09-01T01:00:00Z",
        "requested_at": "2026-09-01T01:00:01Z",
        "completed_at": "2026-09-01T01:00:02Z", "quote_delay_seconds": 2.0,
        "router": "metis", "mode": "ExactIn",
        "other_amount_threshold_raw": "39000000", "slippage_bps": 100,
        "round_trip_min_return": 0.114285714,
        "route_plan": [{
            "amm_key": "amm", "label": "Raydium", "input_mint": "USDC",
            "output_mint": "CA123", "in_amount_raw": "35000000",
            "out_amount_raw": "123", "fee_amount_raw": "1",
            "fee_mint": "USDC", "percent": 100,
        }],
    }]
    assert quote["decision_eligible"] is False and quote["affects"] == "none"
    assert quote["validity"]["summary"]["results"] == 2
    assert quote["validity"]["definition"]["target_anchor"] == "fixed_forward_outcome_target_at"
    assert quote["validity"]["decision_eligible"] is False
    assert quote["validity"]["affects"] == "none"
    serialized = json.dumps(quote).lower()
    assert '"raw":' not in serialized and "transaction" not in serialized
    assert "requestid" not in serialized and "api_key" not in serialized and "taker" not in serialized


def test_web_audit_onchain_jupiter_quote_is_safe_aggregate_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()

    def summary(_connection):
        return {
            "status": "collecting",
            "version": Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
            "registered_at": "2026-09-01T01:00:00Z",
            "activation_shadow_cohort_id": 12,
            "definition": {
                "no_historical_backfill": True,
                "baseline_anchor": "onchain_trigger_recorded_at",
                "target_anchor": "onchain_shadow_frozen_target_at",
                "round_trip_semantics": "minimum_output_lower_bound_not_fill_or_profit",
                "swap_mode": "ExactIn", "slippage_bps": 400,
                "max_queue_delay_seconds": 30, "max_total_delay_seconds": 45,
                "api_key": "hidden", "private_key": "hidden",
            },
            "summary": {
                "eligible_cohorts": 4, "attempts": 3, "results": 3,
                "baseline_terminal": 2, "baseline_pending": 2,
                "baseline_valid_quoted": 1, "target_terminal": 1,
                "valid_round_trips": 1, "positive": 1, "nonpositive": 0,
                "gte_25pct": 1, "independent_trigger_dates": 1,
                "wallet": "hidden",
            },
            "horizons": [{
                "horizon_minutes": 15, "terminal": 1, "valid_quoted": 1,
                "valid_round_trips": 1, "positive": 1, "nonpositive": 0,
                "gte_25pct": 1, "transaction": "hidden",
            }],
            "statuses": [{
                "phase": "target_sell", "quote_terminal_status": "quoted",
                "validity_status": "valid", "count": 1, "requestId": "hidden",
            }],
            "recent": [{
                "token_id": "solana:CA123", "trigger_recorded_at": "2026-09-01T01:00:00Z",
                "phase": "target_sell", "horizon_minutes": 15,
                "quote_terminal_status": "quoted", "validity_status": "valid",
                "queue_delay_seconds": 10, "request_duration_seconds": 2,
                "total_delay_seconds": 12, "round_trip_min_return": 0.30,
                "included_in_round_trip": True, "recorded_at": "2026-09-01T01:15:12Z",
                "transaction": "hidden", "taker": "hidden",
            }],
            "maturity": {
                "mature": False,
                "gate": {
                    "minimum_valid_round_trips": 30,
                    "minimum_independent_trigger_dates": 15,
                    "minimum_positive_results": 5,
                    "minimum_nonpositive_results": 5,
                    "secret": "hidden",
                },
            },
            "decision_eligible": True, "affects": "decision",
        }

    monkeypatch.setattr(
        Store, "onchain_only_jupiter_quote_summary_from_connection",
        staticmethod(summary),
    )
    quote = WebData(config_path).audit()["onchain_only_jupiter_quote"]
    assert quote["summary"]["valid_round_trips"] == 1
    assert quote["horizons"][0]["gte_25pct"] == 1
    assert quote["recent"][0]["round_trip_min_return"] == pytest.approx(0.30)
    assert quote["maturity"]["mature"] is False
    assert quote["decision_eligible"] is False and quote["affects"] == "none"
    serialized = json.dumps(quote).lower()
    for forbidden in (
        "api_key", "private_key", "wallet", "transaction", "requestid", "taker", "secret",
    ):
        assert forbidden not in serialized


def test_telegram_external_origin_handoff_is_forward_only_context_and_keeps_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)
    fetched: list[str] = []

    async def fake_fetch(url: str) -> httpx.Response:
        fetched.append(url)
        final = "https://publisher.example/original-story"
        return httpx.Response(
            200,
            content=(
                b"<html><head><title>Verified external breaking story</title>"
                b"<meta name='description' content='External publisher summary'></head></html>"
            ),
            headers={"Content-Type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", final),
            extensions={"logical_url": final},
        )

    monkeypatch.setattr(web, "_fetch_telegram_external_origin", fake_fetch)
    payload = {
        "catalog_entity_id": "bno_news_telegram",
        "external_url": "https://publisher.example/original-story?utm_source=telegram&token=must-not-store",
        "consent_acknowledged": True,
    }
    result = web.submit_telegram_external_handoff(payload)
    duplicate = web.submit_telegram_external_handoff(payload)
    assert result["status"] == "verified"
    assert duplicate["status"] == "duplicate"
    assert fetched == ["https://publisher.example/original-story"] * 2

    with pytest.raises(APIError, match="public non-Telegram"):
        web.submit_telegram_external_handoff(
            {**payload, "external_url": "https://t.me/BNONews/123"}
        )
    with pytest.raises(APIError, match="accepts only"):
        web.submit_telegram_external_handoff({**payload, "message_text": "must not be accepted"})

    handoff = web.telegram_external_handoffs(write_available=True)
    assert handoff["summary"] == {
        "attempts": 3,
        "completed": 3,
        "pending": 0,
        "verified": 1,
        "duplicate": 1,
        "zero_yield": 0,
        "rejected": 1,
        "error": 0,
    }
    assert handoff["write_available"] is True
    serialized = json.dumps(handoff)
    assert "must-not-store" not in serialized
    assert "message_text" not in serialized

    connection = sqlite3.connect(tmp_path / "db.sqlite3")
    connection.row_factory = sqlite3.Row
    try:
        observation = connection.execute(
            "SELECT * FROM observations WHERE source='telegram-handoff:bno_news_telegram'"
        ).fetchone()
        assert observation["role"] == "identity"
        assert observation["url"] == "https://publisher.example/original-story"
        raw = json.loads(observation["raw_json"])
        assert raw["decision_eligible"] is False
        provenance = connection.execute(
            "SELECT * FROM observation_provenance_assertions WHERE observation_id=?",
            (observation["id"],),
        ).fetchone()
        assert provenance["route_kind"] == "relay"
        assert provenance["origin_identity_state"] == "verified_external_origin_page"
        assert provenance["transport_platform"] == "telegram"
        assert provenance["transport_source"] == "bno_news_telegram"
        assert provenance["decision_eligible"] == 0
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE telegram_external_handoff_attempts SET catalog_entity_id='changed' WHERE id=1"
            )
    finally:
        connection.close()


def test_telegram_external_handoff_http_is_loopback_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    server, thread, base = _start_server(config_path, static)

    async def fake_fetch(url: str) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<title>External origin headline</title>",
            headers={"Content-Type": "text/html"},
            request=httpx.Request("GET", url),
            extensions={"logical_url": url},
        )

    monkeypatch.setattr(server.web_data, "_fetch_telegram_external_origin", fake_fetch)
    payload = {
        "catalog_entity_id": "bno_news_telegram",
        "external_url": "https://publisher.example/story",
        "consent_acknowledged": True,
    }
    try:
        with httpx.Client(timeout=5) as client:
            accepted = client.post(
                f"{base}/api/telegram/external-handoffs",
                headers={"Origin": base},
                json=payload,
            )
            assert accepted.status_code == 200
            assert accepted.json()["decision_eligible"] is False
            visible = client.get(f"{base}/api/telegram/external-handoffs")
            assert visible.status_code == 200
            assert visible.json()["write_available"] is True
            blocked = client.post(
                f"{base}/api/telegram/external-handoffs",
                headers={"Host": "console.example", "Connection": "close"},
                json=payload,
            )
            assert blocked.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_paper_curve_costs_attempts_and_stale_valuation_are_truthful(tmp_path: Path):
    config_path, config = _config(tmp_path)
    config["paper"]["max_quote_age_seconds"] = 1
    config_path.write_text(json.dumps(config), encoding="utf-8")
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(chain="solana", address="P" * 32, name="Paper Cost")
    store.upsert_token(token, seen_at=now - timedelta(seconds=3))
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=10, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=5,
            observed_at=now - timedelta(seconds=3), provider="test-dex",
        )
    )
    store.record_paper_account_snapshot(
        cash_usd=1000, marked_value_usd=0, equity_usd=1000, daily_exposure_usd=0,
        open_position_count=0, priced_position_count=0,
        observed_at=now - timedelta(seconds=4),
    )
    store.paper_buy(
        event_id=1, token=token, price=10.2, quote_price=10, gross_usd=100,
        fee_bps=60, tax_pct=2, reason="web-cost-test",
        quote_observed_at=now - timedelta(seconds=3), quote_provider="test-dex",
        execution_attempted_at=now - timedelta(seconds=2),
    )
    store.record_paper_execution_attempt(
        event_id=1, token_id=token.token_id, side="BUY", status="filled",
        reason="web-cost-test", requested_at=now - timedelta(seconds=2),
        quote_observed_at=now - timedelta(seconds=3), quote_provider="test-dex",
        quote_price=10, execution_price=10.2, gross_usd=100,
    )
    store.record_paper_account_snapshot(
        cash_usd=899.4, marked_value_usd=98, equity_usd=997.4,
        daily_exposure_usd=100, open_position_count=1, priced_position_count=1,
        quote_as_of=now - timedelta(seconds=3), observed_at=now - timedelta(seconds=2),
    )
    store.close()

    portfolio = WebData(config_path).portfolio({})
    assert [item["id"] for item in portfolio["strategy_model"]["strategies"]] == [
        "information_plus_token", "token_only", "token_then_information",
    ]
    assert portfolio["strategy_model"]["cash_ledgers_are_additive"] is False
    lifecycle = portfolio["strategy_model"]["promotion_lifecycle"]
    assert lifecycle["stages"][0] == "COLLECTING"
    assert lifecycle["stages"][-2:] == ["PROMOTABLE", "REJECTED"]
    assert lifecycle["single_trade_online_rewrite"] is False
    assert lifecycle["winner_backfill"] is False
    assert portfolio["strategy_model"]["strategies"][0]["execution_challenger_key"] == (
        "event_route_execution"
    )
    assert portfolio["strategy_model"]["strategies"][1]["exit_comparison_key"] == (
        "onchain_exit_challenger"
    )
    assert portfolio["strategy_model"]["strategies"][2]["entry_pairing"] == "exact"
    assert "activated_at" in portfolio["strategy_model"]["strategies"][1][
        "activation"
    ]
    assert portfolio["strategy_model"]["strategies"][2]["policy_arms"][0][
        "post_entry_information_affects"
    ] == "none"
    arms = {
        arm["arm_id"]: arm
        for strategy in portfolio["strategy_model"]["strategies"]
        for arm in strategy["policy_arms"]
    }
    assert arms["s1-current-paper-baseline"]["policy_role"] == "current_paper_baseline"
    assert arms["s2-fixed-horizon"]["promotion_state"] == "NOT_APPLICABLE_BASELINE"
    assert arms["s2-dynamic-exit-challenger"]["promotion_state"] == "FORWARD_COMPARISON"
    assert arms["s3-causal-control"]["policy_role"] == "causal_control"
    assert all(
        item["exit_architecture"]["dynamic_exit_required"] is True
        for item in portfolio["strategy_model"]["strategies"]
    )
    assert portfolio["strategy_model"]["strategies"][1]["policy_arms"][0][
        "exit_mode"
    ] == "fixed_comparison_baseline"
    assert portfolio["strategy_model"]["strategies"][1]["policy_arms"][1][
        "exit_mode"
    ] == "dynamic"
    assert portfolio["strategy_model"]["strategies"][2]["planned_policy_arms"][0][
        "research_state"
    ] == "not_preregistered"
    assert portfolio["strategy_model"]["strategies"][2]["planned_policy_arms"][0][
        "promotion_state"
    ] == "POLICY_CANDIDATE"
    watch = portfolio["strategy_model"]["research_observers"][0]
    assert watch["id"] == "token_information_watch"
    assert watch["top_level_strategy"] is False
    assert watch["entry_enabled"] is False
    assert watch["affects"] == "none"
    assert portfolio["token_information_watch"]["role"] == "research_observer_only"
    assert portfolio["token_information_confirmation_paper"]["status"] == "not_enabled"
    assert portfolio["narrative_hold"]["status"] == "not_enabled"
    assert portfolio["event_route_execution"]["status"] == "not_enabled"
    assert portfolio["evm_route_research"]["execution"] is False
    assert portfolio["evm_route_research"]["pnl"] is False
    assert portfolio["evm_route_research"]["aggregator_price"]["status"] == (
        "not_registered"
    )
    assert "api_key" not in json.dumps(portfolio["evm_route_research"])
    bsc = next(
        item for item in portfolio["strategy_model"]["chain_execution_status"]
        if item["chain"] == "bsc"
    )
    assert bsc["paper"] == "disabled_until_route_and_cost_complete"
    assert bsc["valuation_authority"] == "research_only"
    assert bsc["cost_components"]["network_fee"] == "UNKNOWN_BNB_GAS"
    assert "sell_transfer_and_tax_checks" in bsc["promotion_blockers"]
    robinhood = next(
        item for item in portfolio["strategy_model"]["chain_execution_status"]
        if item["chain"] == "robinhood"
    )
    assert robinhood["execution_profile_version"] == (
        "robinhood-4663-route-research/v2"
    )
    assert "official_stock_token_rwa_exact_address_exclusion" in (
        robinhood["promotion_blockers"]
    )
    assert len(portfolio["account"]["equity_curve"]) == 3
    assert portfolio["account"]["equity_usd"] is None
    assert portfolio["account"]["valuation_status"] == "incomplete"
    assert portfolio["positions"][0]["quote_stale"] is True
    trade = portfolio["trades"][0]
    assert trade["quote_price"] == pytest.approx(10)
    assert trade["execution_price"] == pytest.approx(10.2)
    assert trade["fee_usd"] == pytest.approx(0.6)
    assert trade["slippage_rate"] == pytest.approx(0.02)
    assert trade["tax_usd"] == pytest.approx(2)
    costs = portfolio["account"]["execution_costs"]
    assert costs["total_fee_usd"] == pytest.approx(0.6)
    assert costs["total_recorded_tax_usd"] == pytest.approx(2)
    assert costs["route_and_chain_fees_modeled"] is False
    assert portfolio["execution_attempts"][0]["status"] == "filled"


def test_web_portfolio_uses_latest_fair_epoch_without_deleting_old_trades(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    with store.db:
        store.db.execute(
            "UPDATE paper_account SET cash_usd=980,realized_pnl_usd=-20,updated_at=?",
            (iso(now - timedelta(minutes=1)),),
        )
        store.db.execute(
            """
            INSERT INTO trades(
                token_id,event_id,side,quantity,price,gross_usd,fee_usd,reason,created_at
            ) VALUES('solana:old',1,'SELL',1,1,1,0,'old-round',?)
            """,
            (iso(now - timedelta(minutes=1)),),
        )
    store.start_simulation_fair_epoch(
        "fair-comparison/web", starting_cash_usd=1000, started_at=now
    )
    store.close()

    portfolio = WebData(config_path).portfolio({})
    assert portfolio["fair_comparison"]["epoch_id"] == "fair-comparison/web"
    assert portfolio["account"]["cash_usd"] == pytest.approx(1000)
    assert portfolio["account"]["realized_pnl_usd"] == pytest.approx(0)
    assert portfolio["trades"] == []
    assert portfolio["account"]["equity_curve"][0]["recorded_at"] >= iso(now)

    connection = sqlite3.connect(tmp_path / "db.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    finally:
        connection.close()


def test_web_sources_exposes_masked_source_poll_learning(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    attempt_id = store.start_source_poll_attempt(
        collector_kind="reverse_news",
        source_key="reverse-news:0123456789abcdef",
        platform="rss_news",
    )
    store.finish_source_poll_attempt(
        attempt_id,
        status="completed",
        fetched_count=4,
        new_observation_count=1,
        decision_eligible_count=1,
        filtered_count=3,
    )
    store.close()

    payload = WebData(config_path).sources()["source_poll_learning"]
    assert payload["status"] == "collecting"
    assert payload["summary"]["completed"] == 1
    assert payload["items"][0]["source_key"] == "reverse-news:0123456789abcdef"
    serialized = json.dumps(payload).lower()
    assert "password" not in serialized and "private_key" not in serialized
    assert "https://" not in serialized and "?q=" not in serialized


def test_web_sources_exposes_forward_token_discovery_without_sensitive_fields(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.register_token_universe_outcome_quality(
        reference_notional_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125,
        max_quote_age_seconds=45, max_tax_pct=10,
    )
    store.register_token_universe_fixed_target_execution(
        paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
    )
    store.register_onchain_only_shadow(
        momentum_threshold=80, paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
        max_quote_delay_seconds=45,
    )
    round_id = store.start_token_discovery_round(
        provider="dexscreener", surface="token_profiles", mode="poll", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        round_id, token_id=f"solana:{'T' * 32}", chain="solana", role="identity",
        first_local_discovery=True, source_link_count=2, new_source_link_count=1,
    )
    store.finish_token_discovery_round(
        round_id, status="completed", requested_count=1, returned_count=2,
    )
    cohort = store.db.execute("SELECT * FROM token_universe_forward_cohorts").fetchone()
    discovered = parse_time(cohort["discovery_recorded_at"])
    quote_round_id = store.start_token_discovery_round(
        provider="dexscreener", surface="universe_baseline",
        mode="batch_quote", chain_scope="solana",
    )
    attempt_ids = store.start_token_discovery_quote_attempts(
        quote_round_id,
        [{
            "cohort_id": cohort["id"], "token_id": cohort["token_id"],
            "chain": "solana", "role": "universe_baseline",
            "queue_due_at": discovered,
            "deadline_at": cohort["baseline_deadline_at"],
        }],
        requested_at=discovered,
    )
    store.finish_token_discovery_quote_attempt(
        attempt_ids[(cohort["token_id"], "universe_baseline")],
        status="error", reason_code="batch_request_failed", error_type="PoolTimeout",
        completed_at=discovered + timedelta(seconds=60),
    )
    store.finish_token_discovery_round(
        quote_round_id, status="error", requested_count=1, error_type="PoolTimeout",
        completed_at=discovered + timedelta(seconds=60),
    )
    for minutes, price in ((1, 1.0), (15, 1.4)):
        when = iso(discovered + timedelta(minutes=minutes, seconds=10))
        store.db.execute(
            "INSERT INTO token_snapshots(token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json) "
            "VALUES(?,?,?,?,?,?,?)",
            (cohort["token_id"], when, when, when, "forward-test", price, "{}"),
        )
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=16))
    store.finalize_token_universe_outcome_quality()
    store.finalize_token_universe_fixed_target_execution()
    store.finalize_missed_opportunity_audits()
    transition_id = store.record_token_universe_funnel_transition(
        str(cohort["token_id"]),
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="web:name-screen",
        metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
    )
    assert transition_id is not None
    assert store.record_token_event_lookup_name_screen(
        int(cohort["id"]), int(transition_id), searchable=False,
    ) is not None
    assert store.finalize_missed_opportunity_no_decision_attributions() == {"inserted": 1}
    store.close()

    sources = WebData(config_path).sources()
    payload = sources["token_discovery_learning"]
    assert payload["status"] == "collecting"
    assert payload["summary"]["completed"] == 1
    assert payload["summary"]["first_local_discovery_count"] == 1
    assert payload["items"][0]["surface"] == "token_profiles"
    serialized = json.dumps(payload).lower()
    assert "password" not in serialized and "private_key" not in serialized
    assert "bridge_token" not in serialized and "https://" not in serialized
    quote_attempts = sources["token_quote_attempts"]
    assert quote_attempts["status"] == "collecting"
    assert quote_attempts["summary"]["attempts"] == 1
    assert quote_attempts["summary"]["errors"] == 1
    assert quote_attempts["summary"]["backoff_active"] == 1
    assert quote_attempts["items"][0]["error_types"] == [
        {"error_type": "PoolTimeout", "count": 1}
    ]
    assert quote_attempts["decision_eligible"] is False
    assert quote_attempts["affects"] == "quote_scheduling_only"
    quote_json = json.dumps(quote_attempts).lower()
    assert cohort["token_id"].lower() not in quote_json
    assert "password" not in quote_json and "private_key" not in quote_json
    assert "bridge_token" not in quote_json and "https://" not in quote_json
    attribution = WebData(config_path).audit()["missed_opportunity_no_decision_attribution"]
    assert attribution["status"] == "collecting"
    assert attribution["summary"]["attributions"] == 1
    assert attribution["statuses"] == [
        {"status": "eligible_trigger_unadmitted", "count": 1}
    ]
    assert attribution["recent"][0]["terminal_transition_id"] == transition_id
    assert attribution["decision_eligible"] is False and attribution["affects"] == "none"
    quality_view = attribution["quality_view"]
    assert quality_view["summary"]["raw_attributions"] == 1
    assert quality_view["summary"]["quality_available_at_classification"] == 1
    assert quality_view["summary"]["quality_missing_at_classification"] == 0
    assert quality_view["summary"]["raw_fixed_return_25"] == 1
    assert quality_view["summary"]["confirmed_executable_known"] == 0
    assert quality_view["decision_eligible"] is False and quality_view["affects"] == "none"
    attribution_json = json.dumps(attribution).lower()
    assert "password" not in attribution_json and "private_key" not in attribution_json
    assert "bridge_token" not in attribution_json and "https://" not in attribution_json
    universe = sources["token_universe_forward"]
    assert universe["status"] == "collecting"
    assert universe["summary"]["cohorts"] == 1
    assert universe["summary"]["baseline_observed"] == 1
    assert universe["decision_eligible"] is False and universe["affects"] == "none"
    universe_json = json.dumps(universe).lower()
    assert "password" not in universe_json and "private_key" not in universe_json
    assert "bridge_token" not in universe_json and "https://" not in universe_json
    miss = WebData(config_path).audit()["missed_opportunity"]
    assert miss["summary"]["audited_outcomes"] == 1
    assert miss["summary"]["potential_misses"] == 1
    assert miss["recent_potential_misses"][0]["funnel_breakpoint"] == "no_decision"
    miss_json = json.dumps(miss).lower()
    assert "password" not in miss_json and "private_key" not in miss_json
    assert "bridge_token" not in miss_json and "https://" not in miss_json
    quality = WebData(config_path).audit()["token_universe_outcome_quality"]
    assert quality["summary"]["assessed_outcomes"] == 1
    assert quality["decision_eligible"] is False and quality["affects"] == "none"
    quality_json = json.dumps(quality).lower()
    assert "raw_json" not in quality_json and "pair_transitions_json" not in quality_json
    assert "password" not in quality_json and "private_key" not in quality_json
    fixed_execution = WebData(config_path).audit()["token_universe_fixed_target_execution"]
    assert fixed_execution["summary"]["assessed_outcomes"] == 1
    assert fixed_execution["summary"]["modeled_executable"] == 0
    assert fixed_execution["terminal_statuses"] == [
        {"terminal_status": "unsupported_chain", "count": 1}
    ]
    assert fixed_execution["decision_eligible"] is False
    assert fixed_execution["affects"] == "none"
    fixed_execution_json = json.dumps(fixed_execution).lower()
    assert "raw_json" not in fixed_execution_json and "private_key" not in fixed_execution_json
    onchain_shadow = WebData(config_path).audit()["onchain_only_shadow"]
    assert onchain_shadow["status"] == "registered_waiting_forward_data"
    assert onchain_shadow["summary"]["cohorts"] == 0
    assert onchain_shadow["maturity"]["mature"] is False
    assert onchain_shadow["definition"]["no_historical_backfill"] is True
    assert onchain_shadow["decision_eligible"] is False
    assert onchain_shadow["affects"] == "none"
    onchain_shadow_json = json.dumps(onchain_shadow).lower()
    assert "raw_json" not in onchain_shadow_json and "private_key" not in onchain_shadow_json
    assert "bridge_token" not in onchain_shadow_json and "https://" not in onchain_shadow_json
    funnel = WebData(config_path).audit()["token_universe_funnel"]
    assert funnel["status"] == "collecting"
    assert funnel["summary"]["cohorts"] == 1
    assert funnel["summary"]["transition_attempts"] == 1
    assert funnel["decision_eligible"] is False and funnel["affects"] == "none"
    funnel_json = json.dumps(funnel).lower()
    assert cohort["token_id"].lower() not in funnel_json
    assert "raw_json" not in funnel_json and "source_record_ids_json" not in funnel_json
    assert "password" not in funnel_json and "private_key" not in funnel_json
    assert "bridge_token" not in funnel_json and "https://" not in funnel_json
    name_screen = WebData(config_path).audit()["token_event_lookup_name_screen"]
    assert name_screen["summary"] == {"screened": 1, "eligible": 0, "rejected": 1}
    assert name_screen["decision_eligible"] is False and name_screen["affects"] == "none"
    name_screen_json = json.dumps(name_screen).lower()
    assert cohort["token_id"].lower() not in name_screen_json
    assert "password" not in name_screen_json and "private_key" not in name_screen_json


def test_learning_closure_does_not_borrow_same_event_outcomes_from_other_source(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    decision_at = utcnow() - timedelta(hours=2)
    event_id = store.create_event("Shared event with independent sources", ["shared event"], 70, decision_at)
    browser = Observation(
        source="browser:x:example", source_kind="social", title="Exact public account post",
        url="https://x.com/example/status/1", author="@example", observed_at=decision_at,
        ingested_at=decision_at, availability_proof="local_receive", role="feature",
        source_item_id="x:example:1", raw={"source_entity_id": "example_media"},
    )
    other = Observation(
        source="independent-news", source_kind="news", title="Independent report of shared event",
        url="https://news.example/shared", observed_at=decision_at, ingested_at=decision_at,
        role="feature", source_item_id="news:shared:1",
    )
    browser_id, _ = store.add_observation(browser)
    other_id, _ = store.add_observation(other)
    store.link_event_observation(event_id, browser_id)
    store.link_event_observation(event_id, other_id)
    token = TokenCandidate(chain="solana", address="Z" * 32, name="Shared Event Token")
    store.upsert_token(token, seen_at=decision_at)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50000,
            market_cap_usd=100000, volume_5m_usd=10000, buys_5m=20, sells_5m=5,
            observed_at=decision_at, provider="test",
        )
    )
    decision = CandidateDecision(
        event_id=event_id, token_id=token.token_id, action="WAIT", score=60,
        match_score=80, canonical_margin=2, reasons=["test"], created_at=decision_at,
    )
    decision_id = store.add_decision(decision)
    store.create_shadow_event_cohort(
        decision, decision_id=decision_id, source_observation_ids=[other_id]
    )
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.1, liquidity_usd=50000,
            market_cap_usd=110000, volume_5m_usd=12000, buys_5m=22, sells_5m=6,
            observed_at=decision_at + timedelta(minutes=61), provider="test",
        )
    )
    store.finalize_shadow_event_outcomes(now=decision_at + timedelta(minutes=65))
    store.db.execute(
        """
        INSERT INTO source_utility_outcomes(
            outcome_key,event_id,token_id,source_observation_id,dimension,value,origin_platform,
            attribution_weight,net_return,opened_at,closed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "other-source-only", event_id, token.token_id, other_id, "source",
            "independent-news", "web", 1.0, 0.1, iso(decision_at), iso(decision_at + timedelta(minutes=65)),
        ),
    )
    store.record_browser_watch_observation(
        {"platform": "x", "handle": "@example", "entity_id": "example_media", "priority": 3},
        observation_id=browser_id, event_id=event_id, observed_at=decision_at,
        decision_eligible=True,
    )
    store.close()

    closure = WebData(config_path).sources()["learning_closure"]
    assert [item["count"] for item in closure["stages"]] == [1, 1, 1, 0, 0]
    assert closure["breakpoint"] == "observed_60m"


def test_web_exposes_forward_admission_reasons_and_keeps_legacy_candidate_uninstrumented(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(chain="solana", address="L" * 32, name="Ledger", symbol="LDG")
    store.upsert_token(token, seen_at=now)
    store.add_token_context_admission_attempt(
        token.token_id,
        outcome="skipped",
        reason="daily_call_limit_reached",
        trigger={"kind": "onchain_momentum", "priority": 1},
        snapshot_observed_at=now,
        momentum_score=88,
        quota_day=now.date().isoformat(),
        daily_call_limit=8,
        calls_used_before=8,
        daily_token_budget=250000,
        tokens_used_before=12000,
        token_reserve_per_call=18000,
        evaluated_at=now,
    )
    event_id = store.create_event("Legacy candidate", ["legacy candidate"], 70, now)
    store.add_decision(
        CandidateDecision(
            event_id, token.token_id, "CANDIDATE", 82, 91, 10, ["legacy"], created_at=now
        )
    )
    store.close()

    web = WebData(config_path)
    sources = web.sources()
    context = sources["token_context_admissions"]
    assert context["summary"]["attempts"] == 1
    assert context["summary"]["admitted"] == 0
    assert context["items"][0]["reason"] == "daily_call_limit_reached"
    assert context["onchain_challenger"]["status"] == "registered"
    assert context["onchain_challenger"]["affects"] == "none"
    shadow = sources["shadow_followup"]["admission"]["summary"]
    assert shadow["candidate_decisions"] == 1
    assert shadow["candidate_instrumented"] == 0
    assert shadow["candidate_legacy_or_uninstrumented"] == 1
    assert shadow["forward_candidate_coverage_rate"] is None
    detail = web.token_detail(token.token_id)
    assert detail["context_admission"]["reason"] == "daily_call_limit_reached"
    assert "password" not in json.dumps(context).lower()


def test_web_api_exposes_real_evidence_wait_portfolio_agents_and_sources(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, token_id = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    store.set_kv(
        "browser_platform_heartbeat:x",
        {
            "platform": "x",
            "visible": True,
            "selector_count": 7,
            "page_url": "https://x.com/i/lists/1",
            "access_state": "authenticated",
            "observed_at": iso(),
            "contains_credentials": False,
        },
    )
    browser_observation = store.db.execute(
        "SELECT id FROM observations WHERE source='browser:x:otter'"
    ).fetchone()
    store.record_browser_watch_observation(
        {
            "platform": "x", "handle": "otter", "entity_id": "otter_daily",
            "priority": 2, "watch_cadence": "normal",
        },
        observation_id=browser_observation["id"],
        event_id=event_id,
        observed_at=iso(),
        decision_eligible=False,
    )
    store.close()
    console_dir = tmp_path / "data" / "web_console"
    console_dir.mkdir(parents=True)
    (console_dir / "console_settings.json").write_text(
        json.dumps(
            {
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "otter",
                        "display_name": "Otter",
                        "url": "https://x.com/otter",
                        "enabled": True,
                        "priority": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    web = WebData(config_path)

    activity = web.overview()["ingestion_activity"]
    assert activity["status"] == "active"
    assert activity["information"]["status"] == "active"
    assert activity["information"]["observations_60s"] == 4
    assert activity["information"]["rate_per_minute_5m"] == pytest.approx(0.8)
    assert activity["tokens"]["status"] == "active"
    assert activity["tokens"]["new_tokens_60s"] == 1
    assert activity["tokens"]["snapshot_updates_60s"] == 1
    assert activity["tokens"]["rate_per_minute_5m"] == pytest.approx(0.4)

    events = web.events({"limit": ["10"]})["items"]
    event_summary = next(item for item in events if item["id"] == event_id)
    assert "observations" not in event_summary
    assert "x" * 600 not in json.dumps(event_summary)
    event = web.event_detail(event_id)
    roles = {item["role"]: item for item in event["observations"]}
    assert event["event_url"] == f"#/events/{event_id}"
    assert event["evidence_ranking"]["method"] == "decision_utility_authority_freshness"
    assert [item["priority_rank"] for item in event["observations"]] == [1, 2, 3, 4]
    assert all(0 <= item["priority_score"] <= 100 for item in event["observations"])
    assert all(item["ranking_method"] == "decision_utility_authority_freshness" for item in event["observations"])
    assert event["source_count"] == 4
    assert event["total_source_count"] == 4
    assert event["eligible_source_count"] == 1
    assert event["eligible_latest_at"] is not None
    assert event["freshness_minutes"] is not None
    feature = next(item for item in event["observations"] if item["source"] == "news-a")
    identity = next(item for item in event["observations"] if item["source"] == "browser:x:otter")
    assert feature["decision_eligible"] is True
    assert len(feature["text"]) == 600 and feature["text_truncated"] is True
    assert feature["platform"] == {"id": "web", "label": "news-a.example", "inferred": True}
    assert feature["author"] == "Otter Daily" and feature["author_known"] is True
    assert feature["influence"]["account_type"] == "publisher"
    assert feature["influence"]["account_type_inferred"] is False
    assert feature["influence"]["authority_tier"] == "established"
    assert feature["influence"]["verified"] is True
    assert feature["influence"]["follower_count"] is None
    assert feature["influence"]["visible_engagement"] == {"view_count": 125000, "like_count": 8500}
    assert feature["metadata"]["trend_lane_id"] == "culture_entertainment"
    assert feature["metadata"]["trend_lane_run_id"] == "seed-lane-run"
    assert feature["metadata"]["trend_lane_taxonomy"] == "trend-lanes/v1"
    assert feature["source_group"] == "original_feature"
    assert event["lead_source"]["id"] == feature["id"]
    assert identity["platform"]["id"] == "x" and identity["author"] == "otter"
    assert identity["source_entity_id"] == "otter_daily"
    assert identity["cross_platform_entity"] == {
        "id": "otter_daily",
        "origin": "entity:otter_daily",
        "deduplication": "explicit_persisted_entity_only",
    }
    assert identity["origin"] == "entity:otter_daily"
    assert "bridge_token" not in identity["metadata"]
    assert identity["influence"]["authority_tier"] == "unknown"
    assert identity["influence"]["account_type_inferred"] is True
    assert identity["influence"]["verified"] is None
    assert identity["influence"]["follower_count"] is None
    assert identity["influence"]["curated_watch"] == {
        "configured": True,
        "priority": 2,
        "tier": "community_trend",
        "display_name": "Otter",
    }
    assert identity["decision_eligible"] is False
    assert identity["ranking_dimensions"]["curated_watch_priority"] == 2
    assert roles["identity"]["original_role"] in {"confirmation", "feature"}
    assert roles["promotion"]["decision_eligible"] is False
    assert "non_decision_role" in roles["promotion"]["rejection_reasons"]
    future = next(item for item in event["observations"] if item["source"] == "future-clock")
    assert future["freshness"] == "future"
    assert future["decision_eligible"] is False
    assert future["author"] is None and future["author_known"] is False
    assert future["source_group"] == "identity_promotion_context"
    assert {"published_at", "observed_at", "ingested_at"}.issubset(future)
    detail = event
    assert detail["ranking_available"] is False
    assert detail["candidate_ranking"] is None
    assert detail["ranking_persistence_gap"] == "candidate_ranking_not_available_for_this_event"
    assert detail["ranked_sources"] == event["observations"]
    assert [group["id"] for group in detail["source_groups"]] == [
        "original_feature", "identity_promotion_context"
    ]
    context_sources = next(
        group["items"] for group in detail["source_groups"] if group["id"] == "identity_promotion_context"
    )
    assert {item["role"] for item in context_sources} == {"identity", "promotion"}
    assert all(item["decision_eligible"] is False for item in context_sources)
    assert [item["observed_at"] for item in detail["evidence_timeline"]] == sorted(
        item["observed_at"] for item in detail["evidence_timeline"]
    )
    assert {item["source"] for item in detail["evidence_timeline"]} == {
        "news-a", "browser:x:otter", "promotion-list", "future-clock"
    }

    token = web.token_detail(token_id)
    assert token["snapshot"]["momentum"] > 0
    assert token["snapshot"]["buys_5m"] == 30
    assert token["linked_event_ids"] == [event_id]
    assert token["evidence_record_count"] == token["evidence_count"] == 1
    assert max(len(item["text"]) for item in token["evidence"]) <= 600
    assert {item["role"] for item in token["attached_links"]} == {"identity", "promotion"}
    assert all(item["decision_eligible"] is False for item in token["attached_links"])
    assert all(item["verification_status"] == "provider_metadata" for item in token["attached_links"])
    assert token["detail_hydration"]["status"] == "pending"
    assert token["context_assessment"]["status"] == "insufficient_verified_sources"
    assert token["context_assessment"]["context_only"] is True
    assert token["context_assessment"]["assessment"]["decision_eligible"] is False
    assert token["context_assessment"]["assessment"]["public_figure_linkage"]["endorsement_inferred"] is False
    assert token["context_assessment"]["agent"]["model"] == "gpt-5.6-luna"
    context_tracking = token["context_assessment"]["outcome_tracking"]
    assert context_tracking["status"] == "pending"
    assert [item["status"] for item in context_tracking["horizons"]] == [
        "pending", "pending", "pending"
    ]
    assert context_tracking["decision_eligible"] is False
    assert context_tracking["endorsement_inferred"] is False
    assert context_tracking["affects"] == "none"
    token_list = web.tokens({})
    coverage = token_list["detail_coverage"]
    assert coverage.pop("tracking_started_at") is not None
    assert coverage == {
        "eligible_solana_tokens": 1,
        "hydrated": 0,
        "pending": 1,
        "no_pair": 0,
        "error": 0,
        "social_links_found": 1,
        "coverage_ratio": 0.0,
    }
    serialized_token = json.dumps(token)
    assert "raw_json" not in serialized_token
    assert "must_not_be_returned" not in serialized_token
    decision_payload = web.decisions({})
    assert decision_payload["ranking_available"] is False
    assert decision_payload["ranking_coverage"] == {"available": 0, "unavailable": 1}
    decision = decision_payload["items"][0]
    assert decision["action"] == "WAIT" and decision["is_wait"] is True
    assert decision["ranking_available"] is False and decision["candidate_ranking"] is None
    assert decision["rejected_reasons"] == ["canonical_token_ambiguous"]
    assert decision["position_usd"] == 0
    safety = {item["name"]: item for item in decision["safety_checks"]["checks"]}
    assert decision["safety_checks"]["basis"] == "persisted_snapshot_at_or_before_decision"
    assert decision["safety_checks"]["snapshot_observed_at"] is not None
    assert safety["liquidity_usd"]["value"] == 50_000
    assert safety["liquidity_usd"]["state"] == "pass"
    assert safety["transactions_5m"]["value"] == 40
    assert safety["buy_ratio_5m"]["value"] == pytest.approx(0.75)
    assert safety["honeypot"]["state"] == "unknown"
    assert safety["sellable"]["state"] == "unknown"
    assert safety["buy_tax_pct"]["state"] == "unknown"
    assert safety["sell_tax_pct"]["state"] == "unknown"
    assert safety["risk_score"]["state"] == "unknown"

    portfolio = web.portfolio({})
    assert portfolio["simulated"] is True
    assert portfolio["ingestion_activity"]["status"] == "active"
    assert portfolio["ingestion_activity"]["truth_source"] == "persisted_sqlite_activity"
    assert portfolio["positions"][0]["current_price"] == pytest.approx(0.01)
    assert portfolio["positions"][0]["quote_as_of"] is not None
    assert portfolio["positions"][0]["take_profit_index"] == 0
    assert portfolio["positions"][0]["take_profit_total"] == 4
    assert portfolio["positions"][0]["take_profit_next"] == {
        "return_pct": 0.5,
        "sell_fraction": 0.2,
    }
    assert portfolio["positions"][0]["narrative_age_minutes"] is not None
    assert portfolio["positions"][0]["narrative_stale"] is False
    assert portfolio["trades"][0]["simulated"] is True
    assert portfolio["account"]["equity_usd"] is not None
    assert portfolio["account"]["total_pnl_usd"] == pytest.approx(
        portfolio["account"]["realized_pnl_usd"]
        + portfolio["account"]["unrealized_pnl_usd"]
    )

    agents = web.agents()
    scout = next(item for item in agents["operations"] if item["kind"] == "trend_scout")
    assert agents["provider"] == "Local Codex CLI"
    assert agents["credential_mode"] == "signed_in_local_session"
    assert agents["uses_api_key"] is False
    assert scout["calls"] == 3 and scout["tokens"] == 12345
    assert scout["next_run_at"] is not None and scout["fallback_used"] is True
    assert agents["usage_summary"]["today"] == {
        "calls": 1,
        "attempts": 2,
        "fallback_attempts": 1,
        "input_tokens": 900,
        "cached_input_tokens": 150,
        "cache_write_input_tokens": 30,
        "output_tokens": 300,
        "reasoning_output_tokens": 120,
        "total_tokens": 1500,
        "known_usage_attempts": 2,
        "unknown_usage_attempts": 0,
        "coverage_pct": 100.0,
        "valid_structured_attempts": 1,
        "invalid_structured_attempts": 0,
        "structured_pass_rate_pct": 100.0,
        "legacy_unattributed_total_tokens": 10845,
    }
    breakdown = agents["usage_breakdown"]["today"]
    assert {(item["model"], item["reasoning_effort"], item["total_tokens"]) for item in breakdown} == {
        ("gpt-5.3-codex-spark", "low", 1000),
        ("gpt-5.6-luna", "medium", 500),
    }
    spark_quality = next(item for item in breakdown if item["model"] == "gpt-5.3-codex-spark")
    luna_quality = next(item for item in breakdown if item["model"] == "gpt-5.6-luna")
    assert spark_quality["structured_pass_rate_pct"] is None
    assert luna_quality["structured_pass_rate_pct"] == 100.0
    assert [(item["attempt_index"], item["fallback"]) for item in agents["recent_attempts"]] == [
        (1, True), (0, False)
    ]
    assert "prompt" not in json.dumps(agents["recent_attempts"])

    sources = web.sources()["items"]
    static = next(item for item in sources if item["name"] == "example-news")
    paused = next(item for item in sources if item["name"] == "paused-dynamic")
    assert static["last_ok_at"] is not None and static["last_item_at"] is not None
    assert paused["status"] == "paused"
    assert paused["pause_reason"] == "consecutive_poll_failures"
    source_payload = web.sources()
    source_names = {item["name"] for item in source_payload["items"]}
    assert "dexscreener-discovery" not in source_names
    assert "dexscreener:token_profiles" in source_names
    assert source_payload["learning"]["status"] == "collecting_samples"
    assert source_payload["learning"]["summary"]["observations"] >= 4
    assert source_payload["learning"]["summary"]["closed_paper_outcomes"] == 0
    assert source_payload["learning"]["summary"]["decision_support_outcomes"] == 0
    assert source_payload["learning"]["summary"]["active_labels"] == 0
    assert source_payload["learning"]["activation_policy"]["rotation_basis"] == "discovery_lead"
    assert source_payload["learning"]["activation_policy"]["decision_support_affects"] == "descriptive_only"
    assert source_payload["trend_lanes"]["status"] == "collecting_exposure"
    assert source_payload["trend_lanes"]["actual_schedule_changed_by_learning"] is False
    assert source_payload["trend_attention_policy"]["version"] == "trend-attention/v2-experiment-gated"
    assert source_payload["trend_attention_policy"]["summary"]["actual_schedule_changed_by_learning"] is False
    policy_lane = next(
        item for item in source_payload["trend_attention_policy"]["items"]
        if item["lane_id"] == "culture_entertainment"
    )
    assert policy_lane["selected_in_last_run"] is True
    assert "recommended_multiplier" in policy_lane and "applied_schedule_multiplier" in policy_lane
    assert len(source_payload["trend_lanes"]["items"]) == 5
    culture_lane = next(
        item for item in source_payload["trend_lanes"]["items"]
        if item["lane_id"] == "culture_entertainment"
    )
    assert culture_lane["selected_in_last_run"] is True
    assert culture_lane["completed_exposures"] == 1
    assert culture_lane["accepted_events"] == 1
    assert culture_lane["accepted_events_per_completed_run"] == 1.0
    assert culture_lane["shadow_mature"] is False
    assert source_payload["watch_account_learning"]["status"] == "collecting_exposure"
    assert source_payload["watch_account_learning"]["summary"]["account_exposures"] == 2
    assert source_payload["watch_account_learning"]["summary"]["exact_source_hits"] == 2
    account_exposure = source_payload["watch_account_learning"]["items"][0]
    assert account_exposure["platform"] == "x" and account_exposure["handle"] == "otter"
    assert account_exposure["completed_exposures"] == 2
    assert account_exposure["browser_bridge_exposures"] == 1
    assert account_exposure["trend_agent_exposures"] == 1
    assert account_exposure["rotation_active"] is False
    assert [item["count"] for item in source_payload["learning_closure"]["stages"]] == [1, 1, 0, 0, 0]
    assert source_payload["learning_closure"]["breakpoint"] == "eligible_event"
    assert source_payload["watch_attention_policy"]["version"] == "watch-attention/v3-experiment-gated"
    assert source_payload["watch_attention_policy"]["status"] == "collecting_evidence"
    assert source_payload["watch_attention_policy"]["summary"][
        "rotation_activation_available"
    ] is False
    assert source_payload["watch_attention_policy"]["summary"][
        "actual_rotation_changed_by_learning"
    ] is False
    attention_item = source_payload["watch_attention_policy"]["items"][0]
    assert attention_item["platform"] == "x" and attention_item["handle"] == "otter"
    assert attention_item["state"] == "collecting_account_exposure"
    assert attention_item["applied_rotation_multiplier"] == 1.0
    assert attention_item["rotation_active"] is False
    assert attention_item["selected_in_last_run"] is True
    assert attention_item["last_selection_role"] == "exploration"
    assert source_payload["watch_attention_policy"]["activation_policy"]["never_affects"] == [
        "evidence_weight", "candidate_ranking", "decision_eligibility",
        "risk", "position_size", "exits", "live_trading",
    ]
    assert source_payload["shadow_followup"]["status"] == "collecting_followup"
    assert source_payload["shadow_followup"]["version"] == "shadow-event-followup/v3-strategy-labels"
    assert source_payload["shadow_followup"]["horizons_minutes"] == [15, 60, 240]
    assert source_payload["shadow_followup"]["summary"]["cohorts"] == 1
    assert source_payload["shadow_followup"]["summary"]["pending_cohorts"] == 1
    assert source_payload["shadow_followup"]["summary"]["reject_cohorts"] == 0
    assert source_payload["shadow_followup"]["summary"]["entry_execution"] == {
        "attempts": 0, "filled": 0, "rejected": 0, "cohort_linked": 0, "unlinked": 0,
    }
    assert source_payload["shadow_followup"]["items"] == []
    assert source_payload["token_context_followup"]["status"] == "collecting_followup"
    assert source_payload["token_context_followup"]["summary"]["assessments"] == 1
    assert source_payload["token_context_followup"]["summary"]["tracked_cohorts"] == 1
    assert source_payload["token_context_followup"]["summary"]["pending_cohorts"] == 1
    assert source_payload["token_context_followup"]["activation"] is False
    assert source_payload["token_context_followup"]["actual_schedule_changed_by_learning"] is False
    assert source_payload["token_context_followup"]["decision_eligible"] is False
    assert source_payload["token_context_followup"]["affects"] == "none"
    assert len(source_payload["platforms"]) == 9
    x_status = next(item for item in source_payload["platforms"] if item["platform"] == "x")
    assert x_status["access_state"] == "authenticated"
    assert x_status["login_recommended"] is True
    assert x_status["contains_credentials"] is False
    assert source_payload["credentials_policy"] == {
        "contains_credentials": False,
        "accepts_passwords": False,
        "accepts_cookies": False,
        "accepts_sessions": False,
    }

    audit = web.audit()
    assert audit["status"] == "partial_evidence"
    assert audit["future_data_rejected"] is True
    assert audit["observed_future_rejection_count"] == 1
    audit_cases = {item["id"]: item for item in audit["cases"]}
    assert audit_cases["r5-false-positive"]["status"] == "policy_enforced"
    assert audit_cases["r5-false-positive"]["observed_case_evidence"] is False
    assert audit_cases["r6-starlink-stale-reverse-evidence"]["status"] == "not_observed"
    assert audit_cases["future-data-rejection"]["status"] == "observed_pass"
    assert audit_cases["future-data-rejection"]["observed_case_evidence"] is True
    audit_evidence = audit["recent_decision_evidence"][0]["evidence"]
    stale_identity = next(item for item in audit_evidence if item["source"] == "browser:x:otter")
    assert stale_identity["original_role"] == "confirmation"
    assert stale_identity["rejection_reasons"]
    assert {"published_at", "observed_at", "ingested_at"}.issubset(stale_identity)


def test_event_detail_exposes_forward_provenance_without_fabricated_independence(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    event_id = 0
    for handle, post_id in (("alpha", "101"), ("beta", "202")):
        event_id, _, _ = engine.ingest(
            Observation(
                source=f"x:{handle}", source_kind="social",
                title="Two public posts describe the same viral animal event",
                text="Two public posts describe the same viral animal event",
                url=f"https://x.com/{handle}/status/{post_id}?token=never-return",
                author=handle, observed_at=now, ingested_at=now,
                availability_proof="local_receive", source_item_id=f"x:{handle}:{post_id}",
                raw={"browser": {"platform": "x"}, "source_entity_id": handle},
            )
        )
    engine.ingest(
        Observation(
            source="relay-feed", source_kind="news",
            title="Two public posts describe the same viral animal event",
            text="Two public posts describe the same viral animal event",
            url="https://x.com/alpha/status/101", author="Relay of alpha",
            observed_at=now, ingested_at=now, source_item_id="relay-viral-animal",
            raw={"feed_url": "https://relay.example/feed.xml"},
        )
    )
    store.close()

    detail = WebData(config_path).event_detail(event_id)
    summary = detail["provenance_summary"]
    assert summary["proven_distinct_origin_lower_bound"] == 2
    assert summary["direct_item_count"] == 2
    assert summary["relay_count"] == 1
    direct = [
        row for row in detail["observations"]
        if row["provenance"]["origin_identity_state"] == "proven_direct_item"
    ]
    relay = next(
        row for row in detail["observations"] if row["provenance"]["route_kind"] == "relay"
    )
    assert len(direct) == 2
    assert all(row["origin_independence"] == "proven_distinct_lower_bound" for row in direct)
    assert relay["origin_independence"] == "unknown"
    assert "proven_distinct_origin" not in relay["priority_reasons"]
    summary_item = next(item for item in WebData(config_path).events({})["items"] if item["id"] == event_id)
    assert summary_item["lead_source"]["provenance"]["origin_identity_state"] == "proven_direct_item"
    assert "independent_origin" not in summary_item["evidence_ranking"]["order"]
    serialized = json.dumps(detail)
    assert "origin_root_key" not in serialized
    assert "never-return" not in serialized


def test_candidate_ranking_api_is_persisted_bounded_sanitized_and_wait_is_truthful(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, token_id = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    row = store.decisions(1)[0]
    hidden = "must-never-leak-from-ranking"
    store.set_candidate_ranking(
        event_id,
        {
            "version": 1,
            "evaluated_at": row["created_at"],
            "status": "completed",
            "outcome": "WAIT",
            "outcome_reasons": ["canonical_token_ambiguous"],
            "ranking_method": "candidate_score_desc_then_bounded_semantic_tiebreak",
            "candidate_count_total": 2,
            "candidate_count_persisted": 2,
            "candidates_truncated": False,
            "tie_break": {
                "used": False,
                "tier": None,
                "confidence": None,
                "preferred_token_id": None,
                "prompt": hidden,
            },
            "candidates": [
                {
                    "rank": 1,
                    "token_id": token_id,
                    "chain": "solana",
                    "address": "A" * 32,
                    "name": "Viral Otter",
                    "symbol": "OTTER",
                    "candidate_score": 65,
                    "match_score": 88,
                    "canonical_margin": 2,
                    "raw_canonical_margin": 2,
                    "score_gap_to_selected": 0,
                    "score_gap_to_score_leader": 0,
                    "score_gap_to_next_rank": 2,
                    "selection_status": "selected_for_final_decision",
                    "action": "WAIT",
                    "position_usd": 0,
                    "reasons": ["match=88.0"],
                    "rejected_reasons": ["canonical_token_ambiguous"],
                    "snapshot": {
                        "observed_at": row["created_at"],
                        "provider": "dexscreener",
                        "price_usd": 0.01,
                        "liquidity_usd": 50_000,
                        "volume_5m_usd": 12_000,
                        "buys_5m": 30,
                        "sells_5m": 10,
                        "security_reports": ["rugcheck"],
                        "raw_json": {"private_key": hidden},
                    },
                    "safety": {"status": "not_checked", "rejected_reasons": []},
                    "tie_break": {"pre_agent_rank": 1, "rank_changed": False, "preferred": False},
                    "private_key": hidden,
                },
                {
                    "rank": 2,
                    "token_id": "solana:" + "B" * 32,
                    "chain": "solana",
                    "address": "B" * 32,
                    "name": "Otter Copy",
                    "symbol": "OTTR",
                    "candidate_score": 63,
                    "match_score": 75,
                    "score_gap_to_selected": 2,
                    "score_gap_to_score_leader": 2,
                    "selection_status": "not_selected_lower_rank",
                    "action": "NOT_SELECTED",
                    "position_usd": 0,
                    "reasons": ["ranked below selected candidate"],
                    "rejected_reasons": [],
                    "snapshot": {"observed_at": row["created_at"], "provider": "dexscreener"},
                    "safety": {"status": "not_checked", "rejected_reasons": []},
                    "tie_break": {"pre_agent_rank": 2, "rank_changed": False, "preferred": False},
                },
            ],
            "final_outcome": {"decision_id": None, "action": "WAIT", "prompt": hidden},
            "bridge_token": hidden,
        },
    )
    pending_ranking = WebData(config_path).event_detail(event_id)["candidate_ranking"]
    assert pending_ranking["status"] == "pending_runtime"
    assert pending_ranking["outcome"] == "UNAVAILABLE"
    assert pending_ranking["final_outcome"] is None
    assert pending_ranking["candidates"][0]["action"] == "PENDING_RUNTIME"
    assert pending_ranking["candidates"][0]["position_usd"] == 0
    decision = CandidateDecision(
        event_id=event_id,
        token_id=token_id,
        action="WAIT",
        score=65,
        match_score=88,
        canonical_margin=2,
        reasons=["match=88.0"],
        rejected_reasons=["canonical_token_ambiguous"],
        created_at=row["created_at"],
    )
    store.finalize_candidate_ranking(event_id, decision, decision_id=int(row["id"]))
    store.close()

    web = WebData(config_path)
    payload = web.decisions({})
    assert payload["ranking_available"] is True
    assert payload["ranking_coverage"] == {"available": 1, "unavailable": 0}
    item = payload["items"][0]
    assert item["action"] == "WAIT" and item["ranking_available"] is True
    assert item["rank"] == 1
    ranking = item["candidate_ranking"]
    assert ranking["outcome"] == "WAIT"
    assert ranking["final_outcome"]["action"] == "WAIT"
    assert [candidate["rank"] for candidate in ranking["candidates"]] == [1, 2]
    assert ranking["candidates"][0]["action"] == "WAIT"
    assert ranking["candidates"][1]["action"] == "NOT_SELECTED"
    assert ranking["candidates"][0]["safety"]["status"] == "not_checked"
    assert ranking["candidates"][0]["snapshot"]["security_reports"] == ["rugcheck"]
    assert hidden not in json.dumps(payload)
    assert "raw_json" not in json.dumps(payload)
    detail = web.event_detail(event_id)
    assert detail["ranking_available"] is True
    assert detail["candidate_ranking"]["final_outcome"]["decision_id"] == int(row["id"])
    assert set(detail["related_token_ids"]) == {token_id, "solana:" + "B" * 32}

    app = (Path(__file__).parents[1] / "src" / "memetrader" / "web_static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "data-testid='candidate-ranking'" in app
    assert "WAIT｜未形成交易信号" in app
    assert "未选中" in app and "NOT SELECTED" in app
    assert "WAIT is never decorated as an opportunity" in app
    assert "data-testid='source-learning'" in app
    assert "data-testid='watch-account-exposure'" in app
    assert "data-testid='trend-attention-policy'" in app
    assert "data-testid='attention-experiment'" in app
    assert "data-testid='token-context-followup'" in app
    assert "data-testid='token-context-onchain-challenger'" in app
    assert "data-testid='solana-holder-shadow'" in app
    assert "data-testid='creator-launch-risk-shadow'" in app
    assert "Creator launch history · forward Shadow" in app
    assert "not RPC verification" in app
    assert "not people, independent buyers, or smart money" in app
    assert "data-testid='information-first-shadow'" in app
    assert "data-testid='information-first-ilg'" in app
    assert "data-testid='token-universe-jupiter-quote'" in app
    assert "data-testid='token-universe-jupiter-quote-evidence'" in app
    assert "Jupiter quote time-validity overlay" in app
    assert "data-testid='token-universe-jupiter-quote-validity'" in app
    assert "data-testid='onchain-only-shadow'" in app
    assert "data-testid='onchain-only-shadow-jupiter-quote'" in app
    assert "Trigger-anchored Jupiter two-leg quote evidence" in app
    assert "No taker, signing, transaction construction, or broadcast occurs" in app
    assert "On-chain first, context not yet observed" in app
    assert "not globally absent" in app
    assert "Historical tokens are not backfilled" in app
    assert "Solana is market-path only and explicitly execution unsupported" in app
    assert "no transaction is built, signed, or broadcast" in app
    assert "AVG ROUND-TRIP MIN RETURN" in app
    assert "quote-bound research, not a profit promise" in app
    assert "low activity is not “unpriced” and is not a buy signal" in app
    assert "first locally recorded same-surface activity crossing" in app
    assert "Token-context forward follow-through: learn what merits more research" in app
    assert "Trend-lane statistics are descriptive and cannot change scheduling on their own" in app
    assert "Account correlations create hypotheses; only a preregistered randomized experiment may alter a watch slot" in app
    assert "Preregistered randomized attention experiment: one normal watch slot only" in app
    assert "Paper source outcomes require an exact final-decision → admitted-cohort → fill → close chain" in app
    assert "Forward learning state" in app
    assert "COLLECTING · NOTHING MATURE" in app
    assert "later WAIT / REJECT / CANDIDATE actions from the same event cannot inflate" in app
    assert "Evidence roles F / C / I / P" in app
    assert "event_topic" in app and "observe only" in app
    assert "Linked narrative / event observation timeline" in app
    assert "Verified narrative / event evidence timeline" not in app
    assert "data-testid='paper-account-curve'" in app
    assert "data-testid='paper-execution-attempts'" in app
    assert "data-testid='attention-trajectory'" in app
    assert "data-testid='story-lifecycle-timeline'" in app
    assert "Facts, propagation & corrections" in app
    assert "An Agent structured assessment is pending verification, not independent fact verification" in app
    assert "No correction label observed in the forward assessment ledger" in app
    assert "data-testid='source-revision-timeline'" in app
    assert "Original source content versions" in app
    assert "Deletion is not retraction, and retraction is not proof that a claim is false" in app
    assert "data-testid='claim-relation-graph'" in app
    assert "Claim targets & relation graph" in app
    assert "PUBLISHER ACTION ≠ INDEPENDENT FACT VERIFICATION · AFFECTS NONE" in app
    assert "A target that appears later never backfills an old relation" in app
    assert "LATEST ASSESSMENT" in app
    assert "OBSERVE ONLY · AFFECTS NONE" in app
    assert "It is not platform-wide mentions, replies, quotes, or repost velocity" in app
    assert "no future price was filled in" in app
    assert "no fake fills are generated" in app
    assert "timeoutMs: page === 'audit' ? 60000 : page === 'sources' ? 30000 : 9000" in app


def test_settings_are_allowlisted_atomic_and_never_expose_secrets(tmp_path: Path):
    config_path, config = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    serialized = json.dumps(
        {
            "settings": web.settings(),
            "health": web.health(),
            "agents": web.agents(),
            "sources": web.sources(),
        }
    )
    assert config["bridge"]["token"] not in serialized
    assert config["notifications"]["telegram_bot_token"] not in serialized
    assert "telegram_chat_id" not in serialized
    settings = web.settings()
    assert settings["values"] == settings["editable"]
    assert settings["schema"]["fields"]
    poll_schema = next(item for item in settings["schema"]["fields"] if item["path"] == "poll_seconds")
    assert poll_schema["current"] == settings["editable"]["poll_seconds"]
    assert poll_schema["default"] is not None
    assert poll_schema["unit"] == "seconds"
    assert poll_schema["restart_required"] is True
    dex_interval = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "sources.dexscreener_discovery.interval_seconds"
    )
    dex_hydration = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "sources.dexscreener_discovery.max_hydrations_per_cycle"
    )
    assert (dex_interval["min"], dex_interval["max"]) == (30, 3600)
    assert (dex_hydration["min"], dex_hydration["max"]) == (0, 300)
    learning_fraction = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.source_learning_exploration_fraction"
    )
    direct_context = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.context_direct_trigger_enabled"
    )
    direct_attention = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.context_direct_event_min_attention"
    )
    assert learning_fraction["min"] == 0.4
    assert direct_context["type"] == "boolean"
    assert (direct_attention["min"], direct_attention["max"]) == (0, 100)
    max_open_positions = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "paper.max_open_positions"
    )
    assert max_open_positions["min"] == 0
    assert settings["live_locked"] is True
    telegram_option = next(
        item
        for item in settings["schema"]["collection_preferences"]["platform_options"]
        if item["value"] == "telegram"
    )
    assert telegram_option["automation_available"] is False
    assert telegram_option["manual_directory_only"] is True

    public_access = tmp_path / "data" / "web_console" / "PUBLIC_ACCESS.txt"
    public_access.parent.mkdir(parents=True, exist_ok=True)
    public_access.write_text(
        "URL: https://example.trycloudflare.com\nUsername: memetrader\nPassword: must-stay-local\n",
        encoding="utf-8",
    )
    public_settings = web.settings()
    assert public_settings["authentication"]["public_url"] == "https://example.trycloudflare.com"
    assert "must-stay-local" not in json.dumps(public_settings)

    result = web.patch_settings(
        {
            "updates": {
                "poll_seconds": 90,
                "autonomous_search": {"max_concurrent_agents": 2},
            },
            "console": {
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "@example",
                        "display_name": "Example",
                        "entity_id": "example_media",
                        "url": "https://x.com/example",
                        "enabled": True,
                        "priority": 1,
                    }
                ],
                "topics": ["viral animals"],
                "platforms": [{"platform": "telegram", "enabled": True}],
            },
        }
    )
    assert result["restart_required"] is True
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["poll_seconds"] == 90
    assert saved["autonomous_search"]["max_concurrent_agents"] == 2
    assert saved["live"]["enabled"] is False
    watchlist = web.watchlist()
    assert watchlist["watch_accounts"][0]["handle"] == "@example"
    assert watchlist["watch_accounts"][0]["priority"] == 1
    assert watchlist["watch_accounts"][0]["entity_id"] == "example_media"
    assert watchlist["platforms"] == [{"platform": "telegram", "enabled": False}]
    assert watchlist["contains_credentials"] is False

    before = config_path.read_bytes()
    for unsafe_update in ({"live": {"enabled": True}}, {"mode": "live"}):
        with pytest.raises(Exception, match="locked or unsupported"):
            web.patch_settings({"updates": unsafe_update})
        assert config_path.read_bytes() == before
    with pytest.raises(Exception, match="between 1 and 2"):
        web.patch_settings({"updates": {"autonomous_search": {"max_concurrent_agents": 3}}})
    with pytest.raises(Exception, match="unsupported fields"):
        web.patch_settings(
            {
                "console": {
                    "watch_accounts": [
                        {"platform": "x", "handle": "bad", "enabled": True, "password": "must-not-save"}
                    ]
                }
            }
        )
    for bad_entity_id in ("NASA", "bad/entity", "-leading", "trailing-", "a" * 65):
        with pytest.raises(Exception, match="entity_id"):
            web.patch_settings(
                {
                    "console": {
                        "watch_accounts": [
                            {
                                "platform": "x",
                                "handle": "@example",
                                "entity_id": bad_entity_id,
                                "enabled": True,
                            }
                        ]
                    }
                }
            )
    with pytest.raises(Exception, match="at most 4"):
        web.patch_settings(
            {
                "console": {
                    "watch_accounts": [
                        {
                            "platform": "x",
                            "handle": f"critical_{index}",
                            "watch_cadence": "critical",
                            "enabled": True,
                        }
                        for index in range(5)
                    ]
                }
            }
        )
    assert "must-not-save" not in (tmp_path / "data" / "web_console" / "console_settings.json").read_text(encoding="utf-8")


def test_watchlist_prioritizes_recent_exact_posts_from_configured_accounts(tmp_path: Path):
    config_path, _config_value = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(
        chain="solana", address="priority-post-token", name="Strait of Hormuz", symbol="HORMUZ"
    )
    store.upsert_token(token)
    now = utcnow()
    store.upsert_token_source_link(
        {
            "token_id": token.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": "https://x.com/WhiteHouse/status/123",
            "normalized_url": "https://x.com/WhiteHouse/status/123",
            "link_kind": "social_post",
            "label": "twitter",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=now - timedelta(minutes=10),
    )
    for index in range(110):
        store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "pumpportal",
                "discovery_surface": "launch_metadata",
                "role": "identity",
                "original_url": f"https://x.com/noise{index}/status/{index}",
                "normalized_url": f"https://x.com/noise{index}/status/{index}",
                "link_kind": "social_post",
                "label": "twitter",
                "platform": "x",
                "verification_status": "provider_metadata",
            },
            observed_at=now,
        )
    store.upsert_token_source_link(
        {
            "token_id": token.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": "https://x.com/DisabledAccount/status/456",
            "normalized_url": "https://x.com/DisabledAccount/status/456",
            "link_kind": "social_post",
            "label": "twitter",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=now,
    )
    store.upsert_token_source_link(
        {
            "token_id": token.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": "https://x.com/elonmusk/status/1098658606264635394",
            "normalized_url": "https://x.com/elonmusk/status/1098658606264635394",
            "link_kind": "social_post",
            "label": "twitter",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=now,
    )
    store.close()
    web = WebData(config_path)
    web.patch_settings(
        {
            "console": {
                "platforms": [{"platform": "x", "enabled": True}],
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "@WhiteHouse",
                        "display_name": "The White House",
                        "entity_id": "white_house",
                        "url": "https://x.com/WhiteHouse",
                        "enabled": True,
                        "priority": 5,
                    },
                    {
                        "platform": "x",
                        "handle": "@DisabledAccount",
                        "display_name": "Disabled Account",
                        "entity_id": "disabled_account",
                        "url": "https://x.com/DisabledAccount",
                        "enabled": False,
                        "priority": 5,
                    },
                    {
                        "platform": "x",
                        "handle": "@elonmusk",
                        "display_name": "Elon Musk",
                        "entity_id": "elon_musk",
                        "url": "https://x.com/elonmusk",
                        "enabled": True,
                        "priority": 5,
                    }
                ],
                "topics": [],
            }
        }
    )
    requests = web.watchlist()["priority_post_requests"]
    assert requests == [
        {
            "url": "https://x.com/WhiteHouse/status/123",
            "platform": "x",
            "handle": "@WhiteHouse",
            "entity_id": "white_house",
            "source_link_id": requests[0]["source_link_id"],
            "first_observed_at": requests[0]["first_observed_at"],
            "decision_eligible": False,
            "affects": "browser_observation_priority_only",
        }
    ]
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.add_observation(
        Observation(
            source="x:whitehouse",
            source_kind="social",
            title="Captured exact White House post",
            url="https://x.com/WhiteHouse/status/123",
            published_at=now - timedelta(minutes=11),
            observed_at=now - timedelta(minutes=9),
            ingested_at=now - timedelta(minutes=9),
            availability_proof="local_receive",
            source_item_id="https://x.com/WhiteHouse/status/123",
            raw={"browser": {"platform": "x"}},
        )
    )
    store.close()
    assert web.watchlist()["priority_post_requests"] == []


def test_watchlist_requests_recent_token_linked_x_post_without_watch_account(tmp_path: Path):
    config_path, _config_value = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(
        chain="solana", address="token-linked-post", name="Linked", symbol="LNK"
    )
    store.upsert_token(token)
    now = utcnow()
    status_id = int((now.timestamp() * 1000 - 1288834974657) * (1 << 22))
    url = f"https://x.com/community_signal/status/{status_id}"
    store.upsert_token_source_link(
        {
            "token_id": token.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": url,
            "normalized_url": url,
            "link_kind": "social_post",
            "label": "twitter",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=now,
    )
    store.close()

    web = WebData(config_path)
    web.patch_settings(
        {"console": {"platforms": [{"platform": "x", "enabled": True}],
                     "watch_accounts": [], "topics": []}}
    )
    requests = web.watchlist()["priority_post_requests"]
    assert len(requests) == 1
    assert requests[0]["url"] == url
    assert requests[0]["handle"] == "@community_signal"
    assert requests[0]["entity_id"] == ""
    assert requests[0]["decision_eligible"] is False
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.add_observation(
        Observation(
            source="x:community_signal",
            source_kind="social",
            title="Captured token-linked media post",
            text="Exact locally captured post body.",
            url=url + "/photo/1",
            availability_proof="local_receive",
            role="identity",
            source_item_id=url + "/photo/1",
            raw={"browser": {"platform": "x"}},
        )
    )
    store.close()
    assert web.watchlist()["priority_post_requests"] == []


def test_notifications_missing_empty_malformed_and_strict_public_whitelist(tmp_path: Path):
    config_path, config = _config(tmp_path)
    web = WebData(config_path)
    notification_path = tmp_path / "notifications.jsonl"

    missing = web.notifications({})
    assert missing["items"] == []
    assert missing["status"] == "missing"
    assert missing["latest_at"] is None
    assert missing["execution_context"] == {
        "mode": "paper",
        "simulated": True,
        "live_enabled": False,
        "live_locked": True,
    }

    notification_path.write_text("", encoding="utf-8")
    empty = web.notifications({})
    assert empty["items"] == [] and empty["status"] == "empty"

    private_value = "private-wallet-material-must-not-leak"
    bot_value = "telegram-bot-token-must-not-leak"
    records = [
        "not-json",
        json.dumps([]),
        json.dumps({"time": "not-a-time", "kind": "paper_buy", "title": "bad time"}),
        json.dumps(
            {
                "time": iso(),
                "kind": "future_kind_with_unknown_payload_contract",
                "title": "unknown kinds are not public",
                "payload": {"private_key": private_value},
            }
        ),
        json.dumps(
            {
                "time": iso(),
                "kind": "paper_buy",
                "title": "solana:public-token",
                "payload": {
                    "event_id": 7,
                    "token_id": "solana:public-token",
                    "action": "CANDIDATE",
                    "amount_usd": 12.5,
                    "score": 83,
                    "source": "example-news",
                    "private_key": private_value,
                    "telegram_bot_token": bot_value,
                    "error": "TimeoutError",
                    "detail": "C:/secret/runtime/path",
                    "unknown_nested": {"cookie": "session-must-not-leak"},
                    "usage": {"agent_prompt": "must-not-leak"},
                },
                "raw_payload": {"bridge_token": "must-not-leak"},
            }
        ),
    ]
    notification_path.write_text("\n".join(records) + "\n", encoding="utf-8")

    payload = web.notifications({})
    assert payload["status"] == "active"
    assert payload["total"] == 1
    assert payload["malformed_skipped"] == 4
    item = payload["items"][0]
    assert item["kind"] == "paper_buy"
    assert item["event_id"] == 7 and item["event_url"] == "#/events/7"
    assert item["token_id"] == "solana:public-token"
    assert item["token_url"] == "#/tokens/solana:public-token"
    assert item["source_display_name"] == "example-news"
    assert item["metrics"] == {"amount_usd": 12.5, "score": 83.0}
    assert item["simulation"] == {
        "is_simulated": True,
        "mode": "paper",
        "label": "PAPER / SIMULATED",
    }
    serialized = json.dumps(payload)
    for forbidden in (
        private_value,
        bot_value,
        "session-must-not-leak",
        "agent_prompt",
        "bridge_token",
        "raw_payload",
        "unknown_nested",
        "TimeoutError",
        "C:/secret/runtime/path",
        config["notifications"]["telegram_bot_token"],
    ):
        assert forbidden not in serialized


def test_notifications_pagination_limit_and_rotated_generation(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    web = WebData(config_path)
    notification_path = tmp_path / "notifications.jsonl"
    now = utcnow()

    def record(minutes: int, title: str) -> str:
        return json.dumps(
            {
                "time": iso(now - timedelta(minutes=minutes)),
                "kind": "event_detected",
                "title": title,
                "payload": {"event_id": minutes + 1, "attention": 70 - minutes},
            }
        )

    notification_path.write_text(record(3, "oldest") + "\n" + record(2, "middle") + "\n", encoding="utf-8")
    notification_path.replace(Path(str(notification_path) + ".1"))
    notification_path.write_text(record(1, "newest") + "\n", encoding="utf-8")

    page = web.notifications({"limit": ["1"], "offset": ["1"]})
    assert page["total"] == 3
    assert page["limit"] == 1 and page["offset"] == 1
    assert page["has_more"] is True
    assert [item["title"] for item in page["items"]] == ["middle"]
    assert page["rotated_generations_read"] == 1
    assert page["bounded_tail"] is True

    clamped = web.notifications({"limit": ["999"], "offset": ["-9"]})
    assert clamped["limit"] == 200 and clamped["offset"] == 0
    assert [item["title"] for item in clamped["items"]] == ["newest", "middle", "oldest"]


def test_http_routes_require_optional_file_token_and_serve_api(tmp_path: Path):
    config_path, config = _config(tmp_path)
    _seed(tmp_path / "db.sqlite3")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
    (static / "app.js").write_text("window.consoleReady = true;", encoding="utf-8")
    token_file = tmp_path / "web-access-token.txt"
    token_file.write_text("a-local-access-token-longer-than-24", encoding="utf-8")
    server, thread, base = _start_server(config_path, static, token_file)
    try:
        with httpx.Client(timeout=5) as client:
            assert client.get(f"{base}/api/health").status_code == 401
            headers = {"Authorization": "Bearer a-local-access-token-longer-than-24"}
            health = client.get(f"{base}/api/health", headers=headers)
            assert health.status_code == 200 and health.json()["live"]["locked"] is True
            notifications = client.get(f"{base}/api/notifications", headers=headers)
            assert notifications.status_code == 200
            assert notifications.json()["execution_context"]["live_locked"] is True
            assert client.get(f"{base}/", headers=headers).text == "<h1>console</h1>"
            asset = client.get(f"{base}/static/app.js", headers=headers)
            assert asset.status_code == 200
            assert "javascript" in asset.headers["content-type"]
            assert asset.text == "window.consoleReady = true;"
            assert client.get(f"{base}/static/missing.js", headers=headers).status_code == 404
            watchlist = client.get(f"{base}/api/watchlist", headers=headers).json()
            assert len(watchlist["platforms"]) == 9
            settings = client.get(f"{base}/api/settings", headers=headers).json()
            assert settings["authentication"]["token_file"] == token_file.name
            assert str(token_file.resolve()) not in json.dumps(settings)
            assert config["bridge"]["token"] not in json.dumps(settings)
            rejected = client.patch(
                f"{base}/api/settings",
                headers=headers,
                json={"updates": {"mode": "live"}},
            )
            assert rejected.status_code == 400
            cross_origin = client.patch(
                f"{base}/api/settings",
                headers={**headers, "Origin": "https://malicious.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert cross_origin.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_wallet_http_is_local_only_public_view_is_masked_and_secret_is_never_persisted(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")

    class FakeWallet:
        def __init__(self):
            self.calls: list[tuple[str, object]] = []

        def snapshot(self, *, public_view: bool = False, refresh: bool = False):
            self.calls.append(("snapshot", public_view))
            return {
                "connected": True,
                "network": "solana-devnet",
                "address": "Abcd1234…Wxyz5678" if public_view else "Abcd1234FullWalletAddressWxyz5678",
                "balance_sol": 0.25,
                "signing": {"available": not public_view, "local_only": True},
                "public_view": public_view,
            }

        def connect(self, private_key, alias):
            self.calls.append(("connect", (private_key, alias)))
            return {"connected": True, "address": "Abcd1234FullWalletAddressWxyz5678"}

        def request_airdrop(self, sol):
            self.calls.append(("faucet", sol))
            return {"status": "confirmed", "sol": sol, "signature": "airdrop-signature"}

        def transfer(self, recipient, sol, confirm_phrase):
            self.calls.append(("transfer", (recipient, sol, confirm_phrase)))
            return {"status": "confirmed", "sol": sol, "signature": "transfer-signature"}

        def disconnect(self):
            self.calls.append(("disconnect", None))
            return {"connected": False}

    fake_wallet = FakeWallet()
    server, thread, base = _start_server(config_path, static)
    server.web_data.wallet_service = fake_wallet
    assert server.wallet_controls_allowed is True
    private_key = "do-not-" + "persist-private-key"
    try:
        with httpx.Client(timeout=5) as client:
            local = client.get(f"{base}/api/wallet")
            assert local.status_code == 200
            assert local.json()["address"] == "Abcd1234FullWalletAddressWxyz5678"
            assert local.json()["signing"]["available"] is True

            public = client.get(f"{base}/api/wallet", headers={"Host": "console.example"})
            assert public.status_code == 200
            assert public.json()["address"] == "Abcd1234…Wxyz5678"
            assert public.json()["signing"]["available"] is False

            connect = client.post(
                f"{base}/api/wallet/connect",
                headers={"Origin": base},
                json={"private_key": private_key, "alias": "test only"},
            )
            faucet = client.post(
                f"{base}/api/wallet/faucet",
                headers={"Origin": base},
                json={"sol": 0.1},
            )
            transfer = client.post(
                f"{base}/api/wallet/transfer",
                headers={"Origin": base},
                json={"recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"},
            )
            disconnected = client.delete(f"{base}/api/wallet", headers={"Origin": base})
            assert [response.status_code for response in (connect, faucet, transfer, disconnected)] == [200] * 4
            assert private_key not in "".join(
                response.text for response in (connect, faucet, transfer, disconnected)
            )

            post_payloads = {
                "/api/wallet/connect": {"private_key": private_key, "alias": "test only"},
                "/api/wallet/faucet": {"sol": 0.1},
                "/api/wallet/transfer": {
                    "recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"
                },
            }
            for route, payload in post_payloads.items():
                assert client.post(
                    f"{base}{route}", headers={"Host": "console.example", "Connection": "close"}, json=payload
                ).status_code == 403
                assert client.post(
                    f"{base}{route}",
                    headers={"Origin": "https://malicious.example", "Connection": "close"},
                    json=payload,
                ).status_code == 403
            assert client.delete(f"{base}/api/wallet", headers={"Host": "console.example"}).status_code == 403
            assert client.delete(
                f"{base}/api/wallet", headers={"Origin": "https://malicious.example"}
            ).status_code == 403

        assert ("connect", (private_key, "test only")) in fake_wallet.calls
        secret = private_key.encode("utf-8")
        assert all(secret not in path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_access_token_server_never_enables_wallet_controls_with_spoofed_loopback_host(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    token = "public-console-token-that-is-long-enough"
    token_file = tmp_path / "access-token.txt"
    token_file.write_text(token, encoding="utf-8")

    class FakeWallet:
        def __init__(self):
            self.calls: list[tuple[str, object]] = []

        def snapshot(self, *, public_view: bool = False, refresh: bool = False):
            self.calls.append(("snapshot", public_view))
            return {
                "address": "masked" if public_view else "full-wallet-address",
                "signing": {"available": not public_view},
            }

        def connect(self, private_key, alias):
            self.calls.append(("connect", alias))
            return {"connected": True}

        def request_airdrop(self, sol):
            self.calls.append(("faucet", sol))
            return {"status": "confirmed"}

        def transfer(self, recipient, sol, confirm_phrase):
            self.calls.append(("transfer", recipient))
            return {"status": "confirmed"}

        def disconnect(self):
            self.calls.append(("disconnect", None))
            return {"connected": False}

    server, thread, base = _start_server(config_path, static, token_file)
    fake_wallet = FakeWallet()
    server.web_data.wallet_service = fake_wallet
    headers = {
        "Authorization": f"Bearer {token}",
        "Host": "127.0.0.1",
        "Connection": "close",
    }
    try:
        assert server.wallet_controls_allowed is False
        with httpx.Client(timeout=5) as client:
            public = client.get(f"{base}/api/wallet", headers=headers)
            assert public.status_code == 200
            assert public.json()["address"] == "masked"
            assert public.json()["signing"]["available"] is False

            mutations = [
                client.post(
                    f"{base}/api/wallet/connect",
                    headers=headers,
                    json={"private_key": "must-not-reach-wallet", "alias": "blocked"},
                ),
                client.post(f"{base}/api/wallet/faucet", headers=headers, json={"sol": 0.1}),
                client.post(
                    f"{base}/api/wallet/transfer",
                    headers=headers,
                    json={"recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"},
                ),
                client.post(
                    f"{base}/api/telegram/external-handoffs",
                    headers=headers,
                    json={
                        "catalog_entity_id": "bno_news_telegram",
                        "external_url": "https://example.com/story",
                        "consent_acknowledged": True,
                    },
                ),
                client.delete(f"{base}/api/wallet", headers=headers),
            ]
            assert [response.status_code for response in mutations] == [403, 403, 403, 403, 403]
        assert fake_wallet.calls == [("snapshot", True)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_non_loopback_binding_requires_access_token(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    with pytest.raises(ValueError, match="requires --access-token-file"):
        create_server(config_path, "0.0.0.0", _free_port(), static_dir=tmp_path)


def test_loopback_settings_reject_dns_rebinding_host(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    server, thread, base = _start_server(config_path, static)
    try:
        with httpx.Client(timeout=5) as client:
            response = client.patch(
                f"{base}/api/settings",
                headers={"Host": "attacker.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert response.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_event_detail_exposes_safe_separate_fact_verification(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, _ = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    now = utcnow()
    verification_id = store.add_agent_fact_verification(
        {
            "verification_run_id": "verifier-run-secret",
            "parent_task": "trend_scout",
            "parent_run_id": "parent-run-secret",
            "subject_id": "subject-secret",
            "subject_kind": "event",
            "subject_title": "Viral otter becomes an internet mascot",
            "claim_sha256": "a" * 64,
            "requested_at": iso(now),
            "completed_at": iso(now),
            "status": "cross_source_supported",
            "claim_status": "probable_report",
            "confidence": 0.87,
            "support_source_count": 2,
            "contradiction_source_count": 0,
            "context_source_count": 0,
            "distinct_support_domain_count": 2,
            "evidence": {
                "sources": [
                    {
                        "url": "https://news-a.example/story",
                        "domain": "news-a.example",
                        "publisher": "News A",
                        "stance": "supports",
                        "content_basis": "The article directly reports the event.",
                        "origin_relationship": "unknown",
                    }
                ]
            },
            "model": "gpt-5.6-terra",
            "reasoning_effort": "medium",
            "tokens_used": 222,
            "error_code": "",
        }
    )
    observation_id, _ = store.add_observation(
        Observation(
            source="agent-scout:news-a.example",
            source_kind="news",
            title="Viral otter becomes an internet mascot",
            url="https://news-a.example/story",
            published_at=now,
            observed_at=now,
            role="identity",
            raw={
                "fact_verification_record_id": verification_id,
                "fact_verification_status": "cross_source_supported",
            },
        )
    )
    store.link_event_observation(event_id, observation_id)
    store.close()

    detail = WebData(config_path).event_detail(event_id)
    result = detail["fact_verification"]["items"][0]
    assert result["status"] == "cross_source_supported"
    assert result["decision_eligible"] is False
    assert result["affects"] == "none"
    serialized = json.dumps(detail)
    assert "verifier-run-secret" not in serialized
    assert "parent-run-secret" not in serialized
    assert "subject-secret" not in serialized
    assert '"claim_sha256"' not in serialized
