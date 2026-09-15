from copy import deepcopy

from memetrader import alpha149, tempo_matrix162
from memetrader.store import Store


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


def test_activity_pair_declares_one_shared_entry_floor_and_strict_pairing():
    parent = _parent("alpha149_mature_two_step_slow_v1", 90, 0.3, 0.15)
    parent["signal_origin_clock"] = "activation_at"
    policies = [tempo_matrix162.policy(parent, arm) for arm in tempo_matrix162.ACTIVITY_PAIR]

    assert {p["max_hold_minutes"] for p in policies} == {5.0, 90.0}
    assert {p["paired_entry_group"] for p in policies} == {
        tempo_matrix162.ACTIVITY_PAIR_GROUP
    }
    assert {p["paired_entry_size"] for p in policies} == {2}
    assert {p["entry_filter"]["activity_floor"]["min_trades"] for p in policies} == {30.0}
    assert all("signal_origin_clock" not in p for p in policies)
    assert policies[0]["excess_return_vs_arm"] == tempo_matrix162.ACTIVITY_PAIR[1]
    assert policies[1]["excess_return_vs_arm"] == tempo_matrix162.ACTIVITY_PAIR[0]


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


def test_registration_appends_activity_pair_at_one_fresh_frontier(tmp_path):
    store = Store(tmp_path / "tempo.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        before = store.db.execute(
            "SELECT COALESCE(MAX(id),0) FROM token_snapshots"
        ).fetchone()[0]
        parent = next(
            policy for policy in alpha149.policies({})
            if policy["arm_id"] == "alpha149_mature_two_step_slow_v1"
        )
        store.append_chain_meme_trader_policy(parent)
        store.register_chain_meme_tempo_matrix162()
        rows = store.db.execute(
            "SELECT arm_id,activated_at,activation_snapshot_id,"
            "activation_evaluation_id,policy_json "
            "FROM chain_meme_trader_policy_additions WHERE definition_version=? "
            "AND arm_id IN (?,?) ORDER BY arm_id",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, *tempo_matrix162.ACTIVITY_PAIR),
        ).fetchall()
        assert len(rows) == 2
        assert len({
            (row["activated_at"], row["activation_snapshot_id"], row["activation_evaluation_id"])
            for row in rows
        }) == 1
        assert {row["activation_snapshot_id"] for row in rows} == {before}
        assert all("signal_origin_clock" not in row["policy_json"] for row in rows)
        assert store.register_chain_meme_tempo_matrix162() == 0
    finally:
        store.close()
