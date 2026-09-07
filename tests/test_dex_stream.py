import asyncio
import json
import time
from datetime import timedelta

import httpx
import pytest

from memetrader.collectors import DexScreenerClient, HttpClient
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
