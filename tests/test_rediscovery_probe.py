import json
import sqlite3
from threading import RLock
from types import SimpleNamespace
from datetime import timedelta
import pytest
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime
from memetrader.rediscovery_funnel import RediscoveryFunnel
from memetrader.rediscovery_probe import protected


def runtime():
    c = sqlite3.connect(':memory:')
    c.executescript('CREATE TABLE chain_meme_trader_positions(token_id,status); '
        'CREATE TABLE chain_meme_trader_v6_entry_evaluations(id INTEGER,definition_version,token_id,reason,feature_json);')
    r = Runtime.__new__(Runtime)
    r.store = SimpleNamespace(db=c, _lock=RLock(), CHAIN_MEME_TRADER_ACTIVE_VERSION='v',
        _rediscovery_funnel=RediscoveryFunnel(), _preentry_safety=SimpleNamespace(pending={}))
    r._pattern_held_tokens=set();r._cohort_pending={};r._paper_quote_rejections=lambda *a:[]
    return r


def send(r, clock, name, age=30000, rediscovered=False):
    t=TokenCandidate('bsc',name,name)
    if rediscovered and t.token_id not in r.store._rediscovery_funnel.members:
        r.store._rediscovery_funnel.episode(t.token_id,clock)
    q=TokenSnapshot('bsc',name,1,5000,None,100,5,4,observed_at=clock,ingested_at=clock,
        raw={'pair':{'pairAddress':'pool'+name,'pairCreatedAt':(clock-timedelta(seconds=age)).timestamp()*1000}})
    r._remember_pattern_quotes({t.token_id:(t,q)})
    return t.token_id


def test_one_probe_two_continuity_and_episode_once(monkeypatch):
    clock=utcnow();monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock)
    r=runtime()
    base=[send(r,clock,str(i)) for i in range(3)]
    for i in range(3):send(r,clock,'early'+str(i),60)
    for i in range(4):send(r,clock,'growth'+str(i),2000)
    for item in r._pattern_watch.values():item['sampled_at']=clock
    first_expiry=r._pattern_watch[base[1]]['expires_at']
    clock+=timedelta(seconds=119)
    p=send(r,clock,'probe',rediscovered=True)
    assert p not in r._pattern_watch
    clock+=timedelta(seconds=1)
    send(r,clock,'probe',rediscovered=True)
    assert p in r._pattern_watch and base[0] not in r._pattern_watch
    assert r._pattern_watch[p]['expires_at']==clock+timedelta(seconds=120)
    assert len(r._pattern_watch)==10
    assert all(k in r._pattern_watch for k in base[1:])
    assert r._pattern_watch[base[1]]['expires_at']==first_expiry
    send(r,clock,'ordinary')
    assert 'bsc:ordinary' not in r._pattern_watch
    clock+=timedelta(seconds=120)
    p2=send(r,clock,'probe2',rediscovered=True)
    assert p2 in r._pattern_watch and p not in r._pattern_watch
    assert len(r._pattern_watch)==10
    assert sum(bool(v.get('rediscovery_probe')) for v in r._pattern_watch.values())==1
    clock+=timedelta(seconds=120)
    send(r,clock,'probe',rediscovered=True)
    assert p not in r._pattern_watch
    assert r.store._rediscovery_funnel.counts['skip_probe_episode_consumed']==1


@pytest.mark.parametrize('kind',['held','open','safety','cohort','next_frame'])
def test_protection_and_expired_probe_survives(monkeypatch,kind):
    clock=utcnow();monkeypatch.setattr('memetrader.runtime.utcnow',lambda:clock)
    r=runtime();token=send(r,clock,'protected')
    if kind=='held':r._pattern_held_tokens.add(token)
    if kind=='open':r.store.db.execute("INSERT INTO chain_meme_trader_positions VALUES(?,'open')",(token,))
    if kind=='safety':r.store._preentry_safety.pending['1']={'token_id':token}
    if kind=='cohort':r._cohort_pending['1']={'signals':{'a':{'selected':{'token_id':token}}}}
    if kind=='next_frame':r.store.db.execute('INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES(1,?,?,?,?)',
        ('v',token,'pattern_observation',json.dumps({'ready_arm_ids':['a']})))
    assert protected(r,token)
    r._pattern_watch[token].update(rediscovery_probe=True,expires_at=clock,sampled_at=clock)
    r._remember_pattern_quotes({})
    assert token in r._pattern_watch
    for i in range(2 if kind!='held' else 3):send(r,clock,str(i))
    for item in r._pattern_watch.values():item['sampled_at']=clock
    clock+=timedelta(seconds=120)
    send(r,clock,'new',rediscovered=True)
    assert token in r._pattern_watch
    r._pattern_watch[token]['quote'].liquidity_usd=0
    send(r,clock,'ordinary')
    assert token in r._pattern_watch  # Legacy unusable replacement cannot evict a protected probe.
