from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

import httpx
from solders.pubkey import Pubkey

from .runtime_timing import RuntimeTiming

from .autonomous_search import AutonomousSearchAgent, _canonical_social_url, _same_social_url
from .collectors import (
    BlueskySearchCollector,
    DexScreenerClient,
    EvmRouteQuoteError,
    EvmRouteQuoteProtocolError,
    EvmUniswapV3QuoteClient,
    EvmZeroXPriceClient,
    FeedRedirectError,
    FeedResponseTooLarge,
    GeckoNewPoolsCollector,
    HttpClient,
    InvalidPublicDocumentContentType,
    JupiterNoRouteError,
    JupiterQuoteError,
    JupiterQuoteClient,
    JupiterQuoteProtocolError,
    MastodonCollector,
    PumpPortalCollector,
    PumpSwapVaultFlowTracker,
    RSSCollector,
    RobinhoodStockTokenRegistryClient,
    SolanaHeldAccountCollector,
    SOLANA_USDC_MINT,
    SOLANA_WRAPPED_SOL_MINT,
    UnsafeFeedURL,
    UnsupportedFeedContentEncoding,
    normalize_loopback_socks5_proxy_url,
    normalize_public_http_url,
)
from .models import (
    CandidateDecision,
    Observation,
    ObservationRevisionHandoff,
    TokenCandidate,
    TokenSnapshot,
    canonical_token_address,
    iso,
    parse_time,
    utcnow,
)
from .store import Store
from .strategy import (
    AgentRouter,
    CandidateEvaluator,
    EventEngine,
    PaperPolicy,
    SafetyChecker,
    clean_text,
    evidence_origin,
    extract_addresses,
    is_context_searchable_token_name,
    is_distinctive_token_name,
    is_promotional_market_content,
    replay_guard,
    sanitize_source_entity_id,
    terms,
    token_snapshot_temporal_rejections,
)


DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "paper",
    "onchain_primary_focus_enabled": False,
    "chain_meme_trader_only_enabled": False,
    "database": "data/memetrader_forward.sqlite3",
    "lock_file": "data/memetrader.lock",
    "poll_seconds": 60,
    "reverse_news_seconds": 45,
    "event_scan_seconds": 10,
    "position_scan_seconds": 15,
    "source_health_seconds": 30,
    "event_min_attention": 35.0,
    "sources": {
        "rss_max_response_bytes": 1_048_576,
        "rss_max_redirects": 5,
        "rss_proxy_url": "",
        "rss": [
            {
                "name": "coindesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "kind": "news",
                "enabled": True,
            },
            {
                "name": "cointelegraph",
                "url": "https://cointelegraph.com/rss",
                "kind": "news",
                "enabled": True,
            },
            {
                "name": "bbc-world",
                "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
                "kind": "news",
                "enabled": True,
            },
            {
                "name": "bbc-entertainment",
                "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
                "kind": "news",
                "enabled": True,
            },
            {
                "name": "google-news-viral",
                "url": "https://news.google.com/rss/search?q=%28%22goes+viral%22+OR+%22internet+reacts%22+OR+%22social+media+erupts%22+OR+%22viral+animal%22+OR+%22viral+meme%22%29+when%3A1h&hl=en-US&gl=US&ceid=US%3Aen",
                "kind": "news",
                "enabled": True,
            },
            {
                "name": "google-news-memecoin",
                "url": "https://news.google.com/rss/search?q=%28memecoin+OR+%22meme+coin%22+OR+pump.fun%29+when%3A1h&hl=en-US&gl=US&ceid=US%3Aen",
                "kind": "news",
                "enabled": True,
            },
        ],
        "bluesky_queries": ["memecoin", "pump.fun", "viral animal", "viral"],
        "mastodon": [
            {
                "name": "mastodon-memecoin",
                "url": "https://mastodon.social/api/v1/timelines/tag/memecoin?limit=40",
                "enabled": True,
            },
            {
                "name": "mastodon-viral",
                "url": "https://mastodon.social/api/v1/timelines/tag/viral?limit=40",
                "enabled": True,
            },
        ],
        "gecko_networks": ["solana"],
        "multichain_meme_data": {
            "chains": ["solana", "bsc", "robinhood"],
            "interval_seconds": 90,
        },
        "dexscreener_discovery": {
            "enabled": True,
            "chains": ["solana"],
            "surface_chains": ["solana"],
            "interval_seconds": 90,
            "max_items_per_surface": 40,
            "max_hydrations_per_cycle": 180,
            "active_token_minutes": 180,
        },
        "solana_holder_shadow": {
            "enabled": True,
            "interval_seconds": 300,
        },
        "pumpportal": {
            "enabled": True,
            "url": "wss://pumpportal.fun/api/data",
            "metadata_enabled": True,
            "metadata_queue_size": 512,
            "metadata_workers": 1,
            "metadata_max_response_bytes": 131_072,
        },
        "reverse_google_news": {
            "enabled": True,
            "queries_per_cycle": 3,
            "max_tokens_scanned_per_cycle": 10,
            "candidate_pool_limit": 300,
            "probe_cooldown_seconds": 120,
            "cooldown_minutes": 15,
            "min_liquidity_usd": 5_000,
            "min_volume_5m_usd": 1_000,
            "min_5m_transactions": 12,
            "min_buy_ratio": 0.55,
            "max_results_per_query": 8,
            "max_result_age_minutes": 180,
            "min_independent_sources": 2,
        },
    },
    "bridge": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 8765,
        "token": "CHANGE_ME",
        "max_body_bytes": 262_144,
    },
    "events": {
        "max_source_age_minutes": 30,
        "cluster_hours": 8,
        "similarity": 0.28,
    },
    "candidate": {
        "chains": ["solana"],
        "min_match_score": 52.0,
        "min_candidate_score": 67.0,
        "min_canonical_margin": 5.0,
        "agent_tie_threshold": 3.0,
        "agent_resolution_confidence": {"low": 0.85, "medium": 0.78},
        "token_watch_minutes": 360,
        "decision_cooldown_seconds": 180,
        "retry_seconds": [25, 60, 150, 300],
        "max_events_per_cycle": 8,
        "max_alias_queries": 4,
        "allow_reentry": False,
        "min_reverse_independent_sources": 2,
        "reverse_only_penalty": 8.0,
    },
    "safety": {
        "require_pretrade_rug_safety_v1": True,
        "min_liquidity_usd": 12_000,
        "max_market_cap_usd": 25_000_000,
        "min_5m_transactions": 8,
        "min_buy_ratio": 0.55,
        "max_tax_pct": 12.0,
        "goplus_evm": True,
        "honeypot_is": True,
        "require_evm_security_report": True,
        "require_evm_simulation": False,
        "goplus_evm_require_open_source": False,
        "goplus_evm_reject_closed_source": True,
        "goplus_evm_reject_flags": [
            "is_honeypot",
            "cannot_buy",
            "hidden_owner",
            "can_take_back_ownership",
            "owner_change_balance",
            "selfdestruct",
            "is_blacklisted",
            "transfer_pausable",
            "slippage_modifiable",
            "personal_slippage_modifiable",
            "honeypot_with_same_creator",
        ],
        "goplus_solana": True,
        "rugcheck": True,
        "require_solana_report": True,
        "goplus_solana_reject_flags": [
            "freezable",
            "mintable",
            "closable",
            "balance_mutable_authority",
            "default_account_state_upgradable",
            "transfer_fee_upgradable",
            "transfer_hook_upgradable",
            "non_transferable",
        ],
        "max_solana_risk_score": 79.0,
    },
    "paper": {
        "starting_cash_usd": 1_000,
        "fee_bps": 60,
        "pump_swap_fee_bps": 125,
        "fixed_fee_usd_each_side": 0.4,
        "slippage_rate": 0.04,
        "max_quote_age_seconds": 45,
        "risk_per_trade_pct": 0.005,
        "max_cash_fraction": 0.08,
        "fixed_position_usd": 20,
        "max_position_usd": 20,
        "min_position_usd": 3,
        "max_liquidity_impact_pct": 0.0025,
        "max_daily_new_exposure_usd": 100,
        "max_open_positions": 0,
        "stop_loss_pct": -0.35,
        "trailing_activate_pct": 0.60,
        "trailing_drawdown_pct": 0.28,
        "emergency_liquidity_usd": 3_000,
        "narrative_stale_minutes": 120,
        "narrative_min_holding_minutes": 20,
        "narrative_exit_buy_ratio": 0.45,
        "max_holding_hours": 24,
        "take_profit_tiers": [
            {"return_pct": 0.50, "sell_fraction": 0.20},
            {"return_pct": 1.00, "sell_fraction": 0.25},
            {"return_pct": 2.00, "sell_fraction": 0.30},
            {"return_pct": 4.00, "sell_fraction": 1.00}
        ]
    },
    "agent": {
        "enabled": False,
        "provider": "codex",
        "codex_path": "codex",
        "timeout_seconds": 90,
        "daily_limits": {"low": 8, "medium": 2, "high": 0},
        "models": {"low": "", "medium": ""},
        "reasoning_effort": {"low": "low", "medium": "medium"}
    },
    "autonomous_search": {
        "enabled": True,
        "codex_path": "codex",
        "model": "gpt-5.3-codex-spark",
        "fallback_models": ["gpt-5.6-luna", "gpt-5.6-sol"],
        "reasoning_effort": "low",
        "timeout_seconds": 180,
        "max_concurrent_agents": 2,
        "profiles": {
            "trend_scout": {
                "model": "gpt-5.3-codex-spark",
                "reasoning_effort": "low",
                "fallback_models": ["gpt-5.6-luna"],
                "fallback_reasoning_effort": "low"
            },
            "token_context": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "low",
                "fallback_models": ["gpt-5.6-terra", "gpt-5.6-sol"],
                "fallback_reasoning_effort": "medium"
            },
            "source_discovery": {
                "model": "gpt-5.3-codex-spark",
                "reasoning_effort": "low",
                "fallback_models": ["gpt-5.6-luna"],
                "fallback_reasoning_effort": "low"
            },
            "fact_verifier": {
                "model": "gpt-5.6-terra",
                "reasoning_effort": "medium",
                "fallback_models": ["gpt-5.6-sol"],
                "fallback_reasoning_effort": "medium"
            }
        },
        "trend_scout_enabled": True,
        "trend_scout_startup_delay_seconds": 45,
        "trend_scout_check_seconds": 30,
        "trend_scout_base_interval_minutes": 12,
        "trend_scout_surge_interval_minutes": 3,
        "trend_scout_quiet_interval_minutes": 30,
        "trend_scout_fallback_min_interval_minutes": 30,
        "trend_scout_fallback_surge_interval_minutes": 10,
        "trend_scout_high_token_threshold": 18_000,
        "trend_scout_high_token_min_interval_minutes": 30,
        "trend_scout_high_token_surge_interval_minutes": 10,
        "trend_scout_surge_duration_minutes": 30,
        "trend_scout_empty_streak_for_quiet": 3,
        "trend_scout_daily_limit": 64,
        "trend_scout_daily_token_budget": 500_000,
        "trend_scout_token_reserve_per_call": 40_000,
        "trend_scout_lookback_minutes": 120,
        "trend_scout_lanes_per_run": 3,
        "trend_scout_surge_lanes_per_run": 5,
        "trend_scout_min_confidence": 0.78,
        "trend_scout_min_memeability": 0.65,
        "trend_scout_min_relevance": 0.72,
        "trend_scout_min_independent_sources": 2,
        "trend_scout_max_events": 3,
        "trend_scout_max_sources_per_event": 3,
        "trend_scout_max_web_searches": 4,
        "trend_scout_surge_attention": 70,
        "source_learning_enabled": True,
        "source_learning_lookback_days": 90,
        "source_learning_min_closed_outcomes": 20,
        "source_learning_min_event_days": 10,
        "source_learning_min_losing_outcomes": 5,
        "source_learning_entity_min_closed_outcomes": 30,
        "source_learning_entity_min_event_days": 15,
        "source_learning_entity_min_platforms": 2,
        "source_learning_exploration_fraction": 0.40,
        "startup_delay_seconds": 120,
        "source_discovery_check_minutes": 60,
        "source_discovery_interval_hours": 24,
        "source_empty_retry_hours": 12,
        "source_error_retry_hours": 4,
        "source_discovery_daily_limit": 2,
        "source_discovery_daily_token_budget": 100_000,
        "source_discovery_token_reserve_per_call": 30_000,
        "max_source_candidates": 6,
        "max_active_rss_sources": 16,
        "max_feed_item_age_hours": 72,
        "source_auto_pause_failures": 3,
        "source_quality_min_recent_items": 2,
        "source_max_market_digest_ratio": 0.5,
        "verify_public_dns": True,
        "context_search_enabled": True,
        "context_search_daily_limit": 8,
        "token_context_daily_token_budget": 250_000,
        "token_context_token_reserve_per_call": 30_000,
        "fact_verifier_enabled": True,
        "fact_verifier_daily_limit": 192,
        "fact_verifier_daily_token_budget": 50_000_000,
        "fact_verifier_token_reserve_per_call": 60_000,
        "fact_verifier_max_web_searches": 6,
        "context_global_cooldown_minutes": 5,
        "context_error_retry_minutes": 10,
        "context_min_momentum_score": 80,
        "context_direct_trigger_enabled": True,
        "context_metadata_link_trigger_enabled": True,
        "context_low_information_exposure_only_enabled": False,
        "context_deferred_retry_enabled": False,
        "context_deferred_retry_min_idle_minutes": 5,
        "context_deferred_retry_interval_minutes": 5,
        "context_high_impact_min_priority": 4,
        "context_direct_event_min_attention": 55,
        "context_direct_event_min_match_score": 70,
        "context_token_cooldown_minutes": 240,
        "context_lookback_minutes": 180,
        "context_min_confidence": 0.78,
        "context_min_relevance": 0.72,
        "context_min_independent_sources": 2,
        "context_max_results": 5,
        "topics": [
            "breaking global news, politics and public figures",
            "viral animals, internet culture, celebrities and entertainment",
            "sports moments with strong meme potential",
            "AI, gaming and technology memes",
            "crypto-native community events"
        ]
    },
    "notifications": {
        "jsonl": "data/notifications.jsonl",
        "ntfy_url": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "notify_raw_events": False,
        "notify_new_tokens": False,
        "notify_wait": False,
        "minimum_event_attention": 35.0,
        "event_attention_step": 15.0,
        "source_error_cooldown_minutes": 30,
    },
    "source_stale_minutes": {"browser": 3, "pumpportal": 3, "other": 20},
    "live": {"enabled": False}
}


def _reverse_news_matches_token(token: TokenCandidate, observation: Observation) -> bool:
    article_text = clean_text(f"{observation.title}\n{observation.text}")
    name = clean_text(token.name)
    if name and name in article_text:
        return True
    article_terms = terms(article_text)
    name_terms = terms(token.name)
    if name_terms and name_terms.issubset(article_terms):
        return True
    symbol = clean_text(token.symbol).strip("$#")
    return len(symbol) >= 5 and symbol in article_terms


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def configure_project_temp(root: Path) -> Path:
    """Keep memeTrader and its Agent subprocess temporary files beside the project."""
    temp_root = (root / "data" / "tmp").resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(temp_root)
    os.environ["TMP"] = str(temp_root)
    tempfile.tempdir = str(temp_root)
    return temp_root


def load_config(path: str | Path) -> tuple[dict[str, Any], Path]:
    config_path = Path(path).resolve()
    configure_project_temp(config_path.parent)
    payload = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    migrated = json.loads(json.dumps(payload))

    runtime = migrated.get("runtime") or {}
    for old, new in {
        "event_scan_seconds": "event_scan_seconds",
        "position_scan_seconds": "position_scan_seconds",
        "source_health_seconds": "source_health_seconds",
    }.items():
        if old in runtime and new not in migrated:
            migrated[new] = runtime[old]
    if "token_watch_seconds" in runtime:
        migrated.setdefault("candidate", {}).setdefault("retry_seconds", runtime["token_watch_seconds"])
    if "poll_seconds" not in migrated:
        interval_values = [
            (migrated.get("sources") or {}).get(name)
            for name in ("rss_interval_seconds", "bluesky_interval_seconds", "mastodon_interval_seconds", "gecko_interval_seconds")
        ]
        interval_values = [float(value) for value in interval_values if value is not None and float(value) > 0]
        if interval_values:
            migrated["poll_seconds"] = min(interval_values)

    paper = migrated.setdefault("paper", {})
    if "initial_cash_usd" in migrated and "starting_cash_usd" not in paper:
        paper["starting_cash_usd"] = migrated["initial_cash_usd"]
    for old, new in {
        "initial_cash_usd": "starting_cash_usd",
        "risk_per_trade": "risk_per_trade_pct",
        "max_liquidity_impact": "max_liquidity_impact_pct",
    }.items():
        if old in paper and new not in paper:
            paper[new] = paper[old]
    if "fee_rate" in paper and "fee_bps" not in paper:
        paper["fee_bps"] = float(paper["fee_rate"]) * 10_000
    if "trailing_drawdown_pct" in paper:
        paper["trailing_drawdown_pct"] = abs(float(paper["trailing_drawdown_pct"]))

    events = migrated.setdefault("events", {})
    if "minimum_attention_score" in events and "event_min_attention" not in migrated:
        migrated["event_min_attention"] = events["minimum_attention_score"]

    candidate = migrated.setdefault("candidate", {})
    for old, new in {
        "max_alias_queries_per_event": "max_alias_queries",
        "recent_token_hours": "token_watch_minutes",
        "min_total_score": "min_candidate_score",
    }.items():
        if old in candidate and new not in candidate:
            candidate[new] = float(candidate[old]) * 60 if old == "recent_token_hours" else candidate[old]
    candidate.setdefault("max_source_age_minutes", events.get("max_source_age_minutes", 30))

    safety = migrated.setdefault("safety", {})
    if "max_sell_tax_pct" in safety and "max_tax_pct" not in safety:
        safety["max_tax_pct"] = safety["max_sell_tax_pct"]
    if "min_buy_sell_ratio" in safety and "min_buy_ratio" not in safety:
        safety["min_buy_ratio"] = safety["min_buy_sell_ratio"]
    if "max_external_risk_level" in safety and "max_solana_risk_score" not in safety:
        safety["max_solana_risk_score"] = safety["max_external_risk_level"]

    config = deep_merge(DEFAULT_CONFIG, migrated)
    root = config_path.parent
    if config.get("mode") not in {"shadow", "paper"}:
        raise ValueError("only shadow and paper modes are implemented; live is hard-locked")
    if bool((config.get("live") or {}).get("enabled")):
        raise ValueError("live.enabled must remain false in this release")

    bridge = config.get("bridge") or {}
    if str(bridge.get("host")) not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("bridge.host must be a loopback address")
    bridge_token = str(bridge.get("token") or "")
    if len(bridge_token) < 24 or bridge_token == "CHANGE_ME" or bridge_token.startswith("RUN_INIT"):
        raise ValueError("run `python -m memetrader init --config config.json` to create a private loopback token")
    if not 1 <= int(bridge.get("max_body_bytes", 262_144)) <= 1_000_000:
        raise ValueError("bridge.max_body_bytes must be between 1 and 1000000")

    sources = config.get("sources") or {}
    if not 16_384 <= int(sources.get("rss_max_response_bytes", 1_048_576)) <= 5_000_000:
        raise ValueError("sources.rss_max_response_bytes must be between 16384 and 5000000")
    if not 0 <= int(sources.get("rss_max_redirects", 5)) <= 10:
        raise ValueError("sources.rss_max_redirects must be between 0 and 10")
    try:
        sources["rss_proxy_url"] = normalize_loopback_socks5_proxy_url(
            str(sources.get("rss_proxy_url") or "")
        )
    except ValueError as exc:
        raise ValueError(
            "sources.rss_proxy_url must be an unauthenticated socks5 URL at a literal loopback IP"
        ) from exc
    for item in sources.get("rss", []):
        if not isinstance(item, dict) or not item.get("url"):
            raise ValueError("sources.rss entries require a URL")
        try:
            normalize_public_http_url(str(item["url"]))
        except ValueError as exc:
            raise ValueError("sources.rss URLs must be credential-free public http/https URLs") from exc

    dex_discovery = sources.get("dexscreener_discovery") or {}
    if not isinstance(dex_discovery, dict):
        raise ValueError("sources.dexscreener_discovery must be an object")
    if dex_discovery.get("enabled", True):
        raw_discovery_chains = dex_discovery.get("chains", [])
        if not isinstance(raw_discovery_chains, list):
            raise ValueError("sources.dexscreener_discovery.chains must be a list")
        discovery_chains = list(dict.fromkeys(
            str(chain).strip().lower()
            for chain in raw_discovery_chains
            if str(chain).strip()
        ))
        if not 1 <= len(discovery_chains) <= 16 or any(
            len(chain) > 40 for chain in discovery_chains
        ):
            raise ValueError(
                "sources.dexscreener_discovery.chains must contain between 1 and 16 bounded chain identifiers"
            )
        dex_discovery["chains"] = discovery_chains
        raw_surface_chains = dex_discovery.get("surface_chains", [])
        if not isinstance(raw_surface_chains, list):
            raise ValueError("sources.dexscreener_discovery.surface_chains must be a list")
        surface_chains = list(dict.fromkeys(
            str(chain).strip().lower()
            for chain in raw_surface_chains
            if str(chain).strip()
        ))
        if len(surface_chains) > 16 or any(len(chain) > 40 for chain in surface_chains):
            raise ValueError(
                "sources.dexscreener_discovery.surface_chains must contain at most 16 bounded chain identifiers"
            )
        dex_discovery["surface_chains"] = surface_chains
        interval = float(dex_discovery.get("interval_seconds", 90))
        if not 30 <= interval <= 3600:
            raise ValueError("sources.dexscreener_discovery.interval_seconds must be between 30 and 3600")
        max_items = int(dex_discovery.get("max_items_per_surface", 40))
        if not 1 <= max_items <= 100:
            raise ValueError("sources.dexscreener_discovery.max_items_per_surface must be between 1 and 100")
        max_hydrations = int(dex_discovery.get("max_hydrations_per_cycle", 180))
        if not 0 <= max_hydrations <= 300:
            raise ValueError("sources.dexscreener_discovery.max_hydrations_per_cycle must be between 0 and 300")
        active_minutes = int(dex_discovery.get("active_token_minutes", 180))
        if not 1 <= active_minutes <= 1440:
            raise ValueError("sources.dexscreener_discovery.active_token_minutes must be between 1 and 1440")

    multichain_meme_data = sources.get("multichain_meme_data") or {}
    if not isinstance(multichain_meme_data, dict):
        raise ValueError("sources.multichain_meme_data must be an object")
    raw_multichain_chains = multichain_meme_data.get("chains", [])
    if not isinstance(raw_multichain_chains, list):
        raise ValueError("sources.multichain_meme_data.chains must be a list")
    multichain_chains = list(dict.fromkeys(
        str(chain).strip().lower()
        for chain in raw_multichain_chains
        if str(chain).strip()
    ))
    if not 1 <= len(multichain_chains) <= 16 or any(
        len(chain) > 40 for chain in multichain_chains
    ):
        raise ValueError(
            "sources.multichain_meme_data.chains must contain between 1 and 16 bounded chain identifiers"
        )
    multichain_meme_data["chains"] = multichain_chains
    multichain_interval = float(multichain_meme_data.get("interval_seconds", 90))
    if not 30 <= multichain_interval <= 3600:
        raise ValueError(
            "sources.multichain_meme_data.interval_seconds must be between 30 and 3600"
        )

    for name in ("poll_seconds", "reverse_news_seconds", "event_scan_seconds", "position_scan_seconds", "source_health_seconds"):
        if float(config.get(name, 0)) <= 0:
            raise ValueError(f"{name} must be positive")

    autonomous = config["autonomous_search"]
    if autonomous.get("enabled", False):
        for name in (
            "source_discovery_check_minutes",
            "source_discovery_interval_hours",
            "source_empty_retry_hours",
            "source_error_retry_hours",
            "trend_scout_check_seconds",
            "trend_scout_base_interval_minutes",
            "trend_scout_surge_interval_minutes",
            "trend_scout_quiet_interval_minutes",
            "trend_scout_fallback_min_interval_minutes",
            "trend_scout_fallback_surge_interval_minutes",
            "trend_scout_high_token_min_interval_minutes",
            "trend_scout_high_token_surge_interval_minutes",
            "trend_scout_surge_duration_minutes",
            "context_global_cooldown_minutes",
            "context_error_retry_minutes",
            "source_quality_min_recent_items",
            "source_learning_lookback_days",
            "source_learning_min_closed_outcomes",
            "source_learning_min_event_days",
            "source_learning_min_losing_outcomes",
            "source_learning_entity_min_closed_outcomes",
            "source_learning_entity_min_event_days",
            "source_learning_entity_min_platforms",
        ):
            if float(autonomous.get(name, 0)) <= 0:
                raise ValueError(f"autonomous_search.{name} must be positive")
        for name in (
            "trend_scout_daily_limit",
            "trend_scout_daily_token_budget",
            "trend_scout_token_reserve_per_call",
            "source_discovery_daily_limit",
            "source_discovery_daily_token_budget",
            "source_discovery_token_reserve_per_call",
            "context_search_daily_limit",
            "token_context_daily_token_budget",
            "token_context_token_reserve_per_call",
            "fact_verifier_daily_limit",
            "fact_verifier_daily_token_budget",
            "fact_verifier_token_reserve_per_call",
            "trend_scout_high_token_threshold",
        ):
            if int(autonomous.get(name, 0)) < 0:
                raise ValueError(f"autonomous_search.{name} must be non-negative")
        if not 1 <= int(autonomous.get("max_concurrent_agents", 2)) <= 2:
            raise ValueError("autonomous_search.max_concurrent_agents must be between 1 and 2")
        if int(autonomous.get("trend_scout_lanes_per_run", 1)) < 1:
            raise ValueError("autonomous_search.trend_scout_lanes_per_run must be positive")
        if int(autonomous.get("trend_scout_surge_lanes_per_run", 1)) < 1:
            raise ValueError("autonomous_search.trend_scout_surge_lanes_per_run must be positive")
        if int(autonomous.get("source_auto_pause_failures", 3)) < 1:
            raise ValueError("autonomous_search.source_auto_pause_failures must be positive")
        if not 1 <= int(autonomous.get("context_high_impact_min_priority", 4)) <= 5:
            raise ValueError("autonomous_search.context_high_impact_min_priority must be between 1 and 5")
        for name in ("context_min_momentum_score", "context_direct_event_min_attention", "context_direct_event_min_match_score"):
            if not 0 <= float(autonomous.get(name, 0)) <= 100:
                raise ValueError(f"autonomous_search.{name} must be between 0 and 100")
        market_ratio = float(autonomous.get("source_max_market_digest_ratio", 0.5))
        if not 0 <= market_ratio <= 1:
            raise ValueError("autonomous_search.source_max_market_digest_ratio must be between 0 and 1")
        if not 30 <= int(autonomous.get("timeout_seconds", 180)) <= 300:
            raise ValueError("autonomous_search.timeout_seconds must be between 30 and 300")
        exploration_fraction = float(autonomous.get("source_learning_exploration_fraction", 0.4))
        if not 0.4 <= exploration_fraction < 1:
            raise ValueError("autonomous_search.source_learning_exploration_fraction must be between 0.4 and 1")
        if int(autonomous.get("source_learning_min_losing_outcomes", 5)) > int(
            autonomous.get("source_learning_min_closed_outcomes", 20)
        ):
            raise ValueError("source learning losing-outcome minimum cannot exceed its closed-outcome minimum")
        if int(autonomous.get("source_learning_entity_min_closed_outcomes", 30)) < int(
            autonomous.get("source_learning_min_closed_outcomes", 20)
        ):
            raise ValueError("entity source learning requires at least the general closed-outcome minimum")
        for task, profile in (autonomous.get("profiles") or {}).items():
            if not isinstance(profile, dict) or not str(profile.get("model") or "").strip():
                raise ValueError(f"autonomous_search.profiles.{task}.model is required")

    paper = config["paper"]
    if not -0.95 < float(paper["stop_loss_pct"]) < 0:
        raise ValueError("paper.stop_loss_pct must be between -0.95 and 0")
    drawdown = abs(float(paper["trailing_drawdown_pct"]))
    if not 0 < drawdown < 1:
        raise ValueError("paper.trailing_drawdown_pct must be between 0 and 1")
    paper["trailing_drawdown_pct"] = drawdown
    if not 0 <= float(paper.get("slippage_rate", 0)) < 0.5:
        raise ValueError("paper.slippage_rate must be between 0 and 0.5")
    if not 0 <= float(paper["fee_bps"]) <= 5000:
        raise ValueError("paper.fee_bps must be between 0 and 5000")
    if not 0 <= float(paper.get("pump_swap_fee_bps", paper["fee_bps"])) <= 5000:
        raise ValueError("paper.pump_swap_fee_bps must be between 0 and 5000")
    if not 0 <= float(paper.get("fixed_fee_usd_each_side", 0)) <= 10_000:
        raise ValueError("paper.fixed_fee_usd_each_side must be between 0 and 10000")
    if not 0 <= float(paper.get("fixed_position_usd", 0)) <= 1_000_000:
        raise ValueError("paper.fixed_position_usd must be between 0 and 1000000")
    if not 1 <= float(paper.get("max_quote_age_seconds", 45)) <= 600:
        raise ValueError("paper.max_quote_age_seconds must be between 1 and 600")
    if int(paper["max_open_positions"]) < 0:
        raise ValueError("paper.max_open_positions must be non-negative; 0 means unlimited")
    tiers = paper.get("take_profit_tiers") or []
    previous_return = -1.0
    for tier in tiers:
        return_pct = float(tier["return_pct"])
        fraction = float(tier["sell_fraction"])
        if return_pct <= previous_return or not 0 < fraction <= 1:
            raise ValueError("paper.take_profit_tiers must be increasing with fractions in (0,1]")
        previous_return = return_pct

    raw_chains = config["candidate"].get("chains", [])
    if not isinstance(raw_chains, list):
        raise ValueError("candidate.chains must be a non-empty list")
    chains = list(dict.fromkeys(str(chain).strip().lower() for chain in raw_chains if str(chain).strip()))
    if not 1 <= len(chains) <= 16 or any(len(chain) > 40 for chain in chains):
        raise ValueError("candidate.chains must contain between 1 and 16 bounded chain identifiers")
    config["candidate"]["chains"] = chains
    return config, root


def initial_config() -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["bridge"]["token"] = secrets.token_urlsafe(32)
    return config


class SingleInstance:
    """OS file lock released automatically if the process exits or crashes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError(f"another memeTrader process is already running: {self.path}") from exc
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.handle:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


class Notifier:
    def __init__(self, root: Path, config: dict[str, Any]):
        path = Path(str(config.get("jsonl", "data/notifications.jsonl")))
        self.path = path if path.is_absolute() else root / path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ntfy_url = str(config.get("ntfy_url") or "").strip()
        self.telegram_bot_token = str(config.get("telegram_bot_token") or "").strip()
        self.telegram_chat_id = str(config.get("telegram_chat_id") or "").strip()

    @staticmethod
    def _request(url: str, data: bytes, headers: dict[str, str]) -> None:
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=8):
                pass
        except Exception:
            pass

    def send(self, kind: str, title: str, payload: dict[str, Any] | None = None) -> None:
        item = {"time": iso(), "kind": kind, "title": title, "payload": payload or {}}
        line = json.dumps(item, ensure_ascii=False, default=str)
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        summary = f"[{kind}] {title}\\n{json.dumps(payload or {}, ensure_ascii=False, default=str)[:2500]}"
        if self.ntfy_url:
            threading.Thread(
                target=self._request,
                args=(self.ntfy_url, summary.encode("utf-8"), {"Content-Type": "text/plain; charset=utf-8", "Title": f"memeTrader: {kind}"}),
                daemon=True,
            ).start()
        if self.telegram_bot_token and self.telegram_chat_id:
            body = urllib.parse.urlencode({"chat_id": self.telegram_chat_id, "text": summary[:4000]}).encode("utf-8")
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            threading.Thread(
                target=self._request,
                args=(url, body, {"Content-Type": "application/x-www-form-urlencoded"}),
                daemon=True,
            ).start()


def _watchlist_accounts(settings_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("watch_accounts") if isinstance(payload, dict) else None
    return [row for row in rows[:500] if isinstance(row, dict)] if isinstance(rows, list) else []


def resolve_watchlist_account(item: dict[str, Any], settings_path: Path) -> dict[str, Any] | None:
    """Resolve only an explicitly configured exact platform/handle/entity mapping."""
    supplied = sanitize_source_entity_id(item.get("source_entity_id"))
    platform = str(item.get("platform") or "").strip().lower()
    author = str(item.get("author") or "").strip().casefold().lstrip("@")
    if not supplied or not platform or not author or platform == "telegram":
        return None
    for account in _watchlist_accounts(settings_path):
        if account.get("enabled", True) is False:
            continue
        account_platform = str(account.get("platform") or "").strip().lower()
        account_handle = str(account.get("handle") or "").strip().casefold().lstrip("@")
        configured = sanitize_source_entity_id(account.get("entity_id"))
        if account_platform == platform and account_handle == author:
            if configured != supplied:
                return None
            try:
                priority = max(1, min(5, int(account.get("priority", 3))))
            except (TypeError, ValueError):
                priority = 3
            return {
                "platform": platform,
                "handle": str(account.get("handle") or "").strip()[:120],
                "entity_id": configured,
                "priority": priority,
                "watch_cadence": "critical"
                if str(account.get("watch_cadence") or "").lower() == "critical" else "normal",
            }
    return None


def resolve_watchlist_source_entity_id(item: dict[str, Any], settings_path: Path) -> str:
    account = resolve_watchlist_account(item, settings_path)
    return str((account or {}).get("entity_id") or "")


def _watch_page_key(value: Any) -> tuple[str, str] | None:
    try:
        parsed = urllib.parse.urlsplit(str(value or "").strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower().removeprefix("www.")
    if host == "twitter.com":
        host = "x.com"
    path = urllib.parse.unquote(parsed.path).rstrip("/").casefold()
    return (host, path) if path else None


def resolve_watchlist_heartbeat_account(
    detail: dict[str, Any], settings_path: Path,
) -> dict[str, Any] | None:
    platform = str(detail.get("platform") or "").strip().lower()
    page_key = _watch_page_key(detail.get("page_url"))
    if not platform or platform == "telegram" or page_key is None:
        return None
    for account in _watchlist_accounts(settings_path):
        if account.get("enabled", True) is False:
            continue
        if str(account.get("platform") or "").strip().lower() != platform:
            continue
        if _watch_page_key(account.get("url")) != page_key:
            continue
        handle = str(account.get("handle") or "").strip()[:120]
        entity_id = sanitize_source_entity_id(account.get("entity_id"))
        if not handle or not entity_id:
            continue
        try:
            priority = max(1, min(5, int(account.get("priority", 3))))
        except (TypeError, ValueError):
            priority = 3
        return {
            "platform": platform,
            "handle": handle,
            "entity_id": entity_id,
            "priority": priority,
            "watch_cadence": "critical"
            if str(account.get("watch_cadence") or "").lower() == "critical" else "normal",
        }
    return None


TELEGRAM_MANUAL_ONLY_HOSTS = {"t.me", "telegram.me"}


def _browser_bridge_url_host(value: Any) -> tuple[bool, str]:
    """Return a conservative final URL host; malformed/credential URLs are invalid."""
    raw = str(value or "")
    if not raw:
        return True, ""
    if raw != raw.strip() or "\\" in raw or any(ord(char) <= 32 or ord(char) == 127 for char in raw):
        return False, ""
    try:
        parsed = urllib.parse.urlsplit(raw)
        _ = parsed.port
    except (TypeError, ValueError):
        return False, ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False, ""
    if parsed.username is not None or parsed.password is not None or "%" in parsed.netloc:
        return False, ""
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except (UnicodeError, ValueError):
        return False, ""
    return bool(host), host


def _is_telegram_manual_only_host(host: str) -> bool:
    value = str(host or "").lower().rstrip(".")
    return any(value == root or value.endswith(f".{root}") for root in TELEGRAM_MANUAL_ONLY_HOSTS)


def _browser_bridge_item_allowed(*, platform: Any, source: Any, url: Any) -> bool:
    platform_name = str(platform or "").strip().casefold()
    source_name = str(source or "").strip().casefold()
    if platform_name == "telegram":
        return False
    source_parts = source_name.split(":")
    if source_parts[0] == "telegram" or (
        len(source_parts) > 1 and source_parts[0] == "browser" and source_parts[1] == "telegram"
    ):
        return False
    for candidate in (url, source if "://" in str(source or "") else ""):
        valid, host = _browser_bridge_url_host(candidate)
        if not valid or _is_telegram_manual_only_host(host):
            return False
    return True


class BrowserBridge:
    def __init__(
        self, host: str, port: int, token: str,
        on_observation: Callable[[Observation], Awaitable[None]],
        on_heartbeat: Callable[[str, dict[str, Any]], Awaitable[None]],
        *,
        max_body_bytes: int = 262_144,
        source_entity_resolver: Callable[[dict[str, Any]], str] | None = None,
    ):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("browser bridge must bind to loopback")
        self.host, self.port, self.token = host, port, token
        self.max_body_bytes = int(max_body_bytes)
        self.on_observation, self.on_heartbeat = on_observation, on_heartbeat
        self.source_entity_resolver = source_entity_resolver
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.host, self.port)

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _respond(self, writer: asyncio.StreamWriter, status: str, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = (
            f"HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(data)}\r\nAccess-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Headers: Content-Type,X-MemeTrader-Token\r\n"
            "Access-Control-Allow-Methods: GET,POST,OPTIONS\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        writer.write(headers + data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            if len(head) > 64_000:
                raise ValueError("headers too large")
            lines = head.decode("latin-1").split("\r\n")
            method, target, _ = lines[0].split(" ", 2)
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            if method == "OPTIONS":
                await self._respond(writer, "204 No Content", {})
                return
            if method == "GET" and urllib.parse.urlparse(target).path == "/health":
                await self._respond(writer, "200 OK", {"ok": True, "time": iso()})
                return
            if headers.get("x-memetrader-token") != self.token:
                await self._respond(writer, "401 Unauthorized", {"ok": False, "error": "bad token"})
                return
            size = int(headers.get("content-length", "0") or 0)
            if size < 0 or size > self.max_body_bytes:
                raise ValueError("invalid content length")
            body = await reader.readexactly(size) if size else b"{}"
            payload = json.loads(body.decode("utf-8"))
            path = urllib.parse.urlparse(target).path
            if method == "POST" and path in {"/heartbeat", "/v1/heartbeat"}:
                source = str(payload.get("source") or payload.get("url") or "browser")[:300]
                raw_detail = payload.get("detail") if isinstance(payload.get("detail"), dict) else payload
                detail = raw_detail if isinstance(raw_detail, dict) else {}
                if not _browser_bridge_item_allowed(
                    platform=detail.get("platform") or payload.get("platform"),
                    source=source,
                    url=detail.get("page_url") or payload.get("url"),
                ):
                    await self._respond(writer, "200 OK", {"ok": True, "accepted": 0})
                    return
                await self.on_heartbeat(source, detail)
                await self._respond(writer, "200 OK", {"ok": True})
                return
            if method == "POST" and path in {"/observe", "/v1/observe"}:
                items = payload if isinstance(payload, list) else [payload]
                accepted = 0
                for item in items[:200]:
                    if not isinstance(item, dict):
                        continue
                    if not _browser_bridge_item_allowed(
                        platform=item.get("platform"),
                        source=item.get("source"),
                        url=item.get("url"),
                    ):
                        continue
                    source_item_state = str(item.get("source_item_state") or "present").strip().lower()
                    if source_item_state not in {
                        "present", "deleted", "retracted", "correction", "access_lost", "restored",
                    }:
                        source_item_state = "present"
                    source_item_state_evidence = str(
                        item.get("source_item_state_evidence") or ""
                    ).strip().lower()
                    if source_item_state_evidence not in {
                        "platform_deleted_marker", "publisher_deleted_marker",
                        "publisher_retraction_marker", "publisher_correction_marker",
                        "platform_restored_marker", "http_410", "access_denied", "api_revision",
                    }:
                        source_item_state_evidence = ""
                    source_item_id = str(item.get("source_item_id") or item.get("url") or "")[:2000]
                    title = str(item.get("title") or item.get("text") or "").strip()
                    if not title and source_item_id and source_item_state != "present":
                        title = "Source item state marker"
                    # Client timestamps are untrusted. Availability starts only when this
                    # local process receives the item.
                    observed_at = utcnow()
                    published_at = None
                    if item.get("published_at"):
                        try:
                            published_at = parse_time(item["published_at"])
                        except Exception:
                            published_at = None
                    if not title:
                        continue
                    source_entity_id = ""
                    if self.source_entity_resolver is not None:
                        source_entity_id = sanitize_source_entity_id(self.source_entity_resolver(item))
                    browser_item = {
                        key: value for key, value in item.items()
                        if key not in {"source_entity_id", "claim_target_url"}
                    }
                    if source_entity_id:
                        browser_item["source_entity_id"] = source_entity_id
                    claim_target_url = ""
                    if (
                        source_item_state in {"correction", "retracted"}
                        and source_item_state_evidence in {
                            "publisher_correction_marker", "publisher_retraction_marker"
                        }
                        and isinstance(item.get("claim_target_url"), str)
                    ):
                        requested_target = str(item["claim_target_url"])[:2000]
                        claim_target_url = (
                            Store._revision_safe_url(requested_target) or "invalid://claim-target"
                        )
                    await self.on_observation(
                        Observation(
                            source=str(item.get("source") or "browser"),
                            source_kind=str(item.get("source_kind") or "social"),
                            title=title[:500], text=str(item.get("text") or title)[:20_000],
                            url=str(item.get("url") or "")[:2000], author=str(item.get("author") or "")[:300],
                            published_at=published_at, observed_at=observed_at,
                            ingested_at=utcnow(), availability_proof="local_receive",
                            source_item_id=source_item_id,
                            capture_phase=str(item.get("capture_phase") or "live")[:20],
                            role="identity" if source_item_state != "present" else "feature",
                            raw={
                                "browser": browser_item,
                                **({"source_entity_id": source_entity_id} if source_entity_id else {}),
                                "source_item_state": source_item_state,
                                **({"source_item_state_evidence": source_item_state_evidence} if source_item_state_evidence else {}),
                                **({"claim_target_url": claim_target_url} if claim_target_url else {}),
                                **({
                                    "source_reported_revision_at": str(item.get("source_reported_revision_at"))[:100]
                                } if item.get("source_reported_revision_at") else {}),
                                **{
                                    key: item.get(key)
                                    for key in ("like_count", "repost_count", "reply_count", "view_count", "score", "priority")
                                    if item.get(key) is not None
                                },
                            },
                        )
                    )
                    accepted += 1
                await self._respond(writer, "200 OK", {"ok": True, "accepted": accepted})
                return
            await self._respond(writer, "404 Not Found", {"ok": False, "error": "not found"})
        except Exception as exc:
            try:
                await self._respond(writer, "400 Bad Request", {"ok": False, "error": type(exc).__name__})
            except Exception:
                writer.close()


class Runtime:
    MAX_DIRECT_HIGH_IMPACT_CONTEXT_PER_CYCLE = 4
    MAX_DIRECT_BROWSER_EXACT_CONTEXT_PER_CYCLE = 4
    MAX_DIRECT_ONCHAIN_CONTEXT_PER_CYCLE = 1
    CHAIN_MEME_ACCOUNT_SNAPSHOT_INTERVAL_SECONDS = 10.0
    CHAIN_MEME_ACTIVE_MARK_INTERVAL_SECONDS = 1.0
    CHAIN_MEME_CARRIED_MARK_INTERVAL_SECONDS = 15.0
    DIRECT_CONTEXT_LANE_CURSOR_KEY = "token_context:hydration_fair_lane_cursor:v2"
    DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY = "token_context:active_retry:activated_at:v1"
    DEFERRED_CONTEXT_RETRY_RUN_KEY = "token_context:active_retry:last_run:v1"
    INFORMATION_FIRST_ACTIVE_OUTCOME_REQUEST_TIMEOUT_SECONDS = 15.0

    def __init__(self, config: dict[str, Any], root: Path):
        self.config, self.root = config, root
        zerox_api_key = os.environ.get("MEMETRADER_ZEROX_API_KEY", "").strip()
        jupiter_api_key = os.environ.get("MEMETRADER_JUPITER_API_KEY", "").strip()
        db_path = Path(str(config["database"]))
        starting_cash = float(config["paper"].get("starting_cash_usd", 1_000))
        self.store = Store(
            db_path if db_path.is_absolute() else root / db_path,
            initial_cash_usd=starting_cash,
        )
        self._last_chain_account_snapshot_monotonic = 0.0
        self.chain_meme_trader_only = bool(config.get("chain_meme_trader_only_enabled", False))
        self.strategy_focus_active = bool(
            config.get("onchain_primary_focus_enabled", False)
            or self.chain_meme_trader_only
        )
        if self.strategy_focus_active:
            self.store.register_strategy_focus()
            self.store.register_route_surface_observations()
        self.store.register_provider_post_ambiguity_shadow(
            _watchlist_accounts(root / "data" / "web_console" / "console_settings.json")
        )
        paper_config = config["paper"]
        self.store.register_token_universe_outcome_quality(
            reference_notional_usd=float(paper_config.get("max_position_usd", 35)),
            min_liquidity_usd=float(config["safety"].get("min_liquidity_usd", 12_000)),
            max_liquidity_impact_pct=float(paper_config.get("max_liquidity_impact_pct", 0.0025)),
            slippage_rate=float(paper_config.get("slippage_rate", 0.04)),
            default_fee_bps=float(paper_config.get("fee_bps", 60)),
            pump_fee_bps=float(paper_config.get("pump_swap_fee_bps", 125)),
            max_quote_age_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
            max_tax_pct=float(config["safety"].get("max_tax_pct", 10)),
        )
        self.store.register_token_universe_fixed_target_execution(
            paper_stake_usd=float(paper_config.get("max_position_usd", 35)),
            min_liquidity_usd=float(config["safety"].get("min_liquidity_usd", 12_000)),
            max_liquidity_impact_pct=float(paper_config.get("max_liquidity_impact_pct", 0.0025)),
            slippage_rate=float(paper_config.get("slippage_rate", 0.04)),
            default_fee_bps=float(paper_config.get("fee_bps", 60)),
            pump_fee_bps=float(paper_config.get("pump_swap_fee_bps", 125)),
            max_tax_pct=float(config["safety"].get("max_tax_pct", 10)),
        )
        self.store.register_onchain_only_shadow(
            momentum_threshold=float(
                (config.get("autonomous_search") or {}).get("context_min_momentum_score", 75)
            ),
            paper_stake_usd=float(paper_config.get("max_position_usd", 35)),
            min_liquidity_usd=float(config["safety"].get("min_liquidity_usd", 12_000)),
            max_liquidity_impact_pct=float(paper_config.get("max_liquidity_impact_pct", 0.0025)),
            slippage_rate=float(paper_config.get("slippage_rate", 0.04)),
            default_fee_bps=float(paper_config.get("fee_bps", 60)),
            pump_fee_bps=float(paper_config.get("pump_swap_fee_bps", 125)),
            max_tax_pct=float(config["safety"].get("max_tax_pct", 10)),
            max_quote_delay_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
        )
        self.store.register_onchain_only_jupiter_quote(
            usdc_input_amount_raw=round(
                float(paper_config.get("max_position_usd", 35)) * 1_000_000
            ),
            slippage_bps=round(float(paper_config.get("slippage_rate", 0.04)) * 10_000),
            max_queue_delay_seconds=30,
            max_total_delay_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
        )
        self.store.register_onchain_only_evm_route_quote(
            EvmUniswapV3QuoteClient.public_network_definitions(),
            paper_stake_usd=float(paper_config.get("max_position_usd", 35)),
            slippage_bps=round(float(paper_config.get("slippage_rate", 0.04)) * 10_000),
            max_queue_delay_seconds=30,
            max_total_delay_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
        )
        if zerox_api_key:
            self.store.register_onchain_only_evm_aggregator_price(
                EvmUniswapV3QuoteClient.public_network_definitions(),
                paper_stake_usd=float(paper_config.get("max_position_usd", 35)),
                slippage_bps=round(float(paper_config.get("slippage_rate", 0.04)) * 10_000),
                max_queue_delay_seconds=30,
                max_total_delay_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
            )
        if str(config.get("mode") or "paper").lower() == "paper":
            self.store.register_event_route_execution_challenger()
            self.store.register_onchain_paper_exploration(
                starting_cash_usd=starting_cash,
                max_open_positions=int(paper_config.get("max_open_positions", 0)),
                estimated_network_fee_usd_each_side=float(
                    paper_config.get("fixed_fee_usd_each_side", 0.4)
                ),
            )
            self.store.register_onchain_paper_exit_challenger(
                starting_cash_usd=starting_cash,
                position_scan_seconds=float(config.get("position_scan_seconds", 15)),
                hard_stop_return=float(paper_config.get("stop_loss_pct", -0.35)),
                trailing_activate_return=float(
                    paper_config.get("trailing_activate_pct", 0.60)
                ),
                trailing_drawdown=float(paper_config.get("trailing_drawdown_pct", 0.28)),
                emergency_liquidity_usd=float(
                    paper_config.get("emergency_liquidity_usd", 3_000)
                ),
                slippage_bps=round(
                    float(paper_config.get("slippage_rate", 0.04)) * 10_000
                ),
                max_quote_delay_seconds=float(
                    paper_config.get("max_quote_age_seconds", 45)
                ),
                estimated_network_fee_usd_each_side=float(
                    paper_config.get("fixed_fee_usd_each_side", 0.4)
                ),
                max_liquidity_impact_pct=float(
                    paper_config.get("max_liquidity_impact_pct", 0.0025)
                ),
            )
            self.store.register_onchain_paper_exit_quote_scheduler()
            self.store.register_onchain_paper_position_monitor()
            if self.strategy_focus_active:
                if self.chain_meme_trader_only:
                    self.store.activate_chain_meme_trader_funded_period()
                    self.store.register_chain_meme_trader_cost_coverage_scaleout()
                    self.store.register_chain_meme_pattern_experiments()
                    self.store.register_chain_meme_v22_vault_shadow(
                        position_definition_version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
                    )
                else:
                    self.store.register_onchain_held_account_monitor()
                    self.store.register_chain_meme_trader()
                    self.store.register_chain_meme_trader_v6()
                    self.store.activate_chain_meme_trader_v6()
                    self.store.register_chain_meme_trader_v12()
                    self.store.activate_chain_meme_trader_v12()
                    self.store.register_chain_meme_trader_v13()
                    self.store.activate_chain_meme_trader_v13()
                    self.store.register_chain_meme_trader_v14()
                    self.store.activate_chain_meme_trader_v14()
                    self.store.register_chain_meme_trader_v15()
                    self.store.activate_chain_meme_trader_v15()
                    self.store.register_chain_meme_trader_v16()
                    self.store.activate_chain_meme_trader_v16()
                    self.store.register_chain_meme_trader_v17()
                    self.store.activate_chain_meme_trader_v17()
                    self.store.register_chain_meme_trader_v18()
                    self.store.activate_chain_meme_trader_v18()
                    self.store.register_chain_meme_trader_v19()
                    self.store.activate_chain_meme_trader_v19()
                    self.store.register_chain_meme_trader_v20()
                    self.store.activate_chain_meme_trader_v20()
                    self.store.register_chain_meme_trader_v21()
                    self.store.activate_chain_meme_trader_v21()
                    self.store.register_chain_meme_trader_v22()
                    self.store.activate_chain_meme_trader_v22()
                    self.store.register_chain_meme_trader_immediate_reverseability()
                    self.store.register_chain_meme_trader_local_surface_quote()
                    self.store.register_chain_meme_trader_local_critical_exit()
                    self.store.register_chain_meme_trader_executable_decay()
                    self.store.register_chain_meme_trader_executable_decay_stop()
                    self.store.register_chain_meme_trader_stage4_v2()
                    self.store.register_chain_meme_trader_postbuy_research()
                    self.store.register_route_preflight_deferred_retry_shadow()
                self.store.register_flat_compression_breakout_shadow()
            self.store.register_onchain_paper_narrative_runner(
                starting_cash_usd=starting_cash,
            )
            self.store.register_onchain_paper_narrative_context()
            self.store.register_token_information_watch(decision_window_seconds=120)
        self.store.register_token_universe_jupiter_quote(
            usdc_input_amount_raw=round(float(paper_config.get("max_position_usd", 35)) * 1_000_000),
        )
        self.store.register_token_universe_jupiter_quote_validity(
            max_queue_delay_seconds=30,
            max_total_delay_seconds=float(paper_config.get("max_quote_age_seconds", 45)),
        )
        self.store.recover_interrupted_exposure_attempts()
        self.store.recover_interrupted_event_context_route_probes()
        self.store.recover_interrupted_event_route_execution_challenger_attempts()
        self.store.recover_interrupted_chain_meme_trader_executions()
        self.store.recover_chain_meme_trader_postbuy_research()
        self.store.recover_interrupted_route_preflight_deferred_retry_shadow()
        if not self.store.open_positions() and not self.store.trades():
            with self.store.db:
                self.store.db.execute("UPDATE paper_account SET cash_usd=?,updated_at=? WHERE singleton=1", (starting_cash, iso()))
        source_config = config.get("sources") or {}
        self.http = HttpClient(
            feed_max_response_bytes=int(source_config.get("rss_max_response_bytes", 1_048_576)),
            feed_max_redirects=int(source_config.get("rss_max_redirects", 5)),
            feed_proxy_url=str(source_config.get("rss_proxy_url") or ""),
            conditional_store=self.store,
        )
        # DexScreener documents 300 requests/minute for token batches.  A
        # 250ms start interval caps this process at 240/minute while allowing
        # held-token marks to refresh materially faster than the generic
        # 600ms public-endpoint default.
        self.market_http = HttpClient(min_host_interval=0.25)
        self.jupiter_http = HttpClient(
            min_host_interval=1.05 if jupiter_api_key else 2.1
        )
        self.evm_route_http = HttpClient(min_host_interval=0.15)
        self.dex = DexScreenerClient(self.market_http)
        self.jupiter = JupiterQuoteClient(self.jupiter_http, jupiter_api_key)
        self.held_accounts = SolanaHeldAccountCollector(
            str(config["safety"].get("solana_rpc_url") or "https://api.mainnet-beta.solana.com")
        )
        self.chain_meme_v21_vault_tracker = PumpSwapVaultFlowTracker()
        self._pattern_vault_tracker = PumpSwapVaultFlowTracker(summary_seconds=10)
        self._pattern_pool_targets: dict[str, dict[str, Any]] = {}
        self._pattern_pool_retry: dict[str, float] = {}
        self._chain_meme_v21_vault_retry_after: dict[str, float] = {}
        self._chain_meme_v21_vault_last_heartbeat = 0.0
        self.evm_route = EvmUniswapV3QuoteClient(self.evm_route_http)
        self.evm_aggregator = (
            EvmZeroXPriceClient(self.evm_route_http, zerox_api_key)
            if zerox_api_key else None
        )
        self.robinhood_stock_tokens = RobinhoodStockTokenRegistryClient(
            self.evm_route_http
        )
        self._evm_route_quote_lock = asyncio.Lock()
        self._jupiter_quote_lock = asyncio.Lock()
        self._jupiter_background_dispatch_lock = asyncio.Lock()
        self._onchain_exit_dispatch_lock = asyncio.Lock()
        self._critical_onchain_exit_event = asyncio.Event()
        self._jupiter_background_epoch_started = 0.0
        self._jupiter_background_epoch_requests = 0
        self._jupiter_background_epoch_seconds = 5.0
        self._chain_meme_quote_version_cursor = 0
        self._chain_meme_normal_slot = 0
        self._wsol_usdc_conversion: dict[str, Any] | None = None
        self._wsol_usdc_conversion_at = 0.0
        self._dex_quote_lock = asyncio.Semaphore(8)
        self._chain_meme_active_idle_event = asyncio.Event()
        self._chain_meme_active_idle_event.set()
        self.events = EventEngine(
            self.store,
            similarity_threshold=float((config.get("events") or {}).get("similarity", 0.28)),
        )
        self.safety = SafetyChecker(self.http, config["safety"])
        self.agent = AgentRouter(self.store, config["agent"])
        known_source_urls = {
            str(item.get("url") or "").rstrip("/")
            for item in config["sources"].get("rss", [])
            if item.get("url")
        }
        self.autonomous_search = AutonomousSearchAgent(
            self.store,
            self.http,
            config["autonomous_search"],
            known_source_urls=known_source_urls,
            console_settings_path=root / "data" / "web_console" / "console_settings.json",
        )
        if config["autonomous_search"].get("context_deferred_retry_enabled", False):
            if not self.store.get_kv(self.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY):
                self.store.set_kv(self.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY, iso())
        self.evaluator = CandidateEvaluator(
            self.store, self.dex, self.safety, config["candidate"], self.agent,
            self.jupiter, config["paper"], self._jupiter_quote_lock,
        )
        self.policy = PaperPolicy(config["paper"])
        self.notifier = Notifier(root, config["notifications"])
        self.bridge: BrowserBridge | None = None
        self._stop = asyncio.Event()
        self._dex_quote_failure_streak = 0
        self._dex_quote_backoff_until = 0.0
        self._dex_quote_backoff_base_seconds = 2.0
        self._dex_quote_backoff_cap_seconds = 30.0
        if self.config["safety"].get("require_pretrade_rug_safety_v1", False):
            self.store.register_pretrade_rug_safety()
        self._record_paper_account_snapshot()

    async def close(self) -> None:
        if self.bridge:
            await self.bridge.close()
        await self.evm_route_http.close()
        await self.held_accounts.close()
        await self.jupiter_http.close()
        await self.market_http.close()
        await self.http.close()
        self.store.close()

    def _dex_quote_low_priority_available(self) -> bool:
        loop = asyncio.get_running_loop()
        return (
            self._chain_meme_active_idle().is_set()
            and
            not self._dex_quote_lock.locked()
            and loop.time() >= self._dex_quote_backoff_until
        )

    def _chain_meme_active_idle(self) -> asyncio.Event:
        idle = getattr(self, "_chain_meme_active_idle_event", None)
        if idle is None:
            idle = asyncio.Event()
            idle.set()
            self._chain_meme_active_idle_event = idle
        return idle

    async def _dex_batch_quote(
        self,
        chain: str,
        addresses: list[str] | tuple[str, ...],
        *,
        fresh: bool = False,
        high_priority: bool = False,
    ) -> dict[str, tuple[TokenCandidate, TokenSnapshot]]:
        """Serialize Dex quote batches and back off across lanes after transport failure."""
        if not high_priority:
            await self._chain_meme_active_idle().wait()
        loop = asyncio.get_running_loop()
        wait = self._dex_quote_backoff_until - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        while True:
            await self._dex_quote_lock.acquire()
            # A failed peer may have extended the shared backoff while this
            # caller was waiting for the serialized quote slot. Never sleep
            # while holding a batch semaphore slot.
            wait = self._dex_quote_backoff_until - loop.time()
            if wait <= 0:
                break
            self._dex_quote_lock.release()
            await asyncio.sleep(wait)
        try:
            try:
                if fresh and hasattr(self.dex, "batch_quote_fresh"):
                    quoted = await self.dex.batch_quote_fresh(chain, addresses)
                else:
                    quoted = await self.dex.batch_quote(chain, addresses)
            except httpx.TransportError as exc:
                self._dex_quote_failure_streak += 1
                base = min(
                    self._dex_quote_backoff_cap_seconds,
                    self._dex_quote_backoff_base_seconds
                    * (2 ** min(self._dex_quote_failure_streak - 1, 4)),
                )
                digest = hashlib.sha256(
                    f"dexscreener:{type(exc).__name__}:{self._dex_quote_failure_streak}".encode()
                ).digest()
                delay = base * (1.0 + int.from_bytes(digest[:2], "big") / 65535.0 * 0.2)
                self._dex_quote_backoff_until = loop.time() + delay
                raise
            self._dex_quote_failure_streak = 0
            self._dex_quote_backoff_until = 0.0
            if getattr(self, "chain_meme_trader_only", False):
                self._remember_pattern_quotes(quoted)
            return quoted
        finally:
            self._dex_quote_lock.release()

    async def solana_holder_shadow_once(self) -> None:
        cfg = self.config["sources"].get("solana_holder_shadow") or {}
        if not cfg.get("enabled", True):
            return
        self.store.enroll_solana_holder_shadow_cohorts()
        due = self.store.due_solana_holder_shadow()
        if due is None:
            return
        endpoint = "https://api.mainnet-beta.solana.com"
        rpc_host = "api.mainnet-beta.solana.com"
        allowed_programs = {
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
        }
        requested_at = utcnow()
        request_count = 0
        response_bytes = 0
        token_program = ""
        slot = None

        async def rpc(method: str, params: list[Any]) -> Any:
            nonlocal request_count, response_bytes
            request_count += 1
            response = await self.http.client.post(
                endpoint,
                json={"jsonrpc": "2.0", "id": request_count, "method": method, "params": params},
                headers={"Accept": "application/json"},
            )
            response_bytes += len(response.content)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("invalid_rpc_payload")
            error = payload.get("error")
            if isinstance(error, dict):
                raise RuntimeError(f"rpc_error_{error.get('code', 'unknown')}")
            return payload.get("result")

        values: dict[str, Any] = {}
        status = "observed"
        reason = "holder_aggregate_observed"
        try:
            mint = str(due["mint_address"])
            info = await rpc("getAccountInfo", [mint, {"encoding": "base64", "commitment": "confirmed"}])
            if not isinstance(info, dict) or not isinstance(info.get("value"), dict):
                raise RuntimeError("mint_account_missing")
            token_program = str(info["value"].get("owner") or "")
            if token_program not in allowed_programs:
                raise RuntimeError("unsupported_token_program")
            context = info.get("context") if isinstance(info.get("context"), dict) else {}
            slot = int(context.get("slot")) if context.get("slot") is not None else None
            consistency = {"commitment": "confirmed"}
            if slot is not None:
                consistency["minContextSlot"] = slot
            supply_result = await rpc("getTokenSupply", [mint, consistency])
            accounts_result = await rpc(
                "getProgramAccounts",
                [
                    token_program,
                    {
                        **consistency,
                        "encoding": "base64",
                        "withContext": True,
                        "filters": [{"memcmp": {"offset": 0, "bytes": mint}}],
                        "dataSlice": {"offset": 32, "length": 40},
                    },
                ],
            )
            if not isinstance(supply_result, dict) or not isinstance(supply_result.get("value"), dict):
                raise RuntimeError("invalid_supply_payload")
            if not isinstance(accounts_result, dict) or not isinstance(accounts_result.get("value"), list):
                raise RuntimeError("invalid_program_accounts_payload")
            supply = int(str(supply_result["value"].get("amount") or "0"))
            account_rows = accounts_result["value"]
            owners: dict[bytes, int] = {}
            nonzero_accounts = 0
            for row in account_rows:
                account = row.get("account") if isinstance(row, dict) else None
                data = account.get("data") if isinstance(account, dict) else None
                encoded = data[0] if isinstance(data, list) and data else None
                if not isinstance(encoded, str):
                    continue
                raw = base64.b64decode(encoded, validate=True)
                if len(raw) < 40:
                    continue
                amount = int.from_bytes(raw[32:40], "little")
                if amount <= 0:
                    continue
                nonzero_accounts += 1
                owner = raw[:32]
                owners[owner] = owners.get(owner, 0) + amount
            amounts = sorted(owners.values(), reverse=True)
            owner_sum = sum(amounts)
            dust_threshold = supply * 0.0001
            dust_count = sum(amount < dust_threshold for amount in amounts) if supply > 0 else 0
            account_context = (
                accounts_result.get("context")
                if isinstance(accounts_result.get("context"), dict) else {}
            )
            if account_context.get("slot") is not None:
                slot = max(int(account_context["slot"]), int(slot or 0))
            values = {
                "token_account_count": len(account_rows),
                "nonzero_token_account_count": nonzero_accounts,
                "unique_owner_count": len(owners),
                "supply_raw": supply,
                "owner_balance_sum_raw": owner_sum,
                "balance_coverage": round(owner_sum / supply, 8) if supply > 0 else None,
                "top1_supply_share": round((amounts[0] if amounts else 0) / supply, 8)
                if supply > 0 else None,
                "top10_supply_share": round(sum(amounts[:10]) / supply, 8)
                if supply > 0 else None,
                "owners_below_1bp_count": dust_count,
                "owners_below_1bp_rate": round(dust_count / len(owners), 8)
                if owners else None,
            }
        except httpx.HTTPStatusError as exc:
            status = "error"
            reason = f"http_status_{exc.response.status_code}"
        except httpx.TransportError as exc:
            status = "error"
            reason = type(exc).__name__
        except (RuntimeError, ValueError, TypeError, binascii.Error) as exc:
            reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
            status = "unavailable" if reason in {
                "mint_account_missing", "unsupported_token_program"
            } else "error"
        completed_at = utcnow()
        self.store.add_solana_holder_shadow_result(
            int(due["shadow_cohort_id"]),
            horizon_minutes=int(due["horizon_minutes"]),
            due_at=due["due_at"], requested_at=requested_at, completed_at=completed_at,
            status=status, reason_code=reason, rpc_host=rpc_host,
            token_program=token_program, slot=slot, rpc_request_count=request_count,
            latency_seconds=(completed_at - requested_at).total_seconds(),
            response_bytes=response_bytes, **values,
        )
        self.store.heartbeat("solana-holder-shadow", item=status == "observed")
        if status == "error":
            self._notify_source_error("solana-holder-shadow", RuntimeError(reason))

    def _record_paper_account_snapshot(self, *, force: bool = False) -> None:
        as_of = utcnow()
        latest_mark = self.store.latest_paper_account_snapshot_at()
        if not force and latest_mark and as_of - latest_mark < timedelta(minutes=5):
            return
        account = self.store.account()
        positions = self.store.open_positions()
        max_quote_age = float(self.config["paper"].get("max_quote_age_seconds", 45))
        marked_value = 0.0
        priced = 0
        quote_times = []
        for position in positions:
            snapshot = self.store.latest_snapshot(position.token_id, at_or_before=as_of)
            if (
                snapshot is None
                or snapshot.price_usd is None
                or (as_of - snapshot.observed_at).total_seconds() > max_quote_age
            ):
                continue
            marked_value += float(snapshot.price_usd) * position.quantity
            priced += 1
            quote_times.append(snapshot.observed_at)
        equity = account["cash_usd"] + marked_value if priced == len(positions) else None
        self.store.record_paper_account_snapshot(
            cash_usd=account["cash_usd"],
            marked_value_usd=marked_value,
            equity_usd=equity,
            daily_exposure_usd=self.store.daily_buy_gross_usd(),
            open_position_count=len(positions),
            priced_position_count=priced,
            quote_as_of=min(quote_times) if quote_times and priced == len(positions) else None,
        )

    def _paper_quote_rejections(self, expected_token_id: str, token, snapshot, received_at) -> list[str]:
        reasons = token_snapshot_temporal_rejections(
            token, snapshot, received_at, require_first_seen=False
        )
        expected_chain, separator, expected_address = str(expected_token_id).partition(":")
        same_identity = (
            bool(separator)
            and token.chain.lower() == expected_chain.lower()
            and canonical_token_address(token.chain, token.address)
            == canonical_token_address(expected_chain, expected_address)
        )
        if not same_identity:
            reasons.append("quote_token_mismatch")
        if snapshot.price_usd is None or float(snapshot.price_usd) <= 0:
            reasons.append("quote_price_unavailable")
        age_seconds = (parse_time(received_at) - parse_time(snapshot.observed_at)).total_seconds()
        if age_seconds > float(self.config["paper"].get("max_quote_age_seconds", 45)):
            reasons.append("quote_stale_at_execution")
        return list(dict.fromkeys(reasons))

    def _paper_fee_bps(self, snapshot: TokenSnapshot) -> float:
        paper = self.config["paper"]
        fixed_fee = float(paper.get("fixed_fee_usd_each_side", 0) or 0)
        fixed_notional = float(paper.get("fixed_position_usd", 0) or 0)
        if fixed_fee > 0 and fixed_notional > 0:
            return fixed_fee / fixed_notional * 10_000
        default_fee = float(paper.get("fee_bps", 60))
        raw = snapshot.raw if isinstance(snapshot.raw, dict) else {}
        pair = raw.get("pair") if isinstance(raw.get("pair"), dict) else {}
        dex_id = str(
            pair.get("dexId") or pair.get("dex_id") or raw.get("dexId") or ""
        ).lower()
        if snapshot.chain.lower() == "solana" and "pump" in dex_id:
            return max(default_fee, float(paper.get("pump_swap_fee_bps", 125)))
        return default_fee

    def _classify_observation(self, obs: Observation) -> Observation:
        if obs.role.lower() == "feature" and is_promotional_market_content(obs.title, obs.text):
            obs.role = "promotion"
            obs.raw = {**obs.raw, "non_event_market_promotion": True}
            return obs
        original_role = obs.role.lower()
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        source_item_state = str(raw.get("source_item_state") or "present").strip().lower()
        tracks_source_action = source_item_state in {"correction", "retracted"}
        if (
            obs.published_at is None
            or (original_role not in {"feature", "confirmation"} and not tracks_source_action)
        ):
            return obs
        max_age = float((self.config.get("events") or {}).get("max_source_age_minutes", 30))
        source_age = obs.observed_at - obs.published_at
        if obs.availability_proof in {"local_poll", "local_receive", "agent_search_verified"} and source_age > timedelta(minutes=max_age):
            if original_role in {"feature", "confirmation"}:
                obs.role = "identity"
            obs.raw = {
                **obs.raw,
                "original_role": original_role,
                "stale_first_observation": True,
                "source_age_minutes": round(source_age.total_seconds() / 60.0, 2),
            }
        elif source_age < timedelta(minutes=-5):
            obs.role = "identity"
            obs.raw = {**obs.raw, "original_role": original_role, "published_time_in_future": True}
        return obs

    async def ingest_observation(self, obs: Observation) -> dict[str, Any]:
        obs = self._classify_observation(obs)
        revision_handoff = ObservationRevisionHandoff()
        event_id, event_created, observation_created = self.events.ingest(
            obs, revision_handoff=revision_handoff
        )
        result = {
            "event_id": event_id,
            "event_created": event_created,
            "observation_created": observation_created,
            "decision_eligible": obs.role.lower() in {"feature", "confirmation"},
            "revision_id": revision_handoff.revision_id,
            "claim_relation_ids": list(revision_handoff.claim_relation_ids),
            "shadow_review": self.store.process_agent_shadow_review_inputs(
                revision_handoff.claim_relation_ids
            ),
        }
        self.store.heartbeat(obs.source, item=observation_created)
        if not observation_created:
            return result
        browser_item = obs.raw.get("browser") if isinstance(obs.raw, dict) else None
        if obs.availability_proof == "local_receive" and isinstance(browser_item, dict):
            observation_id = self.store.observation_id_for(obs)
            exact_url = _canonical_social_url(obs.url or obs.source_item_id)
            handoff_count = 0
            if observation_id is not None and exact_url:
                matched_tokens: set[str] = set()
                for link in self.store.recent_token_social_post_links(
                    minutes=int(
                        self.config["autonomous_search"].get("context_lookback_minutes", 180)
                    ),
                    chains=self.config.get("candidate", {}).get("chains", ("solana", "bsc")),
                ):
                    token_id = str(link["token_id"] or "")
                    if token_id in matched_tokens or not _same_social_url(
                        exact_url, str(link["normalized_url"] or "")
                    ):
                        continue
                    matched_tokens.add(token_id)
                    self.store.record_token_universe_funnel_transition(
                        token_id,
                        stage="context_trigger_evaluation",
                        status="eligible",
                        reason_code="browser_exact_token_metadata_post_captured",
                        evaluation_key=(
                            f"observation:{observation_id}:source_link:{int(link['id'])}:handoff"
                        ),
                        observed_at=obs.observed_at,
                        ingested_at=obs.ingested_at,
                        source_table="observations",
                        source_record_ids={
                            "observation_id": int(observation_id),
                            "source_link_id": int(link["id"]),
                        },
                        source_link_id=int(link["id"]),
                        observation_id=int(observation_id),
                        metadata={
                            "trigger_kind": "token_metadata_source_link",
                            "verification_status": "browser_exact_entity_observation",
                            "decision_eligible": False,
                        },
                    )
                    if self.store.requeue_token_detail_hydration(
                        token_id, enqueued_at=obs.observed_at
                    ):
                        handoff_count += 1
            result["token_context_handoff_count"] = handoff_count
            account = resolve_watchlist_account(
                browser_item, self.root / "data" / "web_console" / "console_settings.json"
            )
            if account is not None and observation_id is not None:
                self.store.record_browser_watch_observation(
                    account,
                    observation_id=observation_id,
                    event_id=event_id,
                    observed_at=obs.observed_at,
                    decision_eligible=obs.role.lower() in {"feature", "confirmation"},
                )
                address_groups = extract_addresses(
                    "\n".join((obs.title, obs.text, obs.url, obs.source_item_id))
                )
                result["kol_token_addressability_cohort_id"] = (
                    self.store.create_kol_token_addressability_cohort(
                        event_id,
                        observation_id,
                        account=account,
                        identifiers={
                            "solana": sorted(address_groups["solana"]),
                            "evm": sorted(address_groups["evm"]),
                        },
                    )
                )
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        if raw.get("agent_task") == "trend_scout" and raw.get("watch_account_exact_match") is True:
            observation_id = self.store.observation_id_for(obs)
            if observation_id is not None:
                self.store.record_attention_experiment_observation(
                    run_id=str(raw.get("trend_lane_run_id") or ""),
                    platform=str(raw.get("platform") or ""),
                    handle=str(raw.get("watch_account_handle") or ""),
                    entity_id=str(raw.get("source_entity_id") or ""),
                    observation_id=observation_id,
                    event_id=event_id,
                    decision_eligible=bool(result["decision_eligible"]),
                    observed_at=obs.observed_at,
                )
        event = self.store.get_event(event_id)
        self.store.set_kv(f"event_decision_next:{event_id}", None)
        self.store.set_kv(f"event_decision_attempt:{event_id}", 0)
        notify_cfg = self.config["notifications"]
        threshold = float(notify_cfg.get("minimum_event_attention", self.config.get("event_min_attention", 40)))
        is_official = obs.source_kind.lower() == "official_social"
        search_cfg = self.config["autonomous_search"]
        if search_cfg.get("enabled", False) and (
            is_official or event.attention >= float(search_cfg.get("trend_scout_surge_attention", 70))
        ):
            self.autonomous_search.mark_trend_surge()
        should_notify = bool(notify_cfg.get("notify_raw_events", False)) or is_official or event.attention >= threshold
        if not should_notify:
            return result
        key = f"event_notification_attention:{event.id}"
        previous = float(self.store.get_kv(key, -1.0))
        step = float(notify_cfg.get("event_attention_step", 15.0))
        if previous >= 0 and event.attention < previous + step:
            return result
        self.store.set_kv(key, event.attention)
        self.notifier.send(
            "event_detected" if previous < 0 else "event_attention_up",
            event.title,
            {
                "event_id": event.id,
                "attention": event.attention,
                "source": obs.source,
                "official": is_official,
                "new_cluster": event_created,
            },
        )
        return result

    async def browser_heartbeat(self, source: str, detail: dict[str, Any] | None = None) -> None:
        detail = detail if isinstance(detail, dict) else {}
        platform = str(detail.get("platform") or "").strip().lower()
        allowed_platforms = {
            "x", "truth", "bluesky", "reddit", "threads", "instagram", "tiktok", "youtube", "telegram"
        }
        if platform not in allowed_platforms:
            return
        if platform == "telegram":
            return
        self.store.heartbeat(f"browser:{source}")
        access_state = str(detail.get("access_state") or "unknown").strip().lower()
        access_state = {
            "content_visible": "accessible",
            "login_prompt": "login_required",
            "no_recent_items": "accessible",
        }.get(access_state, access_state)
        if access_state not in {"accessible", "authenticated", "login_required", "blocked", "unknown"}:
            access_state = "unknown"
        visible = detail.get("visible")
        visible = visible if isinstance(visible, bool) else None
        try:
            selector_count = max(0, min(100_000, int(detail.get("selector_count", 0))))
        except (TypeError, ValueError):
            selector_count = 0
        extension_version = str(detail.get("extension_version") or "").strip()
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}", extension_version):
            extension_version = ""
        page_url = ""
        try:
            parsed = urllib.parse.urlsplit(str(detail.get("page_url") or ""))
            if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
                page_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path[:1500], "", ""))
        except ValueError:
            pass
        self.store.set_kv(
            f"browser_platform_heartbeat:{platform}",
            {
                "platform": platform,
                "visible": visible,
                "selector_count": selector_count,
                "extension_version": extension_version or None,
                "page_url": page_url,
                "access_state": access_state,
                "observed_at": iso(),
                "contains_credentials": False,
            },
        )
        account = resolve_watchlist_heartbeat_account(
            {**detail, "platform": platform, "page_url": page_url},
            self.root / "data" / "web_console" / "console_settings.json",
        )
        if account is not None:
            self.store.record_browser_watch_heartbeat(
                account,
                access_state=access_state,
                visible=visible,
                selector_count=selector_count,
            )

    async def ingest_token(self, token: TokenCandidate) -> bool:
        self.store.record_token_launch_fact(token)
        token_created = self.store.upsert_token(token)
        discovery_cfg = self.config["sources"].get("dexscreener_discovery") or {}
        hydration_chains = {
            str(chain).lower()
            for chain in [
                *self.config["candidate"].get("chains", []),
                *discovery_cfg.get("chains", []),
                *((self.config["sources"].get("multichain_meme_data") or {}).get("chains", [])
                  if self.chain_meme_trader_only else []),
            ]
        }
        if token.chain.lower() in hydration_chains:
            self.store.enqueue_token_detail_hydration(token.chain, token.address)
        self.store.heartbeat(token.source or "onchain", item=token_created)
        if token_created and self.config["notifications"].get("notify_new_tokens", False):
            self.notifier.send(
                "token_new",
                f"{token.symbol or token.name} on {token.chain}",
                {"token_id": token.token_id, "source": token.source},
            )
        return token_created

    def _rss_collectors(self) -> list[RSSCollector]:
        result: list[RSSCollector] = []
        seen_urls: set[str] = set()
        items = [
            *self.config["sources"].get("rss", []),
            *self.autonomous_search.active_rss_sources(),
        ]
        for item in items:
            url = str(item.get("url") or "").strip()
            normalized = url.rstrip("/")
            if not item.get("enabled", True) or not url or normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            result.append(
                RSSCollector(
                    self.http,
                    str(item.get("name") or url),
                    url,
                    str(item.get("source_kind") or ("news" if item.get("kind") == "rss" else item.get("kind")) or "news"),
                )
            )
        return result

    def _bluesky_collectors(self) -> list[BlueskySearchCollector]:
        return [BlueskySearchCollector(self.http, str(query)) for query in self.config["sources"].get("bluesky_queries", []) if str(query).strip()]

    def _mastodon_collectors(self) -> list[MastodonCollector]:
        return [
            MastodonCollector(self.http, str(item.get("name") or item["url"]), str(item["url"]))
            for item in self.config["sources"].get("mastodon", []) if item.get("enabled", True) and item.get("url")
        ]

    def _notify_source_error(self, source: str, exc: Exception) -> None:
        now = utcnow()
        cooldown = float(self.config["notifications"].get("source_error_cooldown_minutes", 30))
        key = f"source_error_alert:{source}"
        previous = self.store.get_kv(key)
        self.store.heartbeat(source, error=f"{type(exc).__name__}: {exc}"[:500])
        if previous and now - parse_time(previous) < timedelta(minutes=cooldown):
            return
        self.store.set_kv(key, iso(now))
        self.notifier.send(
            "source_error",
            source,
            {"error": type(exc).__name__, "detail": str(exc)[:500]},
        )

    @staticmethod
    def _source_poll_identity(collector: Any) -> tuple[str, str, str]:
        url = str(getattr(collector, "url", "") or "").strip()
        query = str(getattr(collector, "query", "") or "").strip()
        class_name = type(collector).__name__.lower()
        if query and not url:
            digest = hashlib.sha256(query.encode("utf-8", errors="ignore")).hexdigest()[:16]
            return "bluesky", f"bluesky-query:{digest}", "bluesky"
        kind = "mastodon" if "mastodon" in class_name else "rss"
        platform = "mastodon" if kind == "mastodon" else "rss_news"
        if url:
            parsed = urllib.parse.urlsplit(url)
            safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            host = (parsed.hostname or "unknown").lower()
            digest = hashlib.sha256(safe_url.encode("utf-8", errors="ignore")).hexdigest()[:12]
            return kind, f"{kind}:{host}:{digest}", platform
        name = str(getattr(collector, "name", type(collector).__name__)).strip()
        return kind, f"{kind}:{name}", platform

    async def _poll_observation_collector(self, collector: Any) -> None:
        name = str(getattr(collector, "name", getattr(collector, "query", type(collector).__name__)))
        url = str(getattr(collector, "url", "") or "")
        collector_kind, source_key, platform = self._source_poll_identity(collector)
        attempt_id = self.store.start_source_poll_attempt(
            collector_kind=collector_kind,
            source_key=source_key,
            platform=platform,
        )
        try:
            observations = await collector.poll()
            self.store.heartbeat(name, item=bool(observations))
            if url:
                self.autonomous_search.record_rss_poll(url, ok=True)
                pause_reason = self.autonomous_search.review_discovered_rss_content(url, observations)
                if pause_reason:
                    self.notifier.send(
                        "autonomous_source_paused",
                        name,
                        {"url": url, "reason": pause_reason},
                    )
                    self.store.finish_source_poll_attempt(
                        attempt_id,
                        status="quality_paused",
                        fetched_count=len(observations),
                        filtered_count=len(observations),
                    )
                    return
            new_observations = 0
            new_events = 0
            eligible = 0
            context_only = 0
            duplicates = 0
            for obs in observations:
                result = await self.ingest_observation(obs)
                new_observations += int(bool(result["observation_created"]))
                new_events += int(bool(result["event_created"]))
                duplicates += int(not result["observation_created"])
                eligible += int(bool(result["decision_eligible"]))
                context_only += int(not result["decision_eligible"])
            self.store.finish_source_poll_attempt(
                attempt_id,
                status="completed",
                fetched_count=len(observations),
                new_observation_count=new_observations,
                new_event_count=new_events,
                decision_eligible_count=eligible,
                context_only_count=context_only,
                duplicate_count=duplicates,
            )
        except Exception as exc:
            self.store.finish_source_poll_attempt(
                attempt_id,
                status="error",
                error_type=type(exc).__name__,
            )
            paused = self.autonomous_search.record_rss_poll(
                url,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            ) if url else False
            if paused:
                self.notifier.send(
                    "autonomous_source_paused",
                    name,
                    {"url": url, "reason": "consecutive_poll_failures"},
                )
            self._notify_source_error(name, exc)

    async def _poll_gecko_network(self, network: str) -> None:
        name = f"geckoterminal:{network}"
        round_id = self.store.start_token_discovery_round(
            provider="geckoterminal",
            surface="new_pools",
            mode="poll",
            chain_scope=str(network),
        )
        try:
            tokens = await GeckoNewPoolsCollector(self.http, network).poll()
            self.store.heartbeat(name, item=bool(tokens))
            duplicates = 0
            for token in tokens:
                known_before = self.store.token_discovery_known(token.token_id)
                created = await self.ingest_token(token)
                first_local = not known_before and created
                duplicates += int(not first_local)
                self.store.add_token_discovery_exposure(
                    round_id,
                    token_id=token.token_id,
                    chain=token.chain,
                    role="new_pool",
                    first_local_discovery=first_local,
                    new_token=created,
                    observed_at=token.first_seen_at,
                )
            self.store.finish_token_discovery_round(
                round_id,
                status="completed",
                requested_count=1,
                returned_count=len(tokens),
                duplicate_token_count=duplicates,
            )
        except Exception as exc:
            self.store.finish_token_discovery_round(
                round_id,
                status="error",
                requested_count=1,
                error_type=type(exc).__name__,
            )
            self._notify_source_error(name, exc)

    def _recent_token_context_source_keys(self, *, limit: int = 240) -> set[str]:
        rows = self.store.db.execute(
            "SELECT assessment_json FROM token_context_assessments ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        keys: set[str] = set()
        for row in rows:
            try:
                assessment = json.loads(row["assessment_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            key = self.autonomous_search.token_context_source_key(
                assessment.get("investigation_trigger")
                if isinstance(assessment, dict) else None
            )
            if key:
                keys.add(key)
        return keys

    def _source_fair_context_order(
        self,
        candidates: list[tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]],
        recent_source_keys: set[str],
    ) -> list[tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]]:
        ordered = sorted(
            candidates,
            key=lambda item: (item[0], item[2].observed_at),
            reverse=True,
        )
        unseen: list[tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]] = []
        seen_once: list[tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]] = []
        same_cycle_duplicates: list[
            tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]
        ] = []
        cycle_keys: set[str] = set()
        for candidate in ordered:
            key = self.autonomous_search.token_context_source_key(candidate[4])
            if key and key in cycle_keys:
                same_cycle_duplicates.append(candidate)
                continue
            if key:
                cycle_keys.add(key)
            if key and key not in recent_source_keys:
                unseen.append(candidate)
            else:
                seen_once.append(candidate)
        return [*unseen, *seen_once, *same_cycle_duplicates]

    async def poll_dexscreener_discovery_once(self) -> None:
        cfg = self.config["sources"].get("dexscreener_discovery") or {}
        if not cfg.get("enabled", True):
            return
        candidate_chains = {
            str(chain).lower() for chain in self.config["candidate"].get("chains", [])
        }
        if self.chain_meme_trader_only:
            candidate_chains = {"solana"}
        surface_chains = {
            *candidate_chains,
            *(str(chain).lower() for chain in cfg.get("surface_chains", [])),
        }
        if self.chain_meme_trader_only:
            surface_chains = {
                str(chain).lower()
                for chain in (
                    self.config["sources"].get("multichain_meme_data") or {}
                ).get("chains", ["solana"])
            }
        max_items = int(cfg.get("max_items_per_surface", 40))
        max_hydrations = int(cfg.get("max_hydrations_per_cycle", 180))
        direct_context_candidates: list[tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]] = []
        onchain_context_candidates: list[
            tuple[int, TokenCandidate, TokenSnapshot, float, dict[str, Any]]
        ] = []
        for surface in self.dex.DISCOVERY_SURFACES:
            await self._chain_meme_active_idle().wait()
            source = f"dexscreener:{surface}"
            round_id = self.store.start_token_discovery_round(
                provider="dexscreener",
                surface=str(surface),
                mode="poll",
                chain_scope=",".join(sorted(surface_chains)),
            )
            try:
                links = await self.dex.discover_surface(surface, surface_chains, limit=max_items)
            except Exception as exc:
                self.store.finish_token_discovery_round(
                    round_id,
                    status="error",
                    requested_count=1,
                    error_type=type(exc).__name__,
                )
                self._notify_source_error(source, exc)
                continue
            self.store.heartbeat(source, item=bool(links))
            by_token: dict[str, list[dict[str, Any]]] = {}
            for link in links:
                token_id = str(link.get("token_id") or "")
                chain = str(link.get("chain") or "").lower()
                address = str(link.get("address") or "")
                if not token_id or chain not in surface_chains or not address:
                    continue
                by_token.setdefault(token_id, []).append(link)
            first_discoveries = 0
            for token_id, token_links in by_token.items():
                known_before = self.store.token_discovery_known(token_id)
                new_links = 0
                source_link_fingerprints: list[str] = []
                for link in token_links:
                    fingerprint, created = self.store.upsert_token_source_link(link)
                    source_link_fingerprints.append(fingerprint)
                    new_links += int(created)
                    self.store.enqueue_token_detail_hydration(
                        str(link.get("chain") or ""), str(link.get("address") or "")
                    )
                first_local = not known_before and new_links > 0
                first_discoveries += int(first_local)
                exposure_id = self.store.add_token_discovery_exposure(
                    round_id,
                    token_id=token_id,
                    chain=str(token_links[0].get("chain") or ""),
                    role=str(token_links[0].get("role") or "identity"),
                    first_local_discovery=first_local,
                    source_link_count=len(token_links),
                    new_source_link_count=new_links,
                )
                if exposure_id is not None:
                    self.store.link_token_discovery_exposure_source_links(
                        exposure_id, source_link_fingerprints
                    )
            self.store.finish_token_discovery_round(
                round_id,
                status="completed",
                requested_count=1,
                returned_count=len(links),
                duplicate_token_count=max(0, len(by_token) - first_discoveries),
            )

        due = self.store.due_token_detail_hydrations(
            limit=max_hydrations,
            chains=tuple(sorted(surface_chains)) if self.chain_meme_trader_only else (),
            prefer_fresh=self.chain_meme_trader_only,
            priority_social_account_urls=(
                () if self.chain_meme_trader_only else (
                    str(account.get("url") or "")
                    for account in self.autonomous_search._configured_high_impact_accounts()
                )
            ),
        )
        if not due:
            return
        by_chain: dict[str, list[Any]] = {}
        for row in due:
            by_chain.setdefault(str(row["chain"]), []).append(row)
        for chain, rows in by_chain.items():
            for offset in range(0, len(rows), 30):
                chunk = rows[offset : offset + 30]
                round_id = self.store.start_token_discovery_round(
                    provider="dexscreener",
                    surface="hydration",
                    mode="batch_quote",
                    chain_scope=str(chain),
                )
                hydration_started_at = utcnow()
                for row in chunk:
                    token_id = str(row["token_id"])
                    self.store.record_token_universe_funnel_transition(
                        token_id,
                        stage="metadata_hydration_attempt",
                        status="attempted",
                        reason_code="due_detail_hydration",
                        evaluation_key=f"round:{round_id}:attempt",
                        observed_at=hydration_started_at,
                        ingested_at=hydration_started_at,
                        source_table="token_discovery_rounds",
                        source_record_ids={"round_id": round_id},
                        round_id=round_id,
                        metadata={"provider": "dexscreener", "chain": str(chain)},
                    )
                try:
                    if hasattr(self.dex, "batch_quote"):
                        quoted_by_token = await self._dex_batch_quote(
                            chain, [str(row["address"]) for row in chunk]
                        )
                    else:
                        quoted_by_token = {}
                        for row in chunk:
                            quoted = await self.dex.quote(chain, str(row["address"]))
                            if quoted:
                                quoted_by_token[quoted[0].token_id] = quoted
                except Exception as exc:
                    self.store.finish_token_discovery_round(
                        round_id,
                        status="error",
                        requested_count=len(chunk),
                        error_type=type(exc).__name__,
                    )
                    self._notify_source_error("dexscreener:hydration", exc)
                    for row in chunk:
                        token_id = str(row["token_id"])
                        self.store.mark_token_detail_hydration(
                            token_id, "error", error=f"{type(exc).__name__}: {exc}"
                        )
                        failed_at = utcnow()
                        self.store.record_token_universe_funnel_transition(
                            token_id,
                            stage="metadata_hydration_result",
                            status="error",
                            reason_code=type(exc).__name__,
                            evaluation_key=f"round:{round_id}:result",
                            observed_at=failed_at,
                            ingested_at=failed_at,
                            source_table="token_discovery_rounds",
                            source_record_ids={"round_id": round_id},
                            round_id=round_id,
                            metadata={"provider": "dexscreener", "chain": str(chain)},
                        )
                    continue
                self.store.heartbeat("dexscreener:hydration", item=bool(quoted_by_token))
                for row in chunk:
                    token_id = str(row["token_id"])
                    quoted = quoted_by_token.get(token_id)
                    if not quoted:
                        self.store.mark_token_detail_hydration(token_id, "no_pair")
                        self.store.add_token_discovery_exposure(
                            round_id,
                            token_id=token_id,
                            chain=chain,
                            role="hydration",
                            no_pair=True,
                        )
                        completed_at = utcnow()
                        self.store.record_token_universe_funnel_transition(
                            token_id,
                            stage="metadata_hydration_result",
                            status="no_pair",
                            reason_code="quote_returned_no_pair",
                            evaluation_key=f"round:{round_id}:result",
                            observed_at=completed_at,
                            ingested_at=completed_at,
                            source_table="token_discovery_rounds",
                            source_record_ids={"round_id": round_id},
                            round_id=round_id,
                            metadata={"provider": "dexscreener", "chain": str(chain)},
                        )
                        continue
                    token, snapshot = quoted
                    if token.token_id != token_id:
                        self.store.mark_token_detail_hydration(token_id, "no_pair")
                        self.store.add_token_discovery_exposure(
                            round_id,
                            token_id=token_id,
                            chain=chain,
                            role="hydration",
                            no_pair=True,
                        )
                        completed_at = utcnow()
                        self.store.record_token_universe_funnel_transition(
                            token_id,
                            stage="metadata_hydration_result",
                            status="no_pair",
                            reason_code="quote_token_mismatch",
                            evaluation_key=f"round:{round_id}:result",
                            observed_at=completed_at,
                            ingested_at=completed_at,
                            source_table="token_discovery_rounds",
                            source_record_ids={"round_id": round_id},
                            round_id=round_id,
                            metadata={"provider": "dexscreener", "chain": str(chain)},
                        )
                        continue
                    momentum = CandidateEvaluator._momentum_score(snapshot)
                    required_liquidity = max(
                        float(self.config["safety"].get("min_liquidity_usd", 12_000)),
                        float(self.config["paper"].get("max_position_usd", 35))
                        / max(
                            0.000001,
                            float(self.config["paper"].get("max_liquidity_impact_pct", 0.0025)),
                        ),
                    )
                    is_candidate_chain = snapshot.chain.lower() in candidate_chains
                    if (
                        is_candidate_chain
                        and snapshot.chain.lower() in {"ethereum", "eth", "bsc", "base"}
                        and momentum >= float(
                            self.config["autonomous_search"].get("context_min_momentum_score", 75)
                        )
                        and snapshot.liquidity_usd is not None
                        and float(snapshot.liquidity_usd) >= required_liquidity
                    ):
                        snapshot = await self.safety.enrich_evm_execution_fields(snapshot)
                    created = self.store.upsert_token(token, seen_at=snapshot.observed_at)
                    snapshot_id = self.store.add_snapshot(snapshot)
                    self.store.mark_token_detail_hydration(token_id, "hydrated")
                    self.store.add_token_discovery_exposure(
                        round_id,
                        token_id=token_id,
                        chain=chain,
                        role="hydration",
                        new_token=created,
                        snapshot_count=1,
                        observed_at=snapshot.observed_at,
                    )
                    completed_at = utcnow()
                    self.store.record_token_universe_funnel_transition(
                        token_id,
                        stage="metadata_hydration_result",
                        status="hydrated",
                        reason_code="snapshot_persisted",
                        evaluation_key=f"round:{round_id}:result",
                        observed_at=snapshot.observed_at,
                        ingested_at=completed_at,
                        source_table="token_snapshots",
                        source_record_ids={"round_id": round_id, "snapshot_id": snapshot_id},
                        round_id=round_id,
                        snapshot_id=snapshot_id,
                        metadata={
                            "provider": "dexscreener",
                            "chain": str(chain),
                            "scope": "candidate" if is_candidate_chain else "research_only",
                            "source_link_count": len(
                                self.store.token_source_links(token_id, limit=100)
                            ),
                        },
                    )
                    if not is_candidate_chain:
                        continue
                    trigger = self.autonomous_search.resolve_token_context_trigger(
                        token,
                        momentum_score=momentum,
                        snapshot_observed_at=snapshot.observed_at,
                        snapshot_id=snapshot_id,
                    )
                    if trigger:
                        candidate = (
                            int(trigger.get("priority") or 0), token, snapshot, momentum, trigger
                        )
                        if str(trigger.get("kind") or "") == "onchain_momentum":
                            onchain_context_candidates.append(candidate)
                        else:
                            direct_context_candidates.append(candidate)
                self.store.finish_token_discovery_round(
                    round_id,
                    status="completed",
                    requested_count=len(chunk),
                    returned_count=len(quoted_by_token),
                    duplicate_token_count=max(0, len(chunk) - len(quoted_by_token)),
                )

        critical_kinds = {"high_impact_account_post", "fresh_high_attention_event_relation"}
        recent_source_keys = self._recent_token_context_source_keys()
        critical = self._source_fair_context_order(
            [
                item for item in direct_context_candidates
                if item[0] >= 2 and str(item[4].get("kind") or "") in critical_kinds
            ],
            recent_source_keys,
        )
        metadata_leads = self._source_fair_context_order(
            [
                item for item in direct_context_candidates
                if item[0] >= 2 and str(item[4].get("kind") or "") not in critical_kinds
            ],
            recent_source_keys,
        )
        high_impact = [*critical, *metadata_leads][
            : self.MAX_DIRECT_HIGH_IMPACT_CONTEXT_PER_CYCLE
        ]
        critical = [
            item for item in high_impact
            if str(item[4].get("kind") or "") in critical_kinds
        ]
        metadata_leads = [item for item in high_impact if item not in critical]
        ordinary = [item for item in direct_context_candidates if item[0] < 2]
        exact_ordinary = self._source_fair_context_order(
            [
                item for item in ordinary
                if str(item[4].get("verification_status") or "")
                == "browser_exact_entity_observation"
                and item[4].get("observation_id") is not None
            ],
            recent_source_keys,
        )
        other_ordinary = [item for item in ordinary if item not in exact_ordinary]
        selected_exact_ordinary = exact_ordinary[
            : self.MAX_DIRECT_BROWSER_EXACT_CONTEXT_PER_CYCLE
        ]
        for candidate in selected_exact_ordinary:
            candidate[4]["selection_path"] = "hydration_browser_exact_post"
        for _, token, _, _, _ in exact_ordinary[
            self.MAX_DIRECT_BROWSER_EXACT_CONTEXT_PER_CYCLE :
        ]:
            self.store.requeue_token_detail_hydration(token.token_id, enqueued_at=utcnow())
        selected_onchain = sorted(
            onchain_context_candidates,
            key=lambda item: (item[3], item[2].observed_at),
            reverse=True,
        )[: self.MAX_DIRECT_ONCHAIN_CONTEXT_PER_CYCLE]
        lane_version = self.store.TOKEN_CONTEXT_ONCHAIN_ADMISSION_CHALLENGER_VERSION
        for candidate in selected_onchain:
            candidate[4]["selection_path"] = "hydration_onchain_challenger"
            candidate[4]["challenger_version"] = lane_version
            candidate[4]["lane_scheduler_version"] = lane_version
        selected_context_candidates = list(critical)
        if metadata_leads and selected_onchain:
            cursor = int(self.store.get_kv(self.DIRECT_CONTEXT_LANE_CURSOR_KEY, 0) or 0)
            onchain_first = cursor % 2 == 1
            first, second = (
                (selected_onchain, metadata_leads)
                if onchain_first else (metadata_leads, selected_onchain)
            )
            lane_preference = "onchain_first" if onchain_first else "metadata_lead_first"
            for candidate in [*metadata_leads, *selected_onchain]:
                candidate[4]["lane_scheduler_version"] = lane_version
                candidate[4]["lane_preference"] = lane_preference
            selected_context_candidates.extend(first)
            selected_context_candidates.extend(second)
            self.store.set_kv(self.DIRECT_CONTEXT_LANE_CURSOR_KEY, cursor + 1)
        else:
            selected_context_candidates.extend(metadata_leads)
            selected_context_candidates.extend(selected_onchain)
        selected_context_candidates.extend(selected_exact_ordinary)
        if other_ordinary:
            selected_context_candidates.append(
                max(
                    other_ordinary,
                    key=lambda item: (item[0], item[2].observed_at),
                )
            )
        seen_context_tokens: set[str] = set()
        for _, token, snapshot, momentum, trigger in selected_context_candidates:
            if token.token_id in seen_context_tokens:
                continue
            seen_context_tokens.add(token.token_id)
            await self._investigate_token_context(
                token,
                snapshot,
                momentum_score=momentum,
                event_relation=trigger,
            )

    async def poll_multichain_meme_data_once(self) -> None:
        """Collect shared Solana/BSC/Robinhood discovery without legacy feeds or Agents."""
        cfg = self.config["sources"].get("multichain_meme_data") or {}
        chains = tuple(
            dict.fromkeys(
                str(chain).strip().lower()
                for chain in cfg.get("chains", [])
                if str(chain).strip()
            )
        )
        await asyncio.gather(*(self._poll_gecko_network(chain) for chain in chains))
        await self.poll_dexscreener_discovery_once()
        self.store.heartbeat("multichain_meme_data")

    async def poll_external_once(self) -> None:
        collectors = [*self._rss_collectors(), *self._bluesky_collectors(), *self._mastodon_collectors()]
        tasks = [self._poll_observation_collector(collector) for collector in collectors]
        tasks.extend(
            self._poll_gecko_network(str(network))
            for network in self.config["sources"].get("gecko_networks", [])
        )
        if tasks:
            await asyncio.gather(*tasks)

    async def discover_sources_once(self, *, force: bool = False) -> dict[str, Any]:
        if self.strategy_focus_active:
            return {"status": "paused", "reason": "strategy_focus_sol_onchain_primary"}
        result = await self.autonomous_search.discover_sources(force=force)
        accepted = result.get("accepted") or []
        if result.get("status") == "completed":
            self.store.heartbeat("autonomous-source-discovery", item=bool(accepted))
        if accepted:
            self.notifier.send(
                "autonomous_sources_added",
                f"added {len(accepted)} public feeds",
                {
                    "sources": [
                        {"name": row.get("name"), "url": row.get("url"), "topic": row.get("topic")}
                        for row in accepted
                    ],
                    "usage": self.autonomous_search.usage(),
                },
            )
        elif result.get("status") == "agent_error":
            self._notify_source_error("autonomous-source-discovery", RuntimeError(str(result.get("error") or "agent error")))
        return result

    async def _autonomous_source_loop(self) -> None:
        cfg = self.config["autonomous_search"]
        if not cfg.get("enabled", False):
            return
        delay = max(0.0, float(cfg.get("startup_delay_seconds", 120)))
        if delay:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except TimeoutError:
                pass
        interval = max(300.0, float(cfg.get("source_discovery_check_minutes", 60)) * 60.0)
        await self._periodic("autonomous_source_discovery", interval, self.discover_sources_once)

    async def scout_trends_once(self, *, force: bool = False) -> dict[str, Any]:
        if self.strategy_focus_active:
            return {"status": "paused", "reason": "strategy_focus_sol_onchain_primary"}
        result, observations = await self.autonomous_search.scout_trends(force=force)
        lane_selection = result.get("lane_selection") if isinstance(result, dict) else None
        run_id = str((lane_selection or {}).get("run_id") or "") if isinstance(lane_selection, dict) else ""
        if result.get("status") == "completed":
            self.store.heartbeat("autonomous-trend-scout", item=bool(observations))
        try:
            for observation in observations:
                await self.ingest_observation(observation)
        except Exception:
            if run_id:
                self.store.finalize_trend_lane_observation_ingestion(run_id, status="error")
            raise
        else:
            if run_id and result.get("status") == "completed":
                self.store.finalize_trend_lane_observation_ingestion(run_id, status="completed")
        if observations:
            self.notifier.send(
                "autonomous_trends_found",
                f"verified {len(result.get('events') or [])} current meme-capable events",
                {
                    "events": result.get("events") or [],
                    "observation_count": len(observations),
                    "usage": self.autonomous_search.usage(),
                    "next_interval_minutes": result.get("next_interval_minutes"),
                },
            )
        elif result.get("status") == "agent_error":
            self._notify_source_error(
                "autonomous-trend-scout",
                RuntimeError(str(result.get("error") or "agent error")),
            )
        return result

    async def _autonomous_trend_loop(self) -> None:
        cfg = self.config["autonomous_search"]
        if not cfg.get("enabled", False) or not cfg.get("trend_scout_enabled", True):
            return
        delay = max(0.0, float(cfg.get("trend_scout_startup_delay_seconds", 45)))
        if delay:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except TimeoutError:
                pass
        interval = max(10.0, float(cfg.get("trend_scout_check_seconds", 30)))
        await self._periodic("autonomous_trend_scout", interval, self.scout_trends_once)

    async def _investigate_token_context(
        self,
        token: TokenCandidate,
        snapshot: TokenSnapshot,
        *,
        momentum_score: float,
        event_relation: dict[str, Any] | None = None,
        retry_lane: bool = False,
        allow_postbuy_research_in_focus: bool = False,
    ) -> None:
        if self.strategy_focus_active and not allow_postbuy_research_in_focus:
            return
        observations = await self.autonomous_search.search_token_context(
            token,
            snapshot,
            momentum_score=momentum_score,
            event_relation=event_relation,
            retry_lane=retry_lane,
        )
        for observation in observations:
            await self.ingest_observation(observation)
        if observations:
            self.store.heartbeat("autonomous-context-search", item=True)
            self.notifier.send(
                "autonomous_context_found",
                token.name or token.symbol or token.token_id,
                {
                    "token_id": token.token_id,
                    "sources": [row.url for row in observations],
                    "usage": self.autonomous_search.usage(),
                },
            )

    async def reverse_news_once(self) -> None:
        cfg = self.config["sources"].get("reverse_google_news") or {}
        if not cfg.get("enabled", True):
            return
        if not self._dex_quote_low_priority_available():
            return
        max_queries = int(cfg.get("queries_per_cycle", 3))
        max_scanned = int(cfg.get("max_tokens_scanned_per_cycle", 10))
        candidate_pool_limit = int(cfg.get("candidate_pool_limit", 300))
        probe_cooldown = int(cfg.get("probe_cooldown_seconds", 120))
        cooldown = int(cfg.get("cooldown_minutes", 15))
        min_liquidity = float(cfg.get("min_liquidity_usd", 5_000))
        min_volume = float(cfg.get("min_volume_5m_usd", 1_000))
        min_transactions = int(cfg.get("min_5m_transactions", 12))
        min_buy_ratio = float(cfg.get("min_buy_ratio", 0.55))
        max_results = max(1, int(cfg.get("max_results_per_query", 8)))
        max_result_age = timedelta(minutes=float(cfg.get("max_result_age_minutes", 180)))
        now = utcnow()
        ranked: list[tuple[int, float, TokenCandidate, dict[str, Any] | None]] = []
        pending_ranked: list[tuple[Any, float, TokenCandidate, dict[str, Any]]] = []
        source_priority = {"pumpportal:migration": 4, "geckoterminal": 3, "dexscreener": 2, "pumpportal": 1}
        pending = self.store.pending_event_lookup_tokens(
            self.config.get("candidate", {}).get("chains", []),
            minutes=180,
            as_of=now,
            limit=candidate_pool_limit,
        )
        screened_pending: list[dict[str, Any]] = []
        for item in pending:
            token = item["token"]
            query = " ".join(part for part in [token.name, token.symbol] if part).strip()
            searchable = len(query) >= 3 and is_context_searchable_token_name(
                token.name or token.symbol
            )
            self.store.record_token_event_lookup_name_screen(
                int(item["cohort_id"]),
                int(item["eligible_transition_id"]),
                searchable=searchable,
                evaluated_at=now,
            )
            if searchable:
                screened_pending.append(item)
        pending = screened_pending
        pending_by_token = {item["token"].token_id: item for item in pending}
        recent_tokens = self.store.recent_tokens(minutes=180, limit=candidate_pool_limit)
        recent_tokens.sort(
            key=lambda token: (
                max((value for prefix, value in source_priority.items() if token.source.startswith(prefix)), default=0),
                token.first_seen_at or now,
            ),
            reverse=True,
        )
        tokens = [item["token"] for item in pending]
        tokens.extend(token for token in recent_tokens if token.token_id not in pending_by_token)
        probe_candidates: list[TokenCandidate] = []
        pending_probes = 0
        pending_probe_limit = min(max_scanned, max_queries)
        for token in tokens:
            if len(probe_candidates) >= max_scanned:
                break
            is_pending = token.token_id in pending_by_token
            if is_pending and pending_probes >= pending_probe_limit:
                continue
            query = " ".join(part for part in [token.name, token.symbol] if part).strip()
            if len(query) < 3 or not is_context_searchable_token_name(token.name or token.symbol):
                continue
            key = f"reverse_news:{token.token_id}"
            last = self.store.get_kv(key)
            if last and now - parse_time(last) < timedelta(minutes=cooldown):
                continue
            probe_key = f"reverse_probe:{token.token_id}"
            last_probe = self.store.get_kv(probe_key)
            if last_probe and now - parse_time(last_probe) < timedelta(seconds=probe_cooldown):
                continue
            self.store.set_kv(probe_key, iso(now))
            probe_candidates.append(token)
            pending_probes += int(is_pending)

        quoted_by_token: dict[str, tuple[TokenCandidate, TokenSnapshot]] = {}
        if hasattr(self.dex, "batch_quote"):
            by_chain: dict[str, list[TokenCandidate]] = {}
            for token in probe_candidates:
                by_chain.setdefault(token.chain, []).append(token)
            for chain, chain_tokens in by_chain.items():
                requested_at = utcnow()
                round_id = self.store.start_token_discovery_round(
                    provider="dexscreener",
                    surface="reverse_context_probe",
                    mode="batch_quote",
                    chain_scope=chain,
                    started_at=requested_at,
                )
                attempt_ids = self.store.start_token_discovery_quote_attempts(
                    round_id,
                    [
                        {
                            "token_id": token.token_id,
                            "chain": token.chain,
                            "role": "reverse_context_probe",
                            "queue_due_at": requested_at,
                        }
                        for token in chain_tokens
                    ],
                    requested_at=requested_at,
                )
                try:
                    batch = await self._dex_batch_quote(
                        chain, [token.address for token in chain_tokens]
                    )
                    quoted_by_token.update(batch)
                    completed_at = utcnow()
                    for token in chain_tokens:
                        attempt_id = attempt_ids.get(
                            (token.token_id, "reverse_context_probe")
                        )
                        if attempt_id is not None:
                            found = token.token_id in batch
                            self.store.finish_token_discovery_quote_attempt(
                                attempt_id,
                                status="success" if found else "no_pair",
                                reason_code=(
                                    "batch_quote_returned_token"
                                    if found else "batch_quote_missing_token"
                                ),
                                completed_at=completed_at,
                            )
                    self.store.finish_token_discovery_round(
                        round_id,
                        status="completed",
                        requested_count=len(chain_tokens),
                        returned_count=len(batch),
                        completed_at=completed_at,
                    )
                except Exception as exc:
                    completed_at = utcnow()
                    for attempt_id in attempt_ids.values():
                        self.store.finish_token_discovery_quote_attempt(
                            attempt_id,
                            status="error",
                            reason_code="batch_request_failed",
                            error_type=type(exc).__name__,
                            completed_at=completed_at,
                        )
                    self.store.finish_token_discovery_round(
                        round_id,
                        status="error",
                        requested_count=len(chain_tokens),
                        error_type=type(exc).__name__,
                        completed_at=completed_at,
                    )
                    self._notify_source_error(f"reverse-quote:{chain}", exc)
        else:
            for token in probe_candidates:
                try:
                    quoted = await self.dex.quote(token.chain, token.address)
                except Exception as exc:
                    self._notify_source_error(f"reverse-quote:{token.token_id}", exc)
                    continue
                if quoted:
                    quoted_by_token[token.token_id] = quoted

        for token in probe_candidates:
            quoted = quoted_by_token.get(token.token_id)
            if not quoted:
                continue
            quoted_token, snap = quoted
            transactions = (snap.buys_5m or 0) + (snap.sells_5m or 0)
            buy_ratio = (snap.buys_5m or 0) / transactions if transactions else 0.0
            momentum = CandidateEvaluator._momentum_score(snap)
            required_liquidity = max(
                float(self.config["safety"].get("min_liquidity_usd", 12_000)),
                float(self.config["paper"].get("max_position_usd", 35))
                / max(
                    0.000001,
                    float(self.config["paper"].get("max_liquidity_impact_pct", 0.0025)),
                ),
            )
            if (
                snap.chain.lower() in {"ethereum", "eth", "bsc", "base"}
                and momentum >= float(
                    self.config["autonomous_search"].get("context_min_momentum_score", 75)
                )
                and snap.liquidity_usd is not None
                and float(snap.liquidity_usd) >= required_liquidity
            ):
                snap = await self.safety.enrich_evm_execution_fields(snap)
            self.store.upsert_token(quoted_token)
            snapshot_id = self.store.add_snapshot(snap)
            market_gate = (
                (snap.liquidity_usd or 0) >= min_liquidity
                and (snap.volume_5m_usd or 0) >= min_volume
                and transactions >= min_transactions
                and buy_ratio >= min_buy_ratio
            )
            pending_item = pending_by_token.get(quoted_token.token_id)
            if pending_item is not None:
                pending_ranked.append(
                    (
                        pending_item["eligible_at"],
                        momentum,
                        quoted_token,
                        pending_item["trigger"],
                    )
                )
                continue
            trigger = self.autonomous_search.resolve_token_context_trigger(
                quoted_token,
                momentum_score=momentum,
                snapshot_observed_at=snap.observed_at,
                snapshot_id=snapshot_id,
            )
            if not market_gate and trigger is None:
                continue
            ranked.append((int((trigger or {}).get("priority") or 0), momentum, quoted_token, trigger))

        pending_ranked.sort(key=lambda item: (item[0], item[2].token_id))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        pending_lookup_limit = max_queries
        if pending_ranked and ranked and max_queries > 1:
            pending_lookup_limit -= 1
        lookup_candidates = [
            (int(trigger.get("priority") or 0), momentum, token, trigger)
            for _, momentum, token, trigger in pending_ranked[:pending_lookup_limit]
        ]
        lookup_candidates.extend(ranked[:max_queries - len(lookup_candidates)])
        if len(lookup_candidates) < max_queries:
            lookup_candidates.extend(
                (int(trigger.get("priority") or 0), momentum, token, trigger)
                for _, momentum, token, trigger in pending_ranked[pending_lookup_limit:]
                if token.token_id not in {item[2].token_id for item in lookup_candidates}
            )
        for _, momentum, token, trigger in lookup_candidates[:max_queries]:
            key = f"reverse_news:{token.token_id}"
            self.store.set_kv(key, iso(now))
            name = token.name.strip() or token.symbol.strip()
            query = f'"{name}" when:1d'
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
                {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
            )
            source = "google-news-reverse"
            matched = 0
            eligible = 0
            context_only = 0
            matched_publishers: set[str] = set()
            outside_time_window = 0
            identity_mismatches = 0
            source_key = "reverse-news:" + hashlib.sha256(
                token.token_id.encode("utf-8", errors="ignore")
            ).hexdigest()[:16]
            attempt_id = self.store.start_source_poll_attempt(
                collector_kind="reverse_news",
                source_key=source_key,
                platform="rss_news",
            )
            lookup_started_at = utcnow()
            self.store.record_token_universe_funnel_transition(
                token.token_id,
                stage="event_lookup_attempt",
                status="started",
                reason_code="reverse_news_lookup_started",
                evaluation_key=f"source_poll_attempt:{attempt_id}:attempt",
                observed_at=lookup_started_at,
                ingested_at=lookup_started_at,
                source_table="source_poll_attempts",
                source_record_ids={"source_poll_attempt_id": attempt_id},
                source_poll_attempt_id=attempt_id,
                metadata={"query": query},
            )
            try:
                observations = await RSSCollector(self.http, source, url, "news").poll()
                new_observations = 0
                new_events = 0
                duplicates = 0
                for obs in observations:
                    if obs.published_at:
                        age = now - obs.published_at
                        if age < timedelta(minutes=-5) or age > max_result_age:
                            outside_time_window += 1
                            continue
                    if not _reverse_news_matches_token(token, obs):
                        identity_mismatches += 1
                        continue
                    obs.role = "identity"
                    obs.raw["reverse_token_id"] = token.token_id
                    obs.raw["reverse_query"] = query
                    obs.raw["token_momentum_score"] = momentum
                    obs.raw["reverse_name_only"] = True
                    obs.raw["decision_eligible"] = False
                    obs.raw["affects"] = "audit_context_only"
                    result = await self.ingest_observation(obs)
                    new_observations += int(bool(result["observation_created"]))
                    new_events += int(bool(result["event_created"]))
                    duplicates += int(not result["observation_created"])
                    matched += 1
                    eligible += int(bool(result["decision_eligible"]))
                    context_only += int(not result["decision_eligible"])
                    matched_publishers.add(evidence_origin(obs))
                    if matched >= max_results:
                        break
                self.store.heartbeat(source, item=matched > 0)
                self.store.finish_source_poll_attempt(
                    attempt_id,
                    status="completed",
                    fetched_count=len(observations),
                    new_observation_count=new_observations,
                    new_event_count=new_events,
                    decision_eligible_count=eligible,
                    context_only_count=context_only,
                    duplicate_count=duplicates,
                    filtered_count=max(0, len(observations) - matched),
                )
                lookup_completed_at = utcnow()
                if matched:
                    lookup_reason = (
                        "reverse_news_matched"
                        if eligible else "reverse_news_identity_matched"
                    )
                elif not observations:
                    lookup_reason = "no_results_returned"
                elif outside_time_window == len(observations):
                    lookup_reason = "all_results_outside_time_window"
                elif identity_mismatches == len(observations):
                    lookup_reason = "no_identity_match"
                else:
                    lookup_reason = "no_eligible_result"
                self.store.record_token_universe_funnel_transition(
                    token.token_id,
                    stage="event_lookup_result",
                    status="found" if matched else "zero_yield",
                    reason_code=lookup_reason,
                    evaluation_key=f"source_poll_attempt:{attempt_id}:result",
                    observed_at=lookup_completed_at,
                    ingested_at=lookup_completed_at,
                    source_table="source_poll_attempts",
                    source_record_ids={"source_poll_attempt_id": attempt_id},
                    source_poll_attempt_id=attempt_id,
                    metadata={
                        "fetched_count": len(observations),
                        "matched_count": matched,
                        "accepted_count": eligible,
                        "decision_eligible_count": eligible,
                        "identity_context_count": context_only,
                        "outside_time_window_count": outside_time_window,
                        "identity_mismatch_count": identity_mismatches,
                        "distinct_publisher_count": len(matched_publishers),
                    },
                )
            except Exception as exc:
                self.store.finish_source_poll_attempt(
                    attempt_id,
                    status="error",
                    error_type=type(exc).__name__,
                )
                lookup_completed_at = utcnow()
                self.store.record_token_universe_funnel_transition(
                    token.token_id,
                    stage="event_lookup_result",
                    status="error",
                    reason_code=type(exc).__name__,
                    evaluation_key=f"source_poll_attempt:{attempt_id}:result",
                    observed_at=lookup_completed_at,
                    ingested_at=lookup_completed_at,
                    source_table="source_poll_attempts",
                    source_record_ids={"source_poll_attempt_id": attempt_id},
                    source_poll_attempt_id=attempt_id,
                )
                self._notify_source_error(source, exc)

            minimum_publishers = int(cfg.get("min_independent_sources", 2))
            if len(matched_publishers) < minimum_publishers:
                snapshot = self.store.latest_snapshot(token.token_id)
                if snapshot is not None:
                    await self._investigate_token_context(
                        token,
                        snapshot,
                        momentum_score=momentum,
                        event_relation=trigger,
                    )

    def _event_has_official_direct_ca(self, event_id: int) -> bool:
        for row in self.store.event_observations(event_id):
            if str(row["source_kind"]).lower() != "official_social":
                continue
            groups = extract_addresses(f"{row['title']}\n{row['text']}")
            if groups["evm"] or groups["solana"]:
                return True
        return False

    async def _collect_event_route_execution_challenger(
        self,
        *,
        decision_id: int,
        event_id: int,
        token: TokenCandidate,
        capacity_probe_id: int,
        baseline_snapshot_id: int | None,
        position_usd: float,
        snapshot: TokenSnapshot,
        fee_bps: float,
    ) -> None:
        """Collect a strict-forward exact-size route comparison without filling Paper."""
        raw_input = int(
            (Decimal(str(position_usd)) * Decimal(1_000_000)).to_integral_value(
                rounding=ROUND_DOWN
            )
        )
        if raw_input <= 0:
            return
        slippage_bps = round(
            float(self.config["paper"].get("slippage_rate", 0.04)) * 10_000
        )
        max_delay = float(self.config["paper"].get("max_quote_age_seconds", 45))
        frozen_at = utcnow()
        attempt_id = self.store.start_event_route_execution_challenger_attempt(
            decision_id=decision_id,
            event_id=event_id,
            token_id=token.token_id,
            capacity_probe_id=capacity_probe_id,
            baseline_snapshot_id=baseline_snapshot_id,
            intended_notional_usd=raw_input / 1_000_000,
            buy_input_amount_raw=raw_input,
            slippage_bps=slippage_bps,
            max_total_delay_seconds=max_delay,
            baseline_quote_price=snapshot.price_usd,
            baseline_execution_price=(
                float(snapshot.price_usd) * (1.0 + slippage_bps / 10_000)
                if snapshot.price_usd is not None else None
            ),
            baseline_fee_bps=fee_bps,
            baseline_buy_tax_pct=snapshot.buy_tax_pct,
            baseline_sell_tax_pct=snapshot.sell_tax_pct,
            frozen_at=frozen_at,
        )
        if attempt_id is None:
            return

        buy_quote: dict[str, Any] | None = None
        phase = "buy"

        async def quote_bundle() -> tuple[dict[str, Any], dict[str, Any]]:
            nonlocal buy_quote, phase
            buy_quote = await self.jupiter.quote(
                Store.JUPITER_USDC_MINT,
                token.address,
                raw_input,
                slippage_bps=slippage_bps,
            )
            sell_input = int(buy_quote.get("other_amount_threshold") or 0)
            if sell_input <= 0:
                raise JupiterQuoteError("exact-size buy minimum output missing")
            phase = "sell"
            sell_quote = await self.jupiter.quote(
                token.address,
                Store.JUPITER_USDC_MINT,
                sell_input,
                slippage_bps=slippage_bps,
            )
            return buy_quote, sell_quote

        try:
            async with self._jupiter_quote_lock:
                buy, sell = await quote_bundle()
        except JupiterNoRouteError:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="no_route",
                validity_status="valid",
                economic_status="not_applicable",
                reason=f"{phase}_route_unavailable",
                buy_quote=buy_quote,
            )
            return
        except JupiterQuoteProtocolError as exc:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="protocol_invalid",
                validity_status="invalid",
                economic_status="not_applicable",
                reason=type(exc).__name__,
                buy_quote=buy_quote,
            )
            return
        except JupiterQuoteError as exc:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="protocol_invalid",
                validity_status="invalid",
                economic_status="not_applicable",
                reason=type(exc).__name__,
                buy_quote=buy_quote,
            )
            return
        except Exception as exc:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="error",
                validity_status="invalid",
                economic_status="not_applicable",
                reason=type(exc).__name__,
                buy_quote=buy_quote,
            )
            return

        buy_requested = parse_time(buy["requested_at"])
        buy_completed = parse_time(buy["completed_at"])
        sell_requested = parse_time(sell["requested_at"])
        sell_completed = parse_time(sell["completed_at"])
        exact_match = (
            str(buy.get("input_mint") or "") == Store.JUPITER_USDC_MINT
            and str(buy.get("output_mint") or "") == token.address
            and int(buy.get("in_amount") or 0) == raw_input
            and int(buy.get("slippage_bps") or -1) == slippage_bps
            and str(sell.get("input_mint") or "") == token.address
            and str(sell.get("output_mint") or "") == Store.JUPITER_USDC_MINT
            and int(sell.get("in_amount") or 0)
            == int(buy.get("other_amount_threshold") or 0)
            and int(sell.get("slippage_bps") or -1) == slippage_bps
        )
        total_delay = (sell_completed - parse_time(frozen_at)).total_seconds()
        clocks_valid = (
            parse_time(frozen_at)
            <= buy_requested
            <= buy_completed
            <= sell_requested
            <= sell_completed
            and 0 <= total_delay <= max_delay
        )
        if not exact_match:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="quoted",
                validity_status="mismatched",
                economic_status="not_applicable",
                reason="exact_size_route_identity_or_amount_mismatch",
                buy_quote=buy,
                sell_quote=sell,
            )
            return
        if not clocks_valid:
            self.store.finish_event_route_execution_challenger_attempt(
                attempt_id,
                quote_terminal_status="quoted",
                validity_status="expired",
                economic_status="not_applicable",
                reason="exact_size_route_time_invalid",
                buy_quote=buy,
                sell_quote=sell,
            )
            return

        sell_min = int(sell.get("other_amount_threshold") or 0)
        round_trip = sell_min / raw_input - 1.0
        route_only_cost = (raw_input - sell_min) / 1_000_000
        fee_keys = (
            "signature_fee_lamports",
            "prioritization_fee_lamports",
            "rent_fee_lamports",
        )
        fee_fields_present = all(
            quote.get(key) is not None for quote in (buy, sell) for key in fee_keys
        )
        signature_fee_nonzero = all(
            int(quote.get("signature_fee_lamports") or 0) > 0 for quote in (buy, sell)
        )
        fee_status = (
            "lamports_present_native_usd_conversion_missing"
            if fee_fields_present and signature_fee_nonzero
            else "quote_fee_fields_incomplete_or_zero"
        )
        self.store.finish_event_route_execution_challenger_attempt(
            attempt_id,
            quote_terminal_status="quoted",
            validity_status="valid",
            economic_status="cost_unknown",
            reason="fresh_exact_size_two_way_route_research_only",
            buy_quote=buy,
            sell_quote=sell,
            round_trip_min_return=round_trip,
            route_only_cost_usd=route_only_cost,
            fee_completeness_status=fee_status,
            network_fee_basis="native_fee_usd_conversion_not_yet_frozen",
        )

    async def evaluate_events_once(self) -> None:
        threshold = float(self.config.get("event_min_attention", 35.0))
        candidate_cfg = self.config["candidate"]
        cooldown = int(candidate_cfg.get("decision_cooldown_seconds", 180))
        retry_seconds = [
            max(1, int(value))
            for value in candidate_cfg.get("retry_seconds", [25, 60, 150, 300])
        ] or [60]
        max_events = int(candidate_cfg.get("max_events_per_cycle", 8))
        now = utcnow()
        evaluated = 0

        for event in self.store.active_events(minutes=480, limit=max(100, max_events)):
            if event.attention < threshold and not self._event_has_official_direct_ca(event.id):
                continue

            next_key = f"event_decision_next:{event.id}"
            next_at = self.store.get_kv(next_key)
            if next_at and now < parse_time(next_at):
                continue

            max_source_age = float(candidate_cfg.get("max_source_age_minutes", 30))
            accepted, _ = replay_guard(self.store.event_observations(event.id), now, max_source_age)
            if not any(str(row["source_kind"]).lower() != "onchain" for row in accepted):
                # Do not repeatedly spend DEX/API work on an event whose only
                # evidence is already stale. Any newly ingested observation clears
                # this key and makes the event immediately eligible again.
                self.store.set_kv(
                    next_key,
                    iso(max(now + timedelta(minutes=5), event.last_seen_at + timedelta(minutes=480))),
                )
                continue

            if evaluated >= max_events:
                break
            evaluated += 1
            decision = await self.evaluator.discover_and_decide(event)
            attempt_key = f"event_decision_attempt:{event.id}"
            attempt = int(self.store.get_kv(attempt_key, 0))
            if not decision:
                delay = retry_seconds[min(attempt, len(retry_seconds) - 1)]
                self.store.set_kv(attempt_key, attempt + 1)
                self.store.set_kv(next_key, iso(now + timedelta(seconds=delay)))
                continue

            token = self.store.token(decision.token_id) if decision.token_id else None
            snap = (
                self.store.latest_snapshot(decision.token_id, at_or_before=decision.created_at)
                if decision.token_id else None
            )
            amount = 0.0
            fee_bps = 0.0
            execution_requested_at = None
            execution_received_at = decision.created_at
            execution_snapshot_id: int | None = None
            route_challenger_ready = False
            pending_entry_attempt: dict[str, Any] | None = None

            if decision.action == "CANDIDATE" and decision.token_id:
                if self.store.position(decision.token_id):
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("position_already_open")
                elif not candidate_cfg.get("allow_reentry", False) and self.store.has_bought_token(decision.token_id):
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("token_already_traded")

            if (
                decision.action == "CANDIDATE"
                and token is not None
                and token.chain.lower() != "solana"
            ):
                decision.action = "WAIT"
                decision.rejected_reasons.append(
                    f"paper_amount_specific_route_unavailable_{token.chain.lower()}"
                )
                if self.config["mode"] == "paper":
                    pending_entry_attempt = {
                        "event_id": event.id,
                        "token_id": token.token_id,
                        "side": "BUY",
                        "status": "rejected",
                        "reason": "amount_specific_route_and_chain_fee_unavailable",
                        "requested_at": decision.created_at,
                    }

            if decision.action == "CANDIDATE" and token and snap:
                execution_requested_at = utcnow()
                try:
                    execution_quote = await self.dex.quote(token.chain, token.address)
                except Exception as exc:
                    execution_quote = None
                    execution_error = type(exc).__name__
                else:
                    execution_error = "quote_unavailable"
                execution_received_at = utcnow()
                if execution_quote is None:
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("entry_quote_unavailable")
                    if self.config["mode"] == "paper":
                        pending_entry_attempt = {
                            "event_id": event.id, "token_id": token.token_id, "side": "BUY",
                            "status": "rejected", "reason": execution_error,
                            "requested_at": execution_requested_at,
                        }
                else:
                    execution_token, execution_snapshot = execution_quote
                    quote_rejections = self._paper_quote_rejections(
                        token.token_id, execution_token, execution_snapshot, execution_received_at
                    )
                    if quote_rejections:
                        decision.action = "WAIT"
                        decision.rejected_reasons.extend(quote_rejections)
                        if self.config["mode"] == "paper":
                            pending_entry_attempt = {
                                "event_id": event.id, "token_id": token.token_id, "side": "BUY",
                                "status": "rejected", "reason": ",".join(quote_rejections),
                                "requested_at": execution_requested_at,
                                "quote_observed_at": execution_snapshot.observed_at,
                                "quote_provider": execution_snapshot.provider,
                                "quote_price": execution_snapshot.price_usd,
                            }
                    else:
                        token, snap = execution_token, execution_snapshot
                        self.store.upsert_token(token, seen_at=snap.observed_at)
                        execution_snapshot_id = self.store.add_snapshot(snap)

            if decision.action == "CANDIDATE" and token and snap and snap.price_usd:
                route_probe = (
                    self.store.event_context_jupiter_route_probe(decision.route_probe_id)
                    if decision.route_probe_id is not None else None
                )
                if route_probe is not None:
                    sell_completed_at = route_probe["sell_completed_at"]
                    probe_age = (
                        (parse_time(execution_received_at) - parse_time(sell_completed_at)).total_seconds()
                        if sell_completed_at else -1.0
                    )
                    route_probe_valid = (
                        str(route_probe["status"]) == "valid"
                        and int(route_probe["decision_eligible"]) == 1
                        and int(route_probe["event_id"]) == int(event.id)
                        and str(route_probe["token_id"]) == str(token.token_id)
                        and 0 <= probe_age <= float(route_probe["max_total_delay_seconds"])
                    )
                    if not route_probe_valid:
                        decision.action = "WAIT"
                        decision.rejected_reasons.append("event_route_stale_or_mismatched")
                        route_probe = None
                if decision.action == "CANDIDATE":
                    account = self.store.account()
                    positions = self.store.open_positions()
                    marked_values = []
                    for pos in positions:
                        mark = self.store.latest_snapshot(pos.token_id, at_or_before=execution_received_at)
                        marked_values.append((mark.price_usd if mark and mark.price_usd else pos.entry_price) * pos.quantity)
                    equity = account["cash_usd"] + sum(marked_values)
                    amount = self.policy.size(
                        cash_usd=account["cash_usd"],
                        equity_usd=equity,
                        open_count=len(positions),
                        snapshot=snap,
                        score=decision.score,
                        daily_exposure_usd=self.store.daily_buy_gross_usd(),
                        executable_capacity_usd=(
                            float(route_probe["input_notional_usd"]) if route_probe is not None else None
                        ),
                    )
                    fee_bps = self._paper_fee_bps(snap)
                    fixed_fee = float(
                        self.config["paper"].get("fixed_fee_usd_each_side", 0) or 0
                    )
                    if fixed_fee > 0:
                        amount = min(amount, max(0.0, account["cash_usd"] - fixed_fee))
                    else:
                        fee_rate = fee_bps / 10_000
                        amount = min(amount, account["cash_usd"] / (1 + fee_rate))
                    decision.position_usd = amount
                    if amount < float(self.config["paper"].get("min_position_usd", 0)):
                        decision.action = "WAIT"
                        decision.rejected_reasons.append("position_size_below_all_in_cash_limit")
                    elif decision.route_probe_id is not None:
                        route_challenger_ready = True
                        decision.action = "WAIT"
                        decision.rejected_reasons.append(
                            "route_backed_paper_execution_not_implemented"
                        )

            decision.created_at = max(
                parse_time(decision.created_at), parse_time(execution_received_at), utcnow()
            )

            decision_id = self.store.add_decision(decision)
            if (
                route_challenger_ready
                and self.config["mode"] == "paper"
                and token is not None
                and snap is not None
                and decision.route_probe_id is not None
            ):
                await self._collect_event_route_execution_challenger(
                    decision_id=decision_id,
                    event_id=event.id,
                    token=token,
                    capacity_probe_id=decision.route_probe_id,
                    baseline_snapshot_id=execution_snapshot_id,
                    position_usd=decision.position_usd,
                    snapshot=snap,
                    fee_bps=fee_bps,
                )
            cohort_id = self.store.create_shadow_event_cohort(
                decision,
                decision_id=decision_id,
                source_observation_ids=[int(row["id"]) for row in accepted],
            )
            ranking = self.store.candidate_ranking(event.id) or {}
            ranked_candidates = [
                item for item in ranking.get("candidates", []) if isinstance(item, dict)
            ]
            selected_candidate = next(
                (
                    item for item in ranked_candidates
                    if str(item.get("token_id") or "") == str(decision.token_id or "")
                ),
                {},
            )
            relation_available_at = decision.created_at
            mapping_basis = "lexical_or_context_relation_available_at_decision"
            if decision.token_id:
                token_address = decision.token_id.split(":", 1)[-1]
                exact_relation_times = []
                for row in accepted:
                    groups = extract_addresses(f"{row['title']}\n{row['text']}")
                    addresses = {*groups["solana"], *groups["evm"]}
                    if any(value.casefold() == token_address.casefold() for value in addresses):
                        exact_relation_times.append(
                            max(parse_time(row["observed_at"]), parse_time(row["ingested_at"]))
                        )
                if exact_relation_times:
                    relation_available_at = min(exact_relation_times)
                    mapping_basis = "exact_ca_in_eligible_source"
            if decision.token_id:
                self.store.create_information_first_shadow_cohort(
                    event.id,
                    decision.token_id,
                    decision_id=decision_id,
                    accepted_observation_ids=[int(row["id"]) for row in accepted],
                    captured_at=decision.created_at,
                    relation_available_at=relation_available_at,
                    candidate_facts={
                        "candidate_count": ranking.get("candidate_count_total"),
                        "selected_rank": selected_candidate.get("rank"),
                        "raw_score_margin": selected_candidate.get("raw_canonical_margin"),
                        "canonical_margin": decision.canonical_margin,
                        "tie_break_used": bool((ranking.get("tie_break") or {}).get("used")),
                        "mapping_basis": mapping_basis,
                        "candidate_set_truncated": bool(ranking.get("candidates_truncated")),
                    },
                )
            self.store.create_attention_experiment_event_cohort(
                event_id=event.id,
                decision_id=decision_id,
                shadow_cohort_id=cohort_id,
            )
            if pending_entry_attempt is not None:
                self.store.record_paper_execution_attempt(
                    **pending_entry_attempt, decision_id=decision_id, cohort_id=cohort_id
                )
            self.store.finalize_candidate_ranking(event.id, decision, decision_id=decision_id)
            signature = json.dumps(
                {
                    "action": decision.action,
                    "token_id": decision.token_id,
                    "rejected": sorted(decision.rejected_reasons),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            notification_key = f"event_decision_notification:{event.id}"
            previous_signature = self.store.get_kv(notification_key)
            should_notify_wait = bool(self.config["notifications"].get("notify_wait", False))
            if signature != previous_signature and (decision.action != "WAIT" or should_notify_wait):
                self.notifier.send(
                    "candidate_decision",
                    f"event {event.id}: {decision.action}",
                    asdict(decision),
                )
            self.store.set_kv(notification_key, signature)

            if decision.action == "WAIT":
                delay = retry_seconds[min(attempt, len(retry_seconds) - 1)]
                self.store.set_kv(attempt_key, attempt + 1)
            elif decision.action == "REJECT":
                delay = max(cooldown, 300)
                self.store.set_kv(attempt_key, 0)
            else:
                delay = cooldown
                self.store.set_kv(attempt_key, 0)
            self.store.set_kv(next_key, iso(now + timedelta(seconds=delay)))

            if decision.action != "CANDIDATE" or not token or not snap or not snap.price_usd or amount <= 0:
                if token and snap:
                    await self._investigate_token_context(
                        token,
                        snap,
                        momentum_score=CandidateEvaluator._momentum_score(snap),
                        event_relation={"decision_id": decision_id},
                    )
                continue
            slippage = float(self.config["paper"].get("slippage_rate", 0.0))
            execution_price = float(snap.price_usd) * (1.0 + slippage)
            if self.config["mode"] == "shadow":
                self.notifier.send(
                    "shadow_buy",
                    token.token_id,
                    {
                        "amount_usd": amount,
                        "quote_price": snap.price_usd,
                        "execution_price": execution_price,
                        "score": decision.score,
                    },
                )
                await self._investigate_token_context(
                    token,
                    snap,
                    momentum_score=CandidateEvaluator._momentum_score(snap),
                    event_relation={"decision_id": decision_id},
                )
                continue
            try:
                position = self.store.paper_buy(
                    event_id=event.id,
                    token=token,
                    price=execution_price,
                    gross_usd=amount,
                    fee_bps=fee_bps,
                    fixed_fee_usd=float(
                        self.config["paper"].get("fixed_fee_usd_each_side", 0) or 0
                    ),
                    reason="event_candidate",
                    quote_price=float(snap.price_usd),
                    tax_pct=snap.buy_tax_pct,
                    quote_observed_at=snap.observed_at,
                    quote_provider=snap.provider,
                    execution_attempted_at=execution_requested_at,
                    decision_id=decision_id,
                    cohort_id=cohort_id,
                    record_execution_attempt=True,
                )
            except ValueError as exc:
                self.store.record_paper_execution_attempt(
                    event_id=event.id, token_id=token.token_id, side="BUY",
                    decision_id=decision_id, cohort_id=cohort_id,
                    status="rejected", reason=str(exc),
                    requested_at=execution_requested_at or utcnow(),
                    quote_observed_at=snap.observed_at, quote_provider=snap.provider,
                    quote_price=snap.price_usd, execution_price=execution_price,
                    gross_usd=amount,
                )
                self.notifier.send(
                    "quote_error", token.token_id,
                    {"error": "paper_buy_rejected", "reason": str(exc)},
                )
                continue
            self._record_paper_account_snapshot(force=True)
            self.notifier.send(
                "paper_buy",
                token.token_id,
                {**asdict(position), "quote_price": snap.price_usd, "slippage_rate": slippage},
            )
            await self._investigate_token_context(
                token,
                snap,
                momentum_score=CandidateEvaluator._momentum_score(snap),
                event_relation={"decision_id": decision_id},
            )

    def _configured_health_sources(self) -> set[str]:
        sources = self.config["sources"]
        configured = {
            str(item.get("name") or item.get("url") or "")
            for item in sources.get("rss", [])
            if item.get("enabled", True) and item.get("url")
        }
        configured.update(
            str(item.get("name") or item.get("url") or "")
            for item in sources.get("mastodon", [])
            if item.get("enabled", True) and item.get("url")
        )
        configured.update(
            f"geckoterminal:{network}"
            for network in sources.get("gecko_networks", [])
        )
        for query in sources.get("bluesky_queries", []):
            if str(query).strip():
                configured.add(str(query))
                configured.add(f"bluesky:{query}")
        if (sources.get("pumpportal") or {}).get("enabled", True):
            configured.update({"pumpportal:create", "pumpportal:migration"})
        if (sources.get("reverse_google_news") or {}).get("enabled", True):
            configured.add("google-news-reverse")
        if (sources.get("dexscreener_discovery") or {}).get("enabled", True):
            configured.update(
                {
                    *(f"dexscreener:{surface}" for surface in DexScreenerClient.DISCOVERY_SURFACES),
                    "dexscreener:hydration",
                }
            )
        configured.update(
            str(item.get("name") or item.get("url") or "")
            for item in self.autonomous_search.active_rss_sources()
            if item.get("url")
        )
        if self.config["autonomous_search"].get("enabled", False):
            configured.update(
                {
                    "autonomous-source-discovery",
                    "autonomous-trend-scout",
                    "autonomous-context-search",
                }
            )
        return configured

    async def check_source_health_once(self, *, include_streams: bool = True) -> None:
        limits = self.config.get("source_stale_minutes") or {}
        configured_sources = self._configured_health_sources()
        bridge_enabled = bool((self.config.get("bridge") or {}).get("enabled", True))
        now = utcnow()
        for row in self.store.source_health():
            source = str(row["source"])
            if source.startswith("browser:"):
                if not bridge_enabled:
                    continue
            elif source not in configured_sources:
                continue
            if not include_streams and source.startswith("pumpportal"):
                continue
            last_ok = row["last_ok_at"]
            if not last_ok:
                continue
            if source.startswith("google-news-reverse:"):
                # Rows from pre-migration builds are one-shot query diagnostics,
                # not resident sources expected to heartbeat forever.
                continue
            if source == "pumpportal:migration":
                # Migrations can legitimately be absent for long periods; the frequent
                # create stream is the connection-health signal for this WebSocket.
                continue
            if source.startswith("browser:"):
                source_group = "browser"
            elif source.startswith("pumpportal"):
                source_group = "pumpportal"
            else:
                source_group = "other"
            threshold = float(limits.get(source_group, 20))
            age_minutes = (now - parse_time(last_ok)).total_seconds() / 60.0
            if age_minutes <= threshold:
                continue
            key = f"source_stale_alert:{source}"
            alerted = self.store.get_kv(key)
            if alerted and now - parse_time(alerted) < timedelta(minutes=max(threshold, 10)):
                continue
            self.store.set_kv(key, iso(now))
            self.notifier.send("source_stale", source, {"minutes_since_ok": round(age_minutes, 1), "threshold": threshold})

    async def monitor_positions_once(self) -> None:
        executed = False
        for position in list(self.store.open_positions()):
            try:
                quoted = await self.dex.quote(position.chain, position.address)
            except Exception as exc:
                self.notifier.send("quote_error", position.token_id, {"error": type(exc).__name__})
                continue
            if not quoted:
                continue
            token, snap = quoted
            snap = await self.safety.enrich_evm(snap)
            snap = await self.safety.enrich_solana(snap)
            quote_received_at = utcnow()
            temporal_rejections = self._paper_quote_rejections(
                position.token_id, token, snap, quote_received_at
            )
            if temporal_rejections:
                self.notifier.send(
                    "quote_error",
                    position.token_id,
                    {"error": "temporal_snapshot_rejected", "reasons": temporal_rejections},
                )
                continue
            self.store.upsert_token(token)
            self.store.add_snapshot(snap)
            if snap.price_usd:
                self.store.update_position_peak(position.token_id, snap.price_usd)
            refreshed = self.store.position(position.token_id)
            if not refreshed:
                continue
            try:
                event = self.store.get_event(refreshed.event_id)
            except KeyError:
                event = None
            action = self.policy.exit_action(refreshed, snap, event=event)
            if not action:
                continue
            fraction, reason = action
            execution_requested_at = utcnow()
            try:
                execution_quote = await self.dex.quote(position.chain, position.address)
            except Exception as exc:
                execution_quote = None
                execution_error = type(exc).__name__
            else:
                execution_error = "quote_unavailable"
            execution_received_at = utcnow()
            if execution_quote is None:
                self.store.record_paper_execution_attempt(
                    event_id=position.event_id, token_id=position.token_id, side="SELL",
                    decision_id=position.decision_id, cohort_id=position.cohort_id,
                    status="rejected", reason=execution_error,
                    requested_at=execution_requested_at,
                )
                continue
            execution_token, execution_snapshot = execution_quote
            quote_rejections = self._paper_quote_rejections(
                position.token_id, execution_token, execution_snapshot, execution_received_at
            )
            if quote_rejections:
                self.store.record_paper_execution_attempt(
                    event_id=position.event_id, token_id=position.token_id, side="SELL",
                    decision_id=position.decision_id, cohort_id=position.cohort_id,
                    status="rejected", reason=",".join(quote_rejections),
                    requested_at=execution_requested_at,
                    quote_observed_at=execution_snapshot.observed_at,
                    quote_provider=execution_snapshot.provider,
                    quote_price=execution_snapshot.price_usd,
                )
                continue
            token, snap = execution_token, execution_snapshot
            self.store.upsert_token(token, seen_at=snap.observed_at)
            self.store.add_snapshot(snap)
            slippage = float(self.config["paper"].get("slippage_rate", 0.0))
            fee = self._paper_fee_bps(snap)
            execution_price = float(snap.price_usd) * (1.0 - slippage)
            result = self.store.paper_sell(
                position.token_id,
                price=execution_price,
                fraction=fraction,
                fee_bps=fee,
                fixed_fee_usd=float(
                    self.config["paper"].get("fixed_fee_usd_each_side", 0) or 0
                ),
                reason=reason,
                quote_price=float(snap.price_usd),
                tax_pct=snap.sell_tax_pct,
                quote_observed_at=snap.observed_at,
                quote_provider=snap.provider,
                execution_attempted_at=execution_requested_at,
                record_execution_attempt=True,
            )
            executed = True
            remaining = self.store.position(position.token_id)
            if remaining and reason.startswith("take_profit_"):
                self.store.set_take_profit_index(position.token_id, remaining.take_profit_index + 1)
            self.notifier.send(
                "paper_sell",
                position.token_id,
                {
                    "fraction": fraction,
                    "reason": reason,
                    "quote_price": snap.price_usd,
                    "execution_price": execution_price,
                    "slippage_rate": slippage,
                    **result,
                },
            )
        self._record_paper_account_snapshot(force=executed)

    async def shadow_event_followup_once(self) -> None:
        self.store.process_agent_shadow_review_inputs()
        self.store.finalize_token_context_deferred_admissions()
        await self.retry_deferred_token_context_once()
        self.store.finalize_shadow_event_outcomes()
        self.store.finalize_token_context_outcomes()
        self.store.finalize_information_first_shadow_outcomes()
        self.store.finalize_information_first_ilg_outcomes()
        self.store.finalize_attention_experiment_outcomes()
        await self.token_universe_followup_once()
        await self.token_universe_jupiter_quote_once(
            include_universe=True,
            include_onchain=False,
        )
        self.store.finalize_token_universe_outcome_quality()
        self.store.finalize_token_universe_fixed_target_execution()
        self.store.finalize_missed_opportunity_audits()
        self.store.finalize_missed_opportunity_no_decision_attributions()

    async def _liquidity_survival_target_once(self, target: dict[str, Any]) -> None:
        requested_at = utcnow()
        deadline_at = parse_time(target["deadline_at"])
        remaining = max(0.0, (deadline_at - requested_at).total_seconds())
        if remaining <= 0:
            return
        try:
            async with asyncio.timeout(min(15.0, remaining)):
                quoted = await self.dex.quote(
                    str(target["chain"]),
                    str(target["token_id"]).split(":", 1)[1],
                )
        except TimeoutError:
            completed_at = utcnow()
            self.store.record_liquidity_survival_attempt(
                int(target["id"]),
                requested_at=requested_at,
                completed_at=completed_at,
                status="timeout",
                reason="deadline_bounded_provider_timeout",
            )
            return
        except Exception as exc:
            completed_at = utcnow()
            self.store.record_liquidity_survival_attempt(
                int(target["id"]),
                requested_at=requested_at,
                completed_at=completed_at,
                status="error",
                reason=type(exc).__name__,
            )
            return
        completed_at = utcnow()
        if quoted is None:
            self.store.record_liquidity_survival_attempt(
                int(target["id"]),
                requested_at=requested_at,
                completed_at=completed_at,
                status="no_pair",
                reason="provider_returned_no_pair",
            )
            return
        token, snapshot = quoted
        pair = self.store._snapshot_pair_fields(snapshot)
        observed_pair = str((pair or {}).get("pair_address") or "")
        if observed_pair != str(target["pair_address"]):
            self.store.record_liquidity_survival_attempt(
                int(target["id"]),
                requested_at=requested_at,
                completed_at=completed_at,
                status="pair_mismatch",
                reason="exact_baseline_pair_not_returned_by_best_pair_quote",
                observed_pair_address=observed_pair,
            )
            return
        self.store.upsert_token(token, seen_at=snapshot.observed_at)
        self.store.add_snapshot(snapshot)
        self.store.record_liquidity_survival_attempt(
            int(target["id"]),
            requested_at=requested_at,
            completed_at=completed_at,
            status="observed",
            reason="exact_same_pair_snapshot_persisted",
            observed_pair_address=observed_pair,
        )

    async def liquidity_survival_once(self) -> None:
        if not self.store.LIQUIDITY_SURVIVAL_ENABLED:
            return
        self.store.finalize_liquidity_survival_deadlines()
        targets = self.store.due_liquidity_survival_targets(limit=4)
        if targets:
            await asyncio.gather(
                *(self._liquidity_survival_target_once(target) for target in targets)
            )
        self.store.finalize_liquidity_survival_deadlines()

    async def _information_first_active_outcome_target_once(
        self, target: dict[str, Any]
    ) -> None:
        requested_at = utcnow()
        deadline_at = parse_time(target["deadline_at"])
        attempt_id = self.store.start_information_first_active_outcome_attempt(
            int(target["id"]),
            retry_index=int(target["retry_index"]),
            scheduled_at=target["scheduled_at"],
            requested_at=requested_at,
        )
        if attempt_id is None:
            return
        remaining_seconds = max(0.001, (deadline_at - requested_at).total_seconds())
        request_timeout = min(
            self.INFORMATION_FIRST_ACTIVE_OUTCOME_REQUEST_TIMEOUT_SECONDS,
            remaining_seconds,
        )
        status, reason, snapshot = "http_error", "dexscreener_request_failed", None
        try:
            async with asyncio.timeout(request_timeout):
                quoted = await self.dex.quote(str(target["chain"]), str(target["address"]))
            if quoted is None:
                status, reason = "no_pair", "dexscreener_no_pair_at_target"
            else:
                _, snapshot = quoted
                if snapshot.price_usd is not None and float(snapshot.price_usd) > 0:
                    status, reason = "observed_mark", "fresh_dexscreener_mark"
                else:
                    status, reason, snapshot = "provider_empty", "pair_without_positive_price", None
        except TimeoutError:
            status, reason = "timeout", "deadline_bounded_provider_timeout"
        except httpx.TimeoutException:
            status, reason = "timeout", "dexscreener_timeout"
        except httpx.HTTPStatusError as exc:
            status = "rate_limited" if exc.response.status_code == 429 else "http_error"
            reason = f"dexscreener_http_{exc.response.status_code}"
        except (TypeError, ValueError, json.JSONDecodeError):
            status, reason = "protocol_invalid", "dexscreener_protocol_invalid"
        except Exception as exc:
            status, reason = "http_error", f"dexscreener_{type(exc).__name__}"
        response_received_at = utcnow()
        if response_received_at > deadline_at:
            self.store.finalize_information_first_active_outcome_deadlines(
                now=response_received_at
            )
        self.store.finish_information_first_active_outcome_attempt(
            attempt_id,
            status=status,
            reason_code=reason,
            response_received_at=response_received_at,
            snapshot=snapshot,
        )

    async def information_first_active_outcome_once(self) -> None:
        """Actively mark due future information-first cohorts without trading."""
        self.store.finalize_information_first_active_outcome_deadlines()
        targets = self.store.due_information_first_active_outcome_targets(limit=4)
        if targets:
            await asyncio.gather(
                *(self._information_first_active_outcome_target_once(target) for target in targets)
            )
        self.store.finalize_information_first_active_outcome_deadlines()

    async def retry_deferred_token_context_once(self) -> None:
        cfg = self.config["autonomous_search"]
        if not cfg.get("context_deferred_retry_enabled", False):
            return
        activated_at = self.store.get_kv(self.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY)
        if not activated_at:
            return
        now = utcnow()
        last_retry = self.store.get_kv(self.DEFERRED_CONTEXT_RETRY_RUN_KEY)
        retry_interval = max(
            float(cfg.get("context_global_cooldown_minutes", 5)),
            float(cfg.get("context_deferred_retry_interval_minutes", 5)),
        )
        if last_retry and now - parse_time(last_retry) < timedelta(minutes=retry_interval):
            return
        due = self.store.due_token_context_active_retries(
            activated_at=activated_at,
            now=now,
            limit=1,
        )
        if not due:
            return
        intent = due[0]
        token = self.store.token(str(intent["token_id"]))
        snapshot = self.store.latest_snapshot(str(intent["token_id"]), at_or_before=now)
        if token is None or snapshot is None:
            return
        relation = None
        anchor = self.store.db.execute(
            "SELECT * FROM token_context_admission_attempts WHERE id=?",
            (int(intent["admission_id"]),),
        ).fetchone()
        if anchor is not None and intent.get("trigger_transition_id") is not None:
            relation = {
                "kind": str(intent["trigger_kind"]),
                "priority": int(intent["trigger_priority"] or 0),
                "transition_id": int(intent["trigger_transition_id"]),
                "selection_path": "deferred_retry_lane",
                "decision_eligible": False,
                "endorsement_inferred": False,
            }
            for key in ("source_link_id", "event_id", "decision_id"):
                if anchor[key] is not None:
                    relation[key] = int(anchor[key])
            for key in ("platform", "entity_id"):
                if str(anchor[key] or ""):
                    relation[key] = str(anchor[key])
            trigger_transition = self.store.db.execute(
                "SELECT observation_id,source_record_ids_json,metadata_json "
                "FROM token_universe_funnel_transitions WHERE id=?",
                (int(intent["trigger_transition_id"]),),
            ).fetchone()
            if trigger_transition is not None:
                try:
                    source_ids = json.loads(
                        str(trigger_transition["source_record_ids_json"] or "{}")
                    )
                except (TypeError, json.JSONDecodeError):
                    source_ids = {}
                try:
                    transition_metadata = json.loads(
                        str(trigger_transition["metadata_json"] or "{}")
                    )
                except (TypeError, json.JSONDecodeError):
                    transition_metadata = {}
                for key in ("source_buy_trade_id", "shadow_cohort_id"):
                    if source_ids.get(key) is not None:
                        relation[key] = int(source_ids[key])
                for key in ("context_snapshot_basis", "investigation_started_at"):
                    if transition_metadata.get(key):
                        relation[key] = str(transition_metadata[key])
                if relation.get("source_buy_trade_id") is not None:
                    position = self.store.db.execute(
                        "SELECT opened_at,status FROM "
                        "onchain_paper_narrative_runner_positions "
                        "WHERE definition_version=? AND source_buy_trade_id=?",
                        (
                            Store.ONCHAIN_PAPER_NARRATIVE_RUNNER_VERSION,
                            int(relation["source_buy_trade_id"]),
                        ),
                    ).fetchone()
                    if position is not None:
                        relation["position_opened_at"] = str(position["opened_at"])
                        relation["position_status"] = str(position["status"])
            if trigger_transition is not None and trigger_transition["observation_id"] is not None:
                observation = self.store.db.execute(
                    "SELECT * FROM observations WHERE id=?",
                    (int(trigger_transition["observation_id"]),),
                ).fetchone()
                if observation is not None:
                    relation.update({
                        "observation_id": int(observation["id"]),
                        "observed_title": str(observation["title"] or "")[:1000],
                        "observed_text": str(observation["text"] or "")[:3000],
                        "content_fingerprint": hashlib.sha256(
                            str(observation["text"] or "").encode("utf-8")
                        ).hexdigest(),
                        "published_at": str(observation["published_at"] or ""),
                        "observed_at": str(observation["observed_at"] or ""),
                        "verification_status": "browser_exact_entity_observation",
                    })
            if anchor["source_link_id"] is not None:
                source_link = self.store.db.execute(
                    "SELECT * FROM token_source_links WHERE id=?",
                    (int(anchor["source_link_id"]),),
                ).fetchone()
                if source_link is not None:
                    relation.update({
                        "link_kind": str(source_link["link_kind"] or ""),
                        "url": str(source_link["normalized_url"] or ""),
                    })
                    if "verification_status" not in relation:
                        relation["verification_status"] = str(
                            source_link["verification_status"] or ""
                        )
        elif anchor is not None and anchor["decision_id"] is not None:
            relation = {"decision_id": int(anchor["decision_id"])}
        self.store.set_kv(self.DEFERRED_CONTEXT_RETRY_RUN_KEY, iso(now))
        await self._investigate_token_context(
            token,
            snapshot,
            momentum_score=CandidateEvaluator._momentum_score(snapshot),
            event_relation=relation,
            retry_lane=True,
        )
        self.store.heartbeat("autonomous-context-retry", item=True)

    async def token_universe_followup_once(self) -> None:
        """Actively quote only due full-universe forward checkpoints."""
        self.store.finalize_token_universe_forward_outcomes()
        self.store.finalize_onchain_only_shadow_gaps()
        due = self.store.due_token_universe_quotes(limit=180)
        due.extend(self.store.due_onchain_only_shadow_quotes(limit=60))
        due.sort(key=lambda item: (
            parse_time(item["deadline_at"]), parse_time(item["queue_due_at"]),
            str(item.get("lane") or "universe"), int(item["cohort_id"]), str(item["role"]),
        ))
        by_chain: dict[str, list[dict[str, Any]]] = {}
        for item in due:
            by_chain.setdefault(str(item["chain"]), []).append(item)
        while by_chain:
            chain = min(
                by_chain,
                key=lambda name: (
                    parse_time(by_chain[name][0]["deadline_at"]),
                    parse_time(by_chain[name][0]["queue_due_at"]),
                    name,
                ),
            )
            items = by_chain[chain]
            chunk = items[:30]
            del items[:30]
            if not items:
                del by_chain[chain]
            roles = sorted({str(item["role"]) for item in chunk})
            surface = roles[0] if len(roles) == 1 else "universe_mixed"
            round_id = self.store.start_token_discovery_round(
                provider="dexscreener", surface=surface, mode="batch_quote",
                chain_scope=chain,
            )
            requested_at = utcnow()
            attempt_ids = self.store.start_token_discovery_quote_attempts(
                round_id, chunk, requested_at=requested_at,
            )
            try:
                quoted = await self._dex_batch_quote(
                    chain,
                    [str(item["token_id"]).split(":", 1)[1] for item in chunk],
                )
            except Exception as exc:
                completed_at = utcnow()
                http_status = getattr(getattr(exc, "response", None), "status_code", None)
                for item in chunk:
                    attempt_id = attempt_ids.get((str(item["token_id"]), str(item["role"])))
                    if attempt_id is not None:
                        self.store.finish_token_discovery_quote_attempt(
                            attempt_id, status="error", reason_code="batch_request_failed",
                            error_type=type(exc).__name__, http_status=http_status,
                            completed_at=completed_at,
                        )
                        if item.get("lane") == Store.ONCHAIN_ONLY_SHADOW_VERSION:
                            self.store.record_onchain_only_shadow_result(
                                item,
                                terminal_status="error",
                                quote_attempt_id=attempt_id,
                                recorded_at=completed_at,
                            )
                self.store.finish_token_discovery_round(
                    round_id, status="error", requested_count=len(chunk),
                    error_type=type(exc).__name__,
                )
                self._notify_source_error(f"dexscreener:{surface}", exc)
                continue
            if self.strategy_focus_active and decision.action == "CANDIDATE":
                decision.action = "WAIT"
                decision.rejected_reasons.append("strategy_focus_s1_paper_entry_paused")
            for item in chunk:
                token_id = str(item["token_id"])
                role = str(item["role"])
                attempt_id = attempt_ids.get((token_id, role))
                result = quoted.get(token_id)
                if result is None or result[0].token_id != token_id:
                    if attempt_id is not None:
                        self.store.finish_token_discovery_quote_attempt(
                            attempt_id, status="no_pair", reason_code="provider_returned_no_pair",
                        )
                    self.store.add_token_discovery_exposure(
                        round_id, token_id=token_id, chain=chain,
                        role=role, no_pair=True,
                    )
                    if item.get("lane") == Store.ONCHAIN_ONLY_SHADOW_VERSION:
                        self.store.record_onchain_only_shadow_result(
                            item,
                            terminal_status="no_pair",
                            quote_attempt_id=attempt_id,
                        )
                    continue
                token, snapshot = result
                required_liquidity = max(
                    float(self.config["safety"].get("min_liquidity_usd", 12_000)),
                    float(self.config["paper"].get("max_position_usd", 35))
                    / max(
                        0.000001,
                        float(self.config["paper"].get("max_liquidity_impact_pct", 0.0025)),
                    ),
                )
                if (
                    snapshot.chain.lower() in {"ethereum", "eth", "bsc", "base"}
                    and snapshot.liquidity_usd is not None
                    and float(snapshot.liquidity_usd) >= required_liquidity
                ):
                    snapshot = await self.safety.enrich_evm_execution_fields(snapshot)
                self.store.upsert_token(token, seen_at=snapshot.observed_at)
                snapshot_id = self.store.add_snapshot(snapshot)
                if attempt_id is not None:
                    self.store.finish_token_discovery_quote_attempt(
                        attempt_id, status="success", reason_code="snapshot_persisted",
                    )
                self.store.add_token_discovery_exposure(
                    round_id, token_id=token_id, chain=chain,
                    role=role, snapshot_count=1,
                    observed_at=snapshot.observed_at,
                )
                if item.get("lane") == Store.ONCHAIN_ONLY_SHADOW_VERSION:
                    self.store.record_onchain_only_shadow_result(
                        item,
                        terminal_status="observed",
                        quote_attempt_id=attempt_id,
                        target_snapshot_id=snapshot_id,
                    )
            self.store.finish_token_discovery_round(
                round_id, status="completed", requested_count=len(chunk),
                returned_count=len(quoted),
                duplicate_token_count=max(0, len(chunk) - len(quoted)),
            )
        self.store.finalize_token_universe_forward_outcomes()
        self.store.finalize_onchain_only_shadow_gaps()

    async def token_universe_jupiter_quote_once(
        self,
        *,
        budget: dict[str, int] | None = None,
        include_universe: bool = True,
        include_onchain: bool = True,
        include_kol: bool = True,
    ) -> None:
        async with self._jupiter_background_dispatch_lock:
            await self._token_universe_jupiter_quote_once_unlocked(
                budget=budget,
                include_universe=include_universe,
                include_onchain=include_onchain,
                include_kol=include_kol,
            )

    async def _record_onchain_pretrade_rug_safety(
        self,
        item: Mapping[str, Any],
        *,
        buy_status: str,
        buy_result: Mapping[str, Any],
        shared_budget: dict[str, int],
    ) -> None:
        if (
            not self.config["safety"].get("require_pretrade_rug_safety_v1", False)
            or item.get("lane") != Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION
            or str(item.get("phase")) != "baseline_buy"
        ):
            return
        snapshot = self.store.token_snapshot_by_id(int(item["baseline_snapshot_id"]))
        if snapshot is None:
            return
        snapshot = await self.safety.enrich_solana(snapshot)
        buy_route_payload = {
            **dict(buy_result),
            "input_mint": str(item["input_mint"]),
            "output_mint": str(item["output_mint"]),
            "input_amount_raw": str(item["input_amount_raw"]),
        }
        selected_surface_pool = self.safety.token_adjacent_route_pool(
            buy_route_payload, token_mint=str(item["output_mint"]), direction="BUY",
        )
        if selected_surface_pool:
            adjacent_leg = next(
                (
                    leg for leg in buy_route_payload.get("route_plan") or []
                    if isinstance(leg, Mapping)
                    and str(leg.get("amm_key") or "") == selected_surface_pool
                    and str(leg.get("output_mint") or "") == str(item["output_mint"])
                ),
                {},
            )
            routed = TokenSnapshot(**asdict(snapshot))
            routed.raw["pair"] = {
                "dexId": "jupiter-route-surface", "pairAddress": selected_surface_pool,
                "baseToken": {"address": str(item["output_mint"])},
                "quoteToken": {"address": str(adjacent_leg.get("input_mint") or item["input_mint"])},
                "route_derived": True,
            }
            snapshot = routed
        snapshot = await self.safety.enrich_solana_pool_custody(snapshot)
        assessed_snapshot_id = self.store.add_snapshot(snapshot)
        surface = self.safety.solana_market_surface_assessment(snapshot)
        self.store.record_market_surface_safety(
            lane=Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
            quote_key=str(item["quote_key"]), token_id=str(item.get("token_id") or snapshot.token_id),
            trigger_snapshot_id=int(item["baseline_snapshot_id"]),
            assessed_snapshot_id=assessed_snapshot_id, assessment=surface,
            observed_at=utcnow(),
        )
        buy_route = self.safety.classify_jupiter_route_truth(
            buy_route_payload, selected_surface_pool=selected_surface_pool,
        )
        self.store.record_execution_route_observation(
            lane=Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
            quote_key=str(item["quote_key"]), token_id=str(item.get("token_id") or snapshot.token_id),
            direction="BUY", classification=buy_route, observed_at=utcnow(),
        )
        sell_preflight: dict[str, Any] = {}
        acquired_raw = int(buy_result.get("other_amount_threshold") or 0)
        if buy_status == "quoted" and acquired_raw > 0:
            provider_request_limit = int(
                shared_budget.get("provider_request_limit", 3)
            )
            if (
                shared_budget["provider_requests"] < provider_request_limit
                and self._jupiter_background_epoch_requests < 3
            ):
                shared_budget["provider_requests"] += 1
                self._jupiter_background_epoch_requests += 1
                try:
                    async with self._jupiter_quote_lock:
                        sell_result = await self.jupiter.quote(
                            str(item["output_mint"]),
                            str(item["input_mint"]),
                            acquired_raw,
                            slippage_bps=int(item.get("slippage_bps") or round(
                                float(self.config["paper"].get("slippage_rate", 0.04)) * 10_000
                            )),
                        )
                except JupiterNoRouteError:
                    sell_preflight = {"status": "no_route", "input_amount_raw": acquired_raw}
                except Exception as exc:
                    sell_preflight = {
                        "status": "error", "input_amount_raw": acquired_raw,
                        "error_type": type(exc).__name__,
                    }
                else:
                    minimum_raw = int(sell_result.get("other_amount_threshold") or 0)
                    fixed_fee = float(
                        self.config["paper"].get("fixed_fee_usd_each_side", 0.0) or 0.0
                    )
                    sell_preflight = {
                        "status": "quoted",
                        "input_amount_raw": acquired_raw,
                        "output_amount_raw": int(sell_result.get("output_amount_raw") or 0),
                        "minimum_output_raw": minimum_raw,
                        "minimum_output_usd": minimum_raw / 1_000_000.0,
                        "net_recovery_usd": minimum_raw / 1_000_000.0 - fixed_fee,
                        "fixed_fee_usd": fixed_fee,
                        "router": str(sell_result.get("router") or ""),
                        "price_impact_bps": sell_result.get("price_impact_bps"),
                        "route_plan": sell_result.get("route_plan") or [],
                    }
            else:
                sell_preflight = {"status": "budget_deferred", "input_amount_raw": acquired_raw}
        if sell_preflight:
            sell_route_payload = {
                **sell_preflight,
                "input_mint": str(item["output_mint"]),
                "output_mint": str(item["input_mint"]),
                "output_amount_raw": str(sell_preflight.get("output_amount_raw") or ""),
                "other_amount_threshold": str(sell_preflight.get("minimum_output_raw") or ""),
            }
            sell_route = self.safety.classify_jupiter_route_truth(
                sell_route_payload, selected_surface_pool=selected_surface_pool,
            )
            entry_debit = int(item["input_amount_raw"]) / 1_000_000.0 + float(
                self.config["paper"].get("fixed_fee_usd_each_side", 0.0) or 0.0
            )
            exit_fee = float(self.config["paper"].get("fixed_fee_usd_each_side", 0.0) or 0.0)
            if entry_debit > 0 and str(sell_preflight.get("status")) == "quoted":
                sell_route["quoted_net_recovery_ratio"] = (
                    int(sell_preflight.get("output_amount_raw") or 0) / 1_000_000.0 - exit_fee
                ) / entry_debit
                sell_route["stress_min_recovery_ratio"] = (
                    int(sell_preflight.get("minimum_output_raw") or 0) / 1_000_000.0 - exit_fee
                ) / entry_debit
            self.store.record_execution_route_observation(
                lane=Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
                quote_key=str(item["quote_key"]),
                token_id=str(item.get("token_id") or snapshot.token_id), direction="SELL",
                classification=sell_route, observed_at=utcnow(),
            )
        assessment = self.safety.solana_pretrade_rug_assessment(
            snapshot, exact_sell_preflight=sell_preflight or None,
        )
        self.store.record_pretrade_rug_safety_assessment(
            lane=Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
            quote_key=str(item["quote_key"]),
            token_id=str(item.get("token_id") or snapshot.token_id),
            trigger_snapshot_id=int(item["baseline_snapshot_id"]),
            assessed_snapshot_id=assessed_snapshot_id,
            assessment=assessment,
            observed_at=utcnow(),
        )

    async def _token_universe_jupiter_quote_once_unlocked(
        self,
        *,
        budget: dict[str, int] | None = None,
        include_universe: bool = True,
        include_onchain: bool = True,
        include_kol: bool = True,
    ) -> None:
        """Share quote-only requests across universe and trigger-anchored lanes."""
        shared = budget if budget is not None else {"provider_requests": 0, "gap_records": 0}
        shared.setdefault("provider_requests", 0)
        shared.setdefault("gap_records", 0)
        shared.setdefault(
            "provider_request_limit",
            2 if self.chain_meme_trader_only and include_onchain
            and not include_universe and not include_kol else 3,
        )
        universe_tasks: list[dict[str, Any]] = []
        onchain_tasks: list[dict[str, Any]] = []
        kol_tasks: list[dict[str, Any]] = []
        if include_universe:
            self.store.finalize_token_universe_jupiter_quote_validity_gaps(limit=12)
            universe_tasks = self.store.due_token_universe_jupiter_quotes(limit=10_000)
        if include_onchain:
            onchain_tasks = self.store.due_onchain_only_jupiter_quotes(limit=10_000)
        if include_kol:
            self.store.refresh_kol_token_addressability_evidence()
            kol_tasks = self.store.due_kol_token_addressability_routes(limit=1)
        requestable: list[dict[str, Any]] = []

        def universe_preflight_reason(item: Mapping[str, Any], evaluated_at: Any) -> str | None:
            source_times = (
                item.get("source_observed_at"), item.get("source_ingested_at"),
                item.get("source_recorded_at"),
            )
            if not all(source_times):
                return "source_time_invalid"
            observed, ingested, recorded = map(parse_time, source_times)
            evaluated = parse_time(evaluated_at)
            if not (
                observed <= ingested <= recorded
                and parse_time(item["anchor_at"]) <= recorded <= evaluated
            ):
                return "source_time_invalid"
            if (
                evaluated - parse_time(item["anchor_at"])
            ).total_seconds() > float(item["max_queue_delay_seconds"]):
                return "queue_delay_expired"
            return None

        def record_gap(item: Mapping[str, Any], reason: str, evaluated_at: Any) -> None:
            if shared["gap_records"] >= 12:
                return
            shared["gap_records"] += 1
            if item.get("lane") == Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION:
                interrupted = reason == "request_evidence_missing"
                self.store.record_onchain_only_jupiter_quote(
                    item,
                    status="interrupted_after_request" if interrupted else "not_requested",
                    attempt_id=item.get("attempt_id") if interrupted else None,
                    evaluated_at=evaluated_at,
                )
            else:
                self.store.record_token_universe_jupiter_quote_validity(
                    item, status="not_requested", evaluated_at=evaluated_at,
                )

        for item in onchain_tasks:
            now = utcnow()
            reason = Store.onchain_only_jupiter_preflight_reason(item, evaluated_at=now)
            if reason:
                record_gap(item, reason, now)
            else:
                requestable.append(dict(item))
        for item in universe_tasks:
            now = utcnow()
            reason = universe_preflight_reason(item, now)
            if reason:
                record_gap(item, reason, now)
            else:
                requestable.append(dict(item))
        for item in kol_tasks:
            candidate = dict(item)
            candidate["lane"] = Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION
            requestable.append(candidate)

        requestable.sort(key=lambda item: (
            parse_time(item["deadline_at"])
            if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION
            else parse_time(item["anchor_at"])
                + timedelta(seconds=float(item["max_queue_delay_seconds"])),
            0 if item.get("lane") == Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION
            else 1 if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION else 2,
            int(item.get("shadow_cohort_id") or item.get("cohort_id") or 0),
            str(item.get("phase") or ""),
        ))
        kol_sent = False
        for item in requestable:
            if shared["provider_requests"] >= shared["provider_request_limit"]:
                break
            loop_now = asyncio.get_running_loop().time()
            if (
                loop_now - self._jupiter_background_epoch_started
                >= self._jupiter_background_epoch_seconds
            ):
                self._jupiter_background_epoch_started = loop_now
                self._jupiter_background_epoch_requests = 0
            if self._jupiter_background_epoch_requests >= 3:
                break
            if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION and kol_sent:
                continue
            requested_at = utcnow()
            if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION:
                reason = (
                    "queue_delay_expired"
                    if requested_at > parse_time(item["deadline_at"])
                    else None
                )
            elif item.get("lane") == Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION:
                reason = Store.onchain_only_jupiter_preflight_reason(
                    item, evaluated_at=requested_at
                )
            else:
                reason = universe_preflight_reason(item, requested_at)
            if reason:
                if item.get("lane") != Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION:
                    record_gap(item, reason, requested_at)
                continue
            attempt_id = None
            if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION:
                attempt_id = self.store.start_kol_token_addressability_route_attempt(
                    item, requested_at=requested_at
                )
                if attempt_id is None:
                    continue
                kol_sent = True
            elif item.get("lane") == Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION:
                attempt_id = self.store.start_onchain_only_jupiter_quote_attempt(
                    item, requested_at=requested_at
                )
                if attempt_id is None:
                    continue
            shared["provider_requests"] += 1
            self._jupiter_background_epoch_requests += 1
            status = "quoted"
            result: dict[str, Any] = {}
            error_type = ""
            try:
                async with self._jupiter_quote_lock:
                    result = await self.jupiter.quote(
                        str(item["input_mint"]),
                        str(item["output_mint"]),
                        int(item["input_amount_raw"]),
                        slippage_bps=int(item.get("slippage_bps") or round(
                            float(self.config["paper"].get("slippage_rate", 0.04)) * 10_000
                        )),
                    )
            except JupiterNoRouteError:
                status = "no_route"
            except JupiterQuoteProtocolError as exc:
                status, error_type = "quote_only_protocol_invalid", type(exc).__name__
            except Exception as exc:
                status, error_type = "error", type(exc).__name__
            completed_at = utcnow()
            payload = {
                "status": status,
                "out_amount_raw": result.get("output_amount_raw"),
                "other_amount_threshold_raw": result.get("other_amount_threshold"),
                "slippage_bps": result.get("slippage_bps"),
                "router": str(result.get("router") or ""),
                "mode": str(result.get("mode") or ""),
                "fee_bps": result.get("fee_bps"),
                "platform_fee_bps": result.get("platform_fee_bps"),
                "price_impact_pct": result.get("price_impact_pct"),
                "price_impact_bps": result.get("price_impact_bps"),
                "price_impact_source": result.get("price_impact_source"),
                "signature_fee_lamports": result.get("signature_fee_lamports"),
                "prioritization_fee_lamports": result.get("prioritization_fee_lamports"),
                "rent_fee_lamports": result.get("rent_fee_lamports"),
                "route_plan": result.get("route_plan") or [],
                "context_slot": result.get("context_slot"),
                "time_taken_ms": result.get("time_taken_ms"),
                "error_type": error_type,
            }
            if item.get("lane") == Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION:
                self.store.record_kol_token_addressability_route_result(
                    item, attempt_id=int(attempt_id), status=status,
                    evaluated_at=completed_at,
                    completed_at=result.get("completed_at") or completed_at,
                    result=result, error_type=error_type,
                )
            elif item.get("lane") == Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION:
                await self._record_onchain_pretrade_rug_safety(
                    item,
                    buy_status=status,
                    buy_result=result,
                    shared_budget=shared,
                )
                self.store.record_onchain_only_jupiter_quote(
                    item,
                    **payload,
                    attempt_id=attempt_id,
                    requested_at=requested_at,
                    completed_at=result.get("completed_at") or completed_at,
                    apply_legacy_exploration=not self.chain_meme_trader_only,
                )
            else:
                self.store.record_token_universe_jupiter_quote_validity(
                    item,
                    **payload,
                    requested_at=result.get("requested_at") or requested_at,
                    completed_at=result.get("completed_at") or completed_at,
                )

    def _route_preflight_deferred_retry_has_priority_work(self) -> bool:
        """Keep executable exits ahead without letting routine work starve the Shadow."""
        if self._critical_onchain_exit_event.is_set():
            return True
        if self.store.due_onchain_paper_exit_challenger_quotes(limit=1):
            return True
        for version in (
            Store.CHAIN_MEME_TRADER_VERSION,
            Store.CHAIN_MEME_TRADER_STAGE4_EXEC_DECAY_VERSION,
        ):
            execution = self.store.due_chain_meme_trader_execution(
                definition_version=version
            )
            if execution is not None and str(execution.get("side")) == "SELL":
                return True
        return False

    async def _dispatch_route_preflight_deferred_retry_shadow_once(self) -> bool:
        """Use one otherwise-idle background slot; never alter the source decision."""
        self.store.enroll_route_preflight_deferred_retry_shadow()
        due = self.store.due_route_preflight_deferred_retry_shadow(limit=1)
        if not due:
            return False
        case = due[0]
        now = utcnow()
        if now > parse_time(case["deadline_at"]):
            self.store.record_route_preflight_deferred_retry_shadow_result(
                int(case["id"]), status="expired_before_request", completed_at=now,
            )
            return True
        if self._route_preflight_deferred_retry_has_priority_work():
            return True
        async with self._jupiter_background_dispatch_lock:
            loop_now = asyncio.get_running_loop().time()
            if (
                loop_now - self._jupiter_background_epoch_started
                >= self._jupiter_background_epoch_seconds
            ):
                self._jupiter_background_epoch_started = loop_now
                self._jupiter_background_epoch_requests = 0
            if self._jupiter_background_epoch_requests >= 3:
                return True
            requested_at = utcnow()
            if requested_at > parse_time(case["deadline_at"]):
                self.store.record_route_preflight_deferred_retry_shadow_result(
                    int(case["id"]), status="expired_before_request",
                    completed_at=requested_at,
                )
                return True
            attempt_id = self.store.start_route_preflight_deferred_retry_shadow_attempt(
                case, requested_at=requested_at,
            )
            if attempt_id is None:
                return True
            self._jupiter_background_epoch_requests += 1
            status = "quoted"
            result: dict[str, Any] = {}
            error_type = ""
            try:
                async with self._jupiter_quote_lock:
                    result = await self.jupiter.quote(
                        str(case["input_mint"]), str(case["output_mint"]),
                        int(case["input_amount_raw"]),
                        slippage_bps=int(case["slippage_bps"]),
                    )
            except JupiterNoRouteError:
                status = "no_route"
            except JupiterQuoteProtocolError as exc:
                status, error_type = "quote_only_protocol_invalid", type(exc).__name__
            except Exception as exc:
                status, error_type = "error", type(exc).__name__
            completed_at = result.get("completed_at") or utcnow()
            route_classification: dict[str, Any] = {}
            if status == "quoted":
                route_classification = self.safety.classify_jupiter_route_truth(
                    {
                        **result,
                        "input_mint": str(case["input_mint"]),
                        "output_mint": str(case["output_mint"]),
                        "input_amount_raw": str(case["input_amount_raw"]),
                    },
                    selected_surface_pool=str(case["selected_surface_pool"] or ""),
                )
            self.store.record_route_preflight_deferred_retry_shadow_result(
                int(case["id"]), attempt_id=int(attempt_id), status=status,
                result=result, route_classification=route_classification,
                error_type=error_type, completed_at=completed_at,
            )
            return True

    async def onchain_only_jupiter_quote_once(self) -> None:
        if await self._dispatch_route_preflight_deferred_retry_shadow_once():
            return
        await self.token_universe_jupiter_quote_once(
            include_universe=False,
            include_onchain=True,
            include_kol=not self.chain_meme_trader_only,
        )

    async def token_information_watch_once(self) -> None:
        """Run one forward Token-first observer WATCH; it has no entry authority."""
        if self.strategy_focus_active:
            self.store.finalize_token_information_watches()
            return
        self.store.enroll_token_information_watches()
        self.store.finalize_token_information_watches()
        due = self.store.due_token_information_watches(limit=1)
        if not due:
            return
        watch = due[0]
        token = self.store.token(str(watch["token_id"]))
        snapshot = self.store.latest_snapshot(
            str(watch["token_id"]), at_or_before=watch["watch_started_at"]
        )
        if token is None or snapshot is None:
            return
        trigger = {
            "kind": "pre_entry_token_watch",
            "priority": 2,
            "transition_id": int(watch["trigger_transition_id"]),
            "shadow_cohort_id": int(watch["shadow_cohort_id"]),
            "watch_started_at": str(watch["watch_started_at"]),
            "decision_deadline_at": str(watch["decision_deadline_at"]),
            "selection_path": "strategy3_pre_entry_watch",
            "decision_eligible": False,
            "endorsement_inferred": False,
        }
        await self._investigate_token_context(
            token, snapshot,
            momentum_score=CandidateEvaluator._momentum_score(snapshot),
            event_relation=trigger,
        )
        self.store.finalize_token_information_watches()
        self.store.heartbeat("token-information-watch", item=True)

    async def onchain_only_evm_route_quote_once(self) -> None:
        """Observe one post-registration EVM cohort without mutating any strategy."""
        if self.strategy_focus_active:
            return
        requestable: dict[str, Any] | None = None
        for item in self.store.due_onchain_only_evm_route_quotes(limit=12):
            evaluated_at = utcnow()
            reason = Store.onchain_only_evm_route_preflight_reason(
                item, evaluated_at=evaluated_at
            )
            if reason:
                interrupted = reason == "request_evidence_missing"
                self.store.record_onchain_only_evm_route_quote(
                    item,
                    status="interrupted_after_request" if interrupted else "not_requested",
                    attempt_id=item.get("attempt_id") if interrupted else None,
                    evaluated_at=evaluated_at,
                )
                continue
            requestable = item
            break
        if requestable is None:
            return
        requested_at = utcnow()
        attempt_id = self.store.start_onchain_only_evm_route_quote_attempt(
            requestable, requested_at=requested_at
        )
        if attempt_id is None:
            return
        status = "quoted"
        result: dict[str, Any] = {}
        error_type = ""
        try:
            async with self._evm_route_quote_lock:
                result = await self.evm_route.quote_round_trip(
                    str(requestable["chain"]),
                    str(requestable["output_token"]),
                    int(requestable["input_amount_raw"]),
                    slippage_bps=int(requestable["slippage_bps"]),
                )
            status = str(result["status"])
        except EvmRouteQuoteProtocolError as exc:
            status, error_type = "quote_only_protocol_invalid", type(exc).__name__
        except EvmRouteQuoteError as exc:
            status, error_type = "error", type(exc).__name__
        except Exception as exc:
            status, error_type = "error", type(exc).__name__
        completed_at = parse_time(result.get("completed_at") or utcnow())
        result_id = self.store.record_onchain_only_evm_route_quote(
            requestable,
            status=status,
            result=result,
            error_type=error_type,
            attempt_id=attempt_id,
            requested_at=requested_at,
            completed_at=completed_at,
        )
        self.store.heartbeat(
            f"uniswap-v3:{requestable['chain']}",
            item=result_id is not None,
            error=error_type if status in {"error", "quote_only_protocol_invalid"} else "",
        )

    async def onchain_only_evm_aggregator_price_once(self) -> None:
        """Observe one new BSC/Robinhood cohort through 0x when configured."""
        if self.strategy_focus_active:
            return
        if self.evm_aggregator is None:
            return
        requestable: dict[str, Any] | None = None
        for item in self.store.due_onchain_only_evm_aggregator_prices(limit=12):
            reason = str(item.get("preflight_reason") or "")
            if reason:
                self.store.record_onchain_only_evm_aggregator_price(
                    item,
                    terminal_status=(
                        "interrupted_after_request"
                        if reason == "request_evidence_missing" else "not_requested"
                    ),
                    attempt_id=item.get("attempt_id"),
                    requested_at=item.get("attempt_requested_at") or utcnow(),
                    completed_at=utcnow(),
                )
                continue
            requestable = item
            break
        if requestable is None:
            return
        requested_at = utcnow()
        attempt_id = self.store.start_onchain_only_evm_aggregator_price_attempt(
            requestable, requested_at=requested_at
        )
        if attempt_id is None:
            return
        result: dict[str, Any] = {}
        status, error_type = "error", ""
        try:
            async with self._evm_route_quote_lock:
                result = await self.evm_aggregator.price(
                    str(requestable["chain"]),
                    str(requestable["sell_token"]),
                    str(requestable["buy_token"]),
                    str(requestable["sell_amount_raw"]),
                    slippage_bps=int(requestable["slippage_bps"]),
                )
            status = str(result["status"])
        except EvmRouteQuoteProtocolError as exc:
            status, error_type = "protocol_invalid", type(exc).__name__
        except Exception as exc:
            status, error_type = "error", type(exc).__name__
        result_id = self.store.record_onchain_only_evm_aggregator_price(
            requestable,
            terminal_status=status,
            result=result,
            attempt_id=attempt_id,
            requested_at=result.get("requested_at") or requested_at,
            completed_at=result.get("completed_at") or utcnow(),
            error_type=error_type,
        )
        self.store.heartbeat(
            f"0x-price:{requestable['chain']}",
            item=result_id is not None,
            error=error_type if status in {"error", "protocol_invalid"} else "",
        )

    async def robinhood_stock_token_registry_once(self) -> None:
        """Refresh the official exact-address exclusion registry."""
        result = await self.robinhood_stock_tokens.fetch()
        run_id = self.store.record_robinhood_stock_token_registry(result)
        self.store.heartbeat("robinhood-stock-token-registry", item=run_id is not None)

    async def _dispatch_onchain_exit_quote_once(self, *, critical_only: bool = False) -> bool:
        """Dispatch one real exit quote; exact account alerts bypass background quota."""
        async with self._onchain_exit_dispatch_lock:
            tasks = self.store.due_onchain_paper_exit_challenger_quotes(limit=1)
            if not tasks:
                return False
            item = tasks[0]
            if critical_only and not str(item.get("reason") or "").startswith(
                "onchain_rug_alert:"
            ):
                return False
            async with self._jupiter_background_dispatch_lock:
                loop_now = asyncio.get_running_loop().time()
                if (
                    loop_now - self._jupiter_background_epoch_started
                    >= self._jupiter_background_epoch_seconds
                ):
                    self._jupiter_background_epoch_started = loop_now
                    self._jupiter_background_epoch_requests = 0
                if not critical_only and self._jupiter_background_epoch_requests >= 3:
                    return False
                requested_at = utcnow()
                attempt_id = self.store.start_onchain_paper_exit_challenger_quote_attempt(
                    item, requested_at=requested_at
                )
                if attempt_id is None:
                    return False
                self._jupiter_background_epoch_requests += 1
                status = "quoted"
                result: dict[str, Any] = {}
                error_type = ""
                try:
                    async with self._jupiter_quote_lock:
                        result = await self.jupiter.quote(
                            str(item["input_mint"]),
                            str(item["output_mint"]),
                            int(item["input_amount_raw"]),
                            slippage_bps=int(item["slippage_bps"]),
                        )
                except JupiterNoRouteError:
                    status = "no_route"
                except JupiterQuoteProtocolError as exc:
                    status, error_type = "quote_only_protocol_invalid", type(exc).__name__
                except Exception as exc:
                    status, error_type = "error", type(exc).__name__
                completed_at = result.get("completed_at") or utcnow()
                self.store.record_onchain_paper_exit_challenger_quote_result(
                    item,
                    attempt_id=int(attempt_id),
                    status=status,
                    output_amount_raw=result.get("output_amount_raw"),
                    other_amount_threshold_raw=result.get("other_amount_threshold"),
                    slippage_bps=result.get("slippage_bps"),
                    signature_fee_lamports=result.get("signature_fee_lamports"),
                    prioritization_fee_lamports=result.get("prioritization_fee_lamports"),
                    rent_fee_lamports=result.get("rent_fee_lamports"),
                    router=str(result.get("router") or ""),
                    mode=str(result.get("mode") or ""),
                    fee_bps=result.get("fee_bps"),
                    platform_fee_bps=result.get("platform_fee_bps"),
                    price_impact_pct=result.get("price_impact_pct"),
                    price_impact_bps=result.get("price_impact_bps"),
                    price_impact_source=str(result.get("price_impact_source") or ""),
                    route_plan=result.get("route_plan") or [],
                    error_type=error_type,
                    completed_at=completed_at,
                )
                return True

    async def held_account_loop(self) -> None:
        """Maintain exact held-account subscriptions and trigger immediate exit truth."""
        while not self._stop.is_set():
            self.store.enroll_onchain_held_account_targets()
            try:
                async for update in self.held_accounts.stream(
                    self.store.onchain_held_account_targets
                ):
                    outcome = self.store.record_onchain_held_account_update(update)
                    self.store.heartbeat(
                        "solana-held-accounts",
                        item=bool(outcome and outcome.get("event_id")),
                        error="",
                    )
                    if outcome and outcome.get("alert_mark_id"):
                        self._critical_onchain_exit_event.set()
                    if self._stop.is_set():
                        return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.store.heartbeat(
                    "solana-held-accounts", item=False, error=type(exc).__name__
                )
                await asyncio.sleep(30 if type(exc).__name__ == "InvalidStatus" else 5)

    async def chain_meme_v21_vault_shadow_enroll_once(
        self, *, v22: bool = False,
    ) -> None:
        """Resolve new runner pools and keep only active observer rings."""
        now = asyncio.get_running_loop().time()
        candidate_pool_rows = (
            self.store.chain_meme_v22_vault_shadow_candidates()
            if v22 else self.store.chain_meme_v21_vault_shadow_candidates()
        )
        candidates = [
            item for item in candidate_pool_rows
            if self._chain_meme_v21_vault_retry_after.get(
                str(item["pool_address"]), 0.0
            ) <= now
        ]
        resolved = await self.held_accounts.resolve_pumpswap_shadow_pools(candidates)
        inserted = 0
        unresolved = 0
        for outcome in resolved:
            if v22:
                self.store.record_chain_meme_v22_vault_shadow_resolution(outcome)
                target_id = self.store.add_chain_meme_v22_vault_shadow_target(outcome)
            else:
                self.store.record_chain_meme_v21_vault_shadow_resolution(outcome)
                target_id = self.store.add_chain_meme_v21_vault_shadow_target(outcome)
            if target_id is not None:
                inserted += 1
                self._chain_meme_v21_vault_retry_after.pop(
                    str(outcome["pool_address"]), None
                )
            elif str(outcome.get("status") or "") != "RESOLVED":
                unresolved += 1
                self._chain_meme_v21_vault_retry_after[
                    str(outcome["pool_address"])
                ] = now + 60.0
        active = (
            self.store.chain_meme_v22_vault_shadow_account_targets()
            if v22 else self.store.chain_meme_v21_vault_shadow_account_targets()
        )
        active_pools = {str(item["pool_address"]) for item in active}
        candidate_pools = {
            str(item["pool_address"]) for item in candidate_pool_rows
        }
        self._chain_meme_v21_vault_retry_after = {
            pool: retry_at
            for pool, retry_at in self._chain_meme_v21_vault_retry_after.items()
            if pool in active_pools or pool in candidate_pools
        }
        self.chain_meme_v21_vault_tracker.retain(
            int(item["pool_target_id"]) for item in active
        )
        self.store.heartbeat(
            f"chain-meme-v{22 if v22 else 21}-vault-shadow-enroll",
            item=bool(inserted or active),
            error="",
            error_detail=f"resolved={inserted};unresolved={unresolved}",
        )

    async def chain_meme_v22_vault_shadow_enroll_once(self) -> None:
        await self.chain_meme_v21_vault_shadow_enroll_once(v22=True)

    def chain_meme_combined_vault_targets(self) -> list[dict[str, Any]]:
        """One physical subscription per address, separate logical observers."""
        targets = self.store.chain_meme_v22_vault_shadow_account_targets()
        for row in self._pattern_pool_targets.values():
            common = {**row, "pool_target_id": row["evidence_id"],
                      "observer_version": "chain-pattern-exact/v1",
                      "decoder_version": "pump-amm-pool/v2-idl-6b5c7e-sdk-1.19.0"}
            for number, kind, pubkey, mint, program in (
                (1, "pool", row["pool_address"], "", self.store.PUMPSWAP_PROGRAM_ID),
                (2, "base_vault", row["base_vault"], row["base_mint"], row["base_token_program"]),
                (3, "quote_vault", row["quote_vault"], row["quote_mint"], row["quote_token_program"]),
            ):
                targets.append({**common, "id": -(row["evidence_id"] * 10 + number),
                    "account_kind": kind, "pubkey": pubkey, "expected_mint": mint,
                    "expected_program_owner": program})
        return targets

    async def chain_meme_pattern_pools_once(self) -> None:
        """Bounded pre-entry Pool/Vault verification, never a trade/exit authority."""
        await self._chain_meme_active_idle().wait()
        watch = getattr(self, "_pattern_watch", {})
        pool_map = {v["pair_address"]: v for v in watch.values()
                    if v["token"].chain == "solana" and v["expires_at"] > utcnow()}
        self._pattern_pool_targets = {k: v for k, v in self._pattern_pool_targets.items() if k in pool_map}
        self._pattern_pool_retry = {k: v for k, v in self._pattern_pool_retry.items() if k in pool_map}
        self._pattern_vault_tracker.retain(v["evidence_id"] for v in self._pattern_pool_targets.values())
        now = asyncio.get_running_loop().time()
        candidates = []
        for address, item in pool_map.items():
            if len(self._pattern_pool_targets) + len(candidates) >= 6 or len(candidates) >= 2:
                break
            if address in self._pattern_pool_targets or self._pattern_pool_retry.get(address, 0) > now:
                continue
            raw = item["quote"].raw or {}
            pairs = raw.get("pairs") or [raw.get("pair", raw)]
            exact = next((p for p in pairs if str(p.get("pairAddress")) == address), None)
            if exact is None or str(exact.get("dexId") or "").lower() not in {"pumpswap", "pump-amm"}:
                continue
            try:
                Pubkey.from_string(address)
            except ValueError:
                continue
            candidates.append({"pool_address": address, "base_mint": item["token"].address,
                "token_id": item["token"].token_id, "quote_observed_at": iso(item["quote"].observed_at),
                "observer_version": "chain-pattern-exact/v1"})
            self._pattern_pool_retry[address] = now + 60
        if not candidates:
            return
        try:
            outcomes = await asyncio.wait_for(self.held_accounts.resolve_pumpswap_shadow_pools(candidates), timeout=5)
        except TimeoutError:
            outcomes = [{**c, "status": "UNKNOWN_RPC", "reason": "pattern_rpc_budget_timeout"} for c in candidates]
        for outcome in outcomes:
            received = utcnow()
            evidence_id = self.store.record_chain_meme_pattern_evidence(outcome["token_id"], outcome["pool_address"],
                "pool_resolution", outcome, observed_at=received,
                source_key=f"{outcome['pool_address']}:{iso(received)}")
            if outcome.get("status") == "RESOLVED" and evidence_id is not None:
                self._pattern_pool_targets[outcome["pool_address"]] = {**outcome, "evidence_id": evidence_id}
        self.store.heartbeat("chain-meme-pattern-pools", item=bool(self._pattern_pool_targets),
            error_detail=f"active={len(self._pattern_pool_targets)};attempted={len(candidates)}")

    async def chain_meme_v21_vault_shadow_loop(
        self, *, v22: bool = False,
    ) -> None:
        """Record bounded Pool/Vault flow summaries with no trading authority."""
        while not self._stop.is_set():
            try:
                async for update in self.held_accounts.stream(
                    (
                        self.chain_meme_combined_vault_targets
                        if v22 else self.store.chain_meme_v21_vault_shadow_account_targets
                    )
                ):
                    if update.get("observer_version") == "chain-pattern-exact/v1":
                        frame = self._pattern_vault_tracker.push(update)
                        if frame is not None:
                            self.store.record_chain_meme_pattern_evidence(update["token_id"], update["pool_address"],
                                "vault_frame", frame, observed_at=frame["observed_at"],
                                source_key=f"{update['pool_target_id']}:{frame['observed_at']}:{frame['observer_state']}")
                        continue
                    frame = self.chain_meme_v21_vault_tracker.push(update)
                    frame_id = (
                        (
                            self.store.record_chain_meme_v22_vault_shadow_frame(frame)
                            if v22
                            else self.store.record_chain_meme_v21_vault_shadow_frame(frame)
                        )
                        if frame is not None else None
                    )
                    now = asyncio.get_running_loop().time()
                    if (
                        frame_id is not None
                        or now - self._chain_meme_v21_vault_last_heartbeat >= 10.0
                    ):
                        self.store.heartbeat(
                            f"chain-meme-v{22 if v22 else 21}-vault-shadow",
                            item=frame_id is not None,
                            error="",
                        )
                        self._chain_meme_v21_vault_last_heartbeat = now
                    if self._stop.is_set():
                        return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.store.heartbeat(
                    f"chain-meme-v{22 if v22 else 21}-vault-shadow",
                    item=False,
                    error=type(exc).__name__,
                    error_detail=str(exc),
                )
                await asyncio.sleep(5)

    async def chain_meme_v22_vault_shadow_loop(self) -> None:
        await self.chain_meme_v21_vault_shadow_loop(v22=True)

    async def chain_meme_local_surface_once(self) -> None:
        """Refresh route-verified PumpSwap or fallback Pump-curve capacity."""
        targets = self.store.chain_meme_trader_local_surface_targets()
        if not targets:
            self.store.heartbeat("chain-meme-local-surface", item=False, error="")
            return
        loop_now = asyncio.get_running_loop().time()
        if (
            self._wsol_usdc_conversion is None
            or loop_now - self._wsol_usdc_conversion_at >= 30.0
        ):
            try:
                async with self._jupiter_quote_lock:
                    conversion = await self.jupiter.quote(
                        SOLANA_WRAPPED_SOL_MINT,
                        SOLANA_USDC_MINT,
                        1_000_000_000,
                        slippage_bps=400,
                    )
                self._wsol_usdc_conversion = {
                    "input_amount_raw": 1_000_000_000,
                    "minimum_output_amount_raw": int(
                        conversion["other_amount_threshold"]
                    ),
                    "completed_at": str(conversion["completed_at"]),
                }
                self._wsol_usdc_conversion_at = asyncio.get_running_loop().time()
            except Exception:
                if loop_now - self._wsol_usdc_conversion_at >= 60.0:
                    self._wsol_usdc_conversion = None
        curve_targets = [
            item for item in targets
            if str(item.get("surface_type") or "") == "pump_bonding_curve"
        ]
        route_targets = [
            item for item in targets
            if str(item.get("surface_type") or "") != "pump_bonding_curve"
        ]
        quotes: list[dict[str, Any]] = []
        if curve_targets:
            quotes.extend(await self.held_accounts.bonding_curve_quotes(
                curve_targets,
                slippage_bps=400,
                wsol_usdc_conversion=self._wsol_usdc_conversion,
            ))
        if route_targets:
            route_quotes = await self.held_accounts.pumpswap_route_surface_quotes(
                route_targets, slippage_bps=400,
            )
            for quote in route_quotes:
                if (
                    quote.get("min_quote_raw") is not None
                    and str(quote.get("status") or "") == "LOCAL_SURFACE_CURRENT"
                ):
                    quote_mint = str(quote.get("quote_mint") or "")
                    if quote_mint == SOLANA_USDC_MINT:
                        quote["direct_estimated_recovery_usd"] = (
                            int(quote["min_quote_raw"]) / 1_000_000.0
                        )
                        quote["conversion_source"] = "direct_pumpswap_usdc_minimum"
                    elif quote_mint == SOLANA_WRAPPED_SOL_MINT and self._wsol_usdc_conversion:
                        conversion_input = int(
                            self._wsol_usdc_conversion["input_amount_raw"]
                        )
                        conversion_output = int(
                            self._wsol_usdc_conversion["minimum_output_amount_raw"]
                        )
                        if conversion_input > 0 and conversion_output > 0:
                            quote["direct_estimated_recovery_usd"] = (
                                int(quote["min_quote_raw"]) * conversion_output
                                / conversion_input / 1_000_000.0
                            )
                            quote["conversion_source"] = (
                                "route_verified_pumpswap_plus_shared_jupiter_wsol_usdc"
                            )
                            quote["conversion_input_raw"] = conversion_input
                            quote["conversion_min_usdc_raw"] = conversion_output
                            quote["conversion_completed_at"] = str(
                                self._wsol_usdc_conversion["completed_at"]
                            )
            quotes.extend(route_quotes)
        recorded = 0
        healthy = 0
        for quote in quotes:
            quote_id = self.store.record_chain_meme_trader_local_surface_quote(quote)
            recorded += int(quote_id is not None)
            if quote_id is not None:
                self.store.sync_chain_meme_trader_local_critical_exit(quote_id)
            healthy += int(not str(quote.get("status") or "").startswith("LOCAL_UNKNOWN"))
        self.store.heartbeat(
            "chain-meme-local-surface",
            item=healthy > 0,
            error=(
                str(quotes[0].get("status") or "local_surface_unknown")
                if quotes and healthy == 0 else ""
            ),
        )

    async def critical_onchain_exit_loop(self) -> None:
        """Drain exact-account risk exits before ordinary background quote work."""
        while not self._stop.is_set():
            await self._critical_onchain_exit_event.wait()
            self._critical_onchain_exit_event.clear()
            while await self._dispatch_onchain_exit_quote_once(critical_only=True):
                self.store.sync_onchain_paper_narrative_runner()
                self.store.record_onchain_paper_exit_challenger_account_snapshot()
                self.store.record_onchain_paper_position_monitor_account_snapshot()

    async def onchain_paper_exit_challenger_once(self) -> None:
        """Monitor paired Shadow positions locally and quote only triggered exits."""
        self.store.enroll_onchain_paper_exit_challenger()
        self.store.enroll_onchain_paper_narrative_runner()
        if self.strategy_focus_active:
            self.store.enroll_onchain_held_account_targets()
        for position in self.store.due_onchain_paper_exit_challenger_marks(limit=3):
            snapshot_id = None
            mark_reason = ""
            try:
                quoted = await self.dex.quote("solana", str(position["address"]))
            except Exception as exc:
                quoted = None
                mark_reason = f"dexscreener_{type(exc).__name__}"
            if quoted is not None:
                token, snapshot = quoted
                received_at = utcnow()
                rejections = self._paper_quote_rejections(
                    str(position["token_id"]), token, snapshot, received_at
                )
                if rejections:
                    mark_reason = "dexscreener_temporal_rejected:" + ",".join(rejections)
                else:
                    self.store.upsert_token(token, seen_at=snapshot.observed_at)
                    snapshot_id = self.store.add_snapshot(snapshot)
            elif not mark_reason:
                mark_reason = "dexscreener_pair_unavailable"
            self.store.record_onchain_paper_exit_challenger_mark(
                int(position["shadow_cohort_id"]),
                snapshot_id=snapshot_id,
                evaluated_at=utcnow(),
                reason=mark_reason,
            )

        dispatched = await self._dispatch_onchain_exit_quote_once()
        if not dispatched:
            await self.onchain_paper_position_monitor_once()
        self.store.sync_onchain_paper_narrative_runner()
        self.store.record_onchain_paper_exit_challenger_account_snapshot()
        self.store.record_onchain_paper_position_monitor_account_snapshot()

    async def chain_meme_trader_once(self) -> None:
        """Advance every active strictly-forward, zero-extra-fee strategy account."""
        if not self.chain_meme_trader_only:
            self.store.enroll_chain_meme_trader()
        enrollment_batches = 8 if self.chain_meme_trader_only else 1
        for _ in range(enrollment_batches):
            enrollment = self.store.enroll_chain_meme_trader_v6(
                limit=4 if self.chain_meme_trader_only else 240,
                definition_version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            )
            if not self.chain_meme_trader_only or int(enrollment["evaluated"]) < 4:
                break
            await asyncio.sleep(0)
        if not self.chain_meme_trader_only:
            self.store.enroll_chain_meme_trader_executable_decay()
            self.store.enroll_chain_meme_trader_stage4_v2()
            self.store.enroll_onchain_held_account_targets()
        legacy_positions = (
            [] if self.chain_meme_trader_only
            else self.store.due_chain_meme_trader_evaluations(limit=3)
        )
        for position in legacy_positions:
            snapshot_id = None
            mark_reason = ""
            try:
                quoted = await self.dex.quote("solana", str(position["address"]))
            except Exception as exc:
                quoted = None
                mark_reason = f"dexscreener_{type(exc).__name__}"
            if quoted is not None:
                token, snapshot = quoted
                received_at = utcnow()
                rejections = self._paper_quote_rejections(
                    str(position["token_id"]), token, snapshot, received_at
                )
                if rejections:
                    mark_reason = "dexscreener_temporal_rejected:" + ",".join(rejections)
                else:
                    self.store.upsert_token(token, seen_at=snapshot.observed_at)
                    snapshot_id = self.store.add_snapshot(snapshot)
            elif not mark_reason:
                mark_reason = "dexscreener_pair_unavailable"
            self.store.record_chain_meme_trader_evaluation(
                int(position["shadow_cohort_id"]), snapshot_id=snapshot_id,
                evaluated_at=utcnow(), reason=mark_reason,
            )
        if not self.chain_meme_trader_only:
            self.store.sync_chain_meme_trader_rug_alerts()
        primary_execution = (
            None if self.chain_meme_trader_only
            else self.store.due_chain_meme_trader_execution()
        )
        active_execution = self.store.due_chain_meme_trader_execution(
            definition_version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        )
        v11_execution = None if self.chain_meme_trader_only else (
            self.store.due_chain_meme_trader_execution(
                definition_version=self.store.CHAIN_MEME_TRADER_V11_VERSION,
            )
        )
        v10_execution = None if self.chain_meme_trader_only else (
            self.store.due_chain_meme_trader_execution(
                definition_version=self.store.CHAIN_MEME_TRADER_V10_VERSION,
            )
        )
        v2_execution = None if self.chain_meme_trader_only else (
            self.store.due_chain_meme_trader_execution(
                definition_version=self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_EQUITY_V2_VERSION,
            )
        )
        challenger_execution = None if self.chain_meme_trader_only else (
            self.store.due_chain_meme_trader_execution(
                definition_version=self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_DECAY_VERSION,
            )
        )
        execution_candidates = (
            active_execution, v11_execution, v10_execution, primary_execution, v2_execution,
            challenger_execution,
        )
        execution_task = next(
            (item for item in execution_candidates if item is not None and item["side"] == "SELL"),
            next((item for item in execution_candidates if item is not None), None),
        )
        quote_versions = (
            ()
            if self.chain_meme_trader_only
            else (
                self.store.CHAIN_MEME_TRADER_VERSION,
                self.store.CHAIN_MEME_TRADER_V11_VERSION,
                self.store.CHAIN_MEME_TRADER_V10_VERSION,
                self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_EQUITY_V2_VERSION,
                self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_DECAY_VERSION,
            )
        )
        task = None
        selected_quote_index = None
        for offset in range(len(quote_versions)):
            index = (self._chain_meme_quote_version_cursor + offset) % len(quote_versions)
            candidate = self.store.due_chain_meme_trader_quote(
                definition_version=quote_versions[index],
            )
            if candidate is not None:
                task = candidate
                selected_quote_index = index
                break
        quote_gets_next_slot = bool(
            task is not None
            and execution_task is not None
            and str(execution_task.get("side")) != "SELL"
            and self._chain_meme_normal_slot == 2
        )
        if execution_task is not None and not quote_gets_next_slot:
            async with self._jupiter_background_dispatch_lock:
                loop_now = asyncio.get_running_loop().time()
                if loop_now - self._jupiter_background_epoch_started >= self._jupiter_background_epoch_seconds:
                    self._jupiter_background_epoch_started = loop_now
                    self._jupiter_background_epoch_requests = 0
                if self._jupiter_background_epoch_requests < 3:
                    requested_at = utcnow()
                    attempt_id = self.store.start_chain_meme_trader_execution(
                        execution_task, requested_at=requested_at
                    )
                    if attempt_id is not None:
                        if str(execution_task.get("side")) != "SELL":
                            self._chain_meme_normal_slot = (
                                self._chain_meme_normal_slot + 1
                            ) % 3
                        self._jupiter_background_epoch_requests += 1
                        status = "quoted"
                        result: dict[str, Any] = {}
                        error_type = ""
                        try:
                            async with self._jupiter_quote_lock:
                                result = await self.jupiter.quote(
                                    str(execution_task["input_mint"]),
                                    str(execution_task["output_mint"]),
                                    int(execution_task["input_amount_raw"]),
                                    slippage_bps=int(execution_task["slippage_bps"]),
                                )
                        except JupiterNoRouteError:
                            status = "no_route"
                        except JupiterQuoteProtocolError as exc:
                            status, error_type = "quote_only_protocol_invalid", type(exc).__name__
                        except Exception as exc:
                            status, error_type = "error", type(exc).__name__
                        result_id = self.store.record_chain_meme_trader_execution_result(
                            int(attempt_id), status=status,
                            output_amount_raw=result.get("output_amount_raw"),
                            other_amount_threshold_raw=result.get("other_amount_threshold"),
                            slippage_bps=result.get("slippage_bps"),
                            route_plan=result.get("route_plan") or [],
                            error_type=error_type,
                            completed_at=result.get("completed_at") or utcnow(),
                        )
                        if result_id is not None:
                            self.store.settle_chain_meme_trader_execution_result(int(result_id))
        if task is not None and (execution_task is None or quote_gets_next_slot):
            quote_tasks = [
                task,
                *self.store.chain_meme_trader_quote_peer_tasks(task, quote_versions),
            ]
            frame_snapshot_id = None
            if any(
                str(item.get("definition_version"))
                == self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_EQUITY_V2_VERSION
                for item in quote_tasks
            ):
                try:
                    quoted = await self.dex.quote("solana", str(task["input_mint"]))
                except Exception:
                    quoted = None
                if quoted is not None:
                    token, snapshot = quoted
                    received_at = utcnow()
                    if not self._paper_quote_rejections(
                        f"solana:{task['input_mint']}", token, snapshot, received_at
                    ):
                        self.store.upsert_token(token, seen_at=snapshot.observed_at)
                        frame_snapshot_id = self.store.add_snapshot(snapshot)
            async with self._jupiter_background_dispatch_lock:
                loop_now = asyncio.get_running_loop().time()
                if loop_now - self._jupiter_background_epoch_started >= self._jupiter_background_epoch_seconds:
                    self._jupiter_background_epoch_started = loop_now
                    self._jupiter_background_epoch_requests = 0
                if self._jupiter_background_epoch_requests < 3:
                    requested_at = utcnow()
                    attempts = [
                        (item, attempt_id)
                        for item in quote_tasks
                        if (attempt_id := self.store.start_chain_meme_trader_quote(
                            item, requested_at=requested_at
                        )) is not None
                    ]
                    if attempts:
                        self._chain_meme_normal_slot = (
                            self._chain_meme_normal_slot + 1
                        ) % 3
                        if selected_quote_index is not None:
                            self._chain_meme_quote_version_cursor = (
                                selected_quote_index + 1
                            ) % len(quote_versions)
                        self._jupiter_background_epoch_requests += 1
                        status = "quoted"
                        result: dict[str, Any] = {}
                        error_type = ""
                        try:
                            async with self._jupiter_quote_lock:
                                result = await self.jupiter.quote(
                                    str(task["input_mint"]), str(task["output_mint"]),
                                    int(task["input_amount_raw"]),
                                    slippage_bps=int(task["slippage_bps"]),
                                )
                        except JupiterNoRouteError:
                            status = "no_route"
                        except JupiterQuoteProtocolError as exc:
                            status, error_type = "quote_only_protocol_invalid", type(exc).__name__
                        except Exception as exc:
                            status, error_type = "error", type(exc).__name__
                        completed_at = result.get("completed_at") or utcnow()
                        for quote_task, attempt_id in attempts:
                            quote_result_id = self.store.record_chain_meme_trader_quote_result(
                                int(attempt_id), status=status,
                                output_amount_raw=result.get("output_amount_raw"),
                                other_amount_threshold_raw=result.get("other_amount_threshold"),
                                slippage_bps=result.get("slippage_bps"),
                                route_plan=result.get("route_plan") or [],
                                error_type=error_type,
                                completed_at=completed_at,
                            )
                            if (
                                quote_result_id is not None
                                and str(quote_task.get("definition_version")) in {
                                    self.store.CHAIN_MEME_TRADER_V10_VERSION,
                                    self.store.CHAIN_MEME_TRADER_V11_VERSION,
                                }
                            ):
                                matrix_version = str(quote_task["definition_version"])
                                frame_id = self.store.record_chain_meme_trader_position_equity_frame(
                                    int(quote_result_id), snapshot_id=frame_snapshot_id,
                                    definition_version=matrix_version,
                                )
                                if frame_id is not None:
                                    self.store.evaluate_chain_meme_trader_stage4_v2_frame(
                                        frame_id, definition_version=matrix_version,
                                    )
                            elif (
                                quote_result_id is not None
                                and str(quote_task.get("definition_version"))
                                == self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_DECAY_VERSION
                            ):
                                self.store.evaluate_chain_meme_trader_executable_decay_quote(
                                    int(quote_result_id)
                                )
                            elif (
                                quote_result_id is not None
                                and str(quote_task.get("definition_version"))
                                == self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_EQUITY_V2_VERSION
                            ):
                                frame_id = self.store.record_chain_meme_trader_position_equity_frame(
                                    int(quote_result_id), snapshot_id=frame_snapshot_id,
                                )
                                if frame_id is not None:
                                    self.store.evaluate_chain_meme_trader_stage4_v2_frame(frame_id)
        if not self.chain_meme_trader_only:
            self.store.record_chain_meme_trader_account_snapshots()
        snapshot_clock = asyncio.get_running_loop().time()
        if (
            snapshot_clock - self._last_chain_account_snapshot_monotonic
            >= self.CHAIN_MEME_ACCOUNT_SNAPSHOT_INTERVAL_SECONDS
        ):
            self.store.record_chain_meme_trader_account_snapshots(
                definition_version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            )
            if (
                self.chain_meme_trader_only
                and self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION
                != self.store.CHAIN_MEME_TRADER_V20_VERSION
                and self.store.chain_meme_trader_has_open_positions(
                    self.store.CHAIN_MEME_TRADER_V20_VERSION
                )
            ):
                self.store.record_chain_meme_trader_account_snapshots(
                    definition_version=self.store.CHAIN_MEME_TRADER_V20_VERSION,
                )
            self._last_chain_account_snapshot_monotonic = snapshot_clock
        if not self.chain_meme_trader_only:
            self.store.record_chain_meme_trader_account_snapshots(
                definition_version=self.store.CHAIN_MEME_TRADER_V11_VERSION,
            )
            self.store.record_chain_meme_trader_account_snapshots(
                definition_version=self.store.CHAIN_MEME_TRADER_V10_VERSION,
            )
            self.store.finalize_chain_meme_trader_immediate_reverseability()
            self.store.record_chain_meme_trader_account_snapshots(
                definition_version=self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_DECAY_VERSION,
            )
            self.store.record_chain_meme_trader_account_snapshots(
                definition_version=self.store.CHAIN_MEME_TRADER_STAGE4_EXEC_EQUITY_V2_VERSION,
            )
        self.store.heartbeat("chain-meme-trader", item=True)

    async def _refresh_chain_meme_market_marks(
        self, targets: list[dict[str, Any]], *, heartbeat_name: str,
        high_priority: bool = False, observe_flat_breakout: bool = False,
        evaluate_version: str | None = None,
        evaluate_versions: list[str] | None = None,
    ) -> int:
        """Refresh a de-duplicated target set with fresh 30-token DEX batches."""
        targets_by_chain: dict[str, list[dict[str, Any]]] = {}
        for item in targets:
            targets_by_chain.setdefault(str(item["chain"]).lower(), []).append(item)
        batches = [
            (chain, chain_targets[start:start + 30])
            for chain, chain_targets in targets_by_chain.items()
            for start in range(0, len(chain_targets), 30)
        ]

        async def refresh_batch(
            chain: str, chunk: list[dict[str, Any]],
        ) -> int:
            batch_started = asyncio.get_running_loop().time()
            timing = getattr(self, "runtime_timing", None)
            if not high_priority:
                await self._chain_meme_active_idle().wait()
            try:
                quoted = await self._dex_batch_quote(
                    chain, [str(item["address"]) for item in chunk],
                    fresh=True, high_priority=high_priority,
                )
            except Exception as exc:
                if timing is not None:
                    timing.observe("held_fetch", asyncio.get_running_loop().time()-batch_started, failures=1)
                self.store.heartbeat(
                    heartbeat_name, error=type(exc).__name__,
                )
                failure_outcomes = [
                        {
                            "kind": "failure",
                            "token_id": str(item["token_id"]),
                            "failure_kind": type(exc).__name__,
                        }
                        for item in chunk
                    ]
                for item in chunk:
                    for pair_address in str(item.get("entry_pair_addresses") or "").split(","):
                        if pair_address:
                            failure_outcomes.append({
                                "kind": "pool_failure",
                                "token_id": str(item["token_id"]),
                                "pair_address": pair_address,
                                "chain": str(item["chain"]),
                                "failure_kind": type(exc).__name__,
                            })
                self.store.apply_chain_meme_trader_market_mark_batch(
                    failure_outcomes,
                    recorded_at=utcnow(),
                )
                return 0
            received_at = utcnow()
            apply_started = asyncio.get_running_loop().time()
            if timing is not None:
                timing.observe("held_fetch", apply_started-batch_started, items=len(chunk))
            outcomes = []
            for item in chunk:
                target_token_id = str(item["token_id"])
                target_chain = str(item["chain"]).strip().lower()
                target_address = str(item["address"])
                effective_token_id = (
                    f"{target_chain}:"
                    f"{canonical_token_address(target_chain, target_address)}"
                )
                result = quoted.get(target_token_id) or quoted.get(effective_token_id)
                if result is None:
                    outcomes.append({
                        "kind": "missing",
                        "token_id": target_token_id,
                        "chain": target_chain,
                        "address": target_address,
                    })
                    for pair_address in str(item.get("entry_pair_addresses") or "").split(","):
                        if pair_address:
                            outcomes.append({
                                "kind": "pool_missing", "token_id": target_token_id,
                                "pair_address": pair_address, "chain": target_chain,
                                "address": target_address,
                            })
                    continue
                token, snapshot = result
                raw = snapshot.raw if isinstance(snapshot.raw, dict) else {}
                pair = raw.get("pair") if isinstance(raw.get("pair"), dict) else raw
                pair_address = str(pair.get("pairAddress") or "").strip()
                expected_pairs = {
                    canonical_token_address(target_chain, value)
                    for value in str(item.get("entry_pair_addresses") or "").split(",")
                    if value
                }
                raw_pairs = (
                    raw.get("pairs") if isinstance(raw.get("pairs"), list) else [pair]
                ) if expected_pairs else []
                observed_pairs: set[str] = set()
                valid_pairs: set[str] = set()
                for raw_pair in raw_pairs:
                    if not isinstance(raw_pair, dict):
                        continue
                    raw_pair_address = str(raw_pair.get("pairAddress") or "").strip()
                    if not raw_pair_address:
                        continue
                    pair_key = canonical_token_address(target_chain, raw_pair_address)
                    observed_pairs.add(pair_key)
                    pool_token = DexScreenerClient._candidate(raw_pair)
                    pool_snapshot = DexScreenerClient._snapshot(raw_pair)
                    if pool_token is None or pool_snapshot is None:
                        continue
                    pool_snapshot.observed_at = snapshot.observed_at
                    pool_snapshot.ingested_at = snapshot.ingested_at
                    if (
                        float(pool_snapshot.price_usd or 0.0) <= 0.0
                        or (
                            pool_snapshot.liquidity_usd is not None
                            and float(pool_snapshot.liquidity_usd) < 0.0
                        )
                    ):
                        continue
                    if canonical_token_address(target_chain, pool_token.address) != canonical_token_address(
                        target_chain, target_address,
                    ):
                        continue
                    pool_token.address = canonical_token_address(target_chain, target_address)
                    pool_snapshot.address = pool_token.address
                    pool_rejections = self._paper_quote_rejections(
                        target_token_id, pool_token, pool_snapshot, received_at,
                    )
                    if pool_rejections:
                        continue
                    valid_pairs.add(pair_key)
                    outcomes.append({
                        "kind": "pool_visible", "token": pool_token,
                        "snapshot": pool_snapshot, "target_token_id": target_token_id,
                        "target_chain": target_chain, "target_address": target_address,
                    })
                for expected_pair in expected_pairs - valid_pairs:
                    outcomes.append({
                        "kind": "pool_failure" if expected_pair in observed_pairs else "pool_missing",
                        "token_id": target_token_id, "pair_address": expected_pair,
                        "chain": target_chain, "address": target_address,
                        "failure_kind": "DATA_REJECTED:ENTRY_POOL_INVALID",
                    })
                if (
                    not pair_address
                    or float(snapshot.price_usd or 0.0) <= 0.0
                    or (
                        snapshot.liquidity_usd is not None
                        and float(snapshot.liquidity_usd) < 0.0
                    )
                ):
                    outcomes.append({
                        "kind": "missing", "token_id": target_token_id,
                        "chain": target_chain, "address": target_address,
                    })
                    continue
                rejections = self._paper_quote_rejections(
                    target_token_id, token, snapshot, received_at,
                )
                if rejections:
                    outcomes.append({
                        "kind": "failure", "token_id": target_token_id,
                        "failure_kind": "DATA_REJECTED:" + ",".join(rejections),
                    })
                    continue
                outcomes.append({
                    "kind": "visible", "token": token, "snapshot": snapshot,
                    "target_token_id": target_token_id,
                    "target_chain": target_chain,
                    "target_address": target_address,
                })
            refreshed_count = self.store.apply_chain_meme_trader_market_mark_batch(
                outcomes, recorded_at=received_at,
            )
            for version in dict.fromkeys(evaluate_versions or ([evaluate_version] if evaluate_version else [])):
                # Use this batch while its observations are fresh; waiting for
                # every other HTTP batch can expire the 15-second exit window.
                self.store.evaluate_chain_meme_trader_market_marks(
                    definition_version=version,
                    token_ids=[str(item["token_id"]) for item in chunk],
                )
            self.store.heartbeat(
                heartbeat_name, item=refreshed_count > 0,
            )
            if timing is not None:
                timing.observe("held_apply_exit", asyncio.get_running_loop().time()-apply_started, items=refreshed_count)
            if observe_flat_breakout:
                self.store.observe_flat_compression_breakout_market_batch(
                    outcomes, recorded_at=received_at,
                )
            return refreshed_count

        return sum(await asyncio.gather(*(
            refresh_batch(chain, chunk)
            for chain, chunk in batches
        )))

    async def chain_meme_market_marks_once(self) -> None:
        """Refresh current-version held tokens on the high-priority DEX lane."""
        idle = self._chain_meme_active_idle()
        idle.clear()
        try:
            active_version = self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION
            target_versions = [active_version]
            if not self.chain_meme_trader_only:
                target_versions.extend([
                    self.store.CHAIN_MEME_TRADER_V13_VERSION,
                    self.store.CHAIN_MEME_TRADER_V11_VERSION,
                ])
            targets = self.store.chain_meme_trader_market_mark_targets(
                definition_versions=target_versions,
            )
            self._pattern_held_tokens = {str(t["token_id"]) for t in targets}
            refreshed = await self._refresh_chain_meme_market_marks(
                targets, heartbeat_name="chain-meme-market-marks",
                high_priority=True,
                evaluate_versions=[active_version, *getattr(self, "_chain_carry_versions", [])],
            )

            if not self.chain_meme_trader_only:
                self.store.evaluate_chain_meme_trader_market_marks(
                    definition_version=self.store.CHAIN_MEME_TRADER_V11_VERSION,
                )
            self.store.heartbeat("chain-meme-market-marks", item=refreshed > 0)
        finally:
            idle.set()

    async def flat_compression_breakout_shadow_once(self) -> None:
        """Refresh one non-held mature-token batch after the held-token lane."""
        targets = self.store.due_flat_compression_breakout_shadow_targets(
            limit=30,
        )
        if not targets:
            self.store.heartbeat("flat-compression-breakout-shadow", item=False)
            return
        refreshed = await self._refresh_chain_meme_market_marks(
            targets,
            heartbeat_name="flat-compression-breakout-shadow",
            high_priority=False,
            observe_flat_breakout=True,
        )
        self.store.heartbeat(
            "flat-compression-breakout-shadow", item=refreshed > 0,
            error_detail=f"targets={len(targets)};refreshed={refreshed}",
        )

    def _remember_pattern_quotes(self, quoted: dict) -> None:
        """Bounded passive watch: reuse discovery/held/flat quotes, no I/O here."""
        current = utcnow()
        watch = getattr(self, "_pattern_watch", {})
        watch = {k: v for k, v in watch.items() if current < v["expires_at"]}
        for token, snapshot in quoted.values():
            token_id, chain = token.token_id, token.chain
            if token_id in watch:
                watch[token_id]["quote"] = snapshot
                continue
            if chain not in {"solana", "bsc", "robinhood"}:
                continue
            raw = snapshot.raw or {}
            pair = raw.get("pair", raw)
            address = str(pair.get("pairAddress") or "")
            created = pair.get("pairCreatedAt")
            if not address or not created or snapshot.price_usd is None or snapshot.price_usd <= 0:
                continue
            age = snapshot.observed_at.timestamp() - float(created) / 1000
            bucket = "early" if age < 900 else "growth" if age < 21600 else "mature"
            capacity = 4 if bucket == "growth" else 3
            if age < 0 or sum(v["token"].chain == chain and v["bucket"] == bucket for v in watch.values()) >= capacity:
                continue
            watch[token_id] = {"token": token, "bucket": bucket, "quote": snapshot,
                "pair_address": canonical_token_address(chain, address),
                "expires_at": current + timedelta(minutes=15)}
        self._pattern_watch = watch

    async def chain_meme_pattern_observer_once(self) -> None:
        """At most 30 shared candidates; low priority and isolated from old entries."""
        self._remember_pattern_quotes({})
        watch = self._pattern_watch
        projected = sampled = 0
        chains = sorted({v["token"].chain for v in watch.values()})
        cursor = getattr(self, "_pattern_chain_cursor", 0)
        if chains:
            offset = cursor % len(chains)
            chains = chains[offset:] + chains[:offset]
        self._pattern_chain_cursor = cursor + 1
        requested = False
        for chain in chains:
            await self._chain_meme_active_idle().wait()
            targets = [v for v in watch.values() if v["token"].chain == chain]
            # Held tokens only consume their core lane's next response. Never
            # make a second request when a held response is late or unavailable.
            due = [v["token"].address for v in targets
                   if v["token"].token_id not in getattr(self, "_pattern_held_tokens", set())
                   and ((utcnow() - v["quote"].observed_at).total_seconds() > 15
                        or v.get("sampled_at") == v["quote"].observed_at)]
            if due and not requested and self._dex_quote_low_priority_available():
                requested = True
                try:
                    quoted = await asyncio.wait_for(self._dex_batch_quote(
                        chain, due, fresh=True, high_priority=False), timeout=3)
                    self._remember_pattern_quotes(quoted)
                except (httpx.HTTPError, TimeoutError) as exc:
                    self.store.heartbeat("chain-meme-pattern-observer", error=type(exc).__name__)
            for item in targets:
                token = item["token"]
                snapshot = item["quote"]
                if (item.get("sampled_at") == snapshot.observed_at
                        or (utcnow() - snapshot.observed_at).total_seconds() > 30):
                    continue
                raw = snapshot.raw or {}
                pair = raw.get("pair", raw)
                pairs = raw.get("pairs") or [pair]
                exact = next((p for p in pairs if canonical_token_address(chain, str(p.get("pairAddress") or "")) == item["pair_address"]), None)
                if exact is None:
                    continue
                observation = DexScreenerClient._snapshot(exact)
                if observation is None:
                    continue
                observation.observed_at, observation.ingested_at = snapshot.observed_at, snapshot.ingested_at
                received = utcnow()
                if self._paper_quote_rejections(token.token_id, token, observation, received):
                    continue
                projected += self.store.observe_chain_meme_pattern(token, observation, recorded_at=received)
                item["sampled_at"] = snapshot.observed_at
                sampled += 1
        self.store.heartbeat("chain-meme-pattern-observer", item=sampled > 0,
            error_detail=f"watched={len(watch)};sampled={sampled};projected={projected}")

    async def chain_meme_carried_market_marks_once(self) -> None:
        """Maintain older open positions without slowing the active strategy lane."""
        carry_versions = [
            version
            for version in (
                self.store.CHAIN_MEME_TRADER_V22_VERSION,
                self.store.CHAIN_MEME_TRADER_V21_VERSION,
                self.store.CHAIN_MEME_TRADER_V20_VERSION,
            )
            if (
                version != self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION
                and self.store.chain_meme_trader_has_open_positions(version)
            )
        ]
        if not carry_versions:
            self.store.heartbeat("chain-meme-carried-market-marks", item=False)
            return
        self._chain_carry_versions = carry_versions
        active_targets = self.store.chain_meme_trader_market_mark_targets(
            definition_versions=[self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION],
        )
        active_token_ids = {str(item["token_id"]) for item in active_targets}
        targets = [
            item for item in self.store.chain_meme_trader_market_mark_targets(
                definition_versions=carry_versions,
            )
            if str(item["token_id"]) not in active_token_ids
        ]
        refreshed = await self._refresh_chain_meme_market_marks(
            targets, heartbeat_name="chain-meme-carried-market-marks",
            evaluate_versions=carry_versions,
        )
        for version in carry_versions:
            if not self.store.chain_meme_trader_has_open_positions(
                version
            ):
                self.store.record_chain_meme_trader_account_snapshots(
                    definition_version=version,
                )
        self.store.heartbeat(
            "chain-meme-carried-market-marks", item=refreshed > 0,
        )

    async def chain_meme_trader_postbuy_research_once(self) -> None:
        """Run one observer-only semantic investigation shared by all v5 strategy arms."""
        due = self.store.due_chain_meme_trader_postbuy_research(limit=1)
        if not due:
            return
        item = due[0]
        cutoff = utcnow()
        latest_start = parse_time(item["latest_start_at"])
        if cutoff > latest_start:
            case_id = self.store.record_chain_meme_trader_postbuy_research_case(
                shadow_cohort_id=int(item["shadow_cohort_id"]),
                token_id=str(item["token_id"]),
                first_buy_fill_id=int(item["first_buy_fill_id"]),
                entry_snapshot_id=int(item["entry_snapshot_id"]),
                position_opened_at=item["position_opened_at"],
                research_cutoff_at=cutoff,
                snapshot_id=None,
                trigger_transition_id=None,
                status="coverage_gap",
                reason_code="research_start_window_missed",
            )
            if case_id is not None:
                self.store.complete_chain_meme_trader_postbuy_research(
                    int(case_id), terminal_status="coverage_gap:start_window_missed",
                )
            return
        token = self.store.token(str(item["token_id"]))
        if token is None:
            case_id = self.store.record_chain_meme_trader_postbuy_research_case(
                shadow_cohort_id=int(item["shadow_cohort_id"]),
                token_id=str(item["token_id"]),
                first_buy_fill_id=int(item["first_buy_fill_id"]),
                entry_snapshot_id=int(item["entry_snapshot_id"]),
                position_opened_at=item["position_opened_at"],
                research_cutoff_at=cutoff,
                snapshot_id=None,
                trigger_transition_id=None,
                status="coverage_gap",
                reason_code="token_record_unavailable",
            )
            if case_id is not None:
                self.store.complete_chain_meme_trader_postbuy_research(
                    int(case_id), terminal_status="coverage_gap:token_record_unavailable",
                )
            return
        frozen = self.store.post_entry_context_snapshot(
            str(item["token_id"]),
            opened_at=item["position_opened_at"],
            at_or_before=cutoff,
            entry_snapshot_id=int(item["entry_snapshot_id"]),
        )
        if frozen is None:
            case_id = self.store.record_chain_meme_trader_postbuy_research_case(
                shadow_cohort_id=int(item["shadow_cohort_id"]),
                token_id=str(item["token_id"]),
                first_buy_fill_id=int(item["first_buy_fill_id"]),
                entry_snapshot_id=int(item["entry_snapshot_id"]),
                position_opened_at=item["position_opened_at"],
                research_cutoff_at=cutoff,
                snapshot_id=None,
                trigger_transition_id=None,
                status="coverage_gap",
                reason_code="no_temporally_valid_snapshot",
            )
            if case_id is not None:
                self.store.complete_chain_meme_trader_postbuy_research(
                    int(case_id), terminal_status="coverage_gap:no_temporally_valid_snapshot",
                )
            return
        snapshot_id, snapshot = frozen
        snapshot_basis = (
            "entry_trigger_snapshot"
            if int(snapshot_id) == int(item["entry_snapshot_id"])
            else "post_entry_snapshot"
        )
        momentum = CandidateEvaluator._momentum_score(snapshot)
        trigger = self.autonomous_search.resolve_token_context_trigger(
            token,
            momentum_score=momentum,
            event_relation={
                "kind": "post_entry_narrative_position",
                "source_buy_trade_id": int(item["first_buy_fill_id"]),
                "source_fill_id": int(item["first_buy_fill_id"]),
                "shadow_cohort_id": int(item["shadow_cohort_id"]),
                "position_opened_at": str(item["position_opened_at"]),
                "position_status": "v5_shared_postbuy",
                "selection_path": "chain_meme_trader_v5_shared_postbuy",
                "context_snapshot_basis": snapshot_basis,
                "investigation_started_at": iso(cutoff),
            },
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=int(snapshot_id),
        )
        transition_id = (
            int(trigger["transition_id"])
            if trigger is not None and trigger.get("transition_id") is not None
            else None
        )
        case_id = self.store.record_chain_meme_trader_postbuy_research_case(
            shadow_cohort_id=int(item["shadow_cohort_id"]),
            token_id=str(item["token_id"]),
            first_buy_fill_id=int(item["first_buy_fill_id"]),
            entry_snapshot_id=int(item["entry_snapshot_id"]),
            position_opened_at=item["position_opened_at"],
            research_cutoff_at=cutoff,
            snapshot_id=int(snapshot_id),
            trigger_transition_id=transition_id,
            status="triggered" if transition_id is not None else "coverage_gap",
            reason_code=(
                "v5_shared_postbuy" if transition_id is not None
                else "token_universe_lineage_unavailable"
            ),
        )
        if case_id is None:
            return
        if transition_id is None:
            self.store.complete_chain_meme_trader_postbuy_research(
                int(case_id), terminal_status="coverage_gap:transition_unavailable",
            )
            return
        try:
            await self._investigate_token_context(
                token,
                snapshot,
                momentum_score=momentum,
                event_relation=trigger,
                allow_postbuy_research_in_focus=True,
            )
        finally:
            self.store.complete_chain_meme_trader_postbuy_research(
                int(case_id), completed_at=utcnow(),
            )
        self.store.heartbeat("chain-meme-postbuy-research", item=True)

    async def onchain_paper_position_monitor_once(self) -> None:
        """Passively value one exact remaining position; never mutate or sell it."""
        tasks = self.store.due_onchain_paper_position_monitor_quotes(limit=1)
        if not tasks:
            return
        async with self._jupiter_background_dispatch_lock:
            loop_now = asyncio.get_running_loop().time()
            if (
                loop_now - self._jupiter_background_epoch_started
                >= self._jupiter_background_epoch_seconds
            ):
                self._jupiter_background_epoch_started = loop_now
                self._jupiter_background_epoch_requests = 0
            if self._jupiter_background_epoch_requests >= 3:
                return
            task = tasks[0]
            requested_at = utcnow()
            attempt_id = self.store.start_onchain_paper_position_monitor_quote_attempt(
                task, requested_at=requested_at
            )
            if attempt_id is None:
                return
            self._jupiter_background_epoch_requests += 1
            status = "quoted"
            result: dict[str, Any] = {}
            error_type = ""
            try:
                async with self._jupiter_quote_lock:
                    result = await self.jupiter.quote(
                        str(task["input_mint"]), str(task["output_mint"]),
                        int(task["input_amount_raw"]),
                        slippage_bps=int(task["slippage_bps"]),
                    )
            except JupiterNoRouteError:
                status = "no_route"
            except JupiterQuoteProtocolError as exc:
                status, error_type = "quote_only_protocol_invalid", type(exc).__name__
            except Exception as exc:
                status, error_type = "error", type(exc).__name__
            self.store.record_onchain_paper_position_monitor_quote_result(
                attempt_id=int(attempt_id),
                status=status,
                output_amount_raw=result.get("output_amount_raw"),
                other_amount_threshold_raw=result.get("other_amount_threshold"),
                slippage_bps=result.get("slippage_bps"),
                router=str(result.get("router") or ""),
                mode=str(result.get("mode") or ""),
                price_impact_bps=result.get("price_impact_bps"),
                error_type=error_type,
                completed_at=result.get("completed_at") or utcnow(),
            )

    async def onchain_paper_narrative_context_once(self) -> None:
        """Investigate each new Strategy 3 position once, without changing its exit."""
        if self.strategy_focus_active:
            return
        self.store.enroll_onchain_paper_narrative_runner()
        due = self.store.due_onchain_paper_narrative_context(limit=8)
        if not due:
            return
        for position in due:
            source_buy_trade_id = int(position["source_buy_trade_id"])
            existing_transition_id = position.get("context_trigger_transition_id")
            if (
                existing_transition_id is None
                and str(position["status"]) not in {"baseline", "narrative_runner"}
            ):
                self.store.record_onchain_paper_narrative_context_seed(
                    source_buy_trade_id=source_buy_trade_id,
                    snapshot_id=None,
                    trigger_transition_id=None,
                    status="coverage_gap",
                    reason_code="position_closed_before_context_trigger",
                )
                continue
            token = self.store.token(str(position["token_id"]))
            if token is None:
                if existing_transition_id is None:
                    self.store.record_onchain_paper_narrative_context_seed(
                        source_buy_trade_id=source_buy_trade_id,
                        snapshot_id=None,
                        trigger_transition_id=None,
                        status="coverage_gap",
                        reason_code="token_record_unavailable",
                    )
                continue
            triggered_at = utcnow()
            frozen = self.store.post_entry_context_snapshot(
                str(position["token_id"]),
                opened_at=position["opened_at"],
                at_or_before=triggered_at,
                snapshot_id=(
                    int(position["context_snapshot_id"])
                    if existing_transition_id is not None
                    and position.get("context_snapshot_id") is not None
                    else None
                ),
                entry_snapshot_id=(
                    int(position["entry_trigger_snapshot_id"])
                    if existing_transition_id is None
                    and position.get("entry_trigger_snapshot_id") is not None
                    else None
                ),
            )
            if frozen is None:
                if existing_transition_id is None:
                    self.store.record_onchain_paper_narrative_context_seed(
                        source_buy_trade_id=source_buy_trade_id,
                        snapshot_id=None,
                        trigger_transition_id=None,
                        status="coverage_gap",
                        reason_code="no_temporally_valid_post_entry_snapshot",
                    )
                continue
            snapshot_id, snapshot = frozen
            snapshot_basis = (
                "entry_trigger_snapshot"
                if int(snapshot_id)
                == int(position.get("entry_trigger_snapshot_id") or -1)
                else "post_entry_snapshot"
            )
            momentum = CandidateEvaluator._momentum_score(snapshot)
            if existing_transition_id is not None:
                trigger = {
                    "kind": "post_entry_narrative_position",
                    "priority": 2,
                    "source_buy_trade_id": source_buy_trade_id,
                    "shadow_cohort_id": int(position["shadow_cohort_id"]),
                    "position_opened_at": str(position["opened_at"]),
                    "position_status": str(position["status"]),
                    "selection_path": "strategy3_forward_post_entry_recovery",
                    "context_snapshot_basis": snapshot_basis,
                    "investigation_started_at": iso(triggered_at),
                    "decision_eligible": False,
                    "endorsement_inferred": False,
                    "transition_id": int(existing_transition_id),
                }
            else:
                trigger = self.autonomous_search.resolve_token_context_trigger(
                    token,
                    momentum_score=momentum,
                    event_relation={
                        "kind": "post_entry_narrative_position",
                        "source_buy_trade_id": source_buy_trade_id,
                        "shadow_cohort_id": int(position["shadow_cohort_id"]),
                        "position_opened_at": str(position["opened_at"]),
                        "position_status": str(position["status"]),
                        "context_snapshot_basis": snapshot_basis,
                        "investigation_started_at": iso(triggered_at),
                    },
                    snapshot_observed_at=snapshot.observed_at,
                    snapshot_id=snapshot_id,
                )
                transition_id = (
                    int(trigger["transition_id"])
                    if trigger is not None and trigger.get("transition_id") is not None
                    else None
                )
                self.store.record_onchain_paper_narrative_context_seed(
                    source_buy_trade_id=source_buy_trade_id,
                    snapshot_id=snapshot_id,
                    trigger_transition_id=transition_id,
                    status="triggered" if transition_id is not None else "coverage_gap",
                    reason_code=(
                        "post_entry_narrative_position"
                        if transition_id is not None else "token_universe_lineage_unavailable"
                    ),
                )
                if transition_id is None:
                    continue
            await self._investigate_token_context(
                token,
                snapshot,
                momentum_score=momentum,
                event_relation=trigger,
            )
            self.store.heartbeat("onchain-paper-narrative-context", item=True)
            break

    async def kol_token_addressability_route_once(self) -> None:
        await self.token_universe_jupiter_quote_once(
            include_universe=False, include_onchain=False, include_kol=True,
        )

    async def _hydrate_pump_metadata(
        self, token: TokenCandidate, *, round_id: int, exposure_id: int
    ) -> None:
        cfg = self.config["sources"].get("pumpportal") or {}
        raw_uri = token.raw.get("uri") if isinstance(token.raw, dict) else None
        if not cfg.get("metadata_enabled", True) or not raw_uri:
            return
        attempted_at = utcnow()
        evaluation_key = f"pump-metadata:{token.token_id}:{str(raw_uri)[:500]}"
        self.store.record_token_universe_funnel_transition(
            token.token_id,
            stage="metadata_hydration_attempt",
            status="attempted",
            reason_code="launch_metadata_uri",
            evaluation_key=evaluation_key + ":attempt",
            observed_at=attempted_at,
            ingested_at=attempted_at,
            source_table="token_discovery_rounds",
            source_record_ids={"round_id": round_id},
            round_id=round_id,
            metadata={"provider": "pumpportal"},
        )
        metadata_uri = ""
        document_host = ""
        retrieval_host = ""
        alternate_uri = ""
        attempt_count = 0
        try:
            metadata_uri = normalize_public_http_url(str(raw_uri))
            parsed_metadata_uri = urllib.parse.urlsplit(metadata_uri)
            document_host = (parsed_metadata_uri.hostname or "unknown").lower()
            request_uri = metadata_uri
            if parsed_metadata_uri.path.startswith("/ipfs/"):
                alternate_hosts = {
                    "ipfs.io": "gateway.pinata.cloud",
                    "gateway.pinata.cloud": "ipfs.io",
                }
                alternate_host = alternate_hosts.get(document_host)
                if alternate_host:
                    alternate_uri = normalize_public_http_url(
                        urllib.parse.urlunsplit(
                            (
                                "https", alternate_host, parsed_metadata_uri.path,
                                parsed_metadata_uri.query, "",
                            )
                        )
                    )
            while True:
                attempt_count += 1
                retrieval_host = (
                    urllib.parse.urlsplit(request_uri).hostname or "unknown"
                ).lower()
                try:
                    response = await self.http.get_public_document(
                        request_uri,
                        maximum_bytes=int(
                            cfg.get("metadata_max_response_bytes", 131_072)
                        ),
                        maximum_redirects=3,
                    )
                    break
                except httpx.HTTPStatusError as exc:
                    status_code = int(exc.response.status_code)
                    retryable = (
                        status_code in {408, 425, 429}
                        or status_code >= 500
                        or (status_code == 403 and bool(alternate_uri))
                    )
                    if attempt_count >= 2 or not retryable:
                        raise
                    if alternate_uri:
                        request_uri = alternate_uri
                    try:
                        retry_after = float(
                            exc.response.headers.get("Retry-After", "0.5") or 0.5
                        )
                    except ValueError:
                        retry_after = 0.5
                    await asyncio.sleep(max(0.0, min(5.0, retry_after)))
                except httpx.TransportError:
                    if attempt_count >= 2:
                        raise
                    if alternate_uri:
                        request_uri = alternate_uri
                    await asyncio.sleep(0.5)
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Pump metadata must be a JSON object")
            links: list[tuple[str, Any]] = []
            for field in ("website", "twitter", "telegram"):
                if payload.get(field):
                    links.append((field, payload.get(field)))
            extensions = payload.get("extensions")
            if isinstance(extensions, dict):
                for field in ("website", "twitter", "telegram"):
                    if extensions.get(field):
                        links.append((field, extensions.get(field)))
            source_links: list[dict[str, Any]] = []
            social_urls: list[str] = []
            seen: set[tuple[str, str]] = set()
            for label, value in links:
                link_kind, platform, normalized_url = DexScreenerClient._classify_link(
                    value, label=label
                )
                if not normalized_url or (normalized_url, link_kind) in seen:
                    continue
                seen.add((normalized_url, link_kind))
                social_urls.append(normalized_url)
                source_links.append(
                    {
                        "token_id": token.token_id,
                        "chain": token.chain.lower(),
                        "address": token.address,
                        "provider": "pumpportal",
                        "discovery_surface": "launch_metadata",
                        "role": "identity",
                        "original_url": str(value)[:4000],
                        "normalized_url": normalized_url[:4000],
                        "link_kind": link_kind,
                        "label": label,
                        "platform": platform,
                        "verification_status": "manual_only"
                        if link_kind == "telegram_manual" else "provider_metadata",
                        "raw": {"metadata_uri": metadata_uri, "field": label},
                    }
                )
            description = str(payload.get("description") or "")[:5000]
            token.name = token.name or str(payload.get("name") or "")[:300]
            token.symbol = token.symbol or str(payload.get("symbol") or "")[:80]
            token.social_urls = list(dict.fromkeys([*token.social_urls, *social_urls]))
            token.raw = {
                **token.raw,
                "description": description,
                "pump_metadata_uri": metadata_uri,
                "token_source_links": source_links,
            }
            completed_at = utcnow()
            source_link_fingerprints = [
                self.store.upsert_token_source_link(link, observed_at=completed_at)[0]
                for link in source_links
            ]
            self.store.upsert_token(token, seen_at=completed_at)
            self.store.link_token_discovery_exposure_source_links(
                exposure_id, source_link_fingerprints, observed_at=completed_at
            )
            source_link_id = None
            if source_link_fingerprints:
                fingerprint = source_link_fingerprints[0]
                source_link_id = next(
                    (
                        int(row["id"])
                        for row in self.store.token_source_links(token.token_id, limit=100)
                        if str(row["fingerprint"]) == fingerprint
                    ),
                    None,
                )
            self.store.record_token_universe_funnel_transition(
                token.token_id,
                stage="metadata_hydration_result",
                status="hydrated",
                reason_code="metadata_links_found" if source_links else "metadata_parsed_no_links",
                evaluation_key=evaluation_key + ":result",
                observed_at=completed_at,
                ingested_at=completed_at,
                source_table="token_source_links" if source_links else "tokens",
                source_record_ids={
                    "round_id": round_id,
                    "exposure_id": exposure_id,
                    "source_link_id": source_link_id,
                },
                round_id=round_id,
                source_link_id=source_link_id,
                metadata={
                    "provider": "pumpportal",
                    "source_link_count": len(source_links),
                    "document_host": document_host,
                    "retrieval_host": retrieval_host,
                    "attempt_count": attempt_count,
                },
            )
            self.store.heartbeat("pumpportal:metadata", item=bool(source_links))
        except Exception as exc:
            completed_at = utcnow()
            status_code = (
                int(exc.response.status_code)
                if isinstance(exc, httpx.HTTPStatusError) else None
            )
            retryable_failure = (
                isinstance(exc, httpx.TransportError)
                or (
                    status_code is not None
                    and (
                        status_code in {408, 425, 429}
                        or status_code >= 500
                        or (status_code == 403 and bool(alternate_uri))
                    )
                )
            )
            document_unavailable = (
                isinstance(
                    exc,
                    (
                        httpx.HTTPStatusError,
                        json.JSONDecodeError,
                        UnsafeFeedURL,
                        FeedRedirectError,
                        FeedResponseTooLarge,
                        InvalidPublicDocumentContentType,
                        UnsupportedFeedContentEncoding,
                    ),
                )
                or str(exc) == "Pump metadata must be a JSON object"
            )
            reason_code = (
                f"http_status_{status_code}"
                if status_code is not None else type(exc).__name__
            )
            self.store.record_token_universe_funnel_transition(
                token.token_id,
                stage="metadata_hydration_result",
                status="unavailable" if document_unavailable and not retryable_failure else "error",
                reason_code=reason_code,
                evaluation_key=evaluation_key + ":result",
                observed_at=completed_at,
                ingested_at=completed_at,
                source_table="token_discovery_rounds",
                source_record_ids={"round_id": round_id},
                round_id=round_id,
                metadata={
                    "provider": "pumpportal",
                    "document_host": document_host or "unknown",
                    "retrieval_host": retrieval_host or document_host or "unknown",
                    "http_status": status_code,
                    "attempt_count": attempt_count,
                },
            )
            # Invalid or unavailable metadata belongs to this Token's coverage
            # ledger.  Only a retry-exhausted transport/provider failure or an
            # unexpected program error is a system-level incident.
            if retryable_failure or not document_unavailable:
                self.store.heartbeat(
                    "pumpportal:metadata",
                    error=f"{reason_code}:{document_host or 'unknown'}",
                    error_detail=(
                        f"{reason_code}; host={retrieval_host or document_host or 'unknown'}; "
                        f"attempts={attempt_count}"
                    ),
                )

    async def pump_loop(self) -> None:
        cfg = self.config["sources"].get("pumpportal") or {}
        if not cfg.get("enabled", True):
            return
        collector = PumpPortalCollector(str(cfg.get("url") or PumpPortalCollector.URL))
        queue: asyncio.Queue[TokenCandidate] = asyncio.Queue()
        metadata_queue: asyncio.Queue[tuple[TokenCandidate, int, int]] = asyncio.Queue(
            maxsize=max(1, int(cfg.get("metadata_queue_size", 512)))
        )

        async def produce() -> None:
            async for token in collector.stream():
                await queue.put(token)

        producer = asyncio.create_task(produce(), name="pumpportal_stream_reader")
        async def hydrate_metadata() -> None:
            while not self._stop.is_set():
                token, round_id, exposure_id = await metadata_queue.get()
                try:
                    await self._hydrate_pump_metadata(
                        token, round_id=round_id, exposure_id=exposure_id
                    )
                finally:
                    metadata_queue.task_done()

        metadata_workers = [
            asyncio.create_task(hydrate_metadata(), name=f"pumpportal_metadata_{index + 1}")
            for index in range(max(1, min(2, int(cfg.get("metadata_workers", 1)))))
        ] if cfg.get("metadata_enabled", True) else []
        window_seconds = max(1.0, float(cfg.get("exposure_window_seconds", 60)))
        try:
            while not self._stop.is_set():
                round_ids = {
                    surface: self.store.start_token_discovery_round(
                        provider="pumpportal",
                        surface=surface,
                        mode="stream_window",
                        chain_scope="solana",
                    )
                    for surface in ("create", "migration")
                }
                returned = {"create": 0, "migration": 0}
                duplicates = {"create": 0, "migration": 0}
                deadline = asyncio.get_running_loop().time() + window_seconds
                try:
                    while not self._stop.is_set():
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            break
                        try:
                            token = await asyncio.wait_for(queue.get(), timeout=min(1.0, remaining))
                        except TimeoutError:
                            continue
                        surface = "migration" if token.source.endswith(":migration") else "create"
                        known_before = self.store.token_discovery_known(token.token_id)
                        created = await self.ingest_token(token)
                        first_local = not known_before and created
                        returned[surface] += 1
                        duplicates[surface] += int(not first_local)
                        exposure_id = self.store.add_token_discovery_exposure(
                            round_ids[surface],
                            token_id=token.token_id,
                            chain=token.chain,
                            role=surface,
                            first_local_discovery=first_local,
                            new_token=created,
                            observed_at=token.first_seen_at,
                        )
                        if (
                            exposure_id is not None
                            and first_local
                            and surface == "create"
                            and isinstance(token.raw, dict)
                            and token.raw.get("uri")
                            and metadata_workers
                        ):
                            try:
                                metadata_queue.put_nowait(
                                    (token, round_ids[surface], int(exposure_id))
                                )
                            except asyncio.QueueFull:
                                skipped_at = utcnow()
                                self.store.record_token_universe_funnel_transition(
                                    token.token_id,
                                    stage="metadata_hydration_attempt",
                                    status="skipped",
                                    reason_code="metadata_queue_full",
                                    evaluation_key=f"pump-metadata:{token.token_id}:queue-full",
                                    observed_at=skipped_at,
                                    ingested_at=skipped_at,
                                    source_table="token_discovery_rounds",
                                    source_record_ids={
                                        "round_id": round_ids[surface],
                                        "exposure_id": int(exposure_id),
                                    },
                                    round_id=round_ids[surface],
                                    metadata={"provider": "pumpportal"},
                                )
                except asyncio.CancelledError:
                    for surface, round_id in round_ids.items():
                        self.store.finish_token_discovery_round(
                            round_id,
                            status="interrupted",
                            returned_count=returned[surface],
                            duplicate_token_count=duplicates[surface],
                        )
                    raise
                status = "interrupted" if self._stop.is_set() else "completed"
                for surface, round_id in round_ids.items():
                    self.store.finish_token_discovery_round(
                        round_id,
                        status=status,
                        returned_count=returned[surface],
                        duplicate_token_count=duplicates[surface],
                    )
        finally:
            producer.cancel()
            for worker in metadata_workers:
                worker.cancel()
            await asyncio.gather(producer, *metadata_workers, return_exceptions=True)

    async def provider_post_ambiguity_once(self) -> None:
        self.store.finalize_provider_post_ambiguity_checkpoints()

    async def run_once(self) -> None:
        await self.poll_external_once()
        await self.poll_dexscreener_discovery_once()
        await self.reverse_news_once()
        await self.evaluate_events_once()
        await self.shadow_event_followup_once()
        self.store.finalize_provider_post_ambiguity_checkpoints()
        await self.onchain_only_jupiter_quote_once()
        await self.monitor_positions_once()
        await self.check_source_health_once(include_streams=False)

    async def _periodic(
        self,
        name: str,
        interval_seconds: float,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        interval_seconds = max(1.0, float(interval_seconds))
        if not hasattr(self, "runtime_timing"):
            self.runtime_timing = RuntimeTiming()
            self._last_timing_write = 0.0
        previous_start = None
        while not self._stop.is_set():
            started = asyncio.get_running_loop().time()
            failed = 0
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failed = 1
                self.store.heartbeat(
                    name, error=type(exc).__name__, error_detail=str(exc),
                )
                self.notifier.send(
                    "runtime_error",
                    name,
                    {"error": type(exc).__name__, "detail": str(exc)[:500]},
                )
            elapsed = asyncio.get_running_loop().time() - started
            self.runtime_timing.observe(
                name, elapsed,
                interval_seconds=started-previous_start if previous_start is not None else None,
                configured_interval_seconds=interval_seconds, failures=failed,
            )
            previous_start = started
            if started - self._last_timing_write >= 10.0:
                self.store.record_runtime_timing(self.runtime_timing.snapshot())
                self._last_timing_write = started
            wait_seconds = max(0.2, interval_seconds - elapsed)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
            except TimeoutError:
                pass

    async def run_forever(self) -> None:
        bridge_cfg = self.config["bridge"]
        if bridge_cfg.get("enabled", True) and not self.chain_meme_trader_only:
            self.bridge = BrowserBridge(
                str(bridge_cfg.get("host", "127.0.0.1")), int(bridge_cfg.get("port", 8765)), str(bridge_cfg["token"]),
                self.ingest_observation, self.browser_heartbeat,
                max_body_bytes=int(bridge_cfg.get("max_body_bytes", 262_144)),
                source_entity_resolver=lambda item: resolve_watchlist_source_entity_id(
                    item, self.root / "data" / "web_console" / "console_settings.json"
                ),
            )
            await self.bridge.start()
            self.notifier.send("bridge_started", "browser bridge", {"host": bridge_cfg.get("host"), "port": bridge_cfg.get("port")})

        if self.chain_meme_trader_only:
            tasks = [
                asyncio.create_task(self.pump_loop(), name="pumpportal"),
                asyncio.create_task(
                    self._periodic(
                        "multichain_meme_data",
                        (self.config["sources"].get("multichain_meme_data") or {}).get("interval_seconds", 90),
                        self.poll_multichain_meme_data_once,
                    ),
                    name="multichain_meme_data",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_trader", 1, self.chain_meme_trader_once,
                    ),
                    name="chain_meme_trader",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_market_marks",
                        self.CHAIN_MEME_ACTIVE_MARK_INTERVAL_SECONDS,
                        self.chain_meme_market_marks_once,
                    ),
                    name="chain_meme_market_marks",
                ),
                asyncio.create_task(
                    self._periodic(
                        "flat_compression_breakout_shadow", 5,
                        self.flat_compression_breakout_shadow_once,
                    ),
                    name="flat_compression_breakout_shadow",
                ),
                asyncio.create_task(
                    self._periodic("chain_meme_pattern_observer", 15,
                                   self.chain_meme_pattern_observer_once),
                    name="chain_meme_pattern_observer",
                ),
                asyncio.create_task(
                    self._periodic("chain_meme_pattern_pools", 15, self.chain_meme_pattern_pools_once),
                    name="chain_meme_pattern_pools",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_carried_market_marks",
                        self.CHAIN_MEME_CARRIED_MARK_INTERVAL_SECONDS,
                        self.chain_meme_carried_market_marks_once,
                    ),
                    name="chain_meme_carried_market_marks",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_v22_vault_shadow_enroll", 15,
                        self.chain_meme_v22_vault_shadow_enroll_once,
                    ),
                    name="chain_meme_v22_vault_shadow_enroll",
                ),
                asyncio.create_task(
                    self.chain_meme_v22_vault_shadow_loop(),
                    name="chain_meme_v22_vault_shadow",
                ),
            ]
            try:
                await self._stop.wait()
            finally:
                self._stop.set()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            return

        tasks = [
            asyncio.create_task(self.pump_loop(), name="pumpportal"),
            asyncio.create_task(self._autonomous_source_loop(), name="autonomous_source_discovery"),
            asyncio.create_task(self._autonomous_trend_loop(), name="autonomous_trend_scout"),
            asyncio.create_task(
                self._periodic("external_sources", self.config.get("poll_seconds", 60), self.poll_external_once),
                name="external_sources",
            ),
            asyncio.create_task(
                self._periodic(
                    "robinhood_stock_token_registry",
                    21_600,
                    self.robinhood_stock_token_registry_once,
                ),
                name="robinhood_stock_token_registry",
            ),
            asyncio.create_task(
                self._periodic(
                    "dexscreener_discovery",
                    (self.config["sources"].get("dexscreener_discovery") or {}).get("interval_seconds", 90),
                    self.poll_dexscreener_discovery_once,
                ),
                name="dexscreener_discovery",
            ),
            asyncio.create_task(
                self._periodic(
                    "provider_post_ambiguity_finalizer",
                    30,
                    self.provider_post_ambiguity_once,
                ),
                name="provider_post_ambiguity_finalizer",
            ),
            asyncio.create_task(
                self._periodic(
                    "solana_holder_shadow",
                    max(
                        300,
                        float(
                            (self.config["sources"].get("solana_holder_shadow") or {}).get(
                                "interval_seconds", 300
                            )
                        ),
                    ),
                    self.solana_holder_shadow_once,
                ),
                name="solana_holder_shadow",
            ),
            asyncio.create_task(
                self._periodic("reverse_news", self.config.get("reverse_news_seconds", 45), self.reverse_news_once),
                name="reverse_news",
            ),
            asyncio.create_task(
                self._periodic("event_evaluation", self.config.get("event_scan_seconds", 10), self.evaluate_events_once),
                name="event_evaluation",
            ),
            asyncio.create_task(
                self._periodic("shadow_event_followup", 30, self.shadow_event_followup_once),
                name="shadow_event_followup",
            ),
            asyncio.create_task(
                self._periodic(
                    "information_first_active_outcome",
                    10,
                    self.information_first_active_outcome_once,
                ),
                name="information_first_active_outcome",
            ),
            asyncio.create_task(
                self._periodic(
                    "liquidity_survival_shadow",
                    10,
                    self.liquidity_survival_once,
                ),
                name="liquidity_survival_shadow",
            ),
            asyncio.create_task(
                self._periodic(
                    "onchain_only_jupiter_quote",
                    5,
                    self.onchain_only_jupiter_quote_once,
                ),
                name="onchain_only_jupiter_quote",
            ),
            asyncio.create_task(
                self._periodic(
                    "token_information_watch",
                    5,
                    self.token_information_watch_once,
                ),
                name="token_information_watch",
            ),
            asyncio.create_task(
                self._periodic(
                    "onchain_only_evm_route_quote",
                    10,
                    self.onchain_only_evm_route_quote_once,
                ),
                name="onchain_only_evm_route_quote",
            ),
            asyncio.create_task(
                self._periodic(
                    "onchain_only_evm_aggregator_price",
                    10,
                    self.onchain_only_evm_aggregator_price_once,
                ),
                name="onchain_only_evm_aggregator_price",
            ),
            asyncio.create_task(
                self._periodic(
                    "onchain_paper_exit_challenger",
                    self.config.get("position_scan_seconds", 15),
                    self.onchain_paper_exit_challenger_once,
                ),
                name="onchain_paper_exit_challenger",
            ),
            asyncio.create_task(
                self._periodic(
                    "onchain_paper_narrative_context",
                    30,
                    self.onchain_paper_narrative_context_once,
                ),
                name="onchain_paper_narrative_context",
            ),
            asyncio.create_task(
                self._periodic("position_monitor", self.config.get("position_scan_seconds", 15), self.monitor_positions_once),
                name="position_monitor",
            ),
            asyncio.create_task(
                self._periodic("source_health", self.config.get("source_health_seconds", 30), self.check_source_health_once),
                name="source_health",
            ),
        ]
        if self.strategy_focus_active:
            tasks.extend([
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_trader", 5, self.chain_meme_trader_once
                    ),
                    name="chain_meme_trader",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_postbuy_research", 5,
                        self.chain_meme_trader_postbuy_research_once,
                    ),
                    name="chain_meme_postbuy_research",
                ),
                asyncio.create_task(
                    self.held_account_loop(), name="solana_held_account_monitor"
                ),
                asyncio.create_task(
                    self.critical_onchain_exit_loop(), name="critical_onchain_exit"
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_market_marks",
                        self.CHAIN_MEME_ACTIVE_MARK_INTERVAL_SECONDS,
                        self.chain_meme_market_marks_once,
                    ),
                    name="chain_meme_market_marks",
                ),
                asyncio.create_task(
                    self._periodic(
                        "flat_compression_breakout_shadow", 5,
                        self.flat_compression_breakout_shadow_once,
                    ),
                    name="flat_compression_breakout_shadow",
                ),
                asyncio.create_task(
                    self._periodic(
                        "chain_meme_carried_market_marks",
                        self.CHAIN_MEME_CARRIED_MARK_INTERVAL_SECONDS,
                        self.chain_meme_carried_market_marks_once,
                    ),
                    name="chain_meme_carried_market_marks",
                ),
            ])
        try:
            await self._stop.wait()
        finally:
            self._stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self) -> None:
        self._stop.set()
