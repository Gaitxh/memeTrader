from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime


def _runtime():
    runtime = Runtime.__new__(Runtime)
    runtime.chain_meme_trader_only = True
    runtime._chain_paper_execution = {"min_pool_liquidity_usd": 1000.0}
    runtime._held_pool_quote_rejections = lambda *args: []
    return runtime


def _snapshot(now, *, age_minutes, dex_id="fourmeme", trades=3, price=0.0, liquidity=0.0):
    token = TokenCandidate("bsc", "0x" + "a" * 40, "Curve")
    born = now - timedelta(minutes=age_minutes)
    snapshot = TokenSnapshot(
        token.chain,
        token.address,
        price,
        liquidity,
        0.0,
        0.0,
        trades,
        0,
        observed_at=now,
        ingested_at=now,
        raw={
            "pair": {
                "chainId": token.chain,
                "dexId": dex_id,
                "pairAddress": "0x" + "b" * 40,
                "pairCreatedAt": int(born.timestamp() * 1000),
                "txns": {"m5": {"buys": trades, "sells": 0}},
            }
        },
    )
    return token, snapshot, born


def test_active_curve_reuses_followup_capacity_without_becoming_tradable(monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    token, snapshot, born = _snapshot(now, age_minutes=20)

    schedule = _runtime()._shared_market_followup_schedule(token, snapshot)

    assert schedule["refresh_at"] == now + timedelta(minutes=5)
    assert abs(
        (schedule["followup_until"] - born - timedelta(hours=6)).total_seconds()
    ) < 0.001


def test_curve_prefilter_rejects_inactive_surface_and_tapers_mature_activity(monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    runtime = _runtime()
    inactive_token, inactive, _ = _snapshot(now, age_minutes=20, trades=2)
    active_token, mature, _ = _snapshot(now, age_minutes=120, trades=8)

    assert runtime._shared_market_followup_schedule(inactive_token, inactive) == {}
    assert runtime._shared_market_followup_schedule(active_token, mature)[
        "refresh_at"
    ] == now + timedelta(minutes=15)


def test_migrated_amm_uses_ordinary_early_pool_cadence(monkeypatch):
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    token, snapshot, _ = _snapshot(
        now,
        age_minutes=20,
        dex_id="pancakeswap",
        trades=8,
        price=0.001,
        liquidity=20_000.0,
    )

    assert _runtime()._shared_market_followup_schedule(token, snapshot)[
        "refresh_at"
    ] == now + timedelta(minutes=1)
