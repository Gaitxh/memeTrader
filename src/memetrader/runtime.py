from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from .autonomous_search import AutonomousSearchAgent
from .collectors import (
    BlueskySearchCollector,
    DexScreenerClient,
    GeckoNewPoolsCollector,
    HttpClient,
    MastodonCollector,
    PumpPortalCollector,
    RSSCollector,
    normalize_loopback_socks5_proxy_url,
    normalize_public_http_url,
)
from .models import CandidateDecision, Observation, TokenCandidate, iso, parse_time, utcnow
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
)


DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "paper",
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
        "gecko_networks": ["solana", "bsc"],
        "dexscreener_discovery": {
            "enabled": True,
            "interval_seconds": 90,
            "max_items_per_surface": 40,
            "max_hydrations_per_cycle": 180,
            "active_token_minutes": 180,
        },
        "pumpportal": {"enabled": True, "url": "wss://pumpportal.fun/api/data"},
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
        "chains": ["solana", "bsc", "base"],
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
        "slippage_rate": 0.02,
        "risk_per_trade_pct": 0.005,
        "max_cash_fraction": 0.08,
        "max_position_usd": 35,
        "min_position_usd": 3,
        "max_liquidity_impact_pct": 0.0025,
        "max_daily_new_exposure_usd": 100,
        "max_open_positions": 3,
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
        "context_global_cooldown_minutes": 5,
        "context_error_retry_minutes": 10,
        "context_min_momentum_score": 80,
        "context_direct_trigger_enabled": True,
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


def load_config(path: str | Path) -> tuple[dict[str, Any], Path]:
    config_path = Path(path).resolve()
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
            "trend_scout_high_token_threshold",
        ):
            if int(autonomous.get(name, 0)) < 0:
                raise ValueError(f"autonomous_search.{name} must be non-negative")
        if not 1 <= int(autonomous.get("max_concurrent_agents", 2)) <= 4:
            raise ValueError("autonomous_search.max_concurrent_agents must be between 1 and 4")
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
    if int(paper["max_open_positions"]) < 1:
        raise ValueError("paper.max_open_positions must be positive")
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


def resolve_watchlist_source_entity_id(item: dict[str, Any], settings_path: Path) -> str:
    """Resolve only an explicitly configured exact platform/handle entity mapping."""
    supplied = sanitize_source_entity_id(item.get("source_entity_id"))
    platform = str(item.get("platform") or "").strip().lower()
    author = str(item.get("author") or "").strip().casefold().lstrip("@")
    if not supplied or not platform or not author or platform == "telegram":
        return ""
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    accounts = payload.get("watch_accounts") if isinstance(payload, dict) else None
    if not isinstance(accounts, list):
        return ""
    for account in accounts[:500]:
        if not isinstance(account, dict) or account.get("enabled", True) is False:
            continue
        account_platform = str(account.get("platform") or "").strip().lower()
        account_handle = str(account.get("handle") or "").strip().casefold().lstrip("@")
        configured = sanitize_source_entity_id(account.get("entity_id"))
        if account_platform == platform and account_handle == author:
            return configured if configured == supplied else ""
    return ""


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
                    title = str(item.get("title") or item.get("text") or "").strip()
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
                    browser_item = {key: value for key, value in item.items() if key != "source_entity_id"}
                    if source_entity_id:
                        browser_item["source_entity_id"] = source_entity_id
                    await self.on_observation(
                        Observation(
                            source=str(item.get("source") or "browser"),
                            source_kind=str(item.get("source_kind") or "social"),
                            title=title[:500], text=str(item.get("text") or title)[:20_000],
                            url=str(item.get("url") or "")[:2000], author=str(item.get("author") or "")[:300],
                            published_at=published_at, observed_at=observed_at,
                            ingested_at=utcnow(), availability_proof="local_receive",
                            source_item_id=str(item.get("source_item_id") or item.get("url") or "")[:2000],
                            capture_phase=str(item.get("capture_phase") or "live")[:20],
                            raw={
                                "browser": browser_item,
                                **({"source_entity_id": source_entity_id} if source_entity_id else {}),
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
    def __init__(self, config: dict[str, Any], root: Path):
        self.config, self.root = config, root
        db_path = Path(str(config["database"]))
        starting_cash = float(config["paper"].get("starting_cash_usd", 1_000))
        self.store = Store(
            db_path if db_path.is_absolute() else root / db_path,
            initial_cash_usd=starting_cash,
        )
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
        self.dex = DexScreenerClient(self.http)
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
        self.evaluator = CandidateEvaluator(self.store, self.dex, self.safety, config["candidate"], self.agent)
        self.policy = PaperPolicy(config["paper"])
        self.notifier = Notifier(root, config["notifications"])
        self.bridge: BrowserBridge | None = None
        self._stop = asyncio.Event()

    async def close(self) -> None:
        if self.bridge:
            await self.bridge.close()
        await self.http.close()
        self.store.close()

    def _classify_observation(self, obs: Observation) -> Observation:
        if obs.role.lower() == "feature" and is_promotional_market_content(obs.title, obs.text):
            obs.role = "promotion"
            obs.raw = {**obs.raw, "non_event_market_promotion": True}
            return obs
        original_role = obs.role.lower()
        if obs.published_at is None or original_role not in {"feature", "confirmation"}:
            return obs
        max_age = float((self.config.get("events") or {}).get("max_source_age_minutes", 30))
        source_age = obs.observed_at - obs.published_at
        if obs.availability_proof in {"local_poll", "local_receive", "agent_search_verified"} and source_age > timedelta(minutes=max_age):
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

    async def ingest_observation(self, obs: Observation) -> None:
        obs = self._classify_observation(obs)
        event_id, event_created, observation_created = self.events.ingest(obs)
        self.store.heartbeat(obs.source, item=observation_created)
        if not observation_created:
            return
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
            return
        key = f"event_notification_attention:{event.id}"
        previous = float(self.store.get_kv(key, -1.0))
        step = float(notify_cfg.get("event_attention_step", 15.0))
        if previous >= 0 and event.attention < previous + step:
            return
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
                "page_url": page_url,
                "access_state": access_state,
                "observed_at": iso(),
                "contains_credentials": False,
            },
        )

    async def ingest_token(self, token: TokenCandidate) -> None:
        token_created = self.store.upsert_token(token)
        self.store.heartbeat(token.source or "onchain", item=token_created)
        if token_created and self.config["notifications"].get("notify_new_tokens", False):
            self.notifier.send(
                "token_new",
                f"{token.symbol or token.name} on {token.chain}",
                {"token_id": token.token_id, "source": token.source},
            )

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

    async def _poll_observation_collector(self, collector: Any) -> None:
        name = str(getattr(collector, "name", getattr(collector, "query", type(collector).__name__)))
        url = str(getattr(collector, "url", "") or "")
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
                    return
            for obs in observations:
                await self.ingest_observation(obs)
        except Exception as exc:
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
        try:
            tokens = await GeckoNewPoolsCollector(self.http, network).poll()
            self.store.heartbeat(name, item=bool(tokens))
            for token in tokens:
                await self.ingest_token(token)
        except Exception as exc:
            self._notify_source_error(name, exc)

    async def poll_dexscreener_discovery_once(self) -> None:
        cfg = self.config["sources"].get("dexscreener_discovery") or {}
        if not cfg.get("enabled", True):
            return
        allowed_chains = {str(chain).lower() for chain in self.config["candidate"].get("chains", [])}
        max_items = int(cfg.get("max_items_per_surface", 40))
        max_hydrations = int(cfg.get("max_hydrations_per_cycle", 180))
        for surface in self.dex.DISCOVERY_SURFACES:
            source = f"dexscreener:{surface}"
            try:
                links = await self.dex.discover_surface(surface, allowed_chains, limit=max_items)
            except Exception as exc:
                self._notify_source_error(source, exc)
                continue
            self.store.heartbeat(source, item=bool(links))
            for link in links:
                token_id = str(link.get("token_id") or "")
                chain = str(link.get("chain") or "").lower()
                address = str(link.get("address") or "")
                if not token_id or chain not in allowed_chains or not address:
                    continue
                self.store.upsert_token_source_link(link)
                self.store.enqueue_token_detail_hydration(chain, address)

        due = self.store.due_token_detail_hydrations(limit=max_hydrations)
        if not due:
            return
        by_chain: dict[str, list[Any]] = {}
        for row in due:
            by_chain.setdefault(str(row["chain"]), []).append(row)
        for chain, rows in by_chain.items():
            for offset in range(0, len(rows), 30):
                chunk = rows[offset : offset + 30]
                try:
                    if hasattr(self.dex, "batch_quote"):
                        quoted_by_token = await self.dex.batch_quote(
                            chain, [str(row["address"]) for row in chunk]
                        )
                    else:
                        quoted_by_token = {}
                        for row in chunk:
                            quoted = await self.dex.quote(chain, str(row["address"]))
                            if quoted:
                                quoted_by_token[quoted[0].token_id] = quoted
                except Exception as exc:
                    self._notify_source_error("dexscreener:hydration", exc)
                    for row in chunk:
                        self.store.mark_token_detail_hydration(
                            str(row["token_id"]), "error", error=f"{type(exc).__name__}: {exc}"
                        )
                    continue
                self.store.heartbeat("dexscreener:hydration", item=bool(quoted_by_token))
                for row in chunk:
                    token_id = str(row["token_id"])
                    quoted = quoted_by_token.get(token_id)
                    if not quoted:
                        self.store.mark_token_detail_hydration(token_id, "no_pair")
                        continue
                    token, snapshot = quoted
                    if token.token_id != token_id:
                        self.store.mark_token_detail_hydration(token_id, "no_pair")
                        continue
                    self.store.upsert_token(token, seen_at=snapshot.observed_at)
                    self.store.add_snapshot(snapshot)
                    self.store.mark_token_detail_hydration(token_id, "hydrated")

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
        result, observations = await self.autonomous_search.scout_trends(force=force)
        if result.get("status") == "completed":
            self.store.heartbeat("autonomous-trend-scout", item=bool(observations))
        for observation in observations:
            await self.ingest_observation(observation)
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
    ) -> None:
        observations = await self.autonomous_search.search_token_context(
            token,
            snapshot,
            momentum_score=momentum_score,
            event_relation=event_relation,
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
        source_priority = {"pumpportal:migration": 4, "geckoterminal": 3, "dexscreener": 2, "pumpportal": 1}
        tokens = self.store.recent_tokens(minutes=180, limit=candidate_pool_limit)
        tokens.sort(
            key=lambda token: (
                max((value for prefix, value in source_priority.items() if token.source.startswith(prefix)), default=0),
                token.first_seen_at or now,
            ),
            reverse=True,
        )
        scanned = 0

        for token in tokens:
            if scanned >= max_scanned:
                break
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
            scanned += 1
            try:
                quoted = await self.dex.quote(token.chain, token.address)
            except Exception as exc:
                self._notify_source_error(f"reverse-quote:{token.token_id}", exc)
                continue
            if not quoted:
                continue
            quoted_token, snap = quoted
            self.store.upsert_token(quoted_token)
            self.store.add_snapshot(snap)
            transactions = (snap.buys_5m or 0) + (snap.sells_5m or 0)
            buy_ratio = (snap.buys_5m or 0) / transactions if transactions else 0.0
            momentum = CandidateEvaluator._momentum_score(snap)
            trigger = self.autonomous_search.resolve_token_context_trigger(
                quoted_token,
                momentum_score=momentum,
            )
            market_gate = (
                (snap.liquidity_usd or 0) >= min_liquidity
                and (snap.volume_5m_usd or 0) >= min_volume
                and transactions >= min_transactions
                and buy_ratio >= min_buy_ratio
            )
            if not market_gate and trigger is None:
                continue
            ranked.append((int((trigger or {}).get("priority") or 0), momentum, quoted_token, trigger))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for _, momentum, token, trigger in ranked[:max_queries]:
            key = f"reverse_news:{token.token_id}"
            self.store.set_kv(key, iso(now))
            name = token.name.strip() or token.symbol.strip()
            query = f'"{name}" when:1d'
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
                {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
            )
            source = "google-news-reverse"
            accepted = 0
            accepted_origins: set[str] = set()
            try:
                observations = await RSSCollector(self.http, source, url, "news").poll()
                for obs in observations:
                    if obs.published_at and now - obs.published_at > max_result_age:
                        continue
                    if not _reverse_news_matches_token(token, obs):
                        continue
                    obs.role = "confirmation"
                    obs.raw["reverse_token_id"] = token.token_id
                    obs.raw["reverse_query"] = query
                    obs.raw["token_momentum_score"] = momentum
                    obs.raw["reverse_name_only"] = True
                    await self.ingest_observation(obs)
                    accepted += 1
                    accepted_origins.add(evidence_origin(obs))
                    if accepted >= max_results:
                        break
                self.store.heartbeat(source, item=accepted > 0)
            except Exception as exc:
                self._notify_source_error(source, exc)

            minimum_sources = int(cfg.get("min_independent_sources", 2))
            if len(accepted_origins) < minimum_sources:
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

        for event in self.store.active_events(minutes=480, limit=max_events):
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

            decision = await self.evaluator.discover_and_decide(event)
            attempt_key = f"event_decision_attempt:{event.id}"
            attempt = int(self.store.get_kv(attempt_key, 0))
            if not decision:
                delay = retry_seconds[min(attempt, len(retry_seconds) - 1)]
                self.store.set_kv(attempt_key, attempt + 1)
                self.store.set_kv(next_key, iso(now + timedelta(seconds=delay)))
                continue

            token = self.store.token(decision.token_id) if decision.token_id else None
            snap = self.store.latest_snapshot(decision.token_id) if decision.token_id else None
            amount = 0.0

            if decision.action == "CANDIDATE" and decision.token_id:
                if self.store.position(decision.token_id):
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("position_already_open")
                elif not candidate_cfg.get("allow_reentry", False) and self.store.has_bought_token(decision.token_id):
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("token_already_traded")

            if decision.action == "CANDIDATE" and token and snap and snap.price_usd:
                account = self.store.account()
                positions = self.store.open_positions()
                marked_values = []
                for pos in positions:
                    mark = self.store.latest_snapshot(pos.token_id)
                    marked_values.append((mark.price_usd if mark and mark.price_usd else pos.entry_price) * pos.quantity)
                equity = account["cash_usd"] + sum(marked_values)
                amount = self.policy.size(
                    cash_usd=account["cash_usd"],
                    equity_usd=equity,
                    open_count=len(positions),
                    snapshot=snap,
                    score=decision.score,
                    daily_exposure_usd=self.store.daily_buy_gross_usd(),
                )
                decision.position_usd = amount
                if amount <= 0:
                    decision.action = "WAIT"
                    decision.rejected_reasons.append("position_size_zero")

            decision_id = self.store.add_decision(decision)
            self.store.create_shadow_event_cohort(
                decision,
                decision_id=decision_id,
                source_observation_ids=[int(row["id"]) for row in accepted],
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
            position = self.store.paper_buy(
                event_id=event.id,
                token=token,
                price=execution_price,
                gross_usd=amount,
                fee_bps=float(self.config["paper"].get("fee_bps", 60)),
                reason="event_candidate",
            )
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
        fee = float(self.config["paper"].get("fee_bps", 80))
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
            slippage = float(self.config["paper"].get("slippage_rate", 0.0))
            execution_price = float(snap.price_usd) * (1.0 - slippage)
            result = self.store.paper_sell(
                position.token_id,
                price=execution_price,
                fraction=fraction,
                fee_bps=fee,
                reason=reason,
            )
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

    async def shadow_event_followup_once(self) -> None:
        self.store.finalize_shadow_event_outcomes()

    async def pump_loop(self) -> None:
        cfg = self.config["sources"].get("pumpportal") or {}
        if not cfg.get("enabled", True):
            return
        collector = PumpPortalCollector(str(cfg.get("url") or PumpPortalCollector.URL))
        async for token in collector.stream():
            if self._stop.is_set():
                break
            await self.ingest_token(token)

    async def run_once(self) -> None:
        await self.poll_external_once()
        await self.poll_dexscreener_discovery_once()
        await self.reverse_news_once()
        await self.evaluate_events_once()
        await self.shadow_event_followup_once()
        await self.monitor_positions_once()
        await self.check_source_health_once(include_streams=False)

    async def _periodic(
        self,
        name: str,
        interval_seconds: float,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        interval_seconds = max(1.0, float(interval_seconds))
        while not self._stop.is_set():
            started = asyncio.get_running_loop().time()
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.notifier.send(
                    "runtime_error",
                    name,
                    {"error": type(exc).__name__, "detail": str(exc)[:500]},
                )
            elapsed = asyncio.get_running_loop().time() - started
            wait_seconds = max(0.2, interval_seconds - elapsed)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
            except TimeoutError:
                pass

    async def run_forever(self) -> None:
        bridge_cfg = self.config["bridge"]
        if bridge_cfg.get("enabled", True):
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
                    "dexscreener_discovery",
                    (self.config["sources"].get("dexscreener_discovery") or {}).get("interval_seconds", 90),
                    self.poll_dexscreener_discovery_once,
                ),
                name="dexscreener_discovery",
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
                self._periodic("position_monitor", self.config.get("position_scan_seconds", 15), self.monitor_positions_once),
                name="position_monitor",
            ),
            asyncio.create_task(
                self._periodic("source_health", self.config.get("source_health_seconds", 30), self.check_source_health_once),
                name="source_health",
            ),
        ]
        try:
            await self._stop.wait()
        finally:
            self._stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self) -> None:
        self._stop.set()
