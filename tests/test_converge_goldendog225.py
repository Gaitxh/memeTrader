import json

import pytest

from memetrader.store import Store
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.goldendog_recovery164 import policy as recovery_policy, PARENT_ARM, ARMS as RECOVERY_ARMS
from scripts import converge_goldendog225


def test_manual_goldendog_pause_preserves_history_and_is_idempotent(tmp_path):
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parents = {item["arm_id"]: item for item in
                   alpha149_policies(cohort_experiment_policies()[2])}
        for arm in converge_goldendog225.ARMS[:2]:
            store.append_chain_meme_trader_policy(parents[arm])
        for arm in RECOVERY_ARMS:
            store.append_chain_meme_trader_policy(recovery_policy(parents[PARENT_ARM], arm))
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        with pytest.raises(RuntimeError, match="threshold"):
            converge_goldendog225.run(apply=True, root=tmp_path)
        for arm in converge_goldendog225.ARMS:
            for index in range(30):
                store.db.execute(
                    "INSERT INTO chain_meme_trader_positions("
                    "definition_version,arm_id,shadow_cohort_id,token_id,"
                    "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                    "entry_signal_price_usd,amount_raw,stake_usd,highest_signal_price_usd,"
                    "status,opened_at,realized_pnl_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (version, arm, 10_000 + index, f"solana:token{index:03d}",
                     20_000 + index, 1, 1, 1.0, "1", 20.0, 1.0,
                     "written_off" if index < 10 else "closed",
                     "2026-09-17T00:00:00Z", -10.0),
                )
        store.db.commit()
        assert len(converge_goldendog225.run(root=tmp_path)["pending_arms"]) == 4
        applied = converge_goldendog225.run(apply=True, root=tmp_path)
        assert applied["status"] == "applied"
        assert converge_goldendog225.run(apply=True, root=tmp_path)["status"] == "already_applied"
        control = json.loads(store.db.execute(
            "SELECT value_json FROM kv WHERE key=?",
            ("chain-meme-account-convergence/v1:" + version,),
        ).fetchone()[0])
        assert all(control["arms"][arm]["state"] == "FAILED_FORWARD_EXPECTANCY"
                   for arm in converge_goldendog225.ARMS)
        assert store.db.execute(
            "SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions"
        ).fetchone()[:] == (120, -1200.0)
        assert store.db.execute(
            "SELECT COUNT(*) FROM kv WHERE key LIKE 'goldendog225:convergence:%'"
        ).fetchone()[0] == 1
    finally:
        store.close()


def test_manual_goldendog_pause_rejects_live(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": True}, "database": str(tmp_path / "missing.db"),
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Paper-only"):
        converge_goldendog225.run(apply=True, root=tmp_path)
