from datetime import timedelta
from types import SimpleNamespace
from memetrader.rediscovery_funnel import RediscoveryFunnel
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime


def test_funnel_preserves_watch_and_accounts_actual_reasons(monkeypatch):
    now=utcnow();monkeypatch.setattr('memetrader.runtime.utcnow',lambda:now)
    plain, tracked=Runtime.__new__(Runtime),Runtime.__new__(Runtime)
    f=RediscoveryFunnel();tracked.store=SimpleNamespace(_rediscovery_funnel=f,get_kv=lambda *args:{})
    for r in (plain,tracked):
        r.config={'paper':{'max_quote_age_seconds':45}};r._pattern_held_tokens=set()
    def send(i,age=60,liq=5000,pool=None):
        t=TokenCandidate('bsc',f'0x{i:040x}','fixture')
        if t.token_id not in f.members:f.episode(t.token_id,now)
        s=TokenSnapshot('bsc',t.address,1,liq,None,200,6,4,observed_at=now,ingested_at=now,
            provider='dexscreener',raw={'pair':{'pairAddress':pool or f'0x{i+100:040x}',
            'pairCreatedAt':(now-timedelta(seconds=age)).timestamp()*1000}})
        for r in (plain,tracked):r._remember_pattern_quotes({t.token_id:(t,s)})
        assert plain._pattern_watch==tracked._pattern_watch
        assert plain._pattern_watch_nonheld_by_chain_bucket==tracked._pattern_watch_nonheld_by_chain_bucket
    for i in range(10):send(i)
    send(10);send(0,liq=0);send(11);send(12,age=2000);send(12,age=2000,pool='other')
    assert f.counts['episode']==13
    assert f.counts['admission_attempt']==13
    assert f.counts['basic_valid']==13
    assert f.counts['admit_base']==3
    assert f.counts['admit_borrow']==7
    for reason in ('skip_bucket_full','refresh_exact_pool','replace_unusable','reclaim_reservation','skip_other_pool'):
        assert f.counts[reason]==1
    assert f.counts['bucket_full_chain_full']==1
    replaced=next(e for e in f.examples if e.get('reason')=='replace_unusable')
    assert replaced['occupancy']['chain_total']==10  # before victim removal


def test_membership_expiry_cap_and_deduplication():
    f=RediscoveryFunnel();now=utcnow()
    f.hit('untracked','BUY',now);assert not f.counts
    for i in range(257):f.episode(str(i),now)
    assert len(f.members)==256 and f.counts['membership_evicted']==1
    for _ in range(10):f.hit('256','snapshot',now)
    assert f.counts['snapshot']==1 and len(f.examples)==32
    f.hit('256','BUY',now+timedelta(hours=2))
    assert not f.members and f.counts['BUY']==0


def test_preepisode_or_missing_clock_quote_not_basic_valid():
    f=RediscoveryFunnel();now=utcnow();t=TokenCandidate('bsc','x','x');f.episode(t.token_id,now)
    s=TokenSnapshot('bsc','x',1,5000,None,1,1,1,observed_at=now-timedelta(seconds=1),ingested_at=now,raw={'pairAddress':'p'})
    f.quote(t,s,'admit_base',now,1000)
    assert f.counts['admission_attempt']==1 and not f.counts['basic_valid']


def test_mature_full_spare_then_chain_full_and_held_exempt(monkeypatch):
    now=utcnow();monkeypatch.setattr('memetrader.runtime.utcnow',lambda:now)
    f=RediscoveryFunnel();r=Runtime.__new__(Runtime)
    r.store=SimpleNamespace(_rediscovery_funnel=f,get_kv=lambda *args:{});r.config={'paper':{'max_quote_age_seconds':45}}
    r._pattern_held_tokens={'bsc:held'}
    plain=Runtime.__new__(Runtime);plain.config=r.config;plain._pattern_held_tokens=r._pattern_held_tokens
    def send(address,age):
        t=TokenCandidate('bsc',address,'fixture')
        if t.token_id not in f.members:f.episode(t.token_id,now)
        s=TokenSnapshot('bsc',address,1,5000,None,200,6,4,observed_at=now,ingested_at=now,
            raw={'pair':{'pairAddress':'pool'+address,'pairCreatedAt':(now-timedelta(seconds=age)).timestamp()*1000}})
        for runtime in (plain,r):runtime._remember_pattern_quotes({t.token_id:(t,s)})
        assert r._pattern_watch==plain._pattern_watch
    send('held',30000)
    for i in range(3):send(str(i),30000)
    send('spare',30000)
    e=next(e for e in f.examples if e.get('reason')=='skip_bucket_full')
    assert e['occupancy']==dict(chain='bsc',target_bucket='mature',occupied=dict(early=0,growth=0,mature=3),
        chain_total=3,base_caps=dict(early=3,growth=4,mature=3),held_count=1)
    for i in range(3):send('early'+str(i),60)
    for i in range(4):send('growth'+str(i),2000)
    send('full',30000)
    assert f.counts['bucket_full_chain_spare']==1 and f.counts['bucket_full_chain_full']==1
    for _ in range(40):send('full',30000)
    assert len(f.examples)==32 and f.counts['bucket_full_chain_full']==1
    assert f.examples[-1]['occupancy']['chain_total']==10
