from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

import memetrader.runtime as runtime_module
from memetrader.runtime import Runtime
from memetrader.store import Store


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
