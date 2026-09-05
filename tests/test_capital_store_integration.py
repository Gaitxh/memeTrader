from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def _new_token(name="Capital"):
    return TokenCandidate("solana", str(Pubkey.new_unique()), name, name[:4], source="fixture")


def _snapshot(token, pair, when, *, price=2.0, liquidity=1000.0, buys=1, sells=1):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000, 500, buys, sells,
        observed_at=when, ingested_at=when, provider="dexscreener",
        raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "dexId": "pumpswap",
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity},
        }},
    )


def _observe(store, clock, token, pair, when, **changes):
    clock[0] = when
    return store.observe_chain_meme_pattern(
        token, _snapshot(token, pair, when, **changes), recorded_at=when,
    )


def _capital_store(tmp_path, monkeypatch, name):
    store = Store(tmp_path / name, initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    assert store.register_chain_meme_capital_experiments() == 18
    assert store.register_chain_meme_capital_experiments() == 0
    return store, clock


def _record_actual_flow(store, clock, token, pair, when, *, net_raw=-1_000_000):
    clock[0] = when
    payload = {
        "complete": True, "scan_complete": True,
        "future_data_rejected": False, "usd_conversion_complete": True,
        "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
        "decision_at": iso(when), "token_id": token.token_id,
        "pool_address": pair, "quote_mint": "USDC",
        "net_quote_flow_raw": net_raw, "effective_breadth": 2,
        "top3_notional_share": .7, "sell_quote_notional_usd": 2,
        "resolver": {
            "status": "verified", "pool_address": pair,
            "base_mint": token.address, "quote_mint": "USDC",
            "base_decimals": 6, "quote_decimals": 6,
            "observed_at": iso(when - timedelta(seconds=2)),
            "recorded_at": iso(when - timedelta(seconds=1.9)),
        },
        "quote_conversion": {
            "quote_mint": "USDC", "usd_per_quote": 1,
            "observed_at": iso(when - timedelta(seconds=2)),
            "recorded_at": iso(when - timedelta(seconds=1.9)),
            "max_age_seconds": 15,
        },
        # Counts are diagnostics only; the decision amount comes from raw transfers.
        "buy_count": 999, "sell_count": 1,
    }
    return store.record_chain_meme_pattern_evidence(
        token.token_id, pair, "amountful_flow", payload,
        observed_at=when - timedelta(milliseconds=200),
        source_key=f"flow:{token.token_id}:{iso(when)}",
    )


def test_registers_18_idempotently_without_rewriting_old_146_or_frontiers(tmp_path, monkeypatch):
    store = Store(tmp_path / "registration.sqlite3", initial_cash_usd=1000)
    activation = store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store.register_chain_meme_trader_cost_coverage_scaleout()
    assert store.register_chain_meme_pattern_experiments() == 18
    registration_json = store._chain_meme_trader_registration(version)["definition_json"]
    old_definition = store._chain_meme_trader_effective_definition(version, registration_json)
    assert len(old_definition["policies"]) == 146
    old_policies = {p["arm_id"]: p for p in old_definition["policies"]}
    old_additions = [tuple(row) for row in store.db.execute(
        "SELECT arm_id,activation_snapshot_id,activation_evaluation_id,behavior_contract_hash "
        "FROM chain_meme_trader_policy_additions WHERE definition_version=? ORDER BY id", (version,)
    )]

    token = _new_token("Frontier")
    store.upsert_token(token)
    snapshot_id = store.add_snapshot(_snapshot(token, str(Pubkey.new_unique()), clock[0]))
    assert snapshot_id > int(activation["activation_snapshot_id"])
    assert store.register_chain_meme_capital_experiments() == 18
    assert store.register_chain_meme_capital_experiments() == 0

    assert store._chain_meme_trader_registration(version)["definition_json"] == registration_json
    effective = store._chain_meme_trader_effective_definition(version, registration_json)
    assert len(effective["policies"]) == 164
    assert {p["arm_id"]: p for p in effective["policies"] if p["arm_id"] in old_policies} == old_policies
    assert [tuple(row) for row in store.db.execute(
        "SELECT arm_id,activation_snapshot_id,activation_evaluation_id,behavior_contract_hash "
        "FROM chain_meme_trader_policy_additions WHERE definition_version=? "
        "AND arm_id NOT IN (SELECT arm_id FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? ORDER BY id DESC LIMIT 18) ORDER BY id", (version, version)
    )] == old_additions
    capital_rows = store.db.execute(
        "SELECT activation_snapshot_id,behavior_contract_hash FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? ORDER BY id DESC LIMIT 18", (version,)
    ).fetchall()
    assert len(capital_rows) == 18
    assert {row["activation_snapshot_id"] for row in capital_rows} == {snapshot_id}
    assert all(row["behavior_contract_hash"] for row in capital_rows)
    store.close()


def test_authoritative_event_next_frame_and_direct_lp_use_separate_20_and_5_ledgers(
    tmp_path, monkeypatch,
):
    store, clock = _capital_store(tmp_path, monkeypatch, "entry.sqlite3")
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    start = clock[0]

    event_token, event_pair = _new_token("Event"), str(Pubkey.new_unique())
    clock[0] = start + timedelta(seconds=1)
    event_id = store.record_chain_meme_pattern_evidence(
        event_token.token_id, "", "authoritative_event", {
            "source_kind": "first_party", "trusted": True,
            "event_type": "official_listing", "contract_address": event_token.address,
            "source_url": "https://www.okx.com/help/fixture",
        }, observed_at=clock[0], source_key="official:event:fixture",
    )
    first = start + timedelta(seconds=2)
    assert _observe(store, clock, event_token, event_pair, first) == 0
    first_features = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE token_id=? ORDER BY id DESC LIMIT 1", (event_token.token_id,)
    ).fetchone()[0])
    assert "authoritative_event_shock_v1" in first_features["ready_arm_ids"]
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE token_id=?", (event_token.token_id,)
    ).fetchone()[0] == 0
    second = first + timedelta(seconds=1)
    assert _observe(store, clock, event_token, event_pair, second) == 1

    direct_token, direct_pair = _new_token("Direct"), str(Pubkey.new_unique())
    clock[0] = second + timedelta(seconds=1)
    surface_id = store.record_chain_meme_pattern_evidence(
        direct_token.token_id, direct_pair, "pool_surface", {
            "status": "RESOLVED", "complete": True, "surface": "NORMAL_DIRECT",
            "pool_address": direct_pair, "base_mint": direct_token.address,
            "base_decimals": 6, "pool_supply_share": .75,
            "max_single_controller_withdraw_fraction_upper_bound": .05,
            "mint_authority": None, "freeze_authority": None,
        }, observed_at=clock[0], source_key="surface:direct:fixture",
    )
    direct_first = clock[0] + timedelta(seconds=1)
    assert _observe(store, clock, direct_token, direct_pair, direct_first) == 0
    direct_features = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE token_id=? ORDER BY id DESC LIMIT 1", (direct_token.token_id,)
    ).fetchone()[0])
    assert direct_features["ready_arm_ids"] == ["direct_lp_float_constrained_v1"]
    assert direct_features["capital_evidence_ids"]["surface"] == surface_id
    direct_second = direct_first + timedelta(seconds=1)
    assert _observe(store, clock, direct_token, direct_pair, direct_second) == 1

    positions = {row["arm_id"]: row for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE token_id IN (?,?)",
        (event_token.token_id, direct_token.token_id),
    )}
    event = positions["authoritative_event_shock_v1"]
    direct = positions["direct_lp_float_constrained_v1"]
    assert event["opened_at"] == iso(second)
    assert event["entry_execution_price_usd"] == pytest.approx(2.08)
    assert event["paper_quantity_tokens"] == pytest.approx(20 / 2.08)
    assert direct["entry_execution_price_usd"] == pytest.approx(2.08)
    assert direct["paper_quantity_tokens"] == pytest.approx(5 / 2.08)
    buys = {row["arm_id"]: row for row in store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE side='BUY' AND token_id IN (?,?)",
        (event_token.token_id, direct_token.token_id),
    )}
    assert buys["authoritative_event_shock_v1"]["gross_usd"] == pytest.approx(20)
    assert buys["direct_lp_float_constrained_v1"]["gross_usd"] == pytest.approx(5)
    flows = store._chain_meme_trader_effective_net_flows(version)
    assert 1000 + flows["authoritative_event_shock_v1"] == pytest.approx(980)
    assert 1000 + flows["direct_lp_float_constrained_v1"] == pytest.approx(995)
    assert event_id is not None
    store.close()


def test_wave_reentry_requires_closed_600_seconds_and_does_not_duplicate_while_open(
    tmp_path, monkeypatch,
):
    store, clock = _capital_store(tmp_path, monkeypatch, "wave.sqlite3")
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    activated = clock[0]
    token, pair = _new_token("Wave"), str(Pubkey.new_unique())
    store.upsert_token(token)
    opened, closed = activated + timedelta(seconds=1), activated + timedelta(seconds=610)
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts(definition_version,token_id,entry_family,"
            "source_snapshot_id,pair_address,decided_at,episode_no,feature_json) "
            "VALUES(?,?, 'broad_launch',1,?,?,1,'{}')",
            (version, token.token_id, pair, iso(opened)),
        )
        old_cohort = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,token_id,"
            "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,amount_raw,"
            "initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at,closed_at,close_reason) "
            "VALUES(?,?,?, ?,900001,1,1,1,1.04,20,0,'0','20000000000',20,1,'closed',?,?,'fixture')",
            (version, "wave_reset_reentry_v1", old_cohort, token.token_id, iso(opened), iso(closed)),
        )

    episode = activated + timedelta(seconds=1211)
    assert _observe(store, clock, token, pair, episode, price=1.0) == 0
    assert _observe(store, clock, token, pair, episode + timedelta(seconds=1), price=1.05) == 0
    trigger = episode + timedelta(seconds=2)
    assert _record_actual_flow(store, clock, token, pair, trigger, net_raw=2_000_000)
    assert _observe(store, clock, token, pair, trigger, price=1.20) == 0
    fill = trigger + timedelta(seconds=1)
    assert _observe(store, clock, token, pair, fill, price=1.25) == 1
    assert _observe(store, clock, token, pair, fill + timedelta(seconds=1), price=1.30) == 0

    positions = store.db.execute(
        "SELECT status,opened_at FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id='wave_reset_reentry_v1' AND token_id=? ORDER BY opened_at",
        (version, token.token_id),
    ).fetchall()
    assert [(row["status"], row["opened_at"]) for row in positions] == [
        ("closed", iso(opened)), ("open", iso(fill)),
    ]
    store.close()


def test_earn_exit_is_pending_until_new_original_pool_frame_and_uses_both_4pct_costs(
    tmp_path, monkeypatch,
):
    store, clock = _capital_store(tmp_path, monkeypatch, "earn.sqlite3")
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token, pair = _new_token("Earn"), str(Pubkey.new_unique())
    store.upsert_token(token)
    opened = clock[0] + timedelta(seconds=1)
    clock[0] = opened
    entry_id = store.add_snapshot(_snapshot(token, pair, opened, price=2.0, liquidity=1000))
    quantity = 20 / 2.08
    amount = str(round(quantity * 1_000_000_000))
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts(definition_version,token_id,entry_family,"
            "source_snapshot_id,pair_address,decided_at,episode_no,feature_json) "
            "VALUES(?,?, 'broad_launch',?,?,?,1,'{}')",
            (version, token.token_id, entry_id, pair, iso(opened)),
        )
        cohort = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades(definition_version,arm_id,shadow_cohort_id,token_id,"
            "side,gross_usd,net_cash_flow_usd,reason,created_at,recorded_at) "
            "VALUES(?,?,?,?,'BUY',20,-20,'fixture',?,?)",
            (version, "earn_the_hold_v1", cohort, token.token_id, iso(opened), iso(opened)),
        )
        buy_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,token_id,"
            "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,amount_raw,"
            "initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at,capital_exit_state_json) "
            "VALUES(?,?,?,?,?,1,?,2,2.08,?,?,?,?,20,2,'open',?,'{}')",
            (version, "earn_the_hold_v1", cohort, token.token_id, buy_id, entry_id,
             quantity, quantity, amount, amount, iso(opened)),
        )

    trigger = opened + timedelta(seconds=121)
    assert _record_actual_flow(store, clock, token, pair, trigger, net_raw=-2_000_000)
    clock[0] = trigger
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, trigger, price=2.0, liquidity=1000), recorded_at=trigger,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=trigger, token_ids=[token.token_id],
    ) == 1
    mark = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE arm_id='earn_the_hold_v1'"
    ).fetchone()
    assert (mark["action"], mark["reason"], mark["status"]) == (
        "CAPITAL_EXIT", "earn_the_hold_deadline_failed", "pending",
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'"
    ).fetchone()[0] == 0
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=trigger, token_ids=[token.token_id],
    ) == 0

    wrong_at = trigger + timedelta(seconds=1)
    wrong_pair = str(Pubkey.new_unique())
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, wrong_pair, wrong_at, price=9.0), recorded_at=wrong_at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=wrong_at, token_ids=[token.token_id],
    ) == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'"
    ).fetchone()[0] == 0

    fill_at = trigger + timedelta(seconds=2)
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair, fill_at, price=2.0, liquidity=1000), recorded_at=fill_at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=fill_at, token_ids=[token.token_id],
    ) == 1
    expected_gross = 20 * (2 / 2.08) * .96
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE arm_id='earn_the_hold_v1' AND side='SELL'"
    ).fetchone()
    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE arm_id='earn_the_hold_v1'"
    ).fetchone()
    assert sell["gross_usd"] == pytest.approx(expected_gross)
    assert sell["net_cash_flow_usd"] == pytest.approx(expected_gross)
    assert position["status"] == "closed"
    assert position["realized_pnl_usd"] == pytest.approx(expected_gross - 20)
    assert store.db.execute(
        "SELECT adapter FROM chain_meme_trader_fills WHERE arm_id='earn_the_hold_v1'"
    ).fetchone()[0] == "dexscreener-market-paper/v1"
    cash = 1000 + store._chain_meme_trader_effective_net_flows(version)["earn_the_hold_v1"]
    assert cash == pytest.approx(1000 - 20 + expected_gross)
    store.close()
