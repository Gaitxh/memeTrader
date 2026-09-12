"""Paired A/B evaluation for two arms that ride the same frozen opportunities.

The project has repeatedly drawn wrong conclusions from unpaired arm comparisons. This makes the
correct comparison cheap and repeatable: for every cohort that contains BOTH arms, it computes the
within-cohort difference, then reports the pooled mean, the sign test, and a token-clustered
bootstrap interval (resampling tokens, because one token can carry dozens of arms).

Read-only. Usage:
    python scripts/paired_arm_ab.py alpha149_mid_band_flow_v1 alpha149_shallow_band_flow_v1
    python scripts/paired_arm_ab.py ARM_A ARM_B --hours 48 --json
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_SETTLED_PER_SIDE = 20


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
        "SELECT arm_id, shadow_cohort_id, token_id, status, stake_usd, realized_pnl_usd, "
        "       opened_at, closed_at, close_reason "
        "FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id IN (?,?) "
        "AND julianday(opened_at)>=julianday('now',?)",
        (version, arms[0], arms[1], '-%d hour' % hours),
    ).fetchall()
    return rows


def summarise(rows, arm):
    items = [r for r in rows if r['arm_id'] == arm]
    settled = [r for r in items if r['status'] != 'open']
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


def paired(rows, a, b):
    """Within-cohort differences, only where BOTH arms are settled."""
    by_cohort = defaultdict(dict)
    for r in rows:
        by_cohort[r['shadow_cohort_id']][r['arm_id']] = r
    diffs = []
    for cohort, arms in by_cohort.items():
        if a not in arms or b not in arms:
            continue
        ra, rb = arms[a], arms[b]
        if ra['status'] == 'open' or rb['status'] == 'open':
            continue
        diffs.append({
            'cohort': cohort,
            'token_id': ra['token_id'],
            'difference': float(ra['realized_pnl_usd'] or 0) - float(rb['realized_pnl_usd'] or 0),
            'a': float(ra['realized_pnl_usd'] or 0),
            'b': float(rb['realized_pnl_usd'] or 0),
        })
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
    """The check that catches a single trade driving the result.

    A clustered interval can exclude zero while one token supplies the whole effect - that is
    exactly how the plateau_stall result looked before its best trade was removed. This reports
    the mean difference with each token dropped in turn, so the weakest version of the claim is
    visible next to the strongest.
    """
    by_token = defaultdict(list)
    for d in diffs:
        by_token[d['token_id']].append(d['difference'])
    if len(by_token) < 2:
        return None
    all_values = [d['difference'] for d in diffs]
    full = sum(all_values) / len(all_values)
    worst_token, worst = None, None
    for token, values in by_token.items():
        remaining = [v for t, vals in by_token.items() if t != token for v in vals]
        if not remaining:
            continue
        mean = sum(remaining) / len(remaining)
        if worst is None or mean < worst:
            worst, worst_token = mean, token
    return {
        'full_mean': round(full, 4),
        'worst_case_mean': round(worst, 4) if worst is not None else None,
        'worst_case_token': worst_token,
        'sign_survives': bool(worst is not None and (worst > 0) == (full > 0)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('arm_a')
    ap.add_argument('arm_b')
    ap.add_argument('--hours', type=int, default=48)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    db = resolve_db()
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=300)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    version = active_version(cur)
    rows = load_positions(cur, version, (args.arm_a, args.arm_b), args.hours)
    a_stats = summarise(rows, args.arm_a)
    b_stats = summarise(rows, args.arm_b)
    diffs = paired(rows, args.arm_a, args.arm_b)
    values = [d['difference'] for d in diffs]
    report = {
        'definition_version': version,
        'window_hours': args.hours,
        'arm_a': args.arm_a, 'arm_b': args.arm_b,
        'a': a_stats, 'b': b_stats,
        'paired_cohorts': len(diffs),
        'mean_difference': round(sum(values) / len(values), 4) if values else None,
        'median_difference': (sorted(values)[len(values) // 2] if values else None),
        'a_better_share': (round(100.0 * sum(1 for v in values if v > 0) / len(values), 1)
                           if values else None),
        'token_clustered_90ci': clustered_interval(diffs),
        'leave_one_token_out': leave_one_token_out(diffs),
        'verdict_ready': (a_stats['settled'] >= MIN_SETTLED_PER_SIDE
                          and b_stats['settled'] >= MIN_SETTLED_PER_SIDE
                          and len(diffs) >= MIN_SETTLED_PER_SIDE),
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
    print()
    print('%-38s %-9s %-9s %-10s %-9s %s' % ('arm', 'positions', 'settled', 'pnl/stake', 'win%', 'pnl'))
    for label, stats in ((args.arm_a, a_stats), (args.arm_b, b_stats)):
        print('%-38s %-9s %-9s %-10s %-9s %s' % (
            label[:38], stats['positions'], stats['settled'],
            ('%.2f%%' % stats['pnl_per_stake']) if stats['pnl_per_stake'] is not None else '-',
            ('%.1f' % stats['win_rate']) if stats['win_rate'] is not None else '-',
            stats['pnl_usd']))
    print()
    print('paired cohorts (both sides settled): %d' % len(diffs))
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
        print('no cohort holds both arms settled yet')
    print()
    if report['verdict_ready']:
        print('VERDICT READY: >=%d settled on both sides and >=%d paired cohorts'
              % (MIN_SETTLED_PER_SIDE, MIN_SETTLED_PER_SIDE))
    else:
        print('NOT READY: needs >=%d settled per side and >=%d paired cohorts; report readiness only'
              % (MIN_SETTLED_PER_SIDE, MIN_SETTLED_PER_SIDE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
