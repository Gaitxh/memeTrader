import json

import pytest

from memetrader.store import Store
from scripts import converge_loss_cohort228 as convergence


def test_manual_loss_pause_is_idempotent_and_keeps_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(convergence, "ARMS", ("alpha149_nonbsc_flow_v1",))
    db_path = tmp_path / "paper.sqlite3"
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": False}, "database": str(db_path),
    }), encoding="utf-8")
    store = Store(db_path, initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        from memetrader.alpha149 import policies
        from memetrader.cohort_experiments import cohort_experiment_policies
        source = next(item for item in policies(cohort_experiment_policies()[2])
                      if item["arm_id"] == convergence.ARMS[0])
        store.append_chain_meme_trader_policy(source)
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        with pytest.raises(RuntimeError, match="threshold"):
            convergence.run(apply=True, root=tmp_path)
        for index in range(50):
            store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,"
                "source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,"
                "entry_signal_price_usd,amount_raw,stake_usd,highest_signal_price_usd,"
                "status,opened_at,realized_pnl_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (version, convergence.ARMS[0], 10_000 + index, f"solana:token{index:03d}",
                 20_000 + index, 1, 1, 1.0, "1", 20.0, 1.0,
                 "written_off" if index < 5 else "closed",
                 "2026-09-17T00:00:00Z", -5.0),
            )
        store.db.commit()
        assert convergence.run(root=tmp_path)["pending_arms"] == list(convergence.ARMS)
        applied = convergence.run(apply=True, root=tmp_path)
        assert applied["status"] == "applied"
        assert convergence.run(apply=True, root=tmp_path)["status"] == "already_applied"
        assert store.db.execute(
            "SELECT COUNT(*),SUM(realized_pnl_usd) FROM chain_meme_trader_positions"
        ).fetchone()[:] == (50, -250.0)
        record = json.loads(store.db.execute(
            "SELECT value_json FROM kv WHERE key=?",
            ("chain-meme-account-convergence/v1:" + version,),
        ).fetchone()[0])
        assert record["arms"][convergence.ARMS[0]]["terminal_at_pause"]["tokens"] == 50
        assert store.db.execute(
            "SELECT COUNT(*) FROM kv WHERE key LIKE 'loss228:convergence:%'"
        ).fetchone()[0] == 1
    finally:
        store.close()


def test_manual_loss_pause_refuses_live(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "mode": "paper", "live": {"enabled": True}, "database": str(tmp_path / "x.db"),
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Paper-only"):
        convergence.run(apply=True, root=tmp_path)
