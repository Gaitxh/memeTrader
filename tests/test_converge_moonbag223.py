import json

import pytest

from memetrader.store import Store
from scripts import converge_moonbag223


def test_exact_source_pause_is_bounded_idempotent_and_preserves_ledger(tmp_path):
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        registered = {p["arm_id"] for p in store._chain_meme_trader_effective_definition(
            version, store._chain_meme_trader_registration(version)["definition_json"])["policies"]}
        assert {converge_moonbag223.ARM, converge_moonbag223.CONTROL} <= registered
        key = "chain-meme-account-convergence/v1:" + version
        with pytest.raises(RuntimeError, match="threshold"):
            converge_moonbag223.run(apply=True, root=tmp_path)
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        for index in range(100):
            for arm, pnl in ((converge_moonbag223.ARM, -1.0),
                             (converge_moonbag223.CONTROL, 1.0)):
                store.db.execute(
                    "INSERT INTO chain_meme_trader_positions("
                    "definition_version,arm_id,shadow_cohort_id,token_id,"
                    "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                    "entry_signal_price_usd,amount_raw,stake_usd,"
                    "highest_signal_price_usd,status,opened_at,realized_pnl_usd) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (version, arm, 10_000 + index, f"solana:token{index:03d}",
                     20_000 + index, 1, 1, 1.0, "1", 20.0, 1.0, "closed",
                     "2026-09-17T00:00:00Z", pnl),
                )
        store.db.commit()
        preview = converge_moonbag223.run(root=tmp_path)
        assert preview["paired"]["pairs"] == 100
        assert preview["paired"]["delta_usd"] == -200
        assert preview["status"] == "preview"
        assert store.db.execute("SELECT 1 FROM kv WHERE key=?", (key,)).fetchone() is None
        applied = converge_moonbag223.run(apply=True, root=tmp_path)
        assert applied["status"] == "applied"
        assert converge_moonbag223.run(apply=True, root=tmp_path)["status"] == "already_applied"
        record = json.loads(store.db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()[0])
        assert record["arms"][converge_moonbag223.ARM]["state"] == "FAILED_SAME_SOURCE_EXIT_VARIANT"
        assert store.db.execute("SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions "
                                "WHERE arm_id IN (?,?)", (converge_moonbag223.ARM,
                                converge_moonbag223.CONTROL)).fetchone()[:] == (200, 0.0)
        assert store.db.execute("SELECT COUNT(*) FROM kv WHERE key LIKE 'moonbag223:convergence:%'").fetchone()[0] == 1
    finally:
        store.close()
