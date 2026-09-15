from copy import deepcopy

from memetrader import alpha149, goldendog_recovery164
from memetrader.age_rate_revisions import next_frame_minimum_principal_recovery_raw
from memetrader.store import Store


def _parent():
    return {
        "arm_id": goldendog_recovery164.PARENT_ARM,
        "canonical_id": goldendog_recovery164.PARENT_ARM,
        "entry_family": goldendog_recovery164.PARENT_ARM,
        "entry_filter": {"direction": goldendog_recovery164.PARENT_ARM},
        "hard_stop_return": -0.55,
        "hard_stop_grace_seconds": 300,
        "hard_stop_confirm_marks": 3,
        "trailing_activate_return": 0.60,
        "trailing_drawdown": 0.30,
        "max_hold_minutes": 240,
        "behavior_contract_hash": "old",
        "forward_started_at": "old",
    }


def _position():
    return {
        "stake_usd": 20.0,
        "realized_proceeds_usd": 0.0,
        "amount_raw": "1000",
        "remaining_quantity_tokens": 1.0,
    }


def test_policy_changes_only_identity_and_principal_recovery_contract():
    parent = _parent()
    original = deepcopy(parent)
    policy = goldendog_recovery164.policy(parent)

    assert parent == original
    assert policy["entry_filter"]["direction"] == goldendog_recovery164.ARM
    assert policy["minimum_principal_recovery_multiple"] == 1.20
    assert policy["dynamic_principal_recovery"] == \
        "minimum_net_debit_after_economic_floor/v4"
    for field in (
        "hard_stop_return", "hard_stop_grace_seconds", "hard_stop_confirm_marks",
        "trailing_activate_return", "trailing_drawdown", "max_hold_minutes",
    ):
        assert policy[field] == parent[field]
    assert "behavior_contract_hash" not in policy
    assert "forward_started_at" not in policy


def test_install_reuses_the_exact_parent_signal_and_exit_shape():
    goldendog_recovery164.install()
    arm = goldendog_recovery164.ARM
    parent = goldendog_recovery164.PARENT_ARM
    assert alpha149.SPECS[arm][0] == alpha149.SPECS[parent][0]
    for field in (
        "hard_stop_return", "hard_stop_grace_seconds", "hard_stop_confirm_marks",
        "trailing_activate_return", "trailing_drawdown",
    ):
        assert alpha149.OVERRIDES[arm][field] == alpha149.OVERRIDES[parent][field]


def test_recovery_waits_for_1_20x_net_value_then_sells_the_minimum_amount():
    definition = {"sell_slippage_bps": 400, "additional_fee_usd_each_fill": 0.0}
    policy = {
        "dynamic_principal_recovery": "minimum_net_debit_after_economic_floor/v4",
        "minimum_principal_recovery_multiple": 1.20,
    }
    assert next_frame_minimum_principal_recovery_raw(
        _position(), {"market_price_usd": 24.99}, definition, policy=policy,
    ) is None

    amount = next_frame_minimum_principal_recovery_raw(
        _position(), {"market_price_usd": 25.0}, definition, policy=policy,
    )
    assert amount == 834
    assert amount < 1000


def test_snapshot_pins_the_forward_paper_boundary():
    snap = goldendog_recovery164.snapshot()
    assert snap["changed_dimension"] == "fresh_mark_minimum_principal_recovery_only"
    assert snap["effects"] == "paper_only"
    assert snap["extra_requests"] == 0
    assert snap["no_historical_backfill"] is True


def test_registration_appends_once_at_its_own_frontier(tmp_path):
    store = Store(tmp_path / "recovery.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.append_chain_meme_trader_policy(_parent())
        assert store.register_chain_meme_goldendog_recovery164() == 1
        assert store.register_chain_meme_goldendog_recovery164() == 0
        row = store.db.execute(
            "SELECT policy_json,activated_at FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, goldendog_recovery164.ARM),
        ).fetchone()
        assert row is not None and row["activated_at"]
        policy = store._json_object(row["policy_json"])
        assert policy["minimum_principal_recovery_multiple"] == 1.20
    finally:
        store.close()
