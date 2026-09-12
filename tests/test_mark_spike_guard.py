"""The mark guard must also reject UPWARD provider/scale artifacts.

Measured by the independent washout review: 913 of 25,408 positions carried a single
mark-to-market jump above 3x (max 1.3e7x); one token printed 0.000403 -> 0.402 in fifteen
seconds. Without a guard the delayed-exit total read $21.7k instead of $2.57k. Upward
artifacts are the more dangerous direction because they manufacture profit and are then
consumed by the take-profit layer.

Same scaffolding as tests/test_mark_outlier_guard.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.store import Store

UTC = timezone.utc


def _token(name="Spike"):
    return TokenCandidate("solana", str(Pubkey.new_unique()), name, name[:4], source="test")


def _snapshot(token, pair, when, *, price=2.0, liquidity=450_000.0, buys=6, sells=3):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000.0, 500.0, buys, sells,
        observed_at=when, ingested_at=when, provider="geckoterminal",
        raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "dexId": "pumpswap",
            "pairCreatedAt": round((when - timedelta(seconds=60)).timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity},
            "txns": {"m5": {"buys": buys, "sells": sells}, "h1": {"buys": buys, "sells": sells}},
            "volume": {"m5": 500.0, "h1": 500.0},
        }},
    )


def test_upward_scale_artifact_cannot_price_a_take_profit(tmp_path, monkeypatch):
    clock = [datetime.now(UTC) + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / "spike.sqlite3", initial_cash_usd=1_000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_pattern_experiments()
        version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        token, pair = _token(), str(Pubkey.new_unique())
        for _ in range(4):
            clock[0] += timedelta(seconds=16)
            store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]), recorded_at=clock[0])
        opened = store.db.execute(
            "SELECT arm_id, entry_execution_price_usd, opened_at FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND token_id=? AND status='open' ORDER BY arm_id",
            (version, token.token_id)).fetchall()
        assert opened, "the pattern lane must open at least one arm"
        entry = float(opened[0]["entry_execution_price_usd"])
        base = datetime.fromisoformat(opened[0]["opened_at"].replace("Z", "+00:00"))

        def mark(minutes, price, liquidity=450_000.0):
            clock[0] = base + timedelta(minutes=minutes)
            store.upsert_chain_meme_trader_market_mark(
                token, _snapshot(token, pair, clock[0], price=price, liquidity=liquidity),
                recorded_at=clock[0])
            return store.evaluate_chain_meme_trader_market_marks(
                definition_version=version, now=clock[0], token_ids=[token.token_id])

        def statuses():
            return [str(row["status"]) for row in store.db.execute(
                "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
                "AND token_id=?", (version, token.token_id))]

        # A calm track: three comparable earlier marks (the guard needs three references).
        for offset, multiple in ((0.5, 1.02), (1.0, 1.04), (1.5, 1.06)):
            mark(offset, entry * multiple)

        # The artifact: 40x the pool's own track while depth is unchanged. Every arm's
        # take-profit tier (+20% for these experiment arms) would fire on it.
        mark(2.0, entry * 40.0, liquidity=460_000.0)
        mark(2.05, entry * 40.0, liquidity=460_000.0)
        assert "closed" not in statuses(), "an upward scale artifact must not close a position"
        assert getattr(store, "_mark_outlier_vetos", 0) > 0, "the veto must be counted"

        # A genuine rise with real depth behind it is still tradeable: the guard must not
        # block ordinary profitable exits.
        mark(3.0, entry * 1.30, liquidity=520_000.0)
        mark(3.05, entry * 1.30, liquidity=520_000.0)
        assert "closed" in statuses(), "a real +30% move with depth must still exit normally"
    finally:
        store.close()
