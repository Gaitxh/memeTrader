"""119 prospective rare-signal Shadow, existing idle tick and snapshot callbacks."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import time
import hashlib
import math
from collections import Counter

from .market_microstructure import TradePageClient, MicrostructureShadow, classify_page, classify_amountful, unknown, VERSION, branch_decision, BRANCH_LIMITS, observed_paper_surface
from .models import utcnow, iso, parse_time, canonical_token_address

KEY='market-microstructure-shadow119'
SOURCES={'event_reawakening_v1','quiet_renewal_v1','clone_liquidity_leader_v1',
         'clone_m5volume_leader_v1','prebreakout_net_accumulation_v1'}


class MicrostructureWorker:
    def __init__(self, store, http, idle):
        self.store, self.idle = store, idle
        saved=store.get_kv(KEY,{}) or {}
        self.shadow=MicrostructureShadow(saved.get('shadow'))
        self.pending=saved.get('pending',{})
        self.anchors=saved.get('anchors',{})
        self.ready=saved.get('ready',{})
        self.recent=saved.get('recent',{})
        self.seen=saved.get('seen',[])[-512:]
        self.counts=saved.get('counts',{})
        self.task=None;self.last_flush=0.;self.last_watch=0.
        @asynccontextmanager
        async def permit():
            # Shared HttpClient arbitration rechecks pending held demand at
            # actual host start. Existing traffic count reserves headroom.
            starts=getattr(http,'_gecko_starts',())
            from .collectors import GECKO_LOW_START_ALLOWED
            allowed=lambda: idle().is_set() and sum(t>time.monotonic()-60 for t in starts)<8
            context=GECKO_LOW_START_ALLOWED.set(allowed)
            try:yield bool(hasattr(http,'_reserve_gecko_request_start') and allowed())
            finally:GECKO_LOW_START_ALLOWED.reset(context)
        self.client=TradePageClient(http,permit=permit)
        self.client.counts=Counter(saved.get('requests',{}))
        if saved.get('next_request_at'):
            self.client.next_start=time.monotonic()+max(0,(parse_time(saved['next_request_at'])-utcnow()).total_seconds())

    def count(self, reason):self.counts[reason]=self.counts.get(reason,0)+1

    def enqueue(self,item):
        arms=[r[0] for r in self.store.db.execute(
            "SELECT arm_id FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
            "AND shadow_cohort_id=? AND status='admitted' LIMIT 256",(item['version'],item['cohort_id']))]
        if not SOURCES.intersection(arms):return
        cohort=self.store.db.execute('SELECT feature_json,entry_family FROM chain_meme_trader_v6_cohorts WHERE id=?',
                                     (item['cohort_id'],)).fetchone()
        feature=json.loads(cohort['feature_json']) if cohort else {}
        events={arm:feature.get('event_keys',{}).get(arm) for arm in sorted(SOURCES.intersection(arms))}
        identity=json.dumps([item['version'],item['token_id'],item['pool'],events if any(events.values()) else item['cohort_id']],sort_keys=True)
        key=hashlib.sha256(identity.encode()).hexdigest()
        self._enqueue(key,{**item,'arms':sorted(SOURCES.intersection(arms)),
            'event_keys':events,'reactivation':bool(cohort and cohort['entry_family']=='reawakening'
                and feature.get('reactivation_ready') and 'event_reawakening_v1' in arms)})

    def _enqueue(self,key,item):
        with self.store._lock, self.store.db:
            self._enqueue_locked(key,item)

    def _enqueue_locked(self,key,item):
        if key in self.seen:return
        self.seen=(self.seen+[key])[-512:]
        if self.store.db.execute('SELECT 1 FROM chain_meme_pattern_evidence WHERE definition_version=? AND kind=? AND source_key=?',
                (item['version'],'microstructure_enrollment119',key)).fetchone():return
        # Unique append receipt survives bounded in-memory eviction and restart.
        capacity=8 if item.get('postbuy') else 7  # Reserve one existing slot for held risk work.
        if self.store.record_chain_meme_pattern_evidence(item['token_id'],item['pool'],
                'microstructure_enrollment119',{**item,'enrollment_status':'QUEUE_CAPACITY' if len(self.pending)>=capacity else 'ENROLLED'},
                observed_at=parse_time(item['requested_at']),source_key=key) is None:return
        if len(self.pending)>=capacity:
            self.count('QUEUE_CAPACITY');self.save();return
        self.pending[key]=item
        self.count('candidate')
        # Persist rare admission with existing safety transaction; no per-quote I/O.
        self.save()

    def admit_watch(self,watch,costs):
        """Cheap existing-watch supply, one admission per idle 15s; no DB scan."""
        now=utcnow()
        if time.monotonic()-self.last_watch<15 or not self.idle().is_set():return
        self.last_watch=time.monotonic()
        if len(self.pending)>=8:return
        with self.store._lock:
            held=self.store.db.execute("SELECT p.token_id,p.shadow_cohort_id,p.opened_at,c.pair_address "
                "FROM chain_meme_trader_positions p JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id "
                "WHERE p.definition_version=? AND p.arm_id='synthetic_fast_harvest_v1' AND p.status='open' LIMIT 1",
                (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,)).fetchone()
            if held:
                key=f"held137:{held['shadow_cohort_id']}:{int(now.timestamp())//60}"
                if key not in self.seen:
                    self._enqueue(key,dict(version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
                        token_id=held['token_id'],pool=held['pair_address'],requested_at=iso(now),
                        expires_at=iso(now+timedelta(seconds=60)),opened_at=held['opened_at'],
                        arms=['synthetic_fast_harvest_v1'],postbuy=True,shadow_costs=costs))
                    return
        for token_id,w in watch.items():
            s=w['quote'];created=w.get('pool_created_at_ms');pool=w.get('pair_address')
            age=now.timestamp()-float(created or 0)/1000
            if (w.get('bucket')!='early' or not pool or not 0<=age<=900 or s.price_usd is None
                or not math.isfinite(s.price_usd) or s.price_usd<=0 or s.liquidity_usd is None
                or not math.isfinite(s.liquidity_usd) or s.liquidity_usd<1000
                or not 0<=(now-s.observed_at).total_seconds()<=30
                or (s.buys_5m or 0)+(s.sells_5m or 0)<3):continue
            key=hashlib.sha256(f'early:{token_id}:{pool}:{created}'.encode()).hexdigest()
            if key in self.seen:continue
            with self.store._lock:
                self._enqueue(key,dict(version=self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
                    token_id=token_id,pool=pool,requested_at=iso(now),expires_at=iso(now+timedelta(seconds=120)),
                    arms=['organic_early_flow_v1'],early=True,pool_created_at_ms=created,shadow_costs=costs))
            break

    def save(self):
        now=utcnow()
        state=dict(pending=self.pending,anchors=self.anchors,ready=self.ready,recent=self.recent,seen=self.seen,counts=self.counts,
            requests=dict(self.client.counts),shadow=self.shadow.snapshot(now),
            next_request_at=iso(now+timedelta(seconds=max(0,self.client.next_start-time.monotonic()))),
            decision_eligible=True,affects='common_paper_signals',
            synthetic_funding='CONDITIONAL_COMMON_PREFLIGHT_REQUIRED')
        self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
            (KEY,json.dumps(state),iso(now)))

    def note_safety(self,item,status,assessment):
        receipt=(assessment or {}).get('exact_pool_sell_simulation')
        targets=list(self.pending.values())+[e['item'] for e in self.anchors.values()]
        for pending in targets:
            if pending.get('version')!=item['version'] or pending.get('cohort_id')!=item['cohort_id']:continue
            if assessment is not None:pending['safety_checked']=True
            pending['safety_allow']=bool((assessment or {}).get('allow')) and status.startswith('BUY_AUTHORIZED_')
            if receipt:pending['sell_simulation']=receipt
            if not status.startswith('REJECT'):continue
            reasons=(assessment or {}).get('hard_veto',[])+(assessment or {}).get('reasons',[])
            pending['safety_reject']=reasons or [status]
            pending['hard_unsellable']=any('cannot_sell' in r or r in {'is_honeypot','honeypot'} for r in reasons)
            self.save()

    def kick(self):
        if self.task is not None and self.task.done() and not self.task.cancelled():
            if self.task.exception() is not None:self.count('WORKER_ERROR')
            self.task=None
        if (self.idle().is_set() and self.pending and time.monotonic()>=self.client.next_start
                and (self.task is None or self.task.done())):
            self.task=asyncio.create_task(self.work())

    async def work(self):
        now=utcnow()
        # Let the existing safety request provide its exact-pool receipt first.
        # Other ready episodes still advance; no extra request or head-of-line wait.
        selected=next(((key,item) for key,item in sorted(self.pending.items(),key=lambda x:not x[1].get('postbuy'))
            if not item.get('cohort_id') or item.get('safety_checked')
            or parse_time(item['expires_at'])<now),None)
        if selected is None:return
        key,item=selected
        if item.get('safety_reject'):
            result=unknown('COMMON_SAFETY_REJECT',safety_reasons=item['safety_reject'])
            if item.get('hard_unsellable'):result['state']='HARD_UNSELLABLE'
        elif parse_time(item['expires_at'])<now:
            result=unknown('SIGNAL_EXPIRED')
        elif item['token_id'].startswith('solana:'):
            # Existing amountful evidence is consulted; no Solana network call.
            with self.store._lock:
                rows=self.store._capital_evidence(item['token_id'],item['pool'],now,('amountful_flow',))['amountful_flow']
            result=(classify_amountful(rows[0]['payload'],token_id=item['token_id'],pool=item['pool'],decision_at=now)
                    if rows else unknown('NO_COMPLETE_AMOUNTFUL'))
            result['evidence_ids']=[r['id'] for r in rows[:1]]
        else:
            try:
                # Bounded indexed token tail; no full-history materialization.
                with self.store._lock:
                    rows=self.store.db.execute('SELECT observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,raw_json FROM token_snapshots '
                        'WHERE token_id=? AND observed_at<=? ORDER BY observed_at DESC LIMIT 128',
                        (item['token_id'],item['requested_at'])).fetchall()
                frames=[];end=parse_time(item['requested_at']);start=end-timedelta(minutes=10)
                if item.get('postbuy'):start=max(start,parse_time(item['opened_at']))
                for r in reversed(rows):
                    p=json.loads(r['raw_json']);pair=p.get('pair') or p
                    if not r['recorded_at'] or not r['ingested_at']:continue
                    observed=parse_time(r['observed_at']);recorded=parse_time(r['recorded_at'])
                    if (canonical_token_address(item['token_id'].split(':')[0],str(pair.get('pairAddress') or ''))==item['pool']
                        and start<=observed<=parse_time(r['ingested_at'] or r['observed_at'])<=recorded<=end):
                        frames.append(dict(token_id=item['token_id'],pool=item['pool'],observed_at=iso(observed),
                            recorded_at=iso(recorded),price_usd=r['price_usd'],liquidity_usd=r['liquidity_usd']))
                # Provider/observer copies are one observation, not a trajectory.
                # Optional price endpoints must never collapse the signed-flow window.
                frames=list({f['observed_at']:f for f in frames}.values())
                if len(frames)>=2 and parse_time(frames[0]['observed_at'])<parse_time(frames[-1]['observed_at']) and (end-parse_time(frames[-1]['observed_at'])).total_seconds()<=30:
                    start=parse_time(frames[0]['observed_at']);end=parse_time(frames[-1]['observed_at'])
                else:frames=[]
                async with asyncio.timeout(3):
                    page=await self.client.fetch(item['token_id'],item['pool'])
                if page.get('reason') in {'BUDGET_OR_BACKOFF','HELD_PRIORITY','GeckoLowPriorityDeferred'}:
                    return  # Same pending episode, bounded by original expiry.
                result=classify_page(page,token_id=item['token_id'],pool=item['pool'],
                    window_start=start,window_end=end,decision_at=utcnow(),price_frames=frames,
                    sell_simulation=item.get('sell_simulation'))
                if item.get('early') and not item.get('postbuy'):
                    from .market_microstructure import classify_short_page
                    result['short_observed']=classify_short_page(page,token_id=item['token_id'],
                        pool=item['pool'],signal_at=item['requested_at'],decision_at=utcnow())
            except TimeoutError:
                result=unknown('REQUEST_TIMEOUT')
        now=utcnow()
        result={**result,'token_id':item['token_id'],'pool':item['pool'],'recorded_at':iso(now),
                'signal_at':item['requested_at'],'source_arms':item['arms']}
        if result.get('phase')=='SYNTHETIC_LPI_BUILDING':branch='synthetic_building_shadow'
        elif result.get('phase')=='SYNTHETIC_DISTRIBUTING_CYCLE':branch='synthetic_distribution_hazard'
        elif result['state']=='ORGANIC_BREADTH_NET_BUY' and item.get('reactivation'):branch='organic_reawakening_flow_v1'
        elif result['state'] in {'ORGANIC_BREADTH_NET_BUY','ORGANIC_BOOTSTRAP_SPREADING'} and item.get('early'):branch='organic_early_flow_v1'
        else:branch='UNKNOWN_OR_INELIGIBLE'
        result.update(branch=branch,funding_gate='AWAIT_STRICT_ORIGINAL_POOL_FRAME_AND_COMMON_SAFETY',
                      episode_keys=item.get('event_keys',{}))
        with self.store._lock, self.store.db:
            self.recent[item['token_id']+'|'+item['pool']]=result
            while len(self.recent)>64:self.recent.pop(next(iter(self.recent)))
            self.store.record_chain_meme_pattern_evidence(item['token_id'],item['pool'],
                VERSION,result,observed_at=now,source_key=key)
            self.pending.pop(key,None);self.count(result['state'])
            if item.get('postbuy'):
                self.count('POSTBUY_CLASSIFIED')
            elif len(self.anchors)<32:
                self.anchors[key]=dict(item=item,result=result,classified_at=iso(now))
            else:self.count('ANCHOR_CAPACITY')
            self.save()

    def observe(self,token_id,snap,ingested,recorded):
        self.shadow.observe(token_id,snap,ingested,recorded)
        pool=canonical_token_address(snap.chain,str((snap.raw.get('pair') or snap.raw).get('pairAddress') or ''))
        for key,entry in list(self.anchors.items()):
            item=entry['item'];at=parse_time(entry['classified_at'])
            if (recorded-at).total_seconds()>120:
                self._capture(key,entry,None,recorded);continue
            if (token_id!=item['token_id'] or pool!=item['pool']
                    or not at<snap.observed_at<=ingested<=recorded
                    or (recorded-snap.observed_at).total_seconds()>30):continue
            import math
            if (snap.price_usd is None or not math.isfinite(snap.price_usd) or snap.price_usd<=0
                    or snap.liquidity_usd is None or not math.isfinite(snap.liquidity_usd) or snap.liquidity_usd<1000):continue
            anchor=dict(price_usd=snap.price_usd,liquidity_usd=snap.liquidity_usd,
                observed_at=iso(snap.observed_at),ingested_at=iso(ingested),recorded_at=iso(recorded),eligible=True,
                surface=observed_paper_surface(snap,ingested,recorded))
            self._capture(key,entry,anchor,recorded)

    def _capture(self,key,entry,anchor,now):
        if anchor is None:
            anchor=dict(eligible=False,price_usd=None,observed_at=iso(now),recorded_at=iso(now))
            self.count('NO_STRICT_NEXT_ANCHOR')
        item=entry['item']
        route=branch_decision(entry['result'],token_id=item['token_id'],pool=item['pool'],
            frame_observed=anchor['observed_at'],frame_recorded=anchor['recorded_at'],
            price=anchor.get('price_usd'),liquidity=anchor.get('liquidity_usd'),
            safety_allow=item.get('safety_allow',False),hard_veto=bool(item.get('safety_reject')),
            surface=anchor.get('surface'),require_safety=False,
            sell_simulation=item.get('sell_simulation'),
            reawakening=item.get('reactivation',False),early=item.get('early',False),
            pool_age_seconds=(now.timestamp()-item['pool_created_at_ms']/1000) if item.get('pool_created_at_ms') else None)
        entry['result']['route']=route
        arms={'ORGANIC_SHADOW_ELIGIBLE':'organic_reawakening_flow_v1',
              'ORGANIC_EARLY_SHADOW_ELIGIBLE':'organic_early_flow_v1',
              'SYNTHETIC_SHADOW_ELIGIBLE':'synthetic_fast_harvest_v1',
              'SYNTHETIC_PENDING_PROOF':'synthetic_fast_harvest_v1'}
        arm=arms.get(route)
        entry['result']['funding_gate']='COMMON_SAFETY_AND_STRICT_NEXT_PENDING' if arm else 'NO_FUNDED_SIGNAL'
        self._ready_signal(key,item,entry['result'],anchor,now,arm)
        short=entry['result'].get('short_observed')
        if short:
            short={**short,'token_id':item['token_id'],'pool':item['pool'],
                'recorded_at':entry['result']['recorded_at']}
            short_route=branch_decision(short,token_id=item['token_id'],pool=item['pool'],
                frame_observed=anchor['observed_at'],frame_recorded=anchor['recorded_at'],
                price=anchor.get('price_usd'),liquidity=anchor.get('liquidity_usd'),
                safety_allow=False,hard_veto=bool(item.get('safety_reject')),
                surface=anchor.get('surface'),require_safety=False,early=True,
                pool_age_seconds=(now.timestamp()-item['pool_created_at_ms']/1000) if item.get('pool_created_at_ms') else None)
            short_arm='organic_short_observed_flow_v1' if short_route=='ORGANIC_EARLY_SHADOW_ELIGIBLE' else None
            self._ready_signal(key+':short',item,short,anchor,now,short_arm)
            self.count('short_route:'+short_route)
            self.shadow.capture(evidence_id=key+':short',evidence=short,token_id=item['token_id'],
                pool=item['pool'],anchor=anchor,now=now,costs=item['shadow_costs'])
        entry['result']['branch_limits']=BRANCH_LIMITS
        self.count('route:'+route)
        self.shadow.capture(evidence_id=key,evidence=entry['result'],token_id=item['token_id'],
            pool=item['pool'],anchor=anchor,now=now,costs=item['shadow_costs'])
        self.anchors.pop(key,None)

    def _ready_signal(self,key,item,evidence,anchor,now,arm):
        if arm and len(self.ready)<32:
            self.ready[key]=dict(token_id=item['token_id'],pool=item['pool'],arm=arm,
                expires_at=iso(now+timedelta(seconds=60)),signal=dict(
                    episode_id='micro119:'+key,decision_key='micro119:'+key+'|'+arm,
                    selected={'token_id':item['token_id'],'pair_address':item['pool']},
                    observed_at=anchor['observed_at'],recorded_at=anchor['recorded_at'],
                    decision_evidence=evidence))
            self.count('signal:'+arm)

    def signals_for(self,token_id,pool,now):
        """Repeat the same frozen key while pending; common durable claim dedupes."""
        self.ready={k:v for k,v in self.ready.items() if parse_time(v['expires_at'])>=now}
        result={v['arm']:v['signal'] for v in self.ready.values()
                if v['token_id']==token_id and v['pool']==pool}
        from .cohort_experiments import recovered_signal_aliases
        return recovered_signal_aliases(result)

    def hazard_for(self,token_id,pool,opened,now):
        evidence=self.recent.get(token_id+'|'+pool,{})
        at=evidence.get('recorded_at')
        if at and parse_time(opened)<parse_time(at)<=now and (now-parse_time(at)).total_seconds()<=120:
            if evidence.get('phase')=='SYNTHETIC_DISTRIBUTING_CYCLE':return 'synthetic_distribution'
            if evidence.get('state')=='HARD_UNSELLABLE':return 'synthetic_sellability_hazard'
        return None

    def flush(self):
        now=time.monotonic()
        if now-self.last_flush>=15 and self.idle().is_set():
            with self.store._lock, self.store.db:
                for key,entry in list(self.anchors.items()):
                    if (utcnow()-parse_time(entry['classified_at'])).total_seconds()>120:
                        self._capture(key,entry,None,utcnow())
                self.save()
            self.last_flush=now
