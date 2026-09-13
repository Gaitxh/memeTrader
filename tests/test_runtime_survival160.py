import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

from memetrader.runtime import Runtime
from memetrader.runtime_timing import RuntimeTiming


def test_periodic_survives_failed_action_health_and_timing_writes():
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        runtime.chain_meme_trader_only = True
        runtime._stop = asyncio.Event()
        runtime.runtime_timing = RuntimeTiming()
        runtime._last_timing_write = -100
        errors = []
        def unavailable(*args, **kwargs):
            raise sqlite3.OperationalError('database is locked')
        runtime.store = SimpleNamespace(heartbeat=unavailable, record_runtime_timing=unavailable)
        runtime.notifier = SimpleNamespace(send=lambda *args: None)
        runtime._record_periodic_traceback = lambda name, error: errors.append(name)
        calls = []
        async def action():
            calls.append(1)
            if len(calls) == 1:
                raise sqlite3.OperationalError('database is locked')
            runtime._stop.set()
        await asyncio.wait_for(runtime._periodic('test', 1, action), 2)
        assert len(calls) == 2
        assert 'test_health_write' in errors and 'test_timing_write' in errors
    asyncio.run(scenario())


@pytest.mark.parametrize('failed', [False, True])
def test_dead_core_task_causes_supervisor_restart_not_zombie(failed):
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        runtime._stop = asyncio.Event()
        async def core():
            if failed:
                raise sqlite3.OperationalError('database is locked')
        task = asyncio.create_task(core(), name='chain_meme_market_marks')
        with pytest.raises(RuntimeError, match='critical runtime task stopped'):
            await asyncio.wait_for(runtime._wait_for_core_tasks([task]), 1)
    asyncio.run(scenario())


def test_finite_optional_task_and_normal_stop_are_not_failures():
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        runtime._stop = asyncio.Event()
        async def optional():
            return None
        task = asyncio.create_task(optional(), name='capital_research_seal')
        waiter = asyncio.create_task(runtime._wait_for_core_tasks([task]))
        await asyncio.sleep(.01)
        assert not waiter.done()
        runtime._stop.set()
        await asyncio.wait_for(waiter, 1)
    asyncio.run(scenario())
