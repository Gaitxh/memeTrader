"""Bounded prequential Paper-mode statistics; no acquisition or hindsight orders.

Predictions are frozen before labels. Endpoint proxies, sampled barrier order and
actual ledger outcomes remain separate. Only two preregistered selector releases
may alter future adaptive selections; ordinary strategies keep frozen contracts.
"""
from copy import deepcopy
from datetime import timedelta
from math import isfinite
import hashlib
import json
from .models import iso, parse_time
from .paper_execution import buy_terms, sell_terms

KEY='mode-learning144/v3'
HORIZONS=(5,15,60)
MAX_PENDING, MAX_GROUPS, MAX_RETURNS=128,256,256
BASELINE='fixed_priority/v1'
CANDIDATE='coverage_cost_aware/v1'


def initialize(state=None):
    if state and state.get('schema')==KEY:return state
    return dict(schema=KEY,episodes={},seen=[],groups={},events=[],counts={},recent=[],
        model=dict(version=BASELINE,cutoff_at=None,releases=0,selected_groups=[]),
        training_cursor=0,actual_pending={},actual_groups={},selections={})


def count(s,key,n=1):s['counts'][key]=s['counts'].get(key,0)+n


def event(s,kind,payload):
    s['training_cursor']+=1
    if len(s['events'])>=256:
        count(s,'event_capacity_skipped');return
    s['events'].append(dict(sequence=s['training_cursor'],kind=kind,**deepcopy(payload)))


def finite(x):
    if x is None or isinstance(x,bool):return None
    try:x=float(x)
    except (TypeError,ValueError):return None
    return x if isfinite(x) else None


def clocks(f,now):
    try:
        o,i,r=(parse_time(f[k]) for k in ('observed_at','ingested_at','recorded_at'))
        return (o,i,r) if o<=i<=r<=parse_time(now) else None
    except (KeyError,TypeError,ValueError):return None


def age_band(age):
    if finite(age) is None or age<0:return 'UNKNOWN'
    return '0_300' if age<300 else '300_900' if age<900 else '900_21600' if age<21600 else 'mature'


def summary(g):
    rows=g['returns'];values=[x['return'] for x in rows];n=len(values)
    total=sum(values);trim=sorted(values)[1:-1] if n>2 else []
    equity=peak=mdd=0.
    for value in values:
        equity+=value;peak=max(peak,equity);mdd=max(mdd,peak-equity)
    return dict(n=n,unique_tokens=len({x['token'] for x in rows}),dates=len({x['date'] for x in rows}),
        net_costed_return=total,mean=total/n if n else None,trimmed_mean=sum(trim)/len(trim) if trim else None,
        top1_removed=total-max(values) if values else None,top3_removed=total-sum(sorted(values)[-3:]) if n>=3 else None,
        sampled_equity_drawdown=mdd,catastrophic=sum(v<=-.5 for v in values),tail100=sum(v>=1 for v in values),
        unknown=g['unknown'],unknown_rate=g['unknown']/(n+g['unknown']) if n+g['unknown'] else 1.)


def predict(state,*,chain,age_bucket,mode,features,decision_at,observed_at,ingested_at,recorded_at):
    s=initialize(state);model=s['model'];f=dict(observed_at=observed_at,ingested_at=ingested_at,recorded_at=recorded_at)
    if not clocks(f,decision_at) or model['cutoff_at'] and parse_time(model['cutoff_at'])>parse_time(decision_at):
        return dict(status='NONCAUSAL',model_version=model['version'])
    key='|'.join((chain,age_bucket,mode,'5'))
    g=s['groups'].get(key);data=summary(g) if g else None
    return dict(status='LEARNED_MODE' if key in model['selected_groups'] else 'FIXED_BASELINE',
        model_version=model['version'],model_cutoff_at=model['cutoff_at'],group=key,estimate=data)


def capture(state,*,episode_key,token_id,pair_address,chain,age_bucket,mode,features,decision_at,
            observed_at,ingested_at,recorded_at,sample_probability=1.,signal=False,paper_terms=None):
    s=initialize(state);f=dict(observed_at=observed_at,ingested_at=ingested_at,recorded_at=recorded_at)
    c=clocks(f,decision_at)
    if not c or not 0<sample_probability<=1 or not (token_id and pair_address):return dict(state=s,status='INVALID')
    if episode_key in s['episodes'] or episode_key in s['seen']:return dict(state=s,status='already_captured')
    if len(s['episodes'])>=MAX_PENDING:count(s,'capacity_censored');return dict(state=s,status='pending_capacity')
    terms=paper_terms or dict(buy_slippage_rate=.04,sell_slippage_rate=.04,stake_usd=2.)
    costs=dict(buy_slippage_bps=round(terms.get('buy_slippage_rate',.04)*10000),
        sell_slippage_bps=round(terms.get('sell_slippage_rate',.04)*10000),
        additional_fee_usd_each_fill=terms.get('buy_fee_usd',0.),min_pool_liquidity_usd=terms.get('floor',1000.))
    prediction=predict(s,chain=chain,age_bucket=age_bucket,mode=mode,features=features,decision_at=decision_at,**f)
    e=dict(key=episode_key,token_id=token_id,pair_address=pair_address,chain=chain,age_bucket=age_bucket,
        mode=mode,signal=bool(signal),probability=sample_probability,features=deepcopy(features),
        decision_at=iso(parse_time(decision_at)),**f,prediction=prediction,costs=costs,
        stake=terms.get('stake_usd',2.),entry=None,last_recorded_at=None,gap=False,
        first_floor=None,first_hits={},results={},learned=[])
    s['episodes'][episode_key]=e;s['seen']=(s['seen']+[episode_key])[-4096:]
    count(s,'signals' if signal else 'sampled_no_signal');event(s,'prediction',e)
    return dict(state=s,status='captured',episode=e)


def finish(s,e,h,status,now,reason='',frame=None):
    if str(h) in e['results']:return None
    r=dict(horizon=h,status=status,available_at=iso(parse_time(now)),reason=reason,
        source='sampled_original_pool_cost_proxy',first_hits=deepcopy(e['first_hits']),first_floor=e['first_floor'],
        path_order_coverage='UNKNOWN' if e['gap'] else 'OBSERVED_SAMPLES_ONLY')
    if status=='OBSERVED':
        entry=e['entry'];terms=buy_terms(e['stake'],entry['price_usd'],e['costs'])
        net=sell_terms(terms['quantity_tokens'],frame['price_usd'],e['costs'])['net_usd']
        r.update(raw_return=frame['price_usd']/entry['price_usd']-1,
            costed_return=net/terms['total_cost_usd']-1,entry=entry,target=deepcopy(frame))
    e['results'][str(h)]=r;count(s,'horizon_'+status)
    event(s,'label',dict(episode_key=e['key'],mode=e['mode'],token_id=e['token_id'],pair_address=e['pair_address'],**r))
    return r


def expire(state,*,now,grace_seconds=90):
    s=initialize(state);now=parse_time(now);labels=[]
    for e in s['episodes'].values():
        if e['entry'] is None:
            if (now-parse_time(e['decision_at'])).total_seconds()>120:
                labels.extend(filter(None,(finish(s,e,h,'UNKNOWN',now,'NO_STRICT_ENTRY_WITHIN_120S') for h in HORIZONS)))
            continue
        start=parse_time(e['entry']['observed_at'])
        for h in HORIZONS:
            if now>start+timedelta(minutes=h,seconds=grace_seconds):
                r=finish(s,e,h,'UNKNOWN',now,'NO_NATURAL_ELIGIBLE_HORIZON');
                if r:labels.append(r)
    return dict(state=s,labels=labels)


def observe(state,*,episode_key,frame,now,liquidity_floor=1000.,max_gap_seconds=90,grace_seconds=90,**unused):
    s=initialize(state);e=s['episodes'].get(episode_key)
    if not e:return dict(state=s,status='unknown_episode',labels=[])
    c=clocks(frame,now)
    if not c or (frame.get('token_id'),frame.get('pair_address'))!=(e['token_id'],e['pair_address']):
        return dict(state=s,status='ignored_noncausal_or_identity',labels=[])
    prior=parse_time(e['last_recorded_at'] or e['decision_at'])
    if c[0]<=prior:return dict(state=s,status='ignored_noncausal_or_identity',labels=[])
    price,liq=finite(frame.get('price_usd')),finite(frame.get('liquidity_usd'))
    if e['entry'] is None:
        if (c[0]-parse_time(e['decision_at'])).total_seconds()>120:return expire(s,now=now)
        if price is None or price<=0 or liq is None or liq<liquidity_floor:return dict(state=s,status='ENTRY_UNKNOWN',labels=[])
        e['entry']={k:frame[k] for k in ('token_id','pair_address','observed_at','ingested_at','recorded_at','price_usd','liquidity_usd')}
        for key in ('receipt_source','processed_at'):
            if key in frame:e['entry'][key]=frame[key]
        count(s,'strict_entry')
    elif (c[0]-prior).total_seconds()>max_gap_seconds:e['gap']=True
    e['last_recorded_at']=iso(c[2]);labels=[]
    if liq is not None and 0<=liq<liquidity_floor and not e['first_floor']:
        e['first_floor']=dict(observed_at=iso(c[0]),recorded_at=iso(c[2]),liquidity_usd=liq)
    valid=price is not None and price>0 and liq is not None and liq>=liquidity_floor
    if valid:
        terms=buy_terms(e['stake'],e['entry']['price_usd'],e['costs'])
        ret=sell_terms(terms['quantity_tokens'],price,e['costs'])['net_usd']/terms['total_cost_usd']-1
        for key,hit in (('minus20',ret<=-.2),('plus30',ret>=.3),('plus100',ret>=1)):
            if hit and key not in e['first_hits']:e['first_hits'][key]=dict(observed_at=iso(c[0]),recorded_at=iso(c[2]),return_fraction=ret)
    for h in HORIZONS:
        elapsed=(c[0]-parse_time(e['entry']['observed_at'])).total_seconds()-h*60
        if str(h) in e['results'] or elapsed<0:continue
        reason='LATE_ENDPOINT' if elapsed>grace_seconds else 'PATH_GAP' if e['gap'] else 'FLOOR_OR_MISSING' if e['first_floor'] or not valid else ''
        r=finish(s,e,h,'UNKNOWN' if reason else 'OBSERVED',now,reason,frame)
        if r:labels.append(r)
    return dict(state=s,status='observed',labels=labels)


def train(state,*,cutoff_at,minimum_group_samples=20,max_candidates=2):
    s=initialize(state);cutoff=parse_time(cutoff_at);consumed=0
    for eid,e in list(s['episodes'].items()):
        for horizon,label in e['results'].items():
            if horizon in e['learned'] or parse_time(label['available_at'])>cutoff:continue
            key='|'.join((e['chain'],e['age_bucket'],e['mode'],horizon))
            if key not in s['groups'] and len(s['groups'])>=MAX_GROUPS:count(s,'group_capacity_skipped');e['learned'].append(horizon);continue
            g=s['groups'].setdefault(key,dict(returns=[],unknown=0))
            if label['status']=='OBSERVED':
                g['returns']=(g['returns']+[dict(key=eid,token=e['token_id'],date=e['decision_at'][:10],
                    return_=label['costed_return'])])[-MAX_RETURNS:]
                g['returns'][-1]['return']=g['returns'][-1].pop('return_')
            else:g['unknown']+=1
            e['learned'].append(horizon);consumed+=1
        if len(e['learned'])==len(HORIZONS):
            s['recent']=(s['recent']+[dict(key=eid,mode=e['mode'],results=e['results'],prediction=e['prediction'])])[-64:]
            del s['episodes'][eid]
    eligible=[]
    for key,g in s['groups'].items():
        m=summary(g)
        actual=s['actual_groups'].get(key.split('|')[2],[])
        actual_ready=len(actual)>=5 and len({r['token_id'] for r in actual})>=3 and sum(r['realized_pnl_usd'] for r in actual)>=0
        # Fixed conservative release gate; not a threshold search or profit proof.
        if actual_ready and key.endswith('|5') and m['n']>=minimum_group_samples and m['unique_tokens']>=10 and m['dates']>=2 and m['unknown_rate']<=.25 and m['top3_removed']>0 and m['sampled_equity_drawdown']<=.5*m['n']:
            eligible.append((m['top3_removed']/m['n'],key))
    chosen=[key for _,key in sorted(eligible,reverse=True)[:min(2,max_candidates)]]
    model=s['model'];promoted=False
    if chosen and chosen!=model['selected_groups'] and model['releases']<2:
        model=dict(version=f'{CANDIDATE}/release{model["releases"]+1}',cutoff_at=iso(cutoff),
            releases=model['releases']+1,selected_groups=chosen,selection_scores={k:summary(s['groups'][k])['mean'] for k in chosen})
        s['model']=model;promoted=True;event(s,'model_release',model)
    count(s,'learned_labels',consumed)
    return dict(state=s,model=deepcopy(model),consumed=consumed,promoted=promoted,candidates=chosen)


def choose(state,signals,features,now):
    from .trajectory144 import ARMS
    available=[a for a in (ARMS[4],ARMS[2],ARMS[0],ARMS[1]) if a in signals]
    if not available:return None
    model=state['model'];chosen=available[0];rule=BASELINE
    if model['cutoff_at'] and parse_time(model['cutoff_at'])<parse_time(now):
        prefix=features['chain']+'|'+age_band(features.get('pool_age_seconds'))+'|'
        learned=[(model.get('selection_scores',{}).get(prefix+a+'|5',0),a) for a in available if prefix+a+'|5' in model['selected_groups']]
        if learned:chosen=max(learned)[1];rule=model['version']
    key=signals[chosen]['decision_key']+'|'+ARMS[5]
    prior=state.setdefault('selections',{}).get(key)
    if prior:return deepcopy(prior) if (parse_time(now)-parse_time(prior['recorded_at'])).total_seconds()<=60 else None
    sig=deepcopy(signals[chosen]);sig['decision_key']=key;sig['recorded_at']=iso(parse_time(now))
    sig['decision_evidence'].update(learning_source_arm=chosen,learning_model=deepcopy(model),learning_selection=rule,router_mode=chosen,selection_recorded_at=sig['recorded_at'])
    state['selections'][key]=deepcopy(sig)
    if len(state['selections'])>256:state['selections'].pop(next(iter(state['selections'])))
    return sig


def bounded_historical_mature_rows(db,definition_version,cutoff_at,*,limit=128):
    if not 1<=limit<=512:raise ValueError('bounded limit')
    # Global integer highwater tail first: no full-period sort/scans.
    rows=db.execute("SELECT id,definition_version,arm_id,shadow_cohort_id,recorded_at FROM chain_meme_trader_trades WHERE id>(SELECT COALESCE(MAX(id),0)-? FROM chain_meme_trader_trades) AND side IN ('SELL','WRITEOFF') AND definition_version=? AND recorded_at<=? ORDER BY id DESC",(limit*16,definition_version,cutoff_at)).fetchall()
    output=[];seen=set()
    for r in rows:
        if (r['arm_id'],r['shadow_cohort_id']) in seen:continue
        seen.add((r['arm_id'],r['shadow_cohort_id']))
        p=db.execute("SELECT p.shadow_cohort_id,p.arm_id,p.token_id,p.stake_usd,p.realized_pnl_usd,p.status,p.closed_at,c.decided_at,c.pair_address,c.feature_json FROM chain_meme_trader_positions p JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id WHERE p.definition_version=? AND p.arm_id=? AND p.shadow_cohort_id=? AND p.status IN ('closed','written_off') AND p.closed_at<=?",(definition_version,r['arm_id'],r['shadow_cohort_id'],cutoff_at)).fetchone()
        if p:output.append({**dict(p),'terminal_receipt_id':r['id'],'terminal_recorded_at':r['recorded_at']})
        if len(output)>=limit:break
    return dict(rows=output,cutoff_at=cutoff_at,limit=limit,basis='bounded_actual_terminal_receipts_reference_only')


class Coordinator:
    """One bounded consumer on existing passive/Store callbacks; no timer or I/O in quotes."""
    def __init__(self,store):
        self.store=store;self.key=KEY+':'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        self.state=initialize(store.get_kv(self.key,None));self.last_flush=0.

    def signals(self,features,signals,now):
        from .trajectory144 import ARMS
        output=dict(signals);output.pop(ARMS[5],None)
        f=features;chain=f['chain'];band=age_band(f.get('pool_age_seconds'))
        costs=getattr(self.store,'_chain_paper_execution',{})
        terms=dict(buy_slippage_rate=costs.get('buy_slippage_bps',400)/10000,
            sell_slippage_rate=costs.get('sell_slippage_bps',400)/10000,
            buy_fee_usd=costs.get('additional_fee_usd_each_fill',0.),stake_usd=2.,floor=costs.get('min_pool_liquidity_usd',1000.))
        sources={a:s for a,s in output.items() if a in (ARMS[0],ARMS[1],ARMS[2],ARMS[4])}
        if not sources:
            key='no_signal:'+f['token_id']+':'+f['pair_address']+':'+str(int(parse_time(now).timestamp())//900)
            if int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%16==0:
                sources={'NO_SIGNAL':dict(decision_key=key,observed_at=f['observed_at'],recorded_at=f['recorded_at'])}
        for arm,sig in sources.items():
            key=sig['decision_key']
            captured=capture(self.state,episode_key=key,token_id=f['token_id'],pair_address=f['pair_address'],chain=chain,
                age_bucket=band,mode=arm,features=f,decision_at=now,observed_at=sig['observed_at'],
                ingested_at=sig.get('decision_evidence',{}).get('feature_vector',{}).get('ingested_at',f['ingested_at']),
                recorded_at=sig['recorded_at'],sample_probability=1/16 if arm=='NO_SIGNAL' else 1.,signal=arm!='NO_SIGNAL',paper_terms=terms)
            if arm in output:
                output[arm]=deepcopy(output[arm]);output[arm]['decision_evidence']['learning_episode_key']=key
                e=self.state['episodes'].get(key)
                if e:output[arm]['decision_evidence']['learning_prediction']=deepcopy(e['prediction'])
        selected=choose(self.state,output,f,now)
        if selected:output[ARMS[5]]=selected
        if ARMS[3] in output and ARMS[0] in output:
            output[ARMS[3]]['decision_evidence']['learning_episode_key']=output[ARMS[0]]['decision_key']
        return output

    def observe(self,token_id,snapshot,ingested,recorded,*,processed_at=None,source='snapshot'):
        from .models import canonical_token_address
        pair=snapshot.raw.get('pair',snapshot.raw) if snapshot.raw else {}
        base=(pair.get('baseToken') or {}).get('address')
        if (snapshot.token_id!=token_id
                or pair.get('chainId') and str(pair['chainId']).lower()!=snapshot.chain
                or base and canonical_token_address(snapshot.chain,base)!=snapshot.address):
            count(self.state,'callback_identity_rejected');return
        pool=canonical_token_address(snapshot.chain,str(pair.get('pairAddress') or ''))
        processed_at=processed_at or recorded
        frame=dict(token_id=token_id,pair_address=pool,observed_at=iso(snapshot.observed_at),
            ingested_at=iso(ingested),recorded_at=iso(recorded),price_usd=snapshot.price_usd,
            liquidity_usd=snapshot.liquidity_usd,receipt_source=source,processed_at=iso(parse_time(processed_at)))
        count(self.state,'callback_'+source+'_frames')
        for key,e in list(self.state['episodes'].items()):
            if (e['token_id'],e['pair_address'])==(token_id,pool):
                had_entry=e['entry'] is not None
                result=observe(self.state,episode_key=key,frame=frame,now=processed_at,liquidity_floor=e['costs']['min_pool_liquidity_usd'])
                count(self.state,'callback_'+source+'_'+result.get('status','expired'))
                if not had_entry and e['entry'] is not None:count(self.state,'callback_'+source+'_entry')
                if result['labels']:count(self.state,'callback_'+source+'_labels',len(result['labels']))

    def record_buy(self,version,arm,cohort,token,fill,at):
        key=arm+':'+str(cohort)
        if len(self.state['actual_pending'])<128:
            self.state['actual_pending'][key]=dict(version=version,arm=arm,cohort=cohort,token_id=token,source_fill_id=fill,opened_at=at)
        else:count(self.state,'actual_capacity_censored')
        count(self.state,'actual_BUY')

    def resolve_actual(self,now):
        for key,row in list(self.state['actual_pending'].items())[:8]:
            p=self.store.db.execute('SELECT status,closed_at,close_reason,stake_usd,realized_pnl_usd FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?', (row['version'],row['arm'],row['cohort'])).fetchone()
            if not p or p['status'] not in ('closed','written_off') or parse_time(p['closed_at'])>parse_time(now):
                self.state['actual_pending'][key]=self.state['actual_pending'].pop(key);continue
            evidence={**row,**dict(p), 'available_at':iso(parse_time(now)), 'source':'actual_Paper_terminal_ledger'}
            self.state['actual_groups'].setdefault(row['arm'],[])
            self.state['actual_groups'][row['arm']]=(self.state['actual_groups'][row['arm']]+[evidence])[-256:]
            event(self.state,'actual_terminal',evidence);count(self.state,'actual_terminal')
            del self.state['actual_pending'][key]

    def flush(self,now):
        s=self.state;self.resolve_actual(now);expire(s,now=now);learn=train(s,cutoff_at=now)
        # The persisted model is released only at this real transaction frontier.
        with self.store._lock,self.store.db:
            if learn['promoted']:
                s['model']['snapshot_frontier']=self.store.db.execute('SELECT COALESCE(MAX(id),0) FROM token_snapshots').fetchone()[0]
            for row in s['events'][:64]:
                token=row.get('token_id','');pool=row.get('pair_address','')
                self.store.db.execute('INSERT OR IGNORE INTO chain_meme_pattern_evidence(definition_version,token_id,pair_address,kind,source_key,observed_at,recorded_at,payload_json) VALUES(?,?,?,?,?,?,?,?)',
                    (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,token,pool,'mode_learning144_'+row['kind'],
                     str(row['sequence']),iso(parse_time(row.get('observed_at') or row.get('available_at') or now)),iso(parse_time(now)),json.dumps(row,ensure_ascii=False)))
            s['events']=s['events'][64:]
            self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
                (self.key,json.dumps(s,ensure_ascii=False),iso(parse_time(now))))
        return dict(pending=len(s['episodes']),counts=s['counts'],model=s['model'],learned=learn['consumed'],event_pending=len(s['events']),extra_requests=0)
