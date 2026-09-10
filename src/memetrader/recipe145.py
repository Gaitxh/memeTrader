"""Restricted deterministic recipes; no generated code, queries or source requests."""
from copy import deepcopy
import json
from .models import iso,parse_time,utcnow
from .mode_learning145 import digest
from .mode_learning144 import age_band
from .trajectory144 import ARMS,VERSION

KEY='recipe145/v1'
FIELDS={'schema','source_arm_id','source_contract_hash','entry_context','exit_template','risk_profile',
        'proposal_cutoff','evidence_refs','feature_contract','cost_activation'}
TEMPLATES=('FAST5','RECLAIM15','TREND30_120','PRINCIPAL_RECOVERY')
SEEDS={ARMS[1]:'trajectory145_sparse_trend_runner_v1',ARMS[2]:'trajectory145_reclaim_trend_runner_v1'}
ACTIVE={'REGISTERED','LOADED','FORWARD_EVALUATION','RETAIN'}


def _economic_comparison(pairs, frozen_risk, current_policy):
    """Describe only actual, same-fill recipe terminals; never change entry rights."""
    candidate_rows = [row for row, _ in pairs]
    net = sum(float(row['realized_pnl_usd']) for row in candidate_rows)
    delta = sum(float(row['realized_pnl_usd']) - float(base['realized_pnl_usd'])
                for row, base in pairs)
    by_token = {}
    for row in candidate_rows:
        by_token[row['token_id']] = by_token.get(row['token_id'], 0.0) + float(row['realized_pnl_usd'])
    ordered = sorted(by_token.values(), reverse=True)
    recipe_notional = frozen_risk.get('notional_usd')
    policy_notional = current_policy.get('notional_usd')
    stakes = [row.get('stake_usd') for row in candidate_rows]
    if recipe_notional is None or policy_notional is None or any(stake is None for stake in stakes):
        risk_status = 'UNKNOWN_STAKE_NOT_RECORDED'
    elif any(float(stake) > min(float(recipe_notional), float(policy_notional)) for stake in stakes):
        risk_status = 'KNOWN_NOTIONAL_VIOLATION'
    else:
        risk_status = 'KNOWN_WITHIN_NOTIONAL'
    dates = {parse_time(row['closed_at']).date().isoformat() for row in candidate_rows}
    missing = []
    if len(pairs) < 20: missing.append('20_same_fill_terminals')
    if len(by_token) < 10: missing.append('10_unique_tokens')
    if len(dates) < 2: missing.append('2_utc_dates')
    if net <= 0: missing.append('positive_costed_net_pnl')
    if delta < 0: missing.append('nonnegative_delta_net_pnl')
    if risk_status == 'UNKNOWN_STAKE_NOT_RECORDED': missing.append('stake_usd_not_recorded')
    if risk_status == 'KNOWN_NOTIONAL_VIOLATION': missing.append('notional_risk_limit_violation')
    status = 'PAPER_SUPPORTED' if not missing else 'INSUFFICIENT'
    return {
        'same_fill_terminals': len(pairs), 'tokens': len(by_token),
        'utc_dates': len(dates), 'costed_net_pnl': net,
        'candidate_net_pnl': net, 'delta_net_pnl': delta,
        'risk_check_basis': 'actual_stake_usd_vs_frozen_recipe_and_current_policy_notional',
        'risk_check_status': risk_status, 'economic_status': status,
        'missing': missing,
        # Concentration is descriptive evidence, never an economic veto.
        'concentration': {'top1_pnl': sum(ordered[:1]), 'top3_pnl': sum(ordered[:3]),
                          'top1_share': (sum(ordered[:1]) / net) if net else None,
                          'top3_share': (sum(ordered[:3]) / net) if net else None},
    }


def recipe(source,template,now,*,evidence=(),context='ALL'):
    return dict(schema=KEY,source_arm_id=source['arm_id'],source_contract_hash=source['behavior_contract_hash'],
        entry_context=context,exit_template=template,risk_profile={'notional_usd':2.,'max_positions':2,'live':False},
        proposal_cutoff=iso(parse_time(now)),evidence_refs=list(evidence),feature_contract=VERSION,
        cost_activation=deepcopy(source.get('_execution',{})))


def compile_recipe(r,source):
    if set(r)!=FIELDS or r['schema']!=KEY:raise ValueError('RECIPE_SCHEMA_FIELDS')
    if r['exit_template'] not in TEMPLATES:raise ValueError('UNSUPPORTED_EXIT')
    if r['risk_profile']!={'notional_usd':2.,'max_positions':2,'live':False}:raise ValueError('RISK_CONTRACT')
    if r['source_arm_id'] not in (ARMS[0],ARMS[1],ARMS[2],ARMS[4]) or r['source_arm_id']!=source.get('arm_id'):raise ValueError('SOURCE_UNSUPPORTED')
    if source.get('entry_paused') or source.get('forward_enabled') is False:raise ValueError('SOURCE_NOT_RUNNABLE')
    if r['source_contract_hash']!=source['behavior_contract_hash'] or r['feature_contract']!=VERSION:raise ValueError('SOURCE_CONTRACT_CHANGED')
    if r['cost_activation']!=source.get('_execution',{}):raise ValueError('COST_ACTIVATION_CHANGED')
    context=r['entry_context']
    if context!='ALL' and (not isinstance(context,dict) or set(context)!={'chain','age_band'} or
            context['chain'] not in ('bsc','solana','robinhood') or context['age_band'] not in ('0_300','300_900','900_21600','mature')):raise ValueError('ENTRY_CONTEXT')
    behavior={k:r[k] for k in FIELDS-{'proposal_cutoff','evidence_refs'}};fingerprint=digest(behavior)
    source_template='TREND30_120' if source.get('trajectory_trend_runner') else 'RECLAIM15' if source.get('max_hold_minutes')==15 else 'FAST5' if source.get('max_hold_minutes')==5 else None
    if context=='ALL' and r['exit_template']==source_template:raise ValueError('DUPLICATE_SOURCE_BEHAVIOR')
    p=deepcopy(source)
    for key in ('stage','canonical_id','behavior_contract_hash','forward_started_at','forward_activation_snapshot_id','runtime_addition_id',
                'paired_entry_group','paired_entry_size','router_exit_profiles','model_contract','_execution','trajectory_trend_runner','dynamic_principal_recovery'):
        p.pop(key,None)
    template=r['exit_template'];arm='recipe145_'+fingerprint[:16]+'_v1'
    p.update(arm_id=arm,canonical_id=arm,name='受限配方·'+template,entry_family=arm,source_arm_ids=[source['arm_id']],entry_alias_of=source['arm_id'],
        notional_usd=2.,max_hold_minutes={'FAST5':5,'RECLAIM15':15,'TREND30_120':30,'PRINCIPAL_RECOVERY':30}[template],
        entry_filter={**p.get('entry_filter',{}),'max_concurrent_positions':2,'include_pending_in_limit':True,'single_token_open_or_reserved':True},
        signal_origin_clock='recipe_activation_at',recipe145_hash=fingerprint,recipe145=deepcopy(r),
        trajectory144_exit='decay',take_profit=[],hard_stop_return=-.2,trailing_activate_return=.3,trailing_drawdown=.15,
        assessment_status='INSUFFICIENT',decision_eligible=True,observer_only=False,affects='paper_only',live=False,
        description='用户授权的受限组件实验；共同安全/严格后帧/原池4%成本；注册不是盈利晋级。')
    if template=='TREND30_120':p.update(trajectory_trend_runner=True,trajectory145_trend_evidence=True,trend_base_hold_minutes=30,trend_max_hold_minutes=120)
    if template=='PRINCIPAL_RECOVERY':p['dynamic_principal_recovery']='minimum_net_debit_next_frame/v2'
    return fingerprint,p


def same_behavior(candidate,existing):
    """Compare executable entry/exit/risk, including pre-existing trend aliases."""
    def fields(p):
        entry=p.get('entry_alias_of') or p.get('arm_id')
        if entry==ARMS[3] or p.get('arm_id')==ARMS[3]:entry=ARMS[0]
        return (entry,(p.get('recipe145') or {}).get('entry_context','ALL'),p.get('notional_usd'),
            (p.get('entry_filter') or {}).get('max_concurrent_positions'),p.get('max_hold_minutes'),
            bool(p.get('trajectory_trend_runner')),p.get('dynamic_principal_recovery'),
            p.get('hard_stop_return'),p.get('trailing_activate_return'),p.get('trailing_drawdown'),p.get('take_profit'))
    return fields(candidate)==fields(existing)


class Manager:
    def __init__(self,store):
        self.store=store;self.version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION;self.key=KEY+':'+self.version
        self.state=store.get_kv(self.key,None) or dict(schema=KEY,activated_at=iso(),proposals={},source_outcomes={},counts={},generation_frontiers={})
        self.policies={};self.existing=[];self.loaded=False;self.dirty=False
        # The immutable append rows are authoritative after a crash between append and KV publication.
        rows=store.db.execute('SELECT id,arm_id,policy_json,activated_at,activation_snapshot_id FROM chain_meme_trader_policy_additions WHERE definition_version=?',(self.version,)).fetchall()
        for row in rows:
            p=json.loads(row['policy_json']);self.existing.append(p);h=p.get('recipe145_hash')
            if not h:continue
            self.policies[row['arm_id']]=p
            self.state['proposals'].setdefault(h,dict(recipe=p['recipe145'],origin='RECOVERED_APPEND_RECEIPT',status='REGISTERED',arm_id=row['arm_id'],registration_index=row['id'],registered_at=row['activated_at'],frontier=row['activation_snapshot_id']))
        for source_arm in SEEDS:
            source=self.source(source_arm)
            if source and not source.get('entry_paused'):
                r=recipe(source,'TREND30_120',self.state['activated_at'],evidence=['145-D_USER_AUTHORIZED_SEED'])
                self.propose(r,'USER_AUTHORIZED_SEED')

    def source(self,arm):
        row=self.store.db.execute('SELECT policy_json,behavior_contract_hash,activated_at FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?',(self.version,arm)).fetchone()
        if not row:return None
        p=json.loads(row['policy_json']);p.update(behavior_contract_hash=row['behavior_contract_hash'],forward_started_at=row['activated_at'],_execution=deepcopy(getattr(self.store,'_chain_paper_execution',{})))
        for prefix in ('chain-meme-account-convergence/v1:','chain-meme-account-loss-retirement/v1:'):
            if arm in (self.store.get_kv(prefix+self.version,{}) or {}).get('arms',{}):p['entry_paused']=True
        return p

    def propose(self,r,origin):
        source=self.source(r['source_arm_id']);h,p=compile_recipe(r,source or {})
        if h in self.state['proposals']:return self.state['proposals'][h]
        if len(self.state['proposals'])>=64:
            self.state['counts']['proposal_capacity_wait']=self.state['counts'].get('proposal_capacity_wait',0)+1
            self.dirty=True;return {'status':'WAIT_CAPACITY','reason':'BOUNDED_PROPOSAL_CAPACITY'}
        arm=SEEDS.get(r['source_arm_id']) if origin=='USER_AUTHORIZED_SEED' else None
        if arm:p.update(arm_id=arm,canonical_id=arm,name='稀疏HOT·量价趋势长持' if r['source_arm_id']==ARMS[1] else '回撤承接·量价趋势长持')
        item=dict(recipe=deepcopy(r),origin=origin,status='VALIDATED',arm_id=p['arm_id'],reason='ENGINEERING_VALIDATED_NOT_ALPHA',validated_at=iso())
        equivalent=next((v['arm_id'] for v in self.existing if same_behavior(p,v)),None)
        if equivalent:item.update(status='DUPLICATE_SUPERSEDED',reason='EXISTING_EXECUTABLE_BEHAVIOR',representative_arm=equivalent)
        self.state['proposals'][h]=item;self.policies[p['arm_id']]=p;self.dirty=True
        return item

    def slots(self):
        return sum(p['status'] in ACTIVE for p in self.state['proposals'].values())

    def register_one(self,now):
        for h,item in self.state['proposals'].items():
            if item['status'] not in ('VALIDATED','WAIT_CAPACITY'):continue
            if self.slots()>=2:item.update(status='WAIT_CAPACITY',reason='TWO_ACTIVE_CANDIDATE_SLOTS');self.dirty=True;return
            source=self.source(item['recipe']['source_arm_id'])
            try:_,policy=compile_recipe(item['recipe'],source or {})
            except (ValueError,KeyError) as exc:item.update(status='REJECT',reason=str(exc));self.dirty=True;continue
            policy.update(arm_id=item['arm_id'],canonical_id=item['arm_id'])
            if item['origin']=='USER_AUTHORIZED_SEED':policy['name']=self.policies[item['arm_id']]['name']
            receipt={'recipe_hash':h,'recipe':item['recipe'],'origin':item['origin'],'status':'REGISTERED'}
            row=self.store.append_chain_meme_trader_policy(policy,activated_at=now,recipe_receipt=receipt)
            item.update(status='LOADED' if self.loaded else 'REGISTERED',registered_at=row['activated_at'],
                loaded_at=iso(parse_time(now)) if self.loaded else None,frontier=row['activation_snapshot_id'],registration_index=row['id'],reason='WAIT_FRESH_SIGNAL')
            self.policies[item['arm_id']]=policy;self.dirty=True;return

    def signals(self,features,signals,now):
        output={}
        for h,item in self.state['proposals'].items():
            if item['status'] not in ACTIVE:continue
            r=item['recipe'];sig=signals.get(r['source_arm_id'])
            if not sig or parse_time(sig['observed_at'])<parse_time(item['registered_at']):continue
            context=r['entry_context']
            if context!='ALL' and (features['chain'],age_band(features.get('pool_age_seconds')))!=(context['chain'],context['age_band']):continue
            alias=deepcopy(sig);alias['decision_key']=sig['decision_key']+'|'+item['arm_id']
            alias['decision_evidence'].update(recipe_activation_at=item['registered_at'],recipe_hash=h,source_decision_key=sig['decision_key'],recipe_source_arm=r['source_arm_id'])
            output[item['arm_id']]=alias
        return output

    def terminal(self,row,now):
        if parse_time(row.get('available_at') or row['closed_at'])>parse_time(now):return
        if row.get('terminal_recorded_at') and parse_time(row['terminal_recorded_at'])>parse_time(now):return
        if parse_time(row['opened_at'])<parse_time(self.state['activated_at']):return
        arm=row['arm'];key=str(row['source_fill_id']);groups=self.state['source_outcomes'];rows=groups.setdefault(arm,[])
        if any(str(r['source_fill_id'])==key for r in rows):return
        rows.append(deepcopy(row));groups[arm]=rows[-256:];self.dirty=True
        for p in self.state['proposals'].values():
            if p['arm_id']==arm and p['status'] in ACTIVE:p.update(status='FORWARD_EVALUATION',reason='ACTUAL_TERMINAL_PENDING_ECONOMIC_REVIEW')
        if arm not in (ARMS[0],ARMS[1],ARMS[2],ARMS[4]):return
        old_front=self.state['generation_frontiers'].get(arm,0);recent=[r for r in rows if r['source_fill_id']>old_front]
        if len(recent)<5 or len({r['token_id'] for r in recent})<3:return
        source=self.source(arm)
        if not source or source.get('entry_paused'):
            self.state['counts']['source_unavailable']=self.state['counts'].get('source_unavailable',0)+1;return
        for template in ('TREND30_120','RECLAIM15','FAST5','PRINCIPAL_RECOVERY'):
            r=recipe(source,template,now,evidence=[str(x['source_fill_id']) for x in recent])
            try:h,compiled=compile_recipe(r,source)
            except ValueError:continue
            if any(same_behavior(compiled,v) for v in self.existing):continue
            if h not in self.state['proposals']:
                item=self.propose(r,'AUTO_GENERATED')
                if item['status']=='DUPLICATE_SUPERSEDED':continue
                self.state['generation_frontiers'][arm]=max(x['source_fill_id'] for x in recent);break

    def disposition(self,h,status,reason,now):
        if status not in ('RETAIN','REVISE','REJECT'):raise ValueError('DISPOSITION')
        item=self.state['proposals'][h]
        if status in ('REVISE','REJECT') and item.get('registered_at'):
            key='chain-meme-account-convergence/v1:'+self.version
            control=self.store.get_kv(key,{}) or {};control.setdefault('activated_at',iso(parse_time(now)))
            control.setdefault('arms',{})[item['arm_id']]={'state':'PAUSED_NEW_ENTRY','basis':'recipe145:'+reason}
            self.store.set_kv(key,control)  # Only this generated candidate; existing exits continue.
        item.update(status=status,reason=reason,disposition_at=iso(parse_time(now)));self.dirty=True

    def flush(self,now):
        self.loaded=True
        paused=set()
        for prefix in ('chain-meme-account-convergence/v1:','chain-meme-account-loss-retirement/v1:'):
            paused.update((self.store.get_kv(prefix+self.version,{}) or {}).get('arms',{}))
        for h,p in self.state['proposals'].items():
            if p['status']=='REGISTERED':p.update(status='LOADED',loaded_at=iso(parse_time(now)));self.dirty=True
            if p['status'] not in ACTIVE:continue
            if p['arm_id'] in paused:
                p.update(status='REVISE',reason='EXISTING_NEW_ENTRY_CONTROL',disposition_at=iso(parse_time(now)));self.dirty=True;continue
            rows=self.state['source_outcomes'].get(p['arm_id'],[]);base=self.state['source_outcomes'].get(p['recipe']['source_arm_id'],[])
            pairs=[(r,b) for r in rows for b in base if (r['source_fill_id'],r['token_id'],r.get('pair_address'))==(b['source_fill_id'],b['token_id'],b.get('pair_address'))]
            p['comparison']={**_economic_comparison(pairs,p['recipe']['risk_profile'],self.policies.get(p['arm_id'],{})),
                'extra_hold_seconds':sum((parse_time(r['closed_at'])-parse_time(b['closed_at'])).total_seconds() for r,b in pairs),
                'observed_costed_mfe':[r.get('observed_costed_mfe') for r,b in pairs],
                'observed_max_drawdown':[r.get('observed_max_drawdown') for r,b in pairs],
                'close_reasons':{reason:sum(r.get('close_reason')==reason for r,b in pairs) for reason in {r.get('close_reason') for r,b in pairs}},
                'open_or_unmatched':'UNKNOWN_NOT_ZERO'}
            if len(pairs)>=10 and p['comparison']['tokens']>=3 and sum(r['realized_pnl_usd'] for r,b in pairs)<0 and p['comparison']['delta_net_pnl']<0:
                p['comparison']['economic_status']='REJECT'
                self.disposition(h,'REJECT','NEGATIVE_MATCHED_FORWARD_EVIDENCE',now)
        self.register_one(now)
        if self.dirty:self.store.set_kv(self.key,self.state);self.dirty=False
        self.store.set_kv('recipe145:status',{'schema':KEY,'updated_at':iso(parse_time(now)),'active_slots':self.slots(),'max_slots':2,
            'counts':{status:sum(p['status']==status for p in self.state['proposals'].values()) for status in ACTIVE|{'WAIT_CAPACITY','REJECT','VALIDATED','REVISE','DUPLICATE_SUPERSEDED'}},
            'candidates':[{k:p.get(k) for k in ('arm_id','origin','status','reason','registered_at','loaded_at','registration_index','comparison')} for p in self.state['proposals'].values()],
            'automatic_registration':True,
            'economic_promotions':sum((p.get('comparison') or {}).get('economic_status')=='PAPER_SUPPORTED'
                                       for p in self.state['proposals'].values()),'extra_requests':0})
