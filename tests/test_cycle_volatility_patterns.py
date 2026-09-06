from copy import deepcopy
from datetime import timedelta

import pytest

from memetrader.forward_patterns import cycle_and_volatility_policies, experiment_policies, pattern_signal
from memetrader.models import TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
from memetrader.store import Store


def _frames(prices, step=30):
    start = utcnow() + timedelta(seconds=1)
    return [dict(token_id="solana:CycleMint", pair_address="pool", price=price,
                 liquidity=10000, buys=15, sells=5, volume=2000, pool_age_seconds=3600,
                 observed_at=iso(start + timedelta(seconds=i * step)),
                 ingested_at=iso(start + timedelta(seconds=i * step)),
                 recorded_at=iso(start + timedelta(seconds=i * step))) for i, price in enumerate(prices)]


def _policy(direction, control=False):
    return next(p for p in cycle_and_volatility_policies()
                if p["entry_family"] == direction and p["entry_filter"]["control"] == control)


def _signal(frames, direction, control=False, **kwargs):
    return pattern_signal(frames, _policy(direction, control), decision_at=frames[-1]["recorded_at"],
                          activated_at=kwargs.get("activated_at", frames[0]["recorded_at"]))[0]


def test_observed_cycle_requires_ordered_wave_deep_reset_and_quiet_base():
    seq = _frames([1, 1.05, 1.10, 1.3, 1.5, 1.45, 1.30, 1.05, 1.0] + [1.01] * 15 + [1.18])
    for frame in seq[10:23]:
        frame["volume"] = 500
    assert _signal(seq, "cycle_reset")
    assert _signal(seq, "cycle_reset", True)
    no_wave = deepcopy(seq)
    for frame in no_wave[:9]:
        frame["price"] = 1.0
    assert not _signal(no_wave, "cycle_reset")
    assert _signal(no_wave, "cycle_reset", True)
    gap = [seq[0], *seq[4:]]
    assert not _signal(gap, "cycle_reset")
    assert not _signal(seq, "cycle_reset", activated_at=seq[9]["recorded_at"])


def test_volatility_treatment_differs_from_fixed_return_control():
    seq = _frames([1, 1.001, .999, 1.002, 1, 1.001, 1, 1.02, 1.06])
    assert _signal(seq, "volatility_flow")
    assert not _signal(seq, "volatility_flow", True)  # 6% impulse: below fixed 8% control.
    noisy = _frames([1, 1.10, .94, 1.06, .95, 1.08, 1, 1.04, 1.09])
    assert not _signal(noisy, "volatility_flow")
    assert _signal(noisy, "volatility_flow", True)
    bad = deepcopy(seq)
    bad[-1]["liquidity"] = 7000
    assert not _signal(bad, "volatility_flow")
    bad = deepcopy(seq)
    bad[-2]["recorded_at"] = iso(parse_time(seq[-1]["recorded_at"]) + timedelta(seconds=1))
    assert not _signal(bad, "volatility_flow")
    bad = deepcopy(seq)
    bad[-2]["pair_address"] = "other-pool"
    assert not _signal(bad, "volatility_flow")
    bad = deepcopy(seq)
    bad[-1]["liquidity"] = .9
    assert not _signal(bad, "volatility_flow")


@pytest.mark.parametrize("chain,post_liquidity,expected_buys", [
    ("solana", 1000, 2), ("bsc", 1000, 2), ("robinhood", 1000, 2),
    ("solana", 999, 0), ("solana", None, 0),
])
def test_new_arms_preserve_registry_and_use_next_frame_five_dollar_fills(tmp_path, monkeypatch, chain, post_liquidity, expected_buys):
    store = Store(tmp_path / "patterns.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    activation = tuple(store.db.execute("SELECT * FROM chain_meme_trader_v6_activations WHERE definition_version=?", (version,)).fetchone())
    parents = experiment_policies()
    assert store.register_chain_meme_cycle_volatility_experiments() == 4
    assert store.register_chain_meme_cycle_volatility_experiments() == 0
    assert experiment_policies() == parents and len(parents) == 18
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    assert tuple(store.db.execute("SELECT * FROM chain_meme_trader_v6_activations WHERE definition_version=?", (version,)).fetchone()) == activation
    assert len({r[0] for r in store.db.execute("SELECT activated_at FROM chain_meme_trader_policy_additions")}) == 1
    seq = _frames([1, 1.001, .999, 1.002, 1, 1.001, 1, 1.04, 1.09])
    now = parse_time(seq[0]["observed_at"])
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    address = "CycleMint" if chain == "solana" else "0x" + "12" * 20
    pool = "pool" if chain == "solana" else "0x" + "ab" * 20
    token = TokenCandidate(chain, address, "Cycle")
    created = round((now - timedelta(hours=1)).timestamp() * 1000)

    def observe(price, liquidity=10000):
        return store.observe_chain_meme_pattern(token, TokenSnapshot(
            chain, address, price, liquidity, 100000, 2000, 15, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": chain, "pairAddress": pool, "pairCreatedAt": created,
                          "baseToken": {"address": address}, "priceUsd": str(price)}},
        ), recorded_at=now)

    for frame in seq:
        now = parse_time(frame["observed_at"])
        assert observe(frame["price"]) == 0  # Signal frame is not a fill.
    assert observe(seq[-1]["price"]) == 0  # Same observed timestamp is not confirmation.
    now += timedelta(seconds=16)
    assert observe(1.1, post_liquidity) == expected_buys
    positions = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE definition_version=?", (version,)).fetchall()
    if not expected_buys:
        assert not positions
        store.close()
        return
    assert len(positions) == 2 and len({r["source_entry_fill_id"] for r in positions}) == 1
    assert len({r["arm_id"] for r in positions}) == 2
    assert all(r["paper_quantity_tokens"] == pytest.approx(5 / (1.1 * 1.04)) for r in positions)
    assert all(value == pytest.approx(-5) for value in store._chain_meme_trader_effective_net_flows(version).values())
    store.close()


@pytest.mark.parametrize("liquidity", [999, None])
def test_pattern_signal_shared_floor_rejects_low_and_missing_liquidity(liquidity):
    seq = _frames([1, 1.001, .999, 1.002, 1, 1.001, 1, 1.02, 1.06])
    seq[-1]["liquidity"] = liquidity
    accepted, reason = pattern_signal(seq, _policy("volatility_flow"),
        decision_at=seq[-1]["recorded_at"], activated_at=seq[0]["recorded_at"])
    assert not accepted
    assert reason == ("entry_pool_liquidity_unknown" if liquidity is None
                      else "entry_pool_liquidity_below_1000_usd")
