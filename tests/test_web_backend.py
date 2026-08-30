from __future__ import annotations

import json
import socket
import threading
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from memetrader.autonomous_search import REGISTRY_KEY, TREND_RESULT_KEY, TREND_RUN_KEY
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store
from memetrader.web import WebData, create_server


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _config(tmp_path: Path) -> tuple[Path, dict]:
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["lock_file"] = "robot.lock"
    config["bridge"]["enabled"] = False
    config["bridge"]["token"] = "bridge-secret-must-never-be-returned"
    config["notifications"]["telegram_bot_token"] = "telegram-secret-must-never-be-returned"
    config["notifications"]["telegram_chat_id"] = "secret-chat-id"
    config["notifications"]["jsonl"] = "notifications.jsonl"
    config["sources"]["rss"] = [
        {"name": "example-news", "url": "https://example.com/feed.xml", "kind": "news", "enabled": True}
    ]
    config["sources"]["mastodon"] = []
    config["sources"]["bluesky_queries"] = []
    config["sources"]["gecko_networks"] = []
    config["sources"]["pumpportal"]["enabled"] = False
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def _seed(path: Path) -> tuple[int, str]:
    store = Store(path, initial_cash_usd=1000)
    now = utcnow()
    event_id = store.create_event("Viral otter becomes an internet mascot", ["otter", "mascot"], 72, now)
    observations = [
        Observation(
            source="news-a",
            source_kind="news",
            title="Viral otter becomes an internet mascot",
            url="https://news-a.example/story",
            published_at=now - timedelta(minutes=2),
            observed_at=now,
            ingested_at=now,
            role="feature",
            source_item_id="feature-1",
        ),
        Observation(
            source="browser:x:otter",
            source_kind="social",
            title="Older otter identity page",
            url="https://x.com/otter/status/1",
            published_at=now - timedelta(hours=2),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="identity-1",
            raw={"original_role": "confirmation", "stale_first_observation": True},
        ),
        Observation(
            source="promotion-list",
            source_kind="news",
            title="Top coins to buy after viral otter",
            url="https://promotion.example/list",
            observed_at=now,
            ingested_at=now,
            role="promotion",
            source_item_id="promotion-1",
            raw={"non_event_market_promotion": True},
        ),
        Observation(
            source="future-clock",
            source_kind="news",
            title="Future timestamp cannot be evidence",
            url="https://future.example/story",
            published_at=now + timedelta(hours=1),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="future-1",
            raw={"original_role": "feature", "published_time_in_future": True},
        ),
    ]
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)

    token = TokenCandidate(
        chain="solana",
        address="A" * 32,
        name="Viral Otter",
        symbol="OTTER",
        created_at=now - timedelta(minutes=1),
        first_seen_at=now,
        source="geckoterminal",
        url="https://www.geckoterminal.com/solana/pools/example",
        social_urls=["https://x.com/otter"],
    )
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana",
            address=token.address,
            price_usd=0.01,
            liquidity_usd=50_000,
            market_cap_usd=500_000,
            volume_5m_usd=12_000,
            buys_5m=30,
            sells_5m=10,
            observed_at=now,
            provider="dexscreener",
        )
    )
    store.add_decision(
        CandidateDecision(
            event_id=event_id,
            token_id=token.token_id,
            action="WAIT",
            score=65,
            match_score=88,
            canonical_margin=2,
            reasons=["match=88.0"],
            rejected_reasons=["canonical_token_ambiguous"],
            created_at=now,
        )
    )
    store.paper_buy(
        event_id=event_id,
        token=token,
        price=0.01,
        gross_usd=10,
        fee_bps=60,
        reason="test-paper-only",
    )
    store.heartbeat("example-news", item=True)
    day = now.date().isoformat()
    store.set_kv(f"autonomous_search_quota:{day}:trend_scout", 3)
    store.set_kv(f"autonomous_search_tokens:{day}:trend_scout", 12345)
    store.set_kv(TREND_RUN_KEY, iso(now - timedelta(minutes=3)))
    store.set_kv(
        TREND_RESULT_KEY,
        {
            "status": "completed",
            "run_at": iso(now - timedelta(minutes=3)),
            "events": [],
            "metadata": {"model": "fallback-model", "reasoning_effort": "low", "tokens_used": 12345},
        },
    )
    store.set_kv(
        REGISTRY_KEY,
        [
            {
                "name": "paused-dynamic",
                "url": "https://dynamic.example/feed.xml",
                "kind": "rss",
                "status": "paused",
                "pause_reason": "consecutive_poll_failures",
            }
        ],
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 0,
            "task": "trend_scout",
            "model": "gpt-5.3-codex-spark",
            "reasoning_effort": "low",
            "started_at": iso(now - timedelta(minutes=4)),
            "finished_at": iso(now - timedelta(minutes=3)),
            "status": "failed",
            "returncode": 1,
            "fallback": 0,
            "input_tokens": 600,
            "cached_input_tokens": 100,
            "cache_write_input_tokens": 20,
            "output_tokens": 200,
            "reasoning_output_tokens": 80,
            "total_tokens": 1000,
            "accounting_source": "codex_json",
        }
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 1,
            "task": "trend_scout",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
            "started_at": iso(now - timedelta(minutes=3)),
            "finished_at": iso(now - timedelta(minutes=2)),
            "status": "completed",
            "returncode": 0,
            "fallback": 1,
            "input_tokens": 300,
            "cached_input_tokens": 50,
            "cache_write_input_tokens": 10,
            "output_tokens": 100,
            "reasoning_output_tokens": 40,
            "total_tokens": 500,
            "accounting_source": "codex_json",
        }
    )
    store.close()
    return event_id, token.token_id


def _start_server(config: Path, static_dir: Path, access_token_file: Path | None = None):
    server = create_server(
        config,
        "127.0.0.1",
        _free_port(),
        static_dir=static_dir,
        access_token_file=access_token_file,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def test_web_api_empty_database_is_safe_and_live_is_locked(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    health = web.health()
    overview = web.overview()
    assert health["ok"] is True
    assert health["sqlite"]["schema_complete"] is True
    assert health["live"] == {"enabled": False, "locked": True, "available": False}
    assert {key: overview["counts"][key] for key in ("observations", "events", "tokens", "decisions", "trades")} == {
        "observations": 0,
        "events": 0,
        "tokens": 0,
        "decisions": 0,
        "trades": 0,
    }
    assert overview["counts"]["open_positions"] == 0
    assert overview["account"]["equity_usd"] == 1000
    assert overview["account"]["quote_as_of"] is None
    assert web.events({})["items"] == []
    assert web.tokens({})["items"] == []
    assert web.decisions({})["items"] == []


def test_web_api_exposes_real_evidence_wait_portfolio_agents_and_sources(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, token_id = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    store.set_kv(
        "browser_platform_heartbeat:x",
        {
            "platform": "x",
            "visible": True,
            "selector_count": 7,
            "page_url": "https://x.com/i/lists/1",
            "access_state": "authenticated",
            "observed_at": iso(),
            "contains_credentials": False,
        },
    )
    store.close()
    web = WebData(config_path)

    events = web.events({"limit": ["10"]})["items"]
    event = next(item for item in events if item["id"] == event_id)
    roles = {item["role"]: item for item in event["observations"]}
    assert event["event_url"] == f"#/events/{event_id}"
    assert event["evidence_ranking"]["method"] == "evidence_priority_not_authority"
    assert [item["priority_rank"] for item in event["observations"]] == [1, 2, 3, 4]
    assert all(0 <= item["priority_score"] <= 100 for item in event["observations"])
    assert all(item["ranking_method"] == "evidence_priority_not_authority" for item in event["observations"])
    assert event["source_count"] == 4
    assert event["total_source_count"] == 4
    assert event["eligible_source_count"] == 1
    assert event["eligible_latest_at"] is not None
    assert event["freshness_minutes"] is not None
    assert roles["feature"]["decision_eligible"] is True
    assert roles["identity"]["original_role"] in {"confirmation", "feature"}
    assert roles["promotion"]["decision_eligible"] is False
    assert "non_decision_role" in roles["promotion"]["rejection_reasons"]
    future = next(item for item in event["observations"] if item["source"] == "future-clock")
    assert future["freshness"] == "future"
    assert future["decision_eligible"] is False
    assert {"published_at", "observed_at", "ingested_at"}.issubset(future)
    detail = web.event_detail(event_id)
    assert detail["ranked_sources"] == event["observations"]
    assert [item["observed_at"] for item in detail["evidence_timeline"]] == sorted(
        item["observed_at"] for item in detail["evidence_timeline"]
    )
    assert {item["source"] for item in detail["evidence_timeline"]} == {
        "news-a", "browser:x:otter", "promotion-list", "future-clock"
    }

    token = web.token_detail(token_id)
    assert token["snapshot"]["momentum"] > 0
    assert token["snapshot"]["buys_5m"] == 30
    decision = web.decisions({})["items"][0]
    assert decision["action"] == "WAIT" and decision["is_wait"] is True
    assert decision["rejected_reasons"] == ["canonical_token_ambiguous"]
    assert decision["position_usd"] == 0

    portfolio = web.portfolio({})
    assert portfolio["simulated"] is True
    assert portfolio["positions"][0]["current_price"] == pytest.approx(0.01)
    assert portfolio["positions"][0]["quote_as_of"] is not None
    assert portfolio["trades"][0]["simulated"] is True
    assert portfolio["account"]["equity_usd"] is not None

    agents = web.agents()
    scout = next(item for item in agents["operations"] if item["kind"] == "trend_scout")
    assert agents["provider"] == "Local Codex CLI"
    assert agents["credential_mode"] == "signed_in_local_session"
    assert agents["uses_api_key"] is False
    assert scout["calls"] == 3 and scout["tokens"] == 12345
    assert scout["next_run_at"] is not None and scout["fallback_used"] is True
    assert agents["usage_summary"]["today"] == {
        "calls": 1,
        "attempts": 2,
        "fallback_attempts": 1,
        "input_tokens": 900,
        "cached_input_tokens": 150,
        "cache_write_input_tokens": 30,
        "output_tokens": 300,
        "reasoning_output_tokens": 120,
        "total_tokens": 1500,
        "known_usage_attempts": 2,
        "unknown_usage_attempts": 0,
        "coverage_pct": 100.0,
        "legacy_unattributed_total_tokens": 10845,
    }
    breakdown = agents["usage_breakdown"]["today"]
    assert {(item["model"], item["reasoning_effort"], item["total_tokens"]) for item in breakdown} == {
        ("gpt-5.3-codex-spark", "low", 1000),
        ("gpt-5.6-luna", "medium", 500),
    }
    assert [(item["attempt_index"], item["fallback"]) for item in agents["recent_attempts"]] == [
        (1, True), (0, False)
    ]
    assert "prompt" not in json.dumps(agents["recent_attempts"])

    sources = web.sources()["items"]
    static = next(item for item in sources if item["name"] == "example-news")
    paused = next(item for item in sources if item["name"] == "paused-dynamic")
    assert static["last_ok_at"] is not None and static["last_item_at"] is not None
    assert paused["status"] == "paused"
    assert paused["pause_reason"] == "consecutive_poll_failures"
    source_payload = web.sources()
    assert len(source_payload["platforms"]) == 9
    x_status = next(item for item in source_payload["platforms"] if item["platform"] == "x")
    assert x_status["access_state"] == "authenticated"
    assert x_status["login_recommended"] is True
    assert x_status["contains_credentials"] is False
    assert source_payload["credentials_policy"] == {
        "contains_credentials": False,
        "accepts_passwords": False,
        "accepts_cookies": False,
        "accepts_sessions": False,
    }

    audit_evidence = web.audit()["recent_decision_evidence"][0]["evidence"]
    stale_identity = next(item for item in audit_evidence if item["source"] == "browser:x:otter")
    assert stale_identity["original_role"] == "confirmation"
    assert stale_identity["rejection_reasons"]
    assert {"published_at", "observed_at", "ingested_at"}.issubset(stale_identity)


def test_settings_are_allowlisted_atomic_and_never_expose_secrets(tmp_path: Path):
    config_path, config = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    serialized = json.dumps(
        {
            "settings": web.settings(),
            "health": web.health(),
            "agents": web.agents(),
            "sources": web.sources(),
        }
    )
    assert config["bridge"]["token"] not in serialized
    assert config["notifications"]["telegram_bot_token"] not in serialized
    assert "telegram_chat_id" not in serialized
    settings = web.settings()
    assert settings["values"] == settings["editable"]
    assert settings["schema"]["fields"]
    poll_schema = next(item for item in settings["schema"]["fields"] if item["path"] == "poll_seconds")
    assert poll_schema["current"] == settings["editable"]["poll_seconds"]
    assert poll_schema["default"] is not None
    assert poll_schema["unit"] == "seconds"
    assert poll_schema["restart_required"] is True
    assert settings["live_locked"] is True

    public_access = tmp_path / "data" / "web_console" / "PUBLIC_ACCESS.txt"
    public_access.parent.mkdir(parents=True, exist_ok=True)
    public_access.write_text(
        "URL: https://example.trycloudflare.com\nUsername: memetrader\nPassword: must-stay-local\n",
        encoding="utf-8",
    )
    public_settings = web.settings()
    assert public_settings["authentication"]["public_url"] == "https://example.trycloudflare.com"
    assert "must-stay-local" not in json.dumps(public_settings)

    result = web.patch_settings(
        {
            "updates": {
                "poll_seconds": 90,
                "autonomous_search": {"max_concurrent_agents": 2},
            },
            "console": {
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "@example",
                        "display_name": "Example",
                        "url": "https://x.com/example",
                        "enabled": True,
                        "priority": 1,
                    }
                ],
                "topics": ["viral animals"],
            },
        }
    )
    assert result["restart_required"] is True
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["poll_seconds"] == 90
    assert saved["autonomous_search"]["max_concurrent_agents"] == 2
    assert saved["live"]["enabled"] is False
    watchlist = web.watchlist()
    assert watchlist["watch_accounts"][0]["handle"] == "@example"
    assert watchlist["watch_accounts"][0]["priority"] == 1
    assert watchlist["contains_credentials"] is False

    before = config_path.read_bytes()
    for unsafe_update in ({"live": {"enabled": True}}, {"mode": "live"}):
        with pytest.raises(Exception, match="locked or unsupported"):
            web.patch_settings({"updates": unsafe_update})
        assert config_path.read_bytes() == before
    with pytest.raises(Exception, match="between 1 and 2"):
        web.patch_settings({"updates": {"autonomous_search": {"max_concurrent_agents": 3}}})
    with pytest.raises(Exception, match="unsupported fields"):
        web.patch_settings(
            {
                "console": {
                    "watch_accounts": [
                        {"platform": "x", "handle": "bad", "enabled": True, "password": "must-not-save"}
                    ]
                }
            }
        )
    assert "must-not-save" not in (tmp_path / "data" / "web_console" / "console_settings.json").read_text(encoding="utf-8")


def test_http_routes_require_optional_file_token_and_serve_api(tmp_path: Path):
    config_path, config = _config(tmp_path)
    _seed(tmp_path / "db.sqlite3")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
    (static / "app.js").write_text("window.consoleReady = true;", encoding="utf-8")
    token_file = tmp_path / "web-access-token.txt"
    token_file.write_text("a-local-access-token-longer-than-24", encoding="utf-8")
    server, thread, base = _start_server(config_path, static, token_file)
    try:
        with httpx.Client(timeout=5) as client:
            assert client.get(f"{base}/api/health").status_code == 401
            headers = {"Authorization": "Bearer a-local-access-token-longer-than-24"}
            health = client.get(f"{base}/api/health", headers=headers)
            assert health.status_code == 200 and health.json()["live"]["locked"] is True
            assert client.get(f"{base}/", headers=headers).text == "<h1>console</h1>"
            asset = client.get(f"{base}/static/app.js", headers=headers)
            assert asset.status_code == 200
            assert "javascript" in asset.headers["content-type"]
            assert asset.text == "window.consoleReady = true;"
            assert client.get(f"{base}/static/missing.js", headers=headers).status_code == 404
            watchlist = client.get(f"{base}/api/watchlist", headers=headers).json()
            assert len(watchlist["platforms"]) == 9
            settings = client.get(f"{base}/api/settings", headers=headers).json()
            assert settings["authentication"]["token_file"] == token_file.name
            assert str(token_file.resolve()) not in json.dumps(settings)
            assert config["bridge"]["token"] not in json.dumps(settings)
            rejected = client.patch(
                f"{base}/api/settings",
                headers=headers,
                json={"updates": {"mode": "live"}},
            )
            assert rejected.status_code == 400
            cross_origin = client.patch(
                f"{base}/api/settings",
                headers={**headers, "Origin": "https://malicious.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert cross_origin.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_wallet_http_is_local_only_public_view_is_masked_and_secret_is_never_persisted(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")

    class FakeWallet:
        def __init__(self):
            self.calls: list[tuple[str, object]] = []

        def snapshot(self, *, public_view: bool = False, refresh: bool = False):
            self.calls.append(("snapshot", public_view))
            return {
                "connected": True,
                "network": "solana-devnet",
                "address": "Abcd1234…Wxyz5678" if public_view else "Abcd1234FullWalletAddressWxyz5678",
                "balance_sol": 0.25,
                "signing": {"available": not public_view, "local_only": True},
                "public_view": public_view,
            }

        def connect(self, private_key, alias):
            self.calls.append(("connect", (private_key, alias)))
            return {"connected": True, "address": "Abcd1234FullWalletAddressWxyz5678"}

        def request_airdrop(self, sol):
            self.calls.append(("faucet", sol))
            return {"status": "confirmed", "sol": sol, "signature": "airdrop-signature"}

        def transfer(self, recipient, sol, confirm_phrase):
            self.calls.append(("transfer", (recipient, sol, confirm_phrase)))
            return {"status": "confirmed", "sol": sol, "signature": "transfer-signature"}

        def disconnect(self):
            self.calls.append(("disconnect", None))
            return {"connected": False}

    fake_wallet = FakeWallet()
    server, thread, base = _start_server(config_path, static)
    server.web_data.wallet_service = fake_wallet
    private_key = "do-not-" + "persist-private-key"
    try:
        with httpx.Client(timeout=5) as client:
            local = client.get(f"{base}/api/wallet")
            assert local.status_code == 200
            assert local.json()["address"] == "Abcd1234FullWalletAddressWxyz5678"
            assert local.json()["signing"]["available"] is True

            public = client.get(f"{base}/api/wallet", headers={"Host": "console.example"})
            assert public.status_code == 200
            assert public.json()["address"] == "Abcd1234…Wxyz5678"
            assert public.json()["signing"]["available"] is False

            connect = client.post(
                f"{base}/api/wallet/connect",
                headers={"Origin": base},
                json={"private_key": private_key, "alias": "test only"},
            )
            faucet = client.post(
                f"{base}/api/wallet/faucet",
                headers={"Origin": base},
                json={"sol": 0.1},
            )
            transfer = client.post(
                f"{base}/api/wallet/transfer",
                headers={"Origin": base},
                json={"recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"},
            )
            disconnected = client.delete(f"{base}/api/wallet", headers={"Origin": base})
            assert [response.status_code for response in (connect, faucet, transfer, disconnected)] == [200] * 4
            assert private_key not in "".join(
                response.text for response in (connect, faucet, transfer, disconnected)
            )

            post_payloads = {
                "/api/wallet/connect": {"private_key": private_key, "alias": "test only"},
                "/api/wallet/faucet": {"sol": 0.1},
                "/api/wallet/transfer": {
                    "recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"
                },
            }
            for route, payload in post_payloads.items():
                assert client.post(
                    f"{base}{route}", headers={"Host": "console.example", "Connection": "close"}, json=payload
                ).status_code == 403
                assert client.post(
                    f"{base}{route}",
                    headers={"Origin": "https://malicious.example", "Connection": "close"},
                    json=payload,
                ).status_code == 403
            assert client.delete(f"{base}/api/wallet", headers={"Host": "console.example"}).status_code == 403
            assert client.delete(
                f"{base}/api/wallet", headers={"Origin": "https://malicious.example"}
            ).status_code == 403

        assert ("connect", (private_key, "test only")) in fake_wallet.calls
        secret = private_key.encode("utf-8")
        assert all(secret not in path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_non_loopback_binding_requires_access_token(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    with pytest.raises(ValueError, match="requires --access-token-file"):
        create_server(config_path, "0.0.0.0", _free_port(), static_dir=tmp_path)


def test_loopback_settings_reject_dns_rebinding_host(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    server, thread, base = _start_server(config_path, static)
    try:
        with httpx.Client(timeout=5) as client:
            response = client.patch(
                f"{base}/api/settings",
                headers={"Host": "attacker.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert response.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
