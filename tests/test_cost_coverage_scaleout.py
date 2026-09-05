from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def _add_broad_snapshot(store: Store) -> tuple[TokenCandidate, int]:
    observed = utcnow()
    address = str(Pubkey.new_unique())
    token = TokenCandidate(
        chain="solana", address=address, name="Scaleout fixture",
        symbol="SCALE", source="dexscreener",
    )
    store.upsert_token(token, seen_at=observed)
    pair = {
        "chainId": "solana",
        "dexId": "pumpfun",
        "pairAddress": f"pool-{address}",
        "pairCreatedAt": round((observed - timedelta(seconds=60)).timestamp() * 1000),
        "priceUsd": "1.0",
        "baseToken": {"address": address, "name": token.name, "symbol": token.symbol},
        "txns": {
            "m5": {"buys": 30, "sells": 20},
            "h1": {"buys": 30, "sells": 20},
        },
        "volume": {"m5": 900.0, "h1": 900.0},
        "priceChange": {"h1": 0.0},
    }
    snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", address, 1.0, 10_000, 100_000, 900.0, 30, 20,
        observed_at=observed, ingested_at=observed,
        provider="dexscreener", raw={"pair": pair},
    ))
    return token, snapshot_id


def _seed_position(
    store: Store, *, version: str, policy: dict, opened_at,
) -> tuple[TokenCandidate, int]:
    token = TokenCandidate(
        chain="solana", address=str(Pubkey.new_unique()),
        name="Scaleout position", symbol="SCALE", source="dexscreener",
    )
    store.upsert_token(token, seen_at=opened_at)
    entry_execution_price = 1.04
    quantity = 20.0 / entry_execution_price
    amount_raw = max(1, round(quantity * 1_000_000_000))
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (version, token.token_id, "broad_launch", 1, "pair-A", iso(opened_at)),
        )
        cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,20,?,'open',?)",
            (
                version, policy["arm_id"], cohort_id, token.token_id, cohort_id,
                1, 1, 1.0, entry_execution_price, quantity, quantity,
                str(amount_raw), str(amount_raw), 1.0, iso(opened_at),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,realized_pnl_usd,reason,created_at) "
            "VALUES(?,?,?,?, 'BUY',20,-20,NULL,'fixture',?)",
            (version, policy["arm_id"], cohort_id, token.token_id, iso(opened_at)),
        )
    return token, cohort_id


def test_cost_coverage_scaleout_append_is_idempotent_and_forward_only(
    tmp_path: Path,
):
    store = Store(tmp_path / "cost-coverage-frontier.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    registration = store._chain_meme_trader_registration(version)
    before = store._chain_meme_trader_effective_definition(
        version, registration["definition_json"],
    )
    old_contracts = [
        (policy["arm_id"], policy["behavior_contract_hash"])
        for policy in before["policies"]
    ]
    assert len(old_contracts) == 127

    _, pre_frontier_id = _add_broad_snapshot(store)
    addition = store.register_chain_meme_trader_cost_coverage_scaleout()
    assert int(addition["activation_snapshot_id"]) == pre_frontier_id
    assert dict(store.register_chain_meme_trader_cost_coverage_scaleout()) == dict(addition)

    after = store._chain_meme_trader_effective_definition(
        version, registration["definition_json"],
    )
    assert [
        (policy["arm_id"], policy["behavior_contract_hash"])
        for policy in after["policies"][:127]
    ] == old_contracts
    assert len(after["policies"]) == 128
    added = after["policies"][-1]
    assert added["arm_id"] == "broad_cost_coverage_scaleout_v1"
    assert added["forward_activation_snapshot_id"] == pre_frontier_id

    assert store.record_chain_meme_trader_account_snapshots(
        definition_version=version,
    ) == 128
    account = store.db.execute(
        "SELECT cash_usd FROM chain_meme_trader_account_snapshots "
        "WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1",
        (version, added["arm_id"]),
    ).fetchone()
    assert account["cash_usd"] == pytest.approx(1000.0)

    store.enroll_chain_meme_trader_v6(definition_version=version)
    assert store.db.execute(
        "SELECT 1 FROM chain_meme_trader_entry_decisions d JOIN "
        "chain_meme_trader_v6_cohorts c ON c.definition_version=d.definition_version "
        "AND c.id=d.shadow_cohort_id WHERE d.definition_version=? AND d.arm_id=? "
        "AND c.source_snapshot_id=?",
        (version, added["arm_id"], pre_frontier_id),
    ).fetchone() is None

    _, post_frontier_id = _add_broad_snapshot(store)
    store.enroll_chain_meme_trader_v6(definition_version=version)
    decision = store.db.execute(
        "SELECT d.status FROM chain_meme_trader_entry_decisions d JOIN "
        "chain_meme_trader_v6_cohorts c ON c.definition_version=d.definition_version "
        "AND c.id=d.shadow_cohort_id WHERE d.definition_version=? AND d.arm_id=? "
        "AND c.source_snapshot_id=?",
        (version, added["arm_id"], post_frontier_id),
    ).fetchone()
    assert decision is not None and decision["status"] == "admitted"
    store.close()


def test_cost_coverage_scaleout_uses_economic_return_and_remaining_fraction(
    tmp_path: Path,
):
    store = Store(tmp_path / "cost-coverage-exits.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_trader_cost_coverage_scaleout()
    version = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    policy = Store.chain_meme_trader_cost_coverage_scaleout_policy()
    started = utcnow()
    token, cohort_id = _seed_position(
        store, version=version, policy=policy,
        opened_at=started - timedelta(minutes=1),
    )

    tick = 0

    def mark(price: float) -> int:
        nonlocal tick
        tick += 1
        at = started + timedelta(seconds=tick)
        store.upsert_chain_meme_trader_market_mark(
            token,
            TokenSnapshot(
                "solana", token.address, price, 10_000, 100_000, 2_000, 8, 2,
                observed_at=at, ingested_at=at, provider="dexscreener",
                raw={"pair": {"pairAddress": "pair-A"}},
            ),
            recorded_at=at,
        )
        return store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=at,
        )

    def position():
        return store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=? AND shadow_cohort_id=?",
            (version, policy["arm_id"], cohort_id),
        ).fetchone()

    def price_for_return(target_return: float) -> float:
        current = position()
        initial = int(current["initial_amount_raw"])
        remaining_fraction = int(current["amount_raw"]) / initial
        target_equity = float(current["stake_usd"]) * (1.0 + target_return)
        unrealized_target = target_equity - float(current["realized_proceeds_usd"] or 0.0)
        return (
            unrealized_target * float(current["entry_execution_price_usd"])
            / (float(current["stake_usd"]) * remaining_fraction * 0.96)
        )

    assert mark(1.04 * (1.0 + 0.1199) / 0.96) == 0

    expected_remaining = (0.50, 0.25, 0.0)
    for tier, (target_return, remaining) in enumerate(
        zip((0.12, 0.30, 0.60), expected_remaining), 1,
    ):
        trigger_price = price_for_return(target_return) * (1.0 + 1e-9)
        assert mark(trigger_price) == 1
        pending = store.db.execute(
            "SELECT * FROM chain_meme_trader_marks WHERE definition_version=? "
            "AND arm_id=? AND shadow_cohort_id=? AND status='pending'",
            (version, policy["arm_id"], cohort_id),
        ).fetchone()
        assert pending is not None and pending["action"] == f"TAKE_PROFIT_{tier}"
        assert mark(trigger_price) == 1
        current = position()
        actual_remaining = int(current["amount_raw"]) / int(current["initial_amount_raw"])
        assert actual_remaining == pytest.approx(remaining, abs=1e-8)
        assert int(current["next_tp_index"]) == tier

    assert position()["status"] == "closed"
    fills = store.db.execute(
        "SELECT input_amount_raw FROM chain_meme_trader_fills WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL' ORDER BY id",
        (version, policy["arm_id"], cohort_id),
    ).fetchall()
    assert len(fills) == 3
    store.close()
