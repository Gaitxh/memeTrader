"""Bounded local all-snapshot universe; fail closed on incomplete scan."""
import sqlite3,json,time,collections,statistics,math
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];O=R/'data/research/universe71';O.mkdir(exist_ok=True)
def stamp(s):
 try:return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
 except (ValueError,TypeError,AttributeError):return None
c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
cut=datetime.now(timezone.utc);hi=c.execute('select max(id) from token_snapshots').fetchone()[0];start=time.monotonic();c.set_progress_handler(lambda:int(time.monotonic()-start>180),1000)
groups=collections.defaultdict(list);seen=0;invalid=0;complete=False
try:
 for s in c.execute("select id,token_id,observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,volume_5m_usd,buys_5m,sells_5m,provider,json_extract(raw_json,'$.upstream_provider') upstream,json_extract(raw_json,'$.pair.pairAddress') pool,json_extract(raw_json,'$.pair.pairCreatedAt') created,json_extract(raw_json,'$.pair.dexId') dex from token_snapshots where id<=? and price_usd>0 and liquidity_usd>=1000 order by id",(hi,)):
  seen+=1
  if seen>250000:raise RuntimeError('qualifying_row_budget')
  obs,ing,rec=[stamp(s[k]) for k in ('observed_at','ingested_at','recorded_at')]
  if None in (obs,ing,rec) or not obs<=ing<=rec<=cut.timestamp() or not s['pool']:invalid+=1;continue
  d=dict(s);d.update(obs=obs,rec=rec);pool=d['pool'] if d['token_id'].startswith('solana:') else d['pool'].lower();d['pool']=pool;groups[(d['token_id'],pool)].append(d)
  if seen%50000==0:print('read',seen,'seconds',round(time.monotonic()-start,2),flush=True)
 complete=True
except (sqlite3.OperationalError,RuntimeError) as e:error=str(e)
meta={'cutoff':cut.isoformat(),'snapshot_frontier':hi,'qualifying_rows_read':seen,'invalid_frames':invalid,'complete_scan':complete,'elapsed':time.monotonic()-start,'error':None if complete else error,'pool_groups_retained':len(groups)}
(O/'scan.json').write_text(json.dumps(meta,indent=2));print(meta,flush=True)
if not complete:raise SystemExit(0)
# Only complete scanning can establish first-ever local original pool membership.
first={}
for key,ss in groups.items():
 ss.sort(key=lambda s:(s['rec'],s['id']))
 if key[0] not in first or (ss[0]['rec'],ss[0]['id'])<first[key[0]][0]:first[key[0]]=((ss[0]['rec'],ss[0]['id']),key[1])
records=[]
for (token,pool),ss in groups.items():
 a=ss[0];day=datetime.fromtimestamp(a['rec'],timezone.utc).date().isoformat()
 if day not in ['2026-09-07','2026-09-08','2026-09-09']:continue
 entry=next((s for s in ss if s['obs']>a['rec']),None);row={'token':token,'pool':pool,'day':day,'chain':token.split(':')[0],'original':first[token][1]==pool,'anchor':a,'entry':entry,'outcomes':{}}
 if entry and day!='2026-09-09':
  for h in [900,3600,21600]:
   path=[s for s in ss if entry['rec']<s['obs']<=entry['rec']+h];end=next((s for s in ss if entry['rec']+h<=s['obs']<=entry['rec']+h+120),None);rets=[s['price_usd']*.96/(entry['price_usd']*1.04)-1 for s in path];row['outcomes'][str(h)]={'path_n':len(path),'endpoint':end['id'] if end else None,'mfe':max(rets) if rets else None,'observed_loss50':min(rets)<=-.5 if rets else None}
 records.append(row)
(O/'universe.json').write_text(json.dumps({'meta':meta,'rows':records}),encoding='utf-8')
