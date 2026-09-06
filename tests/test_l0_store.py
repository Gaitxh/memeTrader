from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


L0_ARMS = {
    "l0_continuation_failure_candidate_v1",
    "l0_continuation_failure_control_v1",
    "l0_profit_lock_candidate_v1",
    "l0_profit_lock_control_v1",
}


def _token(name: str) -> TokenCandidate:
    return TokenCandidate(
        "solana", str(Pubkey.new_unique()), name, name[:4], source="fixture"
    )


def _snapshot(token, pair, when, *, price=2.0, liquidity=10_000.0):
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        liquidity,
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
                "liquidity": {"usd": liquidity},
                "txns": {
                    "m5": {"buys": 3, "sells": 1},
                    "h1": {"buys": 3, "sells": 1},
                },
                "volume": {"m5": 300.0, "h1": 300.0},
            }
        },
    )


def _add_snapshot(store, clock, token, pair, when, **changes):
    clock[0] = when
    store.upsert_token(token, seen_at=when)
    return store.add_snapshot(_snapshot(token, pair, when, **changes))


def _add_mark(store, clock, token, pair, when, *, price, liquidity):
    clock[0] = when
    store.upsert_chain_meme_trader_market_mark(
        token,
        _snapshot(token, pair, when, price=price, liquidity=liquidity),
        recorded_at=when,
    )
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        now=when,
        token_ids=[token.token_id],
    )


def _store_with_l0_entry(tmp_path, monkeypatch, name):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / name, initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()

    pre_token, pre_pair = _token("Before"), str(Pubkey.new_unique())
    pre_id = _add_snapshot(
        store, clock, pre_token, pre_pair, clock[0] + timedelta(seconds=1)
    )
    clock[0] += timedelta(seconds=1)
    assert store.register_chain_meme_l0_experiments() == 4
    assert store.register_chain_meme_l0_experiments() == 0

    store.enroll_chain_meme_trader_v6(
        definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id LIKE 'l0_%'",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()[0] == 0

    token, pair = _token("Forward"), str(Pubkey.new_unique())
    opened_at = clock[0] + timedelta(seconds=1)
    source_id = _add_snapshot(store, clock, token, pair, opened_at)
    result = store.enroll_chain_meme_trader_v6(
        definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    )
    assert result["admitted"] == 1
    return store, clock, token, pair, opened_at, pre_id, source_id


def test_l0_registration_is_idempotent_future_only_and_keeps_base_definition(
    tmp_path, monkeypatch
):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "l0-registration.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    before = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?",
        (version,),
    ).fetchone()[0]

    pre_token, pre_pair = _token("Before"), str(Pubkey.new_unique())
    pre_id = _add_snapshot(
        store, clock, pre_token, pre_pair, clock[0] + timedelta(seconds=1)
    )
    clock[0] += timedelta(seconds=1)
    assert store.register_chain_meme_l0_experiments() == 4
    assert store.register_chain_meme_l0_experiments() == 0
    after = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?",
        (version,),
    ).fetchone()[0]
    assert after == before

    additions = store.db.execute(
        "SELECT * FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id LIKE 'l0_%' ORDER BY arm_id",
        (version,),
    ).fetchall()
    assert {row["arm_id"] for row in additions} == L0_ARMS
    assert {row["activation_snapshot_id"] for row in additions} == {pre_id}
    policies = [json.loads(row["policy_json"]) for row in additions]
    assert all(policy["entry_family"] == "broad_launch" for policy in policies)
    assert all(policy["entry_match_mode"] == "exact_entry_family" for policy in policies)
    assert {
        policy["arm_id"] for policy in policies if policy["capital_exit_kind"]
    } == {
        "l0_continuation_failure_candidate_v1",
        "l0_profit_lock_candidate_v1",
    }
    store.close()


def test_l0_broad_entry_funds_four_accounts_and_s01_exits_on_next_pool_frame(
    tmp_path, monkeypatch
):
    store, clock, token, pair, opened_at, _, source_id = _store_with_l0_entry(
        tmp_path, monkeypatch, "l0-s01-market.sqlite3"
    )
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    positions = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND entry_snapshot_id=? AND arm_id LIKE 'l0_%' ORDER BY arm_id",
        (version, source_id),
    ).fetchall()
    assert {row["arm_id"] for row in positions} == L0_ARMS
    assert len({row["shadow_cohort_id"] for row in positions}) == 1
    assert len({row["source_entry_fill_id"] for row in positions}) == 1
    assert all(row["stake_usd"] == pytest.approx(20.0) for row in positions)
    assert all(row["entry_execution_price_usd"] == pytest.approx(2.08) for row in positions)
    flows = store._chain_meme_trader_effective_net_flows(version)
    assert {arm: flows[arm] for arm in L0_ARMS} == {
        arm: pytest.approx(-20.0) for arm in L0_ARMS
    }

    candidate = "l0_continuation_failure_candidate_v1"
    control = "l0_continuation_failure_control_v1"
    at_60 = opened_at + timedelta(seconds=60)
    _add_mark(store, clock, token, pair, at_60, price=2.1, liquidity=10_000.0)
    state = json.loads(
        store.db.execute(
            "SELECT capital_exit_state_json FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=? AND entry_snapshot_id=?",
            (version, candidate, source_id),
        ).fetchone()[0]
    )
    assert state["checkpoint_60"]["price_usd"] == pytest.approx(2.1)

    at_120 = opened_at + timedelta(seconds=120)
    _add_mark(store, clock, token, pair, at_120, price=2.0, liquidity=9_000.0)
    pending = store.db.execute(
        "SELECT p.status,p.pending_mark_id,m.action,m.reason,m.status AS mark_status,"
        "m.trigger_evidence_json FROM chain_meme_trader_positions p "
        "JOIN chain_meme_trader_marks m ON m.id=p.pending_mark_id "
        "WHERE p.definition_version=? AND p.arm_id=? AND p.entry_snapshot_id=?",
        (version, candidate, source_id),
    ).fetchone()
    assert (pending["status"], pending["action"], pending["mark_status"]) == (
        "open",
        "CAPITAL_EXIT",
        "pending",
    )
    assert pending["reason"] == "l0_continuation_failure_armed"
    assert json.loads(pending["trigger_evidence_json"])["required_fill"] == (
        "next_original_pool_frame"
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND side='SELL'",
        (version, candidate),
    ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT status,pending_mark_id FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id=? AND entry_snapshot_id=?",
        (version, control, source_id),
    ).fetchone()["pending_mark_id"] is None

    fill_at = opened_at + timedelta(seconds=126)
    _add_mark(store, clock, token, pair, fill_at, price=1.95, liquidity=8_500.0)
    statuses = {
        row["arm_id"]: row["status"]
        for row in store.db.execute(
            "SELECT arm_id,status FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND entry_snapshot_id=? AND arm_id IN (?,?)",
            (version, source_id, candidate, control),
        ).fetchall()
    }
    assert statuses == {candidate: "closed", control: "open"}
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND side='SELL'",
        (version, candidate),
    ).fetchone()
    expected_recovery = 20.0 * 1.95 / (2.0 * 1.04) * 0.96
    assert sell["gross_usd"] == pytest.approx(expected_recovery)
    assert sell["realized_pnl_usd"] == pytest.approx(expected_recovery - 20.0)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_pattern_evidence"
    ).fetchone()[0] == 0

    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=fill_at
    )
    accounts = {
        row["arm_id"]: row
        for row in store.db.execute(
            "SELECT * FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=? AND arm_id IN (?,?) ORDER BY id",
            (version, candidate, control),
        ).fetchall()
    }
    assert accounts[candidate]["cash_usd"] == pytest.approx(980.0 + expected_recovery)
    assert accounts[candidate]["realized_pnl_usd"] == pytest.approx(
        expected_recovery - 20.0
    )
    assert accounts[control]["cash_usd"] == pytest.approx(980.0)
    assert accounts[control]["realized_pnl_usd"] == pytest.approx(0.0)
    for arm in (candidate, control):
        assert accounts[arm]["indicative_equity_usd"] == pytest.approx(
            980.0 + expected_recovery
        )
        assert accounts[arm]["indicative_total_pnl_usd"] == pytest.approx(
            expected_recovery - 20.0
        )
    store.close()
