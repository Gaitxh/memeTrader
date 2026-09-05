from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

from solders.pubkey import Pubkey

import memetrader.runtime as runtime_module
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime
from memetrader.store import Store


def _snapshot(token, pair, when, *, price=2.0):
    return TokenSnapshot(
        token.chain, token.address, price, 1_000.0, 100_000.0, 500.0, 3, 1,
        observed_at=when, ingested_at=when, provider="dexscreener",
        raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "dexId": "pumpswap",
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": 1_000.0},
        }},
    )


def _observe(store, clock, token, pair, when):
    clock[0] = when
    return store.observe_chain_meme_pattern(
        token, _snapshot(token, pair, when), recorded_at=when,
    )


def _record_inputs(store, clock, token, pair, when, *, future_conversion=False):
    clock[0] = when
    surface_id = store.record_chain_meme_pattern_evidence(
        token.token_id, pair, "pool_surface", {
            "status": "RESOLVED", "complete": True, "surface": "NORMAL_DIRECT",
            "pool_address": pair, "base_mint": token.address, "quote_mint": "USDC",
            "base_decimals": 6, "pool_supply_share": .75,
            "max_single_controller_withdraw_fraction_upper_bound": .2,
            "mint_authority": None, "freeze_authority": None,
        }, observed_at=when, source_key="b02-surface",
    )
    flow_id = store.record_chain_meme_pattern_evidence(
        token.token_id, pair, "amountful_flow", {
            "complete": True, "scan_complete": True,
            "future_data_rejected": False, "usd_conversion_complete": True,
            "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
            "decision_at": iso(when), "net_quote_flow_raw": 2_000_000,
            "net_quote_flow_usd": 2.0, "effective_breadth": 2,
            "resolver": {
                "status": "verified", "pool_address": pair,
                "base_mint": token.address, "quote_mint": "USDC",
                "base_decimals": 6, "quote_decimals": 6,
                "observed_at": iso(when - timedelta(milliseconds=200)),
                "recorded_at": iso(when - timedelta(milliseconds=100)),
            },
            "quote_conversion": {
                "quote_mint": "USDC", "usd_per_quote": 1.0,
                "observed_at": iso(when + timedelta(seconds=5) if future_conversion
                                   else when - timedelta(milliseconds=200)),
                "recorded_at": iso(when + timedelta(seconds=5) if future_conversion
                                   else when - timedelta(milliseconds=100)),
                "max_age_seconds": 15,
            },
        }, observed_at=when, source_key="b02-flow",
    )
    return surface_id, flow_id


class _Jupiter:
    def __init__(self, clock, pair, token_mint):
        self.clock, self.pair, self.token_mint = clock, pair, token_mint
        self.calls = []

    async def quote(self, input_mint, output_mint, amount, *, slippage_bps):
        self.calls.append((input_mint, output_mint, amount, slippage_bps))
        minimum = 2_000_000 if input_mint == Store.JUPITER_USDC_MINT else 4_500_000
        return {
            "provider": "jupiter", "input_mint": input_mint,
            "output_mint": output_mint, "in_amount": str(amount),
            "out_amount": str(minimum + 100_000),
            "other_amount_threshold": str(minimum), "slippage_bps": slippage_bps,
            "requested_at": iso(self.clock[0]), "completed_at": iso(self.clock[0]),
            "route_plan": [{
                "amm_key": self.pair, "input_mint": input_mint,
                "output_mint": output_mint, "in_amount": str(amount),
            }],
        }


def _runtime(store, clock, jupiter):
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    runtime.jupiter = jupiter
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    runtime._jupiter_background_dispatch_lock = asyncio.Lock()
    runtime._jupiter_quote_lock = asyncio.Lock()
    runtime._jupiter_background_epoch_started = 0.0
    runtime._jupiter_background_epoch_seconds = 5.0
    runtime._jupiter_background_epoch_requests = 0
    runtime._capital_quote_next_at = 0.0
    return runtime


def test_b02_requires_actual_flow_two_exact_quotes_and_later_market_frame_buy(
    tmp_path, monkeypatch,
):
    store = Store(tmp_path / "b02.sqlite3", initial_cash_usd=1_000)
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(runtime_module, "utcnow", lambda: clock[0])
    store.activate_chain_meme_trader_funded_period()
    assert store.register_chain_meme_capital_experiments() == 18
    assert store.register_chain_meme_direct_lp_amount_specific_experiment() == 1
    assert store.register_chain_meme_direct_lp_amount_specific_experiment() == 0
    arm = "direct_lp_amount_specific_confirmed_v1"
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "B02", "B02")
    pair = str(Pubkey.new_unique())
    start = clock[0]
    try:
        # A resolved pool alone is not actual monetary flow and must not queue a quote.
        _record_inputs(store, clock, token, pair, start + timedelta(seconds=1))
        store.db.execute("DELETE FROM chain_meme_pattern_evidence WHERE kind='amountful_flow'")
        _observe(store, clock, token, pair, start + timedelta(seconds=2))
        evaluation = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        assert evaluation["outcomes"][arm] == "wait_direct_lp_positive_actual_flow"
        assert store.due_direct_lp_entry_preflight_quote(now=clock[0]) is None

        _record_inputs(store, clock, token, pair, start + timedelta(seconds=3))
        _observe(store, clock, token, pair, start + timedelta(seconds=4))
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_pattern_evidence "
            "WHERE kind='direct_lp_entry_preflight_request'"
        ).fetchone()[0] == 1

        jupiter = _Jupiter(clock, pair, token.address)
        runtime = _runtime(store, clock, jupiter)
        asyncio.run(runtime.capital_quote_once())
        runtime._capital_quote_next_at = 0.0
        asyncio.run(runtime.capital_quote_once())
        assert jupiter.calls == [
            (Store.JUPITER_USDC_MINT, token.address, 5_000_000, 400),
            (token.address, Store.JUPITER_USDC_MINT, 2_000_000, 400),
        ]
        final = json.loads(store.db.execute(
            "SELECT payload_json FROM chain_meme_pattern_evidence "
            "WHERE kind='direct_lp_entry_preflight'"
        ).fetchone()[0])
        assert final["complete"] and final["exact_pool_route"]
        assert final["sell_input_amount_raw"] == final["buy_minimum_output_raw"]
        assert final["quote_only_pretrade"] and final["is_fill"] is False

        # At the real observer cadence, +15s only signals and +30s executes.
        _observe(store, clock, token, pair, start + timedelta(seconds=19))
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'",
            (arm,),
        ).fetchone()[0] == 0
        _observe(store, clock, token, pair, start + timedelta(seconds=34))
        trade = store.db.execute(
            "SELECT * FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (arm,),
        ).fetchone()
        assert trade is not None and trade["gross_usd"] == 5.0
        assert trade["execution_fill_id"] is None
        assert "dex_mark_paper_fill" in trade["reason"]
    finally:
        store.close()


def test_b02_rejects_flow_whose_conversion_reference_is_from_the_future(
    tmp_path, monkeypatch,
):
    store = Store(tmp_path / "b02-future-flow.sqlite3", initial_cash_usd=1_000)
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_capital_experiments()
    store.register_chain_meme_direct_lp_amount_specific_experiment()
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "B02", "B02")
    pair = str(Pubkey.new_unique())
    try:
        _record_inputs(store, clock, token, pair, clock[0] + timedelta(seconds=1),
                       future_conversion=True)
        _observe(store, clock, token, pair, clock[0] + timedelta(seconds=1))
        evaluation = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        assert evaluation["outcomes"]["direct_lp_amount_specific_confirmed_v1"] \
            == "wait_direct_lp_positive_actual_flow"
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_pattern_evidence "
            "WHERE kind='direct_lp_entry_preflight_request'"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_capital_quote_runtime_keeps_pending_exit_ahead_of_entry_preflight(monkeypatch):
    token = str(Pubkey.new_unique())
    calls = []
    exit_task = {"kind": "exit", "token_id": "solana:" + token,
                 "input_amount_raw": 10, "slippage_bps": 400}

    class FakeStore:
        CHAIN_MEME_TRADER_ACTIVE_VERSION = "fixture"

        def due_capital_quote(self, *, now, task_kind):
            calls.append(("due", task_kind))
            return exit_task if task_kind == "exit" else None

        def due_direct_lp_entry_preflight_quote(self, *, now):
            calls.append(("preflight", None))
            return None

        def record_capital_quote(self, task, quote, **kwargs):
            calls.append(("record", task["kind"]))

        def evaluate_chain_meme_trader_market_marks(self, **kwargs):
            return None

        def heartbeat(self, *args, **kwargs):
            return None

    now = utcnow()
    clock = [now]
    monkeypatch.setattr(runtime_module, "utcnow", lambda: clock[0])
    jupiter = _Jupiter(clock, "unused", token)
    runtime = _runtime(FakeStore(), clock, jupiter)
    asyncio.run(runtime.capital_quote_once())
    assert calls == [("due", "exit"), ("record", "exit")]
