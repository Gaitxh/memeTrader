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


def test_result_experiments_preserve_parents_and_single_slot_does_not_queue(tmp_path, monkeypatch):
    from memetrader.forward_patterns import experiment_policies, result_driven_policies
    from memetrader.capital_exits import EARN_THE_HOLD_POLICY
    parents = {p["arm_id"]: p for p in experiment_policies()}
    candidates = {p["arm_id"]: p for p in result_driven_policies()}
    serial = candidates["serial_conditional_runner_v1"]
    hybrid = candidates["sustained_breakout_earn_hold_v1"]
    assert serial["conditional_exit"] == parents[serial["source_arm_ids"][0]]["conditional_exit"]
    assert serial["take_profit"] == parents[serial["source_arm_ids"][0]]["take_profit"]
    assert hybrid["capital_exit_policy"] == dict(EARN_THE_HOLD_POLICY)
    assert "max_concurrent_positions" not in parents[serial["source_arm_ids"][0]]["entry_filter"]
    store, clock = _capital_store(tmp_path, monkeypatch, "result-experiments.sqlite3")
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    old = [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id")]
    assert store.register_chain_meme_result_experiments() == 2
    assert store.register_chain_meme_result_experiments() == 0
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id LIMIT 18")] == old
    start = clock[0]
    a, b = _new_token("A"), _new_token("B")
    pa, pb = str(Pubkey.new_unique()), str(Pubkey.new_unique())
    for seconds in (1, 2):
        _observe(store, clock, a, pa, start+timedelta(seconds=seconds), buys=4, sells=2)
    arm = "serial_conditional_runner_v1"
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=? AND status='open'", (arm,)).fetchone()[0] == 1
    for seconds in (3, 4):
        _observe(store, clock, b, pb, start+timedelta(seconds=seconds), buys=4, sells=2)
    row = store.db.execute("SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1").fetchone()
    assert json.loads(row[0])["outcomes"][arm] == "strategy_open_slot_limit"
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (arm,)).fetchone()[0] == 1
    # Entry-only fixture transition: releasing a slot must not replay blocked signals.
    store.db.execute("UPDATE chain_meme_trader_positions SET status='closed',closed_at=? WHERE arm_id=?", (iso(start+timedelta(seconds=5)), arm))
    store.db.commit()
    _observe(store, clock, b, pb, start+timedelta(seconds=6), buys=4, sells=2)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (arm,)).fetchone()[0] == 1
    _observe(store, clock, b, pb, start+timedelta(seconds=7), buys=4, sells=2)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (arm,)).fetchone()[0] == 2
    store.close()


def test_second_discussion_event_is_after_publication_next_frame_and_once_per_event(tmp_path, monkeypatch):
    store, clock = _capital_store(tmp_path, monkeypatch, "second-discussion.sqlite3")
    old = [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id")]
    assert store.register_chain_meme_second_discussion() == 8
    assert store.register_chain_meme_second_discussion() == 0
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id LIMIT 18")] == old
    token, pair = _new_token("MatureEvent"), str(Pubkey.new_unique())
    start = clock[0]
    arm = "event_reawakening_v1"
    def event(seconds, key):
        clock[0] = start + timedelta(seconds=seconds)
        return store.record_chain_meme_pattern_evidence(token.token_id, "", "authoritative_event",
            {"source_kind": "first_party", "trusted": True, "event_type": "official_listing",
             "contract_address": token.address}, observed_at=clock[0], source_key=key)
    def observe(seconds, price):
        clock[0] = start + timedelta(seconds=seconds)
        store.record_chain_meme_pattern_evidence(token.token_id, pair, "amountful_flow",
            {"complete": True, "net_quote_flow_usd": 5, "effective_breadth": 3},
            observed_at=clock[0], source_key=f"test-flow-{seconds}")
        snap = _snapshot(token, pair, clock[0], price=price)
        snap.raw["pair"]["pairCreatedAt"] = round((start - timedelta(hours=2)).timestamp()*1000)
        store.observe_chain_meme_pattern(token, snap, recorded_at=clock[0])
    def buys():
        return store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (arm,)).fetchone()[0]
    observe(1, 1)
    assert buys() == 0
    first = event(2, "official-event-one")
    observe(3, 1)
    observe(4, 1.1)
    assert buys() == 0
    observe(5, 1.2)
    assert buys() == 1
    sizes = {r["arm_id"]: (r["stake_usd"], r["paper_quantity_tokens"]) for r in store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE arm_id IN (?,?)",
        (arm, "surface_lifecycle_pipeline_v1"))}
    assert sizes[arm] == pytest.approx((20, 20/(1.2*1.04)))
    assert sizes["surface_lifecycle_pipeline_v1"] == pytest.approx((5, 5/(1.2*1.04)))
    feature = json.loads(store.db.execute("SELECT c.feature_json FROM chain_meme_trader_positions p JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id WHERE p.arm_id=?", (arm,)).fetchone()[0])
    assert feature["event_keys"][arm] == first
    # Entry-only fixture releases positions; the same event still must not buy again.
    store.db.execute("UPDATE chain_meme_trader_positions SET status='closed',closed_at=? WHERE arm_id IN (?,?)", (iso(start+timedelta(seconds=6)), arm, "surface_lifecycle_pipeline_v1"))
    store.db.commit()
    observe(7, 1.3)
    observe(8, 1.4)
    assert buys() == 1
    event(9, "official-event-two")
    observe(10, 1.5)
    observe(11, 1.6)
    assert buys() == 1
    observe(12, 1.7)
    assert buys() == 2
    store.close()


def test_exit_pairs_share_the_same_buy_fill_with_equal_size(tmp_path, monkeypatch):
    store, clock = _capital_store(tmp_path, monkeypatch, "paired-exits.sqlite3")
    assert store.register_chain_meme_second_discussion() == 8
    token, pair = _new_token("Paired"), str(Pubkey.new_unique())
    start = clock[0]
    clock[0] = start + timedelta(seconds=1)
    store.record_chain_meme_pattern_evidence(token.token_id, pair, "pool_surface",
        {"complete": True, "base_decimals": 6}, observed_at=clock[0], source_key="paired-surface")
    _record_actual_flow(store, clock, token, pair, start+timedelta(seconds=2), net_raw=5_000_000)
    _observe(store, clock, token, pair, start+timedelta(seconds=3), buys=4, sells=2)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id LIKE 'paired_%'").fetchone()[0] == 0
    _observe(store, clock, token, pair, start+timedelta(seconds=4), buys=4, sells=2)
    for kind in ("vault_hazard", "earn_the_hold", "failed_continuation_profit_lock"):
        rows = store.db.execute("SELECT shadow_cohort_id,source_entry_fill_id,opened_at,stake_usd,paper_quantity_tokens "
            "FROM chain_meme_trader_positions WHERE arm_id IN (?,?) ORDER BY arm_id",
            (f"paired_{kind}_candidate_v1", f"paired_{kind}_control_v1")).fetchall()
        assert len(rows) == 2
        assert tuple(rows[0]) == tuple(rows[1])
        assert rows[0]["stake_usd"] == 20
    store.close()


def test_market_entry_does_not_scan_historical_reservations_when_none_pending(tmp_path, monkeypatch):
    store, clock = _capital_store(tmp_path, monkeypatch, "empty-reservations.sqlite3")
    clock[0] += timedelta(seconds=1)
    token = _new_token("NoPending")
    store.upsert_token(token)
    snapshot = _snapshot(token, str(Pubkey.new_unique()), clock[0], buys=8, sells=2)
    snapshot.raw["pair"].update(txns={"m5": {"buys": 8, "sells": 2}}, volume={"m5": 500})
    store.add_snapshot(snapshot)
    statements = []
    store.db.set_trace_callback(statements.append)
    result = store.enroll_chain_meme_trader_v6(definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    store.db.set_trace_callback(None)
    assert result["admitted"] == 1
    assert not any("SELECT d.arm_id,COUNT(*) AS pending_count" in sql for sql in statements)
    buy = store.db.execute("SELECT net_cash_flow_usd FROM chain_meme_trader_trades WHERE side='BUY' LIMIT 1").fetchone()
    assert buy[0] == pytest.approx(-20)
    store.close()


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


def test_observed_buyer_real_store_seal_five_dollar_buy_distribution_and_next_pool_sell(tmp_path, monkeypatch):
    from memetrader.early_observed_buyers import ARM_ID
    from memetrader.market_flow import aggregate_market_frames
    store, clock = _capital_store(tmp_path, monkeypatch, "observed-buyer-lifecycle.sqlite3")
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    version, start = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, clock[0]
    parents = [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id")]
    assert store.register_chain_meme_evidence_completion_experiments() == 4
    assert store.register_chain_meme_evidence_completion_experiments() == 0
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id LIMIT 18")] == parents
    token, pair = _new_token("ObservedBuyer"), str(Pubkey.new_unique())
    store.upsert_token(token)
    windows, scan_ids = [], []
    def flow(lo, hi, buyers, selling=False):
        clock[0] = start + timedelta(seconds=hi+1)
        received = iso(clock[0])
        ident = dict(pool_address=pair, base_mint=token.address, quote_mint="USDC")
        amounts = [("BUY", who, 1_000_000) for who in buyers]
        if selling:
            amounts += [("SELL", "early", 200_000_000), ("SELL", "outside", 100_000_000)]
        rows = [dict(**ident, signature=f"{lo}-{i}", instruction_path="0.1", slot=100+hi,
            side=side, signer_address=who, base_amount_raw=1_000_000, quote_amount_raw=raw,
            amount_complete=True, amount_source="parsed_spl_transfer",
            block_time=iso(start+timedelta(seconds=lo+(i+1)/(len(amounts)+1)*(hi-lo))),
            observed_at=received, recorded_at=received) for i,(side,who,raw) in enumerate(amounts)]
        scan = dict(complete=True, coverage_complete=True, status="COMPLETE",
            coverage_start=iso(start+timedelta(seconds=lo)), coverage_end=iso(start+timedelta(seconds=hi)),
            observed_at=received, recorded_at=received, trades=rows)
        scan_id = store.record_chain_meme_pattern_evidence(token.token_id, pair, "participation_scan",
            scan, observed_at=clock[0], source_key=f"scan-{lo}")
        scan_ids.append(scan_id)
        windows.append(dict(window_start=scan["coverage_start"], window_end=scan["coverage_end"], trades=rows, scan=scan))
        aggregate = aggregate_market_frames(windows[-2:], resolver={**ident, "status":"verified",
            "base_decimals":6, "quote_decimals":6, "observed_at":received, "recorded_at":received},
            decision_at=received, quote_conversion=dict(quote_mint="USDC", usd_per_quote=1.0,
                observed_at=received, recorded_at=received, max_age_seconds=30))
        payload = {**aggregate["windows"][-1], **aggregate, "token_id":token.token_id,
                   **ident, "source_evidence_ids":scan_ids[-2:],
                   "conversion_basis":"USDC_unit_accounting_reference_not_executable_fill"}
        store.record_chain_meme_pattern_evidence(token.token_id, pair, "amountful_flow", payload,
            observed_at=clock[0], source_key=f"flow-{lo}")
        store.seal_chain_meme_observed_buyers(token.token_id, pair, aggregate["windows"][-1], scan_id)
    flow(1,11,["early","first2","first3"])
    sealed = store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence WHERE kind='observed_buyer_cohort'").fetchone()[0]
    flow(11,21,["late1","late2","late3"])
    cohorts = store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence WHERE kind='observed_buyer_cohort'").fetchall()
    assert len(cohorts) == 1 and cohorts[0][0] == sealed
    assert json.loads(sealed)["buyer_addresses"] == ["early","first2","first3"]
    _observe(store, clock, token, pair, start+timedelta(seconds=22), buys=4, sells=2)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=?",(ARM_ID,)).fetchone()[0] == 0
    _observe(store, clock, token, pair, start+timedelta(seconds=23), buys=4, sells=2)
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?",(ARM_ID,)).fetchone()
    assert position["stake_usd"] == 5 and position["remaining_quantity_tokens"] == pytest.approx(5/2.08)
    def mark(second, liquidity):
        clock[0] = start+timedelta(seconds=second)
        store.upsert_chain_meme_trader_market_mark(token,
            _snapshot(token,pair,clock[0],liquidity=liquidity),recorded_at=clock[0])
    mark(35,1000)
    flow(54,64,[f"warm{i}" for i in range(8)])
    flow(64,74,[f"warm{i}" for i in range(8)])
    for lo,hi,breadth in [(74,84,4),(84,94,2)]:
        flow(lo,hi,[f"new{i}" for i in range(breadth)],selling=True)
        mark(hi+1,800)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
        pending = store.db.execute("SELECT pending_mark_id FROM chain_meme_trader_positions WHERE arm_id=?",(ARM_ID,)).fetchone()[0]
        assert (pending is not None) == (hi == 94)
    pending_mark = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?",(pending,)).fetchone()
    assert pending_mark["status"] == "pending" and pending_mark["reason"] == "dynamic_distribution_confirmed"
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'",(ARM_ID,)).fetchone()[0] == 0
    mark(96,800)
    store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
    sell = store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'",(ARM_ID,)).fetchone()
    assert sell is not None and sell["net_cash_flow_usd"] == pytest.approx(5/2.08*2*.96)
    assert store.db.execute("SELECT status FROM chain_meme_trader_positions WHERE arm_id=?",(ARM_ID,)).fetchone()[0] == "closed"
    assert [tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions ORDER BY id LIMIT 18")] == parents
    store.close()


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


def test_fast_stop_real_closed_ledger_next_frame_five_dollars_and_once(tmp_path, monkeypatch):
    """A completed natural stop creates a new episode, never repairs its old PNL."""
    from memetrader.capital_entry import opportunity_signal
    from memetrader.capital_policies import opportunity_policies

    store, clock = _capital_store(tmp_path, monkeypatch, "fast-stop-natural.sqlite3")
    # Trade recorded_at uses models.iso(), so advance the same clock there too.
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    assert store.register_chain_meme_opportunity_experiments() == 4
    version, start = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, clock[0]
    token, pair = _new_token("FastStop"), str(Pubkey.new_unique())
    parent, arm = "authoritative_event_shock_v1", "fast_stop_reclaim_v1"
    clock[0] = start + timedelta(seconds=1)
    store.record_chain_meme_pattern_evidence(token.token_id, "", "authoritative_event",
        {"source_kind": "first_party", "trusted": True, "event_type": "official_listing",
         "contract_address": token.address}, observed_at=clock[0], source_key="fast-stop-parent-event")
    for seconds in (2, 3):
        _observe(store, clock, token, pair, start + timedelta(seconds=seconds), price=2)
    original = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (parent,)).fetchone()
    assert original is not None and original["status"] == "open"

    def market(seconds, price):
        clock[0] = start + timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pair, clock[0], price=price), recorded_at=clock[0])
        return store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=clock[0], token_ids=[token.token_id])

    def buys():
        return store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades "
            "WHERE arm_id=? AND side='BUY'", (arm,)).fetchone()[0]

    assert market(4, 1.4) == 1
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'").fetchone()[0] == 0
    assert market(5, 1.4) == 1
    closed = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (parent,)).fetchone()
    assert closed["status"] == "closed" and "hard_stop" in closed["close_reason"]
    expected_loss = 20 / 2.08 * 1.4 * .96 - 20
    assert closed["realized_pnl_usd"] == pytest.approx(expected_loss)
    old_trades = [tuple(r) for r in store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE arm_id=? ORDER BY id", (parent,))]
    assert len(old_trades) == 2
    stop = store._pattern_recent_clean_stop(token.token_id, pair, clock[0], iso(start))
    assert stop["clean"] is True
    assert (stop["entry_price"], stop["stop_price"], stop["stop_liquidity"]) == (2, 1.4, 1000)
    assert store.db.execute("SELECT side FROM chain_meme_trader_trades WHERE id=?",
                            (stop["stop_trade_id"],)).fetchone()[0] == "SELL"
    assert store.db.execute("SELECT market_post_price_usd FROM chain_meme_trader_marks WHERE id=?",
                            (stop["stop_mark_id"],)).fetchone()[0] == 1.4

    # Four post-stop observations, 50 seconds of structure, exactly 60 seconds cooling.
    for seconds, price in ((15, 1.45), (30, 1.6), (45, 1.75), (65, 1.85)):
        _observe(store, clock, token, pair, start + timedelta(seconds=seconds), price=price)
        assert buys() == 0
    features = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert arm in features["ready_arm_ids"]
    _observe(store, clock, token, pair, start + timedelta(seconds=66), price=1.9)
    assert buys() == 1
    new = store.db.execute("SELECT p.*,c.feature_json FROM chain_meme_trader_positions p "
        "JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id WHERE p.arm_id=?", (arm,)).fetchone()
    assert new["stake_usd"] == 5
    assert new["opened_at"] == iso(start + timedelta(seconds=66))
    assert new["paper_quantity_tokens"] == pytest.approx(5 / (1.9 * 1.04))
    assert json.loads(new["feature_json"])["event_keys"][arm] == stop["evidence_id"]

    # Close the new arm normally, then confirm the same original stop cannot be consumed again.
    assert market(67, 1.2) == 1
    assert market(68, 1.2) == 1
    for seconds, price in ((70, 1.90), (85, 1.92), (100, 1.94), (115, 1.96), (116, 1.98)):
        _observe(store, clock, token, pair, start + timedelta(seconds=seconds), price=price)
    assert buys() == 1
    features = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert features["outcomes"][arm] == "event_already_consumed"
    assert [tuple(r) for r in store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE arm_id=? ORDER BY id", (parent,))] == old_trades
    assert store.db.execute("SELECT realized_pnl_usd FROM chain_meme_trader_positions WHERE arm_id=?",
                            (parent,)).fetchone()[0] == pytest.approx(expected_loss)

    # The pure boundary refuses a stop whose accounting evidence is not clean.
    policy = next(p for p in opportunity_policies() if p["arm_id"] == arm)
    frames = [{"observed_at": iso(start + timedelta(seconds=s)), "price": p, "liquidity": 1000}
              for s, p in ((70, 1.90), (85, 1.92), (100, 1.94), (115, 1.96))]
    assert opportunity_signal(frames, policy, decision=clock[0], activated=start,
                              context={"recent_stop": {**stop, "clean": False}}) == (
                                  False, "awaiting_clean_recent_natural_stop")
    store.close()
