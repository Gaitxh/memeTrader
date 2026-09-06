from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.market_api import (
    CoinGeckoDemoPoolClient,
    GeckoTerminalPoolClient,
    normalize_gecko_pool,
)


START = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.value = START

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += timedelta(seconds=seconds)


class Response:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class RawClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class Http:
    def __init__(self, outcomes):
        self.client = RawClient(outcomes)
        self.reservations = []

    async def _reserve_host_request_start(self, host):
        self.reservations.append(host)


class BudgetConsumedWhileQueuedHttp(Http):
    def __init__(self, store):
        super().__init__([])
        self.store = store

    async def _reserve_host_request_start(self, host):
        await super()._reserve_host_request_start(host)
        self.store.set_kv(
            "market_api:coingecko-demo:usage",
            {"month": "2026-09", "monthly": 1, "day": "2026-09-05", "daily": 1},
        )


class Store:
    def __init__(self, value=None):
        self.values = {}
        if value is not None:
            self.values["market_api:coingecko-demo:usage"] = value

    def get_kv(self, key, default=None):
        return copy.deepcopy(self.values.get(key, default))

    def set_kv(self, key, value):
        self.values[key] = copy.deepcopy(value)


def gecko_payload(address="pool-A"):
    pool = {
        "type": "pool",
        "id": f"solana_{address}",
        "attributes": {
            "address": address,
            "base_token_price_usd": "0.0123",
            "reserve_in_usd": "4567.8",
            "volume_usd": {"m5": "90.5"},
            "transactions": {"m5": {"buys": 7, "sells": 3}},
            "pool_created_at": "2026-09-05T11:00:00Z",
            "fdv_usd": "123456",
            "market_cap_usd": "65432",
            "last_updated_at": "2026-09-05T11:59:59Z",
        },
        "relationships": {
            "base_token": {"data": {"type": "token", "id": "solana_BASE"}},
            "quote_token": {"data": {"type": "token", "id": "solana_QUOTE"}},
            "dex": {"data": {"type": "dex", "id": "raydium"}},
        },
    }
    included = [
        {
            "type": "token",
            "id": "solana_BASE",
            "attributes": {"address": "BASE", "name": "Base", "symbol": "B"},
        },
        {
            "type": "token",
            "id": "solana_QUOTE",
            "attributes": {"address": "QUOTE", "name": "USD Coin", "symbol": "USDC"},
        },
        {"type": "dex", "id": "raydium", "attributes": {"name": "Raydium"}},
    ]
    return {"data": [pool], "included": included}


def run(awaitable):
    return asyncio.run(awaitable)


def test_normalize_gecko_pool_is_identity_bound_and_keeps_receipt_provenance():
    payload = gecko_payload()
    payload["data"][0]["attributes"]["volume_usd"]["h1"] = "120.5"
    payload["data"][0]["attributes"]["transactions"]["h1"] = {"buys": 9, "sells": 4}
    payload["data"][0]["attributes"]["base_token_price_quote_token"] = "0.125"
    pair = normalize_gecko_pool(payload["data"][0], payload["included"], "solana", START)
    assert pair is not None
    assert (pair["chainId"], pair["tokenAddress"], pair["pairAddress"]) == (
        "solana", "BASE", "pool-A"
    )
    assert pair["baseToken"]["address"] == "BASE"
    assert pair["quoteToken"]["address"] == "QUOTE"
    assert pair["dexId"] == "raydium"
    assert pair["priceUsd"] == "0.0123"
    assert pair["priceNative"] == 0.125
    assert pair["liquidity"]["usd"] == pytest.approx(4567.8)
    assert pair["volume"]["m5"] == pytest.approx(90.5)
    assert pair["txns"]["m5"] == {"buys": 7, "sells": 3}
    assert pair["volume"]["h1"] - pair["volume"]["m5"] == 30.0
    assert sum(pair["txns"]["h1"].values()) - sum(pair["txns"]["m5"].values()) == 3
    assert pair["pairCreatedAt"] == 1_788_606_000_000
    assert pair["marketCap"] == pytest.approx(65432)
    assert pair["fdv"] == pytest.approx(123456)
    assert pair["source"] == "coingecko-demo"
    assert pair["url"] == "https://www.geckoterminal.com/solana/pools/pool-A"
    assert pair["observedAt"] == "2026-09-05T12:00:00Z"
    assert pair["raw"]["pool"]["attributes"]["last_updated_at"] != pair["observedAt"]

    missing_base = copy.deepcopy(payload["included"])
    missing_base[0]["attributes"].pop("address")
    assert normalize_gecko_pool(payload["data"][0], missing_base, "solana", START) is None

    bad_id = copy.deepcopy(payload["data"][0])
    bad_id["id"] = "solana_another-pool"
    assert normalize_gecko_pool(bad_id, payload["included"], "solana", START) is None

    missing_counts = copy.deepcopy(payload["data"][0])
    missing_counts["attributes"]["transactions"]["m5"] = {}
    missing_counts["attributes"]["transactions"].pop("h1")
    missing_counts["attributes"]["volume_usd"].pop("h1")
    normalized = normalize_gecko_pool(
        missing_counts, payload["included"], "solana", START, provider="geckoterminal"
    )
    assert normalized["txns"]["m5"] == {"buys": None, "sells": None}
    assert normalized["txns"]["h1"] == {"buys": None, "sells": None}
    assert normalized["volume"]["h1"] is None
    assert normalized["source"] == "geckoterminal"
    unknown_ratio = gecko_payload()
    assert normalize_gecko_pool(unknown_ratio["data"][0], unknown_ratio["included"],
                                "solana", START)["priceNative"] is None


@pytest.mark.parametrize("validator", ["etag", "date"])
def test_public_exact_pool_client_preserves_cache_generation_and_identity(validator):
    import httpx
    from memetrader.collectors import HttpClient

    async def scenario():
        clock = Clock()
        payload = gecko_payload()
        unsolicited = copy.deepcopy(payload["data"][0])
        unsolicited["id"], unsolicited["attributes"]["address"] = "solana_other", "other"
        payload["data"].append(unsolicited)
        bad_identity = copy.deepcopy(payload["data"][0])
        bad_identity["id"] = "bsc_pool-A"
        payload["data"].append(bad_identity)
        calls = []
        def respond(request):
            calls.append(request)
            headers = {"cache-control": "public, max-age=30, s-maxage=60", "age": "5",
                       validator: '"generation-1"' if validator == "etag" else "Sat, 05 Sep 2026 12:00:00 GMT"}
            if len(calls) == 3:
                headers[validator] = '"generation-2"' if validator == "etag" else "Sat, 05 Sep 2026 12:02:00 GMT"
            return httpx.Response(200, json=payload if len(calls) <= 3 else {"data": []}, headers=headers)
        http = HttpClient(transport=httpx.MockTransport(respond), min_host_interval=0)
        client = GeckoTerminalPoolClient(http, now_fn=clock)
        first = await client.get_pools("solana", ["pool-A", "pool-A"])
        assert list(first) == ["pool-A"] and first["pool-A"]["provider"] == "geckoterminal"
        assert "/pools/pool-A" in str(calls[0].url)
        assert calls[0].url.params["include"] == "base_token,quote_token,dex"
        clock.advance(54)
        cached = await client.get_pools("solana", ["pool-A"])
        assert len(calls) == 1 and cached["pool-A"]["observedAt"] == first["pool-A"]["observedAt"]
        assert cached["pool-A"]["raw"]["http_cache"]["local_cache_hit"] is True
        clock.advance(2)
        same = await client.get_pools("solana", ["pool-A"])
        assert same["pool-A"]["observedAt"] == first["pool-A"]["observedAt"]
        assert same["pool-A"]["raw"]["http_cache"]["received_at"] != first["pool-A"]["observedAt"]
        assert same["pool-A"]["raw"]["http_cache"]["generation_reused"] is True
        clock.advance(56)
        fresh = await client.get_pools("solana", ["pool-A"])
        assert fresh["pool-A"]["observedAt"] != first["pool-A"]["observedAt"]
        clock.advance(56)
        assert await client.get_pools("solana", ["pool-A"]) == {}
        await http.close()

        single_http = HttpClient(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={"data": payload["data"][0], "included": payload["included"]})),
            min_host_interval=0)
        single = await GeckoTerminalPoolClient(single_http).get_pools("solana", ["pool-A"])
        assert list(single) == ["pool-A"]
        await single_http.close()

    asyncio.run(scenario())


def test_public_exact_pool_client_429_propagates_without_retry():
    import httpx
    from memetrader.collectors import HttpClient

    async def scenario():
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "30"})
        http = HttpClient(transport=httpx.MockTransport(respond), min_host_interval=0)
        client = GeckoTerminalPoolClient(http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_pools("bsc", ["0x" + "a" * 64])
        assert len(calls) == 1
        with pytest.raises(ValueError, match="max_30"):
            await client.get_pools("bsc", [str(i) for i in range(31)])
        assert len(calls) == 1
        await http.close()

    asyncio.run(scenario())


def test_success_uses_exact_endpoint_no_redirect_and_cache_keeps_observed_time():
    clock = Clock()
    http = Http([Response(payload=gecko_payload()), Response(payload=gecko_payload())])
    store = Store()
    client = CoinGeckoDemoPoolClient(http, "demo-secret", store=store, now_fn=clock)

    first = run(client.get_pools("solana", ["pool-A", "pool-A"]))
    assert first["pool-A"]["observedAt"] == "2026-09-05T12:00:00Z"
    assert len(http.client.calls) == 1 and http.reservations == ["api.coingecko.com"]
    url, kwargs = http.client.calls[0]
    assert url.endswith("/networks/solana/pools/multi/pool-A")
    assert kwargs["params"] == {"include": "base_token,quote_token,dex"}
    assert kwargs["headers"] == {"x-cg-demo-api-key": "demo-secret"}
    assert kwargs["follow_redirects"] is False

    clock.advance(30)
    cached = run(client.get_pools("solana", ["pool-A"]))
    assert len(http.client.calls) == 1
    assert cached["pool-A"]["observedAt"] == first["pool-A"]["observedAt"]

    clock.advance(31)
    refreshed = run(client.get_pools("solana", ["pool-A"]))
    assert len(http.client.calls) == 2
    assert refreshed["pool-A"]["observedAt"] == "2026-09-05T12:01:01Z"
    status = client.status()
    assert status["local_daily_used"] == 2
    assert status["remaining_local_daily"] == 238
    assert status["remaining_local_monthly"] == 7998
    assert status["local_usage_only"] is True
    assert "demo-secret" not in repr(status)


def test_absent_or_wrong_identity_pool_is_unavailable_not_dead_and_not_cached():
    clock = Clock()
    wrong = gecko_payload("other-pool")
    http = Http([Response(payload=wrong), Response(payload={"data": [], "included": []})])
    client = CoinGeckoDemoPoolClient(http, "key", now_fn=clock)
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert client.status()["cache_count"] == 0
    clock.advance(1)
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert len(http.client.calls) == 2
    assert "dead" not in repr(client.status()).lower()


def test_evm_pool_selection_and_cache_key_are_case_insensitive_only_for_0x():
    clock = Clock()
    payload = gecko_payload("0xabc")
    payload["data"][0]["id"] = "eth_0xABC"
    payload["data"][0]["relationships"]["base_token"]["data"]["id"] = "eth_0xBASE"
    payload["data"][0]["relationships"]["quote_token"]["data"]["id"] = "eth_0xQUOTE"
    payload["included"][0]["id"] = "eth_0xBASE"
    payload["included"][0]["attributes"]["address"] = "0xbase"
    payload["included"][1]["id"] = "eth_0xQUOTE"
    payload["included"][1]["attributes"]["address"] = "0xquote"
    http = Http([Response(payload=payload)])
    client = CoinGeckoDemoPoolClient(http, "key", now_fn=clock)
    first = run(client.get_pools("eth", ["0xAbC"]))
    assert list(first) == ["0xabc"]
    assert first["0xabc"]["pairAddress"] == "0xabc"
    clock.advance(10)
    second = run(client.get_pools("eth", ["0xABC"]))
    assert list(second) == ["0xabc"]
    assert second["0xabc"]["observedAt"] == first["0xabc"]["observedAt"]
    assert len(http.client.calls) == 1


def test_network_errors_are_charged_once_and_local_budget_is_persistent():
    clock = Clock()
    store = Store()
    http = Http([Response(status_code=500, payload={})])
    client = CoinGeckoDemoPoolClient(
        http, "key", store=store, now_fn=clock, daily_limit=1
    )
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert len(http.client.calls) == 1
    assert client.status()["remaining_local_daily"] == 0
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert len(http.client.calls) == 1

    restarted = CoinGeckoDemoPoolClient(
        Http([]), "key", store=store, now_fn=clock, daily_limit=1
    )
    assert restarted.available() is False
    assert restarted.status()["availability_reason"] == "local_daily_budget_exhausted"


def test_quota_is_rechecked_after_waiting_for_host_reservation():
    clock = Clock()
    store = Store()
    http = BudgetConsumedWhileQueuedHttp(store)
    client = CoinGeckoDemoPoolClient(
        http, "key", store=store, now_fn=clock, daily_limit=1
    )
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert http.reservations == ["api.coingecko.com"]
    assert http.client.calls == []
    assert client.status()["availability_reason"] == "local_daily_budget_exhausted"


def test_429_cooldown_and_auth_disable_do_not_retry_or_expose_key():
    clock = Clock()
    limited_http = Http([Response(status_code=429, headers={"Retry-After": "30"})])
    limited = CoinGeckoDemoPoolClient(limited_http, "rate-key", now_fn=clock)
    assert run(limited.get_pools("solana", ["pool-A"])) == {}
    assert len(limited_http.client.calls) == 1
    assert limited.available() is False
    clock.advance(31)
    assert limited.available() is True

    auth_http = Http([Response(status_code=403, payload={})])
    auth = CoinGeckoDemoPoolClient(auth_http, "auth-key", now_fn=clock)
    assert run(auth.get_pools("solana", ["pool-A"])) == {}
    assert auth.status()["disabled_until_restart"] is True
    assert run(auth.get_pools("solana", ["pool-A"])) == {}
    assert len(auth_http.client.calls) == 1
    assert "auth-key" not in repr(auth.status())


def test_transport_backoff_charges_call_and_batch_size_is_caller_bounded():
    clock = Clock()
    http = Http([OSError("offline")])
    client = CoinGeckoDemoPoolClient(http, "key", now_fn=clock)
    assert run(client.get_pools("solana", ["pool-A"])) == {}
    assert len(http.client.calls) == 1
    status = client.status()
    assert status["local_daily_used"] == 1
    assert status["availability_reason"] == "cooldown"
    with pytest.raises(ValueError, match="max_30"):
        run(client.get_pools("solana", [f"pool-{i}" for i in range(31)]))
