"""The opt-in anti-whipsaw guards must delay a normal-amplitude stop and change nothing else."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.store import Store

UTC = timezone.utc


def _token(name="Whipsaw"):
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
            "txns": {"m5": {"buys": buys, "sells": sells},
                     "h1": {"buys": buys, "sells": sells}},
            "volume": {"m5": 500.0, "h1": 500.0},
        }},
    )


def test_opt_in_guards_hold_through_a_normal_amplitude_dip(tmp_path, monkeypatch):
    clock = [datetime.now(UTC) + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / "whipsaw.sqlite3", initial_cash_usd=1_000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_pattern_experiments()
        version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        token, pair = _token(), str(Pubkey.new_unique())

        for _ in range(4):
            clock[0] += timedelta(seconds=16)
            store.observe_chain_meme_pattern(
                token, _snapshot(token, pair, clock[0]), recorded_at=clock[0])

        opened = store.db.execute(
            "SELECT arm_id,shadow_cohort_id,entry_execution_price_usd,opened_at "
            "FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=? "
            "AND status='open' ORDER BY arm_id", (version, token.token_id)).fetchall()
        assert len(opened) >= 2, "the pattern lane must open at least two arms"
        entry_price = float(opened[0]["entry_execution_price_usd"])
        guarded = str(opened[0]["arm_id"])
        control = str(opened[1]["arm_id"])

        # Only the first arm opts in: a -20% price dip one minute after entry is a
        # stop for the control arm and normal amplitude for the guarded arm.
        original = store._chain_meme_trader_effective_definition

        def opted_in(definition_version, raw_json):
            definition = original(definition_version, raw_json)
            for policy in definition["policies"]:
                if str(policy.get("arm_id")) == guarded:
                    policy.update(hard_stop_return=-.20, hard_stop_grace_seconds=180,
                                  hard_stop_confirm_marks=2)
            return definition

        monkeypatch.setattr(store, "_chain_meme_trader_effective_definition", opted_in)

        def dip(minutes_after_open, price_multiple=0.8):
            clock[0] = (
                datetime.fromisoformat(opened[0]["opened_at"].replace("Z", "+00:00"))
                + timedelta(minutes=minutes_after_open)
            )
            store.upsert_chain_meme_trader_market_mark(
                token, _snapshot(token, pair, clock[0], price=entry_price * price_multiple),
                recorded_at=clock[0])
            return store.evaluate_chain_meme_trader_market_marks(
                definition_version=version, now=clock[0], token_ids=[token.token_id])

        def status(arm):
            return store.db.execute(
                "SELECT status,close_reason FROM chain_meme_trader_positions "
                "WHERE definition_version=? AND arm_id=? AND token_id=?",
                (version, arm, token.token_id)).fetchone()

        # Exits are two-phase: the first mark is a pending intent, the next
        # independent frame settles it into a fill.
        dip(1.0)
        dip(1.05)
        assert status(control)["status"] == "closed"
        assert str(status(control)["close_reason"]).startswith("market_mark_hard_stop")
        assert status(guarded)["status"] == "open", "the grace period must not stop"

        dip(4.0)   # past the 180s grace: first breach of the confirmation streak
        dip(4.05)  # still inside grace? no - this is the confirming second breach
        assert status(guarded)["status"] == "open", "one breach must not be enough"
        dip(4.10)  # settles the confirmed stop
        dip(4.15)
        assert status(guarded)["status"] == "closed"
        assert str(status(guarded)["close_reason"]).startswith("market_mark_hard_stop")

        # A healthy pool with buy dominance is a dip, not a breakdown: the same
        # breach never confirms while liquidity and buy share stay high.
        streak_store = getattr(store, "_hard_stop_streaks", {})
        assert not store._whipsaw_guard_allows_stop(
            {"hard_stop_liquidity_veto_usd": 3000.0,
             "hard_stop_liquidity_veto_min_buy_share": .5},
            "veto", elapsed_minutes=600.0, liquidity=9_000.0, buys=9, sells=1)
        assert store._whipsaw_guard_allows_stop(
            {"hard_stop_liquidity_veto_usd": 3000.0,
             "hard_stop_liquidity_veto_min_buy_share": .5},
            "veto", elapsed_minutes=600.0, liquidity=900.0, buys=9, sells=1)
        assert store._whipsaw_guard_allows_stop(
            {}, "plain", elapsed_minutes=0.0, liquidity=None, buys=None, sells=None)
        assert streak_store is not None
    finally:
        store.close()


def test_guards_are_inert_for_arms_that_do_not_declare_them(tmp_path, monkeypatch):
    clock = [datetime.now(UTC) + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / "inert.sqlite3", initial_cash_usd=1_000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_pattern_experiments()
        version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        token, pair = _token(), str(Pubkey.new_unique())
        for _ in range(4):
            clock[0] += timedelta(seconds=16)
            store.observe_chain_meme_pattern(
                token, _snapshot(token, pair, clock[0]), recorded_at=clock[0])
        opened = store.db.execute(
            "SELECT arm_id,entry_execution_price_usd,opened_at FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND token_id=? AND status='open' ORDER BY arm_id",
            (version, token.token_id)).fetchall()
        assert opened
        base = datetime.fromisoformat(opened[0]["opened_at"].replace("Z", "+00:00"))
        price = float(opened[0]["entry_execution_price_usd"]) * 0.8
        # No policy declares the new fields, so the streak book stays untouched and
        # the ordinary stop still fires on the first breach.
        for minutes in (1.0, 1.05):
            clock[0] = base + timedelta(minutes=minutes)
            store.upsert_chain_meme_trader_market_mark(
                token, _snapshot(token, pair, clock[0], price=price), recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(
                definition_version=version, now=clock[0], token_ids=[token.token_id])
        closed = store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND token_id=? AND status='closed' AND close_reason LIKE 'market_mark_hard_stop%'",
            (version, token.token_id)).fetchone()[0]
        assert closed >= 1
        assert getattr(store, "_hard_stop_streaks", {}) == {}
    finally:
        store.close()
