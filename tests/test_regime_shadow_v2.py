import importlib.util
import sqlite3
from pathlib import Path

spec = importlib.util.spec_from_file_location('regime62', Path(__file__).parents[1]/'scripts/report_regime_shadow_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_missing_activity_and_truncated_coverage_are_unknown():
    s = dict(token_id='bsc:x', observed_at='2026-09-09T00:29:00Z', ingested_at='2026-09-09T00:29:01Z', recorded_at='2026-09-09T00:29:02Z', price_usd=1, liquidity_usd=2000, pair='pool', created=m.stamp('2026-09-09T00:28:00Z')*1000, buys_5m=None, sells_5m=None, volume_5m_usd=None, upstream='gecko', provider='market')
    cut=m.stamp('2026-09-09T00:30:00Z')
    r=m.summarize([], [s], [], cut, {'market':cut-50})['current']['bsc']
    assert r['activity_missing']==1 and r['median_turnover'] is None
    assert r['coverage']=='UNKNOWN' and r['receipt_intensity_ratio'] is None
    s['recorded_at']='2026-09-09T00:31:00Z'
    assert not m.summarize([], [s], [], cut, {})['current']


def test_pregrad_unique_events_not_rows():
    e=dict(token_id='solana:x',observed_at='2026-09-09T00:29:00Z',recorded_at='2026-09-09T00:29:01Z',payload_json='{"stage":"MIGRATED"}')
    r=m.summarize([],[],[e,e],m.stamp('2026-09-09T00:30:00Z'),{'evidence':None})
    assert r['current']['solana']['pregrad_events']['MIGRATED']==1


def test_discovery_expansion_covers_baseline_without_duplicates_and_caps():
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE token_discovery_rounds(id INTEGER PRIMARY KEY,provider,surface);'
                     'CREATE TABLE token_discovery_exposures(id INTEGER PRIMARY KEY,round_id,recorded_at);'
                     "INSERT INTO token_discovery_rounds VALUES(1,'native-launch','test');")
    for i in range(1,9):
        db.execute('INSERT INTO token_discovery_exposures VALUES(?,1,?)',
                   (i, f'2026-09-09T00:{i:02}:00Z'))
    prior=m.stamp('2026-09-09T00:05:00Z')
    rows,span=m.discovery_tail(db,8,prior,initial=2,cap=8)
    assert span==4 and [r['id'] for r in rows]==[5,6,7,8]
    rows,span=m.discovery_tail(db,8,m.stamp('2026-09-08T00:00:00Z'),initial=2,cap=4)
    assert span==4 and min(m.stamp(r['recorded_at']) for r in rows)>m.stamp('2026-09-08T00:00:00Z')
