"""Shared bounded observed trajectories. Rolling activity is a proxy, not signed flow.

No acquisition, SQL, wall-clock backfill, outcome fitting or trading authority here.
All thresholds below are frozen experimental definitions, not profitability claims.
"""
from collections import OrderedDict, Counter, deque
from copy import deepcopy
from math import log, isfinite, sqrt
from statistics import mean, pstdev
import hashlib
import json
from .models import iso, parse_time

VERSION = 'dex-trajectory/v1'
WINDOWS = (5, 15, 30, 60, 180, 300)
MAX_POOLS, MAX_FRAMES, TTL = 512, 192, 900
FRICTION = 1.04 / .96 - 1
SPECS = {
    'dex_hot_impulse_v1': ('hot', '同龄局部加速冲量', 15),
    'dex_quiet_acceleration_v1': ('quiet', '静默后活动加速', 30),
    'dex_volume_leads_price_v1': ('volume_leads', '活动领先压缩价格', 15),
    'dex_compression_breakout_v1': ('breakout', '局部压缩后突破', 15),
    'dex_first_dip_resilience_v1': ('first_dip', '首波回撤快速承接', 15),
}
EXIT_ARMS = {
    'dex_profit_velocity_exit_v1': 'velocity',
    'dex_liquidity_divergence_exit_v1': 'liquidity_divergence',
    'dex_blowoff_exit_v1': 'blowoff',
}


def number(value):
    if value is None or isinstance(value, bool): return None
    try: value = float(value)
    except (ValueError, TypeError): return None
    return value if isfinite(value) else None


def ratio(a, b):
    a, b = number(a), number(b)
    return a / b if a is not None and b is not None and b > 0 else None


def activity(row):
    b, s = number(row.get('buys_5m')), number(row.get('sells_5m'))
    return b+s if b is not None and s is not None and b>=0 and s>=0 else None


def window(rows, seconds):
    end = rows[-1]['t']; eligible = [i for i,r in enumerate(rows) if r['t'] <= end-seconds]
    if not eligible: return None
    part = rows[eligible[-1]:]
    if end-part[0]['t'] > seconds+max(5,seconds/3): return None
    if any(b['t']-a['t']>30 for a,b in zip(part,part[1:])): return None
    if len(part)<3: return None
    first,last=part[0],part[-1];span=last['t']-first['t']
    changes=[log(b['price_usd']/a['price_usd']) for a,b in zip(part,part[1:])]
    mid=min(part[1:-1], key=lambda r:abs(r['t']-(first['t']+span/2)))
    v0=log(mid['price_usd']/first['price_usd'])/(mid['t']-first['t'])
    v1=log(last['price_usd']/mid['price_usd'])/(last['t']-mid['t'])
    lr=ratio(last['liquidity_usd'],first['liquidity_usd'])
    return dict(start_at=first['observed_at'],end_at=last['observed_at'],span_seconds=span,
        frames=len(part),return_fraction=last['price_usd']/first['price_usd']-1,
        log_velocity=log(last['price_usd']/first['price_usd'])/span,
        acceleration=v1-v0,curvature='ACCELERATING' if v1>v0 else 'DECELERATING' if v1<v0 else 'FLAT',
        realized_volatility=sqrt(sum(c*c for c in changes)),
        liquidity_change_fraction=lr-1 if lr is not None else None,
        rolling_volume_change_ratio=ratio(last.get('volume_5m_usd'),first.get('volume_5m_usd')),
        rolling_tx_change_ratio=ratio(activity(last),activity(first)))


def derive(rows):
    """Rows are already canonical, causal and deduplicated by Engine.accept."""
    now=rows[-1];p=now['price_usd'];liquidity=now['liquidity_usd'];tx=activity(now)
    wins={str(w):window(rows,w) for w in WINDOWS}
    xs=[r['t']-rows[0]['t'] for r in rows];ys=[log(r['price_usd']) for r in rows]
    mx,my=mean(xs),mean(ys)
    dx=[x-mx for x in xs];dy=[y-my for y in ys]
    xx=sum(x*x for x in dx); yy=sum(y*y for y in dy)
    slope=sum(x*y for x,y in zip(dx,dy))/xx if xx>0 else None
    residual=[y-(my+(slope or 0)*(x-mx)) for x,y in zip(xs,ys)]
    steps=[b-a for a,b in zip(ys,ys[1:])];positive=[x for x in steps if x>0]
    jump_times=[rows[i+1]['t'] for i,x in enumerate(steps) if x>0]
    intervals=[b-a for a,b in zip(jump_times,jump_times[1:])]
    age=number(now.get('pool_age_seconds'))
    turn=ratio(now.get('volume_5m_usd'),liquidity)
    hour_tx=None
    if number(now.get('buys_1h')) is not None and number(now.get('sells_1h')) is not None:
        hour_tx=now['buys_1h']+now['sells_1h']
    # Age-normalized rates use actual available age, not 12x for a 30-second pool.
    m5span=min(300,age) if age is not None and age>0 else None
    h1span=min(3600,age) if age is not None and age>0 else None
    volume_rate=ratio(now.get('volume_5m_usd'),m5span)
    volume_hour_rate=ratio(now.get('volume_1h_usd'),h1span)
    tx_rate=ratio(tx,m5span);tx_hour_rate=ratio(hour_tx,h1span)
    # Round 3: participant counts, now parsed from the provider payloads instead of
    # being dropped. None whenever the provider does not publish them.
    buyers_now=number(now.get('buyers_5m'))
    # The baseline is the most recent EARLIER frame that actually carried a buyer
    # count (buyer counts arrive from a different provider than the frame itself, so
    # requiring the immediately previous frame would make the comparison unusable).
    buyers_prior=[number(r.get('buyers_5m')) for r in rows[:-1] if number(r.get('buyers_5m')) is not None]
    buyers_prev=buyers_prior[-1] if buyers_prior else None
    buyers_growth=ratio(buyers_now,buyers_prev)
    # Unique buyers per BUY (not per trade): near 1 means each buy came from its own
    # wallet, a low value means few wallets bought repeatedly (bundling proxy).
    participants_per_trade=ratio(buyers_now,number(now.get('buys_5m')))
    f=dict(version=VERSION,observed_at=now['observed_at'],ingested_at=now['ingested_at'],
        recorded_at=now['recorded_at'],token_id=now['token_id'],pair_address=now['pair_address'],
        chain=now['chain'],provider=now['provider'],pool_age_seconds=age,frames=len(rows),windows=wins,
        continuity_started_at=rows[0]['observed_at'],
        current={key:now.get(key) for key in ('price_usd','liquidity_usd','volume_5m_usd','buys_5m','sells_5m','buyers_5m','observed_at')},
        buyers_5m=buyers_now,buyers_growth_5m=buyers_growth,
        participants_per_trade_5m=participants_per_trade,
        buy_count_share=ratio(now.get('buys_5m'),tx),reported_avg_notional_usd=ratio(now.get('volume_5m_usd'),tx),
        volume_acceleration_age_normalized=ratio(volume_rate,volume_hour_rate),
        tx_acceleration_age_normalized=ratio(tx_rate,tx_hour_rate),
        volume_acceleration_5m_1h=ratio(number(now.get('volume_5m_usd'))*12 if number(now.get('volume_5m_usd')) is not None else None,now.get('volume_1h_usd')),
        tx_acceleration_5m_1h=ratio(tx*12 if tx is not None else None,hour_tx),
        volume_liquidity=turn,fdv_liquidity=ratio(now.get('fdv_usd'),liquidity),
        drawdown=p/max(r['price_usd'] for r in rows)-1,
        liquidity_retention=liquidity/max(r['liquidity_usd'] for r in rows),
        monotonic_up_fraction=sum(x>0 for x in steps)/len(steps) if steps else None,
        log_price_r2=1-sum(x*x for x in residual)/yy if yy>0 and len(rows)>=6 else None,
        residual_dispersion=pstdev(residual) if len(rows)>=6 else None,
        plateau_fraction=sum(x==0 for x in steps)/len(steps) if steps else None,
        top3_up_step_share=sum(sorted(positive,reverse=True)[:3])/sum(positive) if positive else None,
        jump_size_cv=ratio(pstdev(positive),mean(positive)) if len(positive)>=3 else None,
        jump_interval_cv=ratio(pstdev(intervals),mean(intervals)) if len(intervals)>=3 else None,
        signed_flow=None,independent_wallets=None,
        interpretation='provider rolling aggregates; selected local pool cohort, not whole-market rank')
    w30=wins['30'];f['price_elasticity_proxy']=ratio(abs(w30['return_fraction']),turn) if w30 else None
    base=[r for r in rows if now['t']-150<=r['t']<=now['t']-30]
    f['base']=None
    if len(base)>=4 and base[-1]['t']-base[0]['t']>=100 and all(b['t']-a['t']<=30 for a,b in zip(base,base[1:])):
        f['base']=dict(range_fraction=max(r['price_usd'] for r in base)/min(r['price_usd'] for r in base)-1,
            high=max(r['price_usd'] for r in base),end_at=base[-1]['observed_at'])
    # First observed significant dip, bounded to this episode; never inferred ATH.
    high=rows[0];trough=None;dip=None
    for r in rows[1:]:
        if trough is None and r['price_usd']>high['price_usd']:high=r
        elif r['price_usd']<=high['price_usd']*(1-FRICTION):
            if trough is None or r['price_usd']<trough['price_usd']:trough=r
        if trough is not None and r['price_usd']>=high['price_usd']:
            segment=[v for v in rows if high['t']<=v['t']<=r['t']]
            dip=dict(recovered_at=r['observed_at'],recovery_seconds=r['t']-trough['t'],
                decline_seconds=trough['t']-high['t'],
                liquidity_retention=min(v['liquidity_usd'] for v in segment)/high['liquidity_usd'],
                volume_ratio=ratio(r.get('volume_5m_usd'),trough.get('volume_5m_usd')))
            break
    f['first_dip']=dip
    return f


def mechanisms(f):
    w=f['windows'].get('30');base=f['base'];out={name:False for name,_,_ in SPECS.values()}
    if not w:return out
    share=f['buy_count_share'];good=share is not None and share>.5
    rising=(w['rolling_volume_change_ratio'] or 0)>1 and (w['rolling_tx_change_ratio'] or 0)>1
    stable=w['liquidity_change_fraction'] is not None and w['liquidity_change_fraction']>=0
    if not(good and stable):return out
    ret=w['return_fraction'];age=f['pool_age_seconds']
    out['hot']=bool(age is not None and age<=900 and ret>FRICTION and w['acceleration']>0 and rising and f['drawdown']>-FRICTION)
    compressed=bool(base and base['range_fraction']<=FRICTION)
    out['quiet']=bool(age is not None and age<=21600 and compressed and 0<ret<=FRICTION and rising and w['acceleration']>0 and w['liquidity_change_fraction']>0)
    out['volume_leads']=bool(compressed and abs(ret)<=FRICTION/2 and rising and
        (f['volume_acceleration_age_normalized'] or 0)>1 and (f['tx_acceleration_age_normalized'] or 0)>1)
    out['breakout']=bool(compressed and rising and ret>FRICTION and w['acceleration']>0)
    dip=f['first_dip']
    out['first_dip']=bool(dip and dip['recovered_at']==f['observed_at'] and dip['recovery_seconds']<=dip['decline_seconds'] and
        dip['liquidity_retention']>=1-FRICTION and (dip['volume_ratio'] or 0)>=1)
    return out


class Engine:
    # Frame admission is provider-scoped. The prefix is a class attribute so an
    # ADDITIVE subclass can observe a wider surface without changing this engine's
    # own rule: the default below is the exact string this gate always used.
    PROVIDER_PREFIX='dexscreener'

    def __init__(self, started):
        self.started=parse_time(started);self.pools=OrderedDict();self.counts=Counter();self.recent=deque(maxlen=32)

    def accept(self,row,now):
        now=parse_time(now);row=dict(row)
        for key in ('price_usd','liquidity_usd','volume_5m_usd','volume_1h_usd','buys_5m','sells_5m','buys_1h','sells_1h','pool_age_seconds','fdv_usd','buyers_5m'):
            row[key]=number(row.get(key))
        try:
            observed,ingested,recorded=(parse_time(row[k]) for k in ('observed_at','ingested_at','recorded_at'))
            valid=self.started<=observed<=ingested<=recorded<=now and (now-observed).total_seconds()<=30
        except (ValueError,TypeError,KeyError):valid=False
        if not valid or not str(row.get('provider','')).startswith(self.PROVIDER_PREFIX) or not row.get('pair_address') or not row.get('token_id') or not (row['price_usd'] and row['price_usd']>0) or row['liquidity_usd'] is None or row['liquidity_usd']<1000:
            self.counts['invalid_or_unknown']+=1;return None
        identity=(row['token_id'],row['pair_address']);row['t']=observed.timestamp()
        # Observation identity includes its acquisition time. Equal values from a
        # genuinely later receipt are still evidence of quiet/flat conditions.
        fingerprint=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k not in ('t','ingested_at','recorded_at')},sort_keys=True).encode()).hexdigest()
        while self.pools and (now-parse_time(next(iter(self.pools.values()))['last_recorded'])).total_seconds()>TTL:
            self.pools.popitem(last=False);self.counts['expired']+=1
        state=self.pools.get(identity)
        if state and (observed<=parse_time(state['last_recorded']) or state['fingerprint']==fingerprint):
            self.counts['duplicate_or_noncausal']+=1;return None
        if state is None:
            if len(self.pools)>=MAX_POOLS:self.pools.popitem(last=False);self.counts['evicted']+=1
            state={'rows':deque(maxlen=MAX_FRAMES),'signals':{},'first_at':row['recorded_at']};self.pools[identity]=state
        rows=state['rows']
        if rows and row['t']-rows[-1]['t']>30:
            gap=row['t']-rows[-1]['t']
            self.counts['gap:30_60s' if gap<=60 else 'gap:60_120s' if gap<=120 else 'gap:over120s']+=1
            rows.clear();state['signals'].clear();self.counts['gap_reset']+=1
        rows.append(row)
        while rows and row['t']-rows[0]['t']>310:rows.popleft()
        f=derive(list(rows));state.update(features=f,fingerprint=fingerprint,last_recorded=row['recorded_at'])
        self.pools.move_to_end(identity);self.counts['distinct_frames']+=1
        for seconds, feature in f['windows'].items():
            if feature:self.counts['window_ready:'+seconds]+=1
        for label,ok in (('base',f['base'] is not None),('buy_share',f['buy_count_share'] is not None),
                         ('age_rate',f['volume_acceleration_age_normalized'] is not None and f['tx_acceleration_age_normalized'] is not None)):
            self.counts['input_ready:'+label if ok else 'input_unknown:'+label]+=1
        return f

    def signals_for(self,token,pool,now):
        now=parse_time(now);state=self.pools.get((token,pool))
        if not state:return {}
        f=state['features']
        if not 0<=(now-parse_time(f['observed_at'])).total_seconds()<=30:return {}
        flags=mechanisms(f)
        self.counts['mechanism_evaluations']+=1
        for kind,flag in flags.items():
            if flag:self.counts['mechanism_ready:'+kind]+=1
        if flags['hot']:
            age=f['pool_age_seconds'];band=0 if age<180 else 1 if age<900 else 2
            peers=[v['features'] for v in self.pools.values() if v['features']['chain']==f['chain'] and
                (0 if (v['features']['pool_age_seconds'] or 0)<180 else 1 if (v['features']['pool_age_seconds'] or 0)<900 else 2)==band and
                0<=(now-parse_time(v['features']['observed_at'])).total_seconds()<=30 and v['features']['windows']['30']]
            score=lambda v:v['windows']['30']['log_velocity']
            rank=sum(score(v)<=score(f) for v in peers)/len(peers) if peers else None
            f={**f,'local_age_peer_count':len(peers),'momentum_percentile':rank}
            flags['hot']=bool(len(peers)>=3 and rank>=.75)
            self.counts['hot_peer_pass' if flags['hot'] else 'hot_peer_insufficient' if len(peers)<3 else 'hot_peer_rank_below']+=1
        output={}
        for arm,(kind,_,_) in SPECS.items():
            if flags[kind] and arm not in state['signals']:
                key=VERSION+':'+token+':'+pool+':'+arm
                state['signals'][arm]=dict(episode_id=key,decision_key=key,selected=dict(token_id=token,pair_address=pool),
                    observed_at=f['observed_at'],recorded_at=f['recorded_at'],decision_evidence=dict(signal_at=f['recorded_at'],
                    activation_at=iso(self.started),mode=kind,feature_vector=deepcopy(f),mechanism_flags=flags))
                self.counts['signal:'+arm]+=1;self.recent.append(dict(token_id=token,pair_address=pool,arm_id=arm,at=f['recorded_at']))
            sig=state['signals'].get(arm)
            if sig and (now-parse_time(sig['recorded_at'])).total_seconds()<=60:output[arm]=sig
        if 'dex_hot_impulse_v1' in output:
            for arm in EXIT_ARMS:
                sig=deepcopy(output['dex_hot_impulse_v1']);sig['decision_key']+=':'+arm;output[arm]=sig
        return output

    def snapshot(self):
        return dict(version=VERSION,started_at=iso(self.started),max_pools=MAX_POOLS,max_frames_per_pool=MAX_FRAMES,
            ttl_seconds=TTL,pools=len(self.pools),counts=dict(self.counts),recent=list(self.recent),extra_requests=0,
            rank_universe='fresh observed local same-chain age band, not all market',
            unavailable=['wallet breadth','signed USD flow','unobserved horizons'])


def policies(base):
    result=[]
    for arm in [*SPECS,*EXIT_ARMS]:
        kind,name,hold=SPECS.get(arm,('hot','同冲量入口·'+EXIT_ARMS.get(arm,''),15))
        p=deepcopy(base)
        p.update(arm_id=arm,canonical_id=arm,name=name,entry_family=arm,notional_usd=5.,max_hold_minutes=hold,
            signal_origin_clock='activation_at',source_arm_ids=['dex_hot_impulse_v1'] if arm in EXIT_ARMS else [],
            paired_opportunity_group='dex_trajectory_v1',paired_opportunity_semantics='same_frozen_signal_where_shared_no_extra_control',
            description='共享连续原池特征的前向5U实验；非已证Alpha。缺失不补零、后帧成交、共同安全门。',
            feature_contract=VERSION,feature_hypothesis=kind,trajectory_exit=EXIT_ARMS.get(arm),requires_distinct_trajectory_frame=True,
            entry_filter=dict(direction=arm,max_concurrent_positions=2,single_token_lifetime_entry=True),
            hard_stop_return=-.20,trailing_activate_return=.30,trailing_drawdown=.15,take_profit=[],
            assessment_status='INSUFFICIENT',observer_only=False,decision_eligible=True,affects='paper_only')
        p['trajectory_rules']={
            'common':'独立观察间隔≤30秒；原池流动性≥1000U；买入笔数占比>50%；共同安全；后帧成交。',
            'hot':'池龄≤15分钟；30秒涨幅超过4%双边摩擦；价格加速、成交额和笔数均增、流动性不降；同链同龄新鲜观察集≥3币、价格速度前25%。',
            'quiet':'至少100秒的先前120秒区间在摩擦尺度内；最近30秒小幅上涨、价格与活动加速、流动性增加。',
            'volume_leads':'先前区间压缩；30秒涨幅绝对值≤半个摩擦尺度；成交额和笔数增长，按池龄归一化速率高于一小时基准。',
            'breakout':'先前区间压缩；30秒涨幅超过摩擦，价格加速、成交额和笔数增长。',
            'first_dip':'观察到超过摩擦尺度的回撤后首次收复高点；恢复时间≤下跌时间，整个回撤期流动性保持、恢复活动不降。',
        }
        p['require_post_decision_observation']=True
        result.append(p)
    return result


def exit_reason(kind,f,opened_at,current):
    if not f or not parse_time(opened_at)<parse_time(f['observed_at'])<=parse_time(f['recorded_at'])<=current:return None
    if (current-parse_time(f['observed_at'])).total_seconds()>15:return None
    w=f['windows']['30']
    if not w or parse_time(w['start_at'])<parse_time(opened_at):return None
    vol=w['rolling_volume_change_ratio'];liq=w['liquidity_change_fraction']
    if kind=='velocity' and w['log_velocity']<0 and w['acceleration']<0 and vol is not None and vol<1 and liq is not None and liq<0:
        return 'dex_price_activity_liquidity_decay'
    if kind=='liquidity_divergence' and w['return_fraction']>0 and liq is not None and liq<=-FRICTION:
        return 'dex_price_up_liquidity_withdrawal'
    if kind=='blowoff' and w['acceleration']<0 and w['return_fraction']>FRICTION and vol is not None and vol>1 and (w['rolling_tx_change_ratio'] or 0)>1:
        return 'dex_accelerated_activity_price_deceleration'
    return None
