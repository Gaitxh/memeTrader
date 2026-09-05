from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.capital_exits import (
    EARN_THE_HOLD_POLICY,
    HOLD,
    POST_TRIGGER_AMOUNT_QUOTE,
    SELL,
    SELL_PARTIAL,
    WAIT,
    evaluate_creator_early_holder_distribution,
    evaluate_earn_the_hold,
    evaluate_executable_recovery_decay,
    evaluate_failed_continuation_profit_lock,
    evaluate_high_recall_exit_pipeline,
    evaluate_price_to_flow_fragility,
    evaluate_vault_hazard,
    validate_sell_fraction,
)


OPENED = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
NOW = OPENED + timedelta(minutes=10)
BASE_POSITION = {
    "opened_at": OPENED.isoformat(),
    "token_id": "token-1",
    "pair_address": "pool-1",
}


def frame(frame_id: str, seconds: int, **values):
    observed = OPENED + timedelta(seconds=seconds)
    return {
        "frame_id": frame_id,
        "observed_at": observed.isoformat(),
        "recorded_at": (observed + timedelta(milliseconds=20)).isoformat(),
        "token_id": "token-1",
        "pair_address": "pool-1",
        **values,
    }


def now_for(value):
    return datetime.fromisoformat(value["recorded_at"]) + timedelta(milliseconds=10)


def flow_values(**values):
    return {
        "flow_semantics": "actual_notional",
        "net_quote_flow_usd": 10.0,
        **values,
    }


def test_earn_the_hold_is_forward_deduplicated_and_fails_only_at_deadline():
    position = dict(BASE_POSITION)
    weak = frame("weak-1", 90, **flow_values(
        position_value_ratio=0.8, value_kind="market",
        price_return=-0.1,
        effective_depth_ratio=0.7,
        net_quote_flow_usd=-5.0,
    ))
    action, reason, state, _ = evaluate_earn_the_hold(position, weak, now=now_for(weak))
    assert (action, reason, state["qualification"]) == (
        HOLD, "probation_continues", "PROBATION"
    )
    duplicate = evaluate_earn_the_hold(position, weak, state, now=now_for(weak))
    assert duplicate[0:2] == (WAIT, "duplicate_frame")

    deadline = frame("weak-2", 120, **flow_values(
        position_value_ratio=0.8, value_kind="market",
        price_return=-0.1,
        effective_depth_ratio=0.7,
        net_quote_flow_usd=-5.0,
    ))
    action, reason, state, evidence = evaluate_earn_the_hold(
        position, deadline, state, now=now_for(deadline)
    )
    assert (action, reason, state["qualification"]) == (
        SELL, "earn_the_hold_deadline_failed", "FAILED_CONTINUATION"
    )
    assert evidence["sell_fraction"] == 1.0


def test_earn_the_hold_requires_actual_notional_and_can_earn_hold():
    position = dict(BASE_POSITION)
    inferred = frame(
        "count-flow", 70, flow_semantics="transaction_count",
        net_quote_flow_usd=50, position_value_ratio=1.1, value_kind="market",
        price_return=0.1, effective_depth_ratio=1.0,
    )
    assert evaluate_earn_the_hold(position, inferred, now=now_for(inferred))[0:2] == (
        WAIT, "actual_notional_flow_required"
    )
    healthy = frame("healthy", 80, **flow_values(
        position_value_ratio=1.1, value_kind="economic",
        price_return=0.05,
        effective_depth_ratio=0.95,
    ))
    action, reason, state, _ = evaluate_earn_the_hold(position, healthy, now=now_for(healthy))
    assert (action, reason, state["qualification"]) == (
        HOLD, "probation_earned_hold", "EARNED_HOLD"
    )


def test_frame_watermark_freshness_identity_and_policy_are_fail_closed_o1():
    position = dict(BASE_POSITION)
    stale = frame("stale", 70, **flow_values(
        position_value_ratio=1.1, value_kind="market",
        price_return=0.1, effective_depth_ratio=1.0,
    ))
    stale_now = datetime.fromisoformat(stale["observed_at"]) + timedelta(seconds=16)
    action, reason, state, _ = evaluate_earn_the_hold(position, stale, now=stale_now)
    assert (action, reason) == (WAIT, "stale_frame")
    assert "last_frame_id" not in state

    mismatched = {**stale, "frame_id": "wrong-pair", "pair_address": "pool-2"}
    assert evaluate_earn_the_hold(
        position, mismatched, state, now=now_for(mismatched)
    )[0:2] == (WAIT, "frame_position_mismatch")

    custom = dict(EARN_THE_HOLD_POLICY)
    custom.update(version="earn-custom/v1", minimum_position_value_ratio=1.2)
    valid = {**stale, "frame_id": "valid"}
    action, reason, state, _ = evaluate_earn_the_hold(
        position, valid, state, now=now_for(valid), policy=custom
    )
    assert (action, reason) == (HOLD, "probation_continues")
    assert state["last_frame_id"] == "valid"
    assert "processed_frame_ids" not in state

    older = frame("older", 69, **flow_values(
        position_value_ratio=1.3, value_kind="market",
        price_return=0.1, effective_depth_ratio=1.0,
    ))
    assert evaluate_earn_the_hold(
        position, older, state, now=now_for(older), policy=custom
    )[0:2] == (WAIT, "out_of_order_frame")

    changed = {**custom, "minimum_position_value_ratio": 1.0}
    newer = frame("newer", 71, **flow_values(
        position_value_ratio=1.3, value_kind="market",
        price_return=0.1, effective_depth_ratio=1.0,
    ))
    assert evaluate_earn_the_hold(
        position, newer, state, now=now_for(newer), policy=changed
    )[0:2] == (WAIT, "policy_changed_for_existing_state")


def test_profit_lock_uses_asof_peak_and_two_independent_bad_frames():
    position = {**BASE_POSITION, "principal_recovered": True}
    peak = frame("peak", 130, **flow_values(
        position_value_ratio=1.8, value_kind="market", economic_return=0.8,
        effective_depth_change_ratio=0.0,
    ))
    action, _, state, _ = evaluate_failed_continuation_profit_lock(
        position, peak, now=now_for(peak)
    )
    assert action == HOLD
    bad1 = frame("bad-1", 140, **flow_values(
        net_quote_flow_usd=-50, position_value_ratio=1.6, value_kind="market",
        economic_return=0.6, effective_depth_change_ratio=-0.2,
    ))
    action, _, state, evidence = evaluate_failed_continuation_profit_lock(
        position, bad1, state, now=now_for(bad1)
    )
    assert action == HOLD and evidence["deterioration_streak"] == 1
    bad2 = frame("bad-2", 150, **flow_values(
        net_quote_flow_usd=-60, position_value_ratio=1.5, value_kind="market",
        economic_return=0.5, effective_depth_change_ratio=-0.3,
    ))
    action, reason, state, evidence = evaluate_failed_continuation_profit_lock(
        position, bad2, state, now=now_for(bad2)
    )
    assert (action, reason) == (SELL, "two_frame_failed_continuation")
    assert evidence["running_peak"] == pytest.approx(1.8)


def test_price_to_flow_fragility_needs_capital_breadth_concentration_and_depth():
    position = dict(BASE_POSITION)
    fragile = frame("blowoff", 130, **flow_values(
        net_quote_flow_usd=-10,
        price_change_ratio_60s=0.5,
        effective_depth_change_ratio=-0.2,
        effective_buyer_breadth_change_ratio=-0.4,
        top3_buy_notional_share=0.8,
        value_kind="market",
    ))
    action, reason, _, evidence = evaluate_price_to_flow_fragility(
        position, fragile, now=now_for(fragile)
    )
    assert (action, reason) == (SELL, "price_rise_without_capital_support")
    assert evidence["fragile_blowoff"] is True


def test_dynamic_creator_distribution_needs_two_actual_notional_frames():
    position = dict(BASE_POSITION)
    first = frame("distribution-1", 130, **flow_values(
        net_quote_flow_usd=-80,
        creator_or_early_holder_sell_notional_usd=400,
        total_sell_notional_usd=800,
        effective_depth_change_ratio=-0.2,
        effective_buyer_breadth_change_ratio=-0.3,
    ))
    action, _, state, _ = evaluate_creator_early_holder_distribution(
        position, first, now=now_for(first)
    )
    assert action == HOLD
    second = frame("distribution-2", 140, **flow_values(
        net_quote_flow_usd=-90,
        creator_or_early_holder_sell_notional_usd=500,
        total_sell_notional_usd=900,
        effective_depth_change_ratio=-0.2,
        effective_buyer_breadth_change_ratio=-0.3,
    ))
    assert evaluate_creator_early_holder_distribution(
        position, second, state, now=now_for(second)
    )[0:2] == (SELL, "dynamic_distribution_confirmed")


def vault_frame(frame_id: str, seconds: int, slot: int, direction: str, **values):
    return frame(
        frame_id,
        seconds,
        pool_target_id="pool-1",
        slot_min=slot,
        slot_max=slot,
        commitment="confirmed",
        effective_quote_reserve_known=True,
        latest_direction=direction,
        base_change_ratio=values.pop("base_change_ratio", 0.1),
        raw_quote_change_ratio=values.pop("raw_quote_change_ratio", -0.1),
        effective_quote_change_ratio=values.pop(
            "effective_quote_change_ratio", -0.1
        ),
        **values,
    )


def test_vault_hazard_rejects_lp_remove_and_requires_increasing_confirmed_slots():
    position = dict(BASE_POSITION)
    lp = vault_frame("lp", 10, 100, "LP_REMOVE_LIKE")
    action, reason, state, evidence = evaluate_vault_hazard(position, lp, now=now_for(lp))
    assert (action, reason) == (HOLD, "lp_remove_is_separate_evidence")
    assert evidence["lp_remove_observed"] is True

    first = vault_frame("sell-1", 11, 101, "SELL_LIKE_NET")
    action, _, state, _ = evaluate_vault_hazard(position, first, state, now=now_for(first))
    assert action == HOLD
    repeated_slot = vault_frame("sell-other", 12, 101, "SELL_LIKE_NET")
    action, reason, state, _ = evaluate_vault_hazard(
        position, repeated_slot, state, now=now_for(repeated_slot)
    )
    assert (action, reason) == (WAIT, "vault_slot_not_strictly_increasing")

    first_again = vault_frame("sell-2", 13, 102, "SELL_LIKE_NET")
    action, _, state, _ = evaluate_vault_hazard(
        position, first_again, state, now=now_for(first_again)
    )
    assert action == HOLD
    second = vault_frame("sell-3", 14, 103, "SELL_LIKE_NET")
    action, reason, state, evidence = evaluate_vault_hazard(
        position, second, state, now=now_for(second)
    )
    assert (action, reason) == (SELL, "two_frame_vault_unwind")
    assert evidence["required_fill"] == POST_TRIGGER_AMOUNT_QUOTE
    assert evidence["risk_state"] == "RED"
    assert evidence["dead_surface_claimed"] is False


def test_vault_extreme_red_still_needs_two_slots_and_never_claims_dead_or_fill():
    position = dict(BASE_POSITION)
    red = vault_frame(
        "red", 10, 100, "SELL_LIKE_NET",
        raw_quote_change_ratio=-0.5,
        effective_quote_change_ratio=-0.4,
    )
    action, reason, state, evidence = evaluate_vault_hazard(
        position, red, now=now_for(red)
    )
    assert (action, reason) == (HOLD, "vault_unwind_needs_independent_confirmation")
    red2 = vault_frame(
        "red-2", 11, 101, "SELL_LIKE_NET",
        raw_quote_change_ratio=-0.5,
        effective_quote_change_ratio=-0.4,
    )
    action, reason, _, evidence = evaluate_vault_hazard(
        position, red2, state, now=now_for(red2)
    )
    assert (action, reason) == (SELL, "two_frame_extreme_exact_red")
    assert evidence["required_fill"] == POST_TRIGGER_AMOUNT_QUOTE
    assert evidence["dead_surface_claimed"] is False


def test_vault_confirmation_gap_over_15_seconds_restarts_bounded_pair():
    position = dict(BASE_POSITION)
    first = vault_frame("gap-1", 30, 200, "SELL_LIKE_NET")
    _, _, state, _ = evaluate_vault_hazard(
        position, first, now=now_for(first)
    )
    after_gap = vault_frame("gap-2", 46, 201, "SELL_LIKE_NET")
    action, _, state, evidence = evaluate_vault_hazard(
        position, after_gap, state, now=now_for(after_gap)
    )
    assert action == HOLD
    assert evidence["qualifying_slots"] == [201]
    contiguous = vault_frame("gap-3", 47, 202, "SELL_LIKE_NET")
    action, _, state, evidence = evaluate_vault_hazard(
        position, contiguous, state, now=now_for(contiguous)
    )
    assert action == SELL
    assert evidence["qualifying_slots"] == [201, 202]


def recovery_frame(frame_id: str, seconds: int, ratio: float, epoch="full"):
    return frame(
        frame_id,
        seconds,
        amount_epoch=epoch,
        amount_unit="mint_raw",
        input_amount_raw="900000000",
        executable_recovery_ratio=ratio,
        recovery_semantics="amount_specific_net",
        fees_included=True,
        slippage_included=True,
    )


def test_executable_recovery_peak_resets_on_amount_epoch_and_requires_post_trigger_fill():
    position = dict(BASE_POSITION)
    peak = recovery_frame("peak", 10, 1.5)
    _, _, state, _ = evaluate_executable_recovery_decay(
        position, peak, now=now_for(peak)
    )
    drop = recovery_frame("drop", 20, 1.2)
    action, reason, state, evidence = evaluate_executable_recovery_decay(
        position, drop, state, now=now_for(drop)
    )
    assert (action, reason) == (SELL, "amount_specific_recovery_decay")
    assert evidence["required_fill"] == POST_TRIGGER_AMOUNT_QUOTE
    assert evidence["dead_surface_claimed"] is False

    partial = recovery_frame("partial-epoch", 30, 1.0, epoch="after-harvest")
    action, _, state, evidence = evaluate_executable_recovery_decay(
        position, partial, state, now=now_for(partial)
    )
    assert action == HOLD and evidence["peak_reset"] is True
    assert evidence["running_peak"] == pytest.approx(1.0)


def test_future_recovery_frame_waits_without_consuming_frame_id():
    position = dict(BASE_POSITION)
    future = recovery_frame("future", 700, 2.0)
    action, reason, state, _ = evaluate_executable_recovery_decay(
        position, future, now=NOW
    )
    assert (action, reason) == (WAIT, "noncausal_or_future_frame")
    assert state.get("last_frame_id") is None


def test_high_recall_pipeline_earns_harvests_then_exits_dead_wave_only():
    position = {
        **BASE_POSITION,
        "principal_usd": 10.0,
        "realized_proceeds_usd": 0.0,
        "sold_fraction": 0.0,
    }
    earned = frame("earned", 70, **flow_values(
        position_value_ratio=1.1,
        value_kind="market",
        price_return=0.1,
        effective_depth_ratio=1.0,
    ))
    action, _, state, _ = evaluate_high_recall_exit_pipeline(
        position, earned, now=now_for(earned)
    )
    assert action == HOLD and state["phase"] == "EARNED_HOLD"

    harvest = frame("harvest", 80, **flow_values(
        economic_return=0.25,
        proposed_sell_fraction=0.4,
    ))
    action, reason, state, evidence = evaluate_high_recall_exit_pipeline(
        position, harvest, state, now=now_for(harvest)
    )
    assert (action, reason) == (SELL_PARTIAL, "harvest_trigger_pending_fill")
    assert state["phase"] == "HARVEST_PENDING"
    assert evidence["sell_fraction"] == pytest.approx(0.4)

    unfilled = frame("harvest-unfilled", 82)
    action, reason, state, _ = evaluate_high_recall_exit_pipeline(
        position, unfilled, state, now=now_for(unfilled)
    )
    assert (action, reason, state["phase"]) == (
        WAIT, "harvest_fill_not_confirmed", "HARVEST_PENDING"
    )

    confirmation = frame("harvest-confirmed", 85)
    filled_position = {
        **position,
        "realized_proceeds_usd": 10.0,
        "sold_fraction": 0.4,
    }
    action, reason, state, _ = evaluate_high_recall_exit_pipeline(
        filled_position, confirmation, state, now=now_for(confirmation)
    )
    assert (action, reason, state["phase"]) == (
        HOLD, "harvest_fill_confirmed", "HARVESTED"
    )

    peak = frame("wave-peak", 90, **flow_values(
        position_value_ratio=1.8, value_kind="economic", economic_return=0.8,
        effective_depth_change_ratio=0.0,
    ))
    _, _, state, _ = evaluate_high_recall_exit_pipeline(
        filled_position, peak, state, now=now_for(peak)
    )
    bad1 = frame("wave-bad-1", 100, **flow_values(
        net_quote_flow_usd=-30, position_value_ratio=1.6, value_kind="economic",
        economic_return=0.6, effective_depth_change_ratio=-0.2,
    ))
    _, _, state, _ = evaluate_high_recall_exit_pipeline(
        filled_position, bad1, state, now=now_for(bad1)
    )
    bad2 = frame("wave-bad-2", 110, **flow_values(
        net_quote_flow_usd=-40, position_value_ratio=1.5, value_kind="economic",
        economic_return=0.5, effective_depth_change_ratio=-0.3,
    ))
    action, reason, state, evidence = evaluate_high_recall_exit_pipeline(
        filled_position, bad2, state, now=now_for(bad2)
    )
    assert (action, reason, state["phase"]) == (
        SELL, "two_frame_dead_wave_exit", "DEAD_WAVE_EXITED"
    )
    assert evidence["reentry_action"] is None


def test_fraction_validation_and_inputs_are_not_mutated():
    assert validate_sell_fraction(1, partial=False) == 1.0
    with pytest.raises(ValueError, match="partial_sell_fraction_must_be_below_one"):
        validate_sell_fraction(1, partial=True)
    with pytest.raises(ValueError, match="sell_fraction_out_of_range"):
        validate_sell_fraction(0, partial=False)

    position = dict(BASE_POSITION)
    original_state = {"processed_frame_ids": ["old"]}
    original_frame = frame("new", 70, **flow_values(
        position_value_ratio=1.1,
        value_kind="market",
        price_return=0.1,
        effective_depth_ratio=1.0,
    ))
    state_copy, frame_copy = copy.deepcopy(original_state), copy.deepcopy(original_frame)
    evaluate_earn_the_hold(
        position, original_frame, original_state, now=now_for(original_frame)
    )
    assert original_state == state_copy
    assert original_frame == frame_copy
