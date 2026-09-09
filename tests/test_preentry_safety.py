import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest

from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.preentry_safety import EVM_FLAGS, PreentrySafety, assess
from memetrader.store import Store
from memetrader.strategy import SafetyChecker
from test_paper_execution import _snapshot


@pytest.mark.parametrize('field', EVM_FLAGS)
def test_explicit_evm_risk_veto(field):
    token=TokenCandidate('bsc','0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow())
    snap.raw['goplus_evm']={field:'1'}
    result=assess(snap,None,source_at=iso())
    assert result['status']=='REJECT' and not result['allow']
    assert field in result['reasons']


def test_missing_reports_are_unknown_and_simulation_failure_not_honeypot():
    token=TokenCandidate('bsc','0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow())
    assert assess(snap,None,source_at=iso())['allow'] is False
    snap.raw['honeypot_is']={'simulationSuccess':False}
    result=assess(snap,None,source_at=iso())
    assert result['status']=='UNKNOWN' and result['reasons']==[]


def test_solana_explicit_control_and_no_lp_lock_false_reject():
    token=TokenCandidate('solana','Token','Risk','RISK',source='fixture')
    snap=_snapshot(token,'Pool',utcnow())
    snap.raw['goplus_solana']={'freezable':{'status':'1'}}
    assert 'dangerous_freezable' in assess(snap,SafetyChecker,source_at=iso())['reasons']
    snap.raw['goplus_solana']={'freezable':{'status':'0'}}
    result=assess(snap,SafetyChecker,source_at=iso())
    assert not result['reasons'] and result['status']=='UNKNOWN'


def test_pending_security_retains_intent_requires_later_frame_and_no_old_report_refresh(tmp_path,monkeypatch):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'safety.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.activate_chain_market_entry_post_observation()
    token=TokenCandidate('bsc','0x'+'12'*20,'Next','NEXT',source='fixture')
    pool='0x'+'34'*20
    clock[0]+=timedelta(seconds=1)
    store.upsert_token(token,seen_at=clock[0])
    source=_snapshot(token,pool,clock[0])
    source.raw['goplus_evm']={'is_honeypot':'0'}
    store.add_snapshot(source)
    store.enroll_chain_meme_trader_v6(definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    async def unavailable(snap):
        assert 'goplus_evm' not in snap.raw
        return snap
    gate=PreentrySafety(store,SimpleNamespace(config={},enrich_evm_execution_fields=unavailable))
    store._preentry_safety=gate
    clock[0]+=timedelta(seconds=1)
    store.upsert_chain_meme_trader_pool_mark(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0])
    assert gate.pending
    assert store.db.execute('SELECT status FROM chain_meme_trader_order_intents').fetchone()[0]=='ready'
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==0
    asyncio.run(gate.work())
    assert gate.cache[(token.token_id,pool)]['allow'] is False
    gate.cache[(token.token_id,pool)]={'status':'PASS','allow':True,'source_at':iso(clock[0])}
    # Security receipt itself cannot authorize an equal-time market frame.
    store.upsert_chain_meme_trader_pool_mark(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0])
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==0
    clock[0]+=timedelta(seconds=1)
    store.upsert_chain_meme_trader_pool_mark(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0])
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]>0
    assert store.db.execute('SELECT status FROM chain_meme_trader_order_intents').fetchone()[0]=='filled'
    assert not gate.pending
    store.close()


@pytest.mark.parametrize('payload',[{}, {'token_name':'Irrelevant'}, {'is_honeypot':None}, {'buy_tax':'NaN'}, {'sell_tax':-1}, {'sell_tax':False}])
def test_provider_presence_without_usable_fact_cannot_authorize(payload):
    token=TokenCandidate('bsc','0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow());snap.raw['goplus_evm']=payload
    result=assess(snap,None,source_at=iso())
    assert result['status']=='UNKNOWN' and not result['allow']
    assert result['usable_facts']==[] and result['hard_veto']==[]

@pytest.mark.parametrize('payload',[{'is_honeypot':'0'},{'cannot_sell':'0'},{'sell_tax':'0.04'}])
def test_one_known_safety_fact_is_sufficient_without_all_fields(payload):
    token=TokenCandidate('bSC'.lower(),'0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow());snap.raw['goplus_evm']=payload
    result=assess(snap,None,source_at=iso())
    assert result['status']=='UNKNOWN' and result['allow'] and result['usable_facts']

def test_solana_empty_reports_wait_but_resolved_control_can_allow_unknown_custody():
    token=TokenCandidate('solana','Token','Risk','RISK',source='fixture')
    snap=_snapshot(token,'Pool',utcnow());snap.raw.update(goplus_solana={},rugcheck={})
    assert not assess(snap,SafetyChecker,source_at=iso())['allow']
    snap.raw['goplus_solana']={'freezable':{'status':'0'}}
    r=assess(snap,SafetyChecker,source_at=iso())
    assert r['allow'] and r['status']=='UNKNOWN' and r['usable_facts']

def test_empty_report_retries_only_after_existing_cache_ttl(tmp_path,monkeypatch):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'retry.sqlite3',initial_cash_usd=1000)
    token=TokenCandidate('bsc','0x'+'12'*20,'Next','NEXT',source='fixture');pool='0x'+'34'*20
    store.upsert_token(token,seen_at=clock[0]);sid=store.add_snapshot(_snapshot(token,pool,clock[0]))
    calls=[]
    async def enrich(snap):
        calls.append(1);snap.raw['goplus_evm']={} if len(calls)==1 else {'is_honeypot':'0'}
    gate=PreentrySafety(store,SimpleNamespace(config={},enrich_evm_execution_fields=enrich))
    gate.pending['1']=dict(version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,cohort_id=1,token_id=token.token_id,pool=pool,snapshot_id=sid,expires_at=iso(clock[0]+timedelta(seconds=120)))
    asyncio.run(gate.work());assert not gate.cache[(token.token_id,pool)]['allow']
    clock[0]+=timedelta(seconds=44);asyncio.run(gate.work());assert len(calls)==1
    clock[0]+=timedelta(seconds=2);asyncio.run(gate.work());assert len(calls)==2
    assert gate.cache[(token.token_id,pool)]['allow'] and '1' in gate.pending
    store.close()
