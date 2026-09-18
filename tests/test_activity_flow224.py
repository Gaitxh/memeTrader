from datetime import timedelta

import pytest

from memetrader.activity_flow224 import ARM, PARENT, alias_signal, policy
from memetrader.activity_tempo193 import PARENT as BASE_PARENT, Tracker, policy as base_policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenSnapshot, utcnow
from memetrader.store import Store
from test_activity_tempo193 import frame
from test_core import _seed_chain_market_position


def _parent():
    base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                if p["arm_id"] == BASE_PARENT)
    return base_policy(base)


def test_old_pool_exit_arm_shares_asof_entry_and_only_changes_own_exits():
    parent = _parent()
    candidate = policy(parent)
    assert candidate["source_arm_ids"] == [PARENT]
    assert candidate["max_hold_minutes"] == 5
    assert candidate["flow_grace_minutes"] == 1
    assert candidate["minimum_buy_ratio"] == .5
    assert candidate["emergency_liquidity_usd"] == 1600
    assert candidate["hard_stop_return"] == parent["hard_stop_return"]
    assert candidate["entry_filter"]["max_concurrent_positions"] == 8
    assert candidate["notional_usd"] == parent["notional_usd"] == 20
    assert candidate["no_historical_backfill"] and not candidate["live"]
    assert "flow_grace_minutes" not in parent
    at = utcnow()
    source = Tracker(at - timedelta(seconds=1)).accept(frame(at), at, floor=1000)
    signal = alias_signal(source)
    assert signal["selected"] == source["selected"]
    assert signal["observed_at"] == source["observed_at"]
    assert signal["decision_key"] != source["decision_key"]
    assert signal["decision_evidence"]["activity_flow224_source_decision_key"] == source["decision_key"]


def test_old_pool_exit_arm_registration_is_append_only(tmp_path):
    store = Store(tmp_path / "flow224.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == BASE_PARENT)
        store.append_chain_meme_trader_policy(base)
        assert store.register_chain_meme_activity_tempo193() == 1
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_activity_flow224() == 1
        assert store.register_chain_meme_activity_flow224() == 0
        row = store.db.execute(
            "SELECT activation_snapshot_id,policy_json FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM),
        ).fetchone()
        assert row[0] == frontier
        assert '"flow_grace_minutes": 1' in row[1]
    finally:
        store.close()


@pytest.mark.parametrize(
    "liquidity,buys,sells,stale,expected",
    [
        (5000, 2, 3, False, "FLOW_EXIT"),
        (1500, 5, 1, False, "LIQUIDITY_EXIT"),
        (5000, 2, 3, True, None),
    ],
)
def test_old_pool_exit_arm_uses_only_fresh_original_pool_mark(
    tmp_path, liquidity, buys, sells, stale, expected,
):
    store = Store(tmp_path / "flow224-exit.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == BASE_PARENT)
        store.append_chain_meme_trader_policy(base)
        assert store.register_chain_meme_activity_tempo193() == 1
        assert store.register_chain_meme_activity_flow224() == 1
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        registration = store._chain_meme_trader_registration(version)
        policies = store._chain_meme_trader_effective_definition(
            version, registration["definition_json"])["policies"]
        candidate = next(p for p in policies if p["arm_id"] == ARM)
        now = utcnow()
        token, cohort_id = _seed_chain_market_position(
            store, version=version, policy=candidate,
            opened_at=now - timedelta(minutes=2),
        )
        observed = now - timedelta(minutes=1) if stale else now
        store.upsert_chain_meme_trader_market_mark(
            token, TokenSnapshot(
                "solana", token.address, 1.1, liquidity, 100_000,
                1000, buys, sells, observed_at=observed,
                ingested_at=now, provider="dexscreener",
                raw={"pair": {"pairAddress": "pair-A"}},
            ), recorded_at=now,
        )
        created = store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=now,
        )
        mark = store.db.execute(
            "SELECT action,status FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND shadow_cohort_id=?",
            (version, cohort_id),
        ).fetchone()
        assert created == (1 if expected else 0)
        assert (mark["action"] if mark else None) == expected
        if mark:
            assert mark["status"] == "pending"
    finally:
        store.close()
