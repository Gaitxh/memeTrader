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

from .collectors import (
    BlueskySearchCollector,
    DexScreenerClient,
    GeckoNewPoolsCollector,
    HttpClient,
    MastodonCollector,
    PumpPortalCollector,
    RSSCollector,
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
    extract_addresses,
    is_distinctive_token_name,
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
        "rss": [],
        "bluesky_queries": [],
        "mastodon": [],
        "gecko_networks": ["solana", "bsc"],
        "pumpportal": {"enabled": True, "url": "wss://pumpportal.fun/api/data"},
        "reverse_google_news": {
            "enabled": True,
            "queries_per_cycle": 3,
            "max_tokens_scanned_per_cycle": 20,
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
        "honeypot_is": True,
        "require_evm_simulation": False,
        "rugcheck": True,
        "require_solana_report": False,
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

    for name in ("poll_seconds", "reverse_news_seconds", "event_scan_seconds", "position_scan_seconds", "source_health_seconds"):
        if float(config.get(name, 0)) <= 0:
            raise ValueError(f"{name} must be positive")

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

    config["candidate"]["chains"] = [str(chain).lower() for chain in config["candidate"].get("chains", [])]
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


class BrowserBridge:
    def __init__(
        self, host: str, port: int, token: str,
        on_observation: Callable[[Observation], Awaitable[None]],
        on_heartbeat: Callable[[str], Awaitable[None]],
        *,
        max_body_bytes: int = 262_144,
    ):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("browser bridge must bind to loopback")
        self.host, self.port, self.token = host, port, token
        self.max_body_bytes = int(max_body_bytes)
        self.on_observation, self.on_heartbeat = on_observation, on_heartbeat
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
                await self.on_heartbeat(source)
                await self._respond(writer, "200 OK", {"ok": True})
                return
            if method == "POST" and path in {"/observe", "/v1/observe"}:
                items = payload if isinstance(payload, list) else [payload]
                accepted = 0
                for item in items[:200]:
                    if not isinstance(item, dict):
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
                                "browser": item,
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
        self.http = HttpClient()
        self.dex = DexScreenerClient(self.http)
        self.events = EventEngine(
            self.store,
            similarity_threshold=float((config.get("events") or {}).get("similarity", 0.28)),
        )
        self.safety = SafetyChecker(self.http, config["safety"])
        self.agent = AgentRouter(self.store, config["agent"])
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

    async def ingest_observation(self, obs: Observation) -> None:
        event_id, event_created, observation_created = self.events.ingest(obs)
        self.store.heartbeat(obs.source, item=observation_created)
        if not observation_created:
            return
        event = self.store.get_event(event_id)
        notify_cfg = self.config["notifications"]
        threshold = float(notify_cfg.get("minimum_event_attention", self.config.get("event_min_attention", 40)))
        is_official = obs.source_kind.lower() == "official_social"
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

    async def browser_heartbeat(self, source: str) -> None:
        self.store.heartbeat(f"browser:{source}")

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
        result = []
        for item in self.config["sources"].get("rss", []):
            if item.get("enabled", True) and item.get("url"):
                result.append(RSSCollector(self.http, str(item.get("name") or item["url"]), str(item["url"]), str(item.get("kind") or "news")))
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
        try:
            observations = await collector.poll()
            self.store.heartbeat(name, item=bool(observations))
            for obs in observations:
                await self.ingest_observation(obs)
        except Exception as exc:
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

    async def poll_external_once(self) -> None:
        collectors = [*self._rss_collectors(), *self._bluesky_collectors(), *self._mastodon_collectors()]
        tasks = [self._poll_observation_collector(collector) for collector in collectors]
        tasks.extend(
            self._poll_gecko_network(str(network))
            for network in self.config["sources"].get("gecko_networks", [])
        )
        if tasks:
            await asyncio.gather(*tasks)

    async def reverse_news_once(self) -> None:
        cfg = self.config["sources"].get("reverse_google_news") or {}
        if not cfg.get("enabled", True):
            return
        max_queries = int(cfg.get("queries_per_cycle", 3))
        max_scanned = int(cfg.get("max_tokens_scanned_per_cycle", 20))
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
        ranked: list[tuple[float, TokenCandidate]] = []
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
            if len(query) < 3 or not is_distinctive_token_name(token.name or token.symbol):
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
            if (snap.liquidity_usd or 0) < min_liquidity:
                continue
            if (snap.volume_5m_usd or 0) < min_volume:
                continue
            if transactions < min_transactions or buy_ratio < min_buy_ratio:
                continue
            ranked.append((CandidateEvaluator._momentum_score(snap), quoted_token))

        ranked.sort(key=lambda item: item[0], reverse=True)
        for momentum, token in ranked[:max_queries]:
            key = f"reverse_news:{token.token_id}"
            self.store.set_kv(key, iso(now))
            name = token.name.strip() or token.symbol.strip()
            query = f'"{name}" when:1d'
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
                {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
            )
            source = "google-news-reverse"
            try:
                observations = await RSSCollector(self.http, source, url, "news").poll()
                accepted = 0
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
                    if accepted >= max_results:
                        break
                self.store.heartbeat(source, item=accepted > 0)
            except Exception as exc:
                self._notify_source_error(source, exc)

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

            self.store.add_decision(decision)
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

    async def check_source_health_once(self) -> None:
        limits = self.config.get("source_stale_minutes") or {}
        disabled_sources = {
            str(item.get("name") or item.get("url") or "")
            for item in self.config["sources"].get("rss", [])
            if not item.get("enabled", True)
        }
        now = utcnow()
        for row in self.store.source_health():
            source = str(row["source"])
            if source in disabled_sources:
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
        await self.reverse_news_once()
        await self.evaluate_events_once()
        await self.monitor_positions_once()
        await self.check_source_health_once()

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
            )
            await self.bridge.start()
            self.notifier.send("bridge_started", "browser bridge", {"host": bridge_cfg.get("host"), "port": bridge_cfg.get("port")})

        tasks = [
            asyncio.create_task(self.pump_loop(), name="pumpportal"),
            asyncio.create_task(
                self._periodic("external_sources", self.config.get("poll_seconds", 60), self.poll_external_once),
                name="external_sources",
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
