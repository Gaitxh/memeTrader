import json

import pytest

from memetrader.store import Store
from scripts import converge_migration219


def test_migration_convergence_is_bounded_and_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    monkeypatch.setattr(converge_migration219, "ROOT", tmp_path)
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_trajectory_regime187()
        assert store.register_chain_meme_migration_first209() == 1
        assert store.register_chain_meme_migration_confirm214() == 1
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        key = "chain-meme-account-convergence/v1:" + version
        with pytest.raises(RuntimeError, match="209 failure threshold"):
            converge_migration219.run(apply=True)
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        for index in range(30):
            for offset, arm in enumerate(converge_migration219.ARMS):
                store.db.execute(
                    "INSERT INTO chain_meme_trader_positions("
                    "definition_version,arm_id,shadow_cohort_id,token_id,"
                    "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                    "entry_signal_price_usd,amount_raw,stake_usd,"
                    "highest_signal_price_usd,status,opened_at,realized_pnl_usd) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (version, arm, 10_000 + index + offset * 100,
                     f"solana:token{index:02d}", 20_000 + index + offset * 100,
                     1, 1, 1.0, "1", 20.0, 1.0, "closed",
                     "2026-09-17T00:00:00Z", -5.0),
                )
        store.db.commit()
        before = store.db.execute(
            "SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions "
            "WHERE arm_id IN (?,?)", converge_migration219.ARMS,
        ).fetchone()
        preview = converge_migration219.run()
        assert preview["status"] == "preview"
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        applied = converge_migration219.run(apply=True)
        assert applied["status"] == "applied"
        assert applied["terminal"][converge_migration219.ARMS[0]]["tokens"] == 30
        assert converge_migration219.run(apply=True)["status"] == "already_applied"
        control = json.loads(store.db.execute(
            "SELECT value_json FROM kv WHERE key=?", (key,)
        ).fetchone()[0])
        assert all(control["arms"][arm]["state"] == "FAILED_FORWARD_EXPECTANCY"
                   for arm in converge_migration219.ARMS)
        after = store.db.execute(
            "SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions "
            "WHERE arm_id IN (?,?)", converge_migration219.ARMS,
        ).fetchone()
        assert tuple(before) == tuple(after) == (60, -300.0)
        assert store.db.execute(
            "SELECT COUNT(*) FROM kv WHERE key LIKE 'migration219:convergence:%'"
        ).fetchone()[0] == 1
    finally:
        store.close()
