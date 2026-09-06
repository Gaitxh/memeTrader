from __future__ import annotations

import json
from datetime import timedelta

from memetrader.models import iso, parse_time
from memetrader.store import Store


SOURCE_VERSION = "chain-outcome-test/v1"


def _snapshot(
    store: Store,
    *,
    token_id: str,
    pair_address: str,
    observed_at,
    ingested_at=None,
    recorded_at=None,
    price: float = 1.0,
) -> int:
    ingested_at = ingested_at or observed_at
    recorded_at = recorded_at or ingested_at
    cursor = store.db.execute(
        "INSERT INTO token_snapshots("
        "token_id,observed_at,ingested_at,recorded_at,provider,price_usd,"
        "liquidity_usd,raw_json) VALUES(?,?,?,?,?,?,?,?)",
        (
            token_id, iso(observed_at), iso(ingested_at), iso(recorded_at),
            "strategy-observer:dexscreener", price, 10_000.0,
            json.dumps({"pair": {"pairAddress": pair_address}}),
        ),
    )
    return int(cursor.lastrowid)


def _cohort(
    store: Store,
    *,
    token_id: str,
    pair_address: str,
    source_snapshot_id: int,
    decided_at,
    episode_no: int,
) -> int:
    cursor = store.db.execute(
        "INSERT INTO chain_meme_trader_v6_cohorts("
        "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
        "decided_at,episode_no,feature_json) VALUES(?,?,'broad_launch',?,?,?,?,?)",
        (
            SOURCE_VERSION, token_id, source_snapshot_id, pair_address,
            iso(decided_at), episode_no, "{}",
        ),
    )
    return int(cursor.lastrowid)


def _migration_fact(
    store: Store, *, token_id: str, observed_at, ingested_at=None,
    recorded_at=None, suffix: str,
) -> int:
    ingested_at = ingested_at or observed_at
    recorded_at = recorded_at or ingested_at
    cursor = store.db.execute(
        "INSERT INTO token_launch_facts("
        "event_fingerprint,token_id,chain,launch_provider,launch_surface,"
        "launch_event_type,address,creator_address,create_signature,bonding_curve_key,"
        "pool_label,token_pairing,source_observed_at,ingested_at,recorded_at,"
        "raw_payload_hash,definition_version) "
        "VALUES(?,?,'bsc','fixture','four_meme','migration',?,'creator',?,'curve',"
        "'pool','BNB',?,?,?,?,'fixture/v1')",
        (
            f"migration-{suffix}", token_id, token_id.partition(":")[2],
            f"signature-{suffix}", iso(observed_at), iso(ingested_at),
            iso(recorded_at), f"hash-{suffix}",
        ),
    )
    return int(cursor.lastrowid)


def test_chain_outcomes_start_after_frontier_and_enroll_in_bounded_batches(tmp_path):
    store = Store(tmp_path / "chain-outcome-frontier.sqlite3", initial_cash_usd=1000)
    start = parse_time("2026-09-06T12:00:00Z")
    old_snapshot = _snapshot(
        store, token_id="bsc:0xold", pair_address="0xpool-old", observed_at=start,
    )
    old_cohort = _cohort(
        store, token_id="bsc:0xold", pair_address="0xpool-old",
        source_snapshot_id=old_snapshot, decided_at=start, episode_no=1,
    )
    registration = store.register_chain_meme_universe_outcomes(
        source_definition_version=SOURCE_VERSION, registered_at=start + timedelta(seconds=1),
    )
    assert int(registration["activation_cohort_id"]) == old_cohort

    new_ids = []
    for index in range(2):
        at = start + timedelta(minutes=index + 1)
        snapshot_id = _snapshot(
            store, token_id=f"bsc:0xnew{index}", pair_address=f"0xpool-new{index}",
            observed_at=at,
        )
        new_ids.append(_cohort(
            store, token_id=f"bsc:0xnew{index}", pair_address=f"0xpool-new{index}",
            source_snapshot_id=snapshot_id, decided_at=at, episode_no=1,
        ))

    first = store.enroll_chain_meme_universe_outcomes(limit=1)
    assert first == {"cohorts_enrolled": 1, "targets_enrolled": 4}
    assert {
        int(row[0]) for row in store.db.execute(
            "SELECT DISTINCT source_cohort_id FROM chain_meme_universe_outcomes"
        )
    } == {new_ids[0]}
    second = store.enroll_chain_meme_universe_outcomes(limit=1)
    assert second == {"cohorts_enrolled": 1, "targets_enrolled": 4}
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_universe_outcomes WHERE source_cohort_id=?",
        (old_cohort,),
    ).fetchone()[0] == 0
    assert store.enroll_chain_meme_universe_outcomes(limit=1) == {
        "cohorts_enrolled": 0, "targets_enrolled": 0,
    }
    store.close()


def test_chain_outcomes_use_only_stored_causal_same_pool_snapshots(tmp_path):
    store = Store(tmp_path / "chain-outcome-causal.sqlite3", initial_cash_usd=1000)
    decided = parse_time("2026-09-06T12:00:03Z")
    token_id, pair = "bsc:0xaaa", "0xpool-a"
    store.register_chain_meme_universe_outcomes(
        source_definition_version=SOURCE_VERSION, registered_at=decided - timedelta(minutes=1),
    )
    source_snapshot = _snapshot(
        store, token_id=token_id, pair_address=pair,
        observed_at=decided - timedelta(seconds=3),
        ingested_at=decided - timedelta(seconds=2),
        recorded_at=decided - timedelta(seconds=1),
    )
    cohort_id = _cohort(
        store, token_id=token_id, pair_address=pair,
        source_snapshot_id=source_snapshot, decided_at=decided, episode_no=1,
    )
    assert store.enroll_chain_meme_universe_outcomes(limit=8)["targets_enrolled"] == 4

    h15 = decided + timedelta(minutes=15)
    wrong_pair = _snapshot(
        store, token_id=token_id, pair_address="0xother-pool",
        observed_at=h15 + timedelta(seconds=1), price=9.0,
    )
    exact_h15 = _snapshot(
        store, token_id=token_id, pair_address=pair,
        observed_at=h15 + timedelta(seconds=5), price=1.5,
    )
    h60 = decided + timedelta(minutes=60)
    _snapshot(
        store, token_id=token_id, pair_address=pair,
        observed_at=h60 + timedelta(seconds=2),
        ingested_at=h60 + timedelta(seconds=1),
        recorded_at=h60 + timedelta(seconds=3), price=2.0,
    )
    h240 = decided + timedelta(minutes=240)
    exact_h240 = _snapshot(
        store, token_id=token_id, pair_address=pair,
        observed_at=h240 + timedelta(seconds=4), price=3.0,
    )

    early = store.finalize_chain_meme_universe_outcomes(
        now=h15 + timedelta(seconds=1), limit=16,
    )
    assert early == {"targets_checked": 2, "observed": 1, "unknown": 0}
    h15_pending = store.db.execute(
        "SELECT status,outcome_snapshot_id FROM chain_meme_universe_outcomes "
        "WHERE source_cohort_id=? AND horizon_minutes=15",
        (cohort_id,),
    ).fetchone()
    assert h15_pending["status"] == "PENDING"
    assert h15_pending["outcome_snapshot_id"] is None

    result = store.finalize_chain_meme_universe_outcomes(
        now=h240 + timedelta(seconds=31), limit=16,
    )
    assert result == {"targets_checked": 3, "observed": 2, "unknown": 1}
    rows = {
        int(row["horizon_minutes"]): row
        for row in store.db.execute(
            "SELECT * FROM chain_meme_universe_outcomes WHERE source_cohort_id=?",
            (cohort_id,),
        )
    }
    assert rows[0]["status"] == "OBSERVED"
    assert int(rows[0]["outcome_snapshot_id"]) == source_snapshot
    assert rows[15]["status"] == "OBSERVED"
    assert int(rows[15]["outcome_snapshot_id"]) == exact_h15
    assert int(rows[15]["outcome_snapshot_id"]) != wrong_pair
    assert rows[60]["status"] == "UNKNOWN"
    assert rows[60]["outcome_snapshot_id"] is None
    assert rows[240]["status"] == "OBSERVED"
    assert int(rows[240]["outcome_snapshot_id"]) == exact_h240
    assert store.finalize_chain_meme_universe_outcomes(
        now=h240 + timedelta(seconds=40), limit=16,
    ) == {"targets_checked": 0, "observed": 0, "unknown": 0}
    store.close()


def test_migration_short_trajectory_is_fact_visible_and_anchored_to_migration_time(
    tmp_path,
):
    store = Store(tmp_path / "chain-outcome-migration-short.sqlite3", initial_cash_usd=1000)
    migration_at = parse_time("2026-09-06T12:00:00Z")
    observer = "chain-outcome-test/migration-short-v1"
    registration = store.register_chain_meme_universe_outcomes(
        source_definition_version=SOURCE_VERSION,
        observer_version=observer,
        registered_at=migration_at - timedelta(minutes=1),
        include_migration_short_trajectory=True,
    )
    definition = json.loads(registration["definition_json"])
    assert definition["migration_short_trajectory"]["target_offsets_seconds"] == [60, 120]
    assert definition["migration_short_trajectory"]["anchor"] == (
        "migration_source_observed_at"
    )

    eligible_token, eligible_pair = "bsc:0xeligible", "0xpool-eligible"
    eligible_fact = _migration_fact(
        store, token_id=eligible_token, observed_at=migration_at,
        ingested_at=migration_at + timedelta(seconds=5),
        recorded_at=migration_at + timedelta(seconds=10), suffix="eligible",
    )
    decided = migration_at + timedelta(seconds=20)
    eligible_source = _snapshot(
        store, token_id=eligible_token, pair_address=eligible_pair,
        observed_at=decided - timedelta(seconds=1),
    )
    eligible_cohort = _cohort(
        store, token_id=eligible_token, pair_address=eligible_pair,
        source_snapshot_id=eligible_source, decided_at=decided, episode_no=1,
    )

    future_token, future_pair = "bsc:0xfuture", "0xpool-future"
    future_decided = migration_at + timedelta(seconds=20)
    _migration_fact(
        store, token_id=future_token,
        observed_at=future_decided + timedelta(seconds=1),
        recorded_at=future_decided + timedelta(seconds=1), suffix="future",
    )
    future_source = _snapshot(
        store, token_id=future_token, pair_address=future_pair,
        observed_at=future_decided - timedelta(seconds=1),
    )
    future_cohort = _cohort(
        store, token_id=future_token, pair_address=future_pair,
        source_snapshot_id=future_source, decided_at=future_decided, episode_no=1,
    )

    late_token, late_pair = "bsc:0xlate", "0xpool-late"
    late_decided = migration_at + timedelta(seconds=20)
    _migration_fact(
        store, token_id=late_token, observed_at=migration_at,
        ingested_at=migration_at + timedelta(seconds=5),
        recorded_at=late_decided + timedelta(seconds=1), suffix="late-recorded",
    )
    late_source = _snapshot(
        store, token_id=late_token, pair_address=late_pair,
        observed_at=late_decided - timedelta(seconds=1),
    )
    late_cohort = _cohort(
        store, token_id=late_token, pair_address=late_pair,
        source_snapshot_id=late_source, decided_at=late_decided, episode_no=1,
    )

    assert store.enroll_chain_meme_universe_outcomes(
        observer_version=observer, limit=99,
    ) == {"cohorts_enrolled": 3, "targets_enrolled": 14}
    eligible = {
        int(row["horizon_minutes"]): row
        for row in store.db.execute(
            "SELECT * FROM chain_meme_universe_outcomes WHERE observer_version=? "
            "AND source_cohort_id=?", (observer, eligible_cohort),
        )
    }
    assert set(eligible) == {0, 1, 2, 15, 60, 240}
    assert eligible[1]["target_at"] == iso(migration_at + timedelta(seconds=60))
    assert eligible[2]["target_at"] == iso(migration_at + timedelta(seconds=120))
    assert f"source_fact_id={eligible_fact}" in eligible[1]["reason"]
    assert "offset_seconds=60" in eligible[1]["reason"]
    assert f"deadline_at={iso(migration_at + timedelta(seconds=90))}" in eligible[1]["reason"]
    for cohort_id in (future_cohort, late_cohort):
        assert [
            int(row[0]) for row in store.db.execute(
                "SELECT horizon_minutes FROM chain_meme_universe_outcomes "
                "WHERE observer_version=? AND source_cohort_id=? ORDER BY horizon_minutes",
                (observer, cohort_id),
            )
        ] == [0, 15, 60, 240]

    h1_snapshot = _snapshot(
        store, token_id=eligible_token, pair_address=eligible_pair,
        observed_at=migration_at + timedelta(seconds=65), price=1.5,
    )
    cohort_anchored_but_later = _snapshot(
        store, token_id=eligible_token, pair_address=eligible_pair,
        observed_at=decided + timedelta(seconds=60), price=9.0,
    )
    h2_snapshot = _snapshot(
        store, token_id=eligible_token, pair_address=eligible_pair,
        observed_at=migration_at + timedelta(seconds=125), price=2.0,
    )
    result = store.finalize_chain_meme_universe_outcomes(
        observer_version=observer,
        now=migration_at + timedelta(seconds=151), limit=16,
    )
    assert result == {"targets_checked": 5, "observed": 5, "unknown": 0}
    finalized = {
        int(row["horizon_minutes"]): row
        for row in store.db.execute(
            "SELECT * FROM chain_meme_universe_outcomes WHERE observer_version=? "
            "AND source_cohort_id=? AND horizon_minutes IN (1,2)",
            (observer, eligible_cohort),
        )
    }
    assert int(finalized[1]["outcome_snapshot_id"]) == h1_snapshot
    assert int(finalized[1]["outcome_snapshot_id"]) != cohort_anchored_but_later
    assert int(finalized[2]["outcome_snapshot_id"]) == h2_snapshot
    assert finalized[1]["reason"].endswith("|first_stored_exact_pool_snapshot")
    assert f"source_fact_id={eligible_fact}" in finalized[2]["reason"]
    store.close()
