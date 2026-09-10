from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest

from memetrader.recipe145 import KEY, Manager, compile_recipe, recipe
from memetrader.models import parse_time
from memetrader.store import Store
from memetrader.trajectory144 import ARMS


NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def manager_store(tmp_path):
    store = Store(tmp_path / "recipe145.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    return store, Manager(store)


def auto_recipe(manager, source_arm=ARMS[0]):
    return recipe(manager.source(source_arm), "RECLAIM15", NOW, evidence=["forward-fill-1"])


def terminal(arm, fill_id, token_id, *, base=NOW, seconds=1):
    at = base + timedelta(seconds=seconds)
    return {
        "arm": arm, "source_fill_id": fill_id, "token_id": token_id,
        "pair_address": "pool-" + token_id, "opened_at": at.isoformat(),
        "closed_at": (at + timedelta(seconds=30)).isoformat(), "realized_pnl_usd": -0.1,
    }


def test_recipe_schema_exit_contract_hash_and_duplicate_behavior(tmp_path):
    store, manager = manager_store(tmp_path)
    source = manager.source(ARMS[0])
    accepted = auto_recipe(manager)
    first_hash, _ = compile_recipe(accepted, source)
    changed_evidence = deepcopy(accepted)
    changed_evidence["proposal_cutoff"] = (NOW + timedelta(days=1)).isoformat()
    changed_evidence["evidence_refs"] = ["later-evidence"]
    assert compile_recipe(changed_evidence, source)[0] == first_hash

    extra = deepcopy(accepted)
    extra["unbounded_parameter"] = 1
    with pytest.raises(ValueError, match="RECIPE_SCHEMA_FIELDS"):
        compile_recipe(extra, source)
    unknown_exit = deepcopy(accepted)
    unknown_exit["exit_template"] = "HOLD_FOREVER"
    with pytest.raises(ValueError, match="UNSUPPORTED_EXIT"):
        compile_recipe(unknown_exit, source)
    with pytest.raises(ValueError, match="DUPLICATE_SOURCE_BEHAVIOR"):
        compile_recipe(recipe(source, "FAST5", NOW), source)
    store.close()


def test_user_seeds_are_named_two_usdc_two_slot_policies(tmp_path):
    store, manager = manager_store(tmp_path)
    manager.flush(NOW)
    manager.flush(NOW + timedelta(seconds=1))
    seeded = [p for p in manager.state["proposals"].values()
              if p["origin"] == "USER_AUTHORIZED_SEED"]
    assert {p["arm_id"] for p in seeded} == {
        "trajectory145_sparse_trend_runner_v1", "trajectory145_reclaim_trend_runner_v1",
    }
    assert {p["status"] for p in seeded} == {"LOADED"}
    for proposal in seeded:
        policy = manager.policies[proposal["arm_id"]]
        assert policy["notional_usd"] == 2.0
        assert policy["entry_filter"]["max_concurrent_positions"] == 2
        assert policy["entry_filter"]["include_pending_in_limit"] is True
        assert policy["live"] is False
    store.close()


def test_slots_wait_then_own_candidate_disposition_frees_registration(tmp_path):
    store, manager = manager_store(tmp_path)
    manager.flush(NOW)
    manager.flush(NOW + timedelta(seconds=1))
    waiting = manager.propose(auto_recipe(manager), "AUTO_GENERATED")
    waiting_hash = next(key for key, value in manager.state["proposals"].items() if value is waiting)
    manager.flush(NOW + timedelta(seconds=2))
    assert manager.state["proposals"][waiting_hash]["status"] == "WAIT_CAPACITY"

    seeded_hash = next(key for key, value in manager.state["proposals"].items()
                       if value["origin"] == "USER_AUTHORIZED_SEED")
    manager.disposition(seeded_hash, "REJECT", "OWN_CANDIDATE_DONE", NOW + timedelta(seconds=3))
    manager.flush(NOW + timedelta(seconds=4))
    assert manager.state["proposals"][waiting_hash]["status"] == "LOADED"
    assert manager.slots() == 2
    store.close()


def test_prefrozen_signal_is_not_replayed_after_recipe_activation(tmp_path):
    store, manager = manager_store(tmp_path)
    manager.flush(NOW)
    proposal = next(value for value in manager.state["proposals"].values()
                    if value["origin"] == "USER_AUTHORIZED_SEED")
    before = NOW - timedelta(seconds=1)
    signal = {
        "observed_at": before.isoformat(), "decision_key": "pre-activation",
        "decision_evidence": {},
    }
    output = manager.signals(
        {"chain": "solana", "pool_age_seconds": 100},
        {proposal["recipe"]["source_arm_id"]: signal}, NOW,
    )
    assert output == {}
    store.close()


def test_append_receipt_is_atomic_and_restart_is_idempotent(tmp_path):
    store, manager = manager_store(tmp_path)
    manager.flush(NOW)
    manager.flush(NOW + timedelta(seconds=1))
    existing = store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()[0]
    store.db.execute(
        "CREATE TRIGGER reject_recipe145_receipt BEFORE INSERT ON chain_meme_pattern_evidence "
        "WHEN NEW.kind='recipe145_registration' BEGIN SELECT RAISE(ABORT, 'receipt failure'); END"
    )
    store.db.commit()
    proposal = manager.propose(auto_recipe(manager), "AUTO_GENERATED")
    seeded_hash = next(key for key, value in manager.state["proposals"].items()
                       if value["origin"] == "USER_AUTHORIZED_SEED")
    manager.disposition(seeded_hash, "REJECT", "MAKE_ROOM_FOR_ATOMIC_FIXTURE", NOW)
    with pytest.raises(Exception, match="receipt failure"):
        manager.register_one(NOW + timedelta(seconds=2))
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()[0] == existing

    store.db.execute("DROP TRIGGER reject_recipe145_receipt")
    store.db.commit()
    manager.register_one(NOW + timedelta(seconds=3))
    count = store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()[0]
    restored = Manager(store)
    restored.flush(NOW + timedelta(seconds=4))
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()[0] == count
    assert proposal["arm_id"] in restored.policies
    store.close()


def test_source_fill_aliases_do_not_inflate_and_real_fills_generate_one_recipe(tmp_path):
    store, manager = manager_store(tmp_path)
    started = parse_time(manager.state["activated_at"])
    # Repeated source-fill aliases are one underlying fill, never five trigger samples.
    for fill_id in range(1, 6):
        manager.terminal(terminal(ARMS[3], fill_id, "alias-" + str(fill_id), base=started, seconds=fill_id), started+timedelta(seconds=60))
        manager.terminal(terminal(ARMS[0], 99, "shared-source-fill", base=started, seconds=fill_id), started+timedelta(seconds=60))
    assert not any(p["origin"] == "AUTO_GENERATED" for p in manager.state["proposals"].values())

    for fill_id in range(1, 6):
        manager.terminal(terminal(ARMS[0], fill_id, "token-" + str(fill_id % 3), base=started, seconds=fill_id), started+timedelta(seconds=60))
    automatic = [p for p in manager.state["proposals"].values() if p["origin"] == "AUTO_GENERATED"]
    assert len(automatic) == 1
    assert automatic[0]["status"] == "VALIDATED"
    assert automatic[0]["reason"] == "ENGINEERING_VALIDATED_NOT_ALPHA"
    assert automatic[0]["recipe"]["schema"] == KEY
    store.close()


def test_generator_does_not_consume_future_terminal_receipt(tmp_path):
    store, manager = manager_store(tmp_path)
    started=parse_time(manager.state['activated_at'])
    row=terminal(ARMS[0],1,'future',base=started)
    manager.terminal(row,started)
    assert not manager.state['source_outcomes']
    row['terminal_recorded_at']=(started+timedelta(seconds=70)).isoformat()
    manager.terminal(row,started+timedelta(seconds=60))
    assert not manager.state['source_outcomes']
    store.close()
