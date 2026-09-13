"""Indexed fixed-horizon observations and identity-bound cohort funnel, read only."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from memetrader.models import canonical_token_address


def date(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def stamp(value):
    return value.isoformat().replace('+00:00', 'Z')


def visible_mark(c, token, pool, start, end):
    # Lexical coarse bounds preserve the token/time index. Julian predicates check
    # exact mixed Z/+00:00 clocks, including full seconds and observation freshness.
    candidates = c.execute('SELECT * FROM chain_meme_trader_market_mark_history '
        'WHERE token_id=? AND recorded_at>=? AND recorded_at<=? '
        'ORDER BY recorded_at,id LIMIT 300',
        (token, stamp(start-timedelta(seconds=1)), stamp(end+timedelta(seconds=1)))).fetchall()
    for row in candidates:
        row = dict(row)
        recorded, observed = date(row['recorded_at']), date(row['observed_at'])
        chain = token.split(':', 1)[0]
        if (canonical_token_address(chain, row['pair_address']) == canonical_token_address(chain, pool)
                and row['status'] == 'VISIBLE' and (row['price_usd'] or 0) > 0
                and start <= observed <= recorded <= end and 0 <= (recorded-observed).total_seconds() <= 15):
            return row
    return None


def washout(c, cutoff):
    cutoff = date(cutoff)
    mature_before = stamp(cutoff - timedelta(minutes=16))
    # Recent high fan-out exits can fill all 200 seats with <16-minute-old
    # positions. Sampling those every two hours forever reports only maturing
    # and discards the mature cohorts the report was meant to evaluate.
    pending = c.execute('SELECT COUNT(*) n,COUNT(DISTINCT token_id) tokens FROM '
        'chain_meme_trader_positions WHERE closed_at>? AND closed_at<=?', (mature_before,stamp(cutoff))).fetchone()
    closed = c.execute('SELECT p.arm_id,p.token_id,p.shadow_cohort_id,p.closed_at,p.close_reason, '
        'p.source_entry_fill_id,COALESCE(json_extract(s.raw_json,\'$.pair.pairAddress\'), v.pair_address) pool '
        'FROM (SELECT * FROM chain_meme_trader_positions WHERE closed_at<=? '
        'ORDER BY closed_at DESC LIMIT 200) p LEFT JOIN token_snapshots s ON s.id=p.entry_snapshot_id '
        'LEFT JOIN chain_meme_trader_v6_cohorts v ON v.id=p.shadow_cohort_id AND v.token_id=p.token_id',
        (mature_before,)).fetchall()
    outcomes = []
    for pos in closed:
        pos = dict(pos); ended = date(pos['closed_at'])
        baseline = visible_mark(c, pos['token_id'], pos['pool'], ended-timedelta(seconds=15), ended) if pos['pool'] else None
        result = {**pos, 'exit_observation': baseline, 'horizons': {}}
        for minutes in (5, 15):
            target = ended + timedelta(minutes=minutes); deadline = target + timedelta(seconds=60)
            # Wait for whole predeclared window; no early winners/late losers bias.
            if cutoff < deadline:
                outcome = {'status': 'maturing'}
            elif not pos['pool']:
                outcome = {'status': 'missing_original_pool'}
            elif baseline is None:
                outcome = {'status': 'missing_exit_observation'}
            else:
                mark = visible_mark(c, pos['token_id'], pos['pool'], target, deadline)
                if mark is None:
                    outcome = {'status': 'missing_followup'}
                else:
                    change = mark['price_usd'] / baseline['price_usd'] - 1
                    risk_exit = any(x in pos['close_reason'].lower() for x in ('rug', 'liquidity', 'writeoff', 'write_off', 'missing', 'fault'))
                    outcome = {'status': 'observed_market_proxy', 'price_change': change,
                        'mark_id': mark['id'], 'observed_at': mark['observed_at'],
                        'rebound_candidate_ge20pct_nonrisk': change >= .2 and not risk_exit}
            result['horizons'][str(minutes)] = outcome
        outcomes.append(result)
    return {'definition': 'Exit price observation to first valid original-pool observation in +5/+15m to +60s; >=20% non-risk-exit rebound candidate. Not executable or cost-net washout proof.',
        'sample_scope': 'Latest <=200 mature exits; arm fan-out is not independent; newer incomplete windows reported separately.',
        'maturing_positions': pending['n'], 'maturing_tokens': pending['tokens'],
        'positions': len(outcomes), 'independent_token_entries': len({(x['token_id'], x['source_entry_fill_id'] or x['shadow_cohort_id']) for x in outcomes}),
        'counts': {str(m): dict(Counter(x['horizons'][str(m)]['status'] for x in outcomes)) for m in (5,15)}, 'samples': outcomes}


def cohort_funnel(c, cutoff, minutes):
    lower = stamp(date(cutoff)-timedelta(minutes=minutes))
    cohorts = c.execute('SELECT id,definition_version,token_id,pair_address,decided_at,entry_family FROM '
        'chain_meme_trader_v6_cohorts WHERE decided_at>=? ORDER BY id DESC LIMIT 2000', (lower,)).fetchall()
    stats, reasons, delays = {}, Counter(), []
    for cohort in cohorts:
        group = (cohort['token_id'].split(':')[0], cohort['entry_family'])
        stat = stats.setdefault(group, dict(cohorts=0, decision_reached=0, admitted=0, with_source_fill=0,
            buy_intent=0, position_booked=0, no_decision_observed=0, arm_evaluations=0))
        stat['cohorts'] += 1
        identity = (cohort['id'], cohort['definition_version'], cohort['token_id'])
        decisions = c.execute('SELECT status,reason FROM chain_meme_trader_entry_decisions WHERE shadow_cohort_id=? AND definition_version=? AND token_id=?', identity).fetchall()
        stat['decision_reached'] += bool(decisions); stat['arm_evaluations'] += len(decisions)
        stat['no_decision_observed'] += not bool(decisions)
        stat['admitted'] += any(x['status'] == 'admitted' for x in decisions)
        reasons.update((x['status'], x['reason']) for x in decisions)
        stat['with_source_fill'] += bool(c.execute('SELECT 1 FROM chain_meme_trader_v6_entry_fills WHERE entry_cohort_id=? AND definition_version=? AND token_id=? LIMIT 1', identity).fetchone())
        stat['buy_intent'] += bool(c.execute("SELECT 1 FROM chain_meme_trader_order_intents WHERE shadow_cohort_id=? AND definition_version=? AND token_id=? AND side='BUY' LIMIT 1", identity).fetchone())
        position = c.execute('SELECT MIN(opened_at) opened_at FROM chain_meme_trader_positions WHERE shadow_cohort_id=? AND definition_version=? AND token_id=?', identity).fetchone()
        stat['position_booked'] += position['opened_at'] is not None
        if position['opened_at']:
            elapsed = (date(position['opened_at']) - date(cohort['decided_at'])).total_seconds()
            if elapsed >= 0:
                delays.append(elapsed)
    return {'scope': 'Latest <=2000 cohorts within window, each cohort id is one opportunity; shared source fills can precede arm decisions, so stages are NOT assumed sequential. No decision means unknown/pending, not rejection.',
        'groups': [dict(chain=k[0], family=k[1], **v) for k,v in stats.items()],
        'arm_decision_reasons_nonindependent': [dict(status=k[0], reason=k[1], count=v) for k,v in reasons.most_common(20)],
        'cohort_to_first_position_seconds': {str(p): sorted(delays)[int((len(delays)-1)*p)] if delays else None for p in (.5,.9,.99)}}
