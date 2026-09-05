import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.capital_policies import capital_policies
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def setup(store, monkeypatch, *, pending=True, fraction=.4):
    store.activate_chain_meme_trader_funded_period()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    policy = next(p for p in capital_policies() if p["capital_exit_kind"] == "executable_recovery_decay")
    store.append_chain_meme_trader_policy(policy)
    tick = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: tick[0])
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "T", "T")
    store.upsert_token(token)
    pair = str(Pubkey.new_unique())
    with store.db:
        store.db.execute("INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,decided_at,episode_no,feature_json) "
            "VALUES(?,?,?,1,?,?,1,'{}')", (version, token.token_id, "broad_launch", pair, iso(tick[0])))
        cohort = store.db.execute("SELECT last_insert_rowid()").fetchone()[0]
        store.db.execute("INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,baseline_quote_result_id,"
            "entry_snapshot_id,entry_signal_price_usd,entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at,capital_exit_state_json) "
            "VALUES(?,?,?,?,?,1,1,2,?,10.1234567,10.1234567,'10000000000','10000000000',20,3,'open',?,?)",
            (version, policy["arm_id"], cohort, token.token_id, cohort, 20 / 10.1234567, iso(tick[0]), json.dumps({"bad_streak": 2})))
        store.db.execute("INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,net_cash_flow_usd,reason,created_at) "
            "VALUES(?,?,?,?,'BUY',20,-20,'fixture',?)", (version, policy["arm_id"], cohort, token.token_id, iso(tick[0])))
    tick[0] += timedelta(seconds=1)
    store.record_chain_meme_pattern_evidence(token.token_id, pair, "pool_surface",
        dict(status="RESOLVED", complete=True, pool_address=pair, base_mint=token.address, base_decimals=6),
        observed_at=tick[0], source_key="surface")
    mark_id = None
    if pending:
        with store.db:
            store.db.execute("INSERT INTO chain_meme_trader_marks(definition_version,arm_id,shadow_cohort_id,"
                "recorded_at,action,reason,sell_amount_raw,market_pair_address,trigger_evidence_json,status) "
                "VALUES(?,?,?,?,'TAKE_PROFIT_1','capital_fixture',?,?,?,'pending')",
                (version, policy["arm_id"], cohort, iso(tick[0]), str(round(10**10 * fraction)), pair,
                 json.dumps({"required_fill": "post_trigger_amount_specific_quote"})))
            mark_id = store.db.execute("SELECT last_insert_rowid()").fetchone()[0]
            store.db.execute("UPDATE chain_meme_trader_positions SET pending_mark_id=?", (mark_id,))
    tick[0] += timedelta(seconds=1)
    return tick, token, pair, mark_id


def quote_for(store, task, when, minimum=12_000_000):
    return dict(provider="jupiter", input_mint=task["token_id"].partition(":")[2], output_mint=store.JUPITER_USDC_MINT,
                in_amount=str(task["input_amount_raw"]), out_amount=str(minimum + 500_000),
                other_amount_threshold=str(minimum), slippage_bps=400,
                requested_at=iso(when), completed_at=iso(when + timedelta(milliseconds=100)),
                route_plan=[dict(amm_key=task["pair_address"], input_mint=task["token_id"].partition(":")[2],
                                 output_mint=store.JUPITER_USDC_MINT, in_amount=str(task["input_amount_raw"]))])


def test_real_amount_partial_exit_cost_no_double_slippage_and_duplicate(tmp_path, monkeypatch):
    store = Store(tmp_path / "partial.sqlite3", initial_cash_usd=1000)
    tick, _, _, mark_id = setup(store, monkeypatch)
    task = store.due_capital_quote(now=tick[0])
    assert task["input_amount_raw"] == 4_049_382
    assert task["requested_synthetic_amount_raw"] == 4_000_000_000
    assert store.due_capital_quote(now=tick[0]) is None
    requested = tick[0]
    quote = quote_for(store, task, requested)
    tick[0] += timedelta(seconds=1)
    assert store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0]) == 1
    assert store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0]) == 0
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions").fetchone()
    assert position["status"] == "open" and position["amount_raw"] == "6000000000"
    assert position["remaining_quantity_tokens"] == pytest.approx(10.1234567 * .6)
    assert position["allocated_cost_usd"] == pytest.approx(8)
    assert position["realized_proceeds_usd"] == pytest.approx(12)  # Not 12 * .96.
    assert position["realized_pnl_usd"] == pytest.approx(4)
    assert json.loads(position["capital_exit_state_json"])["bad_streak"] == 2
    fill = store.db.execute("SELECT * FROM chain_meme_trader_fills").fetchone()
    assert fill["adapter"] == "jupiter-amountful-market-paper/v1" and fill["input_amount_raw"] == "4049382"
    assert fill["output_amount_raw"] == "12000000"
    mark = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?", (mark_id,)).fetchone()
    assert mark["market_post_price_usd"] is None and mark["status"] == "filled"
    assert store.db.execute("SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades").fetchone()[0] == pytest.approx(-8)
    store.close()


@pytest.mark.parametrize("bad", ["none", "future", "wrong_amount", "wrong_pool", "quantity_changed", "transaction", "slippage"])
def test_invalid_quotes_are_evidence_only_and_do_not_settle(tmp_path, monkeypatch, bad):
    store = Store(tmp_path / (bad + ".sqlite3"), initial_cash_usd=1000)
    tick, _, _, _ = setup(store, monkeypatch)
    task = store.due_capital_quote(now=tick[0])
    requested = tick[0]
    quote = quote_for(store, task, requested)
    tick[0] += timedelta(seconds=1)
    if bad == "none":
        quote = None
    elif bad == "future":
        quote["completed_at"] = iso(tick[0] + timedelta(seconds=5))
    elif bad == "wrong_amount":
        quote["in_amount"] = str(task["requested_synthetic_amount_raw"])
    elif bad == "wrong_pool":
        quote["route_plan"][0]["amm_key"] = str(Pubkey.new_unique())
    elif bad == "quantity_changed":
        with store.db:
            store.db.execute("UPDATE chain_meme_trader_positions SET remaining_quantity_tokens=9")
    elif bad == "transaction":
        quote["transaction"] = "not_quote_only"
    elif bad == "slippage":
        quote["slippage_bps"] = 50
    assert store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0]) == 0
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_fills").fetchone()[0] == 0
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions").fetchone()
    assert position["status"] == "open" and position["allocated_cost_usd"] == 0 and position["realized_proceeds_usd"] == 0
    evidence = json.loads(store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence "
        "WHERE kind='capital_valuation'").fetchone()[0])
    assert not evidence["complete"] and evidence["error_code"]
    store.close()


def test_valuation_throttle_full_close_and_dex_settlement_is_skipped(tmp_path, monkeypatch):
    store = Store(tmp_path / "valuation.sqlite3", initial_cash_usd=1000)
    tick, token, pair, _ = setup(store, monkeypatch, pending=False)
    task = store.due_capital_quote(now=tick[0])
    assert task["kind"] == "valuation" and task["input_amount_raw"] == 10_123_456
    requested = tick[0]
    quote = quote_for(store, task, requested)
    tick[0] += timedelta(seconds=1)
    assert store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0]) == 0
    assert store.due_capital_quote(now=tick[0] + timedelta(seconds=28)) is None
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_fills").fetchone()[0] == 0
    tick[0] += timedelta(seconds=1)  # An exit bypasses the still-active valuation cooldown.
    policy = store.db.execute("SELECT arm_id FROM chain_meme_trader_positions").fetchone()[0]
    with store.db:
        store.db.execute("INSERT INTO chain_meme_trader_marks(definition_version,arm_id,shadow_cohort_id,recorded_at,action,"
            "reason,sell_amount_raw,market_pair_address,trigger_evidence_json,status) VALUES(?,?,1,?,'FLOW_EXIT','exact',"
            "'10000000000',?,?,'pending')", (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, policy, iso(tick[0]), pair,
            json.dumps({"required_fill": "post_trigger_amount_specific_quote"})))
        mark_id = store.db.execute("SELECT last_insert_rowid()").fetchone()[0]
        store.db.execute("UPDATE chain_meme_trader_positions SET pending_mark_id=?", (mark_id,))
    tick[0] += timedelta(seconds=1)
    store.upsert_chain_meme_trader_market_mark(token, TokenSnapshot("solana", token.address, 5, 10000, 100000,
        500, 5, 2, observed_at=tick[0], ingested_at=tick[0], raw={"pair": {"pairAddress": pair}}), recorded_at=tick[0])
    store.evaluate_chain_meme_trader_market_marks(now=tick[0])
    assert store.db.execute("SELECT status FROM chain_meme_trader_marks WHERE id=?", (mark_id,)).fetchone()[0] == "pending"
    task = store.due_capital_quote(now=tick[0])
    requested = tick[0]
    quote = quote_for(store, task, requested, minimum=25_000_000)
    tick[0] += timedelta(seconds=1)
    assert store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0]) == 1
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions").fetchone()
    assert position["status"] == "closed" and position["remaining_quantity_tokens"] == 0
    assert position["allocated_cost_usd"] == 20 and position["realized_pnl_usd"] == 5
    store.close()


def test_old_strategies_have_no_capital_quote_work(tmp_path):
    store = Store(tmp_path / "old.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    assert store.due_capital_quote() is None
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_pattern_evidence").fetchone()[0] == 0
    store.close()


def test_recovery_valuation_reaches_real_evaluator_and_queues_later_quote(tmp_path, monkeypatch):
    store = Store(tmp_path / "recovery.sqlite3", initial_cash_usd=1000)
    tick, token, pair, _ = setup(store, monkeypatch, pending=False)
    for minimum in (35_000_000, 28_000_000):
        task = store.due_capital_quote(now=tick[0])
        assert task and task["kind"] == "valuation"
        requested = tick[0]
        quote = quote_for(store, task, requested, minimum=minimum)
        tick[0] += timedelta(seconds=1)
        store.record_capital_quote(task, quote, requested_at=requested, completed_at=tick[0])
        store.upsert_chain_meme_trader_market_mark(token, TokenSnapshot("solana", token.address, 2, 10000,
            100000, 500, 5, 2, observed_at=tick[0], ingested_at=tick[0],
            raw={"pair": {"pairAddress": pair}}), recorded_at=tick[0])
        store.evaluate_chain_meme_trader_market_marks(now=tick[0])
        tick[0] += timedelta(seconds=31)
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions").fetchone()
    assert position["pending_mark_id"] is not None and position["status"] == "open"
    mark = store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE id=?", (position["pending_mark_id"],)).fetchone()
    assert mark["reason"] == "amount_specific_recovery_decay"
    assert json.loads(mark["trigger_evidence_json"])["required_fill"] == "post_trigger_amount_specific_quote"
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_fills").fetchone()[0] == 0
    assert store.due_capital_quote(now=tick[0])["kind"] == "exit"
    store.close()
