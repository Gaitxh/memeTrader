"""Frozen58, decision-time only features; no production writes."""
import json,sqlite3,statistics,collections,math
from pathlib import Path
from datetime import datetime,timedelta
R=Path(__file__).resolve().parents[1];O=R/'data/research/conditional66';O.mkdir(exist_ok=True)
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
frozen=json.loads((R/'data/research/s1_pairs58/result.json').read_text())
pairs=[p for p in frozen['pairs'] if p['terminal'] and p['fast_max_hold'] and p['partition']!='storm_confounded'];assert len(pairs)==21
c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
marks={r['shadow_cohort_id']:dict(r) for r in c.execute("select shadow_cohort_id,recorded_at from chain_meme_trader_marks where definition_version=? and arm_id=? and reason='market_mark_max_hold'",(pairs[0]['fast']['definition_version'],'age_rate_horizon_fast_v1'))}
sells=[dict(r) for r in c.execute("select shadow_cohort_id,created_at from chain_meme_trader_trades where definition_version=? and arm_id=? and side='SELL'",(pairs[0]['fast']['definition_version'],'age_rate_horizon_fast_v1'))]
out=[]
for p in pairs:
 a=p['fast'];cut=dt(a['last_evaluated_at']);opened=dt(a['opened_at']);entry=dict(c.execute('select * from token_snapshots where id=?',(a['entry_snapshot_id'],)).fetchone());pair=json.loads(entry['raw_json']).get('pair',{}).get('pairAddress')
 assert dt(marks[p['cohort']]['recorded_at'])==cut
 assert not any(t['shadow_cohort_id']==p['cohort'] and dt(t['created_at'])<cut for t in sells)
 canon=lambda v:str(v or '').lower() if p['chain']!='solana' else str(v or '')
 rows=[]
 for s in c.execute('select * from token_snapshots where token_id=? and observed_at>=? and observed_at<=? order by observed_at,id',(p['token_id'],a['opened_at'],cut.isoformat().replace('+00:00','Z'))):
  s=dict(s);raw=json.loads(s.pop('raw_json'));sp=raw.get('pair',{}).get('pairAddress')
  try:
   obs,ing,rec=[dt(s[k]) for k in ('observed_at','ingested_at','recorded_at')]
   if not (obs<=ing<=rec<=cut and (rec-obs).total_seconds()<=15 and canon(sp)==canon(pair) and pair):continue
   if not s['price_usd'] or s['price_usd']<=0 or s['liquidity_usd'] is None or s['liquidity_usd']<1000:continue
   s['source']=raw.get('upstream_provider') or s['provider'];rows.append(s)
  except (ValueError,TypeError):continue
 rows.sort(key=lambda s:(s['recorded_at'],s['id']));last=rows[-1] if rows else None
 fresh=last is not None and (cut-dt(last['observed_at'])).total_seconds()<=30
 x={'token_id':p['token_id'],'chain':p['chain'],'date':p['utc_date'],'cohort':p['cohort'],'cutoff':cut.isoformat(),'boundary_lag_seconds':(cut-opened).total_seconds()-900,'incremental_runner_pnl':-p['delta'],'runner_reason':p['runner']['close_reason'],'snapshot_rows':len(rows),'last_snapshot':last,'source_mix':dict(collections.Counter(s['source'] for s in rows)),'fresh':fresh,'entry_liquidity':entry['liquidity_usd'],'states':{k:'UNKNOWN' for k in ['economic','liquidity','direction','activity','support']}}
 if fresh:
  net=a['paper_quantity_tokens']*last['price_usd']*.96-a['stake_usd'];x['net_return']=net/a['stake_usd'];x['states']['economic']='positive' if net>0 else 'underwater'
  if entry['liquidity_usd'] and entry['liquidity_usd']>0:
   x['entry_liquidity_retention']=last['liquidity_usd']/entry['liquidity_usd'];x['states']['liquidity']='deteriorating' if x['entry_liquidity_retention']<1 else 'not_deteriorating'
  x['sampled_high_liquidity_retention']=last['liquidity_usd']/max(s['liquidity_usd'] for s in rows);x['sampled_price_drawdown']=last['price_usd']/max(s['price_usd'] for s in rows)-1
  for seconds,state,field in [(60,'direction','price_usd'),(300,'activity','volume_5m_usd')]:
   prev=[s for s in rows if dt(s['observed_at'])<=cut-timedelta(seconds=seconds)]
   prev=prev[-1] if prev else None
   if prev and (cut-timedelta(seconds=seconds)-dt(prev['observed_at'])).total_seconds()<=60 and prev['source']==last['source'] and prev[field] is not None and last[field] is not None:
    x['states'][state]=('cooling' if last[field]<prev[field] else 'not_cooling') if state=='activity' else ('down' if last[field]<prev[field] else 'not_down')
  st=x['states'];x['states']['support']='UNKNOWN' if any(st[k]=='UNKNOWN' for k in ['economic','liquidity','direction','activity']) else ('yes' if st['economic']=='positive' and st['liquidity']=='not_deteriorating' and st['direction']=='not_down' and st['activity']=='not_cooling' else 'no')
 out.append(x)
def stats(xs):
 ds=sorted(x['incremental_runner_pnl'] for x in xs);return dict(n=len(xs),sum=sum(ds),median=statistics.median(ds) if ds else None,beneficial=sum(d>0 for d in ds),top1_removed=sum(ds[:-1]) if len(ds)>1 else None,top3_removed=sum(ds[:-3]) if len(ds)>3 else None,chains=dict(collections.Counter(x['chain'] for x in xs)),dates=dict(collections.Counter(x['date'] for x in xs)))
summary={key:{v:stats([x for x in out if x['states'][key]==v]) for v in sorted({x['states'][key] for x in out})} for key in out[0]['states']}
(O/'result.json').write_text(json.dumps({'frozen_cutoff':frozen['cutoff'],'summary':summary,'rows':out},indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
