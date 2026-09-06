import json
from datetime import datetime, timezone
import httpx

from memetrader.authoritative_events import collect_coinbase_status_observations, collect_kraken_listing_events, collect_kucoin_listing_events, collect_okx_listing_events


class Response:
    def __init__(self, value):
        self.content = value if isinstance(value, bytes) else (json.dumps(value) if isinstance(value, dict) else value).encode()
    def json(self):
        return json.loads(self.content)


class Http:
    def __init__(self, api, article):
        self.api = httpx.Response(200, json=api, request=httpx.Request("GET", "https://www.okx.com/api/v5/support/announcements"))
        self.article = httpx.Response(200, text=article, request=httpx.Request("GET", "https://www.okx.com/help/list-cat"))
    async def get_public_document(self, url, **kwargs):
        return self.api if url.endswith("announcements") else self.article


class RssHttp:
    def __init__(self, url, content):
        self.response = httpx.Response(200, content=content.encode(), request=httpx.Request("GET", url))
    async def get_public_document(self, url, **kwargs):
        return self.response


class KucoinHttp:
    def __init__(self, payload):
        self.response = httpx.Response(
            200, json=payload,
            request=httpx.Request("GET", "https://api.kucoin.com/api/v3/announcements"),
        )
        self.calls = []
    async def get_public_document(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_kucoin_public_listing_feed_keeps_unknown_ca_diagnostic():
    now = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
    exact = "https://solscan.io/token/So11111111111111111111111111111111111111112"
    items = [
        {
            "annTitle": "CAT (CAT) Gets Listed!",
            "annType": ["latest-announcements", "new-listings"],
            "annDesc": f"KuCoin will list CAT. Contract: {exact}",
            "annUrl": "https://www.kucoin.com/announcement/cat-gets-listed",
            "cTime": int(now.timestamp() * 1000),
        },
        {
            "annTitle": "DOG (DOG) Gets Listed!",
            "annType": ["new-listings"],
            "annDesc": "KuCoin will list DOG.",
            "annUrl": "https://www.kucoin.com/announcement/dog-gets-listed",
            "cTime": int(now.timestamp() * 1000),
        },
    ]
    http = KucoinHttp({"code": "200000", "data": {"items": items}})
    result = __import__("asyncio").run(collect_kucoin_listing_events(http, now=now))
    assert len(http.calls) == 1
    assert http.calls[0][1]["maximum_bytes"] == 524_288
    assert result["events"][0]["contract_address"].startswith("So")
    assert result["events"][0]["next_frame_trade_required"] is True
    assert result["diagnostics"][0]["kind"] == "kucoin_listing_without_exact_ca"
    assert result["diagnostics"][0]["search_symbol"] == "DOG"


def test_kraken_rss_is_no_ca_candidate_not_trade_event():
    rss = '<rss><channel><item><title>SOFID is available for trading!</title><link>https://blog.kraken.com/product/asset-listings/sofid-is-available-for-trading</link><pubDate>Fri, 04 Sep 2026 15:09:16 +0000</pubDate></item></channel></rss>'
    result = __import__("asyncio").run(collect_kraken_listing_events(
        RssHttp("https://blog.kraken.com/feed", rss), now=datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)))
    assert result["events"] == []
    assert result["diagnostics"][0]["kind"] == "kraken_listing_without_exact_ca"


def test_coinbase_status_rss_is_observation_only():
    rss = '<rss><channel><item><title>Delayed Sends/Receives - Mina</title><link>https://status.exchange.coinbase.com/incidents/x</link><pubDate>Thu, 03 Sep 2026 21:00:23 -0700</pubDate></item></channel></rss>'
    result = __import__("asyncio").run(collect_coinbase_status_observations(
        RssHttp("https://status.exchange.coinbase.com/history.rss", rss), now=datetime(2026, 9, 4, 5, 0, tzinfo=timezone.utc)))
    assert result["events"] == []
    assert result["diagnostics"][0]["kind"] == "coinbase_status_observation"


def test_okx_returns_only_exact_explorer_ca_and_preserves_timestamps():
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    api = {"code": "0", "data": [{"details": [{
        "annType": "announcements-new-listings", "title": "OKX to list CAT",
        "url": "https://www.okx.com/help/list-cat", "pTime": "1788609599000",
    }]}]}
    article = "OKX will list CAT. https://solscan.io/token/So11111111111111111111111111111111111111112"
    result = __import__("asyncio").run(collect_okx_listing_events(
        Http(api, article), now=now, max_age_seconds=3600))
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["source_kind"] == "first_party"
    assert event["chain"] == "solana"
    assert event["contract_address"].startswith("So")
    assert event["published_at"] <= event["observed_at"] <= event["ingested_at"]


def test_okx_without_ca_is_diagnostic_not_entry():
    api = {"code": "0", "data": [{"details": [{
        "title": "OKX to list CAT", "url": "https://www.okx.com/help/list-cat",
        "pTime": "1788609599000",
    }]}]}
    result = __import__("asyncio").run(collect_okx_listing_events(
        Http(api, "OKX will list CAT; contract coming soon"),
        now=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc), max_age_seconds=3600))
    assert result["events"] == []
    assert result["diagnostics"][0]["kind"] == "okx_listing_without_exact_ca"


def test_okx_article_budget_and_ambiguous_hrefs_do_not_emit_event():
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    details = [{"title": "OKX to list CAT", "url": "https://www.okx.com/help/list-cat", "pTime": "1788609599000"} for _ in range(4)]
    api = {"code": "0", "data": [{"details": details}]}
    article = ('<a href="https://solscan.io/token/So11111111111111111111111111111111111111112">A</a>'
               '<a href="https://bscscan.com/token/0x1111111111111111111111111111111111111111">B</a>')
    result = __import__("asyncio").run(collect_okx_listing_events(
        Http(api, article), now=now, max_age_seconds=3600))
    assert result["events"] == []
    assert result["diagnostics"][0]["kind"] == "ambiguous_contract_set"
