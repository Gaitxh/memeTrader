from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import iso, parse_time
from memetrader.store import Store


SOURCE_VERSION = "chain-regime-source/v1"
OBSERVER_VERSION = "chain-regime-outcomes/v1"

LEGACY_REGIME_QUERY = """
SELECT o.source_cohort_id,o.target_at,o.status,o.outcome_observed_at AS observed_at,
o.evaluated_at AS recorded_at,o.outcome_price_usd AS h15price,
o.outcome_liquidity_usd AS h15liq,c.token_id,c.pair_address,
h.outcome_price_usd AS h0price,s.observed_at AS baseline_at,
json_extract(s.raw_json,'$.pair.pairCreatedAt') AS created_ms
FROM chain_meme_universe_outcomes o
JOIN chain_meme_trader_v6_cohorts c ON c.id=o.source_cohort_id
JOIN chain_meme_universe_outcomes h ON h.observer_version=o.observer_version
    AND h.source_cohort_id=o.source_cohort_id AND h.horizon_minutes=0
JOIN token_snapshots s ON s.id=h.outcome_snapshot_id
WHERE o.observer_version=? AND o.status IN ('OBSERVED','UNKNOWN')
    AND o.target_at>=? AND o.target_at<=? AND o.horizon_minutes=15
ORDER BY o.target_at DESC,o.id DESC LIMIT 1000
"""

REWRITTEN_REGIME_QUERY = """
WITH observed AS (
SELECT o.id AS outcome_id,o.source_cohort_id,o.target_at,o.status,o.outcome_observed_at AS observed_at,
o.evaluated_at AS recorded_at,o.outcome_price_usd AS h15price,o.outcome_liquidity_usd AS h15liq,
c.token_id,c.pair_address,h.outcome_price_usd AS h0price,s.observed_at AS baseline_at,
json_extract(s.raw_json,'$.pair.pairCreatedAt') AS created_ms
FROM chain_meme_universe_outcomes o JOIN chain_meme_trader_v6_cohorts c ON c.id=o.source_cohort_id
JOIN chain_meme_universe_outcomes h ON h.observer_version=o.observer_version AND h.source_cohort_id=o.source_cohort_id AND h.horizon_minutes=0
JOIN token_snapshots s ON s.id=h.outcome_snapshot_id
WHERE o.observer_version=? AND o.status='OBSERVED' AND o.target_at>=? AND o.target_at<=? AND o.horizon_minutes=15 ORDER BY o.target_at DESC,o.id DESC LIMIT 1000),
unknown AS (
SELECT o.id AS outcome_id,o.source_cohort_id,o.target_at,o.status,o.outcome_observed_at AS observed_at,
o.evaluated_at AS recorded_at,o.outcome_price_usd AS h15price,o.outcome_liquidity_usd AS h15liq,
c.token_id,c.pair_address,h.outcome_price_usd AS h0price,s.observed_at AS baseline_at,
json_extract(s.raw_json,'$.pair.pairCreatedAt') AS created_ms
FROM chain_meme_universe_outcomes o JOIN chain_meme_trader_v6_cohorts c ON c.id=o.source_cohort_id
JOIN chain_meme_universe_outcomes h ON h.observer_version=o.observer_version AND h.source_cohort_id=o.source_cohort_id AND h.horizon_minutes=0
JOIN token_snapshots s ON s.id=h.outcome_snapshot_id
WHERE o.observer_version=? AND o.status='UNKNOWN' AND o.target_at>=? AND o.target_at<=? AND o.horizon_minutes=15 ORDER BY o.target_at DESC,o.id DESC LIMIT 1000)
SELECT source_cohort_id,target_at,status,observed_at,recorded_at,h15price,h15liq,token_id,pair_address,h0price,baseline_at,created_ms
FROM (SELECT * FROM observed UNION ALL SELECT * FROM unknown)
ORDER BY target_at DESC,outcome_id DESC LIMIT 1000
"""


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


def test_regime_status_branches_preserve_query_and_use_existing_due_index(tmp_path):
    store = Store(tmp_path / "chain-opportunity-regime-branches.sqlite3", initial_cash_usd=1_000)
    start = parse_time("2026-09-06T12:00:00Z")
    store.register_chain_meme_universe_outcomes(
        source_definition_version=SOURCE_VERSION,
        observer_version=OBSERVER_VERSION,
        registered_at=start - timedelta(seconds=1),
    )
    with store.db:
        for index in range(3):
            token_id = f"bsc:0x{index + 1:040x}"
            pair = f"0x{index + 101:040x}"
            snapshot_id = _snapshot(
                store, token_id, pair, start,
                created_at=start - timedelta(seconds=60), price=1.0, liquidity=200.0,
            )
            _cohort(store, token_id, pair, snapshot_id, start)
    store.enroll_chain_meme_universe_outcomes(observer_version=OBSERVER_VERSION, limit=3)
    h15_at = start + timedelta(minutes=15, seconds=5)
    with store.db:
        for row in store.db.execute(
            "SELECT token_id,pair_address FROM chain_meme_trader_v6_cohorts"
        ):
            _snapshot(store, row["token_id"], row["pair_address"], h15_at,
                created_at=start - timedelta(seconds=60), price=1.2, liquidity=200.0)
    store.finalize_chain_meme_universe_outcomes(
        observer_version=OBSERVER_VERSION, now=start + timedelta(minutes=16), limit=6
    )
    # Each status exceeds the branch limit.  The shared target timestamp makes
    # the id tie-breaker observable, while newer h15 rows without a horizon-0
    # join must not consume either branch's pre-UNION limit.
    valid_per_status = 1_002
    valid_count = valid_per_status * 2
    snapshot_start = int(store.db.execute("SELECT COALESCE(MAX(id),0)+1 FROM token_snapshots").fetchone()[0])
    cohort_start = int(store.db.execute("SELECT COALESCE(MAX(id),0)+1 FROM chain_meme_trader_v6_cohorts").fetchone()[0])
    target_at = iso(start + timedelta(minutes=15))
    with store.db:
        store.db.executemany(
            "INSERT INTO token_snapshots(id,token_id,observed_at,ingested_at,recorded_at,provider,raw_json) "
            "VALUES(?,?,?,?,?,?,?)",
            [
                (snapshot_start + offset, f"bsc:0x{offset + 10_000:040x}", iso(start), iso(start),
                 iso(start), "fixture", '{"pair":{"pairCreatedAt":0}}')
                for offset in range(valid_count)
            ],
        )
        store.db.executemany(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "id,definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,'broad_launch',?,?,?,1,'{}')",
            [
                (cohort_start + offset, SOURCE_VERSION, f"bsc:0x{offset + 10_000:040x}",
                 snapshot_start + offset, f"0x{offset + 20_000:040x}", iso(start))
                for offset in range(valid_count)
            ],
        )
        store.db.executemany(
            "INSERT INTO chain_meme_universe_outcomes("
            "observer_version,source_cohort_id,horizon_minutes,target_at,status,outcome_snapshot_id) "
            "VALUES(?,?,0,?,'OBSERVED',?)",
            [
                (OBSERVER_VERSION, cohort_start + offset, iso(start), snapshot_start + offset)
                for offset in range(valid_count)
            ],
        )
        store.db.executemany(
            "INSERT INTO chain_meme_universe_outcomes("
            "observer_version,source_cohort_id,horizon_minutes,target_at,status) VALUES(?,?,15,?,?)",
            [
                (OBSERVER_VERSION, cohort_start + offset, target_at,
                 "OBSERVED" if offset % 2 == 0 else "UNKNOWN")
                for offset in range(valid_count)
            ],
        )
        # These are newer than every eligible row but have no h=0 row, so the
        # inner join must exclude them before the per-status limit is applied.
        missing_start = cohort_start + valid_count
        store.db.executemany(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "id,definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,'broad_launch',?,?,?,1,'{}')",
            [
                (missing_start + offset, SOURCE_VERSION, f"bsc:0x{offset + 30_000:040x}",
                 snapshot_start + valid_count + offset, f"0x{offset + 40_000:040x}", iso(start))
                for offset in range(20)
            ],
        )
        store.db.executemany(
            "INSERT INTO chain_meme_universe_outcomes("
            "observer_version,source_cohort_id,horizon_minutes,target_at,status) VALUES(?,?,15,?,?)",
            [
                (OBSERVER_VERSION, missing_start + offset, iso(start + timedelta(minutes=16)),
                 "OBSERVED" if offset % 2 == 0 else "UNKNOWN")
                for offset in range(20)
            ],
        )
    store.db.execute(
        "UPDATE chain_meme_universe_outcomes SET status='UNKNOWN',outcome_snapshot_id=NULL,"
        "outcome_observed_at=NULL,outcome_price_usd=NULL,outcome_liquidity_usd=NULL "
        "WHERE observer_version=? AND horizon_minutes=15 AND source_cohort_id=("
        "SELECT MIN(source_cohort_id) FROM chain_meme_universe_outcomes WHERE observer_version=?)",
        (OBSERVER_VERSION, OBSERVER_VERSION),
    )
    bounds = (iso(start), iso(start + timedelta(hours=2)))
    old_rows = [tuple(row) for row in store.db.execute(LEGACY_REGIME_QUERY, (OBSERVER_VERSION, *bounds))]
    new_rows = [tuple(row) for row in store.db.execute(
        REWRITTEN_REGIME_QUERY, (OBSERVER_VERSION, *bounds, OBSERVER_VERSION, *bounds)
    )]
    plan = [row[3] for row in store.db.execute(
        "EXPLAIN QUERY PLAN " + REWRITTEN_REGIME_QUERY,
        (OBSERVER_VERSION, *bounds, OBSERVER_VERSION, *bounds),
    )]
    assert len(old_rows) == 1_000
    assert new_rows == old_rows
    assert {row[2] for row in new_rows} == {"OBSERVED", "UNKNOWN"}
    assert {row[1] for row in new_rows} == {target_at}
    assert sum("chain_meme_universe_outcomes_due_idx" in detail for detail in plan) >= 2
    store.close()
