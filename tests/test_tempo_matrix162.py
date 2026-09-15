from copy import deepcopy

from memetrader import alpha149, tempo_matrix162


def _parent(arm, hold, activate, drawdown):
    return {
        "arm_id": arm,
        "canonical_id": arm,
        "name": arm,
        "entry_family": arm,
        "entry_filter": {
            "direction": arm,
            "max_concurrent_positions": 2,
            "single_token_lifetime_entry": True,
        },
        "notional_usd": 2.0,
        "max_hold_minutes": hold,
        "hard_stop_return": -0.2,
        "trailing_activate_return": activate,
        "trailing_drawdown": drawdown,
        "behavior_contract_hash": "old",
        "forward_started_at": "old",
    }


def test_policy_changes_only_identity_and_hold_horizon():
    parent = _parent("alpha149_df_mature_price_up_fast_v1", 5, 0.3, 0.15)
    original = deepcopy(parent)
    arm = "alpha149_df_mature_price_up_hold90_v1"
    result = tempo_matrix162.policy(parent, arm)

    assert parent == original
    assert result["max_hold_minutes"] == 90
    assert result["entry_filter"]["direction"] == arm
    assert result["notional_usd"] == 2
    assert result["hard_stop_return"] == -0.2
    assert result["trailing_activate_return"] == 0.3
    assert result["trailing_drawdown"] == 0.15
    assert "behavior_contract_hash" not in result
    assert "forward_started_at" not in result


def test_install_reuses_each_parent_signal_kind_and_exit_shape():
    tempo_matrix162.install()
    for arm, spec in tempo_matrix162.EXPERIMENTS.items():
        parent = spec["parent"]
        assert alpha149.SPECS[arm][0] == alpha149.SPECS[parent][0]
        assert alpha149.SPECS[arm][2] == int(spec["max_hold_minutes"])
        assert alpha149.OVERRIDES[arm]["max_hold_minutes"] == spec["max_hold_minutes"]
        for field in ("hard_stop_return", "trailing_activate_return", "trailing_drawdown"):
            assert alpha149.OVERRIDES[arm].get(field) == alpha149.OVERRIDES[parent].get(field)


def test_each_fresh_pair_differs_only_in_hold_horizon():
    tempo_matrix162.install()
    for fast_arm, slow_arm in tempo_matrix162.PAIRS:
        assert alpha149.SPECS[fast_arm][0] == alpha149.SPECS[slow_arm][0]
        assert alpha149.SPECS[fast_arm][2] == 5
        assert alpha149.SPECS[slow_arm][2] == 90
        for field in ("hard_stop_return", "trailing_activate_return", "trailing_drawdown"):
            assert alpha149.OVERRIDES[fast_arm].get(field) == alpha149.OVERRIDES[slow_arm].get(field)


def test_snapshot_declares_forward_paper_boundary():
    snap = tempo_matrix162.snapshot()
    assert snap["changed_dimension"] == "max_hold_minutes_only"
    assert snap["effects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert snap["no_historical_backfill"] is True
