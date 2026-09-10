from datetime import timedelta
import json
from memetrader.models import utcnow, iso
from memetrader.trajectory144 import Engine, ARMS, policies, trend_extension, short_fast_failure_exit


def row(at, i, *, token="bsc:0x1111111111111111111111111111111111111111", pool="0x2222222222222222222222222222222222222222", price=1, buys=10, sells=10, volume=100, chain="bsc"):
    return {"token_id": token, "pair_address": pool, "chain":chain, "provider":"dexscreener", "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
            "price_usd": price, "liquidity_usd": 10000, "volume_5m_usd": volume+i*20, "buys_5m": buys+i, "sells_5m": sells,
            "pool_age_seconds": 30+i*10}


def test_actual_window_early_degenerate_and_causality():
    at=utcnow(); e=Engine(at)
    for i in range(4): f=e.accept(row(at+timedelta(seconds=i*10),i,price=1+i*.04,buys=i*i,volume=100+i*i*20),at+timedelta(seconds=i*10))
    assert f["window_30"]["span_seconds"] == 30 and f["early_m5_h1_degenerate"]
    assert ARMS[0] in e.signals_for(row(at,0)["token_id"],row(at,0)["pair_address"],at+timedelta(seconds=30))
    future=row(at+timedelta(seconds=40),4,price=2); assert e.accept(future,at+timedelta(seconds=30)) is None


def test_missing_window_and_sparse_peer_are_explicit():
    at=utcnow(); e=Engine(at)
    for i in range(4): e.accept(row(at+timedelta(seconds=i*10),i,price=1+i*.04),at+timedelta(seconds=i*10))
    s=e.signals_for(row(at,0)["token_id"],row(at,0)["pair_address"],at+timedelta(seconds=30)); assert s[ARMS[1]]["decision_evidence"]["sparse_peer_mode"]
    g=Engine(at); g.accept(row(at,0),at); g.accept(row(at+timedelta(seconds=70),1,price=2),at+timedelta(seconds=70)); assert not g.signals_for(row(at,0)["token_id"],row(at,0)["pair_address"],at+timedelta(seconds=70))


def test_policy_size_and_restart_payload_are_bounded():
    at=utcnow(); e=Engine(at); e.accept(row(at,0),at); payload=e.state_payload(); json.dumps(payload); restored=Engine(at); assert restored.load_state(payload)
    ps=policies({}); assert len(ps)==6 and all(p["notional_usd"]==2 and p["entry_filter"]["max_concurrent_positions"]==2 for p in ps)
    runner=next(p for p in ps if p["arm_id"]==ARMS[3]); assert runner["entry_alias_of"]==ARMS[0] and runner["trend_max_hold_minutes"]==120


def test_fresh_trend_extension_and_fast_failure_are_causal():
    at=utcnow(); e=Engine(at)
    for i in range(31): f=e.accept(row(at+timedelta(seconds=i*10),i,price=1+i*.04),at+timedelta(seconds=i*10))
    assert trend_extension(f,at,at+timedelta(seconds=300))
    assert not trend_extension(f,at,at+timedelta(seconds=331))
    f["window_30"].update(return_fraction=-.1,activity_change=.5,liquidity_change=.9)
    assert short_fast_failure_exit(f,at,at+timedelta(seconds=300))


def test_jittered_window_peer_chain_and_exact_trend_alias():
    at=utcnow(); e=Engine(at); times=(0, 12, 32, 52)
    for i, second in enumerate(times): e.accept(row(at+timedelta(seconds=second),i,price=1+i*.05,buys=i*i,volume=100+i*i*20),at+timedelta(seconds=second))
    token, pool=row(at,0)["token_id"],row(at,0)["pair_address"]
    f=e.pools[(token,pool)]["features"]; assert f["window_30"]["span_seconds"] == 40
    # A fresh other-chain trajectory cannot become this BSC pool's rank peer.
    other="So11111111111111111111111111111111111111112"
    for i, second in enumerate(times): e.accept(row(at+timedelta(seconds=second),i,token="solana:"+other,pool="So11111111111111111111111111111111111111112",chain="solana",price=1+i*.05),at+timedelta(seconds=second))
    signals=e.signals_for(token,pool,at+timedelta(seconds=52)); assert signals[ARMS[1]]["decision_evidence"]["peer_count"] == 1
    assert signals[ARMS[3]]["decision_key"] == signals[ARMS[0]]["decision_key"]


def test_ordered_second_wave_and_restart_json_payload():
    at=utcnow(); e=Engine(at); prices=[1,1.05,1.1,1.2,.9,.91,.9,.91,.9,.91,.9,.91,.9,.91,1,1.1,1.2]
    for i, price in enumerate(prices):
        now=at+timedelta(seconds=i*10); e.accept(row(now,i,price=price,buys=i*i,volume=100+i*i*20),now)
    token,pool=row(at,0)["token_id"],row(at,0)["pair_address"]
    assert ARMS[4] in e.signals_for(token,pool,at+timedelta(seconds=160))
    payload=e.state_payload(); json.dumps(payload); restored=Engine(at); assert restored.load_state(payload)
    assert restored.signals_for(token,pool,at+timedelta(seconds=160))[ARMS[4]]["decision_key"] == e.signals_for(token,pool,at+timedelta(seconds=160))[ARMS[4]]["decision_key"]


def test_absorption_needs_real_dip_not_monotonic_path():
    at=utcnow(); e=Engine(at)
    for i, price in enumerate((1,1.05,1.1,1.15,1.2)): e.accept(row(at+timedelta(seconds=i*10),i,price=price),at+timedelta(seconds=i*10))
    assert not e.pools[(row(at,0)["token_id"],row(at,0)["pair_address"])]["features"]["absorption_recovery"]
