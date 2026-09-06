from __future__ import annotations

from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.paper_execution import sell_terms
from memetrader.revision_main_extensions import BALANCED_HARVEST_FLOW_EXIT_ARMS
from memetrader.store import Store


def _snapshot(
    token: TokenCandidate,
    pair: str,
    at,
    *,
    price: float = 1.0,
    volume: float = 300.0,
    buys: int = 3,
    sells: int = 1,
) -> TokenSnapshot:
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        1_000.0,
        100_000.0,
        volume,
        buys,
        sells,
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
                "txns": {
                    "m5": {"buys": buys, "sells": sells},
                    "h1": {"buys": buys, "sells": sells},
                },
                "volume": {"m5": volume, "h1": volume},
            }
        },
    )


def _open_revised_broad_positions(tmp_path, monkeypatch, name: str):
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
    policies = {item["arm_id"]: item for item in definition["policies"]}
    clock[0] += timedelta(seconds=1)
    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Capital revision", "CAP", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    store.add_snapshot(_snapshot(token, pair, clock[0]))
    store.enroll_chain_meme_trader_v6(definition_version=new)
    return store, clock, new, definition, policies, token, pair


def _position(store: Store, version: str, arm: str, token_id: str):
    return store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?",
        (version, arm, token_id),
    ).fetchone()


def _mark(store, token, pair, at, *, price, volume=300.0, buys=3, sells=1):
    store.upsert_chain_meme_trader_market_mark(
        token,
        _snapshot(
            token, pair, at, price=price, volume=volume, buys=buys, sells=sells
        ),
        recorded_at=at,
    )


@pytest.mark.parametrize(
    ("arm", "target_return", "fraction"),
    [
        ("broad_principal_lock_runner_v1", 0.40, 0.75),
        ("broad_cost_coverage_scaleout_v1", 0.30, 1.00),
        ("l0_profit_lock_candidate_v1", 0.25, 0.50),
        ("l0_profit_lock_control_v1", 0.25, 1.00),
    ],
)
def test_revised_capital_take_profit_fraction_fills_on_next_frame_with_costs(
    tmp_path, monkeypatch, arm, target_return, fraction,
):
    store, clock, version, definition, policies, token, pair = (
        _open_revised_broad_positions(
            tmp_path, monkeypatch, f"capital-tp-{arm}.sqlite3"
        )
    )
    policy = policies[arm]
    assert policy["strategy_revision"] == 2
    assert policy["take_profit"] == [
        {"return": target_return, "fraction_of_remaining": fraction}
    ]
    position = _position(store, version, arm, token.token_id)
    assert position is not None and position["stake_usd"] == pytest.approx(20.0)
    initial_amount = int(position["amount_raw"])
    initial_quantity = float(position["remaining_quantity_tokens"])

    trigger_at = clock[0] + timedelta(minutes=1)
    clock[0] = trigger_at
    price = 1.04 * (1.0 + target_return + 0.01) / 0.96
    _mark(store, token, pair, trigger_at, price=price)
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=trigger_at
    ) >= 1
    pending = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? ORDER BY id DESC LIMIT 1",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    assert pending["action"] == "TAKE_PROFIT_1"
    expected_amount = (
        initial_amount
        if fraction == 1.0
        else max(1, min(initial_amount, round(initial_amount * fraction)))
    )
    assert int(pending["sell_amount_raw"]) == expected_amount
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()[0] == 0

    sold_at = trigger_at + timedelta(seconds=1)
    clock[0] = sold_at
    _mark(store, token, pair, sold_at, price=price)
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=sold_at
    ) >= 1
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    formal_quantity = initial_quantity * expected_amount / initial_amount
    expected = sell_terms(formal_quantity, price, definition)["net_usd"]
    assert sell["created_at"] == iso(sold_at)
    assert sell["gross_usd"] == pytest.approx(expected)
    assert sell["net_cash_flow_usd"] == pytest.approx(expected)

    untouched_arm = next(iter(BALANCED_HARVEST_FLOW_EXIT_ARMS))
    assert store.db.execute(
        "SELECT COALESCE(SUM(net_cash_flow_usd),0) FROM chain_meme_trader_trades "
        "WHERE definition_version=? AND arm_id=?",
        (version, untouched_arm),
    ).fetchone()[0] == pytest.approx(-20.0)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND side='SELL'",
        (version, untouched_arm),
    ).fetchone()[0] == 0
    store.close()


@pytest.mark.parametrize(
    ("arm", "capital_kind"),
    [
        ("l0_continuation_failure_candidate_v1", "l0_loss_deterioration"),
        ("l0_continuation_failure_control_v1", None),
    ],
)
def test_revised_continuation_pair_exits_unrecovered_at_ten_minutes_next_frame(
    tmp_path, monkeypatch, arm, capital_kind,
):
    store, clock, version, definition, policies, token, pair = (
        _open_revised_broad_positions(
            tmp_path, monkeypatch, f"capital-review-{arm}.sqlite3"
        )
    )
    policy = policies[arm]
    assert policy["strategy_revision"] == 2
    assert policy.get("capital_exit_kind") == capital_kind
    assert policy["runner_review_minutes"] == 10.0
    assert policy["max_hold_minutes"] == 30.0
    position = _position(store, version, arm, token.token_id)
    assert position is not None
    price = 1.04 * 0.90 / 0.96

    before = clock[0] + timedelta(minutes=9, seconds=59)
    clock[0] = before
    _mark(store, token, pair, before, price=price)
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=before
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()[0] == 0

    trigger_at = clock[0] + timedelta(seconds=2)
    clock[0] = trigger_at
    _mark(store, token, pair, trigger_at, price=price)
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=trigger_at
    ) >= 1
    pending = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    assert pending["action"] == "RUNNER_REVIEW_EXIT"
    assert pending["status"] == "pending"

    sold_at = trigger_at + timedelta(seconds=1)
    clock[0] = sold_at
    _mark(store, token, pair, sold_at, price=price)
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=sold_at
    ) >= 1
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    expected = sell_terms(
        float(position["remaining_quantity_tokens"]), price, definition
    )["net_usd"]
    assert sell["created_at"] == iso(sold_at)
    assert sell["gross_usd"] == pytest.approx(expected)
    assert sell["net_cash_flow_usd"] == pytest.approx(expected)
    assert _position(store, version, arm, token.token_id)["status"] == "closed"
    store.close()
