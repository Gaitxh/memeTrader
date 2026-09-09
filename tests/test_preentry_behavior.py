from datetime import timedelta
from memetrader.models import utcnow,iso
from memetrader.preentry_safety import assess_behavior


def row(now,state='SYNTHETIC_SUPPORT_PATTERN',reserve='10',known=True):
    return dict(id=1,token_id='solana:T',pair_address='Pool',observed_at=iso(now),recorded_at=iso(now),payload=dict(observer_version='chain-pattern-exact/v1',observed_at=iso(now),observer_state=state,effective_quote_reserve_raw=reserve,features=dict(effective_quote_reserve_known=known,flow_granularity='confirmed_slot_net_not_transaction_identity')))

def assess(r,now):return assess_behavior([r],token_id='solana:T',pool='Pool',now=now)

def test_confirmed_effective_reserve_reject_is_not_native_real_reserve_zero():
    now=utcnow()
    assert assess(row(now,'EFFECTIVE_RESERVE_NONPOSITIVE','0'),now)['hard_veto']
    assert not assess(row(now,'EFFECTIVE_RESERVE_NONPOSITIVE','0',False),now)['hard_veto']
    assert not assess(row(now,'OBSERVED_NORMAL','100'),now)['hard_veto']

def test_soft_hazard_is_separate_and_recovery_not_blacklist():
    now=utcnow()
    for state in ('SYNTHETIC_SUPPORT_PATTERN','UNWIND_HAZARD_PRECURSOR_RECOVERY_UNKNOWN'):
        a=assess(row(now,state),now)
        assert a['soft_hazard']==[state] and a['hard_veto']==[]
    old=row(now);new=row(now+timedelta(seconds=1),'OBSERVED_NORMAL');new['id']=2
    assert assess_behavior([old,new],token_id='solana:T',pool='Pool',now=now+timedelta(seconds=1))['soft_hazard']==[]

def test_future_stale_wrong_pool_or_unverified_evidence_cannot_veto():
    now=utcnow()
    assert not assess(row(now+timedelta(seconds=1)),now)['soft_hazard']
    assert not assess(row(now-timedelta(seconds=16)),now)['soft_hazard']
    r=row(now);r['pair_address']='pool'
    assert not assess(r,now)['soft_hazard']
    r=row(now);r['payload']['observer_version']='unverified'
    assert not assess(r,now)['soft_hazard']


def test_hazard_wait_beats_cached_pass_and_retains_pending_without_fetch(tmp_path,monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from memetrader.models import TokenCandidate
    from memetrader.store import Store
    from memetrader.preentry_safety import PreentrySafety
    from test_paper_execution import _snapshot
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'behavior.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.activate_chain_market_entry_post_observation()
    token=TokenCandidate('bsc','0x'+'12'*20,'Next','NEXT',source='fixture');pool='0x'+'34'*20
    clock[0]+=timedelta(seconds=1);store.upsert_token(token,seen_at=clock[0]);store.add_snapshot(_snapshot(token,pool,clock[0]))
    store.enroll_chain_meme_trader_v6(definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    async def forbidden(snap):raise AssertionError('no refresh while local hazard waits')
    gate=PreentrySafety(store,SimpleNamespace(config={},enrich_evm_execution_fields=forbidden));store._preentry_safety=gate
    soft={'hard_veto':[],'soft_hazard':['SYNTHETIC_SUPPORT_PATTERN'],'behavior_sources':[{'observed_at':iso(clock[0]),'recorded_at':iso(clock[0])}]}
    monkeypatch.setattr(gate,'behavior',lambda item,now:soft)
    gate.cache[(token.token_id,pool)]={'status':'PASS','allow':True,'source_at':iso(clock[0])}
    clock[0]+=timedelta(seconds=1);store.upsert_chain_meme_trader_pool_mark(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0])
    assert gate.pending and store.db.execute('select count(*) from chain_meme_trader_positions').fetchone()[0]==0
    asyncio.run(gate.work())
    soft['soft_hazard']=[]
    clock[0]+=timedelta(seconds=1);store.upsert_chain_meme_trader_pool_mark(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0])
    assert store.db.execute('select count(*) from chain_meme_trader_positions').fetchone()[0]>0
    store.close()
