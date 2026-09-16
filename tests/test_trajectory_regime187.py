from copy import deepcopy

from memetrader.store import Store
from memetrader.trajectory144 import ARMS as TRAJECTORY_ARMS, policies as trajectory_policies
from memetrader.trajectory_regime187 import (
    ARMED_RUNNER_ARM, ARMED_CONTROL, ARMS, FAST_PARENT, NONSOL_FAST_ARM,
    RUNNER_PARENT, SOLANA_RUNNER_ARM, alias_signals, policies, snapshot,
)


def _signal(arm, chain):
    return {
        "decision_key": f"decision:{arm}:{chain}",
        "decision_evidence": {
            "mode": arm,
            "feature_vector": {"chain": chain},
        },
        "selected": {"token_id": f"{chain}:token", "pair_address": "pool"},
    }


def test_chain_routing_and_armed_runner_alias_exact_parent_signals():
    sol = alias_signals({
        FAST_PARENT: _signal(FAST_PARENT, "solana"),
        RUNNER_PARENT: _signal(RUNNER_PARENT, "solana"),
    })
    assert SOLANA_RUNNER_ARM in sol
    assert NONSOL_FAST_ARM not in sol
    assert ARMED_RUNNER_ARM in sol
    assert sol[SOLANA_RUNNER_ARM]["selected"] == sol[RUNNER_PARENT]["selected"]

    bsc = alias_signals({
        FAST_PARENT: _signal(FAST_PARENT, "bsc"),
        RUNNER_PARENT: _signal(RUNNER_PARENT, "bsc"),
    })
    assert SOLANA_RUNNER_ARM not in bsc
    assert NONSOL_FAST_ARM in bsc
    assert ARMED_RUNNER_ARM in bsc
    assert bsc[NONSOL_FAST_ARM]["decision_key"].endswith(NONSOL_FAST_ARM)


def test_policies_are_additive_paper_only_and_change_only_declared_exit_field():
    parents = {policy["arm_id"]: policy for policy in trajectory_policies({})}
    all_policies = policies(parents[FAST_PARENT], parents[RUNNER_PARENT])
    by_arm = {policy["arm_id"]: policy for policy in all_policies}
    assert set(ARMS) <= set(by_arm)
    armed = by_arm[ARMED_RUNNER_ARM]
    runner = parents[TRAJECTORY_ARMS[3]]
    assert armed["trailing_activate_return"] == 0.0
    assert "after break-even" in armed["name"]
    assert armed["trailing_drawdown"] == runner["trailing_drawdown"] == 0.15
    assert armed["excess_return_vs_arm"] == ARMED_CONTROL
    assert all(by_arm[arm]["affects"] == "paper_only" for arm in ARMS)
    assert all(by_arm[arm]["no_historical_backfill"] is True for arm in ARMS)
    assert snapshot()["extra_requests"] == 0

    ignored = {
        "arm_id", "canonical_id", "entry_family", "name", "description",
        "entry_filter", "entry_alias_of", "source_arm_ids", "assessment_status",
        "decision_eligible", "observer_only", "affects", "live",
        "no_historical_backfill", "paired_opportunity_group",
        "excess_return_vs_arm", "trailing_activate_return",
        "signal_origin_clock",
    }
    assert {k: deepcopy(v) for k, v in armed.items() if k not in ignored} == {
        k: deepcopy(v) for k, v in runner.items() if k not in ignored
    }


def test_zero_trailing_activation_is_not_treated_as_disabled():
    assert Store._chain_meme_trailing_activation({"trailing_activate_return": 0.0}) == 0.0
    assert Store._chain_meme_trailing_activation({}) == 99.0


def test_existing_cohort_registration_appends_new_arms_at_one_frontier(tmp_path):
    store = Store(tmp_path / "trajectory187.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        store.register_chain_meme_cohort_experiments()
        assert store.register_chain_meme_trajectory_regime187() == 3
        rows = store.db.execute(
            "SELECT arm_id,activated_at,activation_snapshot_id FROM "
            "chain_meme_trader_policy_additions WHERE definition_version=? AND "
            "arm_id IN (?,?,?) ORDER BY arm_id",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, *ARMS),
        ).fetchall()
        assert len(rows) == 3
        assert len({row["activated_at"] for row in rows}) == 1
        assert {row["activation_snapshot_id"] for row in rows} == {frontier}
        assert store.register_chain_meme_trajectory_regime187() == 0
    finally:
        store.close()
