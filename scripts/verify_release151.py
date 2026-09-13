"""Read-only deployment receipt: immutable contracts, fresh progress and safe mode."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--label',required=True); a=p.parse_args()
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    db=Path(cfg['database']); db=db if db.is_absolute() else ROOT/db
    c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=10); c.row_factory=sqlite3.Row
    out={'at':datetime.now(timezone.utc).isoformat(),'database':str(db),
         'mode':cfg.get('mode'),'live_enabled':cfg.get('live',{}).get('enabled')}
    out['contracts']={r['definition_version']+':'+r['arm_id']:hashlib.sha256(r['policy_json'].encode()).hexdigest()
        for r in c.execute('SELECT definition_version,arm_id,policy_json FROM chain_meme_trader_policy_additions')}
    out['definitions']={r['definition_version']:hashlib.sha256(r['definition_json'].encode()).hexdigest()
        for r in c.execute('SELECT definition_version,definition_json FROM chain_meme_trader_v6_registrations')}
    out['positions']=[dict(r) for r in c.execute('SELECT status,COUNT(*) positions,MAX(opened_at) latest_open,MAX(closed_at) latest_close FROM chain_meme_trader_positions GROUP BY status')]
    for key in ('runtime-loaded-manifest','forward-review151','native-paper:last-held'):
        row=c.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()
        out[key]=json.loads(row[0]) if row else None
    c.close()
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(endpoint):
        with client.open('http://127.0.0.1:8790'+endpoint,timeout=20) as response:
            return json.load(response)
    out['health']=get('/health')
    errors=get('/api/errors'); out['errors']={'summary':errors.get('summary'), 'open_cases':[
        {k:r.get(k) for k in ('id','component','error_type','occurrence_count','last_seen_at')}
        for r in errors.get('cases',[]) if r.get('status') not in ('fixed','ignored')]}
    perf=get('/api/performance'); timing=perf.get('timing') or {}
    out['performance']={k:timing.get(k) for k in ('components','passive_queue','dex_http_capacity','shared_batch_coverage')}
    out['performance']['recorded_at']=perf.get('timing_recorded_at')
    source=ROOT/'src/memetrader'; manifest=out['runtime-loaded-manifest'] or {}
    out['loaded_hash_matches']={name:hashlib.sha256((source/name).read_bytes()).hexdigest()==value
        for name,value in manifest.get('source_sha256',{}).items()}
    folder=ROOT/'data/reports/deep_cycle_20260913/deployment';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(a.label+'.json');path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'receipt':str(path),'mode':out['mode'],'live':out['live_enabled'],
        'pid':manifest.get('pid'),'loaded_at':manifest.get('started_at'),
        'mismatch':[k for k,v in out['loaded_hash_matches'].items() if not v], 'errors':out['errors']['summary']},ensure_ascii=False))

if __name__=='__main__': main()
