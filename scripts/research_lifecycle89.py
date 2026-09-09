"""Review every effective arm from frozen current-period rows, not winner labels."""
import collections
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/research/lifecycle89'


def metrics(rows):
    terminal = [r for r in rows if r['status'] in ('closed', 'written_off')]
    values = sorted(r['realized_pnl_usd'] for r in terminal)
    n = len(values); trim = int(n*.1)
    gains = sum(max(v, 0) for v in values); losses = -sum(min(v, 0) for v in values)
    return dict(n=n, tokens=len({r['token_id'] for r in terminal}),
        open=sum(r['status']=='open' for r in rows), pnl=sum(values),
        median=statistics.median(values) if n else None,
        mean=statistics.mean(values) if n else None,
        trim10=statistics.mean(values[trim:n-trim] if trim else values) if n else None,
        wins=sum(v>0 for v in values), profit_factor=gains/losses if losses else None,
        best=max(values) if n else None, worst=min(values) if n else None,
        top1_removed=sum(values[:-1]) if n else None,
        top3_removed=sum(values[:-3]) if n>=3 else None,
        catastrophic_n=sum(r['realized_pnl_usd'] <= -.5*r['stake_usd'] for r in terminal),
        close_reasons=dict(collections.Counter(r['close_reason'] for r in terminal)))


def compare(left, right):
    # No fuzzy matching: nonempty source fill and all economic entry fields agree.
    def key(r):
        return r['token_id'], r['source_entry_fill_id']
    fields = ('source_buy_trade_id', 'entry_snapshot_id', 'stake_usd',
              'entry_execution_price_usd', 'paper_quantity_tokens', 'opened_at')
    index = collections.defaultdict(list)
    for r in right:
        if r['source_entry_fill_id']: index[key(r)].append(r)
    pairs = []; unmatched = []; incompatible = []
    for a in left:
        choices = index.get(key(a), []) if a['source_entry_fill_id'] else []
        if len(choices)!=1:
            unmatched.append(a); continue
        b = choices[0]
        if any(a[f]!=b[f] or a[f] is None for f in fields):
            incompatible.append({'left':a,'right':b}); continue
        if a['status'] not in ('closed','written_off') or b['status'] not in ('closed','written_off'):
            unmatched.append(a); continue
        pairs.append(dict(token=a['token_id'], source_fill=a['source_entry_fill_id'],
            left_pnl=a['realized_pnl_usd'], right_pnl=b['realized_pnl_usd'],
            delta=a['realized_pnl_usd']-b['realized_pnl_usd'],
            left_reason=a['close_reason'], right_reason=b['close_reason'],
            opened_at=a['opened_at'], left_closed=a['closed_at'],right_closed=b['closed_at']))
    deltas=sorted(p['delta'] for p in pairs)
    clean=[p for p in pairs if not (p['opened_at']<'2026-09-08T19:51:47' and
           max(p['left_closed'] or '',p['right_closed'] or '')>='2026-09-08T19:06:00')]
    return dict(n=len(pairs),left=sum(p['left_pnl'] for p in pairs),right=sum(p['right_pnl'] for p in pairs),
        delta=sum(deltas),wins=sum(d>1e-9 for d in deltas),ties=sum(abs(d)<=1e-9 for d in deltas),
        losses=sum(d< -1e-9 for d in deltas),top3_delta_removed=sum(deltas[:-3]),
        clean_n=len(clean),clean_delta=sum(p['delta'] for p in clean),
        unmatched_metrics=metrics(unmatched),incompatible=len(incompatible),rows=pairs)


def run():
    frozen=json.loads((OUT/'frozen.json').read_text())
    positions=collections.defaultdict(list)
    for row in frozen['positions']: positions[row['arm_id']].append(row)
    policies={p['arm_id']:p for p in frozen['policies']}
    controls={}
    for c in sorted(frozen['controls'],key=lambda c:c['updated_at']):
        controls.update(json.loads(c['value_json'])['arms'])
    rows=[]
    for arm,p in policies.items():
        m=metrics(positions[arm]); control=controls.get(arm,{})
        reason=control.get('reason',''); representative=control.get('representative')
        same_hash=bool(representative in policies and p.get('behavior_contract_hash') and
                       p.get('behavior_contract_hash')==policies[representative].get('behavior_contract_hash'))
        if not p.get('entry_paused'): status='ACTIVE'
        elif p.get('account_lifecycle')=='RETIRED_DUPLICATE' and same_hash: status='DUPLICATE_SUPERSEDED'
        elif arm in ('market_regime_throttle_v1','early_impulse_profit_lock_control_v1'): status='DUPLICATE_SUPERSEDED'
        elif m['pnl']>0: status='EXPERIMENT_COMPLETE_POSITIVE'
        elif 'DATA_INPUT_BLOCKED' in reason or arm in ('inventory_baseline_v1','inventory_contraction_v1'):
            status='DATA_BLOCKED'
        elif m['n']<30 or 'convergence63:' in reason: status='INSUFFICIENT'
        elif m['pnl']<0 and (m['median'] or 0)<=0: status='FAILED'
        else: status='INSUFFICIENT'
        rows.append(dict(arm_id=arm,name=p.get('name'),paused=bool(p.get('entry_paused')),
            lifecycle=status,control=control,metrics=m,paired_group=p.get('paired_entry_group'),
            behavior_hash=p.get('behavior_contract_hash'),representative_hash_equal=same_hash))
    comparisons={}
    for a,b in [('age_rate_horizon_fast_v1','resource_age_rate_candidate_v1'),
                ('market_regime_throttle_v1','event_reawakening_v1'),
                ('early_impulse_profit_lock_control_v1','early_impulse_trailing_60m_v1')]:
        comparisons[a]=dict(reference=b,**compare(positions[a],positions[b]))
    for r in rows:
        if r['paused'] and r['metrics']['pnl']>0 and r['control'].get('representative') in policies and r['arm_id'] not in comparisons:
            b=r['control']['representative'];comparisons[r['arm_id']]=dict(reference=b,**compare(positions[r['arm_id']],positions[b]))
    result=dict(cutoff=frozen['cutoff'],version=frozen['version'],trade_frontier=frozen['trade_frontier'],
        counts=dict(collections.Counter(r['lifecycle'] for r in rows)),arms=rows,comparisons=comparisons,
        caveat='Lifecycle is a current evidence disposition, not a claim of statistically proven negative alpha. All prior controls retained.')
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'counts':result['counts'],'comparisons':{a:{k:v for k,v in r.items() if k!='rows'} for a,r in comparisons.items()}},indent=2))


if __name__=='__main__':run()
