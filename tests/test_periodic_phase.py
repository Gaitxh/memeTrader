import asyncio
from types import SimpleNamespace
import pytest
from memetrader.runtime import Runtime
from memetrader.runtime_timing import RuntimeTiming


def test_initial_phase_shifts_first_start_only():
    async def scenario():
        async def run(phase):
            r = Runtime.__new__(Runtime)
            r.chain_meme_trader_only = False
            r._stop = asyncio.Event()
            r.runtime_timing = RuntimeTiming()
            r._last_timing_write = asyncio.get_running_loop().time()
            r.store = SimpleNamespace(record_runtime_timing=lambda *a: None)
            starts = []
            origin = asyncio.get_running_loop().time()
            async def action():
                starts.append(asyncio.get_running_loop().time()-origin)
                if len(starts) == 3:
                    r._stop.set()
            await r._periodic('fixture', 1, action, initial_delay_seconds=phase)
            return starts
        ordinary, shifted = await asyncio.gather(run(0), run(.3))
        assert len(ordinary) == len(shifted) == 3
        assert ordinary[0] < .1
        assert shifted[0] == pytest.approx(.3, abs=.1)
        for starts in (ordinary, shifted):
            assert [b-a for a,b in zip(starts,starts[1:])] == pytest.approx([1,1], abs=.1)
    asyncio.run(scenario())


def test_stop_during_initial_phase_never_runs_action():
    async def scenario():
        r = Runtime.__new__(Runtime)
        r.chain_meme_trader_only = False
        r._stop = asyncio.Event()
        called = []
        async def action(): called.append(True)
        task = asyncio.create_task(r._periodic('fixture',15,action,initial_delay_seconds=10))
        await asyncio.sleep(0)
        r._stop.set()
        await asyncio.wait_for(task,.2)
        assert not called
    asyncio.run(scenario())
