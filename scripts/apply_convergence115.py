"""Narrow reversible NEW-entry pause after independently reproduced theme sensitivity."""
import json,sqlite3,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
ARMS={'resource_age_rate_candidate_v1','dynamic_principal_recovery_runner_v2',
      'age_rate_half_runner_recovery_v3','narrative_hold_recovered_runner_v2'}
def main():
    from memetrader.store import Store
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    assert not cfg.get('live',{}).get('enabled')
    path=Path(cfg['database']);path=path if path.is_absolute() else ROOT/path
    c=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=3);c.row_factory=sqlite3.Row
    c.execute('BEGIN IMMEDIATE')
    v=c.execute('SELECT definition_version FROM chain_meme_trader_v6_activations WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1').fetchone()[0]
    raw=c.execute('SELECT definition_json FROM chain_meme_trader_v6_registrations WHERE definition_version=?',(v,)).fetchone()[0]
    ps={p['arm_id']:p for p in Store.chain_meme_trader_effective_definition_from_connection(c,v,raw)['policies']}
    assert ARMS<=ps.keys() and all(not ps[a].get('paired_entry_group') for a in ARMS)
    # Cooling reads already-recorded prior core loss receipts; it does not require
    # concurrent parent enrollment or copy the parent's unsigned age-rate signal.
    assert all(p.get('entry_paused') or a in ARMS or a=='failed_impulse_cooling_v1'
        or not (set(p.get('source_arm_ids',[]))&ARMS) for a,p in ps.items())
    rows=c.execute("SELECT p.realized_pnl_usd,s.raw_json FROM chain_meme_trader_positions p JOIN token_snapshots s ON s.id=p.entry_snapshot_id WHERE p.definition_version=? AND p.arm_id='resource_age_rate_candidate_v1' AND p.token_id LIKE 'bsc:%' AND p.status IN ('closed','written_off')",(v,)).fetchall()
    themed=[];other=[]
    for r in rows:
        b=json.loads(r['raw_json']).get('pair',{}).get('baseToken',{})
        (themed if b.get('symbol')=='BNC4' or b.get('name')=='4Stock' else other).append(r['realized_pnl_usd'])
    assert len(themed)==11 and sum(themed)>700 and len(other)>=45 and sum(other)<-30
    tables=['chain_meme_trader_registrations','chain_meme_trader_v6_registrations','chain_meme_trader_v6_activations','chain_meme_trader_policy_additions']
    tables += [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'chain_meme_trader%fund%' OR name LIKE 'chain_meme_trader%capital%')")]
    def digest():
        h=hashlib.sha256()
        for t in sorted(set(tables)):
            for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid'):h.update(json.dumps(tuple(r)).encode())
        for a in sorted(ARMS):
            for t in ('chain_meme_trader_positions','chain_meme_trader_trades'):
                for r in c.execute('SELECT * FROM '+t+' WHERE definition_version=? AND arm_id=? ORDER BY rowid',(v,a)):h.update(json.dumps(tuple(r)).encode())
        return h.hexdigest()
    before=digest();key='chain-meme-account-convergence/v1:'+v
    old=json.loads(c.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()[0])
    new=json.loads(json.dumps(old));now=datetime.now(timezone.utc).isoformat()
    for a in sorted(ARMS):
        new['arms'][a]=dict(state='PAUSED_NEW_ENTRY',assessment_status='INSUFFICIENT',
            assessment_note='MANIPULATION_CONTAMINATED / RESEARCH_REQUIRED：父策略收益高度集中于疑似操纵主题；不是已证正常币Alpha，也不等于每枚币已证诈骗。暂缓新增仓位，既有退出继续。',
            assessment_evidence='docs/PROJECT_CONTEXT/AGE_RATE_MANIPULATION_115.md',
            reason='115: independently reproduced theme sensitivity; signed-flow/breadth verification unavailable; reversible research pause, preserve exits/history')
    new['activated_at']=now
    c.execute('UPDATE kv SET value_json=?,updated_at=? WHERE key=?',(json.dumps(new,ensure_ascii=False),now,key))
    assert digest()==before
    assert all(p['entry_paused'] for p in Store.chain_meme_trader_effective_definition_from_connection(c,v,raw)['policies'] if p['arm_id'] in ARMS)
    counts={a:c.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?',(v,a)).fetchone()[0] for a in ARMS}
    c.commit();c.close()
    result=dict(cutoff=now,version=v,paused=sorted(ARMS),theme_n=len(themed),theme_pnl=sum(themed),other_n=len(other),other_pnl=sum(other),immutable_digest=before,position_counts=counts,previous_control=old)
    (ROOT/'data/research/manipulation115/applied.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='previous_control'}))
if __name__=='__main__':main()
