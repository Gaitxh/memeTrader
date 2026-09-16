"""Bounded, read-only contemporaneous controls for the supplied address cohort.

This is retrospective research, not a Paper signal or an executable fill model.
Candidates and matching use only anchor-time fields; later same-pool marks are
outcomes and never enter the matching score.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('id,token_id,observed_at,ingested_at,recorded_at,provider,price_usd,'
          'liquidity_usd,buys_5m,sells_5m,raw_json')


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except (AttributeError, ValueError):
        return None


def age_band(seconds):
    if seconds is None:
        return 'unknown'
    for upper in (300, 1800, 7200, 86400):
        if seconds < upper:
            return str(upper)
    return 'older'


def frame(row, *, cutoff, entry=True):
    row = dict(row)
    observed, ingested, recorded = (instant(row.get(k)) for k in
                                    ('observed_at', 'ingested_at', 'recorded_at'))
    if not observed or not ingested or not recorded or not observed <= ingested <= recorded <= cutoff:
        return None
    if (recorded - observed).total_seconds() > 15:
        return None
    price, liquidity = row['price_usd'], row['liquidity_usd']
    if not isinstance(liquidity, (int, float)) or not math.isfinite(liquidity) or liquidity < 0:
        return None
    if entry and (not isinstance(price, (int, float)) or not math.isfinite(price)
                  or price <= 0 or liquidity < 1000 or not row['buys_5m'] or not row['sells_5m']):
        return None
    try:
        pair = json.loads(row['raw_json']).get('pair') or {}
        pool = pair.get('pairAddress')
        created = pair.get('pairCreatedAt')
        age = (observed.timestamp() - float(created) / 1000) if created is not None else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    chain = row['token_id'].split(':', 1)[0]
    base = (pair.get('baseToken') or {}).get('address')
    if (not pool or not base or str(pair.get('chainId') or '').lower() != chain
            or (base if chain == 'solana' else base.lower()) != row['token_id'].split(':', 1)[1]
            or (age is not None and age < 0)):
        return None
    return {'id': row['id'], 'token_id': row['token_id'], 'chain': chain,
            'observed_at': row['observed_at'], 'recorded_at': row['recorded_at'],
            'provider': row['provider'], 'pool': pool if chain == 'solana' else pool.lower(),
            'price_usd': price, 'liquidity_usd': liquidity,
            'buys_5m': row['buys_5m'], 'sells_5m': row['sells_5m'],
            'pool_age_seconds': age, 'age_band': age_band(age)}


def match_score(case, candidate):
    if (case['chain'], case['provider'], case['age_band']) != (
            candidate['chain'], candidate['provider'], candidate['age_band']):
        return None
    ratio = candidate['liquidity_usd'] / case['liquidity_usd']
    gap = (instant(case['recorded_at']) - instant(candidate['recorded_at'])).total_seconds()
    if not 0.5 <= ratio <= 2 or not 0 <= gap <= 1800:
        return None
    age_gap = 0 if case['pool_age_seconds'] is None else abs(
        candidate['pool_age_seconds'] - case['pool_age_seconds']) / max(case['pool_age_seconds'], 60)
    return gap / 1800 + abs(math.log2(ratio)) + age_gap


def outcome(connection, anchor, *, cutoff_id, cutoff, minutes=30):
    start = instant(anchor['recorded_at'])
    target = start + timedelta(minutes=minutes)
    upper = target + timedelta(minutes=5)
    rows = connection.execute(f'SELECT {FIELDS} FROM token_snapshots WHERE token_id=? '
        'AND observed_at>? AND observed_at<=? AND id<=? ORDER BY observed_at,id LIMIT 1501',
        (anchor['token_id'], anchor['observed_at'], upper.isoformat().replace('+00:00', 'Z'), cutoff_id)).fetchall()
    truncated = len(rows) > 1500
    eligible = []
    for row in rows[:1500]:
        valid = frame(row, cutoff=cutoff, entry=False)
        if valid and valid['pool'] == anchor['pool'] and valid['provider'] == anchor['provider'] \
                and instant(valid['observed_at']) > start:
            eligible.append(valid)
    writeoffs = [x for x in eligible if x['liquidity_usd'] < 1000
                 and instant(x['recorded_at']) <= target]
    first_writeoff = min(writeoffs, key=lambda x: (instant(x['recorded_at']), x['id']), default=None)
    endpoints = [x for x in eligible if abs((instant(x['observed_at']) - target).total_seconds()) <= 300
                 and x['liquidity_usd'] >= 1000 and isinstance(x['price_usd'], (int, float))
                 and math.isfinite(x['price_usd']) and x['price_usd'] > 0 and x['sells_5m']]
    end = min(endpoints, key=lambda x: (abs((instant(x['observed_at']) - target).total_seconds()), x['id']), default=None)
    return {'horizon_minutes': minutes, 'endpoint_snapshot_id': end['id'] if end else None,
            'observed_writeoff_snapshot_id': first_writeoff['id'] if first_writeoff else None,
            'observed_same_pool_frames': len(eligible),
            'history_truncated': truncated,
            'endpoint_covered': (end is not None or first_writeoff is not None) and not truncated,
            'indicative_two_sided_cost_mark_return': (
                None if truncated else -1.0 if first_writeoff else
                end['price_usd'] * .96 / (anchor['price_usd'] * 1.04) - 1 if end else None),
            'warning': 'Anchor marks are not next-observed BUY/SELL fills; this is not executable PnL.'}


def research(connection, casebook, *, neighbor_ids=4000, max_controls=3, seconds=60):
    cutoff = instant(casebook['cutoff_utc'])
    last_id = connection.execute('SELECT MAX(id) FROM token_snapshots').fetchone()[0]
    deadline = time.monotonic() + seconds
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    supplied = {item['token']['token_id'] for case in casebook['cases'] for item in case['matches']}
    results = []
    for token_id in sorted(supplied):
        if time.monotonic() > deadline:
            break
        rows = connection.execute(f'SELECT {FIELDS} FROM token_snapshots WHERE token_id=? '
            'AND id<=? ORDER BY id LIMIT 3001', (token_id, last_id)).fetchall()
        truncated = len(rows) > 3000
        anchors = [x for row in rows[:3000] if (x := frame(row, cutoff=cutoff))]
        anchor = anchors[0] if anchors else None
        item = {'token_id': token_id, 'anchor': anchor, 'anchor_history_truncated': truncated,
                'controls': [], 'case_outcome': None}
        results.append(item)
        if anchor is None:
            continue
        item['case_outcome'] = outcome(connection, anchor, cutoff_id=last_id, cutoff=cutoff)
        candidates = connection.execute(f'SELECT {FIELDS} FROM token_snapshots '
            'WHERE id>=? AND id<=? AND liquidity_usd>=? AND liquidity_usd<=? AND price_usd>0',
            (max(0, anchor['id'] - neighbor_ids), anchor['id'],
             anchor['liquidity_usd'] * .5, anchor['liquidity_usd'] * 2))
        best = {}
        for row in candidates:
            if row['token_id'] in supplied:
                continue
            candidate = frame(row, cutoff=instant(anchor['recorded_at']))
            if candidate is None:
                continue
            score = match_score(anchor, candidate)
            if score is None:
                continue
            key = candidate['token_id']
            if key not in best or (score, candidate['id']) < (best[key][0], best[key][1]['id']):
                best[key] = (score, candidate)
        for score, candidate in sorted(best.values(), key=lambda x: (x[0], x[1]['id']))[:max_controls]:
            item['controls'].append({'score': score, 'anchor': candidate,
                'outcome': outcome(connection, candidate, cutoff_id=last_id, cutoff=cutoff)})
    return {'casebook_cutoff_utc': casebook['cutoff_utc'], 'read_snapshot_max_id': last_id,
            'research_completed_at': datetime.now(timezone.utc).isoformat(),
            'neighbor_ids': neighbor_ids, 'max_controls_per_case': max_controls,
            'time_match_max_seconds': 1800, 'liquidity_ratio_bounds': [.5, 2],
            'results': results, 'not_an_entry_signal': True}


def summary(report):
    cases = report['results']
    matched = [x for x in cases if x['controls']]
    pairs = [(x['case_outcome']['indicative_two_sided_cost_mark_return'],
              control['outcome']['indicative_two_sided_cost_mark_return'])
             for x in matched for control in x['controls']
             if x['case_outcome']['endpoint_covered'] and control['outcome']['endpoint_covered']]
    paired_cases = {x['token_id'] for x in matched for control in x['controls']
                    if x['case_outcome']['endpoint_covered'] and control['outcome']['endpoint_covered']}
    paired_controls = {control['anchor']['token_id'] for x in matched for control in x['controls']
                       if x['case_outcome']['endpoint_covered'] and control['outcome']['endpoint_covered']}
    return {'supplied_canonical_tokens': len(cases),
            'eligible_case_anchors': sum(x['anchor'] is not None for x in cases),
            'cases_with_controls': len(matched),
            'control_links': sum(len(x['controls']) for x in cases),
            'paired_30m_endpoints': len(pairs),
            'paired_independent_case_tokens': len(paired_cases),
            'paired_distinct_control_tokens': len(paired_controls),
            'case_endpoint_coverage': sum(bool(x['case_outcome'] and x['case_outcome']['endpoint_covered']) for x in cases),
            'case_positive_indicative_cost_mark_rate_in_covered_pairs': (
                sum(a > 0 for a, _ in pairs) / len(pairs) if pairs else None),
            'control_positive_indicative_cost_mark_rate_in_covered_pairs': (
                sum(b > 0 for _, b in pairs) / len(pairs) if pairs else None),
            'warning': 'Post-selected addresses, repeated controls, censored endpoints and mark-only costs; not a strategy edge or executable PnL.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--casebook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--neighbor-ids', type=int, default=4000)
    parser.add_argument('--seconds', type=int, default=60)
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    database = (ROOT / config['database']).resolve()
    with sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        report = research(con, json.loads(args.casebook.read_text(encoding='utf-8')),
                          neighbor_ids=args.neighbor_ids, seconds=args.seconds)
    report['summary'] = summary(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
