from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.keypair import Keypair

import memetrader.live_wallets as live_module
from memetrader.collectors import SOLANA_WRAPPED_SOL_MINT
from memetrader.live_wallets import SLIPPAGE_BPS, SolanaLiveWalletManager
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.store import Store


def test_live_wallet_binds_one_strategy_and_mirrors_only_new_forward_trade(tmp_path, monkeypatch):
    monkeypatch.setattr(live_module, "_dpapi_protect", lambda value: bytes(reversed(value)))
    monkeypatch.setattr(live_module, "_dpapi_unprotect", lambda value: bytes(reversed(value)))

    database = tmp_path / "forward.sqlite3"
    store = Store(database, initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v14()
    store.activate_chain_meme_trader_v14()
    definition = Store._json_object(registration["definition_json"])
    strategy_id = next(
        policy["arm_id"] for policy in definition["policies"]
        if policy["entry_family"] == "broad_launch"
    )

    manager = SolanaLiveWalletManager(tmp_path, database)
    monkeypatch.setattr(
        manager, "_balances",
        lambda wallet, refresh=False: {"status": "ok", "sol": 1.0, "usdc": 100.0},
    )
    keypair = Keypair()
    manager.connect(str(keypair), "QA wallet", strategy_id)
    state_text = manager.state_path.read_text(encoding="utf-8")
    assert str(keypair) not in state_text
    wallet_id = manager.snapshot()["wallets"][0]["id"]
    manager.set_enabled(wallet_id, True)

    observed = utcnow()
    address = str(Keypair().pubkey())
    token = TokenCandidate(
        chain="solana", address=address, name="Live QA", symbol="LQA",
        source="dexscreener",
    )
    store.upsert_token(token, seen_at=observed)
    store.add_snapshot(TokenSnapshot(
        "solana", address, 1.0, 10_000, 100_000, 250, 2, 1,
        observed_at=observed, ingested_at=observed, provider="dexscreener",
        raw={"pair": {
            "chainId": "solana", "dexId": "pumpfun", "pairAddress": "pool-live-qa",
            "pairCreatedAt": round((observed - timedelta(minutes=1)).timestamp() * 1000),
            "priceUsd": "1.0",
            "baseToken": {"address": address, "name": "Live QA", "symbol": "LQA"},
            "quoteToken": {"address": SOLANA_WRAPPED_SOL_MINT},
            "txns": {"m5": {"buys": 2, "sells": 1}, "h1": {"buys": 2, "sells": 1}},
            "volume": {"m5": 250.0, "h1": 250.0},
        }},
    ))
    store.enroll_chain_meme_trader_v6(definition_version=Store.CHAIN_MEME_TRADER_V14_VERSION)
    store.close()

    balances = iter([0, 12_345])
    monkeypatch.setattr(manager, "_token_balance_raw", lambda owner, mint: next(balances))
    monkeypatch.setattr(
        manager, "_quote",
        lambda input_mint, output_mint, amount_raw: {
            "outAmount": "12345", "slippageBps": SLIPPAGE_BPS,
        },
    )
    monkeypatch.setattr(manager, "_swap_transaction", lambda quote, address: "encoded")
    monkeypatch.setattr(manager, "_sign_and_send", lambda wallet_id, transaction: "signature")
    monkeypatch.setattr(manager, "_confirm", lambda signature: True)

    assert manager.sync_once() == 1
    saved = json.loads(manager.state_path.read_text(encoding="utf-8"))
    wallet = saved["wallets"][0]
    assert wallet["enabled"] is True
    assert wallet["pending"] is None
    assert wallet["last_trade_id"] > 0
    position = next(iter(saved["positions"][wallet_id].values()))
    assert position["amount_raw"] == 12_345
    assert "signature" in manager.execution_log_path.read_text(encoding="utf-8")

    store = Store(database)
    paper_position = store.db.execute(
        "SELECT arm_id,shadow_cohort_id,token_id FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id=?",
        (Store.CHAIN_MEME_TRADER_V14_VERSION, strategy_id),
    ).fetchone()
    sell_trade_ids = []
    with store.db:
        store.db.execute(
            "UPDATE chain_meme_trader_positions SET initial_amount_raw='1000' "
            "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
            (
                Store.CHAIN_MEME_TRADER_V14_VERSION, strategy_id,
                paper_position["shadow_cohort_id"],
            ),
        )
        for index in (1, 2):
            filled_at = (observed + timedelta(seconds=10 + index)).isoformat()
            fill_id = store.db.execute(
                "INSERT INTO chain_meme_trader_fills("
                "definition_version,intent_id,result_id,attempt_id,execution_mode,adapter,"
                "arm_id,shadow_cohort_id,token_id,side,input_amount_raw,output_amount_raw,"
                "gross_usd,filled_at) VALUES(?,?,?,?, 'paper','test',?,?,?,'SELL',"
                "'250','10000000',10,?)",
                (
                    Store.CHAIN_MEME_TRADER_V14_VERSION, -100 - index,
                    -100 - index, -100 - index, strategy_id,
                    paper_position["shadow_cohort_id"], token.token_id, filled_at,
                ),
            ).lastrowid
            sell_trade_ids.append(store.db.execute(
                "INSERT INTO chain_meme_trader_trades("
                "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "net_cash_flow_usd,realized_pnl_usd,reason,created_at,execution_fill_id) "
                "VALUES(?,?,?,?,'SELL',10,10,-10,'test_partial',?,?)",
                (
                    Store.CHAIN_MEME_TRADER_V14_VERSION, strategy_id,
                    paper_position["shadow_cohort_id"], token.token_id,
                    filled_at, fill_id,
                ),
            ).lastrowid)
    store.close()

    first_sell = manager._next_trade({**wallet, "last_trade_id": wallet["last_trade_id"]})
    second_sell = manager._next_trade({**wallet, "last_trade_id": sell_trade_ids[0]})
    assert first_sell["sell_fraction"] == pytest.approx(0.25)
    assert second_sell["sell_fraction"] == pytest.approx(1 / 3)

    manager.connect(str(Keypair()), "Second wallet, same strategy", strategy_id)
    assert len(manager.snapshot()["wallets"]) == 2


def test_live_wallet_accepts_appended_strategy_but_keeps_real_balance_gate(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(live_module, "_dpapi_protect", lambda value: bytes(reversed(value)))
    monkeypatch.setattr(live_module, "_dpapi_unprotect", lambda value: bytes(reversed(value)))
    database = tmp_path / "forward.sqlite3"
    store = Store(database, initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v22()
    store.activate_chain_meme_trader_v22()
    source = Store._json_object(registration["definition_json"])["policies"][-1]
    appended = dict(source)
    for field in ("stage", "behavior_contract_hash"):
        appended.pop(field, None)
    appended.update({
        "arm_id": "wallet_additive_forward_v1",
        "canonical_id": "wallet-additive-forward-v1",
        "name": "Wallet additive forward",
    })
    store.append_chain_meme_trader_policy(appended)
    store.close()

    manager = SolanaLiveWalletManager(tmp_path, database)
    balances = {"status": "ok", "sol": 1.0, "usdc": 0.0}
    monkeypatch.setattr(manager, "_balances", lambda wallet, refresh=False: balances)
    manager.connect(str(Keypair()), "Added strategy", appended["arm_id"])
    wallet_id = manager.snapshot()["wallets"][0]["id"]
    with pytest.raises(live_module.LiveWalletError, match="USDC 不足最小买入金额"):
        manager.set_enabled(wallet_id, True)
    balances["usdc"] = 12.0
    manager.set_enabled(wallet_id, True)
    assert manager.snapshot()["wallets"][0]["enabled"] is True


def test_live_wallet_detail_is_safe_and_lists_recent_operations_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(live_module, "_dpapi_protect", lambda value: bytes(reversed(value)))
    monkeypatch.setattr(live_module, "_dpapi_unprotect", lambda value: bytes(reversed(value)))
    database = tmp_path / "forward.sqlite3"
    store = Store(database, initial_cash_usd=1000)
    registration = store.register_chain_meme_trader_v14()
    store.activate_chain_meme_trader_v14()
    definition = Store._json_object(registration["definition_json"])
    strategy_id, replacement_strategy_id = [
        policy["arm_id"] for policy in definition["policies"]
        if policy["entry_family"] == "broad_launch"
    ][:2]
    store.close()

    manager = SolanaLiveWalletManager(tmp_path, database)
    monkeypatch.setattr(
        manager, "_balances",
        lambda wallet, refresh=False: {"status": "ok", "sol": 1.0, "usdc": 100.0},
    )
    keypair = Keypair()
    manager.connect(str(keypair), "Detail QA", strategy_id)
    wallet_id = manager.snapshot()["wallets"][0]["id"]
    manager.bind(wallet_id, replacement_strategy_id)
    manager._append_execution({
        "wallet_id": wallet_id, "paper_trade_id": 10, "side": "BUY",
        "status": "confirmed", "amount_raw": 20_000_000, "signature": "public-but-omitted",
    })
    manager._append_execution({
        "wallet_id": wallet_id, "paper_trade_id": 11, "side": "SELL",
        "status": "confirmed", "amount_raw": 123, "error": "also-omitted",
    })

    detail = manager.detail(wallet_id)
    assert detail["wallet"]["strategy_id"] == replacement_strategy_id
    assert detail["wallet"]["strategy_id"] != strategy_id
    assert detail["balance"]["status"] == "ok"
    assert [item["paper_trade_id"] for item in detail["executions"]] == [11, 10]
    serialized = json.dumps(detail)
    assert str(keypair) not in serialized
    assert "signature" not in serialized
    assert "public-but-omitted" not in serialized
    assert "also-omitted" not in serialized


def test_live_buy_scales_to_fresh_integer_usdc_balance(tmp_path, monkeypatch):
    manager = SolanaLiveWalletManager(tmp_path, tmp_path / "unused.sqlite3")
    manager._write({
        "version": 1,
        "wallets": [{
            "id": "wallet", "address": "address", "enabled": True,
            "entry_enabled": True, "last_trade_id": 0, "pending": None,
        }],
        "positions": {},
    })
    monkeypatch.setattr(
        manager, "_next_trade",
        lambda wallet: {
            "id": 1, "side": "BUY", "token_id": "solana:mint",
            "shadow_cohort_id": 10,
        },
    )
    monkeypatch.setattr(
        manager, "_balances",
        lambda wallet, refresh=False: {
            "status": "ok", "sol_raw": 5_000_000, "usdc_raw": 7_500_000,
        },
    )
    token_balances = iter([0, 123])
    monkeypatch.setattr(manager, "_token_balance_raw", lambda owner, mint: next(token_balances))
    quoted = []
    monkeypatch.setattr(
        manager, "_quote",
        lambda input_mint, output_mint, amount_raw: (
            quoted.append(amount_raw) or {"outAmount": "123"}
        ),
    )
    monkeypatch.setattr(manager, "_swap_transaction", lambda quote, address: "encoded")
    monkeypatch.setattr(manager, "_sign_and_send", lambda wallet_id, transaction: "signature")
    monkeypatch.setattr(manager, "_confirm", lambda signature: True)

    assert manager.sync_once() == 1
    assert quoted == [7_500_000]


def test_paused_wallet_skips_buy_but_continues_existing_sell(tmp_path, monkeypatch):
    manager = SolanaLiveWalletManager(tmp_path, tmp_path / "unused.sqlite3")
    manager._write({
        "version": 1,
        "wallets": [{
            "id": "wallet", "address": "address", "enabled": True,
            "entry_enabled": True, "last_trade_id": 0, "pending": None,
        }],
        "positions": {"wallet": {"10": {"token_id": "solana:mint", "amount_raw": 100}}},
    })
    manager.set_enabled("wallet", False)

    def next_trade(wallet):
        if int(wallet["last_trade_id"]) == 0:
            return {"id": 1, "side": "BUY", "token_id": "solana:other", "shadow_cohort_id": 11}
        if int(wallet["last_trade_id"]) == 1:
            return {
                "id": 2, "side": "SELL", "token_id": "solana:mint",
                "shadow_cohort_id": 10, "sell_fraction": 1.0,
            }
        return None

    monkeypatch.setattr(manager, "_next_trade", next_trade)
    quoted = []
    monkeypatch.setattr(
        manager, "_quote",
        lambda input_mint, output_mint, amount_raw: (
            quoted.append((input_mint, output_mint, amount_raw)) or {"outAmount": "1"}
        ),
    )
    monkeypatch.setattr(manager, "_swap_transaction", lambda quote, address: "encoded")
    signed = []
    monkeypatch.setattr(
        manager, "_sign_and_send",
        lambda wallet_id, transaction: signed.append(wallet_id) or "signature",
    )
    monkeypatch.setattr(manager, "_confirm", lambda signature: True)

    assert manager.sync_once() == 0
    assert manager.sync_once() == 1
    saved = json.loads(manager.state_path.read_text(encoding="utf-8"))
    assert signed == ["wallet"]
    assert quoted == [("mint", live_module.USDC_MINT, 100)]
    assert saved["positions"]["wallet"] == {}
    assert saved["wallets"][0]["enabled"] is False
    assert saved["wallets"][0]["entry_enabled"] is False


def test_unknown_confirmation_keeps_pending_and_does_not_rebroadcast(tmp_path, monkeypatch):
    manager = SolanaLiveWalletManager(tmp_path, tmp_path / "unused.sqlite3")
    manager._write({
        "version": 1,
        "wallets": [{
            "id": "wallet", "address": "address", "enabled": True,
            "entry_enabled": True, "last_trade_id": 0, "pending": None,
        }],
        "positions": {},
    })
    monkeypatch.setattr(
        manager, "_next_trade",
        lambda wallet: {
            "id": 1, "side": "BUY", "token_id": "solana:mint",
            "shadow_cohort_id": 10,
        },
    )
    monkeypatch.setattr(
        manager, "_balances",
        lambda wallet, refresh=False: {
            "status": "ok", "sol_raw": 5_000_000, "usdc_raw": 20_000_000,
        },
    )
    monkeypatch.setattr(manager, "_token_balance_raw", lambda owner, mint: 0)
    monkeypatch.setattr(manager, "_quote", lambda *args: {"outAmount": "123"})
    monkeypatch.setattr(manager, "_swap_transaction", lambda quote, address: "encoded")
    signed = []
    monkeypatch.setattr(
        manager, "_sign_and_send",
        lambda wallet_id, transaction: signed.append(wallet_id) or "signature",
    )
    monkeypatch.setattr(manager, "_confirm", lambda signature: None)

    assert manager.sync_once() == 0
    assert manager.sync_once() == 0
    saved = json.loads(manager.state_path.read_text(encoding="utf-8"))
    assert signed == ["wallet"]
    assert saved["wallets"][0]["pending"]["signature"] == "signature"
    assert saved["wallets"][0]["enabled"] is False
