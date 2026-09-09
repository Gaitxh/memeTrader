"""Bounded raw identity/first-frame audit of frozen coverage55 identities."""
import json,sqlite3,collections,statistics
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parents[1]
out=root/'data/research/native_coverage55'
r=json.loads((out/'result.json').read_text(encoding='utf-8'))
c=sqlite3.connect(f'file:{root.as_posix()}/data/memetrader_forward_20260830_r6.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row
def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
audit=[]
for x in r['rows']:
 if x['surface'].startswith('comparison:'):continue
 snaps=c.execute('select id,observed_at,ingested_at,recorded_at,raw_json from token_snapshots where token_id=? and observed_at>=? and id<=? order by observed_at,id',(x['token_id'],x['receipt'],r['snapshot_frontier'])).fetchall()
 first=None;identities=[]
 for s in snaps:
  if not all(s[k] for k in ('observed_at','ingested_at','recorded_at')):continue
  if not dt(x['receipt'])<=dt(s['observed_at'])<=dt(s['ingested_at'])<=dt(s['recorded_at'])<=dt(r['cutoff']):continue
  raw=json.loads(s['raw_json']);p=raw.get('pair',{});chain,address=x['token_id'].split(':',1)
  ok=p.get('chainId')==chain and str(p.get('baseToken',{}).get('address','')).lower()==address.lower() and bool(p.get('pairAddress'))
  identities.append((s['id'],ok))
  if first is None:first={'id':s['id'],'delay':(dt(s['recorded_at'])-dt(x['receipt'])).total_seconds(),'pair':p.get('pairAddress'),'provider':raw.get('upstream_provider') or p.get('provider') or p.get('source'),'price':p.get('priceUsd'),'liquidity':p.get('liquidity'),'identity_ok':ok}
 audit.append({'token_id':x['token_id'],'surface':x['surface'],'first_snapshot':first,'bad_identity_ids':[i for i,ok in identities if not ok],'first_valid_identity_ok':None if not x['first_valid'] else dict(identities).get(x['first_valid']['id'])})
summary={}
for g in ('four_meme_rest','pons_v2'):
 xs=[x for x in audit if x['surface']==g];fs=[x['first_snapshot'] for x in xs if x['first_snapshot']]
 summary[g]={'n':len(xs),'first_snapshot_n':len(fs),'first_snapshot_delay_median':statistics.median(x['delay'] for x in fs) if fs else None,'within30':sum(x['delay']<=30 for x in fs),'within120':sum(x['delay']<=120 for x in fs),'bad_identity_tokens':sum(bool(x['bad_identity_ids']) for x in xs),'invalid_first_valid_identity':sum(x['first_valid_identity_ok'] is False for x in xs)}
print([dict(x) for x in c.execute('pragma table_info(chain_meme_pattern_evidence)')])
(out/'identity_audit.json').write_text(json.dumps({'summary':summary,'rows':audit},indent=2),encoding='utf-8')
print(json.dumps(summary))
