"""Prospective event/clone/reawakening Shadow. No trading or network authority."""
from copy import deepcopy
import math
from .models import iso, parse_time, utcnow, canonical_token_address
from .event_candidates import freeze_event_candidates
from .cohort_experiments import freeze_clone_episode, evaluate_clone_consensus_leader_entry

ARM='event_clone_narrative_reawakening_v1'
KEY='event-clone-narrative99'
# Proposed contract only; Shadow never registers/funds or settles this policy.
EXIT_CONTRACT={'notional_usd':5,'max_concurrent_positions':4,'hard_stop_pct':20,
    'trailing_activation_pct':30,'trailing_drawdown_pct':15,'max_hold_minutes':30,
    'principal_recovery':'actual_net_debit_only_when_raw_fraction_le_half',
    'extension':'actual_principal_recovered_and_healthy_and_96B_confirmed_expanding_only'}

def freeze(event, candidates, *, now, activated_at, existing=None):
    """One immutable event episode; caller supplies already verified local evidence."""
    if existing is not None:return deepcopy(existing)
    out={'arm_id':ARM,'decision_eligible':False,'affects':'none','state':'WAIT',
         'reason':'event_confirmation_missing','event_key':event.get('event_key'),
         'frozen_at':iso(now),'event_recorded_at':event.get('recorded_at'),'event_evidence_id':event.get('evidence_id')}
    try:
        valid=(event.get('confirmed') is True and event.get('novelty') is True
            and event.get('promotion_only') is False and event.get('independent_origins',0)>=2
            and event.get('evidence_id') and event.get('event_key')
            and parse_time(activated_at)<=parse_time(event['recorded_at'])<=now
            and parse_time(event['published_at'])<=parse_time(event['observed_at'])<=parse_time(event['recorded_at']))
    except (KeyError,ValueError,TypeError):valid=False
    if not valid:return out
    rows=list(candidates)
    if not 1<=len(rows)<=25:return {**out,'reason':'bounded_candidate_set_missing'}
    exact=event.get('exact_token_id') if event.get('verified_binding') is True else None
    if exact:
        matches=[r for r in rows if r['token_id']==exact]
        # Multiple pools are not resolved by an Agent or a later winner.
        if len(matches)!=1:return {**out,'reason':'exact_binding_pool_ambiguous'}
        target=matches[0]
        out.update(mode='A',target=deepcopy(target))
    else:
        no_ca={**event,'identity_status':'no_exact_ca','contract_address':None,
               'ingested_at':event['recorded_at']}
        _,reason,search=freeze_event_candidates(no_ca,rows,query=event.get('query',''),frozen_at=now)
        if not search:return {**out,'reason':reason}
        action,reason,clone,_=freeze_clone_episode(rows,episode_id=event['event_key'],decision_at=now,activated_at=activated_at)
        if action!='FROZEN':return {**out,'reason':reason,'candidate_set':search}
        out.update(mode='B',candidate_set=search,clone=clone)
        p=clone['payload']
        if not p['leaders_overlap']:return {**out,'reason':'no_unique_joint_consensus'}
        out['target']=deepcopy(p['liquidity_leader'])
    # Freeze may only consume an already available market frame.
    t=out['target']
    try:
        if not parse_time(activated_at)<=parse_time(t['observed_at'])<=parse_time(t['recorded_at'])<=now:
            return {**out,'reason':'candidate_clock_invalid'}
    except (KeyError,TypeError,ValueError):return {**out,'reason':'candidate_clock_invalid'}
    return {**out,'state':'FROZEN','reason':'await_strict_original_pool_confirmation'}

def advance(case, frame, *, now, activated_at, rediscovery=None, reawakening_ready=False, safety=None):
    result=deepcopy(case)
    if case['state'] not in {'FROZEN','SIGNAL'}:return result
    target=case['target'];after=parse_time(case.get('signal_recorded_at',case['frozen_at']))
    try:
        valid=(frame['token_id']==target['token_id'] and frame['pair_address']==target['pair_address']
            and frame.get('original_pool') is True and math.isfinite(frame['price_usd']) and frame['price_usd']>0
            and math.isfinite(frame['liquidity_usd']) and frame['liquidity_usd']>=1000
            and after<parse_time(frame['observed_at'])<=parse_time(frame['ingested_at'])<=parse_time(frame['recorded_at'])<=now
            and (now-parse_time(frame['observed_at'])).total_seconds()<=30)
    except (KeyError,ValueError,TypeError):valid=False
    if not valid:return {**result,'reason':'wait_fresh_exact_pool_three_clocks'}
    if case['state']=='FROZEN':
        if case['mode']=='B' and evaluate_clone_consensus_leader_entry(case['clone'],frame,
                decision_at=now,activated_at=activated_at)[0]!='SELECT':
            return {**result,'reason':'wait_frozen_consensus_confirmation'}
        if rediscovery is not None:
            if not (rediscovery['token_id']==target['token_id'] and
                    parse_time(case['event_recorded_at'])<=parse_time(rediscovery['recorded_at'])<parse_time(frame['observed_at']) and reawakening_ready):
                return {**result,'reason':'wait_new_rediscovery_and_reawakening_confirmation'}
            result.update(mode='C',rediscovery_evidence_id=rediscovery['id'])
        elif frame.get('lifecycle')=='mature':
            return {**result,'reason':'wait_dormant_episode_for_old_token'}
        return {**result,'state':'SIGNAL','reason':'shadow_signal_requires_safety_and_later_frame','signal_recorded_at':iso(now)}
    # Shadow never asks the security worker to spend requests or simulates a fill.
    if not safety:return {**result,'reason':'WAIT_SECURITY_NO_EXISTING_ASOF_ASSESSMENT'}
    if safety.get('pool')!=target['pair_address'] or safety.get('token_id')!=target['token_id']:
        return {**result,'reason':'WAIT_SECURITY_IDENTITY'}
    if not (after<=parse_time(safety['source_at'])<parse_time(frame['observed_at']) and
            (now-parse_time(safety['source_at'])).total_seconds()<=45):
        return {**result,'reason':'WAIT_SECURITY_CLOCK'}
    if safety.get('allow') and safety.get('scope_checked') is not True:
        return {**result,'reason':'WAIT_COMMON_SCOPE_ASSESSMENT'}
    return {**result,'state':'SHADOW_READY' if safety.get('allow') else 'VETOED',
            'reason':'not_a_fill_no_funded_registration','safety':deepcopy(safety),'next_frame_recorded_at':frame['recorded_at']}

class EventCloneShadow:
    """32 live episodes, existing callbacks only; bounded KV/checkpoint flush."""
    def __init__(self,store):
        self.store=store
        self.state=store.get_kv(KEY,None) or {'activated_at':iso(),'cases':{},'rediscoveries':{},'counts':{},'recent':[],
            'decision_eligible':False,'affects':'none','status':'SHADOW_DATA_BLOCKED'}
        self.dirty=False
    def count(self,reason):
        c=self.state['counts'];c[reason]=c.get(reason,0)+1;self.dirty=True
    def receive(self,kind,payload,token_id,pool,eid,at):
        if kind=='rediscovery_episode':
            self.state['rediscoveries'][token_id]={'id':eid,'token_id':token_id,'recorded_at':iso(at)}
            while len(self.state['rediscoveries'])>128:self.state['rediscoveries'].pop(next(iter(self.state['rediscoveries'])))
            self.count('rediscovery_received');return
        if kind not in {'narrative_hold_result_v2','authoritative_no_ca_candidate_set','narrative'}:return
        self.count(kind+'_received')
        # Existing listing freezes/legacy CA mentions lack independent event novelty.
        if kind!='narrative_hold_result_v2':
            self.count('WAIT_INDEPENDENT_EVENT_NOVELTY');return
        p=payload;v=p.get('verifier') or {}
        confirmed=(p.get('narrative_type')=='real_event_novelty' and p.get('promotion_only') is False
            and p.get('independent_origin_count',0)>=2 and p.get('event_key')
            and v.get('model')=='gpt-5.6-terra' and v.get('status')=='cross_source_supported'
            and v.get('claim_status') in {'confirmed_fact','probable_report'}
            and p.get('state') not in {'CONTRADICTED','UNKNOWN','STALE_OR_PROMOTION'})
        if not confirmed:self.count('WAIT_VERIFIED_EVENT_BINDING');return
        if p.get('token_binding_basis')!='verified_exact_contract_frozen_cohort':
            self.count('WAIT_FROZEN_EVENT_LINK');return
        sources=[s for s in p.get('scout_sources',[]) if s.get('event_key')==p['event_key'] and s.get('published_at') and s.get('available_at')
            and parse_time(s['published_at'])<=parse_time(s['available_at'])<=parse_time(p['cutoff'])]
        if not sources:self.count('WAIT_SOURCE_CLOCKS');return
        key=p['event_key']+'|'+token_id+'|'+pool
        if key in self.state['cases']:return
        if len(self.state['cases'])>=32:self.count('SKIP_CAPACITY');return
        # Captures receipt now; first future market callback freezes identity/pool.
        self.state['cases'][key]={'state':'WAIT_MARKET','event':{'confirmed':True,'novelty':True,
            'promotion_only':False,'independent_origins':p['independent_origin_count'],'event_key':p['event_key'],
            'evidence_id':eid,'published_at':min(s['published_at'] for s in sources),'observed_at':iso(at),'recorded_at':iso(at),
            'verified_binding':p.get('token_binding_basis')=='verified_exact_contract_frozen_cohort','exact_token_id':token_id},
            'token_id':token_id,'pool':pool,'received_at':iso(at)}
        self.count('verified_event_received')
    def frame(self,token,snapshot,recorded_at,features):
        if not self.state['cases']:return
        now=parse_time(recorded_at);pair=(snapshot.raw or {}).get('pair') or {}
        row={'token_id':token.token_id,'chain':token.chain,'address':token.address,'pair_address':canonical_token_address(token.chain,pair.get('pairAddress','')),
            'name':token.name,'symbol':token.symbol,'normalized_symbol':token.symbol,'original_pool':bool(pair.get('chainId')==token.chain and canonical_token_address(token.chain,(pair.get('baseToken') or {}).get('address',''))==token.address),
            'lifecycle':'mature' if pair.get('pairCreatedAt') and (now.timestamp()*1000-float(pair['pairCreatedAt']))>=3600000 else 'new_pool',
            'observed_at':iso(snapshot.observed_at),'ingested_at':iso(snapshot.ingested_at) if snapshot.ingested_at else None,
            'recorded_at':iso(now),'price_usd':snapshot.price_usd,'liquidity_usd':snapshot.liquidity_usd}
        for key,case in list(self.state['cases'].items()):
            if case.get('token_id')!=token.token_id or case.get('pool')!=row['pair_address']:continue
            prior=(case['state'],case.get('reason'))
            if case['state']=='WAIT_MARKET':
                result=freeze(case['event'],[row],now=now,activated_at=self.state['activated_at'])
            else:
                safety=getattr(self.store,'_preentry_safety',None)
                cached=safety.cache.get((token.token_id,row['pair_address'])) if safety else None
                result=advance(case,row,now=now,activated_at=self.state['activated_at'],
                    rediscovery=self.state['rediscoveries'].get(token.token_id),
                    reawakening_ready=bool(features.get('reactivation_ready')),safety=cached)
            case.update(result)
            if prior!=(case['state'],case.get('reason')):
                self.count(case['state']+':'+case.get('reason',''))
                self.state['recent']=(self.state['recent']+[{'event_key':key,'state':case['state'],'reason':case.get('reason'),'at':iso(now)}])[-32:]
    def freeze_market_set(self,event,candidates,at):
        # Original no-CA collector has not independently verified novelty. Persist
        # this waiting outcome, never borrow later winner/binding knowledge.
        result=freeze(event,candidates,now=at,activated_at=self.state['activated_at'])
        self.count('no_ca:'+result['reason'])
        if result['state']=='FROZEN':
            target=result['target'];key=result['event_key']+'|'+target['token_id']+'|'+target['pair_address']
            if key not in self.state['cases'] and len(self.state['cases'])<32:
                self.state['cases'][key]={**result,'token_id':target['token_id'],'pool':target['pair_address'],'received_at':iso(at)}
        self.state['recent']=(self.state['recent']+[result])[-32:]
    def flush(self):
        now=utcnow()
        for key,case in list(self.state['cases'].items()):
            if (now-parse_time(case['received_at'])).total_seconds()>1800:
                self.state['cases'].pop(key);self.count('EXPIRED_NO_BACKFILL')
        if self.dirty:
            self.state['updated_at']=iso(now)
            self.store.record_chain_meme_pattern_evidence('', '', KEY,
                {'decision_eligible':False,'affects':'none','counts':dict(self.state['counts']),
                 'recent':deepcopy(self.state['recent']),'active_cases':len(self.state['cases'])},
                observed_at=now,source_key=KEY+':'+iso(now))
            self.store.set_kv(KEY,self.state);self.dirty=False
