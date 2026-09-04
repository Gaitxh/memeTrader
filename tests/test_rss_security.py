from __future__ import annotations

import asyncio
import gzip
import json
import socket
from pathlib import Path

import httpx
import pytest

from memetrader.collectors import (
    FeedRedirectError,
    FeedResponseTooLarge,
    HttpClient,
    InvalidFeedContentType,
    RSSCollector,
    UnsupportedFeedContentEncoding,
    UnsafeFeedURL,
    normalize_loopback_socks5_proxy_url,
    rss_cache_key,
)
from memetrader.models import utcnow
from memetrader.runtime import initial_config, load_config
from memetrader.store import Store
from memetrader.web import WebData


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>News</title>
<item><title>Fresh story</title><link>https://public.example/story</link>
<pubDate>Sun, 30 Aug 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>News</title>
<entry><title>Fresh atom story</title><link href="https://public.example/atom-story" />
<updated>2026-08-30T01:00:00Z</updated></entry>
</feed>"""


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes, on_read=None):
        self.chunks = chunks
        self.on_read = on_read

    async def __aiter__(self):
        if self.on_read is not None:
            self.on_read()
        for chunk in self.chunks:
            yield chunk


class PeerStream:
    def __init__(self, address: str):
        self.address = address

    def get_extra_info(self, key):
        return (self.address, 443) if key == "server_addr" else None


def streamed_response(
    request: httpx.Request,
    content: bytes,
    *,
    headers: dict[str, str] | None = None,
    extensions: dict | None = None,
) -> httpx.Response:
    return httpx.Response(
        200,
        stream=ChunkStream(content),
        headers=headers,
        extensions=extensions,
        request=request,
    )


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch):
    def resolve(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("memetrader.collectors.socket.getaddrinfo", resolve)


def run(value):
    return asyncio.run(value)


def test_direct_private_feed_url_is_rejected_before_request():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=RSS, request=request)

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(UnsafeFeedURL):
                await RSSCollector(http, "private", "http://127.0.0.1/feed.xml").poll()
            with pytest.raises(UnsafeFeedURL):
                await RSSCollector(http, "credentials", "https://user:pass@public.example/feed.xml").poll()
            with pytest.raises(UnsafeFeedURL):
                await RSSCollector(http, "fragment", "https://public.example/feed.xml#items").poll()
        finally:
            await http.close()

    run(scenario())
    assert calls == 0


def test_http_client_ttl_cache_prunes_expired_entries_and_bounds_size(monkeypatch):
    clock = [100.0]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"url": str(request.url)}, request=request)

    monkeypatch.setattr("memetrader.collectors.time.monotonic", lambda: clock[0])

    async def scenario():
        http = HttpClient(
            transport=httpx.MockTransport(handler), min_host_interval=0,
        )
        try:
            for index in range(HttpClient.MAX_CACHE_ENTRIES):
                await http.get(
                    "https://public.example/cache",
                    params={"index": index}, ttl=1,
                )
            assert len(http._cache) == HttpClient.MAX_CACHE_ENTRIES
            clock[0] = 102.0
            await http.get(
                "https://public.example/cache",
                params={"index": "fresh"}, ttl=1,
            )
            assert len(http._cache) == 1
            assert next(iter(http._cache.values()))[0] == pytest.approx(103.0)
        finally:
            await http.close()

    run(scenario())


def test_http_client_spaces_request_starts_without_serializing_responses():
    starts = []

    async def handler(request: httpx.Request) -> httpx.Response:
        starts.append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.15)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def scenario():
        http = HttpClient(
            transport=httpx.MockTransport(handler), min_host_interval=0.03,
        )
        try:
            started = asyncio.get_running_loop().time()
            await asyncio.gather(
                http.get("https://public.example/one"),
                http.get("https://public.example/two"),
            )
            return asyncio.get_running_loop().time() - started
        finally:
            await http.close()

    elapsed = run(scenario())
    assert starts[1] - starts[0] >= 0.02
    assert elapsed < 0.25


def test_runtime_config_rejects_private_static_feed_and_invalid_limits(tmp_path: Path):
    config = initial_config()
    config["sources"]["rss"] = [{"name": "private", "url": "http://10.0.0.2/feed"}]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="sources.rss URLs"):
        load_config(path)

    config["sources"]["rss"] = []
    config["sources"]["rss_max_response_bytes"] = 10
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="rss_max_response_bytes"):
        load_config(path)


def test_rss_proxy_config_accepts_only_credential_free_literal_loopback_socks5(tmp_path: Path):
    assert normalize_loopback_socks5_proxy_url("") == ""
    assert (
        normalize_loopback_socks5_proxy_url("socks5://127.0.0.1:7890")
        == "socks5://127.0.0.1:7890"
    )
    assert normalize_loopback_socks5_proxy_url("socks5://[::1]:1080") == "socks5://[::1]:1080"
    invalid = [
        "socks5h://127.0.0.1:7890",
        "http://127.0.0.1:7890",
        "socks5://localhost:7890",
        "socks5://192.168.1.2:7890",
        "socks5://user:pass@127.0.0.1:7890",
        "socks5://127.0.0.1:7890/",
        "socks5://127.0.0.1:7890?dns=remote",
        "socks5://127.0.0.1:7890#fragment",
        "socks5://127.0.0.1",
        "socks5://127.0.0.1:0",
        "socks5://127.0.0.1:65536",
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            normalize_loopback_socks5_proxy_url(value)

    config = initial_config()
    config["sources"]["rss_proxy_url"] = "socks5://localhost:7890"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="rss_proxy_url"):
        load_config(path)

    config["sources"]["rss_proxy_url"] = "socks5://127.0.0.1:7890"
    path.write_text(json.dumps(config), encoding="utf-8")
    loaded, _ = load_config(path)
    assert loaded["sources"]["rss_proxy_url"] == "socks5://127.0.0.1:7890"


def test_public_redirect_to_private_destination_is_rejected():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"}, request=request)

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(UnsafeFeedURL):
                await RSSCollector(http, "redirect", "https://public.example/feed.xml").poll()
        finally:
            await http.close()

    run(scenario())
    assert calls == 1


def test_public_document_handoff_rejects_private_and_telegram_redirects_before_fetch():
    async def scenario(location: str, expected_exception: type[Exception]):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(302, headers={"Location": location}, request=request)

        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(expected_exception):
                await http.get_public_document(
                    "https://public.example/story",
                    forbidden_host_suffixes={"t.me", "telegram.me", "telegram.org"},
                )
        finally:
            await http.close()
        assert calls == 1

    run(scenario("http://169.254.169.254/latest/meta-data", UnsafeFeedURL))
    run(scenario("https://t.me/BNONews/123", UnsafeFeedURL))


def test_feed_redirect_loop_and_excess_are_bounded():
    async def loop_scenario():
        def handler(request: httpx.Request) -> httpx.Response:
            target = "/b" if request.url.path == "/a" else "/a"
            return httpx.Response(302, headers={"Location": target}, request=request)

        http = HttpClient(transport=httpx.MockTransport(handler), feed_max_redirects=5)
        try:
            with pytest.raises(FeedRedirectError, match="loop"):
                await RSSCollector(http, "loop", "https://public.example/a").poll()
        finally:
            await http.close()

    async def excess_scenario():
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            number = int(request.url.path.strip("/") or 0)
            return httpx.Response(302, headers={"Location": f"/{number + 1}"}, request=request)

        http = HttpClient(transport=httpx.MockTransport(handler), feed_max_redirects=2)
        try:
            with pytest.raises(FeedRedirectError, match="limit"):
                await RSSCollector(http, "excess", "https://public.example/0").poll()
            assert calls == 3
        finally:
            await http.close()

    run(loop_scenario())
    run(excess_scenario())


def test_oversized_feed_body_is_rejected_before_xml_parse():
    body = b"<rss>" + (b"x" * 200) + b"</rss>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/rss+xml", "Content-Length": str(len(body))},
            request=request,
        )

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler), feed_max_response_bytes=64)
        try:
            with pytest.raises(FeedResponseTooLarge):
                await RSSCollector(http, "large", "https://public.example/feed.xml").poll()
        finally:
            await http.close()

    run(scenario())


def test_bad_feed_content_type_is_rejected_even_when_body_mentions_rss():
    def handler(request: httpx.Request) -> httpx.Response:
        return streamed_response(request, RSS, headers={"Content-Type": "text/html"})

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(InvalidFeedContentType):
                await RSSCollector(http, "html", "https://public.example/feed.xml").poll()
        finally:
            await http.close()

    run(scenario())


def test_compressed_feed_is_rejected_before_read_and_identity_response_is_sanitized():
    compressed_read = False
    requests: list[httpx.Request] = []

    def compressed_handler(request: httpx.Request) -> httpx.Response:
        nonlocal compressed_read
        requests.append(request)

        def mark_read():
            nonlocal compressed_read
            compressed_read = True

        return httpx.Response(
            200,
            stream=ChunkStream(gzip.compress(RSS), on_read=mark_read),
            headers={"Content-Type": "application/rss+xml", "Content-Encoding": "gzip"},
            request=request,
        )

    async def reject_compressed():
        http = HttpClient(transport=httpx.MockTransport(compressed_handler))
        try:
            with pytest.raises(UnsupportedFeedContentEncoding):
                await http.get_public_feed("https://public.example/feed.xml")
        finally:
            await http.close()

    run(reject_compressed())
    assert requests[0].headers["Accept-Encoding"] == "identity"
    assert compressed_read is False

    def identity_handler(request: httpx.Request) -> httpx.Response:
        return streamed_response(
            request,
            RSS,
            headers={
                "Content-Type": "application/rss+xml",
                "Content-Encoding": "identity",
                "Content-Length": str(len(RSS)),
            },
        )

    async def accept_identity():
        http = HttpClient(transport=httpx.MockTransport(identity_handler))
        try:
            response = await http.get_public_feed("https://public.example/feed.xml")
            assert response.content == RSS
            assert "Content-Encoding" not in response.headers
            assert "Content-Length" not in response.headers
        finally:
            await http.close()

    run(accept_identity())


def test_chunked_feed_without_content_length_is_still_bounded():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=ChunkStream(b"<rss>" + b"x" * 40, b"y" * 40 + b"</rss>"),
            headers={"Content-Type": "application/rss+xml", "Transfer-Encoding": "chunked"},
            request=request,
        )

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler), feed_max_response_bytes=64)
        try:
            with pytest.raises(FeedResponseTooLarge):
                await http.get_public_feed("https://public.example/feed.xml")
        finally:
            await http.close()

    run(scenario())


def test_feed_request_is_ip_pinned_with_original_host_and_sni_metadata():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return streamed_response(request, RSS, headers={"Content-Type": "application/rss+xml"})

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            rows = await RSSCollector(http, "pinned", "https://public.example/feed.xml").poll()
            assert len(rows) == 1
        finally:
            await http.close()

    run(scenario())
    request = requests[0]
    assert request.url.host == "93.184.216.34"
    assert request.headers["Host"] == "public.example"
    assert request.extensions["sni_hostname"] == "public.example"
    assert request.extensions["feed_original_url"] == "https://public.example/feed.xml"
    assert request.extensions["feed_approved_ip"] == "93.184.216.34"


def test_ordinary_http_get_keeps_its_existing_unpinned_behavior():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            response = await http.get("https://ordinary.example/data")
            assert response.json() == {"ok": True}
        finally:
            await http.close()

    run(scenario())
    assert requests[0].url.host == "ordinary.example"
    assert "feed_approved_ip" not in requests[0].extensions


def test_mixed_public_private_dns_is_rejected_before_request(monkeypatch: pytest.MonkeyPatch):
    def mixed_dns(host, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.8", 0)),
        ]

    monkeypatch.setattr("memetrader.collectors.socket.getaddrinfo", mixed_dns)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return streamed_response(request, RSS, headers={"Content-Type": "application/rss+xml"})

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(UnsafeFeedURL, match="non-public"):
                await http.get_public_feed("https://mixed.example/feed.xml")
        finally:
            await http.close()

    run(scenario())
    assert calls == 0


def test_feed_peer_must_match_the_approved_pinned_destination():
    def handler(request: httpx.Request) -> httpx.Response:
        return streamed_response(
            request,
            RSS,
            headers={"Content-Type": "application/rss+xml"},
            extensions={"network_stream": PeerStream("1.1.1.1")},
        )

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(UnsafeFeedURL, match="unapproved"):
                await http.get_public_feed("https://public.example/feed.xml")
        finally:
            await http.close()

    run(scenario())


def test_socks_feed_peer_must_be_the_exact_configured_loopback_proxy():
    def handler(peer: str):
        def respond(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "93.184.216.34"
            assert request.headers["Host"] == "public.example"
            assert request.extensions["sni_hostname"] == "public.example"
            return streamed_response(
                request,
                RSS,
                headers={"Content-Type": "application/rss+xml"},
                extensions={"network_stream": PeerStream(peer)},
            )

        return respond

    async def accepted():
        http = HttpClient(
            feed_proxy_url="socks5://127.0.0.1:7890",
            transport=httpx.MockTransport(handler("127.0.0.1")),
        )
        try:
            assert len(await RSSCollector(http, "proxy", "https://public.example/feed.xml").poll()) == 1
        finally:
            await http.close()

    async def rejected():
        http = HttpClient(
            feed_proxy_url="socks5://127.0.0.1:7890",
            transport=httpx.MockTransport(handler("127.0.0.2")),
        )
        try:
            with pytest.raises(UnsafeFeedURL, match="unapproved"):
                await http.get_public_feed("https://public.example/feed.xml")
        finally:
            await http.close()

    run(accepted())
    run(rejected())


def test_feed_connect_failure_tries_only_the_preapproved_addresses(monkeypatch: pytest.MonkeyPatch):
    def two_public_addresses(host, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("1.1.1.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0)),
        ]

    monkeypatch.setattr("memetrader.collectors.socket.getaddrinfo", two_public_addresses)
    attempted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempted.append(request.url.host)
        if request.url.host == "1.1.1.1":
            raise httpx.ConnectError("first approved address failed", request=request)
        return streamed_response(request, RSS, headers={"Content-Type": "application/rss+xml"})

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        try:
            assert len(await RSSCollector(http, "retry", "https://public.example/feed.xml").poll()) == 1
        finally:
            await http.close()

    run(scenario())
    assert attempted == ["1.1.1.1", "93.184.216.34"]


def test_etag_and_last_modified_survive_store_restart_and_304_is_truthful(tmp_path: Path):
    db = tmp_path / "rss.sqlite3"
    seen_headers: list[httpx.Headers] = []

    def first_handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        return streamed_response(
            request,
            RSS,
            headers={
                "Content-Type": "application/rss+xml",
                "ETag": '"feed-v1"',
                "Last-Modified": "Sun, 30 Aug 2026 01:00:00 GMT",
            },
        )

    async def first_poll():
        store = Store(db)
        http = HttpClient(transport=httpx.MockTransport(first_handler), conditional_store=store)
        try:
            rows = await RSSCollector(http, "etag", "https://public.example/feed.xml").poll()
            assert len(rows) == 1
        finally:
            await http.close()
            store.close()

    run(first_poll())
    assert "if-none-match" not in seen_headers[0]

    def second_handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        assert request.headers["If-None-Match"] == '"feed-v1"'
        assert request.headers["If-Modified-Since"] == "Sun, 30 Aug 2026 01:00:00 GMT"
        return httpx.Response(304, headers={"ETag": '"feed-v1"'}, request=request)

    async def second_poll():
        store = Store(db)
        http = HttpClient(transport=httpx.MockTransport(second_handler), conditional_store=store)
        collector = RSSCollector(http, "etag", "https://public.example/feed.xml")
        try:
            assert await collector.poll() == []
            assert collector.last_not_modified is True
            cache = store.get_kv(rss_cache_key("https://public.example/feed.xml"))
            assert cache["last_status"] == 304
            assert cache["etag"] == '"feed-v1"'
        finally:
            await http.close()
            store.close()

    run(second_poll())


def test_rss_proxy_configuration_is_not_exposed_by_console_api_payloads(tmp_path: Path):
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["sources"]["rss_proxy_url"] = "socks5://127.0.0.1:7890"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    Store(tmp_path / "db.sqlite3").close()
    web = WebData(path)
    payload = json.dumps(
        {
            "health": web.health(),
            "sources": web.sources(),
            "settings": web.settings(),
            "agents": web.agents(),
        }
    )
    assert config["sources"]["rss_proxy_url"] not in payload
    assert "rss_proxy_url" not in payload


@pytest.mark.parametrize(
    ("path", "content", "content_type", "title"),
    [
        ("/rss", RSS, "application/rss+xml", "Fresh story"),
        ("/atom", ATOM, "application/atom+xml", "Fresh atom story"),
        ("/fallback", RSS, "text/plain", "Fresh story"),
    ],
)
def test_valid_rss_atom_and_conservative_plain_xml_fallback(path, content, content_type, title):
    def handler(request: httpx.Request) -> httpx.Response:
        return streamed_response(request, content, headers={"Content-Type": content_type})

    async def scenario():
        http = HttpClient(transport=httpx.MockTransport(handler))
        before = utcnow()
        try:
            rows = await RSSCollector(http, "valid", f"https://public.example{path}").poll()
        finally:
            await http.close()
        after = utcnow()
        assert [row.title for row in rows] == [title]
        assert before <= rows[0].observed_at <= after
        assert rows[0].source_item_id in {
            "https://public.example/story", "https://public.example/atom-story"
        }
        assert rows[0].raw["source_item_state"] == "present"
        if path == "/atom":
            assert rows[0].raw["source_reported_revision_at"] == "2026-08-30T01:00:00Z"

    run(scenario())
