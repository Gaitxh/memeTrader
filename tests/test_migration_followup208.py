import asyncio
from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, parse_time, utcnow
from memetrader.runtime import Runtime, initial_config


ADDRESS = "5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def curve(token, at, born):
    return TokenSnapshot(
        "solana", token.address, None, None, None, 500, 3, 1,
        observed_at=at, ingested_at=at, provider="dexscreener",
        raw={"pair": {
            "chainId": "solana", "dexId": "pumpfun", "pairAddress": POOL,
            "pairCreatedAt": int(born.timestamp() * 1000),
            "baseToken": {"address": token.address},
            "txns": {"m5": {"buys": 3, "sells": 1}},
        }},
    )


def make_runtime(tmp_path, monkeypatch, clock):
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["bridge"]["enabled"] = False
    config["chain_meme_trader_only_enabled"] = True
    config["sources"]["multichain_meme_data"]["chains"] = ["solana"]
    runtime = Runtime(config, tmp_path)
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(
        runtime, "_held_pool_quote_rejections",
        lambda *args: ["quote_price_unavailable", "quote_liquidity_unavailable"],
    )
    return runtime


def test_old_curve_followup_uses_only_fresh_causal_migration_receipt(tmp_path, monkeypatch):
    async def scenario():
        clock = [utcnow() + timedelta(seconds=5)]
        runtime = make_runtime(tmp_path, monkeypatch, clock)
        born = clock[0] - timedelta(days=13)
        token = TokenCandidate("solana", ADDRESS, "Migrated")
        quote = curve(token, clock[0], born)
        try:
            assert runtime._shared_market_followup_schedule(token, quote) == {}
            create = TokenCandidate(
                "solana", ADDRESS, "Migrated", source="pumpportal:create",
                first_seen_at=clock[0] - timedelta(minutes=1),
                raw={"pump_event_type": "create", "signature": "create-only"},
            )
            runtime.store.record_token_launch_fact(create)
            assert runtime._shared_market_followup_schedule(token, quote) == {}
            migration = TokenCandidate(
                "solana", ADDRESS, "Migrated", source="pumpportal:migration",
                first_seen_at=clock[0] - timedelta(seconds=1),
                raw={"pump_event_type": "migration", "pool": "pump-amm",
                     "signature": "migration-receipt"},
            )
            runtime.store.record_token_launch_fact(migration)
            fact = runtime.store.db.execute(
                "SELECT recorded_at FROM token_launch_facts WHERE token_id=? "
                "AND launch_event_type='migration'", (token.token_id,),
            ).fetchone()
            future_event = TokenCandidate(
                "solana", ADDRESS, "Migrated", source="pumpportal:migration",
                first_seen_at=clock[0] + timedelta(seconds=1),
                raw={"pump_event_type": "migration", "pool": "pump-amm",
                     "signature": "future-event"},
            )
            runtime.store.record_token_launch_fact(future_event)
            scheduled = runtime._shared_market_followup_schedule(token, quote)
            assert scheduled["refresh_at"] == clock[0] + timedelta(minutes=5)
            assert scheduled["followup_until"] == parse_time(fact["recorded_at"]) + timedelta(hours=3)
            clock[0] = scheduled["followup_until"] + timedelta(seconds=1)
            quote.observed_at = quote.ingested_at = clock[0]
            assert runtime._shared_market_followup_schedule(token, quote) == {}
        finally:
            await runtime.close()
    asyncio.run(scenario())


def test_migration_curve_reuses_bounded_fresh_hydration_lane(tmp_path, monkeypatch):
    async def scenario():
        clock = [utcnow() + timedelta(seconds=5)]
        runtime = make_runtime(tmp_path, monkeypatch, clock)
        migration = TokenCandidate(
            "solana", ADDRESS, "Migrated", source="pumpportal:migration",
            first_seen_at=clock[0] - timedelta(seconds=1),
            raw={"pump_event_type": "migration", "pool": "pump-amm",
                 "signature": "migration-lane"},
        )
        runtime.store.upsert_token(migration)
        runtime.store.record_token_launch_fact(migration)
        runtime.store.enqueue_token_detail_hydration("solana", ADDRESS, enqueued_at=clock[0])
        calls = []
        async def quote(chain, addresses, *, fresh=False, **kwargs):
            calls.append((chain, tuple(addresses), fresh))
            return {migration.token_id: (migration, curve(
                migration, clock[0], clock[0] - timedelta(days=13)))}
        monkeypatch.setattr(runtime, "_dex_batch_quote", quote)
        runtime.dex = type("Dex", (), {"DISCOVERY_SURFACES": {}, "batch_quote": True})()
        try:
            await runtime.chain_meme_token_details_once()
            first = dict(runtime.store.token_detail_hydration(migration.token_id))
            assert first["status"] == "hydrated"
            assert parse_time(first["next_attempt_at"]) == clock[0] + timedelta(minutes=5)
            clock[0] += timedelta(minutes=5, seconds=1)
            await runtime.chain_meme_token_details_once()
            second = dict(runtime.store.token_detail_hydration(migration.token_id))
            assert second["attempts"] == 2
            assert second["enqueued_at"] == first["enqueued_at"]
            assert calls == [
                ("solana", (ADDRESS,), False),
                ("solana", (ADDRESS,), True),
            ]
        finally:
            await runtime.close()
    asyncio.run(scenario())
