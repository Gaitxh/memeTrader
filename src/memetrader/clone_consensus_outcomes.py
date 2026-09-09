"""Prospective, unfunded consensus outcomes using persisted snapshot callbacks."""
import math
from .models import iso, parse_time, canonical_token_address
from .paper_execution import buy_terms, sell_terms
from .safety_veto_shadow import SafetyVetoShadow

KEY='clone-consensus-outcomes106'


class CloneConsensusOutcomes(SafetyVetoShadow):
    def capture_signal(self, evidence_id, token_id, pool, anchor, costs, now):
        # Only called after a newly inserted, globally deduplicated evidence row.
        item={'version':'consensus106','cohort_id':evidence_id,'token_id':token_id,
              'pool':pool,'requested_at':iso(now),'notional':5,'shadow_costs':costs}
        super().capture(item,'WAIT_HAZARD',{'reasons':['consensus_selected']},
                        anchor,['clone_consensus_leader_v2'],now)
        key=f'consensus106:{evidence_id}:WAIT_HAZARD'
        row=self.state['pending'].get(key)
        if row:
            row.update(category='CONSENSUS',status='PENDING',evidence_id=evidence_id,
                       safety_recorded_at=anchor['observed_at'],
                       last_recorded_at=anchor['recorded_at'],first_floor=None,first_positive=None)

    def observe(self, token_id, snap, ingested, recorded):
        pool=canonical_token_address(snap.chain,str((snap.raw.get('pair') or snap.raw).get('pairAddress') or ''))
        for row in self.state['pending'].values():
            if row['token_id']!=token_id or row['pool']!=pool or not pool:continue
            if not row['anchor'].get('eligible'):continue
            if not (parse_time(row['last_recorded_at'])<snap.observed_at<=ingested<=recorded
                    and (recorded-snap.observed_at).total_seconds()<=30):continue
            if (snap.observed_at-parse_time(row['anchor']['observed_at'])).total_seconds()>14700:continue
            clocks={'observed_at':iso(snap.observed_at),'ingested_at':iso(ingested),
                    'recorded_at':iso(recorded),'provider':snap.provider,'pool':pool}
            liq=snap.liquidity_usd;price=snap.price_usd
            if liq is not None and math.isfinite(liq) and liq>=0:
                if liq<row['costs'].get('min_pool_liquidity_usd',1000) and row['first_floor'] is None:
                    row['first_floor']={**clocks,'liquidity_usd':liq}
                    self.state['floor_episodes']=self.state.get('floor_episodes',0)+1
                elif liq>=row['costs'].get('min_pool_liquidity_usd',1000) and price is not None and math.isfinite(price) and price>0:
                    terms=buy_terms(5,row['anchor']['price_usd'],row['costs'])
                    net=sell_terms(terms['quantity_tokens'],price,row['costs'])['net_usd']/terms['total_cost_usd']-1
                    if net>0 and row['first_positive'] is None:row['first_positive']={**clocks,'costed_return':net}
            # Parent resolves each fixed horizon's first eligible natural frame.
            # Temporarily isolate this row to retain strict inter-frame causality.
            pending=self.state['pending'];self.state['pending']={'current':row}
            try:super().observe(token_id,snap,ingested,recorded)
            finally:self.state['pending']=pending
            for result in row['results'].values():
                if result['status']=='OBSERVED_SHADOW':
                    result['status']='OBSERVED'
                    result['prior_floor_hazard']=row['first_floor']
                    result['first_positive']=row['first_positive']
                    result['path_order']='FLOOR_FIRST' if row['first_floor'] and (not row['first_positive'] or row['first_floor']['observed_at']<row['first_positive']['observed_at']) else ('POSITIVE_FIRST' if row['first_positive'] else 'UNKNOWN')
            row['last_recorded_at']=iso(recorded);self.dirty=True

    def snapshot(self):
        state=super().snapshot()
        return {**state,'group_unit':'one newly inserted consensus decision evidence; never historical backfill',
                'interpretation':'fixed-horizon sampled price proxy, not fill or executable survival; floor order is observed-only and gaps remain unknown',
                'future_path_coverage':'UNKNOWN_BETWEEN_SAMPLES'}
