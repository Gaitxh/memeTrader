import asyncio
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from memetrader.collectors import (
    DEX_REQUEST_FOLLOWUP_PRIORITY,
    DexLowPriorityCapacityDeferred,
    HttpClient,
)
from memetrader.followup_capacity import reserve_signal_followup_capacity
from memetrader.models import iso, utcnow


def test_live_signal_reserves_only_its_remaining_original_lifetime():
    now = utcnow()
    client = SimpleNamespace(dex_followup_urgent_until=0.0)
    remaining = reserve_signal_followup_capacity(
        client,
        {"arm": {"recorded_at": iso(now - timedelta(seconds=17))}},
        now=now,
        monotonic_now=100.0,
    )
    assert remaining == pytest.approx(43.0)
    assert client.dex_followup_urgent_until == pytest.approx(143.0)


def test_expired_future_and_invalid_signals_do_not_reserve_capacity():
    now = utcnow()
    client = SimpleNamespace(dex_followup_urgent_until=91.0)
    signals = {
        "expired": {"recorded_at": iso(now - timedelta(seconds=61))},
        "future": {"recorded_at": iso(now + timedelta(seconds=1))},
        "invalid": {"recorded_at": "not-a-clock"},
    }
    assert reserve_signal_followup_capacity(
        client, signals, now=now, monotonic_now=100.0,
    ) == 0.0
    assert client.dex_followup_urgent_until == 91.0


def test_existing_longer_reservation_is_never_shortened():
    now = utcnow()
    client = SimpleNamespace(dex_followup_urgent_until=200.0)
    reserve_signal_followup_capacity(
        client,
        {"arm": {"recorded_at": iso(now)}},
        now=now,
        monotonic_now=100.0,
    )
    assert client.dex_followup_urgent_until == 200.0


def test_early_signal_reservation_keeps_the_existing_followup_slot_free():
    async def scenario():
        client = HttpClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
            min_host_interval=0,
            dex_low_priority_wait=0.01,
        )
        release = asyncio.Event()
        ready = asyncio.Event()
        active = 0

        async def background():
            nonlocal active
            async with client._dex_inflight_slot():
                active += 1
                if active == 4:
                    ready.set()
                await release.wait()

        tasks = [asyncio.create_task(background()) for _ in range(4)]
        try:
            await asyncio.wait_for(ready.wait(), 1)
            wall_now = utcnow()
            loop_now = asyncio.get_running_loop().time()
            reserve_signal_followup_capacity(
                client,
                {"arm": {"recorded_at": iso(wall_now)}},
                now=wall_now,
                monotonic_now=loop_now,
            )
            with pytest.raises(DexLowPriorityCapacityDeferred):
                async with client._dex_inflight_slot():
                    pass
            token = DEX_REQUEST_FOLLOWUP_PRIORITY.set(True)
            try:
                async with client._dex_inflight_slot():
                    assert client.snapshot_http_capacity()["active_low_priority"] == 5
            finally:
                DEX_REQUEST_FOLLOWUP_PRIORITY.reset(token)
        finally:
            release.set()
            await asyncio.gather(*tasks)
            await client.close()

    asyncio.run(scenario())
