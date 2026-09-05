"""Bounded collector for one first-party exchange announcement surface."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
from typing import Any, Mapping
from urllib.parse import urlparse


OKX_ENDPOINT = "https://www.okx.com/api/v5/support/announcements"
_CA_URL = re.compile(
    r"https?://(?:www\.)?(?P<host>solscan\.io|explorer\.solana\.com|bscscan\.com)"
    r"/(?:token|address)/(?P<address>0x[0-9a-fA-F]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})"
)
_LISTING_WORDS = re.compile(r"\b(list|listing|list(?:ed|ing)|launch|上线|上币)\b", re.I)


def _time(value: Any) -> datetime | None:
    try:
        value = float(value) / 1000.0
        return datetime.fromtimestamp(value, timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[str] = []
    def handle_data(self, data: str) -> None:
        self.text.append(data)
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def _article_parts(content: bytes) -> tuple[str, list[str]]:
    parser = _ArticleParser()
    parser.feed(content.decode("utf-8", errors="ignore"))
    return " ".join(parser.text), parser.links


async def collect_okx_listing_events(
    http: Any, *, now: datetime | None = None, max_age_seconds: float = 3600,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch at most two recent articles; missing CA stays explicitly unverified.

    The caller supplies the existing public-feed client.  Both endpoint and
    article requests are individually bounded to four seconds and failures
    return a diagnostic rather than blocking a trading lane.
    """
    now = now or datetime.now(timezone.utc)
    diagnostics: list[dict[str, Any]] = []
    try:
        response = await asyncio.wait_for(http.get_public_document(OKX_ENDPOINT, maximum_bytes=524_288), timeout=4)
        if urlparse(str(getattr(response, "url", OKX_ENDPOINT))).netloc.lower() != "www.okx.com":
            raise ValueError("okx_endpoint_redirected_official_host")
        payload = response.json()
        if not isinstance(payload, Mapping) or payload.get("code") != "0":
            raise ValueError("okx_api_not_success")
    except Exception as exc:
        return {"events": [], "diagnostics": [{"kind": "okx_fetch_failed", "error": type(exc).__name__}]}
    details = ((payload.get("data") or [{}])[0].get("details") or []) if isinstance(payload, Mapping) else []
    events: list[dict[str, Any]] = []
    article_attempts = 0
    for item in details:
        if len(events) >= 2 or article_attempts >= 2 or not isinstance(item, Mapping):
            break
        title, url = str(item.get("title") or "").strip(), str(item.get("url") or "").strip()
        parsed = urlparse(url)
        published = _time(item.get("pTime"))
        if parsed.scheme != "https" or parsed.netloc.lower() != "www.okx.com" or not parsed.path.startswith("/help/"):
            continue
        if not published or published > now or (now - published).total_seconds() > max_age_seconds or not _LISTING_WORDS.search(title):
            continue
        article_attempts += 1
        try:
            article = await asyncio.wait_for(http.get_public_document(url, maximum_bytes=524_288), timeout=4)
            if urlparse(str(getattr(article, "url", url))).netloc.lower() != "www.okx.com":
                diagnostics.append({"kind": "okx_article_official_host_mismatch", "url": url})
                continue
            body, links = _article_parts(getattr(article, "content", b""))
        except Exception as exc:
            diagnostics.append({"kind": "okx_article_fetch_failed", "url": url, "error": type(exc).__name__})
            continue
        if not _LISTING_WORDS.search(f"{title} {body}"):
            continue
        matches = list(_CA_URL.finditer(body))
        for link in links:
            matches.extend(_CA_URL.finditer(link))
        if not matches:
            observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            diagnostics.append({"kind": "okx_listing_without_exact_ca", "url": url, "title": title,
                "source": "okx", "source_kind": "first_party", "event_type": "official_listing",
                "identity_status": "no_exact_ca", "published_at": published.isoformat().replace("+00:00", "Z"),
                "observed_at": observed, "ingested_at": observed})
            continue
        unique = {(m.group("host"), m.group("address")) for m in matches}
        if len(unique) != 1:
            diagnostics.append({"kind": "ambiguous_contract_set", "url": url,
                                "title": title, "candidates": sorted(unique)})
            continue
        match = matches[0]
        host, address = match.group("host"), match.group("address")
        chain = "bsc" if host == "bscscan.com" else "solana"
        observed = datetime.now(timezone.utc)
        events.append({
            "source": "okx",
            "source_kind": "first_party",
            "trusted": True,
            "event_type": "official_listing",
            "title": title,
            "url": url,
            "chain": chain,
            "contract_address": address,
            "published_at": published.isoformat().replace("+00:00", "Z"),
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "ingested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_host": "www.okx.com",
            "next_frame_trade_required": True,
        })
    return {"events": events[:2], "diagnostics": diagnostics}
