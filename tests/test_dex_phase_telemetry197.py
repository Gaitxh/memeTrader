import asyncio

import httpx

from memetrader.collectors import DEX_REQUEST_FOLLOWUP_PRIORITY, HttpClient


def test_dex_phases_separate_start_pacing_from_http_and_keep_bounded_samples():
    async def scenario():
        async def respond(request):
            await asyncio.sleep(0.015)
            return httpx.Response(200, json={"pairs": []})

        client = HttpClient(transport=httpx.MockTransport(respond), min_host_interval=0.02)
        try:
            token = DEX_REQUEST_FOLLOWUP_PRIORITY.set(True)
            try:
                for _ in range(66):
                    await client.get("https://api.dexscreener.com/latest/dex/tokens/test")
            finally:
                DEX_REQUEST_FOLLOWUP_PRIORITY.reset(token)
            phase = client.snapshot_http_capacity()["dex_phase_followup"]
            assert phase["samples"] == 64
            assert phase["failures"] == 0
            assert phase["start_ms_p95"] >= 1
            assert phase["http_ms_p95"] >= 10
            assert phase["total_ms_p95"] >= phase["http_ms_p95"]
            assert client.snapshot_http_capacity()["dex_phase_background"]["samples"] == 0
        finally:
            await client.close()

    asyncio.run(scenario())


def test_dex_timeout_records_the_active_http_phase():
    async def scenario():
        async def fail(request):
            await asyncio.sleep(0.01)
            raise httpx.ConnectTimeout("synthetic")

        client = HttpClient(transport=httpx.MockTransport(fail), min_host_interval=0)
        try:
            try:
                await client.get("https://api.dexscreener.com/latest/dex/tokens/test")
            except httpx.ConnectTimeout:
                pass
            else:
                raise AssertionError("expected timeout")
            phase = client.snapshot_http_capacity()["dex_phase_background"]
            assert phase["samples"] == 1
            assert phase["failures"] == 1
            assert phase["last_outcome"] == "ConnectTimeout"
            assert phase["http_ms_p95"] >= 5
        finally:
            await client.close()

    asyncio.run(scenario())
