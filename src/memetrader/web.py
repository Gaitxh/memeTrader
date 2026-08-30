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
from .strategy import CandidateEvaluator, evidence_origin, evidence_rejection


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
DEFAULT_CONSOLE_SETTINGS = {
    "platforms": [{"platform": name, "enabled": True} for name in PLATFORMS],
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
    "agent_model",
    "agent_task",
    "category",
    "confidence",
    "event_title",
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
    "source_age_minutes",
    "stale_first_observation",
    "token_momentum_score",
    "view_count",
    "volume_usd",
}
SENSITIVE_QUERY_MARKERS = ("api_key", "apikey", "auth", "credential", "key", "secret", "signature", "token")


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
        platforms.append({"platform": platform, "enabled": enabled})

    accounts_value = value.get("watch_accounts", [])
    if not isinstance(accounts_value, list) or len(accounts_value) > 500:
        raise APIError(400, "watch_accounts must be a bounded list")
    accounts: list[dict[str, Any]] = []
    seen_accounts: set[tuple[str, str]] = set()
    allowed_account_fields = {"platform", "handle", "display_name", "url", "enabled", "priority"}
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
        self.auth_info = {"required": False, "mode": "loopback", "token_file": None}
        self._settings_lock = threading.Lock()
        self._system_lock = threading.Lock()
        self._system_cache_at = None
        self._system_cache: dict[str, Any] | None = None
        self._reload_config()

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
            "momentum": momentum,
            "momentum_score": momentum,
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
        with self.connect() as connection:
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
        return {
            "id": int(row["id"]),
            "source": row["source"],
            "source_kind": row["source_kind"],
            "title": row["title"],
            "text": row["text"],
            "url": _safe_url(row["url"]),
            "author": row["author"],
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
            "metadata": safe_raw,
        }

    def _events_payload(
        self, connection: sqlite3.Connection, rows: list[sqlite3.Row], *, include_observations: bool
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
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
                grouped[int(observation["event_id"])].append(self._observation_payload(observation))
        output: list[dict[str, Any]] = []
        for row in rows:
            event_id = int(row["id"])
            observations = grouped.get(event_id, [])
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
            }
            if include_observations:
                payload["observations"] = observations
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
            items = self._events_payload(connection, rows, include_observations=True)
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
            token_ids = list(dict.fromkeys(str(item["token_id"]) for item in decisions if item.get("token_id")))
            event["decisions"] = decisions
            event["related_token_ids"] = token_ids
            event["evidence_timeline"] = event["observations"]
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
        snapshots = self._latest_snapshots(connection, [str(row["token_id"]) for row in rows if row["token_id"]])
        output = []
        for row in rows:
            action = str(row["action"])
            output.append(
                {
                    "id": int(row["id"]),
                    "event_id": int(row["event_id"]),
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
                    "rejected_reasons": _json_load(row["rejected_reasons_json"], []),
                    "position_usd": float(row["position_usd"]),
                    "created_at": row["created_at"],
                    "snapshot": self._snapshot_payload(snapshots.get(str(row["token_id"]))),
                    "ranking_available": False,
                    "persistence_gap": "candidate_ranking_not_persisted_in_0.6.3",
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
            "ranking_available": False,
            "persistence_gap": "only_final_candidate_decision_is_persisted_in_0.6.3",
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
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "max_concurrent_agents": int(cfg.get("max_concurrent_agents", 2)),
            "provider": "Local Codex CLI",
            "credential_mode": "signed_in_local_session",
            "uses_api_key": False,
            "codex_available": codex_available,
            "date": day,
            "operations": output,
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
        with self.connect() as connection:
            if connection is not None and self._table_exists(connection, "source_health"):
                health = {str(row["source"]): row for row in connection.execute("SELECT * FROM source_health")}
            registry = self._kv(connection, REGISTRY_KEY, [])
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
                counts["future_rejected"] = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM observations WHERE raw_json LIKE '%\"published_time_in_future\": true%'"
                    ).fetchone()[0]
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
        return {
            "release": "0.6.3",
            "forward_database": {"path_exposed": False, "status": self.database_health()["status"]},
            "cases": [
                {
                    "id": "r5-false-positive",
                    "title": "r5 promotional false-positive exclusion",
                    "summary": "Promotional listicles and generic Coins/Attention matches remain excluded from performance.",
                    "database": "r5",
                    "status": "excluded",
                    "outcome": "not_in_performance",
                    "included_in_performance": False,
                    "reason": "promotional_listicles_and_generic_token_name_matches",
                    "examples": ["Coins", "Attention"],
                },
                {
                    "id": "r6-starlink-stale-reverse-evidence",
                    "title": "r6 Starlink stale reverse evidence",
                    "summary": "Stale reverse evidence is retained as identity context and cannot create decision attention.",
                    "database": "r6",
                    "status": "protected",
                    "outcome": "identity_only",
                    "rule": "stale feature/confirmation is retained as identity with zero attention",
                    "runtime_evidence": starlink,
                },
                {
                    "id": "future-data-rejection",
                    "title": "Future-data rejection",
                    "summary": "Evidence observed or ingested after the decision is rejected; outcome fields are forbidden.",
                    "status": "enforced",
                    "outcome": "future_features_rejected",
                    "rules": [
                        "observed_at_must_not_follow_decision_time",
                        "ingested_at_must_not_follow_decision_time",
                        "future_outcomes_are_forbidden_features",
                        "future_published_time_is_identity_only",
                    ],
                    "observed_rejection_count": counts["future_rejected"],
                },
            ],
            "observation_counts": counts,
            "recent_decision_evidence": recent_decisions,
            "status": "pass",
            "future_data_rejected": True,
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
                        {"value": platform, "label": platform.upper()} for platform in PLATFORMS
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
                "wallet": "not_supported",
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
                    "/api/portfolio", "/api/agents", "/api/sources", "/api/audit", "/api/settings",
                    "/api/watchlist",
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
        self._error(APIError(405, "method not allowed"))

    def do_PUT(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        self._error(APIError(405, "method not allowed"))

    def do_DELETE(self) -> None:
        if not self._authorized():
            self._unauthorized()
            return
        self._error(APIError(405, "method not allowed"))

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
        super().__init__(address, WebRequestHandler)


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
