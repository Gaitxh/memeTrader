from datetime import timedelta
from types import SimpleNamespace
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime
from memetrader.rediscovery_funnel import RediscoveryFunnel
from memetrader.reactivation_watch import eligible


def setup(monkeypatch):
    clock=[utcnow()];monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock[0])
    f=RediscoveryFunnel();r=Runtime.__new__(Runtime)
    r.store=SimpleNamespace(_rediscovery_funnel=f)
    r._pattern_held_tokens=set();r._pattern_protection_ready=True
    r._paper_quote_rejections=lambda *a:[]
    def send(name,age=30000,episode=False,price=2,liq=6000,volume=300):
        t=TokenCandidate('bsc',name,'fixture');now=clock[0]
        s=TokenSnapshot('bsc',name,price,liq,None,volume,4,2,observed_at=now,ingested_at=now,
            raw={'pair':{'pairAddress':'pool'+name,'pairCreatedAt':(now-timedelta(seconds=age)).timestamp()*1000}})
        if episode and t.token_id not in f.members:
            f.episode(t.token_id,now,{'pool':'pool'+name,'price':1,'liquidity':5000,'volume':100,'trades':2})
        r._remember_pattern_quotes({t.token_id:(t,s)})
        return t,s
    return r,f,clock,send


def test_spare_borrow_one_slot_and_release(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for i in range(3):send('m'+str(i))
    t,_=send('probe',episode=True)
    assert r._pattern_watch[t.token_id]['reactivation_probe']
    send('other',episode=True)
    assert 'bsc:other' not in r._pattern_watch
    assert len(r._pattern_watch)==4
    clock[0]+=timedelta(seconds=121);r._remember_pattern_quotes({})
    assert t.token_id not in r._pattern_watch and len(r._pattern_watch)==3
    send('probe');assert t.token_id not in r._pattern_watch
    assert f.counts['temporary_slot_released']==1


def test_reclaims_only_sampled_overflow_not_early_base(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for i in range(10):
        t,s=send('e'+str(i),age=10);r._pattern_watch[t.token_id]['sampled_at']=s.observed_at
    clock[0]+=timedelta(seconds=121)
    t,_=send('probe',episode=True)
    assert len(r._pattern_watch)==10 and r._pattern_watch[t.token_id]['reactivation_probe']
    assert sum(v['bucket']=='early' for v in r._pattern_watch.values())==9
    assert f.counts['temporary_slot']==1


def test_base_full_does_not_steal_mature_or_growth(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for prefix,count,age in [('e',3,10),('g',4,2000),('m',3,30000)]:
        for i in range(count):
            t,s=send(prefix+str(i),age);r._pattern_watch[t.token_id]['sampled_at']=s.observed_at
    before=set(r._pattern_watch);clock[0]+=timedelta(seconds=121)
    send('probe',episode=True)
    assert set(r._pattern_watch)==before and not f.counts['temporary_slot']


def test_startup_and_pending_sources_protect_overflow(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for i in range(10):
        t,s=send('e'+str(i),30000 if i>=7 else 10);r._pattern_watch[t.token_id]['sampled_at']=s.observed_at
    clock[0]+=timedelta(seconds=121)
    r._pattern_protection_ready=False;send('probe',episode=True)
    assert not f.counts['temporary_slot']
    r._pattern_protection_ready=True
    # All potential overflow victims protected by existing independent lanes.
    r.store._preentry_safety=SimpleNamespace(pending={'a':{'token_id':'bsc:e0'}})
    r.store._market_entry_pending_tokens={'bsc:e1'}
    r._cohort_pending={('bsc:e2','poole2'): {}}
    r.store._pattern_ready_until={'bsc:e'+str(i):clock[0]+timedelta(seconds=180) for i in range(3,10)}
    before=set(r._pattern_watch);send('probe')
    assert not f.counts['temporary_slot'] and set(r._pattern_watch)==before


def test_held_and_pending_probe_survives_lease(monkeypatch):
    r,f,clock,send=setup(monkeypatch);t,_=send('probe',episode=True)
    r._pattern_held_tokens={t.token_id};clock[0]+=timedelta(seconds=121)
    r._remember_pattern_quotes({});assert t.token_id in r._pattern_watch
    r._pattern_held_tokens=set();r.store._market_entry_pending_tokens={t.token_id}
    r._remember_pattern_quotes({});assert t.token_id in r._pattern_watch
    r.store._market_entry_pending_tokens=set();clock[0]+=timedelta(seconds=16)
    r._remember_pattern_quotes({});assert t.token_id not in r._pattern_watch


def test_base_reservation_reclaims_unprotected_extra_probe(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for i in range(3):send('m'+str(i))
    send('probe',episode=True)
    for i in range(4):send('g'+str(i),2000)
    for i in range(3):send('e'+str(i),10)
    assert len(r._pattern_watch)==10 and 'bsc:probe' not in r._pattern_watch
    assert r._pattern_watch_nonheld_by_chain_bucket['bsc']=={'early':3,'growth':4,'mature':3}


def test_pending_extra_probe_cannot_be_reservation_victim(monkeypatch):
    r,f,clock,send=setup(monkeypatch)
    for i in range(3):send('m'+str(i))
    send('probe',episode=True)
    r.store._preentry_safety=SimpleNamespace(pending={'pending':{'token_id':'bsc:probe'}})
    for i in range(4):send('g'+str(i),2000)
    for i in range(2):send('e'+str(i),10)
    send('new_early',10)
    assert 'bsc:probe' in r._pattern_watch and 'bsc:new_early' in r._pattern_watch
    assert len(r._pattern_watch)==10 and 'bsc:g3' not in r._pattern_watch
    assert r._pattern_watch_nonheld_by_chain_bucket['bsc']['early']==3


def test_unknown_other_pool_decay_or_no_activity_never_special(monkeypatch):
    r,f,clock,send=setup(monkeypatch);t,s=send('probe',episode=True)
    member=f.members[t.token_id];member['seen'].discard('temporary_slot')
    assert eligible(member,t,s,clock[0],1000)
    member['baseline']['pool']='other';assert not eligible(member,t,s,clock[0],1000)
    member['baseline']['pool']='poolprobe';s.liquidity_usd=4000
    assert not eligible(member,t,s,clock[0],1000)
    s.liquidity_usd=6000;s.volume_5m_usd=100;s.buys_5m=1;s.sells_5m=1
    assert not eligible(member,t,s,clock[0],1000)
    member['baseline']=None;assert not eligible(member,t,s,clock[0],1000)
