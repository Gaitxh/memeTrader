"""Frozen SQLite sequence falsifier for a 60s ordinary queue; no production I/O."""
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'data/research/flat68/baseline.json').read_text(encoding='utf-8-sig'))
T0 = datetime(2026, 9, 9, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat().replace('+00:00', 'Z')


def fixture():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE tokens(token_id TEXT PRIMARY KEY,chain TEXT,address TEXT);
    CREATE TABLE chain_meme_trader_v6_entry_evaluations(id INTEGER PRIMARY KEY,token_id TEXT,definition_version TEXT,feature_json TEXT);
    CREATE TABLE chain_meme_trader_flat_breakout_shadow(id INTEGER PRIMARY KEY,token_id TEXT,pair_address TEXT,observer_version TEXT,status TEXT);
    CREATE TABLE chain_meme_trader_market_marks(token_id TEXT PRIMARY KEY,last_attempt_at TEXT);
    CREATE TABLE chain_meme_trader_positions(token_id TEXT,status TEXT);
    ''')
    for n in range(360):
        insert(db, f't{n:03}', n + 1)
    return db


def insert(db, token, eid, pair='p', created=-30000):
    db.execute('INSERT OR IGNORE INTO tokens VALUES(?,?,?)', (token, 'bsc', token))
    db.execute('INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES(?,?,?,?)',
               (eid, token, BASE['params'][0], json.dumps({'pair_address': pair, 'pair_created_at': stamp(created)})))


def select(db, second, limit):
    # The exact previously measured production SQL, not a surrogate selector.
    return [dict(r) for r in db.execute(BASE['query'],
        (*BASE['params'][:2], stamp(second), stamp(second-5), stamp(second-60), limit))]


def transition(db, second):
    if second == 5:
        insert(db, 'new_ordinary', 1000)
    if second == 10:
        db.execute('INSERT INTO chain_meme_trader_flat_breakout_shadow VALUES(1,?,?,?,?)',
                   ('t000', 'p', BASE['params'][1], 'near_trigger'))
    if second == 15:
        db.execute("INSERT INTO chain_meme_trader_positions VALUES('t001','open')")
        insert(db, 't002', 1001, pair='successor')
    if second == 20:
        insert(db, 'new_young', 1002, created=20)
    if second == 25:
        db.execute("UPDATE chain_meme_trader_positions SET status='closed' WHERE token_id='t001'")


def run():
    baseline, candidate = fixture(), fixture()
    queue = set()
    result = {'mode': 'DETERMINISTIC_FROZEN_FIXTURE_NOT_NATURAL_REPLAY',
              'seconds': 65, 'queue_capacity': 360, 'events': [],
              'production_writes': 0, 'network_calls': 0}
    for sec in range(0, 66, 5):
        for db in (baseline, candidate):
            transition(db, sec)
        start = time.perf_counter()
        expected = select(baseline, sec, 30)
        baseline_ms = (time.perf_counter()-start)*1000
        # Generous oracle revalidation: current full ordering/due/held/pair state.
        # This gives the queue every advantage, NOT a proposed optimized query.
        eligible = select(candidate, sec, 10000)
        if sec % 60 == 0:
            queue = {r['token_id'] for r in eligible[:360]}
        near = {'near_trigger', 'breakout_confirmation_pending', 'shadow_breakout_candidate'}
        actual = [r for r in eligible if r['token_id'] in queue or r['observer_state'] in near][:30]
        for db, rows in ((baseline, expected), (candidate, actual)):
            db.executemany('INSERT OR REPLACE INTO chain_meme_trader_market_marks VALUES(?,?)',
                           [(r['token_id'], stamp(sec)) for r in rows])
        result['events'].append({'second': sec, 'baseline': expected, 'queue': actual,
                                 'equal': expected == actual, 'baseline_fixture_ms': baseline_ms})
    result['mismatched_ticks'] = [r['second'] for r in result['events'] if not r['equal']]
    for side in ('baseline', 'queue'):
        result[side+'_requested_tokens'] = sum(len(e[side]) for e in result['events'])
        result[side+'_first_new_ordinary'] = next(e['second'] for e in result['events']
            if any(r['token_id']=='new_ordinary' for r in e[side]))
    assert result['baseline_first_new_ordinary'] == 5
    assert result['queue_first_new_ordinary'] == 60
    assert all(any(r['token_id']=='t000' for r in e['queue']) for e in result['events'] if e['second']>=10)
    assert not any(r['token_id']=='t001' for e in result['events'] if e['second'] in (15,20) for r in e['queue'])
    result['disposition'] = 'REJECT_ORDINARY_QUEUE_SEMANTIC_MISMATCH'
    out = ROOT / 'data/research/flat87'
    out.mkdir(parents=True, exist_ok=True)
    (out/'simulation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='events'}, indent=2))


if __name__ == '__main__':
    run()
