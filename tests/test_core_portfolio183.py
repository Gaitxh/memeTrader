from memetrader.core_portfolio183 import (
    ARMS,
    FAST_ARM,
    PAIR_GROUP,
    PARENT_ARM,
    RUNNER_ARM,
    policies,
    snapshot,
)


def _parent():
    return {
        "arm_id": PARENT_ARM,
        "canonical_id": PARENT_ARM,
        "entry_family": "market_visible",
        "entry_match_mode": "exact_entry_family",
        "entry_filter": {
            "min_m5_trades": 20,
            "min_m5_volume_usd": 5000.0,
            "min_prior55_trades_exclusive": 5,
            "max_m5_trades_exclusive": 400,
            "min_volume_over_liquidity": 0.30,
        },
        "entry_paused": True,
        "forward_started_at": "old-frontier",
        "behavior_contract_hash": "old-hash",
        "hard_stop_return": -0.30,
        "take_profit": [{"fraction_of_remaining": 0.2, "return": 0.8}],
    }


def test_pair_keeps_one_entry_and_changes_only_exit_tempo():
    pair = {policy["arm_id"]: policy for policy in policies(_parent())}
    assert tuple(pair) == ARMS
    assert pair[FAST_ARM]["entry_filter"] == pair[RUNNER_ARM]["entry_filter"]
    assert pair[FAST_ARM]["entry_family"] == pair[RUNNER_ARM]["entry_family"]
    assert pair[FAST_ARM]["paired_entry_group"] == PAIR_GROUP
    assert pair[RUNNER_ARM]["paired_entry_group"] == PAIR_GROUP

    assert pair[FAST_ARM]["max_hold_minutes"] == 5.0
    assert pair[FAST_ARM]["hard_stop_return"] == -0.15
    assert "dynamic_principal_recovery" not in pair[FAST_ARM]

    assert pair[RUNNER_ARM]["max_hold_minutes"] == 30.0
    assert pair[RUNNER_ARM]["hard_stop_return"] == -0.50
    assert pair[RUNNER_ARM]["trajectory_exit"] == "alpha149_vol_scaled_stop"
    assert pair[RUNNER_ARM]["minimum_principal_recovery_multiple"] == 1.20


def test_pair_has_a_fresh_frontier_and_no_extra_data_requests():
    for policy in policies(_parent()):
        assert "entry_paused" not in policy
        assert "forward_started_at" not in policy
        assert "behavior_contract_hash" not in policy
        assert policy["source_arm_ids"] == [PARENT_ARM]
    assert snapshot()["extra_requests"] == 0
    assert snapshot()["no_historical_backfill"] is True
