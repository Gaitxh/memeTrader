"""ACTIVITY-FLOOR150 entry activity floors, as new ENTRY arms.

The measured problem (round 120-18, 1,035 closed positions, actual -8,990.05U): the
write-off rate falls from 34.8% to 6.0% when the entry snapshot's own 5-minute activity
is >= 30 trades, and the 404 BSC positions below that floor carry a 78.6% write-off rate
at -15.39 U/pos - about 69.2% of the whole epoch loss in one filterable population.

These tests pin the three properties that make this a one-factor entry experiment rather
than a new strategy, plus the floor arithmetic and the missing-evidence rule.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from memetrader import activity_floor150
from memetrader import alpha149 as a149


@dataclass
class _Snap:
    buys_5m: int | None = 100
    sells_5m: int | None = 50
    volume_5m_usd: float | None = 25_000.0


def test_the_arms_are_entry_arms_and_so_live_in_SPECS():
    """Unlike EXIT150 these MUST be entry arms: they need their own entry signal so the
    shared acceptance loop can screen them."""
    assert len(activity_floor150.ARMS) == 2
    for arm, (kind, _name, hold) in activity_floor150.ARMS.items():
        assert arm in a149.SPECS, arm
        assert arm in a149.ALL_ARMS, arm
        assert arm not in a149.EXIT_ARMS, arm
        assert kind == activity_floor150.PARENT_KIND, arm
        assert hold == activity_floor150.HOLD_MINUTES, arm


def test_the_arms_differ_from_the_control_in_exactly_one_respect():
    """Same kind, same hold, same stop/trail/notional; the floor is the only difference.

    Asserted on the built policy (the real end state). The standalone builder and the
    registered body do not carry an identical key set, so this pins:
      - every exit-contract field that both carry is EQUAL;
      - on the shared keys, the only differences are identity/label fields;
      - the floor is declared on our arms and absent from the control.
    """
    policies = a149.policies({"stage": 1, "forward_enabled": True, "entry_filter": {}})
    by_arm = {p["arm_id"]: p for p in policies}
    control = by_arm[activity_floor150.PARENT_ARM]

    exit_fields = ("hard_stop_return", "trailing_activate_return", "trailing_drawdown",
                   "max_hold_minutes", "take_profit", "trajectory_exit", "notional_usd",
                   "feature_contract", "feature_hypothesis", "trajectory_engine",
                   "requires_distinct_trajectory_frame", "affects", "observer_only",
                   "decision_eligible", "signal_origin_clock", "stage", "forward_enabled")
    identity_fields = {"arm_id", "canonical_id", "name", "description", "entry_family",
                       "entry_filter", "excess_return_vs_arm"}

    for arm in activity_floor150.ARMS:
        policy = by_arm[arm]
        for field in exit_fields:
            assert policy[field] == control[field], (arm, field)
        # On the shared keys, nothing outside the identity/label set may differ.
        shared = set(policy) & set(control)
        differing = {k for k in shared if policy[k] != control[k]}
        assert differing <= identity_fields, (arm, sorted(differing - identity_fields))
        # The floor is declared on our arms and absent from the control.
        assert policy["entry_filter"]["activity_floor"] == activity_floor150.FLOORS[arm], arm
        assert "activity_floor" not in (control.get("entry_filter") or {})


def test_no_existing_arm_is_screened():
    """`reject_reason` must return None for every arm that is not ours - that is what makes
    this additive. Checked against the whole arm registry, not a sample."""
    snap = _Snap(buys_5m=0, sells_5m=0, volume_5m_usd=0.0)
    ours = set(activity_floor150.ARMS)
    for arm in a149.ALL_ARMS:
        if arm in ours:
            continue
        assert activity_floor150.reject_reason(arm, snap) is None, arm


@pytest.mark.parametrize("arm,floor", sorted(activity_floor150.FLOORS.items()))
def test_the_floor_admits_and_rejects_at_the_measured_level(arm, floor):
    if "min_trades" in floor:
        threshold = int(floor["min_trades"])
        assert activity_floor150.allows(arm, _Snap(buys_5m=threshold, sells_5m=0)) is True
        assert activity_floor150.allows(arm, _Snap(buys_5m=threshold - 1, sells_5m=0)) is False
        # trades is buys + sells, not buys alone
        assert activity_floor150.allows(
            arm, _Snap(buys_5m=threshold - 5, sells_5m=5)) is True
    if "min_volume_5m_usd" in floor:
        threshold = float(floor["min_volume_5m_usd"])
        assert activity_floor150.allows(arm, _Snap(volume_5m_usd=threshold)) is True
        assert activity_floor150.allows(arm, _Snap(volume_5m_usd=threshold - 1)) is False


def test_missing_evidence_never_admits():
    """A snapshot with no activity fields must fail the floor, not raise and not pass."""
    for arm in activity_floor150.ARMS:
        assert activity_floor150.allows(arm, _Snap(buys_5m=None, sells_5m=None,
                                                   volume_5m_usd=None)) is False
        assert activity_floor150.allows(arm, _Snap(buys_5m=0, sells_5m=0,
                                                   volume_5m_usd=0.0)) is False
    # The reject reason must be specific enough to audit from the evaluation log.
    assert activity_floor150.reject_reason(
        "activity_floor150_t30_v1", _Snap(buys_5m=1, sells_5m=1)) == "activity_floor_trades_not_met"
    assert activity_floor150.reject_reason(
        "activity_floor150_v5k_v1", _Snap(buys_5m=9_999, sells_5m=9_999,
                                          volume_5m_usd=1.0)) == "activity_floor_volume_not_met"


def test_apply_touches_only_its_own_arms():
    foreign = [{"arm_id": activity_floor150.PARENT_ARM, "name": "control"},
               {"arm_id": "some_other_arm", "hard_stop_return": -0.2}]
    before = json.dumps(foreign, sort_keys=True)
    assert activity_floor150.apply(foreign) == foreign
    assert json.dumps(foreign, sort_keys=True) == before

    mine = [{"arm_id": "activity_floor150_t30_v1"}]
    activity_floor150.apply(mine)
    assert mine[0]["entry_filter"]["activity_floor"] == {"min_trades": 30.0}
    assert mine[0]["excess_return_vs_arm"] == activity_floor150.PARENT_ARM
    assert mine[0]["affects"] == "paper_only"
    assert mine[0]["decision_eligible"] is True


def test_the_floor_is_declared_in_the_policy_body_for_auditability():
    """A reviewer reading the registered policy must be able to see the floor, not only
    discover it by reading the acceptance loop."""
    policies = a149.policies({"stage": 1, "forward_enabled": True, "entry_filter": {}})
    by_arm = {p["arm_id"]: p for p in policies}
    for arm, floor in activity_floor150.FLOORS.items():
        assert by_arm[arm]["entry_filter"]["activity_floor"] == floor, arm


def test_snapshot_is_json_serializable_and_declares_no_authority():
    snap = activity_floor150.snapshot()
    json.dumps(snap)
    assert snap["affects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert snap["parent_arm"] == activity_floor150.PARENT_ARM
    assert "in-sample" in snap["evidence"]
    assert "never admits" in snap["missing_evidence"]


@pytest.mark.parametrize("arm", sorted(activity_floor150.ARMS))
def test_each_arm_is_sized_and_bounded(arm):
    policy_override = activity_floor150.OVERRIDES[arm]
    assert policy_override["notional_usd"] == 2.0
    assert policy_override["max_hold_minutes"] == activity_floor150.HOLD_MINUTES
    assert policy_override["assessment_status"] == "INSUFFICIENT"
    assert policy_override["observer_only"] is False
    assert policy_override["take_profit"] == []
