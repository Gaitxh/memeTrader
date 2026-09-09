"""Active-period, append-only narrative checkpoints on the existing agent runner."""
import asyncio, json, uuid, math
from copy import deepcopy
from datetime import timedelta
from urllib.parse import urlparse
from .models import utcnow, iso, parse_time

KEY='narrative-hold/v2'
ARM='narrative_hold_recovered_runner_v2'

def exact_binding(source, token_id):
    address=token_id.split(':',1)[-1]
    text=str(source.get('content_basis') or '')
    if not token_id.startswith('solana:'):address,text=address.lower(),text.lower()
    return source.get('token_id')==token_id and source.get('binding')=='exact_contract' and address in text

def extension_allowed(position, evidence, now):
    p=dict(position)
    try:
        return bool(evidence and evidence.get('state')=='CONFIRMED_EXPANDING'
            and evidence.get('evidence_id') and evidence.get('pool')==p['mark_pair_address']
            and parse_time(evidence['cutoff'])<=parse_time(evidence['recorded_at'])<=now
            and (now-parse_time(evidence['recorded_at'])).total_seconds()<=2400
            and p['principal_recovered']==1 and int(p['amount_raw'])>0
            and p['realized_proceeds_usd']>=p['stake_usd']>0
            and p['mark_status']=='VISIBLE' and p['mark_liquidity_usd']>=1000
            and math.isfinite(p['mark_price_usd']) and p['mark_price_usd']>0
            and parse_time(p['opened_at'])<=parse_time(p['mark_observed_at'])<=parse_time(p['mark_recorded_at'])<=now
            and (now-parse_time(p['mark_observed_at'])).total_seconds()<=15)
    except (KeyError,TypeError,ValueError):return False

def max_hold(store, position, policy, now):
    base=float(policy.get('max_hold_minutes') or 240.)
    if not policy.get('entry_filter',{}).get('narrative_hold_v2'):return base
    state=store.get_kv(KEY,{})
    key=f"{position['definition_version']}:{position['token_id']}:{position['shadow_cohort_id']}"
    evidence=state.get('latest',{}).get(key)
    if not state.get('overlay_enabled') or not extension_allowed(position,evidence,now):return base
    safety=getattr(store,'_preentry_safety',None)
    if safety is None:return base
    risk=safety.behavior({'token_id':position['token_id'],'pool':position['mark_pair_address']},now)
    if risk.get('hard_veto') or risk.get('soft_hazard'):return base
    return max(base,60.)

def policy(parent):
    p=deepcopy(parent)
    for k in ('stage','entry_paused','entry_pause_reason','runtime_addition_id'):p.pop(k,None)
    p.update(arm_id=ARM,canonical_id=ARM,name='本金已回收·叙事验证Runner',notional_usd=5.,
        source_arm_ids=[parent['arm_id']],dynamic_principal_recovery='minimum_net_debit_next_frame/v2',
        description='相同池龄入场；真实回本后仅经持久化独立叙事验证延长soft hold，未验证盈利。')
    p.pop('paired_entry_group',None);p.pop('paired_entry_size',None)
    p['entry_filter']={**p.get('entry_filter',{}),'max_concurrent_positions':4,'narrative_hold_v2':True}
    return p

def aggregate(sources, verification, previous, token_id, cutoff):
    """Only prior-locally-available, exact-bound independently checked novelty."""
    status=verification.get('status');claim=verification.get('claim_status')
    if status in ('contradicted','conflicted') or claim in ('false_claim','correction','retraction','impersonation'):
        return {'state':'CONTRADICTED','origins':[]}
    if claim in ('promotion','satire'):
        return {'state':'STALE_OR_PROMOTION','origins':[]}
    good=[]
    for s in sources:
        try:valid=(exact_binding(s,token_id)
            and parse_time(s['published_at'])<=cutoff and parse_time(s['available_at'])<=cutoff
            and s.get('novelty') is True and not s.get('promotion_only')
            and s.get('origin_id') and s.get('verified_origin') is True)
        except (KeyError,TypeError,ValueError):valid=False
        if valid:good.append(s)
    origins=sorted({s['origin_id'] for s in good});platforms=sorted({urlparse(s['url']).netloc for s in good})
    prior=set((previous or {}).get('origins',[]));new=set(origins)-prior
    confirmed=(previous is not None and status=='cross_source_supported'
        and claim in ('confirmed_fact','probable_report') and float(verification.get('confidence') or 0)>=.8
        and len(origins)>=2 and len(platforms)>=2 and len(new)>=1
        and str(verification.get('model','')).startswith('gpt-5.6-terra'))
    state='CONFIRMED_EXPANDING' if confirmed else 'EMERGING' if origins else 'UNKNOWN'
    if previous and not new and previous.get('origins'):state='STALE_OR_PROMOTION'
    return {'state':state,'origins':origins,'new_origins':len(new),'platform_count':len(platforms)}

class NarrativeHold:
    def __init__(self,runtime):
        self.r=runtime;self.store=runtime.store;self.search=runtime.autonomous_search
        self.state=self.store.get_kv(KEY,None)
        if not self.state:
            frontier=self.store.db.execute('SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_trades').fetchone()[0]
            self.state={'started_at':iso(),'cursor':frontier,'cases':{},'latest':{},'day':'','calls':0,'reserved_tokens':0,'overlay_enabled':True}
        profiles=self.search.config.setdefault('profiles',{})
        profiles.setdefault('fact_verifier',{'model':'gpt-5.6-terra','reasoning_effort':'low','fallback_models':[]})
        for case in self.state['cases'].values():
            for cp,status in list(case['points'].items()):
                if status=='DISPATCHED':
                    case['points'][cp]='RUNTIME_INTERRUPTED'
                    self.record(case,'skip',{'checkpoint':cp,'reason':'RUNTIME_INTERRUPTED'},utcnow())
        # Shared execution slots remain owned by AutonomousSearch; V2 runs one case at a time.
        row=self.store.db.execute("SELECT policy_json FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id='resource_age_rate_candidate_v1'",(self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,)).fetchone()
        if row and not self.store.db.execute('SELECT 1 FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?',(self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,ARM)).fetchone():
            self.store.append_chain_meme_trader_policy(policy(json.loads(row[0])),activated_at=utcnow())
        self.save()

    def save(self):self.store.set_kv(KEY,self.state)
    def record(self,case,kind,payload,at):
        return self.store.record_chain_meme_pattern_evidence(case['token_id'],case['pool'],'narrative_hold_'+kind+'_v2',
            {'decision_eligible':False,'affects':'observer_only','case':case['id'],**payload},observed_at=at,source_key=case['id']+':'+kind+':'+payload.get('checkpoint','case'))

    def collect(self):
        rows=self.store.db.execute('SELECT id,definition_version,shadow_cohort_id,token_id,side,created_at FROM chain_meme_trader_trades WHERE id>? ORDER BY id LIMIT 256',(self.state['cursor'],)).fetchall()
        for row in rows:
            self.state['cursor']=row['id']
            if row['side']!='BUY' or row['definition_version']!=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION:continue
            key=f"{row['definition_version']}:{row['token_id']}:{row['shadow_cohort_id']}"
            if key in self.state['cases']:continue
            if self.store.db.execute('SELECT 1 FROM chain_meme_pattern_evidence WHERE definition_version=? AND kind=? AND source_key=?',
                (row['definition_version'],'narrative_hold_case_v2',key+':case:case')).fetchone():continue
            p=self.store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=? AND shadow_cohort_id=? LIMIT 1',(row['definition_version'],row['token_id'],row['shadow_cohort_id'])).fetchone()
            if not p:continue
            cohort=self.store.db.execute('SELECT pair_address FROM chain_meme_trader_v6_cohorts WHERE id=?',(row['shadow_cohort_id'],)).fetchone()
            case={'id':key,'token_id':row['token_id'],'cohort_id':row['shadow_cohort_id'],'pool':cohort[0] if cohort else '',
                'opened_at':p['opened_at'],'points':{},'leads':[],'first_buy_id':row['id']}
            self.record(case,'case',{'opened_at':p['opened_at'],'first_buy_id':row['id']},utcnow())
            if len(self.state['cases'])<128:self.state['cases'][key]=case
            else:self.record(case,'skip',{'checkpoint':'capacity','reason':'CASE_CAPACITY'},utcnow())
        if rows:self.save()

    async def once(self):
        if not self.r._chain_meme_active_idle().is_set():return
        self.collect();now=utcnow();day=now.date().isoformat()
        if self.state['day']!=day:self.state.update(day=day,calls=0,reserved_tokens=0,actual_tokens=0)
        for key,case in list(self.state['cases'].items()):
            positions=self.store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND token_id=? AND shadow_cohort_id=? AND status='open'",(self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,case['token_id'],case['cohort_id'])).fetchall()
            if not positions:
                self.record(case,'skip',{'checkpoint':'closed','reason':'NO_OPEN_POSITION'},now)
                self.state['cases'].pop(key);self.state['latest'].pop(key,None);self.save();continue
            elapsed=(now-parse_time(case['opened_at'])).total_seconds()
            for i,(due,grace) in enumerate(((150,90),(720,180),(2700,900))):
                cp=str(i)
                if cp in case['points'] or elapsed<due:continue
                arms=[p['arm_id'] for p in positions]
                previous=case.get('previous')
                new_local=any(parse_time(s['available_at'])>parse_time(previous['cutoff']) for s in case['leads']) if previous else bool(case['leads'])
                reason=None
                if elapsed>due+grace:reason='START_WINDOW_MISSED'
                elif not any(('age_rate' in a or 'reawakening' in a or 'clone' in a or a==ARM or 'principal_recovery' in a) for a in arms):reason='FAMILY_PRIORITY_SKIP'
                elif i and not (previous and previous.get('state') in ('EMERGING','CONFIRMED_EXPANDING') or new_local):reason='NO_NEW_LOCAL_EVIDENCE'
                elif not self.search.enabled:reason='AGENTS_DISABLED'
                elif self.state.get('research_paused'):reason='LATENCY_GUARD_PAUSED'
                elif self.state['calls']>=4 or max(self.state['reserved_tokens'],self.state.get('actual_tokens',0))+60000>240000:reason='DAILY_BUDGET'
                token=self.store.token(case['token_id'])
                mark=self.store.db.execute('SELECT * FROM chain_meme_trader_market_marks WHERE token_id=?',(case['token_id'],)).fetchone()
                # Existing market marks are only a cheap local research selection filter.
                if not token:reason='TOKEN_UNAVAILABLE'
                if not mark or mark['status']!='VISIBLE' or not mark['liquidity_usd'] or mark['liquidity_usd']<1000 or (now-parse_time(mark['observed_at'])).total_seconds()>30:
                    reason='LOCAL_MARK_NOT_HEALTHY'
                if self.search._profile('token_context')['model']!='gpt-5.6-luna' or self.search._profile('fact_verifier')['model']!='gpt-5.6-terra':reason='MODEL_POLICY_UNVERIFIED'
                if reason:
                    case['points'][cp]=reason;self.record(case,'skip',{'checkpoint':cp,'reason':reason,'cutoff':iso(now)},now);self.save();continue
                if not self.r._chain_meme_active_idle().is_set():return
                case['points'][cp]='DISPATCHED';self.state['calls']+=1;self.state['reserved_tokens']+=60000
                self.record(case,'checkpoint',{'checkpoint':cp,'cutoff':iso(now),'arms':arms,'models':{'scout':self.search._profile('token_context'),'verifier':self.search._profile('fact_verifier')}},now);self.save()
                baseline=self.r.runtime_timing.snapshot() if hasattr(self.r,'runtime_timing') else {}
                worker=asyncio.create_task(self.research(case,cp,token,arms,now))
                try:
                    while not worker.done():
                        await asyncio.wait([worker],timeout=5)
                        after=self.r.runtime_timing.snapshot() if hasattr(self.r,'runtime_timing') else {}
                        self.guard(baseline,after)
                    await worker
                finally:
                    if not worker.done():worker.cancel()
                self.save()
                return

    def guard(self,baseline,after):
        reason=None
        for component in ('held_fetch','held_apply_exit'):
            a=baseline.get('components',{}).get(component,{})
            b=after.get('components',{}).get(component,{})
            before=a.get('duration_seconds',{}).get('p95');post=b.get('duration_seconds',{}).get('p95')
            if a.get('sample_count',0)>=20 and b.get('sample_count',0)>=20 and before and post and post>before+min(before*.25,.25):reason='LATENCY_GUARD:'+component
        if after.get('passive_queue',{}).get('dropped_batches',0)>baseline.get('passive_queue',{}).get('dropped_batches',0):reason='PASSIVE_DROP_GUARD'
        if reason and self.state.get('overlay_enabled'):
            self.state.update(overlay_enabled=False,research_paused=True,overlay_disabled_reason=reason,overlay_disabled_at=iso())
            self.save()

    async def research(self,case,cp,token,arms,cutoff):
        run=uuid.uuid4().hex;result={'state':'UNKNOWN','origins':[]};metadata={};verified={};payload={}
        try:
            if not self.search._consume_quota('token_context',int(self.search.config.get('context_search_daily_limit',384))):raise ValueError('SHARED_SCOUT_QUOTA')
            prompt=('Read-only postbuy narrative research. No trade authority. Exact token '+token.token_id+' '+str(token.name)+' '+str(token.symbol)+
                '. Checkpoint cutoff '+iso(cutoff)+'. Use <=3 live web searches, public news/X/metadata only; no paid API. '
                'Never infer endorsement from same name or affiliation. Identify corrections/retractions/impersonation/promotion and copied origins. '
                'Return JSON {event_found:bool,claim:string,sources:[{url,published_at,token_id,binding:"exact_contract|unknown",'
                'origin_id,novelty:bool,promotion_only:bool,public_figure_catalyst,endorsement_evidence,X_address_cashtag_KOL,amplification,content_basis}]}. '
                'content_basis must contain a short verbatim exact-contract binding excerpt from the public source; omit exact_contract if the source does not explicitly bind this address. '
                'At most6 sources. Unknown timestamps/binding stay unknown. No future publication beyond cutoff. Previously available leads (untrusted): '+json.dumps(case['leads'][-6:])+
                ' Local metadata links are only unverified hints: '+json.dumps([dict(r) for r in self.store.token_source_links(token.token_id,limit=6)],default=str))
            def admitted():
                if not self.r._chain_meme_active_idle().is_set():raise ValueError('CORE_BUSY_AT_AGENT_ADMISSION')
            payload,metadata=await self.search._search(prompt,'token_context',run_id=run,on_started=admitted);self.search._record_tokens('token_context',metadata)
            self.state['actual_tokens']=self.state.get('actual_tokens',0)+int(metadata.get('tokens_used') or 30000)
            eligible=[s for s in case['leads'] if s.get('published_at') and parse_time(s['published_at'])<=cutoff and parse_time(s['available_at'])<=cutoff][:6]
            fresh=[]
            for source in (payload.get('sources') or [])[:6]:
                try:
                    if urlparse(source.get('url','')).scheme not in ('https','http') or parse_time(source['published_at'])>cutoff:continue
                except (ValueError,TypeError,KeyError):continue
                bounded={k:(v[:1500] if isinstance(v,str) else v) for k,v in source.items()
                    if k in ('url','published_at','token_id','binding','origin_id','novelty','promotion_only','public_figure_catalyst','endorsement_evidence','X_address_cashtag_KOL','amplification','content_basis') and isinstance(v,(str,bool,int,float,type(None)))}
                fresh.append({**bounded,'available_at':iso(utcnow())})
            if eligible and self.r._chain_meme_active_idle().is_set() and not self.state.get('research_paused') and self.state['actual_tokens']+30000<=240000:
                subject={'subject_id':run,'subject_kind':'token_context','title':token.token_id,
                    'claim':'As-of '+iso(cutoff)+': exact contract '+token.token_id+' has genuinely novel independently-originated propagation. Independently verify the exact address appears and is bound in each source, not just the scout excerpt. No name/affiliation endorsement inference. Check the stored source excerpts only up to cutoff, never later edits. '+json.dumps(eligible),
                    'sources':eligible}
                v=await self.search._verify_fact_subjects(parent_task='token_context',parent_run_id=run,subjects=[subject],requested_at=cutoff,on_started=admitted)
                verified=v.get(run,{})
                self.state['actual_tokens']+=int(verified.get('tokens_used') or 30000)
                record=self.store.db.execute('SELECT evidence_json FROM agent_fact_verifications WHERE id=?',(verified.get('record_id'),)).fetchone()
                proof=json.loads(record[0]) if record else {}
                supported={s['url'] for s in proof.get('sources',[]) if s.get('stance')=='supports' and s.get('origin_relationship')=='distinct_origin'}
                eligible=[{**s,'verified_origin':s['url'] in supported} for s in eligible]
                result=aggregate(eligible,verified,case.get('previous'),token.token_id,cutoff)
                if metadata.get('model')!='gpt-5.6-luna':result={'state':'UNKNOWN','origins':[],'reason':'SCOUT_MODEL_UNVERIFIED'}
            if fresh:
                source_id=self.record(case,'sources',{'checkpoint':cp,'cutoff':iso(cutoff),'sources':fresh,'scout_run_id':run},utcnow())
                for s in fresh:s['source_evidence_id']=source_id
            by_url={s['url']:s for s in case['leads']}
            for s in fresh:by_url.setdefault(s['url'],s)
            case['leads']=list(by_url.values())[-12:]
        except Exception as exc:result['error']=type(exc).__name__+':'+str(exc)[:160]
        completed=utcnow();result.update(checkpoint=cp,cutoff=iso(cutoff),completed_at=iso(completed),scout_run_id=run,scout_metadata=metadata,scout_sources=case['leads'],verifier=verified,arms=arms)
        eid=self.record(case,'result',result,completed)
        case['points'][cp]='COMPLETE';case['previous']={k:result[k] for k in ('state','origins','cutoff')}
        self.state['latest'][case['id']]={'state':result['state'],'recorded_at':iso(completed),'cutoff':iso(cutoff),'evidence_id':eid,'pool':case['pool']}
        self.save()
