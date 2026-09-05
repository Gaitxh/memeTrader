import json
from datetime import datetime, timezone
import httpx

from memetrader.authoritative_events import collect_okx_listing_events


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
