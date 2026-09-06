from __future__ import annotations

from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.paper_execution import sell_terms
from memetrader.store import Store


ARM = "broad_principal_lock_runner_v1"


def _snapshot(token: TokenCandidate, pair: str, at, *, price: float) -> TokenSnapshot:
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        1_000.0,
        100_000.0,
        300.0,
        3,
        1,
        observed_at=at,
        ingested_at=at,
        provider="dexscreener",
        raw={
            "pair": {
                "chainId": token.chain,
                "dexId": "pumpswap",
                "pairAddress": pair,
                "pairCreatedAt": round((at - timedelta(seconds=60)).timestamp() * 1000),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": 1_000.0},
                "txns": {"m5": {"buys": 3, "sells": 1}},
                "volume": {"m5": 300.0},
            }
        },
    )


def _open_position(tmp_path, monkeypatch, name: str):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(
        Store,
        "CHAIN_MEME_TRADER_ACTIVE_VERSION",
        Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION,
    )
    store = Store(tmp_path / name)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_capital_experiments()
    store.register_chain_meme_trader_cost_coverage_scaleout()
    store.register_chain_meme_l0_experiments()
    old = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    new = Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION
    clock[0] += timedelta(seconds=1)
    store.activate_chain_meme_trader_funding_epoch(
        target_version=new,
        source_version=old,
        at=clock[0],
        apply_strategy_revisions=True,
    )
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", new)
    definition = store._chain_meme_trader_effective_definition(
        new, store._chain_meme_trader_registration(new)["definition_json"]
    )
    policy = next(item for item in definition["policies"] if item["arm_id"] == ARM)
    assert policy["strategy_revision"] == 2
    assert policy["exit_family"] == "principal_lock_runner"
    assert policy["runner_review_minutes"] == 30.0
    clock[0] += timedelta(seconds=1)
    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Principal review", "PR", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    store.add_snapshot(_snapshot(token, pair, clock[0], price=1.0))
    store.enroll_chain_meme_trader_v6(definition_version=new)
    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?",
        (new, ARM, token.token_id),
    ).fetchone()
    assert position is not None
    return store, clock, new, definition, token, pair, position


def _mark(store: Store, token: TokenCandidate, pair: str, at, price: float) -> None:
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, at, price=price), recorded_at=at
    )


def test_principal_review_exits_positive_unrecovered_position_on_next_frame(
    tmp_path, monkeypatch,
):
    store, clock, version, definition, token, pair, position = _open_position(
        tmp_path, monkeypatch, "principal-unrecovered.sqlite3"
    )
    review_at = clock[0] + timedelta(minutes=30)
    clock[0] = review_at
    price = 1.04 * 1.05 / 0.96
    _mark(store, token, pair, review_at, price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=review_at
    )
    pending = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND status='pending'",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()
    assert pending["action"] == "RUNNER_REVIEW_EXIT"
    assert pending["reason"] == "market_mark_principal_not_recovered_at_review"
    assert float(position["realized_proceeds_usd"]) == 0.0

    sold_at = review_at + timedelta(seconds=1)
    clock[0] = sold_at
    _mark(store, token, pair, sold_at, price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=sold_at
    )
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()
    expected = sell_terms(
        float(position["remaining_quantity_tokens"]), price, definition
    )["net_usd"]
    assert sell["created_at"] == iso(sold_at)
    assert sell["gross_usd"] == pytest.approx(expected)
    assert expected > float(position["stake_usd"])
    store.close()


def test_principal_review_keeps_runner_after_actual_proceeds_recover_stake(
    tmp_path, monkeypatch,
):
    store, clock, version, _definition, token, pair, position = _open_position(
        tmp_path, monkeypatch, "principal-recovered.sqlite3"
    )
    take_profit_at = clock[0] + timedelta(minutes=1)
    clock[0] = take_profit_at
    price = 1.04 * 1.41 / 0.96
    _mark(store, token, pair, take_profit_at, price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=take_profit_at
    )
    fill_at = take_profit_at + timedelta(seconds=1)
    clock[0] = fill_at
    _mark(store, token, pair, fill_at, price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=fill_at
    )
    recovered = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()
    assert recovered["status"] == "open"
    assert int(recovered["principal_recovered"]) == 1
    assert float(recovered["realized_proceeds_usd"]) >= float(recovered["stake_usd"])

    review_at = clock[0] + timedelta(minutes=29)
    clock[0] = review_at
    _mark(store, token, pair, review_at, price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=review_at
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND status='pending'",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, ARM, position["shadow_cohort_id"]),
    ).fetchone()[0] == "open"
    store.close()
