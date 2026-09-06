from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import iso, parse_time
from memetrader.store import Store


SOURCE_VERSION = "chain-regime-source/v1"
OBSERVER_VERSION = "chain-regime-outcomes/v1"


def _snapshot(store, token_id, pair_address, at, *, created_at, price, liquidity):
    cursor = store.db.execute(
        "INSERT INTO token_snapshots("
        "token_id,observed_at,ingested_at,recorded_at,provider,price_usd,"
        "liquidity_usd,raw_json) VALUES(?,?,?,?,?,?,?,?)",
        (token_id, iso(at), iso(at), iso(at), "strategy-observer:dexscreener",
         price, liquidity, json.dumps({"pair": {"pairAddress": pair_address,
             "pairCreatedAt": round(created_at.timestamp() * 1000)}})),
    )
    return int(cursor.lastrowid)


def _cohort(store, token_id, pair_address, snapshot_id, decided_at):
    cursor = store.db.execute(
        "INSERT INTO chain_meme_trader_v6_cohorts("
        "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
        "decided_at,episode_no,feature_json) VALUES(?,?,'broad_launch',?,?,?,1,'{}')",
        (SOURCE_VERSION, token_id, snapshot_id, pair_address, iso(decided_at)),
    )
    return int(cursor.lastrowid)


def test_store_outcomes_feed_per_chain_regimes_and_unknown_coverage(tmp_path):
    store = Store(tmp_path / "chain-opportunity-regime.sqlite3", initial_cash_usd=1_000)
    start = parse_time("2026-09-06T12:00:00Z")
    store.register_chain_meme_universe_outcomes(
        source_definition_version=SOURCE_VERSION,
        observer_version=OBSERVER_VERSION,
        registered_at=start - timedelta(seconds=1),
    )

    cohorts = []
    with store.db:
        for chain, count in (("bsc", 20), ("solana", 20)):
            for index in range(count):
                if chain == "bsc":
                    token_id = f"bsc:0x{index + 1:040x}"
                    pair = f"0x{index + 101:040x}"
                else:
                    token_id = f"solana:{Pubkey.new_unique()}"
                    pair = str(Pubkey.new_unique())
                source_id = _snapshot(
                    store, token_id, pair, start,
                    created_at=start - timedelta(seconds=60), price=1.0, liquidity=200.0,
                )
                cohorts.append((chain, index, token_id, pair,
                    _cohort(store, token_id, pair, source_id, start), source_id))

    assert store.enroll_chain_meme_universe_outcomes(
        observer_version=OBSERVER_VERSION, limit=64
    ) == {"cohorts_enrolled": 40, "targets_enrolled": 160}

    h15_at = start + timedelta(minutes=15, seconds=5)
    with store.db:
        for chain, index, token_id, pair, _, _ in cohorts:
            if chain == "solana" and index >= 15:
                continue
            _snapshot(store, token_id, pair, h15_at,
                created_at=start - timedelta(seconds=60), price=1.2, liquidity=200.0)

    evaluated_at = start + timedelta(minutes=16)
    assert store.finalize_chain_meme_universe_outcomes(
        observer_version=OBSERVER_VERSION, now=evaluated_at, limit=128
    ) == {"targets_checked": 80, "observed": 75, "unknown": 5}

    bsc_cohort = next(row for row in cohorts if row[0] == "bsc")
    observed = store.db.execute(
        "SELECT * FROM chain_meme_universe_outcomes WHERE observer_version=? "
        "AND source_cohort_id=? AND horizon_minutes=15",
        (OBSERVER_VERSION, bsc_cohort[4]),
    ).fetchone()
    assert observed["status"] == "OBSERVED"
    assert parse_time(observed["target_at"]) == start + timedelta(minutes=15)
    assert parse_time(observed["outcome_observed_at"]) == h15_at
    assert parse_time(observed["evaluated_at"]) == evaluated_at
    h0 = store.db.execute(
        "SELECT * FROM chain_meme_universe_outcomes WHERE observer_version=? "
        "AND source_cohort_id=? AND horizon_minutes=0",
        (OBSERVER_VERSION, bsc_cohort[4]),
    ).fetchone()
    assert h0["status"] == "OBSERVED"
    assert int(h0["outcome_snapshot_id"]) == bsc_cohort[5]

    unknown_cohort = next(row for row in cohorts if row[0] == "solana" and row[1] == 19)
    unknown = store.db.execute(
        "SELECT * FROM chain_meme_universe_outcomes WHERE observer_version=? "
        "AND source_cohort_id=? AND horizon_minutes=15",
        (OBSERVER_VERSION, unknown_cohort[4]),
    ).fetchone()
    assert unknown["status"] == "UNKNOWN"
    assert unknown["reason"] == "no_fresh_stored_exact_pool_snapshot"
    assert unknown["outcome_snapshot_id"] is None
    assert unknown["outcome_observed_at"] is None
    assert parse_time(unknown["evaluated_at"]) == evaluated_at

    result = store.update_chain_opportunity_regimes(
        OBSERVER_VERSION, now=evaluated_at
    )
    assert set(result["groups"]) == {"bsc|early", "solana|early"}
    bsc = result["groups"]["bsc|early"]
    assert bsc["regime"] == "HOT"
    assert (bsc["total_episodes"], bsc["known_episodes"], bsc["coverage"]) == (
        20, 20, pytest.approx(1.0)
    )
    solana = result["groups"]["solana|early"]
    assert solana["regime"] == "INSUFFICIENT"
    assert (solana["total_episodes"], solana["known_episodes"]) == (20, 15)
    assert solana["coverage"] == pytest.approx(0.75)
    assert result["authority"] == "label_only_no_buy_sell_no_strategy_change"
    assert result["scope"] == "bounded_enrolled_cohorts_not_full_market;latest_1000_due_rows"
    assert store.get_kv(f"opportunity-regime:{OBSERVER_VERSION}") == result
    store.close()
