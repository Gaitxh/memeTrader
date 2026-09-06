from copy import deepcopy
from datetime import timedelta

import pytest

from memetrader.forward_patterns import experiment_policies, pattern_signal
from memetrader.models import TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
from memetrader.research_finalists import finalist_policies, evaluate_finalist_exit
from memetrader.store import Store


def policy(kind):
    return next(p for p in finalist_policies() if p["arm_id"] == f"finalist_{kind}_v1")


def frames(kind):
    prices = {"boundary_retest": [1, 1.01, 1, 1.10, 1.12, 1.11, 1.02, 1.04, 1.09],
              "seller_absorption": [1, .995, .99, .99, .995, 1, 1.02, 1.05, 1.08],
              "price_then_depth": [1, 1, 1, 1.12, 1.13, 1.12, 1.12, 1.125, 1.13]}[kind]
    at = utcnow() + timedelta(seconds=1)
    seq = [dict(token_id="solana:Finalist", pair_address="pool", upstream_provider="dexscreener",
                price=p, liquidity=10000, buys=60, sells=40, volume=2000, pool_age_seconds=3600,
                observed_at=iso(at + timedelta(seconds=15*i)),
                ingested_at=iso(at + timedelta(seconds=15*i)),
                recorded_at=iso(at + timedelta(seconds=15*i))) for i, p in enumerate(prices)]
    if kind == "seller_absorption":
        for f, share in zip(seq, [30, 35, 40, 43, 47, 49, 60, 63, 65]):
            f.update(buys=share, sells=100-share)
    if kind == "price_then_depth":
        for f, liq in zip(seq[-3:], [11500, 11800, 12000]):
            f["liquidity"] = liq
    return seq


def signal(seq, kind, start=None):
    return pattern_signal(seq, policy(kind), decision_at=seq[-1]["recorded_at"],
                          activated_at=start or seq[0]["recorded_at"])[0]


@pytest.mark.parametrize("kind", ["boundary_retest", "seller_absorption", "price_then_depth"])
def test_three_distinct_ordered_entries_and_causal_rejections(kind):
    seq = frames(kind)
    assert signal(seq, kind)
    assert not signal(seq, kind, seq[1]["recorded_at"])
    for field, value in [("liquidity", None), ("liquidity", -1), ("price", float("nan")),
                         ("pair_address", "other"), ("upstream_provider", "gecko")]:
        bad = deepcopy(seq)
        bad[4][field] = value
        assert not signal(bad, kind)
    bad = deepcopy(seq)
    bad[4]["recorded_at"] = iso(parse_time(seq[-1]["recorded_at"]) + timedelta(seconds=1))
    assert not signal(bad, kind)
    assert not signal(seq[:3] + seq[6:], kind)
    assert all(not signal(frames(other), kind) for other in
               ("boundary_retest", "seller_absorption", "price_then_depth") if other != kind)


def test_phase_counterexamples_and_dense_sampling():
    seq = frames("boundary_retest")
    for f, p in zip(seq[-3:], [1.13, 1.14, 1.15]):
        f["price"] = p
    assert not signal(seq, "boundary_retest")  # Never revisited the frozen boundary.
    seq = frames("price_then_depth")
    seq[3]["liquidity"] = 14000
    assert not signal(seq, "price_then_depth")  # Liquidity already led the impulse.
    seq = frames("boundary_retest")
    dense = []
    for f in seq[:-1]:
        dense.append(f)
        extra = deepcopy(f)
        for key in ("observed_at", "ingested_at", "recorded_at"):
            extra[key] = iso(parse_time(f[key]) + timedelta(seconds=1))
        dense.append(extra)
    dense.append(seq[-1])
    assert signal(dense, "boundary_retest")


def exit_input(at, value=5, price=1, liq=10000, buys=60, volume=1000):
    return dict(frame_id=iso(at), observed_at=iso(at), recorded_at=iso(at),
                token_id="solana:Finalist", pair_address="pool", original_pool=True,
                provider="dexscreener", price_usd=price, liquidity_usd=liq,
                economic_value_usd=value, buys=buys, sells=100-buys, volume=volume)


def evaluate(kind, values):
    start = utcnow()
    position = dict(token_id="solana:Finalist", pair_address="pool", stake_usd=5, opened_at=iso(start))
    cfg = policy(kind)["capital_exit_policy"]
    state, outputs = {}, []
    for seconds, changes in values:
        at = start + timedelta(seconds=seconds)
        frame = exit_input(at, **changes)
        before = deepcopy(state)
        result = evaluate_finalist_exit(position, frame, state, now=at, policy=cfg)
        assert state == before
        state = result[2]
        outputs.append(result)
    return outputs


def test_exit_mechanisms_net_profit_clock_divergence_activity():
    out = evaluate("profit_budget", [(10, {"value": 6}), (20, {"value": 5.5}), (30, {"value": 5.49})])
    assert [r[0] for r in out] == ["HOLD", "HOLD", "SELL"]
    assert out[-1][3]["required_fill"] == "next_original_pool_frame"
    out = evaluate("progress_clock", [(s, {"value": 5 + s * .0015}) for s in range(10, 251, 10)])
    assert all(r[0] == "HOLD" for r in out)  # Slow cumulative progress resets the anchor.
    out = evaluate("progress_clock", [(s, {}) for s in range(10, 201, 10)])
    assert out[-2][0] == "SELL"
    out = evaluate("progress_clock", [(10, {}), (190, {}), (200, {})])
    assert all(r[0] == "HOLD" for r in out)  # Missing time is not market stagnation.
    for kind, liqs, buys, volumes in [
        ("depth_divergence", [10000, 10200, 10400], [60]*3, [1000]*3),
        ("activity_failure", [10000]*3, [55, 60, 65], [1000, 1100, 1200]),
    ]:
        values = [(10*(i+1), dict(value=5-.1*i, price=1-.01*i, liq=liqs[i], buys=buys[i], volume=volumes[i]))
                  for i in range(3)]
        assert evaluate(kind, values)[-1][0] == "SELL"
        values[-1] = (200, values[-1][1])
        assert evaluate(kind, values)[-1][0] == "HOLD"


def test_exit_future_duplicate_source_and_account_independence():
    at = utcnow()
    p = dict(token_id="solana:Finalist", pair_address="pool", stake_usd=5, opened_at=iso(at-timedelta(seconds=10)))
    cfg = policy("profit_budget")["capital_exit_policy"]
    f = exit_input(at, value=6)
    first = evaluate_finalist_exit(p, f, now=at, policy=cfg)
    assert evaluate_finalist_exit(p, f, first[2], now=at, policy=cfg)[1] == "duplicate_frame"
    future = {**f, "recorded_at": iso(at+timedelta(seconds=1))}
    assert evaluate_finalist_exit(p, future, now=at, policy=cfg)[0] == "WAIT"
    other = evaluate_finalist_exit({**p, "stake_usd": 10}, f, now=at, policy=cfg)
    assert first[2]["peak_profit"] == 1 and other[2]["peak_profit"] == -4
    for seconds in (10, 20):
        next_at = at + timedelta(seconds=seconds)
        f = {**exit_input(next_at, value=5.4), "provider": "gecko" if seconds == 20 else "dexscreener"}
        first = evaluate_finalist_exit(p, f, first[2], now=next_at, policy=cfg)
    assert first[0] == "HOLD"  # Source transition breaks confirmation streak.


@pytest.mark.parametrize("chain", ["solana", "bsc", "robinhood"])
def test_additive_registry_matched_entries_costs_slots_and_next_frame(tmp_path, monkeypatch, chain):
    now = utcnow()
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.models.utcnow", lambda: now)
    store = Store(tmp_path / "finalists.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    before = store._chain_meme_trader_registration(version)["definition_json"]
    parents = experiment_policies()
    assert store.register_chain_meme_research_finalists() == 8
    assert store.register_chain_meme_research_finalists() == 0
    assert before == store._chain_meme_trader_registration(version)["definition_json"]
    assert parents == experiment_policies()
    assert len({r[0] for r in store.db.execute("SELECT activated_at FROM chain_meme_trader_policy_additions")}) == 1

    def observe(number, liquidity=10000):
        address = "Finalist"+str(number) if chain == "solana" else "0x"+f"{number:040x}"
        pair = "pool"+str(number) if chain == "solana" else "0x"+f"{number+100:040x}"
        token = TokenCandidate(chain, address, "Finalist")
        return store.observe_chain_meme_pattern(token, TokenSnapshot(
            chain, address, 1, liquidity, 100000, 2000, 15, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": chain, "pairAddress": pair,
                "pairCreatedAt": round((now-timedelta(seconds=180)).timestamp()*1000),
                "baseToken": {"address": address}, "priceUsd": "1"}}), recorded_at=now)

    for n in range(1, 6):
        now += timedelta(seconds=16)
        assert observe(n) == 0
        assert observe(n) == 0
        now += timedelta(seconds=16)
        assert observe(n) == (5 if n <= 4 else 0)
    positions = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'finalist_%'").fetchall()
    assert len(positions) == 20
    for n in range(1, 5):
        subset = [r for r in positions if r["token_id"].endswith(str(n))]
        assert len(subset) == 5 and len({r["source_entry_fill_id"] for r in subset}) == 1
    assert all(r["stake_usd"] == 5 and r["paper_quantity_tokens"] == pytest.approx(5/1.04) for r in positions)
    assert all(x == pytest.approx(-20) for x in store._chain_meme_trader_effective_net_flows(version).values())
    store.close()


@pytest.mark.parametrize("chain", ["solana", "bsc"])
def test_matched_exit_store_wires_net_profit_and_preserves_baseline(tmp_path, monkeypatch, chain):
    now = utcnow()
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.models.utcnow", lambda: now)
    store = Store(tmp_path / "exit.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_research_finalists()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    address = "FinalistStore" if chain == "solana" else "0x" + "aB" * 20
    pair = "pool" if chain == "solana" else "0x" + "cD" * 20
    token = TokenCandidate(chain, address, "Fixture")
    created = round((now-timedelta(seconds=180)).timestamp()*1000)

    def snapshot(price=1):
        return TokenSnapshot(chain, token.address, price, 10000, 100000, 2000, 15, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": chain, "pairAddress": pair, "pairCreatedAt": created,
                          "baseToken": {"address": token.address}, "priceUsd": str(price)}})

    now += timedelta(seconds=1)
    assert store.observe_chain_meme_pattern(token, snapshot(), recorded_at=now) == 0
    now += timedelta(seconds=16)
    # One account lacks funds: all five matched arms are rejected, not four fills.
    real_flows = store._chain_meme_trader_effective_net_flows
    monkeypatch.setattr(store, "_chain_meme_trader_effective_net_flows",
                        lambda version: {"finalist_baseline_v1": -999})
    assert store.observe_chain_meme_pattern(token, snapshot(), recorded_at=now) == 0
    import json
    rejected = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1").fetchone()[0])
    assert len(rejected["paired_rejections"]) == 5
    assert set(rejected["paired_rejections"].values()) == {"paired_group_cash_blocked"}
    monkeypatch.setattr(store, "_chain_meme_trader_effective_net_flows", real_flows)
    now += timedelta(seconds=16)
    assert store.observe_chain_meme_pattern(token, snapshot(), recorded_at=now) == 5
    for price in (1.30, 1.19, 1.18):
        now += timedelta(seconds=10)
        store.upsert_chain_meme_trader_market_mark(token, snapshot(price), recorded_at=now)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now, token_ids=[token.token_id])
    candidate = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id='finalist_profit_budget_v1'").fetchone()
    assert candidate["status"] == "open" and candidate["pending_mark_id"] is not None
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE side='SELL'").fetchone()[0] == 0
    now += timedelta(seconds=10)
    store.upsert_chain_meme_trader_market_mark(token, snapshot(1.17), recorded_at=now)
    store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now, token_ids=[token.token_id])
    candidate = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id='finalist_profit_budget_v1'").fetchone()
    baseline = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id='finalist_baseline_v1'").fetchone()
    assert candidate["status"] == "closed" and baseline["status"] == "open"
    assert candidate["realized_proceeds_usd"] == pytest.approx(5/1.04*1.17*.96)
    assert candidate["realized_pnl_usd"] == pytest.approx(5/1.04*1.17*.96-5)
    store.close()


def test_incomplete_exit_frame_breaks_confirmations():
    out = evaluate("depth_divergence", [(10, {}), (20, dict(value=4.9, price=.99, liq=10200)),
        (25, dict(liq=None)), (30, dict(value=4.8, price=.98, liq=10400))])
    assert out[1][2]["bad_streak"] == 1
    assert out[2][0] == "WAIT" and out[2][2]["bad_streak"] == 0
    assert out[-1][0] == "HOLD"


def test_unknown_provider_or_source_transition_does_not_preserve_profit_peak():
    at = utcnow()
    p = dict(token_id="solana:Finalist", pair_address="pool", stake_usd=5, opened_at=iso(at-timedelta(seconds=10)))
    cfg = policy("profit_budget")["capital_exit_policy"]
    state = evaluate_finalist_exit(p, exit_input(at, value=6), now=at, policy=cfg)[2]
    later = at + timedelta(seconds=10)
    f = {**exit_input(later, value=5.4), "provider": None}
    missing = evaluate_finalist_exit(p, f, state, now=later, policy=cfg)
    assert missing[0] == "WAIT" and "accepted" not in missing[2]
    f["provider"] = "gecko"
    changed = evaluate_finalist_exit(p, f, state, now=later, policy=cfg)
    assert changed[2]["peak_profit"] == pytest.approx(.4)


@pytest.mark.parametrize("kind", ["progress_clock", "depth_divergence", "activity_failure"])
def test_other_exits_reach_pending_then_next_observed_sell(tmp_path, monkeypatch, kind):
    from dataclasses import replace
    now = utcnow()
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.models.utcnow", lambda: now)
    store = Store(tmp_path / (kind+".sqlite3"), initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_research_finalists()
    token = TokenCandidate("solana", "Exit"+kind, "Fixture")
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    created = round((now-timedelta(seconds=180)).timestamp()*1000)

    def snap(price=1, liq=10000, buys=55, volume=1000):
        return TokenSnapshot("solana", token.address, price, liq, 100000, volume, buys, 100-buys,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": "solana", "pairAddress": "pool", "pairCreatedAt": created,
                          "baseToken": {"address": token.address}, "priceUsd": str(price)}})

    now += timedelta(seconds=1)
    assert store.observe_chain_meme_pattern(token, snap(), recorded_at=now) == 0
    now += timedelta(seconds=16)
    assert store.observe_chain_meme_pattern(token, snap(), recorded_at=now) == 5
    values = [{}]*7 if kind == "progress_clock" else [
        dict(price=1-.01*i, liq=10000+200*i if kind == "depth_divergence" else 10000,
             buys=55+5*i, volume=1000+100*i) for i in range(3)]
    for values_at_frame in values:
        now += timedelta(seconds=30 if kind == "progress_clock" else 10)
        # Quote has 3s transport latency, used to test the stronger post-decision boundary.
        observation = replace(snap(**values_at_frame), observed_at=now-timedelta(seconds=3))
        store.upsert_chain_meme_trader_market_mark(token, observation, recorded_at=now)
        store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now, token_ids=[token.token_id])
    arm = f"finalist_{kind}_v1"
    get_position = lambda: store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (arm,)).fetchone()
    assert get_position()["pending_mark_id"] is not None and get_position()["status"] == "open"
    trigger_at = now
    now += timedelta(seconds=1)
    early_quote = replace(snap(**values[-1]), observed_at=trigger_at-timedelta(seconds=1))
    store.upsert_chain_meme_trader_market_mark(token, early_quote, recorded_at=now)
    store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now, token_ids=[token.token_id])
    assert get_position()["status"] == "open"  # Received later but observed before trigger: not a fill.
    now += timedelta(seconds=10)
    store.upsert_chain_meme_trader_market_mark(token, snap(**values[-1]), recorded_at=now)
    store.evaluate_chain_meme_trader_market_marks(definition_version=version, now=now, token_ids=[token.token_id])
    assert get_position()["status"] == "closed"
    assert store.db.execute("SELECT status FROM chain_meme_trader_positions WHERE arm_id='finalist_baseline_v1'").fetchone()[0] == "open"
    store.close()


@pytest.mark.parametrize("kind", ["boundary_retest", "seller_absorption", "price_then_depth"])
def test_three_entry_sequences_use_real_store_next_frame(tmp_path, monkeypatch, kind):
    now = utcnow()
    monkeypatch.setattr("memetrader.store.utcnow", lambda: now)
    monkeypatch.setattr("memetrader.models.utcnow", lambda: now)
    store = Store(tmp_path / (kind+".sqlite3"), initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_research_finalists()
    token = TokenCandidate("solana", "Entry"+kind, "Fixture")
    created = round((now-timedelta(hours=1)).timestamp()*1000)

    def observe(f, observed=None):
        return store.observe_chain_meme_pattern(token, TokenSnapshot("solana", token.address,
            f["price"], f["liquidity"], 100000, f["volume"], f["buys"], f["sells"],
            observed_at=observed or now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"chainId": "solana", "pairAddress": "pool", "pairCreatedAt": created,
                          "baseToken": {"address": token.address}, "priceUsd": str(f["price"])}}), recorded_at=now)

    seq = frames(kind)
    for f in seq:
        observed = parse_time(f["observed_at"])
        now = observed + timedelta(seconds=3)
        assert observe(f, observed) == 0
    signal_at = now
    now += timedelta(seconds=1)
    assert observe(seq[-1], signal_at-timedelta(seconds=1)) == 0
    now += timedelta(seconds=16)
    assert observe(seq[-1]) == 1
    rows = store.db.execute("SELECT arm_id FROM chain_meme_trader_positions").fetchall()
    assert [r[0] for r in rows] == [f"finalist_{kind}_v1"]
    store.close()
