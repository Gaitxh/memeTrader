from __future__ import annotations

import argparse
import base64
import copy
import hmac
import http.client
import ipaddress
import json
import math
import mimetypes
import os
import socket
import sqlite3
import subprocess
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlparse, urlunparse

from .autonomous_search import (
    CONTEXT_ERROR_RETRY_KEY,
    CONTEXT_RESULT_KEY,
    CONTEXT_RUN_KEY,
    REGISTRY_KEY,
    SOURCE_RESULT_KEY,
    SOURCE_RUN_KEY,
    TREND_RESULT_KEY,
    TREND_RUN_KEY,
)
from .models import TokenSnapshot, iso, parse_time, utcnow
from .runtime import DEFAULT_CONFIG, load_config
from .strategy import CandidateEvaluator, evidence_origin, evidence_rejection, sanitize_source_entity_id
from .wallet import SolanaDevnetWallet, WalletError


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
PLATFORMS = (
    "x",
    "truth",
    "bluesky",
    "reddit",
    "threads",
    "instagram",
    "tiktok",
    "youtube",
    "telegram",
)
PLATFORM_ACCESS = {
    "x": ("browser_public_or_signed_in", True),
    "truth": ("browser_public_or_signed_in", True),
    "bluesky": ("public_web", False),
    "reddit": ("browser_public_or_signed_in", True),
    "threads": ("browser_public_or_signed_in", True),
    "instagram": ("browser_signed_in_recommended", True),
    "tiktok": ("browser_public_or_signed_in", True),
    "youtube": ("public_web", False),
    "telegram": ("manual_directory_only", False),
}
PLATFORM_AUTOMATION_DISABLED = {"telegram"}
DEFAULT_CONSOLE_SETTINGS = {
    "platforms": [
        {"platform": name, "enabled": name not in PLATFORM_AUTOMATION_DISABLED}
        for name in PLATFORMS
    ],
    "watch_accounts": [],
    "topics": [],
}
EXPECTED_TABLES = {
    "decisions",
    "event_observations",
    "events",
    "kv",
    "observations",
    "paper_account",
    "positions",
    "source_health",
    "token_snapshots",
    "tokens",
    "trades",
}
SAFE_OBSERVATION_RAW_FIELDS = {
    "account_type",
    "agent_model",
    "agent_task",
    "authority_tier",
    "category",
    "confidence",
    "event_title",
    "follower_count",
    "followers_count",
    "is_official",
    "is_verified",
    "keywords",
    "like_count",
    "memeability",
    "non_event_market_promotion",
    "original_role",
    "published_time_in_future",
    "relevance",
    "reply_count",
    "repost_count",
    "reverse_name_only",
    "reverse_token_id",
    "source_entity_id",
    "source_age_minutes",
    "stale_first_observation",
    "token_momentum_score",
    "view_count",
    "volume_usd",
}
PLATFORM_HOSTS = {
    "x": {"x.com", "twitter.com"},
    "truth": {"truthsocial.com"},
    "bluesky": {"bsky.app"},
    "reddit": {"reddit.com", "www.reddit.com", "old.reddit.com"},
    "threads": {"threads.net", "www.threads.net"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "tiktok": {"tiktok.com", "www.tiktok.com"},
    "youtube": {"youtube.com", "www.youtube.com", "youtu.be"},
    "telegram": {"t.me", "telegram.me"},
}
AUTHORITY_TIER_SCORES = {
    "official_primary": 20.0,
    "primary_source": 20.0,
    "major_news": 16.0,
    "established": 12.0,
    "specialist": 8.0,
    "community": 4.0,
}
CURATED_PRIORITY_TIERS = {
    5: "authoritative_organization",
    4: "original_public_figure_creator",
    3: "curated_monitor",
    2: "community_trend",
    1: "noisy_satire_discovery_only",
}
SENSITIVE_QUERY_MARKERS = ("api_key", "apikey", "auth", "credential", "key", "secret", "signature", "token")
NOTIFICATION_KIND_META = {
    "event_detected": ("events", "info"),
    "event_attention_up": ("events", "info"),
    "token_new": ("tokens", "info"),
    "candidate_decision": ("decisions", "info"),
    "paper_buy": ("paper", "success"),
    "paper_sell": ("paper", "success"),
    "shadow_buy": ("paper", "info"),
    "source_error": ("sources", "error"),
    "source_stale": ("sources", "warning"),
    "autonomous_source_paused": ("sources", "warning"),
    "autonomous_sources_added": ("sources", "info"),
    "autonomous_trends_found": ("agents", "info"),
    "autonomous_context_found": ("agents", "info"),
    "quote_error": ("system", "warning"),
    "runtime_error": ("system", "error"),
    "bridge_started": ("system", "info"),
}
NOTIFICATION_NUMERIC_FIELDS = {
    "attention",
    "score",
    "match_score",
    "canonical_margin",
    "position_usd",
    "amount_usd",
    "cost_usd",
    "remaining_cost_usd",
    "gross_usd",
    "net_usd",
    "pnl_usd",
    "fee_usd",
    "quantity",
    "fraction",
    "quote_price",
    "execution_price",
    "entry_price",
    "highest_price",
    "slippage_rate",
    "minutes_since_ok",
    "threshold",
    "observation_count",
}
NOTIFICATION_BOOLEAN_FIELDS = {"official", "new_cluster"}
NOTIFICATION_ACTIONS = {"WAIT", "CANDIDATE", "REJECT", "BUY", "SELL"}
NOTIFICATION_TAIL_BYTES = 2_000_000
NOTIFICATION_ROTATIONS = 2


# Only these non-secret, non-live fields are writable through the console.
# The running bot intentionally does not hot-reload them; a supervised restart is
# required so the single Runtime remains the only strategy owner.
SETTING_SPECS: dict[str, tuple[str, float, float]] = {
    "poll_seconds": ("float", 10, 3600),
    "reverse_news_seconds": ("float", 15, 3600),
    "event_scan_seconds": ("float", 1, 600),
    "position_scan_seconds": ("float", 5, 600),
    "source_health_seconds": ("float", 10, 3600),
    "event_min_attention": ("float", 0, 100),
    "events.max_source_age_minutes": ("float", 1, 1440),
    "events.cluster_hours": ("float", 1, 72),
    "events.similarity": ("float", 0, 1),
    "candidate.max_alias_queries": ("int", 1, 20),
    "candidate.token_watch_minutes": ("int", 10, 2880),
    "candidate.min_candidate_score": ("float", 0, 100),
    "candidate.min_match_score": ("float", 0, 100),
    "candidate.min_canonical_margin": ("float", 0, 100),
    "candidate.decision_cooldown_seconds": ("int", 10, 86400),
    "candidate.max_events_per_cycle": ("int", 1, 100),
    "candidate.max_source_age_minutes": ("float", 1, 1440),
    "candidate.min_reverse_independent_sources": ("int", 1, 10),
    "candidate.reverse_only_penalty": ("float", 0, 100),
    "safety.min_liquidity_usd": ("float", 0, 100_000_000),
    "safety.max_market_cap_usd": ("float", 1, 10_000_000_000),
    "safety.min_5m_transactions": ("int", 0, 100_000),
    "safety.min_buy_ratio": ("float", 0, 1),
    "safety.max_tax_pct": ("float", 0, 100),
    "safety.max_solana_risk_score": ("float", 0, 100),
    "paper.risk_per_trade_pct": ("float", 0.0001, 0.1),
    "paper.max_position_usd": ("float", 0, 1_000_000),
    "paper.min_position_usd": ("float", 0, 1_000_000),
    "paper.max_cash_fraction": ("float", 0, 1),
    "paper.max_liquidity_impact_pct": ("float", 0, 0.1),
    "paper.max_daily_new_exposure_usd": ("float", 0, 10_000_000),
    "paper.max_open_positions": ("int", 1, 100),
    "paper.stop_loss_pct": ("float", -0.95, -0.0001),
    "paper.trailing_activate_pct": ("float", 0, 20),
    "paper.trailing_drawdown_pct": ("float", 0.0001, 0.9999),
    "paper.narrative_stale_minutes": ("float", 1, 10080),
    "paper.narrative_min_holding_minutes": ("float", 0, 10080),
    "paper.narrative_exit_buy_ratio": ("float", 0, 1),
    "paper.max_holding_hours": ("float", 0.1, 720),
    "autonomous_search.max_concurrent_agents": ("int", 1, 2),
    "autonomous_search.trend_scout_base_interval_minutes": ("float", 1, 1440),
    "autonomous_search.trend_scout_surge_interval_minutes": ("float", 1, 1440),
    "autonomous_search.trend_scout_quiet_interval_minutes": ("float", 1, 1440),
    "autonomous_search.trend_scout_daily_limit": ("int", 0, 1000),
    "autonomous_search.trend_scout_daily_token_budget": ("int", 0, 100_000_000),
    "autonomous_search.trend_scout_token_reserve_per_call": ("int", 0, 10_000_000),
    "autonomous_search.source_discovery_interval_hours": ("float", 1, 720),
    "autonomous_search.source_discovery_daily_limit": ("int", 0, 100),
    "autonomous_search.source_discovery_daily_token_budget": ("int", 0, 10_000_000),
    "autonomous_search.source_discovery_token_reserve_per_call": ("int", 0, 10_000_000),
    "autonomous_search.context_global_cooldown_minutes": ("float", 1, 1440),
    "autonomous_search.context_token_cooldown_minutes": ("float", 1, 10080),
    "autonomous_search.context_search_daily_limit": ("int", 0, 1000),
    "autonomous_search.context_min_momentum_score": ("float", 0, 100),
    "autonomous_search.token_context_daily_token_budget": ("int", 0, 100_000_000),
    "autonomous_search.token_context_token_reserve_per_call": ("int", 0, 10_000_000),
}


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)
        self.message = message


def _json_load(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return copy.deepcopy(default)
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return copy.deepcopy(default)


def _safe_url(value: Any) -> str | None:
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    safe_query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.casefold().replace("-", "_")
        if any(marker in lowered for marker in SENSITIVE_QUERY_MARKERS):
            safe_query.append((key, "REDACTED"))
        else:
            safe_query.append((key, item))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(safe_query), ""))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _observation_platform(source: Any, source_kind: Any, url: Any) -> dict[str, Any]:
    source_text = str(source or "").strip()
    source_prefix = source_text.split(":", 1)[0].lower()
    safe_url = _safe_url(url)
    host = (urlparse(safe_url).hostname or "").lower() if safe_url else ""
    for platform, hosts in PLATFORM_HOSTS.items():
        if host in hosts or source_prefix == platform:
            return {"id": platform, "label": "X" if platform == "x" else platform.title(), "inferred": True}
    if host:
        return {"id": "web", "label": host.removeprefix("www."), "inferred": True}
    kind = str(source_kind or "").strip().lower()
    if kind in {"social", "official_social"}:
        return {"id": "social", "label": "Social", "inferred": True}
    if kind == "news":
        return {"id": "web", "label": "Web / news", "inferred": True}
    return {"id": "unknown", "label": "Unknown", "inferred": False}


def _known_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _observation_influence(source_kind: Any, safe_raw: dict[str, Any], engagement: dict[str, float]) -> dict[str, Any]:
    kind = str(source_kind or "").strip().lower()
    official = _known_bool(safe_raw.get("is_official"))
    if kind == "official_social":
        official = True
    verified = _known_bool(safe_raw.get("is_verified"))
    explicit_type = str(safe_raw.get("account_type") or "").strip().lower()
    known_types = {"official", "publisher", "journalist", "creator", "public_figure", "community", "organization"}
    account_type_inferred = explicit_type not in known_types
    if explicit_type not in known_types:
        explicit_type = "official" if kind == "official_social" else ("social" if kind == "social" else ("publisher" if kind == "news" else "unknown"))
    authority_tier = str(safe_raw.get("authority_tier") or "").strip().lower()
    authority_inferred = False
    if authority_tier not in AUTHORITY_TIER_SCORES:
        authority_tier = "official_primary" if official is True else "unknown"
        authority_inferred = official is True
    followers = _safe_float(safe_raw.get("follower_count"))
    if followers is None:
        followers = _safe_float(safe_raw.get("followers_count"))
    followers = max(0, int(followers)) if followers is not None else None
    visible_engagement = {key: int(value) for key, value in engagement.items() if value > 0}
    return {
        "account_type": explicit_type,
        "account_type_inferred": account_type_inferred and explicit_type != "unknown",
        "official": official,
        "verified": verified,
        "authority_tier": authority_tier,
        "authority_known": authority_tier != "unknown",
        "authority_inferred": authority_inferred,
        "follower_count": followers,
        "visible_engagement": visible_engagement,
        "reach": int(engagement.get("view_count") or 0) or None,
    }


def _minutes_since(value: Any) -> float | None:
    if not value:
        return None
    try:
        return round(max(0.0, (utcnow() - parse_time(value)).total_seconds() / 60.0), 2)
    except Exception:
        return None


def _iso_add(value: Any, delta: timedelta) -> str | None:
    if not value:
        return None
    try:
        return iso(parse_time(value) + delta)
    except Exception:
        return None


def _query_int(query: dict[str, list[str]], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int((query.get(name) or [default])[0])
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _is_loopback(host: str) -> bool:
    if str(host).lower() in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _nested_get(mapping: dict[str, Any], path: str) -> Any:
    value: Any = mapping
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _nested_set(mapping: dict[str, Any], path: str, value: Any) -> None:
    target = mapping
    parts = path.split(".")
    for part in parts[:-1]:
        next_value = target.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            target[part] = next_value
        target = next_value
    target[parts[-1]] = value


def _flatten_updates(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise APIError(400, "settings update must be a JSON object")
    output: dict[str, Any] = {}
    for key, item in value.items():
        key = str(key)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            output.update(_flatten_updates(item, path))
        else:
            output[path] = item
    return output


def _coerce_setting(path: str, value: Any) -> int | float:
    kind, minimum, maximum = SETTING_SPECS[path]
    if isinstance(value, bool):
        raise APIError(400, f"{path} must be numeric")
    try:
        parsed: int | float = int(value) if kind == "int" else float(value)
    except (TypeError, ValueError):
        raise APIError(400, f"{path} must be {kind}") from None
    if kind == "int" and float(parsed) != float(value):
        raise APIError(400, f"{path} must be an integer")
    if not minimum <= float(parsed) <= maximum:
        raise APIError(400, f"{path} must be between {minimum:g} and {maximum:g}")
    return parsed


def _plain_text(value: Any, field: str, maximum: int, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise APIError(400, f"{field} is required")
    if len(text) > maximum or any(ord(character) < 32 for character in text):
        raise APIError(400, f"{field} is invalid")
    return text


def _validate_console_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise APIError(400, "console settings must be a JSON object")
    unknown = sorted(set(value) - {"platforms", "watch_accounts", "topics"})
    if unknown:
        raise APIError(400, "unsupported console setting: " + ", ".join(unknown))

    platforms_value = value.get("platforms", DEFAULT_CONSOLE_SETTINGS["platforms"])
    if not isinstance(platforms_value, list) or len(platforms_value) > len(PLATFORMS):
        raise APIError(400, "platforms must be a bounded list")
    platforms: list[dict[str, Any]] = []
    seen_platforms: set[str] = set()
    for item in platforms_value:
        if not isinstance(item, dict) or set(item) - {"platform", "enabled"}:
            raise APIError(400, "each platform may contain only platform and enabled")
        platform = _plain_text(item.get("platform"), "platform", 32, required=True).lower()
        if platform not in PLATFORMS or platform in seen_platforms:
            raise APIError(400, f"unsupported or duplicate platform: {platform}")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise APIError(400, "platform enabled must be boolean")
        seen_platforms.add(platform)
        platforms.append(
            {
                "platform": platform,
                "enabled": enabled and platform not in PLATFORM_AUTOMATION_DISABLED,
            }
        )

    accounts_value = value.get("watch_accounts", [])
    if not isinstance(accounts_value, list) or len(accounts_value) > 500:
        raise APIError(400, "watch_accounts must be a bounded list")
    accounts: list[dict[str, Any]] = []
    seen_accounts: set[tuple[str, str]] = set()
    allowed_account_fields = {"platform", "handle", "display_name", "url", "enabled", "priority", "entity_id"}
    for item in accounts_value:
        if not isinstance(item, dict) or set(item) - allowed_account_fields:
            raise APIError(400, "watch account contains unsupported fields")
        platform = _plain_text(item.get("platform"), "watch account platform", 32, required=True).lower()
        if platform not in PLATFORMS:
            raise APIError(400, f"unsupported watch account platform: {platform}")
        handle = _plain_text(item.get("handle"), "watch account handle", 120, required=True)
        if any(character.isspace() for character in handle):
            raise APIError(400, "watch account handle must not contain whitespace")
        key = (platform, handle.casefold().lstrip("@"))
        if key in seen_accounts:
            raise APIError(400, f"duplicate watch account: {platform}/{handle}")
        display_name = _plain_text(item.get("display_name"), "watch account display_name", 160)
        raw_entity_id = _plain_text(item.get("entity_id"), "watch account entity_id", 64)
        entity_id = sanitize_source_entity_id(raw_entity_id)
        if raw_entity_id and not entity_id:
            raise APIError(
                400,
                "watch account entity_id must be a lowercase 1-64 character slug using letters, numbers, _ or -",
            )
        raw_url = _plain_text(item.get("url"), "watch account url", 2048)
        url = _safe_url(raw_url) if raw_url else None
        if raw_url and url is None:
            raise APIError(400, "watch account url must be a public http/https URL")
        if url:
            host = (urlparse(url).hostname or "").lower().rstrip(".")
            if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
                raise APIError(400, "watch account url must be public")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
                raise APIError(400, "watch account url must be public")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise APIError(400, "watch account enabled must be boolean")
        priority = item.get("priority", 3)
        if isinstance(priority, bool):
            raise APIError(400, "watch account priority must be an integer between 1 and 5")
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            raise APIError(400, "watch account priority must be an integer between 1 and 5") from None
        if not 1 <= priority <= 5:
            raise APIError(400, "watch account priority must be an integer between 1 and 5")
        seen_accounts.add(key)
        accounts.append(
            {
                "platform": platform,
                "handle": handle,
                "display_name": display_name,
                "entity_id": entity_id,
                "url": url or "",
                "enabled": enabled,
                "priority": priority,
            }
        )

    topics_value = value.get("topics", [])
    if not isinstance(topics_value, list) or len(topics_value) > 100:
        raise APIError(400, "topics must be a bounded list")
    topics: list[str] = []
    seen_topics: set[str] = set()
    for item in topics_value:
        topic = _plain_text(item, "topic", 160, required=True)
        key = topic.casefold()
        if key not in seen_topics:
            seen_topics.add(key)
            topics.append(topic)
    return {"platforms": platforms, "watch_accounts": accounts, "topics": topics}


class WebData:
    """Read-only live view of the resident Runtime plus an allowlisted config editor."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.console_settings_path = self.config_path.parent / "data" / "web_console" / "console_settings.json"
        self.wallet_service = SolanaDevnetWallet(self.console_settings_path.parent)
        self.auth_info = {"required": False, "mode": "loopback", "token_file": None}
        self._settings_lock = threading.Lock()
        self._system_lock = threading.Lock()
        self._system_cache_at = None
        self._system_cache: dict[str, Any] | None = None
        self._reload_config()

    def wallet_state(self, *, public_view: bool = False, refresh: bool = False) -> dict[str, Any]:
        return self.wallet_service.snapshot(public_view=public_view, refresh=refresh)

    def connect_wallet(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise APIError(400, "wallet connection must be a JSON object")
        unknown = set(payload) - {"private_key", "alias"}
        if unknown:
            raise APIError(400, "unsupported wallet connection fields")
        if "private_key" not in payload:
            raise APIError(400, "private_key is required")
        try:
            return self.wallet_service.connect(payload.get("private_key"), payload.get("alias"))
        except WalletError as exc:
            raise APIError(400, str(exc)) from None

    def wallet_airdrop(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - {"sol"}:
            raise APIError(400, "unsupported Devnet faucet fields")
        try:
            return self.wallet_service.request_airdrop(payload.get("sol", 0.1))
        except WalletError as exc:
            raise APIError(400, str(exc)) from None

    def wallet_transfer(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) - {"recipient", "sol", "confirm_phrase"}:
            raise APIError(400, "unsupported Devnet transfer fields")
        try:
            return self.wallet_service.transfer(
                payload.get("recipient"), payload.get("sol"), payload.get("confirm_phrase")
            )
        except WalletError as exc:
            raise APIError(400, str(exc)) from None

    def disconnect_wallet(self) -> dict[str, Any]:
        return self.wallet_service.disconnect()

    def console_settings(self) -> dict[str, Any]:
        if not self.console_settings_path.exists():
            return copy.deepcopy(DEFAULT_CONSOLE_SETTINGS)
        try:
            value = json.loads(self.console_settings_path.read_text(encoding="utf-8"))
            return _validate_console_settings(value)
        except (OSError, json.JSONDecodeError, APIError):
            # A broken optional preference file must not stop observation of the
            # resident bot. The next valid PATCH replaces it atomically.
            return copy.deepcopy(DEFAULT_CONSOLE_SETTINGS)

    def public_access_url(self) -> str | None:
        access_path = self.console_settings_path.with_name("PUBLIC_ACCESS.txt")
        try:
            for line in access_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("URL: "):
                    value = line[5:].strip()
                    parsed = urlparse(value)
                    if parsed.scheme == "https" and parsed.hostname:
                        return value
        except OSError:
            pass
        return None

    def _reload_config(self) -> None:
        self.config, self.root = load_config(self.config_path)
        database = Path(str(self.config["database"]))
        self.database = database if database.is_absolute() else self.root / database
        lock_file = Path(str(self.config.get("lock_file") or "data/memetrader.lock"))
        self.lock_file = lock_file if lock_file.is_absolute() else self.root / lock_file

    def _notification_log_path(self) -> Path:
        configured = Path(str((self.config.get("notifications") or {}).get("jsonl") or "data/notifications.jsonl"))
        return configured if configured.is_absolute() else self.root / configured

    @staticmethod
    def _notification_text(value: Any, maximum: int, *, allow_path: bool = False) -> str | None:
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            return None
        text = " ".join(str(value).split()).strip()
        if not text or len(text) > maximum:
            return None
        lowered = text.casefold()
        if not allow_path and (
            "\\" in text
            or text.startswith(("/", "~"))
            or "://" in text
            or "file://" in lowered
            or (len(text) > 2 and text[1:3] == ":/")
        ):
            return None
        return text

    @staticmethod
    def _tail_text_lines(path: Path, maximum_bytes: int) -> tuple[list[str], bool, bool]:
        """Read a bounded tail while tolerating append, replacement, and rotation races."""
        if maximum_bytes <= 0:
            return [], False, False
        try:
            with path.open("rb") as handle:
                size = handle.seek(0, os.SEEK_END)
                start = max(0, size - maximum_bytes)
                handle.seek(start)
                data = handle.read(maximum_bytes)
        except FileNotFoundError:
            return [], False, False
        except OSError:
            return [], True, False
        if start and data:
            newline = data.find(b"\n")
            data = data[newline + 1:] if newline >= 0 else b""
        return data.decode("utf-8", errors="replace").splitlines(), True, start > 0

    def _public_notification(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        kind = self._notification_text(raw.get("kind"), 80)
        title = self._notification_text(raw.get("title"), 300)
        try:
            when = parse_time(raw.get("time"))
        except Exception:
            return None
        if not kind or not title or kind not in NOTIFICATION_KIND_META:
            return None
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        group, severity = NOTIFICATION_KIND_META[kind]

        event_id = None
        value = payload.get("event_id")
        if not isinstance(value, bool):
            try:
                parsed_event_id = int(value)
                event_id = parsed_event_id if parsed_event_id > 0 else None
            except (TypeError, ValueError):
                pass

        token_id = self._notification_text(payload.get("token_id"), 512)
        if token_id is None and kind in {"paper_buy", "paper_sell", "shadow_buy", "quote_error"}:
            token_id = self._notification_text(title, 512)

        action = self._notification_text(payload.get("action"), 32)
        action = action.upper() if action else None
        if action not in NOTIFICATION_ACTIONS:
            action = {"paper_buy": "BUY", "shadow_buy": "BUY", "paper_sell": "SELL"}.get(kind)
        if kind == "candidate_decision":
            if action == "CANDIDATE":
                severity = "success"
            elif action == "WAIT":
                severity = "warning"
            elif action == "REJECT":
                severity = "error"

        source_name = self._notification_text(payload.get("source"), 200)
        if source_name is None and group == "sources":
            source_name = self._notification_text(title, 200)
        reason = self._notification_text(payload.get("reason"), 160)

        metrics: dict[str, Any] = {}
        for field in NOTIFICATION_NUMERIC_FIELDS:
            number = _safe_float(payload.get(field))
            if number is not None:
                metrics[field] = number
        for field in NOTIFICATION_BOOLEAN_FIELDS:
            if isinstance(payload.get(field), bool):
                metrics[field] = payload[field]

        item: dict[str, Any] = {
            "time": iso(when),
            "kind": kind,
            "title": title,
            "group": group,
            "severity": severity,
            "metrics": metrics,
        }
        if event_id is not None:
            item.update({"event_id": event_id, "event_url": f"#/events/{event_id}"})
        if token_id is not None:
            item.update({"token_id": token_id, "token_url": f"#/tokens/{token_id}"})
        if action is not None:
            item["action"] = action
        if source_name is not None:
            item["source_display_name"] = source_name
        if reason is not None:
            item["reason"] = reason
        if kind in {"paper_buy", "paper_sell", "shadow_buy"}:
            mode = "shadow" if kind == "shadow_buy" else "paper"
            item["simulation"] = {
                "is_simulated": True,
                "mode": mode,
                "label": f"{mode.upper()} / SIMULATED",
            }
        return item

    def notifications(self, query: dict[str, list[str]]) -> dict[str, Any]:
        limit = _query_int(query, "limit", 100, 1, 200)
        offset = _query_int(query, "offset", 0, 0, 1_000_000)
        base = self._notification_log_path()
        paths = [base, *(Path(str(base) + f".{index}") for index in range(1, NOTIFICATION_ROTATIONS + 1))]
        remaining = NOTIFICATION_TAIL_BYTES
        lines: list[str] = []
        files_seen = 0
        rotated_files_seen = 0
        truncated = False
        for index, path in enumerate(paths):
            batch, existed, clipped = self._tail_text_lines(path, remaining)
            if not existed:
                continue
            files_seen += 1
            rotated_files_seen += int(index > 0)
            truncated = truncated or clipped
            lines.extend(batch)
            remaining = max(0, remaining - sum(len(line.encode("utf-8", errors="replace")) + 1 for line in batch))
            if remaining == 0:
                truncated = True
                break

        items: list[dict[str, Any]] = []
        malformed = 0
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except (TypeError, ValueError, json.JSONDecodeError):
                malformed += 1
                continue
            item = self._public_notification(raw)
            if item is None:
                malformed += 1
                continue
            items.append(item)
        items.sort(key=lambda item: parse_time(item["time"]), reverse=True)

        latest_at = items[0]["time"] if items else None
        stale = False
        if latest_at:
            stale = utcnow() - parse_time(latest_at) > timedelta(minutes=30)
        if items:
            status = "stale" if stale else "active"
        elif files_seen:
            status = "empty"
        else:
            status = "missing"
        total = len(items)
        return {
            "items": items[offset:offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "latest_at": latest_at,
            "status": status,
            "stale": stale,
            "malformed_skipped": malformed,
            "bounded_tail": True,
            "history_truncated": truncated,
            "rotated_generations_read": rotated_files_seen,
            "as_of": iso(),
            "execution_context": {
                "mode": str(self.config.get("mode") or "paper"),
                "simulated": True,
                "live_enabled": False,
                "live_locked": True,
            },
        }

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection | None]:
        if not self.database.exists():
            yield None
            return
        connection = sqlite3.connect(
            self.database.resolve().as_uri() + "?mode=ro",
            uri=True,
            timeout=1.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=1000")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _kv(connection: sqlite3.Connection | None, key: str, default: Any = None) -> Any:
        if connection is None or not WebData._table_exists(connection, "kv"):
            return default
        row = connection.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        return default if row is None else _json_load(row["value_json"], default)

    def database_health(self) -> dict[str, Any]:
        if not self.database.exists():
            return {
                "status": "missing",
                "ok": False,
                "exists": False,
                "schema_complete": False,
                "journal_mode": None,
                "size_bytes": None,
            }
        try:
            with self.connect() as connection:
                assert connection is not None
                tables = {
                    str(row["name"])
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                quick_check = str(connection.execute("PRAGMA quick_check(1)").fetchone()[0])
                journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
            return {
                "status": "ok" if quick_check == "ok" else "error",
                "ok": quick_check == "ok",
                "exists": True,
                "schema_complete": EXPECTED_TABLES.issubset(tables),
                "journal_mode": journal_mode,
                "size_bytes": self.database.stat().st_size,
                "quick_check": quick_check,
            }
        except (OSError, sqlite3.Error):
            return {
                "status": "unavailable",
                "ok": False,
                "exists": True,
                "schema_complete": None,
                "journal_mode": None,
                "size_bytes": self.database.stat().st_size if self.database.exists() else None,
            }

    def _bridge_health(self) -> dict[str, Any]:
        bridge = self.config.get("bridge") or {}
        enabled = bool(bridge.get("enabled", True))
        host = str(bridge.get("host") or "127.0.0.1")
        port = int(bridge.get("port") or 8765)
        if not enabled:
            return {"enabled": False, "reachable": None, "host": host, "port": port}
        if not _is_loopback(host):
            return {"enabled": True, "reachable": False, "host": host, "port": port, "reason": "non_loopback"}
        try:
            connection = http.client.HTTPConnection(host, port, timeout=0.5)
            connection.request("GET", "/health")
            response = connection.getresponse()
            body = response.read(4096)
            connection.close()
            payload = _json_load(body.decode("utf-8", errors="replace"), {})
            return {
                "enabled": True,
                "reachable": response.status == 200 and bool(payload.get("ok")),
                "host": host,
                "port": port,
            }
        except (OSError, TimeoutError, http.client.HTTPException):
            return {"enabled": True, "reachable": False, "host": host, "port": port}

    @staticmethod
    def _scheduled_task_health() -> dict[str, Any]:
        if os.name != "nt":
            return {"supported": False, "exists": None, "state": "unknown"}
        script = (
            "$ErrorActionPreference='Stop';"
            "$task=Get-ScheduledTask -TaskName 'memeTrader Paper Bot';"
            "$info=$task|Get-ScheduledTaskInfo;"
            "[pscustomobject]@{exists=$true;state=[string]$task.State;"
            "last_run_at=if($info.LastRunTime){$info.LastRunTime.ToUniversalTime().ToString('o')}else{$null};"
            "next_run_at=if($info.NextRunTime){$info.NextRunTime.ToUniversalTime().ToString('o')}else{$null};"
            "last_result=[int64]$info.LastTaskResult}|ConvertTo-Json -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                shell=False,
            )
            if completed.returncode != 0:
                return {"supported": True, "exists": False, "state": "missing"}
            payload = _json_load(completed.stdout, {})
            return {
                "supported": True,
                "exists": bool(payload.get("exists")),
                "state": str(payload.get("state") or "unknown").lower(),
                "last_run_at": payload.get("last_run_at"),
                "next_run_at": payload.get("next_run_at"),
                "last_result": payload.get("last_result"),
            }
        except (OSError, subprocess.SubprocessError):
            return {"supported": True, "exists": None, "state": "unknown"}

    def _latest_activity(self) -> str | None:
        with self.connect() as connection:
            if connection is None:
                return None
            values: list[str] = []
            for table, column in (
                ("observations", "ingested_at"),
                ("token_snapshots", "observed_at"),
                ("source_health", "last_ok_at"),
            ):
                if not self._table_exists(connection, table):
                    continue
                row = connection.execute(f"SELECT MAX({column}) AS value FROM {table}").fetchone()
                if row and row["value"]:
                    values.append(str(row["value"]))
        if not values:
            return None
        try:
            return iso(max(parse_time(value) for value in values))
        except Exception:
            return max(values)

    @staticmethod
    def _activity_lane(
        *,
        latest_at: str | None,
        counts: dict[str, int | float],
        active_window_seconds: float,
        degraded_window_seconds: float,
    ) -> dict[str, Any]:
        age_seconds: float | None = None
        if latest_at:
            try:
                age_seconds = round(max(0.0, (utcnow() - parse_time(latest_at)).total_seconds()), 1)
            except Exception:
                pass
        if age_seconds is None:
            status = "waiting"
        elif age_seconds <= active_window_seconds:
            status = "active"
        elif age_seconds <= degraded_window_seconds:
            status = "degraded"
        else:
            status = "stale"
        return {
            "status": status,
            "latest_at": latest_at,
            "age_seconds": age_seconds,
            "active_window_seconds": round(active_window_seconds, 1),
            "degraded_window_seconds": round(degraded_window_seconds, 1),
            **counts,
        }

    def ingestion_activity(self, connection: sqlite3.Connection | None) -> dict[str, Any]:
        """Return recent persisted collection activity without synthesizing heartbeats."""

        now = utcnow()
        cutoffs = {60: iso(now - timedelta(seconds=60)), 300: iso(now - timedelta(seconds=300))}
        poll_seconds = max(10.0, float(self.config.get("poll_seconds", 60)))
        active_window = max(90.0, poll_seconds * 3)
        degraded_window = max(900.0, active_window * 4)
        query_ok = True
        try:
            information_latest: str | None = None
            information_counts: dict[str, int | float] = {
                "observations_60s": 0,
                "observations_5m": 0,
                "rate_per_minute_5m": 0.0,
            }
            token_latest: str | None = None
            token_counts: dict[str, int | float] = {
                "new_tokens_60s": 0,
                "new_tokens_5m": 0,
                "token_updates_60s": 0,
                "token_updates_5m": 0,
                "snapshot_updates_60s": 0,
                "snapshot_updates_5m": 0,
                "rate_per_minute_5m": 0.0,
            }
            if connection is not None and self._table_exists(connection, "observations"):
                live_information = "LOWER(source_kind)!='onchain' AND COALESCE(capture_phase,'live')='live'"
                row = connection.execute(
                    f"""
                    SELECT MAX(ingested_at) AS latest,
                           SUM(CASE WHEN ingested_at>=? THEN 1 ELSE 0 END) AS count_60s,
                           SUM(CASE WHEN ingested_at>=? THEN 1 ELSE 0 END) AS count_5m
                    FROM observations WHERE {live_information}
                    """,
                    (cutoffs[60], cutoffs[300]),
                ).fetchone()
                information_latest = str(row["latest"]) if row and row["latest"] else None
                information_counts["observations_60s"] = int(row["count_60s"] or 0)
                information_counts["observations_5m"] = int(row["count_5m"] or 0)
                information_counts["rate_per_minute_5m"] = round(
                    float(information_counts["observations_5m"]) / 5.0, 2
                )
            token_times: list[str] = []
            if connection is not None and self._table_exists(connection, "tokens"):
                row = connection.execute(
                    """
                    SELECT MAX(last_seen_at) AS latest,
                           SUM(CASE WHEN first_seen_at>=? THEN 1 ELSE 0 END) AS new_60s,
                           SUM(CASE WHEN first_seen_at>=? THEN 1 ELSE 0 END) AS new_5m,
                           SUM(CASE WHEN last_seen_at>=? THEN 1 ELSE 0 END) AS updated_60s,
                           SUM(CASE WHEN last_seen_at>=? THEN 1 ELSE 0 END) AS updated_5m
                    FROM tokens
                    """,
                    (cutoffs[60], cutoffs[300], cutoffs[60], cutoffs[300]),
                ).fetchone()
                if row and row["latest"]:
                    token_times.append(str(row["latest"]))
                token_counts["new_tokens_60s"] = int(row["new_60s"] or 0)
                token_counts["new_tokens_5m"] = int(row["new_5m"] or 0)
                token_counts["token_updates_60s"] = int(row["updated_60s"] or 0)
                token_counts["token_updates_5m"] = int(row["updated_5m"] or 0)
            if connection is not None and self._table_exists(connection, "token_snapshots"):
                row = connection.execute(
                    """
                    SELECT MAX(observed_at) AS latest,
                           SUM(CASE WHEN observed_at>=? THEN 1 ELSE 0 END) AS count_60s,
                           SUM(CASE WHEN observed_at>=? THEN 1 ELSE 0 END) AS count_5m
                    FROM token_snapshots
                    """,
                    (cutoffs[60], cutoffs[300]),
                ).fetchone()
                if row and row["latest"]:
                    token_times.append(str(row["latest"]))
                token_counts["snapshot_updates_60s"] = int(row["count_60s"] or 0)
                token_counts["snapshot_updates_5m"] = int(row["count_5m"] or 0)
            if token_times:
                try:
                    token_latest = iso(max(parse_time(value) for value in token_times))
                except Exception:
                    token_latest = max(token_times)
            token_counts["rate_per_minute_5m"] = round(
                (
                    float(token_counts["token_updates_5m"])
                    + float(token_counts["snapshot_updates_5m"])
                )
                / 5.0,
                2,
            )
        except sqlite3.Error:
            query_ok = False
        information = self._activity_lane(
            latest_at=information_latest,
            counts=information_counts,
            active_window_seconds=active_window,
            degraded_window_seconds=degraded_window,
        )
        tokens = self._activity_lane(
            latest_at=token_latest,
            counts=token_counts,
            active_window_seconds=active_window,
            degraded_window_seconds=degraded_window,
        )
        statuses = {information["status"], tokens["status"]}
        if not query_ok:
            status = "unavailable"
            information["status"] = "unavailable"
            tokens["status"] = "unavailable"
        elif statuses == {"active"}:
            status = "active"
        elif "active" in statuses or "degraded" in statuses:
            status = "degraded"
        elif "stale" in statuses:
            status = "stale"
        else:
            status = "waiting"
        return {
            "status": status,
            "as_of": iso(now),
            "truth_source": "persisted_sqlite_activity",
            "query_ok": query_ok,
            "information": information,
            "tokens": tokens,
        }

    def system_health(self) -> dict[str, Any]:
        now = utcnow()
        with self._system_lock:
            if self._system_cache_at and self._system_cache and now - self._system_cache_at < timedelta(seconds=10):
                return copy.deepcopy(self._system_cache)
            bridge = self._bridge_health()
            task = self._scheduled_task_health()
            latest_activity = self._latest_activity()
            activity_age = _minutes_since(latest_activity)
            recent_window = max(5.0, float(self.config.get("poll_seconds", 60)) * 3.0 / 60.0)
            recent_activity = activity_age is not None and activity_age <= recent_window
            task_running = str(task.get("state") or "").lower() == "running"
            inferred_running = bool(bridge.get("reachable") or task_running or (self.lock_file.exists() and recent_activity))
            payload = {
                "inferred_running": inferred_running,
                "inference": "bridge_or_task_or_lock_with_recent_activity",
                "single_instance_lock_present": self.lock_file.exists(),
                "latest_database_activity_at": latest_activity,
                "latest_database_activity_minutes": activity_age,
                "recent_database_activity": recent_activity,
                "browser_bridge": bridge,
                "scheduled_task": task,
            }
            self._system_cache_at = now
            self._system_cache = copy.deepcopy(payload)
            return payload

    def health(self) -> dict[str, Any]:
        database = self.database_health()
        live_locked = self.config.get("mode") in {"paper", "shadow"} and not bool(
            (self.config.get("live") or {}).get("enabled")
        )
        return {
            "ok": bool(database.get("ok") and live_locked),
            "service": "memetrader-web",
            "time": iso(),
            "mode": self.config.get("mode"),
            "paper": self.config.get("mode") == "paper",
            "live": {"enabled": False, "locked": True, "available": False},
            "sqlite": database,
            "system": self.system_health(),
        }

    def _latest_snapshots(
        self, connection: sqlite3.Connection, token_ids: list[str]
    ) -> dict[str, sqlite3.Row]:
        if not token_ids or not self._table_exists(connection, "token_snapshots"):
            return {}
        placeholders = ",".join("?" for _ in token_ids)
        rows = connection.execute(
            f"""
            SELECT ts.* FROM token_snapshots ts
            WHERE ts.token_id IN ({placeholders})
              AND ts.id=(
                  SELECT newer.id FROM token_snapshots newer
                  WHERE newer.token_id=ts.token_id
                  ORDER BY newer.observed_at DESC,newer.id DESC LIMIT 1
              )
            """,
            token_ids,
        )
        return {str(row["token_id"]): row for row in rows}

    @staticmethod
    def _snapshot_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        raw = _json_load(row["raw_json"], {})
        rugcheck = raw.get("rugcheck") if isinstance(raw, dict) else None
        risk_score = None
        rugged = None
        if isinstance(rugcheck, dict):
            risk_score = _safe_float(rugcheck.get("score_normalised"))
            if risk_score is None:
                risk_score = _safe_float(rugcheck.get("score"))
            rugged = rugcheck.get("rugged") if isinstance(rugcheck.get("rugged"), bool) else None
        report_names = (
            name
            for name in ("goplus_evm", "honeypot_is", "goplus_solana", "rugcheck")
            if isinstance(raw.get(name), dict)
        ) if isinstance(raw, dict) else ()
        buys = row["buys_5m"]
        sells = row["sells_5m"]
        transactions = None if buys is None or sells is None else int(buys) + int(sells)
        buy_ratio = None if not transactions else int(buys) / transactions
        token_id = str(row["token_id"])
        chain, address = token_id.split(":", 1)
        snapshot = TokenSnapshot(
            chain=chain,
            address=address,
            price_usd=row["price_usd"],
            liquidity_usd=row["liquidity_usd"],
            market_cap_usd=row["market_cap_usd"],
            volume_5m_usd=row["volume_5m_usd"],
            buys_5m=buys,
            sells_5m=sells,
            buyers_5m=row["buyers_5m"],
            holders=row["holders"],
            buy_tax_pct=row["buy_tax_pct"],
            sell_tax_pct=row["sell_tax_pct"],
            honeypot=None if row["honeypot"] is None else bool(row["honeypot"]),
            sellable=None if row["sellable"] is None else bool(row["sellable"]),
            observed_at=row["observed_at"],
            provider=row["provider"],
        )
        momentum = round(CandidateEvaluator._momentum_score(snapshot), 2)
        return {
            "observed_at": row["observed_at"],
            "provider": row["provider"],
            "price_usd": row["price_usd"],
            "liquidity_usd": row["liquidity_usd"],
            "market_cap_usd": row["market_cap_usd"],
            "volume_5m_usd": row["volume_5m_usd"],
            "buys_5m": buys,
            "sells_5m": sells,
            "transactions_5m": transactions,
            "buy_ratio_5m": buy_ratio,
            "buyers_5m": row["buyers_5m"],
            "holders": row["holders"],
            "buy_tax_pct": row["buy_tax_pct"],
            "sell_tax_pct": row["sell_tax_pct"],
            "honeypot": None if row["honeypot"] is None else bool(row["honeypot"]),
            "sellable": None if row["sellable"] is None else bool(row["sellable"]),
            "risk_score": risk_score,
            "rugged": rugged,
            "security_reports": list(report_names),
            "momentum": momentum,
            "momentum_score": momentum,
        }

    def _safety_check_payload(
        self, snapshot: dict[str, Any] | None, rejected_reasons: list[str]
    ) -> dict[str, Any]:
        """Describe persisted deterministic inputs without inferring unavailable safety facts."""
        cfg = self.config.get("safety") or {}
        rejected = set(rejected_reasons)

        def minimum(name: str, value: Any, threshold: float, reason: str) -> dict[str, Any]:
            number = _safe_float(value)
            state = "fail" if reason in rejected else ("unknown" if number is None else ("pass" if number >= threshold else "fail"))
            return {"name": name, "value": number, "operator": ">=", "threshold": threshold, "state": state}

        def maximum(name: str, value: Any, threshold: float, reason: str) -> dict[str, Any]:
            number = _safe_float(value)
            state = "fail" if reason in rejected else ("unknown" if number is None else ("pass" if number <= threshold else "fail"))
            return {"name": name, "value": number, "operator": "<=", "threshold": threshold, "state": state}

        snapshot = snapshot or {}
        honeypot = snapshot.get("honeypot")
        sellable = snapshot.get("sellable")
        risk_reasons = sorted(
            reason
            for reason in rejected
            if reason.startswith(("goplus_", "solana_", "evm_", "honeypot"))
            or reason in {"not_sellable"}
        )
        risk_score = _safe_float(snapshot.get("risk_score"))
        risk_threshold = float(cfg.get("max_solana_risk_score", 79.0))
        risk_state = (
            "fail"
            if risk_reasons or snapshot.get("rugged") is True
            else "unknown"
            if risk_score is None
            else "pass"
            if risk_score <= risk_threshold
            else "fail"
        )
        checks = [
            minimum(
                "liquidity_usd",
                snapshot.get("liquidity_usd"),
                float(cfg.get("min_liquidity_usd", 12_000)),
                "low_liquidity",
            ),
            minimum(
                "transactions_5m",
                snapshot.get("transactions_5m"),
                float(cfg.get("min_5m_transactions", 8)),
                "insufficient_recent_transactions",
            ),
            minimum(
                "buy_ratio_5m",
                snapshot.get("buy_ratio_5m"),
                float(cfg.get("min_buy_ratio", 0.55)),
                "buy_flow_too_weak",
            ),
            {
                "name": "honeypot",
                "value": honeypot if isinstance(honeypot, bool) else None,
                "expected": False,
                "state": "fail" if "honeypot" in rejected or honeypot is True else ("pass" if honeypot is False else "unknown"),
            },
            {
                "name": "sellable",
                "value": sellable if isinstance(sellable, bool) else None,
                "expected": True,
                "state": "fail" if "not_sellable" in rejected or sellable is False else ("pass" if sellable is True else "unknown"),
            },
            maximum(
                "buy_tax_pct",
                snapshot.get("buy_tax_pct"),
                float(cfg.get("max_tax_pct", 12.0)),
                "buy_tax_too_high",
            ),
            maximum(
                "sell_tax_pct",
                snapshot.get("sell_tax_pct"),
                float(cfg.get("max_tax_pct", 12.0)),
                "sell_tax_too_high",
            ),
            {
                "name": "risk_score",
                "value": risk_score,
                "operator": "<=",
                "threshold": risk_threshold,
                "state": risk_state,
                "reports": list(snapshot.get("security_reports") or []),
                "failed_reasons": risk_reasons,
            },
        ]
        return {
            "basis": "persisted_snapshot_at_or_before_decision",
            "snapshot_observed_at": snapshot.get("observed_at"),
            "checks": checks,
            "unknown_count": sum(1 for item in checks if item["state"] == "unknown"),
            "failed_count": sum(1 for item in checks if item["state"] == "fail"),
        }

    def _position_payloads(self, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        if not self._table_exists(connection, "positions"):
            return []
        rows = list(connection.execute("SELECT * FROM positions ORDER BY opened_at"))
        snapshots = self._latest_snapshots(connection, [str(row["token_id"]) for row in rows])
        event_ids = [int(row["event_id"]) for row in rows]
        events: dict[int, sqlite3.Row] = {}
        if event_ids and self._table_exists(connection, "events"):
            placeholders = ",".join("?" for _ in event_ids)
            events = {
                int(row["id"]): row
                for row in connection.execute(f"SELECT * FROM events WHERE id IN ({placeholders})", event_ids)
            }
        paper = self.config.get("paper") or {}
        tiers = list(paper.get("take_profit_tiers") or [])
        output: list[dict[str, Any]] = []
        for row in rows:
            snapshot_row = snapshots.get(str(row["token_id"]))
            snapshot = self._snapshot_payload(snapshot_row)
            current_price = snapshot.get("price_usd") if snapshot else None
            quantity = float(row["quantity"])
            remaining_cost = float(row["remaining_cost_usd"])
            market_value = quantity * float(current_price) if current_price is not None else None
            unrealized = market_value - remaining_cost if market_value is not None else None
            unrealized_pct = unrealized / remaining_cost if unrealized is not None and remaining_cost else None
            entry_price = float(row["entry_price"])
            highest_price = float(row["highest_price"])
            trailing_active = highest_price / entry_price - 1 >= float(paper.get("trailing_activate_pct", 0.6))
            event = events.get(int(row["event_id"]))
            narrative_age = _minutes_since(event["last_seen_at"] if event else None)
            narrative_stale = (
                narrative_age >= float(paper.get("narrative_stale_minutes", 120))
                if narrative_age is not None
                else None
            )
            tp_index = int(row["take_profit_index"])
            output.append(
                {
                    "token_id": row["token_id"],
                    "event_id": int(row["event_id"]),
                    "chain": row["chain"],
                    "address": row["address"],
                    "symbol": row["symbol"],
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "quote_as_of": snapshot.get("observed_at") if snapshot else None,
                    "highest_price": highest_price,
                    "cost_usd": float(row["cost_usd"]),
                    "remaining_cost_usd": remaining_cost,
                    "market_value_usd": market_value,
                    "unrealized_pnl_usd": unrealized,
                    "unrealized_pnl_pct": unrealized_pct,
                    "realized_pnl_usd": float(row["realized_pnl_usd"]),
                    "opened_at": row["opened_at"],
                    "take_profit_index": tp_index,
                    "take_profit_total": len(tiers),
                    "take_profit_next": tiers[tp_index] if tp_index < len(tiers) else None,
                    "stop_price": entry_price * (1 + float(paper.get("stop_loss_pct", -0.35))),
                    "trailing_active": trailing_active,
                    "trailing_stop_price": (
                        highest_price * (1 - abs(float(paper.get("trailing_drawdown_pct", 0.28))))
                        if trailing_active
                        else None
                    ),
                    "narrative_last_seen_at": event["last_seen_at"] if event else None,
                    "narrative_age_minutes": narrative_age,
                    "narrative_stale": narrative_stale,
                    "snapshot": snapshot,
                    "simulated": True,
                }
            )
        return output

    def overview(self) -> dict[str, Any]:
        counts = {"observations": 0, "events": 0, "tokens": 0, "decisions": 0, "trades": 0}
        account = {"cash_usd": None, "realized_pnl_usd": None}
        positions: list[dict[str, Any]] = []
        daily_exposure: float | None = None
        ingestion_activity: dict[str, Any]
        with self.connect() as connection:
            ingestion_activity = self.ingestion_activity(connection)
            if connection is not None:
                for table in counts:
                    if self._table_exists(connection, table):
                        counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                if self._table_exists(connection, "paper_account"):
                    row = connection.execute(
                        "SELECT cash_usd,realized_pnl_usd,updated_at FROM paper_account WHERE singleton=1"
                    ).fetchone()
                    if row:
                        account = {
                            "cash_usd": float(row["cash_usd"]),
                            "realized_pnl_usd": float(row["realized_pnl_usd"]),
                            "updated_at": row["updated_at"],
                        }
                positions = self._position_payloads(connection)
                if self._table_exists(connection, "trades"):
                    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    row = connection.execute(
                        "SELECT COALESCE(SUM(gross_usd),0) AS value FROM trades WHERE side='BUY' AND created_at>=?",
                        (iso(start),),
                    ).fetchone()
                    daily_exposure = float(row["value"] or 0)
        missing_quotes = sum(1 for row in positions if row["market_value_usd"] is None)
        known_marks = sum(float(row["market_value_usd"] or 0) for row in positions if row["market_value_usd"] is not None)
        equity = None
        if account["cash_usd"] is not None and not missing_quotes:
            equity = float(account["cash_usd"]) + known_marks
        quote_times = [row["quote_as_of"] for row in positions if row["quote_as_of"]]
        system = self.system_health()
        runtime = {
            **system,
            "running": system["inferred_running"],
            "status": "running" if system["inferred_running"] else "stopped",
            "mode": self.config.get("mode"),
            "access": "public-protected" if self.auth_info.get("required") else "local",
        }
        database_health = self.database_health()
        counts["open_positions"] = len(positions)
        account_payload = {
            **account,
            "equity_usd": equity,
            "known_marked_value_usd": known_marks,
            "unpriced_position_count": missing_quotes,
            "daily_new_exposure_usd": daily_exposure,
            "daily_exposure_usd": daily_exposure,
            "exposure_usd": daily_exposure,
            "quote_as_of": min(quote_times) if quote_times and not missing_quotes else None,
        }
        recent_events = self.events({"limit": ["7"], "hours": ["48"]})["items"]
        return {
            "time": iso(),
            "mode": self.config.get("mode"),
            "paper": self.config.get("mode") == "paper",
            "simulated": self.config.get("mode") == "paper",
            "access": runtime["access"],
            "live_locked": True,
            "live": {"enabled": False, "locked": True, "available": False},
            "runtime": runtime,
            "sqlite": database_health,
            "health": {
                "sqlite": database_health,
                "browser_bridge": system["browser_bridge"],
                "scheduler": system["scheduled_task"],
                "web_console": {"status": "ok", "ok": True},
            },
            "account": account_payload,
            "open_positions": positions,
            "open_position_count": len(positions),
            "recent_events": recent_events,
            "counts": counts,
            "ingestion_activity": ingestion_activity,
        }

    def _observation_payload(self, row: sqlite3.Row, decision_at=None) -> dict[str, Any]:
        raw = _json_load(row["raw_json"], {})
        if not isinstance(raw, dict):
            raw = {}
        safe_raw = {key: raw[key] for key in SAFE_OBSERVATION_RAW_FIELDS if key in raw}
        role = str(row["role"] or "feature").lower()
        decision_at = decision_at or utcnow()
        rejection_reasons = evidence_rejection(row, decision_at, float((self.config.get("events") or {}).get("max_source_age_minutes", 30)))
        if role not in {"feature", "confirmation"} and "non_decision_role" not in rejection_reasons:
            rejection_reasons.append("non_decision_role")
        published = row["published_at"]
        observed = row["observed_at"]
        source_age = None
        if published and observed:
            try:
                source_age = round((parse_time(observed) - parse_time(published)).total_seconds() / 60.0, 2)
            except Exception:
                pass
        max_age = float((self.config.get("events") or {}).get("max_source_age_minutes", 30))
        freshness = "unknown"
        if source_age is not None:
            freshness = "future" if source_age < -5 else ("fresh" if source_age <= max_age else "stale")
        engagement_values = {
            key: max(0.0, _safe_float(safe_raw.get(key)) or 0.0)
            for key in ("view_count", "like_count", "repost_count", "reply_count")
        }
        engagement_total = (
            engagement_values["view_count"]
            + engagement_values["like_count"] * 20
            + engagement_values["repost_count"] * 40
            + engagement_values["reply_count"] * 10
        )
        engagement_heat = round(min(10.0, math.log10(engagement_total + 1) * 2.0), 2) if engagement_total else 0.0
        platform = _observation_platform(row["source"], row["source_kind"], row["url"])
        influence = _observation_influence(row["source_kind"], safe_raw, engagement_values)
        author = str(row["author"] or "").strip()
        source_entity_id = sanitize_source_entity_id(safe_raw.get("source_entity_id"))
        full_text = str(row["text"] or "")
        text_excerpt = full_text[:600]
        return {
            "id": int(row["id"]),
            "source": row["source"],
            "source_kind": row["source_kind"],
            "title": row["title"],
            "text": text_excerpt,
            "text_truncated": len(full_text) > len(text_excerpt),
            "url": _safe_url(row["url"]),
            "author": author or None,
            "author_known": bool(author),
            "platform": platform,
            "source_entity_id": source_entity_id or None,
            "cross_platform_entity": (
                {
                    "id": source_entity_id,
                    "origin": f"entity:{source_entity_id}",
                    "deduplication": "explicit_persisted_entity_only",
                }
                if source_entity_id
                else None
            ),
            "influence": influence,
            "published_at": published,
            "observed_at": observed,
            "ingested_at": row["ingested_at"],
            "availability_proof": row["availability_proof"],
            "capture_phase": row["capture_phase"],
            "role": role,
            "original_role": safe_raw.get("original_role"),
            "decision_eligible": not rejection_reasons,
            "rejection_reasons": rejection_reasons,
            "source_age_minutes": source_age,
            "freshness": freshness,
            "origin": evidence_origin(row),
            "engagement_heat": engagement_heat,
            "engagement_observed": any(engagement_values.values()),
            "metadata": safe_raw,
        }

    @staticmethod
    def _rank_evidence(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        origin_counts: dict[str, int] = {}
        for item in observations:
            origin = str(item.get("origin") or "")
            if origin:
                origin_counts[origin] = origin_counts.get(origin, 0) + 1
        first_observed_id = None
        if observations:
            first_observed_id = min(
                observations,
                key=lambda item: (
                    parse_time(item.get("observed_at") or item.get("ingested_at") or "1970-01-01T00:00:00Z"),
                    int(item.get("id") or 0),
                ),
            ).get("id")
        ranked: list[dict[str, Any]] = []
        role_scores = {"feature": 20.0, "confirmation": 15.0, "identity": 2.0, "promotion": 0.0}
        freshness_scores = {"fresh": 8.0, "unknown": 2.0, "stale": 0.0, "future": 0.0}
        for item in observations:
            value = copy.deepcopy(item)
            role = str(value.get("role") or "identity")
            eligible = bool(value.get("decision_eligible"))
            freshness = str(value.get("freshness") or "unknown")
            origin = str(value.get("origin") or "")
            independent = bool(origin and origin_counts.get(origin) == 1)
            first_observed = value.get("id") == first_observed_id
            influence = value.get("influence") if isinstance(value.get("influence"), dict) else {}
            authority_tier = str(influence.get("authority_tier") or "unknown")
            authority_score = AUTHORITY_TIER_SCORES.get(authority_tier, 0.0)
            curated_watch = influence.get("curated_watch") if isinstance(influence.get("curated_watch"), dict) else {}
            curated_priority = int(curated_watch.get("priority") or 0)
            decision_utility = (60.0 if eligible else 0.0) + role_scores.get(role, 0.0)
            freshness_score = freshness_scores.get(freshness, 0.0)
            score = decision_utility
            reasons = ["decision_eligible"] if eligible else ["context_only"]
            reasons.append(f"role:{role}")
            if authority_score:
                score += authority_score / 20.0 * 8.0
                reasons.append(f"authority:{authority_tier}")
            else:
                reasons.append("authority_unknown")
            if freshness == "fresh":
                score += freshness_score
                reasons.append("fresh")
            elif freshness == "unknown":
                score += freshness_score
                reasons.append("freshness_unknown")
            else:
                reasons.append(freshness)
            if independent:
                score += 2.0
                reasons.append("independent_origin")
            if value.get("url"):
                score += 1.0
                reasons.append("direct_source_link")
            if curated_priority:
                score += curated_priority / 5.0
                reasons.append(f"configured_curated_tier:{curated_priority}")
            heat = max(0.0, min(10.0, _safe_float(value.get("engagement_heat")) or 0.0))
            score += heat / 10.0
            if heat:
                reasons.append("observed_engagement")
            if first_observed:
                reasons.append("first_locally_observed_source")
            if role in {"identity", "promotion"} or not eligible:
                source_group = "identity_promotion_context"
            elif role == "feature":
                source_group = "original_feature"
            elif str(value.get("source_kind") or "").lower() in {"social", "official_social"} and not authority_score:
                source_group = "community_amplification"
            else:
                source_group = "authoritative_confirmation"
            value["first_observed_source"] = first_observed
            value["independent_origin"] = independent
            value["source_group"] = source_group
            value["ranking_dimensions"] = {
                "decision_utility": round(decision_utility, 2),
                "authority": round(authority_score, 2) if authority_score else None,
                "freshness": round(freshness_score, 2),
                "curated_watch_priority": curated_priority or None,
                "engagement_heat": round(heat, 2) if heat else None,
            }
            value["priority_score"] = round(max(0.0, min(100.0, score)), 2)
            value["priority_reasons"] = reasons
            value["ranking_method"] = "decision_utility_authority_freshness"
            ranked.append(value)
        ranked.sort(
            key=lambda item: (
                float((item.get("ranking_dimensions") or {}).get("decision_utility") or 0),
                float((item.get("ranking_dimensions") or {}).get("authority") or 0),
                float((item.get("ranking_dimensions") or {}).get("freshness") or 0),
                float((item.get("ranking_dimensions") or {}).get("curated_watch_priority") or 0),
                bool(item.get("independent_origin")),
                float((item.get("ranking_dimensions") or {}).get("engagement_heat") or 0),
                parse_time(item.get("observed_at") or "1970-01-01T00:00:00Z"),
            ),
            reverse=True,
        )
        for index, item in enumerate(ranked, 1):
            item["priority_rank"] = index
        return ranked

    def _events_payload(
        self, connection: sqlite3.Connection, rows: list[sqlite3.Row], *, include_observations: bool
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        curated_accounts: dict[tuple[str, str], dict[str, Any]] = {}
        for account in self.console_settings().get("watch_accounts", []):
            if not account.get("enabled", True):
                continue
            platform = str(account.get("platform") or "").strip().lower()
            for identity in (account.get("handle"), account.get("display_name")):
                identity_key = str(identity or "").strip().casefold().lstrip("@")
                if platform and identity_key:
                    curated_accounts[(platform, identity_key)] = account
        ids = [int(row["id"]) for row in rows]
        grouped: dict[int, list[dict[str, Any]]] = {event_id: [] for event_id in ids}
        placeholders = ",".join("?" for _ in ids)
        if self._table_exists(connection, "event_observations") and self._table_exists(connection, "observations"):
            for observation in connection.execute(
                f"""
                SELECT eo.event_id,o.* FROM event_observations eo
                JOIN observations o ON o.id=eo.observation_id
                WHERE eo.event_id IN ({placeholders}) ORDER BY o.observed_at ASC,o.id ASC
                """,
                ids,
            ):
                value = self._observation_payload(observation)
                platform = str((value.get("platform") or {}).get("id") or "").lower()
                author = str(value.get("author") or "").strip().casefold().lstrip("@")
                curated = curated_accounts.get((platform, author))
                if curated:
                    priority = int(curated.get("priority") or 3)
                    value["influence"]["curated_watch"] = {
                        "configured": True,
                        "priority": priority,
                        "tier": CURATED_PRIORITY_TIERS[priority],
                        "display_name": str(curated.get("display_name") or "") or None,
                    }
                grouped[int(observation["event_id"])].append(value)
        output: list[dict[str, Any]] = []
        for row in rows:
            event_id = int(row["id"])
            observations = grouped.get(event_id, [])
            ranked_observations = self._rank_evidence(observations)
            origins = {item["origin"] for item in observations if item["origin"]}
            eligible_observations = [item for item in observations if item["decision_eligible"]]
            eligible_origins = {
                item["origin"] for item in eligible_observations if item["origin"]
            }
            eligible_times = [item["observed_at"] for item in eligible_observations if item["observed_at"]]
            eligible_latest_at = max(eligible_times, key=parse_time) if eligible_times else None
            roles: dict[str, int] = {}
            for item in observations:
                roles[item["role"]] = roles.get(item["role"], 0) + 1
            payload = {
                "id": event_id,
                "title": row["title"],
                "aliases": _json_load(row["aliases_json"], []),
                "attention": float(row["attention"]),
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "age_minutes": _minutes_since(row["first_seen_at"]),
                "freshness_minutes": _minutes_since(eligible_latest_at),
                "status": row["status"],
                "source_count": len(origins),
                "total_source_count": len(origins),
                "eligible_source_count": len(eligible_origins),
                "eligible_latest_at": eligible_latest_at,
                "observation_count": len(observations),
                "roles": roles,
                "decision_eligible": bool(eligible_origins),
                "event_url": f"#/events/{event_id}",
                "evidence_ranking": {
                    "method": "decision_utility_authority_freshness",
                    "order": ["decision_utility", "known_authority", "freshness", "configured_curated_tier", "independent_origin", "observed_engagement"],
                },
            }
            if ranked_observations:
                lead = ranked_observations[0]
                payload["lead_source"] = {
                    key: lead.get(key)
                    for key in (
                        "id", "platform", "author", "author_known", "source_entity_id", "cross_platform_entity",
                        "source_kind", "role", "source_group",
                        "decision_eligible", "freshness", "influence", "url", "first_observed_source", "independent_origin",
                    )
                }
            else:
                payload["lead_source"] = None
            if include_observations:
                payload["observations"] = ranked_observations
            output.append(payload)
        return output

    def events(self, query: dict[str, list[str]]) -> dict[str, Any]:
        limit = _query_int(query, "limit", 50, 1, 200)
        offset = _query_int(query, "offset", 0, 0, 1_000_000)
        hours = _query_int(query, "hours", 48, 1, 8760)
        requested_status = str((query.get("status") or [""])[0]).strip()
        where = ["last_seen_at>=?"]
        params: list[Any] = [iso(utcnow() - timedelta(hours=hours))]
        if requested_status:
            where.append("status=?")
            params.append(requested_status)
        with self.connect() as connection:
            if connection is None or not self._table_exists(connection, "events"):
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            total = int(connection.execute(f"SELECT COUNT(*) FROM events WHERE {' AND '.join(where)}", params).fetchone()[0])
            rows = list(
                connection.execute(
                    f"SELECT * FROM events WHERE {' AND '.join(where)} ORDER BY last_seen_at DESC,attention DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                )
            )
            items = self._events_payload(connection, rows, include_observations=False)
        requested_role = str((query.get("role") or [""])[0]).strip().lower()
        if requested_role:
            items = [item for item in items if item["roles"].get(requested_role)]
        return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": iso()}

    def event_detail(self, event_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            if connection is None or not self._table_exists(connection, "events"):
                raise APIError(404, "event not found")
            row = connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if row is None:
                raise APIError(404, "event not found")
            event = self._events_payload(connection, [row], include_observations=True)[0]
            decisions = self._decision_rows(connection, "d.event_id=?", [event_id], 200, 0)
            candidate_ranking = self._candidate_ranking(connection, event_id)
            ranked_token_ids = [
                str(item["token_id"])
                for item in (candidate_ranking or {}).get("candidates", [])
                if item.get("token_id")
            ]
            token_ids = list(
                dict.fromkeys(
                    [str(item["token_id"]) for item in decisions if item.get("token_id")]
                    + ranked_token_ids
                )
            )
            event["decisions"] = decisions
            event["related_token_ids"] = token_ids
            event["candidate_ranking"] = candidate_ranking
            event["ranking_available"] = candidate_ranking is not None
            event["ranking_persistence_gap"] = (
                None if candidate_ranking else "candidate_ranking_not_available_for_this_event"
            )
            event["ranked_sources"] = event["observations"]
            group_order = (
                "original_feature",
                "authoritative_confirmation",
                "community_amplification",
                "identity_promotion_context",
            )
            event["source_groups"] = [
                {
                    "id": group,
                    "items": [item for item in event["observations"] if item.get("source_group") == group],
                }
                for group in group_order
                if any(item.get("source_group") == group for item in event["observations"])
            ]
            event["evidence_timeline"] = sorted(
                event["observations"],
                key=lambda item: parse_time(item.get("observed_at") or "1970-01-01T00:00:00Z"),
            )
            return event

    def _token_links(self, connection: sqlite3.Connection, token_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        links: dict[str, list[dict[str, Any]]] = {token_id: [] for token_id in token_ids}
        if not token_ids:
            return links
        placeholders = ",".join("?" for _ in token_ids)
        if self._table_exists(connection, "decisions"):
            for row in connection.execute(
                f"SELECT id,event_id,token_id,action,created_at FROM decisions WHERE token_id IN ({placeholders})",
                token_ids,
            ):
                links[str(row["token_id"])].append(
                    {
                        "direction": "decision",
                        "event_id": int(row["event_id"]),
                        "decision_id": int(row["id"]),
                        "action": row["action"],
                        "observed_at": row["created_at"],
                    }
                )
        if self._table_exists(connection, "observations") and self._table_exists(connection, "event_observations"):
            for row in connection.execute(
                """
                SELECT eo.event_id,o.id,o.observed_at,o.raw_json FROM observations o
                JOIN event_observations eo ON eo.observation_id=o.id
                WHERE o.raw_json LIKE '%reverse_token_id%'
                """
            ):
                raw = _json_load(row["raw_json"], {})
                token_id = str(raw.get("reverse_token_id") or "") if isinstance(raw, dict) else ""
                if token_id in links:
                    links[token_id].append(
                        {
                            "direction": "token_to_event",
                            "event_id": int(row["event_id"]),
                            "observation_id": int(row["id"]),
                            "observed_at": row["observed_at"],
                        }
                    )
        for token_id in links:
            links[token_id].sort(key=lambda item: str(item.get("observed_at") or ""), reverse=True)
        return links

    def tokens(self, query: dict[str, list[str]]) -> dict[str, Any]:
        limit = _query_int(query, "limit", 100, 1, 300)
        offset = _query_int(query, "offset", 0, 0, 1_000_000)
        hours = _query_int(query, "hours", 24, 1, 8760)
        chain = str((query.get("chain") or [""])[0]).strip().lower()
        where = ["last_seen_at>=?"]
        params: list[Any] = [iso(utcnow() - timedelta(hours=hours))]
        if chain:
            where.append("chain=?")
            params.append(chain)
        with self.connect() as connection:
            if connection is None or not self._table_exists(connection, "tokens"):
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            total = int(connection.execute(f"SELECT COUNT(*) FROM tokens WHERE {' AND '.join(where)}", params).fetchone()[0])
            rows = list(
                connection.execute(
                    f"SELECT * FROM tokens WHERE {' AND '.join(where)} ORDER BY last_seen_at DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                )
            )
            token_ids = [str(row["token_id"]) for row in rows]
            snapshots = self._latest_snapshots(connection, token_ids)
            links = self._token_links(connection, token_ids)
            items = [self._token_payload(row, snapshots.get(str(row["token_id"])), links[str(row["token_id"])]) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": iso()}

    def _token_payload(
        self, row: sqlite3.Row, snapshot_row: sqlite3.Row | None, links: list[dict[str, Any]]
    ) -> dict[str, Any]:
        social = _json_load(row["social_urls_json"], [])
        snapshot = self._snapshot_payload(snapshot_row)
        decision_links = [item for item in links if item["direction"] == "decision"]
        reverse_links = [item for item in links if item["direction"] == "token_to_event"]
        return {
            "token_id": row["token_id"],
            "chain": row["chain"],
            "address": row["address"],
            "name": row["name"],
            "symbol": row["symbol"],
            "created_at": row["created_at"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "source": row["source"],
            "url": _safe_url(row["url"]),
            "social_urls": [url for value in social if (url := _safe_url(value))],
            "snapshot": snapshot,
            "momentum": snapshot.get("momentum") if snapshot else None,
            "evidence_chain": links,
            "evidence_count": len(links),
            "evidence_record_count": len(links),
            "event_to_token": "persisted decision relation" if decision_links else None,
            "token_to_event": "verified reverse-context observation" if reverse_links else None,
            "evidence_role": "confirmation" if reverse_links else ("decision_record" if decision_links else None),
            "linked_event_ids": sorted({int(item["event_id"]) for item in links}),
        }

    def token_detail(self, token_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            if connection is None or not self._table_exists(connection, "tokens"):
                raise APIError(404, "token not found")
            row = connection.execute("SELECT * FROM tokens WHERE token_id=?", (token_id,)).fetchone()
            if row is None:
                raise APIError(404, "token not found")
            snapshot = self._latest_snapshots(connection, [token_id]).get(token_id)
            links = self._token_links(connection, [token_id])[token_id]
            payload = self._token_payload(row, snapshot, links)
            linked_event_ids = payload["linked_event_ids"]
            evidence: list[dict[str, Any]] = []
            if linked_event_ids and self._table_exists(connection, "event_observations"):
                placeholders = ",".join("?" for _ in linked_event_ids)
                evidence = [
                    self._observation_payload(item)
                    for item in connection.execute(
                        f"""
                        SELECT DISTINCT o.* FROM observations o
                        JOIN event_observations eo ON eo.observation_id=o.id
                        WHERE eo.event_id IN ({placeholders})
                        ORDER BY o.observed_at ASC,o.id ASC
                        """,
                        linked_event_ids,
                    )
                ]
            payload["evidence"] = evidence
            snapshots = []
            if self._table_exists(connection, "token_snapshots"):
                snapshots = [
                    self._snapshot_payload(item)
                    for item in connection.execute(
                        "SELECT * FROM token_snapshots WHERE token_id=? ORDER BY observed_at DESC,id DESC LIMIT 200",
                        (token_id,),
                    )
                ]
            payload["snapshot_history"] = snapshots
            payload["decisions"] = self._decision_rows(connection, "d.token_id=?", [token_id], 200, 0)
            return payload

    def _candidate_ranking(
        self,
        connection: sqlite3.Connection,
        event_id: int,
    ) -> dict[str, Any] | None:
        if not self._table_exists(connection, "kv"):
            return None
        row = connection.execute(
            "SELECT value_json FROM kv WHERE key=?",
            (f"candidate_ranking:{int(event_id)}",),
        ).fetchone()
        raw = _json_load(row["value_json"], None) if row else None
        if not isinstance(raw, dict):
            return None

        def text_value(value: Any, limit: int = 512) -> str | None:
            if value is None:
                return None
            return str(value)[:limit]

        def reasons(value: Any) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item)[:300] for item in value[:100]]

        def integer(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def snapshot_payload(value: Any) -> dict[str, Any] | None:
            if not isinstance(value, dict):
                return None
            reports = value.get("security_reports")
            allowed_reports = {"goplus_evm", "honeypot_is", "goplus_solana", "rugcheck"}
            return {
                "observed_at": text_value(value.get("observed_at")),
                "provider": text_value(value.get("provider"), 120),
                "price_usd": _safe_float(value.get("price_usd")),
                "liquidity_usd": _safe_float(value.get("liquidity_usd")),
                "market_cap_usd": _safe_float(value.get("market_cap_usd")),
                "volume_5m_usd": _safe_float(value.get("volume_5m_usd")),
                "buys_5m": integer(value.get("buys_5m")),
                "sells_5m": integer(value.get("sells_5m")),
                "transactions_5m": integer(value.get("transactions_5m")),
                "buyers_5m": integer(value.get("buyers_5m")),
                "holders": integer(value.get("holders")),
                "buy_tax_pct": _safe_float(value.get("buy_tax_pct")),
                "sell_tax_pct": _safe_float(value.get("sell_tax_pct")),
                "honeypot": value.get("honeypot") if isinstance(value.get("honeypot"), bool) else None,
                "sellable": value.get("sellable") if isinstance(value.get("sellable"), bool) else None,
                "risk_score": _safe_float(value.get("risk_score")),
                "rugged": value.get("rugged") if isinstance(value.get("rugged"), bool) else None,
                "security_reports": [
                    str(item) for item in reports[:10]
                    if str(item) in allowed_reports
                ] if isinstance(reports, list) else [],
            }

        candidates: list[dict[str, Any]] = []
        for value in (raw.get("candidates") if isinstance(raw.get("candidates"), list) else [])[:25]:
            if not isinstance(value, dict):
                continue
            rank = integer(value.get("rank"))
            token_id = text_value(value.get("token_id"), 512)
            if rank is None or rank < 1 or not token_id:
                continue
            rejected = reasons(value.get("rejected_reasons"))
            snapshot = snapshot_payload(value.get("snapshot"))
            safety = value.get("safety") if isinstance(value.get("safety"), dict) else {}
            tie_break = value.get("tie_break") if isinstance(value.get("tie_break"), dict) else {}
            action = str(value.get("action") or "NOT_SELECTED").upper()
            if action not in {"WAIT", "REJECT", "CANDIDATE", "NOT_SELECTED", "PENDING_RUNTIME"}:
                action = "NOT_SELECTED"
            candidate = {
                "rank": rank,
                "token_id": token_id,
                "chain": text_value(value.get("chain"), 32),
                "address": text_value(value.get("address"), 512),
                "name": text_value(value.get("name"), 200),
                "symbol": text_value(value.get("symbol"), 80),
                "candidate_score": _safe_float(value.get("candidate_score")),
                "match_score": _safe_float(value.get("match_score")),
                "canonical_margin": _safe_float(value.get("canonical_margin")),
                "raw_canonical_margin": _safe_float(value.get("raw_canonical_margin")),
                "score_gap_to_selected": _safe_float(value.get("score_gap_to_selected")),
                "score_gap_to_score_leader": _safe_float(value.get("score_gap_to_score_leader")),
                "score_gap_to_next_rank": _safe_float(value.get("score_gap_to_next_rank")),
                "selection_status": text_value(value.get("selection_status"), 80),
                "action": action,
                "position_usd": _safe_float(value.get("position_usd")) or 0.0,
                "reasons": reasons(value.get("reasons")),
                "rejected_reasons": rejected,
                "snapshot": snapshot,
                "safety": {
                    "status": text_value(safety.get("status"), 40) or "not_checked",
                    "rejected_reasons": reasons(safety.get("rejected_reasons")),
                },
                "tie_break": {
                    "pre_agent_rank": integer(tie_break.get("pre_agent_rank")),
                    "rank_changed": tie_break.get("rank_changed") is True,
                    "preferred": tie_break.get("preferred") is True,
                },
            }
            candidate["safety_checks"] = self._safety_check_payload(snapshot, rejected)
            candidates.append(candidate)
        candidates.sort(key=lambda item: item["rank"])

        final = raw.get("final_outcome") if isinstance(raw.get("final_outcome"), dict) else None
        final_outcome = None
        if final is not None:
            decision_id = integer(final.get("decision_id"))
            action = str(final.get("action") or "WAIT").upper()
            if decision_id is None or action not in {"WAIT", "REJECT", "CANDIDATE"}:
                final = None
        if final is not None:
            decision_id = integer(final.get("decision_id"))
            action = str(final.get("action") or "WAIT").upper()
            if action not in {"WAIT", "REJECT", "CANDIDATE"}:
                action = "WAIT"
            final_outcome = {
                "decision_id": decision_id,
                "action": action,
                "token_id": text_value(final.get("token_id"), 512) or "",
                "candidate_score": _safe_float(final.get("candidate_score")) or 0.0,
                "match_score": _safe_float(final.get("match_score")) or 0.0,
                "canonical_margin": _safe_float(final.get("canonical_margin")) or 0.0,
                "position_usd": _safe_float(final.get("position_usd")) or 0.0,
                "reasons": reasons(final.get("reasons")),
                "rejected_reasons": reasons(final.get("rejected_reasons")),
                "created_at": text_value(final.get("created_at")),
            }
        if final_outcome is None:
            for candidate in candidates:
                if str(candidate.get("selection_status") or "").startswith("selected_"):
                    candidate["action"] = "PENDING_RUNTIME"
                    candidate["position_usd"] = 0.0
        tie_break = raw.get("tie_break") if isinstance(raw.get("tie_break"), dict) else {}
        status = text_value(raw.get("status"), 80) or "unknown"
        if final_outcome is None and status == "completed":
            status = "pending_runtime"
        return {
            "available": True,
            "version": integer(raw.get("version")) or 1,
            "event_id": int(event_id),
            "evaluated_at": text_value(raw.get("evaluated_at")),
            "status": status,
            "outcome": (
                text_value(raw.get("outcome"), 80) or "UNAVAILABLE"
                if final_outcome is not None
                else "UNAVAILABLE"
            ),
            "outcome_reasons": reasons(raw.get("outcome_reasons")),
            "ranking_method": text_value(raw.get("ranking_method"), 160),
            "candidate_count_total": integer(raw.get("candidate_count_total")) or 0,
            "candidate_count_persisted": len(candidates),
            "candidates_truncated": raw.get("candidates_truncated") is True,
            "tie_break": {
                "used": tie_break.get("used") is True,
                "tier": text_value(tie_break.get("tier"), 40),
                "confidence": _safe_float(tie_break.get("confidence")),
                "preferred_token_id": text_value(tie_break.get("preferred_token_id"), 512),
            },
            "candidates": candidates,
            "final_outcome": final_outcome,
        }

    def _decision_rows(
        self,
        connection: sqlite3.Connection,
        where: str,
        params: list[Any],
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        if not self._table_exists(connection, "decisions"):
            return []
        rows = list(
            connection.execute(
                f"""
                SELECT d.*,e.title AS event_title,t.name AS token_name,t.symbol AS token_symbol,t.chain AS token_chain,
                       t.address AS token_address
                FROM decisions d
                LEFT JOIN events e ON e.id=d.event_id
                LEFT JOIN tokens t ON t.token_id=d.token_id
                WHERE {where} ORDER BY d.id DESC LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
        )
        output = []
        ranking_cache: dict[int, dict[str, Any] | None] = {}
        for row in rows:
            action = str(row["action"])
            rejected_reasons = _json_load(row["rejected_reasons_json"], [])
            snapshot_row = None
            if row["token_id"] and self._table_exists(connection, "token_snapshots"):
                snapshot_row = connection.execute(
                    """
                    SELECT * FROM token_snapshots
                    WHERE token_id=? AND observed_at<=?
                    ORDER BY observed_at DESC,id DESC LIMIT 1
                    """,
                    (str(row["token_id"]), row["created_at"]),
                ).fetchone()
            snapshot = self._snapshot_payload(snapshot_row)
            event_id = int(row["event_id"])
            if event_id not in ranking_cache:
                ranking_cache[event_id] = self._candidate_ranking(connection, event_id)
            latest_ranking = ranking_cache[event_id]
            final_outcome = latest_ranking.get("final_outcome") if latest_ranking else None
            ranking = (
                latest_ranking
                if isinstance(final_outcome, dict) and final_outcome.get("decision_id") == int(row["id"])
                else None
            )
            selected_rank = None
            if ranking:
                selected = next(
                    (
                        item for item in ranking["candidates"]
                        if item.get("token_id") == str(row["token_id"])
                    ),
                    None,
                )
                selected_rank = selected.get("rank") if selected else None
            output.append(
                {
                    "id": int(row["id"]),
                    "event_id": event_id,
                    "event_title": row["event_title"],
                    "token_id": row["token_id"],
                    "token": {
                        "name": row["token_name"],
                        "symbol": row["token_symbol"],
                        "chain": row["token_chain"],
                        "address": row["token_address"],
                    },
                    "action": action,
                    "is_wait": action == "WAIT",
                    "score": float(row["score"]),
                    "candidate_score": float(row["score"]),
                    "match_score": float(row["match_score"]),
                    "canonical_margin": float(row["canonical_margin"]),
                    "reasons": _json_load(row["reasons_json"], []),
                    "rejected_reasons": rejected_reasons,
                    "position_usd": float(row["position_usd"]),
                    "created_at": row["created_at"],
                    "snapshot": snapshot,
                    "safety_checks": self._safety_check_payload(snapshot, rejected_reasons),
                    "rank": selected_rank,
                    "candidate_ranking": ranking,
                    "ranking_available": ranking is not None,
                    "persistence_gap": None if ranking else "candidate_ranking_unavailable_for_this_decision",
                    "simulated": self.config.get("mode") == "paper",
                }
            )
        return output

    def decisions(self, query: dict[str, list[str]]) -> dict[str, Any]:
        limit = _query_int(query, "limit", 100, 1, 300)
        offset = _query_int(query, "offset", 0, 0, 1_000_000)
        where = ["1=1"]
        params: list[Any] = []
        action = str((query.get("action") or [""])[0]).strip().upper()
        if action:
            where.append("d.action=?")
            params.append(action)
        event_id = str((query.get("event_id") or [""])[0]).strip()
        if event_id:
            try:
                params.append(int(event_id))
            except ValueError:
                raise APIError(400, "event_id must be an integer") from None
            where.append("d.event_id=?")
        with self.connect() as connection:
            if connection is None or not self._table_exists(connection, "decisions"):
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            total_where = " AND ".join(part.replace("d.", "") for part in where)
            total = int(connection.execute(f"SELECT COUNT(*) FROM decisions WHERE {total_where}", params).fetchone()[0])
            items = self._decision_rows(connection, " AND ".join(where), params, limit, offset)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "ranking_available": any(item["ranking_available"] for item in items),
            "ranking_coverage": {
                "available": sum(1 for item in items if item["ranking_available"]),
                "unavailable": sum(1 for item in items if not item["ranking_available"]),
            },
            "as_of": iso(),
        }

    def portfolio(self, query: dict[str, list[str]]) -> dict[str, Any]:
        trade_limit = _query_int(query, "trade_limit", 200, 1, 1000)
        account = {"cash_usd": None, "realized_pnl_usd": None, "updated_at": None}
        positions: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        daily_exposure: float | None = None
        with self.connect() as connection:
            if connection is not None:
                if self._table_exists(connection, "paper_account"):
                    row = connection.execute("SELECT * FROM paper_account WHERE singleton=1").fetchone()
                    if row:
                        account = {
                            "cash_usd": float(row["cash_usd"]),
                            "realized_pnl_usd": float(row["realized_pnl_usd"]),
                            "updated_at": row["updated_at"],
                        }
                positions = self._position_payloads(connection)
                if self._table_exists(connection, "trades"):
                    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    exposure_row = connection.execute(
                        "SELECT COALESCE(SUM(gross_usd),0) AS value FROM trades WHERE side='BUY' AND created_at>=?",
                        (iso(start),),
                    ).fetchone()
                    daily_exposure = float(exposure_row["value"] or 0)
                    trades = [
                        {
                            "id": int(row["id"]),
                            "token_id": row["token_id"],
                            "event_id": int(row["event_id"]),
                            "side": row["side"],
                            "quantity": float(row["quantity"]),
                            "price": float(row["price"]),
                            "gross_usd": float(row["gross_usd"]),
                            "fee_usd": float(row["fee_usd"]),
                            "reason": row["reason"],
                            "created_at": row["created_at"],
                            "simulated": True,
                        }
                        for row in connection.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (trade_limit,))
                    ]
        missing = sum(1 for row in positions if row["market_value_usd"] is None)
        known_marks = sum(float(row["market_value_usd"] or 0) for row in positions if row["market_value_usd"] is not None)
        account["known_marked_value_usd"] = known_marks
        account["unpriced_position_count"] = missing
        account["equity_usd"] = (
            float(account["cash_usd"]) + known_marks if account["cash_usd"] is not None and not missing else None
        )
        account["unrealized_pnl_usd"] = (
            sum(float(row["unrealized_pnl_usd"]) for row in positions) if not missing else None
        )
        account["daily_exposure_usd"] = daily_exposure
        account["exposure_usd"] = daily_exposure
        return {
            "mode": "paper",
            "simulated": True,
            "live": {"enabled": False, "locked": True, "available": False},
            "account": account,
            "summary": account,
            "positions": positions,
            "trades": trades,
            "as_of": iso(),
        }

    @staticmethod
    def _agent_last_result(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        events = value.get("events") if isinstance(value.get("events"), list) else []
        return {
            "status": value.get("status"),
            "run_at": value.get("run_at"),
            "token_id": value.get("token_id"),
            "confidence": value.get("confidence"),
            "domains": value.get("domains") if isinstance(value.get("domains"), list) else [],
            "event_count": len(events),
            "accepted_count": len(value.get("accepted") or []) if isinstance(value.get("accepted"), list) else None,
            "rejected_count": len(value.get("rejected") or []) if isinstance(value.get("rejected"), list) else None,
            "model": metadata.get("model"),
            "reasoning_effort": metadata.get("reasoning_effort"),
            "tokens_used": metadata.get("tokens_used"),
            "attempt_count": len(metadata.get("attempts") or []) if isinstance(metadata.get("attempts"), list) else None,
            "next_interval_minutes": value.get("next_interval_minutes"),
        }

    @staticmethod
    def _agent_usage_rows(
        connection: sqlite3.Connection | None,
        since: str,
        group_columns: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        if connection is None or not WebData._table_exists(connection, "agent_attempts"):
            return []
        allowed = {"task", "model", "reasoning_effort"}
        if any(column not in allowed for column in group_columns):
            raise ValueError("unsupported usage grouping")
        prefix = ",".join(group_columns)
        select_prefix = f"{prefix}," if prefix else ""
        group = f" GROUP BY {prefix}" if prefix else ""
        rows = connection.execute(
            f"""
            SELECT {select_prefix}
                   COUNT(DISTINCT run_id) AS calls,
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN fallback=1 THEN 1 ELSE 0 END) AS fallback_attempts,
                   SUM(input_tokens) AS input_tokens,
                   SUM(cached_input_tokens) AS cached_input_tokens,
                   SUM(cache_write_input_tokens) AS cache_write_input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(reasoning_output_tokens) AS reasoning_output_tokens,
                   SUM(total_tokens) AS total_tokens,
                   SUM(CASE WHEN total_tokens IS NOT NULL THEN 1 ELSE 0 END) AS known_usage_attempts,
                   SUM(CASE WHEN total_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_usage_attempts
            FROM agent_attempts WHERE finished_at>=?{group}
            ORDER BY total_tokens DESC,attempts DESC
            """,
            (since,),
        )
        output: list[dict[str, Any]] = []
        for row in rows:
            attempts = int(row["attempts"] or 0)
            known = int(row["known_usage_attempts"] or 0)
            item = {column: row[column] for column in group_columns}
            item.update(
                {
                    "calls": int(row["calls"] or 0),
                    "attempts": attempts,
                    "fallback_attempts": int(row["fallback_attempts"] or 0),
                    "input_tokens": row["input_tokens"],
                    "cached_input_tokens": row["cached_input_tokens"],
                    "cache_write_input_tokens": row["cache_write_input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "reasoning_output_tokens": row["reasoning_output_tokens"],
                    "total_tokens": row["total_tokens"],
                    "known_usage_attempts": known,
                    "unknown_usage_attempts": int(row["unknown_usage_attempts"] or 0),
                    "coverage_pct": round(known / attempts * 100, 2) if attempts else None,
                }
            )
            output.append(item)
        return output

    def agents(self) -> dict[str, Any]:
        cfg = self.config.get("autonomous_search") or {}
        codex_path = str(cfg.get("codex_path") or "codex")
        codex_available = shutil.which(codex_path) is not None
        day = utcnow().date().isoformat()
        specs = {
            "trend_scout": {
                "profile": "trend_scout",
                "call_budget": int(cfg.get("trend_scout_daily_limit", 0)),
                "token_budget": int(cfg.get("trend_scout_daily_token_budget", 0)),
                "reserve": int(cfg.get("trend_scout_token_reserve_per_call", 0)),
                "run_key": TREND_RUN_KEY,
                "result_key": TREND_RESULT_KEY,
            },
            "source_discovery": {
                "profile": "source_discovery",
                "call_budget": int(cfg.get("source_discovery_daily_limit", 0)),
                "token_budget": int(cfg.get("source_discovery_daily_token_budget", 0)),
                "reserve": int(cfg.get("source_discovery_token_reserve_per_call", 0)),
                "run_key": SOURCE_RUN_KEY,
                "result_key": SOURCE_RESULT_KEY,
            },
            "token_context": {
                "profile": "token_context",
                "call_budget": int(cfg.get("context_search_daily_limit", 0)),
                "token_budget": int(cfg.get("token_context_daily_token_budget", 0)),
                "reserve": int(cfg.get("token_context_token_reserve_per_call", 0)),
                "run_key": CONTEXT_RUN_KEY,
                "result_key": CONTEXT_RESULT_KEY,
            },
        }
        output = []
        usage_summary: dict[str, Any] = {}
        usage_breakdown: dict[str, Any] = {}
        recent_attempts: list[dict[str, Any]] = []
        with self.connect() as connection:
            for kind, item in specs.items():
                profile = dict((cfg.get("profiles") or {}).get(item["profile"]) or {})
                calls = int(self._kv(connection, f"autonomous_search_quota:{day}:{kind}", 0))
                tokens = int(self._kv(connection, f"autonomous_search_tokens:{day}:{kind}", 0))
                last_run = self._kv(connection, item["run_key"])
                last_result = self._agent_last_result(self._kv(connection, item["result_key"]))
                if kind == "trend_scout":
                    recorded_interval = _safe_float((last_result or {}).get("next_interval_minutes"))
                    interval = recorded_interval if recorded_interval is not None else float(cfg.get("trend_scout_base_interval_minutes", 12))
                    next_run = _iso_add(last_run, timedelta(minutes=interval))
                    trigger = "scheduled"
                elif kind == "source_discovery":
                    status = str((last_result or {}).get("status") or "")
                    if status == "agent_error":
                        interval = float(cfg.get("source_error_retry_hours", 4))
                    elif status == "completed" and (last_result or {}).get("accepted_count") == 0:
                        interval = float(cfg.get("source_empty_retry_hours", 12))
                    else:
                        interval = float(cfg.get("source_discovery_interval_hours", 24))
                    next_run = _iso_add(last_run, timedelta(hours=interval))
                    trigger = "scheduled"
                else:
                    interval = float(cfg.get("context_global_cooldown_minutes", 5))
                    next_run = _iso_add(last_run, timedelta(minutes=interval))
                    error_retry = self._kv(connection, CONTEXT_ERROR_RETRY_KEY)
                    if error_retry:
                        try:
                            if next_run is None or parse_time(error_retry) > parse_time(next_run):
                                next_run = error_retry
                        except Exception:
                            next_run = error_retry
                    trigger = "event_driven"
                primary = str(profile.get("model") or cfg.get("model") or "")
                used_model = str((last_result or {}).get("model") or "") or None
                enabled = bool(cfg.get("enabled", False)) and (
                    bool(cfg.get("trend_scout_enabled", True)) if kind == "trend_scout" else True
                )
                labels = {
                    "trend_scout": "Trend Scout",
                    "source_discovery": "Source Discovery",
                    "token_context": "Token Context",
                }
                result_status = str((last_result or {}).get("status") or "not_run")
                result_summary = result_status
                if last_result and last_result.get("event_count") is not None:
                    result_summary += f" · events={last_result['event_count']}"
                output.append(
                    {
                        "kind": kind,
                        "name": labels[kind],
                        "label": labels[kind],
                        "enabled": enabled,
                        "status": result_status if enabled else "disabled",
                        "trigger": trigger,
                        "model": primary,
                        "reasoning_effort": profile.get("reasoning_effort") or cfg.get("reasoning_effort"),
                        "fallback_models": list(profile.get("fallback_models") or []),
                        "fallback_reasoning_effort": profile.get("fallback_reasoning_effort"),
                        "last_used_model": used_model,
                        "fallback_used": bool(used_model and primary and used_model != primary),
                        "calls": calls,
                        "calls_today": calls,
                        "call_budget": item["call_budget"],
                        "daily_call_budget": item["call_budget"],
                        "tokens": tokens,
                        "tokens_today": tokens,
                        "token_budget": item["token_budget"],
                        "daily_token_budget": item["token_budget"],
                        "token_reserve_per_call": item["reserve"],
                        "last_run_at": last_run,
                        "next_run_at": next_run,
                        "last_result": result_summary,
                        "last_result_detail": last_result,
                    }
                )
            today_since = f"{day}T00:00:00Z"
            seven_day_since = iso(utcnow() - timedelta(days=7))
            today_rows = self._agent_usage_rows(connection, today_since)
            seven_day_rows = self._agent_usage_rows(connection, seven_day_since)
            usage_summary = {
                "today": today_rows[0] if today_rows else {
                    "calls": 0, "attempts": 0, "fallback_attempts": 0,
                    "input_tokens": None, "cached_input_tokens": None,
                    "cache_write_input_tokens": None, "output_tokens": None,
                    "reasoning_output_tokens": None, "total_tokens": None,
                    "known_usage_attempts": 0, "unknown_usage_attempts": 0, "coverage_pct": None,
                },
                "seven_days": seven_day_rows[0] if seven_day_rows else {
                    "calls": 0, "attempts": 0, "fallback_attempts": 0,
                    "input_tokens": None, "cached_input_tokens": None,
                    "cache_write_input_tokens": None, "output_tokens": None,
                    "reasoning_output_tokens": None, "total_tokens": None,
                    "known_usage_attempts": 0, "unknown_usage_attempts": 0, "coverage_pct": None,
                },
            }
            legacy_today = sum(int(item.get("tokens_today") or 0) for item in output)
            ledger_today = int(usage_summary["today"].get("total_tokens") or 0)
            usage_summary["today"]["legacy_unattributed_total_tokens"] = max(0, legacy_today - ledger_today)
            usage_breakdown = {
                "today": self._agent_usage_rows(connection, today_since, ("task", "model", "reasoning_effort")),
                "seven_days": self._agent_usage_rows(connection, seven_day_since, ("task", "model", "reasoning_effort")),
            }
            if connection is not None and self._table_exists(connection, "agent_attempts"):
                recent_attempts = [
                    {
                        "run_id": str(row["run_id"])[:12],
                        "attempt_index": int(row["attempt_index"]),
                        "task": row["task"],
                        "model": row["model"],
                        "reasoning_effort": row["reasoning_effort"],
                        "started_at": row["started_at"],
                        "finished_at": row["finished_at"],
                        "status": row["status"],
                        "fallback": bool(row["fallback"]),
                        "input_tokens": row["input_tokens"],
                        "cached_input_tokens": row["cached_input_tokens"],
                        "cache_write_input_tokens": row["cache_write_input_tokens"],
                        "output_tokens": row["output_tokens"],
                        "reasoning_output_tokens": row["reasoning_output_tokens"],
                        "total_tokens": row["total_tokens"],
                        "accounting_source": row["accounting_source"],
                    }
                    for row in connection.execute(
                        "SELECT * FROM agent_attempts ORDER BY finished_at DESC,id DESC LIMIT 50"
                    )
                ]
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "max_concurrent_agents": int(cfg.get("max_concurrent_agents", 2)),
            "provider": "Local Codex CLI",
            "credential_mode": "signed_in_local_session",
            "uses_api_key": False,
            "codex_available": codex_available,
            "date": day,
            "operations": output,
            "usage_summary": usage_summary,
            "usage_breakdown": usage_breakdown,
            "recent_attempts": recent_attempts,
            "as_of": iso(),
        }

    def sources(self) -> dict[str, Any]:
        configured: list[dict[str, Any]] = []
        source_cfg = self.config.get("sources") or {}
        for item in source_cfg.get("rss", []):
            configured.append(
                {
                    "name": str(item.get("name") or item.get("url") or "rss"),
                    "kind": "rss",
                    "url": _safe_url(item.get("url")),
                    "configured": True,
                    "enabled": bool(item.get("enabled", True)),
                    "dynamic": False,
                }
            )
        for item in source_cfg.get("mastodon", []):
            configured.append(
                {
                    "name": str(item.get("name") or item.get("url") or "mastodon"),
                    "kind": "mastodon",
                    "url": _safe_url(item.get("url")),
                    "configured": True,
                    "enabled": bool(item.get("enabled", True)),
                    "dynamic": False,
                }
            )
        for network in source_cfg.get("gecko_networks", []):
            configured.append(
                {
                    "name": f"geckoterminal:{network}",
                    "kind": "new_pool",
                    "url": None,
                    "configured": True,
                    "enabled": True,
                    "dynamic": False,
                }
            )
        pump = source_cfg.get("pumpportal") or {}
        configured.append(
            {
                "name": "pumpportal:create",
                "kind": "stream",
                "url": None,
                "configured": True,
                "enabled": bool(pump.get("enabled", True)),
                "dynamic": False,
            }
        )
        for name in ("dexscreener", "goplus-evm", "honeypot-is", "goplus-solana", "rugcheck"):
            configured.append(
                {
                    "name": name,
                    "kind": "quote_or_safety",
                    "url": None,
                    "configured": True,
                    "enabled": True,
                    "dynamic": False,
                }
            )
        health: dict[str, sqlite3.Row] = {}
        dynamic: list[dict[str, Any]] = []
        platform_heartbeats: dict[str, dict[str, Any]] = {}
        with self.connect() as connection:
            if connection is not None and self._table_exists(connection, "source_health"):
                health = {str(row["source"]): row for row in connection.execute("SELECT * FROM source_health")}
            registry = self._kv(connection, REGISTRY_KEY, [])
            for platform in PLATFORMS:
                value = self._kv(connection, f"browser_platform_heartbeat:{platform}", {})
                if isinstance(value, dict):
                    platform_heartbeats[platform] = value
            if isinstance(registry, list):
                for item in registry:
                    if not isinstance(item, dict):
                        continue
                    dynamic.append(
                        {
                            "name": str(item.get("name") or item.get("url") or "dynamic-rss"),
                            "kind": str(item.get("kind") or "rss"),
                            "url": _safe_url(item.get("url")),
                            "configured": False,
                            "enabled": item.get("status") == "active",
                            "dynamic": True,
                            "registry_status": item.get("status"),
                            "pause_reason": item.get("pause_reason"),
                            "last_success_at": item.get("last_success_at"),
                            "last_failure_at": item.get("last_failure_at"),
                            "consecutive_failures": item.get("consecutive_failures"),
                        }
                    )
        limits = self.config.get("source_stale_minutes") or {}
        items = []
        known_names: set[str] = set()
        for item in [*configured, *dynamic]:
            name = str(item["name"])
            known_names.add(name)
            row = health.get(name)
            last_ok = row["last_ok_at"] if row else item.get("last_success_at")
            last_item = row["last_item_at"] if row else None
            last_error = row["last_error_at"] if row else item.get("last_failure_at")
            if name.startswith("browser:"):
                threshold = float(limits.get("browser", 3))
            elif name.startswith("pumpportal"):
                threshold = float(limits.get("pumpportal", 3))
            else:
                threshold = float(limits.get("other", 20))
            age = _minutes_since(last_ok)
            if not item.get("enabled"):
                status = "paused" if item.get("dynamic") else "disabled"
            elif last_ok is None:
                status = "unknown"
            elif age is not None and age > threshold:
                status = "stale"
            elif last_error and (not last_ok or str(last_error) > str(last_ok)):
                status = "error"
            else:
                status = "healthy"
            items.append(
                {
                    **item,
                    "status": status,
                    "last_ok_at": last_ok,
                    "last_item_at": last_item,
                    "last_error_at": last_error,
                    "last_error_type": (str(row["last_error"]).split(":", 1)[0] if row and row["last_error"] else None),
                    "minutes_since_ok": age,
                    "stale_after_minutes": threshold,
                }
            )
        for name, row in health.items():
            if name in known_names:
                continue
            last_ok = row["last_ok_at"]
            age = _minutes_since(last_ok)
            threshold = float(limits.get("browser" if name.startswith("browser:") else "other", 20))
            items.append(
                {
                    "name": name,
                    "kind": "observed",
                    "url": None,
                    "configured": False,
                    "enabled": True,
                    "dynamic": False,
                    "status": "unknown" if last_ok is None else ("stale" if age is not None and age > threshold else "healthy"),
                    "last_ok_at": last_ok,
                    "last_item_at": row["last_item_at"],
                    "last_error_at": row["last_error_at"],
                    "last_error_type": str(row["last_error"]).split(":", 1)[0] if row["last_error"] else None,
                    "minutes_since_ok": age,
                    "stale_after_minutes": threshold,
                }
            )
        items.sort(key=lambda item: (item["status"] not in {"error", "stale"}, str(item["name"]).lower()))
        watchlist = self.console_settings()
        configured_platforms = {
            str(item.get("platform") or ""): bool(item.get("enabled", True))
            for item in watchlist["platforms"]
            if isinstance(item, dict)
        }
        platform_status = []
        for platform in PLATFORMS:
            access_mode, login_recommended = PLATFORM_ACCESS[platform]
            enabled = configured_platforms.get(platform, False)
            heartbeat = platform_heartbeats.get(platform, {})
            last_heartbeat_at = heartbeat.get("observed_at")
            heartbeat_age = _minutes_since(last_heartbeat_at)
            access_state = str(heartbeat.get("access_state") or "not_observed")
            if not enabled:
                access_state = "disabled"
            elif heartbeat_age is not None and heartbeat_age > float(limits.get("browser", 3)):
                access_state = "stale"
            platform_status.append(
                {
                    "platform": platform,
                    "enabled": enabled,
                    "access_mode": access_mode,
                    "login_recommended": login_recommended,
                    "access_state": access_state,
                    "last_heartbeat_at": last_heartbeat_at,
                    "minutes_since_heartbeat": heartbeat_age,
                    "visible": heartbeat.get("visible"),
                    "selector_count": int(heartbeat.get("selector_count") or 0),
                    "page_url": _safe_url(heartbeat.get("page_url")),
                    "contains_credentials": False,
                }
            )
        return {
            "items": items,
            "summary": {
                "active": sum(1 for item in items if item["status"] == "healthy"),
                "paused": sum(1 for item in items if item["status"] == "paused"),
                "errors": sum(1 for item in items if item["status"] == "error"),
                "stale": sum(1 for item in items if item["status"] == "stale"),
            },
            "collection_preferences": {
                "platforms": watchlist["platforms"],
                "accounts": watchlist["watch_accounts"],
                "topics": watchlist["topics"],
                "contains_credentials": False,
                "credential_submission_supported": False,
            },
            "platforms": platform_status,
            "credentials_policy": {
                "contains_credentials": False,
                "accepts_passwords": False,
                "accepts_cookies": False,
                "accepts_sessions": False,
            },
            "browser_bridge": self._bridge_health(),
            "as_of": iso(),
        }

    def audit(self) -> dict[str, Any]:
        counts = {
            "observations": 0,
            "feature": 0,
            "confirmation": 0,
            "identity": 0,
            "promotion": 0,
            "stale_downgraded": 0,
            "future_rejected": 0,
        }
        starlink: dict[str, Any] = {"event_id": 360, "present": False}
        recent_decisions: list[dict[str, Any]] = []
        with self.connect() as connection:
            if connection is not None and self._table_exists(connection, "observations"):
                counts["observations"] = int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
                for row in connection.execute("SELECT role,COUNT(*) AS value FROM observations GROUP BY role"):
                    role = str(row["role"]).lower()
                    if role in counts:
                        counts[role] = int(row["value"])
                counts["stale_downgraded"] = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM observations WHERE raw_json LIKE '%\"stale_first_observation\": true%'"
                    ).fetchone()[0]
                )
                future_rows = connection.execute(
                    "SELECT * FROM observations WHERE raw_json LIKE '%\"published_time_in_future\": true%'"
                ).fetchall()
                decision_at = utcnow()
                max_age = float((self.config.get("events") or {}).get("max_source_age_minutes", 30))
                counts["future_rejected"] = sum(
                    "published_time_in_future" in evidence_rejection(row, decision_at, max_age)
                    for row in future_rows
                )
            if connection is not None and self._table_exists(connection, "events"):
                row = connection.execute("SELECT * FROM events WHERE id=360").fetchone()
                if row:
                    event = self._events_payload(connection, [row], include_observations=True)[0]
                    starlink = {
                        "event_id": 360,
                        "present": True,
                        "title": event["title"],
                        "attention": event["attention"],
                        "roles": event["roles"],
                        "decision_eligible": event["decision_eligible"],
                        "total_source_count": event["total_source_count"],
                        "eligible_source_count": event["eligible_source_count"],
                        "eligible_latest_at": event["eligible_latest_at"],
                        "evidence": [
                            {
                                "source": item["source"],
                                "origin": item["origin"],
                                "role": item["role"],
                                "original_role": item["original_role"],
                                "published_at": item["published_at"],
                                "observed_at": item["observed_at"],
                                "ingested_at": item["ingested_at"],
                                "freshness": item["freshness"],
                                "decision_eligible": item["decision_eligible"],
                                "rejection_reasons": item["rejection_reasons"],
                            }
                            for item in event["observations"]
                        ],
                        "attempt_count": self._kv(connection, "event_decision_attempt:360"),
                        "next_check_at": self._kv(connection, "event_decision_next:360"),
                    }
            if connection is not None:
                recent_decisions = self._decision_rows(connection, "1=1", [], 20, 0)
                for decision in recent_decisions:
                    event_id = int(decision["event_id"])
                    if not self._table_exists(connection, "event_observations"):
                        decision["evidence"] = []
                        continue
                    evidence = []
                    for row in connection.execute(
                        """
                        SELECT o.* FROM observations o JOIN event_observations eo ON eo.observation_id=o.id
                        WHERE eo.event_id=? ORDER BY o.observed_at ASC
                        """,
                        (event_id,),
                    ):
                        item = self._observation_payload(row, parse_time(decision["created_at"]))
                        evidence.append(
                            {
                                "source": item["source"],
                                "origin": item["origin"],
                                "role": item["role"],
                                "original_role": item["original_role"],
                                "published_at": item["published_at"],
                                "observed_at": item["observed_at"],
                                "ingested_at": item["ingested_at"],
                                "decision_eligible": item["decision_eligible"],
                                "rejection_reasons": item["rejection_reasons"],
                                "url": item["url"],
                            }
                        )
                    decision["evidence"] = evidence
        starlink_stale_reverse = [
            item
            for item in starlink.get("evidence", [])
            if item.get("original_role") in {"feature", "confirmation"}
            and item.get("role") == "identity"
            and (
                item.get("freshness") == "stale"
                or any("stale" in str(reason) for reason in item.get("rejection_reasons", []))
            )
        ]
        starlink["observed_stale_reverse_count"] = len(starlink_stale_reverse)
        starlink_observed_pass = bool(
            starlink.get("present")
            and starlink_stale_reverse
            and all(item.get("decision_eligible") is False for item in starlink_stale_reverse)
        )
        starlink_review = bool(
            starlink.get("present")
            and any(item.get("decision_eligible") is True for item in starlink_stale_reverse)
        )
        future_observed = counts["future_rejected"] > 0
        cases = [
            {
                "id": "r5-false-positive",
                "title": "r5 promotional false-positive exclusion",
                "summary": "The active forward database excludes r5 from performance; this API does not claim to have re-run the archived r5 audit.",
                "database": "r5",
                "status": "policy_enforced",
                "evidence_state": "documented_policy_only",
                "outcome": "not_in_performance",
                "included_in_performance": False,
                "observed_case_evidence": False,
                "reason": "promotional_listicles_and_generic_token_name_matches",
                "examples": ["Coins", "Attention"],
            },
            {
                "id": "r6-starlink-stale-reverse-evidence",
                "title": "r6 Starlink stale reverse evidence",
                "summary": "Stale reverse evidence must remain identity context and cannot create decision attention.",
                "database": "r6",
                "status": "review_required" if starlink_review else ("observed_pass" if starlink_observed_pass else "not_observed"),
                "evidence_state": "observed_case" if starlink.get("present") else "case_not_present_in_active_database",
                "outcome": "identity_only" if starlink_observed_pass else "not_observed",
                "rule": "stale feature/confirmation is retained as identity with zero attention",
                "observed_case_evidence": starlink_observed_pass,
                "runtime_evidence": starlink,
            },
            {
                "id": "future-data-rejection",
                "title": "Future-data rejection",
                "summary": "The policy rejects evidence observed or ingested after a decision; an observed pass requires matching rows in this database.",
                "status": "observed_pass" if future_observed else "policy_enforced",
                "evidence_state": "observed_case" if future_observed else "policy_only_no_matching_rows",
                "outcome": "future_features_rejected" if future_observed else "rule_enforced_not_observed",
                "rules": [
                    "observed_at_must_not_follow_decision_time",
                    "ingested_at_must_not_follow_decision_time",
                    "future_outcomes_are_forbidden_features",
                    "future_published_time_is_identity_only",
                ],
                "observed_case_evidence": future_observed,
                "observed_rejection_count": counts["future_rejected"],
            },
        ]
        case_statuses = {str(item["status"]) for item in cases}
        if "review_required" in case_statuses:
            overall_status = "review_required"
        elif all(item.get("observed_case_evidence") is True for item in cases):
            overall_status = "pass"
        elif any(item.get("observed_case_evidence") is True for item in cases):
            overall_status = "partial_evidence"
        else:
            overall_status = "policy_only"
        return {
            "release": "0.6.3",
            "forward_database": {"path_exposed": False, "status": self.database_health()["status"]},
            "cases": cases,
            "observation_counts": counts,
            "recent_decision_evidence": recent_decisions,
            "status": overall_status,
            "policy_enforced": True,
            "future_data_rejected": True if future_observed else None,
            "observed_future_rejection_count": counts["future_rejected"],
            "as_of": iso(),
        }

    def settings(self) -> dict[str, Any]:
        editable: dict[str, Any] = {}
        schema_fields: list[dict[str, Any]] = []
        for path in SETTING_SPECS:
            current = _nested_get(self.config, path)
            _nested_set(editable, path, current)
            kind, minimum, maximum = SETTING_SPECS[path]
            group = path.split(".", 1)[0] if "." in path else "runtime"
            unit = None
            if path.endswith("_seconds"):
                unit = "seconds"
            elif path.endswith("_minutes"):
                unit = "minutes"
            elif path.endswith("_hours"):
                unit = "hours"
            elif path.endswith("_usd"):
                unit = "USD"
            elif "token_budget" in path or "token_reserve" in path:
                unit = "tokens"
            elif path.endswith("_daily_limit"):
                unit = "calls/day"
            elif path.endswith("max_concurrent_agents"):
                unit = "agents"
            elif path.endswith("_pct") or path.endswith("_ratio") or path.endswith("_fraction"):
                unit = "ratio"
            schema_fields.append(
                {
                    "path": path,
                    "label": path.rsplit(".", 1)[-1].replace("_", " "),
                    "group": group.replace("_", " ").title(),
                    "type": "integer" if kind == "int" else "number",
                    "current": current,
                    "default": _nested_get(DEFAULT_CONFIG, path),
                    "min": minimum,
                    "max": maximum,
                    "unit": unit,
                    "safe": True,
                    "editable": True,
                    "restart_required": True,
                }
            )
        console = self.console_settings()
        return {
            "editable": editable,
            "values": copy.deepcopy(editable),
            "schema": {
                "fields": schema_fields,
                "collection_preferences": {
                    "platform_options": [
                        {
                            "value": platform,
                            "label": platform.upper(),
                            "automation_available": platform not in PLATFORM_AUTOMATION_DISABLED,
                            "manual_directory_only": platform in PLATFORM_AUTOMATION_DISABLED,
                        }
                        for platform in PLATFORMS
                    ]
                },
            },
            "editable_metadata": {item["path"]: copy.deepcopy(item) for item in schema_fields},
            "console": console,
            "collection_preferences": copy.deepcopy(console),
            "editable_paths": sorted(SETTING_SPECS),
            "live_locked": True,
            "locked": {
                "mode": self.config.get("mode"),
                "live.enabled": False,
                "live.available": False,
                "bridge": "secret_and_binding_not_exposed",
                "notifications": "secrets_not_exposed",
                "wallet": "solana_devnet_signer_local_only_mainnet_locked",
            },
            "agent_runtime": {
                "provider": "Local Codex CLI",
                "credential_mode": "signed_in_local_session",
                "uses_api_key": False,
                "codex_available": shutil.which(str((self.config.get("autonomous_search") or {}).get("codex_path") or "codex")) is not None,
            },
            "authentication": {
                **copy.deepcopy(self.auth_info),
                "public_url": self.public_access_url(),
            },
            "console_settings_storage": "data/web_console/console_settings.json",
            "restart_required_after_change": True,
        }

    def watchlist(self) -> dict[str, Any]:
        value = self.console_settings()
        return {
            **value,
            "storage": "data/web_console/console_settings.json",
            "contains_credentials": False,
            "as_of": iso(),
        }

    @staticmethod
    def _write_json_temp(path: Path, value: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".memetrader-web-",
            suffix=".json",
            dir=path.parent,
            delete=False,
        )
        temp_path = Path(handle.name)
        with handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path

    def patch_settings(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise APIError(400, "settings update must be a JSON object")
        console_supplied = "console" in payload
        console_patch = payload.get("console")
        if "updates" in payload:
            if set(payload) - {"updates", "console"}:
                raise APIError(400, "unsupported settings envelope field")
            config_payload = payload.get("updates")
        elif "config" in payload:
            if set(payload) - {"config", "console"}:
                raise APIError(400, "unsupported settings envelope field")
            config_payload = payload.get("config")
        elif "values" in payload:
            if set(payload) - {"values", "console"}:
                raise APIError(400, "unsupported settings envelope field")
            config_payload = payload.get("values")
        else:
            config_payload = {key: value for key, value in payload.items() if key != "console"}
        flat = _flatten_updates(config_payload) if config_payload else {}
        unknown = sorted(set(flat) - set(SETTING_SPECS))
        if unknown:
            raise APIError(400, "setting is locked or unsupported: " + ", ".join(unknown))
        changes = {path: _coerce_setting(path, value) for path, value in flat.items()}
        if not changes and not console_supplied:
            raise APIError(400, "at least one setting is required")

        console_value: dict[str, Any] | None = None
        if console_supplied:
            if not isinstance(console_patch, dict):
                raise APIError(400, "console settings must be a JSON object")
            merged_console = {**self.console_settings(), **console_patch}
            console_value = _validate_console_settings(merged_console)

        with self._settings_lock:
            try:
                current = json.loads(self.config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise APIError(500, "configuration is not readable") from exc
            updated = copy.deepcopy(current)
            for path, value in changes.items():
                _nested_set(updated, path, value)
            config_temp: Path | None = None
            console_temp: Path | None = None
            original_config = current
            try:
                if changes:
                    config_temp = self._write_json_temp(self.config_path, updated)
                    load_config(config_temp)
                if console_value is not None:
                    console_temp = self._write_json_temp(self.console_settings_path, console_value)
                if config_temp is not None:
                    os.replace(config_temp, self.config_path)
                    config_temp = None
                try:
                    if console_temp is not None:
                        os.replace(console_temp, self.console_settings_path)
                        console_temp = None
                except Exception:
                    if changes:
                        rollback = self._write_json_temp(self.config_path, original_config)
                        os.replace(rollback, self.config_path)
                    raise
                if changes:
                    self._reload_config()
            except APIError:
                raise
            except Exception as exc:
                raise APIError(400, "configuration update failed validation") from exc
            finally:
                for temp_path in (config_temp, console_temp):
                    if temp_path is not None:
                        try:
                            temp_path.unlink(missing_ok=True)
                        except OSError:
                            pass
        return {
            "ok": True,
            "changed": changes,
            "console": console_value if console_value is not None else self.console_settings(),
            "restart_required": bool(changes),
            "live": {"enabled": False, "locked": True, "available": False},
        }


class WebRequestHandler(BaseHTTPRequestHandler):
    server_version = "memeTraderWeb/0.6.3"
    protocol_version = "HTTP/1.1"

    @property
    def data(self) -> WebData:
        return self.server.web_data  # type: ignore[attr-defined]

    @property
    def static_dir(self) -> Path:
        return self.server.static_dir  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _authorized(self) -> bool:
        expected = getattr(self.server, "access_token", None)
        if not expected:
            return True
        authorization = str(self.headers.get("Authorization") or "")
        candidate = ""
        if authorization.startswith("Bearer "):
            candidate = authorization[7:].strip()
        elif authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:].strip(), validate=True).decode("utf-8")
                candidate = decoded.partition(":")[2]
            except (ValueError, UnicodeDecodeError):
                candidate = ""
        return bool(candidate) and hmac.compare_digest(candidate, expected)

    def _mutation_origin_allowed(self) -> bool:
        host_header = str(self.headers.get("Host") or "").strip()
        try:
            request_host = urlparse(f"//{host_header}").hostname
        except ValueError:
            return False
        if not request_host:
            return False
        if not getattr(self.server, "access_token", None) and not _is_loopback(request_host):
            return False
        origin = str(self.headers.get("Origin") or "").strip()
        if origin:
            try:
                if urlparse(origin).netloc.lower() != host_header.lower():
                    return False
            except ValueError:
                return False
        return str(self.headers.get("Sec-Fetch-Site") or "").lower() != "cross-site"

    def _request_host_is_loopback(self) -> bool:
        host_header = str(self.headers.get("Host") or "").strip()
        try:
            host = urlparse(f"//{host_header}").hostname
        except ValueError:
            return False
        return bool(host and _is_loopback(host))

    def _local_wallet_origin_allowed(self) -> bool:
        if not getattr(self.server, "wallet_controls_allowed", False):
            return False
        if not self._request_host_is_loopback():
            return False
        host_header = str(self.headers.get("Host") or "").strip().lower()
        origin = str(self.headers.get("Origin") or "").strip()
        if origin:
            try:
                parsed = urlparse(origin)
            except ValueError:
                return False
            if not parsed.hostname or not _is_loopback(parsed.hostname) or parsed.netloc.lower() != host_header:
                return False
        return str(self.headers.get("Sec-Fetch-Site") or "").lower() != "cross-site"

    def _read_json_body(self, *, maximum: int = 65_536) -> Any:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise APIError(400, "invalid request body size") from None
        if length <= 0 or length > maximum:
            raise APIError(400, "invalid request body size")
        content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise APIError(415, "Content-Type must be application/json")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise APIError(400, "request body must be valid JSON") from None

    def _discard_request_body(self, *, maximum: int) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            return
        if 0 < length <= maximum:
            self.rfile.read(length)
        elif length > maximum:
            self.close_connection = True

    def _unauthorized(self) -> None:
        body = b'{"error":"authentication required"}'
        self.send_response(401)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("WWW-Authenticate", 'Basic realm="memeTrader", charset="UTF-8"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _headers(self, status: int, content_type: str, length: int, *, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'")
        self.end_headers()

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _error(self, error: APIError) -> None:
        self._json(error.status, {"error": error.message})

    def _route_get(self, path: str, query: dict[str, list[str]]) -> Any:
        if path in {"/health", "/api/health"}:
            return self.data.health()
        if path == "/api":
            return {
                "service": "memetrader-web",
                "version": "0.6.3",
                "routes": [
                    "/api/overview", "/api/events", "/api/tokens", "/api/decisions",
                    "/api/portfolio", "/api/notifications", "/api/agents", "/api/sources", "/api/audit", "/api/settings",
                    "/api/watchlist", "/api/wallet",
                ],
                "live": {"enabled": False, "locked": True, "available": False},
            }
        if path == "/api/overview":
            return self.data.overview()
        if path == "/api/events":
            return self.data.events(query)
        if path.startswith("/api/events/"):
            try:
                return self.data.event_detail(int(path.rsplit("/", 1)[1]))
            except ValueError:
                raise APIError(400, "event id must be an integer") from None
        if path == "/api/tokens":
            return self.data.tokens(query)
        if path.startswith("/api/tokens/"):
            return self.data.token_detail(unquote(path[len("/api/tokens/"):]))
        if path == "/api/decisions":
            return self.data.decisions(query)
        if path == "/api/portfolio":
            return self.data.portfolio(query)
        if path == "/api/notifications":
            return self.data.notifications(query)
        if path == "/api/agents":
            return self.data.agents()
        if path == "/api/sources":
            return self.data.sources()
        if path == "/api/audit":
            return self.data.audit()
        if path == "/api/settings":
            return self.data.settings()
        if path == "/api/watchlist":
            return self.data.watchlist()
        if path == "/api/wallet":
            local_wallet_view = bool(
                getattr(self.server, "wallet_controls_allowed", False)
                and self._request_host_is_loopback()
            )
            return self.data.wallet_state(public_view=not local_wallet_view)
        raise APIError(404, "API route not found")

    def do_GET(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api" or parsed.path == "/health" or parsed.path.startswith("/api/"):
                self._json(200, self._route_get(parsed.path.rstrip("/") or "/", parse_qs(parsed.query)))
                return
            self._serve_static(parsed.path)
        except APIError as exc:
            self._error(exc)
        except (sqlite3.Error, OSError):
            self._json(503, {"error": "data source temporarily unavailable"})

    def do_PATCH(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        if not self._mutation_origin_allowed():
            self._error(APIError(403, "settings update origin is not allowed"))
            return
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/settings":
            self._error(APIError(404, "API route not found"))
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 65536:
                raise APIError(400, "invalid request body size")
            content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise APIError(415, "Content-Type must be application/json")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise APIError(400, "request body must be valid JSON") from None
            self._json(200, self.data.patch_settings(payload))
        except APIError as exc:
            self._error(exc)

    def do_POST(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        path = urlparse(self.path).path.rstrip("/")
        wallet_routes = {
            "/api/wallet/connect": self.data.connect_wallet,
            "/api/wallet/faucet": self.data.wallet_airdrop,
            "/api/wallet/transfer": self.data.wallet_transfer,
        }
        action = wallet_routes.get(path)
        if action is None:
            self._error(APIError(405, "method not allowed"))
            return
        if not self._local_wallet_origin_allowed():
            self._discard_request_body(maximum=4096)
            self._error(APIError(403, "wallet actions are available only on the local loopback console"))
            return
        try:
            payload = self._read_json_body(maximum=4096)
            self._json(200, action(payload))
        except APIError as exc:
            self._error(exc)

    def do_PUT(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        self._error(APIError(405, "method not allowed"))

    def do_DELETE(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        if urlparse(self.path).path.rstrip("/") != "/api/wallet":
            self._error(APIError(405, "method not allowed"))
            return
        if not self._local_wallet_origin_allowed():
            self._error(APIError(403, "wallet actions are available only on the local loopback console"))
            return
        self._json(200, self.data.disconnect_wallet())

    def _serve_static(self, requested: str) -> None:
        index = self.static_dir / "index.html"
        if not index.is_file():
            if requested == "/":
                self._json(200, self._route_get("/api", {}))
                return
            raise APIError(404, "page not found")
        decoded = unquote(requested)
        static_asset = decoded.startswith("/static/")
        relative = decoded[len("/static/"):] if static_asset else decoded.lstrip("/")
        candidate = (self.static_dir / relative).resolve() if relative else index.resolve()
        try:
            candidate.relative_to(self.static_dir.resolve())
        except ValueError:
            raise APIError(404, "page not found") from None
        if not candidate.is_file() and static_asset:
            raise APIError(404, "static asset not found")
        if not candidate.is_file():
            candidate = index
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        cache = "no-cache" if candidate.name == "index.html" else "public, max-age=300"
        self._headers(200, content_type, len(body), cache=cache)
        self.wfile.write(body)


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        web_data: WebData,
        static_dir: Path,
        access_token: str | None = None,
    ):
        self.web_data = web_data
        self.static_dir = static_dir
        self.access_token = access_token
        self._wallet_controls_allowed = bool(_is_loopback(address[0]) and not access_token)
        super().__init__(address, WebRequestHandler)

    @property
    def wallet_controls_allowed(self) -> bool:
        return self._wallet_controls_allowed


class IPv6WebServer(WebServer):
    address_family = socket.AF_INET6


def create_server(
    config_path: str | Path = "config.json",
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    static_dir: str | Path | None = None,
    access_token_file: str | Path | None = None,
) -> WebServer:
    if not 1 <= int(port) <= 65535:
        raise ValueError("web port must be between 1 and 65535")
    access_token: str | None = None
    token_name: str | None = None
    if access_token_file is not None:
        token_path = Path(access_token_file).resolve()
        try:
            access_token = token_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError("access token file is not readable") from exc
        if len(access_token) < 24:
            raise ValueError("access token must contain at least 24 characters")
        token_name = token_path.name
    if not _is_loopback(host) and not access_token:
        raise ValueError("non-loopback web binding requires --access-token-file")
    data = WebData(config_path)
    data.auth_info = {
        "required": bool(access_token),
        "mode": "bearer_or_basic" if access_token else "loopback",
        "token_file": token_name,
    }
    assets = Path(static_dir).resolve() if static_dir else Path(__file__).with_name("web_static")
    server_class = IPv6WebServer if host == "::1" else WebServer
    return server_class((host, int(port)), data, assets, access_token)


def serve(
    config_path: str | Path = "config.json",
    host: str = "127.0.0.1",
    port: int = 8787,
    access_token_file: str | Path | None = None,
) -> int:
    server = create_server(config_path, host, port, access_token_file=access_token_file)
    print(f"memeTrader Web: http://{host}:{port}")
    print("Live trading is locked; this console displays Shadow/Paper state only.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback memeTrader Web console")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--access-token-file")
    args = parser.parse_args(argv)
    return serve(args.config, args.host, args.port, args.access_token_file)


if __name__ == "__main__":
    raise SystemExit(main())
