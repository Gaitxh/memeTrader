import json

import pytest

from memetrader.store import Store
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.trajectory144 import policies as trajectory_policies
from scripts import converge_fast226


def test_paired_fast_pause_does_not_change_runner_or_trades(tmp_path):
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        policies = {item["arm_id"]: item for item in
                    trajectory_policies(cohort_experiment_policies()[2])}
        for arm in (converge_fast226.FAST, converge_fast226.RUNNER):
            store.append_chain_meme_trader_policy(policies[arm])
        with pytest.raises(RuntimeError, match="threshold"):
            converge_fast226.run(apply=True, root=tmp_path)
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        for arm in (converge_fast226.FAST, converge_fast226.RUNNER):
            for index in range(100):
                store.db.execute(
                    "INSERT INTO chain_meme_trader_positions("
                    "definition_version,arm_id,shadow_cohort_id,token_id,"
                    "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                    "entry_signal_price_usd,amount_raw,stake_usd,highest_signal_price_usd,"
                    "status,opened_at,realized_pnl_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (version, arm, 10_000 + index, f"solana:token{index:03d}",
                     20_000 + index, 1, 1, 1.0, "1", 20.0, 1.0, "closed",
                     "2026-09-17T00:00:00Z", -10.0 if arm == converge_fast226.FAST else 1.0),
                )
        store.db.commit()
        preview = converge_fast226.run(root=tmp_path)
        assert preview["evidence"]["tokens"] == 100
        assert preview["evidence"]["runner_minus_fast_usd"] == 1100.0
        applied = converge_fast226.run(apply=True, root=tmp_path)
        assert applied["status"] == "applied"
        assert converge_fast226.run(apply=True, root=tmp_path)["status"] == "already_applied"
        controls = json.loads(store.db.execute(
            "SELECT value_json FROM kv WHERE key=?",
            ("chain-meme-account-convergence/v1:" + version,),
        ).fetchone()[0])["arms"]
        assert controls[converge_fast226.FAST]["state"] == "DOMINATED_IN_PAIRED_TEST"
        assert converge_fast226.RUNNER not in controls
        assert store.db.execute(
            "SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions"
        ).fetchone()[:] == (200, -900.0)
    finally:
        store.close()


def test_paired_fast_pause_rejects_live(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": True}, "database": str(tmp_path / "missing.db"),
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Paper-only"):
        converge_fast226.run(apply=True, root=tmp_path)
