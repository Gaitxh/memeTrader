import ast
import inspect
import textwrap

from memetrader.store import Store


def test_pending_buy_reservations_are_cohort_scoped_and_indexed(tmp_path):
    store = Store(tmp_path / "entry-reservation.sqlite3", initial_cash_usd=1000)
    version, other_version = "entry-v1", "entry-v0"
    intent_rows = [
        ("ready-alpha", version, "entry:broad", 101, "BUY", "ready"),
        ("retry-alpha", version, "entry:broad", 102, "BUY", "retry"),
        ("filled", version, "entry:broad", 103, "BUY", "filled"),
        ("sell", version, "entry:broad", 104, "SELL", "ready"),
        ("other-version", other_version, "entry:broad", 101, "BUY", "ready"),
    ]
    store.db.executemany(
        "INSERT INTO chain_meme_trader_order_intents("
        "intent_key,definition_version,execution_mode,arm_id,shadow_cohort_id,"
        "token_id,side,input_mint,output_mint,input_amount_raw,slippage_bps,"
        "status,reason,created_at,expires_at) VALUES(?,?,'paper',?,?,"
        "'solana:token',?,?,?,'1',400,?,'test','2026-09-08T00:00:00+00:00',"
        "'2026-09-08T00:01:00+00:00')",
        [(key, ver, arm, cohort, side, "USDC", "token", status)
         for key, ver, arm, cohort, side, status in intent_rows],
    )
    decision_rows = [
        (version, "alpha", 101, "admitted"),
        (version, "beta", 101, "admitted"),
        (version, "rejected", 101, "rejected"),
        (version, "alpha", 102, "admitted"),
        (version, "beta", 102, "rejected"),
        (version, "ignored-filled", 103, "admitted"),
        (other_version, "wrong-version", 101, "admitted"),
    ]
    store.db.executemany(
        "INSERT INTO chain_meme_trader_entry_decisions("
        "definition_version,arm_id,shadow_cohort_id,token_id,baseline_quote_result_id,"
        "decided_at,status,reason) VALUES(?,?,?,'solana:token',1,"
        "'2026-09-08T00:00:00+00:00',?,'test')",
        decision_rows,
    )
    # Exercise the SQL actually used by enrollment, not a copied query.
    tree = ast.parse(textwrap.dedent(inspect.getsource(Store.enroll_chain_meme_trader_v6)))
    query = next(node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and node.value.startswith("SELECT d.arm_id,COUNT(*) AS pending_count FROM "))
    counts = {row["arm_id"]: row["pending_count"]
              for row in store.db.execute(query, (version,))}
    assert counts == {"alpha": 2, "beta": 1}

    plan = " ".join(
        str(row["detail"])
        for row in store.db.execute("EXPLAIN QUERY PLAN " + query, (version,))
    )
    assert "chain_meme_trader_entry_decisions_cohort_idx" in plan
    assert "shadow_cohort_id=?" in plan
    assert "CROSS JOIN" in inspect.getsource(Store.enroll_chain_meme_trader_v6)
    store.close()
