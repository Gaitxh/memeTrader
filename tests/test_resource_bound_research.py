from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.resource_bound_research import (
    evaluate_resource_exit, resource_entry_signal, resource_policies,
)


START = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def policy(mechanism, role="candidate"):
    return next(p for p in resource_policies()
                if p["arm_id"] == f"resource_{mechanism}_{role}_v1")


def entry_frame(**changes):
    at = START + timedelta(seconds=10)
    frame = dict(price=1, liquidity=10000, pool_age_seconds=1200,
                 buys=6, sells=4, volume=1000, volume_h1=4000,
                 buys_h1=24, sells_h1=16, upstream_provider="dexscreener",
                 observed_at=at.isoformat(), ingested_at=at.isoformat(),
                 recorded_at=at.isoformat())
    frame.update(changes)
    return frame


def signal(frame, mechanism="age_rate", role="candidate", **changes):
    return resource_entry_signal([frame], policy(mechanism, role),
                                 decision_at=changes.get("decision_at", frame["recorded_at"]),
                                 activated_at=changes.get("activated_at", START))


def test_age_twenty_minutes_constant_rate_is_false_acceleration():
    frame = entry_frame()
    control = signal(frame, role="control")
    candidate = signal(frame)
    assert control[0] and control[2]["common_ready"]
    assert not candidate[0] and candidate[2]["common_ready"]
    assert candidate[2]["old_max_rate"] == pytest.approx(11 / 3)
    assert candidate[2]["adjusted_max_rate"] == pytest.approx(1)


def test_age_sixty_minutes_agrees_and_real_acceleration_passes():
    # Sixty-minute history has the complete prior 55-minute denominator.
    frame = entry_frame(pool_age_seconds=3600)
    result = signal(frame)
    assert result[0]
    assert result[2]["adjusted_max_rate"] == result[2]["old_max_rate"]
    # At twenty minutes, m5 activity triples the actual prior rate.
    accelerated = entry_frame(buys=18, sells=12, volume=3000,
                              buys_h1=36, sells_h1=24, volume_h1=6000)
    assert signal(accelerated)[0]
    assert signal(accelerated)[2]["adjusted_max_rate"] == pytest.approx(3)


@pytest.mark.parametrize("changes", [
    {"volume_h1": 1000}, {"volume_h1": 999}, {"volume_h1": None},
    {"buys_h1": 6, "sells_h1": 4}, {"buys": -1},
    {"volume": None}, {"price": float("nan")}, {"liquidity": 999},
])
def test_invalid_or_nonpositive_baseline_rejects_both_arms(changes):
    for role in ("candidate", "control"):
        result = signal(entry_frame(**changes), role=role)
        assert not result[0] and not result[2]["common_ready"]


@pytest.mark.parametrize("age", [0, 899, 900])
def test_age_at_or_below_fifteen_minutes_is_not_common_opportunity(age):
    assert not signal(entry_frame(pool_age_seconds=age), role="control")[0]


def test_entry_future_late_pre_activation_and_missing_clock_rejected():
    frame = entry_frame()
    at = START + timedelta(seconds=10)
    assert not signal(frame, role="control", decision_at=at-timedelta(seconds=1))[0]
    assert not signal(frame, role="control", decision_at=at+timedelta(seconds=31))[0]
    assert not signal(frame, role="control", activated_at=at+timedelta(seconds=1))[0]
    for changes in ({"ingested_at": None}, {"upstream_provider": ""},
                    {"ingested_at": (at-timedelta(seconds=1)).isoformat()}):
        assert not signal({**frame, **changes}, role="control")[0]


def test_cooling_endpoint_semantics_retrace_and_activity():
    frame = entry_frame(pool_age_seconds=3600, volume=500, volume_h1=11500,
                        price_change_m5=-2, price_change_h1=30)
    result = signal(frame, "cooling_hold")
    assert result[0]
    assert result[2]["activity_ratio"] == pytest.approx(.5)
    assert result[2]["path_semantics"] == "aggregate_endpoints_not_intrawindow_path"
    for changes in ({"price_change_m5": 1}, {"price_change_m5": -15},
                    {"volume": 2000, "volume_h1": 13000}):
        changed = {**frame, **changes}
        assert signal(changed, "cooling_hold", "control")[0]
        assert not signal(changed, "cooling_hold")[0]
    assert not signal({**frame, "price_change_m5": -100}, "cooling_hold", "control")[0]


def test_cooling_fee_changes_prior_displacement_scale_without_mutation():
    frame = entry_frame(pool_age_seconds=3600, volume=500, volume_h1=11500,
                        price_change_m5=-2, price_change_h1=30)
    cfg = policy("cooling_hold")
    cfg["_execution"] = {"additional_fee_usd_each_fill": 1}
    before = deepcopy((frame, cfg))
    result = resource_entry_signal([frame], cfg, decision_at=frame["recorded_at"],
                                   activated_at=START)
    assert not result[0] and result[1] == "resource_prior_rise_below_friction_scale"
    assert (frame, cfg) == before
    assert signal(frame, "cooling_hold")[0]


def exit_frame(seconds, *, price=1.095, value=5.48, **changes):
    at = START + timedelta(seconds=seconds)
    frame = dict(frame_id=str(seconds), observed_at=at.isoformat(), recorded_at=at.isoformat(),
                 token_id="solana:Resource", pair_address="pool", original_pool=True,
                 provider="dexscreener", price_usd=price, liquidity_usd=10000,
                 economic_value_usd=value)
    frame.update(changes)
    return frame


def evaluate(frame, state=None, now=None):
    position = dict(token_id="solana:Resource", pair_address="pool", stake_usd=5,
                    opened_at=START.isoformat())
    cfg = policy("profit_structure")["capital_exit_policy"]
    before = deepcopy((position, frame, state, cfg))
    result = evaluate_resource_exit(position, frame, state,
                                    now=now or frame["recorded_at"], policy=cfg)
    assert (position, frame, state, cfg) == before
    return result


def support_state():
    state = None
    for seconds, price, value in [(10, 1.10, 5.50), (20, 1.09, 5.45), (30, 1.095, 5.48)]:
        result = evaluate(exit_frame(seconds, price=price, value=value), state)
        state = result[2]
        if seconds < 30:
            assert not state.get("support")
    assert state["support"]["price"] == 1.09
    assert state["support"]["confirmed_at"] == exit_frame(30)["observed_at"]
    return state


def test_confirmed_profitable_support_exempts_clock_then_break_sells():
    state = support_state()
    for seconds in range(40, 191, 10):
        result = evaluate(exit_frame(seconds), state)
        state = result[2]
    assert result[0] == "HOLD" and result[3]["clock_exempted"]
    assert result[3]["clock_triggered"]
    broken = evaluate(exit_frame(200, price=1.08, value=5.40), state)
    assert broken[0] == "SELL" and not broken[2].get("support")
    assert broken[3]["required_fill"] == "next_original_pool_frame"


@pytest.mark.parametrize("value", [5, 4.9])
def test_nonprofitable_position_cannot_receive_clock_exemption(value):
    state = support_state()
    for seconds in range(40, 181, 10):
        state = evaluate(exit_frame(seconds), state)[2]
    result = evaluate(exit_frame(190, value=value), state)
    assert result[0] == "SELL" and not result[3]["clock_exempted"]


@pytest.mark.parametrize("changes", [{"provider": "geckoterminal"}, {}])
def test_provider_change_or_observation_gap_clears_old_support(changes):
    state = support_state()
    seconds = 40 if changes else 100
    result = evaluate(exit_frame(seconds, **changes), state)
    assert result[0] == "HOLD" and result[3]["observation_reset"]
    assert not result[2].get("support")
    assert len(result[2]["structure_window"]) == 1


def test_exit_duplicate_out_of_order_future_and_opening_frame_wait():
    state = support_state()
    assert evaluate(exit_frame(30), state)[1] == "duplicate_frame"
    assert evaluate(exit_frame(29, frame_id="late"), state)[1] == "out_of_order_frame"
    assert evaluate(exit_frame(0))[1] == "noncausal_or_future_frame"
    assert evaluate(exit_frame(40), state, now=START+timedelta(seconds=39))[0] == "WAIT"
    assert evaluate(exit_frame(40), state, now=START+timedelta(seconds=56))[1] == "stale_frame"
    assert evaluate(exit_frame(31), state)[1] == "finalist_frame_too_close"
