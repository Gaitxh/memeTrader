from datetime import timedelta

from memetrader.activity_tempo193 import ARM, PARENT, Tracker, interval_fields, policy
from memetrader.alpha149 import policies as alpha149_policies
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store
from test_l0_store import _snapshot


TOKEN = "solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump"
POOL = "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3"


def frame(at, **overrides):
    result = {
        "chain": "solana", "token_id": TOKEN, "pair_address": POOL,
        "provider": "dexscreener", "observed_at": iso(at),
        "ingested_at": iso(at), "recorded_at": iso(at),
        "price_usd": .01, "liquidity_usd": 5000,
        "volume_5m_usd": 1500, "pool_age_seconds": 7200,
        "buys_5m": 24, "sells_5m": 8,
        "buys_1h": 60, "sells_1h": 36,
        "price_change_5m_pct": 5.0,
    }
    result.update(overrides)
    return result


def test_dex_and_gecko_hour_intervals_are_as_of_fields():
    dex = {"txns": {"h1": {"buys": 60, "sells": 36}},
           "volume": {"h1": 2000}, "priceChange": {"m5": 5}}
    gecko = {"raw": {"pool": {"attributes": {
        "transactions": {"h1": {"buys": 60, "sells": 36}},
        "volume_usd": {"h1": "2000"},
        "price_change_percentage": {"m5": "5"},
    }}}}
    for pair in (dex, gecko):
        fields = interval_fields(pair)
        assert fields["buys_1h"] == 60
        assert fields["sells_1h"] == 36
        assert float(fields["price_change_5m_pct"]) == 5


def test_signal_uses_current_frame_and_dedupes_token_pool():
    at = utcnow()
    tracker = Tracker(at - timedelta(seconds=1))
    signal = tracker.accept(frame(at), at, floor=1000)
    assert signal is not None
    assert signal["selected"] == {"token_id": TOKEN, "pair_address": POOL}
    assert signal["decision_evidence"]["prior_55m_trades"] == 64
    assert signal["decision_evidence"]["tempo_ratio"] == 5.5
    assert tracker.accept(frame(at + timedelta(seconds=1)),
                          at + timedelta(seconds=1), floor=1000) is None


def test_missing_stale_buy_only_underfunded_or_nonaccelerating_never_signals():
    at = utcnow()
    bad = [
        {"sells_5m": 0}, {"buys_1h": None}, {"liquidity_usd": None},
        {"liquidity_usd": 1500}, {"pool_age_seconds": 3599},
        {"price_change_5m_pct": -1}, {"price_change_5m_pct": None},
        {"buys_1h": 20, "sells_1h": 3},
        {"buys_1h": 100, "sells_1h": 100},
        {"ingested_at": iso(at + timedelta(seconds=1))},
        {"recorded_at": None},
    ]
    for fields in bad:
        assert Tracker(at - timedelta(seconds=1)).accept(
            frame(at, **fields), at, floor=1000) is None
    assert Tracker(at - timedelta(seconds=1)).accept(
        frame(at), at + timedelta(seconds=31), floor=1000) is None


def test_policy_registers_at_new_frontier_and_next_frame_only(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "activity193.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent_seed = next(p for p in alpha149_policies(cohort_experiment_policies()[2])
                           if p["arm_id"] == PARENT)
        store.append_chain_meme_trader_policy(parent_seed)
        trial = policy(parent_seed)
        assert trial["entry_match_mode"] == "isolated_cohort_observer"
        assert trial["max_hold_minutes"] == 30
        assert trial["notional_usd"] == 20
        assert trial["hard_stop_return"] == parent_seed["hard_stop_return"]
        frontier = store.db.execute("SELECT COALESCE(MAX(id),0) FROM token_snapshots").fetchone()[0]
        assert store.register_chain_meme_activity_tempo193() == 1
        assert store.register_chain_meme_activity_tempo193() == 0
        row = store.db.execute(
            "SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions WHERE arm_id=?",
            (ARM,),
        ).fetchone()
        assert row["activation_snapshot_id"] == frontier
        token = TokenCandidate("solana", TOKEN.split(":", 1)[1], "Tempo", "TMP")
        store.upsert_token(token, seen_at=clock[0])
        clock[0] += timedelta(seconds=1)
        signal = Tracker(clock[0] - timedelta(seconds=1)).accept(
            frame(clock[0]), clock[0], floor=1000)
        assert signal is not None
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 0
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)
        ).fetchone()[0] == 0
        clock[0] += timedelta(seconds=7)
        assert store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0], liquidity=5000),
            recorded_at=clock[0], cohort_signals={ARM: signal},
        ) == 1
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ARM,)
        ).fetchone()
        assert position["source_entry_fill_id"] is not None
        assert position["opened_at"] > signal["observed_at"]
    finally:
        store.close()
