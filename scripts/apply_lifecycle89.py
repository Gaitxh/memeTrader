"""Apply reviewed display assessments only; never modify enrollment controls."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/research/lifecycle89'
FIELDS={'assessment_status','assessment_note','assessment_evidence'}
NOTES={
 'FAILED':'Current frozen costed sample is negative; not proof of universal negative alpha.',
 'EXPERIMENT_COMPLETE_POSITIVE':'Profitable completed experiment; not FAILED. Formal paired enrollment remains paused.',
 'DUPLICATE_SUPERSEDED':'Duplicate contract or verified common-fill substitute; absolute profit does not require duplicate capital.',
 'DATA_BLOCKED':'Required input contract unavailable; not an economic failure conclusion.',
 'INSUFFICIENT':'Insufficient independent evidence or paired dependency; no threshold relaxation.'}


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 frozen=json.loads((OUT/'frozen.json').read_text());result=json.loads((OUT/'result.json').read_text())
 assessments={r['arm_id']:r for r in result['arms'] if r['paused']}
 c=sqlite3.connect((ROOT/'data/memetrader_forward_20260830_r6.sqlite3').as_uri()+('?mode=rw' if args.apply else '?mode=ro'),uri=True,timeout=5)
 c.execute('BEGIN IMMEDIATE' if args.apply else 'BEGIN')
 tables=json.loads((ROOT/'data/research/admission84/before_immutable.json').read_text())['tables']
 def digest():
  return hashlib.sha256(json.dumps({t:[list(r) for r in c.execute('select * from '+t+' order by rowid')] for t in tables},sort_keys=True,default=str).encode()).hexdigest()
 before=digest();now=datetime.now(timezone.utc).isoformat();changes=[]
 for old in frozen['controls']:
  current=c.execute('select value_json from kv where key=?',(old['key'],)).fetchone()[0]
  control=json.loads(current)
  assert control==json.loads(old['value_json']), 'Concurrent control update: re-review needed'
  updated=json.loads(current)
  for arm,state in updated['arms'].items():
   if arm not in assessments:continue
   status=assessments[arm]['lifecycle'];note=NOTES[status]
   if arm=='age_rate_horizon_fast_v1':
    note='Profitable 15m defensive benchmark: 33 same fills +101.718U versus parent +323.320U; fewer downside losses but sacrifices +221.602U net. Pair complete; retain research benchmark, no duplicate Paper capital.'
   state.update(assessment_status=status,assessment_note=note,assessment_evidence='docs/PROJECT_CONTEXT/PAUSED_POSITIVE_AUDIT_RESULT_89.md')
  strip=lambda x:{**x,'arms':{a:{k:v for k,v in s.items() if k not in FIELDS} for a,s in x['arms'].items()}}
  assert strip(control)==strip(updated), 'Non-display mutation'
  if args.apply:c.execute('update kv set value_json=?,updated_at=? where key=?',(json.dumps(updated),now,old['key']))
  changes.append(old['key'])
 assert digest()==before
 c.commit();c.close()
 data=dict(applied=args.apply,at=now,arms=len(assessments),keys=changes,immutable=before,entry_control_unchanged=True)
 (OUT/('applied.json' if args.apply else 'preview.json')).write_text(json.dumps(data,indent=2))
 print(json.dumps(data))


if __name__=='__main__':main()
