import json
from datetime import datetime, timezone
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from research_sample_controls192 import frame, match_score, outcome


def row(*, observed='2026-01-01T00:01:00Z', recorded='2026-01-01T00:01:01Z',
        ingested='2026-01-01T00:01:01Z', pool='pool', liquidity=2000, sells=3):
    return dict(id=1, token_id='solana:token', observed_at=observed,
        ingested_at=ingested, recorded_at=recorded, provider='dexscreener',
        price_usd=1, liquidity_usd=liquidity, buys_5m=5, sells_5m=sells,
        raw_json=json.dumps({'pair': {'pairAddress': pool, 'pairCreatedAt': 1767225600000,
                                      'chainId': 'solana', 'baseToken': {'address': 'token'}}}))


def test_frame_rejects_future_ingestion_and_buy_only():
    cutoff = datetime(2026, 1, 1, 0, 1, 2, tzinfo=timezone.utc)
    assert frame(row(ingested='2026-01-01T00:02:00Z'), cutoff=cutoff) is None
    assert frame(row(sells=0), cutoff=cutoff) is None
    assert frame(row(liquidity=None), cutoff=cutoff) is None
    assert frame(row(), cutoff=cutoff)['pool'] == 'pool'
    assert frame(row(liquidity=100), cutoff=cutoff, entry=False)['liquidity_usd'] == 100


def test_control_matching_uses_only_same_time_source_age_liquidity():
    cutoff = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
    case = frame(row(observed='2026-01-01T00:04:00Z',
                     ingested='2026-01-01T00:04:01Z',
                     recorded='2026-01-01T00:04:01Z'), cutoff=cutoff)
    earlier = frame(row(), cutoff=cutoff)
    assert match_score(case, earlier) is not None
    assert match_score(case, {**earlier, 'provider': 'geckoterminal'}) is None
    assert match_score(case, {**earlier, 'liquidity_usd': 100}) is None
    assert match_score(case, {**earlier, 'recorded_at': '2026-01-01T00:05:01Z'}) is None


def test_known_same_pool_depth_loss_is_writeoff_not_old_price_profit():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE token_snapshots (id INTEGER, token_id TEXT, observed_at TEXT, '
                'ingested_at TEXT, recorded_at TEXT, provider TEXT, price_usd REAL, '
                'liquidity_usd REAL, buys_5m INTEGER, sells_5m INTEGER, raw_json TEXT)')
    start = row()
    low = row(observed='2026-01-01T00:03:00Z', ingested='2026-01-01T00:03:01Z',
              recorded='2026-01-01T00:03:01Z', liquidity=300)
    low['id'] = 2
    columns = list(start)
    con.executemany(f'INSERT INTO token_snapshots VALUES ({",".join("?" for _ in columns)})',
                    [[item[k] for k in columns] for item in (start, low)])
    anchor = frame(start, cutoff=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))
    result = outcome(con, anchor, cutoff_id=2,
                     cutoff=datetime(2026, 1, 1, 0, 35, tzinfo=timezone.utc))
    assert result['endpoint_covered']
    assert result['observed_writeoff_snapshot_id'] == 2
    assert result['indicative_two_sided_cost_mark_return'] == -1
