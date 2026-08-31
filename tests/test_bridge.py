from __future__ import annotations

import asyncio
import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from memetrader.models import Observation
from memetrader.runtime import BrowserBridge, resolve_watchlist_source_entity_id


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_browser_bridge_uses_local_receive_time_and_versioned_routes(tmp_path: Path):
    async def scenario() -> None:
        observations: list[Observation] = []
        heartbeats: list[tuple[str, dict]] = []

        async def on_observation(obs: Observation) -> None:
            observations.append(obs)

        async def on_heartbeat(source: str, detail: dict) -> None:
            heartbeats.append((source, detail))

        port = free_port()
        settings_path = tmp_path / "console_settings.json"
        settings_path.write_text(
            '{"watch_accounts":[{"platform":"x","handle":"@example","entity_id":"example_media","enabled":true}]}',
            encoding="utf-8",
        )
        bridge = BrowserBridge(
            "127.0.0.1",
            port,
            "secret-token-that-is-long-enough",
            on_observation,
            on_heartbeat,
            max_body_bytes=100_000,
            source_entity_resolver=lambda item: resolve_watchlist_source_entity_id(item, settings_path),
        )
        await bridge.start()
        base = f"http://127.0.0.1:{port}"
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                health = await client.get(f"{base}/health")
                assert health.status_code == 200

                before = datetime.now(timezone.utc)
                response = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:x:example",
                        "source_kind": "social",
                        "title": "A newly observed public post",
                        "text": "A newly observed public post with enough content to be useful.",
                        "url": "https://x.com/example/status/1",
                        "source_item_id": "x:1",
                        "published_at": "2026-01-01T00:00:00Z",
                        "observed_at": "1999-01-01T00:00:00Z",
                        "capture_phase": "initial",
                        "platform": "x",
                        "author": "example",
                        "source_entity_id": "example_media",
                        "like_count": 1200,
                        "repost_count": 300,
                        "view_count": 50000,
                    },
                )
                assert response.status_code == 200
                assert response.json()["accepted"] == 1
                assert len(observations) == 1
                assert observations[0].observed_at >= before
                assert observations[0].observed_at.year != 1999
                assert observations[0].availability_proof == "local_receive"
                assert observations[0].capture_phase == "initial"
                assert observations[0].raw["like_count"] == 1200
                assert observations[0].raw["view_count"] == 50000
                assert observations[0].raw["source_entity_id"] == "example_media"
                assert observations[0].raw["browser"]["source_entity_id"] == "example_media"

                forged = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:x:example",
                        "source_kind": "social",
                        "title": "An attacker cannot choose an arbitrary deduplication entity",
                        "platform": "x",
                        "author": "example",
                        "source_entity_id": "forged_entity",
                    },
                )
                assert forged.status_code == 200
                assert "source_entity_id" not in observations[1].raw
                assert "source_entity_id" not in observations[1].raw["browser"]

                wrong_author = dict(
                    source="browser:x:impostor",
                    source_kind="social",
                    title="A display-name similarity cannot claim a configured entity",
                    platform="x",
                    author="Example Media",
                    source_entity_id="example_media",
                )
                response = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json=wrong_author,
                )
                assert response.status_code == 200
                assert "source_entity_id" not in observations[2].raw

                telegram = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:telegram:example",
                        "source_kind": "social",
                        "title": "Telegram content must remain manual-directory only",
                        "platform": "telegram",
                        "author": "example",
                        "url": "https://t.me/example/1",
                    },
                )
                assert telegram.status_code == 200
                assert telegram.json()["accepted"] == 0
                assert len(observations) == 3

                telegram_spoofs = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json=[
                        {
                            "source": "browser:x:spoof",
                            "platform": "x",
                            "title": "A forged X platform must not hide a Telegram URL",
                            "url": "https://news.t.me/example/2",
                        },
                        {
                            "source": "browser:telegram:spoof",
                            "platform": "x",
                            "title": "The source prefix independently blocks Telegram",
                            "url": "https://x.com/example/status/2",
                        },
                        {
                            "source": "browser:x:spoof",
                            "platform": "x",
                            "title": "Telegram legacy host subdomains are manual-only",
                            "url": "https://channel.telegram.me/example/3",
                        },
                        {
                            "source": "browser:x:spoof",
                            "platform": "x",
                            "title": "Credential and authority confusion URLs are rejected",
                            "url": "https://x.com@t.me/example/4",
                        },
                        {
                            "source": "browser:x:spoof",
                            "platform": "x",
                            "title": "Backslash URL confusion is rejected",
                            "url": "https://x.com\\@t.me/example/5",
                        },
                    ],
                )
                assert telegram_spoofs.status_code == 200
                assert telegram_spoofs.json()["accepted"] == 0
                assert len(observations) == 3

                unauthorized = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "wrong"},
                    json={"title": "blocked"},
                )
                assert unauthorized.status_code == 401

                blocked_heartbeat = await client.post(
                    f"{base}/v1/heartbeat",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:x:spoof",
                        "detail": {
                            "platform": "x",
                            "page_url": "https://updates.t.me/example",
                        },
                    },
                )
                assert blocked_heartbeat.status_code == 200
                assert blocked_heartbeat.json()["accepted"] == 0
                assert heartbeats == []

                heartbeat = await client.post(
                    f"{base}/v1/heartbeat",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "https://x.com/i/lists/1",
                        "detail": {
                            "platform": "x",
                            "visible": True,
                            "selector_count": 4,
                            "page_url": "https://x.com/i/lists/1?secret=never-store",
                            "access_state": "authenticated",
                        },
                    },
                )
                assert heartbeat.status_code == 200
                assert heartbeats[0][0] == "https://x.com/i/lists/1"
                assert heartbeats[0][1]["platform"] == "x"

                tombstone = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:x:example",
                        "source_kind": "social",
                        "source_item_id": "x:1",
                        "url": "https://x.com/example/status/1",
                        "platform": "x",
                        "author": "example",
                        "source_item_state": "deleted",
                        "source_item_state_evidence": "platform_deleted_marker",
                        "source_reported_revision_at": "2026-08-31T00:00:00Z",
                    },
                )
                assert tombstone.status_code == 200
                assert tombstone.json()["accepted"] == 1
                assert observations[-1].title == "Source item state marker"
                assert observations[-1].role == "identity"
                assert observations[-1].raw["source_item_state"] == "deleted"
                assert observations[-1].raw["source_item_state_evidence"] == "platform_deleted_marker"

                correction = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "secret-token-that-is-long-enough"},
                    json={
                        "source": "browser:x:example",
                        "source_kind": "social",
                        "source_item_id": "x:2",
                        "url": "https://x.com/example/status/2",
                        "platform": "x",
                        "author": "example",
                        "title": "Publisher correction",
                        "source_item_state": "correction",
                        "source_item_state_evidence": "publisher_correction_marker",
                        "claim_target_url": "https://x.com/example/status/1?secret=never-forward",
                    },
                )
                assert correction.status_code == 200
                assert correction.json()["accepted"] == 1
                assert observations[-1].raw["claim_target_url"] == "https://x.com/example/status/1"
                assert "claim_target_url" not in observations[-1].raw["browser"]
                assert "never-forward" not in json.dumps(observations[-1].raw)
        finally:
            await bridge.close()

    asyncio.run(scenario())


def test_browser_bridge_rejects_non_loopback():
    async def noop_observation(_: Observation) -> None:
        return None

    async def noop_heartbeat(_: str, __: dict) -> None:
        return None

    with pytest.raises(ValueError, match="loopback"):
        BrowserBridge(
            "0.0.0.0",
            free_port(),
            "secret-token-that-is-long-enough",
            noop_observation,
            noop_heartbeat,
        )


def test_extension_manifest_does_not_inject_telegram_pages():
    manifest = (Path(__file__).parents[1] / "browser-extension" / "manifest.json").read_text(
        encoding="utf-8"
    )
    assert "t.me" not in manifest
    assert "telegram.me" not in manifest
