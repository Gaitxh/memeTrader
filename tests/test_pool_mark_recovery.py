"""Regression tests for pool-mark recovery after a coverage-gap failure.

Round 89 reproduced a latent defect in `Store.upsert_chain_meme_trader_pool_mark`:

  * `record_chain_meme_trader_pool_mark_failure` INSERTs the row with
    `observed_at = attempted_at` (store.py:32814-32815) -- a WALL clock in a column that otherwise
    carries the provider's DATA time;
  * the recovery only applies `WHERE observed_at IS NULL OR excluded.observed_at > observed_at`
    (store.py:32755-32756);
  * `observed_at` is declared NOT NULL, so the `IS NULL` branch is UNREACHABLE.

When the local clock is coarse the failure stamp and the next real observation are byte-identical, the
strict `>` is false, and the recovery is silently discarded. Measured on this platform: eight
consecutive `datetime.now(UTC)` calls returned ONE distinct value. The public symptom was
`tests/test_market_api_runtime.py::test_first_pool_failure_then_same_pool_quote_side_recovery` failing
at HEAD.

The fix adds one disjunct: a row that has NEVER carried a successful sample (`sample_sequence = 0`)
accepts its first observation regardless of the timestamp comparison. These tests pin BOTH halves --
the new leniency, and the fact that a row which HAS held a real datum keeps the strict newest-wins
rule, so a stale quote still cannot overwrite fresh data.
"""
from __future__ import annotations

from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def _snapshot(token, pool, observed):
    raw = {
        "pair": {
            "chainId": token.chain, "pairAddress": pool,
            "baseToken": {"address": token.address, "name": token.name, "symbol": token.symbol},
            "quoteToken": {"address": "USDC", "name": "USD Coin", "symbol": "USDC"},
            "dexId": "raydium", "priceUsd": "1.25", "liquidity": {"usd": 25_000.0},
            "volume": {"m5": 500.0}, "txns": {"m5": {"buys": 8, "sells": 3}},
            "pairCreatedAt": round((observed - timedelta(minutes=2)).timestamp() * 1000),
        }
    }
    return TokenSnapshot(
        chain=token.chain, address=token.address, provider="dexscreener",
        observed_at=observed, ingested_at=observed, price_usd=1.25, liquidity_usd=25_000.0,
        market_cap_usd=None, volume_5m_usd=500.0, buys_5m=8, sells_5m=3, raw=raw,
    )


def _row(store, token_id, pool):
    return store.db.execute(
        "SELECT status, observed_at, price_usd, sample_sequence, last_success_at "
        "FROM chain_meme_trader_pool_marks WHERE token_id=? AND pair_address=?",
        (token_id, pool)).fetchone()


def _setup(tmp_path):
    store = Store(tmp_path / "pool_marks.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate("robinhood", "0x" + "d5" * 20, "Held QQQ", "QQQ")
    pool = "0x" + "ab" * 32  # a V4 pool id, not a 20-byte token address
    return store, token, pool


def test_first_observation_is_accepted_when_the_failure_stamp_ties(tmp_path):
    """The defect: the failure's attempt clock equals the recovery's data time, byte for byte."""
    store, token, pool = _setup(tmp_path)
    stamp = utcnow()
    store.record_chain_meme_trader_pool_mark_failure(
        token_id=token.token_id, pair_address=pool, chain=token.chain,
        failure_kind="DEX_SOURCE_COVERAGE_GAP", recorded_at=stamp)

    before = _row(store, token.token_id, pool)
    assert before["status"] == "UNKNOWN"
    assert before["sample_sequence"] == 0, "a failed row must not claim a sample"
    assert before["observed_at"] == iso(stamp)

    # The recovery whose DATA time ties the failure stamp exactly -- the coarse-clock case.
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, stamp), recorded_at=stamp,
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)

    after = _row(store, token.token_id, pool)
    assert after["status"] == "VISIBLE"
    assert after["sample_sequence"] == 1
    assert after["price_usd"] == 1.25
    assert after["last_success_at"]


def test_a_row_with_history_keeps_the_strict_newest_wins_rule(tmp_path):
    """The other half: once a row holds a real datum, an older quote must NOT overwrite it."""
    store, token, pool = _setup(tmp_path)
    fresh = utcnow()
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, fresh), recorded_at=fresh,
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)
    good = _row(store, token.token_id, pool)
    assert good["status"] == "VISIBLE" and good["sample_sequence"] == 1

    stale = fresh - timedelta(seconds=30)
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, stale), recorded_at=fresh,
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)

    after = _row(store, token.token_id, pool)
    assert after["observed_at"] == good["observed_at"], "a stale quote advanced the data time"
    assert after["sample_sequence"] == 1, "a stale quote consumed a sample slot"


def test_a_missing_row_with_history_refuses_a_stale_quote(tmp_path):
    """`sample_sequence` is the discriminator, not `status`: a MISSING row that once had data is
    protected, because the miss path does not reset the sequence."""
    store, token, pool = _setup(tmp_path)
    fresh = utcnow()
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, fresh), recorded_at=fresh,
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)
    store.record_chain_meme_trader_pool_mark_miss(
        token_id=token.token_id, pair_address=pool, chain=token.chain, address=token.address,
        recorded_at=fresh + timedelta(seconds=1))
    missing = _row(store, token.token_id, pool)
    assert missing["status"] == "MISSING"
    assert missing["sample_sequence"] == 1

    stale = fresh - timedelta(seconds=30)
    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, stale), recorded_at=fresh + timedelta(seconds=2),
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)
    after = _row(store, token.token_id, pool)
    assert after["observed_at"] == missing["observed_at"]
    assert after["sample_sequence"] == 1


def test_a_missing_row_without_history_does_accept_its_first_quote(tmp_path):
    """A pool first recorded as absent has sequence 0, so its first real quote is a first observation."""
    store, token, pool = _setup(tmp_path)
    stamp = utcnow()
    store.record_chain_meme_trader_pool_mark_miss(
        token_id=token.token_id, pair_address=pool, chain=token.chain, address=token.address,
        recorded_at=stamp)
    assert _row(store, token.token_id, pool)["sample_sequence"] == 0

    store.upsert_chain_meme_trader_pool_mark(
        token, _snapshot(token, pool, stamp), recorded_at=stamp,
        target_token_id=token.token_id, target_chain=token.chain, target_address=token.address)
    after = _row(store, token.token_id, pool)
    assert after["status"] == "VISIBLE" and after["sample_sequence"] == 1
