"""Read-only post53 natural receipt cohort; no market/backtest writes."""
import sqlite3,json,collections,statistics
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/research/native_coverage55';OUT.mkdir(exist_ok=True)
c=sqlite3.connect('file:E:/memeTrader/data/memetrader_forward_20260830_r6.sqlite3?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row
cut=datetime.now(timezone.utc);cutoff=cut.isoformat().replace('+00:00','Z');start='2026-09-08T21:17:40Z'
hi=c.execute('select max(id) from token_snapshots').fetchone()[0]
def date(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
cohort=[dict(x) for x in c.execute("select e.token_id,min(e.observed_at) receipt,r.surface from token_discovery_exposures e join token_discovery_rounds r on r.id=e.round_id where r.provider='native-launch' and r.started_at>=? and r.started_at<=? and e.first_local_discovery=1 group by e.token_id,r.surface",(start,cutoff))]
frozen={x['token_id'] for x in json.loads((ROOT/'data/research/native_launch53/acceptance.json').read_text())['rows']}
# Small outcome-blind descriptive comparison, same chain/hour, first20 lexical identities.
controls=[];buckets=collections.defaultdict(list)
for x in c.execute("select e.token_id,min(e.observed_at) receipt,r.provider surface from token_discovery_exposures e join token_discovery_rounds r on r.id=e.round_id where r.provider!='native-launch' and e.chain in ('bsc','robinhood') and e.first_local_discovery=1 and r.started_at>=? and r.started_at<=? group by e.token_id",(start,cutoff)):
 x=dict(x);buckets[(x['token_id'].split(':')[0],x['receipt'][:13])].append(x)
for xs in buckets.values():
 for x in sorted(xs,key=lambda z:z['token_id'])[:20]:x['surface']='comparison:'+x['surface'];controls.append(x)
print('cohorts',len(cohort),len(controls),flush=True)
evaluation_first={}
for e in c.execute("select token_id,min(evaluated_at) at from chain_meme_trader_v6_entry_evaluations where evaluated_at>=? and evaluated_at<=? group by token_id",(start,cutoff)):
 evaluation_first[e['token_id']]=e['at']
rows=[]
for i,x in enumerate(cohort+controls):
 token=x['token_id'];at=date(x['receipt']);snaps=c.execute("select id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,json_extract(raw_json,'$.pair.pairAddress') pair,json_extract(raw_json,'$.upstream_provider') upstream from token_snapshots where token_id=? and observed_at>=? and observed_at<=? and id<=? order by observed_at,id",(token,x['receipt'],cutoff,hi)).fetchall()
 valid=[];reasons=collections.Counter();pairs=set();providers=set()
 for s in snaps:
  causal=all(s[k] for k in ('observed_at','ingested_at','recorded_at')) and at<=date(s['observed_at'])<=date(s['ingested_at'])<=date(s['recorded_at'])<=cut
  if not causal:reasons['invalid_clocks']+=1;continue
  if not s['pair']:reasons['missing_exact_pool']+=1;continue
  pairs.add(s['pair'].lower() if token.startswith('bsc:') or token.startswith('robinhood:') else s['pair']);providers.add(s['upstream'] or s['provider'])
  if not s['price_usd'] or s['price_usd']<=0:reasons['price_missing_or_nonpositive']+=1;continue
  if s['liquidity_usd'] is None:reasons['liquidity_missing']+=1;continue
  if s['liquidity_usd']<1000:reasons['liquidity_below_1000']+=1;continue
  valid.append(dict(s))
 valid.sort(key=lambda z:(z['recorded_at'],z['id']));first=valid[0] if valid else None
 h=c.execute('select * from token_detail_hydration where token_id=?',(token,)).fetchone()
 attempts=[dict(r) for r in c.execute('select requested_at,status,reason_code,completed_at from token_discovery_quote_attempts where token_id=? and requested_at>=? and requested_at<=? order by requested_at',(token,x['receipt'],cutoff))]
 er=evaluation_first.get(token)
 if er and date(er)<at:er=None
 rows.append(dict(x,frozen53=token in frozen,age_seconds=(cut-at).total_seconds(),snapshot_count=len(snaps),invalid=dict(reasons),first_valid=first,delay_seconds=(date(first['recorded_at'])-at).total_seconds() if first else None,pools=sorted(pairs),providers=sorted(providers),hydration=dict(h) if h else None,quote_attempts=attempts,first_strategy_evaluation=er))
 if i%500==0:print('processed',i,flush=True)
summary={}
for group in sorted({r['surface'] for r in rows}):
 rs=[r for r in rows if r['surface']==group];coverage={}
 for horizon in (30,60,120,180,300,900):
  mature=[r for r in rs if r['age_seconds']>=horizon];n=sum(r['delay_seconds'] is not None and r['delay_seconds']<=horizon for r in mature);coverage[str(horizon)]={'mature_n':len(mature),'valid_n':n,'fraction':n/len(mature) if mature else None}
 summary[group]={'n':len(rs),'ever_valid':sum(r['first_valid'] is not None for r in rs),'coverage':coverage,'hydration_status':dict(collections.Counter((r['hydration'] or {}).get('status','missing') for r in rs)),'attempt_status':dict(collections.Counter(a['status'] for r in rs for a in r['quote_attempts'])),'no_snapshot':sum(not r['snapshot_count'] for r in rs),'multi_pool':sum(len(r['pools'])>1 for r in rs),'providers':dict(collections.Counter(p for r in rs for p in r['providers'])),'strategy_evaluated':sum(r['first_strategy_evaluation'] is not None for r in rs)}
result={'cutoff':cutoff,'start':start,'snapshot_frontier':hi,'summary':summary,'rows':rows};(OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(OUT/'summary.json').write_text(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2),encoding='utf-8');print(json.dumps(summary))
