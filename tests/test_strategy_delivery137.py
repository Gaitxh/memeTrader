import asyncio
from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from memetrader.market_microstructure import classify
from memetrader.microstructure_shadow_worker import MicrostructureWorker
from memetrader.cohort_experiments import recovered_signal_aliases
from test_l0_store import _snapshot
from test_synthetic_harvest136 import report,TOKEN,POOL


def setup(tmp_path,monkeypatch):
    clock=[utcnow()]
    for m in ('store','models','preentry_safety','microstructure_shadow_worker','narrative_hold'):
        monkeypatch.setattr('memetrader.'+m+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'137.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.register_chain_meme_cohort_experiments()
    token=TokenCandidate('bsc',TOKEN.split(':')[1],'Test','T');store.upsert_token(token)
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    return clock,store,token,gate


def test_early_no_cohort_candidate_preflight_and_postbuy_real_classifier(tmp_path,monkeypatch):
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    clock[0]+=timedelta(seconds=1);start=clock[0];end=start+timedelta(seconds=30)
    clock[0]+=timedelta(seconds=60)
    rows=[dict(id=str(i),token_id=TOKEN,pool=POOL,wallet='one',kind='buy',usd=100,
        observed_at=start+timedelta(seconds=i),recorded_at=iso(clock[0])) for i in range(4)]
    frames=[dict(token_id=TOKEN,pool=POOL,observed_at=at,recorded_at=iso(clock[0]),
        price_usd=price,liquidity_usd=2000) for at,price in ((start,1),(end,2))]
    evidence=classify(rows,token_id=TOKEN,pool=POOL,window_start=start,window_end=end,
        received_at=clock[0],recorded_at=clock[0],decision_at=clock[0],coverage_start=start,
        coverage_end=end,complete=True,price_frames=frames)
    assert evidence['phase']=='SYNTHETIC_LPI_BUILDING_CANDIDATE'
    evidence.update(token_id=TOKEN,pool=POOL,recorded_at=iso(clock[0]),signal_at=iso(start))
    idle=asyncio.Event();idle.set()
    worker=MicrostructureWorker(store,SimpleNamespace(_host_backoff_until={}),lambda:idle)
    store._microstructure119=worker
    worker.anchors['early']={'result':evidence,'classified_at':iso(clock[0]),
        'item':dict(token_id=TOKEN,pool=POOL,early=True,arms=[],shadow_costs={},requested_at=iso(start))}
    clock[0]+=timedelta(seconds=1)
    worker.observe(TOKEN,_snapshot(token,POOL,clock[0]),clock[0],clock[0])
    signal=worker.signals_for(TOKEN,POOL,clock[0]);arm='synthetic_fast_harvest_v1'
    assert arm in signal  # No prior cohort, BUY or simulation needed to reach preflight.
    for _ in range(2):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals=signal)
        clock[0]+=timedelta(seconds=1)
    assert len(gate.pending)==1 and next(iter(gate.pending.values()))['requires_exact_pool_sell_simulation']
    gate.cache[(TOKEN,POOL)]=dict(status='UNKNOWN',allow=True,source_at=iso(clock[0]),reasons=[])
    count=store.db.execute('SELECT count(*) FROM token_snapshots').fetchone()[0]
    for _ in range(20):
        clock[0]+=timedelta(milliseconds=10)
        gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert store.db.execute('SELECT count(*) FROM token_snapshots').fetchone()[0]==count
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    async def enrich(snap):snap.raw.update(report(clock[0]));return snap
    gate.checker.enrich_evm_execution_fields=enrich;gate.cache.clear()
    asyncio.run(gate.work())
    assert gate.cache[(TOKEN,POOL)]['exact_pool_sell_simulation']['exact_size'] is False
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    pos=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert pos and pos['stake_usd']==1
    opened=clock[0];clock[0]+=timedelta(seconds=20)
    worker.last_watch=0;worker.admit_watch({},{});assert any(i.get('postbuy') for i in worker.pending.values())
    # Real page normalization/classifier consumes only post-open signed trades.
    data=[]
    for i in range(5):
        buy=i<3;at=opened+timedelta(seconds=i*5)
        data.append({'id':str(i),'attributes':dict(block_timestamp=iso(at),
            from_token_address='quote' if buy else token.address,
            to_token_address=token.address if buy else 'quote',
            tx_from_address='one',volume_in_usd='100' if buy else '900')})
    async def fetch(*a):return dict(payload={'data':list(reversed(data))},received_at=iso(clock[0]))
    worker.client.fetch=fetch
    asyncio.run(worker.work())
    assert worker.hazard_for(TOKEN,POOL,iso(opened),clock[0])=='synthetic_distribution'
    for _ in range(2):
        clock[0]+=timedelta(seconds=1)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN])
    assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]=='closed'
    store.close()


@pytest.mark.parametrize('base,child,origin',[
    ('event_clone_narrative_reawakening_v1','event_recovered_narrative_runner_v1','event_recorded_at'),
    ('organic_reawakening_flow_v1','organic_reawakening_recovered_runner_v1','signal_at')])
def test_alias_same_fill_half_recovery_settlement_and_narrative(tmp_path,monkeypatch,base,child,origin):
    from memetrader.narrative_hold import NarrativeHold
    from test_narrative_hold import TYPES
    clock,store,token,gate=setup(tmp_path,monkeypatch);clock[0]+=timedelta(seconds=1)
    n=NarrativeHold(SimpleNamespace(store=store,autonomous_search=SimpleNamespace(config={})))
    signal=recovered_signal_aliases({base:dict(episode_id='same',decision_key='same|'+base,
        selected=dict(token_id=TOKEN,pair_address=POOL),observed_at=iso(clock[0]),recorded_at=iso(clock[0]),
        decision_evidence={origin:iso(clock[0])})})
    for _ in range(2):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals=signal)
        clock[0]+=timedelta(seconds=1)
    gate.cache[(TOKEN,POOL)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    def position(arm):return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert position(base)['source_entry_fill_id']==position(child)['source_entry_fill_id']
    original=int(position(child)['amount_raw']);opened=clock[0]
    def mark(price,seconds):
        clock[0]+=timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=price),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN])
    mark(6,2);assert position(child)['principal_recovered']==0
    mark(6,1)
    p=position(child);assert p['principal_recovered']==1 and p['realized_proceeds_usd']>=5
    assert int(p['amount_raw'])>=original/2 and position(base)['principal_recovered']==0
    n.collect();assert len(n.state['cases'])==1
    case=next(iter(n.state['cases'].values()));eid=n.record(case,'result',{'checkpoint':'verified','state':'CONFIRMED_EXPANDING'},clock[0])
    n.state['overlay_enabled']=True
    n.state['latest'][case['id']]=dict(**TYPES,state='CONFIRMED_EXPANDING',pool=POOL,
        cutoff=iso(clock[0]),recorded_at=iso(clock[0]),evidence_id=eid);n.save()
    mark(6,1801);mark(6,1)
    assert position(base)['status']=='closed' and position(child)['status']=='open'
    mark(1,1);mark(1,1)
    assert position(child)['status']=='closed'  # Narrative cannot override trailing safety.
    store.close()
