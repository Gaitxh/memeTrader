"""Read-only arm projection accounting. Never infer historical missing receipts."""
from collections import Counter
from datetime import datetime, timedelta, timezone


def _date(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def projection_diagnostics(c, cutoff, minutes, limit=2000):
    limit = min(2000, max(1, int(limit)))
    end = _date(cutoff)
    start = end - timedelta(minutes=minutes)
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'chain_meme_trader_v6_cohorts', 'chain_meme_trader_entry_decisions',
                'chain_meme_trader_positions', 'chain_meme_trader_entry_participant_outcomes'}
    if not required <= tables:
        return {'status': 'unknown', 'reason': 'required_schema_missing'}
    receipt_table = 'chain_meme_trader_entry_gate_refusals'
    has_receipts = receipt_table in tables
    # Indexed lexical coarse bounds include mixed Z/+00:00 and whole-second UTC;
    # exact filtering remains causal and never includes evidence beyond cutoff.
    lower = (start-timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    upper = (end+timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    cohorts = c.execute('SELECT id,definition_version,token_id,pair_address,decided_at,entry_family '
        'FROM chain_meme_trader_v6_cohorts WHERE decided_at>=? AND decided_at<=? '
        'AND julianday(decided_at)>=julianday(?) AND julianday(decided_at)<=julianday(?) '
        'ORDER BY id DESC LIMIT ?', (lower, upper, start.isoformat(), end.isoformat(), limit+1)).fetchall()
    truncated = len(cohorts) > limit
    stats, tokens, pools, reasons, examples = Counter(), set(), set(), Counter(), []
    positions_by_token = {}
    for cohort in cohorts[:limit]:
        version, cohort_id = cohort['definition_version'], cohort['id']
        identity = (version, cohort_id)
        tokens.add(cohort['token_id'])
        pair = cohort['pair_address'] or ''
        if not cohort['token_id'].startswith('solana:'):
            pair = pair.lower()
        pools.add((cohort['token_id'].split(':', 1)[0], pair))
        decisions = c.execute('SELECT arm_id,status,decided_at FROM chain_meme_trader_entry_decisions '
            'WHERE definition_version=? AND shadow_cohort_id=?', identity).fetchall()
        admitted = {d['arm_id'] for d in decisions if d['status']=='admitted' and _date(d['decided_at'])<=end}
        # Reuse the existing (definition_version,token_id,...) index, once per
        # token. A version+cohort-only query scans the full funding-period book.
        token_key = (version, cohort['token_id'])
        if token_key not in positions_by_token:
            by_cohort = {}
            for p in c.execute('SELECT shadow_cohort_id,arm_id,opened_at FROM chain_meme_trader_positions '
                               'WHERE definition_version=? AND token_id=?', token_key):
                if _date(p['opened_at']) <= end:
                    by_cohort.setdefault(p['shadow_cohort_id'], set()).add(p['arm_id'])
            positions_by_token[token_key] = by_cohort
        booked = positions_by_token[token_key].get(cohort_id, set())
        cash = {r['arm_id'] for r in c.execute('SELECT arm_id,outcome,recorded_at FROM '
            'chain_meme_trader_entry_participant_outcomes WHERE definition_version=? AND shadow_cohort_id=?',
            identity) if r['outcome']=='skipped_cash_unavailable_at_fill' and _date(r['recorded_at'])<=end}
        cap = set()
        if has_receipts:
            for row in c.execute(f'SELECT arm_id,gate,reason,attempted_at,recorded_at FROM {receipt_table} '
                                 'WHERE definition_version=? AND shadow_cohort_id=?', identity):
                if _date(row['attempted_at']) <= _date(row['recorded_at']) <= end:
                    if row['gate'] == 'pool_concentration':
                        cap.add(row['arm_id'])
                    reasons[(row['gate'], row['reason'])] += 1
        unresolved = admitted - booked - cash - cap
        # A later successful booking wins the current-as-of disposition, while
        # the earlier refusal remains separately reported as an attempted gate.
        disjoint_cash, disjoint_cap = (cash & admitted)-booked, (cap & admitted)-booked-cash
        stats.update(cohorts=1, cohorts_with_positions=int(bool(booked)),
            admitted_arms=len(admitted), booked_arms=len(booked),
            booked_admitted_arms=len(booked & admitted),
            cash_refused_admitted_arms=len(disjoint_cash),
            concentration_refused_admitted_arms=len(disjoint_cap),
            observed_concentration_refusals=len(cap), unresolved_admitted_arms=len(unresolved))
        if (cap or unresolved) and len(examples) < 12:
            examples.append(dict(definition_version=version, cohort_id=cohort_id,
                token_id=cohort['token_id'], pair_address=cohort['pair_address'],
                admitted_arms=len(admitted), booked_arms=len(booked),
                concentration_receipts=len(cap), unresolved_admitted_arms=len(unresolved)))
    return {'status': 'observed', 'cutoff': cutoff, 'window_minutes': minutes, 'truncated': truncated,
        'sample_limit_cohorts': limit, 'unit': 'cohort opportunity; arm counts are non-independent fanout',
        'gate_receipt_schema_available': has_receipts, 'counts': dict(stats),
        'distinct_tokens': len(tokens), 'distinct_chain_pools': len(pools),
        'gate_reasons': [dict(gate=k[0], reason=k[1], arm_attempts=v) for k,v in reasons.most_common(20)],
        'examples': examples, 'limits': [
            'No historical backfill: missing receipts are unresolved/pending/unobserved, never inferred rejections.',
            'Admitted-arm partition is booked + cash refused + concentration refused + unresolved as of cutoff.',
            'Native/direct positions may have no ordinary admitted-arm decision; booked_arms is reported separately.',
            'A shared source fill is not an arm-level position. Prior refusal can coexist with later booking.']}
