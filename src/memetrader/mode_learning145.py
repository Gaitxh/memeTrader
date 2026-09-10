"""Versioned finite learner. Recipes, sampled endpoints and real fills stay distinct."""
from copy import deepcopy
import hashlib
import json
import math
from . import mode_learning144 as old
from .models import iso, parse_time
from .trajectory144 import ARMS,VERSION

KEY='mode-learning146/v5'
HORIZONS=(5,15,30,60)
ROUTER='trajectory146_learned_mode_selector_v1'
MODES=(ARMS[0],ARMS[1],ARMS[2],ARMS[4])
UTILITY='fixed_full_position_costed_endpoint_or_known_floor_minus1/v1'


def policy(base):
    p=deepcopy(base)
    p.update(arm_id=ROUTER,canonical_id=ROUTER,entry_family=ROUTER,name='独立在线学习·含池底损失模式选择',
        signal_origin_clock='learning_activation_at',learning_schema=KEY,
        description='2U/max2独立前向学习实验；无有效模型走已有固定优先级基线。仅允许已实现模式，含已知池底全损代理，UNKNOWN删失；不改变317。',
        model_contract=KEY+': '+UTILITY+'; rolling256;20observed/10tokens/2dates/coverage75%; fixed baseline or sealed causal model; rollback needs fresh same-group evidence',
        entry_rules144='从实际第二波/承接/早龄/稀疏HOT信号择一；只用已封存的可用模型，未发布时固定优先级；严格后帧和统一安全。')
    p['entry_filter']={**p['entry_filter'],'direction':ROUTER}
    return p


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def initialize(state=None,*,now,contract):
    if state and state.get('schema')==KEY:return state
    contract={**deepcopy(contract),'economic_semantics':UTILITY}
    s=old.initialize();s.update(schema=KEY,horizons=list(HORIZONS),activated_at=iso(parse_time(now)),
        contract=deepcopy(contract),contract_hash=digest(contract),group_summaries={},dispositions={},
        previous_models=[],rollback_history=[],dirty_groups=[],actual_frontier=0)
    return s


def statistics(group):
    events=group['events'];returns=[r for r in events if r['status']=='OBSERVED']
    floors=sum(r['status']=='MODEL_FLOOR_EVENT' for r in events)
    model_returns=[{**r,'return':-1. if r['status']=='MODEL_FLOOR_EVENT' else r['return']}
        for r in events if r['status'] in ('OBSERVED','MODEL_FLOOR_EVENT')]
    result=old.summary({'returns':model_returns,'unknown':len(events)-len(model_returns)})
    result.update(mature_episodes=len(events),floor_events=floors,endpoint_observed=len(returns),
        endpoint_conditional_mean=sum(r['return'] for r in returns)/len(returns) if returns else None,
        policy_model_mean=result['mean'],policy_model_n=len(model_returns),
        floor_rate=floors/len(events) if events else None,economic_semantics=UTILITY)
    return result


def rollback(s,*,reason,frontier,now,target='previous_valid_or_baseline'):
    rejected={r['from_version'] for r in s['rollback_history']}|{s['model']['version']}
    previous=next((m for m in reversed(s['previous_models']) if m['version'] not in rejected and valid_model(m,s['contract_hash'])),None)
    for group in s['model'].get('selected_groups',[]):
        s.setdefault('release_blocks',{})[group]={'recorded_at':iso(parse_time(now)),
            'label_frontier':s.get('group_label_frontiers',{}).get(group,0),'actual_frontier':s.get('actual_frontier',0)}
        s['dispositions'][group]={'status':'ROLLBACK_WAIT_FRESH_EVIDENCE','missing':['fresh_post_rollback_group_sample']}
    selected=deepcopy(previous) if previous and target!='baseline' else dict(version=old.BASELINE,
        cutoff_at=None,selected_groups=[],selection_scores={},releases=s['model'].get('releases',0))
    receipt=dict(from_version=s['model']['version'],to_version=selected['version'],reason=reason,
        selected_groups=list(s['model'].get('selected_groups',[])),observation_frontier=frontier,
        actual_frontier=s.get('actual_frontier',0),recorded_at=iso(parse_time(now)),affects='new_orders_only')
    s['model']=selected;s['rollback_history']=(s['rollback_history']+[receipt])[-32:]
    old.event(s,'model_rollback',receipt)
    return receipt


def valid_model(model,contract_hash):
    if model.get('version')==old.BASELINE:return True
    fields={k:v for k,v in model.items() if k not in ('seal','snapshot_frontier')}
    return bool(str(model.get('version','')).startswith('finite/v5:')
        and model.get('contract_hash')==contract_hash and model.get('seal')==digest(fields))


def known_floor_label(e,label,h):
    floor=label.get('first_floor')
    return bool(e and e.get('entry') and floor
        and parse_time(floor['recorded_at'])<=parse_time(label['available_at'])
        and 0<(parse_time(floor['observed_at'])-parse_time(e['entry']['observed_at'])).total_seconds()<=int(h)*60+90)


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
                status=label['status'],return_=label.get('costed_return'),decision_at=e['decision_at'],
                anchor_at=(e.get('entry') or {}).get('observed_at',e['decision_at']),available_at=label['available_at'])])[-256:]
            group['events'][-1]['return']=group['events'][-1].pop('return_')
            s.setdefault('group_label_frontiers',{})[key]=s.get('group_label_frontiers',{}).get(key,0)+1
            s.setdefault('group_last_label_at',{})[key]=max(s.get('group_last_label_at',{}).get(key,''),label['available_at'])
            e['learned'].append(horizon);consumed+=1;dirty.add(key)
        if len(e['learned'])==len(HORIZONS):
            s['recent']=(s['recent']+[dict(key=eid,mode=e['mode'],results=e['results'],prediction=e['prediction'])])[-64:]
            del s['episodes'][eid]
    for key in dirty:
        m=statistics(s['groups'][key]);s['group_summaries'][key]=m
        block=s.get('release_blocks',{}).get(key)
        if block:
            fresh=[r for r in s['groups'][key]['events'] if all(r.get(k) and parse_time(r[k])>parse_time(block['recorded_at'])
                    for k in ('decision_at','anchor_at','available_at'))]
            m=statistics({'events':fresh})
        tradable=key.split('|')[2] in s.get('available_modes',MODES)
        missing=[name for name,ok in (('20_observed',m['endpoint_observed']>=20),('10_tokens',m['unique_tokens']>=10),
            ('2_dates',m['dates']>=2),('coverage_75pct',m['unknown_rate']<=.25),
            ('positive_costed_mean',(m['policy_model_mean'] or 0)>0),('drawdown_bound',m['sampled_equity_drawdown']<=.5*m['n'])) if not ok]
        s['dispositions'][key]={'status':'CONTROL_ONLY' if not tradable else 'ECONOMIC_REVIEW_ELIGIBLE' if not missing else 'ROLLBACK_WAIT_FRESH_EVIDENCE' if block else 'INSUFFICIENT',
            'missing':missing+(['nontradable_mode'] if not tradable else []),'frontier':s['training_cursor'],
            'release_statistics':m,'concentration':{'top1_removed':m['top1_removed'],'top3_removed':m['top3_removed']}}
    promoted=False
    if consumed and s.get('contract_valid',True):
        candidates=[]
        for k,d in s['dispositions'].items():
            if d['missing'] or not k.endswith('|5') or k.split('|')[2] not in s.get('available_modes',MODES):continue
            block=s.get('release_blocks',{}).get(k)
            if block and (s.get('group_label_frontiers',{}).get(k,0)<=block['label_frontier']
                    or parse_time(s.get('group_last_label_at',{}).get(k) or block['recorded_at'])<=parse_time(block['recorded_at'])):
                d['status']='ROLLBACK_WAIT_FRESH_EVIDENCE';continue
            candidates.append(k)
        chosen=sorted(candidates,key=lambda k:(s['dispositions'][k]['release_statistics']['policy_model_mean'],k),reverse=True)[:2]
        if chosen and chosen!=s['model']['selected_groups']:
            scores={k:s['dispositions'][k]['release_statistics']['policy_model_mean'] for k in chosen}
            model=dict(version='finite/v5:'+digest([s['training_cursor'],s['contract_hash'],scores])[:16],
                cutoff_at=iso(cutoff),training_frontier=s['training_cursor'],contract_hash=s['contract_hash'],
                selected_groups=chosen,selection_scores=scores,releases=s['model'].get('releases',0)+1,
                estimates={k:deepcopy(s['dispositions'][k]['release_statistics']) for k in chosen})
            model['seal']=digest(model)
            s['previous_models']=(s['previous_models']+[deepcopy(s['model'])])[-2:]
            s['model']=model;promoted=True;old.event(s,'model_release',model)
    old.count(s,'learned_labels',consumed)
    return {'consumed':consumed,'promoted':promoted,'dirty_groups':len(dirty)}


def matched_baseline(s):
    """Only actual equal-entry terminals from the frozen fixed-priority choice."""
    from .trajectory144 import ARMS
    routers=[r for r in s['actual_groups'].get(ROUTER,[])
             if r.get('model_version')==s['model']['version']]
    pairs=[];seen=set()
    for r in routers:
        arm=r.get('baseline_arm');decision=r.get('baseline_decision_key')
        terms=r.get('entry_terms') or {}
        if (not arm or arm==ROUTER or not decision or not r.get('source_fill_id')
                or not r.get('pair_address') or not terms.get('opened_at')
                or not all(isinstance(terms.get(k),(int,float)) and math.isfinite(terms[k]) and terms[k]>0
                           for k in ('stake_usd','paper_quantity_tokens','entry_execution_price_usd'))):continue
        identity=(r['version'],r['token_id'],r['pair_address'],r['source_fill_id'])
        if identity in seen:continue
        baseline=next((b for b in s['actual_groups'].get(arm,[])
            if b.get('decision_key')==decision and b.get('entry_terms')==terms
            and tuple(b.get(k) for k in ('version','token_id','pair_address','source_fill_id'))==identity),None)
        if baseline is not None:pairs.append((r,baseline));seen.add(identity)
    return pairs,dict(status='MATCHED_FIXED_PRIORITY' if pairs else 'NO_MATCHED_BASELINE',
        router_terminals=len(routers),pairs=len(pairs),unmatched=len(routers)-len(pairs),
        router_minus_baseline_usd=sum(r['realized_pnl_usd']-b['realized_pnl_usd'] for r,b in pairs) if pairs else None,
        basis='actual_fixed_priority_equal_entry_terminals_not_selected_source')


class Coordinator(old.Coordinator):
    router_arm=ROUTER
    def __init__(self,store):
        from .models import utcnow
        from .trajectory144 import VERSION
        self.store=store;self.key=KEY+':'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        self.legacy=old.Coordinator(store)  # Original317 retains its frozen v3 selection/release contract.
        contract={'feature':VERSION,'costs':deepcopy(getattr(store,'_chain_paper_execution',{})),'horizons':list(HORIZONS),'economic_semantics':UTILITY}
        self.state=initialize(store.get_kv(self.key,None),now=utcnow(),contract=contract);self.last_flush=0.
        self.legacy.other_pending_count=lambda:len(self.state['episodes'])
        row=store.db.execute('SELECT activated_at FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?',
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,ROUTER)).fetchone()
        self.activation_at=row['activated_at'] if row else self.state['activated_at']
        self.state['contract_valid']=self.state['contract_hash']==digest(contract)
        if not self.state['contract_valid'] or not valid_model(self.state['model'],self.state['contract_hash']):
            rollback(self.state,reason='INPUT_OR_MODEL_CONTRACT_INVALID',frontier=self.state['training_cursor'],now=utcnow(),target='baseline')
        self.reindex()

    def signals(self,features,signals,now):
        routed=self.legacy.signals(features,deepcopy(signals),now)
        sources={a:s for a,s in signals.items() if a in self.state.get('available_modes',MODES)
            and parse_time(s['observed_at'])>=parse_time(self.activation_at)}
        learned=super().signals(features,sources,now).get(ROUTER)
        if learned:
            learned['decision_evidence'].update(learning_activation_at=self.activation_at,
                learning_contract=deepcopy(self.state['contract']),learning_contract_hash=self.state['contract_hash'])
            routed[ROUTER]=learned
        return routed

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
            e=self.state['episodes'].get(event.get('episode_key'))
            if event.get('kind')=='label' and event.get('status')=='UNKNOWN' and known_floor_label(e,event,event['horizon']):
                event['status']='MODEL_FLOOR_EVENT';event['source']='sampled_model_floor_event_not_fill'
                if e:e['results'][str(event['horizon'])].update(status=event['status'],source=event['source'])

    def classify_floor_labels(self):
        for e in self.state['episodes'].values():
            if not e.get('entry') or not e.get('first_floor'):continue
            for h,label in e['results'].items():
                if label['status']=='UNKNOWN' and known_floor_label(e,label,h):
                    label.update(status='MODEL_FLOOR_EVENT',source='sampled_model_floor_event_not_fill')
        for event in self.state['events']:
            e=self.state['episodes'].get(event.get('episode_key'))
            if event.get('kind')=='label' and event.get('status')=='UNKNOWN' and known_floor_label(e,event,event['horizon']):
                event.update(status='MODEL_FLOOR_EVENT',source='sampled_model_floor_event_not_fill')

    def record_buy(self,version,arm,cohort,token,fill,at):
        if arm.startswith('trajectory144_'):
            self.legacy.record_buy(version,arm,cohort,token,fill,at)
        super().record_buy(version,arm,cohort,token,fill,at)
        row=self.store.db.execute('SELECT c.feature_json,c.pair_address,p.stake_usd,p.paper_quantity_tokens,p.entry_execution_price_usd,p.opened_at '
            'FROM chain_meme_trader_v6_cohorts c JOIN chain_meme_trader_positions p ON p.shadow_cohort_id=c.id '
            'WHERE c.id=? AND p.definition_version=? AND p.arm_id=?',(cohort,version,arm)).fetchone()
        p=self.state['actual_pending'].get(arm+':'+str(cohort))
        if p and row:
            signal=json.loads(row['feature_json']).get('cohort_signals',{}).get(arm,{})
            evidence=signal.get('decision_evidence',{})
            p.update(model_version=(evidence.get('learning_model') or {}).get('version',old.BASELINE),
                source_arm=evidence.get('learning_source_arm',arm),pair_address=row['pair_address'],
                baseline_arm=evidence.get('fixed_priority_source_arm'),
                baseline_decision_key=evidence.get('fixed_priority_decision_key'),
                decision_key=signal.get('decision_key'),
                entry_terms={k:row[k] for k in ('stake_usd','paper_quantity_tokens','entry_execution_price_usd','opened_at')})

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
        pairs,comparison=matched_baseline(self.state)
        self.state['economic_comparison']=comparison
        if (self.state['model']['version']!=old.BASELINE and len(pairs)>=10 and len({r['token_id'] for r,b in pairs})>=3
                and sum(r['realized_pnl_usd'] for r,b in pairs)<0
                and sum(r['realized_pnl_usd']-b['realized_pnl_usd'] for r,b in pairs)<0):
            rollback(self.state,reason='POST_RELEASE_MATCHED_ECONOMIC_FAILURE',frontier=self.state['actual_frontier'],now=now)

    def flush(self,now):
        s=self.state
        manager=getattr(self.store,'_recipe145',None)
        if manager:
            sources=[manager.source(a) for a in MODES]
            s['available_modes']=[p['arm_id'] for p in sources if p and not p.get('entry_paused')
                and p.get('forward_enabled',True) and p.get('trajectory_engine')=='v144' and p.get('feature_contract')==VERSION]
        self.legacy_status=self.legacy.flush(now)
        legacy_horizons={}
        for key,group in self.legacy.state['groups'].items():
            totals=legacy_horizons.setdefault(key.split('|')[-1],{'OBSERVED':0,'UNKNOWN':0})
            totals['OBSERVED']+=len(group['returns']);totals['UNKNOWN']+=group['unknown']
        self.legacy_status.update(schema=old.KEY,horizons=legacy_horizons,
            unique_episodes=len(self.legacy.state['seen']),last_update=iso(parse_time(now)))
        if not valid_model(s['model'],s['contract_hash']):rollback(s,reason='MODEL_INVALID',frontier=s['training_cursor'],now=now,target='baseline')
        self.resolve_actual(now);old.expire(s,now=now);self.classify_floor_labels();learn=train(s,cutoff_at=now);self.reindex()
        events=s['events'][:64]
        with self.store._lock,self.store.db:
            for r in events:
                self.store.db.execute('INSERT OR IGNORE INTO chain_meme_pattern_evidence(definition_version,token_id,pair_address,kind,source_key,observed_at,recorded_at,payload_json) VALUES(?,?,?,?,?,?,?,?)',
                    (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,r.get('token_id',''),r.get('pair_address',''),'mode_learning146_'+r['kind'],
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
            tot['OBSERVED']+=m['endpoint_observed'];tot['UNKNOWN']+=m['unknown'];tot['MODEL_FLOOR_EVENT']+=m['floor_events']
        return dict(schema=KEY,activated_at=s['activated_at'],pending=len(s['episodes']),counts=s['counts'],horizons=horizons,
            decision_eligible=True,affects=ROUTER,trading_selector_contract=KEY,legacy_selector_contract=old.KEY,
            superseded_schema='mode-learning145/v4',superseded_state='PRESERVED_NOT_RELABELED',
            economic_comparison=s.get('economic_comparison',{'status':'NO_MATCHED_BASELINE','pairs':0}),
            model=s['model'],last_update=iso(parse_time(now)),learned=learn['consumed'],dirty_groups=learn['dirty_groups'],
            event_pending=len(s['events']),extra_requests=0,unique_episodes=len(s['seen']),
            dispositions=s['dispositions'],rollback_history=s['rollback_history'],baseline_reason='FIXED_BASELINE_NO_RELEASE' if s['model']['version']==old.BASELINE else None)
