"""Frozen60 holdout migrations, descriptive continuity only."""
import sqlite3,json,collections
from datetime import datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'data/research/postgrad69';O.mkdir(exist_ok=True)
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
f=json.loads((R/'data/research/pregrad60/result.json').read_text());front=json.loads((R/'data/research/pregrad60/frozen_features.json').read_text())['frontier'];cut=dt(f['cutoff']);xs=[x for x in f['rows'] if x['split']=='holdout' and x['migration'] and not x['preexisting_migration']];assert len(xs)==52
c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;out=[]
for x in xs:
 token=x['token_id'];receipt=x['migration']['recorded_at'];ss=[];reasons=collections.Counter();all_rows=0
 for row in c.execute('select * from token_snapshots where token_id=? and observed_at>? and id<=? order by observed_at,id',(token,receipt,front)):
  all_rows+=1;s=dict(row);raw=json.loads(s.pop('raw_json'));pair=raw.get('pair',{})
  try:causal=dt(receipt)<dt(s['observed_at'])<=dt(s['ingested_at'])<=dt(s['recorded_at'])<=cut
  except (ValueError,TypeError):causal=False
  if not causal:reasons['invalid_clocks_or_after_cutoff']+=1;continue
  if pair.get('dexId')!='pumpswap' or pair.get('chainId')!='solana' or pair.get('baseToken',{}).get('address')!=token.split(':')[1] or not pair.get('pairAddress'):reasons['not_exact_pumpswap_identity']+=1;continue
  s.update(pair=pair['pairAddress'],source=raw.get('upstream_provider') or s['provider']);ss.append(s)
  if not s['price_usd'] or s['price_usd']<=0:reasons['price_missing_nonpositive']+=1
  elif s['liquidity_usd'] is None:reasons['liquidity_unknown']+=1
  elif s['liquidity_usd']<1000:reasons['below_floor']+=1
 valid=lambda s:s['price_usd'] is not None and s['price_usd']>0 and s['liquidity_usd'] is not None and s['liquidity_usd']>=1000
 anchor=next((s for s in ss if valid(s)),None);entry=next((s for s in ss if anchor and s['pair']==anchor['pair'] and valid(s) and 0<(dt(s['observed_at'])-dt(anchor['recorded_at'])).total_seconds()<=120),None)
 assert bool(anchor)==bool(x['postgrad'].get('anchor')) and bool(entry)==bool(x['postgrad'].get('entry'))
 attempts=[dict(r) for r in c.execute('select requested_at,completed_at,status,reason_code from token_discovery_quote_attempts where token_id=? and requested_at>=? and requested_at<=?',(token,receipt,f['cutoff']))]
 hand=c.execute('select value_json,updated_at from kv where key=?',('pregrad_migration_handoff:'+token,)).fetchone();handoff=dict(hand) if hand and dt(hand['updated_at'])<=cut else None
 windows={}
 for minute in (5,15,30,60):
  path=[s for s in ss if entry and s['pair']==entry['pair'] and minute*60<=(dt(s['observed_at'])-dt(entry['recorded_at'])).total_seconds()<=minute*60+120]
  windows[str(minute)]={'mature':bool(entry and (cut-dt(entry['recorded_at'])).total_seconds()>=minute*60+120),'any_frame':len(path),'valid_frames':sum(valid(s) for s in path),'first_id':path[0]['id'] if path else None}
 reason='covered_strict_next' if entry else 'no_later_valid_same_pool_within120s' if anchor else 'no_qualifying_pumpswap_price_liquidity' if ss else 'no_recorded_pumpswap_pool_identity'
 out.append({'token_id':token,'migration_id':x['migration']['id'],'migration_receipt':receipt,'snapshot_count':all_rows,'pumpswap_rows':len(ss),'first_known_market_pool':ss[0] if ss else None,'anchor':anchor,'entry':entry,'reason':reason,'frame_rejections':dict(reasons),'quote_attempts':attempts,'handoff_kv_asof':handoff,'windows_from_entry':windows})
summary={'n':len(out),'known_pumpswap_pool':sum(bool(x['first_known_market_pool']) for x in out),'anchor':sum(bool(x['anchor']) for x in out),'entry':sum(bool(x['entry']) for x in out),'handoff_kv_asof':sum(bool(x['handoff_kv_asof']) for x in out),'tokens_with_logged_quote_attempts':sum(bool(x['quote_attempts']) for x in out),'reasons':dict(collections.Counter(x['reason'] for x in out)),'windows':{str(m):{'mature':sum(x['windows_from_entry'][str(m)]['mature'] for x in out),'any':sum(bool(x['windows_from_entry'][str(m)]['any_frame']) for x in out),'valid':sum(bool(x['windows_from_entry'][str(m)]['valid_frames']) for x in out)} for m in (5,15,30,60)}}
(O/'result.json').write_text(json.dumps({'cutoff':f['cutoff'],'frontier':front,'summary':summary,'rows':out},indent=2),encoding='utf-8');print(json.dumps(summary))
