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

@pytest.mark.parametrize('payload',[{'is_honeypot':'0'},{'cannot_sell':'0'},{'cannot_sell_all':'0'}])
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


@pytest.mark.parametrize('payload',[{'sell_tax':'0.04'},{'buy_tax':'0','sell_tax':'0'}, {'honeypot_with_same_creator':'0'}])
def test_bsc_weak_facts_do_not_authorize(payload):
    token=TokenCandidate('bsc','0x'+'12'*20,'Risk')
    snap=_snapshot(token,'0x'+'34'*20,utcnow());snap.raw['goplus_evm']=payload
    r=assess(snap,None,source_at=iso())
    assert r['status']=='WEAK' and not r['allow'] and not r['hard_veto']
    snap.raw['goplus_evm']['hidden_owner']='1'
    assert assess(snap,None,source_at=iso())['status']=='REJECT'


@pytest.mark.parametrize('second,allowed', [({'cannot_sell_all':'0'},True),({'sell_tax':'0'},False),({},False),({'is_honeypot':'1'},False)])
def test_weak_retry_once_persisted_and_shadow(tmp_path,monkeypatch,second,allowed):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'weak.sqlite3',initial_cash_usd=1000)
    token=TokenCandidate('bsc','0x'+'12'*20,'Weak');pool='0x'+'34'*20
    store.upsert_token(token,seen_at=clock[0]);sid=store.add_snapshot(_snapshot(token,pool,clock[0]))
    old=store.db.execute('SELECT raw_json FROM token_snapshots WHERE id=?',(sid,)).fetchone()[0]
    calls=[]
    async def enrich(snap):
        calls.append(1);snap.raw['goplus_evm']={'sell_tax':'0'} if len(calls)==1 else second
        snap.raw['honeypot_is_error']='HTTPStatusError'
    checker=SimpleNamespace(config={},enrich_evm_execution_fields=enrich)
    gate=PreentrySafety(store,checker)
    gate.pending['1']=dict(version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,cohort_id=1,token_id=token.token_id,
        pool=pool,snapshot_id=sid,requested_at=iso(clock[0]),notional=5,expires_at=iso(clock[0]+timedelta(seconds=120)))
    asyncio.run(gate.work())
    assert len(calls)==1 and gate.cache[(token.token_id,pool)]['status']=='WEAK'
    assert next(iter(store._safety_veto_shadow.state['pending'].values()))['category']=='WAIT_WEAK'
    clock[0]+=timedelta(seconds=4);asyncio.run(gate.work());assert len(calls)==1
    gate=PreentrySafety(store,checker)  # Due/attempt state survives process loss.
    clock[0]+=timedelta(seconds=1);asyncio.run(gate.work())
    result=gate.cache[(token.token_id,pool)]
    assert len(calls)==2 and result['allow']==allowed
    assert result['provider_availability']['honeypot_is']['error_type']=='HTTPStatusError'
    clock[0]+=timedelta(seconds=50);asyncio.run(gate.work());assert len(calls)==2
    gate=PreentrySafety(store,checker);asyncio.run(gate.work());assert len(calls)==2
    assert store.db.execute('SELECT raw_json FROM token_snapshots WHERE id=?',(sid,)).fetchone()[0]==old
    store.close()


@pytest.mark.parametrize('report',[{'is_honeypot':'0'},{'is_honeypot':'1'}])
def test_strong_first_check_has_no_weak_retry(tmp_path,monkeypatch,report):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'strong.sqlite3');token=TokenCandidate('bsc','0x'+'12'*20,'Strong');pool='0x'+'34'*20
    store.upsert_token(token);sid=store.add_snapshot(_snapshot(token,pool,clock[0]));calls=[]
    async def enrich(snap):calls.append(1);snap.raw['goplus_evm']=report
    gate=PreentrySafety(store,SimpleNamespace(config={},enrich_evm_execution_fields=enrich))
    gate.pending['1']=dict(version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,cohort_id=1,token_id=token.token_id,
        pool=pool,snapshot_id=sid,expires_at=iso(clock[0]+timedelta(seconds=120)))
    asyncio.run(gate.work());clock[0]+=timedelta(seconds=10);asyncio.run(gate.work())
    assert len(calls)==1 and 'weak_retry_due_at' not in gate.pending['1']
    store.close()

@pytest.mark.parametrize('report,allowed,hard', [
    ({'cannot_sell':'0'}, True, False),
    ({'hidden_owner':'1'}, False, True),
    ({}, False, False),
    ({'cannot_buy':'0','is_open_source':'0','sell_tax':''}, False, False),
    ({'cannot_sell':'0','is_open_source':'0'}, True, False),
    ({'sell_tax':'0.13'}, False, True),
])
def test_robinhood_goplus_partial_report(report,allowed,hard):
    token=TokenCandidate('robinhood','0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow())
    snap.raw['pair']['dexId']='uniswap'
    snap.raw['goplus_evm']=report
    result=assess(snap,None,source_at=iso())
    assert result['allow'] is allowed
    assert bool(result['hard_veto']) is hard
    assert 'external_security_provider_unsupported' not in result['unknowns']
    if report.get('is_open_source')=='0':
        assert result['soft_hazard']==['closed_source_unverified']
        assert result['status']=='UNKNOWN'
    snap.raw['pair']['baseToken']['address']='0x'+'56'*20
    assert not assess(snap,None,source_at=iso())['allow']


def test_robinhood_enrichment_uses_existing_goplus_endpoint():
    token=TokenCandidate('robinhood','0x'+'12'*20,'Risk','RISK',source='fixture')
    snap=_snapshot(token,'0x'+'34'*20,utcnow())
    calls=[]
    async def get(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(json=lambda:{'code':1,'result':{snap.address:{'cannot_sell':'0'}}})
    checker=SafetyChecker.__new__(SafetyChecker)
    checker.config={};checker.http=SimpleNamespace(get=get)
    asyncio.run(checker.enrich_evm_execution_fields(snap))
    assert len(calls)==1 and calls[0][0].endswith('/token_security/4663')
    assert calls[0][1]=={'params':{'contract_addresses':snap.address},'ttl':60}
    assert snap.raw['goplus_evm']=={'cannot_sell':'0'}
