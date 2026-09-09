"""Apply reviewed convergence54 through existing NEW-entry control only."""
import argparse,json,sqlite3,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/research/convergence54'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 evidence=json.loads((OUT/'before.json').read_text())
 v='chain-meme-trader/funding-20260906-v002-final-1000'
 kept={}
 selected=set(['staged_probe_5u_only_control_v1','staged_probe_5u_conditional_15u_shadow_v1','serial_conditional_runner_v1','experiment_pullback_reclaim_candidate_v1','creator_early_holder_distribution_v1'])
 cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'));assert not cfg.get('live',{}).get('enabled')
 db=Path(cfg['database']);db=db if db.is_absolute() else ROOT/db
 c=sqlite3.connect(db.as_uri()+('?mode=rw' if args.apply else '?mode=ro'),uri=True,timeout=5);c.row_factory=sqlite3.Row
 c.execute('BEGIN IMMEDIATE' if args.apply else 'BEGIN')
 assert c.execute('select definition_version from chain_meme_trader_v6_activations where entry_execution_enabled=1 order by activated_at desc,rowid desc limit 1').fetchone()[0]==v
 policies={}
 for t in ('chain_meme_trader_registrations','chain_meme_trader_v6_registrations'):
  row=c.execute('select definition_json from '+t+' where definition_version=?',(v,)).fetchone()
  if row:
   for p in json.loads(row[0]).get('policies',[]):policies[p['arm_id']]=p
 for row in c.execute('select policy_json from chain_meme_trader_policy_additions where definition_version=?',(v,)):
  p=json.loads(row[0]);policies[p['arm_id']]=p
 groups={};hashes={}
 for arm,p in policies.items():
  if p.get('paired_entry_group'):groups.setdefault(p['paired_entry_group'],[]).append(arm)
  if p.get('behavior_contract_hash'):hashes.setdefault(p['behavior_contract_hash'],[]).append(arm)
 existing=set()
 for row in c.execute('select value_json from kv where key in (?,?)',('chain-meme-account-convergence/v1:'+v,'chain-meme-account-loss-retirement/v1:'+v)):
  existing.update(json.loads(row[0])['arms'])
 for g,members in groups.items():
  if selected.intersection(members):assert set(members)<=selected|existing,(g,members)
 verified={}
 for arm in selected:
  r=dict(c.execute("select count(*) terminals,count(distinct token_id) tokens,sum(realized_pnl_usd) realized from chain_meme_trader_positions where definition_version=? and arm_id=? and status in ('closed','written_off')",(v,arm)).fetchone())
  assert arm in policies and r['tokens']>=30 and r['realized']<=-50,(arm,r)
  for t in ('chain_meme_trader_accounting_contaminations','chain_meme_trader_position_voids'):
   assert c.execute('select count(*) from '+t+' where definition_version=? and arm_id=?',(v,arm)).fetchone()[0]==0
  verified[arm]=r
 tables=[r[0] for r in c.execute("select name from sqlite_master where type='table' and (name like 'chain_meme_trader%fund%' or name like 'chain_meme_trader%capital%')")]
 tables+=['chain_meme_trader_registrations','chain_meme_trader_v6_registrations','chain_meme_trader_v6_activations','chain_meme_trader_policy_additions']
 def digest():
  h=hashlib.sha256()
  for t in sorted(set(tables)):
   h.update(t.encode())
   for r in c.execute('select * from '+t+' order by rowid'):h.update(json.dumps(tuple(r)).encode())
  for arm in sorted(selected):
   for t in ('chain_meme_trader_positions','chain_meme_trader_trades'):
    for r in c.execute('select * from '+t+' where definition_version=? and arm_id=? order by rowid',(v,arm)):h.update(json.dumps(tuple(r)).encode())
  return h.hexdigest()
 before=digest();key='chain-meme-account-convergence/v1:'+v
 previous=json.loads(c.execute('select value_json from kv where key=?',(key,)).fetchone()[0]);updated=json.loads(json.dumps(previous));now=datetime.now(timezone.utc).isoformat()
 for arm in sorted(selected):updated['arms'].setdefault(arm,{'state':'PAUSED_NEW_ENTRY','representative':arm,'reason':'convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement'})
 if args.apply:
  updated['activated_at']=now;c.execute('update kv set value_json=?,updated_at=? where key=?',(json.dumps(updated),now,key))
 assert digest()==before
 c.commit()
 result={'applied':args.apply,'cutoff':now,'version':v,'paused':sorted(selected),'kept':kept,'ledger':verified,'paired_groups':{g:m for g,m in groups.items() if set(m)&(selected|set(kept))},'behavior_equivalent_groups':{h:m for h,m in hashes.items() if len(m)>1 and set(m)&selected},'immutable_digest':before,'immutable_tables':tables,'previous_control':previous,'new_control':updated}
 (OUT/('applied.json' if args.apply else 'preview.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps({'applied':args.apply,'paused':len(selected),'kept':kept,'cutoff':now,'digest':before}))
if __name__=='__main__':main()
