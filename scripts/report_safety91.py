"""Bounded safety evidence readback, account fanout deduplicated by cohort."""
import json,sqlite3,collections,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'data/research/system91'
c=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
front=json.loads((O/'frontier.json').read_text());cut=datetime.datetime.now(datetime.timezone.utc).isoformat()
rows=[]
for r in c.execute("select id,definition_version,payload_json from chain_meme_pattern_evidence where id>=225000 and kind='preentry_obvious_scam_v1' order by id"):
 p=json.loads(r['payload_json']);rows.append((r['id'],(r['definition_version'],p['cohort_id']),p))
trades=[dict(r) for r in c.execute("select id,definition_version,shadow_cohort_id,token_id,created_at from chain_meme_trader_trades where id>=500000 and side='BUY' and created_at>='2026-09-09T08:53:24Z'")]
def report(post):
 rs=[r for r in rows if not post or r[0]>front['evidence_id']]
 ts=[t for t in trades if not post or t['id']>front['trade_id']]
 statuses=collections.defaultdict(set);authorized=set();zero_facts=set()
 for _,key,p in rs:
  st=p['safety_status'];a=p.get('assessment') or {};status=a.get('status')
  if st.startswith('WAIT') or st.startswith('EXPIRED'):statuses['WAIT'].add(key)
  if status in ('PASS','UNKNOWN','REJECT','HAZARD'):statuses[status].add(key)
  if st.startswith('BUY_AUTHORIZED'):
   authorized.add(key)
   if not a.get('usable_facts'):zero_facts.add(key)
 buys={(t['definition_version'],t['shadow_cohort_id']) for t in ts}
 return dict(buy_cohorts=len(buys),buy_tokens=len({t['token_id'] for t in ts}),audited=len(buys&authorized),unaudited=len(buys-authorized),status_cohorts={s:len(statuses[s]) for s in ('PASS','UNKNOWN','REJECT','WAIT','HAZARD')},zero_recorded_usable_facts_authorizations=len(zero_facts),unaudited_keys=list(buys-authorized))
result={'cutoff':cut,'frontier':front,'all_since_safety90':report(False),'post91_frontier':report(True),'semantics':'Statuses overlap over lifecycle, not mutually exclusive. Old authorization rows pre91 lack usable_facts field; not proof all were empty.'}
(O/'safety_denominator.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
