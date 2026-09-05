from __future__ import annotations

import asyncio
import sqlite3
import threading
from datetime import timedelta
from types import SimpleNamespace

import pytest

import memetrader.runtime as runtime_module
from memetrader.runtime import Runtime
from memetrader.store import Store
from memetrader.models import TokenCandidate, iso, utcnow


def test_capital_research_seal_uses_readonly_worker_and_reuses_persisted_model(
    tmp_path, monkeypatch,
):
    store = Store(tmp_path / "capital-research.sqlite3", initial_cash_usd=1000)
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    main_thread = threading.get_ident()
    calls = {"load": 0, "seal": 0}

    def load_samples(connection, version, cutoff):
        calls["load"] += 1
        assert threading.get_ident() != main_thread
        assert connection is not store.db
        assert version == store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        assert cutoff
        assert connection.execute("SELECT 1").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE must_not_write(value INTEGER)")
        return [{"sample_id": "sealed-1"}]

    model = {
        "version": "competing-risk/v1", "samples": [{"sample_id": "sealed-1"}],
        "bins": [], "trained_at": "2026-09-06T00:00:00Z",
    }

    def seal(source, *, trained_at):
        calls["seal"] += 1
        assert source == [{"sample_id": "sealed-1"}]
        assert trained_at
        return model

    monkeypatch.setattr(runtime_module, "load_competing_risk_samples", load_samples)
    monkeypatch.setattr(runtime_module, "seal_competing_risk_model", seal)
    asyncio.run(runtime.seal_capital_research_once())
    assert calls == {"load": 1, "seal": 1}
    assert runtime._capital_risk_model == model

    key = "capital_research:competing_risk_v1:" + store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    assert store.get_kv(key) == model
    del runtime._capital_risk_model
    asyncio.run(runtime.seal_capital_research_once())
    assert calls == {"load": 1, "seal": 1}
    assert runtime._capital_risk_model == model
    store.close()


def test_flat_compression_read_is_async_readonly_and_does_not_hold_store_write_lock(
    tmp_path, monkeypatch,
):
    store = Store(tmp_path / "flat-shadow.sqlite3", initial_cash_usd=1000)
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    main_thread = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    observations = {}

    def blocking_read(*, limit, connection):
        observations["thread"] = threading.get_ident()
        observations["separate_connection"] = connection is not store.db
        observations["readable"] = connection.execute("SELECT 1").fetchone()[0]
        observations["limit"] = limit
        started.set()
        observations["released_while_waiting"] = release.wait(timeout=.5)
        return []

    async def unexpected_refresh(*args, **kwargs):
        pytest.fail("empty shadow query attempted a market refresh")

    monkeypatch.setattr(store, "due_flat_compression_breakout_shadow_targets", blocking_read)
    runtime._refresh_chain_meme_market_marks = unexpected_refresh

    async def ticker():
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(.002)
        assert started.is_set()
        # This write uses Store's normal connection while the bounded read is
        # still blocked on its independent worker connection.
        store.set_kv("flat-shadow:event-loop-probe", {"advanced": True})
        release.set()

    async def scenario():
        await asyncio.gather(runtime.flat_compression_breakout_shadow_once(), ticker())

    asyncio.run(scenario())
    assert observations == {
        "thread": observations["thread"],
        "separate_connection": True,
        "readable": 1,
        "limit": 30,
        "released_while_waiting": True,
    }
    assert observations["thread"] != main_thread
    assert store.get_kv("flat-shadow:event-loop-probe") == {"advanced": True}
    store.close()


def test_origin_transient_failure_is_visible_and_retries_only_once(tmp_path, monkeypatch):
    store = Store(tmp_path / "origin-retry.sqlite3", initial_cash_usd=1000)
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    now = utcnow()
    monkeypatch.setattr(runtime_module, "utcnow", lambda: now)
    token = TokenCandidate("solana", "origin-mint", "Origin", "ORG", first_seen_at=now,
        source="pumpportal:create", raw={"pump_event_type": "create", "txType": "create",
        "signature": "known-create"})
    store.record_token_launch_fact(token, ingested_at=now)
    pool = dict(token_id=token.token_id, pool_address="origin-pool", base_mint=token.address)
    runtime._pattern_pool_targets = {"origin-pool": pool}
    runtime.held_accounts = SimpleNamespace()
    runtime._chain_meme_active_idle_event = asyncio.Event()
    runtime._chain_meme_active_idle_event.set()
    calls = []

    async def fail(*args, **kwargs):
        calls.append(True)
        return {"status": "unverified", "reason": "get_transaction_failed:ReadTimeout"}

    monkeypatch.setattr(runtime_module, "verify_creator_from_known_signature", fail)

    async def scenario():
        nonlocal now
        await runtime._chain_meme_pattern_origin_once(pool)
        await runtime._chain_meme_pattern_origin_once(pool)
        assert len(calls) == 1
        row = store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence "
                               "WHERE kind='token_origin'").fetchone()
        assert store._json_object(row[0])["reason"] == "get_transaction_failed:ReadTimeout"
        now += timedelta(seconds=61)
        await runtime._chain_meme_pattern_origin_once(pool)
        now += timedelta(seconds=61)
        await runtime._chain_meme_pattern_origin_once(pool)
        assert len(calls) == 2
        assert "retry_at" not in runtime._pattern_origin_cache["origin-pool"]

    asyncio.run(scenario())
    store.close()
