"""Apply the authorized 59 duplicate retirements and 6 entry pauses; no ledger edits."""
import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from memetrader.store import Store
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    path = Path(config['database'])
    if not path.is_absolute(): path = ROOT/path
    court = ROOT/'data/research/alpha_diagnosis_20260907/court/arm_court.csv'
    rows = list(csv.DictReader(court.open(encoding='utf-8')))
    retired = [r for r in rows if r['recommendation']=='RETIRE_DUPLICATE']
    paused = [r for r in rows if r['recommendation']=='FREEZE_NEW_ENTRY']
    assert len(retired)==59 and len(paused)==6
    arms = {r['arm_id']: {'state':'RETIRED_DUPLICATE' if r in retired else 'PAUSED_NEW_ENTRY',
                         'representative':r['representative'], 'reason':r['reason']} for r in retired+paused}
    assert len(arms)==65 and all(r['representative'] not in arms for r in retired)
    db = sqlite3.connect(path.as_uri()+('?mode=rw' if args.apply else '?mode=ro'),uri=True,timeout=5)
    db.row_factory = sqlite3.Row
    if args.apply: db.execute('BEGIN IMMEDIATE')
    else: db.execute('PRAGMA query_only=ON')
    active = db.execute('SELECT definition_version FROM chain_meme_trader_v6_activations WHERE entry_execution_enabled=1 ORDER BY activated_at DESC LIMIT 1').fetchone()[0]
    assert active == Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    raw = db.execute('SELECT definition_json FROM chain_meme_trader_registrations WHERE definition_version=?',(active,)).fetchone()[0]
    definition = Store.chain_meme_trader_effective_definition_from_connection(db,active,raw)
    known = {p['arm_id'] for p in definition['policies']}
    assert len(known)==230 and set(arms)<=known
    key = f'chain-meme-account-convergence/v1:{active}'
    existing = db.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()
    placeholders=','.join('?' for _ in arms)
    positions = [dict(r) for r in db.execute(f'SELECT arm_id,COUNT(*) AS open_positions FROM chain_meme_trader_positions WHERE definition_version=? AND status=\'open\' AND arm_id IN ({placeholders}) GROUP BY arm_id',(active,*arms))]
    payload = dict(activated_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                   definition_version=active, arms=arms, court_sha256=hashlib.sha256(court.read_bytes()).hexdigest(),
                   trade_frontier=db.execute('SELECT MAX(id) FROM chain_meme_trader_trades').fetchone()[0],
                   snapshot_frontier=db.execute('SELECT MAX(id) FROM token_snapshots').fetchone()[0])
    if existing:
        payload=json.loads(existing[0]);assert payload['arms']==arms
    elif args.apply:
        db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)',(key,json.dumps(payload,ensure_ascii=False,sort_keys=True),payload['activated_at']))
    db.commit();db.close()
    result=dict(applied=args.apply,already_present=bool(existing),retired=59,paused=6,visible_accounts=171,
                entries_enabled_accounts=165,open_positions_preserved=positions,activation=payload)
    output=ROOT/'data/research/account_convergence_20260907';output.mkdir(exist_ok=True)
    (output/('activation.json' if args.apply else 'preview.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='activation'},ensure_ascii=True))


if __name__=='__main__': main()
