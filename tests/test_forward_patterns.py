from datetime import timedelta
import json

import pytest
from solders.pubkey import Pubkey

from memetrader.forward_patterns import experiment_policies, pattern_signal, conditional_fraction
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def policy(direction, control=False):
    return next(p for p in experiment_policies() if p["entry_family"] == direction
                and p["entry_filter"]["control"] == control)


def frames(prices, *, age=1800, step=30):
    now = utcnow()
    return [dict(token_id="solana:test", pair_address="pool", price=price, liquidity=10000,
                 buys=15, sells=5, volume=2000, pool_age_seconds=age,
                 observed_at=iso(now + timedelta(seconds=i * step)),
                 ingested_at=iso(now + timedelta(seconds=i * step)),
                 recorded_at=iso(now + timedelta(seconds=i * step))) for i, price in enumerate(prices)]


def signal(sequence, direction, control=False, **kwargs):
    return pattern_signal(sequence, policy(direction, control),
        decision_at=sequence[-1]["recorded_at"], activated_at=sequence[0]["recorded_at"], **kwargs)[0]


def test_breakout_control_is_not_continuation_and_no_backdated_history():
    f = frames([1, 1.20, 1.15])
    assert signal(f, "sustained_breakout", True)
    assert not signal(f, "sustained_breakout")
    f = frames([1, 1.08, 1.16])
    assert signal(f, "sustained_breakout")
    assert not pattern_signal(f, policy("sustained_breakout"), decision_at=f[-1]["recorded_at"],
                             activated_at=f[-1]["recorded_at"])[0]
    f[1]["pair_address"] = "other-pool"
    assert not signal(f, "sustained_breakout")


def test_reclaim_requires_intermediate_pullback_not_future_peak():
    assert signal(frames([1, 1.20, 1.08, 1.15]), "pullback_reclaim")
    assert not signal(frames([1, 1.08, 1.16, 1.20]), "pullback_reclaim")
    assert signal(frames([1, 1.08, 1.16, 1.20]), "pullback_reclaim", True)


def test_panic_reclaim_needs_recovery_and_retained_liquidity():
    f = frames([1, 0.7, 0.73, 0.78])
    assert signal(f, "panic_reclaim")
    f[1]["liquidity"] = 6000
    assert not signal(f, "panic_reclaim")
    assert signal(f, "panic_reclaim", True)
    assert not signal(frames([1, 0.85, 0.73, 0.7]), "panic_reclaim")


def test_quiet_requires_actual_sequence_not_a_data_gap():
    f = frames([1] * 12 + [1.08, 1.15], age=30000, step=60)
    for item in f[:12]:
        item.update(buys=1, sells=0, volume=20)
    assert signal(f, "quiet_reawakening")
    assert not signal([f[0], *f[-3:]], "quiet_reawakening")
    missing = [dict(item) for item in f]
    missing[1]["buys"] = None
    assert not signal(missing, "quiet_reawakening")


@pytest.mark.parametrize("direction", ["participation", "migration", "narrative", "support_risk"])
def test_richer_directions_never_invent_missing_evidence(direction):
    f = frames([1, 1.1, 1.2], age=90)
    assert not signal(f, direction)
    assert not signal(f, direction, True)


def test_conditional_exit_is_mechanism_not_nearby_tp_parameter():
    strong = [dict(buys=6, sells=4, liquidity=9000)] * 2
    assert conditional_fraction(policy("conditional_runner"), strong, 10000) == .5
    assert conditional_fraction(policy("conditional_runner", True), strong, 10000) == 1
    assert conditional_fraction(policy("conditional_runner"), strong, None) == 1
    assert conditional_fraction(policy("conditional_runner"), strong[:1], 10000) == 1
    hashes = [Store.chain_meme_trader_behavior_hash(p) for p in experiment_policies()]
    assert len(set(hashes)) == 18


@pytest.mark.parametrize("chain", ["solana", "bsc"])
def test_pattern_same_fill_next_observation_cash_and_legacy_isolation(tmp_path, monkeypatch, chain):
    store = Store(tmp_path / "pattern.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    assert store.register_chain_meme_pattern_experiments() == 18
    assert store.register_chain_meme_pattern_experiments() == 0
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    now = utcnow() + timedelta(seconds=1)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    token = TokenCandidate(chain=chain, address=str(Pubkey.new_unique()) if chain == "solana" else "0x" + "12" * 20,
                           name="Pattern", symbol="P", source="test")
    original_pool = "pool" if chain == "solana" else "0x" + "aB" * 20
    store.upsert_token(token, seen_at=now)
    def observe(liquidity=10000, pair_address=original_pool):
        return store.observe_chain_meme_pattern(token, TokenSnapshot(
            chain, token.address, 2, liquidity, 100000, 500, 6, 3,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": chain, "pairAddress": pair_address,
                  "pairCreatedAt": round((now - timedelta(seconds=60)).timestamp() * 1000),
                  "baseToken": {"address": token.address}, "priceUsd": "2"}},
        ), recorded_at=now)
    assert observe() == 0
    now += timedelta(seconds=16)
    assert observe() == 2
    rows = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE definition_version=?", (version,)).fetchall()
    assert len(rows) == 2
    assert len({r["source_entry_fill_id"] for r in rows}) == 1
    assert all(r["paper_quantity_tokens"] == pytest.approx(20 / 2.08) for r in rows)
    assert all("conditional_runner" in r["arm_id"] for r in rows)
    assert store.enroll_chain_meme_trader_v6(definition_version=version)["evaluated"] == 0
    now += timedelta(seconds=16)
    assert observe() == 0
    now += timedelta(seconds=16)
    assert observe(pair_address="new-pool") == 0
    now += timedelta(seconds=16)
    assert observe(liquidity=.48, pair_address="new-pool") == 0
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=?", (version,)).fetchone()[0] == 2
    def mark(price):
        store.upsert_chain_meme_trader_market_mark(token, TokenSnapshot(
            chain, token.address, price, 10000, 100000, 500, 6, 3,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"pairAddress": original_pool}}), recorded_at=now)
        return store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now)
    now += timedelta(seconds=16)
    mark(2.35)  # Independent preceding continuity sample, below TP after costs.
    now += timedelta(seconds=12)
    mark(2.50)
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'").fetchone()[0] == 0
    now += timedelta(seconds=2)
    mark(2.50)
    remaining = {r["arm_id"]: r["remaining_quantity_tokens"] for r in store.db.execute(
        "SELECT arm_id,remaining_quantity_tokens FROM chain_meme_trader_positions WHERE definition_version=?", (version,))}
    assert remaining[policy("conditional_runner")["arm_id"]] == pytest.approx(20 / 2.08 / 2)
    assert remaining[policy("conditional_runner", True)["arm_id"]] == 0
    for trade in store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE side='SELL'"):
        fraction = .5 if trade["arm_id"] == policy("conditional_runner")["arm_id"] else 1
        assert trade["net_cash_flow_usd"] == pytest.approx(20 / 2.08 * fraction * 2.50 * .96)
    store.close()


def test_runtime_reuses_held_quote_and_real_dex_receipt(tmp_path):
    import asyncio
    from memetrader.collectors import DexScreenerClient
    from memetrader.runtime import Runtime
    runtime = Runtime.__new__(Runtime)
    runtime.store = Store(tmp_path / "runtime-pattern.sqlite3", initial_cash_usd=1000)
    runtime.store.activate_chain_meme_trader_funded_period()
    runtime.store.register_chain_meme_pattern_experiments()
    runtime.config = {"paper": {"max_quote_age_seconds": 45}}
    pair = dict(chainId="solana", pairAddress="pool", dexId="pumpswap", priceUsd="2",
                baseToken={"address": str(Pubkey.new_unique()), "symbol": "T"},
                pairCreatedAt=round((utcnow() - timedelta(seconds=60)).timestamp() * 1000),
                liquidity={"usd": 10000}, txns={"m5": {"buys": 6, "sells": 3}}, volume={"m5": 500})
    token, snapshot = DexScreenerClient._candidate(pair), DexScreenerClient._snapshot(pair)
    assert snapshot.ingested_at is None  # Real provider's default, not a hand-filled fixture.
    runtime.store.upsert_token(token)
    runtime._remember_pattern_quotes({token.token_id: (token, snapshot)})
    runtime._pattern_held_tokens = {token.token_id}
    async def forbidden(*args, **kwargs):
        pytest.fail("held observer made a duplicate external request")
    runtime._dex_batch_quote = forbidden
    async def scenario():
        await runtime.chain_meme_pattern_observer_once()
        await runtime.chain_meme_pattern_observer_once()
    asyncio.run(scenario())
    assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_v6_entry_evaluations WHERE reason='pattern_observation'").fetchone()[0] == 1
    runtime.store.close()


def test_mature_watch_leaves_breakout_window_without_renewal_or_extra_slots(monkeypatch):
    from types import SimpleNamespace
    from memetrader.runtime import Runtime
    runtime = Runtime.__new__(Runtime)
    now = utcnow()
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
    quoted = {}
    for i, age in enumerate((60, 30000, 30000, 30000, 30000)):
        token = TokenCandidate("solana", str(Pubkey.new_unique()), str(i), str(i))
        quote = SimpleNamespace(observed_at=now, price_usd=1, raw={
            "pairAddress": f"pool{i}", "pairCreatedAt": int((now-timedelta(seconds=age)).timestamp()*1000)})
        quoted[token.token_id] = token, quote
    runtime._remember_pattern_quotes(quoted)
    assert len(runtime._pattern_watch) == 4  # One early and only three mature slots.
    expires = {k: v["expires_at"] for k, v in runtime._pattern_watch.items()}
    for item in runtime._pattern_watch.values():
        assert item["expires_at"] - now == timedelta(minutes=20 if item["bucket"] == "mature" else 15)
    now += timedelta(minutes=5)
    runtime._remember_pattern_quotes(quoted)
    assert {k: v["expires_at"] for k, v in runtime._pattern_watch.items()} == expires
    now += timedelta(minutes=15, seconds=1)
    runtime._remember_pattern_quotes({})
    assert not runtime._pattern_watch
