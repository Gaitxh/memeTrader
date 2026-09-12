"""EXIT-LADDER150 contract tests.

The module exists to fix ONE measured defect: round 120-57 found that the deployed
`exit150_full15_v1` / `exit150_full25_v1` pair - the fleet's only same-frontier exit pair, and the
basis of the only near-readable paired forward result - is NOT a single-factor comparison, because
BOTH +25% arms also raise `trailing_activate_return` from the 0.30 base to 0.35. So the measured
-7.124U/pos within-cohort difference cannot be attributed to the take-profit level.

The load-bearing property is therefore: across this module's arms, EXACTLY ONE field differs, and
in particular `trailing_activate_return` is identical and equal to the 0.30 base. If that ever
stops being true the module no longer answers the question it was built for, so it is asserted
directly rather than assumed.
"""
import json

from memetrader import exit_ladder150 as el
from memetrader import exits150


ARMS = sorted(el.EXIT_ARMS)


def test_four_arms_with_distinct_levels():
    assert len(ARMS) == 4, "the curve needs four points to distinguish monotone from peaked"
    assert sorted(el.LEVELS.values()) == [0.10, 0.15, 0.20, 0.25]


def test_exactly_one_field_differs_across_the_arms():
    """The whole point: a single-factor dose-response."""
    fields = [set(el.OVERRIDES[arm]) for arm in ARMS]
    union = set().union(*fields)
    differing = {f for f in union if len({json.dumps(el.OVERRIDES[a].get(f), sort_keys=True)
                                          for a in ARMS}) > 1}
    assert differing == {"take_profit", "name", "canonical_id", "entry_family", "description"}, (
        f"more than the tier level differs across the arms: {sorted(differing)}"
    )
    # and the tier is the only difference INSIDE take_profit
    tiers = [el.OVERRIDES[a]["take_profit"] for a in ARMS]
    for t in tiers:
        assert len(t) == 1, "one tier per arm, so the level is the only dimension"
        assert t[0]["fraction_of_remaining"] == 1.0, "full capture in every arm"


def test_the_confounding_field_is_pinned():
    """trailing_activate_return is the field that broke full15 vs full25."""
    values = {el.OVERRIDES[a]["trailing_activate_return"] for a in ARMS}
    assert values == {0.30}, f"trailing activation must be pinned at the base 0.30, got {values}"
    # and it equals what the DEPLOYED full15 uses, so t15 is comparable to it
    assert exits150.OVERRIDES["exit150_full15_v1"]["trailing_activate_return"] == 0.30


def test_every_other_contract_field_matches_the_deployed_full_capture_arm():
    """Only the level may differ from the already-running full-capture contract."""
    reference = exits150.OVERRIDES["exit150_full15_v1"]
    compare = ("hard_stop_return", "trailing_activate_return", "trailing_drawdown",
               "max_hold_minutes", "notional_usd", "max_concurrent_positions", "trajectory_exit")
    for arm in ARMS:
        for field in compare:
            assert el.OVERRIDES[arm][field] == reference[field], (
                f"{arm}.{field} = {el.OVERRIDES[arm][field]!r} but the deployed full15 uses "
                f"{reference[field]!r}; the module would no longer be single-factor"
            )


def test_the_documented_confound_is_actually_present_in_the_deployed_pair():
    """The defect this module exists for must still be real, or the module is unnecessary.

    If someone later aligns the +25% arms' trailing activation, this test fails and the module's
    premise should be re-examined rather than left in place by inertia.
    """
    a = exits150.OVERRIDES["exit150_full15_v1"]
    b = exits150.OVERRIDES["exit150_full25_v1"]
    assert a["take_profit"] != b["take_profit"], "the levels must differ"
    assert a["trailing_activate_return"] != b["trailing_activate_return"], (
        "the round-120-57 confound has been removed; re-check whether EXIT-LADDER150 is still "
        "needed before deleting this assertion"
    )


def test_apply_touches_only_its_own_arms():
    others = [{"arm_id": "alpha149_vol_scaled_exit_v1", "name": "keep me"},
              {"arm_id": "exit150_full15_v1", "name": "keep me too"}]
    snapshot = [dict(p) for p in others]
    el.apply(others)
    assert others == snapshot, "another module's arms must be returned untouched"

    mine = [{"arm_id": ARMS[0]}]
    el.apply(mine)
    assert mine[0]["name"] == el.NAMES[ARMS[0]]
    assert mine[0]["take_profit"] == el.OVERRIDES[ARMS[0]]["take_profit"]
    assert mine[0]["exposure_contract"] == "exit_carrier_same_signal_as_first_firing_arm/v1"


def test_snapshot_states_the_purpose_and_the_guards():
    snap = el.snapshot()
    assert snap["affects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert set(snap["arms"]) == set(ARMS)
    assert "not to promote a level" in snap["purpose"]
    assert "0.30" in snap["pinned_field"]
    # the duplication of the deployed t15 must be declared, not hidden
    assert "frontier effect" in snap["dishonesty_guards"].lower()


def test_merged_specs_adds_only_this_modules_arms():
    base = {"alpha149_existing_v1": ("kind", "label", 15)}
    merged = el.merged_specs(base)
    assert "alpha149_existing_v1" in merged
    for arm in ARMS:
        assert arm in merged
        assert merged[arm][2] == 90


def test_levels_are_inside_the_measured_reachable_band():
    """The levels must sit where positions actually reach, or the curve cannot move."""
    assert min(el.LEVELS.values()) >= 0.10
    assert max(el.LEVELS.values()) <= 0.30
