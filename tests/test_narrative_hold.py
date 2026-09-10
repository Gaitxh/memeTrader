from datetime import timedelta
from types import SimpleNamespace
import asyncio
import pytest
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.narrative_hold import aggregate,extension_allowed,policy,NarrativeHold,ARM,KEY,max_hold,pending_scout_leads
from memetrader.resource_bound_research import resource_policies
from memetrader.narrative_hold import value_checkpoint
from test_resource_bound_store import setup_store,quote


TYPES=dict(classifier_version='narrative-types/96B',narrative_type='real_event_novelty',diffusion_stage='independent_amplification',token_binding_basis='verified_exact_contract_frozen_cohort',independent_origin_count=2,promotion_only=False)

def test_value_admission_settlement_not_elapsed_or_metadata():
    now=utcnow();case=dict(token_id='bsc:token',pool='pool',opened_at=iso(now-timedelta(hours=2)),points={},local_leads=[{'url':'https://x.com/project','verified_origin':False}])
    p=dict(arm_id=ARM,principal_recovered=0,amount_raw='20',realized_proceeds_usd=0,stake_usd=5)
    m=dict(pair_address='pool',status='VISIBLE',liquidity_usd=2000,price_usd=1,observed_at=iso(now),recorded_at=iso(now))
    assert value_checkpoint(case,[p],m,now)==(None,'VALUE_NOT_YET_RECOVERED')
    assert value_checkpoint(case,[{**p,'principal_recovered':1,'realized_proceeds_usd':4.99}],m,now)[0] is None
    p.update(principal_recovered=1,realized_proceeds_usd=5)
    assert value_checkpoint(case,[p],m,now)==('value110:recovery','RECOVERY_TRIGGERED')
    for update in ({'pair_address':'other'},{'liquidity_usd':999},{'observed_at':iso(now-timedelta(seconds=31))},{'recorded_at':iso(now+timedelta(seconds=1))}):
        assert value_checkpoint(case,[p],{**m,**update},now)[0] is None
    assert value_checkpoint(case,[{**p,'amount_raw':'0'}],m,now)[0] is None
    case.update(points={'value110:recovery':'COMPLETE'},value_research_started_at=iso(now-timedelta(seconds=721)),previous={'state':'UNKNOWN'})
    assert value_checkpoint(case,[p],m,now)==(None,'NO_CONSTRUCTIVE_EVIDENCE')
    case['previous']['state']='EMERGING'
    assert value_checkpoint(case,[p],m,now)[0]=='value110:1'
    case['points'].update({'value110:1':'COMPLETE','value110:2':'RUNTIME_INTERRUPTED'})
    assert value_checkpoint(case,[p],m,now)==(None,'CASE_BUDGET')


@pytest.mark.parametrize('arm_id',['event_recovered_narrative_runner_v1','organic_reawakening_recovered_runner_v1'])
def test_recovered_narrative_runners_require_settled_principal(arm_id):
    now=utcnow();case=dict(token_id='bsc:token',pool='pool',opened_at=iso(now-timedelta(minutes=2)),points={},leads=[])
    mark=dict(pair_address='pool',status='VISIBLE',liquidity_usd=2000,price_usd=1,observed_at=iso(now),recorded_at=iso(now))
    position=dict(arm_id=arm_id,principal_recovered=0,amount_raw='10',realized_proceeds_usd=0,stake_usd=5)
    assert value_checkpoint(case,[position],mark,now)==(None,'VALUE_NOT_YET_RECOVERED')
    position.update(principal_recovered=1,realized_proceeds_usd=5)
    assert value_checkpoint(case,[position],mark,now)==('value110:recovery','RECOVERY_TRIGGERED')

def test_value_wait_reconsiders_recovery_without_spending_or_burning_checkpoint(monkeypatch):
    now=utcnow();monkeypatch.setattr('memetrader.narrative_hold.utcnow',lambda:now)
    case=dict(id='case',token_id='bsc:token',pool='pool',cohort_id=1,opened_at=iso(now-timedelta(minutes=4)),points={},leads=[])
    p=dict(arm_id=ARM,principal_recovered=0,amount_raw='10',realized_proceeds_usd=0,stake_usd=5)
    m=dict(pair_address='pool',status='VISIBLE',liquidity_usd=2000,price_usd=1,observed_at=iso(now),recorded_at=iso(now))
    n=NarrativeHold.__new__(NarrativeHold);n.state=dict(cases={'case':case},latest={},day=now.date().isoformat(),calls=0,reserved_tokens=0)
    n.collect=lambda:None;n.save=lambda:None;n.record=lambda *a:1
    db=SimpleNamespace(execute=lambda sql,*a:SimpleNamespace(fetchall=lambda:[p],fetchone=lambda:m))
    n.store=SimpleNamespace(db=db,CHAIN_MEME_TRADER_ACTIVE_VERSION='v',token=lambda _:object(),_preentry_safety=SimpleNamespace(behavior=lambda *a:{}))
    event=asyncio.Event();event.set();n.r=SimpleNamespace(_chain_meme_active_idle=lambda:event)
    n.search=SimpleNamespace(enabled=True,_profile=lambda role:{'model':'gpt-5.6-luna' if role=='token_context' else 'gpt-5.6-terra'})
    calls=[]
    async def research(case,cp,*args):calls.append(cp);case['points'][cp]='COMPLETE'
    n.research=research
    monkeypatch.setattr('memetrader.narrative_hold.local_social_leads',lambda *a:[])
    monkeypatch.setattr('memetrader.narrative_hold.authoritative_local_lead',lambda *a:None)
    asyncio.run(n.once());asyncio.run(n.once())
    assert calls==[] and case['points']=={} and n.state['calls']==0
    assert n.state['admission_counts']['VALUE_NOT_YET_RECOVERED']==1
    p.update(principal_recovered=1,realized_proceeds_usd=5)
    asyncio.run(n.once());asyncio.run(n.once())
    assert calls==['value110:recovery'] and n.state['calls']==1
    assert n.state['reserved_tokens']==60000

def sources(now):
    return [dict(token_id='solana:A',binding='exact_contract',published_at=iso(now-timedelta(minutes=1)),available_at=iso(now-timedelta(seconds=1)),source_type='independent_news',event_key='event',verified_binding=True,novelty=True,promotion_only=False,content_basis='Exact contract A',origin_id=x,verified_origin=True,url='https://'+x+'/news') for x in ['one.org','two.org']]


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
    e=dict(**TYPES,state='CONFIRMED_EXPANDING',pool='pool',evidence_id=1,cutoff=iso(now-timedelta(minutes=1)),recorded_at=iso(now))
    assert extension_allowed(p,e,now)
    for update in [dict(principal_recovered=0),dict(realized_proceeds_usd=4.99),dict(mark_liquidity_usd=999),dict(mark_pair_address='other'),dict(mark_observed_at=iso(now-timedelta(seconds=16)))]:
        assert not extension_allowed({**p,**update},e,now)
    assert not extension_allowed(p,{**e,'state':'UNKNOWN'},now)


def test_recovered_runner_extension_requires_verified_evidence_and_clear_safety():
    now=utcnow();position=dict(definition_version='v',token_id='bsc:token',shadow_cohort_id=1,principal_recovered=1,amount_raw='20',realized_proceeds_usd=5,stake_usd=5,mark_status='VISIBLE',mark_pair_address='pool',mark_liquidity_usd=2000,mark_price_usd=1,opened_at=iso(now-timedelta(minutes=30)),mark_observed_at=iso(now),mark_recorded_at=iso(now))
    evidence=dict(**TYPES,state='CONFIRMED_EXPANDING',pool='pool',evidence_id=1,cutoff=iso(now-timedelta(minutes=1)),recorded_at=iso(now))
    key='v:bsc:token:1';state={'overlay_enabled':True,'latest':{key:evidence}}
    safe=SimpleNamespace(behavior=lambda *a:{})
    store=SimpleNamespace(get_kv=lambda *a:state,_preentry_safety=safe)
    policy=dict(max_hold_minutes=30,entry_filter={'narrative_hold_v2':True})
    assert max_hold(store,position,policy,now)==60
    state['latest'][key]={**evidence,'state':'UNKNOWN'}
    assert max_hold(store,position,policy,now)==30
    state['latest'][key]=evidence;store._preentry_safety=SimpleNamespace(behavior=lambda *a:{'hard_veto':['risk']})
    assert max_hold(store,position,policy,now)==30


def test_persisted_sources_are_admitted_only_as_of_cutoff():
    now=utcnow();cutoff=now+timedelta(seconds=1)
    source=dict(source_evidence_id=1,scout_model='gpt-5.6-luna',url='https://example.test/news',published_at=iso(now-timedelta(seconds=1)),available_at=iso(now))
    assert pending_scout_leads({'leads':[source]},cutoff)==[source]
    assert pending_scout_leads({'leads':[{**source,'available_at':iso(cutoff)}]},cutoff)==[]
    assert pending_scout_leads({'leads':[{**source,'published_at':iso(now+timedelta(seconds=2))}]},cutoff)==[]


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
    n.state['latest'][case['id']]=dict(**TYPES,state='CONFIRMED_EXPANDING',pool='pool',cutoff=iso(clock[0]),recorded_at=iso(clock[0]),evidence_id=eid);n.save()
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
    calls=[]
    async def search(*a,**k):
        calls.append('scout');now[0]+=timedelta(seconds=1)
        return {'sources':ss},{'model':'gpt-5.6-luna','run_id':'scout','tokens_used':10}
    async def verify(**k):return {subject['subject_id']:dict(record_id=1,status='cross_source_supported',claim_status='confirmed_fact',confidence=.9,model='gpt-5.6-terra',tokens_used=10) for subject in k['subjects']}
    n.search=SimpleNamespace(_consume_quota=lambda *a:True,config={},_search=search,_record_tokens=lambda *a:None,_verify_fact_subjects=verify)
    case=dict(id='case',pool='pool',token_id='solana:A',leads=[],points={});token=TokenCandidate('solana','A','Example')
    asyncio.run(n.research(case,'0',token,[ARM],now[0]))
    assert case['previous']['state']=='UNKNOWN'
    assert any(kind=='sources' for kind,_,_ in records)
    assert all(s.get('source_evidence_id') for s in case['leads'])
    first=now[0]
    now[0]+=timedelta(minutes=12)
    case.update(opened_at=iso(first-timedelta(minutes=5)),value_research_started_at=iso(first),points={'value110:recovery':'COMPLETE'})
    position=dict(arm_id=ARM,principal_recovered=1,amount_raw='20',realized_proceeds_usd=5,stake_usd=5)
    mark=dict(pair_address='pool',status='VISIBLE',liquidity_usd=2000,price_usd=1,observed_at=iso(now[0]),recorded_at=iso(now[0]))
    assert value_checkpoint(case,[position],mark,now[0])[0]=='value110:1'
    assert value_checkpoint({**case,'leads':[]},[position],mark,now[0])[0] is None
    asyncio.run(n.research(case,'1',token,[ARM],now[0]))
    assert case['previous']['state']=='CONFIRMED_EXPANDING'
    assert n.state['actual_tokens']==20
    assert calls==['scout']
    assert records[-1][1]['research_mode']=='VERIFY_PERSISTED_SOURCES'


def test_latency_guard_disables_overlay_and_further_research():
    n=NarrativeHold.__new__(NarrativeHold);n.state={'overlay_enabled':True};n.save=lambda:None
    def timing(p95):return {'components':{'held_fetch':{'sample_count':30,'duration_seconds':{'p95':p95}}}}
    n.guard(timing(1),timing(1.4))
    assert n.state['overlay_enabled'] is False and n.state['research_paused'] is True


@pytest.mark.parametrize('role,expected',[('project_channel','project_channels_only'),('trading_call','promotion_trading_call_amplification'),('volume_tracker','promotion_trading_call_amplification')])
def test_project_and_trading_channels_never_extend(role,expected):
    now=utcnow();ss=[{**s,'source_type':role} for s in sources(now)]
    v=dict(status='cross_source_supported',claim_status='confirmed_fact',confidence=.99,model='gpt-5.6-terra')
    result=aggregate(ss,v,{},'solana:A',now)
    assert result['narrative_type']==expected and result['promotion_only'] is True
    assert result['state']!='CONFIRMED_EXPANDING' and result['independent_origin_count']==0


def test_real_event_news_can_be_separate_from_exact_community_binding():
    now=utcnow();news=[{**s,'binding':'unknown','content_basis':'Independent external event report'} for s in sources(now)]
    community={**sources(now)[0],'source_type':'community','url':'https://community.org/post','origin_id':'community'}
    v=dict(status='cross_source_supported',claim_status='confirmed_fact',confidence=.9,model='gpt-5.6-terra')
    r=aggregate(news+[community],v,{},'solana:A',now)
    assert r['state']=='CONFIRMED_EXPANDING' and r['independent_origin_count']==2
    assert r['diffusion_stage']=='independent_community_amplification'
    assert aggregate(news,v,{},'solana:A',now)['state']=='UNKNOWN'
    assert aggregate(news+[community],v,{},'solana:OtherCA',now)['state']=='UNKNOWN'
    assert aggregate(news+[{**community,'event_key':'different headline'}],v,{},'solana:A',now)['state']=='UNKNOWN'
    assert aggregate(news+[{**community,'source_type':'project_channel'}],v,{},'solana:A',now)['state']=='UNKNOWN'
    assert aggregate(news+[{**community,'verified_binding':False}],v,{},'solana:A',now)['state']=='UNKNOWN'


def test_legacy_untyped_confirmation_is_not_extension_authority():
    from memetrader.models import utcnow
    # Even a former CONFIRMED_EXPANDING needs the new typed evidence contract.
    now=utcnow()
    assert not extension_allowed({},dict(state='CONFIRMED_EXPANDING',evidence_id=1),now)


def test_existing_authoritative_event_can_trigger_research_but_not_hold(tmp_path):
    from memetrader.store import Store
    from memetrader.narrative_hold import authoritative_local_lead
    import json
    s=Store(tmp_path/'event.sqlite3',initial_cash_usd=1000);now=utcnow()
    case=dict(token_id='bsc:0x123',pool='pool',opened_at=iso(now-timedelta(minutes=3)),points={},leads=[])
    event=dict(chain='bsc',contract_address='0x123',source_kind='first_party',event_type='official_listing',
        published_at=iso(now-timedelta(minutes=1)),url='https://www.okx.com/help/listing')
    sql="INSERT INTO chain_meme_pattern_evidence(definition_version,token_id,pair_address,kind,source_key,observed_at,recorded_at,payload_json) VALUES(?,?,?,?,?,?,?,?)"
    s.db.execute(sql,('v',case['token_id'],'','authoritative_event','fixture',iso(now-timedelta(seconds=2)),iso(now-timedelta(seconds=1)),json.dumps(event)))
    lead=authoritative_local_lead(s.db,'v',case,now);assert lead['evidence_id']
    plan=s.db.execute("EXPLAIN QUERY PLAN SELECT id FROM chain_meme_pattern_evidence WHERE definition_version=? AND token_id=? AND pair_address='' AND kind='authoritative_event' ORDER BY id DESC LIMIT 8",('v',case['token_id'])).fetchall()
    assert any('chain_meme_pattern_evidence_lookup' in r[3] for r in plan)
    p=dict(arm_id=ARM,principal_recovered=0,amount_raw='10',realized_proceeds_usd=0,stake_usd=5)
    mark=dict(pair_address='pool',status='VISIBLE',liquidity_usd=2000,price_usd=1,observed_at=iso(now),recorded_at=iso(now))
    case['authoritative_lead']=lead
    assert value_checkpoint(case,[p],mark,now)==('event139:first','AUTHORITATIVE_EVENT_TRIGGERED')
    assert not extension_allowed(p,lead,now)
    assert authoritative_local_lead(s.db,'v',case,now-timedelta(seconds=1)) is None
    event['contract_address']='0x999';s.db.execute('UPDATE chain_meme_pattern_evidence SET payload_json=?',(json.dumps(event),))
    assert authoritative_local_lead(s.db,'v',case,now) is None
    s.close()
