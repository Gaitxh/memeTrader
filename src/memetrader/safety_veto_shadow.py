"""Unfunded safety-veto sampled outcomes. No network, replay or trade authority."""
import math
from .models import iso, parse_time, canonical_token_address, utcnow
from .paper_execution import buy_terms, sell_terms

KEY='safety-veto-shadow95'
HORIZONS=(15,60,240)

class SafetyVetoShadow:
    def __init__(self, state=None):
        self.state=state or {'started_at':iso(),'pending':{},'recent':[],'seen':[],
                            'groups':{},'capacity_skipped':0,'triggers':0,'detail_evicted':0}
        self.dirty=False;self.last_flush=0.0

    def capture(self, item, status, assessment, anchor, arms, now):
        if not (status.startswith('REJECT') or status in {'WAIT_HAZARD','WAIT_WEAK'}):return
        if parse_time(item['requested_at']) < parse_time(self.state['started_at']):return
        category='REJECT' if status.startswith('REJECT') else status
        key=f"{item['version']}:{item['cohort_id']}:{category}"
        if key in self.state['seen']:return
        self.state['seen']=(self.state['seen']+[key])[-512:]
        self.state['triggers']+=1;self.dirty=True
        if len(self.state['pending'])>=128:
            self.state['capacity_skipped']+=1;return
        assessment=assessment or {}
        reasons=sorted(set(assessment.get('reasons',[])+assessment.get('hard_veto',[])+assessment.get('soft_hazard',[]))) or (['bsc_only_weak_safety_facts'] if status=='WAIT_WEAK' else ['UNKNOWN_REASON'])
        self.state['pending'][key]={'token_id':item['token_id'],'pool':item['pool'],
            'cohort_id':item['cohort_id'],'category':category,'status':status,'reasons':reasons,
            'hard_veto':assessment.get('hard_veto',assessment.get('reasons',[])),
            'soft_hazard':assessment.get('soft_hazard',[]),'arms':arms,
            'signal_requested_at':item['requested_at'],'safety_source_at':assessment.get('source_at'),
            'safety_recorded_at':iso(now),'anchor':anchor,'notional':item['notional'],
            'costs':item.get('shadow_costs',{}),'results':{}}

    def observe(self, token_id, snap, ingested, recorded):
        if not self.state['pending']:return
        raw=snap.raw or {};pair=raw.get('pair',raw)
        pool=canonical_token_address(snap.chain,str(pair.get('pairAddress') or ''))
        for row in list(self.state['pending'].values()):
            if row['token_id']!=token_id or row['pool']!=pool or not pool:continue
            if not (snap.observed_at<=ingested<=recorded and (recorded-snap.observed_at).total_seconds()<=30):continue
            anchor=row['anchor'];price=snap.price_usd;liq=snap.liquidity_usd
            if not anchor or not anchor.get('eligible'):continue
            if not (price is not None and math.isfinite(price) and price>0 and liq is not None
                    and math.isfinite(liq) and liq>=row['costs'].get('min_pool_liquidity_usd',1000)):continue
            start=parse_time(row['safety_recorded_at'])
            if snap.observed_at<=max(start,parse_time(anchor['recorded_at'])):continue
            for h in HORIZONS:
                if str(h) in row['results']:continue
                delta=(snap.observed_at-start).total_seconds()-h*60
                if not 0<=delta<=300 or (recorded-start).total_seconds()>h*60+300:continue
                terms=buy_terms(row['notional'],anchor['price_usd'],row['costs'])
                net=sell_terms(terms['quantity_tokens'],price,row['costs'])['net_usd']
                row['results'][str(h)]={'status':'OBSERVED_SHADOW','observed_at':iso(snap.observed_at),
                    'ingested_at':iso(ingested),'recorded_at':iso(recorded),'provider':snap.provider,
                    'raw_return':price/anchor['price_usd']-1,
                    'paper_cost_estimated_return':net/terms['total_cost_usd']-1}
                self._aggregate(row,h,row['results'][str(h)]);self.dirty=True

    def _aggregate(self,row,h,result):
        for reason in row['reasons']:
            key=f"{row['token_id'].split(':')[0]}|{row['category']}|{reason}|{h}"
            if key not in self.state['groups'] and len(self.state['groups'])>=256:key='OTHER_BOUNDED'
            g=self.state['groups'].setdefault(key,{'observed':0,'unknown':0,'raw_sum':0.,'costed_sum':0.,'costed_positive':0})
            if result['status']=='UNKNOWN':g['unknown']+=1
            else:
                g['observed']+=1;g['raw_sum']+=result['raw_return'];g['costed_sum']+=result['paper_cost_estimated_return']
                g['costed_positive']+=int(result['paper_cost_estimated_return']>0)

    def expire(self,now):
        for key,row in list(self.state['pending'].items()):
            for h in HORIZONS:
                if str(h) not in row['results'] and (now-parse_time(row['safety_recorded_at'])).total_seconds()>h*60+300:
                    result={'status':'UNKNOWN','reason':'NO_NATURAL_ELIGIBLE_FRAME_OR_ANCHOR'}
                    row['results'][str(h)]=result;self._aggregate(row,h,result);self.dirty=True
            if len(row['results'])==3:
                if len(self.state['recent'])>=128:self.state['detail_evicted']+=1
                self.state['recent']=(self.state['recent']+[row])[-128:]
                self.state['pending'].pop(key);self.dirty=True

    def snapshot(self):
        return {**self.state,'decision_eligible':False,'affects':'none','unfunded':True,
            'horizons_minutes':list(HORIZONS),'grace_seconds':300,
            'interpretation':'sampled reference-price counterfactual; not fill/strategy exit replay or proof of sellability',
            'group_unit':'trigger category per cohort; multiple reasons overlap; no preactivation backfill',
            'source_coverage':'newly persisted token snapshots only; absent observations UNKNOWN'}
