from __future__ import annotations

import asyncio
from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime, initial_config


def make_runtime(tmp_path):
    config = initial_config()
    config["database"] = "market-api-runtime.sqlite3"
    config["bridge"]["enabled"] = False
    runtime = Runtime(config, tmp_path)
    async def no_exact(chain, addresses):
        return {}
    runtime.dex.exact_pools_fresh = no_exact
    return runtime


def pair_payload(token: TokenCandidate, pool: str, *, provider="coingecko-demo", observed=None):
    observed = observed or utcnow()
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
        "marketCap": None,
        "source": provider,
        "provider": provider,
        "observedAt": iso(observed),
    }


class FakeCoinGecko:
    def __init__(self, outputs=(), *, available=True):
        self.outputs = list(outputs)
        self.is_available = available
        self.calls = []

    def available(self):
        return self.is_available

    def status(self):
        return {
            "provider": "coingecko-demo",
            "available": self.is_available,
            "remaining_local_daily": 240,
            "remaining_local_monthly": 8000,
            "local_usage_only": True,
        }

    async def get_pools(self, chain, addresses):
        self.calls.append((chain, list(addresses)))
        output = self.outputs.pop(0) if self.outputs else {}
        return output() if callable(output) else output


def target_for(token: TokenCandidate, pool: str):
    return {
        "token_id": token.token_id,
        "chain": token.chain,
        "address": token.address,
        "entry_pair_addresses": pool,
    }


def test_gecko_one_poll_uses_received_market_pair_without_dex_duplicate(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path)
        observed = utcnow()
        token = TokenCandidate(
            "solana", "G" * 32, "Gecko received market", "GRM",
            source="geckoterminal:solana",
            raw={"market_pair": pair_payload(
                TokenCandidate("solana", "G" * 32, "Gecko received market", "GRM"),
                "pool-gecko", provider="geckoterminal", observed=observed,
            )},
        )

        class Gecko:
            def __init__(self, http, network):
                assert network == "solana"

            async def poll(self):
                return [token]

        class NoDex:
            def __getattr__(self, name):
                raise AssertionError(f"unexpected Dex call: {name}")

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        runtime.dex = NoDex()
        await runtime._poll_gecko_network("solana")
        snapshot = runtime.store.latest_snapshot(token.token_id)
        assert snapshot is not None
        assert snapshot.provider == "geckoterminal"
        assert snapshot.price_usd == 1.25
        assert snapshot.observed_at == observed
        assert runtime.store.token_detail_hydration(token.token_id)["status"] == "hydrated"
        await runtime.close()

    asyncio.run(scenario())


def test_healthy_held_dex_pool_never_calls_complementary_provider(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "H" * 32, "Healthy Dex", "HDX")
        pool = "healthy-pool"
        observed = utcnow()

        class Dex:
            async def batch_quote_fresh(self, chain, addresses):
                assert (chain, list(addresses)) == ("solana", [token.address])
                pair = pair_payload(token, pool, provider="dexscreener", observed=observed)
                return {token.token_id: (
                    token,
                    TokenSnapshot(
                        token.chain, token.address, 1.25, 25_000, None, 500, 8, 3,
                        observed_at=observed, ingested_at=observed,
                        provider="dexscreener", raw={"pair": pair},
                    ),
                )}

        runtime.dex = Dex()
        coingecko = FakeCoinGecko()
        runtime.coingecko = coingecko
        refreshed = await runtime._refresh_chain_meme_market_marks(
            [target_for(token, pool)], heartbeat_name="fixture", high_priority=True,
        )
        assert refreshed == 1
        assert runtime._market_pool_gaps == {}
        await runtime.complementary_market_data_once()
        assert coingecko.calls == []
        await runtime.close()

    asyncio.run(scenario())


def test_dex_gap_queues_then_wrong_token_and_wrong_pool_are_refused(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "M" * 32, "Missing Dex", "MDX")
        pool = "entry-pool"
        target = target_for(token, pool)

        class MissingDex:
            async def batch_quote_fresh(self, chain, addresses):
                return {}
            async def exact_pools_fresh(self, chain, addresses):
                return {}

        wrong_token = TokenCandidate("solana", "W" * 32, "Wrong", "WRG")
        coingecko = FakeCoinGecko([
            lambda: {pool: pair_payload(wrong_token, pool)},
            lambda: {pool: pair_payload(token, "other-pool")},
        ])
        runtime.dex = MissingDex()
        runtime.coingecko = coingecko
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]

        await runtime._refresh_chain_meme_market_marks(
            [target], heartbeat_name="fixture", high_priority=True,
        )
        assert coingecko.calls == []
        assert len(runtime._market_pool_gaps) == 1

        before = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at FROM chain_meme_trader_market_marks WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        await runtime.complementary_market_data_once()
        after_wrong_token = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at FROM chain_meme_trader_market_marks WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        assert tuple(after_wrong_token) == tuple(before)

        next(iter(runtime._market_pool_gaps.values()))["next_attempt"] = 0.0
        next(iter(runtime._market_pool_gaps.values()))["next_complement_attempt"] = 0.0
        await runtime.complementary_market_data_once()
        after_wrong_pool = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at FROM chain_meme_trader_market_marks WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        assert tuple(after_wrong_pool) == tuple(before)
        assert coingecko.calls == [("solana", [pool]), ("solana", [pool])]
        await runtime.close()

    asyncio.run(scenario())


def test_cached_observation_does_not_advance_market_sample_or_old_period(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "C" * 32, "Cached observation", "CCH")
        pool = "cached-pool"
        target = target_for(token, pool)
        observed = utcnow()
        same_pair = pair_payload(token, pool, observed=observed)
        coingecko = FakeCoinGecko([{pool: same_pair}, {pool: same_pair}])
        runtime.coingecko = coingecko
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime._queue_market_pool_gap(target, pool, [])
        old_counts = tuple(runtime.store.db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM chain_meme_trader_v6_activations),"
            "(SELECT COUNT(*) FROM chain_meme_trader_trades),"
            "(SELECT COUNT(*) FROM chain_meme_trader_account_snapshots)"
        ).fetchone())

        await runtime.complementary_market_data_once()
        first = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at,provider FROM chain_meme_trader_market_marks "
            "WHERE token_id=?", (token.token_id,),
        ).fetchone()
        next(iter(runtime._market_pool_gaps.values()))["next_attempt"] = 0.0
        next(iter(runtime._market_pool_gaps.values()))["next_complement_attempt"] = 0.0
        await runtime.complementary_market_data_once()
        second = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at,provider FROM chain_meme_trader_market_marks "
            "WHERE token_id=?", (token.token_id,),
        ).fetchone()
        assert tuple(second) == tuple(first)
        assert first["provider"] == "coingecko-demo"
        new_counts = tuple(runtime.store.db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM chain_meme_trader_v6_activations),"
            "(SELECT COUNT(*) FROM chain_meme_trader_trades),"
            "(SELECT COUNT(*) FROM chain_meme_trader_account_snapshots)"
        ).fetchone())
        assert new_counts == old_counts
        await runtime.close()

    asyncio.run(scenario())


def test_per_pool_due_and_unavailable_budget_are_silent_without_http(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "D" * 32, "Due gate", "DUE")
        pool = "due-pool"
        target = target_for(token, pool)
        coingecko = FakeCoinGecko([{}])
        runtime.coingecko = coingecko
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime._queue_market_pool_gap(target, pool, [])

        await runtime.complementary_market_data_once()
        assert coingecko.calls == [("solana", [pool])]
        await runtime.complementary_market_data_once()
        assert coingecko.calls == [("solana", [pool])]

        next(iter(runtime._market_pool_gaps.values()))["next_attempt"] = 0.0
        coingecko.is_available = False
        await runtime.complementary_market_data_once()
        assert coingecko.calls == [("solana", [pool])]
        await runtime.close()

    asyncio.run(scenario())


def test_original_pool_due_order_rotates_past_repeated_missing_chain(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        rh = TokenCandidate("robinhood", "0x" + "1" * 40, "Missing RH", "RH")
        sol = TokenCandidate("solana", "S" * 32, "Waiting Solana", "SOL")
        targets = [target_for(rh, "rh-pool"), target_for(sol, "sol-pool")]
        calls = []
        async def exact(chain, addresses):
            calls.append((chain, addresses))
            assert len(addresses) <= 30
            return {} if chain == "robinhood" else {
                "sol-pool": pair_payload(sol, "sol-pool", provider="dexscreener")}
        runtime.dex.exact_pools_fresh = exact
        runtime.coingecko = FakeCoinGecko(available=False)
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: targets
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: None
        for target in targets:
            runtime._queue_market_pool_gap(target, target["entry_pair_addresses"], [])
        await runtime.complementary_market_data_once()
        # At the next periodic tick RH is due again, but SOL is still unattempted.
        runtime._market_pool_gaps[(rh.token_id, "rh-pool")]["next_attempt"] = (
            asyncio.get_running_loop().time() - 1)
        await runtime.complementary_market_data_once()
        mark = runtime.store.db.execute(
            "SELECT provider FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (sol.token_id, "sol-pool"),
        ).fetchone()
        assert mark["provider"] == "dexscreener"
        await runtime.complementary_market_data_once()
        assert calls == [("robinhood", ["rh-pool"]), ("solana", ["sol-pool"]),
                         ("robinhood", ["rh-pool"])]
        assert runtime.coingecko.calls == []
        await runtime.close()
    asyncio.run(scenario())


def test_exact_original_pool_recovers_dust_without_spending_complement_quota(tmp_path):
    from memetrader.collectors import DexScreenerClient
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "S" * 32, "Original dust pool", "DUST")
        pool = "original-pool"
        target = target_for(token, pool)
        calls = []
        payload = pair_payload(token, pool, provider="dexscreener")
        payload["liquidity"]["usd"] = 0.84
        class Http:
            async def get(self, url, *, ttl):
                calls.append((url, ttl))
                class Response:
                    def json(self):
                        return {"pairs": [payload]}
                return Response()
        runtime.dex = DexScreenerClient(Http())
        runtime.coingecko = FakeCoinGecko(available=False)
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        evaluations = []
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: evaluations.append(kwargs)
        runtime._queue_market_pool_gap(target, pool, ["current-period"])
        await runtime.complementary_market_data_once()
        mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert mark["liquidity_usd"] == 0.84
        assert mark["provider"] == "dexscreener"
        assert evaluations == [{"definition_version": "current-period", "token_ids": [token.token_id]}]
        assert calls == [(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pool}", 0)]
        assert runtime.coingecko.calls == []
        await runtime.close()
    asyncio.run(scenario())


def test_token_endpoint_gap_after_restart_is_not_original_pool_absence(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "R" * 32, "Known complement", "RST")
        pool = "known-original"
        target = target_for(token, pool)
        from memetrader.collectors import DexScreenerClient
        pair = pair_payload(token, pool)
        snapshot = runtime._complement_snapshot(pair)
        runtime.store.upsert_chain_meme_trader_pool_mark(token, snapshot)
        class Dex:
            async def batch_quote_fresh(self, chain, addresses):
                return {}
        runtime.dex = Dex()
        runtime.coingecko = FakeCoinGecko(available=False)
        # New Runtime's in-memory complement set is empty; database evidence survives.
        assert not runtime._market_complement_pools
        await runtime._refresh_chain_meme_market_marks([target], heartbeat_name="fixture", high_priority=True)
        mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert mark["consecutive_misses"] == 0
        assert mark["last_success_at"] is not None
        assert runtime._market_pool_gaps
        await runtime.close()
    asyncio.run(scenario())
