"""Additive Paper exit using only existing, causal original-pool marks.

Rolling counts are activity proxies, not signed money flow; USD liquidity is
quoted market depth, not proof of LP deposits/withdrawals. No network calls.
"""
from copy import deepcopy
from math import isfinite

from .models import iso, parse_time

ARM = 'alpha149_confirmed_recovery_decay_v1'
PARENT = 'alpha149_moonbag_steady_v1'
VERSION = 'confirmed-recovery-decay/151-v1'
CONTRACT = dict(version=VERSION, sample_seconds=15, max_gap_seconds=90,
                fresh_seconds=15, minimum_hold_seconds=300, confirmations=2,
                decay_votes=3, volatility_proxy='snapshot_realized_30s_not_ATR')


def policy(base):
    result = deepcopy(base)
    result.update(arm_id=ARM, canonical_id=ARM, entry_family=ARM,
        name='组合退出151·波动保护与衰减回本',
        source_arm_ids=[PARENT], excess_return_vs_arm=PARENT,
        entry_filter={**base.get('entry_filter', {}), 'direction': ARM},
        composite_exit151=CONTRACT.copy(),
        dynamic_principal_recovery='confirmed_decay151',
        trajectory_exit='alpha149_vol_scaled_stop', hard_stop_return=-.50,
        description='与安全带阶梯母臂同入口，复用原池行情；实际快照波动率保护（非ATR）、'
            '两次多维衰减确认后按下一帧净回款最小回本；既有2x/3x/5x阶梯及回本后Moonbag追踪、'
            '原时间退出和紧急风险优先。成交笔数与USD流动性仅为市场行为代理。独立Paper，待验证。')
    for key in ('behavior_contract_hash', 'forward_activation_snapshot_id', 'forward_started_at'):
        result.pop(key, None)
    return result


def number(value):
    try:
        value = float(value)
        return value if isfinite(value) else None
    except (TypeError, ValueError):
        return None


def evaluate(position, mark, state, now):
    """State is held in the existing position JSON, shared settlement owns cash.

    True returns a recovery *trigger*, never a fill or principal-recovered flag.
    Caller skips pending marks, unsafe surfaces and previous parent exit actions.
    """
    state = deepcopy(state or {})
    try:
        observed, recorded, now = parse_time(mark['observed_at']), parse_time(mark['recorded_at']), parse_time(now)
        opened = parse_time(position['opened_at'])
        eligible = (opened < observed <= recorded <= now
                    and 0 <= (now-observed).total_seconds() <= CONTRACT['fresh_seconds'])
    except (TypeError, ValueError, KeyError):
        return state, None
    entry_pair = str(position.get('entry_pair_address') or '')
    mark_pair = str(mark.get('pair_address') or '')
    # Solana keys are case sensitive; EVM addresses are not.
    if str(position.get('token_id', '')).startswith(('bsc:', 'robinhood:', 'ethereum:')):
        entry_pair, mark_pair = entry_pair.lower(), mark_pair.lower()
    if (not eligible or not entry_pair or mark_pair != entry_pair or mark.get('status') != 'VISIBLE'
            or mark.get('token_id') != position['token_id']
            or number(mark.get('price')) is None or float(mark['price']) <= 0):
        return state, None
    frame = {key: mark.get(key) for key in ('sequence', 'observed_at', 'recorded_at',
                'pair_address', 'token_id', 'price', 'liquidity', 'buys', 'sells')}
    prior = state.get('sample')
    if prior:
        gap = (observed-parse_time(prior['observed_at'])).total_seconds()
        if frame['sequence'] == prior['sequence'] or gap < CONTRACT['sample_seconds']:
            return state, None
        if frame['pair_address'] != prior['pair_address'] or gap > CONTRACT['max_gap_seconds']:
            state = {}
            prior = None
    state['version'], state['sample'] = VERSION, frame
    if not prior or (observed-opened).total_seconds() < CONTRACT['minimum_hold_seconds']:
        state.pop('confirmation', None)
        return state, None
    def share(row):
        b, s = number(row.get('buys')), number(row.get('sells'))
        return (b/(b+s), b+s) if b is not None and s is not None and b >= 0 and s >= 0 and b+s > 0 else (None, None)
    cs, ct = share(frame); ps, pt = share(prior)
    cp, pp = number(frame['price']), number(prior['price'])
    cl, pl = number(frame['liquidity']), number(prior['liquidity'])
    votes = dict(price=cp < pp if pp is not None and pp > 0 else None,
        buy_count_share=cs < ps if cs is not None and ps is not None else None,
        rolling_activity=ct < pt if ct is not None and pt is not None else None,
        liquidity_usd_proxy=cl < pl if cl is not None and pl is not None else None)
    if sum(v is True for v in votes.values()) < CONTRACT['decay_votes']:
        state.pop('confirmation', None)  # recovery cancels a prior bearish frame
        return state, None
    first = state.get('confirmation')
    state['confirmation'] = dict(sequence=frame['sequence'], at=iso(observed))
    if first is None:
        return state, None
    evidence = dict(version=VERSION, first=first, second=state['confirmation'], votes=votes,
                    sample=frame, support=prior, interpretation='rolling_market_activity_proxies')
    return state, evidence
