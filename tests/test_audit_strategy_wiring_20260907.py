"""Focused Store regressions for the 2026-09-07 static-wiring findings.

Only pytest temporary Stores are written. Policy factories and the normal funding
revision path build the effective rules; no production database or policy is read.
"""
from datetime import timedelta
import json

import pytest
from solders.pubkey import Pubkey

from memetrader.forward_patterns import experiment_policies, result_driven_policies
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


LOSS_PAIR = ("l0_continuation_failure_candidate_v1", "l0_continuation_failure_control_v1")
PROFIT_PAIR = ("l0_profit_lock_candidate_v1", "l0_profit_lock_control_v1")


@pytest.fixture
def revised_store(tmp_path, monkeypatch):
    stores = []

    def create(extra_arms=()):
        # Also keep activation ahead of any unpatched source-factory wall clock.
        clock = [utcnow() + timedelta(days=1)]
        monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
        monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
        old = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
        version = Store.CHAIN_MEME_TRADER_FINAL_V002_PERIOD_VERSION
        monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", old)
        store = Store(tmp_path / f"wiring-{len(stores)}.sqlite3", initial_cash_usd=1000)
        stores.append(store)
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_l0_experiments()
        for policy in experiment_policies() + result_driven_policies():
            if policy["arm_id"] in extra_arms:
                store.append_chain_meme_trader_policy(policy)
        clock[0] += timedelta(seconds=1)
        store.activate_chain_meme_trader_funding_epoch(
            target_version=version, source_version=old, at=clock[0],
            apply_strategy_revisions=True,
        )
        monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", version)
        store.activate_chain_market_entry_post_observation()
        definition = store._chain_meme_trader_effective_definition(
            version, store._chain_meme_trader_registration(version)["definition_json"]
        )
        return store, clock, version, {p["arm_id"]: p for p in definition["policies"]}

    yield create
    for store in stores:
        store.close()


def _token(chain="solana"):
    return TokenCandidate(chain, str(Pubkey.new_unique()) if chain == "solana"
                          else "0x" + "12" * 20, "Wiring", "WIRE", source="fixture")


def _snapshot(token, pair, at, *, price=1.0, liquidity=10000.0, volume=2000.0, age=60):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100000.0, volume, 6, 4,
        observed_at=at, ingested_at=at, provider="dexscreener",
        raw={"pair": {"chainId": token.chain, "dexId": "pumpswap",
            "pairAddress": pair, "pairCreatedAt": round((at-timedelta(seconds=age)).timestamp()*1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity},
            "txns": {"m5": {"buys": 6, "sells": 4}, "h1": {"buys": 6, "sells": 4}},
            "volume": {"m5": volume, "h1": volume}}},
    )


def _enroll(store, clock, version, token, pair):
    clock[0] += timedelta(seconds=1)
    store.upsert_token(token, seen_at=clock[0])
    store.add_snapshot(_snapshot(token, pair, clock[0]))
    return store.enroll_chain_meme_trader_v6(definition_version=version)


def _receipt(store, clock, token, pair, *, price=1.0):
    clock[0] += timedelta(seconds=1)
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pair, clock[0], price=price), recorded_at=clock[0]
    )


def _position(store, version, arm, token):
    return store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?", (version, arm, token.token_id)
    ).fetchone()


def _mark(store, clock, version, token, pair, *, seconds=6, price=1.0, liquidity=10000.0):
    clock[0] += timedelta(seconds=seconds)
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, clock[0], price=price, liquidity=liquidity),
        recorded_at=clock[0],
    )
    store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=clock[0], token_ids=[token.token_id]
    )


@pytest.mark.parametrize("arm", [
    "experiment_sustained_breakout_candidate_v1", "sustained_breakout_earn_hold_v1",
])
def test_nullable_volume_waits_without_aborting_store_observer(revised_store, arm):
    control = "experiment_sustained_breakout_control_v1"
    store, clock, version, policies = revised_store((arm, control))
    assert policies[arm]["entry_family"] == "sustained_breakout"
    assert policies[arm]["entry_filter"]["control"] is False
    frozen_hash = policies[arm]["behavior_contract_hash"]
    frozen_definition = store._chain_meme_trader_registration(version)["definition_json"]
    token, pair = _token(), str(Pubkey.new_unique())

    def observe(price, volume):
        clock[0] += timedelta(seconds=15)
        return store.observe_chain_meme_pattern(
            token, _snapshot(token, pair, clock[0], price=price, volume=volume, age=1000),
            recorded_at=clock[0],
        )

    for price in (1.0, 1.1, 1.25):
        observe(price, None)
    outcome = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE definition_version=? AND token_id=? AND reason='pattern_observation' "
        "ORDER BY id DESC LIMIT 1", (version, token.token_id)
    ).fetchone()[0])
    assert arm not in outcome["ready_arm_ids"]
    assert control in outcome["ready_arm_ids"]
    observe(1.26, None)
    assert _position(store, version, arm, token) is None
    assert _position(store, version, control, token) is not None

    # Actual later complete frames can form a fresh signal, then a later BUY.
    for price in (1.30, 1.35, 1.50, 1.51):
        observe(price, 2500.0)
    assert _position(store, version, arm, token) is not None
    assert store._chain_meme_trader_registration(version)["definition_json"] == frozen_definition
    current = store._chain_meme_trader_effective_definition(version, frozen_definition)
    assert next(p for p in current["policies"] if p["arm_id"] == arm)["behavior_contract_hash"] == frozen_hash


@pytest.mark.parametrize("partial_price,covered", [(1.5, False), (2.3, True)])
def test_l0_profit_lock_uses_actual_partial_cash_not_tp_or_legacy_flag(
    revised_store, partial_price, covered,
):
    store, clock, version, policies = revised_store()
    arm = PROFIT_PAIR[0]
    assert policies[arm]["exit_family"] == "l0_profit_lock"
    assert policies[arm]["take_profit"] == [{"return": .25, "fraction_of_remaining": .5}]
    token, pair = _token(), str(Pubkey.new_unique())
    _enroll(store, clock, version, token, pair)
    _receipt(store, clock, token, pair)
    initial = _position(store, version, arm, token)
    assert initial is not None and initial["stake_usd"] == 20
    _mark(store, clock, version, token, pair, seconds=60, price=1.5)
    assert _position(store, version, arm, token)["pending_mark_id"] is not None
    _mark(store, clock, version, token, pair, price=partial_price)
    partial = _position(store, version, arm, token)
    assert partial["status"] == "open" and partial["next_tp_index"] == 1
    assert partial["principal_recovered"] == 0  # No retrofit of another family's persisted flag.
    assert (partial["realized_proceeds_usd"] >= partial["stake_usd"]) is covered
    sells = store.db.execute(
        "SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades "
        "WHERE definition_version=? AND arm_id=? AND token_id=? AND side='SELL'",
        (version, arm, token.token_id),
    ).fetchone()[0]
    assert partial["realized_proceeds_usd"] == pytest.approx(sells)
    for price, liquidity in ((partial_price, 10000), (partial_price-.025, 9900),
                             (partial_price-.05, 9800)):
        _mark(store, clock, version, token, pair, price=price, liquidity=liquidity)
    position = _position(store, version, arm, token)
    if not covered:
        assert position["pending_mark_id"] is None
        assert position["status"] == "open"
        return
    mark = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?",
                            (position["pending_mark_id"],)).fetchone()
    assert mark is not None and mark["action"] == "CAPITAL_EXIT"
    assert mark["reason"] == "l0_two_frame_profit_lock"
    assert position["status"] == "open"  # Trigger is not the fill.
    _mark(store, clock, version, token, pair, price=partial_price-.06, liquidity=9700)
    assert _position(store, version, arm, token)["status"] == "closed"


def test_old_l0_mixed_case_evm_pool_reaches_both_exit_adapters(revised_store):
    store, clock, version, policies = revised_store()
    token, pair = _token("bsc"), "0x" + "aB" * 20
    _enroll(store, clock, version, token, pair)
    _receipt(store, clock, token, pair)
    arm = LOSS_PAIR[0]
    assert _position(store, version, arm, token) is not None
    revised = [row[0] for row in store.db.execute(
        "SELECT arm_id FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=?",
        (version, token.token_id),
    ) if policies[row[0]].get("revision_exit_kind") == "l0_loss_deterioration"]
    assert revised  # Cover revision_loss_exit substate as well as capital_exit_kind.
    targets = [arm, revised[0]]
    for seconds, price, liquidity in ((60, 1.0, 10000), (6, .99, 9900), (6, .98, 9800)):
        _mark(store, clock, version, token, pair.lower(), seconds=seconds,
              price=price, liquidity=liquidity)
    for target in targets:
        position = _position(store, version, target, token)
        mark = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?",
                                (position["pending_mark_id"],)).fetchone()
        assert mark is not None and mark["reason"] == "l0_loss_deterioration_armed"
        assert position["status"] == "open"
    _mark(store, clock, version, token, pair.lower(), price=.975, liquidity=9700)
    assert all(_position(store, version, target, token)["status"] == "closed" for target in targets)
    assert _position(store, version, LOSS_PAIR[1], token)["status"] == "open"


@pytest.mark.parametrize("pair_arms", [LOSS_PAIR, PROFIT_PAIR])
@pytest.mark.parametrize("blocked_at", ["signal", "receipt"])
def test_main_l0_pair_requires_both_accounts_at_signal_and_receipt(
    revised_store, monkeypatch, pair_arms, blocked_at,
):
    store, clock, version, policies = revised_store()
    assert all(policies[a]["entry_match_mode"] == "exact_entry_family" for a in pair_arms)
    assert policies[pair_arms[0]]["paired_entry_group"] == policies[pair_arms[1]]["paired_entry_group"]
    balances = {pair_arms[0]: -981.0} if blocked_at == "signal" else {}
    # Match the existing first-receipt cash-race fixture: keep Store admission,
    # decisions, pending intents and projection real; inject only account net flow.
    monkeypatch.setattr(store, "_chain_meme_trader_effective_net_flows", lambda version: dict(balances))
    token, pair = _token(), str(Pubkey.new_unique())
    _enroll(store, clock, version, token, pair)
    if blocked_at == "signal":
        decisions = {r["arm_id"]: r["status"] for r in store.db.execute(
            "SELECT arm_id,status FROM chain_meme_trader_entry_decisions "
            "WHERE definition_version=? AND token_id=?", (version, token.token_id)
        )}
        assert all(decisions[a] == "rejected" for a in pair_arms)
    else:
        balances[pair_arms[0]] = -981.0
    _receipt(store, clock, token, pair)
    assert all(_position(store, version, arm, token) is None for arm in pair_arms)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=?",
        (version, token.token_id),
    ).fetchone()[0] > 0  # Unpaired eligible accounts are not blocked by this pair.
    balances.clear()
    _receipt(store, clock, token, pair, price=.9)
    assert all(_position(store, version, arm, token) is None for arm in pair_arms)
    # A different forward opportunity with both funded still fills one shared cohort.
    other, other_pair = _token(), str(Pubkey.new_unique())
    _enroll(store, clock, version, other, other_pair)
    _receipt(store, clock, other, other_pair)
    positions = [_position(store, version, arm, other) for arm in pair_arms]
    assert all(position is not None for position in positions)
    assert len({position["source_entry_fill_id"] for position in positions}) == 1
