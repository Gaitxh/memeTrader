import asyncio

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime_timing import RuntimeTiming
from test_market_api_runtime import make_runtime, pair_payload, target_for


def test_held_latency_separates_runtime_slot_from_transport_and_apply(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        runtime.runtime_timing = RuntimeTiming()
        token = TokenCandidate("solana", "A" * 32, "A", "A")
        pool = "B" * 32

        class Dex:
            async def batch_quote_fresh(self, chain, addresses):
                await asyncio.sleep(0.005)
                observed = utcnow()
                pair = pair_payload(token, pool, provider="dexscreener", observed=observed)
                return {token.token_id: (
                    token,
                    TokenSnapshot(
                        token.chain, token.address, 1.25, 25_000.0, None, 500.0, 8, 3,
                        observed_at=observed, ingested_at=observed,
                        provider="dexscreener", raw={"pair": pair, "pairs": [pair]},
                    ),
                )}

        runtime.dex = Dex()
        for _ in range(8):
            await runtime._dex_quote_lock.acquire()

        async def release_slot():
            await asyncio.sleep(0.025)
            runtime._dex_quote_lock.release()

        release = asyncio.create_task(release_slot())
        refreshed = await runtime._refresh_chain_meme_market_marks(
            [target_for(token, pool)], heartbeat_name="fixture", high_priority=True,
        )
        await release
        for _ in range(7):
            runtime._dex_quote_lock.release()
        components = runtime.runtime_timing.snapshot()["components"]
        assert refreshed == 1
        assert components["held_runtime_slot_wait"]["duration_seconds"]["p50"] >= 0.015
        assert components["held_transport_with_client_wait"]["duration_seconds"]["p50"] >= 0.004
        assert components["held_apply_exit"]["sample_count"] == 1
        await runtime.close()

    asyncio.run(scenario())


def test_held_local_slot_deferral_is_not_reported_as_transport_failure(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        runtime.runtime_timing = RuntimeTiming()
        token = TokenCandidate("solana", "C" * 32, "C", "C")
        runtime._dex_quote_backoff_until = asyncio.get_running_loop().time() + 60

        refreshed = await runtime._refresh_chain_meme_market_marks(
            [target_for(token, "D" * 32)], heartbeat_name="fixture", high_priority=True,
        )
        snapshot = runtime.runtime_timing.snapshot()
        assert refreshed == 0
        assert snapshot["activity"]["held_runtime_slot_deferred"]["calls"] == 1
        assert "held_transport_with_client_wait" not in snapshot["activity"]
        assert "held_fetch" not in snapshot["activity"]
        await runtime.close()

    asyncio.run(scenario())
