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
