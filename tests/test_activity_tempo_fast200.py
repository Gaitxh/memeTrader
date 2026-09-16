from datetime import timedelta

from memetrader.activity_tempo193 import PARENT as BASE_PARENT, Tracker, policy as base_policy
from memetrader.activity_tempo_fast200 import ARM, PARENT, alias_signal, policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import utcnow
from memetrader.store import Store
from test_activity_tempo193 import frame


def test_fast_arm_shares_entry_and_changes_only_hold():
    base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                if p["arm_id"] == BASE_PARENT)
    parent = base_policy(base)
    candidate = policy(parent)
    assert candidate["notional_usd"] == parent["notional_usd"] == 20
    assert candidate["hard_stop_return"] == parent["hard_stop_return"]
    assert candidate["max_hold_minutes"] == 5
    assert parent["max_hold_minutes"] == 30
    assert candidate["source_arm_ids"] == [PARENT]
    assert candidate["no_historical_backfill"] and not candidate["live"]
    at = utcnow()
    source = Tracker(at - timedelta(seconds=1)).accept(frame(at), at, floor=1000)
    signal = alias_signal(source)
    assert signal["selected"] == source["selected"]
    assert signal["observed_at"] == source["observed_at"]
    assert signal["decision_key"] != source["decision_key"]


def test_fast_arm_registration_is_append_only(tmp_path):
    store = Store(tmp_path / "tempo200.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == BASE_PARENT)
        store.append_chain_meme_trader_policy(base)
        assert store.register_chain_meme_activity_tempo193() == 1
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_activity_tempo_fast200() == 1
        assert store.register_chain_meme_activity_tempo_fast200() == 0
        row = store.db.execute(
            "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM),
        ).fetchone()
        assert row[0] == frontier
    finally:
        store.close()
