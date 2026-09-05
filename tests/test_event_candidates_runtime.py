from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

import memetrader.runtime as runtime_module
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime
from memetrader.store import Store


def test_pattern_observer_yields_between_tokens_without_resampling():
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime._chain_meme_active_idle_event = asyncio.Event()
        runtime._chain_meme_active_idle_event.set()
        runtime._remember_pattern_quotes = lambda quotes: None
        runtime._rank_no_ca_events = lambda: None
        runtime._paper_quote_rejections = lambda *args: []
        tokens = [TokenCandidate("solana", str(Pubkey.new_unique()), "Token", "ABC") for _ in range(2)]
        now = utcnow()
        runtime._pattern_watch = {token.token_id: {"token": token,
            "quote": _snapshot(token, "pair-" + token.address, now),
            "pair_address": "pair-" + token.address} for token in tokens}
        runtime._pattern_held_tokens = set(runtime._pattern_watch)
        calls, ready, timing = [], [], []
        def observe(token, *args, **kwargs):
            if calls:
                assert ready == ["held_response"]
            else:
                asyncio.get_running_loop().call_soon(ready.append, "held_response")
            calls.append(token.token_id)
            return 0
        runtime.store = SimpleNamespace(capital_cross_section=lambda *args: {},
            observe_chain_meme_pattern=observe, heartbeat=lambda *args, **kwargs: None)
        runtime.runtime_timing = SimpleNamespace(observe=lambda name, duration, **kwargs: timing.append(name))
        await runtime.chain_meme_pattern_observer_once()
        assert calls == [token.token_id for token in tokens]
        assert timing == ["pattern_token_compute", "pattern_token_compute"]
        await runtime.chain_meme_pattern_observer_once()
        assert len(calls) == 2
    asyncio.run(run())


def test_held_metrics_exclude_background_waits():
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime._chain_meme_active_idle_event = asyncio.Event()
        runtime._chain_meme_active_idle_event.set()
        names, retrieval = [], []
        runtime.runtime_timing = SimpleNamespace(
            observe=lambda name, *args, **kwargs: names.append(name),
            observe_retrieval=lambda **kwargs: retrieval.append(kwargs))
        runtime.store = SimpleNamespace(heartbeat=lambda *args, **kwargs: None,
            apply_chain_meme_trader_market_mark_batch=lambda *args, **kwargs: None)
        async def failed(*args, **kwargs):
            raise TimeoutError()
        runtime._dex_batch_quote = failed
        target = {"token_id": "solana:test", "chain": "solana", "address": "test"}
        for high_priority in (False, True):
            await runtime._refresh_chain_meme_market_marks([target], heartbeat_name="test",
                high_priority=high_priority)
        assert names == ["observer_fetch_with_wait", "held_fetch"]
        assert len(retrieval) == 1 and retrieval[0]["failed"] == 1
    asyncio.run(run())


def test_same_token_history_uses_token_prefix_index(tmp_path):
    store = Store(tmp_path / "token-history-index.db")
    plan = " ".join(str(row[3]) for row in store.db.execute(
        "EXPLAIN QUERY PLAN SELECT DISTINCT p.arm_id FROM chain_meme_trader_positions p "
        "JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id "
        "WHERE p.definition_version=? AND p.token_id=? AND c.pair_address=?", ("v", "solana:x", "p")))
    assert "chain_meme_trader_positions_token_history_idx" in plan
    assert "definition_version=? AND token_id=?" in plan
    store.close()


def _snapshot(token, pair, when, *, price=2.0):
    return TokenSnapshot(
        token.chain, token.address, price, 1_000.0, 100_000.0, 500.0, 2, 1,
        observed_at=when, ingested_at=when, provider="dexscreener",
        raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "dexId": "pumpswap",
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": 1_000.0},
        }},
    )


def _fixture(tmp_path, monkeypatch, name):
    store = Store(tmp_path / name, initial_cash_usd=1_000)
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(runtime_module, "utcnow", lambda: clock[0])
    store.activate_chain_meme_trader_funded_period()
    assert store.register_chain_meme_capital_experiments() == 18
    assert store.register_chain_meme_opportunity_experiments() == 4

    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    runtime._remember_pattern_quotes = lambda quoted: None

    tokens = [
        TokenCandidate("solana", str(Pubkey.new_unique()), "Alpha", "ABC", source="fixture"),
        TokenCandidate("solana", str(Pubkey.new_unique()), "Alpha Clone", "ABC", source="fixture"),
    ]
    pairs = [str(Pubkey.new_unique()), str(Pubkey.new_unique())]
    event = {
        "kind": "okx_listing_without_exact_ca", "source": "okx",
        "source_kind": "first_party", "event_type": "official_listing",
        "identity_status": "no_exact_ca", "title": "OKX will list Alpha (ABC)",
        "url": "https://www.okx.com/help/alpha-listing",
        "published_at": iso(clock[0] - timedelta(minutes=1)),
        "observed_at": iso(clock[0] - timedelta(seconds=2)),
        "ingested_at": iso(clock[0] - timedelta(seconds=2)),
    }
    return store, runtime, clock, event, tokens, pairs


class _Dex:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def search(self, query, limit=30):
        self.calls.append((query, limit))
        return self.result


def _freeze(runtime, clock, event, tokens, pairs):
    clock[0] += timedelta(seconds=1)
    runtime.dex = _Dex([
        (token, _snapshot(token, pair, clock[0] - timedelta(milliseconds=100)))
        for token, pair in zip(tokens, pairs)
    ])
    asyncio.run(runtime._freeze_no_ca_event(event))
    row = runtime.store.db.execute(
        "SELECT * FROM chain_meme_pattern_evidence "
        "WHERE kind='authoritative_no_ca_candidate_set'"
    ).fetchone()
    assert row is not None
    return row


def _record_flow(store, clock, token, pair, *, net_raw):
    observed = clock[0] - timedelta(milliseconds=200)
    payload = {
        "complete": True, "scan_complete": True,
        "future_data_rejected": False, "usd_conversion_complete": True,
        "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
        "decision_at": iso(clock[0]), "net_quote_flow_raw": net_raw,
        "resolver": {
            "status": "verified", "pool_address": pair,
            "base_mint": token.address, "quote_mint": "USDC", "quote_decimals": 6,
            "observed_at": iso(observed - timedelta(seconds=1)),
            "recorded_at": iso(observed - timedelta(milliseconds=900)),
        },
        "quote_conversion": {
            "quote_mint": "USDC", "usd_per_quote": 1.0,
            "observed_at": iso(observed - timedelta(seconds=1)),
            "recorded_at": iso(observed - timedelta(milliseconds=900)),
            "max_age_seconds": 30,
        },
        # Counts are diagnostics and are not the ranking input.
        "buy_count": 0, "sell_count": 999_999,
    }
    return store.record_chain_meme_pattern_evidence(
        token.token_id, pair, "amountful_flow", payload,
        observed_at=observed,
        source_key=f"amountful:{token.token_id}:{iso(clock[0])}",
    )


def test_runtime_freezes_first_search_result_and_never_searches_event_again(tmp_path, monkeypatch):
    store, runtime, clock, event, tokens, pairs = _fixture(
        tmp_path, monkeypatch, "no-ca-freeze.sqlite3",
    )
    try:
        frozen = _freeze(runtime, clock, event, tokens, pairs)
        assert runtime.dex.calls == [("ABC", 25)]
        payload = json.loads(frozen["payload_json"])
        assert payload["candidate_count"] == 2
        assert payload["authoritative_ca"] is False
        assert all(member["authoritative_ca"] is False for member in payload["candidates"])

        runtime.dex.result = [
            (TokenCandidate("solana", str(Pubkey.new_unique()), "Later Winner", "ABC"),
             _snapshot(tokens[0], str(Pubkey.new_unique()), clock[0])),
        ]
        asyncio.run(runtime._freeze_no_ca_event(event))
        assert runtime.dex.calls == [("ABC", 25)]
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_pattern_evidence "
            "WHERE kind='authoritative_no_ca_candidate_set'"
        ).fetchone()[0] == 1
        assert json.loads(store.db.execute(
            "SELECT payload_json FROM chain_meme_pattern_evidence "
            "WHERE kind='authoritative_no_ca_candidate_set'"
        ).fetchone()[0])["candidate_set_hash"] == payload["candidate_set_hash"]
    finally:
        store.close()


def test_complete_same_round_flow_selects_once_then_next_frame_buys_five_dollars(
    tmp_path, monkeypatch,
):
    store, runtime, clock, event, tokens, pairs = _fixture(
        tmp_path, monkeypatch, "no-ca-rank-entry.sqlite3",
    )
    try:
        frozen = _freeze(runtime, clock, event, tokens, pairs)
        set_key = frozen["source_key"]

        clock[0] += timedelta(seconds=2)
        _record_flow(store, clock, tokens[0], pairs[0], net_raw=8_000_000)
        clock[0] += timedelta(seconds=1)
        runtime._rank_no_ca_events()
        wait = store.db.execute(
            "SELECT payload_json FROM chain_meme_pattern_evidence "
            "WHERE kind='authoritative_no_ca_amount_rank' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        wait_payload = json.loads(wait[0])
        assert wait_payload["action"] == "WAIT"
        assert wait_payload["reason"] == "incomplete_amountful_coverage"
        assert wait_payload["missing_token_ids"] == [tokens[1].token_id]

        clock[0] += timedelta(seconds=1)
        _record_flow(store, clock, tokens[1], pairs[1], net_raw=3_000_000)
        clock[0] += timedelta(seconds=1)
        runtime._rank_no_ca_events()
        selected_row = store.db.execute(
            "SELECT * FROM chain_meme_pattern_evidence WHERE kind=? AND source_key=?",
            ("authoritative_no_ca_amount_rank", set_key + "|selected"),
        ).fetchone()
        selected = json.loads(selected_row["payload_json"])
        assert selected["action"] == "SELECT"
        assert selected["selected"]["token_id"] == tokens[0].token_id
        assert selected["selected"]["pair_address"] == pairs[0]
        assert selected["selected"]["authoritative_ca"] is False
        assert selected["next_frame_trade_required"] is True

        # A later flow reversal cannot move the frozen selector time forward.
        selected_id, selected_recorded = selected_row["id"], selected_row["recorded_at"]
        clock[0] += timedelta(seconds=1)
        _record_flow(store, clock, tokens[1], pairs[1], net_raw=20_000_000)
        runtime._rank_no_ca_events()
        unchanged = store.db.execute(
            "SELECT * FROM chain_meme_pattern_evidence WHERE kind=? AND source_key=?",
            ("authoritative_no_ca_amount_rank", set_key + "|selected"),
        ).fetchone()
        assert (unchanged["id"], unchanged["recorded_at"]) == (selected_id, selected_recorded)
        assert json.loads(unchanged["payload_json"])["selected"]["token_id"] == tokens[0].token_id

        first = clock[0] + timedelta(seconds=1)
        clock[0] = first
        assert store.observe_chain_meme_pattern(
            tokens[0], _snapshot(tokens[0], pairs[0], first), recorded_at=first,
        ) == 0
        first_features = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE token_id=? ORDER BY id DESC LIMIT 1", (tokens[0].token_id,),
        ).fetchone()[0])
        assert "no_ca_event_flow_leader_v1" in first_features["ready_arm_ids"]
        assert first_features["event_keys"]["no_ca_event_flow_leader_v1"] == set_key

        second = first + timedelta(seconds=1)
        clock[0] = second
        store.observe_chain_meme_pattern(
            tokens[0], _snapshot(tokens[0], pairs[0], second), recorded_at=second,
        )
        buy = store.db.execute(
            "SELECT * FROM chain_meme_trader_trades "
            "WHERE arm_id='no_ca_event_flow_leader_v1' AND side='BUY'"
        ).fetchone()
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions "
            "WHERE arm_id='no_ca_event_flow_leader_v1'"
        ).fetchone()
        assert buy is not None and position is not None
        assert buy["gross_usd"] == pytest.approx(5.0)
        assert position["stake_usd"] == pytest.approx(5.0)
        assert position["paper_quantity_tokens"] == pytest.approx(5 / (2 * 1.04))
        cohort = json.loads(store.db.execute(
            "SELECT c.feature_json FROM chain_meme_trader_v6_cohorts c "
            "WHERE c.id=?", (position["shadow_cohort_id"],),
        ).fetchone()[0])
        assert cohort["event_keys"]["no_ca_event_flow_leader_v1"] == set_key
        assert selected["authoritative_ca"] is False
    finally:
        store.close()
