"""Versioned finite learner. Recipes, sampled endpoints and real fills stay distinct."""
from copy import deepcopy
import hashlib
import json
from . import mode_learning144 as old
from .models import iso, parse_time

KEY='mode-learning145/v4'
HORIZONS=(5,15,30,60)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def initialize(state=None,*,now,contract):
    if state and state.get('schema')==KEY:return state
    s=old.initialize();s.update(schema=KEY,horizons=list(HORIZONS),activated_at=iso(parse_time(now)),
        contract=deepcopy(contract),contract_hash=digest(contract),group_summaries={},dispositions={},
        previous_models=[],rollback_history=[],dirty_groups=[],actual_frontier=0)
    return s


def statistics(group):
    events=group['events'];returns=[r for r in events if r['status']=='OBSERVED']
    result=old.summary({'returns':returns,'unknown':sum(r['status']!='OBSERVED' for r in events)})
    result.update(mature_episodes=len(events),floor_events=sum(r['status']=='MODEL_FLOOR_EVENT' for r in events))
    return result


def rollback(s,*,reason,frontier,now,target='previous_valid_or_baseline'):
    previous=next((m for m in reversed(s['previous_models']) if valid_model(m,s['contract_hash'])),None)
    selected=deepcopy(previous) if previous and target!='baseline' else dict(version=old.BASELINE,
        cutoff_at=None,selected_groups=[],selection_scores={},releases=s['model'].get('releases',0))
    receipt=dict(from_version=s['model']['version'],to_version=selected['version'],reason=reason,
        observation_frontier=frontier,recorded_at=iso(parse_time(now)),affects='new_orders_only')
    s['model']=selected;s['rollback_history']=(s['rollback_history']+[receipt])[-32:]
    old.event(s,'model_rollback',receipt)
    return receipt


def valid_model(model,contract_hash):
    if model.get('version')==old.BASELINE:return True
    fields={k:v for k,v in model.items() if k not in ('seal','snapshot_frontier')}
    return bool(model.get('contract_hash')==contract_hash and model.get('seal')==digest(fields))


def train(s,*,cutoff_at,limit=64):
    cutoff=parse_time(cutoff_at);consumed=0;dirty=set()
    for eid,e in list(s['episodes'].items()):
        for horizon,label in e['results'].items():
            if consumed>=min(64,limit):break
            if horizon in e['learned'] or parse_time(label['available_at'])>cutoff:continue
            key='|'.join((e['chain'],e['age_bucket'],e['mode'],horizon))
            if key not in s['groups'] and len(s['groups'])>=256:
                old.count(s,'group_capacity_skipped');e['learned'].append(horizon);continue
            group=s['groups'].setdefault(key,{'events':[]})
            group['events']=(group['events']+[dict(key=eid,token=e['token_id'],date=e['decision_at'][:10],
                status=label['status'],return_=label.get('costed_return'))])[-256:]
            group['events'][-1]['return']=group['events'][-1].pop('return_')
            e['learned'].append(horizon);consumed+=1;dirty.add(key)
        if len(e['learned'])==len(HORIZONS):
            s['recent']=(s['recent']+[dict(key=eid,mode=e['mode'],results=e['results'],prediction=e['prediction'])])[-64:]
            del s['episodes'][eid]
    for key in dirty:
        m=statistics(s['groups'][key]);s['group_summaries'][key]=m
        missing=[name for name,ok in (('20_observed',m['n']>=20),('10_tokens',m['unique_tokens']>=10),
            ('2_dates',m['dates']>=2),('coverage_75pct',m['unknown_rate']<=.25),
            ('positive_costed_mean',(m['mean'] or 0)>0),('drawdown_bound',m['sampled_equity_drawdown']<=.5*m['n'])) if not ok]
        s['dispositions'][key]={'status':'ECONOMIC_REVIEW_ELIGIBLE' if not missing else 'INSUFFICIENT',
            'missing':missing,'frontier':s['training_cursor'],'concentration':{'top1_removed':m['top1_removed'],'top3_removed':m['top3_removed']}}
    promoted=False
    if consumed and s.get('contract_valid',True):
        candidates=[k for k,d in s['dispositions'].items() if not d['missing'] and k.endswith('|5')]
        chosen=sorted(candidates,key=lambda k:(s['group_summaries'][k]['mean'],k),reverse=True)[:2]
        if chosen and chosen!=s['model']['selected_groups']:
            scores={k:s['group_summaries'][k]['mean'] for k in chosen}
            model=dict(version='finite/v4:'+digest([s['training_cursor'],s['contract_hash'],scores])[:16],
                cutoff_at=iso(cutoff),training_frontier=s['training_cursor'],contract_hash=s['contract_hash'],
                selected_groups=chosen,selection_scores=scores,releases=s['model'].get('releases',0)+1,
                estimates={k:deepcopy(s['group_summaries'][k]) for k in chosen})
            model['seal']=digest(model)
            s['previous_models']=(s['previous_models']+[deepcopy(s['model'])])[-2:]
            s['model']=model;promoted=True;old.event(s,'model_release',model)
    old.count(s,'learned_labels',consumed)
    return {'consumed':consumed,'promoted':promoted,'dirty_groups':len(dirty)}


class Coordinator(old.Coordinator):
    def __init__(self,store):
        from .models import utcnow
        from .trajectory144 import VERSION
        self.store=store;self.key=KEY+':'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        self.legacy=old.Coordinator(store)  # Only drain already captured v3 work; no new v3 predictions.
        contract={'feature':VERSION,'costs':deepcopy(getattr(store,'_chain_paper_execution',{})),'horizons':list(HORIZONS)}
        self.state=initialize(store.get_kv(self.key,None),now=utcnow(),contract=contract);self.last_flush=0.
        self.state['contract_valid']=self.state['contract_hash']==digest(contract)
        if not self.state['contract_valid'] or not valid_model(self.state['model'],self.state['contract_hash']):
            rollback(self.state,reason='INPUT_OR_MODEL_CONTRACT_INVALID',frontier=self.state['training_cursor'],now=utcnow(),target='baseline')
        self.reindex()

    def capture_episode(self,**kwargs):
        if (not self.state.get('contract_valid',True) or parse_time(kwargs['decision_at'])<parse_time(self.state['activated_at'])
                or len(self.state['episodes'])+len(self.legacy.state['episodes'])>=128):
            old.count(self.state,'capacity_or_contract_wait');return {'status':'pending_capacity'}
        return super().capture_episode(**kwargs)

    def observe(self,*args,**kwargs):
        first_event=len(self.state['events'])
        super().observe(*args,**kwargs)
        if self.legacy.state['episodes']:self.legacy.observe(*args,**kwargs)
        # Reclassify newly generated known floor events, never as real Paper fills.
        for event in self.state['events'][first_event:]:
            if event.get('kind')=='label' and event.get('status')=='UNKNOWN' and event.get('first_floor'):
                event['status']='MODEL_FLOOR_EVENT';event['source']='sampled_model_floor_event_not_fill'
                e=self.state['episodes'].get(event['episode_key'])
                if e:e['results'][str(event['horizon'])].update(status=event['status'],source=event['source'])

    def classify_floor_labels(self):
        for e in self.state['episodes'].values():
            if not e.get('first_floor'):continue
            for label in e['results'].values():
                if label['status']=='UNKNOWN':label.update(status='MODEL_FLOOR_EVENT',source='sampled_model_floor_event_not_fill')
        for event in self.state['events']:
            if event.get('kind')=='label' and event.get('status')=='UNKNOWN' and event.get('first_floor'):
                event.update(status='MODEL_FLOOR_EVENT',source='sampled_model_floor_event_not_fill')

    def record_buy(self,version,arm,cohort,token,fill,at):
        super().record_buy(version,arm,cohort,token,fill,at)
        row=self.store.db.execute('SELECT feature_json,pair_address FROM chain_meme_trader_v6_cohorts WHERE id=?',(cohort,)).fetchone()
        p=self.state['actual_pending'].get(arm+':'+str(cohort))
        if p and row:
            signal=json.loads(row['feature_json']).get('cohort_signals',{}).get(arm,{})
            evidence=signal.get('decision_evidence',{})
            p.update(model_version=(evidence.get('learning_model') or {}).get('version',old.BASELINE),
                source_arm=evidence.get('learning_source_arm',arm),pair_address=row['pair_address'])

    def record_valuation(self,arm,cohort,mfe,drawdown):
        p=self.state['actual_pending'].get(arm+':'+str(cohort))
        if p is not None:
            if mfe is not None:p['observed_costed_mfe']=max(p.get('observed_costed_mfe',mfe),mfe)
            if drawdown is not None:p['observed_max_drawdown']=min(p.get('observed_max_drawdown',drawdown),drawdown)

    def resolve_actual(self,now):
        before=self.state['counts'].get('actual_terminal',0);super().resolve_actual(now)
        fresh=self.state['counts'].get('actual_terminal',0)-before
        if not fresh:return
        self.state['actual_frontier']+=fresh
        from .trajectory144 import ARMS
        pairs=[]
        for r in self.state['actual_groups'].get(ARMS[5],[]):
            if r.get('model_version')!=self.state['model']['version']:continue
            base=next((b for b in self.state['actual_groups'].get(r.get('source_arm'),[]) if
                (b['source_fill_id'],b['token_id'],b.get('pair_address'))==(r['source_fill_id'],r['token_id'],r.get('pair_address'))),None)
            if base:pairs.append((r,base))
        if (self.state['model']['version']!=old.BASELINE and len(pairs)>=10 and len({r['token_id'] for r,b in pairs})>=3
                and sum(r['realized_pnl_usd'] for r,b in pairs)<0
                and sum(r['realized_pnl_usd']-b['realized_pnl_usd'] for r,b in pairs)<0):
            rollback(self.state,reason='POST_RELEASE_MATCHED_ECONOMIC_FAILURE',frontier=self.state['actual_frontier'],now=now)

    def flush(self,now):
        s=self.state
        if self.legacy.state['episodes'] or self.legacy.state['actual_pending']:self.legacy.flush(now)
        if not valid_model(s['model'],s['contract_hash']):rollback(s,reason='MODEL_INVALID',frontier=s['training_cursor'],now=now,target='baseline')
        self.resolve_actual(now);old.expire(s,now=now);self.classify_floor_labels();learn=train(s,cutoff_at=now);self.reindex()
        events=s['events'][:64]
        with self.store._lock,self.store.db:
            for r in events:
                self.store.db.execute('INSERT OR IGNORE INTO chain_meme_pattern_evidence(definition_version,token_id,pair_address,kind,source_key,observed_at,recorded_at,payload_json) VALUES(?,?,?,?,?,?,?,?)',
                    (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,r.get('token_id',''),r.get('pair_address',''),'mode_learning145_'+r['kind'],
                     str(r['sequence']),iso(parse_time(r.get('observed_at') or r.get('available_at') or now)),iso(parse_time(now)),json.dumps(r)))
            s['events']=s['events'][len(events):]
            self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',(self.key,json.dumps(s),iso(parse_time(now))))
        manager=getattr(self.store,'_recipe145',None)
        if manager:
            for r in events:
                if r['kind']=='actual_terminal':manager.terminal(r,now)
            manager.flush(now)
        horizons={}
        for key,m in s['group_summaries'].items():
            h=key.split('|')[-1];tot=horizons.setdefault(h,dict(OBSERVED=0,UNKNOWN=0,MODEL_FLOOR_EVENT=0))
            tot['OBSERVED']+=m['n'];tot['UNKNOWN']+=m['unknown']-m['floor_events'];tot['MODEL_FLOOR_EVENT']+=m['floor_events']
        return dict(schema=KEY,activated_at=s['activated_at'],pending=len(s['episodes']),counts=s['counts'],horizons=horizons,
            model=s['model'],last_update=iso(parse_time(now)),learned=learn['consumed'],dirty_groups=learn['dirty_groups'],
            event_pending=len(s['events']),extra_requests=0,unique_episodes=len(s['seen']),
            dispositions=s['dispositions'],rollback_history=s['rollback_history'],baseline_reason='FIXED_BASELINE_NO_RELEASE' if s['model']['version']==old.BASELINE else None)
