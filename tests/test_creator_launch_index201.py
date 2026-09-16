from memetrader.store import Store


def test_creator_launch_lookups_use_asof_indexes(tmp_path):
    store = Store(tmp_path / "creator-index201.sqlite3", initial_cash_usd=1000)
    try:
        indexes = {row[1] for row in store.db.execute("PRAGMA index_list(token_launch_facts)")}
        assert "token_launch_facts_creator_asof_idx" in indexes
        assert "token_launch_facts_definition_recorded_idx" in indexes
        prior = list(store.db.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*),MIN(recorded_at) FROM token_launch_facts "
            "WHERE definition_version=? AND launch_event_type='create' "
            "AND creator_address=? AND id<? AND recorded_at<?",
            (store.TOKEN_LAUNCH_FACT_VERSION, "creator", 10, "2099-01-01"),
        ))
        assert any("token_launch_facts_creator_asof_idx" in row[3] for row in prior)
        start = list(store.db.execute(
            "EXPLAIN QUERY PLAN SELECT MIN(recorded_at) FROM token_launch_facts "
            "WHERE definition_version=?", (store.TOKEN_LAUNCH_FACT_VERSION,),
        ))
        assert any("token_launch_facts_definition_recorded_idx" in row[3] for row in start)
    finally:
        store.close()
