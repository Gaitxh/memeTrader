"""Offline tests for route-ready original-pool queue selection; no Store/DB."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from memetrader.runtime import Runtime


def _runtime(now, *, providers_available=True):
    runtime = Runtime.__new__(Runtime)
    version = "test-route-period"
    rows = [
        dict(chain="solana", address="queued", pair_address="sol-pool", next_attempt=now - 20),
        dict(chain="robinhood", address="0x" + "12" * 20,
             pair_address="0x" + "ab" * 20, next_attempt=now - 10),
    ]
    for row in rows:
        row.update(token_id=f"{row['chain']}:{row['address']}", versions=[version],
                   next_primary_attempt=now + 60, next_public_attempt=now + 60,
                   next_complement_attempt=now + 60)
    runtime._market_pool_gaps = {
        (row["token_id"], row["pair_address"]): row for row in rows
    }
    runtime._market_complement_pools = set()
    runtime._dex_quote_low_priority_available = lambda: providers_available
    runtime._gecko_pool_backoff_until = 0 if providers_available else now + 60
    runtime.dex = SimpleNamespace(exact_pools_fresh=AsyncMock(return_value={}))
    runtime.gecko_pools = SimpleNamespace(get_pools=AsyncMock(return_value={}))
    runtime.coingecko = SimpleNamespace(
        status=lambda: {}, available=lambda: providers_available,
        get_pools=AsyncMock(return_value={}),
    )
    runtime.store = SimpleNamespace(
        CHAIN_MEME_TRADER_ACTIVE_VERSION=version,
        set_kv=Mock(),
        chain_meme_trader_market_mark_targets=Mock(return_value=rows),
        apply_chain_meme_trader_market_mark_batch=Mock(),
        evaluate_chain_meme_trader_market_marks=Mock(),
        heartbeat=Mock(),
    )
    return runtime, rows


def test_cooled_head_does_not_block_later_chain_with_due_demo_route():
    async def scenario():
        now = asyncio.get_running_loop().time()
        runtime, (head, ready) = _runtime(now)
        ready["next_complement_attempt"] = 0
        untouched_head = copy.deepcopy(head)

        await runtime.complementary_market_data_once()

        runtime.dex.exact_pools_fresh.assert_not_awaited()
        runtime.gecko_pools.get_pools.assert_not_awaited()
        runtime.coingecko.get_pools.assert_awaited_once_with(
            ready["chain"], [ready["pair_address"]],
        )
        assert head == untouched_head  # Not selected, not marked attempted/failed.
        assert ready["next_attempt"] >= now + 10
        assert ready["next_complement_attempt"] >= now + 60
        outcomes = runtime.store.apply_chain_meme_trader_market_mark_batch.call_args.args[0]
        assert len(outcomes) == 1
        assert outcomes[0]["token_id"] == ready["token_id"]
        assert outcomes[0]["kind"] == "pool_failure"  # Empty response is not recovery.

    asyncio.run(scenario())


@pytest.mark.parametrize("blocked_by", ["pool_deadlines", "provider_unavailable"])
def test_all_routes_cooled_make_no_requests_and_do_not_advance_attempts(blocked_by):
    async def scenario():
        now = asyncio.get_running_loop().time()
        runtime, rows = _runtime(now, providers_available=blocked_by == "pool_deadlines")
        if blocked_by == "provider_unavailable":
            for row in rows:
                row.update(next_primary_attempt=0, next_public_attempt=0, next_complement_attempt=0)
        unchanged_queue = copy.deepcopy(runtime._market_pool_gaps)

        await runtime.complementary_market_data_once()

        runtime.dex.exact_pools_fresh.assert_not_awaited()
        runtime.gecko_pools.get_pools.assert_not_awaited()
        runtime.coingecko.get_pools.assert_not_awaited()
        assert runtime._market_pool_gaps == unchanged_queue
        runtime.store.chain_meme_trader_market_mark_targets.assert_not_called()
        runtime.store.apply_chain_meme_trader_market_mark_batch.assert_not_called()
        runtime.store.evaluate_chain_meme_trader_market_marks.assert_not_called()
        runtime.store.heartbeat.assert_not_called()

    asyncio.run(scenario())
