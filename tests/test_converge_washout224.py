import json

import pytest

from memetrader.store import Store
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.washout_reclaim212 import PARENT
from scripts import converge_washout224


def test_losing_washout_pause_is_bounded_and_preserves_positions(tmp_path):
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        base = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                    if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(base)
        assert store.register_chain_meme_washout_reclaim212() >= 1
        assert store.register_chain_meme_washout_confirm222() == 1
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        key = "chain-meme-account-convergence/v1:" + version
        with pytest.raises(RuntimeError, match="threshold"):
            converge_washout224.run(apply=True, root=tmp_path)
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        for index in range(40):
            store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,"
                "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                "entry_signal_price_usd,amount_raw,stake_usd,"
                "highest_signal_price_usd,status,opened_at,realized_pnl_usd) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (version, converge_washout224.ARM, 10_000 + index,
                 f"solana:token{index:03d}", 20_000 + index, 1, 1, 1.0,
                 "1", 20.0, 1.0, "written_off" if index < 8 else "closed",
                 "2026-09-17T00:00:00Z", -10.0),
            )
        store.db.commit()
        preview = converge_washout224.run(root=tmp_path)
        assert preview["evidence"] == {
            "terminals": 40, "tokens": 40, "net_usd": -400.0, "writeoffs": 8,
        }
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        applied = converge_washout224.run(apply=True, root=tmp_path)
        assert applied["status"] == "applied"
        assert converge_washout224.run(apply=True, root=tmp_path)["status"] == "already_applied"
        record = json.loads(store.db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()[0])
        assert record["arms"][converge_washout224.ARM]["state"] == "FAILED_FORWARD_EXPECTANCY"
        assert store.db.execute("SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions "
                                "WHERE arm_id=?", (converge_washout224.ARM,)).fetchone()[:] == (40, -400.0)
        assert store.db.execute("SELECT COUNT(*) FROM kv WHERE key LIKE 'washout224:convergence:%'").fetchone()[0] == 1
    finally:
        store.close()
