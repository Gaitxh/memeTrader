"""Complete normalized universe only; frozen dates and broad preregistered split."""
import json,sqlite3,itertools,statistics,collections,math
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];O=R/'data/research/universe71';meta=json.loads((O/'normalized.json').read_text());assert meta['complete']
c=sqlite3.connect(O/'normalized_identity.sqlite3');c.row_factory=sqlite3.Row
records=[]
for token,trows in itertools.groupby(c.execute('select * from frames order by token,pool,rec,id'),lambda r:r['token']):
 pools=[(pool,list(rs)) for pool,rs in itertools.groupby(trows,lambda r:r['pool'])];original=min(pools,key=lambda z:(z[1][0]['rec'],z[1][0]['id']))[0]
 for pool,ss in pools:
  a=ss[0];day=datetime.fromtimestamp(a['rec'],timezone.utc).date().isoformat()
  if day not in ['2026-09-07','2026-09-08','2026-09-09']:continue
  e=next((s for s in ss if s['obs']>a['rec']),None);age=a['obs']-a['created']/1000 if isinstance(a['created'],(int,float)) else None
  trades=a['buys']+a['sells'] if a['buys'] is not None and a['sells'] is not None else None
  row={'token':token,'pool':pool,'day':day,'chain':token.split(':')[0],'original':pool==original,'source':a['source'],'venue':a['dex'],'quote':a['quote'],'launchpad':'UNKNOWN','anchor_id':a['id'],'anchor_rec':a['rec'],'entry_id':e['id'] if e else None,'entry_rec':e['rec'] if e else None,'entry_delay_seconds':e['rec']-a['rec'] if e else None,'age':age,'liq':a['liq'],'features':{'activity_rate':trades/min(age,300) if trades is not None and age is not None and age>0 else None,'buy_share':a['buys']/trades if trades else None,'turnover':a['volume']/a['liq'] if a['volume'] is not None else None,'price_growth':e['price']/a['price']-1 if e else None,'liq_growth':e['liq']/a['liq']-1 if e else None,'same_source':e['source']==a['source'] if e else None,'path_efficiency':None,'native_state':None},'outcomes':{}}
  if e and day!='2026-09-09':
   for h in (900,3600,21600):
    path=[s for s in ss if e['rec']<s['obs']<=e['rec']+h];end=next((s for s in ss if e['rec']+h<=s['obs']<=e['rec']+h+120),None);rs=[(s['price']*.96/(e['price']*1.04)-1,s['rec']) for s in path];best=max(rs,key=lambda z:z[0]) if rs else None
    row['outcomes'][str(h)]={'frames':len(path),'endpoint_id':end['id'] if end else None,'endpoint_net':end['price']*.96/(e['price']*1.04)-1 if end else None,'mfe':best[0] if best else None,'peak_observed_at':best[1] if best else None,'loss50':min(z[0] for z in rs)<=-.5 if rs else None}
  records.append(row)
original=[r for r in records if r['original']];train=[r for r in original if r['day']=='2026-09-07' and r['entry_id']]
medians={k:statistics.median([r['features'][k] for r in train if r['features'][k] is not None]) for k in ['activity_rate','buy_share','turnover','price_growth','liq_growth'] if any(r['features'][k] is not None for r in train)}
for r in records:
 f=r['features'];r['support']=None if any(f[k] is None for k in ['activity_rate','price_growth','liq_growth']) else f['activity_rate']>=medians.get('activity_rate',float('inf')) and f['price_growth']>=0 and f['liq_growth']>=0

def stats(xs):
 out={'n':len(xs),'entries':sum(bool(r['entry_id']) for r in xs),'horizons':{}}
 for h in ['900','3600','21600']:
  oo=[r['outcomes'].get(h,{}) for r in xs];values=[z['mfe'] for z in oo if z.get('mfe') is not None]
  out['horizons'][h]={'observed_paths':len(values),'endpoint_n':sum(z.get('endpoint_id') is not None for z in oo),'tail100':sum(v>=1 for v in values),'tail400':sum(v>=4 for v in values),'tail900':sum(v>=9 for v in values),'loss50':sum(z.get('loss50') is True for z in oo),'tail100_after_remove_top1':max(0,sum(v>=1 for v in values)-1),'tail100_after_remove_top3':max(0,sum(v>=1 for v in values)-3)}
 return out
summary={day:stats([r for r in original if r['day']==day]) for day in ['2026-09-07','2026-09-08','2026-09-09']}
splits={f'{day}:{support}':stats([r for r in original if r['day']==day and r['support']==support]) for day in ['2026-09-07','2026-09-08'] for support in [True,False,None]}
strata={f'{day}:{chain}:{source}':stats([r for r in original if r['day']==day and r['chain']==chain and r['source']==source]) for day,chain,source in sorted({(r['day'],r['chain'],r['source']) for r in original})}
(O/'universe.json').write_text(json.dumps({'meta':meta,'medians':medians,'summary':summary,'splits':splits,'strata':strata,'rows':records}),encoding='utf-8');(O/'summary.json').write_text(json.dumps({'medians':medians,'summary':summary,'splits':splits},indent=2));print(json.dumps({'pools':len(records),'original':len(original),'summary':summary,'splits':splits}),flush=True)
