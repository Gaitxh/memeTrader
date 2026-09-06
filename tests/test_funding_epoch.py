from __future__ import annotations

import json
import asyncio
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store
from memetrader.runtime import Runtime


def test_new_period_models_seal_prior_period_at_activation_frontier(tmp_path, monkeypatch):
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION)
    store = Store(tmp_path / "research-source.sqlite3")
    old, new = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION, Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_duration_risk_experiment()
    cutoff = utcnow()
    store.activate_chain_meme_trader_funding_epoch(target_version=new, source_version=old, at=cutoff)
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", new)
    calls = []

    def samples(connection, version, at):
        assert version == old and at == iso(cutoff)
        calls.append(version)
        return dict(samples=[], excluded={}, cutoff_at=at, definition_version=version)

    monkeypatch.setattr("memetrader.runtime.load_competing_risk_samples", samples)
    monkeypatch.setattr("memetrader.runtime.load_duration_risk_samples", samples)
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()

    async def seal():
        for _ in range(2):
            await runtime.seal_capital_research_once()
            await runtime.seal_duration_research_once()

    asyncio.run(seal())
    assert calls == [old, old]
    for model in (runtime._capital_risk_model, runtime._duration_risk_model):
        assert model["definition_version"] == old and model["cutoff_at"] == iso(cutoff)
    assert store._chain_meme_trader_effective_net_flows(new) == {}
    store.close()


@pytest.mark.parametrize("arm,ages", [
    ("broad_mature_continuity_control_v1", [0, 16, 32, 33]),
])
def test_reviewed_epoch_replaces_rules_not_old_ledger_and_buys_on_later_frame(tmp_path, monkeypatch, arm, ages):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION)
    store = Store(tmp_path / "reviewed.sqlite3")
    activation = store.activate_chain_meme_trader_funded_period()
    old, new = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION, Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    old_raw = store._chain_meme_trader_registration(old)["definition_json"]
    definition = store._chain_meme_trader_effective_definition(new, store._chain_meme_trader_registration(new)["definition_json"])
    selected = next(p for p in definition["policies"] if p["arm_id"] == arm)
    assert selected["strategy_revision"] == 2
    assert selected["revision_history"][-1]["source_definition_version"] == old
    assert selected["forward_started_at"] == activation["activated_at"]
    assert store._chain_meme_trader_effective_net_flows(new) == {}
    assert store.record_chain_meme_trader_account_snapshots(definition_version=new) == len(definition["policies"])
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_account_snapshots WHERE definition_version=? AND cash_usd=1000", (new,)).fetchone()[0] == len(definition["policies"])
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "Revision test", "REV", source="fixture")
    pair = str(Pubkey.new_unique())
    start = clock[0] + timedelta(seconds=1)
    mature = "mature" in arm
    for index, elapsed in enumerate(ages):
        clock[0] = when = start + timedelta(seconds=elapsed)
        snap = _snapshot(token, pair, when)
        snap.buys_5m, snap.sells_5m = 30, 25
        snap.raw["pair"]["pairCreatedAt"] = int((start - timedelta(seconds=600 if mature else 60)).timestamp()*1000)
        snap.raw["pair"]["txns"] = {"m5": {"buys": 30, "sells": 25}, "h1": {"buys": 35 if mature else 30, "sells": 25}}
        store.observe_chain_meme_pattern(token, snap, recorded_at=when)
        count = store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? AND side='BUY'", (new, arm)).fetchone()[0]
        assert count == int(index == len(ages)-1)
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?", (new, arm)).fetchone()
    assert position["stake_usd"] == pytest.approx(20)
    assert position["paper_quantity_tokens"] == pytest.approx(20/1.04)
    assert store._chain_meme_trader_registration(old)["definition_json"] == old_raw
    assert dict(store.activate_chain_meme_trader_funded_period()) == dict(activation)
    store.close()


def test_reviewed_flash_revision_remains_on_main_lane_with_revised_volume_band(
    tmp_path, monkeypatch,
):
    arm = "broad_flash_tail_first_mover_v1"
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(
        Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION",
        Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION,
    )
    store = Store(tmp_path / "reviewed-flash-main.sqlite3")
    store.activate_chain_meme_trader_funded_period()
    old = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    new = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    old_registration = store._chain_meme_trader_registration(old)
    old_raw = old_registration["definition_json"]
    old_definition = store._chain_meme_trader_effective_definition(
        old, old_raw,
    )
    new_registration = store._chain_meme_trader_registration(new)
    new_definition = store._chain_meme_trader_effective_definition(
        new, new_registration["definition_json"],
    )
    original = next(p for p in old_definition["policies"] if p["arm_id"] == arm)
    revised = next(p for p in new_definition["policies"] if p["arm_id"] == arm)
    assert revised["arm_id"] == original["arm_id"]
    assert revised["canonical_id"] == original["canonical_id"]
    assert revised["strategy_revision"] == 2
    assert revised.get("entry_match_mode") == original.get("entry_match_mode")
    assert revised.get("entry_match_mode") not in {
        "isolated_pattern_observer", "isolated_cohort_observer",
    }
    assert "entry_revision_kind" not in revised
    assert revised["entry_filter"]["max_age_seconds_exclusive"] == 120.0
    assert revised["entry_filter"]["prior55_trades_equal"] == 0
    assert revised["entry_filter"]["min_m5_trades"] == 50
    assert revised["entry_filter"]["min_m5_volume_usd"] == 200.0
    assert "max_m5_volume_usd_exclusive" not in revised["entry_filter"]

    start = clock[0] + timedelta(seconds=1)
    token_ids = []
    for index, volume in enumerate((199.0, 1_200.0, 1_200.0, 1_200.0, 1_200.0)):
        clock[0] = observed = start + timedelta(seconds=index)
        token = TokenCandidate(
            "solana", str(Pubkey.new_unique()), f"Flash {index}", f"F{index}",
            source="fixture",
        )
        token_ids.append(token.token_id)
        pair = str(Pubkey.new_unique())
        snapshot = _snapshot(token, pair, observed)
        snapshot.buys_5m, snapshot.sells_5m = 30, 20
        snapshot.volume_5m_usd = volume
        snapshot.raw["pair"]["pairCreatedAt"] = int(
            (observed - timedelta(seconds=60)).timestamp() * 1000
        )
        snapshot.raw["pair"]["txns"] = {
            "m5": {"buys": 30, "sells": 20},
            "h1": {"buys": 30, "sells": 20},
        }
        snapshot.raw["pair"]["volume"] = {"m5": volume, "h1": volume}
        store.add_snapshot(snapshot)

    store.enroll_chain_meme_trader_v6(definition_version=new)
    buys = store.db.execute(
        "SELECT token_id FROM chain_meme_trader_trades WHERE "
        "definition_version=? AND arm_id=? AND side='BUY' ORDER BY id",
        (new, arm),
    ).fetchall()
    assert [row["token_id"] for row in buys] == token_ids[1:]
    assert len(buys) == 4  # Main lane coverage is not capped by the three early watch slots.
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE "
        "definition_version=? AND arm_id=?", (old, arm),
    ).fetchone()[0] == 0
    assert store._chain_meme_trader_registration(old)["definition_json"] == old_raw
    store.close()


def _snapshot(token, pair, when, *, price=1.0):
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        10_000.0,
        100_000.0,
        300.0,
        3,
        1,
        observed_at=when,
        ingested_at=when,
        provider="dexscreener",
        raw={
            "pair": {
                "chainId": token.chain,
                "dexId": "pumpswap",
                "pairAddress": pair,
                "pairCreatedAt": round(
                    (when - timedelta(seconds=60)).timestamp() * 1000
                ),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": 10_000.0},
                "txns": {
                    "m5": {"buys": 3, "sells": 1},
                    "h1": {"buys": 3, "sells": 1},
                },
                "volume": {"m5": 300.0, "h1": 300.0},
            }
        },
    )


def test_reviewed_loss_exit_keeps_original_rule_and_independent_state(tmp_path, monkeypatch):
    from memetrader.strategy_revisions import ADDITIVE_L0_LOSS_EXIT_ARMS
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION)
    store = Store(tmp_path / "loss-revision.sqlite3")
    store.activate_chain_meme_trader_funded_period()
    old, new = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION, Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    old_definition = store._chain_meme_trader_effective_definition(old, store._chain_meme_trader_registration(old)["definition_json"])
    definition = store._chain_meme_trader_effective_definition(new, store._chain_meme_trader_registration(new)["definition_json"])
    policy = next(p for p in definition["policies"] if p["arm_id"] in ADDITIVE_L0_LOSS_EXIT_ARMS and p["entry_family"] == "broad_launch")
    original = next(p for p in old_definition["policies"] if p["arm_id"] == policy["arm_id"])
    assert policy["exit_family"] == original["exit_family"]
    assert policy["entry_family"] == original["entry_family"]
    assert policy["behavior_contract_hash"] != original["behavior_contract_hash"]
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "Loss", "LOSS", source="fixture")
    pair = str(Pubkey.new_unique())
    opened = clock[0] + timedelta(seconds=1)
    clock[0] = opened
    store.upsert_token(token, seen_at=opened)
    store.add_snapshot(_snapshot(token, pair, opened))
    store.enroll_chain_meme_trader_v6(definition_version=new)
    position = dict(store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?", (new, policy["arm_id"])).fetchone())
    position["capital_exit_state_json"] = json.dumps({"unrelated_state": "preserved"})
    for seconds, price, expected in ((60, 1.0, "HOLD"), (65, .99, "HOLD"), (70, .98, "SELL")):
        now = opened + timedelta(seconds=seconds)
        position.update(mark_price_usd=price, mark_liquidity_usd=10000,
            mark_pair_address=pair, mark_status="VISIBLE", sample_sequence=seconds,
            mark_observed_at=iso(now), mark_recorded_at=iso(now), entry_pair_address=pair)
        result = store._capital_exit_result(position, {**policy,
            "capital_exit_kind": policy["revision_exit_kind"],
            "capital_exit_policy": policy["revision_exit_policy"]}, now, {}, state_key="revision_loss_exit")
        assert result[0] == expected
        position["capital_exit_state_json"] = store.db.execute(
            "SELECT capital_exit_state_json FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
            (new, policy["arm_id"], position["shadow_cohort_id"])).fetchone()[0]
    assert json.loads(position["capital_exit_state_json"])["unrelated_state"] == "preserved"
    store.close()


def test_reviewed_runner_pair_shares_later_entry_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION)
    from memetrader.strategy_revisions import CONDITIONAL_RUNNER_ARMS
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "runner-revision.sqlite3")
    old, new = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION, Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    store.activate_chain_meme_trader_funding_epoch(target_version=new, source_version=old,
        at=clock[0], apply_strategy_revisions=True)
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", new)
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "Runner", "RUN", source="fixture")
    pair = str(Pubkey.new_unique())
    start = clock[0] + timedelta(seconds=1)
    for index, seconds in enumerate((0, 16, 17)):
        clock[0] = now = start + timedelta(seconds=seconds)
        store.observe_chain_meme_pattern(token, _snapshot(token, pair, now), recorded_at=now)
        rows = store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE definition_version=? AND side='BUY'", (new,)).fetchall()
        pair_buys = [row for row in rows if row["arm_id"] in CONDITIONAL_RUNNER_ARMS]
        assert len(pair_buys) == (2 if index == 2 else 0)
    assert len({row["shadow_cohort_id"] for row in pair_buys}) == 1
    assert len({row["created_at"] for row in pair_buys}) == 1
    assert len({row["net_cash_flow_usd"] for row in pair_buys}) == 1
    store.close()


def test_funding_epoch_copies_effective_strategy_set_and_keeps_ledgers_isolated(
    tmp_path, monkeypatch
):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "funding-epoch.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    source_version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    assert store.register_chain_meme_result_experiments() == 2

    source_registration = store._chain_meme_trader_registration(source_version)
    source_raw = json.loads(source_registration["definition_json"])
    source_effective = store._chain_meme_trader_effective_definition(
        source_version, source_registration["definition_json"]
    )
    source_additions = store.db.execute(
        "SELECT * FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? ORDER BY id",
        (source_version,),
    ).fetchall()
    assert len(source_additions) == 2

    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Old position", "OLD", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    opened_at = clock[0] + timedelta(seconds=1)
    clock[0] = opened_at
    store.upsert_token(token, seen_at=opened_at)
    snapshot_id = store.add_snapshot(_snapshot(token, pair, opened_at))
    source_policy = next(
        policy
        for policy in source_effective["policies"]
        if policy.get("hard_stop_return") is not None
        and not policy.get("capital_exit_kind")
    )
    quantity = 20.0 / 1.04
    amount_raw = str(round(quantity * 1_000_000_000))
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (
                source_version,
                token.token_id,
                "broad_launch",
                snapshot_id,
                pair,
                iso(opened_at),
            ),
        )
        cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,20,1,'open',?)",
            (
                source_version,
                source_policy["arm_id"],
                cohort_id,
                token.token_id,
                cohort_id,
                snapshot_id,
                snapshot_id,
                1.0,
                1.04,
                quantity,
                quantity,
                amount_raw,
                amount_raw,
                iso(opened_at),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,reason,created_at,recorded_at) "
            "VALUES(?,?,?,?, 'BUY',20,-20,'fixture',?,?)",
            (
                source_version,
                source_policy["arm_id"],
                cohort_id,
                token.token_id,
                iso(opened_at),
                iso(opened_at),
            ),
        )

    target_version = "chain-meme-trader/test-funding-epoch/v1"
    epoch_at = opened_at + timedelta(seconds=1)
    clock[0] = epoch_at
    activation = store.activate_chain_meme_trader_funding_epoch(
        target_version=target_version,
        source_version=source_version,
        at=epoch_at,
    )
    assert activation["activated_at"] == iso(epoch_at)
    assert activation["activation_snapshot_id"] == snapshot_id

    target_registration = store._chain_meme_trader_registration(target_version)
    target_raw = json.loads(target_registration["definition_json"])
    target_effective = store._chain_meme_trader_effective_definition(
        target_version, target_registration["definition_json"]
    )
    assert target_raw["starting_cash_usd_each_arm"] == pytest.approx(1000.0)
    assert target_raw["funding_source_version"] == source_version
    assert {policy["arm_id"] for policy in target_raw["policies"]} == {
        policy["arm_id"] for policy in source_raw["policies"]
    }
    assert {
        policy["arm_id"]: policy["behavior_contract_hash"]
        for policy in target_effective["policies"]
    } == {
        policy["arm_id"]: policy["behavior_contract_hash"]
        for policy in source_effective["policies"]
    }
    assert all(
        policy["forward_started_at"] == iso(epoch_at)
        and policy["forward_activation_snapshot_id"] == snapshot_id
        for policy in target_effective["policies"]
    )
    target_additions = store.db.execute(
        "SELECT * FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? ORDER BY id",
        (target_version,),
    ).fetchall()
    assert [row["arm_id"] for row in target_additions] == [
        row["arm_id"] for row in source_additions
    ]
    assert [row["policy_json"] for row in target_additions] == [
        row["policy_json"] for row in source_additions
    ]
    assert all(
        row["activated_at"] == iso(epoch_at)
        and row["activation_snapshot_id"] == snapshot_id
        for row in target_additions
    )
    assert {
        item["source_addition_id"] for item in target_raw["funding_source_policy_additions"]
    } == {int(row["id"]) for row in source_additions}
    stop = store.db.execute(
        "SELECT * FROM chain_meme_trader_primary_stops WHERE definition_version=?",
        (source_version,),
    ).fetchone()
    assert stop["stopped_at"] == iso(epoch_at)
    assert stop["source_frontier"] == snapshot_id

    for offset in (2, 3):
        mark_at = opened_at + timedelta(seconds=offset)
        clock[0] = mark_at
        store.upsert_chain_meme_trader_market_mark(
            token,
            _snapshot(token, pair, mark_at, price=0.5),
            recorded_at=mark_at,
        )
        store.evaluate_chain_meme_trader_market_marks(
            definition_version=source_version,
            now=mark_at,
            token_ids=[token.token_id],
        )
    old_position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (source_version, source_policy["arm_id"], cohort_id),
    ).fetchone()
    assert old_position["status"] == "closed"
    source_flow = store._chain_meme_trader_effective_net_flows(source_version)[
        source_policy["arm_id"]
    ]
    expected_recovery = 20.0 * 0.5 / 1.04 * 0.96
    assert source_flow == pytest.approx(-20.0 + expected_recovery)
    assert store._chain_meme_trader_effective_net_flows(target_version).get(
        source_policy["arm_id"], 0.0
    ) == pytest.approx(0.0)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=?",
        (target_version,),
    ).fetchone()[0] == 0

    frozen_registration = target_registration["definition_json"]
    frozen_additions = [tuple(row) for row in target_additions]
    repeated = store.activate_chain_meme_trader_funding_epoch(
        target_version=target_version,
        source_version=source_version,
        at=epoch_at + timedelta(days=1),
    )
    assert repeated["activated_at"] == activation["activated_at"]
    assert store._chain_meme_trader_registration(target_version)[
        "definition_json"
    ] == frozen_registration
    assert [
        tuple(row)
        for row in store.db.execute(
            "SELECT * FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? ORDER BY id",
            (target_version,),
        ).fetchall()
    ] == frozen_additions
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=?",
        (target_version,),
    ).fetchone()[0] == 0
    store.close()
