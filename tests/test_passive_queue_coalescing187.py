from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime_timing import RuntimeTiming
from test_market_api_runtime import make_runtime, pair_payload


def _quote(token, pool, observed):
    pair = pair_payload(token, pool, provider="dexscreener", observed=observed)
    return token, TokenSnapshot(
        token.chain, token.address, 1.25, 25_000.0, None, 500.0, 8, 3,
        observed_at=observed, ingested_at=observed, provider="dexscreener",
        raw={"pair": pair},
    )


def test_pending_duplicate_coalesces_and_feature_only_upgrades_to_normal(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.runtime_timing = RuntimeTiming()
    runtime._cohort_started_at = utcnow()
    token = TokenCandidate("solana", "A" * 32, "A", "A")
    value = _quote(token, "B" * 32, runtime._cohort_started_at)

    runtime._remember_pattern_quotes(
        {token.token_id: value}, feature_only148={token.token_id: "B" * 32},
    )
    runtime._remember_pattern_quotes({token.token_id: value})

    assert len(runtime._cohort_batches) == 1
    assert runtime._cohort_batches[0][2] == {}
    queue = runtime.runtime_timing.snapshot()["passive_queue"]
    assert queue["enqueued_batches"] == 1
    assert queue["coalesced_quotes"] == 1
    assert queue["normal_takeovers"] == 1
    runtime.store.close()


def test_normal_receipt_is_not_downgraded_and_eviction_clears_index(tmp_path):
    runtime = make_runtime(tmp_path)
    runtime.runtime_timing = RuntimeTiming()
    runtime._cohort_started_at = utcnow()
    first_token = TokenCandidate("solana", "A" * 32, "A", "A")
    first = _quote(first_token, "B" * 32, runtime._cohort_started_at)
    runtime._remember_pattern_quotes({first_token.token_id: first})
    runtime._remember_pattern_quotes(
        {first_token.token_id: first},
        feature_only148={first_token.token_id: "B" * 32},
    )
    assert runtime._cohort_batches[0][2] == {}

    for index in range(1, 17):
        address = chr(65 + index) * 32
        pool = chr(66 + index) * 32
        token = TokenCandidate("solana", address, address, address)
        runtime._remember_pattern_quotes({token.token_id: _quote(
            token, pool, runtime._cohort_started_at,
        )})
    assert len(runtime._cohort_batches) == 16
    before = runtime.runtime_timing.snapshot()["passive_queue"]["enqueued_batches"]
    runtime._remember_pattern_quotes({first_token.token_id: first})
    after = runtime.runtime_timing.snapshot()["passive_queue"]["enqueued_batches"]
    assert after == before + 1
    runtime.store.close()
