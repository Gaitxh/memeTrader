import asyncio
import json
import time
from datetime import timedelta

import httpx
import pytest

from memetrader.collectors import (
    DEX_REQUEST_HIGH_PRIORITY, DexLowPriorityCapacityDeferred,
    DexScreenerClient, HttpClient,
)
from memetrader.models import iso, utcnow
from memetrader.runtime import Runtime, initial_config


@pytest.mark.parametrize("surface,role", [("token_profiles", "identity"), ("profile_updates", "identity"),
                                        ("community_takeovers", "identity"), ("boosts_latest", "promotion")])
def test_official_stream_handshake_and_updates_remain_discovery(monkeypatch, surface, role):
    item = {"chainId": "solana", "tokenAddress": "A" * 32,
            "url": "https://dexscreener.com/solana/pool", "updatedAt": "2020-01-01T00:00:00Z"}
    payloads = [{"limit": 90, "data": [item]}, [dict(item, description="changed"), dict(item, chainId="polygon")]]

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def __aiter__(self):
            async def messages():
                for payload in payloads:
                    yield json.dumps(payload)
            return messages()

    def connect(url, **kwargs):
        assert url == "wss://api.dexscreener.com" + DexScreenerClient.DISCOVERY_SURFACES[surface][0]
        assert kwargs["max_queue"] == 4
        return Socket()

    monkeypatch.setattr("memetrader.collectors.websockets.connect", connect)

    async def scenario():
        before = utcnow()
        frames = [frame async for frame in DexScreenerClient(None).stream_surface(surface, {"solana"})]
        assert len(frames) == 2
        for index, (received, rows) in enumerate(frames):
            assert received >= before and len(rows) == 1
            assert rows[0]["role"] == role
            assert rows[0]["raw"]["received_at"] == iso(received)
            assert rows[0]["raw"]["initial_snapshot"] is (index == 0)
            assert rows[0]["raw"]["item"]["updatedAt"].startswith("2020-")
    asyncio.run(scenario())


def test_discovery_limit_is_applied_after_supported_chain_filter():
    item = {"chainId": "solana", "tokenAddress": "A" * 32,
            "url": "https://dexscreener.com/solana/pool"}
    payload = [None, dict(item, chainId="polygon"), dict(item, tokenAddress=""), item,
               dict(item, tokenAddress="B" * 32), dict(item, tokenAddress="C" * 32)]
    rows = DexScreenerClient(None).discovery_links("token_profiles", payload, {"solana"}, limit=2)
    assert [row["token_id"] for row in rows] == ["solana:" + "A" * 32, "solana:" + "B" * 32]


def test_stream_replay_is_deduplicated_and_enters_existing_hydration_only(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "stream.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        received = utcnow() - timedelta(seconds=1)
        item = {"chainId": "solana", "tokenAddress": "A" * 32,
                "url": "https://dexscreener.com/solana/pool"}
        rows = runtime.dex.discovery_links("boosts_latest", [item], {"solana"})
        changed = runtime.dex.discovery_links("boosts_latest", [dict(item, amount=100)], {"solana"})

        async def stream(surface, chains):
            for frame in (rows, rows, changed):
                yield received, frame
            runtime._stop.set()

        runtime.dex.stream_surface = stream
        await runtime.dex_discovery_stream_loop("boosts_latest")
        db = runtime.store.db
        assert db.execute("SELECT COUNT(*) FROM token_discovery_rounds WHERE mode='stream_message'").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM token_detail_hydration").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM token_snapshots").fetchone()[0] == 0
        link = db.execute("SELECT first_observed_at,role FROM token_source_links LIMIT 1").fetchone()
        assert link["first_observed_at"] == iso(received) and link["role"] == "promotion"
        eligibility = db.execute("SELECT decision_eligible,affects FROM token_discovery_exposure_source_links").fetchall()
        assert len(eligibility) == 2
        assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in eligibility)
        await runtime.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("retry", [False, True])
def test_terminal_dex_429_cools_other_endpoint_even_without_retry(retry):
    async def scenario():
        calls = []
        errors = 2 if retry else 1

        async def handler(request):
            calls.append(time.monotonic())
            return httpx.Response(429 if len(calls) <= errors else 200,
                                  headers={"Retry-After": "0.02"}, json=[])

        client = HttpClient(min_host_interval=0, transport=httpx.MockTransport(handler))
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://api.dexscreener.com/token-profiles/latest/v1", retry_429=retry)
        deadline = client._host_backoff_until["api.dexscreener.com"]
        await client.get("https://api.dexscreener.com/latest/dex/pairs/solana/pool", retry_429=False)
        assert calls[-1] >= deadline - 0.002
        assert len(calls) == errors + 1
        await client.close()
    asyncio.run(scenario())


def test_real_dex_starts_prioritize_held_then_resume_lows_before_held_response():
    async def scenario():
        starts = []
        held_started = asyncio.Event()
        release_held = asyncio.Event()

        async def handler(request):
            name = request.url.path.rsplit("/", 1)[-1]
            starts.append((name, time.monotonic()))
            if name.startswith("held"):
                if sum(n.startswith("held") for n, _ in starts) == 2:
                    held_started.set()
                await release_held.wait()
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0.03, transport=httpx.MockTransport(handler))
        runtime = Runtime.__new__(Runtime)
        runtime.dex = DexScreenerClient(client)
        runtime._dex_quote_lock = asyncio.Semaphore(8)
        runtime._dex_low_priority_slots = asyncio.Semaphore(5)
        runtime._dex_quote_backoff_until = 0.0
        runtime._dex_quote_failure_streak = 0
        deadline = time.monotonic() + 0.15
        client._host_backoff_until["api.dexscreener.com"] = deadline
        tasks = []

        async def wait_queued(high, count):
            while len(client._dex_start_waiters[high]) != count:
                await asyncio.sleep(0)

        try:
            tasks = [asyncio.create_task(runtime._dex_batch_quote(
                "solana", [f"low{i}"], fresh=True)) for i in range(2)]
            await asyncio.wait_for(wait_queued(False, 2), timeout=1)
            highs = [asyncio.create_task(runtime._dex_batch_quote(
                "solana", [f"held{i}"], fresh=True, high_priority=True)) for i in range(2)]
            tasks.extend(highs)
            await asyncio.wait_for(held_started.wait(), timeout=1)
            await asyncio.wait_for(asyncio.gather(*tasks[:2]), timeout=1)
            assert [n for n, _ in starts] == ["held0", "held1", "low0", "low1"]
            assert all(not task.done() for task in highs)
            assert starts[0][1] >= deadline
            assert all(b[1] - a[1] >= 0.029 for a, b in zip(starts, starts[1:]))
        finally:
            release_held.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await client.close()
        assert not any(client._dex_start_waiters.values())
    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_high", [False, True])
def test_dex_start_cancellation_releases_priority_and_pacing_turn(cancel_high):
    from memetrader.collectors import DEX_REQUEST_HIGH_PRIORITY

    async def scenario():
        starts = []

        async def handler(request):
            starts.append(request.url.path)
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0.01, transport=httpx.MockTransport(handler))
        deadline = time.monotonic() + 0.1
        client._host_backoff_until["api.dexscreener.com"] = deadline

        async def request(high):
            token = DEX_REQUEST_HIGH_PRIORITY.set(high)
            try:
                await client.get("https://api.dexscreener.com/" + ("held" if high else "low"))
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(token)

        tasks = {high: asyncio.create_task(request(high)) for high in (False, True)}
        async def queued():
            while not all(client._dex_start_waiters.values()):
                await asyncio.sleep(0)
        try:
            await asyncio.wait_for(queued(), timeout=1)
            tasks[cancel_high].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[cancel_high]
            await asyncio.wait_for(tasks[not cancel_high], timeout=1)
            assert starts == (["/low"] if cancel_high else ["/held"])
            assert client._last["api.dexscreener.com"] >= deadline
            assert not any(client._dex_start_waiters.values())
        finally:
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            await client.close()
    asyncio.run(scenario())


def test_dex_low_429_retry_yields_start_to_new_held_request():
    from memetrader.collectors import DEX_REQUEST_HIGH_PRIORITY

    async def scenario():
        starts = []
        rate_limited = asyncio.Event()
        release_held = asyncio.Event()

        async def handler(request):
            name = request.url.path
            starts.append((name, time.monotonic()))
            if len(starts) == 1:
                rate_limited.set()
                return httpx.Response(429, headers={"Retry-After": "0.08"}, json=[])
            if name == "/held":
                await release_held.wait()
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0.02, transport=httpx.MockTransport(handler))
        low = asyncio.create_task(client.get("https://api.dexscreener.com/low"))
        await rate_limited.wait()
        token = DEX_REQUEST_HIGH_PRIORITY.set(True)
        high = asyncio.create_task(client.get("https://api.dexscreener.com/held", retry_429=False))
        DEX_REQUEST_HIGH_PRIORITY.reset(token)
        try:
            await asyncio.wait_for(low, timeout=1)
            assert [name for name, _ in starts] == ["/low", "/held", "/low"]
            assert starts[1][1] >= client._host_backoff_until["api.dexscreener.com"]
            assert starts[2][1] - starts[1][1] >= 0.019
            assert not high.done()
        finally:
            release_held.set()
            await asyncio.gather(low, high, return_exceptions=True)
            await client.close()
    asyncio.run(scenario())


def test_direct_dex_low_inflight_requests_leave_reserved_capacity_for_held_work():
    async def scenario():
        starts = []
        lows_started = asyncio.Event()
        highs_started = asyncio.Event()
        release_lows = asyncio.Event()

        async def handler(request):
            name = request.url.path.rsplit("/", 1)[-1]
            starts.append(name)
            if name.startswith("low"):
                if sum(item.startswith("low") for item in starts) == 5:
                    lows_started.set()
                await release_lows.wait()
            elif sum(item.startswith("held") for item in starts) == 3:
                highs_started.set()
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0, transport=httpx.MockTransport(handler))
        lows = [asyncio.create_task(client.get(f"https://api.dexscreener.com/low{i}"))
                for i in range(5)]
        try:
            await asyncio.wait_for(lows_started.wait(), timeout=1)
            with pytest.raises(DexLowPriorityCapacityDeferred, match="low-priority"):
                await client.get("https://api.dexscreener.com/deferred-low")
            priority_token = DEX_REQUEST_HIGH_PRIORITY.set(True)
            try:
                highs = [asyncio.create_task(client.get(
                    f"https://api.dexscreener.com/held{i}"
                )) for i in range(3)]
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(priority_token)
            await asyncio.wait_for(highs_started.wait(), timeout=1)
            assert all(not task.done() for task in lows)
            await asyncio.gather(*highs)
        finally:
            release_lows.set()
            await asyncio.gather(*lows, return_exceptions=True)
            await client.close()
    asyncio.run(scenario())


def test_dex_connection_failure_retires_only_its_client_generation():
    async def scenario():
        slow_started = asyncio.Event()
        release_slow = asyncio.Event()

        async def first_handler(request):
            if request.url.path == "/slow":
                slow_started.set()
                await release_slow.wait()
                return httpx.Response(200, json=[])
            raise httpx.ConnectError("TLS failed after proxy CONNECT", request=request)

        first = httpx.AsyncClient(transport=httpx.MockTransport(first_handler))
        replacement = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=[])
        ))
        clients = iter((first, replacement))
        client = HttpClient(min_host_interval=0, client_factory=lambda: next(clients))
        slow = asyncio.create_task(client.get("https://api.dexscreener.com/slow"))
        try:
            await asyncio.wait_for(slow_started.wait(), timeout=1)
            with pytest.raises(httpx.ConnectError):
                await client.get("https://api.dexscreener.com/failure")
            assert not first.is_closed
            release_slow.set()
            await slow
            assert first.is_closed
            assert (await client.get("https://api.dexscreener.com/after")).status_code == 200
            status = client.snapshot_http_capacity()
            assert status["connect_errors"] == 1
            assert status["client_generation_retirements"] == 1
            assert status["retired_client_generations"] == 0
        finally:
            release_slow.set()
            await asyncio.gather(slow, return_exceptions=True)
            await client.close()
    asyncio.run(scenario())


def test_dex_proxy_connect_tls_failures_do_not_exhaust_a_small_connection_pool(monkeypatch):
    async def scenario():
        connections = 0

        async def proxy(reader, writer):
            nonlocal connections
            connections += 1
            while await reader.readline() != b"\r\n":
                pass
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(proxy, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("https_proxy", f"http://127.0.0.1:{port}")
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        client = HttpClient(
            timeout=0.5,
            min_host_interval=0,
            client_limits=httpx.Limits(max_connections=3, max_keepalive_connections=3),
        )
        try:
            for index in range(5):
                with pytest.raises(httpx.ConnectError):
                    await client.get(f"https://dex-recovery.test/{index}", retry_429=False)
            status = client.snapshot_http_capacity()
            assert connections == 5
            assert status["connect_errors"] == 5
            assert status["pool_timeouts"] == 0
            assert status["client_generation_retirements"] == 5
        finally:
            await client.close()
            server.close()
            await server.wait_closed()
    asyncio.run(scenario())


def test_cancelled_direct_dex_low_request_releases_its_inflight_slot():
    async def scenario():
        low_starts = 0
        first_five_started = asyncio.Event()
        replacement_started = asyncio.Event()
        release_lows = asyncio.Event()

        async def handler(request):
            nonlocal low_starts
            low_starts += 1
            if low_starts == 5:
                first_five_started.set()
            if low_starts == 6:
                replacement_started.set()
            await release_lows.wait()
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0, transport=httpx.MockTransport(handler))
        lows = [asyncio.create_task(client.get(f"https://api.dexscreener.com/low{i}"))
                for i in range(5)]
        try:
            await asyncio.wait_for(first_five_started.wait(), timeout=1)
            lows[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await lows[0]
            replacement = asyncio.create_task(client.get("https://api.dexscreener.com/replacement"))
            await asyncio.wait_for(replacement_started.wait(), timeout=1)
            release_lows.set()
            await asyncio.gather(*lows[1:], replacement)
        finally:
            release_lows.set()
            await asyncio.gather(*lows, return_exceptions=True)
            await client.close()
    asyncio.run(scenario())


def test_dex_inflight_waiters_are_paced_when_capacity_reopens():
    async def scenario():
        starts = []
        lows_started = asyncio.Event()
        initial_highs_started = asyncio.Event()
        all_highs_started = asyncio.Event()
        release_lows = asyncio.Event()
        release_highs = asyncio.Event()

        async def handler(request):
            name = request.url.path.rsplit("/", 1)[-1]
            starts.append((name, time.monotonic()))
            if name.startswith("low"):
                if sum(item.startswith("low") for item, _ in starts) == 5:
                    lows_started.set()
                await release_lows.wait()
            else:
                count = sum(item.startswith("held") for item, _ in starts)
                if count == 3:
                    initial_highs_started.set()
                if count == 6:
                    all_highs_started.set()
                await release_highs.wait()
            return httpx.Response(200, json=[])

        client = HttpClient(min_host_interval=0.02, transport=httpx.MockTransport(handler))
        lows = [asyncio.create_task(client.get(f"https://api.dexscreener.com/low{i}"))
                for i in range(5)]
        highs = []
        try:
            await asyncio.wait_for(lows_started.wait(), timeout=1)
            priority_token = DEX_REQUEST_HIGH_PRIORITY.set(True)
            try:
                highs = [asyncio.create_task(client.get(f"https://api.dexscreener.com/held{i}"))
                         for i in range(6)]
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(priority_token)
            await asyncio.wait_for(initial_highs_started.wait(), timeout=1)
            await asyncio.sleep(0.08)
            release_lows.set()
            await asyncio.wait_for(all_highs_started.wait(), timeout=1)
            held_starts = [started for name, started in starts if name.startswith("held")]
            assert all(b - a >= 0.018 for a, b in zip(held_starts, held_starts[1:]))
        finally:
            release_lows.set()
            release_highs.set()
            await asyncio.gather(*lows, *highs, return_exceptions=True)
            await client.close()
    asyncio.run(scenario())
