from datetime import datetime, timedelta, timezone

import pytest

from memetrader.capital_context import (
    build_capital_exit_frame,
    evaluate_capital_exit_context,
)
from memetrader.capital_exits import HOLD, SELL, WAIT, evaluate_exit


OPENED = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
TOKEN = "solana:mint"
POOL = "pool"


def stamp(seconds):
    return (OPENED + timedelta(seconds=seconds)).isoformat()


def position(**changes):
    return {
        "token_id": TOKEN, "entry_pair_address": POOL,
        "opened_at": stamp(0), "stake_usd": 100,
        "realized_proceeds_usd": 30, "allocated_cost_usd": 20,
        "principal_recovered": 1, "amount_raw": "50",
        "initial_amount_raw": "100", "paper_quantity_tokens": 100,
        "remaining_quantity_tokens": 50, **changes,
    }


def market(seconds=80, price=2, liquidity=800, sequence=8, **changes):
    return {
        "token_id": TOKEN, "pair_address": POOL, "status": "VISIBLE",
        "price_usd": price, "liquidity_usd": liquidity,
        "sample_sequence": sequence, "observed_at": stamp(seconds),
        "recorded_at": stamp(seconds + 0.1), **changes,
    }


def entry(**changes):
    return {
        "token_id": TOKEN, "pair_address": POOL, "price_usd": 1,
        "liquidity_usd": 1000, "observed_at": stamp(-2),
        "recorded_at": stamp(0), **changes,
    }


def flow(evidence_id, seconds, *, net_raw=-20_000_000, breadth=2,
         top3=.8, creator=10, sells=40, **changes):
    payload = {
        "complete": True, "scan_complete": True,
        "future_data_rejected": False, "usd_conversion_complete": True,
        "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
        "decision_at": stamp(seconds), "token_id": TOKEN,
        "pool_address": POOL, "quote_mint": "quote",
        "net_quote_flow_raw": net_raw, "effective_breadth": breadth,
        "top3_notional_share": top3,
        "creator_sell_quote_notional_usd": creator,
        "sell_quote_notional_usd": sells,
        # Counts are retained diagnostics and are never used as notional.
        "buy_count": 999, "sell_count": 1,
        "resolver": {
            "status": "verified", "pool_address": POOL,
            "base_mint": "mint", "quote_mint": "quote",
            "base_decimals": 6, "quote_decimals": 6,
            "observed_at": stamp(seconds - 1),
            "recorded_at": stamp(seconds - .9),
        },
        "quote_conversion": {
            "quote_mint": "quote", "usd_per_quote": 1,
            "observed_at": stamp(seconds - 1),
            "recorded_at": stamp(seconds - .9), "max_age_seconds": 15,
        },
        **changes,
    }
    return {
        "id": evidence_id, "token_id": TOKEN, "pair_address": POOL,
        "observed_at": stamp(seconds), "recorded_at": stamp(seconds + .2),
        "payload": payload,
    }


def vault(evidence_id, seconds, slot, direction="SELL_LIKE_NET", **changes):
    payload = {
        "observer_version": "chain-pattern-exact/v1",
        "pool_target_id": 44, "observed_at": stamp(seconds),
        "slot_min": slot, "slot_max": slot,
        "features": {
            "flow_granularity": "confirmed_slot_net_not_transaction_identity",
            "effective_quote_reserve_known": True,
            "latest_direction": direction,
            "windows": {"10": {
                "base_change_ratio": .2,
                "raw_quote_change_ratio": -.2,
                "effective_quote_change_ratio": -.2,
            }},
        },
        **changes,
    }
    return {
        "id": evidence_id, "token_id": TOKEN, "pair_address": POOL,
        "observed_at": stamp(seconds), "recorded_at": stamp(seconds + .1),
        "payload": payload,
    }


def test_builds_market_value_cost_partial_and_actual_native_flow():
    prior_flow = flow(1, 70, net_raw=5_000_000, breadth=4)
    current_flow = flow(2, 80)
    current_flow["payload"]["resolver"].update(
        observed_at=stamp(-30), recorded_at=stamp(-29),
    )
    adapted_position, frame = build_capital_exit_frame(
        position(), market(), entry(), [current_flow, prior_flow], [],
        kind="price_to_flow_fragility", now=stamp(81),
        previous_market=market(20, price=1.5, liquidity=1000, sequence=7),
    )
    assert adapted_position["sold_fraction"] == pytest.approx(.5)
    assert adapted_position["remaining_cost_usd"] == pytest.approx(80)
    assert frame["market_position_value_usd"] == pytest.approx(100)
    assert frame["market_position_value_usd"] == pytest.approx(100)
    assert frame["net_market_position_value_usd"] == pytest.approx(96)
    assert frame["position_value_ratio"] == pytest.approx(1.2)
    assert frame["economic_return"] == pytest.approx(.26)
    assert frame["value_kind"] == "economic"
    assert frame["proposed_sell_fraction"] == pytest.approx(70 / 96)
    assert frame["price_return"] == pytest.approx(1)
    assert frame["effective_depth_ratio"] == pytest.approx(.8)
    assert frame["effective_depth_change_ratio"] == pytest.approx(-.2)
    assert frame["effective_depth_change_window_seconds"] == pytest.approx(60)
    assert frame["effective_buyer_breadth_change_ratio"] == pytest.approx(-.5)
    assert frame["net_quote_flow_raw"] == -20_000_000
    assert frame["net_quote_flow_native"] == pytest.approx(-20)
    assert frame["net_quote_flow_usd"] == pytest.approx(-20)
    assert frame["frame_id"] == "amountful:2"
    assert evaluate_exit(
        "price_to_flow_fragility", adapted_position, frame, now=stamp(81)
    )[0] == SELL


def test_counts_or_unverified_conversion_never_become_flow_but_market_survives():
    invalid = flow(2, 80, usd_conversion_complete=False)
    adapted_position, frame = build_capital_exit_frame(
        position(), market(), entry(), [invalid], [],
        kind="earn_the_hold", now=stamp(81),
    )
    assert frame["flow_semantics"] is None
    assert frame["net_quote_flow_usd"] is None
    assert frame["position_value_ratio"] == pytest.approx(1.2)
    assert evaluate_exit(
        "earn_the_hold", adapted_position, frame, now=stamp(81)
    )[0:2] == (WAIT, "actual_notional_flow_required")


def test_pool_creator_is_not_promoted_to_token_creator_distribution():
    baseline = flow(0, 60, net_raw=10_000_000, creator=0, sells=10, breadth=8)
    first = flow(1, 70, net_raw=-80_000_000, creator=40, sells=80, breadth=4)
    second = flow(2, 80, net_raw=-90_000_000, creator=50, sells=90, breadth=2)
    result = evaluate_capital_exit_context(
        "creator_early_holder_distribution", position(),
        market(70, liquidity=1000, sequence=7), entry(),
        amountful_rows=[baseline, first], now=stamp(71),
        previous_market=market(60, liquidity=1200, sequence=6),
    )
    assert result[0:2] == (WAIT, "missing_or_invalid_distribution_evidence")
    assert result[3]["creator_scope"] is None


def test_realized_principal_infers_recovery_without_legacy_flag():
    adapted, frame = build_capital_exit_frame(
        position(principal_recovered=0, realized_proceeds_usd=110),
        market(), entry(), [flow(2, 80)], [], kind="failed_continuation_profit_lock",
        now=stamp(81),
    )
    assert adapted["principal_recovered"] is True
    assert frame["proposed_sell_fraction"] is None


def test_two_confirmed_vault_rows_trigger_once_and_reuse_is_duplicate():
    rows = [vault(10, 70, 100), vault(11, 80, 101)]
    result = evaluate_capital_exit_context(
        "vault_hazard", position(), market(), entry(),
        vault_rows=rows, now=stamp(81),
    )
    assert result[0:2] == (SELL, "two_frame_vault_unwind")
    assert result[3]["required_fill"] == "post_trigger_amount_specific_quote"
    assert result[3]["confirmation_basis"] == "confirmed_slot_net_not_transaction_identity"
    repeated = evaluate_capital_exit_context(
        "vault_hazard", position(), market(), entry(),
        vault_rows=rows, state=result[2], now=stamp(81),
    )
    assert repeated[0:2] == (WAIT, "duplicate_frame")


def test_vault_identity_or_nonconfirmed_producer_cannot_sell():
    wrong = vault(10, 80, 100)
    wrong["pair_address"] = "other"
    assert evaluate_capital_exit_context(
        "vault_hazard", position(), market(), entry(),
        vault_rows=[wrong], now=stamp(81),
    )[0] == WAIT
    unconfirmed = vault(11, 80, 101)
    unconfirmed["payload"]["features"]["flow_granularity"] = "unknown"
    assert evaluate_capital_exit_context(
        "vault_hazard", position(), market(), entry(),
        vault_rows=[unconfirmed], now=stamp(81),
    )[0] == WAIT
