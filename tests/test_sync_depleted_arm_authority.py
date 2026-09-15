import importlib.util
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sync_depleted_arm_authority",
    ROOT / "scripts" / "sync_depleted_arm_authority.py",
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE chain_meme_trader_account_snapshots("
        "id INTEGER PRIMARY KEY,definition_version TEXT,arm_id TEXT,cash_usd REAL,"
        "open_position_count INTEGER,closed_position_count INTEGER,"
        "realized_pnl_usd REAL,recorded_at TEXT)"
    )
    return connection


def test_latest_snapshot_must_be_below_cash_floor_and_have_zero_open_positions():
    connection = _connection()
    connection.executemany(
        "INSERT INTO chain_meme_trader_account_snapshots VALUES(?,?,?,?,?,?,?,?)",
        [
            (1, "v", "recovered", 10.0, 0, 1, -990.0, "t1"),
            (2, "v", "recovered", 25.0, 0, 2, -975.0, "t2"),
            (3, "v", "still-open", 5.0, 1, 2, -995.0, "t3"),
            (4, "v", "depleted", 19.5, 0, 3, -980.5, "t4"),
            (5, "other", "wrong-period", 1.0, 0, 5, -999.0, "t5"),
        ],
    )
    rows = sync.latest_depleted_rows(connection, "v", 20.0)
    assert [row["arm_id"] for row in rows] == ["depleted"]
    assert rows[0]["id"] == 4


def test_merge_is_latched_idempotent_and_excludes_other_lifecycle_controls():
    authority = {
        "count": 1,
        "arms": [{"arm_id": "already-failed", "cash_usd": 1.0}],
    }
    candidates = [
        {"id": 2, "arm_id": "already-failed", "cash_usd": 2.0,
         "closed_position_count": 2, "realized_pnl_usd": -998.0, "recorded_at": "t2"},
        {"id": 3, "arm_id": "dominated", "cash_usd": 3.0,
         "closed_position_count": 3, "realized_pnl_usd": -997.0, "recorded_at": "t3"},
        {"id": 4, "arm_id": "newly-depleted", "cash_usd": 4.0,
         "closed_position_count": 4, "realized_pnl_usd": -996.0, "recorded_at": "t4"},
    ]
    updated, added = sync.merge_candidates(authority, candidates, {"dominated"})
    assert [item["arm_id"] for item in added] == ["newly-depleted"]
    assert updated["count"] == 2
    assert set(added[0]) == {"arm_id", "cash_usd", "observed_at"}
    again, second = sync.merge_candidates(updated, candidates, {"dominated"})
    assert second == []
    assert again == updated
