import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from memetrader.market_microstructure import classify, classify_page, branch_decision, TradePageClient

T=datetime(2026,9,10,tzinfo=timezone.utc)
TOKEN='bsc:0xabc'
POOL='0xdef'

def row(i,wallet,kind,usd):
    return dict(id=str(i),token_id=TOKEN,pool=POOL,wallet=wallet,kind=kind,usd=usd,
                observed_at=T+timedelta(seconds=i),recorded_at=T+timedelta(seconds=60))

def assess(rows,**kw):
    args=dict(token_id=TOKEN,pool=POOL,window_start=T,window_end=T+timedelta(seconds=30),
        received_at=T+timedelta(seconds=60),recorded_at=T+timedelta(seconds=60),
        decision_at=T+timedelta(seconds=60),coverage_start=T,coverage_end=T+timedelta(seconds=30),complete=True)
    return classify(rows,**{**args,**kw})

def organic():return [row(i,'0x'+str(i),'buy',100) for i in range(6)]
def synthetic():return [row(i,'0xa','buy' if i<3 else 'sell',100 if i<3 else 900) for i in range(4)]

def test_organic_and_synthetic_signed_not_count():
    a=assess(organic());b=assess(synthetic())
    assert a['state']=='ORGANIC_BREADTH_NET_BUY' and a['metrics']['effective_breadth']==6
    assert b['state']=='SYNTHETIC_SINGLE_WALLET_CYCLE'
    assert b['metrics']['buys']==3 and b['metrics']['net_usd']==-600
    assert b['signer_is_not_human_identity']

@pytest.mark.parametrize('change',[{'complete':False},{'coverage_start':T+timedelta(seconds=1)},
    {'coverage_end':T+timedelta(seconds=29)},{'decision_at':T}])
def test_unknown_coverage_and_future_receipt(change):assert assess(organic(),**change)['state']=='UNKNOWN'

def test_future_rows_identity_and_duplicates():
    rows=organic();rows[0]['recorded_at']=T+timedelta(seconds=61)
    assert assess(rows)['state']=='UNKNOWN'
    rows=organic();rows[0]['pool']='other'
    assert assess(rows)['state']=='UNKNOWN'
    assert assess(organic()+organic()[:1])['state']=='UNKNOWN'
    # Later-than-signal trades may prove coverage, but never alter window metrics.
    assert assess(organic()+[row(40,'0xa','sell',999999)])['metrics']['sell_usd']==0

def test_truncated300_not_zero_and_base_orientation():
    data=[]
    for i in range(300,0,-1):
        data.append(dict(id=str(i),attributes=dict(from_token_address='0xquote',to_token_address='0xabc',
            tx_from_address=str(i),volume_in_usd='10',kind='sell',block_timestamp=(T+timedelta(seconds=i)).isoformat())))
    p=dict(payload={'data':data},received_at=(T+timedelta(seconds=301)).isoformat())
    got=classify_page(p,token_id=TOKEN,pool=POOL,window_start=T-timedelta(seconds=10),
        window_end=T+timedelta(seconds=30),decision_at=T+timedelta(seconds=301))
    assert got['reason']=='UNKNOWN_COVERAGE'
    got=classify_page(p,token_id=TOKEN,pool=POOL,window_start=T+timedelta(seconds=1),
        window_end=T+timedelta(seconds=30),decision_at=T+timedelta(seconds=301))
    assert got['metrics']['buys']==30 and got['metrics']['sell_usd']==0

def test_branch_strict_next_and_exact_sell_simulation():
    kwargs=dict(token_id=TOKEN,pool=POOL,frame_observed=T+timedelta(seconds=61),
        frame_recorded=T+timedelta(seconds=62),price=1.,liquidity=2000.,safety_allow=True,reawakening=True)
    assert branch_decision(assess(organic()),**kwargs)=='ORGANIC_SHADOW_ELIGIBLE'
    assert branch_decision(assess(organic()),**{**kwargs,'frame_observed':T+timedelta(seconds=60)})=='WAIT'
    assert branch_decision(assess(organic()),**{**kwargs,'hard_veto':True})=='REJECT'
    s=assess(synthetic())
    assert branch_decision(s,**kwargs)=='WAIT'
    sim=dict(success=True,token_id=TOKEN,pool=POOL,observed_at=T+timedelta(seconds=59),recorded_at=T+timedelta(seconds=60))
    assert branch_decision(s,**kwargs,sell_simulation=sim)=='SYNTHETIC_SHADOW_ELIGIBLE'
    assert branch_decision(s,**kwargs,sell_simulation={**sim,'pool':'other'})=='WAIT'

@asynccontextmanager
async def permit():yield True

class Http:
    def __init__(self,status=200):self._host_backoff_until={};self.calls=0;self.status=status
    async def get(self,url,**kwargs):
        assert kwargs=={'retry_429':False}
        self.calls+=1
        r=httpx.Response(self.status,json={'data':[]},request=httpx.Request('GET',url))
        r.raise_for_status();return r

def test_cache_duplicate_calls_and_global_budget():
    async def run():
        h=Http();c=TradePageClient(h,permit=permit,now=lambda:T,clock=lambda:100.)
        a,b=await asyncio.gather(c.fetch(TOKEN,POOL),c.fetch(TOKEN,POOL))
        assert h.calls==1 and a['received_at']==b['received_at']
        assert (await c.fetch(TOKEN,'0xother'))['reason']=='BUDGET_OR_BACKOFF'
        assert h.calls==1
    asyncio.run(run())

def test_no_guard_no_request_and_429_shared_backoff():
    async def run():
        h=Http(429);c=TradePageClient(h,clock=lambda:100.)
        assert (await c.fetch(TOKEN,POOL))['reason']=='HELD_START_GUARD_UNAVAILABLE'
        assert h.calls==0
        c.permit=permit
        assert (await c.fetch(TOKEN,POOL))['reason']=='RATE_LIMIT'
        assert h._host_backoff_until['api.geckoterminal.com']==160
        assert (await c.fetch(TOKEN,POOL))['reason']=='BUDGET_OR_BACKOFF'
        assert h.calls==1
    asyncio.run(run())

def test_shadow_unknown_and_hard_expire_without_backfill():
    from memetrader.market_microstructure import MicrostructureShadow
    from memetrader.models import utcnow, iso
    s=MicrostructureShadow();now=utcnow()
    anchor=dict(eligible=False,price_usd=None,observed_at=iso(now),recorded_at=iso(now))
    for i,state in enumerate(('UNKNOWN','HARD_UNSELLABLE')):
        args=dict(evidence_id=i,evidence={'state':state},token_id=TOKEN,pool=POOL,
                  anchor=anchor,now=now,costs={})
        s.capture(**args);s.capture(**args)
    assert s.counts=={'UNKNOWN':1,'HARD_UNSELLABLE':1}
    result=s.snapshot(now+timedelta(minutes=246))
    assert not result['outcomes']['pending']
    assert len(result['outcomes']['recent'])==2
    assert all(v['status']=='UNKNOWN' for r in result['outcomes']['recent'] for v in r['results'].values())
    assert result['decision_eligible'] is False

def test_real_shared_gecko_start_priority_and_cancel_cleanup():
    import time
    from memetrader.collectors import HttpClient, GECKO_REQUEST_HIGH_PRIORITY
    async def run():
        order=[]
        async def handler(req):
            order.append(req.url.path)
            return httpx.Response(200,json={})
        h=HttpClient(transport=httpx.MockTransport(handler),min_host_interval=.001)
        host='api.geckoterminal.com'
        h._last[host]=time.monotonic()-2.0
        low=asyncio.create_task(h.get('https://'+host+'/low',retry_429=False))
        await asyncio.sleep(.01)
        token=GECKO_REQUEST_HIGH_PRIORITY.set(True)
        high=asyncio.create_task(h.get('https://'+host+'/held',retry_429=False))
        GECKO_REQUEST_HIGH_PRIORITY.reset(token)
        await high
        assert order==['/held']
        low.cancel()
        with pytest.raises(asyncio.CancelledError):await low
        assert not h._gecko_start_waiters[False] and not h._gecko_start_waiters[True]
        await h.close()
    asyncio.run(run())

def test_worker_rare_queue_dedup_no_network_in_enqueue_and_passive_expiry():
    from memetrader.microstructure_shadow_worker import MicrostructureWorker
    from memetrader.models import utcnow,iso
    from threading import RLock
    from types import SimpleNamespace
    class DB:
        def execute(self,sql,args):
            if sql.startswith('SELECT arm_id'):return [('event_reawakening_v1',)]
            return []
    class Store:
        db=DB();_lock=RLock()
        def get_kv(self,*a):return {}
        def record_chain_meme_pattern_evidence(self,*a,**kw):pass
    async def run():
        idle=asyncio.Event();idle.set();h=Http();w=MicrostructureWorker(Store(),h,lambda:idle)
        now=utcnow()
        item=dict(version='v',cohort_id=1,token_id=TOKEN,pool=POOL,requested_at=iso(now),
                  expires_at=iso(now+timedelta(seconds=120)),shadow_costs={})
        w.enqueue(item);w.enqueue(item)
        assert len(w.pending)==1 and h.calls==0
        await w.work()
        assert h.calls==1 and not w.pending and w.counts['UNKNOWN']==1
        for entry in w.anchors.values():entry['classified_at']=iso(now-timedelta(seconds=121))
        w.flush()
        assert not w.anchors and w.shadow.counts['UNKNOWN']==1
        idle.clear();w.enqueue({**item,'cohort_id':2});w.kick()
        assert w.task is None and h.calls==1
        rejected={**item,'cohort_id':2}
        w.note_safety(rejected,'REJECT',{'reasons':['cannot_sell_all']})
        await w.work()
        assert h.calls==1 and w.counts['HARD_UNSELLABLE']==1
    asyncio.run(run())
