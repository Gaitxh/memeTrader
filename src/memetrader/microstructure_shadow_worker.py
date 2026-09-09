"""119 prospective rare-signal Shadow, existing idle tick and snapshot callbacks."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import time

from .market_microstructure import TradePageClient, MicrostructureShadow, classify_page, unknown
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
        self.seen=saved.get('seen',[])[-512:]
        self.counts=saved.get('counts',{})
        self.task=None;self.last_flush=0.
        @asynccontextmanager
        async def permit():
            # Shared HttpClient arbitration rechecks pending held demand at
            # actual host start. Existing traffic count reserves headroom.
            starts=getattr(http,'_gecko_starts',())
            yield bool(idle().is_set() and sum(t>time.monotonic()-60 for t in starts)<8)
        self.client=TradePageClient(http,permit=permit)

    def count(self, reason):self.counts[reason]=self.counts.get(reason,0)+1

    def enqueue(self,item):
        key=f"{item['version']}:{item['cohort_id']}"
        if key in self.seen:return
        arms=[r[0] for r in self.store.db.execute(
            "SELECT arm_id FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
            "AND shadow_cohort_id=? AND status='admitted' LIMIT 256",(item['version'],item['cohort_id']))]
        if not SOURCES.intersection(arms):return
        self.seen=(self.seen+[key])[-512:]
        if len(self.pending)>=8:
            self.count('QUEUE_CAPACITY');return
        self.pending[key]={**item,'arms':sorted(SOURCES.intersection(arms))}
        self.count('candidate')
        # Persist rare admission with existing safety transaction; no per-quote I/O.
        self.save()

    def save(self):
        now=utcnow()
        state=dict(pending=self.pending,anchors=self.anchors,seen=self.seen,counts=self.counts,
            requests=dict(self.client.counts),shadow=self.shadow.snapshot(now),
            decision_eligible=False,affects='none',paper_arms_registered=False)
        self.store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) '
            'ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
            (KEY,json.dumps(state),iso(now)))

    def note_safety(self,item,status,assessment):
        key=f"{item['version']}:{item['cohort_id']}"
        pending=self.pending.get(key)
        if pending is not None and status.startswith('REJECT'):
            reasons=(assessment or {}).get('hard_veto',[])+(assessment or {}).get('reasons',[])
            pending['safety_reject']=reasons or [status]
            pending['hard_unsellable']=any('cannot_sell' in r or r in {'is_honeypot','honeypot'} for r in reasons)
            self.save()

    def kick(self):
        if (self.idle().is_set() and self.pending and time.monotonic()>=self.client.next_start
                and (self.task is None or self.task.done())):
            self.task=asyncio.create_task(self.work())

    async def work(self):
        key,item=next(iter(self.pending.items()))
        now=utcnow()
        if item.get('safety_reject'):
            result=unknown('COMMON_SAFETY_REJECT',safety_reasons=item['safety_reject'])
            if item.get('hard_unsellable'):result['state']='HARD_UNSELLABLE'
        elif parse_time(item['expires_at'])<now:
            result=unknown('SIGNAL_EXPIRED')
        elif item['token_id'].startswith('solana:'):
            # Existing amountful evidence is consulted; no Solana network call.
            with self.store._lock:
                rows=self.store._capital_evidence(item['token_id'],item['pool'],now,('amountful_flow',))['amountful_flow']
            result=unknown('AMOUNTFUL_WALLET_ADAPTER_REQUIRED' if rows else 'NO_COMPLETE_AMOUNTFUL',
                           evidence_ids=[r['id'] for r in rows])
        else:
            try:
                async with asyncio.timeout(3):
                    page=await self.client.fetch(item['token_id'],item['pool'])
                if page.get('reason') in {'BUDGET_OR_BACKOFF','HELD_PRIORITY'}:
                    return  # Same pending episode, bounded by original expiry.
                end=parse_time(item['requested_at'])
                result=classify_page(page,token_id=item['token_id'],pool=item['pool'],
                    window_start=end-timedelta(minutes=10),window_end=end,decision_at=utcnow())
            except TimeoutError:
                result=unknown('REQUEST_TIMEOUT')
        now=utcnow()
        result={**result,'token_id':item['token_id'],'pool':item['pool'],'recorded_at':iso(now),
                'signal_at':item['requested_at'],'source_arms':item['arms']}
        with self.store._lock:
            self.store.record_chain_meme_pattern_evidence(item['token_id'],item['pool'],
                'market_microstructure_classifier_v1',result,observed_at=now,source_key=key)
            self.pending.pop(key,None);self.count(result['state'])
            if len(self.anchors)<32:
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
                observed_at=iso(snap.observed_at),ingested_at=iso(ingested),recorded_at=iso(recorded),eligible=True)
            self._capture(key,entry,anchor,recorded)

    def _capture(self,key,entry,anchor,now):
        if anchor is None:
            anchor=dict(eligible=False,price_usd=None,observed_at=iso(now),recorded_at=iso(now))
            self.count('NO_STRICT_NEXT_ANCHOR')
        item=entry['item']
        self.shadow.capture(evidence_id=key,evidence=entry['result'],token_id=item['token_id'],
            pool=item['pool'],anchor=anchor,now=now,costs=item['shadow_costs'])
        self.anchors.pop(key,None)

    def flush(self):
        now=time.monotonic()
        if now-self.last_flush>=15 and self.idle().is_set():
            with self.store._lock:
                for key,entry in list(self.anchors.items()):
                    if (utcnow()-parse_time(entry['classified_at'])).total_seconds()>120:
                        self._capture(key,entry,None,utcnow())
                self.save()
            self.last_flush=now
