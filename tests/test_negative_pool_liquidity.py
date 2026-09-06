from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solders.pubkey import Pubkey

from memetrader.market_api import normalize_gecko_pool
from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.paper_execution import pool_has_trade_liquidity, pool_is_below_floor
from memetrader.store import Store


UTC = timezone.utc


def _token(name="Negative"):
    return TokenCandidate(
        "solana", str(Pubkey.new_unique()), name, name[:4], source="test"
    )


def _snapshot(token, pair, when, *, price=2.0, liquidity=10_000.0):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000.0, 500.0, 6, 3,
        observed_at=when, ingested_at=when, provider="geckoterminal",
        raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "dexId": "pumpswap",
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity},
            "txns": {"m5": {"buys": 6, "sells": 3},
                     "h1": {"buys": 6, "sells": 3}},
            "volume": {"m5": 500.0, "h1": 500.0},
        }},
    )


def _gecko_payload():
    pool = {
        "type": "pool", "id": "bsc_pool-A",
        "attributes": {
            "address": "pool-A", "base_token_price_usd": "0.0123",
            "reserve_in_usd": "-0.854545280417652",
            "volume_usd": {"m5": "500"},
            "transactions": {"m5": {"buys": 6, "sells": 3}},
            "pool_created_at": "2026-09-06T14:00:00Z",
        },
        "relationships": {
            "base_token": {"data": {"type": "token", "id": "bsc_BASE"}},
            "quote_token": {"data": {"type": "token", "id": "bsc_QUOTE"}},
            "dex": {"data": {"type": "dex", "id": "uniswap-v4-bsc"}},
        },
    }
    included = [
        {"type": "token", "id": "bsc_BASE",
         "attributes": {"address": "BASE", "name": "Base", "symbol": "B"}},
        {"type": "token", "id": "bsc_QUOTE",
         "attributes": {"address": "QUOTE", "name": "Quote", "symbol": "Q"}},
        {"type": "dex", "id": "uniswap-v4-bsc", "attributes": {}},
    ]
    return pool, included


def test_negative_liquidity_is_unknown_not_dust_and_raw_gecko_value_is_retained():
    definition = {"min_pool_liquidity_usd": 1_000.0}
    assert not pool_is_below_floor(-0.85, definition)
    assert not pool_has_trade_liquidity(-0.85, definition)
    assert pool_has_trade_liquidity(1_000.0, definition)

    pool, included = _gecko_payload()
    pair = normalize_gecko_pool(
        pool, included, "bsc", datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
    )
    assert pair["liquidity"]["usd"] is None
    assert pair["raw"]["pool"]["attributes"]["reserve_in_usd"] \
        == "-0.854545280417652"


def test_negative_liquidity_cannot_enter_or_exit_until_fresh_positive_frame(
    tmp_path, monkeypatch,
):
    clock = [datetime.now(UTC) + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / "negative-pool.sqlite3", initial_cash_usd=1_000)
    try:
        store.activate_chain_meme_trader_funded_period()
        version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION

        # Main enrollment must reject a known-invalid negative reserve as
        # unknown rather than interpreting it as trade capacity.
        main_token, main_pair = _token("Main"), str(Pubkey.new_unique())
        store.upsert_token(main_token, seen_at=clock[0])
        negative_entry = store.add_snapshot(
            _snapshot(main_token, main_pair, clock[0], liquidity=-0.85)
        )
        store.enroll_chain_meme_trader_v6(definition_version=version)
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND entry_snapshot_id=?",
            (version, negative_entry),
        ).fetchone()[0] == 0
        rejected = store.db.execute(
            "SELECT reason FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? AND source_snapshot_id=?",
            (version, negative_entry),
        ).fetchone()
        assert rejected["reason"] == "entry_pool_liquidity_unknown"

        store.register_chain_meme_pattern_experiments()
        token, pair = _token("Pattern"), str(Pubkey.new_unique())

        def observe(liquidity):
            clock[0] += timedelta(seconds=16)
            return store.observe_chain_meme_pattern(
                token, _snapshot(token, pair, clock[0], liquidity=liquidity),
                recorded_at=clock[0],
            )

        assert observe(10_000) == 0  # READY only.
        assert observe(-0.32) == 0   # Cannot be its post-signal BUY frame.
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND token_id=?",
            (version, token.token_id),
        ).fetchone()[0] == 0
        assert observe(10_000) == 0  # A new valid signal after the bad frame.
        assert observe(10_000) == 2  # Its next independent valid frame fills.

        candidate = "experiment_conditional_runner_candidate_v1"
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=? AND token_id=?",
            (version, candidate, token.token_id),
        ).fetchone()
        assert position is not None and position["status"] == "open"

        # A negative live reserve is neither a SELL fill nor a dust writeoff.
        clock[0] += timedelta(seconds=2)
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pair, clock[0], liquidity=-0.31),
            recorded_at=clock[0],
        )
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=clock[0], token_ids=[token.token_id]
        ) == 0
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
            "AND arm_id=? AND token_id=? AND side IN ('SELL','WRITEOFF')",
            (version, candidate, token.token_id),
        ).fetchone()[0] == 0

        # Once fresh positive liquidity returns, the ordinary retained max-hold
        # path can trigger and the following independent frame can settle.
        opened = datetime.fromisoformat(position["opened_at"].replace("Z", "+00:00"))
        clock[0] = opened + timedelta(minutes=16)
        for _ in range(2):
            store.upsert_chain_meme_trader_market_mark(
                token, _snapshot(token, pair, clock[0], liquidity=10_000),
                recorded_at=clock[0],
            )
            store.evaluate_chain_meme_trader_market_marks(
                definition_version=version, now=clock[0], token_ids=[token.token_id]
            )
            clock[0] += timedelta(seconds=2)
        closed = store.db.execute(
            "SELECT status,close_reason FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=? AND token_id=?",
            (version, candidate, token.token_id),
        ).fetchone()
        assert closed["status"] == "closed"
        assert closed["close_reason"].startswith("market_mark_max_hold")
    finally:
        store.close()
