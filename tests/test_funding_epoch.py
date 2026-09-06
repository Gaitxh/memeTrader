from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


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
