"""Bounded read-only falsification; no fitted exit or production writes."""
import sqlite3,json,time,statistics
from datetime import datetime,timedelta,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'data/research/system90/addendum_a';O.mkdir(exist_ok=True)
def dt(x):return datetime.fromisoformat(x.replace('Z','+00:00'))
def iso(x):return x.isoformat().replace('+00:00','Z')
c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
start=time.monotonic();c.set_progress_handler(lambda:int(time.monotonic()-start>60),10000)
cut=iso(datetime.now(timezone.utc));c.execute('begin')
front=c.execute('select max(id) from chain_meme_trader_market_mark_history').fetchone()[0]
parents=[dict(r) for r in c.execute("select * from chain_meme_trader_positions where arm_id='resource_age_rate_candidate_v1'")]
fast={r['source_entry_fill_id']:dict(r) for r in c.execute("select * from chain_meme_trader_positions where arm_id='age_rate_horizon_fast_v1' and status in ('closed','written_off')") if r['source_entry_fill_id']}
out=[]
for p in parents:
 f=fast.get(p['source_entry_fill_id']);matched=bool(f and all(p[k]==f[k] for k in ('token_id','entry_snapshot_id','stake_usd','paper_quantity_tokens','opened_at','entry_execution_price_usd')))
 e=c.execute('select * from token_snapshots where id=?',(p['entry_snapshot_id'],)).fetchone()
 if not e:continue
 raw=json.loads(e['raw_json']);pair=raw.get('pair',{}).get('pairAddress');chain=p['token_id'].split(':')[0]
 canon=lambda v:str(v or '') if chain=='solana' else str(v or '').lower()
 opened=dt(p['opened_at']);boundary=opened+timedelta(seconds=900);end=min(dt(p['closed_at']) if p['closed_at'] else dt(cut),dt(cut))
 x={'token':p['token_id'],'cohort':p['shadow_cohort_id'],'matched_fast':matched,'terminal':p['status'] in ('closed','written_off'),'pnl':p['realized_pnl_usd'],'boundary':iso(boundary),'state':'UNKNOWN','reason':p['close_reason']}
 if end<boundary:x['state']='EXIT_BEFORE_15M' if x['terminal'] else 'NOT_YET_15M';out.append(x);continue
 rows=[]
 for rr in c.execute('select * from chain_meme_trader_market_mark_history where token_id=? and recorded_at>=? and recorded_at<=? and id<=? order by recorded_at,id',(p['token_id'],p['opened_at'],iso(end),front)):
  r=dict(rr)
  if not pair or canon(r['pair_address'])!=canon(pair) or r['status']!='VISIBLE':continue
  if not r['price_usd'] or r['price_usd']<=0 or r['liquidity_usd'] is None or r['liquidity_usd']<1000:continue
  if not r['observed_at'] or not (dt(r['observed_at'])<=dt(r['recorded_at'])) or (dt(r['recorded_at'])-dt(r['observed_at'])).total_seconds()>15:continue
  rows.append(r)
 after=next((r for r in rows if dt(r['observed_at'])>=boundary),None)
 if after:x['first_after_15m']={'id':after['id'],'lag_seconds':(dt(after['observed_at'])-boundary).total_seconds(),'net_proxy':p['paper_quantity_tokens']*after['price_usd']*.96-p['stake_usd']}
 pre=[r for r in rows if dt(r['recorded_at'])<=boundary];last=pre[-1] if pre else None
 x['valid_rows']=len(rows)
 if not last or (boundary-dt(last['observed_at'])).total_seconds()>15:out.append(x);continue
 # No later feature row is used. History lacks ingestion clock; reported explicitly.
 net=p['paper_quantity_tokens']*last['price_usd']*.96-p['stake_usd']
 x.update(state='UNCOVERED' if net<0 else 'COVERED',net_at_boundary=net,frame_id=last['id'],liquidity_retention=last['liquidity_usd']/e['liquidity_usd'] if e['liquidity_usd'] else None,giveback=last['price_usd']/max(r['price_usd'] for r in pre)-1)
 displacement=abs(pre[-1]['price_usd']-pre[0]['price_usd']);travel=sum(abs(b['price_usd']-a['price_usd']) for a,b in zip(pre,pre[1:]));x['path_efficiency']=displacement/travel if travel else None
 # Fixed broad structural veto, excludes economic coverage deliberately.
 x['structural_decay']=x['liquidity_retention'] is not None and x['liquidity_retention']<1 and len(pre)>1 and last['price_usd']<pre[-2]['price_usd']
 nxt=next((r for r in rows if dt(r['observed_at'])>boundary and dt(r['observed_at'])>dt(last['recorded_at'])),None)
 if nxt and (dt(nxt['recorded_at'])-boundary).total_seconds()<=30:
  x['next_frame_exit_proxy']=p['paper_quantity_tokens']*nxt['price_usd']*.96-p['stake_usd'];x['exit_minus_parent']=x['next_frame_exit_proxy']-p['realized_pnl_usd'] if x['terminal'] else None
 hits={};prior=None;gap=False
 for r in rows:
  if prior and dt(r['observed_at'])<=dt(prior['recorded_at']):continue
  if (dt(r['observed_at'])-(dt(prior['observed_at']) if prior else opened)).total_seconds()>30:gap=True
  ret=p['paper_quantity_tokens']*r['price_usd']*.96/p['stake_usd']-1
  for name,yes in [('stop20',ret<=-.2),('up30',ret>=.3),('up100',ret>=1)]:
   if yes and name not in hits:hits[name]=r['observed_at']
  prior=r
 x['sampled_first_hits']=hits;x['continuous_first_hit']='UNKNOWN' if gap else 'SAMPLED_ONLY';out.append(x)
def stats(rs):
 ts=[r for r in rs if r['terminal']];ds=[r['exit_minus_parent'] for r in ts if r.get('exit_minus_parent') is not None]
 return {'n':len(rs),'terminal_n':len(ts),'parent_pnl':sum(r['pnl'] for r in ts),'max_parent_pnl':max((r['pnl'] for r in ts),default=None),'next_frame_n':len(ds),'next_exit_minus_parent':sum(ds),'structural_decay_n':sum(r.get('structural_decay') is True for r in rs)}
summary={g:{s:stats([r for r in out if (g=='all' or r['matched_fast']) and r['state']==s]) for s in sorted({r['state'] for r in out})} for g in ['all','same_fill_fast']}
(O/'research.json').write_text(json.dumps({'cutoff':cut,'frontier':front,'summary':summary,'rows':out,'limitations':['Mark history has no ingestion timestamp; cannot certify full three-clock classifier','Sparse sampled hits are not continuous first-hit truth','Full initial quantity cost proxy; partial exits require richer cash ledger','No threshold search or new strategy']},indent=2),encoding='utf8');print(json.dumps(summary));c.close()
