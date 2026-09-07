"""Offline regression coverage for the audited DexScreener cache timestamp bug."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from memetrader.collectors import DexScreenerClient, GeckoNewPoolsCollector, HttpClient


def _pair(chain):
    address = "So11111111111111111111111111111111111111112" if chain == "solana" else "0x" + "12" * 20
    pool = "CachePool" if chain == "solana" else "0x" + "ab" * 20
    return {
        "chainId": chain,
        "pairAddress": pool,
        "baseToken": {"address": address, "name": "Cache receipt", "symbol": "CACHE"},
        "priceUsd": "2",
        "liquidity": {"usd": 10000},
        "volume": {"m5": 500},
        "txns": {"m5": {"buys": 6, "sells": 3}},
    }


@pytest.mark.parametrize("chain", ["solana", "bsc", "robinhood"])
@pytest.mark.parametrize("entrypoint", ["search", "quote", "batch_quote"])
def test_cached_dex_payload_preserves_first_observation(monkeypatch, chain, entrypoint):
    async def scenario():
        wall = [datetime(2026, 9, 7, tzinfo=timezone.utc)]
        monkeypatch.setattr("memetrader.collectors.utcnow", lambda: wall[0])
        pair = _pair(chain)
        calls = []

        def handler(request):
            calls.append(request.url)
            payload = {"pairs": [pair]} if entrypoint == "search" else [pair]
            return httpx.Response(200, json=payload)

        http = HttpClient(transport=httpx.MockTransport(handler), min_host_interval=0)
        dex = DexScreenerClient(http)
        address = pair["baseToken"]["address"]

        async def read():
            if entrypoint == "search":
                return (await dex.search(address))[0]
            if entrypoint == "quote":
                return await dex.quote(chain, address)
            return (await dex.batch_quote(chain, [address]))[f"{chain}:{address}"]

        try:
            first_token, first = await read()
            wall[0] += timedelta(seconds=1)
            second_token, second = await read()
            assert len(calls) == 1  # This must exercise an actual local HTTP-cache hit.
            assert first_token.token_id == second_token.token_id == f"{chain}:{address}"
            assert first.raw["pair"] == second.raw["pair"] == pair
            assert first.price_usd == second.price_usd == 2
            assert first.ingested_at is None and second.ingested_at is None
            assert second.observed_at == first.observed_at
            assert second.observed_at < wall[0]
        finally:
            await http.close()

    asyncio.run(scenario())


def test_cached_gecko_new_pool_preserves_first_market_observation(monkeypatch):
    async def scenario():
        wall = [datetime(2026, 9, 7, tzinfo=timezone.utc)]
        monkeypatch.setattr("memetrader.collectors.utcnow", lambda: wall[0])
        calls = []
        payload = {
            "data": [{
                "id": "solana_CachePool", "type": "pool",
                "attributes": {"address": "CachePool", "base_token_price_usd": "2",
                               "reserve_in_usd": "10000"},
                "relationships": {
                    "base_token": {"data": {"type": "token", "id": "solana_Base"}},
                    "quote_token": {"data": {"type": "token", "id": "solana_Quote"}},
                    "dex": {"data": {"type": "dex", "id": "pumpswap"}},
                },
            }],
            "included": [
                {"id": "solana_Base", "type": "token",
                 "attributes": {"address": "Base", "name": "Cache receipt", "symbol": "CACHE"}},
                {"id": "solana_Quote", "type": "token",
                 "attributes": {"address": "Quote", "name": "Quote", "symbol": "Q"}},
            ],
        }

        def handler(request):
            calls.append(request.url)
            return httpx.Response(200, json=payload)

        http = HttpClient(transport=httpx.MockTransport(handler), min_host_interval=0)
        collector = GeckoNewPoolsCollector(http, "solana")
        try:
            first = (await collector.poll())[0]
            wall[0] += timedelta(seconds=1)
            cached = (await collector.poll())[0]
            assert len(calls) == 1  # Exercise the real HttpClient TTL cache.
            assert first.token_id == cached.token_id == "solana:Base"
            first_pair, cached_pair = first.raw["market_pair"], cached.raw["market_pair"]
            assert first_pair["priceUsd"] == cached_pair["priceUsd"] == "2"
            assert first_pair["liquidity"] == cached_pair["liquidity"] == {"usd": 10000.0}
            assert first_pair["observedAt"] == "2026-09-07T00:00:00Z"
            assert cached_pair["observedAt"] == first_pair["observedAt"]
        finally:
            await http.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("chain", ["solana", "bsc", "robinhood"])
def test_fresh_dex_response_advances_even_when_price_and_payload_are_unchanged(monkeypatch, chain):
    async def scenario():
        wall = [datetime(2026, 9, 7, tzinfo=timezone.utc)]
        monkeypatch.setattr("memetrader.collectors.utcnow", lambda: wall[0])
        pair = _pair(chain)
        calls = []

        def handler(request):
            calls.append(request.url)
            return httpx.Response(200, json=[pair])

        http = HttpClient(transport=httpx.MockTransport(handler), min_host_interval=0)
        dex = DexScreenerClient(http)
        address = pair["baseToken"]["address"]
        token_id = f"{chain}:{address}"
        try:
            _, warm = (await dex.batch_quote(chain, [address]))[token_id]
            wall[0] += timedelta(seconds=1)
            _, fresh = (await dex.batch_quote_fresh(chain, [address]))[token_id]
            wall[0] += timedelta(seconds=1)
            _, next_fresh = (await dex.batch_quote_fresh(chain, [address]))[token_id]
            assert len(calls) == 3  # Held-token reads still bypass the hydration cache.
            assert warm.observed_at < fresh.observed_at < next_fresh.observed_at
            assert next_fresh.observed_at == wall[0]
            assert warm.raw["pair"] == fresh.raw["pair"] == next_fresh.raw["pair"]
        finally:
            await http.close()

    asyncio.run(scenario())
