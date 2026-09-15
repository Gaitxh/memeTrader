import asyncio
from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime, initial_config
from memetrader.store import Store


def test_valid_lifecycle_followups_reserve_capacity_without_wasting_spare(tmp_path):
    store = Store(tmp_path / "first-before-refresh.sqlite3")
    now = utcnow()
    for index in range(3):
        token_id = f"solana:refresh-{index}"
        store.enqueue_token_detail_hydration("solana", f"refresh-{index}", enqueued_at=now)
        store.mark_token_detail_hydration(
            token_id, "hydrated", now=now - timedelta(minutes=2),
            refresh_at=now - timedelta(minutes=1),
            followup_until=now + timedelta(minutes=30),
        )
    for index in range(4):
        store.enqueue_token_detail_hydration("solana", f"first-{index}", enqueued_at=now)

    full = store.due_token_detail_hydrations(
        limit=4, now=now, chains=("solana",), followup_limit=3, prefer_fresh=True,
    )
    assert [row["status"] for row in full].count("pending") == 1
    assert [row["status"] for row in full].count("hydrated") == 3

    with_spare = store.due_token_detail_hydrations(
        limit=6, now=now, chains=("solana",), followup_limit=3, prefer_fresh=True,
    )
    assert [row["status"] for row in with_spare].count("pending") == 3
    assert [row["status"] for row in with_spare].count("hydrated") == 3
    store.close()


def test_new_discovery_receipt_promotes_no_pair_and_error(tmp_path):
    store = Store(tmp_path / "discovery-promotes-retry.sqlite3")
    now = utcnow()
    for status in ("no_pair", "error"):
        token_id = f"solana:{status}"
        store.enqueue_token_detail_hydration("solana", status, enqueued_at=now)
        store.mark_token_detail_hydration(token_id, status, now=now)
        assert store.promote_token_detail_hydration_from_discovery(
            token_id, observed_at=now + timedelta(seconds=1),
        )
        row = store.token_detail_hydration(token_id)
        assert row["status"] == "pending"
        assert row["next_attempt_at"] == row["enqueued_at"]
    store.close()


def test_shared_hydration_uses_one_full_batch_per_chain_and_broadcasts_first_frame(
    tmp_path, monkeypatch,
):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        config["sources"]["multichain_meme_data"]["chains"] = ["bsc", "solana"]
        runtime = Runtime(config, tmp_path)
        tokens = []
        for chain in ("bsc", "solana"):
            for index in range(30):
                address = ("0x" + f"{index + 1:040x}") if chain == "bsc" else f"S{index:031d}"
                token = TokenCandidate(chain, address, f"{chain}-{index}")
                tokens.append(token)
                runtime.store.upsert_token(token)
                runtime.store.enqueue_token_detail_hydration(chain, address)

        calls = []

        async def batch_quote(chain, addresses, **kwargs):
            calls.append((chain, list(addresses)))
            token = next(item for item in tokens if item.chain == chain and item.address == addresses[0])
            snapshot = TokenSnapshot(
                chain, token.address, 1.0, 10_000, 20_000, 100, 3, 1,
                observed_at=utcnow(), ingested_at=utcnow(), provider="dexscreener",
                raw={"pair": {
                    "chainId": chain, "dexId": "amm", "pairAddress": "pool-" + chain,
                    "baseToken": {"address": token.address}, "priceUsd": "1",
                    "liquidity": {"usd": 10_000},
                    "pairCreatedAt": int((utcnow() - timedelta(minutes=20)).timestamp() * 1000),
                }},
            )
            return {token.token_id: (token, snapshot)}

        broadcasts = []
        monkeypatch.setattr(runtime, "_dex_batch_quote", batch_quote)
        monkeypatch.setattr(runtime, "_remember_pattern_quotes", lambda quoted: broadcasts.append(quoted))
        runtime.dex = type("Dex", (), {"DISCOVERY_SURFACES": {}, "batch_quote": True})()

        await runtime.poll_dexscreener_discovery_once(hydration_only=True)

        assert sorted((chain, len(addresses)) for chain, addresses in calls) == [
            ("bsc", 30), ("solana", 30),
        ]
        expected_broadcasts = {
            next(token.token_id for token in tokens if token.chain == chain and token.address == addresses[0])
            for chain, addresses in calls
        }
        assert {next(iter(batch)) for batch in broadcasts} == expected_broadcasts
        await runtime.close()

    asyncio.run(scenario())
