"""Apply verified research-only exclusions from a frozen duplicate audit. No refunds."""
import argparse,hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--audit',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    audit=json.loads(Path(a.audit).read_text(encoding='utf8'))
    db=sqlite3.connect(Path(a.database).resolve().as_uri()+('?mode=rw' if a.apply else '?mode=ro'),uri=True,timeout=10);db.row_factory=sqlite3.Row
    now=datetime.now(timezone.utc).isoformat();by_version={};frozen=[]
    for group in audit['duplicate_groups']:
        version,arm,key=group['definition_version'],group['arm_id'],group['decision_key']
        rows=db.execute('SELECT p.*,c.feature_json FROM chain_meme_trader_positions p JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id WHERE p.definition_version=? AND p.arm_id=? AND p.token_id=? ORDER BY p.opened_at,p.shadow_cohort_id',
                        (version,arm,group['members'][0]['token_id'])).fetchall()
        matched=[r for r in rows if json.loads(r['feature_json']).get('event_keys',{}).get(arm)==key]
        expected={m['shadow_cohort_id'] for m in group['members']}
        if {r['shadow_cohort_id'] for r in matched}!=expected:raise ValueError('Audit membership changed; re-audit required')
        for r in matched:
            frozen.append(dict(r))
            frozen.extend(dict(t) for t in db.execute('SELECT * FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=? ORDER BY id',(version,arm,r['shadow_cohort_id'])))
        for r in matched[1:]:
            by_version.setdefault(version,{})[arm+':'+str(r['shadow_cohort_id'])]=dict(
                reason='duplicate-opportunity-contamination',arm_id=arm,shadow_cohort_id=r['shadow_cohort_id'],
                source_entry_fill_id=r['source_entry_fill_id'],token_id=r['token_id'],decision_key=key,
                original_cohort_id=matched[0]['shadow_cohort_id'],recorded_realized_pnl_usd=r['realized_pnl_usd'],
                research_metrics_eligible=False,financial_adjustment_usd=0,recorded_at=now)
    before=hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()
    if a.apply:
        with db:
            for version,annotations in by_version.items():
                key='duplicate-opportunity-contamination/v1:'+version
                existing=db.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()
                value=json.loads(existing[0]) if existing else {'positions':{},'affects':'research_eligibility_only','financial_adjustment_usd':0}
                for identity,annotation in annotations.items():value['positions'].setdefault(identity,annotation)
                db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',(key,json.dumps(value),now))
    print(json.dumps({'applied':a.apply,'annotation_count':sum(map(len,by_version.values())),'frozen_position_trade_digest':before,'annotations':by_version}))
    db.close()

if __name__=='__main__':main()
