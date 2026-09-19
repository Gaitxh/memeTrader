"""Market-observed recovery instead of a trade from a retired prerequisite.

The parent waits for a recorded core loss. This independent revision preserves
its cooling aggregate hypothesis and exits, but requires a later observed low
and rebound. No new requests, account resets, learning labels or hidden orders.
"""
from copy import deepcopy
from math import isfinite
from .models import parse_time, iso
from .resource_bound_research import resource_entry_signal
from .trajectory_regime187 import _clone

ARM = 'revision246_observed_cooling_recovery_v1'
PARENT = 'failed_impulse_cooling_v1'
CONTRACT = 'observed-cooling-recovery246/v1'
RULES = dict(lookback_seconds=120, minimum_span_seconds=30,
    maximum_gap_seconds=45, minimum_leg_seconds=10, minimum_dip_ratio=.99,
    minimum_rebound_ratio=1.02, maximum_seed_price_ratio=1.03,
    minimum_depth_retention=.90, minimum_buy_share=.55)


def policy(parent):
    if parent.get('arm_id') != PARENT:
        raise ValueError('Exact failed-impulse parent required')
    out = _clone(parent, ARM, 'Observed cooling recovery without retired-core trade')
    for key in ('paired_entry_group', 'paired_entry_size', 'resource_bound_research'):
        out.pop(key, None)
    out['entry_filter'].pop('failed_impulse_cooling', None)
    out['entry_filter'].pop('opportunity', None)
    out['entry_filter'].update(contract=CONTRACT, direction='cooling_hold',
        control=False, path_recovery246=deepcopy(RULES), max_concurrent_positions=8)
    out.update(notional_usd=20., revision_of=PARENT,
        entry_match_mode='isolated_pattern_observer', source_arm_ids=[PARENT],
        comparison_semantics='Replace executed-core-loss prerequisite with observed recovery; exits unchanged.',
        description='Same 1h-24h cooling aggregate hypothesis as parent; no prior account loss required. '
        'Observe >=1% dip then >=2% rebound, <=3% above seed, 90% depth retained, '
        '30-120s actual coverage and <=45s gaps. Standard safety and later original-pool '
        'Paper fill; trigger is not a guaranteed fill price.20U/cap8; hypothesis only.')
    return out


def _number(value):
    if value is None or isinstance(value, bool):
        raise ValueError('unknown number')
    value = float(value)
    if not isfinite(value):
        raise ValueError('nonfinite number')
    return value


def _time(value):
    if not value:
        raise ValueError('explicit clock required')
    return parse_time(value)


def signal(history, selected_policy, *, decision_at, activated_at):
    evidence = dict(contract=CONTRACT, needs_parent_trade=False, extra_requests=0)
    def result(ok, reason):
        evidence.update(allowed=ok, reason=reason)
        return ok, reason, evidence
    try:
        cfg = selected_policy['entry_filter']
        if cfg.get('contract') != CONTRACT or not 3 <= len(history) <= 80:
            return result(False, 'cooling246_history_or_contract_missing')
        rules = cfg['path_recovery246']
        limits = {key:_number(rules[key]) for key in RULES}
        if any(value <= 0 for value in limits.values()):
            raise ValueError('invalid bound')
        now, start = _time(decision_at), _time(activated_at)
        last = history[-1]
        end = _time(last['observed_at'])
        if not 0 <= (now-end).total_seconds() <= 30:
            return result(False, 'cooling246_stale_frame')
        recent = [r for r in history if _time(r['observed_at']) >= start
                  and 0 <= (end-_time(r['observed_at'])).total_seconds()
                  <= limits['lookback_seconds']]
        if len(recent) < 3:
            return result(False, 'cooling246_need_post_activation_path')
        identity = (last['token_id'], last['pair_address'], last['upstream_provider'])
        if not str(identity[2]).startswith(('dexscreener', 'geckoterminal')):
            return result(False, 'cooling246_unsupported_source')
        if not identity[0].startswith(('solana:', 'bsc:', 'robinhood:')):
            return result(False, 'cooling246_unsupported_chain')
        previous = None
        values = []
        for row in recent:
            clocks = tuple(_time(row[k]) for k in ('observed_at','ingested_at','recorded_at'))
            o, i, recorded = clocks
            if ((row['token_id'],row['pair_address'],row['upstream_provider']) != identity
                    or not start <= o <= i <= recorded <= now):
                return result(False, 'cooling246_identity_or_clock')
            if previous and (o <= previous[2] or
                    (o-previous[0]).total_seconds() > limits['maximum_gap_seconds']):
                return result(False, 'cooling246_gap_or_repeat')
            price, depth = _number(row['price']), _number(row['liquidity'])
            if price <= 0 or depth < 0:
                raise ValueError('invalid price or depth')
            values.append((price,depth,clocks)); previous = clocks
        seed, middle, final = recent[0], recent[1:-1], recent[-1]
        span = (end-values[0][2][0]).total_seconds()
        if span < limits['minimum_span_seconds']:
            return result(False, 'cooling246_need_actual_span')
        cooling, reason, aggregate = resource_entry_signal([seed], selected_policy,
            decision_at=seed['recorded_at'], activated_at=activated_at)
        evidence['cooling_seed'] = aggregate
        if not cooling:
            return result(False, 'cooling246_seed:'+reason)
        low_index = min(range(1,len(recent)-1), key=lambda n:values[n][0])
        low = recent[low_index]
        seed_price, low_price, final_price = values[0][0], values[low_index][0], values[-1][0]
        if ((values[low_index][2][0]-values[0][2][0]).total_seconds()
                < limits['minimum_leg_seconds'] or
                (end-values[low_index][2][0]).total_seconds() < limits['minimum_leg_seconds']):
            return result(False, 'cooling246_need_independent_legs')
        floor = _number((selected_policy.get('_execution') or {}).get('min_pool_liquidity_usd',1000))
        depth_floor = max(floor,values[0][1]*limits['minimum_depth_retention'])
        buys, sells = _number(final['buys']), _number(final['sells'])
        volume, low_volume = _number(final['volume']), _number(low['volume'])
        evidence.update(seed_at=seed['observed_at'], low_at=low['observed_at'],
            confirmation_at=final['observed_at'], available_at=final['recorded_at'],
            seed_price=seed_price, low_price=low_price, confirmation_price=final_price,
            actual_span_seconds=span, frames=len(recent), minimum_depth=depth_floor,
            note='Reported aggregates are proxies; final fill may differ from this trigger.')
        if min(value[1] for value in values) < depth_floor:
            return result(False, 'cooling246_depth_not_retained')
        if not (low_price <= seed_price*limits['minimum_dip_ratio']
                and final_price >= low_price*limits['minimum_rebound_ratio']
                and final_price <= seed_price*limits['maximum_seed_price_ratio']):
            return result(False, 'cooling246_no_observed_recovery')
        if (buys < 1 or sells < 1 or buys+sells < 8 or low_volume < 0
                or volume < low_volume or buys/(buys+sells) < limits['minimum_buy_share']):
            return result(False, 'cooling246_activity_not_supporting')
        return result(True, 'cooling246_observed_recovery_ready')
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return result(False, 'cooling246_unknown_or_invalid')
