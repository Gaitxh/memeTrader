from scripts.deep_cycle_report import quantile, paper_family, generation_delta

def test_quantile_empty_and_zero_time():
    assert quantile([], .5) is None
    assert quantile([0, 1, 9], .5) == 1

def test_quantile_does_not_fake_missing_or_winrate():
    assert quantile([None, 0.0], .99) == 0.0

def test_native_name_and_generation_reset_are_not_misclassified():
    assert paper_family('pump_native_absorption_fast_v1') == 'native_paper'
    assert generation_delta({'client_generation': 2, 'request_cancellations': 1}, {'client_generation': 1, 'request_cancellations': 9})['unknown']

def test_same_generation_counter_delta():
    assert generation_delta({'client_generation': 2, 'request_cancellations': 5}, {'client_generation': 2, 'request_cancellations': 3})['request_cancellations'] == 2


def test_fixed_horizon_observation_excludes_wrong_pool_stale_and_future():
    import sqlite3
    from scripts.review_metrics151 import visible_mark, date
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE chain_meme_trader_market_mark_history(id INTEGER, token_id TEXT, '
        'pair_address TEXT,status TEXT,price_usd REAL,observed_at TEXT,recorded_at TEXT)')
    for i,pool,observed in [(1,'other','00:05:00'), (2,'pool','00:04:00'),
                            (3,'pool','00:05:02'), (4,'pool','00:05:00')]:
        c.execute('INSERT INTO chain_meme_trader_market_mark_history VALUES(?,?,?,\'VISIBLE\',1,?,?)',
            (i,'solana:T',pool,'2026-09-13T'+observed+'Z','2026-09-13T00:05:01Z'))
    mark=visible_mark(c,'solana:T','pool',date('2026-09-13T00:05:00Z'),date('2026-09-13T00:06:00Z'))
    assert mark['id']==4
    assert visible_mark(c,'solana:T','missing',date('2026-09-13T00:05:00Z'),date('2026-09-13T00:06:00Z')) is None
    c.close()


def test_maturing_fanout_does_not_hide_mature_exit_samples(tmp_path, monkeypatch):
    from datetime import timedelta
    from test_age_rate_revision_store import fixture
    from memetrader.models import iso
    from scripts.review_metrics151 import washout, date
    store, pos, mark, policies = fixture(tmp_path, monkeypatch)
    arm = policies[0]['arm_id']
    row = pos(arm)
    closed = date(row['opened_at']) + timedelta(minutes=10)
    # The report is read-only; test fixtures explicitly create terminal states.
    store.db.execute("UPDATE chain_meme_trader_positions SET status='closed',closed_at=?", (iso(closed+timedelta(minutes=30)),))
    store.db.execute("UPDATE chain_meme_trader_positions SET closed_at=? WHERE arm_id=?", (iso(closed),arm))
    result = washout(store.db,iso(closed+timedelta(minutes=31)))
    assert result['positions'] == 1
    assert result['samples'][0]['arm_id'] == arm
    assert result['maturing_positions'] == 3
    assert not result['counts']['15'].get('maturing')
    store.close()
