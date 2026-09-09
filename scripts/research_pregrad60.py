"""Read-only first-state reserve-velocity research; see prereg60 before use."""
import json,sqlite3,collections,statistics,math
from pathlib import Path
from datetime import datetime,timezone
from memetrader.pregrad_watch import bonding_curve_identity
from memetrader.collectors import SOLANA_SYSTEM_PROGRAM_ID,SOLANA_WRAPPED_SOL_MINT
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/research/pregrad60';OUT.mkdir(exist_ok=True)
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
c=sqlite3.connect(f'file:{ROOT.as_posix()}/data/memetrader_forward_20260830_r6.sqlite3?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row
prior=json.loads((OUT/'frozen_features.json').read_text(encoding='utf-8')) if (OUT/'frozen_features.json').exists() else None
cut=dt(prior['cutoff']) if prior else datetime.now(timezone.utc);cutoff=cut.isoformat();hi=prior['frontier'] if prior else c.execute('select max(id) from token_snapshots').fetchone()[0]
ev=[dict(x) for x in c.execute("select id,token_id,observed_at,recorded_at,payload_json from chain_meme_pattern_evidence where kind='pregrad_watch' and recorded_at<=? order by id",(cutoff,))]
states={};reject=collections.Counter();stages=collections.Counter()
for e in ev:
 p=json.loads(e['payload_json']);stages[p.get('stage')]+=1;t=e['token_id']
 if t in states or p.get('stage')!='PREGRAD' or len(p.get('reserve_frames',[]))!=2:continue
 try:
  a,b=p['reserve_frames'];launch=dt(p['launch_observed_at']);available=dt(e['recorded_at'])
  identity=bonding_curve_identity(p)
  assert identity['curve_address']==p['curve_address'] and p['token_id']==t
  assert launch<=dt(a['observed_at'])<=dt(a['recorded_at'])<dt(b['observed_at'])<=dt(b['recorded_at'])<=available<=cut
  assert a['slot']<b['slot'] and a['data_hash'] and b['data_hash']
  assert not a['curve_complete'] and not b['curve_complete']
  assert a['quote_mint']==b['quote_mint'] and b['quote_mint'] in (SOLANA_SYSTEM_PROGRAM_ID,SOLANA_WRAPPED_SOL_MINT)
  assert all(isinstance(f['real_quote_reserves_raw'],int) and f['real_quote_reserves_raw']>=0 for f in (a,b))
  spacing=(dt(b['observed_at'])-dt(a['observed_at'])).total_seconds();v=(b['real_quote_reserves_raw']-a['real_quote_reserves_raw'])/1e9/spacing
  stored=p.get('net_reserve_growth_quote_per_second');assert stored is not None and math.isclose(v,stored,abs_tol=1e-12)
 except (AssertionError,ValueError,KeyError,TypeError):reject['invalid_first_eligible_record']+=1;continue
 date=available.date().isoformat();level=b['real_quote_reserves_raw']/1e9;age=(available-launch).total_seconds()
 states[t]=dict(token_id=t,evidence_id=e['id'],available=e['recorded_at'],date=date,split='train' if date<'2026-09-08' else 'holdout' if date=='2026-09-08' else 'prospective',velocity=v,reserve_sol=level,seed=p.get('initial_quote_amount'),age=age,spacing=spacing,frames=[a,b],progress=None,reserve_band=0 if level<10 else 1 if level<30 else 2 if level<60 else 3,age_band=0 if age<60 else 1 if age<180 else 2)
train=sorted(x['velocity'] for x in states.values() if x['split']=='train' and x['velocity']>0)
q1=train[int((len(train)-1)/3)] if train else None;q2=train[int(2*(len(train)-1)/3)] if train else None
for x in states.values():x['bin']='nonpositive' if x['velocity']<=0 else 'positive_low' if x['velocity']<=q1 else 'positive_mid' if x['velocity']<=q2 else 'positive_high'
(OUT/'frozen_features.json').write_text(json.dumps({'cutoff':cutoff,'frontier':hi,'quantiles':[q1,q2],'rows':list(states.values()),'stages':dict(stages),'rejected':dict(reject)},indent=2),encoding='utf-8')
print('features',len(states),'q',q1,q2,flush=True)
# Freeze matches using features alone, BEFORE outcome reads.
used=set();matches=[]
for x in sorted(states.values(),key=lambda z:(z['available'],z['token_id'])):
 if x['bin']!='positive_high':continue
 candidates=[y for y in states.values() if y['bin'] in ('nonpositive','positive_low') and y['date']==x['date'] and y['reserve_band']==x['reserve_band'] and y['age_band']==x['age_band'] and y['token_id'] not in used]
 if not candidates:matches.append([x['token_id'],None]);continue
 y=min(candidates,key=lambda z:(abs(z['reserve_sol']-x['reserve_sol']),abs(z['age']-x['age']),abs(z['spacing']-x['spacing']),z['token_id']));used.add(y['token_id']);matches.append([x['token_id'],y['token_id']])
(OUT/'matches.json').write_text(json.dumps(matches),encoding='utf-8')
migrations={}
for e in c.execute("select * from token_launch_facts where launch_event_type='migration' and recorded_at<=? order by id",(cutoff,)):
 if e['token_id'] not in states:continue
 if dt(e['source_observed_at'])<=dt(e['ingested_at'])<=dt(e['recorded_at'])<=cut:
  migrations.setdefault(e['token_id'],dict(e))
for i,x in enumerate(states.values()):
 m=migrations.get(x['token_id']);x['migration']=m;x['preexisting_migration']=bool(m and dt(m['recorded_at'])<=dt(x['available']));x['postgrad']={}
 if not m or x['preexisting_migration']:continue
 x['migration_delay']=(dt(m['recorded_at'])-dt(x['available'])).total_seconds()
 ss=[]
 for s in c.execute('select id,observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,provider,raw_json from token_snapshots where token_id=? and observed_at>? and id<=? order by observed_at,id',(x['token_id'],m['recorded_at'],hi)):
  if not all(s[k] for k in ('observed_at','ingested_at','recorded_at')):continue
  if not dt(m['recorded_at'])<dt(s['observed_at'])<=dt(s['ingested_at'])<=dt(s['recorded_at'])<=cut:continue
  raw=json.loads(s['raw_json']);pair=raw.get('pair',{})
  if pair.get('dexId')!='pumpswap' or pair.get('chainId')!='solana' or pair.get('baseToken',{}).get('address')!=x['token_id'].split(':',1)[1] or not pair.get('pairAddress'):continue
  ss.append(dict(id=s['id'],observed_at=s['observed_at'],recorded_at=s['recorded_at'],price=s['price_usd'],liquidity=s['liquidity_usd'],pair=pair['pairAddress'],provider=raw.get('upstream_provider') or s['provider']))
 valid=lambda s:s['price'] is not None and s['price']>0 and s['liquidity'] is not None and s['liquidity']>=1000
 anchor=next((s for s in ss if valid(s)),None);x['postgrad']['anchor']=anchor
 if not anchor:continue
 entry=next((s for s in ss if s['pair']==anchor['pair'] and valid(s) and 0<(dt(s['observed_at'])-dt(anchor['recorded_at'])).total_seconds()<=120),None);x['postgrad']['entry']=entry
 if not entry:continue
 for minutes in (15,60):
  path=[s for s in ss if s['pair']==entry['pair'] and dt(s['observed_at'])>dt(entry['recorded_at'])];end=next((s for s in path if minutes*60<=(dt(s['observed_at'])-dt(entry['recorded_at'])).total_seconds()<=minutes*60+120),None)
  observed=[s for s in path if valid(s) and (dt(s['observed_at'])-dt(entry['recorded_at'])).total_seconds()<=minutes*60]
  ret=lambda s:s['price']*.96/(entry['price']*1.04)-1
  x['postgrad'][str(minutes)]=dict(endpoint=end,return_net=ret(end) if end and valid(end) else None,mfe_observed=max((ret(s) for s in observed),default=None),frames=len(observed),below_floor_frames=sum(s['liquidity'] is not None and s['liquidity']<1000 for s in path if (dt(s['observed_at'])-dt(entry['recorded_at'])).total_seconds()<=minutes*60))
 if i%500==0:print('outcomes',i,flush=True)
summary={}
for split in ('train','holdout','prospective'):
 for band in ('nonpositive','positive_low','positive_mid','positive_high'):
  xs=[x for x in states.values() if x['split']==split and x['bin']==band and not x['preexisting_migration']];out={'n':len(xs),'migration_observed':sum(bool(x['migration']) for x in xs)}
  for h in (3600,21600):
   mature=[x for x in xs if (cut-dt(x['available'])).total_seconds()>=h];out[str(h)]={'mature':len(mature),'migration_observed':sum(x.get('migration_delay',float('inf'))<=h for x in mature)}
  out['entries']=sum(bool(x['postgrad'].get('entry')) for x in xs)
  for h in ('15','60'):
   results=[x['postgrad'].get(h,{}) for x in xs];rs=sorted(z['return_net'] for z in results if z.get('return_net') is not None);mf=[z['mfe_observed'] for z in results if z.get('mfe_observed') is not None]
   out[h]=dict(endpoint_n=len(rs),mean=statistics.mean(rs) if rs else None,median=statistics.median(rs) if rs else None,sum=sum(rs),top1_removed=sum(rs[:-1]) if len(rs)>1 else None,top3_removed=sum(rs[:-3]) if len(rs)>3 else None,observed_path_n=len(mf),righttail100=sum(v>=1 for v in mf))
  summary[split+':'+band]=out
result=dict(cutoff=cutoff,summary=summary,rows=list(states.values()),quantiles=[q1,q2],preexisting_migrations=sum(x['preexisting_migration'] for x in states.values()))
(OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(summary))
