import asyncio
import ssl
import time

import pytest

import memetrader.collectors as collectors
from memetrader.collectors import DEX_REQUEST_HIGH_PRIORITY, HttpClient


class _SlowClient:
    def __init__(self, release: asyncio.Event, *, close_error: bool = False):
        self.release = release
        self.close_error = close_error
        self.close_started = asyncio.Event()
        self.closed = False

    async def block(self) -> None:
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.close_started.set()
        await self.release.wait()
        self.closed = True
        if self.close_error:
            raise RuntimeError("synthetic close failure")


class _HealthyClient:
    async def ping(self) -> str:
        return "ok"

    async def aclose(self) -> None:
        return None


def _high_token():
    return DEX_REQUEST_HIGH_PRIORITY.set(True)


def test_cancelled_high_request_does_not_wait_for_slow_retired_close():
    async def scenario():
        release = asyncio.Event()
        slow = _SlowClient(release)
        replacements = iter((slow, _HealthyClient()))
        client = HttpClient(client_factory=lambda: next(replacements))
        try:
            async def request():
                async with client._request_client("api.dexscreener.com") as transport:
                    await transport.block()

            token = _high_token()
            try:
                started = time.monotonic()
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(request(), timeout=0.03)
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(token)
            assert time.monotonic() - started < 0.15
            await asyncio.wait_for(slow.close_started.wait(), timeout=0.2)
            assert client.snapshot_http_capacity()["client_generations_closing"] == 1
        finally:
            release.set()
            await client.close()
    asyncio.run(scenario())


def test_retired_client_waits_for_peer_and_new_current_remains_usable():
    async def scenario():
        release = asyncio.Event()
        old = _SlowClient(release)
        healthy = _HealthyClient()
        clients = iter((old, healthy))
        client = HttpClient(client_factory=lambda: next(clients))
        peer_done = asyncio.Event()
        try:
            async def peer():
                async with client._request_client("api.dexscreener.com"):
                    await peer_done.wait()

            async def cancelled():
                async with client._request_client("api.dexscreener.com") as transport:
                    await transport.block()

            peer_task = asyncio.create_task(peer())
            await asyncio.sleep(0)
            token = _high_token()
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(cancelled(), timeout=0.03)
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(token)
            assert not old.close_started.is_set()
            async with client._request_client("api.dexscreener.com") as current:
                assert await current.ping() == "ok"
            peer_done.set()
            await peer_task
            await asyncio.wait_for(old.close_started.wait(), timeout=0.2)
        finally:
            peer_done.set()
            release.set()
            await client.close()
    asyncio.run(scenario())


def test_rotation_cap_reuses_current_and_records_suppression():
    async def scenario():
        release = asyncio.Event()
        stale = [_SlowClient(release) for _ in range(HttpClient.MAX_RETIRED_OR_CLOSING_CLIENTS)]
        current = _SlowClient(release)
        clients = iter([current, *stale])
        client = HttpClient(client_factory=lambda: next(clients))
        try:
            async def cancelled():
                async with client._request_client("api.dexscreener.com") as transport:
                    await transport.block()

            token = _high_token()
            try:
                for _ in range(HttpClient.MAX_RETIRED_OR_CLOSING_CLIENTS + 1):
                    with pytest.raises(TimeoutError):
                        await asyncio.wait_for(cancelled(), timeout=0.01)
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(token)
            status = client.snapshot_http_capacity()
            assert status["client_generation_retirements"] == HttpClient.MAX_RETIRED_OR_CLOSING_CLIENTS
            assert status["client_rotation_suppressed"] == 1
            assert status["client_generations_closing"] == HttpClient.MAX_RETIRED_OR_CLOSING_CLIENTS
            assert client.client is stale[-1]
        finally:
            release.set()
            await client.close()
    asyncio.run(scenario())


def test_background_close_exception_is_consumed_and_counted():
    async def scenario():
        release = asyncio.Event()
        broken = _SlowClient(release, close_error=True)
        replacements = iter((broken, _HealthyClient()))
        client = HttpClient(client_factory=lambda: next(replacements))
        try:
            async def cancelled():
                async with client._request_client("api.dexscreener.com") as transport:
                    await transport.block()

            token = _high_token()
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(cancelled(), timeout=0.01)
            finally:
                DEX_REQUEST_HIGH_PRIORITY.reset(token)
            release.set()
            await asyncio.wait_for(broken.close_started.wait(), timeout=0.2)
            for _ in range(10):
                if client.snapshot_http_capacity()["client_close_errors"]:
                    break
                await asyncio.sleep(0)
            assert client.snapshot_http_capacity()["client_close_errors"] == 1
        finally:
            release.set()
            await client.close()
    asyncio.run(scenario())


def test_rotation_reuses_one_strict_certifi_verification_context(monkeypatch):
    created = []

    class Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(collectors.httpx, "AsyncClient", Client)

    async def scenario():
        client = HttpClient(proxy_url="socks5://127.0.0.1:7890")
        initial = client.client
        context = client._verification_context
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        await client._retire_failed_client(initial, "cancel")
        replacement = client.client
        assert replacement is not initial
        assert initial.kwargs["verify"] is context
        assert replacement.kwargs["verify"] is context
        assert initial.kwargs["trust_env"] is False
        await client.close()

    asyncio.run(scenario())
