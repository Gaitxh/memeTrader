"""Bounded case-only frozen research; no production writes or strategy replay fitting."""
import json,sqlite3,time,collections,math
from pathlib import Path
from datetime import datetime
from research_first_hit75 import walk
R=Path(__file__).resolve().parents[1];O=R/'data/research/today23_78';O.mkdir(exist_ok=True)
CUT='2026-09-09T06:49:35Z';V='chain-meme-trader/funding-20260906-v002-final-1000'
ADDRESSES='''0xb429a196034128e652b116b1525b856294dd98b3
0x3df3644bcf4ce0d993e18c86c3080e53bfea06f1
0x9cd3a3eed3e4a2c832590dd59aa8c3f657bd8888
0x56aaa501fa9eb6670d6175d686957434c3d21e18
GLRyB95LzCyyY8TVfwZVDyrVcZuSJPJJoaPTnyWs89mv
Fhxcx7cHmhDkfwziHyCwN8vQRvEFRK3zezokaE8gL5q7
0xb97d9e5ad6244d27588fe0a624a8c78e512934ee
0x80baa4b3bfac6f4978700df824b1b3d98e889136
0xcf3d41f9671dc2e86ee4c0271b79ae6fdce36c05
0x87359b7d78b03bd81b567bf425263b453c73eeee
0x7d1a8dbb40b7b5518ef69b93a6faeba91eea7777
0x113d68c8cca4fe5ba25f49c00784079d168e7777
0xc26e887d361a67226fa2903375ccd312e2bb7777
0x43330ef84f7f226c32562463dfd7442461907777
0x320474b5f11b030407b7e7bd5f5a989c730a0000
4oWhtcmBBsMG1bLZCLKusmq4t9fxdVVfbyJLevsYg5Ct
0xba4e0404a1169a03429e1d06c1e8ecd6b61d7777
0x0d11e308e40c15e1181aed4f4bbfc4744e9deeed
0xb244edd7674d0969fe63ceaa3d4a2ed69f397db0
6CsmCtDAhRcbp3G4KiinKC2JjLJ9BpR7isqcgZefqLym
9RdsqgqtfkFkteNcWSu27wDGKcn6A9hTXoVet6TfS5H4
0x50ec3b65691a911be049cd0d2d6e639cd1cfdb9b
0xd5eeb6104796eca13899fbd69400630905247777'''.split()
def ts(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def norm(chain,a):return a if chain=='solana' else str(a or '').lower()
def valid(s):
 try:
  p=json.loads(s['raw_json']).get('pair',{});chain,addr=s['token_id'].split(':',1)
  if p.get('chainId')!=chain or norm(chain,p.get('baseToken',{}).get('address'))!=addr:return None
  if not ts(s['observed_at'])<=ts(s['ingested_at'])<=ts(s['recorded_at'])<=ts(CUT):return None
  if not p.get('pairAddress') or not s['price_usd'] or s['price_usd']<=0:return None
  age=ts(s['observed_at'])-p['pairCreatedAt']/1000 if p.get('pairCreatedAt') else None
  if age is not None and age<0:return None
  raw=json.loads(s['raw_json']);txn=p.get('txns',{}).get('m5',{})
  return dict(id=s['id'],token=s['token_id'],pool=norm(chain,p['pairAddress']),obs=ts(s['observed_at']),rec=ts(s['recorded_at']),ing=ts(s['ingested_at']),price=s['price_usd'],liq=s['liquidity_usd'],source=raw.get('upstream_provider',s['provider']),age=age,buys=txn.get('buys'),sells=txn.get('sells'),volume=p.get('volume',{}).get('m5'),quote=p.get('quoteToken',{}).get('address'),dex=p.get('dexId'))
 except (ValueError,TypeError,KeyError):return None

def main():
 c=sqlite3.connect((R/'data/memetrader_forward_20260830_r6.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 blockers=[]
 def query(sql,args=()):
  start=time.monotonic();c.set_progress_handler(lambda:int(time.monotonic()-start>4),1000)
  try:return [dict(x) for x in c.execute(sql,args).fetchall()]
  except sqlite3.OperationalError as e:blockers.append(dict(sql=sql,error=str(e)));return []
 keys=[chain+':'+a for a in ADDRESSES for chain in ('bsc','robinhood','solana','ethereum','base')]
 ids=query('select token_id,chain,address,symbol,source,first_seen_at from tokens where token_id in ('+','.join('?'*len(keys))+')',keys)
 from memetrader.store import Store
 raw=query('select definition_json from chain_meme_trader_v6_registrations where definition_version=?',(V,))[0]['definition_json']
 policies=Store.chain_meme_trader_effective_definition_from_connection(c,V,raw)['policies'];active=[p['arm_id'] for p in policies if not p.get('entry_paused')]
 out=[]
 for ident in ids:
  token=ident['token_id'];sn=query('select * from token_snapshots where token_id=? and recorded_at<=? order by observed_at limit 20001',(token,CUT));ss=sorted(filter(None,map(valid,sn)),key=lambda s:(s['rec'],s['id']))
  pools=collections.defaultdict(list)
  for s in ss:pools[s['pool']].append(s)
  episodes=[]
  for pool,frames in pools.items():
   a=next((s for s in frames if s['liq'] is not None and s['liq']>=1000),None)
   if not a:continue
   e=next((s for s in frames if s['obs']>a['rec'] and s['liq'] is not None and s['liq']>=1000),None)
   ep=dict(anchor=a,entry=e,entry_delay=e['obs']-a['rec'] if e else None,first_hit=walk(e,[s for s in frames if s['liq'] is not None and s['liq']>=1000]) if e else None,outcomes={})
   if e:
    prev=e;future=[];floor=[]
    for s in frames:
     if s['obs']<=prev['rec']:continue
     if s['obs']>e['rec']+21720:break
     if s['liq'] is None:continue
     if s['liq']<1000:floor.append(s)
     else:future.append(s)
     prev=s
    ep['floor_first']=floor[0] if floor else None
    for h in (900,3600,21600):
     fs=[s for s in future if s['obs']<=e['rec']+h];end=next((s for s in future if h<=s['obs']-e['rec']<=h+120),None)
     nets=[s['price']*.96/(e['price']*1.04)-1 for s in fs]
     ep['outcomes'][str(h)]=dict(n=len(fs),mfe=max(nets) if nets else None,minimum=min(nets) if nets else None,endpoint_id=end['id'] if end else None,endpoint_net=end['price']*.96/(e['price']*1.04)-1 if end else None)
   episodes.append(ep)
  episodes.sort(key=lambda x:x['anchor']['rec'])
  discovery=query('select e.id,e.observed_at,e.recorded_at,e.first_local_discovery,r.provider,r.surface from token_discovery_exposures e join token_discovery_rounds r on r.id=e.round_id where e.token_id=? and e.recorded_at<=? order by e.observed_at limit 1001',(token,CUT))
  facts=query('select * from token_launch_facts where token_id=? and recorded_at<=? order by id limit 1000',(token,CUT))
  evidence=query('select id,kind,observed_at,recorded_at,payload_json from chain_meme_pattern_evidence where definition_version=? and token_id=? and recorded_at<=? order by id limit 2001',(V,token,CUT))
  ev=query("select id,source_snapshot_id,evaluated_at,status,reason,feature_json from chain_meme_trader_v6_entry_evaluations where definition_version=? and token_id=? and reason='pattern_observation' and evaluated_at<=? order by id limit 2001",(V,token,CUT))
  # Mutable terminal columns after cutoff must never be labelled as historical terminal truth.
  pos=query('select arm_id,shadow_cohort_id,source_entry_fill_id,source_buy_trade_id,entry_snapshot_id,opened_at,closed_at,status,close_reason,realized_pnl_usd,stake_usd from chain_meme_trader_positions where definition_version=? and token_id=? and opened_at<=? order by opened_at',(V,token,CUT))
  for p in pos:
   p['cutoff_censored']=not p['closed_at'] or ts(p['closed_at'])>ts(CUT)
   if p['cutoff_censored']:p['realized_pnl_usd']=None;p['close_reason']='CENSORED_AT_CUTOFF';p['status']='CENSORED'
   row=query("select json_extract(raw_json,'$.pair.pairAddress') pool from token_snapshots where id=?",(p['entry_snapshot_id'],));p['entry_pool']=row[0]['pool'] if row else None
  decisions=query('select id,arm_id,shadow_cohort_id,decided_at,status,reason from chain_meme_trader_entry_decisions where definition_version=? and token_id=? and decided_at<=? order by id limit 2001',(V,token,CUT))
  out.append(dict(identity=ident,snapshot_rows=len(sn),snapshot_truncated=len(sn)>20000,episodes=episodes,frames=ss,discovery=discovery,snapshot_audit=dict(raw=len(sn),identity_clock_price_valid=len(ss),floor_valid=sum(s['liq'] is not None and s['liq']>=1000 for s in ss),floor_below=sum(s['liq'] is not None and s['liq']<1000 for s in ss)),launch_facts=facts,evidence=evidence,pattern_evaluations=ev,decisions=decisions,positions=pos,active_captures=sorted({p['arm_id'] for p in pos if p['arm_id'] in active})))
  print(token,len(sn),len(episodes),len(pos),flush=True)
 result=dict(cutoff=CUT,addresses=ADDRESSES,identities=len(ids),missing=[a for a in ADDRESSES if not any(i['address']==a for i in ids)],active_arms_at_read=active,active_state_not_backdated=True,blockers=blockers,cases=out)
 (O/'casebook.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('DONE',len(out),'blockers',len(blockers))
if __name__=='__main__':main()
