"""C3 contract tests: real HTTP batching and actual Paper pipeline, no network."""
import asyncio
from collections import deque
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from memetrader.collectors import DexScreenerClient, HttpClient
from memetrader.models import TokenCandidate, utcnow, iso
from memetrader.shared_batch148 import SharedBatchCoverage
from memetrader.runtime import Runtime
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from memetrader.trajectory144 import Engine, ARMS
from test_l0_store import _snapshot


def asset(i, when, chain='bsc'):
    token=TokenCandidate(chain,'0x'+f'{i:040x}','Batch','B')
    pool='0x'+f'{i+1000:040x}'
    return token,_snapshot(token,pool,when,price=1,liquidity=3000)


@pytest.mark.parametrize('n',[0,1,28,29,30,31,60])
def test_actual_client_never_adds_an_http_batch(n):
    now=utcnow();manager=SharedBatchCoverage()
    for i in (1,2,3):
        token,snap=asset(i,now);assert manager.offer(token,snap,now)
    legacy=['0x'+f'{j+100:040x}' for j in range(n)]
    extended,selected=manager.extend_batch('bsc',legacy,now)
    assert extended[:len(legacy)]==legacy
    assert len(selected)<=2
    async def requests(addresses):
        calls=[]
        async def handler(req):
            calls.append(req);return httpx.Response(200,json=[])
        client=HttpClient(transport=httpx.MockTransport(handler),min_host_interval=0)
        try:
            await DexScreenerClient(client).batch_quote_fresh('bsc',addresses)
            return calls
        finally:await client.client.aclose()
    before=asyncio.run(requests(legacy));after=asyncio.run(requests(extended))
    assert len(after)==len(before)
    if n in (0,30,60):assert not selected
    assert all(len(str(r.url).split('/')[-1].split(','))<=30 for r in after)


def test_fixed_lease_capacity_and_normal_priority_takeover():
    now=utcnow();manager=SharedBatchCoverage()
    for chain in ('bsc','robinhood'):
        for i in range(1,15):
            token,snap=asset(i,now,chain);manager.offer(token,snap,now)
    assert len(manager.waiting)==24
    original=[]
    for chain in ('bsc','robinhood'):
        _,selection=manager.extend_batch(chain,['0x'+'f'*40],now)
        original.extend(selection)
    assert len(manager.active)==4
    until={k:v['expires_at'] for k,v in manager.active.items()}
    manager.extend_batch('bsc',['0x'+'f'*40],now+timedelta(seconds=100))
    assert {k:v['expires_at'] for k,v in manager.active.items()}==until
    manager.prune(now+timedelta(seconds=110),excluded={original[0]})
    assert original[0] not in manager.active
    manager.prune(now+timedelta(seconds=180))
    assert not manager.active
    token,snap=asset(1,now+timedelta(seconds=180))
    assert not manager.offer(token,snap,now+timedelta(seconds=180))


def test_response_uses_exact_pool_and_original_clocks():
    now=utcnow();manager=SharedBatchCoverage();token,snap=asset(1,now)
    assert manager.offer(token,snap,now)
    _,selected=manager.extend_batch('bsc',['0x'+'f'*40],now)
    later=now+timedelta(seconds=15)
    response=_snapshot(token,'0x'+'e'*40,later,price=99)
    original=deepcopy(snap.raw['pair']);original['priceUsd']='1.1'
    response.raw['pairs']=[response.raw['pair'],original]
    got=manager.response({token.token_id:(token,response)},selected,later,DexScreenerClient._snapshot)
    received=got[token.token_id][1]
    assert received.raw['pair']['pairAddress']==snap.raw['pair']['pairAddress']
    assert received.price_usd==1.1 and received.observed_at==later and received.ingested_at==later
    assert manager.active[token.token_id]['frames']==2
    assert not manager.response({token.token_id:(token,response)},selected,later,DexScreenerClient._snapshot)
    wrong=_snapshot(token,'0x'+'d'*40,later+timedelta(seconds=15),price=999)
    assert not manager.response({token.token_id:(token,wrong)},selected,later+timedelta(seconds=15),DexScreenerClient._snapshot)
    assert manager.counts['SOURCE_NO_EXACT_POOL']==1


def test_inflight_exact_response_survives_normal_watch_takeover():
    now=utcnow();manager=SharedBatchCoverage();token,snap=asset(1,now)
    manager.offer(token,snap,now)
    _,selected=manager.extend_batch('bsc',['0x'+'f'*40],now)
    at=now+timedelta(seconds=2)
    manager.prune(at,excluded={token.token_id})
    assert not manager.active
    response=_snapshot(token,snap.raw['pair']['pairAddress'],at,price=1.1)
    result=manager.response({token.token_id:(token,response)},selected,at,DexScreenerClient._snapshot)
    assert result[token.token_id][1].observed_at==at
    assert not manager.active
    assert manager.counts['RELEASED_INFLIGHT_DELIVERED']==1


def test_known_floor_is_delivered_to_learning_then_releases_slot():
    now=utcnow();manager=SharedBatchCoverage();token,snap=asset(1,now)
    manager.offer(token,snap,now);_,selected=manager.extend_batch('bsc',['0x'+'f'*40],now)
    at=now+timedelta(seconds=15);bad=_snapshot(token,snap.raw['pair']['pairAddress'],at,price=.5,liquidity=100)
    got=manager.response({token.token_id:(token,bad)},selected,at,DexScreenerClient._snapshot)
    assert got[token.token_id][1].liquidity_usd==100
    assert token.token_id not in manager.active
    assert manager.counts['KNOWN_FLOOR']==1


def test_real_tagged_callback_safety_later_buy_exit_without_legacy_fanout(tmp_path,monkeypatch):
    clock=[utcnow()]
    for module in ('runtime','models','store','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'shared-pipeline.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.register_chain_meme_cohort_experiments()
    clock[0]+=timedelta(seconds=1);start=clock[0]
    runtime=Runtime.__new__(Runtime);runtime.store=store;runtime.config={'paper':{'max_quote_age_seconds':45}}
    runtime._cohort_started_at=start;runtime._cohort_state={};runtime._cohort_saved_at=start
    runtime._shared_batch148=SharedBatchCoverage()
    store._trajectory144=Engine(start)
    idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    token=TokenCandidate('bsc','0x'+'1'*40,'Extra','EX');pool='0x'+'2'*40;store.upsert_token(token)
    seen=[]
    def legacy(frames,state,**kw):
        assert not frames, 'Feature-only input leaked into old strategy scan'
        seen.append(1);return state,{}
    monkeypatch.setattr('memetrader.cohort_experiments.consume_passive_cohort_batch',legacy)
    snapshots=[]
    async def deliver(i):
        clock[0]=start+timedelta(seconds=i*10)
        snap=_snapshot(token,pool,clock[0],price=1+i*i*.015,liquidity=3000)
        snap.raw['pair']['pairCreatedAt']=int((start-timedelta(seconds=50)).timestamp()*1000)
        snap.buys_5m=3+i*i;snap.sells_5m=1;snap.volume_5m_usd=300+i*i*30
        snapshots.append(snap)
        runtime._cohort_batches=deque([(clock[0],[(token,snap)],{token.token_id:pool})],maxlen=16)
        await runtime.chain_meme_cohort_observer_once()
    async def run():
        for i in range(1,7):await deliver(i)
        assert gate.pending
        assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ARMS[1],)).fetchone()[0]==0
        gate.cache[(token.token_id,pool)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
        await deliver(7)
        with store._lock,store.db:gate.resume(token,snapshots[-1],clock[0])
        p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARMS[1],)).fetchone()
        assert p is not None and p['stake_usd']==2
        assert p['opened_at']>iso(start+timedelta(seconds=30))
        for _ in range(2):
            clock[0]+=timedelta(seconds=2)
            store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pool,clock[0],price=.1),recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
        p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARMS[1],)).fetchone()
        assert p['status']=='closed' and int(p['amount_raw'])==0
        assert 'hard_stop' in p['close_reason']
        assert seen
    try:asyncio.run(run())
    finally:store.close()


def test_feature_only_budget_defers_without_retiming_or_legacy_scan(tmp_path,monkeypatch):
    clock=utcnow();store=Store(tmp_path/'budget.sqlite3',initial_cash_usd=1000)
    runtime=Runtime.__new__(Runtime);runtime.store=store;runtime.config={'paper':{'max_quote_age_seconds':45}}
    runtime._cohort_started_at=clock;runtime._cohort_state={};runtime._cohort_saved_at=clock
    runtime._shared_batch148=SharedBatchCoverage();store._trajectory144=Engine(clock)
    idle=asyncio.Event();runtime._chain_meme_active_idle=lambda:idle
    monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock)
    monkeypatch.setattr('memetrader.cohort_experiments.consume_passive_cohort_batch',lambda frames,state,**kw:(state,{}) if not frames else pytest.fail('legacy input'))
    values=[asset(i,clock) for i in range(1,8)]
    tags={t.token_id:s.raw['pair']['pairAddress'] for t,s in values}
    runtime._cohort_batches=deque([(clock,values,tags)],maxlen=16)
    try:
        asyncio.run(runtime.chain_meme_cohort_observer_once())
        assert runtime._cohort_batches
        received,remaining,metadata=runtime._cohort_batches[0]
        assert received==clock and 1<=len(remaining)<=7
        assert all(s.observed_at==clock for t,s in remaining)
        assert set(metadata)=={t.token_id for t,s in remaining}
        assert store.db.execute('SELECT COUNT(*) FROM token_snapshots').fetchone()[0]==0
    finally:store.close()
