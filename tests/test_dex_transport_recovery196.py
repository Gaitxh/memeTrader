import asyncio

import httpx

from memetrader.runtime import Runtime


def test_inflight_success_clears_interleaved_transport_backoff():
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        runtime._chain_meme_active_idle_event = asyncio.Event()
        runtime._chain_meme_active_idle_event.set()
        runtime._dex_quote_lock = asyncio.Semaphore(8)
        runtime._dex_low_priority_slots = asyncio.Semaphore(5)
        runtime._dex_quote_backoff_until = 0.0
        runtime._dex_quote_failure_streak = 0
        runtime._dex_quote_backoff_base_seconds = 2.0
        runtime._dex_quote_backoff_cap_seconds = 30.0
        success_started = asyncio.Event()
        release_success = asyncio.Event()

        async def batch_quote(chain, addresses):
            if chain == "solana":
                success_started.set()
                await release_success.wait()
                return {}
            raise httpx.ConnectError(
                "intermittent proxy failure",
                request=httpx.Request("GET", "https://api.dexscreener.com"),
            )

        runtime.dex = type("Dex", (), {"batch_quote": staticmethod(batch_quote)})()
        success = asyncio.create_task(runtime._dex_batch_quote("solana", ["A"]))
        await success_started.wait()
        try:
            try:
                await runtime._dex_batch_quote("bsc", ["B"])
                assert False, "expected transport error"
            except httpx.ConnectError:
                pass
            assert runtime._dex_quote_backoff_until > asyncio.get_running_loop().time()
            assert runtime._dex_quote_failure_streak == 1
        finally:
            release_success.set()
        assert await success == {}
        assert runtime._dex_quote_failure_streak == 0
        assert runtime._dex_quote_transport_backoff_until == 0
        assert runtime._dex_quote_backoff_until == 0

    asyncio.run(scenario())
