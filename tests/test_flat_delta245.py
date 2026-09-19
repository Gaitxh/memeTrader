"""Guard the incremental selector against full-period scans; no timing asserts."""
import ast
import inspect
import sqlite3
from textwrap import dedent
from memetrader.flat_selector import FlatSelector


def delta_sql():
    tree = ast.parse(dedent(inspect.getsource(FlatSelector._advance)))
    return next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, str) and 'e.id>?' in n.value)


def test_delta_matches_old_query_with_interleaved_versions_and_same_token():
    db = sqlite3.connect(':memory:')
    try:
        db.executescript('''
            CREATE TABLE tokens(token_id TEXT PRIMARY KEY,chain TEXT,address TEXT);
            CREATE TABLE chain_meme_trader_v6_entry_evaluations(
                id INTEGER PRIMARY KEY,definition_version TEXT,token_id TEXT,feature_json TEXT);
            CREATE INDEX period_pool ON chain_meme_trader_v6_entry_evaluations(
                definition_version,json_extract(feature_json,'$.pair_address'),token_id);
        ''')
        db.executemany('INSERT INTO tokens VALUES(?,?,?)',
                       [(f'solana:t{i}','solana',f't{i}') for i in range(11)])
        db.executemany('INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES(?,?,?,?)',
            [(i,'current' if i % 4 else 'other',f'solana:t{i%11}',
              '{"pair_address":"p'+str(i%13)+'","pair_created_at":12}' if i%7 else '{}')
             for i in range(1,10001)])
        new = delta_sql()
        assert 'NOT INDEXED' in new
        old = new.replace(' e NOT INDEXED JOIN', ' e JOIN')
        for params in [('current',9950,10000),('other',9950,10000),
                       ('absent',9950,10000),('current',10000,10000)]:
            assert db.execute(new,params).fetchall() == db.execute(old,params).fetchall()
        # Count VM instructions instead of flaky wall-clock performance.
        steps = []
        for query in (old,new):
            count = [0]
            def step():
                count[0] += 1
                return 0
            db.set_progress_handler(step,1)
            db.execute(query,('current',9950,10000)).fetchall()
            db.set_progress_handler(None,0)
            steps.append(count[0])
        assert steps[1] < steps[0] / 5, steps
    finally:
        db.close()


def test_delta_retains_version_and_both_frontiers_no_new_limit_or_sort_loss():
    sql = delta_sql()
    assert 'e.definition_version=?' in sql
    assert 'e.id>? AND e.id<=?' in sql
    assert 'ORDER BY e.id' in sql
    assert 'LIMIT' not in sql.upper()
    assert "json_extract(e.feature_json,'$.pair_address')" in sql
