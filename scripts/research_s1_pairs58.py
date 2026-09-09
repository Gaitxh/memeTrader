"""Read-only exact-fill S1 horizon comparison; no replay or threshold search."""
import collections
import json
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/research/s1_pairs58'
OUT.mkdir(exist_ok=True)
ARMS = ('age_rate_horizon_fast_v1', 'age_rate_horizon_runner_v1')
VERSION = 'chain-meme-trader/funding-20260906-v002-final-1000'
def date(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))
storm_start = date('2026-09-08T19:06:00Z')
storm_end = date('2026-09-08T19:51:47Z')
native = date('2026-09-08T21:17:50Z')
c = sqlite3.connect(f'file:{ROOT.as_posix()}/data/memetrader_forward_20260830_r6.sqlite3?mode=ro', uri=True, timeout=5)
c.row_factory = sqlite3.Row
c.execute('BEGIN')
cutoff = datetime.now(timezone.utc).isoformat()
rows = [dict(x) for x in c.execute('select * from chain_meme_trader_positions where definition_version=? and arm_id in (?,?)', (VERSION, *ARMS))]
trades = [dict(x) for x in c.execute('select * from chain_meme_trader_trades where definition_version=? and arm_id in (?,?)', (VERSION, *ARMS))]
c.rollback(); c.close()
groups = collections.defaultdict(dict)
for row in rows:
    key = (row['token_id'], row['shadow_cohort_id'], row['source_entry_fill_id'])
    assert row['arm_id'] not in groups[key], 'ambiguous duplicate position'
    groups[key][row['arm_id']] = row
pairs=[]; rejected=[]
for key, group in groups.items():
    if not key[2] or len(group)!=2:
        rejected.append(dict(key=key, reason='missing_shared_fill_or_counterpart'));continue
    a,b=(group[arm] for arm in ARMS)
    fields=('source_buy_trade_id','entry_snapshot_id','initial_amount_raw','stake_usd','entry_execution_price_usd','paper_quantity_tokens','opened_at')
    differences=[f for f in fields if a[f]!=b[f] or a[f] is None]
    buy=[]
    for x in (a,b):
        ts=[t for t in trades if t['arm_id']==x['arm_id'] and t['shadow_cohort_id']==key[1] and t['token_id']==key[0]]
        buys=[t for t in ts if t['side'].upper()=='BUY'];buy.append(buys)
        total=sum(t['realized_pnl_usd'] or 0 for t in ts)
        assert math.isclose(total,x['realized_pnl_usd'] or 0,abs_tol=1e-8), 'position/trade PnL mismatch'
    if len(buy[0])!=1 or len(buy[1])!=1 or any(buy[0][0][f]!=buy[1][0][f] for f in ('gross_usd','net_cash_flow_usd','created_at')):
        differences.append('BUY_cash_or_time')
    if differences:
        rejected.append(dict(key=key,reason=differences));continue
    terminal=all(x['closed_at'] and x['status']!='open' for x in (a,b))
    opened=date(a['opened_at']);last=max(date(x['closed_at'] or cutoff) for x in (a,b))
    if opened<storm_end and last>=storm_start: partition='storm_confounded'
    elif last<storm_start: partition='pre_storm'
    elif opened>=native: partition='post_native53'
    else: partition='post_fix_pre_native53'
    durations=[(date(x['closed_at'])-opened).total_seconds() if x['closed_at'] else None for x in (a,b)]
    pairs.append(dict(token_id=key[0],cohort=key[1],source_entry_fill_id=key[2],partition=partition,terminal=bool(terminal),
        opened_at=a['opened_at'],chain=key[0].split(':')[0],utc_date=opened.date().isoformat(),
        fast=a,runner=b,delta=(a['realized_pnl_usd']-b['realized_pnl_usd']) if terminal else None,
        both_exit_before15m=bool(terminal and max(durations)<900),
        fast_max_hold='max_hold' in (a['close_reason'] or ''),duration_seconds=durations))
def summary(xs):
    xs=[x for x in xs if x['terminal']];ds=sorted(x['delta'] for x in xs);n=len(ds);k=int(n*.1);trim=ds[k:n-k] if k else ds
    return dict(n=n,unique_tokens=len({x['token_id'] for x in xs}),fast_pnl=sum(x['fast']['realized_pnl_usd'] for x in xs),runner_pnl=sum(x['runner']['realized_pnl_usd'] for x in xs),
        sum_delta=sum(ds),mean=statistics.mean(ds) if n else None,median=statistics.median(ds) if n else None,trimmed_mean_10pct=statistics.mean(trim) if trim else None,
        min=min(ds) if ds else None,max=max(ds) if ds else None,wins=sum(d>1e-8 for d in ds),ties=sum(abs(d)<=1e-8 for d in ds),losses=sum(d< -1e-8 for d in ds),
        top1_removed_sum=sum(ds[:-1]) if n>1 else None,top3_removed_sum=sum(ds[:-3]) if n>3 else None,
        both_before15m=sum(x['both_exit_before15m'] for x in xs),fast_max_hold=sum(x['fast_max_hold'] for x in xs),
        reasons=dict(collections.Counter(x['fast']['close_reason']+' | '+x['runner']['close_reason'] for x in xs)),chains=dict(collections.Counter(x['chain'] for x in xs)),dates=dict(collections.Counter(x['utc_date'] for x in xs)))
clean=[x for x in pairs if x['partition']!='storm_confounded']
summaries={p:summary([x for x in pairs if x['partition']==p]) for p in ('pre_storm','storm_confounded','post_fix_pre_native53','post_native53')}
summaries.update(clean=summary(clean),clean_fast_max_hold=summary([x for x in clean if x['fast_max_hold']]),clean_no_treatment=summary([x for x in clean if x['both_exit_before15m']]))
result=dict(cutoff=cutoff,storm_interval=['2026-09-08T19:06:00Z','2026-09-08T19:51:47Z'],pairs=pairs,rejected=rejected,open_censored=sum(not x['terminal'] for x in pairs),summary=summaries)
(OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='pairs'},indent=2))
