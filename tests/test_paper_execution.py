from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.paper_execution import (
    DEFAULT_EXECUTION_SETTINGS,
    buy_terms,
    effective_execution_settings,
    execution_definition_fields,
    normalize_execution_settings,
    pool_is_below_floor,
    sell_terms,
)
from memetrader.store import Store


def _token(name: str) -> TokenCandidate:
    return TokenCandidate(
        "solana", str(Pubkey.new_unique()), name, name[:4], source="fixture"
    )


def _snapshot(token, pair, when, *, price=2.0, liquidity=10_000.0):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000.0, 300.0, 3, 1,
        observed_at=when, ingested_at=when, provider="dexscreener",
        raw={"pair": {"chainId": token.chain, "dexId": "pumpswap",
            "pairAddress": pair,
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity},
            "txns": {"m5": {"buys": 3, "sells": 1},
                     "h1": {"buys": 3, "sells": 1}},
            "volume": {"m5": 300.0, "h1": 300.0}}},
    )


def _mark(store, clock, token, pair, when, *, price, liquidity):
    clock[0] = when
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, when, price=price, liquidity=liquidity),
        recorded_at=when,
    )
    return store.evaluate_chain_meme_trader_market_marks(
        definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        now=when, token_ids=[token.token_id],
    )


def test_execution_settings_validate_and_exact_quotes_do_not_double_slip():
    assert normalize_execution_settings() == DEFAULT_EXECUTION_SETTINGS
    settings = normalize_execution_settings({
        "buy_slippage_pct": 10,
        "sell_slippage_pct": 5,
        "additional_fee_usd_each_fill": 1,
        "min_pool_liquidity_usd": 0,
    })
    fields = execution_definition_fields(settings)
    assert fields == {
        "buy_slippage_bps": 1000,
        "sell_slippage_bps": 500,
        "additional_fee_usd_each_fill": 1.0,
        "min_pool_liquidity_usd": 0.0,
    }
    assert buy_terms(20, 2, fields) == pytest.approx({
        "execution_price_usd": 2.2, "quantity_tokens": 20 / 2.2,
        "notional_usd": 20, "fee_usd": 1, "total_cost_usd": 21,
    })
    assert sell_terms(10, 2, fields)["net_usd"] == pytest.approx(18)
    assert sell_terms(10, 2, fields, exact_gross_usd=17)["net_usd"] == 16
    assert not pool_is_below_floor(None, {**fields, "min_pool_liquidity_usd": 1000})
    assert pool_is_below_floor(999, {**fields, "min_pool_liquidity_usd": 1000})
    assert not pool_is_below_floor(1000, {**fields, "min_pool_liquidity_usd": 1000})
    for bad in (True, -0.01, 50.01, 1.234):
        with pytest.raises(ValueError):
            normalize_execution_settings({"buy_slippage_pct": bad})


def test_activation_is_immutable_and_market_ledger_uses_frozen_execution(
    tmp_path, monkeypatch,
):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "paper-execution.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    registration = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?", (version,),
    ).fetchone()
    raw_before = registration["definition_json"]
    policy_hashes_before = {
        row["arm_id"]: row["behavior_contract_hash"]
        for row in store.db.execute(
            "SELECT arm_id,behavior_contract_hash FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=?", (version,),
        )
    }
    settings = {"buy_slippage_pct": 10, "sell_slippage_pct": 5,
                "additional_fee_usd_each_fill": 1,
                "min_pool_liquidity_usd": 1000}
    activated = store.activate_chain_paper_execution(
        settings, activated_at=clock[0],
    )
    assert store.activate_chain_paper_execution(
        settings, activated_at=clock[0] + timedelta(seconds=1),
    )["activation_key"] == activated["activation_key"]
    assert effective_execution_settings(store.db) == normalize_execution_settings(settings)
    assert store.db.execute(
        "SELECT COUNT(*) FROM kv WHERE key LIKE 'chain-paper-execution:activation:%'"
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?", (version,),
    ).fetchone()[0] == raw_before
    assert {
        row["arm_id"]: row["behavior_contract_hash"]
        for row in store.db.execute(
            "SELECT arm_id,behavior_contract_hash FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=?", (version,),
        )
    } == policy_hashes_before

    pre, pre_pair = _token("Before"), str(Pubkey.new_unique())
    clock[0] += timedelta(seconds=1)
    store.upsert_token(pre, seen_at=clock[0])
    store.add_snapshot(_snapshot(pre, pre_pair, clock[0]))
    assert store.register_chain_meme_l0_experiments() == 4

    token, pair = _token("Forward"), str(Pubkey.new_unique())
    opened = clock[0] + timedelta(seconds=1)
    clock[0] = opened
    store.upsert_token(token, seen_at=opened)
    source_id = store.add_snapshot(_snapshot(token, pair, opened))
    store.enroll_chain_meme_trader_v6(definition_version=version)
    candidate = "l0_continuation_failure_candidate_v1"
    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND entry_snapshot_id=?", (version, candidate, source_id),
    ).fetchone()
    assert position["entry_execution_price_usd"] == pytest.approx(2.2)
    assert position["paper_quantity_tokens"] == pytest.approx(20 / 2.2)
    assert position["stake_usd"] == pytest.approx(21)
    buy = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND side='BUY'", (version, candidate),
    ).fetchone()
    assert (buy["gross_usd"], buy["net_cash_flow_usd"]) == pytest.approx((20, -21))

    _mark(store, clock, token, pair, opened + timedelta(seconds=60),
          price=2.1, liquidity=10_000)
    _mark(store, clock, token, pair, opened + timedelta(seconds=120),
          price=2.0, liquidity=9_000)
    _mark(store, clock, token, pair, opened + timedelta(seconds=126),
          price=1.95, liquidity=8_500)
    expected = (20 / 2.2) * 1.95 * 0.95 - 1
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND side='SELL'", (version, candidate),
    ).fetchone()
    assert sell["net_cash_flow_usd"] == pytest.approx(expected)
    assert sell["realized_pnl_usd"] == pytest.approx(expected - 21)
    evidence = json.loads(store.db.execute(
        "SELECT m.trigger_evidence_json FROM chain_meme_trader_positions p "
        "JOIN chain_meme_trader_fills f ON f.id=p.last_fill_id "
        "JOIN chain_meme_trader_marks m ON m.id=-f.intent_id "
        "WHERE p.definition_version=? AND p.arm_id=? AND p.entry_snapshot_id=?",
        (version, candidate, source_id),
    ).fetchone()[0])
    assert evidence["paper_execution"] == {
        "buy_slippage_bps": 1000, "sell_slippage_bps": 500,
        "additional_fee_usd_each_fill": 1.0,
        "slippage_already_in_exact_minimum": False,
    }

    control = "l0_continuation_failure_control_v1"
    dust_token, dust_pair = _token("Dust"), str(Pubkey.new_unique())
    dust_opened = opened + timedelta(seconds=132)
    clock[0] = dust_opened
    store.upsert_token(dust_token, seen_at=dust_opened)
    dust_source_id = store.add_snapshot(_snapshot(dust_token, dust_pair, dust_opened))
    store.enroll_chain_meme_trader_v6(definition_version=version)
    _mark(store, clock, dust_token, dust_pair, dust_opened + timedelta(seconds=6),
          price=1.9, liquidity=999)
    _mark(store, clock, dust_token, dust_pair, dust_opened + timedelta(seconds=12),
          price=1.9, liquidity=999)
    written = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=(SELECT shadow_cohort_id FROM "
        "chain_meme_trader_positions WHERE definition_version=? AND arm_id=? "
        "AND entry_snapshot_id=?) AND side='WRITEOFF'",
        (version, control, version, control, dust_source_id),
    ).fetchone()
    assert written["gross_usd"] == written["net_cash_flow_usd"] == 0
    assert written["realized_pnl_usd"] == pytest.approx(-21)
    store.close()
