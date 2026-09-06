from memetrader.revision_main_extensions import (
    BALANCED_HARVEST_FLOW_EXIT_ARMS,
    REAWAKENING_MATURE_ACCELERATION_ARMS,
    revise_main_extension,
)


def test_main_extension_arm_sets_are_complete_and_disjoint():
    assert len(REAWAKENING_MATURE_ACCELERATION_ARMS) == 32
    assert len(BALANCED_HARVEST_FLOW_EXIT_ARMS) == 8
    assert REAWAKENING_MATURE_ACCELERATION_ARMS.isdisjoint(
        BALANCED_HARVEST_FLOW_EXIT_ARMS
    )


def test_reawakening_revision_uses_main_mature_acceleration_and_old_exit():
    source = {
        "arm_id": "canonical-0186f1e75b238e63",
        "entry_family": "reawakening",
        "source_entry_family": "reawakening",
        "exit_family": "peak_guard",
        "entry_filter": {"min_age_seconds": 21_600},
        "hard_stop_return": -0.35,
        "take_profit": [{"return": 0.8, "fraction_of_remaining": 0.2}],
    }

    revised = revise_main_extension(source)

    assert revised is not source
    assert source["entry_filter"] == {"min_age_seconds": 21_600}
    assert revised["entry_family"] == "flow_burst"
    assert revised["source_entry_family"] == "reawakening"
    assert "entry_match_mode" not in revised
    assert revised["entry_filter"] == {
        "min_age_seconds": 3_600.0,
        "max_age_seconds_exclusive": 21_600.0,
        "min_m5_trades": 8,
        "min_m5_volume_usd": 500.0,
    }
    assert revised["exit_family"] == "peak_guard"
    assert revised["hard_stop_return"] == -0.35
    assert revised["take_profit"] == source["take_profit"]
    assert revised["revision_equivalence_group"] == (
        "main_mature_flow_acceleration_v2"
    )
    assert "strategy_revision" not in revised


def test_balanced_harvest_adds_flow_exit_without_changing_entry_or_tiers():
    source = {
        "arm_id": "canonical-2d3874b5b4dfe162",
        "entry_family": "broad_launch",
        "exit_family": "balanced_harvest",
        "hard_stop_return": -0.35,
        "trailing_activate_return": 0.60,
        "trailing_drawdown": 0.28,
        "max_hold_minutes": 240.0,
        "take_profit": [{"return": 0.8, "fraction_of_remaining": 0.2}],
    }

    revised = revise_main_extension(source)

    for key in (
        "entry_family",
        "exit_family",
        "hard_stop_return",
        "trailing_activate_return",
        "trailing_drawdown",
        "max_hold_minutes",
        "take_profit",
    ):
        assert revised[key] == source[key]
    assert revised["zero_activity_grace_minutes"] == 15.0
    assert revised["flow_grace_minutes"] == 15.0
    assert revised["minimum_buy_ratio"] == 0.45
    assert "entry_filter" not in revised
    assert revised["revision_equivalence_group"] == (
        "broad_balanced_harvest_flow_exit_v2"
    )


def test_unselected_policy_is_unchanged_copy():
    source = {"arm_id": "another-arm", "entry_filter": {"x": 1}}
    revised = revise_main_extension(source)

    assert revised == source
    assert revised is not source
    assert revised["entry_filter"] is not source["entry_filter"]
