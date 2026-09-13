import asyncio
from datetime import timedelta

from memetrader.models import utcnow
from memetrader.runtime import Runtime, initial_config
from memetrader.store import Store


def test_followup_selection_prioritizes_watched_token_before_oldest_due(tmp_path):
    store = Store(tmp_path / "priority.sqlite3")
    now = utcnow()
    for index in range(3):
        token_id = f"solana:growth-{index}"
        store.enqueue_token_detail_hydration(
            "solana", f"growth-{index}", enqueued_at=now - timedelta(minutes=30),
        )
        store.mark_token_detail_hydration(
            token_id, "hydrated", now=now - timedelta(minutes=2),
            refresh_at=now - timedelta(seconds=60 - index),
            followup_until=now + timedelta(hours=1),
        )
    selected = store.due_token_detail_hydrations(
        limit=2, now=now, chains=("solana",), followup_limit=2,
        priority_token_ids=("solana:growth-2",),
    )
    assert [row["token_id"] for row in selected][0] == "solana:growth-2"
    store.close()


def test_fast_hydration_cycle_uses_one_full_batch_and_reserves_followups(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        runtime = Runtime(config, tmp_path)
        captured = []
        runtime.store.due_token_detail_hydrations = lambda **kwargs: (
            captured.append(kwargs) or []
        )
        await runtime.poll_dexscreener_discovery_once(hydration_only=True)
        assert captured[0]["limit"] == 30
        assert captured[0]["followup_limit"] == 24
        await runtime.close()

    asyncio.run(scenario())
