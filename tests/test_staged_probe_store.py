from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
from memetrader.store import Store


ARMS = {
    "staged_probe_20u_once_control_v1",
    "staged_probe_5u_only_control_v1",
    "staged_probe_5u_conditional_15u_shadow_v1",
}
CANDIDATE = "staged_probe_5u_conditional_15u_shadow_v1"


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
                "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": liquidity},
                "txns": {"m5": {"buys": 3, "sells": 1}},
                "volume": {"m5": 300.0},
            }
        },
    )


def _signals(token, pair, at):
    return {
        arm: {
            "episode_id": "s03-shared-opportunity",
            "decision_key": "s03-shared-opportunity",
            "selected": {"token_id": token.token_id, "pair_address": pair},
            "observed_at": iso(at),
            "recorded_at": iso(at),
            "decision_evidence": {"broad_gate": True},
        }
        for arm in ARMS
    }


def _enter(store, clock, token, pair):
    signal_at = clock[0] + timedelta(seconds=1)
    clock[0] = signal_at
    store.upsert_token(token, seen_at=signal_at)
    assert store.observe_chain_meme_pattern(
        token, _snapshot(token, pair, signal_at),
        recorded_at=signal_at, cohort_signals=_signals(token, pair, signal_at),
    ) == 0
    fill_at = signal_at + timedelta(seconds=6)
    clock[0] = fill_at
    assert store.observe_chain_meme_pattern(
        token, _snapshot(token, pair, fill_at),
        recorded_at=fill_at, cohort_signals={},
    ) == 3
    return fill_at


def _mark(store, clock, token, pair, at, *, price, liquidity=10_000.0):
    clock[0] = at
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, at, price=price, liquidity=liquidity),
        recorded_at=at,
    )
    return store.evaluate_chain_meme_trader_market_marks(
        definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        now=at, token_ids=[token.token_id],
    )


def _state(store, cohort_id):
    raw = store.db.execute(
        "SELECT capital_exit_state_json FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, CANDIDATE, cohort_id),
    ).fetchone()[0]
    return json.loads(raw)["staged_probe"]


def _setup(tmp_path, monkeypatch, name):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / name, initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    return store, clock


def _open_shadow(store, clock, token, pair, opened_at, cohort_id):
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=60), price=2.0)
    assert _state(store, cohort_id)["checkpoint_60"]["price_usd"] == pytest.approx(2.0)
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=120), price=2.1)
    assert _state(store, cohort_id)["status"] == "QUALIFIED"
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=126), price=2.2)
    state = _state(store, cohort_id)
    assert state["status"] == "SHADOW_OPEN"
    return state


def test_staged_probe_registers_three_isolated_arms_and_settles_shadow_off_ledger(
    tmp_path, monkeypatch,
):
    store, clock = _setup(tmp_path, monkeypatch, "staged-probe.sqlite3")
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    base = store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?", (version,),
    ).fetchone()[0]
    assert store.register_chain_meme_staged_probe() == 3
    assert store.register_chain_meme_staged_probe() == 0
    assert store.db.execute(
        "SELECT definition_json FROM chain_meme_trader_v6_registrations "
        "WHERE definition_version=?", (version,),
    ).fetchone()[0] == base
    additions = store.db.execute(
        "SELECT * FROM chain_meme_trader_policy_additions WHERE definition_version=? "
        "AND arm_id LIKE 'staged_probe_%' ORDER BY arm_id", (version,),
    ).fetchall()
    assert {row["arm_id"] for row in additions} == ARMS
    policies = [json.loads(row["policy_json"]) for row in additions]
    assert {row["activated_at"] for row in additions} == {row["registered_at"] for row in additions}
    assert all(policy["entry_match_mode"] == "isolated_cohort_observer" for policy in policies)
    assert all(policy["paired_opportunity_group"] == "staged_probe_s03" for policy in policies)
    assert all("paired_entry_group" not in policy for policy in policies)

    token, pair = _token("Staged"), str(Pubkey.new_unique())
    _enter(store, clock, token, pair)
    positions = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND token_id=? AND arm_id LIKE 'staged_probe_%' ORDER BY arm_id",
        (version, token.token_id),
    ).fetchall()
    assert {row["arm_id"] for row in positions} == ARMS
    assert {row["stake_usd"] for row in positions} == {5.0, 20.0}
    assert len({row["shadow_cohort_id"] for row in positions}) == 2
    five = [row for row in positions if row["stake_usd"] == 5.0]
    assert len({row["shadow_cohort_id"] for row in five}) == 1
    assert len({row["source_entry_fill_id"] for row in five}) == 1
    candidate = next(row for row in positions if row["arm_id"] == CANDIDATE)
    opened_at = parse_time(candidate["opened_at"])
    assert opened_at is not None
    state = _open_shadow(
        store, clock, token, pair, opened_at, int(candidate["shadow_cohort_id"]),
    )
    assert state["shadow_fill"]["notional_usd"] == pytest.approx(15.0)
    assert state["shadow_fill"]["execution_price_usd"] == pytest.approx(2.2 * 1.04)
    assert state["shadow_account"]["cash_after_fill_usd"] == pytest.approx(985.0)

    trigger_at = opened_at + timedelta(minutes=15)
    _mark(store, clock, token, pair, trigger_at, price=2.4)
    assert store.db.execute(
        "SELECT pending_mark_id FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, CANDIDATE, int(candidate["shadow_cohort_id"])),
    ).fetchone()[0] is not None
    fill_at = trigger_at + timedelta(seconds=6)
    _mark(store, clock, token, pair, fill_at, price=2.5)
    closed = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, CANDIDATE, int(candidate["shadow_cohort_id"])),
    ).fetchone()
    assert closed["status"] == "closed"
    formal_recovery = 5.0 / (2.0 * 1.04) * 2.5 * 0.96
    assert closed["realized_pnl_usd"] == pytest.approx(formal_recovery - 5.0)
    state = json.loads(closed["capital_exit_state_json"])["staged_probe"]
    shadow_recovery = 15.0 / (2.2 * 1.04) * 2.5 * 0.96
    assert state["status"] == "SHADOW_CLOSED"
    assert state["shadow_exit"]["shadow_net_recovery_usd"] == pytest.approx(shadow_recovery)
    assert state["shadow_exit"]["shadow_net_pnl_usd"] == pytest.approx(shadow_recovery - 15.0)
    assert state["formal_exit_settlement"]["kind"] == "final_close"
    flows = store.db.execute(
        "SELECT side,net_cash_flow_usd FROM chain_meme_trader_trades WHERE "
        "definition_version=? AND arm_id=? ORDER BY id", (version, CANDIDATE),
    ).fetchall()
    assert [(row["side"], row["net_cash_flow_usd"]) for row in flows] == [
        ("BUY", -5.0), ("SELL", pytest.approx(formal_recovery)),
    ]
    store.close()


@pytest.mark.parametrize("legacy", [False, True])
def test_staged_probe_shadow_budget_is_shared_across_candidate_positions(
    tmp_path, monkeypatch, legacy,
):
    store, clock = _setup(tmp_path, monkeypatch, "staged-budget.sqlite3")
    store.register_chain_meme_staged_probe()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token, pair = _token("Budget"), str(Pubkey.new_unique())
    _enter(store, clock, token, pair)
    candidate = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?", (version, CANDIDATE, token.token_id),
    ).fetchone()
    prior = dict(candidate)
    prior["shadow_cohort_id"] = int(candidate["shadow_cohort_id"]) + 100_000
    prior["source_buy_trade_id"] = int(candidate["source_buy_trade_id"]) + 100_000
    prior["status"] = "closed"
    prior["closed_at"] = prior["opened_at"]
    prior["capital_exit_state_json"] = json.dumps({
        "staged_probe": {
            "status": "SHADOW_OPEN",
            "shadow_fill": ({"notional_usd": 990.0} if legacy else
                {"notional_usd": 989.9, "fee_usd": 0.1, "total_cost_usd": 990.0}),
        }
    })
    columns = list(prior)
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions(" + ",".join(columns) + ") "
            "VALUES(" + ",".join("?" for _ in columns) + ")",
            tuple(prior[column] for column in columns),
        )
    opened_at = parse_time(candidate["opened_at"])
    assert opened_at is not None
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=60), price=2.0)
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=120), price=2.1)
    _mark(store, clock, token, pair, opened_at + timedelta(seconds=126), price=2.2)
    state = _state(store, int(candidate["shadow_cohort_id"]))
    assert state["status"] == "COMPLETE_NO_SHADOW"
    assert state["budget_rejected"]["reason"] == "shadow_account_cash_below_15_usd"
    assert state["budget_rejected"]["available_cash_usd"] == pytest.approx(10.0)
    assert "shadow_fill" not in state
    assert store.db.execute(
        "SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE "
        "definition_version=? AND arm_id=?", (version, CANDIDATE),
    ).fetchone()[0] == pytest.approx(-5.0)
    store.close()


def test_staged_probe_shadow_writeoff_records_zero_recovery_only_in_nested_state(
    tmp_path, monkeypatch,
):
    store, clock = _setup(tmp_path, monkeypatch, "staged-writeoff.sqlite3")
    store.register_chain_meme_staged_probe()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token, pair = _token("Writeoff"), str(Pubkey.new_unique())
    _enter(store, clock, token, pair)
    candidate = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?", (version, CANDIDATE, token.token_id),
    ).fetchone()
    opened_at = parse_time(candidate["opened_at"])
    assert opened_at is not None
    _open_shadow(store, clock, token, pair, opened_at, int(candidate["shadow_cohort_id"]))
    _mark(
        store, clock, token, pair, opened_at + timedelta(seconds=132),
        price=2.0, liquidity=99.0,
    )
    written = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, CANDIDATE, int(candidate["shadow_cohort_id"])),
    ).fetchone()
    assert written["status"] == "written_off"
    assert written["realized_pnl_usd"] == pytest.approx(-5.0)
    state = json.loads(written["capital_exit_state_json"])["staged_probe"]
    assert state["status"] == "SHADOW_CLOSED"
    assert state["shadow_exit"]["settlement_kind"] == "terminal_formal_writeoff"
    assert state["shadow_exit"]["shadow_net_recovery_usd"] == 0.0
    assert state["shadow_exit"]["shadow_net_pnl_usd"] == pytest.approx(-15.0)
    trades = store.db.execute(
        "SELECT side,net_cash_flow_usd,realized_pnl_usd FROM chain_meme_trader_trades "
        "WHERE definition_version=? AND arm_id=? ORDER BY id", (version, CANDIDATE),
    ).fetchall()
    assert [row["side"] for row in trades] == ["BUY", "WRITEOFF"]
    assert sum(float(row["net_cash_flow_usd"]) for row in trades) == pytest.approx(-5.0)
    store.close()
