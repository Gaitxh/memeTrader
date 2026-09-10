import asyncio
from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.models import iso
from memetrader.market_microstructure import classify_page,classify_short_page
from memetrader.microstructure_shadow_worker import MicrostructureWorker
from test_strategy_delivery137 import setup,TOKEN,POOL
from test_l0_store import _snapshot


def page(signal):
    data=[dict(id=str(i),attributes=dict(from_token_address='quote',to_token_address=TOKEN.split(':')[1],
        tx_from_address=str(i),volume_in_usd='100',block_timestamp=iso(signal-timedelta(seconds=i))))
        for i in (0,5,10,15,20)]
    return dict(payload={'data':data},received_at=iso(signal+timedelta(seconds=1)))


@pytest.mark.parametrize('case',['valid','too_short','stale','unordered','duplicate','future_receipt'])
def test_short_window_is_independent_and_coverage_is_explicit(case):
    from memetrader.models import utcnow
    signal=utcnow();p=page(signal);now=signal+timedelta(seconds=2)
    if case=='too_short':p['payload']['data']=p['payload']['data'][:3]
    if case=='stale':
        for r in p['payload']['data']:r['attributes']['block_timestamp']=iso(signal-timedelta(seconds=40+int(r['id'])))
    if case=='unordered':p['payload']['data'].reverse()
    if case=='duplicate':p['payload']['data'].insert(0,p['payload']['data'][0])
    if case=='future_receipt':now=signal
    short=classify_short_page(p,token_id=TOKEN,pool=POOL,signal_at=signal,decision_at=now)
    if case=='valid':
        assert short['state']=='ORGANIC_BREADTH_NET_BUY'
        assert short['observed_window_seconds']==20
        baseline=classify_page(p,token_id=TOKEN,pool=POOL,window_start=signal-timedelta(minutes=10),window_end=signal,decision_at=now)
        assert baseline['state']=='UNKNOWN'
    else:assert short['state']=='UNKNOWN'


def test_shared_page_producer_security_later_fill_and_five_minute_exit(tmp_path,monkeypatch):
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    clock[0]+=timedelta(seconds=30);signal=clock[0];clock[0]+=timedelta(seconds=1)
    idle=asyncio.Event();idle.set()
    worker=MicrostructureWorker(store,SimpleNamespace(_host_backoff_until={}),lambda:idle)
    calls=[]
    async def fetch(*a):calls.append(a);return page(signal)
    worker.client.fetch=fetch
    worker.pending['short-test']=dict(version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,token_id=TOKEN,pool=POOL,
        requested_at=iso(signal),expires_at=iso(signal+timedelta(seconds=120)),early=True,
        pool_created_at_ms=(signal-timedelta(seconds=60)).timestamp()*1000,arms=[],shadow_costs={})
    asyncio.run(worker.work());assert len(calls)==1
    assert worker.recent[TOKEN+'|'+POOL]['state']=='UNKNOWN'
    clock[0]+=timedelta(seconds=1)
    worker.observe(TOKEN,_snapshot(token,POOL,clock[0]),clock[0],clock[0])
    signals=worker.signals_for(TOKEN,POOL,clock[0]);arm='organic_short_observed_flow_v1'
    assert arm in signals and 'organic_early_flow_v1' not in signals
    for _ in range(3):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals=signals)
        clock[0]+=timedelta(seconds=1)
    def positions():return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchall()
    assert not positions() and len(gate.pending)==1
    gate.cache[(TOKEN,POOL)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert len(positions())==1 and positions()[0]['stake_usd']==2
    for _ in range(2):
        clock[0]+=timedelta(seconds=301 if _==0 else 1)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN])
    assert positions()[0]['status']=='closed'
    assert store.db.execute("SELECT count(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'",(arm,)).fetchone()[0]==1
    store.close()
