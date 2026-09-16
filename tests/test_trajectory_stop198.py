from datetime import timedelta

from memetrader.models import TokenSnapshot, utcnow
from memetrader.store import Store
from memetrader.trajectory_stop198 import ARM, PARENT, alias_signals, policy
from test_core import _seed_chain_market_position


def _mark(store, token, at, price):
    store.upsert_chain_meme_trader_market_mark(token, TokenSnapshot(
        "solana", token.address, price, 50_000, 100_000, 1000, 6, 2,
        observed_at=at, ingested_at=at, provider="dexscreener",
        raw={"pair": {"pairAddress": "pair-A"}},
    ), recorded_at=at)


def test_policy_and_alias_preserve_parent_entry():
    parent = {"arm_id": PARENT, "entry_filter": {"direction": PARENT},
              "hard_stop_return": -.20, "notional_usd": 2.0}
    candidate = policy(parent)
    assert candidate["hard_stop_return"] == -.20
    assert candidate["notional_usd"] == 2.0
    assert candidate["fresh_stop_confirm_marks"] == 2
    assert candidate["fresh_stop_catastrophe_return"] == -.35
    assert candidate["no_historical_backfill"] and candidate["live"] is False
    source = {"decision_key": "source", "selected": {"token_id": "solana:t", "pair_address": "p"},
              "decision_evidence": {"mode": PARENT}}
    result = alias_signals({PARENT: source})
    assert result[ARM]["decision_key"] == "source|" + ARM
    assert result[ARM]["selected"] == source["selected"]
    assert source["decision_evidence"]["mode"] == PARENT


def test_fresh_stop_confirms_distinct_marks_and_survives_restart(tmp_path):
    path = tmp_path / "stop198.sqlite3"
    store = Store(path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_trajectory_stop198() == 1
        assert store.register_chain_meme_trajectory_stop198() == 0
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        addition = store.db.execute(
            "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?", (version, ARM),
        ).fetchone()
        assert addition[0] == frontier
        registration = store._chain_meme_trader_registration(version)
        definition = store._chain_meme_trader_effective_definition(version, registration["definition_json"])
        candidate = next(item for item in definition["policies"] if item["arm_id"] == ARM)
        opened = utcnow() - timedelta(minutes=2)
        token, cohort = _seed_chain_market_position(store, version=version, policy=candidate, opened_at=opened)
        first = opened + timedelta(seconds=60)
        _mark(store, token, first, .83)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=first)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=first + timedelta(seconds=1))
        assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_marks WHERE "
            "definition_version=? AND arm_id=? AND action='HARD_STOP'", (version, ARM)).fetchone()[0] == 0
    finally:
        store.close()

    store = Store(path, initial_cash_usd=1000)
    try:
        second = first + timedelta(seconds=5)
        _mark(store, token, second, .82)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=second)
        mark = store.db.execute("SELECT status,action FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1", (version, ARM)).fetchone()
        assert tuple(mark) == ("pending", "HARD_STOP")
        assert store.db.execute("SELECT status FROM chain_meme_trader_positions WHERE "
            "definition_version=? AND arm_id=? AND shadow_cohort_id=?", (version, ARM, cohort)).fetchone()[0] == "open"
        post = second + timedelta(seconds=5)
        _mark(store, token, post, .80)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=post)
        assert store.db.execute("SELECT status FROM chain_meme_trader_positions WHERE "
            "definition_version=? AND arm_id=? AND shadow_cohort_id=?", (version, ARM, cohort)).fetchone()[0] != "open"
    finally:
        store.close()


def test_fresh_stop_recovery_and_catastrophe(tmp_path):
    store = Store(tmp_path / "stop198-other.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        store.register_chain_meme_trajectory_stop198()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        definition = store._chain_meme_trader_effective_definition(
            version, store._chain_meme_trader_registration(version)["definition_json"])
        candidate = next(item for item in definition["policies"] if item["arm_id"] == ARM)
        opened = utcnow() - timedelta(minutes=2)
        token, cohort = _seed_chain_market_position(store, version=version, policy=candidate, opened_at=opened)
        for seconds, price in ((60, .83), (65, .95), (70, .83)):
            at = opened + timedelta(seconds=seconds)
            _mark(store, token, at, price)
            store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=at)
        assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_marks WHERE "
            "definition_version=? AND arm_id=? AND action='HARD_STOP'", (version, ARM)).fetchone()[0] == 0
        catastrophe = opened + timedelta(seconds=75)
        _mark(store, token, catastrophe, .70)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=catastrophe)
        assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_marks WHERE "
            "definition_version=? AND arm_id=? AND action='HARD_STOP'", (version, ARM)).fetchone()[0] == 1
    finally:
        store.close()
