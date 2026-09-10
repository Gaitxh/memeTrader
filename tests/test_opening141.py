import asyncio
from collections import deque
from datetime import timedelta
from types import SimpleNamespace

import pytest

from memetrader.cohort_experiments import REGIME_ARM, cohort_experiment_policies, regime_route
from memetrader.cohort_enrollment import open_or_reserved_full
from memetrader.models import iso, utcnow
from memetrader.runtime import Runtime
from test_cohort_router138 import _signal
from test_l0_store import _snapshot
from test_strategy_delivery137 import setup
from test_synthetic_harvest136 import TOKEN, POOL


@pytest.mark.parametrize('delay', [20, 61])
def test_busy_pending_merge_keeps_frozen_clocks_but_never_renews_expiry(tmp_path, monkeypatch, delay):
    clock,store,token,_=setup(tmp_path,monkeypatch)
    monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock[0])
    runtime=Runtime.__new__(Runtime);runtime.store=store
    runtime._cohort_started_at=clock[0];runtime._cohort_state={}
    runtime._paper_quote_rejections=lambda *a:[]
    idle=asyncio.Event();runtime._chain_meme_active_idle=lambda:idle
    calls=[];signal=_signal('one_shot',clock[0],'once')
    def consume(frames,state,**kwargs):
        arm='one_shot' if not calls else 'different_arm'
        calls.append(arm)
        return state,{(TOKEN,POOL):{arm:signal if arm=='one_shot' else _signal(arm,clock[0],'other')}}
    monkeypatch.setattr('memetrader.cohort_experiments.consume_passive_cohort_batch',consume)
    projected=[]
    monkeypatch.setattr(store,'observe_chain_meme_pattern',lambda *a,**kw:projected.append(kw) or 0)
    async def run():
        runtime._cohort_batches=deque([(clock[0],[(token,_snapshot(token,POOL,clock[0]))])])
        await runtime.chain_meme_cohort_observer_once()
        assert projected==[]
        clock[0]+=timedelta(seconds=delay);idle.set()
        runtime._cohort_batches=deque([(clock[0],[(token,_snapshot(token,POOL,clock[0]))])])
        await runtime.chain_meme_cohort_observer_once()
        result=projected[-1]['cohort_signals']
        assert 'different_arm' in result
        assert ('one_shot' in result)==(delay<=60)
        if delay<=60:assert result['one_shot']==signal
    asyncio.run(run());store.close()


def test_regime_priority_and_synthetic_scope_are_explicit():
    now=utcnow()
    signals={s:_signal(s,now,s) for s in ('organic_reawakening_flow_v1','dex_hot_impulse_v1')}
    selected,audit=regime_route(signals)
    assert audit['state']=='REAWAKENING'
    assert audit['branches']['NEW_HOT']=='AVAILABLE_LOWER_PRIORITY'
    assert selected['decision_evidence']['router_source_origin_at']==iso(now)
    assert selected['decision_key'].endswith('|'+REGIME_ARM)
    for phase in ('SYNTHETIC_LPI_BUILDING_CANDIDATE','SYNTHETIC_LPI_BUILDING','SYNTHETIC_DISTRIBUTING_CYCLE'):
        assert regime_route(signals,{'phase':phase})[0] is None
    assert regime_route(signals,{'state':'HARD_UNSELLABLE'})[0] is None
    assert regime_route({})[1]['state']=='UNKNOWN'
    policy=next(p for p in cohort_experiment_policies() if p['arm_id']==REGIME_ARM)
    assert policy['notional_usd']==5 and policy['entry_filter']['max_concurrent_positions']==2
    assert 'narrative_hold_v2' not in policy['entry_filter']
    assert policy['dynamic_principal_recovery']=='minimum_net_debit_keep_half_next_frame/v3'


def test_signal_denominator_separates_consumed_keys_from_buy_cohorts():
    from memetrader.rediscovery_funnel import CohortFlow
    flow=CohortFlow();now=utcnow()
    for _ in range(3):
        flow.opportunity('v','a','old','signal_received',now)
        flow.opportunity('v','a','old','cohort_event_consumed_or_position_open',now)
    snapshot=flow.snapshot()
    assert snapshot['counts']=={}
    assert snapshot['signal_opportunities']['counts']=={'signal_received':1,'cohort_event_consumed_or_position_open':1}
    for n in range(1025):flow.opportunity('v','a',str(n),'signal_received',now)
    assert flow.snapshot()['signal_opportunities']['retained']==1024
    assert flow.snapshot()['signal_opportunities']['evicted']==2


@pytest.mark.parametrize('recover',[False,True])
def test_actual_common_buy_partial_settlement_and_conditional_runner(tmp_path,monkeypatch,recover):
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    clock[0]+=timedelta(seconds=1)
    source='organic_reawakening_flow_v1';signals={source:_signal(source,clock[0],'new-reawakening')}
    for _ in range(2):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals=signals)
        clock[0]+=timedelta(seconds=1)
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(REGIME_ARM,)).fetchone()[0]==0
    gate.cache[(TOKEN,POOL)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    def position():return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(REGIME_ARM,)).fetchone()
    assert position() and position()['stake_usd']==5
    initial=int(position()['amount_raw'])
    policy=next(p for p in cohort_experiment_policies() if p['arm_id']==REGIME_ARM)
    def mark(price,seconds=1):
        clock[0]+=timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=price),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN])
    if recover:
        mark(6)
        assert position()['principal_recovered']==0
        assert store._cohort_router_exit_policy(policy,position())['max_hold_minutes']==15
        mark(6)
        assert position()['principal_recovered']==1 and position()['realized_proceeds_usd']>=5
        assert int(position()['amount_raw'])>=initial/2
        assert store._cohort_router_exit_policy(policy,position())['max_hold_minutes']==60
    mark(6 if recover else 1,901);mark(6 if recover else 1)
    assert position()['status']==('open' if recover else 'closed')
    if recover:
        mark(.3);mark(.3)
        assert position()['status']=='closed'  # hard/trailing dominates runner
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(REGIME_ARM,)).fetchone()[0]==1
    store.close()


def test_pending_reservations_count_toward_two_slots(tmp_path,monkeypatch):
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    for n in range(3):
        from memetrader.models import TokenCandidate
        token=TokenCandidate('bsc','0x'+str(n+3)*40,'Capacity','CAP');store.upsert_token(token)
        clock[0]+=timedelta(seconds=1)
        sig=_signal('organic_early_flow_v1',clock[0],str(n));sig['selected']['token_id']=token.token_id
        for _ in range(2):
            store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals={'organic_early_flow_v1':sig})
            clock[0]+=timedelta(seconds=1)
    rows=list(store.db.execute('SELECT cohort_id FROM chain_meme_cohort_enrollment_claims WHERE arm_id=?',(REGIME_ARM,)))
    assert len(rows)==2
    assert open_or_reserved_full(store.db,version,REGIME_ARM,2)
    assert not open_or_reserved_full(store.db,version,REGIME_ARM,2,rows[0][0])
    store.close()


def test_pre_activation_source_and_later_distribution_do_not_authorize_router(tmp_path,monkeypatch):
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    source='organic_early_flow_v1';old=clock[0]-timedelta(seconds=1)
    clock[0]+=timedelta(seconds=1);sig=_signal(source,clock[0],'new')
    sig['decision_evidence']['signal_at']=iso(old)
    store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals={source:sig})
    assert not store.db.execute('SELECT 1 FROM chain_meme_trader_entry_decisions WHERE arm_id=?',(REGIME_ARM,)).fetchone()
    clock[0]+=timedelta(seconds=1);sig=_signal(source,clock[0],'fresh')
    for _ in range(2):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals={source:sig})
        clock[0]+=timedelta(seconds=1)
    gate.cache[(TOKEN,POOL)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    store._microstructure119=SimpleNamespace(recent={TOKEN+'|'+POOL:dict(phase='SYNTHETIC_DISTRIBUTING_CYCLE',recorded_at=iso(clock[0]))},
        enqueue=lambda *a:None,note_safety=lambda *a:None,observe=lambda *a:None)
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert not store.db.execute('SELECT 1 FROM chain_meme_trader_positions WHERE arm_id=?',(REGIME_ARM,)).fetchone()
    store.close()
