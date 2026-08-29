from __future__ import annotations

import asyncio
import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "live_identity_probe.json"
TOKENS = [
    {"case_id": "pnut", "chain": "solana", "address": "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump"},
    {"case_id": "official_trump", "chain": "solana", "address": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"},
    {"case_id": "melania", "chain": "solana", "address": "FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P"},
    {"case_id": "jing_tian_user_ca", "chain": "bsc", "address": "0xff673079235560e4de3fe4554c9981d759af7777"},
    {"case_id": "niu_lai", "chain": "bsc", "address": "0xBEEA1D618e533a387D941F58a7d4c9b7bD377777"}
]


def rss_items(content: bytes, limit: int = 8) -> list[dict]:
    root = ET.fromstring(content)
    out = []
    for item in root.findall(".//item")[:limit]:
        def value(name: str) -> str:
            node = item.find(name)
            return (node.text or "").strip() if node is not None else ""
        out.append({"title": value("title"), "link": value("link"), "published_at_source_claim": value("pubDate")})
    return out


async def main() -> int:
    observed = datetime.now(timezone.utc).isoformat()
    results = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "memeTrader-research/0.5"}) as client:
        for target in TOKENS:
            item = {**target, "observed_at": observed, "historical_decision_eligible": False}
            try:
                response = await client.get(f"https://api.dexscreener.com/token-pairs/v1/{target['chain']}/{target['address']}")
                response.raise_for_status()
                pairs = response.json()
                if isinstance(pairs, dict):
                    pairs = pairs.get("pairs") or []
                pair = max(pairs, key=lambda row: float(((row.get("liquidity") or {}).get("usd") or 0)), default=None)
                if not pair:
                    item["status"] = "unresolved_on_dexscreener"
                    results.append(item)
                    continue
                base = pair.get("baseToken") or {}
                item["status"] = "resolved"
                item["identity"] = {
                    "name": base.get("name"), "symbol": base.get("symbol"), "address": base.get("address"),
                    "pair_url": pair.get("url"), "dex_id": pair.get("dexId")
                }
                item["current_snapshot_reference_only"] = {
                    "price_usd": pair.get("priceUsd"), "market_cap": pair.get("marketCap") or pair.get("fdv"),
                    "liquidity_usd": (pair.get("liquidity") or {}).get("usd"), "pair_created_at": pair.get("pairCreatedAt")
                }
                query = " ".join(str(part) for part in (base.get("name"), base.get("symbol")) if part)
                news_url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
                    "q": f'"{query}"', "hl": "en-US", "gl": "US", "ceid": "US:en"
                })
                news = await client.get(news_url)
                news.raise_for_status()
                item["news_query"] = query
                item["news_observed_now"] = rss_items(news.content)
            except Exception as exc:
                item["status"] = "error"
                item["error"] = f"{type(exc).__name__}: {exc}"
            results.append(item)
    payload = {
        "generated_at": observed,
        "purpose": "Live identity and retrieval pipeline smoke test. Current pages and metrics are not historical decision evidence.",
        "results": results
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resolved = sum(item.get("status") == "resolved" for item in results)
    with_news = sum(bool(item.get("news_observed_now")) for item in results)
    print(json.dumps({"output": str(OUT), "resolved": resolved, "with_news": with_news}, ensure_ascii=False))
    return 0 if resolved >= 4 and with_news >= 3 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
