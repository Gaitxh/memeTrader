"""Regression coverage for prompt exact-pool recovery writes."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.runtime import Runtime


def _pair(token: TokenCandidate, pool: str) -> dict:
    observed = utcnow()
    return {
        "chainId": token.chain,
        "tokenAddress": token.address,
        "pairAddress": pool,
        "baseToken": {"address": token.address, "name": token.name, "symbol": token.symbol},
        "quoteToken": {"address": "USDC", "name": "USD Coin", "symbol": "USDC"},
        "dexId": "raydium",
        "priceUsd": "1.25",
        "liquidity": {"usd": 25_000.0},
        "volume": {"m5": 500.0},
        "txns": {"m5": {"buys": 8, "sells": 3}},
        "pairCreatedAt": round((observed - timedelta(minutes=2)).timestamp() * 1000),
        "provider": "dexscreener",
        "observedAt": iso(observed),
    }


def _target(token: TokenCandidate, pool: str) -> dict:
    return {
        "token_id": token.token_id,
        "chain": token.chain,
        "address": token.address,
        "entry_pair_addresses": pool,
    }


def test_exact_original_pool_is_applied_before_other_pool_fallback():
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        version = "test-original-pool-early-apply"
        token_a = TokenCandidate("solana", "A" * 32, "Exact first", "EXACT")
        token_b = TokenCandidate("solana", "B" * 32, "Public second", "PUBLIC")
        pool_a, pool_b = "pool-a", "pool-b"
        target_a, target_b = _target(token_a, pool_a), _target(token_b, pool_b)
        applied, evaluations = [], []

        def apply(outcomes, *, recorded_at):
            applied.append((outcomes, recorded_at))

        def evaluate(**kwargs):
            evaluations.append(kwargs)

        runtime.config = {"paper": {"max_quote_age_seconds": 45}}
        runtime._market_pool_gaps = {}
        runtime._market_complement_pools = set()
        runtime._gecko_pool_backoff_until = 0.0
        runtime._dex_quote_lock = asyncio.Semaphore(8)
        runtime._dex_quote_backoff_until = 0.0
        runtime._dex_quote_low_priority_available = lambda: True
        runtime.store = SimpleNamespace(
            CHAIN_MEME_TRADER_ACTIVE_VERSION=version,
            set_kv=Mock(),
            chain_meme_trader_market_mark_targets=Mock(return_value=[target_a, target_b]),
            apply_chain_meme_trader_market_mark_batch=apply,
            evaluate_chain_meme_trader_market_marks=evaluate,
            heartbeat=Mock(),
        )

        async def exact(chain, pools):
            assert (chain, pools) == ("solana", [pool_a, pool_b])
            return {pool_a: _pair(token_a, pool_a)}

        async def public(chain, pools):
            assert (chain, pools) == ("solana", [pool_b])
            assert applied
            first_outcomes = applied[0][0]
            assert any(
                outcome["kind"] == "pool_visible" and outcome["target_token_id"] == token_a.token_id
                for outcome in first_outcomes
            )
            assert any(
                call["definition_version"] == version and token_a.token_id in call["token_ids"]
                for call in evaluations
            )
            return {pool_b: _pair(token_b, pool_b)}

        runtime.dex = SimpleNamespace(exact_pools_fresh=exact)
        runtime.gecko_pools = SimpleNamespace(get_pools=public)
        runtime.coingecko = SimpleNamespace(
            status=lambda: {}, available=lambda: True,
            get_pools=AsyncMock(side_effect=AssertionError("Demo must not run after public recovery")),
        )
        runtime._queue_market_pool_gap(target_a, pool_a, [version])
        runtime._queue_market_pool_gap(target_b, pool_b, [version])

        await runtime.complementary_market_data_once()

        runtime.coingecko.get_pools.assert_not_awaited()
        assert any(
            outcome["kind"] == "pool_visible" and outcome["target_token_id"] == token_b.token_id
            for outcomes, _ in applied for outcome in outcomes
        )

    asyncio.run(scenario())
