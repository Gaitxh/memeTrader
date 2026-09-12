"""RUNUP-FLOOR150 entry run-up caps, as new ENTRY arms.

The measured problem (round 120-20, 1,712 positions, actual -11,509.67U): the write-off
rate jumps from 0.6% at a 15% run-up cap (entry price vs the earliest price observed in
the 20 minutes before the decision) to 6.0% at 20% and 24.8% uncapped, and the separation
is token-clustered significant BOTH ways (write-off +0.322pp CI [+0.082,+0.565];
PnL -4.851 U/pos CI [-9.491,-0.055]).

These tests pin the one-factor discipline, the floor arithmetic, and the
missing-evidence rule.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from memetrader import alpha149 as a149
from memetrader import runup_floor150


@dataclass
class _Snap:
    price_usd: float | None = 110.0
    buys_5m: int | None = 100
    sells_5m: int | None = 50


def _hist(price: float | None):
    return [{"price": price, "id": 1}]


def test_the_arms_are_entry_arms_and_live_in_SPECS():
    assert len(runup_floor150.ARMS) == 2
    for arm, (kind, _name, hold) in runup_floor150.ARMS.items():
        assert arm in a149.SPECS, arm
        assert arm in a149.ALL_ARMS, arm
        assert arm not in a149.EXIT_ARMS, arm
        assert kind == runup_floor150.PARENT_KIND, arm
        assert hold == runup_floor150.HOLD_MINUTES, arm


def test_the_arms_differ_from_the_control_in_exactly_one_respect():
    """Asserted on the BUILT policy, so a future edit that quietly changes a stop or hold fails."""
    policies = a149.policies({"stage": 1, "forward_enabled": True, "entry_filter": {}})
    by_arm = {p["arm_id"]: p for p in policies}
    control = by_arm[runup_floor150.PARENT_ARM]
    exit_fields = ("hard_stop_return", "trailing_activate_return", "trailing_drawdown",
                   "max_hold_minutes", "take_profit", "trajectory_exit", "notional_usd",
                   "feature_contract", "feature_hypothesis", "trajectory_engine",
                   "requires_distinct_trajectory_frame", "affects", "observer_only",
                   "decision_eligible", "signal_origin_clock", "stage", "forward_enabled")
    identity_fields = {"arm_id", "canonical_id", "name", "description", "entry_family",
                       "entry_filter", "excess_return_vs_arm"}
    for arm in runup_floor150.ARMS:
        policy = by_arm[arm]
        for field in exit_fields:
            assert policy[field] == control[field], (arm, field)
        differing = {k for k in (set(policy) & set(control)) if policy[k] != control[k]}
        assert differing <= identity_fields, (arm, sorted(differing - identity_fields))
        # The floor is declared on the arm and absent from the control.
        assert policy["entry_filter"]["entry_floor"]["max_runup_pct"] == 15.0, arm
        assert "entry_floor" not in (control.get("entry_filter") or {})


def test_the_conjunction_arm_carries_both_floors():
    r15 = runup_floor150.OVERRIDES["runup_floor150_r15_v1"]["entry_filter"]
    both = runup_floor150.OVERRIDES["runup_floor150_r15a30_v1"]["entry_filter"]
    assert "activity_floor" not in r15, "the one-factor arm must differ from the control ONLY by run-up"
    assert both["activity_floor"] == {"min_trades": 30.0}
    assert both["entry_floor"] == r15["entry_floor"]


def test_no_existing_arm_is_screened():
    """What makes this additive: every other arm must be allowed, whatever the inputs."""
    snap = _Snap(price_usd=10_000.0)
    ours = set(runup_floor150.ARMS)
    for arm in a149.ALL_ARMS:
        if arm in ours:
            continue
        assert runup_floor150.reject_reason(arm, snap, _hist(0.001)) is None, arm
        assert runup_floor150.reject_reason(arm, snap, None) is None, arm


def test_the_runup_cap_admits_and_rejects_at_the_measured_level():
    arm = "runup_floor150_r15_v1"
    # 100 -> 115 is exactly +15%: admitted. 100 -> 115.01 is over: rejected.
    assert runup_floor150.allows(arm, _Snap(price_usd=115.0), _hist(100.0)) is True
    assert runup_floor150.allows(arm, _Snap(price_usd=115.01), _hist(100.0)) is False
    assert runup_floor150.reject_reason(arm, _Snap(price_usd=200.0), _hist(100.0)) == "runup_floor_exceeded"
    # A pool that has not moved is admitted.
    assert runup_floor150.allows(arm, _Snap(price_usd=100.0), _hist(100.0)) is True


def test_the_window_uses_the_EARLIEST_frame():
    """`history` is ascending, so history[0] is the earliest of the 20-minute window."""
    arm = "runup_floor150_r15_v1"
    hist = [{"price": 100.0}, {"price": 130.0}, {"price": 200.0}]
    assert runup_floor150.runup_pct(_Snap(price_usd=200.0), hist) == pytest.approx(100.0)
    assert runup_floor150.allows(arm, _Snap(price_usd=200.0), hist) is False


def test_missing_evidence_never_admits():
    for arm in runup_floor150.ARMS:
        assert runup_floor150.allows(arm, _Snap(price_usd=110.0), None) is False
        assert runup_floor150.allows(arm, _Snap(price_usd=110.0), []) is False
        assert runup_floor150.allows(arm, _Snap(price_usd=110.0), _hist(None)) is False
        assert runup_floor150.allows(arm, _Snap(price_usd=110.0), _hist(0.0)) is False
        assert runup_floor150.allows(arm, _Snap(price_usd=None), _hist(100.0)) is False
    assert runup_floor150.reject_reason(
        "runup_floor150_r15_v1", _Snap(), None) == "runup_floor_window_unknown"


def test_the_conjunction_arm_also_enforces_the_activity_floor():
    arm = "runup_floor150_r15a30_v1"
    # run-up OK, activity too low -> rejected by the activity floor.
    assert runup_floor150.reject_reason(
        arm, _Snap(price_usd=105.0, buys_5m=5, sells_5m=5), _hist(100.0)) == "activity_floor_trades_not_met"
    # both OK -> admitted
    assert runup_floor150.allows(
        arm, _Snap(price_usd=105.0, buys_5m=30, sells_5m=0), _hist(100.0)) is True


def test_apply_touches_only_its_own_arms():
    foreign = [{"arm_id": runup_floor150.PARENT_ARM, "name": "control"},
               {"arm_id": "some_other_arm"}]
    before = json.dumps(foreign, sort_keys=True)
    assert runup_floor150.apply(foreign) == foreign
    assert json.dumps(foreign, sort_keys=True) == before
    mine = [{"arm_id": "runup_floor150_r15_v1"}]
    runup_floor150.apply(mine)
    assert mine[0]["excess_return_vs_arm"] == runup_floor150.PARENT_ARM
    assert mine[0]["affects"] == "paper_only"


def test_snapshot_is_json_serializable_and_declares_no_authority():
    snap = runup_floor150.snapshot()
    json.dumps(snap)
    assert snap["affects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert "in-sample" in snap["evidence"]
    assert "never admits" in snap["missing_evidence"]
    assert "20" in snap["window"]


@pytest.mark.parametrize("arm", sorted(runup_floor150.ARMS))
def test_each_arm_is_sized_and_bounded(arm):
    o = runup_floor150.OVERRIDES[arm]
    assert o["notional_usd"] == 2.0
    assert o["max_hold_minutes"] == runup_floor150.HOLD_MINUTES
    assert o["assessment_status"] == "INSUFFICIENT"
    assert o["observer_only"] is False
    assert o["take_profit"] == []
