"""Relative-activity revision of the existing absolute-quiet Paper strategy.
Pure, bounded by the existing 80 observations; no I/O and no outcome labels.
Rolling trade counts are not independent wallets or signed capital flow.
This file is a staged candidate, not authorization to register or deploy it.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite
from statistics import median
from typing import Any, Mapping, Sequence
from memetrader.models import canonical_token_address
from memetrader.trajectory_regime187 import _clone

PARENT = 'experiment_quiet_reawakening_candidate_v1'
ARM = 'revision237_relative_reawakening_v3'
CONTRACT = 'relative-reawakening237/v1'
MAX_FRAMES = 80
RULES = dict(contract=CONTRACT, direction='relative_reawakening',
    maximum_lookback_seconds=900., baseline_end_lag_seconds=120.,
    minimum_baseline_span_seconds=120., minimum_baseline_frames=3,
    minimum_spacing_seconds=15., maximum_gap_seconds=90.,
    maximum_frame_age_seconds=30., minimum_pool_age_seconds=21600.,
    maximum_baseline_price_ratio=1.10, minimum_price_ratio=1.12,
    minimum_liquidity_retention=.80, minimum_trades_5m=10.,
    minimum_volume_5m_usd=1000., minimum_buy_share=.55,
    minimum_trade_growth=3., minimum_volume_growth=3.,
    max_concurrent_positions=8, single_token_lifetime_entry=True,
    include_pending_in_limit=True, single_token_open_or_reserved=True)

def policy(parent: Mapping[str, Any]) -> dict[str, Any]:
    if parent.get('arm_id') != PARENT:
        raise ValueError('The absolute-quiet parent is required')
    result = _clone(parent, ARM, 'Relative-activity reawakening revision')
    for key in ('entry_revision_kind', 'entry_alias_of', 'paired_entry_group',
                'paired_entry_size', 'notional_revision', 'concurrency_cap_revision',
                'parameter_note', 'signal_origin_clock'):
        result.pop(key, None)
    result.update(entry_family='quiet_reawakening',
        source_entry_family='quiet_reawakening',
        entry_match_mode='isolated_pattern_observer',
        entry_filter=deepcopy(RULES), revision_of=PARENT, strategy_revision=3,
        revision_contract=CONTRACT, feature_contract=CONTRACT,
        revision_parent_behavior_hash=parent.get('behavior_contract_hash'),
        notional_usd=20., require_post_decision_observation=True,
        revision_changes='Relative 3x counts AND volume; actual <=90s gaps; unchanged exits.',
        comparison_semantics='Changed entry population, not a controlled exit experiment.',
        description='Observed mature-pool baseline then relative renewal. No new requests; '
                    'old exits retained. Next observed Paper fill required; unproven.')
    return result


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None

def timestamp(value: Any) -> datetime:
    if isinstance(value, str) and value.strip():
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('An explicit timezone is required')
    return value.astimezone(timezone.utc)


def identity(row: Mapping[str, Any]) -> tuple[str, str, str]:
    token = str(row.get('token_id') or '')
    chain, sep, address = token.partition(':')
    pool = str(row.get('pair_address') or '')
    provider = str(row.get('upstream_provider') or '')
    if (not sep or chain not in ('solana', 'bsc', 'robinhood') or not address
            or not pool or not provider.startswith(('dexscreener', 'geckoterminal'))):
        raise ValueError('Unsupported or incomplete source identity')
    if row.get('chain') is not None and row['chain'] != chain:
        raise ValueError('Conflicting chain')
    return (chain + ':' + canonical_token_address(chain, address),
            canonical_token_address(chain, pool), provider)


def signal(history: Sequence[Mapping[str, Any]], selected_policy: Mapping[str, Any],
           *, decision_at: Any, activated_at: Any) -> tuple[bool, str, dict[str, Any]]:
    evidence = dict(contract=CONTRACT, rolling_activity_is_proxy=True)
    def reject(reason):
        return False, 'relative237_' + reason, evidence
    if not 4 <= len(history) <= MAX_FRAMES:
        return reject('bounded_history_required')
    try:
        cfg = selected_policy['entry_filter']
        if cfg['contract'] != CONTRACT:
            return reject('wrong_contract')
        now, activation = timestamp(decision_at), timestamp(activated_at)
        if activation >= now:
            return reject('activation_not_passed')
        end = timestamp(history[-1]['observed_at'])
        if not 0 <= (now - end).total_seconds() <= cfg['maximum_frame_age_seconds']:
            return reject('stale_or_future_latest')
        expected = identity(history[-1])
        frames, seen, previous = [], set(), None
        for item in history:
            observed = timestamp(item['observed_at'])
            ingested = timestamp(item['ingested_at'])
            recorded = timestamp(item['recorded_at'])
            if not observed <= ingested <= recorded <= now:
                return reject('unavailable_or_reversed_clock')
            if observed <= activation or (end-observed).total_seconds() > cfg['maximum_lookback_seconds']:
                continue
            key = str(item.get('id') or item.get('frame_id') or '')
            if not key or key in seen or (previous is not None and observed <= previous):
                return reject('duplicate_or_out_of_order')
            if identity(item) != expected:
                return reject('mixed_identity_or_provider')
            seen.add(key)
            previous = observed
            frames.append((item, observed))
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError):
        return reject('invalid_contract_identity_or_clock')
    # Select a duration, not just the last three dense observations.
    spaced = []
    for index in range(len(frames)-1, -1, -1):
        at = frames[index][1]
        if (end-at).total_seconds() < cfg['baseline_end_lag_seconds']:
            continue
        if spaced and (frames[spaced[-1]][1]-at).total_seconds() < cfg['minimum_spacing_seconds']:
            continue
        spaced.append(index)
        span = (frames[spaced[0]][1]-at).total_seconds()
        if len(spaced) >= cfg['minimum_baseline_frames'] and span >= cfg['minimum_baseline_span_seconds']:
            break
    if (len(spaced) < cfg['minimum_baseline_frames'] or
            (frames[spaced[0]][1]-frames[spaced[-1]][1]).total_seconds() < cfg['minimum_baseline_span_seconds']):
        return reject('await_observed_baseline_span')
    first, last_base = spaced[-1], spaced[0]
    markets = {}
    prior = None
    for index in range(first, len(frames)):
        row, at = frames[index]
        if prior is not None and (at-prior).total_seconds() > cfg['maximum_gap_seconds']:
            return reject('observation_gap')
        prior = at
        values = tuple(number(row.get(k)) for k in ('price','liquidity','volume','buys','sells'))
        if any(x is None for x in values) or values[0] <= 0 or min(values[1:]) < 0:
            return reject('critical_market_field_missing_or_invalid')
        if not values[3].is_integer() or not values[4].is_integer():
            return reject('fractional_trade_count')
        markets[index] = values
    prices = [markets[i][0] for i in range(first, last_base+1)]
    baseline_trades = median(markets[i][3]+markets[i][4] for i in spaced)
    baseline_volume = median(markets[i][2] for i in spaced)
    price, depth, volume, buys, sells = markets[len(frames)-1]
    age = number(frames[-1][0].get('pool_age_seconds'))
    base_depth = markets[last_base][1]
    floor = number((selected_policy.get('_execution') or {}).get('min_pool_liquidity_usd', 1000.))
    if baseline_trades <= 0 or baseline_volume <= 0 or base_depth <= 0:
        return reject('positive_baseline_required')
    if floor is None or floor < 0:
        return reject('invalid_execution_floor')
    trades = buys+sells
    evidence.update(token_id=expected[0], pair_address=expected[1], upstream_provider=expected[2],
        signal_observed_at=frames[-1][0]['observed_at'],
        signal_recorded_at=frames[-1][0]['recorded_at'], signal_price=price,
        baseline_start_at=frames[first][0]['observed_at'],
        baseline_end_at=frames[last_base][0]['observed_at'],
        selected_frame_ids=[frames[i][0].get('id',frames[i][0].get('frame_id')) for i in reversed(spaced)],
        baseline_trades_5m=baseline_trades, baseline_volume_5m_usd=baseline_volume,
        trade_growth=trades/baseline_trades, volume_growth=volume/baseline_volume,
        price_ratio=price/markets[last_base][0], baseline_price_ratio=max(prices)/min(prices),
        liquidity_retention=depth/base_depth, observed_frames=len(frames)-first)
    checks = (
        ('pool_not_mature', age is not None and age >= cfg['minimum_pool_age_seconds']),
        ('baseline_not_compressed', max(prices)/min(prices) <= cfg['maximum_baseline_price_ratio']),
        ('current_depth_below_floor', depth >= max(1000.,floor)),
        ('depth_not_retained', depth >= base_depth*cfg['minimum_liquidity_retention']),
        ('price_not_recovered', price >= markets[last_base][0]*cfg['minimum_price_ratio']),
        ('current_activity_too_low', trades >= cfg['minimum_trades_5m'] and volume >= cfg['minimum_volume_5m_usd']),
        ('buy_share_not_met', trades > 0 and buys >= trades*cfg['minimum_buy_share']),
        ('relative_trade_growth_not_met', trades >= baseline_trades*cfg['minimum_trade_growth']),
        ('relative_volume_growth_not_met', volume >= baseline_volume*cfg['minimum_volume_growth']),
    )
    for reason, passed in checks:
        if not passed:
            return reject(reason)
    return True, 'relative237_reawakening_ready', evidence
