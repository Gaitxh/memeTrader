from datetime import timedelta
from types import SimpleNamespace
import asyncio
import pytest
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.narrative_hold import aggregate,extension_allowed,policy,NarrativeHold,ARM,KEY,max_hold
from memetrader.resource_bound_research import resource_policies
from test_resource_bound_store import setup_store,quote


def sources(now):
    return [dict(token_id='solana:A',binding='exact_contract',published_at=iso(now-timedelta(minutes=1)),available_at=iso(now-timedelta(seconds=1)),novelty=True,promotion_only=False,content_basis='Exact contract A',origin_id=x,verified_origin=True,url='https://'+x+'/news') for x in ['one.org','two.org']]


def test_only_verified_prior_available_independent_growth():
    now=utcnow();v=dict(status='cross_source_supported',claim_status='confirmed_fact',confidence=.9,model='gpt-5.6-terra')
    assert aggregate(sources(now),v,{},'solana:A',now)['state']=='CONFIRMED_EXPANDING'
    s=sources(now);s[1]['available_at']=iso(now+timedelta(seconds=1))
    assert aggregate(s,v,{},'solana:A',now)['state']!='CONFIRMED_EXPANDING'
    s=sources(now);s[1]['origin_id']='one.org'
    assert aggregate(s,v,{},'solana:A',now)['state']!='CONFIRMED_EXPANDING'
    assert aggregate(sources(now),v,{'origins':['one.org','two.org']},'solana:A',now)['state']=='STALE_OR_PROMOTION'
    assert aggregate(sources(now),{**v,'status':'contradicted'}, {},'solana:A',now)['state']=='CONTRADICTED'
    assert aggregate(sources(now),v,{},'solana:B',now)['state']=='UNKNOWN'


def test_extension_requires_actual_settlement_and_fresh_healthy_exact_pool():
    now=utcnow();p=dict(principal_recovered=1,amount_raw='20',realized_proceeds_usd=5,stake_usd=5,mark_status='VISIBLE',mark_pair_address='pool',mark_liquidity_usd=2000,mark_price_usd=1,opened_at=iso(now-timedelta(minutes=30)),mark_observed_at=iso(now),mark_recorded_at=iso(now))
    e=dict(state='CONFIRMED_EXPANDING',pool='pool',evidence_id=1,cutoff=iso(now-timedelta(minutes=1)),recorded_at=iso(now))
    assert extension_allowed(p,e,now)
    for update in [dict(principal_recovered=0),dict(realized_proceeds_usd=4.99),dict(mark_liquidity_usd=999),dict(mark_pair_address='other'),dict(mark_observed_at=iso(now-timedelta(seconds=16)))]:
        assert not extension_allowed({**p,**update},e,now)
    assert not extension_allowed(p,{**e,'state':'UNKNOWN'},now)


def test_registration_same_fill_unique_case_and_no_backfill(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    monkeypatch.setattr('memetrader.narrative_hold.utcnow',lambda:clock[0])
    parent=next(p for p in resource_policies() if p['arm_id']=='resource_age_rate_candidate_v1')
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    search=SimpleNamespace(config={})
    runtime=SimpleNamespace(store=store,autonomous_search=search)
    n=NarrativeHold(runtime)
    token=TokenCandidate('solana','NarrativeFixture','Fixture');created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    for _ in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,quote(token,'pool',created,clock[0],age_rate=True),recorded_at=clock[0])
    rows=store.db.execute('SELECT * FROM chain_meme_trader_positions').fetchall()
    assert len(rows)==2 and len({r['source_entry_fill_id'] for r in rows})==1
    n.collect();assert len(n.state['cases'])==1
    n.collect();assert store.db.execute("SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE kind='narrative_hold_case_v2'").fetchone()[0]==1
    case=next(iter(n.state['cases'].values()));case['points']['0']='DISPATCHED';n.save()
    resumed=NarrativeHold(runtime)
    assert next(iter(resumed.state['cases'].values()))['points']['0']=='RUNTIME_INTERRUPTED'
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id=?',(ARM,)).fetchone()[0]==1
    store.close()


def test_child_preserves_all_parent_exit_rules():
    parent=next(p for p in resource_policies() if p['arm_id']=='resource_age_rate_candidate_v1');child=policy(parent)
    for key in ('hard_stop_return','trailing_activate_return','trailing_drawdown','max_hold_minutes','take_profit','require_post_decision_observation'):
        assert child[key]==parent[key]
    assert max_hold(None,{},parent,utcnow())==parent['max_hold_minutes']


def test_persisted_overlay_extends_only_soft_exit_and_preserves_hard_exit(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    monkeypatch.setattr('memetrader.narrative_hold.utcnow',lambda:clock[0])
    parent=next(p for p in resource_policies() if p['arm_id']=='resource_age_rate_candidate_v1')
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    n=NarrativeHold(SimpleNamespace(store=store,autonomous_search=SimpleNamespace(config={})))
    token=TokenCandidate('solana','NarrativeExit','Fixture');created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    for _ in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,quote(token,'pool',created,clock[0],age_rate=True),recorded_at=clock[0])
    def pos():return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    def mark(price,seconds):
        clock[0]+=timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token,quote(token,'pool',created,clock[0],price=price),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    mark(1.5,10);mark(2,1)
    assert pos()['principal_recovered']==1
    n.collect();case=next(iter(n.state['cases'].values()))
    eid=n.record(case,'result',{'checkpoint':'test','state':'CONFIRMED_EXPANDING'},clock[0])
    n.state['latest'][case['id']]=dict(state='CONFIRMED_EXPANDING',pool='pool',cutoff=iso(clock[0]),recorded_at=iso(clock[0]),evidence_id=eid);n.save()
    store._preentry_safety=SimpleNamespace(behavior=lambda *a:dict(hard_veto=[],soft_hazard=[]),resume=lambda *a:None)
    mark(2,1790)
    assert pos()['pending_mark_id'] is None
    parentpos=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(parent['arm_id'],)).fetchone()
    assert parentpos['pending_mark_id'] is not None
    mark(.1,1)
    # Recovered principal prevents total economic hard loss, but the unchanged trailing safety still exits.
    pending=store.db.execute('SELECT * FROM chain_meme_trader_marks WHERE id=?',(pos()['pending_mark_id'],)).fetchone()
    assert pending is not None and pending['action']!='TIME_EXIT'
    store.close()



def test_busy_core_does_not_even_collect():
    n=NarrativeHold.__new__(NarrativeHold)
    event=asyncio.Event()
    n.r=SimpleNamespace(_chain_meme_active_idle=lambda:event)
    n.collect=lambda:pytest.fail('low research collected during core busy')
    asyncio.run(n.once())



def test_longitudinal_new_sources_are_not_backdated(tmp_path,monkeypatch):
    import json
    now=[utcnow()];monkeypatch.setattr('memetrader.narrative_hold.utcnow',lambda:now[0])
    n=NarrativeHold.__new__(NarrativeHold);n.state={'actual_tokens':0,'latest':{}}
    records=[];n.record=lambda case,kind,payload,at: records.append((kind,payload,at)) or len(records)
    n.save=lambda:None
    event=asyncio.Event();event.set();n.r=SimpleNamespace(_chain_meme_active_idle=lambda:event)
    ss=sources(now[0]);proof={'sources':[dict(url=s['url'],stance='supports',origin_relationship='distinct_origin') for s in ss]}
    n.store=SimpleNamespace(token_source_links=lambda *a,**k:[],db=SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchone=lambda:[json.dumps(proof)])))
    async def search(*a,**k):return {'sources':ss},{'model':'gpt-5.6-luna','run_id':'scout','tokens_used':10}
    async def verify(**k):return {k['parent_run_id']:dict(record_id=1,status='cross_source_supported',claim_status='confirmed_fact',confidence=.9,model='gpt-5.6-terra',tokens_used=10)}
    n.search=SimpleNamespace(_consume_quota=lambda *a:True,config={},_search=search,_record_tokens=lambda *a:None,_verify_fact_subjects=verify)
    case=dict(id='case',pool='pool',token_id='solana:A',leads=[],points={});token=TokenCandidate('solana','A','Example')
    asyncio.run(n.research(case,'0',token,[ARM],now[0]))
    assert case['previous']['state']=='UNKNOWN'
    assert any(kind=='sources' for kind,_,_ in records)
    assert all(s.get('source_evidence_id') for s in case['leads'])
    now[0]+=timedelta(minutes=12)
    asyncio.run(n.research(case,'1',token,[ARM],now[0]))
    assert case['previous']['state']=='CONFIRMED_EXPANDING'
    assert n.state['actual_tokens']==30


def test_latency_guard_disables_overlay_and_further_research():
    n=NarrativeHold.__new__(NarrativeHold);n.state={'overlay_enabled':True};n.save=lambda:None
    def timing(p95):return {'components':{'held_fetch':{'sample_count':30,'duration_seconds':{'p95':p95}}}}
    n.guard(timing(1),timing(1.4))
    assert n.state['overlay_enabled'] is False and n.state['research_paused'] is True
