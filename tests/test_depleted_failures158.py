import importlib.util
import sqlite3
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply_depleted_failures158.py"
SPEC = importlib.util.spec_from_file_location("depleted_failures158", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def policy(arm, **extra):
    return {"arm_id": arm, **extra}


def test_selection_requires_settled_and_realized_loss_depletion():
    metrics = {
        "loss": {"settled_net_cash": -990, "realized_pnl": -990, "terminal_positions": 1, "realized_trade_count": 1},
        # Cash tied in an open position, but settled realized equity is healthy.
        "locked": {"settled_net_cash": -990, "realized_pnl": -10, "terminal_positions": 1, "realized_trade_count": 1},
        "profit": {"settled_net_cash": 5, "realized_pnl": 5, "terminal_positions": 1, "realized_trade_count": 1},
        "nan": {"settled_net_cash": None, "realized_pnl": -990, "terminal_positions": 1, "realized_trade_count": 1},
        "missing_pnl": {"settled_net_cash": -990, "realized_pnl": None, "terminal_positions": 1, "realized_trade_count": 1, "bad_realized_pnl_count": 1},
        "no_terminal": {"settled_net_cash": -990, "realized_pnl": -990, "terminal_positions": 0, "realized_trade_count": 0},
    }
    selected, preview = module.select_depleted_failures(
        [policy(name) for name in metrics], metrics, 1000,
    )
    assert [item["arm_id"] for item in selected] == ["loss"]
    dispositions = {item["arm_id"]: item["disposition"] for item in preview}
    assert dispositions["locked"] == "NOT_DEPLETED_BY_SETTLED_REALIZED_LOSS"
    assert dispositions["missing_pnl"] == "NOT_DEPLETED_BY_SETTLED_REALIZED_LOSS"


def test_partial_sell_profit_on_open_inventory_prevents_false_failure():
    selected, _ = module.select_depleted_failures([policy("partial")], {
        "partial": {"settled_net_cash": -990, "realized_pnl": 25, "terminal_positions": 1,
                    "realized_trade_count": 2},
    }, 1000)
    assert selected == []


def test_selection_preserves_existing_pause_and_control_merge_preserves_unrelated():
    metrics = {"already": {"settled_net_cash": -990, "realized_pnl": -990, "terminal_positions": 1, "realized_trade_count": 1},
               "new": {"settled_net_cash": -990, "realized_pnl": -990, "terminal_positions": 1, "realized_trade_count": 1}}
    selected, preview = module.select_depleted_failures(
        [policy("already", entry_paused=True, account_lifecycle="PAUSED_NEW_ENTRY"), policy("new")], metrics, 1000,
    )
    assert [item["arm_id"] for item in selected] == ["new"]
    assert preview[0]["disposition"] == "PRESERVE_EXISTING_LIFECYCLE"
    old = {"keep": "metadata", "arms": {"unrelated": {"state": "PAUSED_NEW_ENTRY"}}}
    merged = module.merged_control(old, selected, "2026-09-14T00:00:00Z")
    assert merged["keep"] == "metadata"
    assert merged["arms"]["unrelated"] == old["arms"]["unrelated"]
    assert merged["arms"]["new"]["state"] == "PAUSED_NEW_ENTRY"
    assert merged["arms"]["new"]["assessment_status"] == "FAILED"
    assert old == {"keep": "metadata", "arms": {"unrelated": {"state": "PAUSED_NEW_ENTRY"}}}


def test_sql_aggregate_counts_partial_exit_and_authorizer_blocks_history_update():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE chain_meme_trader_trades(definition_version,arm_id,side,net_cash_flow_usd,realized_pnl_usd)")
    db.execute("CREATE TABLE chain_meme_trader_positions(definition_version,arm_id,status)")
    db.execute("CREATE TABLE kv(key PRIMARY KEY,value_json,updated_at)")
    # A terminal loss exists, but a partial SELL from still-open inventory made
    # realized PnL recover above the depletion floor.
    db.executemany("INSERT INTO chain_meme_trader_trades VALUES('v',?,?,?,?)", [
        ("partial", "BUY", -1000.0, None), ("partial", "SELL", 10.0, -990.0),
        ("partial", "SELL", 30.0, 30.0),
        ("missing", "BUY", -1000.0, None), ("missing", "SELL", 10.0, None),
    ])
    db.executemany("INSERT INTO chain_meme_trader_positions VALUES('v',?,?)", [
        ("partial", "closed"), ("partial", "open"), ("missing", "closed"),
    ])
    metrics = module.aggregate_metrics(db, "v")
    assert metrics["partial"]["realized_pnl"] == -960.0
    assert metrics["partial"]["bad_realized_pnl_count"] == 0
    assert metrics["missing"]["bad_realized_pnl_count"] == 1
    selected, _ = module.select_depleted_failures(
        [policy("partial"), policy("missing")], metrics, 1000,
    )
    assert selected == []
    db.set_authorizer(module.kv_only_authorizer)
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE chain_meme_trader_trades SET net_cash_flow_usd=0")
    db.execute("INSERT INTO kv VALUES('receipt','{}','now')")
