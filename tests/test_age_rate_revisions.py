from datetime import datetime, timedelta, timezone

from memetrader.age_rate_revisions import (
    evaluate_age_rate_checkpoint,
    minimum_principal_recovery_sell_amount_raw,
    next_frame_minimum_principal_recovery_raw,
)
from memetrader.capital_exits import HOLD, SELL, WAIT
from memetrader.paper_execution import sell_terms


OPENED = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
POSITION = {
    "opened_at": OPENED.isoformat(),
    "token_id": "solana:age-rate",
    "pair_address": "pool-age-rate",
    "stake_usd": 100.0,
    "realized_proceeds_usd": 0.0,
}
DEFINITION = {"sell_slippage_bps": 400, "additional_fee_usd_each_fill": 0.5}


def frame(name: str, seconds: float, *, remaining_sell_net=100.0, price=10.0, liquidity=1_000.0):
    observed = OPENED + timedelta(seconds=seconds)
    return {
        "frame_id": name,
        "observed_at": observed.isoformat(),
        "recorded_at": observed.isoformat(),
        "token_id": POSITION["token_id"],
        "pair_address": POSITION["pair_address"],
        "net_market_position_value_usd": remaining_sell_net,
        "market_price_usd": price,
        "market_liquidity_usd": liquidity,
    }


def now_for(value):
    return datetime.fromisoformat(value["recorded_at"]) + timedelta(seconds=1)


def test_checkpoint_economic_coverage_uses_unsold_net_value_not_realized_only():
    before = frame("before", 899, remaining_sell_net=100, price=10, liquidity=1_000)
    action, _, state, _ = evaluate_age_rate_checkpoint(
        POSITION, before, now=now_for(before)
    )
    assert action == HOLD
    checkpoint = frame("checkpoint", 900, remaining_sell_net=100, price=10, liquidity=1_000)
    action, reason, state, evidence = evaluate_age_rate_checkpoint(
        POSITION, checkpoint, state, now=now_for(checkpoint)
    )
    assert (action, reason) == (HOLD, "checkpoint_continue_parent")
    assert evidence["economic_coverage"] == "COVERED"
    assert POSITION["realized_proceeds_usd"] == 0.0
    assert state["checkpoint_status"] == "PASSED_TO_PARENT"


def test_checkpoint_exits_when_uncovered_or_when_both_price_and_liquidity_decline():
    before = frame("before-uncovered", 899, remaining_sell_net=100, price=10, liquidity=1_000)
    _, _, state, _ = evaluate_age_rate_checkpoint(POSITION, before, now=now_for(before))
    uncovered = frame("uncovered", 900, remaining_sell_net=99, price=11, liquidity=1_100)
    result = evaluate_age_rate_checkpoint(POSITION, uncovered, state, now=now_for(uncovered))
    assert result[0:2] == (SELL, "checkpoint_economic_uncovered_or_deteriorating")
    assert result[3]["economic_coverage"] == "UNCOVERED"

    before = frame("before-deterioration", 899, remaining_sell_net=100, price=10, liquidity=1_000)
    _, _, state, _ = evaluate_age_rate_checkpoint(POSITION, before, now=now_for(before))
    deteriorating = frame("deteriorating", 900, remaining_sell_net=100, price=9, liquidity=900)
    result = evaluate_age_rate_checkpoint(POSITION, deteriorating, state, now=now_for(deteriorating))
    assert result[0:2] == (SELL, "checkpoint_economic_uncovered_or_deteriorating")
    assert result[3]["deterioration"] is True


def test_checkpoint_keeps_unknown_deterioration_unknown_without_a_causal_prior():
    checkpoint = frame("first-checkpoint", 900, remaining_sell_net=100)
    result = evaluate_age_rate_checkpoint(POSITION, checkpoint, now=now_for(checkpoint))
    assert result[0:2] == (WAIT, "checkpoint_structure_unknown")
    assert result[3]["deterioration"] == "UNKNOWN"


def test_checkpoint_rejects_future_and_stale_frames_without_consuming_checkpoint():
    future = frame("future", 900)
    future_now = OPENED + timedelta(seconds=899)
    result = evaluate_age_rate_checkpoint(POSITION, future, now=future_now)
    assert result[0:2] == (WAIT, "noncausal_or_future_frame")
    assert "checkpoint_status" not in result[2]

    stale = frame("stale", 900)
    result = evaluate_age_rate_checkpoint(
        POSITION, stale, now=OPENED + timedelta(seconds=916)
    )
    assert result[0:2] == (WAIT, "stale_frame")
    assert "checkpoint_status" not in result[2]


def test_minimum_recovery_raw_rounds_through_sell_fees_and_recomputes_on_next_frame():
    raw = minimum_principal_recovery_sell_amount_raw(
        remaining_amount_raw=10_000,
        remaining_quantity_tokens=10.0,
        market_price_usd=20.0,
        definition=DEFINITION,
        debit_gap_usd=5.0,
    )
    assert raw is not None and 1 <= raw < 10_000
    net = sell_terms(10.0 * raw / 10_000, 20.0, DEFINITION)["net_usd"]
    prior_net = sell_terms(10.0 * (raw - 1) / 10_000, 20.0, DEFINITION)["net_usd"]
    assert net >= 5.0 > prior_net

    position = {
        "stake_usd": 10.0,
        "realized_proceeds_usd": 5.0,
        "amount_raw": "10000",
        "remaining_quantity_tokens": 10.0,
        "principal_recovered": 0,
    }
    first = next_frame_minimum_principal_recovery_raw(
        position, {"market_price_usd": 20.0}, DEFINITION
    )
    second = next_frame_minimum_principal_recovery_raw(
        position, {"market_price_usd": 40.0}, DEFINITION
    )
    assert first is not None and second is not None and second < first
    assert position["principal_recovered"] == 0


def test_minimum_recovery_requires_a_strictly_partial_coverable_amount():
    assert minimum_principal_recovery_sell_amount_raw(
        remaining_amount_raw=10,
        remaining_quantity_tokens=1.0,
        market_price_usd=1.0,
        definition=DEFINITION,
        debit_gap_usd=5.0,
    ) is None
