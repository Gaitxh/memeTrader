"""EXIT150 reachable staged ladders, as new exit-carrier arms.

The measured problem these arms exist for (live epoch, 350 positions): every position's own
peak economic return was p50 +22.7% / p90 +34.8% / max +55.0%, while the configured first
take-profit tier is +80%. `next_tp_index` and `principal_recovered` were 0 on every position,
so the ladder fired zero times and no profit was ever banked.

These tests pin the three properties that make it an exit-only experiment rather than a new
strategy, plus the reachability arithmetic that justifies the levels.
"""
from __future__ import annotations

import pytest

from memetrader import alpha149 as a149
from memetrader import exits150


def test_the_three_arms_exist_and_are_carrier_only():
    assert len(exits150.EXIT_ARMS) == 3
    for arm in exits150.EXIT_ARMS:
        assert arm in a149.EXIT_ARMS, arm
        # A carrier must NOT be an entry arm: the signal loop emits entries from SPECS only,
        # and the clone loop then hands each EXIT_ARMS entry the carrier's frozen signal.
        # Adding one to SPECS would give it its own entry gate - a different strategy.
        assert arm not in a149.SPECS, arm
        assert arm in a149.ALL_ARMS, arm


def test_no_existing_arm_was_modified():
    """The pre-existing carriers and entry arms keep their exact exit contracts.

    Asserted on the BUILT policy (the real end state), not on the OVERRIDES dict, because an
    arm may legitimately inherit a field from the shared builder default instead of declaring
    it - `alpha149_merged_multi_setup_v1` inherits `take_profit=[]` that way.
    """
    expected = {
        # arm: (hard stop, trailing activate, trailing drawdown)
        "alpha149_vol_scaled_exit_v1": (-0.9, 0.45, 0.25),
        "alpha149_merged_multi_setup_v1": (-0.45, 0.45, 0.25),
        "alpha149_confirmed_stop_steady_v2": (-0.2, 0.3, 0.15),
    }
    policies = a149.policies({"stage": 1, "forward_enabled": True, "entry_filter": {}})
    by_arm = {p["arm_id"]: p for p in policies}
    for arm, (stop, activate, drawdown) in expected.items():
        policy = by_arm[arm]
        assert policy["hard_stop_return"] == stop, arm
        assert policy["trailing_activate_return"] == activate, arm
        assert policy["trailing_drawdown"] == drawdown, arm
        assert policy["take_profit"] == [], arm
    # the pre-existing exit carrier keeps its own trajectory-exit kind
    assert a149.EXIT_ARMS["alpha149_vol_scaled_exit_v1"] == "alpha149_vol_scaled_stop"


def test_the_ladder_is_reachable_given_the_measured_distribution():
    """Every tier must sit inside the range the instrument actually produced.

    Measured on the live epoch: +10% reached by 65.4% of positions, +20% by 51.0%, +30% by
    32.0%, +45% by 1.2%, +60% by 0.0%, maximum +55.0%. The old first tier was +80%.
    """
    measured_max = 0.550
    for arm in exits150.EXIT_ARMS:
        tiers = exits150.OVERRIDES[arm]["take_profit"]
        assert tiers, arm
        assert tiers[0]["return"] <= 0.30, (arm, "first tier must be inside the reachable band")
        assert tiers[0]["fraction_of_remaining"] >= 0.50, (arm, "the first tier must bank real size")
        for tier in tiers:
            assert 0 < tier["return"] < 8.0
            assert 0 < tier["fraction_of_remaining"] <= 1.0
        # Tiers are applied in order and each is taken from the REMAINING quantity.
        returns = [t["return"] for t in tiers]
        assert returns == sorted(returns), arm
        assert sum(t["fraction_of_remaining"] for t in tiers) <= 1.5, arm
    # A moonbag must remain after the last tier so a runner is not fully sold.
    for arm in exits150.EXIT_ARMS:
        remaining = 1.0
        for tier in exits150.OVERRIDES[arm]["take_profit"]:
            remaining *= 1.0 - tier["fraction_of_remaining"]
        assert remaining > 0.0, arm


def test_the_stop_moved_outside_the_measured_noise():
    """-0.20 economic is a -13.3% price move; the pools' own 30s move is p90 9.49%/p95 18.65%."""
    sell_net = 0.96 / 1.04
    for arm in exits150.EXIT_ARMS:
        stop = exits150.OVERRIDES[arm]["hard_stop_return"]
        assert stop <= -0.35, (arm, "must be wider than the noise")
        implied_price_move = (1.0 + stop) / sell_net - 1.0
        assert implied_price_move <= -0.28, (arm, implied_price_move)
        assert stop > -0.90, (arm, "still a stop, not an unbounded hold")


def test_the_three_arms_differ_in_exactly_one_respect_each():
    bank15 = exits150.OVERRIDES["exit150_bank15_v1"]
    bank25 = exits150.OVERRIDES["exit150_bank25_v1"]
    widestop = exits150.OVERRIDES["exit150_widestop_v1"]
    # bank15 vs bank25: the first-tier level is the only difference in the ladder.
    assert bank15["take_profit"] != bank25["take_profit"]
    assert bank15["hard_stop_return"] == bank25["hard_stop_return"]
    assert bank15["trailing_drawdown"] == bank25["trailing_drawdown"]
    # bank15 vs widestop: the stop width is the only difference in risk.
    assert bank15["take_profit"] == widestop["take_profit"]
    assert bank15["hard_stop_return"] != widestop["hard_stop_return"]


def test_apply_touches_only_its_own_arms():
    foreign = [{"arm_id": "alpha149_merged_multi_setup_v1", "take_profit": []},
               {"arm_id": "some_other_arm", "hard_stop_return": -0.2}]
    snapshot = [dict(p) for p in foreign]
    assert exits150.apply(foreign) == snapshot

    mine = [{"arm_id": "exit150_bank15_v1"}]
    exits150.apply(mine)
    assert mine[0]["take_profit"] == exits150.OVERRIDES["exit150_bank15_v1"]["take_profit"]
    assert mine[0]["affects"] == "paper_only"
    assert mine[0]["decision_eligible"] is True
    assert "feature_contract" not in mine[0], (
        "the registered carriers use alpha149/v1; relabelling it would risk routing the arm "
        "away from the features it reads"
    )


def test_the_standalone_policy_builder_produces_the_carrier_shape():
    """`alpha149.policies` must stamp the arms exactly like the registered exit carriers."""
    policies = a149.policies({"stage": 1, "forward_enabled": True, "entry_filter": {}})
    by_arm = {p["arm_id"]: p for p in policies}
    for arm in exits150.EXIT_ARMS:
        policy = by_arm[arm]
        # `alpha149_vol_scaled_exit_v1` (the live template) carries this same hypothesis label.
        assert policy["feature_hypothesis"] == "uncrowded_first_frame", arm
        assert policy["trajectory_engine"] == "alpha149", arm
        assert policy["requires_distinct_trajectory_frame"] is True, arm
        assert policy["trajectory_exit"] is None, arm
        assert policy["take_profit"] == exits150.OVERRIDES[arm]["take_profit"], arm
        assert policy["hard_stop_return"] == exits150.OVERRIDES[arm]["hard_stop_return"], arm
        assert policy["max_hold_minutes"] == exits150.OVERRIDES[arm]["max_hold_minutes"], arm
        assert policy["name"] == exits150.KINDS[exits150.EXIT_ARMS[arm]], arm


def test_snapshot_is_json_serializable_and_declares_no_authority():
    import json

    snap = exits150.snapshot()
    json.dumps(snap)
    assert snap["affects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert "in-sample" in snap["evidence"]


@pytest.mark.parametrize("arm", sorted(exits150.EXIT_ARMS))
def test_each_arm_is_sized_small_and_bounded(arm):
    override = exits150.OVERRIDES[arm]
    assert override["notional_usd"] == 1.0
    assert override["max_concurrent_positions"] == 4
    assert override["assessment_status"] == "INSUFFICIENT"
    assert override["observer_only"] is False
    assert override["max_hold_minutes"] in {90, 180}
