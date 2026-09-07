from __future__ import annotations

import asyncio
from datetime import timedelta
import httpx
import json
import pytest
import time

from memetrader.collectors import DexScreenerClient, HttpClient
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime, initial_config
from memetrader.runtime_timing import RuntimeTiming


def make_runtime(tmp_path):
    config = initial_config()
    config["database"] = "market-api-runtime.sqlite3"
    config["bridge"]["enabled"] = False
    runtime = Runtime(config, tmp_path)
    async def no_exact(chain, addresses):
        return {}
    runtime.dex.exact_pools_fresh = no_exact
    runtime.gecko_pools.get_pools = no_exact
    return runtime


def test_chain_entry_burst_yields_to_execution_after_work_budget(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        runtime.chain_meme_trader_only = True
        runtime.CHAIN_MEME_ENTRY_WORK_BUDGET_SECONDS = 0.01
        enroll_calls = 0
        execution_checks = 0

        def slow_enroll(*, limit, definition_version):
            nonlocal enroll_calls
            enroll_calls += 1
            time.sleep(0.02)
            return {"evaluated": 4}

        def due_execution(*, definition_version=None):
            nonlocal execution_checks
            execution_checks += 1
            return None

        runtime.store.enroll_chain_meme_trader_v6 = slow_enroll
        runtime.store.due_chain_meme_trader_execution = due_execution
        runtime._last_chain_account_snapshot_monotonic = (
            asyncio.get_running_loop().time()
        )

        await runtime.chain_meme_trader_once()

        assert enroll_calls == 1
        assert execution_checks == 1
        await runtime.chain_meme_trader_once()
        assert enroll_calls == 2
        assert execution_checks == 2
        await runtime.close()

    asyncio.run(scenario())


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


def test_held_cooldown_releases_priority_without_fake_market_result(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        runtime.chain_meme_trader_only = True
        runtime.runtime_timing = RuntimeTiming()
        token = TokenCandidate("solana", "A" * 32, "Held cooldown", "HELD")
        target = target_for(token, "original-pool")
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime._dex_quote_backoff_until = asyncio.get_running_loop().time() + 120

        def no_result(*args, **kwargs):
            raise AssertionError("local deferral must not write a market result")

        runtime.store.apply_chain_meme_trader_market_mark_batch = no_result
        await asyncio.wait_for(runtime.chain_meme_market_marks_once(), timeout=1)
        assert runtime._chain_meme_active_idle().is_set()
        assert runtime._pattern_held_tokens == {token.token_id}
        assert (token.token_id, "original-pool") in runtime._market_pool_gaps
        assert "held_fetch" not in runtime.runtime_timing.snapshot()["components"]
        await runtime.close()

    asyncio.run(scenario())


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
        token.raw["market_pair"]["volume"]["m5"] = 200_000.0
        token.raw["market_pair"]["txns"]["m5"] = {"buys": 300, "sells": 100}

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
        shadow = runtime.store.db.execute(
            "SELECT c.*,s.provider,s.raw_json FROM onchain_only_shadow_cohorts c "
            "JOIN token_snapshots s ON s.id=c.trigger_snapshot_id WHERE c.token_id=?",
            (token.token_id,),
        ).fetchone()
        assert shadow is not None and shadow["baseline_status"] == "valid"
        assert shadow["momentum_score"] >= 80
        assert shadow["provider"] == "geckoterminal"
        assert json.loads(shadow["raw_json"])["pair"]["pairAddress"] == "pool-gecko"
        assert shadow["trigger_observed_at"] == iso(observed)
        assert shadow["trigger_observed_at"] <= shadow["trigger_ingested_at"] <= shadow["trigger_recorded_at"]
        await runtime.close()

    asyncio.run(scenario())


def test_gecko_new_pool_cohort_batch_keeps_all_pools_and_reports_overflow(tmp_path, monkeypatch):
    async def scenario():
        runtime = make_runtime(tmp_path)
        observed = utcnow()
        runtime._cohort_started_at = observed - timedelta(seconds=1)
        tokens = []
        for index, letter in enumerate("ABCDEFGHJKLM"):
            token = TokenCandidate("solana", letter * 32, "New pool", "NEW")
            token.raw = {"market_pair": pair_payload(
                token, f"pool-{index}", provider="geckoterminal", observed=observed,
            )}
            tokens.append(token)
        sibling = TokenCandidate("solana", tokens[0].address, "Sibling pool", "NEW")
        sibling.raw = {"market_pair": pair_payload(
            sibling, "sibling-pool", provider="geckoterminal", observed=observed,
        )}
        tokens.append(sibling)

        class Gecko:
            def __init__(self, http, network):
                pass

            async def poll(self):
                return tokens

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        runtime.autonomous_search.resolve_token_context_trigger = lambda *args, **kwargs: None
        await runtime._poll_gecko_network("solana")
        assert len(runtime._cohort_batches) == 1
        batch = runtime._cohort_batches[0][1]
        assert len(batch) == len(tokens) == 13
        assert len({(token.token_id, snapshot.raw["pair"]["pairAddress"])
                    for token, snapshot in batch}) == 13
        assert all(snapshot.observed_at == observed for _, snapshot in batch)
        for _ in range(8):
            runtime._remember_pattern_quotes({"one": batch[0]})
        assert len(runtime._cohort_batches) == 8
        assert runtime._cohort_dropped_batches == 1
        assert runtime._cohort_dropped_quotes == 13
        await runtime.chain_meme_cohort_observer_once()
        saved = runtime.store.get_kv(
            f"passive-cohort:{runtime.store.CHAIN_MEME_TRADER_ACTIVE_VERSION}", {})
        assert saved["dropped_batches"] == 1
        assert saved["dropped_quotes"] == 13
        await runtime.close()

    asyncio.run(scenario())


def test_gecko_new_pool_reuses_only_fresh_same_held_pool_once_per_round(
    tmp_path, monkeypatch,
):
    async def scenario():
        runtime = make_runtime(tmp_path)
        observed = utcnow()
        same = TokenCandidate(
            "solana", "A" * 32, "Same held pool", "SAME",
            source="geckoterminal:solana",
            raw={"market_pair": pair_payload(
                TokenCandidate("solana", "A" * 32, "Same held pool", "SAME"),
                "held-pool", provider="geckoterminal", observed=observed,
            )},
        )
        other = TokenCandidate(
            "solana", "B" * 32, "Different pool", "DIFF",
            source="geckoterminal:solana",
            raw={"market_pair": pair_payload(
                TokenCandidate("solana", "B" * 32, "Different pool", "DIFF"),
                "new-pool", provider="geckoterminal", observed=observed,
            )},
        )

        class Gecko:
            def __init__(self, http, network):
                assert network == "solana"
            async def poll(self):
                return [same, other]

        target_calls = []
        def targets(**kwargs):
            target_calls.append(kwargs)
            return [
                {**target_for(same, "held-pool"), "watch_reason": "OPEN_POSITION"},
                {**target_for(other, "original-other"), "watch_reason": "OPEN_POSITION"},
            ]

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        runtime.store.chain_meme_trader_market_mark_targets = targets
        evaluations = []
        runtime.store.evaluate_chain_meme_trader_market_marks = (
            lambda **kwargs: evaluations.append(kwargs)
        )
        await runtime._poll_gecko_network("solana")
        same_mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (same.token_id, "held-pool"),
        ).fetchone()
        other_mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=?",
            (other.token_id,),
        ).fetchone()
        assert len(target_calls) == 1
        assert same_mark["status"] == "VISIBLE"
        assert same_mark["provider"] == "geckoterminal"
        assert other_mark is None
        assert evaluations and all(
            item["token_ids"] == [same.token_id] for item in evaluations
        )
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
        failure = runtime.store.db.execute(
            "SELECT status,consecutive_misses,first_missing_at,failure_kind "
            "FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert failure["status"] == "UNKNOWN"
        assert failure["consecutive_misses"] == 0 and failure["first_missing_at"] is None
        assert failure["failure_kind"] == "DATA_REJECTED:ENTRY_POOL_INVALID"
        health = runtime.store.db.execute(
            "SELECT last_ok_at,last_item_at FROM source_health "
            "WHERE source='coingecko:gap_recovery'",
        ).fetchone()
        assert health["last_ok_at"] is not None and health["last_item_at"] is None
        await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("provider", ["coingecko-demo", "geckoterminal"])
def test_cached_observation_does_not_advance_market_sample_or_old_period(tmp_path, provider):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "C" * 32, "Cached observation", "CCH")
        pool = "cached-pool"
        target = target_for(token, pool)
        observed = utcnow()
        same_pair = pair_payload(token, pool, observed=observed, provider=provider)
        coingecko = FakeCoinGecko([{pool: same_pair}, {pool: same_pair}])
        if provider == "geckoterminal":
            runtime.gecko_pools = coingecko
            runtime.coingecko = FakeCoinGecko()
        else:
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
        same_pair["raw"] = {"http_cache": {"local_cache_hit": True}}
        next(iter(runtime._market_pool_gaps.values()))["next_attempt"] = 0.0
        next(iter(runtime._market_pool_gaps.values()))["next_complement_attempt"] = 0.0
        await runtime.complementary_market_data_once()
        second = runtime.store.db.execute(
            "SELECT sample_sequence,observed_at,provider FROM chain_meme_trader_market_marks "
            "WHERE token_id=?", (token.token_id,),
        ).fetchone()
        assert tuple(second) == tuple(first)
        assert first["provider"] == provider
        if provider == "geckoterminal":
            assert runtime.coingecko.calls == []
            assert runtime.store.db.execute(
                "SELECT COUNT(*) FROM source_health WHERE source='coingecko:gap_recovery'"
            ).fetchone()[0] == 0
        new_counts = tuple(runtime.store.db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM chain_meme_trader_v6_activations),"
            "(SELECT COUNT(*) FROM chain_meme_trader_trades),"
            "(SELECT COUNT(*) FROM chain_meme_trader_account_snapshots)"
        ).fetchone())
        assert new_counts == old_counts
        await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("status_code", [404, 429])
def test_public_pool_error_defers_without_blocking_demo(tmp_path, status_code):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "P" * 32, "Public fallback", "PUB")
        pool = "public-pool"
        target = target_for(token, pool)
        calls = []

        async def fail(chain, addresses):
            calls.append((chain, addresses))
            response = httpx.Response(status_code, headers={"Retry-After": "120"},
                request=httpx.Request("GET", "https://api.geckoterminal.com/api/v2/networks/solana/pools/public-pool"))
            response.raise_for_status()

        runtime.gecko_pools.get_pools = fail
        runtime.coingecko = FakeCoinGecko([{pool: pair_payload(token, pool)}])
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime._queue_market_pool_gap(target, pool, [])
        started = asyncio.get_running_loop().time()
        await runtime.complementary_market_data_once()
        assert len(calls) == len(runtime.coingecko.calls) == 1
        mark = runtime.store.db.execute(
            "SELECT provider,status,consecutive_misses FROM chain_meme_trader_pool_marks WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        assert tuple(mark) == ("coingecko-demo", "VISIBLE", 0)
        gap = next(iter(runtime._market_pool_gaps.values()))
        assert gap["next_public_attempt"] >= started + 120
        assert (runtime._gecko_pool_backoff_until > started) == (status_code == 429)
        gap["next_attempt"] = 0
        await runtime.complementary_market_data_once()
        assert len(calls) == len(runtime.coingecko.calls) == 1
        await runtime.close()

    asyncio.run(scenario())


def test_primary_recovery_during_public_fetch_discards_late_fallback(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "R" * 32, "Recovered", "REC")
        target = target_for(token, "recovered-pool")
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.coingecko = FakeCoinGecko()
        runtime._queue_market_pool_gap(target, "recovered-pool", [])

        async def recover(chain, addresses):
            runtime._market_pool_gaps.clear()
            return {"recovered-pool": pair_payload(token, "recovered-pool", provider="geckoterminal")}

        runtime.gecko_pools.get_pools = recover
        await runtime.complementary_market_data_once()
        assert runtime.coingecko.calls == []
        assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_pool_marks").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_public_gecko_host_pacing_leaves_other_sources_unchanged(monkeypatch):
    async def scenario():
        http = HttpClient(min_host_interval=0.25)
        waits = []

        async def record_wait(seconds):
            waits.append(seconds)

        monkeypatch.setattr("memetrader.collectors.asyncio.sleep", record_wait)
        for host in ("api.geckoterminal.com", "api.dexscreener.com"):
            http._last[host] = time.monotonic()
            await http._reserve_host_request_start(host)
        assert 2.0 < waits[0] <= 2.1
        assert 0.2 < waits[1] <= 0.25
        await http.close()

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


@pytest.mark.parametrize("blocked_by", ["held_busy", "dex_backoff"])
def test_complement_skips_blocked_dex_but_uses_cg_and_discards_after_recovery(
    tmp_path, blocked_by,
):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("solana", "I" * 32, "Idle lane", "IDL")
        pool = "idle-pool"
        target = target_for(token, pool)
        calls = []

        async def exact(chain, addresses):
            calls.append((chain, list(addresses)))
            runtime._market_pool_gaps.pop(next(iter(runtime._market_pool_gaps)), None)
            return {}

        runtime.dex.exact_pools_fresh = exact
        runtime.coingecko = FakeCoinGecko([
            {pool: pair_payload(token, pool)},
        ])
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime._queue_market_pool_gap(target, pool, [])

        if blocked_by == "held_busy":
            runtime._chain_meme_active_idle().clear()
        else:
            runtime._dex_quote_backoff_until = asyncio.get_running_loop().time() + 60
        await runtime.complementary_market_data_once()
        assert calls == []
        assert runtime.coingecko.calls == [("solana", [pool])]
        mark = runtime.store.db.execute(
            "SELECT sample_sequence,provider FROM chain_meme_trader_pool_marks "
            "WHERE token_id=? AND pair_address=?", (token.token_id, pool),
        ).fetchone()
        assert tuple(mark) == (1, "coingecko-demo")

        runtime._chain_meme_active_idle().set()
        runtime._dex_quote_backoff_until = 0
        gap = next(iter(runtime._market_pool_gaps.values()))
        gap["next_attempt"] = gap["next_complement_attempt"] = 0
        await runtime.complementary_market_data_once()
        assert calls == [("solana", [pool])]
        assert runtime.coingecko.calls == [("solana", [pool])]
        assert runtime.store.db.execute(
            "SELECT sample_sequence FROM chain_meme_trader_pool_marks "
            "WHERE token_id=? AND pair_address=?", (token.token_id, pool),
        ).fetchone()[0] == 1
        await runtime.close()

    asyncio.run(scenario())


def test_fresh_dex_quote_does_not_sleep_and_retry_inside_held_lane():
    async def scenario():
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(
                429, headers={"Retry-After": "15"}, request=request,
            )

        http = HttpClient(
            transport=httpx.MockTransport(handler), min_host_interval=0,
        )
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await DexScreenerClient(http).batch_quote_fresh(
                    "solana", ["S" * 32],
                )
            assert calls == 1
        finally:
            await http.close()

    asyncio.run(scenario())


def test_exact_empty_with_unavailable_cg_is_coverage_failure_not_writeoff(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        runtime.store.activate_chain_meme_trader_funded_period()
        version = runtime.store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        token = TokenCandidate(
            "bsc", "0x1a5f9d77ca46646cd4937fd8d093f460b66f4444",
            "Coverage gap", "GAP",
        )
        pool = "0x" + "e2" * 32  # A BSC v4-style 64-hex pool identity.
        observed = utcnow() - timedelta(seconds=90)
        entry = TokenSnapshot(
            token.chain, token.address, 1.0, None, None, 10.0, 1, 1,
            observed_at=observed, ingested_at=observed, provider="geckoterminal",
            raw={"pair": pair_payload(token, pool, provider="geckoterminal", observed=observed)},
        )
        runtime.store.upsert_token(token, seen_at=observed)
        entry_id = runtime.store.add_snapshot(entry)
        runtime.store.upsert_chain_meme_trader_pool_mark(
            token, entry, recorded_at=observed,
        )
        registration = runtime.store.db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (version,),
        ).fetchone()
        arm_id = json.loads(registration[0])["policies"][0]["arm_id"]
        with runtime.store.db:
            cursor = runtime.store.db.execute(
                "INSERT INTO chain_meme_trader_v6_cohorts("
                "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
                "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
                (version, token.token_id, "broad_launch", entry_id, pool, iso(observed)),
            )
            cohort_id = int(cursor.lastrowid)
            runtime.store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
                "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,amount_raw,"
                "stake_usd,highest_signal_price_usd,status,opened_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (version, arm_id, cohort_id, token.token_id, -1, -1, entry_id,
                 1.0, "1000000", 20.0, 1.0, "open", iso(observed)),
            )

        exact_calls = []
        async def exact(chain, addresses):
            exact_calls.append((chain, list(addresses)))
            return {}  # HTTP 200 with no matching pair.
        runtime.dex.exact_pools_fresh = exact
        runtime.coingecko = FakeCoinGecko(available=False)
        target = target_for(token, pool)
        runtime._queue_market_pool_gap(target, pool, [version])
        await runtime.complementary_market_data_once()

        mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert exact_calls == [("bsc", [pool])]
        assert mark["status"] == "VISIBLE"
        assert mark["price_usd"] == pytest.approx(1.0)
        assert mark["consecutive_misses"] == 0 and mark["first_missing_at"] is None
        assert mark["failure_kind"] == "DEX_SOURCE_COVERAGE_GAP"
        assert mark["last_attempt_at"] > iso(observed)
        assert runtime.store.db.execute(
            "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=? AND shadow_cohort_id=?", (version, arm_id, cohort_id),
        ).fetchone()[0] == "open"
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='WRITEOFF'",
        ).fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_exact_coverage_backoff_does_not_delay_independent_pool_fallback(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("robinhood", "0x" + "13" * 20, "Fallback")
        pool = "0x" + "ab" * 20
        target = target_for(token, pool)
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.coingecko = FakeCoinGecko(available=False)
        calls = {"dex": 0, "public": 0}
        async def empty_exact(chain, addresses):
            calls["dex"] += 1
            runtime._queue_market_pool_gap(target, pool, [])  # Hot-lane refresh while request is in flight.
            return {}
        async def public(chain, addresses):
            calls["public"] += 1
            return {pool: pair_payload(token, pool, provider="geckoterminal")}
        runtime.dex.exact_pools_fresh = empty_exact
        runtime.gecko_pools.get_pools = public
        runtime._queue_market_pool_gap(target, pool, [])
        await runtime.complementary_market_data_once()
        key = (token.token_id, pool)
        retry_at = runtime._market_pool_gaps[key]["next_primary_attempt"]
        assert retry_at > asyncio.get_running_loop().time() + 50
        # The hot lane can report the same gap again without resetting its retry clock.
        runtime._queue_market_pool_gap(target, pool, [])
        assert runtime._market_pool_gaps[key]["next_primary_attempt"] == retry_at
        runtime._market_pool_gaps[key]["next_attempt"] = 0
        await runtime.complementary_market_data_once()
        assert calls == {"dex": 1, "public": 2}
        runtime._market_pool_gaps[key].update(next_attempt=0, next_primary_attempt=0)
        await runtime.complementary_market_data_once()
        assert calls == {"dex": 2, "public": 3}
        assert runtime.coingecko.calls == []
        await runtime.close()
    asyncio.run(scenario())


def test_partial_exact_response_marks_only_uncovered_pool_as_coverage_failure(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("bsc", "0x" + "12" * 20, "Partial", "PRT")
        covered, uncovered = "0x" + "ab" * 20, "0x" + "cd" * 32
        target = target_for(token, f"{covered},{uncovered}")
        old_pair = pair_payload(token, uncovered, provider="coingecko-demo")
        old_pair["priceUsd"] = "2.0"
        runtime.store.upsert_chain_meme_trader_pool_mark(
            token, runtime._complement_snapshot(old_pair),
        )
        before = runtime.store.db.execute(
            "SELECT sample_sequence,price_usd FROM chain_meme_trader_pool_marks "
            "WHERE token_id=? AND pair_address=?", (token.token_id, uncovered),
        ).fetchone()

        async def exact(chain, addresses):
            assert set(addresses) == {covered, uncovered}
            return {covered: pair_payload(token, covered, provider="dexscreener")}
        runtime.dex.exact_pools_fresh = exact
        runtime.coingecko = FakeCoinGecko(available=False)
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: None
        runtime._queue_market_pool_gap(target, covered, [])
        runtime._queue_market_pool_gap(target, uncovered, [])
        await runtime.complementary_market_data_once()

        visible = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, covered),
        ).fetchone()
        gap = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, uncovered),
        ).fetchone()
        assert visible["status"] == "VISIBLE" and visible["provider"] == "dexscreener"
        assert gap["status"] == "VISIBLE" and gap["consecutive_misses"] == 0
        assert gap["first_missing_at"] is None
        assert gap["failure_kind"] == "DEX_SOURCE_COVERAGE_GAP"
        assert (gap["sample_sequence"], gap["price_usd"]) == tuple(before)
        await runtime.close()

    asyncio.run(scenario())


def test_cg_canonical_evm_key_lands_for_checksum_requested_pool(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("bsc", "0x" + "34" * 20, "Checksum", "SUM")
        requested_pool = "0xAbCdEf1234567890aBCdEf1234567890ABcDef12"
        canonical_pool = requested_pool.lower()
        target = target_for(token, requested_pool)
        runtime.coingecko = FakeCoinGecko([{
            canonical_pool: pair_payload(
                token, canonical_pool, provider="coingecko-demo",
            ),
        }])
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: None
        runtime._queue_market_pool_gap(target, requested_pool, [])
        await runtime.complementary_market_data_once()
        mark = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, canonical_pool),
        ).fetchone()
        assert mark["status"] == "VISIBLE"
        assert mark["provider"] == "coingecko-demo"
        assert runtime.coingecko.calls == [("bsc", [requested_pool])]
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
        assert calls == [("robinhood", ["rh-pool"]), ("solana", ["sol-pool"])]
        runtime._market_pool_gaps[(rh.token_id, "rh-pool")].update(
            next_attempt=0, next_primary_attempt=0,
        )
        await runtime.complementary_market_data_once()
        assert calls == [("robinhood", ["rh-pool"]), ("solana", ["sol-pool"]),
                         ("robinhood", ["rh-pool"])]
        assert runtime.coingecko.calls == []
        health = runtime.store.db.execute(
            "SELECT * FROM source_health WHERE source='dexscreener:original_pool'"
        ).fetchone()
        assert health["last_item_at"] is not None and not health["last_error"]
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
            async def get(self, url, *, ttl, retry_429):
                calls.append((url, ttl, retry_429))
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
        assert calls == [(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pool}", 0, False)]
        assert runtime.coingecko.calls == []
        await runtime.close()
    asyncio.run(scenario())


def test_first_pool_failure_then_same_pool_quote_side_recovery(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        held = TokenCandidate("robinhood", "0x" + "d5" * 20, "Held QQQ", "QQQ")
        base = TokenCandidate("robinhood", "0x" + "df" * 20, "Pool base", "BIRK")
        pool = "0x" + "ab" * 32  # V4 pool ID is not a 20-byte token address.
        target = target_for(held, pool)
        runtime.store.record_chain_meme_trader_pool_mark_failure(
            token_id=held.token_id, pair_address=pool, chain=held.chain,
            failure_kind="DEX_SOURCE_COVERAGE_GAP")
        row = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (held.token_id, pool)).fetchone()
        assert row["status"] == "UNKNOWN" and row["last_attempt_at"]
        assert row["last_success_at"] is None and row["first_missing_at"] is None
        assert row["sample_sequence"] == row["consecutive_misses"] == 0
        payload = pair_payload(base, pool, provider="dexscreener")
        payload.update(quoteToken={"address": held.address.upper(), "name": held.name, "symbol": held.symbol},
                       priceUsd="0.00001486", priceNative="0.00000002090", marketCap=123_456)
        token, snap = runtime._held_pool_quote(payload, held.token_id)
        assert token.token_id == held.token_id
        expected = .00001486 / .00000002090
        assert snap.price_usd == pytest.approx(expected)
        assert snap.buys_5m == 3 and snap.sells_5m == 8
        assert snap.market_cap_usd is None
        assert snap.raw["pair"]["baseToken"]["address"] == base.address
        assert snap.raw["target_pricing"]["side"] == "quote"
        assert runtime._held_pool_quote({**payload, "priceNative": None}, held.token_id) == (None, None)
        assert runtime._held_pool_quote(payload, "bsc:" + held.address) == (None, None)
        async def exact(chain, pools):
            return {pool: payload}
        runtime.dex.exact_pools_fresh = exact
        runtime.coingecko = FakeCoinGecko(available=False)
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: None
        runtime._queue_market_pool_gap(target, pool, [])
        await runtime.complementary_market_data_once()
        row = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (held.token_id, pool)).fetchone()
        assert row["status"] == "VISIBLE" and row["last_success_at"]
        assert row["price_usd"] == pytest.approx(expected) and row["sample_sequence"] == 1
        runtime.store.record_chain_meme_trader_pool_mark_failure(
            token_id=held.token_id, pair_address=pool, chain=held.chain, failure_kind="HTTP_TIMEOUT")
        after = runtime.store.db.execute(
            "SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (held.token_id, pool)).fetchone()
        assert after["price_usd"] == row["price_usd"]
        assert after["last_success_at"] == row["last_success_at"]
        assert after["sample_sequence"] == 1 and after["first_missing_at"] is None
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


def test_held_positive_price_without_liquidity_keeps_complete_pool_and_gap(tmp_path):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("bsc", "0x" + "71" * 20, "Incomplete held", "INC")
        pool = "0x" + "72" * 20
        target = target_for(token, pool)
        complete_at = utcnow() - timedelta(seconds=2)
        complete = pair_payload(
            token, pool, provider="geckoterminal", observed=complete_at,
        )
        runtime.store.upsert_chain_meme_trader_pool_mark(
            token, runtime._complement_snapshot(complete), recorded_at=complete_at,
        )
        before = runtime.store.db.execute(
            "SELECT sample_sequence,price_usd,liquidity_usd,observed_at,last_success_at "
            "FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        runtime._queue_market_pool_gap(target, pool, [])
        key = (token.token_id, pool)
        runtime._market_complement_pools.add(key)

        incomplete = pair_payload(
            token, pool, provider="dexscreener", observed=utcnow(),
        )
        incomplete["liquidity"]["usd"] = None

        class Dex:
            async def batch_quote_fresh(self, chain, addresses):
                assert (chain, list(addresses)) == ("bsc", [token.address])
                return {token.token_id: (
                    token,
                    TokenSnapshot(
                        token.chain, token.address, 1.25, None, None, 500, 8, 3,
                        observed_at=utcnow(), ingested_at=utcnow(),
                        provider="dexscreener", raw={"pair": incomplete},
                    ),
                )}

        runtime.dex = Dex()
        refreshed = await runtime._refresh_chain_meme_market_marks(
            [target], heartbeat_name="fixture", high_priority=True,
        )
        after = runtime.store.db.execute(
            "SELECT sample_sequence,price_usd,liquidity_usd,observed_at,last_success_at "
            "FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert refreshed == 0
        assert key in runtime._market_pool_gaps
        assert key in runtime._market_complement_pools
        assert tuple(after) == tuple(before)
        await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("public_recovers", [True, False])
def test_incomplete_exact_pool_continues_public_then_demo_fallback(
    tmp_path, public_recovers,
):
    async def scenario():
        runtime = make_runtime(tmp_path)
        token = TokenCandidate("bsc", "0x" + "81" * 20, "Fallback held", "FBK")
        pool = "0x" + "82" * 20
        target = target_for(token, pool)
        incomplete = pair_payload(token, pool, provider="dexscreener")
        incomplete["liquidity"]["usd"] = None
        exact_calls = []
        public_calls = []

        async def exact(chain, addresses):
            exact_calls.append((chain, list(addresses)))
            return {pool: incomplete}

        async def public(chain, addresses):
            public_calls.append((chain, list(addresses)))
            return ({pool: pair_payload(token, pool, provider="geckoterminal")}
                    if public_recovers else {})

        runtime.dex.exact_pools_fresh = exact
        runtime.gecko_pools.get_pools = public
        runtime.coingecko = FakeCoinGecko([
            {pool: pair_payload(token, pool, provider="coingecko-demo")},
        ])
        runtime.store.chain_meme_trader_market_mark_targets = lambda **kwargs: [target]
        runtime.store.evaluate_chain_meme_trader_market_marks = lambda **kwargs: None
        runtime._queue_market_pool_gap(target, pool, [])
        await runtime.complementary_market_data_once()

        mark = runtime.store.db.execute(
            "SELECT provider,status,liquidity_usd,sample_sequence "
            "FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
            (token.token_id, pool),
        ).fetchone()
        assert exact_calls == [("bsc", [pool])]
        assert public_calls == [("bsc", [pool])]
        assert runtime.coingecko.calls == ([] if public_recovers else [("bsc", [pool])])
        assert tuple(mark) == (
            "geckoterminal" if public_recovers else "coingecko-demo",
            "VISIBLE", 25_000.0, 1,
        )
        await runtime.close()

    asyncio.run(scenario())
