from copy import deepcopy
from datetime import timedelta

from memetrader.models import iso, utcnow
from memetrader.store import Store
from memetrader.trajectory144 import ARMS, Engine, policies
from memetrader.trend_moonbag169 import (
    ARM, ARMS as MOONBAG_ARMS, CONTROL_ARM, PAIR_GROUP, RECOVERY_CONTRACT,
    alias_signals, snapshot,
)


def _row(at, i):
    return {
        "token_id": "bsc:0x1111111111111111111111111111111111111111",
        "pair_address": "0x2222222222222222222222222222222222222222",
        "chain": "bsc", "provider": "dexscreener",
        "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
        "price_usd": 1 + i * .04, "liquidity_usd": 10000,
        "volume_5m_usd": 100 + i * i * 20, "buys_5m": i * i,
        "sells_5m": 1, "pool_age_seconds": 30 + i * 10,
    }


def test_pair_changes_only_identity_and_principal_recovery():
    pair = {p["arm_id"]: p for p in policies({}) if p["arm_id"] in MOONBAG_ARMS}
    assert set(pair) == set(MOONBAG_ARMS)
    control, challenger = pair[CONTROL_ARM], pair[ARM]
    assert control["paired_entry_group"] == challenger["paired_entry_group"] == PAIR_GROUP
    assert control["paired_entry_size"] == challenger["paired_entry_size"] == 2
    assert "signal_origin_clock" not in control and "signal_origin_clock" not in challenger
    assert "dynamic_principal_recovery" not in control
    assert challenger["dynamic_principal_recovery"] == RECOVERY_CONTRACT
    ignored = {"arm_id", "canonical_id", "entry_family", "name", "description",
               "entry_filter", "dynamic_principal_recovery", "excess_return_vs_arm"}
    assert {k: v for k, v in control.items() if k not in ignored} == {
        k: v for k, v in challenger.items() if k not in ignored
    }
    assert control["entry_filter"]["direction"] == CONTROL_ARM
    assert challenger["entry_filter"]["direction"] == ARM


def test_engine_aliases_one_fresh_parent_signal_to_both_pair_members():
    at = utcnow()
    engine = Engine(at)
    for i in range(4):
        now = at + timedelta(seconds=i * 10)
        engine.accept(_row(now, i), now)
    row = _row(at, 0)
    signals = engine.signals_for(row["token_id"], row["pair_address"], at + timedelta(seconds=30))
    parent = signals[ARMS[3]]
    for arm in MOONBAG_ARMS:
        assert signals[arm]["observed_at"] == parent["observed_at"]
        assert signals[arm]["recorded_at"] == parent["recorded_at"]
        assert signals[arm]["selected"] == parent["selected"]
        assert signals[arm]["decision_key"] == parent["decision_key"] + "|" + arm


def test_alias_without_parent_is_a_noop_and_snapshot_is_forward_paper_only():
    original = {"unrelated": {"decision_key": "x"}}
    assert alias_signals(deepcopy(original)) == original
    state = snapshot()
    assert state["changed_dimension"] == "dynamic_principal_recovery_only"
    assert state["effects"] == "paper_only"
    assert state["extra_requests"] == 0
    assert state["no_historical_backfill"] is True


def test_existing_registration_path_appends_both_arms_at_one_fresh_frontier(tmp_path):
    store = Store(tmp_path / "moonbag.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        before = store.db.execute(
            "SELECT COALESCE(MAX(id),0) FROM token_snapshots"
        ).fetchone()[0]
        store.register_chain_meme_cohort_experiments()
        rows = store.db.execute(
            "SELECT arm_id,activated_at,activation_snapshot_id,policy_json "
            "FROM chain_meme_trader_policy_additions WHERE definition_version=? "
            "AND arm_id IN (?,?) ORDER BY arm_id",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, *MOONBAG_ARMS),
        ).fetchall()
        assert len(rows) == 2
        assert len({row["activated_at"] for row in rows}) == 1
        assert {row["activation_snapshot_id"] for row in rows} == {before}
        assert store.register_chain_meme_cohort_experiments() == 0
    finally:
        store.close()
