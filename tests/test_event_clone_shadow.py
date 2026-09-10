from datetime import timedelta
from copy import deepcopy
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.event_clone_shadow import freeze,advance,EventCloneShadow
from test_cohort_experiments import _candidate

def fixture():
    now=utcnow();activated=now-timedelta(hours=1)
    rows=[_candidate(now,i) for i in range(5)]
    for r in rows:
        r.update(chain='solana',address=r['token_id'].split(':')[1],name='clone',symbol='clone',ingested_at=r['recorded_at'])
    event=dict(confirmed=True,novelty=True,promotion_only=False,independent_origins=2,event_key='news-1',evidence_id=5,
        published_at=iso(now-timedelta(seconds=4)),observed_at=iso(now-timedelta(seconds=3)),recorded_at=iso(now-timedelta(seconds=2)),
        source='independent',url='https://example.org/event',title='real event',query='clone')
    return now,activated,rows,event

def test_a_confirmation_next_frame_then_safety_then_later_frame():
    now,activated,rows,event=fixture();event.update(exact_token_id=rows[0]['token_id'],verified_binding=True)
    case=freeze(event,rows[:1],now=now,activated_at=activated)
    assert case['state']=='FROZEN' and case['mode']=='A'
    frame={**rows[0],'observed_at':iso(now+timedelta(seconds=1)),'ingested_at':iso(now+timedelta(seconds=1)), 'recorded_at':iso(now+timedelta(seconds=2))}
    signal=advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated)
    assert signal['state']=='SIGNAL'
    assert advance(signal,frame,now=now+timedelta(seconds=2),activated_at=activated)['state']=='SIGNAL'
    frame.update(observed_at=iso(now+timedelta(seconds=4)),ingested_at=iso(now+timedelta(seconds=4)),recorded_at=iso(now+timedelta(seconds=5)))
    assert 'WAIT_SECURITY' in advance(signal,frame,now=now+timedelta(seconds=5),activated_at=activated)['reason']
    safe=dict(allow=True,token_id=rows[0]['token_id'],pool=rows[0]['pair_address'],source_at=iso(now+timedelta(seconds=3)),scope_checked=True)
    result=advance(signal,frame,now=now+timedelta(seconds=5),activated_at=activated,safety=safe)
    assert result['state']=='SHADOW_READY' and result['decision_eligible'] is False
    safe['allow']=False
    assert advance(signal,frame,now=now+timedelta(seconds=5),activated_at=activated,safety=safe)['state']=='VETOED'

def test_b_joint_leader_frozen_no_later_winner_or_tie():
    now,activated,rows,event=fixture()
    assert freeze(event,rows,now=now,activated_at=activated)['reason']=='no_unique_joint_consensus'
    rows[4]['volume_5m_usd']=9000
    case=freeze(event,rows,now=now,activated_at=activated)
    assert case['mode']=='B' and case['target']['token_id']==rows[4]['token_id']
    changed=deepcopy(rows);changed[0]['liquidity_usd']=1e9
    assert freeze(event,changed,now=now,activated_at=activated,existing=case)==case
    frame={**rows[4],'observed_at':iso(now+timedelta(seconds=1)),'ingested_at':iso(now+timedelta(seconds=1)),'recorded_at':iso(now+timedelta(seconds=2))}
    assert advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated)['state']=='SIGNAL'
    rows[3]['volume_5m_usd']=9000
    assert freeze(event,rows,now=now,activated_at=activated)['state']=='WAIT'

def test_c_requires_new_episode_and_existing_reawakening():
    now,activated,rows,event=fixture();event.update(exact_token_id=rows[0]['token_id'],verified_binding=True)
    rows[0]['lifecycle']='mature'
    case=freeze(event,rows[:1],now=now,activated_at=activated)
    frame={**rows[0],'observed_at':iso(now+timedelta(seconds=1)),'ingested_at':iso(now+timedelta(seconds=1)),'recorded_at':iso(now+timedelta(seconds=2))}
    assert advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated)['state']=='FROZEN'
    episode=dict(id=9,token_id=rows[0]['token_id'],recorded_at=iso(now))
    assert advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated,rediscovery=episode)['state']=='FROZEN'
    assert advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated,rediscovery=episode,reawakening_ready=True)['mode']=='C'

def test_unverified_future_promotion_and_wrong_pool_never_signal():
    now,activated,rows,event=fixture()
    for key,value in [('confirmed',False),('novelty',False),('promotion_only',True),('recorded_at',iso(now+timedelta(seconds=1)))]:
        bad={**event,key:value};assert freeze(bad,rows,now=now,activated_at=activated)['state']=='WAIT'
    event.update(exact_token_id=rows[0]['token_id'],verified_binding=True)
    case=freeze(event,rows[:1],now=now,activated_at=activated)
    frame={**rows[0],'pair_address':'OTHER','observed_at':iso(now+timedelta(seconds=1)),'ingested_at':iso(now+timedelta(seconds=1)),'recorded_at':iso(now+timedelta(seconds=2))}
    assert advance(case,frame,now=now+timedelta(seconds=2),activated_at=activated)['state']=='FROZEN'

def test_observer_bounded_callbacks_and_no_authority():
    class Store:
        def __init__(self):self.saved=[]
        def get_kv(self,*args):return None
        def set_kv(self,*args):self.saved.append(args)
        def record_chain_meme_pattern_evidence(self,*args,**kwargs):self.saved.append(args)
    store=Store();shadow=EventCloneShadow(store)
    for i in range(140):shadow.receive('rediscovery_episode',{},'solana:'+str(i),'',i,utcnow())
    shadow.receive('narrative_hold_result_v2',{'state':'UNKNOWN'},'solana:x','p',141,utcnow())
    assert len(shadow.state['rediscoveries'])==128 and not shadow.state['cases']
    shadow.flush();assert len(store.saved)==2
    shadow.flush();assert len(store.saved)==2

def test_receive_accepts_persisted_scout_provenance_and_exposes_only_fresh_signal():
    class Store:
        def get_kv(self,*args):return None
    shadow=EventCloneShadow(Store());now=utcnow()
    candidate=_candidate(now,0);token_id=candidate['token_id'];pool=candidate['pair_address']
    address=token_id.split(':',1)[1]
    source=dict(url='https://example.org/event',event_key='news-1',published_at=iso(now-timedelta(seconds=8)),
        available_at=iso(now-timedelta(seconds=4)),source_evidence_id=41,scout_model='gpt-5.6-luna')
    # VERIFY_PERSISTED_SOURCES intentionally has no fresh Scout metadata: the
    # source record itself carries the original Scout model, evidence id, and clocks.
    result=dict(state='CONFIRMED_EXPANDING',narrative_type='real_event_novelty',promotion_only=False,
        independent_origin_count=2,event_key='news-1',token_binding_basis='verified_exact_contract_frozen_cohort',
        cutoff=iso(now-timedelta(seconds=1)),research_mode='VERIFY_PERSISTED_SOURCES',scout_metadata={},
        scout_sources=[source],verifier=dict(model='gpt-5.6-terra',status='cross_source_supported',
        claim_status='confirmed_fact',confidence=.9))
    shadow.receive('narrative_hold_result_v2',result,token_id,pool,99,now)
    assert len(shadow.state['cases'])==1
    class Snapshot:
        def __init__(self,at):
            self.observed_at=at;self.ingested_at=at;self.price_usd=1;self.liquidity_usd=2000
            self.raw={'pair':{'pairAddress':pool,'chainId':'solana','baseToken':{'address':address}}}
    token=TokenCandidate('solana',address,'Example')
    shadow.frame(token,Snapshot(now+timedelta(seconds=1)),now+timedelta(seconds=2),{})
    assert next(iter(shadow.state['cases'].values()))['state']=='FROZEN'
    shadow.frame(token,Snapshot(now+timedelta(seconds=3)),now+timedelta(seconds=4),{})
    signals=shadow.signals_for(token_id,pool,now+timedelta(seconds=4))
    signal=signals['event_clone_narrative_reawakening_v1']
    assert signal['episode_id']=='news-1' and signal['decision_evidence']['event_evidence_id']==99
    assert signal['decision_evidence']['event_recorded_at']==iso(now)
    assert shadow.signals_for(token_id,pool,now+timedelta(seconds=34))=={}

def test_live_store_callback_once_on_insert_and_same_admission_contract(tmp_path):
    from memetrader.store import Store
    store=Store(tmp_path/'shadow99.sqlite3',initial_cash_usd=1000)
    shadow=EventCloneShadow(store);store._event_clone_shadow=shadow
    now=utcnow()
    one=store.record_chain_meme_pattern_evidence('solana:X','','rediscovery_episode',{},observed_at=now,source_key='same')
    two=store.record_chain_meme_pattern_evidence('solana:X','','rediscovery_episode',{},observed_at=now,source_key='same')
    assert one==two and shadow.state['counts']['rediscovery_received']==1
    assert store.db.execute('select count(*) from chain_meme_trader_trades').fetchone()[0]==0
    shadow.flush()
    assert store.get_kv('event-clone-narrative99')['decision_eligible'] is False
