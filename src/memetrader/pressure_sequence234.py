"""Independent activity-before-price Paper entries; bounded, causal and request-free.

Reported five-minute aggregates are activity proxies, never signed wallet flow.
These are prospective hypotheses. No historical outcome selects a live candidate.
"""
from __future__ import annotations
from collections import Counter, OrderedDict
from copy import deepcopy
from typing import Any, Mapping
from .models import canonical_token_address, iso, parse_time
from .impulse_retest230 import number, policies as retest_policies, RUNNER as RETEST_RUNNER

VERSION = 'pressure-sequence234/v1'
YOUNG = 'pressure234_young_runner_v1'
MATURE = 'pressure234_mature_fast_v1'
HYBRID = 'retest234_scaleout_runner_v1'
ARMS = (YOUNG, MATURE, HYBRID)
PARENT = 'trajectory144_trend_runner_v1'
MAX_POOLS = 512
MAX_FIRED = 2048
MAX_GAP = 35
TTL = 90


class Tracker:
    def __init__(self, started_at: Any):
        self.started_at = parse_time(started_at)
        self.states: OrderedDict = OrderedDict()
        self.fired: OrderedDict = OrderedDict()
        self.counts = Counter()

    def _frame(self, frame, now):
        try:
            if any(not frame.get(k) for k in ('observed_at','ingested_at','recorded_at')):
                return None
            o, i, r = (parse_time(frame[k]) for k in ('observed_at','ingested_at','recorded_at'))
            chain = str(frame['chain']).lower()
            token = str(frame['token_id'])
            address = canonical_token_address(chain, token.split(':',1)[1])
            pool = canonical_token_address(chain, str(frame['pair_address']))
            provider = str(frame.get('provider') or '')
            if not (chain in ('solana','bsc','robinhood') and address and pool
                    and token == chain+':'+address and self.started_at <= o <= i <= r <= now
                    and 0 <= (now-o).total_seconds() <= 30
                    and provider.startswith(('dexscreener','geckoterminal'))):
                return None
            values = {k:number(frame.get(k)) for k in
                      ('price_usd','liquidity_usd','volume_5m_usd','buys_5m','sells_5m','pool_age_seconds')}
            if any(v is None or v < 0 for v in values.values()) or values['price_usd'] <= 0:
                return None
            return dict(values, token_id=token, pair_address=pool, chain=chain,
                        provider=provider, observed_at=iso(o), ingested_at=iso(i),
                        recorded_at=iso(r)), o, r
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def _seed(self, key, row, observed, recorded, arm):
        self.states[key] = dict(first=row, pressure=None, arm=arm,
                               last_at=observed, last_recorded=recorded, first_at=observed)
        self.states.move_to_end(key)
        if len(self.states) > MAX_POOLS:
            self.states.popitem(last=False)
            self.counts['capacity_evicted'] += 1
        self.counts['baseline_seeded'] += 1

    def accept(self, frame: Mapping[str, Any], now: Any, *, floor: float):
        now = parse_time(now)
        parsed = self._frame(frame, now)
        if parsed is None:
            self.counts['invalid_or_unknown'] += 1
            return {}
        row, observed, recorded = parsed
        key = (row['token_id'], row['pair_address'])
        threshold = number(floor)
        if threshold is None or threshold <= 0 or row['liquidity_usd'] < max(2000., threshold):
            self.states.pop(key, None)
            self.counts['strategy_depth_floor'] += 1
            return {}
        age = row['pool_age_seconds']
        arm = YOUNG if row['chain']=='solana' and age<=3600 else MATURE if age>=21600 else None
        if arm is None or (key,arm) in self.fired:
            return {}
        state = self.states.get(key)
        if state and observed <= state['last_recorded']:
            self.counts['duplicate_or_noncausal'] += 1
            return {}
        if state and (state['first']['provider'] != row['provider'] or state['arm'] != arm
                      or (observed-state['last_at']).total_seconds()>MAX_GAP
                      or (observed-state['first_at']).total_seconds()>TTL):
            self.states.pop(key, None)
            self.counts['episode_boundary_reset'] += 1
            state = None
        if state is None:
            self._seed(key,row,observed,recorded,arm)
            return {}
        state.update(last_at=observed,last_recorded=recorded)
        self.states.move_to_end(key)
        a = state['first']; b = state['pressure']; price = row['price_usd']
        share = row['buys_5m']/(row['buys_5m']+row['sells_5m']) if row['buys_5m']+row['sells_5m']>0 else None
        if price < .98*a['price_usd'] or row['liquidity_usd'] < .95*a['liquidity_usd']:
            self.counts['structure_reset'] += 1
            self._seed(key,row,observed,recorded,arm)
            return {}
        if b is None:
            if price > 1.04*a['price_usd']:
                self.counts['price_led_not_activity_led'] += 1
                self._seed(key,row,observed,recorded,arm)
                return {}
            ready = ((observed-state['first_at']).total_seconds()>=10
                     and row['buys_5m']-a['buys_5m']>=max(3,.25*a['buys_5m'])
                     and row['volume_5m_usd']>=1.2*a['volume_5m_usd']
                     and row['volume_5m_usd']-a['volume_5m_usd']>=100
                     and row['buys_5m']+row['sells_5m']>=8
                     and row['volume_5m_usd']>=500 and share is not None and share>=.55)
            if ready:
                state['pressure']=row
                self.counts['pressure_before_price'] += 1
            return {}
        anchor = max(a['price_usd'],b['price_usd'])
        if price>1.15*anchor or row['liquidity_usd']<.95*b['liquidity_usd']:
            self.counts['late_or_depth_lost'] += 1
            self._seed(key,row,observed,recorded,arm)
            return {}
        ready = ((observed-parse_time(b['observed_at'])).total_seconds()>=5
                 and price>=1.025*anchor and row['buys_5m']>=b['buys_5m']
                 and row['volume_5m_usd']>=b['volume_5m_usd']
                 and row['sells_5m']>=1 and share is not None and share>=.55)
        if not ready:
            return {}
        self.states.pop(key,None)
        self.fired[(key,arm)]=None
        if len(self.fired)>MAX_FIRED:
            self.fired.popitem(last=False)
        self.counts['signal:'+arm] += 1
        decision_key=f'{VERSION}:{arm}:{key[0]}:{key[1]}:{a["observed_at"]}'
        return {arm:dict(episode_id=decision_key,decision_key=decision_key,
            selected=dict(token_id=key[0],pair_address=key[1]),
            observed_at=row['observed_at'],recorded_at=row['recorded_at'],
            decision_evidence=dict(version=VERSION,mode=arm,first=deepcopy(a),
                pressure=deepcopy(b),confirmation=deepcopy(row),feature_vector=deepcopy(row),
                interpretation='reported rolling activity, not signed capital or wallet breadth',
                extra_collector_requests=0))}

    def snapshot(self):
        return dict(version=VERSION,started_at=iso(self.started_at),pools=len(self.states),
                    counts=dict(self.counts),max_pools=MAX_POOLS,max_fired=MAX_FIRED,
                    extra_collector_requests=0)


def hybrid_signal(parent):
    if not isinstance(parent,Mapping) or not parent.get('decision_key'):
        return {}
    result=deepcopy(dict(parent))
    result['decision_key']+=':'+HYBRID
    result.setdefault('decision_evidence',{}).update(mode=HYBRID,
        pressure234_source_arm=RETEST_RUNNER,pressure234_exit_hypothesis='bank_half_keep_right_tail')
    return {HYBRID:result}


def policies(parent):
    base=retest_policies(parent)[1]
    result=[]
    for arm in ARMS:
        p=deepcopy(base)
        p.update(arm_id=arm,canonical_id=arm,entry_family=arm,
                 feature_contract=VERSION,source_arm_ids=[],entry_match_mode='isolated_cohort_observer',
                 name={YOUNG:'Activity before price: young runner',MATURE:'Activity before price: old-pool fast',
                       HYBRID:'Retest: bank half, keep the trend'}[arm],
                 max_hold_minutes=5 if arm==MATURE else 30,
                 hard_stop_return=-.15 if arm==MATURE else -.20,
                 trailing_activate_return=.20 if arm==MATURE else .30,
                 trailing_drawdown=.10 if arm==MATURE else .15,
                 notional_usd=20.,requires_distinct_trajectory_frame=False,
                 requires_distinct_wide_frame=False,paired_opportunity_group=VERSION+':'+arm)
        p['entry_filter']=dict(direction=arm,max_concurrent_positions=8,
            single_token_lifetime_entry=True,single_token_open_or_reserved=True)
        p['take_profit']=([{'return':.12,'fraction_of_remaining':1.0}] if arm==MATURE else
                          [{'return':.15,'fraction_of_remaining':.5},
                           {'return':.50,'fraction_of_remaining':.5}])
        p['entry_rules234']=('Three as-of same-provider original-pool observations: activity expands '
            'before price; later 2.5% price acceptance, not >15% chase.10s/5s spacing,90s expiry,35s gap.'
            'Young Solana<=1h or mature supported chain>=6h.2000U or configured floor, whichever higher.')
        p['description']=p['entry_rules234']+' 20U Paper; independent bounded account; hypothesis not alpha.'
        p['research_only_claim']='Natural costs/losses decide retention; no hindsight or guaranteed fill.'
        if arm==HYBRID:
            p.update(feature_contract='impulse-retest230/v1',entry_alias_of=RETEST_RUNNER,
                     source_arm_ids=[RETEST_RUNNER],paired_opportunity_group='impulse-retest230/v1',
                     paired_opportunity_semantics='common actual source BUY only; scaleouts versus existing fast/runner',
                     entry_rules234='Exact existing230 trigger; only partial-profit exits differ from runner.',
                     description='Same230 retest entry and runner stops/horizon; +15% economic return sells '
                                 'half remaining,+50% sells half remaining; tail retains30m/trailing.20U/cap8.'
                                 ' Each actual partial fill incurs configured costs; unknown quote does not fill.')
        else:
            p.pop('entry_alias_of',None)
        result.append(p)
    return result
