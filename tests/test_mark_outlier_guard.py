"""A dust-liquidity outlier print must not be allowed to price a stop or a trail.

Measured defect being fixed (2026-09-12T00:30:54Z, solana:Xxd7AzFSJK...pump): 1,040 marks
climb smoothly to 0.02963 (+384% over entry), then a single mark eleven seconds later
prints 0.00000192 with liquidity 1,943 against a 461,061 pool, and the trailing exit
filled there for a -100% result.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.store import Store

UTC = timezone.utc


def _token(name="Dust"):
    return TokenCandidate("solana", str(Pubkey.new_unique()), name, name[:4], source="test")


def _snapshot(token, pair, when, *, price=2.0, liquidity=10_000.0, buys=6, sells=3):
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


def _open_positions(tmp_path, monkeypatch, name):
    clock = [datetime.now(UTC) + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / name, initial_cash_usd=1_000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_pattern_experiments()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token, pair = _token(), str(Pubkey.new_unique())
    for _ in range(4):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]), recorded_at=clock[0])
    opened = store.db.execute(
        "SELECT arm_id,entry_execution_price_usd,opened_at FROM chain_meme_trader_positions "
        "WHERE definition_version=? AND token_id=? AND status='open' ORDER BY arm_id",
        (version, token.token_id)).fetchall()
    return store, clock, version, token, pair, opened


def test_dust_outlier_mark_cannot_price_a_stop(tmp_path, monkeypatch):
    store, clock, version, token, pair, opened = _open_positions(tmp_path, monkeypatch, "dust.sqlite3")
    try:
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

        # A normal track first: three comparable earlier marks (needed by the guard).
        # The multiples stay BELOW the lowest take-profit tier of these experiment arms so
        # no tier fires first; liquidity mirrors the real case (a ~450k pool), making 1,943
        # the same dust ratio the live defect showed.
        for offset, multiple in ((0.5, 1.05), (1.0, 1.10), (1.5, 1.15)):
            mark(offset, entry * multiple)

        def statuses():
            return [str(row["status"]) for row in store.db.execute(
                "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
                "AND token_id=?", (version, token.token_id))]

        # The dust print: <=10% of the median price AND <=25% of the median liquidity.
        # It is a -100% "loss" for every arm, so without the guard this books the exit.
        mark(2.0, entry * 0.00004, liquidity=1_943.0)
        mark(2.05, entry * 0.00004, liquidity=1_943.0)
        assert "closed" not in statuses(), "a dust print must not close any position"
        assert getattr(store, "_mark_outlier_vetos", 0) > 0, "the veto must be counted"

        # A genuine collapse (real depth still in the pool) is still exit-eligible.
        mark(3.0, entry * 0.75, liquidity=380_000.0)
        mark(3.05, entry * 0.75, liquidity=380_000.0)
        assert "closed" in statuses(), "a real -25% collapse must still exit"
    finally:
        store.close()


def test_plausibility_helper_fails_open_without_a_reference(tmp_path, monkeypatch):
    store, clock, version, token, pair, opened = _open_positions(tmp_path, monkeypatch, "open.sqlite3")
    try:
        position = {"token_id": token.token_id, "mark_pair_address": pair,
                    "mark_observed_at": None}
        # No earlier marks -> no judgement, previous behaviour stands.
        assert store._mark_is_plausible(position, 1.0, 5_000.0) is True
        # Nonsense input never vetoes either.
        assert store._mark_is_plausible(position, None, None) is True
        assert store._mark_is_plausible(position, "abc", 5_000.0) is True
    finally:
        store.close()
