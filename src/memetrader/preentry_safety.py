"""Signal-only, asynchronous obvious-risk veto for the common Paper BUY path."""
import asyncio
from collections import OrderedDict
from dataclasses import replace
from datetime import timedelta
import json
import math
import time

from .models import canonical_token_address, iso, parse_time, utcnow

VERSION = 'preentry_obvious_scam_v1'

def stock_registry_evidence(connection, token_id, decision_at):
    chain, address = token_id.split(':', 1)
    if chain != 'robinhood':
        return None
    at = iso(parse_time(decision_at))
    run = connection.execute('SELECT id,completed_at,recorded_at,deployment_count FROM '
        'robinhood_stock_token_registry_runs WHERE source_url=? AND requested_at<=completed_at '
        'AND completed_at<=recorded_at AND completed_at<=? AND recorded_at<=? '
        'ORDER BY completed_at DESC,id DESC LIMIT 1',
        ('https://api.robinhood.com/rhj/assets',at,at)).fetchone()
    evidence = {'status':'UNKNOWN','classification_only':True,'source_at':None,
                'reason':'official_registry_unavailable_or_empty'}
    if run is None:
        return evidence
    evidence.update(run_id=run['id'],source_at=run['completed_at'],recorded_at=run['recorded_at'])
    if run['deployment_count'] <= 0 or not connection.execute(
            'SELECT 1 FROM robinhood_stock_token_registry_entries WHERE run_id=? AND recorded_at<=? LIMIT 1',
            (run['id'],at)).fetchone():
        return evidence
    hit = connection.execute('SELECT 1 FROM robinhood_stock_token_registry_entries '
        'WHERE contract_address=? AND run_id=? AND chain_id=4663 AND recorded_at<=? LIMIT 1',
        (canonical_token_address(chain,address),run['id'],at)).fetchone()
    evidence.update(status='EXCLUDED_STOCK_TOKEN' if hit else 'NOT_LISTED',
        reason='official_robinhood_stock_token_not_meme' if hit else 'not_in_latest_available_registry')
    return evidence

EVM_FLAGS = ('is_honeypot','cannot_sell','cannot_sell_all','hidden_owner','can_take_back_ownership',
    'owner_change_balance','is_blacklisted','blacklist','transfer_pausable',
    'slippage_modifiable','personal_slippage_modifiable','honeypot_with_same_creator')
SOFT_VAULT_STATES = {'SYNTHETIC_SUPPORT_PATTERN',
    'UNWIND_HAZARD_PRECURSOR_RECOVERY_UNKNOWN'}


def assess_behavior(rows, *, token_id, pool, now):
    """Consume existing confirmed exact-pool evidence, never infer from raw counts."""
    from .capital_context import _valid_vault_row
    valid=[r for r in rows if _valid_vault_row(r,token_id,pool,now)]
    result=dict(hard_veto=[],soft_hazard=[],behavior_sources=[])
    if not valid:return result
    row=max(valid,key=lambda r:(parse_time(r['observed_at']),int(r['id'])))
    payload=row.get('payload') or json.loads(row.get('payload_json') or '{}')
    features=payload.get('features') or {}
    reserve=payload.get('effective_quote_reserve_raw')
    # Real quote reserve alone may legally be zero on a native curve. Only
    # the protocol observer's known effective reserve is economic evidence.
    if features.get('effective_quote_reserve_known') is True and reserve is not None:
        try:
            if int(reserve)<=0:result['hard_veto'].append('effective_quote_reserve_nonpositive')
        except (TypeError,ValueError):pass
    state=payload.get('observer_state')
    if state in SOFT_VAULT_STATES:result['soft_hazard'].append(state)
    result['behavior_sources']=[dict(evidence_id=row['id'],observed_at=row['observed_at'],
        recorded_at=row['recorded_at'],observer_state=state)]
    return result


def flag(value):
    if isinstance(value, dict): value=value.get('status')
    if value in (True, 1, '1', 'true'): return True
    if value in (False, 0, '0', 'false'): return False
    return None


def assess(snapshot, checker, *, source_at, max_tax=12):
    raw=snapshot.raw;pair=raw.get('pair') or {};reasons=[];unknown=[];sources=[];usable=[];soft=[]
    chain=snapshot.chain;pool=str(pair.get('pairAddress') or '')
    identity=bool(pool and pair.get('chainId')==chain and
        canonical_token_address(chain,(pair.get('baseToken') or {}).get('address',''))==snapshot.address)
    if not identity: reasons.append('canonical_surface_identity_mismatch')
    if chain in {'bsc','robinhood'}:
        g=raw.get('goplus_evm'); h=raw.get('honeypot_is')
        if isinstance(g,dict):
            sources.append('goplus_evm')
            for field in EVM_FLAGS:
                if chain!='bsc' and field=='cannot_sell_all':continue  #105 changes BSC only.
                value=flag(g.get(field))
                if value is True:reasons.append(field)
                elif value is None:unknown.append(field)
                else:usable.append('goplus_evm:'+field+'=false')
            for field in ('buy_tax','sell_tax'):
                try:
                    if isinstance(g[field],bool):raise ValueError('invalid tax')
                    value=float(g[field])*100
                    if not math.isfinite(value) or value<0:raise ValueError('invalid tax')
                    if value>max_tax:reasons.append(field+'_above_existing_tax_limit')
                    else:usable.append('goplus_evm:'+field+'='+str(value)+'pct')
                except (KeyError,ValueError,TypeError):unknown.append(field)
        else:unknown.append('goplus_unavailable')
        if isinstance(h,dict):
            sources.append('honeypot_is')
            honeypot=flag((h.get('honeypotResult') or {}).get('isHoneypot'))
            if honeypot is True:reasons.append('honeypot')
            elif honeypot is False:usable.append('honeypot_is:isHoneypot=false')
            # A generic simulation failure is UNKNOWN, not proof of sell failure.
            if h.get('simulationSuccess') is False:unknown.append('simulation_failed_unknown_cause')
            for field in ('buyTax','sellTax'):
                value=(h.get('simulationResult') or {}).get(field)
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0:
                    if value>max_tax:reasons.append(field+'_above_existing_tax_limit')
                    else:usable.append('honeypot_is:'+field+'='+str(value)+'pct')
    elif chain=='solana':
        old=checker.solana_pretrade_rug_assessment(snapshot)
        for field,value in (old.get('facts',{}).get('token_controls') or {}).items():
            if value is False:usable.append('solana_control:'+field+'=false')
        if flag((raw.get('rugcheck') or {}).get('rugged')) is False:
            usable.append('rugcheck:rugged=false')
        hard=set(old['hard_rejections'])
        # Only explicit dangerous token controls/verified mismatches. No LP-lock,
        # whale concentration, or global exact-route/depth requirement.
        reasons += [r for r in hard if r.startswith('dangerous_') or r in
            {'non_transferable','malicious_creator','pool_identity_mismatch','pool_custody_mismatch'}]
        for name in ('goplus_solana','rugcheck'):
            if isinstance(raw.get(name),dict):sources.append(name)
        if (raw.get('rugcheck') or {}).get('rugged') is True:reasons.append('rugged')
        rpc=raw.get('solana_pool_rpc') or {}
        if rpc.get('status')=='rejected':reasons.append('verified_pool_rejected:'+str(rpc.get('reason')))
        unknown += [x for x in old['unknowns'] if not x.startswith('exact_size_')]
    if chain=='robinhood':
        # Existing canonical provider surface is the available boundary; it is
        # not a security audit or a claim of verified deployed contract code.
        if str(pair.get('dexId') or '').lower() not in {'uniswap','uniswap-v3','uniswap-v4','pons'}:
            unknown.append('protocol_surface_unsupported')
        else:
            sources.append('canonical_provider_surface')
            # Surface identity is necessary, but is not a usable security fact.
        if flag((raw.get('goplus_evm') or {}).get('is_open_source')) is False:
            soft.append('closed_source_unverified')
            unknown.append('closed_source_unverified')
    elif chain not in {'bsc','solana'}:unknown.append('chain_unsupported')
    if not usable:unknown.append('no_usable_safety_fact')
    strong = [x for x in usable if x == 'honeypot_is:isHoneypot=false' or
              x.startswith('goplus_evm:') and x.endswith('=false') and 'honeypot_with_same_creator' not in x]
    weak = chain == 'bsc' and bool(usable) and not strong
    if weak:unknown.append('bsc_only_weak_safety_facts')
    status='REJECT' if reasons else 'WEAK' if weak else 'UNKNOWN' if unknown or not sources else 'PASS'
    allow=not reasons and bool(usable) and 'protocol_surface_unsupported' not in unknown
    if weak:allow=False
    return dict(version=VERSION,status=status,allow=allow,reasons=sorted(set(reasons)),
        hard_veto=sorted(set(reasons)),soft_hazard=sorted(set(soft)),usable_facts=sorted(set(usable)),
        strong_facts=strong,provider_availability={name:dict(
            available=isinstance(raw.get(name),dict),error_type=raw.get(name+'_error'))
            for name in ('goplus_evm','honeypot_is') if chain in {'bsc','robinhood'}},
        unknowns=sorted(set(unknown)),sources=sources,source_at=source_at,
        source_clock='local_security_acquisition_complete_not_chain_time',
        token_id=snapshot.token_id,pool=canonical_token_address(chain,pool))


class PreentrySafety:
    """One bounded security worker; pending entry uses only a later causal frame."""
    def __init__(self,store,checker,timing=None):
        self.store=store;self.checker=checker;self.timing=timing;self.task=None
        self.key=VERSION+':pending:'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        self.pending=store.get_kv(self.key,{}) or {}
        self.cache=OrderedDict()
        from .safety_veto_shadow import SafetyVetoShadow, KEY
        store._safety_veto_shadow = SafetyVetoShadow(store.get_kv(KEY, None))

    def save(self):
        self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
            (self.key,json.dumps(self.pending),iso()))

    def behavior(self,item,now):
        rows=self.store._capital_evidence(item['token_id'],item['pool'],now,('vault_frame',))
        return assess_behavior(rows['vault_frame'],token_id=item['token_id'],pool=item['pool'],now=now)

    def record(self,item,status,assessment=None):
        now=iso();payload={**item,'safety_status':status,'assessment':assessment,
            'not_a_safety_guarantee':True,'decision_eligible':False}
        self.store.db.execute('INSERT OR IGNORE INTO chain_meme_pattern_evidence('
            'definition_version,token_id,pair_address,kind,source_key,observed_at,recorded_at,payload_json) '
            'VALUES(?,?,?,?,?,?,?,?)',(item['version'],item['token_id'],item['pool'],VERSION,
            str(item['cohort_id'])+':'+status,now,now,json.dumps(payload)))
        if (status.startswith('REJECT') or status in {'WAIT_HAZARD','WAIT_WEAK'}) and self.store.db.execute('SELECT changes()').fetchone()[0]:
            row=self.store.db.execute('SELECT price_usd,liquidity_usd,observed_at,ingested_at,recorded_at FROM token_snapshots WHERE id=?',
                                      (item['snapshot_id'],)).fetchone()
            anchor=dict(row) if row else None
            if anchor is not None:
                price=anchor['price_usd'];liq=anchor['liquidity_usd']
                anchor['eligible']=bool(price is not None and math.isfinite(price) and price>0
                    and liq is not None and math.isfinite(liq) and liq>=item.get('shadow_costs',{}).get('min_pool_liquidity_usd',1000)
                    and anchor['ingested_at'] and parse_time(anchor['observed_at'])<=parse_time(anchor['ingested_at'])<=parse_time(anchor['recorded_at'])<=parse_time(now))
            arms=[r[0] for r in self.store.db.execute('SELECT arm_id FROM chain_meme_trader_entry_decisions WHERE definition_version=? AND shadow_cohort_id=? AND status=\'admitted\' ORDER BY arm_id LIMIT 256',
                    (item['version'],item['cohort_id']))]
            self.store._safety_veto_shadow.capture(item,status,assessment,anchor,arms,parse_time(now))
            # Commit the trigger with its existing safety audit, not on a later
            # polling tick; a restart must not silently lose the denominator.
            self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) '
                'ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
                ('safety-veto-shadow95',json.dumps(self.store._safety_veto_shadow.snapshot()),now))
        # Capacity refusal has no worker item: record an explicit consumed skip,
        # rather than leaving an apparently resumable claim without a queue slot.
        if status.startswith('REJECT') or status in {'EXPIRED_SECURITY_OR_NEXT_FRAME','WAIT_QUEUE_CAPACITY'}:
            self.store.db.execute('UPDATE chain_meme_cohort_enrollment_claims SET terminal_reason=? '
                'WHERE definition_version=? AND cohort_id=? AND terminal_reason IS NULL',
                (status,item['version'],item['cohort_id']))

    def guard(self,*,version,cohort_id,token_id,snapshot_id,filled_at,definition,reason,**kwargs):
        row=self.store.db.execute('SELECT raw_json,observed_at FROM token_snapshots WHERE id=?',(snapshot_id,)).fetchone()
        pair=(json.loads(row['raw_json']).get('pair') or {}) if row else {}
        pool=canonical_token_address(token_id.split(':')[0],str(pair.get('pairAddress') or ''))
        item=dict(version=version,cohort_id=cohort_id,token_id=token_id,pool=pool,snapshot_id=snapshot_id,
            requested_at=filled_at,reason=reason,notional=definition['policy_notional_usd'],
            expires_at=iso(parse_time(filled_at)+timedelta(seconds=float(definition.get('max_signal_to_execution_start_seconds',120)))))
        item['funding_mode']=kwargs.get('funding_mode','legacy_cash_limited')
        item['signal_price_usd']=kwargs.get('signal_price_usd')
        item['shadow_costs']={key:definition.get(key,default) for key,default in (
            ('buy_slippage_bps',400),('sell_slippage_bps',400),('additional_fee_usd_each_fill',0.0),('min_pool_liquidity_usd',1000))}
        registry = stock_registry_evidence(self.store.db,token_id,filled_at)
        if registry is not None:
            item['stock_registry'] = registry
            if registry['status']=='EXCLUDED_STOCK_TOKEN':
                self.record(item,'REJECT_SCOPE',dict(status='REJECT',allow=False,
                    reasons=[registry['reason']],source_at=registry['source_at'],
                    classification_only=True,not_a_scam_claim=True))
                return False
        behavior=self.behavior(item,parse_time(filled_at))
        if behavior['hard_veto'] or behavior['soft_hazard']:
            hard=bool(behavior['hard_veto'])
            assessment=dict(version=VERSION,status='REJECT' if hard else 'HAZARD',allow=False,
                reasons=behavior['hard_veto'],source_at=behavior['behavior_sources'][0]['observed_at'],**behavior)
            self.record(item,'REJECT_BEHAVIOR' if hard else 'WAIT_HAZARD',assessment)
            if not hard and str(cohort_id) not in self.pending and len(self.pending)<128:
                self.pending[str(cohort_id)]=item;self.save()
            return False
        # Explicit evidence already available on the signal is never erased by
        # a later provider outage. Its source clock remains the old frame's.
        original=self.store.token_snapshot_by_id(snapshot_id)
        if original is not None:
            known=assess(original,self.checker,source_at=iso(original.observed_at))
            if known['status']=='REJECT':
                self.record(item,'REJECT_EXISTING_EVIDENCE',known)
                return False
        cached=self.cache.get((token_id,pool))
        if cached and parse_time(cached['source_at'])<=parse_time(filled_at)<parse_time(cached['source_at'])+timedelta(seconds=45):
            if cached['status']=='REJECT':self.record(item,'REJECT',cached);return False
            if cached['allow'] and row and parse_time(cached['source_at'])<parse_time(row['observed_at']):
                self.record(item,'BUY_AUTHORIZED_'+cached['status'],cached);return True
        if str(cohort_id) not in self.pending:
            if len(self.pending)>=128:self.record(item,'WAIT_QUEUE_CAPACITY');return False
            self.pending[str(cohort_id)]=item;self.save();self.record(item,'WAIT_SECURITY')
        return False

    def kick(self):
        if self.pending and (self.task is None or self.task.done()):
            self.task=asyncio.create_task(self.work())

    async def work(self):
        now=utcnow()
        for key,value in list(self.cache.items()):
            if parse_time(value['source_at'])+timedelta(seconds=45)<=now:self.cache.pop(key)
        with self.store._lock,self.store.db:
            for key,item in list(self.pending.items()):
                if parse_time(item['expires_at'])<now:
                    self.record(item,'EXPIRED_SECURITY_OR_NEXT_FRAME');self.pending.pop(key)
            self.save()
            item=None
            for candidate in self.pending.values():
                cached=self.cache.get((candidate['token_id'],candidate['pool']))
                if candidate.get('weak_retry_exhausted'):continue
                if cached and cached['status']=='WEAK':
                    if 'weak_retry_due_at' not in candidate:
                        candidate['weak_retry_due_at']=iso(now+timedelta(seconds=5))
                        self.record(candidate,'WAIT_WEAK',cached);self.save()
                    if candidate.get('weak_retry_used') or now<parse_time(candidate['weak_retry_due_at']):continue
                elif cached:continue
                local=self.behavior(candidate,now)
                if not local['hard_veto'] and not local['soft_hazard']:
                    if candidate.get('weak_retry_due_at'):
                        if candidate.get('weak_retry_used') or now<parse_time(candidate['weak_retry_due_at']):continue
                        candidate['weak_retry_used']=True
                        # Persist the attempt before I/O; restart never repeats it.
                        candidate['weak_retry_exhausted']=True
                        self.save()
                    item=candidate;break
        if not item:return
        snapshot=self.store.token_snapshot_by_id(item['snapshot_id'])
        if snapshot is None:return
        # Never mutate the original snapshot or attach fresh reports to old data.
        snapshot=replace(snapshot,raw=dict(snapshot.raw));start=time.monotonic()
        # A failed refresh must not re-date security payloads from an old frame.
        for name in ('goplus_evm','honeypot_is','goplus_solana','rugcheck'):
            snapshot.raw.pop(name,None)
            snapshot.raw.pop(name+'_error',None)
        try:
            if snapshot.chain in {'bsc','robinhood'}:await self.checker.enrich_evm_execution_fields(snapshot)
            elif snapshot.chain=='solana':await self.checker.enrich_solana(snapshot)
            result=assess(snapshot,self.checker,source_at=iso(),max_tax=float(self.checker.config.get('max_tax_pct',12)))
        except Exception as exc:
            result=dict(version=VERSION,status='UNKNOWN',allow=False,reasons=[],unknowns=[type(exc).__name__],source_at=iso())
        self.cache[(item['token_id'],item['pool'])]=result
        while len(self.cache)>256:self.cache.popitem(last=False)
        with self.store._lock,self.store.db:
            self.record(item,'CHECKED_'+result['status'],result)
            if result['status']=='WEAK':
                item.setdefault('weak_retry_due_at',iso(utcnow()+timedelta(seconds=5)))
                self.record(item,'WAIT_WEAK',result)
            self.save()
        if self.timing:self.timing.observe('preentry_safety_fetch',time.monotonic()-start,items=1)

    def resume(self,token,snapshot,recorded_at):
        matches=[(k,x) for k,x in self.pending.items() if x['token_id']==token.token_id]
        if not matches:return
        pair=snapshot.raw.get('pair') or {};pool=canonical_token_address(token.chain,str(pair.get('pairAddress') or ''))
        for key,item in matches:
            result=self.cache.get((token.token_id,item['pool']))
            if not result:continue
            if result['status']=='REJECT':
                self.record(item,'REJECT',result);self.pending.pop(key);self.save();continue
            if not result['allow'] or not (parse_time(result['source_at'])<snapshot.observed_at<=recorded_at<=parse_time(item['expires_at'])):continue
            if recorded_at>=parse_time(result['source_at'])+timedelta(seconds=45):continue
            if pool!=item['pool'] or pair.get('chainId')!=token.chain or canonical_token_address(token.chain,(pair.get('baseToken') or {}).get('address',''))!=token.address:continue
            ing=snapshot.ingested_at or recorded_at
            if not snapshot.observed_at<=ing<=recorded_at or (recorded_at-snapshot.observed_at).total_seconds()>15:continue
            reg=self.store._chain_meme_trader_registration(item['version'])
            definition=self.store._chain_meme_trader_effective_definition(item['version'],reg['definition_json'])
            if not (snapshot.price_usd and math.isfinite(snapshot.price_usd) and snapshot.price_usd>0 and
                    snapshot.liquidity_usd is not None and math.isfinite(snapshot.liquidity_usd) and
                    snapshot.liquidity_usd>=float(definition.get('min_pool_liquidity_usd',1000))):continue
            # Legacy intent receipts are frozen by their existing settlement
            # path below, after the common guard can authorize this new frame.
            if self.store.db.execute("SELECT 1 FROM chain_meme_trader_order_intents WHERE shadow_cohort_id=? AND side='BUY' AND status IN ('ready','retry')",(item['cohort_id'],)).fetchone():
                continue
            sid=self.store._add_snapshot_locked(replace(snapshot,ingested_at=ing))
            filled_at=max(recorded_at,utcnow())
            if filled_at>parse_time(item['expires_at']):continue
            projected=self.store._project_chain_meme_trader_market_entry(version=item['version'],cohort_id=item['cohort_id'],
                token_id=token.token_id,snapshot_id=sid,market_price=snapshot.price_usd,filled_at=iso(filled_at),
                reason=item['reason']+':'+VERSION,definition={**definition,'policy_notional_usd':item['notional']},
                funding_mode=item['funding_mode'],signal_price_usd=item['signal_price_usd'])
            self.record(item,'PROJECTED' if projected else 'NO_ACCOUNT_PROJECTED',result)
            if projected:self.pending.pop(key);self.save()
