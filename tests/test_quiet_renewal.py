from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, utcnow
from memetrader.quiet_renewal import renewal_policies, renewal_signal
from test_runner_capture import frame, runner_quote, PAIR
from test_resource_bound_store import setup_store


def path(start):
    return [frame(start + timedelta(seconds=15 * (i + 1)),
                  price=(1. + .005 * (i % 2)) if i < 13 else (1.10 if i == 13 else 1.12),
                  buys=3 if i < 13 else 9, sells=2 if i < 13 else 6,
                  volume=500 if i < 13 else 1500, pair_age=1200)
            for i in range(15)]


def test_quiet_to_demand_requires_two_breakout_frames():
    start = utcnow()
    history = path(start)
    p = renewal_policies()[0]
    assert renewal_signal(history, p, decision_at=history[-1]["recorded_at"], activated_at=start)[0]
    for key, value in (("price", 1.02), ("buys", 1), ("liquidity", 100)):
        changed = [dict(f) for f in history]
        changed[-2][key] = value
        assert not renewal_signal(changed, p, decision_at=history[-1]["recorded_at"], activated_at=start)[0]


@pytest.mark.parametrize("key,value", [("upstream_provider", "other"), ("pair_address", "other"),
                                      ("ingested_at", "2099-01-01T00:00:00+00:00")])
def test_middle_frame_cannot_hide_identity_or_future_data(key, value):
    start = utcnow()
    history = path(start)
    history[5][key] = value
    assert not renewal_signal(history, renewal_policies()[0],
                              decision_at=history[-1]["recorded_at"], activated_at=start)[0]


def test_registration_and_next_observation_same_fill(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    assert store.register_chain_meme_quiet_renewal() == 2
    assert store.register_chain_meme_quiet_renewal() == 0
    start = clock[0]
    token = TokenCandidate("solana", "RunnerFixture", "Renewal", created_at=start - timedelta(minutes=20))
    history = path(start)
    history.append({**history[-1], "observed_at": (start + timedelta(seconds=240)).isoformat(), "price": 1.13})
    for i, f in enumerate(history):
        clock[0] = start + timedelta(seconds=15 * (i + 1))
        quote = runner_quote(token, PAIR, int(token.created_at.timestamp() * 1000), clock[0], price=f["price"])
        quote.buys_5m, quote.sells_5m, quote.volume_5m_usd = f["buys"], f["sells"], f["volume"]
        pair = quote.raw["pair"]
        pair["txns"]["m5"] = {"buys": f["buys"], "sells": f["sells"]}
        pair["volume"]["m5"] = f["volume"]
        projected = store.observe_chain_meme_pattern(token, quote, recorded_at=clock[0])
        assert projected == (2 if i == 15 else 0)
    rows = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'quiet_renewal_%'").fetchall()
    assert len(rows) == 2
    assert len({r["source_entry_fill_id"] for r in rows}) == 1
    assert all(r["paper_quantity_tokens"] == pytest.approx(5 / 1.13 / 1.04) for r in rows)
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    store.close()
