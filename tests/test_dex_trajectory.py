from datetime import timedelta
from copy import deepcopy
from types import SimpleNamespace
import time
import pytest
from memetrader.models import utcnow, iso, TokenCandidate
from memetrader.dex_trajectory import Engine, derive, mechanisms, exit_reason, VERSION, MAX_POOLS, MAX_FRAMES
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from test_l0_store import _snapshot


def frame(at,i=0,*,token='bsc:0x'+'1'*40,pool='0x'+'2'*40,price=1,liquidity=10000,volume=100):
    return dict(token_id=token,pair_address=pool,chain='bsc',provider='dexscreener',
        observed_at=iso(at),ingested_at=iso(at),recorded_at=iso(at),
        price_usd=price,liquidity_usd=liquidity,volume_5m_usd=volume,volume_1h_usd=1000,
        buys_5m=10+i,sells_5m=2,buys_1h=60,sells_1h=10,fdv_usd=100000,pool_age_seconds=60+i*5)


def test_missing_duplicate_future_pool_and_gap_are_not_new_coverage():
    at=utcnow();e=Engine(at);r=frame(at)
    assert e.accept(r,at)['windows']['5'] is None
    duplicate=dict(r,observed_at=iso(at+timedelta(seconds=5)),ingested_at=iso(at+timedelta(seconds=5)),recorded_at=iso(at+timedelta(seconds=5)))
    assert e.accept(r,at) is None
    assert e.accept(duplicate,at+timedelta(seconds=5))['frames']==2
    assert e.accept(dict(r,ingested_at=None),at) is None
    assert e.accept(dict(r,recorded_at=iso(at+timedelta(seconds=1))),at) is None
    for i in range(1,8):
        t=at+timedelta(seconds=i*5)
        r=frame(t,i,price=1+i*.01);r.update(buys_5m=None,volume_1h_usd=None)
        f=e.accept(r,t)
    assert f['buy_count_share'] is None and f['volume_acceleration_age_normalized'] is None
    assert f['windows']['30']['span_seconds']==30 and f['windows']['60'] is None
    t+=timedelta(seconds=40);f=e.accept(frame(t,20,price=2),t)
    assert f['frames']==1 and f['windows']['30'] is None
    assert not e.signals_for(r['token_id'],r['pair_address'],t)
    f=e.accept(frame(t,20,pool='0x'+'3'*40,price=2),t)
    assert f['frames']==1


def test_fixed_state_mechanisms_are_distinct_and_no_regularity_scam_gate():
    at=utcnow();e=Engine(at)
    for i in range(31):
        t=at+timedelta(seconds=i*5)
        f=e.accept(frame(t,i,price=1+(max(0,i-24)/6)**2*.04,liquidity=10000+max(0,i-24)*20,volume=100+max(0,i-24)*20),t)
    flags=mechanisms(f)
    assert flags['quiet'] and not flags['hot'] and not flags['breakout']
    assert f['base'] is not None and f['signed_flow'] is None and f['independent_wallets'] is None
    assert 'scam' not in f and f['windows']['30']['acceleration']>0
    # Mechanistic metamorphic comparisons, not historical optimized thresholds.
    breakout=deepcopy(f);breakout['windows']['30']['return_fraction']=.12
    assert mechanisms(breakout)['breakout'] and not mechanisms(breakout)['quiet']
    volume=deepcopy(f);volume['windows']['30']['return_fraction']=.01
    volume.update(volume_acceleration_age_normalized=2,tx_acceleration_age_normalized=2)
    assert mechanisms(volume)['volume_leads']


def test_first_dip_requires_observed_recovery_and_retained_liquidity():
    at=utcnow();e=Engine(at)
    prices=[1,1.10,1.30,1.22,1.15,1.20,1.31]
    for i,p in enumerate(prices):
        t=at+timedelta(seconds=i*5);f=e.accept(frame(t,i,price=p,volume=100+i*10),t)
    assert f['first_dip']['recovery_seconds']==10
    assert mechanisms(f)['first_dip']
    bad=deepcopy(f);bad['first_dip']['liquidity_retention']=.5
    assert not mechanisms(bad)['first_dip']


def test_new_contracts_and_post_entry_decay_do_not_touch_parent():
    p={p['arm_id']:p for p in cohort_experiment_policies()}
    assert p['dex_hot_impulse_v1']['feature_contract']==VERSION
    assert p['dex_hot_impulse_v1']['notional_usd']==5 and p['dex_hot_impulse_v1']['take_profit']==[]
    assert p['dex_profit_velocity_exit_v1']['source_arm_ids']==['dex_hot_impulse_v1']
    assert p['cohort_opportunity_router_v1']['max_hold_minutes']==5
    at=utcnow();opened=at-timedelta(seconds=60)
    f=dict(observed_at=iso(at),recorded_at=iso(at),windows={'30':dict(start_at=iso(at-timedelta(seconds=30)),
        log_velocity=-.001,acceleration=-.0001,rolling_volume_change_ratio=.5,liquidity_change_fraction=-.1,return_fraction=-.05)})
    assert exit_reason('velocity',f,iso(opened),at)=='dex_price_activity_liquidity_decay'
    assert exit_reason('velocity',f,iso(at-timedelta(seconds=10)),at) is None
    assert exit_reason('velocity',f,iso(opened),at+timedelta(seconds=16)) is None


def test_actual_hot_producer_common_safety_later_fill_exit_and_dedup(tmp_path,monkeypatch):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    s=Store(tmp_path/'dex.sqlite3',initial_cash_usd=1000);s.activate_chain_meme_trader_funded_period();s.register_chain_meme_cohort_experiments()
    from memetrader.rediscovery_funnel import CohortFlow
    s._cohort_flow=CohortFlow()
    clock[0]+=timedelta(seconds=1);start=clock[0];engine=Engine(start);s._dex_trajectory=engine
    gate=PreentrySafety(s,SimpleNamespace(config={}));s._preentry_safety=gate
    token=TokenCandidate('bsc','0x'+'1'*40,'Hot fixture','HOT');pool='0x'+'2'*40;s.upsert_token(token)
    def current(i):
        clock[0]=start+timedelta(seconds=i*5)
        for j in (3,2,1):
            r=frame(clock[0],i,token='bsc:0x'+str(j)*40,price=1+.004*i*i/j,volume=100+i*30)
            engine.accept(r,clock[0])
        snap=_snapshot(token,pool,clock[0],price=1+.004*i*i)
        snap.volume_5m_usd=100+i*30;snap.buys_5m=10+i;snap.sells_5m=2
        return snap
    for i in range(9):snap=current(i)
    signals=engine.signals_for(token.token_id,pool,clock[0])
    assert 'dex_hot_impulse_v1' in signals
    s.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    snap=current(9);s.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    assert gate.pending and s.db.execute("SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id='dex_hot_impulse_v1'").fetchone()[0]==0
    gate.cache[(token.token_id,pool)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    snap=current(10)
    with s._lock,s.db:gate.resume(token,snap,clock[0])
    positions=[dict(r) for r in s.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'dex_%'")]
    assert len(positions)==4 and len({p['source_entry_fill_id'] for p in positions})==1
    for p in positions:assert p['stake_usd']==5
    snap=current(11);s.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    assert s.db.execute("SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id LIKE 'dex_%'").fetchone()[0]==4
    # Existing hard-stop trigger and genuinely later same-pool settlement.
    for _ in range(2):
        clock[0]+=timedelta(seconds=2)
        s.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pool,clock[0],price=.3),recorded_at=clock[0])
        s.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    assert all(r[0]=='closed' for r in s.db.execute("SELECT status FROM chain_meme_trader_positions WHERE arm_id LIKE 'dex_%'"))
    counts=s._cohort_flow.snapshot()['counts']
    assert counts['BUY']==1 and counts['SAFETY_AUTHORIZED']==1 and counts['TERMINAL_SELL']==1
    assert len(s._cohort_flow.snapshot()['by_arm'])==4
    s.close()


def test_bounded_incremental_work_and_no_io():
    at=utcnow();e=Engine(at);timings=[]
    for i in range(250):
        t=at+timedelta(seconds=i*2);start=time.perf_counter()
        e.accept(frame(t,i,price=1+i*.01,volume=100+i),t);timings.append(time.perf_counter()-start)
    assert max(len(v['rows']) for v in e.pools.values())<=MAX_FRAMES
    assert len(e.pools)<=MAX_POOLS
    assert sorted(timings)[int(len(timings)*.95)]<.02


def test_gap_cancels_frozen_signal_and_exit_variants_share_control_hold():
    at=utcnow();e=Engine(at)
    for i in range(9):
        t=at+timedelta(seconds=i*5)
        for j in (3,2,1):e.accept(frame(t,i,token='bsc:0x'+str(j)*40,price=1+.004*i*i/j,volume=100+i*30),t)
    identity=('bsc:0x'+'1'*40,'0x'+'2'*40)
    assert e.signals_for(*identity,t)
    t+=timedelta(seconds=31);e.accept(frame(t,20,price=3),t)
    assert e.signals_for(*identity,t)=={}
    assert not e.pools[identity]['features']['windows']['30']
    p={p['arm_id']:p for p in cohort_experiment_policies()}
    assert p['dex_profit_velocity_exit_v1']['max_hold_minutes']==p['dex_hot_impulse_v1']['max_hold_minutes']


def test_actual_runtime_uses_real_passive_receipt_for_legacy_dex_objects(tmp_path,monkeypatch):
    import asyncio
    from collections import deque
    from memetrader.runtime import Runtime
    clock=[utcnow()]
    for module in ('runtime','store','models'):monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    s=Store(tmp_path/'clock.sqlite3',initial_cash_usd=1000);s.activate_chain_meme_trader_funded_period()
    r=Runtime.__new__(Runtime);r.store=s;r._cohort_started_at=clock[0];r._cohort_state={}
    r._paper_quote_rejections=lambda *a:[]
    idle=asyncio.Event();idle.set();r._chain_meme_active_idle=lambda:idle
    s._dex_trajectory=Engine(clock[0])
    token=TokenCandidate('bsc','0x'+'1'*40,'Clock','CLK');pool='0x'+'2'*40
    s.upsert_token(token)
    for i in range(9):
        clock[0]+=timedelta(seconds=5)
        snapshot=_snapshot(token,pool,clock[0],price=1+.001*i);snapshot.ingested_at=None
        received=clock[0]+timedelta(milliseconds=10);clock[0]=received
        r._cohort_batches=deque([(received,[(token,snapshot)])])
        asyncio.run(r.chain_meme_cohort_observer_once())
    feature=s._dex_trajectory.pools[(token.token_id,pool)]['features']
    assert feature['windows']['30'] and feature['frames']==9
    assert s._dex_trajectory.pools[(token.token_id,pool)]['rows'][-1]['ingestion_basis']=='passive_queue_receipt'
    assert s._dex_trajectory.pools[(token.token_id,pool)]['rows'][-1]['ingested_at']==iso(received)
    s.close()
