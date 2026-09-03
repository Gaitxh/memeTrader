from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import math
import re
import socket
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, AsyncIterator

import httpx
import websockets

from .models import Observation, TokenCandidate, TokenSnapshot, iso, parse_time, utcnow


RSS_CACHE_KEY_PREFIX = "rss_http_cache:v1:"
RSS_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RSS_XML_MEDIA_TYPES = {
    "application/atom+xml",
    "application/rdf+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
}
RSS_GENERIC_MEDIA_TYPES = {"", "application/octet-stream", "binary/octet-stream", "text/plain"}
METADATA_HOSTS = {
    "instance-data.ec2.internal",
    "metadata",
    "metadata.aws.internal",
    "metadata.google.internal",
    "metadata.google",
}


class UnsafeFeedURL(ValueError):
    pass


class JupiterQuoteError(RuntimeError):
    pass


class JupiterNoRouteError(JupiterQuoteError):
    pass


class JupiterQuoteProtocolError(JupiterQuoteError):
    pass


class EvmRouteQuoteError(RuntimeError):
    pass


class EvmRouteQuoteProtocolError(EvmRouteQuoteError):
    pass


class EvmRouteRpcError(EvmRouteQuoteError):
    pass


class EvmRouteExecutionReverted(EvmRouteRpcError):
    pass


class FeedRedirectError(RuntimeError):
    pass


class FeedResponseTooLarge(RuntimeError):
    pass


class InvalidFeedContentType(RuntimeError):
    pass


class InvalidPublicDocumentContentType(RuntimeError):
    pass


class UnsupportedFeedContentEncoding(RuntimeError):
    pass


def _public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
        and not address.is_multicast
        and not address.is_unspecified
    )


def _canonical_ip(value: str) -> str:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return str(address)


def normalize_public_http_url(value: str) -> str:
    """Validate the non-DNS portion of a public HTTP(S) feed URL."""
    raw = str(value or "").strip()
    if not raw or any(ord(char) <= 32 or ord(char) == 127 for char in raw):
        raise UnsafeFeedURL("feed URL contains whitespace or control characters")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise UnsafeFeedURL("invalid feed URL") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise UnsafeFeedURL("feed URL must use public http or https")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeFeedURL("feed URL credentials are forbidden")
    if "#" in raw or parsed.fragment:
        raise UnsafeFeedURL("feed URL fragments are forbidden")
    host = parsed.hostname.lower().rstrip(".")
    if (
        host in {"localhost", "localhost.localdomain", *METADATA_HOSTS}
        or host.endswith(".local")
        or host.endswith(".ec2.internal")
    ):
        raise UnsafeFeedURL("feed URL host is not public")
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None and not _public_ip(str(literal)):
        raise UnsafeFeedURL("feed URL address is not public")
    netloc = host
    if ":" in netloc and not netloc.startswith("["):
        netloc = f"[{netloc}]"
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, "")
    )


def normalize_loopback_socks5_proxy_url(value: str) -> str:
    """Accept only an unauthenticated SOCKS5 proxy at a literal loopback IP."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if any(ord(char) <= 32 or ord(char) == 127 for char in raw):
        raise ValueError("RSS proxy URL contains whitespace or control characters")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid RSS proxy URL") from exc
    if parsed.scheme.lower() != "socks5":
        raise ValueError("RSS proxy must use socks5")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("RSS proxy credentials are forbidden")
    if parsed.path or parsed.query or parsed.fragment or "?" in raw or "#" in raw:
        raise ValueError("RSS proxy URL cannot contain a path, query, or fragment")
    if not parsed.hostname or port is None or not 1 <= port <= 65_535:
        raise ValueError("RSS proxy requires a literal loopback IP and valid port")
    if "%" in parsed.hostname:
        raise ValueError("RSS proxy requires an unscoped literal loopback IP")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError("RSS proxy host must be a literal loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("RSS proxy host must be loopback")
    host = f"[{address}]" if isinstance(address, ipaddress.IPv6Address) else str(address)
    return f"socks5://{host}:{port}"


async def public_destination_addresses(url: str) -> set[str]:
    """Resolve one request hop and reject it if any destination is non-public."""
    normalized = normalize_public_http_url(url)
    host = urllib.parse.urlsplit(normalized).hostname or ""
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        addresses = {_canonical_ip(str(literal))}
    else:
        try:
            rows = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeFeedURL("feed URL host did not resolve") from exc
        addresses = {
            _canonical_ip(str(row[4][0]))
            for row in rows
            if row and row[4]
        }
    if not addresses or any(not _public_ip(value) for value in addresses):
        raise UnsafeFeedURL("feed URL resolved to a non-public destination")
    return addresses


def rss_cache_key(url: str) -> str:
    normalized = normalize_public_http_url(url)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{RSS_CACHE_KEY_PREFIX}{digest}"


def _looks_like_feed_xml(content: bytes) -> bool:
    sample = content[:4096].lstrip(b"\xef\xbb\xbf\x00\t\r\n ")
    sample = re.sub(br"^<\?xml[^>]*>\s*", b"", sample, count=1, flags=re.I)
    sample = re.sub(br"^(?:<!--.*?-->\s*)+", b"", sample, count=1, flags=re.I | re.S)
    return bool(re.match(br"<(?:rss|feed|rdf:RDF)(?:\s|>)", sample, flags=re.I))


def _validate_feed_content_type(headers: httpx.Headers, content: bytes) -> None:
    media_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if media_type in RSS_XML_MEDIA_TYPES or media_type.endswith("+xml"):
        return
    if media_type in RSS_GENERIC_MEDIA_TYPES and _looks_like_feed_xml(content):
        return
    raise InvalidFeedContentType("response is not a conservatively identifiable RSS/Atom XML feed")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _published(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return parse_time(str(value))
    except Exception:
        try:
            return parsedate_to_datetime(str(value)).astimezone()
        except Exception:
            return None


class HttpClient:
    """Small host-aware client for free public endpoints."""

    def __init__(
        self,
        *,
        timeout: float = 12.0,
        min_host_interval: float = 0.6,
        user_agent: str = "memeTrader/0.6",
        feed_max_response_bytes: int = 1_048_576,
        feed_max_redirects: int = 5,
        feed_proxy_url: str = "",
        conditional_store: Any | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json,text/xml,application/xml,text/html,*/*"},
            transport=transport,
        )
        self.feed_proxy_url = normalize_loopback_socks5_proxy_url(feed_proxy_url)
        proxy_host = urllib.parse.urlsplit(self.feed_proxy_url).hostname if self.feed_proxy_url else None
        self.feed_proxy_ip = _canonical_ip(proxy_host) if proxy_host else None
        self._require_feed_peer = transport is None
        self.feed_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
            headers={"User-Agent": user_agent},
            proxy=(self.feed_proxy_url or None) if transport is None else None,
            transport=transport,
        )
        self.min_host_interval = min_host_interval
        self.feed_max_response_bytes = max(1, int(feed_max_response_bytes))
        self.feed_max_redirects = max(0, int(feed_max_redirects))
        self.conditional_store = conditional_store
        self._last: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cache: dict[str, tuple[float, Any]] = {}

    async def close(self) -> None:
        await self.client.aclose()
        await self.feed_client.aclose()

    async def get(self, url: str, *, params: dict[str, Any] | None = None, ttl: float = 0, headers: dict[str, str] | None = None) -> httpx.Response:
        key = url + "?" + urllib.parse.urlencode(sorted((params or {}).items()), doseq=True)
        cached = self._cache.get(key)
        if ttl and cached and cached[0] > time.monotonic():
            response = httpx.Response(200, request=httpx.Request("GET", url), json=cached[1])
            return response
        host = urllib.parse.urlparse(url).netloc.lower()
        async with self._locks[host]:
            wait = self.min_host_interval - (time.monotonic() - self._last[host])
            if wait > 0:
                await asyncio.sleep(wait)
            response = await self.client.get(url, params=params, headers=headers)
            self._last[host] = time.monotonic()
            if response.status_code == 429:
                retry = min(15.0, float(response.headers.get("Retry-After", "2") or 2))
                await asyncio.sleep(retry)
                response = await self.client.get(url, params=params, headers=headers)
                self._last[host] = time.monotonic()
        response.raise_for_status()
        if ttl:
            try:
                self._cache[key] = (time.monotonic() + ttl, response.json())
            except Exception:
                pass
        return response

    def _feed_cache(self, url: str) -> dict[str, Any]:
        if self.conditional_store is None:
            return {}
        value = self.conditional_store.get_kv(rss_cache_key(url), {})
        return value if isinstance(value, dict) else {}

    def _set_feed_cache(self, url: str, value: dict[str, Any]) -> None:
        if self.conditional_store is not None:
            self.conditional_store.set_kv(rss_cache_key(url), value)

    @staticmethod
    def _peer_address(response: httpx.Response) -> str | None:
        stream = response.extensions.get("network_stream")
        if stream is None or not hasattr(stream, "get_extra_info"):
            return None
        for key in ("server_addr", "peername"):
            try:
                value = stream.get_extra_info(key)
            except Exception:
                continue
            if isinstance(value, (tuple, list)) and value:
                try:
                    return _canonical_ip(str(value[0]))
                except ValueError:
                    return None
            if isinstance(value, str) and value:
                try:
                    return _canonical_ip(value)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _pinned_url(url: str, address: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        host = address
        if ":" in host:
            host = f"[{host}]"
        port = parsed.port
        netloc = f"{host}:{port}" if port is not None else host
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, ""))

    @staticmethod
    def _host_header(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        default_port = 443 if parsed.scheme == "https" else 80
        return f"{host}:{parsed.port}" if parsed.port is not None and parsed.port != default_port else host

    @asynccontextmanager
    async def _pinned_feed_response(
        self,
        logical_url: str,
        approved_addresses: set[str],
        headers: dict[str, str],
    ) -> AsyncIterator[httpx.Response]:
        parsed = urllib.parse.urlsplit(logical_url)
        original_host = parsed.hostname or ""
        last_error: Exception | None = None
        ordered_addresses = sorted(approved_addresses, key=lambda value: (":" in value, value))
        for address in ordered_addresses:
            pinned_url = self._pinned_url(logical_url, address)
            request = self.feed_client.build_request(
                "GET",
                pinned_url,
                headers={**headers, "Host": self._host_header(logical_url)},
                extensions={
                    "sni_hostname": original_host,
                    "feed_original_url": logical_url,
                    "feed_approved_ip": address,
                },
            )
            try:
                response = await self.feed_client.send(request, stream=True, follow_redirects=False)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError) as exc:
                last_error = exc
                continue
            try:
                yield response
            finally:
                await response.aclose()
            return
        if last_error is not None:
            raise last_error
        raise UnsafeFeedURL("feed URL has no approved destination")

    async def get_public_feed(self, url: str) -> httpx.Response:
        """Fetch a bounded public feed with manual, independently checked redirects."""
        original_url = normalize_public_http_url(url)
        cache = self._feed_cache(original_url)
        conditional_url = str(cache.get("final_url") or original_url)
        try:
            conditional_url = normalize_public_http_url(conditional_url)
        except UnsafeFeedURL:
            conditional_url = original_url
        etag = str(cache.get("etag") or "")[:1024]
        last_modified = str(cache.get("last_modified") or "")[:256]
        current_url = original_url
        seen: set[str] = set()
        redirects = 0

        while True:
            current_url = normalize_public_http_url(current_url)
            if current_url in seen:
                raise FeedRedirectError("feed redirect loop detected")
            seen.add(current_url)
            approved_addresses = await public_destination_addresses(current_url)
            request_headers = {
                "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "identity",
            }
            if current_url == conditional_url:
                if etag:
                    request_headers["If-None-Match"] = etag
                if last_modified:
                    request_headers["If-Modified-Since"] = last_modified

            host = urllib.parse.urlsplit(current_url).netloc.lower()
            async with self._locks[host]:
                wait = self.min_host_interval - (time.monotonic() - self._last[host])
                if wait > 0:
                    await asyncio.sleep(wait)
                async with self._pinned_feed_response(
                    current_url,
                    approved_addresses,
                    request_headers,
                ) as upstream:
                    self._last[host] = time.monotonic()
                    peer = self._peer_address(upstream)
                    expected_peers = {self.feed_proxy_ip} if self.feed_proxy_ip else approved_addresses
                    if peer is None:
                        if self._require_feed_peer:
                            raise UnsafeFeedURL("feed connection destination could not be verified")
                    elif peer not in expected_peers or (not self.feed_proxy_ip and not _public_ip(peer)):
                        raise UnsafeFeedURL("feed connection reached an unapproved destination")

                    if upstream.status_code in RSS_REDIRECT_STATUSES:
                        location = upstream.headers.get("Location", "")
                        if not location:
                            raise FeedRedirectError("feed redirect omitted Location")
                        if redirects >= self.feed_max_redirects:
                            raise FeedRedirectError("feed redirect limit exceeded")
                        current_url = normalize_public_http_url(
                            urllib.parse.urljoin(current_url, location)
                        )
                        redirects += 1
                        continue

                    content_encoding = upstream.headers.get("Content-Encoding", "").strip().lower()
                    if content_encoding not in {"", "identity"}:
                        raise UnsupportedFeedContentEncoding(
                            "compressed feed responses are not accepted"
                        )
                    if upstream.status_code == 304:
                        not_modified_headers = httpx.Headers(upstream.headers)
                        not_modified_headers.pop("Content-Encoding", None)
                        not_modified_headers.pop("Content-Length", None)
                        self._set_feed_cache(
                            original_url,
                            {
                                "url": original_url,
                                "final_url": current_url,
                                "etag": str(upstream.headers.get("ETag") or etag)[:1024],
                                "last_modified": str(
                                    upstream.headers.get("Last-Modified") or last_modified
                                )[:256],
                                "last_checked_at": iso(),
                                "last_status": 304,
                            },
                        )
                        return httpx.Response(
                            304,
                            headers=not_modified_headers,
                            request=upstream.request,
                        )

                    upstream.raise_for_status()
                    content_length = upstream.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = -1
                        if declared_size > self.feed_max_response_bytes:
                            raise FeedResponseTooLarge("feed response exceeds configured byte limit")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in upstream.aiter_raw():
                        size += len(chunk)
                        if size > self.feed_max_response_bytes:
                            raise FeedResponseTooLarge("feed response exceeds configured byte limit")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    _validate_feed_content_type(upstream.headers, content)
                    safe_headers = httpx.Headers(upstream.headers)
                    safe_headers.pop("Content-Encoding", None)
                    safe_headers.pop("Content-Length", None)
                    response = httpx.Response(
                        upstream.status_code,
                        content=content,
                        headers=safe_headers,
                        request=upstream.request,
                    )
                    response.headers.pop("Content-Encoding", None)
                    response.headers.pop("Content-Length", None)
                    self._set_feed_cache(
                        original_url,
                        {
                            "url": original_url,
                            "final_url": current_url,
                            "etag": str(upstream.headers.get("ETag") or "")[:1024],
                            "last_modified": str(upstream.headers.get("Last-Modified") or "")[:256],
                            "last_checked_at": iso(),
                            "last_status": int(upstream.status_code),
                        },
                    )
                    return response

    async def get_public_document(
        self,
        url: str,
        *,
        maximum_bytes: int = 524_288,
        maximum_redirects: int = 3,
        forbidden_host_suffixes: set[str] | None = None,
    ) -> httpx.Response:
        """Fetch one bounded public text document with DNS pinning and checked redirects."""
        current_url = normalize_public_http_url(url)
        forbidden = {str(value).lower().strip(".") for value in (forbidden_host_suffixes or set())}
        seen: set[str] = set()
        redirects = 0
        maximum_bytes = max(1, int(maximum_bytes))
        maximum_redirects = max(0, int(maximum_redirects))
        while True:
            current_url = normalize_public_http_url(current_url)
            host_name = (urllib.parse.urlsplit(current_url).hostname or "").lower().rstrip(".")
            if any(host_name == suffix or host_name.endswith(f".{suffix}") for suffix in forbidden):
                raise UnsafeFeedURL("document URL host is not allowed")
            if current_url in seen:
                raise FeedRedirectError("document redirect loop detected")
            seen.add(current_url)
            approved_addresses = await public_destination_addresses(current_url)
            request_headers = {
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain,application/xml;q=0.8,*/*;q=0.1",
                "Accept-Encoding": "identity",
            }
            host = urllib.parse.urlsplit(current_url).netloc.lower()
            async with self._locks[host]:
                wait = self.min_host_interval - (time.monotonic() - self._last[host])
                if wait > 0:
                    await asyncio.sleep(wait)
                async with self._pinned_feed_response(
                    current_url, approved_addresses, request_headers
                ) as upstream:
                    self._last[host] = time.monotonic()
                    peer = self._peer_address(upstream)
                    expected_peers = {self.feed_proxy_ip} if self.feed_proxy_ip else approved_addresses
                    if peer is None:
                        if self._require_feed_peer:
                            raise UnsafeFeedURL("document connection destination could not be verified")
                    elif peer not in expected_peers or (not self.feed_proxy_ip and not _public_ip(peer)):
                        raise UnsafeFeedURL("document connection reached an unapproved destination")
                    if upstream.status_code in RSS_REDIRECT_STATUSES:
                        location = upstream.headers.get("Location", "")
                        if not location:
                            raise FeedRedirectError("document redirect omitted Location")
                        if redirects >= maximum_redirects:
                            raise FeedRedirectError("document redirect limit exceeded")
                        current_url = normalize_public_http_url(
                            urllib.parse.urljoin(current_url, location)
                        )
                        redirects += 1
                        continue
                    content_encoding = upstream.headers.get("Content-Encoding", "").strip().lower()
                    if content_encoding not in {"", "identity"}:
                        raise UnsupportedFeedContentEncoding(
                            "compressed document responses are not accepted"
                        )
                    upstream.raise_for_status()
                    media_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    if not (
                        media_type.startswith("text/")
                        or media_type in {"application/json", "application/xml", "application/xhtml+xml"}
                        or media_type.endswith("+json")
                        or media_type.endswith("+xml")
                    ):
                        raise InvalidPublicDocumentContentType(
                            "response is not a text document"
                        )
                    content_length = upstream.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_size = int(content_length)
                        except ValueError:
                            declared_size = -1
                        if declared_size > maximum_bytes:
                            raise FeedResponseTooLarge("document response exceeds byte limit")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in upstream.aiter_raw():
                        size += len(chunk)
                        if size > maximum_bytes:
                            raise FeedResponseTooLarge("document response exceeds byte limit")
                        chunks.append(chunk)
                    safe_headers = httpx.Headers(upstream.headers)
                    safe_headers.pop("Content-Encoding", None)
                    safe_headers.pop("Content-Length", None)
                    return httpx.Response(
                        upstream.status_code,
                        content=b"".join(chunks),
                        headers=safe_headers,
                        request=httpx.Request("GET", current_url),
                        extensions={"logical_url": current_url},
                    )


class RSSCollector:
    def __init__(self, http: HttpClient, name: str, url: str, source_kind: str = "news"):
        self.http, self.name, self.url, self.source_kind = http, name, url, source_kind
        self.last_not_modified = False

    async def poll(self) -> list[Observation]:
        self.last_not_modified = False
        response = await self.http.get_public_feed(self.url)
        self.last_not_modified = response.status_code == 304
        if self.last_not_modified:
            return []
        observed_at = utcnow()
        root = ET.fromstring(response.content)
        root_name = root.tag.rsplit("}", 1)[-1].lower()
        if root_name not in {"rss", "feed", "rdf"}:
            raise InvalidFeedContentType("XML root is not RSS, Atom, or RDF")
        items = root.findall(".//item")
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//a:entry", ns)
        out: list[Observation] = []
        for item in items[:80]:
            def text(*names: str) -> str:
                for name in names:
                    node = item.find(name)
                    if node is not None and node.text:
                        return node.text.strip()
                return ""
            title = text("title", "{http://www.w3.org/2005/Atom}title")
            if not title:
                continue
            link = text("link")
            if not link:
                node = item.find("{http://www.w3.org/2005/Atom}link")
                link = node.attrib.get("href", "") if node is not None else ""
            description = text("description", "summary", "{http://www.w3.org/2005/Atom}summary", "content", "{http://www.w3.org/2005/Atom}content")
            published = text("pubDate", "published", "{http://www.w3.org/2005/Atom}published")
            updated = text("updated", "{http://www.w3.org/2005/Atom}updated")
            updated_at = _published(updated)
            source_item_id = text("guid", "id", "{http://www.w3.org/2005/Atom}id") or link
            author = text("author", "creator", "{http://www.w3.org/2005/Atom}author")
            source_node = item.find("source")
            publisher = (source_node.text or "").strip() if source_node is not None and source_node.text else ""
            publisher_url = source_node.attrib.get("url", "") if source_node is not None else ""
            out.append(
                Observation(
                    source=self.name,
                    source_kind=self.source_kind,
                    title=title,
                    text=description,
                    url=link,
                    author=author or publisher,
                    published_at=_published(published or updated),
                    observed_at=observed_at,
                    availability_proof="local_poll",
                    source_item_id=source_item_id,
                    raw={
                        "feed_url": self.url,
                        "publisher": publisher,
                        "publisher_url": publisher_url,
                        "source_item_state": "present",
                        **({
                            "source_reported_revision_at": iso(updated_at),
                            "source_item_state_evidence": "api_revision",
                        } if updated_at else {}),
                    },
                )
            )
        for tombstone in root.findall(".//{http://purl.org/atompub/tombstones/1.0}deleted-entry")[:80]:
            source_item_id = str(tombstone.attrib.get("ref") or "").strip()
            deleted_at = str(tombstone.attrib.get("when") or "").strip()
            deleted_time = _published(deleted_at)
            if not source_item_id:
                continue
            out.append(
                Observation(
                    source=self.name,
                    source_kind=self.source_kind,
                    title="Source item deletion marker",
                    text="",
                    url=source_item_id if source_item_id.startswith(("http://", "https://")) else "",
                    observed_at=observed_at,
                    availability_proof="local_poll",
                    role="identity",
                    source_item_id=source_item_id,
                    raw={
                        "feed_url": self.url,
                        "source_item_state": "deleted",
                        "source_item_state_evidence": "publisher_deleted_marker",
                        **({"source_reported_revision_at": iso(deleted_time)} if deleted_time else {}),
                    },
                )
            )
        return out


class BlueskySearchCollector:
    def __init__(self, http: HttpClient, query: str):
        self.http, self.query = http, query

    async def poll(self) -> list[Observation]:
        response = await self.http.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": self.query, "limit": 50, "sort": "latest"},
        )
        out: list[Observation] = []
        for post in response.json().get("posts", []):
            record = post.get("record") or {}
            text = str(record.get("text") or "").strip()
            if not text:
                continue
            author = post.get("author") or {}
            handle = str(author.get("handle") or "")
            uri = str(post.get("uri") or "")
            rkey = uri.rsplit("/", 1)[-1] if uri else ""
            url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else ""
            out.append(
                Observation(
                    source=f"bluesky:{self.query}", source_kind="social", title=text[:240], text=text,
                    url=url, author=handle, published_at=_published(record.get("createdAt")), observed_at=utcnow(),
                    availability_proof="local_poll", source_item_id=uri or url,
                    raw={
                        "like_count": post.get("likeCount"),
                        "repost_count": post.get("repostCount"),
                        "source_revision_id": post.get("cid"),
                        "source_item_state": "present",
                    },
                )
            )
        return out


class MastodonCollector:
    """Poll a public Mastodon-compatible account or tag timeline."""

    def __init__(self, http: HttpClient, name: str, url: str):
        self.http, self.name, self.url = http, name, url

    async def poll(self) -> list[Observation]:
        response = await self.http.get(self.url)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("statuses") or payload.get("items") or []
        out: list[Observation] = []
        for status in payload[:80] if isinstance(payload, list) else []:
            content = str(status.get("content") or status.get("text") or "")
            title = str(status.get("spoiler_text") or content)[:240]
            account = status.get("account") or {}
            author = str(account.get("acct") or status.get("username") or "")
            url = str(status.get("url") or status.get("uri") or "")
            if title.strip():
                out.append(
                    Observation(
                        source=self.name, source_kind="social", title=title, text=content, url=url, author=author,
                        published_at=_published(status.get("created_at")), observed_at=utcnow(),
                        availability_proof="local_poll",
                        source_item_id=str(status.get("id") or status.get("uri") or url),
                        raw={
                            "platform": "mastodon",
                            "reblogs_count": status.get("reblogs_count"),
                            "favourites_count": status.get("favourites_count"),
                            "source_item_state": "present",
                            **({
                                "source_reported_revision_at": status.get("edited_at"),
                                "source_item_state_evidence": "api_revision",
                            } if status.get("edited_at") else {}),
                        },
                    )
                )
        return out


class GeckoNewPoolsCollector:
    def __init__(self, http: HttpClient, network: str):
        self.http, self.network = http, network

    async def poll(self) -> list[TokenCandidate]:
        response = await self.http.get(
            f"https://api.geckoterminal.com/api/v2/networks/{self.network}/new_pools",
            params={"include": "base_token", "page": 1}, ttl=20,
        )
        payload = response.json()
        included = {item.get("id"): item for item in payload.get("included", [])}
        out: list[TokenCandidate] = []
        for pool in payload.get("data", [])[:40]:
            attrs = pool.get("attributes") or {}
            rel = (((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {})
            token_data = included.get(rel.get("id"), {})
            token_attrs = token_data.get("attributes") or {}
            address = str(token_attrs.get("address") or rel.get("id", "").split("_", 1)[-1])
            if not address:
                continue
            chain = "solana" if self.network == "solana" else ("bsc" if self.network in {"bsc", "binance-smart-chain"} else self.network)
            out.append(
                TokenCandidate(
                    chain=chain, address=address, name=str(token_attrs.get("name") or attrs.get("name") or ""),
                    symbol=str(token_attrs.get("symbol") or ""), created_at=_published(attrs.get("pool_created_at")),
                    source=f"geckoterminal:{self.network}", url=f"https://www.geckoterminal.com/{self.network}/pools/{attrs.get('address','')}",
                    raw={"pool": attrs, "pool_address": attrs.get("address")},
                )
            )
        return out


class DexScreenerClient:
    BASE = "https://api.dexscreener.com"
    DISCOVERY_SURFACES = {
        "token_profiles": ("/token-profiles/latest/v1", "identity"),
        "community_takeovers": ("/community-takeovers/latest/v1", "identity"),
        "ads": ("/ads/latest/v1", "promotion"),
        "boosts_latest": ("/token-boosts/latest/v1", "promotion"),
        "boosts_top": ("/token-boosts/top/v1", "promotion"),
    }
    SOCIAL_HOSTS = {
        "bsky.app": "bluesky",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "linkedin.com": "linkedin",
        "reddit.com": "reddit",
        "threads.com": "threads",
        "threads.net": "threads",
        "tiktok.com": "tiktok",
        "truthsocial.com": "truth",
        "twitter.com": "x",
        "x.com": "x",
        "youtube.com": "youtube",
        "youtu.be": "youtube",
    }

    @staticmethod
    def metadata_is_usable(name: str, symbol: str) -> bool:
        """Reject provider payloads that concatenate an asset catalogue into one token."""
        return len(str(name or "").strip()) <= 160 and len(str(symbol or "").strip()) <= 64
    TELEGRAM_HOSTS = {"t.me", "telegram.me"}

    def __init__(self, http: HttpClient):
        self.http = http

    @staticmethod
    def _chain(chain_id: str) -> str:
        return {"bsc": "bsc", "solana": "solana", "base": "base", "ethereum": "ethereum"}.get(chain_id, chain_id)

    @staticmethod
    def _normalized_link_url(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = urllib.parse.urlsplit(raw)
            without_fragment = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
            )
            return normalize_public_http_url(without_fragment)
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _classify_link(cls, value: Any, *, label: str = "", platform: str = "") -> tuple[str, str, str]:
        normalized = cls._normalized_link_url(value)
        if not normalized:
            return "invalid", "", ""
        parsed = urllib.parse.urlsplit(normalized)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        if any(host == root or host.endswith(f".{root}") for root in cls.TELEGRAM_HOSTS):
            return "telegram_manual", "telegram", normalized
        if host == "dexscreener.com" or host.endswith(".dexscreener.com"):
            return "dex_page", "dexscreener", normalized
        label_hint = f"{label} {platform}".casefold()
        if host in {"twitter.com", "x.com"} and path.casefold().startswith("/search"):
            return "search", "x", normalized
        if "search" in label_hint or (
            host in {"bing.com", "google.com"} and path.casefold().startswith("/search")
        ):
            return "search", "", normalized
        detected_platform = str(platform or "").strip().lower()
        detected_platform = {
            "twitter": "x",
            "truthsocial": "truth",
            "telegram": "telegram",
        }.get(detected_platform, detected_platform)
        if not detected_platform:
            detected_platform = next(
                (
                    name
                    for root, name in cls.SOCIAL_HOSTS.items()
                    if host == root or host.endswith(f".{root}")
                ),
                "",
            )
        lowered_path = path.casefold()
        post_markers = {
            "x": "/status/",
            "truth": "/posts/",
            "bluesky": "/post/",
            "reddit": "/comments/",
            "threads": "/post/",
            "tiktok": "/video/",
        }
        marker = post_markers.get(detected_platform)
        is_post = bool(marker and marker in lowered_path)
        if detected_platform == "truth":
            segments = [part for part in path.split("/") if part]
            is_post = "/statuses/" in lowered_path or (
                len(segments) >= 2 and segments[0].startswith("@") and segments[-1].isdigit()
            )
        if detected_platform == "instagram":
            is_post = lowered_path.startswith(("/p/", "/reel/", "/reels/"))
        elif detected_platform == "youtube":
            is_post = host == "youtu.be" or lowered_path.startswith(("/watch", "/shorts/", "/live/"))
        if detected_platform:
            return ("social_post" if is_post else "social_profile"), detected_platform, normalized
        return "website", "", normalized

    @classmethod
    def _source_link_rows(
        cls,
        *,
        chain: str,
        address: str,
        surface: str,
        role: str,
        raw: dict[str, Any],
        primary_url: Any = "",
        links: list[Any] | tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        token_id = f"{chain.lower()}:{address}"
        candidates: list[tuple[Any, str, str]] = [(primary_url, surface, "")]
        for item in links:
            if isinstance(item, dict):
                candidates.append(
                    (
                        item.get("url"),
                        str(item.get("label") or item.get("type") or item.get("platform") or ""),
                        str(item.get("platform") or item.get("type") or ""),
                    )
                )
            elif item:
                candidates.append((item, "", ""))
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for original_url, label, platform in candidates:
            link_kind, detected_platform, normalized_url = cls._classify_link(
                original_url,
                label=label,
                platform=platform,
            )
            if not normalized_url:
                continue
            key = (normalized_url, link_kind, detected_platform)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "token_id": token_id,
                    "chain": chain.lower(),
                    "address": address,
                    "provider": "dexscreener",
                    "discovery_surface": surface,
                    "role": role,
                    "original_url": str(original_url or "")[:4000],
                    "normalized_url": normalized_url[:4000],
                    "link_kind": link_kind,
                    "label": str(label or "")[:200],
                    "platform": detected_platform[:80],
                    "verification_status": "manual_only" if link_kind == "telegram_manual" else "provider_metadata",
                    "raw": raw,
                }
            )
        if not rows:
            rows.append(
                {
                    "token_id": token_id,
                    "chain": chain.lower(),
                    "address": address,
                    "provider": "dexscreener",
                    "discovery_surface": surface,
                    "role": role,
                    "original_url": "",
                    "normalized_url": "",
                    "link_kind": "metadata",
                    "label": surface,
                    "platform": "",
                    "verification_status": "provider_metadata",
                    "raw": raw,
                }
            )
        return rows

    @classmethod
    def _pair_source_links(cls, pair: dict[str, Any], chain: str, address: str) -> list[dict[str, Any]]:
        info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
        links = [*(info.get("websites") or []), *(info.get("socials") or [])]
        return cls._source_link_rows(
            chain=chain,
            address=address,
            surface="pair_info",
            role="identity",
            raw={"pair": pair},
            primary_url=pair.get("url"),
            links=links,
        )

    @staticmethod
    def _candidate(pair: dict[str, Any]) -> TokenCandidate | None:
        base = pair.get("baseToken") or {}
        address = str(base.get("address") or "")
        chain = DexScreenerClient._chain(str(pair.get("chainId") or ""))
        name = str(base.get("name") or "")
        symbol = str(base.get("symbol") or "")
        if not address or not chain or not DexScreenerClient.metadata_is_usable(name, symbol):
            return None
        info = pair.get("info") or {}
        source_links = DexScreenerClient._pair_source_links(pair, chain, address)
        social_urls = [
            str(row["normalized_url"])
            for row in source_links
            if row["normalized_url"] and row["link_kind"] not in {"dex_page", "metadata"}
        ]
        created = pair.get("pairCreatedAt")
        created_at = None
        if created:
            try:
                created_at = datetime.fromtimestamp(float(created) / 1000, tz=utcnow().tzinfo)
            except Exception:
                pass
        return TokenCandidate(
            chain=chain, address=address, name=name, symbol=symbol,
            created_at=created_at, source="dexscreener", url=str(pair.get("url") or ""),
            social_urls=list(dict.fromkeys(social_urls)), raw={"pair": pair, "token_source_links": source_links},
        )

    @staticmethod
    def _snapshot(pair: dict[str, Any]) -> TokenSnapshot | None:
        candidate = DexScreenerClient._candidate(pair)
        if not candidate:
            return None
        tx = (pair.get("txns") or {}).get("m5") or {}
        volume = (pair.get("volume") or {}).get("m5")
        liquidity = (pair.get("liquidity") or {}).get("usd")
        return TokenSnapshot(
            chain=candidate.chain, address=candidate.address, price_usd=_float(pair.get("priceUsd")),
            liquidity_usd=_float(liquidity), market_cap_usd=_float(pair.get("marketCap") or pair.get("fdv")),
            volume_5m_usd=_float(volume), buys_5m=_int(tx.get("buys")), sells_5m=_int(tx.get("sells")),
            observed_at=utcnow(), provider="dexscreener", raw={"pair": pair},
        )

    async def search(self, query: str, limit: int = 30) -> list[tuple[TokenCandidate, TokenSnapshot]]:
        response = await self.http.get(f"{self.BASE}/latest/dex/search", params={"q": query}, ttl=12)
        by_token: dict[str, tuple[TokenCandidate, TokenSnapshot]] = {}
        for pair in response.json().get("pairs", [])[:limit]:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if candidate and snap:
                current = by_token.get(candidate.token_id)
                if current is None or (snap.liquidity_usd or 0.0) > (current[1].liquidity_usd or 0.0):
                    by_token[candidate.token_id] = (candidate, snap)
        return list(by_token.values())

    async def quote(self, chain: str, address: str) -> tuple[TokenCandidate, TokenSnapshot] | None:
        response = await self.http.get(f"{self.BASE}/token-pairs/v1/{chain}/{address}", ttl=8)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("pairs") or []
        ranked: list[tuple[float, TokenCandidate, TokenSnapshot]] = []
        for pair in payload if isinstance(payload, list) else []:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if (
                candidate
                and snap
                and candidate.chain.lower() == self._chain(chain).lower()
                and candidate.address.lower() == str(address).lower()
            ):
                ranked.append(((snap.liquidity_usd or 0.0), candidate, snap))
        if not ranked:
            return None
        _, candidate, snap = max(ranked, key=lambda row: row[0])
        return candidate, snap

    async def batch_quote(
        self,
        chain: str,
        addresses: list[str] | tuple[str, ...],
    ) -> dict[str, tuple[TokenCandidate, TokenSnapshot]]:
        """Hydrate up to many token details through DexScreener's documented 30-address endpoint."""
        normalized_chain = self._chain(str(chain)).lower()
        unique = list(dict.fromkeys(str(value).strip() for value in addresses if str(value).strip()))
        by_token: dict[str, tuple[TokenCandidate, TokenSnapshot]] = {}
        for offset in range(0, len(unique), 30):
            chunk = unique[offset : offset + 30]
            requested = {value.lower(): value for value in chunk}
            joined = urllib.parse.quote(",".join(chunk), safe=",")
            response = await self.http.get(
                f"{self.BASE}/tokens/v1/{normalized_chain}/{joined}",
                ttl=8,
            )
            payload = response.json()
            if isinstance(payload, dict):
                payload = payload.get("pairs") or []
            for pair in payload if isinstance(payload, list) else []:
                candidate, snap = self._candidate(pair), self._snapshot(pair)
                if not candidate or not snap or candidate.chain.lower() != normalized_chain:
                    continue
                requested_address = requested.get(candidate.address.lower())
                if requested_address is None:
                    continue
                candidate.address = requested_address
                snap.address = requested_address
                current = by_token.get(candidate.token_id)
                if current is None or (snap.liquidity_usd or 0.0) > (current[1].liquidity_usd or 0.0):
                    by_token[candidate.token_id] = (candidate, snap)
        return by_token


    async def discover_surface(
        self,
        surface: str,
        allowed_chains: set[str] | list[str] | tuple[str, ...],
        *,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        if surface not in self.DISCOVERY_SURFACES:
            raise ValueError(f"unknown DexScreener discovery surface: {surface}")
        path, role = self.DISCOVERY_SURFACES[surface]
        response = await self.http.get(f"{self.BASE}{path}", ttl=45)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("items") if isinstance(payload.get("items"), list) else [payload]
        if not isinstance(payload, list):
            raise ValueError("DexScreener discovery response must be a list or object")
        allowed = {self._chain(str(chain).lower()) for chain in allowed_chains}
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in payload[: max(1, int(limit))]:
            if not isinstance(item, dict):
                continue
            chain = self._chain(str(item.get("chainId") or "").lower())
            address = str(item.get("tokenAddress") or "").strip()
            if not chain or chain not in allowed or not address:
                continue
            item_rows = self._source_link_rows(
                chain=chain,
                address=address,
                surface=surface,
                role=role,
                raw={"item": item},
                primary_url=item.get("url"),
                links=item.get("links") or [],
            )
            for row in item_rows:
                key = (row["token_id"], row["normalized_url"], row["link_kind"], row["role"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows


class JupiterQuoteClient:
    """Read-only Jupiter Swap API V2 quote client."""

    BASE = "https://api.jup.ag/swap/v2/order"

    def __init__(self, http: HttpClient):
        self.http = http

    async def quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        *,
        slippage_bps: int = 50,
    ) -> dict[str, Any]:
        input_mint, output_mint = str(input_mint).strip(), str(output_mint).strip()
        amount, slippage_bps = int(amount), int(slippage_bps)
        if not input_mint or not output_mint or amount <= 0:
            raise ValueError("input/output mint and amount are required")
        if slippage_bps < 0 or slippage_bps > 10000:
            raise ValueError("slippage_bps must be between 0 and 10000")
        requested_at = iso(utcnow())
        try:
            response = await self.http.get(self.BASE, params={
                "inputMint": input_mint, "outputMint": output_mint,
                "amount": amount, "slippageBps": slippage_bps,
            })
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                try:
                    exc.response.read()
                    message = exc.response.content.decode("utf-8", errors="replace").casefold()
                except Exception:
                    message = ""
                message = (message + " " + str(exc)).casefold()
                if exc.response.status_code == 400 and (
                    "no route" in message or "no_route" in message or "no route found" in message
                    or "find any route" in message or "failed to get quotes" in message
                ):
                    raise JupiterNoRouteError("Jupiter returned no route") from exc
            raise JupiterQuoteError(f"Jupiter quote failed with HTTP {exc.response.status_code}") from exc
        completed_at = iso(utcnow())
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Jupiter quote response must be an object")
        if any(payload.get(key) for key in ("transaction", "swapTransaction")):
            raise JupiterQuoteProtocolError("Jupiter quote response contains a transaction")
        if (
            str(payload.get("inputMint") or "") != input_mint
            or str(payload.get("outputMint") or "") != output_mint
            or str(payload.get("inAmount") or "") != str(amount)
            or int(payload.get("slippageBps") if payload.get("slippageBps") is not None else -1) != slippage_bps
            or str(payload.get("swapMode") or "ExactIn") != "ExactIn"
            or int(payload.get("outAmount") or 0) <= 0
            or int(payload.get("otherAmountThreshold") or 0) <= 0
            or int(payload.get("otherAmountThreshold") or 0) > int(payload.get("outAmount") or 0)
            or not isinstance(payload.get("routePlan"), list)
            or not payload.get("routePlan")
        ):
            raise JupiterQuoteError("Jupiter quote response does not match the requested route")

        def text(value: Any) -> str | None:
            return str(value) if value is not None else None

        price_impact_bps: float | None = None
        price_impact_source = ""
        raw_price_impact = payload.get("priceImpact")
        raw_price_impact_pct = payload.get("priceImpactPct")
        try:
            if raw_price_impact is not None:
                parsed_impact = float(raw_price_impact)
                if not math.isfinite(parsed_impact):
                    raise ValueError("non-finite price impact")
                # Swap V2 priceImpact is expressed in percentage points.
                price_impact_bps = parsed_impact * 100.0
                price_impact_source = "priceImpact_percentage_points"
            elif raw_price_impact_pct is not None:
                parsed_impact = float(raw_price_impact_pct)
                if not math.isfinite(parsed_impact):
                    raise ValueError("non-finite price impact")
                # Deprecated priceImpactPct is a decimal ratio.
                price_impact_bps = parsed_impact * 10_000.0
                price_impact_source = "priceImpactPct_decimal_ratio"
        except (TypeError, ValueError, OverflowError) as exc:
            raise JupiterQuoteProtocolError("Jupiter price impact is invalid") from exc

        route_plan: list[dict[str, Any]] = []
        for item in payload.get("routePlan") or []:
            if not isinstance(item, dict) or not isinstance(item.get("swapInfo"), dict):
                continue
            swap = item["swapInfo"]
            route_plan.append({
                "percent": item.get("percent"),
                "amm_key": text(swap.get("ammKey")), "label": text(swap.get("label")),
                "input_mint": text(swap.get("inputMint")), "output_mint": text(swap.get("outputMint")),
                "in_amount": text(swap.get("inAmount")), "out_amount": text(swap.get("outAmount")),
                "fee_amount": text(swap.get("feeAmount")), "fee_mint": text(swap.get("feeMint")),
            })
        return {
            "provider": "jupiter", "requested_at": requested_at, "completed_at": completed_at,
            "input_mint": text(payload.get("inputMint")), "in_amount": text(payload.get("inAmount")),
            "output_mint": text(payload.get("outputMint")), "out_amount": text(payload.get("outAmount")),
            "other_amount_threshold": text(payload.get("otherAmountThreshold")),
            "mode": text(payload.get("mode") or payload.get("swapMode")),
            "router": text(payload.get("router")),
            "slippage_bps": payload.get("slippageBps"),
            "price_impact_pct": text(
                raw_price_impact if raw_price_impact is not None else raw_price_impact_pct
            ),
            "price_impact_bps": price_impact_bps,
            "price_impact_source": price_impact_source,
            "fee_bps": payload.get("feeBps"),
            "signature_fee_lamports": payload.get("signatureFeeLamports"),
            "prioritization_fee_lamports": payload.get("prioritizationFeeLamports"),
            "rent_fee_lamports": payload.get("rentFeeLamports"),
            "platform_fee_bps": (
                (payload.get("platformFee") or {}).get("feeBps")
                if isinstance(payload.get("platformFee"), dict) else None
            ),
            "output_amount_raw": text(payload.get("outAmount")),
            "route_plan": route_plan,
            "context_slot": payload.get("contextSlot"),
            "time_taken_ms": payload.get("totalTime")
            if payload.get("totalTime") is not None
            else ((float(payload["timeTaken"]) * 1000) if payload.get("timeTaken") is not None else None),
        }


class EvmUniswapV3QuoteClient:
    """Read-only exact-input Uniswap V3 QuoterV2 observer for EVM research lanes."""

    QUOTE_EXACT_INPUT_SELECTOR = "cdca1753"
    GET_POOL_SELECTOR = "1698ee82"
    NETWORKS = {
        "bsc": {
            "chain_id": 56,
            "rpc_url": "https://bsc-dataseed.bnbchain.org",
            "factory": "0xdB1d10011AD0Ff90774D0C6Bb92e5C5c8b4461F7",
            "quoter": "0x78D78E420Da98ad378D7799bE8f4AF69033EB077",
            "accounting_token": "0x55d398326f99059ff775485246999027b3197955",
            "accounting_symbol": "USDT",
            "accounting_decimals": 18,
            "wrapped_native": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "native_symbol": "BNB",
        },
        "base": {
            "chain_id": 8453,
            "rpc_url": "https://mainnet.base.org",
            "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
            "quoter": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
            "accounting_token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "accounting_symbol": "USDC",
            "accounting_decimals": 6,
            "wrapped_native": "0x4200000000000000000000000000000000000006",
            "native_symbol": "ETH",
        },
        "robinhood": {
            "chain_id": 4663,
            "rpc_url": "https://rpc.mainnet.chain.robinhood.com",
            "factory": "0x1f7d7550b1b028f7571e69a784071f0205fd2efa",
            "quoter": "0x33e885ed0ec9bf04ecfb19341582aadcb4c8a9e7",
            "accounting_token": "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168",
            "accounting_symbol": "USDG",
            "accounting_decimals": 6,
            "wrapped_native": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
            "native_symbol": "ETH",
        },
    }
    FEE_TIERS = (100, 500, 3000, 10000)

    def __init__(self, http: HttpClient):
        self.http = http
        self._lock = asyncio.Lock()
        self._request_id = 0
        self._last_request_started = 0.0

    @classmethod
    def public_network_definitions(cls) -> dict[str, dict[str, Any]]:
        return {
            chain: {**values, "fee_tiers": list(cls.FEE_TIERS)}
            for chain, values in cls.NETWORKS.items()
        }

    @staticmethod
    def _address(value: Any) -> str:
        address = str(value or "").strip()
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
            raise ValueError("valid EVM address required")
        return "0x" + address[2:].lower()

    @staticmethod
    def _word(value: int) -> str:
        number = int(value)
        if number < 0 or number >= 2**256:
            raise ValueError("ABI integer outside uint256")
        return f"{number:064x}"

    @classmethod
    def _get_pool_data(cls, token_a: str, token_b: str, fee: int) -> str:
        return "0x" + cls.GET_POOL_SELECTOR + token_a[2:].rjust(64, "0") + token_b[2:].rjust(64, "0") + cls._word(fee)

    @classmethod
    def _quote_data(cls, path: bytes, amount_in: int) -> str:
        encoded_path = path.hex()
        padded_length = ((len(encoded_path) + 63) // 64) * 64
        return (
            "0x" + cls.QUOTE_EXACT_INPUT_SELECTOR
            + cls._word(64) + cls._word(amount_in) + cls._word(len(path))
            + encoded_path.ljust(padded_length, "0")
        )

    @staticmethod
    def _path_bytes(edges: list[tuple[str, int, str]]) -> bytes:
        if not edges:
            raise ValueError("at least one route edge required")
        raw = bytes.fromhex(edges[0][0][2:])
        current = edges[0][0]
        for token_in, fee, token_out in edges:
            if token_in != current or int(fee) < 0 or int(fee) >= 2**24:
                raise ValueError("invalid contiguous Uniswap V3 path")
            raw += int(fee).to_bytes(3, "big") + bytes.fromhex(token_out[2:])
            current = token_out
        return raw

    async def _rpc(self, network: dict[str, Any], method: str, params: list[Any]) -> Any:
        async with self._lock:
            interval = max(0.0, float(self.http.min_host_interval))
            wait = interval - (time.monotonic() - self._last_request_started)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_started = time.monotonic()
            self._request_id += 1
            request_id = self._request_id
            try:
                response = await self.http.client.post(
                    str(network["rpc_url"]),
                    json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
                )
                response.raise_for_status()
            except Exception as exc:
                raise EvmRouteQuoteError(f"EVM RPC {method} failed") from exc
            try:
                payload = response.json()
            except Exception as exc:
                raise EvmRouteQuoteProtocolError("EVM RPC returned malformed JSON") from exc
        if not isinstance(payload, dict) or payload.get("id") != request_id:
            raise EvmRouteQuoteProtocolError("EVM RPC response identity mismatch")
        if isinstance(payload.get("error"), dict):
            error = payload["error"]
            message = str(error.get("message") or "EVM RPC error")
            normalized = message.lower()
            if method == "eth_call" and (
                "revert" in normalized or "execution reverted" in normalized
            ):
                raise EvmRouteExecutionReverted(message)
            raise EvmRouteRpcError(message)
        if "result" not in payload:
            raise EvmRouteQuoteProtocolError("EVM RPC result missing")
        return payload["result"]

    async def _call(
        self,
        network: dict[str, Any],
        to: str,
        data: str,
        block_tag: str,
        *,
        allow_revert: bool = False,
    ) -> str | None:
        try:
            result = await self._rpc(network, "eth_call", [{"to": to, "data": data}, block_tag])
        except EvmRouteExecutionReverted:
            if allow_revert:
                return None
            raise
        if not isinstance(result, str) or not result.startswith("0x"):
            raise EvmRouteQuoteProtocolError("eth_call returned invalid data")
        return result

    async def _pool(
        self,
        network: dict[str, Any],
        token_a: str,
        token_b: str,
        fee: int,
        block_tag: str,
    ) -> str | None:
        result = await self._call(
            network,
            str(network["factory"]),
            self._get_pool_data(token_a, token_b, fee),
            block_tag,
        )
        assert result is not None
        body = result[2:]
        if len(body) < 64:
            raise EvmRouteQuoteProtocolError("factory getPool result too short")
        address = "0x" + body[-40:].lower()
        return None if int(address, 16) == 0 else address

    async def _quote_path(
        self,
        network: dict[str, Any],
        edges: list[tuple[str, int, str]],
        amount_in: int,
        block_tag: str,
    ) -> tuple[int, int] | None:
        result = await self._call(
            network,
            str(network["quoter"]),
            self._quote_data(self._path_bytes(edges), amount_in),
            block_tag,
            allow_revert=True,
        )
        if result is None:
            return None
        body = result[2:]
        if len(body) < 256 or len(body) % 64:
            raise EvmRouteQuoteProtocolError("QuoterV2 result shape invalid")
        amount_out = int(body[0:64], 16)
        gas_estimate = int(body[192:256], 16)
        if amount_out <= 0 or gas_estimate <= 0:
            raise EvmRouteQuoteProtocolError("QuoterV2 returned non-positive output")
        return amount_out, gas_estimate

    async def quote_round_trip(
        self,
        chain: str,
        token_address: str,
        input_amount_raw: int,
        *,
        slippage_bps: int = 400,
    ) -> dict[str, Any]:
        chain = str(chain).strip().lower()
        if chain not in self.NETWORKS:
            raise ValueError("unsupported EVM route research chain")
        network = dict(self.NETWORKS[chain])
        token = self._address(token_address)
        stable = self._address(network["accounting_token"])
        wrapped = self._address(network["wrapped_native"])
        amount_in = int(input_amount_raw)
        slippage = int(slippage_bps)
        if amount_in <= 0 or slippage < 0 or slippage >= 10_000:
            raise ValueError("positive amount and valid slippage required")
        if token in {stable, wrapped}:
            raise ValueError("target token must differ from route base assets")

        requested_at = iso(utcnow())
        chain_id = int(await self._rpc(network, "eth_chainId", []), 16)
        if chain_id != int(network["chain_id"]):
            raise EvmRouteQuoteProtocolError("EVM RPC chain mismatch")
        block_tag = str(await self._rpc(network, "eth_blockNumber", []))
        block = await self._rpc(network, "eth_getBlockByNumber", [block_tag, False])
        if not isinstance(block, dict) or not block.get("hash") or not block.get("timestamp"):
            raise EvmRouteQuoteProtocolError("EVM block context missing")
        for address in (network["factory"], network["quoter"]):
            code = await self._rpc(network, "eth_getCode", [address, block_tag])
            if not isinstance(code, str) or code in {"0x", "0x0"}:
                raise EvmRouteQuoteProtocolError("official Uniswap contract code missing")

        pool_cache: dict[tuple[str, str, int], str | None] = {}

        async def route_pools(edges: list[tuple[str, int, str]]) -> list[str] | None:
            pools: list[str] = []
            for token_in, fee, token_out in edges:
                key = (token_in, token_out, int(fee))
                if key not in pool_cache:
                    pool_cache[key] = await self._pool(
                        network, token_in, token_out, int(fee), block_tag
                    )
                if pool_cache[key] is None:
                    return None
                pools.append(str(pool_cache[key]))
            return pools

        paired: list[dict[str, Any]] = []
        buy_pool_seen = False
        buy_quote_seen = False
        candidates: list[list[tuple[str, int, str]]] = [
            [(stable, fee, token)] for fee in self.FEE_TIERS
        ]
        candidates.extend(
            [(stable, first_fee, wrapped), (wrapped, second_fee, token)]
            for first_fee in self.FEE_TIERS
            for second_fee in self.FEE_TIERS
        )
        for edges in candidates:
                pools = await route_pools(edges)
                if pools is None:
                    continue
                buy_pool_seen = True
                buy = await self._quote_path(network, edges, amount_in, block_tag)
                if buy is None:
                    continue
                buy_quote_seen = True
                buy_output, buy_gas = buy
                minimum = buy_output * (10_000 - slippage) // 10_000
                if minimum <= 0:
                    continue
                reverse = [(out_token, edge_fee, in_token) for in_token, edge_fee, out_token in reversed(edges)]
                sell = await self._quote_path(network, reverse, minimum, block_tag)
                if sell is None:
                    continue
                sell_output, sell_gas = sell
                sell_minimum = sell_output * (10_000 - slippage) // 10_000
                if sell_minimum <= 0:
                    continue
                paired.append({
                    "buy_output_raw": str(buy_output),
                    "buy_minimum_output_raw": str(minimum),
                    "sell_output_raw": str(sell_output),
                    "sell_minimum_output_raw": str(sell_minimum),
                    "buy_quoter_gas_estimate": buy_gas,
                    "sell_quoter_gas_estimate": sell_gas,
                    "buy_path": [
                        {"token_in": a, "token_out": b, "fee_tier": f, "pool": pools[index]}
                        for index, (a, f, b) in enumerate(edges)
                    ],
                    "sell_path": [
                        {"token_in": a, "token_out": b, "fee_tier": f, "pool": pools[-1-index]}
                        for index, (a, f, b) in enumerate(reverse)
                    ],
                })

        final_block = await self._rpc(network, "eth_getBlockByNumber", [block_tag, False])
        if (
            not isinstance(final_block, dict)
            or str(final_block.get("hash") or "").lower()
            != str(block["hash"]).lower()
        ):
            raise EvmRouteQuoteProtocolError("EVM fixed block hash changed during quote")
        completed_at = iso(utcnow())
        best = max(paired, key=lambda item: int(item["sell_output_raw"])) if paired else None
        status = (
            "quoted" if best is not None
            else "sell_quote_unavailable" if buy_quote_seen
            else "buy_quote_unavailable" if buy_pool_seen
            else "no_official_pool"
        )
        return {
            "provider": "uniswap_v3_quoter_v2",
            "chain": chain,
            "chain_id": chain_id,
            "requested_at": requested_at,
            "completed_at": completed_at,
            "block_number": int(block_tag, 16),
            "block_hash": str(block["hash"]),
            "block_timestamp": iso(datetime.fromtimestamp(int(str(block["timestamp"]), 16), tz=utcnow().tzinfo)),
            "input_token": stable,
            "accounting_symbol": str(network["accounting_symbol"]),
            "accounting_decimals": int(network["accounting_decimals"]),
            "output_token": token,
            "input_amount_raw": str(amount_in),
            "slippage_bps": slippage,
            "status": status,
            "buy_output_raw": best["buy_output_raw"] if best else None,
            "buy_minimum_output_raw": best["buy_minimum_output_raw"] if best else None,
            "sell_output_raw": best["sell_output_raw"] if best else None,
            "sell_minimum_output_raw": best["sell_minimum_output_raw"] if best else None,
            "buy_quoter_gas_estimate": best["buy_quoter_gas_estimate"] if best else None,
            "sell_quoter_gas_estimate": best["sell_quoter_gas_estimate"] if best else None,
            "buy_path": best["buy_path"] if best else [],
            "sell_path": best["sell_path"] if best else [],
            "immediate_round_trip_stable_ratio": (
                int(best["sell_minimum_output_raw"]) / amount_in if best else None
            ),
            "venue_fee_semantics": "uniswap_v3_fee_tier_embedded_in_amount_out",
            "fee_completeness": "quote_only_no_full_transaction_network_fee",
            "economic_status": "cost_unknown",
            "execution_scope": "pool_math_quote_only",
            "transfer_semantics_checked": False,
            "router_transaction_simulated": False,
            "decision_eligible": False,
            "affects": "none",
        }


class PumpPortalCollector:
    """Free launch/migration metadata only; paid transaction subscriptions are not used."""

    URL = "wss://pumpportal.fun/api/data"

    def __init__(self, url: str | None = None):
        self.url = url or self.URL

    async def stream(self) -> AsyncIterator[TokenCandidate]:
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    async for raw in ws:
                        item = json.loads(raw)
                        received_at = utcnow()
                        address = str(item.get("mint") or item.get("tokenAddress") or "")
                        if not address:
                            continue
                        event_type = str(
                            item.get("txType") or item.get("eventType") or item.get("type") or "create"
                        ).lower()
                        source = "pumpportal:migration" if "migrat" in event_type else "pumpportal:create"
                        yield TokenCandidate(
                            chain="solana",
                            address=address,
                            name=str(item.get("name") or ""),
                            symbol=str(item.get("symbol") or ""),
                            first_seen_at=received_at,
                            source=source,
                            url=f"https://pump.fun/coin/{address}",
                            raw={**item, "pump_event_type": event_type},
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
