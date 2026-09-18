"""Paired A/B evaluation for two arms that ride the same frozen opportunities.

The project has repeatedly drawn wrong conclusions from unpaired arm comparisons. This makes the
correct comparison cheap and repeatable: for every shared opportunity it computes the within-pair
difference, then reports the pooled mean, the sign test, and a token-clustered bootstrap interval
(resampling tokens, because one token can carry dozens of arms).

THREE PAIRING MODES, and the choice is forced by the arms, not by preference:

  --pair-on cohort   (default) the two arms were admitted on the SAME frozen signal, i.e. the
                     same shadow_cohort_id. This is the stronger design because the market
                     moment is identical.
  --pair-on token    the two arms traded the SAME token at different moments. This is required
                     whenever the arms cannot share a cohort -- measured 2026-09-14 on
                     `demand_floor153_d47_v1` vs its control: all 10 of the new arm's tokens had
                     also been traded by the control, but at DIFFERENT cohorts, because the
                     control carries `single_token_lifetime_entry` and had already consumed those
                     tokens before the new arm existed. Pairing on cohort would have reported
                     "0 pairs" forever and the arm could never be judged.

  --pair-on source_buy matches identical recorded source fills, namespaced by execution
                       model and period, with equal stakes. Reference existence and
                       external economic adjustments still require a ledger audit.

In token mode the independent unit is the TOKEN (the project's agreed unit) and each arm
contributes its FIRST position on that token, so one token cannot be counted many times through
fan-out.

Read-only. Usage:
    python scripts/paired_arm_ab.py ARM_A ARM_B
    python scripts/paired_arm_ab.py ARM_A ARM_B --pair-on token --min-tokens 30 --hours 48
    python scripts/paired_arm_ab.py ARM_A ARM_B --json
"""
from __future__ import annotations

import argparse
import json
import random
import math
import statistics
from datetime import datetime, timezone
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The project-agreed bar: >=30 INDEPENDENT TOKENS, a paired comparison, and a negative result
# after cost. It used to be 20 settled positions, which is not the same thing.
MIN_SETTLED_PER_SIDE = 30


def resolve_db() -> Path:
    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    return ROOT / cfg['database']


def active_version(cur) -> str:
    return cur.execute(
        "SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
    ).fetchone()[0]


def load_positions(cur, version: str, arms: tuple[str, str], hours: int):
    rows = cur.execute(
        "SELECT definition_version,source_entry_fill_id,source_buy_trade_id,entry_reason,arm_id, shadow_cohort_id, token_id, status, stake_usd, realized_pnl_usd, "
        "       opened_at, closed_at, close_reason "
        "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id IN (?,?) "
        "AND julianday(opened_at)>=julianday('now',?)",
        (version, arms[0], arms[1], '-%d hour' % hours),
    ).fetchall()
    return rows


def summarise(rows, arm):
    items = [dict(r) for r in rows if r['arm_id'] == arm]
    settled = [r for r in items if _terminal(r)]
    stake = sum(float(r['stake_usd'] or 0) for r in settled)
    pnl = sum(float(r['realized_pnl_usd'] or 0) for r in settled)
    wins = sum(1 for r in settled if float(r['realized_pnl_usd'] or 0) > 0)
    return {
        'positions': len(items),
        'settled': len(settled),
        'tokens': len({r['token_id'] for r in items}),
        'stake_usd': round(stake, 2),
        'pnl_usd': round(pnl, 2),
        'pnl_per_stake': round(100.0 * pnl / stake, 2) if stake else None,
        'win_rate': round(100.0 * wins / len(settled), 1) if settled else None,
    }


TERMINAL_STATES = frozenset(('closed', 'written_off'))

def _terminal(row):
    if row.get('status') not in TERMINAL_STATES:
        return False
    try:
        stake, pnl = float(row['stake_usd']), float(row['realized_pnl_usd'])
        return math.isfinite(stake) and stake > 0 and math.isfinite(pnl)
    except (KeyError, TypeError, ValueError):
        return False

def _opened(row):
    try:
        at = datetime.fromisoformat(str(row['opened_at']).replace('Z', '+00:00'))
        return at.timestamp() if at.tzinfo is not None else None
    except (KeyError, TypeError, ValueError):
        return None

def _source_key(row):
    def positive(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            number = int(value)
            return number if number > 0 and str(number) == str(value) else None
        except (TypeError, ValueError):
            return None
    fill = positive(row.get('source_entry_fill_id'))
    if fill is not None:
        return ('v6_entry_fill', fill)
    if row.get('entry_reason') == 'later_observed_protocol_model_paper':
        trade = positive(row.get('source_buy_trade_id'))
        return ('native_trade', trade) if trade is not None else None
    return None


def paired(rows, a, b, pair_on="cohort"):
    """Keep all common terminal units, including ties; never select on maturity.

    Token mode selects the first OPENED position in the supplied window before
    checking terminal status. Different entry moments are descriptive, not a
    controlled exit experiment. Source mode namespaces v6 fills and native trades.
    Ambiguous duplicates, invalid amounts and identity mismatches are excluded.
    """
    if pair_on not in ('cohort', 'token', 'source_buy') or a == b:
        raise ValueError('distinct arms and a supported pairing mode are required')
    groups = defaultdict(lambda: defaultdict(list))
    for value in rows:
        r = dict(value)
        if r.get('arm_id') not in (a, b) or not r.get('token_id'):
            continue
        opened = _opened(r)
        if opened is None:
            continue
        version = r.get('definition_version', '')
        token = r['token_id']
        if pair_on == 'token':
            key = (version, token)
        elif pair_on == 'source_buy':
            source = _source_key(r)
            if source is None:
                continue
            key = (version, token, *source)
        else:
            if r.get('shadow_cohort_id') is None:
                continue
            key = (version, token, r['shadow_cohort_id'])
        groups[key][r['arm_id']].append((opened, r))
    diffs = []
    for key, grouped in groups.items():
        chosen = {}
        for arm in (a, b):
            entries = grouped.get(arm, [])
            if not entries:
                break
            if pair_on == 'token':
                first_at = min(t for t, _ in entries)
                entries = [(t, r) for t, r in entries if t == first_at]
            if len(entries) != 1 or not _terminal(entries[0][1]):
                break
            chosen[arm] = entries[0][1]
        if a not in chosen or b not in chosen:
            continue
        ra, rb = chosen[a], chosen[b]
        if pair_on == 'source_buy' and not math.isclose(float(ra['stake_usd']), float(rb['stake_usd']), rel_tol=0, abs_tol=1e-9):
            continue
        if pair_on == 'source_buy' and ra.get('source_buy_trade_id') != rb.get('source_buy_trade_id'):
            continue
        av, bv = float(ra['realized_pnl_usd']), float(rb['realized_pnl_usd'])
        unit = ra['shadow_cohort_id'] if pair_on == 'cohort' else ra['token_id'] if pair_on == 'token' else key[2:]
        diffs.append(dict(unit=unit, cohort=ra['shadow_cohort_id'],
            token_id=ra['token_id'], definition_version=ra.get('definition_version', ''),
            difference=av-bv, a=av, b=bv, pair_key=key))
    return diffs



def clustered_interval(diffs, iterations=5000, seed=20260912):
    """Bootstrap over TOKENS, because positions cluster inside a token."""
    by_token = defaultdict(list)
    for d in diffs:
        by_token[d['token_id']].append(d['difference'])
    tokens = list(by_token)
    if len(tokens) < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        picked = [tokens[rng.randrange(len(tokens))] for _ in tokens]
        values = [v for t in picked for v in by_token[t]]
        if values:
            means.append(sum(values) / len(values))
    means.sort()
    n = len(means)
    return (round(means[int(.05 * n)], 4), round(means[int(.95 * n)], 4))


def leave_one_token_out(diffs):
    """Report the least supportive removal for either effect direction."""
    by_token = defaultdict(list)
    for d in diffs:
        by_token[d['token_id']].append(float(d['difference']))
    if len(by_token) < 2:
        return None
    total = sum(sum(v) for v in by_token.values())
    count = sum(len(v) for v in by_token.values())
    full = total / count
    remaining = {t: (total-sum(v))/(count-len(v)) for t,v in by_token.items()}
    lower_token = min(remaining, key=remaining.get)
    upper_token = max(remaining, key=remaining.get)
    worst_token = lower_token if full >= 0 else upper_token
    survives = (min(remaining.values()) > 0 if full > 0 else
                max(remaining.values()) < 0 if full < 0 else False)
    return dict(full_mean=round(full,4), worst_case_mean=round(remaining[worst_token],4),
                worst_case_token=worst_token, minimum_remaining_mean=min(remaining.values()),
                maximum_remaining_mean=max(remaining.values()), sign_survives=survives)



def source_pair_coverage(rows, a, b):
    """Describe every supplied source unit, including unpaired and pending units.

    This measures overlap, not missed-trade causality or independent evidence.
    Apply a common activation/time window before calling for revision reviews.
    """
    if a == b:
        raise ValueError('distinct arms required')
    groups = defaultdict(lambda: defaultdict(list))
    invalid = 0
    selected_rows = 0
    for value in rows:
        row = dict(value)
        arm = row.get('arm_id')
        if arm not in (a, b):
            continue
        selected_rows += 1
        source = _source_key(row)
        if source is None or not row.get('token_id') or _opened(row) is None:
            invalid += 1
            continue
        key = (row.get('definition_version', ''), row['token_id'], *source)
        groups[key][arm].append(row)
    counts = defaultdict(int)
    token_sets = defaultdict(set)
    for key, grouped in groups.items():
        left, right = grouped.get(a, []), grouped.get(b, [])
        if len(left) > 1 or len(right) > 1:
            category = 'ambiguous_duplicate'
        elif not left:
            category = 'b_only'
        elif not right:
            category = 'a_only'
        else:
            ra, rb = left[0], right[0]
            if ra.get('source_buy_trade_id') != rb.get('source_buy_trade_id'):
                category = 'source_pointer_mismatch'
            elif not (_terminal(ra) and _terminal(rb)):
                states = {ra.get('status'), rb.get('status')}
                if states <= TERMINAL_STATES:
                    category = 'invalid_terminal_money'
                elif states <= TERMINAL_STATES | {'open'}:
                    category = 'awaiting_terminal'
                else:
                    category = 'unsupported_status'
            elif not math.isclose(float(ra['stake_usd']), float(rb['stake_usd']),
                                  rel_tol=0, abs_tol=1e-9):
                category = 'unequal_stake'
            else:
                category = 'common_terminal'
        counts[category] += 1
        token_sets[category].add(key[1])
    return {'input_positions': selected_rows, 'invalid_input_positions': invalid,
            'source_units': len(groups), 'counts': dict(counts),
            'tokens_by_category': {k: len(v) for k, v in token_sets.items()},
            'independent_tokens_in_union': len({key[1] for key in groups}),
            'warning': 'Categories partition source units, not independent tokens. '
                       'One-sided records are not proof of missed opportunities; '
                       'open or absent outcomes are never zero returns.'}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('arm_a')
    ap.add_argument('arm_b')
    ap.add_argument('--hours', type=int, default=48)
    ap.add_argument('--pair-on', choices=('cohort', 'token', 'source_buy'), default='cohort',
                    help='cohort = same frozen signal (stronger); token = same token, different '
                         'moments (descriptive); source_buy = identical namespaced recorded source')
    ap.add_argument('--min-tokens', type=int, default=MIN_SETTLED_PER_SIDE,
                    help='independent units required before a verdict is allowed (default 30)')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    if args.hours <= 0 or args.min_tokens < 2 or args.arm_a == args.arm_b:
        ap.error('positive hours, at least two tokens and distinct arms are required')

    db = resolve_db()
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    version = active_version(cur)
    rows = load_positions(cur, version, (args.arm_a, args.arm_b), args.hours)
    con.close()
    a_stats = summarise(rows, args.arm_a)
    b_stats = summarise(rows, args.arm_b)
    diffs = paired(rows, args.arm_a, args.arm_b, pair_on=args.pair_on)
    values = [d['difference'] for d in diffs]
    paired_tokens = len({d['token_id'] for d in diffs})
    report = {
        'definition_version': version,
        'window_hours': args.hours,
        'pair_on': args.pair_on,
        'economic_basis': 'raw terminal position PnL; external adjustments need separate audit',
        'matching_warning': 'Token mode uses first within the declared input window; different entry times are not a controlled exit test',
        'all_ties_retained': True,
        'source_pair_coverage': source_pair_coverage(rows, args.arm_a, args.arm_b)
            if args.pair_on == 'source_buy' else None,
        'as_of_utc': datetime.now(timezone.utc).isoformat(),
        'arm_a': args.arm_a, 'arm_b': args.arm_b,
        'a': a_stats, 'b': b_stats,
        'paired_units': len(diffs),
        'paired_tokens': paired_tokens,
        'mean_difference': round(sum(values) / len(values), 4) if values else None,
        'median_difference': (statistics.median(values) if values else None),
        'a_better_share': (round(100.0 * sum(1 for v in values if v > 0) / len(values), 1)
                           if values else None),
        'token_clustered_90ci': clustered_interval(diffs),
        'leave_one_token_out': leave_one_token_out(diffs),
        # The agreed bar is INDEPENDENT TOKENS on both sides plus enough paired units. Counting
        # settled positions instead let fan-out masquerade as sample size.
        'verdict_ready': (a_stats['tokens'] >= args.min_tokens
                          and b_stats['tokens'] >= args.min_tokens
                          and paired_tokens >= args.min_tokens),
        'minimum_independent_tokens': args.min_tokens,
        'minimum_settled_per_side': MIN_SETTLED_PER_SIDE,
    }
    if report['token_clustered_90ci']:
        low, high = report['token_clustered_90ci']
        report['interval_excludes_zero'] = bool(low > 0 or high < 0)
    else:
        report['interval_excludes_zero'] = None
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print('definition : %s' % version)
    print('window     : last %d hours' % args.hours)
    print('pairing    : %s%s' % (args.pair_on,
                                 '  (same frozen signal)'
                                 if args.pair_on == 'cohort' else
                                 '  (same namespaced source BUY, equal stake)' if args.pair_on == 'source_buy' else
                                 '  (same token, first position per arm in this window; descriptive)'))
    print()
    print('%-38s %-9s %-9s %-10s %-9s %s' % ('arm', 'positions', 'settled', 'pnl/stake', 'win%', 'pnl'))
    for label, stats in ((args.arm_a, a_stats), (args.arm_b, b_stats)):
        print('%-38s %-9s %-9s %-10s %-9s %s' % (
            label[:38], stats['positions'], stats['settled'],
            ('%.2f%%' % stats['pnl_per_stake']) if stats['pnl_per_stake'] is not None else '-',
            ('%.1f' % stats['win_rate']) if stats['win_rate'] is not None else '-',
            stats['pnl_usd']))
    print()
    print('paired units (%s) : %d' % (args.pair_on, len(diffs)))
    print('independent tokens in the paired set: %d' % paired_tokens)
    if report['source_pair_coverage'] is not None:
        print('source-unit coverage (not zero returns): %s' %
              json.dumps(report['source_pair_coverage'], ensure_ascii=False))
    if values:
        print('mean difference (A - B)           : %+.4f USD' % report['mean_difference'])
        print('median difference                 : %+.4f USD' % report['median_difference'])
        print('A better in                        : %.1f%% of pairs' % report['a_better_share'])
        ci = report['token_clustered_90ci']
        if ci:
            print('token-clustered 90%% interval       : [%+.4f, %+.4f]%s'
                  % (ci[0], ci[1], '  (excludes zero)' if report['interval_excludes_zero'] else ''))
        else:
            print('token-clustered interval           : not enough distinct tokens')
        loo = report['leave_one_token_out']
        if loo:
            print('drop the single worst token        : mean %+.4f (token %s) -> sign %s'
                  % (loo['worst_case_mean'], str(loo['worst_case_token'])[:34],
                     'survives' if loo['sign_survives'] else 'FLIPS'))
    else:
        print('no %s holds both arms settled yet' % args.pair_on)
    print()
    if report['verdict_ready']:
        print('DESCRIPTIVE SAMPLE MINIMUM MET (not profitability proof): >=%d tokens per side and >=%d paired tokens'
              % (args.min_tokens, args.min_tokens))
    else:
        print('NOT READY: needs >=%d independent tokens per side and >=%d paired tokens '
              '(A has %d, B has %d, paired %d)'
              % (args.min_tokens, args.min_tokens, a_stats['tokens'], b_stats['tokens'],
                 paired_tokens))
    return 0


if __name__ == '__main__':
    sys.exit(main())
