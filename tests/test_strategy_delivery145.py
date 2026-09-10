from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from memetrader.models import TokenCandidate, iso, parse_time, utcnow
from memetrader.preentry_safety import PreentrySafety
from memetrader.recipe145 import Manager, SEEDS, recipe
from memetrader.store import Store
from memetrader.trajectory144 import ARMS, Engine
from test_l0_store import _snapshot
from test_trajectory144 import row


def _setup(tmp_path, monkeypatch):
    clock = [utcnow()]
    for module in ("store", "models", "preentry_safety"):
        monkeypatch.setattr("memetrader." + module + ".utcnow", lambda: clock[0])
    store = Store(tmp_path / "delivery145.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    manager = Manager(store)
    # register_one is deliberately one bounded candidate at a time.
    manager.flush(clock[0])
    clock[0] += timedelta(seconds=1)
    manager.flush(clock[0])
    gate = PreentrySafety(store, SimpleNamespace(config={}))
    store._preentry_safety = gate
    return store, manager, gate, clock


def _source_signal(source_arm, engine, token, pool, clock, start):
    prices = ([1, 1.1, 1.3, 1.1, 1.15, 1.25, 1.31]
              if source_arm == ARMS[2] else [1, 1.01, 1.05, 1.14, 1.25])
    snapshot = None
    for index, price in enumerate(prices, 1):
        clock[0] += timedelta(seconds=10)
        item = row(clock[0], index, token=token.token_id, pool=pool, price=price,
                   buys=index * index, volume=100 + index * index * 20)
        engine.accept(item, clock[0])
        snapshot = _snapshot(token, pool, clock[0], price=price)
        snapshot.volume_5m_usd = item["volume_5m_usd"]
        snapshot.buys_5m = item["buys_5m"]
        snapshot.sells_5m = item["sells_5m"]
    return engine.signals_for(token.token_id, pool, clock[0])[source_arm], snapshot


@pytest.mark.parametrize("source_arm", (ARMS[1], ARMS[2]))
def test_authorized_seed_uses_common_safety_later_buy_and_same_fill_exit(tmp_path, monkeypatch, source_arm):
    store, manager, gate, clock = _setup(tmp_path, monkeypatch)
    seed = SEEDS[source_arm]
    policy = manager.policies[seed]
    proposal = next(item for item in manager.state["proposals"].values() if item["arm_id"] == seed)
    assert policy["notional_usd"] == 2.0
    assert policy["entry_filter"]["max_concurrent_positions"] == 2
    assert policy["signal_origin_clock"] == "recipe_activation_at"
    assert policy["trend_base_hold_minutes"] == 30
    assert policy["trend_max_hold_minutes"] == 120
    assert policy["hard_stop_return"] == pytest.approx(-0.2)

    token = TokenCandidate("bsc", "0x" + ("1" if source_arm == ARMS[1] else "3") * 40, "145 fixture", "T145")
    pool = "0x" + ("2" if source_arm == ARMS[1] else "4") * 40
    store.upsert_token(token)
    clock[0] += timedelta(seconds=1)
    start = clock[0]
    engine = Engine(start)
    store._trajectory144 = engine
    source, snapshot = _source_signal(source_arm, engine, token, pool, clock, start)

    # A signal from before the seed's append frontier is never replayed.
    stale = deepcopy(source)
    stale["observed_at"] = iso(parse_time(proposal["registered_at"]) - timedelta(seconds=1))
    stale["recorded_at"] = stale["observed_at"]
    assert seed not in manager.signals(engine.pools[(token.token_id, pool)]["features"], {source_arm: stale}, clock[0])

    seed_signal = manager.signals(engine.pools[(token.token_id, pool)]["features"], {source_arm: source}, clock[0])[seed]
    combined = {source_arm: source, seed: seed_signal}
    store.observe_chain_meme_pattern(token, snapshot, recorded_at=clock[0], cohort_signals=combined)
    clock[0] += timedelta(seconds=10)
    item = row(clock[0], 88, token=token.token_id, pool=pool, price=snapshot.price_usd * 1.001, buys=888, volume=88888)
    engine.accept(item, clock[0])
    next_snapshot = _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.001)
    next_snapshot.volume_5m_usd = item["volume_5m_usd"]
    next_snapshot.buys_5m = item["buys_5m"]
    next_snapshot.sells_5m = item["sells_5m"]
    store.observe_chain_meme_pattern(token, next_snapshot, recorded_at=clock[0], cohort_signals=combined)
    assert gate.pending
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id IN (?,?)", (source_arm, seed)).fetchone()[0] == 0

    gate.cache[(token.token_id, pool)] = {"status": "PASS", "allow": True, "source_at": iso(clock[0]), "reasons": []}
    clock[0] += timedelta(seconds=10)
    item = row(clock[0], 99, token=token.token_id, pool=pool, price=snapshot.price_usd * 1.001, buys=999, volume=99999)
    engine.accept(item, clock[0])
    later = _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.001)
    later.volume_5m_usd = item["volume_5m_usd"]
    later.buys_5m = item["buys_5m"]
    later.sells_5m = item["sells_5m"]
    with store._lock, store.db:
        gate.resume(token, later, clock[0])
    positions = store.db.execute("SELECT arm_id,stake_usd,source_entry_fill_id,opened_at FROM chain_meme_trader_positions WHERE arm_id IN (?,?) ORDER BY arm_id", (source_arm, seed)).fetchall()
    assert len(positions) == 2, {
        "pending": gate.pending,
        "outcomes": [dict(row) for row in store.db.execute("SELECT arm_id,outcome FROM chain_meme_trader_entry_participant_outcomes")],
    }
    assert {row["stake_usd"] for row in positions} == {2.0}
    assert len({row["source_entry_fill_id"] for row in positions}) == 1
    assert all(row["opened_at"] > source["recorded_at"] for row in positions)

    # A true adverse mark exits both paired accounts under the hard-stop contract.
    for _ in range(2):
        clock[0] += timedelta(seconds=2)
        store.upsert_chain_meme_trader_market_mark(token, _snapshot(token, pool, clock[0], price=0.2), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])
    closed = store.db.execute("SELECT arm_id,status,close_reason FROM chain_meme_trader_positions WHERE arm_id IN (?,?)", (source_arm, seed)).fetchall()
    assert {row["status"] for row in closed} == {"closed"}
    assert all("hard_stop" in row["close_reason"] for row in closed)
    store.close()


def test_seed_policies_have_forward_activation_and_30_to_120_trend_contract(tmp_path, monkeypatch):
    store, manager, _, clock = _setup(tmp_path, monkeypatch)
    for source_arm, seed in SEEDS.items():
        proposal = next(item for item in manager.state["proposals"].values() if item["arm_id"] == seed)
        policy = manager.policies[seed]
        assert proposal["origin"] == "USER_AUTHORIZED_SEED"
        assert proposal["status"] in {"LOADED", "REGISTERED"}
        assert policy["source_arm_ids"] == [source_arm]
        assert policy["entry_alias_of"] == source_arm
        assert policy["signal_origin_clock"] == "recipe_activation_at"
        assert policy["max_hold_minutes"] == 30
        assert policy["trend_base_hold_minutes"] == 30
        assert policy["trend_max_hold_minutes"] == 120
        assert policy["trajectory145_trend_evidence"] is True
        assert policy["hard_stop_return"] == pytest.approx(-0.2)
        assert policy["trailing_activate_return"] == pytest.approx(0.3)
        assert policy["trailing_drawdown"] == pytest.approx(0.15)
    store.close()


def test_seed_keeps_30_minute_base_until_fresh_300_second_trend_evidence(tmp_path, monkeypatch):
    store, manager, _, clock = _setup(tmp_path, monkeypatch)
    seed = SEEDS[ARMS[1]]
    policy = manager.policies[seed]
    token_id = "bsc:0x" + "5" * 40
    pool = "0x" + "6" * 40
    opened = clock[0] - timedelta(minutes=31)
    position = {
        "id": 1, "definition_version": store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        "arm_id": seed, "shadow_cohort_id": 1, "token_id": token_id,
        "mark_pair_address": pool, "opened_at": iso(opened), "source_entry_fill_id": 7,
        "highest_economic_value_usd": 2.0,
    }
    store._trajectory144 = SimpleNamespace(pools={})
    assert store._cohort_router_exit_policy(policy, position)["max_hold_minutes"] == 30

    feature = {
        "observed_at": iso(clock[0]), "recorded_at": iso(clock[0]), "drawdown": 0.0,
        "windows": {"300": {"start_at": iso(clock[0] - timedelta(seconds=300)),
                               "end_at": iso(clock[0]), "log_slope": 0.01,
                               "activity_change": 1.1, "liquidity_change": 1.0}},
    }
    store._trajectory144 = SimpleNamespace(pools={(token_id, pool): {"features": feature}})
    assert store._cohort_router_exit_policy(policy, position)["max_hold_minutes"] == 120.0
    rows = store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence WHERE kind='trajectory145_trend_decision'").fetchall()
    assert rows and any('TREND_EXTENDED' in row["payload_json"] for row in rows)
    store.close()


def test_seed_wait_buy_checkpoint_reopens_without_duplicate_claim_fill_or_recipe(tmp_path, monkeypatch):
    from memetrader.mode_learning145 import Coordinator

    store, manager, gate, clock = _setup(tmp_path, monkeypatch)
    learning = Coordinator(store)
    store._mode_learning144 = learning
    source_arm, seed = ARMS[1], SEEDS[ARMS[1]]
    token = TokenCandidate("bsc", "0x" + "7" * 40, "restart fixture", "RST145")
    pool = "0x" + "8" * 40
    store.upsert_token(token)
    clock[0] += timedelta(seconds=1)
    engine = Engine(clock[0])
    store._trajectory144 = engine
    source, snapshot = _source_signal(source_arm, engine, token, pool, clock, clock[0])
    seed_signal = manager.signals(engine.pools[(token.token_id, pool)]["features"], {source_arm: source}, clock[0])[seed]
    combined = {source_arm: source, seed: seed_signal}
    store.observe_chain_meme_pattern(token, snapshot, recorded_at=clock[0], cohort_signals=combined)
    clock[0] += timedelta(seconds=10)
    item = row(clock[0], 88, token=token.token_id, pool=pool, price=snapshot.price_usd * 1.001, buys=888, volume=88888)
    engine.accept(item, clock[0])
    next_snapshot = _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.001)
    next_snapshot.volume_5m_usd = item["volume_5m_usd"]
    next_snapshot.buys_5m = item["buys_5m"]
    next_snapshot.sells_5m = item["sells_5m"]
    store.observe_chain_meme_pattern(token, next_snapshot, recorded_at=clock[0], cohort_signals=combined)
    assert len(gate.pending) == 1
    claims_before = store.db.execute("SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims").fetchone()[0]
    additions_before = store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id IN (?,?)", (seed, SEEDS[ARMS[2]])).fetchone()[0]
    engine_checkpoint = engine.state_payload()
    database = tmp_path / "delivery145.sqlite3"
    store.close()

    store = Store(database, initial_cash_usd=1000)
    manager = Manager(store)
    gate = PreentrySafety(store, SimpleNamespace(config={}))
    store._preentry_safety = gate
    restored_engine = Engine(parse_time(engine_checkpoint["started_at"]))
    assert restored_engine.load_state(engine_checkpoint)
    store._trajectory144 = restored_engine
    learning = Coordinator(store)
    store._mode_learning144 = learning
    assert len(gate.pending) == 1
    assert manager.slots() == 2
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims").fetchone()[0] == claims_before
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id IN (?,?)", (seed, SEEDS[ARMS[2]])).fetchone()[0] == additions_before

    gate.cache[(token.token_id, pool)] = {"status": "PASS", "allow": True, "source_at": iso(clock[0]), "reasons": []}
    clock[0] += timedelta(seconds=1)
    with store._lock, store.db:
        gate.resume(token, _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.002), clock[0])
    positions = store.db.execute("SELECT arm_id,source_entry_fill_id FROM chain_meme_trader_positions WHERE arm_id IN (?,?)", (source_arm, seed)).fetchall()
    assert len(positions) == 2 and len({row["source_entry_fill_id"] for row in positions}) == 1
    assert len(learning.state["actual_pending"]) == 2
    learning.flush(clock[0])
    store.close()

    store = Store(database, initial_cash_usd=1000)
    restored_learning = Coordinator(store)
    assert len(restored_learning.state["actual_pending"]) == 2
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id IN (?,?)", (source_arm, seed)).fetchone()[0] == 2
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id IN (?,?)", (seed, SEEDS[ARMS[2]])).fetchone()[0] == additions_before
    store.close()


def test_principal_recovery_partial_fill_survives_reopen_without_duplicate_trades(tmp_path, monkeypatch):
    store, manager, gate, clock = _setup(tmp_path, monkeypatch)
    source_arm, released_seed = ARMS[1], SEEDS[ARMS[2]]
    released_hash = next(
        key for key, item in manager.state["proposals"].items()
        if item["arm_id"] == released_seed
    )
    # Fixture disposition opens one real recipe slot; registration still uses Manager.
    manager.disposition(released_hash, "REJECT", "fixture_release_candidate_slot", clock[0])
    manager.flush(clock[0])
    proposal = manager.propose(
        recipe(manager.source(source_arm), "PRINCIPAL_RECOVERY", clock[0], evidence=["fixture"]),
        "AUTO_GENERATED",
    )
    manager.flush(clock[0])
    principal_arm = proposal["arm_id"]
    assert manager.policies[principal_arm]["dynamic_principal_recovery"] == "minimum_net_debit_next_frame/v2"

    token = TokenCandidate("bsc", "0x" + "9" * 40, "principal fixture", "PR145")
    pool = "0x" + "a" * 40
    store.upsert_token(token)
    clock[0] += timedelta(seconds=1)
    engine = Engine(clock[0])
    store._trajectory144 = engine
    source, snapshot = _source_signal(source_arm, engine, token, pool, clock, clock[0])
    principal_signal = manager.signals(
        engine.pools[(token.token_id, pool)]["features"], {source_arm: source}, clock[0]
    )[principal_arm]
    combined = {source_arm: source, principal_arm: principal_signal}
    store.observe_chain_meme_pattern(token, snapshot, recorded_at=clock[0], cohort_signals=combined)
    clock[0] += timedelta(seconds=10)
    item = row(clock[0], 88, token=token.token_id, pool=pool, price=snapshot.price_usd * 1.001, buys=888, volume=88888)
    engine.accept(item, clock[0])
    safety_snapshot = _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.001)
    safety_snapshot.volume_5m_usd = item["volume_5m_usd"]
    safety_snapshot.buys_5m = item["buys_5m"]
    safety_snapshot.sells_5m = item["sells_5m"]
    store.observe_chain_meme_pattern(token, safety_snapshot, recorded_at=clock[0], cohort_signals=combined)
    gate.cache[(token.token_id, pool)] = {"status": "PASS", "allow": True, "source_at": iso(clock[0]), "reasons": []}
    clock[0] += timedelta(seconds=1)
    with store._lock, store.db:
        gate.resume(token, _snapshot(token, pool, clock[0], price=snapshot.price_usd * 1.002), clock[0])

    def position():
        return store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (principal_arm,)
        ).fetchone()

    def mark(price):
        clock[0] += timedelta(seconds=1)
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pool, clock[0], price=price), recorded_at=clock[0]
        )
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])

    mark(1.5)
    before = position()
    assert before["pending_mark_id"] is not None and before["principal_recovered"] == 0
    mark(2.0)
    partial = position()
    assert partial["status"] == "open" and partial["principal_recovered"] == 1
    assert partial["realized_proceeds_usd"] >= partial["stake_usd"]
    assert 0 < int(partial["amount_raw"]) < int(before["amount_raw"])
    assert partial["highest_signal_price_usd"] == 2.0
    buys_sells = store.db.execute(
        "SELECT side,COUNT(*) AS n FROM chain_meme_trader_trades WHERE arm_id=? GROUP BY side", (principal_arm,)
    ).fetchall()
    assert {row["side"]: row["n"] for row in buys_sells} == {"BUY": 1, "SELL": 1}
    database = tmp_path / "delivery145.sqlite3"
    partial_state = (partial["amount_raw"], partial["realized_proceeds_usd"], partial["highest_signal_price_usd"])
    store.close()

    store = Store(database, initial_cash_usd=1000)
    restored = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (principal_arm,)).fetchone()
    restored_manager = Manager(store)
    assert (restored["amount_raw"], restored["realized_proceeds_usd"], restored["highest_signal_price_usd"]) == partial_state
    assert restored["status"] == "open" and restored["principal_recovered"] == 1
    assert restored_manager.policies[principal_arm]["dynamic_principal_recovery"] == "minimum_net_debit_next_frame/v2"
    final_counts = store.db.execute(
        "SELECT side,COUNT(*) AS n FROM chain_meme_trader_trades WHERE arm_id=? GROUP BY side", (principal_arm,)
    ).fetchall()
    assert {row["side"]: row["n"] for row in final_counts} == {"BUY": 1, "SELL": 1}
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id=?", (principal_arm,)
    ).fetchone()[0] == 1
    store.close()
