import sqlite3
from datetime import timedelta

from memetrader.chain_web import ChainWebData
from memetrader.models import iso, utcnow


def test_discovery_activity_counts_first_tokens_not_duplicate_polls_or_strategy_projections(monkeypatch):
    now = utcnow().replace(second=30, microsecond=0)
    monkeypatch.setattr("memetrader.chain_web.utcnow", lambda: now)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE token_discovery_exposures(id INTEGER PRIMARY KEY,chain TEXT,token_id TEXT,
          first_local_discovery INTEGER,recorded_at TEXT,observed_at TEXT);
        CREATE TABLE chain_meme_trader_v6_entry_evaluations(id INTEGER PRIMARY KEY,token_id TEXT,
          source_snapshot_id INTEGER,feature_json TEXT,decided_at TEXT);
    """)
    at = iso(now - timedelta(minutes=2))
    db.executemany("INSERT INTO token_discovery_exposures VALUES(?,?,?,?,?,?)", [
        (1,"solana","solana:A",1,at,at),(2,"solana","solana:A",0,at,at),
        (3,"bsc","bsc:B",1,at,at),(4,"robinhood","robinhood:C",1,at,at),
        (5,"solana","solana:A",1,at,at),
    ])
    db.executemany("INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES(?,?,?,?,?)", [
        (1,"solana:A",5,'{"policy_entry_family":"broad_launch"}',at),
        (2,"bsc:B",6,'{"policy_entry_family":"reawakening","reason":"cash_unavailable"}',at),
        (3,"bsc:B",6,'{"policy_entry_family":"reawakening"}',at),
    ])
    web = ChainWebData.__new__(ChainWebData)
    web._discovery_series_cache = None
    result = web._discovery_activity_series(db)
    assert len(result["points"]) == 60
    assert sum(p["solana"]["new"] for p in result["points"]) == 1
    assert sum(p["bsc"]["new"] for p in result["points"]) == 1
    assert sum(p["robinhood"]["new"] for p in result["points"]) == 1
    assert sum(p["bsc"]["reactivated"] for p in result["points"]) == 1
    assert sum(p["solana"]["reactivated"] for p in result["points"]) == 0
    queries = []
    db.set_trace_callback(queries.append)
    assert web._discovery_activity_series(db) is result
    assert queries == []
