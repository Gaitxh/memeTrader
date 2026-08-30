from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from memetrader.models import Observation
from memetrader.runtime import BrowserBridge


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
        bridge = BrowserBridge(
            "127.0.0.1",
            port,
            "secret-token-that-is-long-enough",
            on_observation,
            on_heartbeat,
            max_body_bytes=100_000,
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

                unauthorized = await client.post(
                    f"{base}/v1/observe",
                    headers={"X-MemeTrader-Token": "wrong"},
                    json={"title": "blocked"},
                )
                assert unauthorized.status_code == 401

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
