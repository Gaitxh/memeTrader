"""Indexed fixed-horizon observations and identity-bound cohort funnel, read only."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from memetrader.models import canonical_token_address


COMPOSITE151_ARM = 'alpha149_confirmed_recovery_decay_v1'
COMPOSITE151_PARENT = 'alpha149_moonbag_steady_v1'


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


def composite_exit151_diagnostics(c, limit=200):
    """Return a bounded, persisted-only readout for the additive exit arm.

    A terminal reason says what settled the position, not which earlier evaluator
    prevented a composite signal.  Only a persisted SELL intent with the exact
    composite reason establishes that the two-confirmation trigger fired.
    """
    limit = min(200, max(1, int(limit)))
    columns = {row[1] for row in c.execute('PRAGMA table_info(chain_meme_trader_positions)')}
    required = {'definition_version', 'arm_id', 'shadow_cohort_id', 'token_id',
                'opened_at', 'closed_at', 'close_reason', 'capital_exit_state_json'}
    if not required <= columns:
        return {'status': 'unknown', 'reason': 'positions_schema_unavailable'}
    # 201 makes the 200-row cap explicit without turning an arm-wide historical
    # report into an unbounded scan.  This same path is usable on an archive.
    rows = c.execute('SELECT definition_version,shadow_cohort_id,token_id,opened_at,closed_at,close_reason, '
        'capital_exit_state_json FROM chain_meme_trader_positions WHERE arm_id=? '
        'ORDER BY COALESCE(closed_at,opened_at) DESC,definition_version DESC,shadow_cohort_id DESC,token_id DESC LIMIT ?',
        (COMPOSITE151_ARM, limit + 1)).fetchall()
    truncated = len(rows) > limit
    rows = [dict(row) for row in rows[:limit]]
    reasons = Counter(row['close_reason'] or 'unknown_terminal_reason' for row in rows if row['closed_at'])
    state_available = sum(row['capital_exit_state_json'] is not None for row in rows)
    # The persisted state contains a pending single confirmation, not the
    # evaluate() return evidence (which has first/second).  Do not manufacture
    # a two-confirmation metric from arbitrary JSON substrings.
    confirmation_checkpoints = 0
    for row in rows:
        try:
            state = json.loads(row['capital_exit_state_json'] or '{}')
            composite = state.get('composite151') if isinstance(state, dict) else None
            confirmation_checkpoints += isinstance(composite, dict) and isinstance(composite.get('confirmation'), dict)
        except (TypeError, ValueError):
            pass
    intent_columns = {row[1] for row in c.execute('PRAGMA table_info(chain_meme_trader_order_intents)')}
    intent_required = {'definition_version', 'arm_id', 'shadow_cohort_id', 'token_id', 'side', 'reason'}
    trigger = {'status': 'unknown', 'reason': 'sell_intent_schema_unavailable', 'count': None}
    if intent_required <= intent_columns:
        # The CTE has precisely the selected diagnostic identities and ordering;
        # an excluded 201st row cannot alter a <=200 report result.
        trigger_rows = c.execute('WITH child AS (SELECT definition_version,shadow_cohort_id,token_id '
            'FROM chain_meme_trader_positions WHERE arm_id=? '
            'ORDER BY COALESCE(closed_at,opened_at) DESC,definition_version DESC,shadow_cohort_id DESC,token_id DESC LIMIT ?) '
            'SELECT COUNT(*) n FROM chain_meme_trader_order_intents i JOIN child c '
            'ON c.definition_version=i.definition_version AND c.shadow_cohort_id=i.shadow_cohort_id '
            'AND c.token_id=i.token_id WHERE i.arm_id=? AND i.side=\'SELL\' '
            'AND i.reason=\'confirmed_market_decay_net_recovery151\'',
            (COMPOSITE151_ARM, limit, COMPOSITE151_ARM)).fetchone()
        count = int(trigger_rows['n'] if hasattr(trigger_rows, 'keys') else trigger_rows[0])
        trigger = {'status': 'observed' if count else 'not_observed', 'count': count,
                   'evidence': 'persisted_sell_intent_exact_reason'}
    if not rows:
        trigger = {'status': 'no_natural_samples', 'count': 0,
                   'evidence': 'no_child_arm_positions_in_bounded_scope'}
    by_version = {}
    for row in rows:
        group = by_version.setdefault(row['definition_version'], {'positions': 0, 'tokens': set(), 'open_positions': 0})
        group['positions'] += 1; group['tokens'].add(row['token_id'])
        group['open_positions'] += row['closed_at'] is None
    return {
        'definition': 'Bounded persisted Paper positions for the composite151 child arm. Terminal reasons are outcomes, not causal pre-emption claims.',
        'sample_scope': f'Latest <={limit} child-arm positions by terminal/open time; archive-compatible; no parent comparison is computed.',
        'status': 'ok' if rows else 'no_natural_samples', 'arm_id': COMPOSITE151_ARM, 'parent_arm_id': COMPOSITE151_PARENT,
        'natural_paper_positions': len(rows),
        'independent_tokens': len({row['token_id'] for row in rows}),
        'open_positions': sum(row['closed_at'] is None for row in rows),
        'definition_version_counts': [dict(definition_version=version, positions=group['positions'],
            independent_tokens=len(group['tokens']), open_positions=group['open_positions'])
            for version, group in sorted(by_version.items())],
        'terminal_reasons': dict(reasons),
        'persisted_two_confirmation_trigger': trigger,
        'state_checkpoint': {'available_positions': state_available,
                             'pending_confirmation_positions': confirmation_checkpoints,
                             'meaning': 'single-confirmation checkpoint only; not an exit-trigger proof'},
        'parent_comparison': {'status': 'pending', 'reason': 'not computed in this bounded per-arm readout'},
        'truncated': truncated,
    }


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
        'counts': {str(m): dict(Counter(x['horizons'][str(m)]['status'] for x in outcomes)) for m in (5,15)},
        'composite_exit151': composite_exit151_diagnostics(c), 'samples': outcomes}


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
