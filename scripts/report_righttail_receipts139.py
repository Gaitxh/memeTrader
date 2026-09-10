"""Bounded read-only receipt completion of saved47/78 matching, never new matching."""
import json, sqlite3, pathlib, time
from datetime import datetime, timedelta
from collections import Counter

ROOT=pathlib.Path(__file__).resolve().parents[1]
SAVE=ROOT/'data/research/full_delivery139'
VERSION='chain-meme-trader/funding-20260906-v002-final-1000'
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def canonical(s):return s if s.startswith('solana:') else s.lower()
def main():
    frozen=json.loads((ROOT/'data/research/user_righttail_cases_20260908/matched_corrected47.json').read_text())
    cutoff=frozen['cutoff'];deadline=time.monotonic()+8
    c=sqlite3.connect((ROOT/'data/memetrader_forward_20260830_r6.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=1)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
    c.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
    sql="SELECT id,source_snapshot_id,evaluated_at,status,reason,feature_json FROM chain_meme_trader_v6_entry_evaluations INDEXED BY chain_meme_trader_v6_entry_eval_pool_idx WHERE definition_version=? AND token_id=? AND COALESCE(json_extract(feature_json,'$.pair_address'),'')!='' AND source_snapshot_id>=? AND source_snapshot_id<=? ORDER BY id LIMIT 2049"
    plan=[r[3] for r in c.execute('EXPLAIN QUERY PLAN '+sql,(VERSION,'fixture',0,1))]
    assert any('chain_meme_trader_v6_entry_eval_pool_idx' in p for p in plan)
    rows=[];seen=set();reads=0
    for case in frozen['results']:
      for role,record in [('case',case)]+[('control',v) for v in case.get('controls',[])]:
        anchor=record.get('anchor');token=canonical(anchor['token_id'] if anchor else case['token_id'])
        key=(role,token,anchor['id'] if anchor else None)
        if role=='control' and key in seen:continue
        seen.add(key);path=record.get('path') or {};entry=path.get('strict_next')
        out=dict(role=role,token_id=token,case_token_id=case['token_id'],anchor=anchor,
          strict_next=entry,activity_presence=(anchor or {}).get('activity_presence'),
          horizon_tolerance_seconds=120,endpoints={},decision_scope=VERSION)
        if not anchor:
            out['stage']='NO_VALID_ANCHOR';rows.append(out);continue
        try:
            raw=list(c.execute(sql,(VERSION,token,anchor['id'],cutoff['id'])))
            evaluations=[]
            for r in raw[:2048]:
                f=json.loads(r['feature_json']);pool=f.get('pair_address') or ''
                if canonical(token.split(':')[0]+':'+pool)!=canonical(token.split(':')[0]+':'+anchor['pool']):continue
                if not dt(anchor['recorded_at'])<=dt(r['evaluated_at'])<=dt(cutoff['recorded_at']):continue
                evaluations.append(dict(id=r['id'],snapshot_id=r['source_snapshot_id'],at=r['evaluated_at'],
                    status=r['status'],reason=r['reason'],ready=f.get('ready_arm_ids',[]),
                    outcomes=f.get('outcomes',{}),paired_rejections=f.get('paired_rejections',{})))
            out['evaluation_truncated']=len(raw)>2048
            out['first_evaluation']=evaluations[0] if evaluations else None
            out['first_ready']=next((x for x in evaluations if x['ready']),None)
            out['gate_counts']=dict(Counter(reason for e in evaluations for reason in e['outcomes'].values() if isinstance(reason,str)))
            cohorts=list(c.execute('SELECT id,pair_address,decided_at FROM chain_meme_trader_v6_cohorts WHERE definition_version=? AND token_id=? AND decided_at>=? AND decided_at<=? ORDER BY decided_at LIMIT 65',
                (VERSION,token,anchor['recorded_at'],cutoff['recorded_at'])))
            decisions=[]
            for co in cohorts[:64]:
                if canonical(token.split(':')[0]+':'+co['pair_address'])!=canonical(token.split(':')[0]+':'+anchor['pool']):continue
                decisions.extend(dict(r) for r in c.execute('SELECT id,shadow_cohort_id,arm_id,status,reason,decided_at FROM chain_meme_trader_entry_decisions WHERE definition_version=? AND shadow_cohort_id=? ORDER BY id LIMIT 256',(VERSION,co['id'])))
            out['decisions']=decisions;out['cohort_truncated']=len(cohorts)>64
            out['actual_system_saved']=record.get('actual_system') if role=='case' else None
            out['stage']='ACTUAL_DECISION' if decisions else 'READY_NO_DECISION' if out['first_ready'] else 'EVALUATED_NO_READY' if evaluations else 'UNKNOWN_BOUNDED_EVALUATION' if out['evaluation_truncated'] else 'NO_EXACT_POOL_EVALUATION_IN_FROZEN_PERIOD'
            frames=[]
            if entry:
                previous=dt(entry['recorded_at'])
                for id in path.get('future_ids',[]):
                    assert id<=cutoff['id']
                    r=c.execute("SELECT id,token_id,observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,COALESCE(json_extract(raw_json,'$.pair.pairAddress'),json_extract(raw_json,'$.pairAddress')) AS pool FROM token_snapshots WHERE id=?",(id,)).fetchone();reads+=1
                    if not r or canonical(r['token_id'])!=token or not r['ingested_at'] or not r['price_usd'] or r['price_usd']<=0 or r['liquidity_usd'] is None or r['liquidity_usd']<1000:continue
                    if canonical(token.split(':')[0]+':'+str(r['pool']))!=canonical(token.split(':')[0]+':'+anchor['pool']):continue
                    if not previous<dt(r['observed_at'])<=dt(r['ingested_at'])<=dt(r['recorded_at'])<=dt(cutoff['recorded_at']):continue
                    previous=dt(r['recorded_at']);frames.append(dict(r))
            for minutes in (5,15,30,60,360):
                target=dt(entry['recorded_at'])+timedelta(minutes=minutes) if entry else None
                hit=next((r for r in frames if target<=dt(r['observed_at'])<=target+timedelta(seconds=120)),None) if target else None
                out['endpoints'][str(minutes)] = dict(status='OBSERVED_SAMPLED',receipt=hit,
                    raw_return=hit['price_usd']/entry['price_usd']-1,cost_proxy_return=hit['price_usd']*.96/(entry['price_usd']*1.04)-1,
                    warning='sampled mark, not a fill; gaps do not prove no prior stop/floor') if hit else dict(status='UNKNOWN',reason='NO_STRICT_NEXT' if not entry else 'NO_SAVED_QUALIFIED_HORIZON_FRAME')
        except sqlite3.OperationalError as e:
            out.update(stage='UNKNOWN_QUERY_BUDGET',query_error=str(e))
        rows.append(out)
    today=json.loads((ROOT/'data/research/today23_78/analysis.json').read_text())
    summary=dict(rows=len(rows),cases=sum(r['role']=='case' for r in rows),control_anchor_rows=sum(r['role']=='control' for r in rows),
        unique_case_normalized_controls=len({r['token_id'] for r in rows if r['role']=='control'}),
        stages=dict(Counter(r['stage'] for r in rows if r['role']=='case')),
        endpoint_coverage={str(m):sum(r.get('endpoints',{}).get(str(m),{}).get('status')=='OBSERVED_SAMPLED' for r in rows) for m in (5,15,30,60,360)},snapshot_pk_reads=reads)
    SAVE.mkdir(exist_ok=True)
    (SAVE/'righttail_receipts.json').write_text(json.dumps(dict(cutoff=cutoff,summary=summary,query_plan=plan,
        meaning='saved outcome-blind assignments, no rematch/no production snapshot range scan/no retrospective strategy signals',
        today23_existing_summary=today['summary'],rows=rows),ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False));c.close()
if __name__=='__main__':main()
