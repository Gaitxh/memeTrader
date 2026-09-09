"""Explicit user126 restoration of existing profitable arms and mandatory pair."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'resource_age_rate_candidate_v1'
FAST = 'age_rate_horizon_fast_v1'
RUNNER = 'age_rate_horizon_runner_v1'
ARMS = {PARENT, FAST, RUNNER}
REPORT = 'docs/PROJECT_CONTEXT/POSITIVE_REACTIVATION_126.md'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    from memetrader.store import Store
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    assert not cfg.get('live',{}).get('enabled')
    db=Path(cfg['database']);db=db if db.is_absolute() else ROOT/db
    out=ROOT/'data/research/positive126';out.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(db.as_uri()+('?mode=rw' if args.apply else '?mode=ro'),uri=True,timeout=3)
    c.row_factory=sqlite3.Row;c.execute('BEGIN IMMEDIATE' if args.apply else 'BEGIN')
    v=c.execute('SELECT definition_version FROM chain_meme_trader_v6_activations WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1').fetchone()[0]
    raw=c.execute('SELECT definition_json FROM chain_meme_trader_v6_registrations WHERE definition_version=?',(v,)).fetchone()[0]
    def policies():return {p['arm_id']:p for p in Store.chain_meme_trader_effective_definition_from_connection(c,v,raw)['policies']}
    before_p=policies();group=before_p[FAST]['paired_entry_group']
    assert {a for a,p in before_p.items() if p.get('paired_entry_group')==group}=={FAST,RUNNER}
    assert before_p[FAST]['paired_entry_size']==before_p[RUNNER]['paired_entry_size']==2
    assert not before_p[PARENT].get('paired_entry_group')
    stats={}
    for a in sorted(ARMS):
        values=[r[0] for r in c.execute("SELECT realized_pnl_usd FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND status IN ('closed','written_off')",(v,a))]
        wins=sum(x for x in values if x>0);loss=-sum(x for x in values if x<0)
        stats[a]=dict(terminals=len(values),pnl=sum(values),profit_factor=wins/loss if loss else None,top3_removed=sum(values)-sum(sorted(values,reverse=True)[:3]))
        for t in ('chain_meme_trader_accounting_contaminations','chain_meme_trader_position_voids'):
            assert c.execute('SELECT count(*) FROM '+t+' WHERE definition_version=? AND arm_id=?',(v,a)).fetchone()[0]==0, 'explicit accounting defect needs review'
    assert stats[PARENT]['pnl']>0 and stats[FAST]['pnl']>0 and stats[FAST]['top3_removed']>0
    tables=['chain_meme_trader_registrations','chain_meme_trader_v6_registrations','chain_meme_trader_v6_activations','chain_meme_trader_policy_additions']
    tables += [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'chain_meme_trader%fund%' OR name LIKE 'chain_meme_trader%capital%')")]
    def digest():
        h=hashlib.sha256()
        for t in sorted(set(tables)):
            h.update(t.encode())
            for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid'):h.update(json.dumps(tuple(r)).encode())
        for t in ('chain_meme_trader_positions','chain_meme_trader_trades'):
            for a in sorted(ARMS):
                for r in c.execute('SELECT * FROM '+t+' WHERE definition_version=? AND arm_id=? ORDER BY rowid',(v,a)):h.update(json.dumps(tuple(r)).encode())
        return h.hexdigest()
    before_hash=digest();now=datetime.now(timezone.utc).isoformat();changes={}
    notes={PARENT:'MANIPULATION_CONTAMINATED / MIXED_HIGH_RECALL. Positive existing Paper comparator reactivated by user126; not normal-organic alpha. Common safety unchanged.',
           FAST:'ACTIVE learning; prior EXPERIMENT_COMPLETE_POSITIVE: 33 terminals +101.718U, top3 removed +25.543U. Distinct15m exit; compare equal fills against parent. Existing mandatory pair restored, no duplicate account.',
           RUNNER:'ACTIVE mandatory companion for existing age_rate_horizon_pair_v1 only; 33 terminals -12.576U. Not independently promoted or classified profitable. Required to permit original fast arm enrollment.'}
    keys=['chain-meme-account-convergence/v1:'+v,'chain-meme-account-loss-retirement/v1:'+v]
    for key in keys:
        row=c.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()
        if row is None:continue
        old=json.loads(row[0]);new=json.loads(row[0]);removed={a:new['arms'].pop(a) for a in sorted(ARMS) if a in new['arms']}
        if not removed:continue
        new['activated_at']=now
        new.setdefault('reactivations',[]).append(dict(message_id='C2C-20260910-PROFIT-FIRST-POSITIVE-REACTIVATION-126',at=now,previous=removed))
        new.setdefault('active_assessments',{}).update({a:dict(assessment_status='ACTIVE',assessment_note=notes[a],assessment_evidence=REPORT) for a in removed})
        changes[key]=dict(before=old,after=new)
        if args.apply:c.execute('UPDATE kv SET value_json=?,updated_at=? WHERE key=?',(json.dumps(new),now,key))
    after_p=policies()
    if args.apply:
        assert all(not after_p[a].get('entry_paused') for a in ARMS)
        assert all(after_p[a]==p for a,p in before_p.items() if a not in ARMS)
    assert digest()==before_hash
    result=dict(applied=args.apply,at=now,version=v,stats=stats,restored=sorted(ARMS),pair=group,changes=changes,
        immutable_history_funding_hash=before_hash,unrelated_effective_policies_unchanged=True,
        selected_effective={a:{k:after_p[a].get(k) for k in ('entry_paused','account_lifecycle','assessment_status','paired_entry_group','paired_entry_size')} for a in ARMS})
    c.commit();c.close()
    target=out/('applied.json' if args.apply else 'preview.json')
    if args.apply and not changes:target=out/'already_applied.json'
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:val for k,val in result.items() if k!='changes'}))


if __name__=='__main__':main()
