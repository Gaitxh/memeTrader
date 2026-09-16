"""C3 contract tests: real HTTP batching and actual Paper pipeline, no network."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from memetrader.collectors import (
    DEX_REQUEST_FOLLOWUP_PRIORITY, DexLowPriorityCapacityDeferred,
    DexScreenerClient, HttpClient,
)
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


@pytest.mark.parametrize('has_quote_owner',[False,True])
def test_unrouted_cohort_pending_is_not_a_price_feed_takeover(monkeypatch,has_quote_owner):
    from test_observation_leases145_runtime import LeaseStore,bare_runtime
    clock=[utcnow()];monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock[0])
    runtime=bare_runtime(LeaseStore());runtime.chain_meme_trader_only=True
    normal,snap=asset(10,clock[0]);extra,extra_snap=asset(11,clock[0])
    runtime._remember_pattern_quotes({normal.token_id:(normal,snap)})
    manager=runtime._shared_batch148
    assert manager.offer(extra,extra_snap,clock[0],excluded=set(runtime._pattern_watch))
    runtime._cohort_pending={(extra.token_id,extra_snap.raw['pair']['pairAddress']):{'signals':{}}}
    runtime._market_priority_tokens={extra.token_id} if has_quote_owner else set()
    runtime._rank_no_ca_events=lambda:None
    runtime._dex_quote_low_priority_available=lambda:True
    idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
    calls=[]
    async def quote_batch(chain,addresses,**kwargs):
        calls.append((list(addresses),kwargs));return {}
    runtime._dex_batch_quote=quote_batch
    clock[0]+=timedelta(seconds=16)
    asyncio.run(runtime.chain_meme_pattern_observer_once())
    assert calls and normal.address in calls[0][0]
    assert (extra.address in calls[0][0]) is (not has_quote_owner)
    if not has_quote_owner:
        assert calls[0][1]['feature_only148'][extra.token_id]==extra_snap.raw['pair']['pairAddress']
        assert extra.token_id in manager.active


@pytest.mark.parametrize('dispatches,age_seconds,quote_owner,expected', [
    (1, 16, False, True),
    (0, 16, False, False),
    (1, 61, False, False),
    (1, 16, True, False),
])
def test_frozen_cohort_signal_borrows_existing_watch_batch(
    monkeypatch, dispatches, age_seconds, quote_owner, expected,
):
    from test_observation_leases145_runtime import LeaseStore,bare_runtime

    clock=[utcnow()]
    monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock[0])
    runtime=bare_runtime(LeaseStore())
    runtime.chain_meme_trader_only=True
    watched,watched_snapshot=asset(10,clock[0])
    pending,pending_snapshot=asset(11,clock[0])
    runtime._remember_pattern_quotes({watched.token_id:(watched,watched_snapshot)})
    runtime._cohort_pending={
        (pending.token_id,pending_snapshot.raw['pair']['pairAddress']):{
            'signals':{'trial':{'recorded_at':iso(clock[0]-timedelta(seconds=age_seconds-16))}},
            'dispatch_counts':{'trial':dispatches},
        },
    }
    runtime._market_priority_tokens={pending.token_id} if quote_owner else set()
    runtime._rank_no_ca_events=lambda:None
    runtime._dex_quote_low_priority_available=lambda:True
    idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
    calls=[]

    async def quote_batch(chain,addresses,**kwargs):
        calls.append((list(addresses),kwargs))
        return {}

    runtime._dex_batch_quote=quote_batch
    clock[0]+=timedelta(seconds=16)
    asyncio.run(runtime.chain_meme_pattern_observer_once())

    assert len(calls)==1
    assert watched.address in calls[0][0]
    assert (pending.address in calls[0][0]) is expected
    assert pending.token_id not in calls[0][1].get('feature_only148',{})
    status = runtime.store.kv['coverage145:status']
    assert status['watch_refresh']['bsc']['due'] == (2 if expected else 1)
    assert status['watch_refresh']['bsc']['result'] == 'returned'
    if dispatches and age_seconds <= 60:
        followup = next(item for item in status['signal_followups']
                        if item['token_id'] == pending.token_id)
        assert followup['in_watch'] is False
        assert followup['due'] is expected
        assert followup['returned'] is False


def test_watched_frozen_signal_records_missing_next_frame(monkeypatch):
    from test_observation_leases145_runtime import LeaseStore,bare_runtime

    clock=[utcnow()]
    monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock[0])
    runtime=bare_runtime(LeaseStore())
    runtime.chain_meme_trader_only=True
    token,snapshot=asset(12,clock[0])
    runtime._remember_pattern_quotes({token.token_id:(token,snapshot)})
    runtime._cohort_pending={
        (token.token_id,snapshot.raw['pair']['pairAddress']):{
            'signals':{'trial':{'recorded_at':iso(clock[0])}},
            'dispatch_counts':{'trial':1},
        },
    }
    runtime._rank_no_ca_events=lambda:None
    runtime._dex_quote_low_priority_available=lambda:True
    runtime.market_http=SimpleNamespace(dex_followup_urgent_until=0.0)
    idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
    priority_seen=[]
    budgets=[]

    @asynccontextmanager
    async def budget(seconds):
        budgets.append(seconds)
        yield

    monkeypatch.setattr('memetrader.runtime.dex_low_budget',budget)

    async def quote_batch(chain,addresses,**kwargs):
        priority_seen.append(DEX_REQUEST_FOLLOWUP_PRIORITY.get())
        return {}

    runtime._dex_batch_quote=quote_batch
    clock[0]+=timedelta(seconds=16)
    asyncio.run(runtime.chain_meme_pattern_observer_once())

    status=runtime.store.kv['coverage145:status']
    followup=status['signal_followups'][0]
    assert followup['token_id']==token.token_id
    assert followup['in_watch'] is True
    assert followup['due'] is True
    assert followup['returned'] is False
    assert followup['sampled'] is False
    assert status['watch_refresh']['bsc']['result']=='returned'
    assert status['watch_refresh']['bsc']['returned']==0
    assert status['watch_refresh']['bsc']['urgent_followup'] is True
    assert priority_seen==[True]
    assert budgets==[6]
    assert runtime.market_http.dex_followup_urgent_until>0


def test_frozen_followup_borrows_one_existing_low_http_slot():
    async def scenario():
        client=HttpClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=[])),
                          min_host_interval=0)
        release=asyncio.Event()
        ready=asyncio.Event()
        active=[0]

        async def background():
            async with client._dex_inflight_slot():
                active[0]+=1
                if active[0]==4:
                    ready.set()
                await release.wait()

        tasks=[asyncio.create_task(background()) for _ in range(4)]
        try:
            await asyncio.wait_for(ready.wait(),timeout=2)
            client.dex_followup_urgent_until=asyncio.get_running_loop().time()+10
            with pytest.raises(DexLowPriorityCapacityDeferred):
                async with client._dex_inflight_slot():
                    pass
            token=DEX_REQUEST_FOLLOWUP_PRIORITY.set(True)
            try:
                async with client._dex_inflight_slot():
                    assert client.snapshot_http_capacity()['active_low_priority']==5
            finally:
                DEX_REQUEST_FOLLOWUP_PRIORITY.reset(token)
            assert client.snapshot_http_capacity()['followup_reservation_deferred']==1
        finally:
            release.set()
            await asyncio.gather(*tasks)
            await client.client.aclose()

    asyncio.run(scenario())


def test_irregular_three_real_frames_use_valid_contract_span():
    from memetrader.trajectory144 import _window
    start=utcnow()
    def rows(times):
        return [dict(t=(start+timedelta(seconds=s)).timestamp(),observed_at=iso(start+timedelta(seconds=s)),
            price_usd=1+s/200,liquidity_usd=3000,volume_5m_usd=300+s*10,buys_5m=3+s,sells_5m=1) for s in times]
    # Actual initial follow-up delays observed in the shared-batch trial.
    w=_window(rows([0,15.804106,61.588254]))
    assert w is not None and w['span_seconds']==pytest.approx(61.588254,abs=.001)
    assert w['start_at']==iso(start)
    assert _window(rows([0,15,91])) is None  # still reject the 76-second gap
    assert _window(rows([0,50,100])) is None  # still reject >90 total span
    assert _window(rows([0,50])) is None  # never fabricate a third observation


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


def test_coverage_waits_for_third_point_without_false_gap_label():
    now=utcnow();manager=SharedBatchCoverage();token,snap=asset(1,now)
    manager.offer(token,snap,now);_,selected=manager.extend_batch('bsc',['0x'+'f'*40],now)
    for seconds in (50,70):
        at=now+timedelta(seconds=seconds)
        response=_snapshot(token,snap.raw['pair']['pairAddress'],at,price=1.1)
        manager.response({token.token_id:(token,response)},selected,at,DexScreenerClient._snapshot)
        if seconds==50:assert '30' not in manager.active[token.token_id]['windows']
    assert manager.active[token.token_id]['windows']['30']=='OBSERVED'


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
        assert p is not None and p['stake_usd']==20  # current uniform Paper contract
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
