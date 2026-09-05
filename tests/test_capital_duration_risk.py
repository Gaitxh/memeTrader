import json
import sqlite3

from memetrader.capital_duration_risk import (
    duration_risk_context,
    load_duration_risk_samples,
    seal_duration_risk_model,
)


CUTOFF = "2026-09-05T12:10:00Z"


def _db():
    db = sqlite3.connect(":memory:")
    db.executescript("""
      CREATE TABLE chain_meme_trader_v6_cohorts(
        id INTEGER, definition_version, token_id, source_snapshot_id,
        episode_no, decided_at, pair_address);
      CREATE TABLE chain_meme_trader_positions(
        definition_version, arm_id, shadow_cohort_id, token_id, opened_at,
        closed_at, status, last_evaluated_at);
      CREATE TABLE token_snapshots(
        id, token_id, liquidity_usd, price_usd, observed_at, ingested_at, recorded_at, raw_json);
      CREATE TABLE chain_meme_trader_trades(
        id, definition_version, arm_id, shadow_cohort_id, token_id, side,
        net_cash_flow_usd, realized_pnl_usd, created_at, recorded_at);
      CREATE TABLE chain_meme_trader_accounting_contaminations(
        definition_version, arm_id, shadow_cohort_id, recorded_at);
      CREATE TABLE chain_meme_trader_market_fill_corrections(
        definition_version, arm_id, shadow_cohort_id, recorded_at);
      CREATE TABLE chain_meme_trader_capital_credits(
        definition_version, arm_id, shadow_cohort_id, recorded_at);
    """)
    return db


def _episode(db, n, token, status="closed", episode=1, close="2026-09-05T12:05:00Z"):
    entry = "2026-09-05T12:00:00Z"
    db.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES(?,?,?,?,?,?,?)",
               (n, "v", token, n, episode, entry, "pool"))
    db.execute("INSERT INTO chain_meme_trader_positions VALUES(?,?,?,?,?,?,?,?)",
               ("v", "arm", n, token, entry, close if status != "open" else None,
                status, None if status != "open" else "2026-09-05T12:04:00Z"))
    db.execute("INSERT INTO token_snapshots VALUES(?,?,?,?,?,?,?,?)",
               (n, token, 20000, 1, "2026-09-04T23:59:00Z", "2026-09-04T23:59:01Z",
                "2026-09-04T23:59:02Z", json.dumps({"pair": {"pairAddress": "pool"}})))
    db.execute("INSERT INTO chain_meme_trader_trades VALUES(?,?,?,?,?,?,?,?,?,?)",
               (n * 2, "v", "arm", n, token, "BUY", -10, 0, entry, entry))
    if status != "open":
        db.execute("INSERT INTO chain_meme_trader_trades VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (n * 2 + 1, "v", "arm", n, token, "SELL", 20 if n == 1 else 5, 10 if n == 1 else 0,
                    close, close))
    db.execute("INSERT INTO token_snapshots VALUES(?,?,?,?,?,?,?,?)",
               (1000+n, token, 20000, 1, "2026-09-05T12:04:00Z", "2026-09-05T12:04:00Z",
                "2026-09-05T12:04:00Z", json.dumps({"pair": {"pairAddress": "pool"}})))


def test_same_time_event_and_censor_use_same_risk_set():
    source = {"cutoff_at": CUTOFF, "definition_version": "v", "samples": [
        {"sample_id": "a", "token_id": "a", "feature_observed_at": "2026-09-04T23:00:00Z",
         "feature_recorded_at": "2026-09-04T23:00:01Z", "entry_at": "2026-09-05T12:00:00Z",
         "event_at": "2026-09-05T12:05:00Z", "event_type": "profit_exit", "censor_type": None,
         "duration_seconds": 300, "available_at": "2026-09-05T12:05:00Z", "bin_key": "solana:10k_100k"},
        {"sample_id": "b", "token_id": "b", "feature_observed_at": "2026-09-04T23:00:00Z",
         "feature_recorded_at": "2026-09-04T23:00:01Z", "entry_at": "2026-09-05T12:00:00Z",
         "event_at": "2026-09-05T12:05:00Z", "event_type": None, "censor_type": "administrative_cutoff",
         "duration_seconds": 300, "available_at": "2026-09-05T12:05:00Z", "bin_key": "solana:10k_100k"},
    ]}
    model = seal_duration_risk_model(source, trained_at=CUTOFF, minimum_samples=1)
    assert model["cumulative_incidence"]["solana:10k_100k"]["300"]["profit_exit"] == 0.5
    assert model["right_censored"] == 1


def test_loader_open_is_censored_and_future_or_polluted_is_rejected():
    db = _db()
    _episode(db, 1, "solana:a", "open")
    db.execute("INSERT INTO chain_meme_trader_trades VALUES(?,?,?,?,?,?,?,?,?,?)",
               (99, "v", "arm", 1, "solana:a", "SELL", 3, 0,
                "2026-09-05T12:02:00Z", "2026-09-05T12:02:00Z"))
    _episode(db, 2, "solana:b", "closed")
    db.execute("UPDATE chain_meme_trader_positions SET closed_at=? WHERE shadow_cohort_id=2", ("2026-09-05T12:11:00Z",))
    _episode(db, 3, "solana:c", "closed")
    db.execute("INSERT INTO chain_meme_trader_accounting_contaminations VALUES(?,?,?,?)", ("v", "arm", 3, CUTOFF))
    source = load_duration_risk_samples(db, "v", CUTOFF)
    assert len(source["samples"]) == 2
    assert all(s["event_type"] is None for s in source["samples"])
    assert all(s["censor_type"] == "data_gap" for s in source["samples"])
    assert source["excluded"]["engineering_pollution"] == 1


def test_loader_recovers_profit_and_loss_from_immutable_sell_cost():
    db = _db()
    _episode(db, 1, "solana:profit", "closed")
    _episode(db, 2, "solana:loss", "closed")
    db.execute("UPDATE chain_meme_trader_trades SET net_cash_flow_usd=0, realized_pnl_usd=-10 "
               "WHERE shadow_cohort_id=2 AND side='SELL'")
    source = load_duration_risk_samples(db, "v", CUTOFF)
    assert {s["event_type"] for s in source["samples"]} == {"profit_exit", "loss_exit"}


def test_future_mutable_writeoff_time_does_not_change_asof_ledger():
    db = _db()
    _episode(db, 1, "solana:writeoff", "closed")
    db.execute("UPDATE chain_meme_trader_trades SET side='WRITEOFF',net_cash_flow_usd=0,realized_pnl_usd=-10 WHERE side='SELL'")
    db.execute("UPDATE chain_meme_trader_positions SET closed_at='2026-09-05T13:00:00Z',status='written_off'")
    source = load_duration_risk_samples(db, "v", CUTOFF)
    assert source["samples"][0]["event_type"] == "writeoff_exit"
    assert source["samples"][0]["event_at"] == "2026-09-05T12:05:00Z"


def test_new_duration_arm_uses_real_store_next_frame_and_seals_without_retraining(tmp_path, monkeypatch):
    import asyncio
    from datetime import timedelta
    from solders.pubkey import Pubkey
    from memetrader.models import TokenCandidate, iso, utcnow
    from memetrader.store import Store
    from memetrader.runtime import Runtime
    from test_event_candidates_runtime import _snapshot

    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
    store = Store(tmp_path / "duration-real.db")
    try:
        store.activate_chain_meme_trader_funded_period()
        assert store.register_chain_meme_duration_risk_experiment() == 1
        assert store.register_chain_meme_duration_risk_experiment() == 0
        runtime = Runtime.__new__(Runtime)
        runtime.store = store
        runtime._chain_meme_active_idle_event = asyncio.Event()
        runtime._chain_meme_active_idle_event.set()
        clock[0] += timedelta(seconds=1)
        asyncio.run(runtime.seal_duration_research_once())
        sealed_id = runtime._duration_risk_model["model_id"]
        assert runtime._duration_risk_model["samples"] == []

        token = TokenCandidate("solana", str(Pubkey.new_unique()), "Duration", "DUR")
        pair = str(Pubkey.new_unique())
        for _ in range(2):
            clock[0] += timedelta(seconds=15)
            snap = _snapshot(token, pair, clock[0] - timedelta(milliseconds=100))
            # Test-only mature bin; no claim that this is empirical evidence.
            context = dict(sealed=True, sample_status="sufficient_sample",
                observed_at=iso(snap.observed_at), recorded_at=iso(clock[0]),
                cutoff_at=iso(clock[0]-timedelta(minutes=10)), trained_at=iso(clock[0]-timedelta(minutes=9)),
                gap_sensitivity={"300": {"profit_exit": .6, "loss_exit": .2, "writeoff_exit": .1}})
            store.observe_chain_meme_pattern(token, snap, recorded_at=clock[0],
                cross_section={"duration_risk": context})
        trade = store.db.execute("SELECT * FROM chain_meme_trader_trades WHERE arm_id='duration_competing_risk_v1' AND side='BUY'").fetchone()
        assert trade is not None and trade["gross_usd"] == 5
        clock[0] += timedelta(seconds=15)
        store.observe_chain_meme_pattern(token, _snapshot(token, pair, clock[0]-timedelta(milliseconds=100)),
            recorded_at=clock[0])
        source = load_duration_risk_samples(store.db, store.CHAIN_MEME_TRADER_ACTIVE_VERSION, iso(clock[0]))
        assert len(source["samples"]) == 1
        assert source["samples"][0]["censor_type"] == "administrative_cutoff"
        asyncio.run(runtime.seal_duration_research_once())
        assert runtime._duration_risk_model["model_id"] == sealed_id
    finally:
        store.close()


def test_duplicate_token_does_not_increase_maturity_and_context_reports_insufficient():
    base = {"token_id": "solana:x", "feature_observed_at": "2026-09-04T23:00:00Z",
            "feature_recorded_at": "2026-09-04T23:00:01Z", "entry_at": "2026-09-05T12:00:00Z",
            "event_at": "2026-09-05T12:05:00Z", "event_type": "profit_exit", "censor_type": None,
            "duration_seconds": 300, "available_at": "2026-09-05T12:05:00Z", "bin_key": "solana:10k_100k"}
    source = {"cutoff_at": CUTOFF, "definition_version": "v", "samples": [
        {**base, "sample_id": "a"}, {**base, "sample_id": "b"}]}
    model = seal_duration_risk_model(source, trained_at=CUTOFF, minimum_samples=2)
    assert model["sample_status"] == "insufficient_sample"
    context = duration_risk_context(model, token_id="solana:x", liquidity_usd=20000, observed_at="2026-09-05T12:10:45Z",
                                    recorded_at="2026-09-05T12:10:45Z", decision_at="2026-09-05T12:11:00Z")
    assert context["sample_status"] == "insufficient_sample"


def test_informative_gap_is_separate_adverse_sensitivity_not_fake_writeoff():
    base = {"feature_observed_at": "2026-09-05T11:00:00Z", "feature_recorded_at": "2026-09-05T11:00:01Z",
            "entry_at": "2026-09-05T12:00:00Z", "available_at": CUTOFF, "bin_key": "solana:10k_100k"}
    source = {"cutoff_at": CUTOFF, "samples": [
        {**base, "token_id": "solana:a", "sample_id": "a", "duration_seconds": 60,
         "event_at": "2026-09-05T12:01:00Z", "event_type": None, "censor_type": "data_gap"},
        {**base, "token_id": "solana:b", "sample_id": "b", "duration_seconds": 120,
         "event_at": "2026-09-05T12:02:00Z", "event_type": "profit_exit", "censor_type": None}]}
    model = seal_duration_risk_model(source, trained_at=CUTOFF, minimum_samples=1)
    assert model["data_gap_fraction_by_bin"]["solana:10k_100k"] == .5
    stress = model["gap_sensitivity"]["solana:10k_100k"]["300"]
    assert stress == {"observation_gap": .5, "profit_exit": .5}
    assert model["samples"][0]["event_type"] is None
