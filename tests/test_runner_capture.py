import asyncio
from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runner_capture import (
    evaluate_runner_exit,
    post_signal_compatible,
    runner_policies,
    runner_signal,
)
from memetrader.runtime import Runtime, initial_config
from test_resource_bound_store import setup_store


PAIR = "RunnerPool"


def frame(at, *, price=1.0, liq=10_000.0, volume=12_000.0,
          buys=60, sells=40, pc5=20.0, token_age=300.0, pair_age=300.0,
          provider="dexscreener"):
    return {
        "id": int(at.timestamp()),
        "token_id": "solana:RunnerFixture",
        "pair_address": PAIR,
        "price": price,
        "liquidity": liq,
        "volume": volume,
        "volume_h1": volume + 3_000.0,
        "buys": buys,
        "sells": sells,
        "buys_h1": buys + 20,
        "sells_h1": sells + 10,
        "price_change_m5": pc5,
        "price_change_h1": pc5,
        "pool_age_seconds": pair_age,
        "token_age_seconds": token_age,
        "observed_at": at.isoformat(),
        "ingested_at": at.isoformat(),
        "recorded_at": at.isoformat(),
        "upstream_provider": provider,
    }


def policy(control=False):
    arm = "runner_capture_legacy_exit_control_v1" if control else "runner_capture_v1"
    return next(p for p in runner_policies() if p["arm_id"] == arm)


def test_explosive_asof_signal_needs_no_future_path():
    start = utcnow()
    f = frame(start + timedelta(seconds=10))
    passed, reason, evidence = runner_signal(
        [f], policy(), decision_at=f["recorded_at"], activated_at=start.isoformat())
    assert passed and reason == "runner_explosive_ready"
    assert evidence["route"] == "explosive"
    assert evidence["rolling_activity_is_proxy"] is True
    assert evidence["price_change_5m"] == pytest.approx(.20)


def test_persistent_signal_allows_non_monotone_runner_but_rejects_weak_path():
    start = utcnow()
    times = [start + timedelta(seconds=x) for x in (10, 20, 30)]
    history = [
        frame(times[0], price=1.00, pc5=5, volume=5_000),
        frame(times[1], price=.98, pc5=5, volume=5_000),
        frame(times[2], price=1.12, pc5=5, volume=5_000),
    ]
    passed, reason, evidence = runner_signal(
        history, policy(), decision_at=times[-1].isoformat(), activated_at=start.isoformat())
    assert passed and reason == "runner_persistent_ready"
    assert evidence["path_return"] == pytest.approx(.12)
    weak = [dict(x) for x in history]
    weak[-1] = {**weak[-1], "price": 1.02}
    passed, _, _ = runner_signal(
        weak, policy(), decision_at=times[-1].isoformat(), activated_at=start.isoformat())
    assert not passed


def test_successor_pair_is_not_mistaken_for_fresh_runner():
    start = utcnow()
    f = frame(start + timedelta(seconds=10), token_age=1800, pair_age=60)
    passed, reason, _ = runner_signal(
        [f], policy(), decision_at=f["recorded_at"], activated_at=start.isoformat())
    assert not passed
    assert reason == "runner_successor_pair_requires_migration_verification"


def test_fill_requires_next_same_source_frame_and_bounded_drift():
    start = utcnow()
    signal = frame(start + timedelta(seconds=10), price=1.0)
    passed, _, evidence = runner_signal(
        [signal], policy(), decision_at=signal["recorded_at"], activated_at=start.isoformat())
    assert passed
    later = frame(start + timedelta(seconds=20), price=1.2)
    assert post_signal_compatible(later, evidence, policy(), decision_at=later["recorded_at"])
    assert not post_signal_compatible(
        {**later, "price": 1.31}, evidence, policy(), decision_at=later["recorded_at"])
    assert not post_signal_compatible(
        {**later, "upstream_provider": "geckoterminal"}, evidence, policy(),
        decision_at=later["recorded_at"])


def exit_sequence(points):
    p = policy()["capital_exit_policy"]
    start = utcnow()
    position = {
        "token_id": "solana:RunnerFixture",
        "pair_address": PAIR,
        "opened_at": start.isoformat(),
        "stake_usd": 5.0,
    }
    state = {}
    out = []
    for i, point in enumerate(points):
        at = start + timedelta(seconds=6 * (i + 1))
        price = point.get("price", 1.0)
        value = point.get("value", price * 5.0)
        buys = point.get("buys", 60)
        sells = point.get("sells", 40)
        f = {
            "frame_id": str(i),
            "token_id": position["token_id"],
            "pair_address": PAIR,
            "original_pool": True,
            "observed_at": at.isoformat(),
            "recorded_at": at.isoformat(),
            "provider": "dexscreener",
            "price_usd": price,
            "liquidity_usd": point.get("liq", 10_000.0),
            "economic_value_usd": value,
            "buys": buys,
            "sells": sells,
            "volume": point.get("volume", 12_000.0),
        }
        result = evaluate_runner_exit(position, f, state, now=at, policy=p)
        state = result[2]
        out.append(result)
    return out


def test_runner_exit_survives_large_normal_pullback_when_local_volatility_is_high():
    out = exit_sequence([
        {"price": 1.0}, {"price": 1.5}, {"price": 1.32},
        {"price": 1.65}, {"price": 1.38}, {"price": 1.8},
    ])
    assert all(x[0] != "SELL" for x in out)
    assert out[-1][3]["peak_economic_return"] == pytest.approx(.8)


def test_runner_exit_detects_crowded_plateau_before_plain_trailing_stop():
    points = []
    prices = [2.00, 2.02, 2.01, 2.02, 2.01, 2.00]
    for i, price in enumerate(prices):
        total = 100 + i * 5
        share = .66 - i * .025
        buys = round(total * share)
        points.append({"price": price, "buys": buys, "sells": total - buys})
    out = exit_sequence(points)
    assert all(x[0] != "SELL" for x in out[:-1])
    assert out[-1][0] == "SELL"
    assert out[-1][1] == "runner_crowded_plateau_exhaustion"
    assert out[-1][3]["required_fill"] == "next_original_pool_frame"


def test_runner_exit_requires_failed_rebound_or_demand_break_after_drawdown():
    out = exit_sequence([
        {"price": 2.0, "buys": 65, "sells": 35},
        {"price": 1.20, "buys": 48, "sells": 52},
        {"price": 1.36, "buys": 55, "sells": 45},
        {"price": 1.18, "buys": 55, "sells": 45},
    ])
    assert out[1][0] != "SELL"
    assert out[2][0] != "SELL"
    assert out[-1][0] == "SELL"
    assert out[-1][1] == "runner_failed_rebound_second_break"


def test_runner_peak_reclaim_clears_old_warning_before_new_drawdown():
    out = exit_sequence([{"price": p, "value": p / 10}
                         for p in (100, 97, 94, 91, 88, 84, 98, 83)])
    assert out[5][2]["warning"] is not None
    assert out[6][2]["warning"] is None
    assert out[-1][0] != "SELL"
    assert not out[-1][2]["warning"]["bounced"]


@pytest.mark.parametrize("field,value", [("upstream_provider", "other"),
                                        ("liquidity", 0.0)])
def test_persistent_runner_does_not_skip_intervening_market_boundary(field, value):
    start = utcnow()
    history = [frame(start + timedelta(seconds=s), price=p, pc5=0, volume=4000)
               for s, p in ((10, 1.0), (15, 1.02), (20, 1.04), (30, 1.09))]
    history[1][field] = value
    passed, reason, _ = runner_signal(history, policy(),
        decision_at=history[-1]["recorded_at"], activated_at=start)
    assert not passed
    assert reason == "runner_wait_conditions_not_met"


def runner_quote(token, pair, created, at, *, price=1.0):
    buys, sells, volume = 60, 40, 12_000.0
    return TokenSnapshot(
        token.chain, token.address, price, 10_000.0, 100_000.0, volume, buys, sells,
        observed_at=at, ingested_at=at, provider="dexscreener", raw={"pair": {
            "chainId": token.chain,
            "pairAddress": pair,
            "baseToken": {"address": token.address},
            "pairCreatedAt": created,
            "priceUsd": str(price),
            "priceChange": {"m5": 20.0, "h1": 25.0},
            "volume": {"m5": volume, "h1": 15_000.0},
            "txns": {
                "m5": {"buys": buys, "sells": sells},
                "h1": {"buys": 80, "sells": 50},
            },
        }},
    )


def test_runtime_startup_registers_runner_pair_at_own_frontier(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        runtime = Runtime(config, tmp_path)
        rows = runtime.store.db.execute(
            "SELECT arm_id,activated_at,activation_snapshot_id,activation_evaluation_id "
            "FROM chain_meme_trader_policy_additions WHERE arm_id LIKE 'runner_capture_%' "
            "ORDER BY arm_id").fetchall()
        assert [r["arm_id"] for r in rows] == [
            "runner_capture_legacy_exit_control_v1", "runner_capture_v1"]
        assert len({r["activated_at"] for r in rows}) == 1
        assert all(r["activation_snapshot_id"] >= 0 for r in rows)
        assert all(r["activation_evaluation_id"] >= 0 for r in rows)
        assert runtime.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_policy_additions "
            "WHERE arm_id LIKE 'runner_ultra_early_%'").fetchone()[0] == 2
        assert runtime.store.register_chain_meme_ultra_early_runner() == 0
        await runtime.close()
    asyncio.run(scenario())


def test_store_registers_same_fill_runner_pair_without_mutating_epoch(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    store.activate_chain_paper_execution({
        "buy_slippage_pct": 4, "sell_slippage_pct": 4,
        "additional_fee_usd_each_fill": .1, "min_pool_liquidity_usd": 1000,
    }, activated_at=clock[0])
    assert store.register_chain_meme_runner_capture() == 2
    assert store.register_chain_meme_runner_capture() == 0
    token = TokenCandidate(
        "solana", "RunnerFixture", "Runner", created_at=clock[0] - timedelta(minutes=5))
    created = int(token.created_at.timestamp() * 1000)
    for i, price in enumerate((1.0, 1.05)):
        clock[0] += timedelta(seconds=16)
        projected = store.observe_chain_meme_pattern(
            token, runner_quote(token, PAIR, created, clock[0], price=price), recorded_at=clock[0])
        assert projected == (0 if i == 0 else 2)
    rows = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'runner_capture_%' "
        "ORDER BY arm_id").fetchall()
    assert len(rows) == 2
    assert len({r["source_entry_fill_id"] for r in rows}) == 1
    assert len({r["opened_at"] for r in rows}) == 1
    assert all(r["paper_quantity_tokens"] == pytest.approx(5 / 1.05 / 1.04) for r in rows)
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    store.close()
