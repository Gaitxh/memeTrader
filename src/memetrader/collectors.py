from __future__ import annotations

import asyncio
import json
import math
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, AsyncIterator

import httpx
import websockets

from .models import Observation, TokenCandidate, TokenSnapshot, parse_time, utcnow


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

    def __init__(self, *, timeout: float = 12.0, min_host_interval: float = 0.6, user_agent: str = "memeTrader/0.5"):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json,text/xml,application/xml,text/html,*/*"},
        )
        self.min_host_interval = min_host_interval
        self._last: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cache: dict[str, tuple[float, Any]] = {}

    async def close(self) -> None:
        await self.client.aclose()

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
        response.raise_for_status()
        if ttl:
            try:
                self._cache[key] = (time.monotonic() + ttl, response.json())
            except Exception:
                pass
        return response


class RSSCollector:
    def __init__(self, http: HttpClient, name: str, url: str, source_kind: str = "news"):
        self.http, self.name, self.url, self.source_kind = http, name, url, source_kind

    async def poll(self) -> list[Observation]:
        response = await self.http.get(self.url)
        root = ET.fromstring(response.content)
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
            description = text("description", "summary", "{http://www.w3.org/2005/Atom}summary", "content")
            pub = text("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated")
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
                    published_at=_published(pub),
                    observed_at=utcnow(),
                    availability_proof="local_poll",
                    raw={
                        "feed_url": self.url,
                        "publisher": publisher,
                        "publisher_url": publisher_url,
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
                    availability_proof="local_poll", raw={"like_count": post.get("likeCount"), "repost_count": post.get("repostCount")},
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
                        availability_proof="local_poll", raw={"reblogs_count": status.get("reblogs_count"), "favourites_count": status.get("favourites_count")},
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

    def __init__(self, http: HttpClient):
        self.http = http

    @staticmethod
    def _chain(chain_id: str) -> str:
        return {"bsc": "bsc", "solana": "solana", "base": "base", "ethereum": "ethereum"}.get(chain_id, chain_id)

    @staticmethod
    def _candidate(pair: dict[str, Any]) -> TokenCandidate | None:
        base = pair.get("baseToken") or {}
        address = str(base.get("address") or "")
        chain = DexScreenerClient._chain(str(pair.get("chainId") or ""))
        if not address or not chain:
            return None
        info = pair.get("info") or {}
        socials = [str(x.get("url")) for x in info.get("socials", []) if x.get("url")]
        websites = [str(x.get("url")) for x in info.get("websites", []) if x.get("url")]
        created = pair.get("pairCreatedAt")
        created_at = None
        if created:
            try:
                created_at = datetime.fromtimestamp(float(created) / 1000, tz=utcnow().tzinfo)
            except Exception:
                pass
        return TokenCandidate(
            chain=chain, address=address, name=str(base.get("name") or ""), symbol=str(base.get("symbol") or ""),
            created_at=created_at, source="dexscreener", url=str(pair.get("url") or ""),
            social_urls=list(dict.fromkeys(websites + socials)), raw={"pair": pair},
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
        out: list[tuple[TokenCandidate, TokenSnapshot]] = []
        for pair in response.json().get("pairs", [])[:limit]:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if candidate and snap:
                out.append((candidate, snap))
        return out

    async def quote(self, chain: str, address: str) -> tuple[TokenCandidate, TokenSnapshot] | None:
        response = await self.http.get(f"{self.BASE}/token-pairs/v1/{chain}/{address}", ttl=8)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload.get("pairs") or []
        ranked: list[tuple[float, TokenCandidate, TokenSnapshot]] = []
        for pair in payload if isinstance(payload, list) else []:
            candidate, snap = self._candidate(pair), self._snapshot(pair)
            if candidate and snap:
                ranked.append(((snap.liquidity_usd or 0.0), candidate, snap))
        if not ranked:
            return None
        _, candidate, snap = max(ranked, key=lambda row: row[0])
        return candidate, snap


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
                            source=source,
                            url=f"https://pump.fun/coin/{address}",
                            raw={**item, "pump_event_type": event_type},
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
