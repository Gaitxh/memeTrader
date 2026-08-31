from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from memetrader.collectors import DexScreenerClient, MastodonCollector
from memetrader.models import CandidateDecision, EventView, Observation, Position, TokenCandidate, TokenSnapshot, iso, parse_time
from memetrader.runtime import load_config
from memetrader.store import Store
from memetrader.strategy import (
    CandidateEvaluator,
    EventEngine,
    classify_event_topic,
    evidence_origin,
    PaperPolicy,
    SafetyChecker,
    extract_addresses,
    extract_aliases,
    is_context_searchable_token_name,
    is_distinctive_token_name,
    is_promotional_market_content,
    replay_guard,
    temporal_rejection_reasons,
    token_snapshot_temporal_rejections,
)


def test_source_poll_exposure_summary_includes_zero_yield_and_errors_without_raw_queries(tmp_path: Path):
    store = Store(tmp_path / "poll-exposure.sqlite3", initial_cash_usd=1000)
    completed = store.start_source_poll_attempt(
        collector_kind="rss",
        source_key="rss:news.example:masked",
        platform="rss_news",
    )
    store.finish_source_poll_attempt(
        completed,
        status="completed",
        fetched_count=3,
        new_observation_count=2,
        new_event_count=1,
        decision_eligible_count=1,
        context_only_count=2,
        duplicate_count=1,
    )
    zero = store.start_source_poll_attempt(
        collector_kind="rss",
        source_key="rss:news.example:masked",
        platform="rss_news",
    )
    store.finish_source_poll_attempt(zero, status="completed")
    failed = store.start_source_poll_attempt(
        collector_kind="bluesky",
        source_key="bluesky-query:0123456789abcdef",
        platform="bluesky",
    )
    store.finish_source_poll_attempt(failed, status="error", error_type="TimeoutError")

    summary = store.source_poll_learning_summary_from_connection(store.db)
    rss = next(item for item in summary["items"] if item["platform"] == "rss_news")
    assert summary["status"] == "collecting"
    assert summary["summary"]["attempts"] == 3
    assert rss["completed"] == 2
    assert rss["completed_zero_yield"] == 1
    assert rss["new_observations_per_completed_poll"] == 1.0
    payload = json.dumps(summary)
    assert "TimeoutError" in payload
    assert "q=" not in payload and "token=" not in payload and "https://" not in payload
    store.close()


def test_event_attention_points_are_forward_append_only_and_future_safe(tmp_path: Path):
    store = Store(tmp_path / "attention-trajectory.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = datetime.now(timezone.utc)
    base = dict(
        source_kind="news",
        title="Viral capybara mascot appears online",
        text="Viral capybara mascot appears online",
        observed_at=now,
        ingested_at=now,
    )
    event_id, _, _ = engine.ingest(Observation(source="news-a", source_item_id="a", **base))
    engine.ingest(Observation(source="news-b", source_item_id="b", role="confirmation", **base))
    engine.ingest(Observation(source="context", source_item_id="c", role="promotion", **base))
    engine.ingest(Observation(source="news-a", source_item_id="a", **base))
    future = now + timedelta(hours=1)
    engine.ingest(
        Observation(
            source="future",
            source_kind="news",
            title=base["title"],
            text=base["text"],
            observed_at=future,
            ingested_at=future,
            source_item_id="future",
        )
    )

    points = list(store.db.execute(
        "SELECT * FROM event_attention_points WHERE event_id=? ORDER BY id", (event_id,)
    ))
    assert len(points) == 4
    assert [row["trigger_role"] for row in points] == ["feature", "confirmation", "promotion", "feature"]
    assert points[2]["trigger_decision_eligible"] == 0
    assert points[3]["trigger_decision_eligible"] == 0
    assert points[3]["exclusion_reason"] == "trigger_observed_in_future"
    assert points[2]["attention"] == points[1]["attention"]
    assert points[3]["attention"] == points[2]["attention"]
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE event_attention_points SET attention=99 WHERE id=?", (points[0]["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM event_attention_points WHERE id=?", (points[0]["id"],))
    store.close()

    reopened = Store(tmp_path / "attention-trajectory.sqlite3")
    assert reopened.db.execute("SELECT COUNT(*) FROM event_attention_points").fetchone()[0] == 4
    reopened.create_event("Legacy event without fabricated history", ["legacy"], 10, now)
    assert reopened.db.execute("SELECT COUNT(*) FROM event_attention_points").fetchone()[0] == 4
    reopened.close()


def test_token_discovery_exposure_preserves_denominator_and_forward_outcomes(tmp_path: Path):
    store = Store(tmp_path / "token-discovery.sqlite3", initial_cash_usd=1000)
    observed_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    token = TokenCandidate(chain="solana", address="D" * 32, name="Discovery Token", symbol="DISC")

    first_round = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="solana",
        started_at=observed_at,
    )
    store.add_token_discovery_exposure(
        first_round, token_id=token.token_id, chain="solana", role="new_pool",
        first_local_discovery=True, new_token=True, observed_at=observed_at,
    )
    store.finish_token_discovery_round(
        first_round, status="completed", requested_count=1, returned_count=1,
        completed_at=observed_at + timedelta(seconds=1),
    )
    empty_round = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="solana",
    )
    store.finish_token_discovery_round(empty_round, status="completed", requested_count=1)
    error_round = store.start_token_discovery_round(
        provider="dexscreener", surface="token_profiles", mode="poll", chain_scope="solana",
    )
    store.finish_token_discovery_round(
        error_round, status="error", requested_count=1, error_type="TimeoutError",
    )

    event_id = store.create_event("Discovery event", ["discovery"], 80, observed_at)
    store.upsert_token(token, seen_at=observed_at)
    decision_at = observed_at + timedelta(minutes=1)
    decision_id = store.add_decision(
        CandidateDecision(
            event_id, token.token_id, "CANDIDATE", 85, 75, 20,
            ["forward discovery"], position_usd=10, created_at=decision_at,
        )
    )
    store.paper_buy(
        event_id=event_id, token=token, price=1, gross_usd=10, fee_bps=60,
        reason="forward-discovery-test", decision_id=decision_id,
        quote_observed_at=decision_at, execution_attempted_at=decision_at,
    )

    summary = store.token_discovery_learning_summary_from_connection(store.db)
    gecko = next(item for item in summary["items"] if item["provider"] == "geckoterminal")
    dex = next(item for item in summary["items"] if item["provider"] == "dexscreener")
    assert summary["status"] == "collecting"
    assert gecko["rounds"] == 2 and gecko["completed_zero_new"] == 1
    assert gecko["first_local_discovery_count"] == 1
    assert gecko["candidate_first_discoveries"] == 1
    assert gecko["paper_bought_first_discoveries"] == 1
    assert gecko["candidate_conversion_rate"] == 1
    assert dex["errors"] == 1 and dex["last_error_type"] == "TimeoutError"
    assert summary["affects"] == "review_only_no_schedule_or_trading_effect"
    store.close()


def test_runtime_restart_reclassifies_only_unfinished_exposure_attempts(tmp_path: Path):
    database = tmp_path / "interrupted-exposure.sqlite3"
    store = Store(database, initial_cash_usd=1000)
    poll_id = store.start_source_poll_attempt(
        collector_kind="rss", source_key="rss:interrupted", platform="rss_news",
    )
    round_id = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
    )
    completed_round = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="solana",
    )
    store.finish_token_discovery_round(completed_round, status="completed", requested_count=1)
    for run_id in ("interrupted-trend", "completed-before-ingestion"):
        store.start_trend_lane_run(
            run_id=run_id, taxonomy_version="fixture", prompt_version="fixture",
            selection_mode="fixture", surge=False, max_web_searches=1,
            started_at=datetime.now(timezone.utc),
            lanes=[{
                "id": "fixture", "prompt": "fixture", "event_topics": ["other"],
                "selection_role": "baseline", "attention_multiplier": 1.0,
                "total_lane_count": 1,
            }],
        )
    store.finish_trend_lane_run("completed-before-ingestion", status="completed")
    store.recover_interrupted_exposure_attempts()
    poll = store.db.execute("SELECT * FROM source_poll_attempts WHERE id=?", (poll_id,)).fetchone()
    interrupted = store.db.execute(
        "SELECT * FROM token_discovery_rounds WHERE id=?", (round_id,)
    ).fetchone()
    completed = store.db.execute(
        "SELECT * FROM token_discovery_rounds WHERE id=?", (completed_round,)
    ).fetchone()
    assert poll["status"] == "error" and poll["error_type"] == "ProcessRestart"
    assert interrupted["status"] == "interrupted"
    assert interrupted["error_type"] == "ProcessRestart"
    assert completed["status"] == "completed" and completed["error_type"] == ""
    interrupted_trend = store.db.execute(
        "SELECT * FROM trend_lane_runs WHERE run_id='interrupted-trend'"
    ).fetchone()
    completed_before_ingestion = store.db.execute(
        "SELECT * FROM trend_lane_runs WHERE run_id='completed-before-ingestion'"
    ).fetchone()
    assert interrupted_trend["status"] == "agent_error"
    assert interrupted_trend["observation_ingestion_status"] == "error"
    assert completed_before_ingestion["status"] == "completed"
    assert completed_before_ingestion["observation_ingestion_status"] == "error"
    assert completed_before_ingestion["error_type"] == "ProcessRestartDuringIngestion"
    store.close()


def test_store_migrates_legacy_source_outcomes_without_backfill(tmp_path: Path):
    database = tmp_path / "legacy-source-outcomes.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE source_utility_outcomes (
            id INTEGER PRIMARY KEY,
            outcome_key TEXT NOT NULL,
            event_id INTEGER NOT NULL,
            token_id TEXT NOT NULL,
            source_observation_id INTEGER NOT NULL,
            dimension TEXT NOT NULL,
            value TEXT NOT NULL,
            origin_platform TEXT NOT NULL,
            attribution_weight REAL NOT NULL,
            net_return REAL NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT NOT NULL,
            UNIQUE(outcome_key,source_observation_id,dimension,value)
        );
        INSERT INTO source_utility_outcomes(
            outcome_key,event_id,token_id,source_observation_id,dimension,value,origin_platform,
            attribution_weight,net_return,opened_at,closed_at
        ) VALUES('legacy',1,'solana:legacy',1,'source','legacy-news','rss',1,0.1,
                 '2026-08-30T00:00:00Z','2026-08-30T01:00:00Z');
        """
    )
    connection.close()

    store = Store(database, initial_cash_usd=1000)
    row = store.db.execute("SELECT * FROM source_utility_outcomes").fetchone()
    assert row["attribution_basis"] == "discovery_lead"
    assert row["attribution_version"] == "legacy-event-window/v1"
    assert row["decision_id"] is None and row["cohort_id"] is None
    assert store.db.execute(
        "SELECT COUNT(*) FROM source_utility_outcomes WHERE attribution_basis='decision_support'"
    ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM paper_source_attribution_attempts"
    ).fetchone()[0] == 0
    store.close()


def test_temporal_guard_rejects_future_and_outcome():
    obs = Observation(
        source="later",
        source_kind="news",
        title="later result",
        observed_at="2026-01-01T02:00:00Z",
        ingested_at="2026-01-01T02:00:01Z",
        availability_proof="fixture_arrival",
        role="outcome",
        raw={"future_return": 20},
    )
    reasons = temporal_rejection_reasons(obs, datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 30)
    assert "observed_after_decision" in reasons
    assert "ingested_after_decision" in reasons
    assert "non_feature_role" in reasons
    assert "forbidden_hindsight_field" in reasons


def test_mastodon_collector_freezes_platform_for_forward_learning(tmp_path: Path):
    class Response:
        def json(self):
            return [{
                "content": "A public viral post",
                "created_at": "2026-08-31T00:00:00Z",
                "url": "https://mastodon.social/@example/1",
                "account": {"acct": "example"},
                "reblogs_count": 4,
                "favourites_count": 9,
            }]

    class Http:
        async def get(self, *args, **kwargs):
            return Response()

    observations = asyncio.run(
        MastodonCollector(Http(), "mastodon-viral", "https://mastodon.social/api/v1/timelines/tag/viral").poll()
    )
    assert len(observations) == 1
    assert observations[0].raw["platform"] == "mastodon"
    store = Store(tmp_path / "mastodon-learning.sqlite3")
    store.add_observation(observations[0])
    summary = store.source_learning_summary()
    assert any(
        item["dimension"] == "platform" and item["value"] == "mastodon"
        for item in summary["items"]
    )
    store.close()


def test_future_token_and_snapshot_are_rejected():
    decision_at = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    token = {
        "created_at": "2026-01-01T00:10:00Z",
        "first_seen_at": "2026-01-01T00:10:10Z",
        "raw": {"winner_token": True},
    }
    snapshot = {
        "observed_at": "2026-01-01T00:11:00Z",
        "raw": {"ath_after_signal": True},
    }
    reasons = token_snapshot_temporal_rejections(token, snapshot, decision_at)
    assert "token_created_after_decision" in reasons
    assert "token_observed_after_decision" in reasons
    assert "snapshot_observed_after_decision" in reasons
    assert "forbidden_hindsight_field:token" in reasons
    assert "forbidden_hindsight_field:snapshot" in reasons


def test_source_learning_records_only_closed_paper_lead_evidence(tmp_path: Path):
    store = Store(tmp_path / "learning.sqlite3", initial_cash_usd=1000)
    now = datetime.now(timezone.utc)
    event_id = store.create_event(
        "Forward mascot event",
        ["mascot"],
        80,
        now - timedelta(minutes=3),
        topic="animals_internet_culture",
    )
    observations = [
        Observation(
            source="browser:x:alpha",
            source_kind="social",
            title="First local post",
            observed_at=now - timedelta(minutes=3),
            ingested_at=now - timedelta(minutes=3),
            role="feature",
            source_item_id="lead-a",
            raw={
                "browser": {"platform": "x"},
                "source_entity_id": "alpha",
                "trend_lane_id": "culture_entertainment",
            },
        ),
        Observation(
            source="news-b",
            source_kind="news",
            title="Independent report within lead window",
            observed_at=now - timedelta(minutes=2, seconds=30),
            ingested_at=now - timedelta(minutes=2, seconds=30),
            role="confirmation",
            source_item_id="lead-b",
        ),
        Observation(
            source="promotion-c",
            source_kind="social",
            title="Context-only promotion",
            observed_at=now - timedelta(minutes=2, seconds=50),
            ingested_at=now - timedelta(minutes=2, seconds=50),
            role="promotion",
            source_item_id="promo",
        ),
        Observation(
            source="delayed-ingestion",
            source_kind="news",
            title="Observed early but ingested after the position opened",
            published_at=now - timedelta(minutes=3),
            observed_at=now - timedelta(minutes=3),
            ingested_at=now + timedelta(minutes=1),
            role="feature",
            source_item_id="delayed-ingestion",
        ),
        Observation(
            source="future-published",
            source_kind="news",
            title="Future publication timestamp",
            published_at=now + timedelta(minutes=1),
            observed_at=now - timedelta(minutes=3),
            ingested_at=now - timedelta(minutes=3),
            role="feature",
            source_item_id="future-published",
        ),
        Observation(
            source="news-b",
            source_kind="news",
            title="A later confirmation from the same source",
            observed_at=now - timedelta(minutes=1),
            ingested_at=now - timedelta(minutes=1),
            role="confirmation",
            source_item_id="late",
        ),
    ]
    ids = []
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
        ids.append(observation_id)
    token = TokenCandidate(chain="solana", address="L" * 32, name="Mascot", symbol="MASC")
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            "solana", token.address, 1.0, 100_000, 100_000, 10_000, 20, 5,
            observed_at=now, ingested_at=now,
        )
    )
    decision = CandidateDecision(
        event_id, token.token_id, "CANDIDATE", 90, 90, 20, ["test"], created_at=now,
    )
    decision_id = store.add_decision(decision)
    cohort_id = store.create_shadow_event_cohort(
        decision, decision_id=decision_id, source_observation_ids=ids,
    )
    assert cohort_id is not None
    store.paper_buy(
        event_id=event_id, token=token, price=1.0, gross_usd=100, fee_bps=0,
        reason="test", decision_id=decision_id, cohort_id=cohort_id,
    )
    store.paper_sell(token.token_id, price=1.1, fraction=0.5, fee_bps=0, reason="partial")
    assert store.db.execute("SELECT COUNT(*) FROM source_utility_outcomes").fetchone()[0] == 0
    store.paper_sell(token.token_id, price=1.2, fraction=1.0, fee_bps=0, reason="close")
    outcome_rows = list(store.db.execute("SELECT * FROM source_utility_outcomes"))
    discovery_rows = [row for row in outcome_rows if row["attribution_basis"] == "discovery_lead"]
    support_rows = [row for row in outcome_rows if row["attribution_basis"] == "decision_support"]
    assert {int(row["source_observation_id"]) for row in discovery_rows} == set(ids[:2])
    assert support_rows == []
    assert all(abs(float(row["attribution_weight"]) - 0.5) < 1e-9 for row in discovery_rows)
    assert all(int(row["decision_id"]) == decision_id for row in outcome_rows)
    assert all(int(row["cohort_id"]) == cohort_id for row in outcome_rows)
    assert all(
        row["attribution_version"] == Store.PAPER_SOURCE_ATTRIBUTION_VERSION
        for row in outcome_rows
    )
    assert all(row["dimension"] != "entity" or row["value"] == "alpha" for row in outcome_rows)
    assert any(
        row["dimension"] == "event_topic" and row["value"] == "animals_internet_culture"
        for row in discovery_rows
    )
    assert not any(
        row["value"] in {"promotion-c", "delayed-ingestion", "future-published", "late-d"}
        for row in discovery_rows
    )
    attempt = store.db.execute("SELECT * FROM paper_source_attribution_attempts").fetchone()
    assert attempt["status"] == "attributed"
    assert attempt["reason"] == "attributed_admitted_cohort"
    assert int(attempt["eligible_source_count"]) == 2

    conservative = store.source_learning_summary()
    assert conservative["status"] == "collecting_samples"
    assert conservative["summary"]["closed_paper_outcomes"] == 1
    assert conservative["summary"]["decision_support_outcomes"] == 0
    assert conservative["summary"]["attributed_closed_outcomes"] == 1
    assert conservative["summary"]["closed_attribution_coverage_rate"] == 1.0
    assert conservative["activation_policy"]["rotation_basis"] == "discovery_lead"
    assert conservative["activation_policy"]["decision_support_affects"] == "descriptive_only"
    relaxed = store.source_learning_summary(
        min_closed_outcomes=0.5,
        min_event_days=1,
        min_losing_outcomes=0,
        entity_min_closed_outcomes=0.5,
        entity_min_event_days=1,
        entity_min_platforms=1,
    )
    assert relaxed["status"] == "learning_active"
    assert any(item["dimension"] == "platform" and item["value"] == "x" for item in relaxed["items"])
    topic_item = next(
        item
        for item in relaxed["items"]
        if item["dimension"] == "event_topic" and item["value"] == "animals_internet_culture"
    )
    assert topic_item["rotation_active"] is False
    assert topic_item["rotation_multiplier"] == 1.0
    lane_item = next(
        item
        for item in relaxed["items"]
        if item["dimension"] == "trend_lane" and item["value"] == "culture_entertainment"
    )
    assert lane_item["rotation_active"] is False
    assert lane_item["rotation_multiplier"] == 1.0
    store.close()


def test_paper_source_attribution_is_exact_tax_aware_and_never_backfills_legacy(tmp_path: Path):
    now = datetime.now(timezone.utc)
    store = Store(tmp_path / "exact-paper-attribution.sqlite3", initial_cash_usd=1000)
    event_id = store.create_event("Exact forward event", ["exact"], 80, now - timedelta(minutes=1))
    observation_id, _ = store.add_observation(
        Observation(
            source="x:exact",
            source_kind="social",
            title="Exact forward feature",
            observed_at=now - timedelta(minutes=1),
            ingested_at=now - timedelta(minutes=1),
            role="feature",
            raw={"platform": "x", "source_entity_id": "exact_person"},
        )
    )
    store.link_event_observation(event_id, observation_id)
    token = TokenCandidate(chain="solana", address="T" * 32, name="Exact", symbol="EXACT")
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            "solana", token.address, 1.0, 100_000, 100_000, 10_000, 20, 5,
            observed_at=now, ingested_at=now,
        )
    )
    decision = CandidateDecision(
        event_id, token.token_id, "CANDIDATE", 90, 90, 20, ["test"], created_at=now,
    )
    decision_id = store.add_decision(decision)
    cohort_id = store.create_shadow_event_cohort(
        decision, decision_id=decision_id, source_observation_ids=[observation_id],
    )
    assert cohort_id is not None
    position = store.paper_buy(
        event_id=event_id, token=token, price=1.0, gross_usd=100, fee_bps=0,
        reason="test", tax_pct=10, decision_id=decision_id, cohort_id=cohort_id,
    )
    assert position.decision_id == decision_id and position.cohort_id == cohort_id
    store.paper_sell(
        token.token_id, price=1.0, fraction=1.0, fee_bps=0, reason="close", tax_pct=10,
    )
    outcome = store.db.execute("SELECT * FROM source_utility_outcomes LIMIT 1").fetchone()
    attempt = store.db.execute("SELECT * FROM paper_source_attribution_attempts").fetchone()
    # BUY tax is already inside gross_usd and reduces acquired quantity; adding it
    # again to buy_cost would double-count it. The later 10% SELL tax reduces 90 to 81.
    assert float(outcome["net_return"]) == pytest.approx(-0.19)
    assert float(attempt["buy_cost_usd"]) == pytest.approx(100.0)
    assert float(attempt["sell_net_usd"]) == pytest.approx(81.0)
    assert float(attempt["net_return"]) == pytest.approx(-0.19)
    trade_links = {
        (int(row["decision_id"]), int(row["cohort_id"]))
        for row in store.db.execute("SELECT decision_id,cohort_id FROM trades")
    }
    assert trade_links == {(decision_id, cohort_id)}

    legacy_token = TokenCandidate(
        chain="solana", address="U" * 32, name="Legacy", symbol="LEGACY",
    )
    store.upsert_token(legacy_token, seen_at=now)
    store.paper_buy(
        event_id=event_id, token=legacy_token, price=1.0, gross_usd=50,
        fee_bps=0, reason="legacy-test",
    )
    store.paper_sell(
        legacy_token.token_id, price=1.1, fraction=1.0, fee_bps=0, reason="legacy-close",
    )
    attempts = list(store.db.execute("SELECT * FROM paper_source_attribution_attempts ORDER BY closed_at"))
    assert len(attempts) == 2
    assert attempts[-1]["status"] == "skipped"
    assert attempts[-1]["reason"] == "legacy_missing_decision"
    assert store.db.execute(
        "SELECT COUNT(DISTINCT outcome_key) FROM source_utility_outcomes"
    ).fetchone()[0] == 1
    store.close()


def test_source_diagnostics_separate_roles_and_require_pre_candidate_timestamps(tmp_path: Path):
    now = datetime.now(timezone.utc)
    candidate_at = now - timedelta(minutes=2)
    store = Store(tmp_path / "source-role-timing.sqlite3")
    event_id = store.create_event("Timed source event", ["timed"], 80, now - timedelta(minutes=5))
    observations = [
        Observation(
            source="mixed-source", source_kind="news", title="Timely feature",
            observed_at=now - timedelta(minutes=4), ingested_at=now - timedelta(minutes=4),
            role="feature",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Timely confirmation",
            observed_at=now - timedelta(minutes=3, seconds=30),
            ingested_at=now - timedelta(minutes=3, seconds=30), role="confirmation",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Identity only",
            observed_at=now - timedelta(minutes=4), ingested_at=now - timedelta(minutes=4),
            role="identity",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Promotion only",
            observed_at=now - timedelta(minutes=4), ingested_at=now - timedelta(minutes=4),
            role="promotion",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Observed after decision",
            observed_at=now - timedelta(minutes=1), ingested_at=now - timedelta(minutes=1),
            role="feature",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Ingested after decision",
            observed_at=now - timedelta(minutes=4), ingested_at=now - timedelta(minutes=1),
            role="feature",
        ),
        Observation(
            source="mixed-source", source_kind="news", title="Published after decision",
            published_at=now - timedelta(minutes=1), observed_at=now - timedelta(minutes=4),
            ingested_at=now - timedelta(minutes=4), role="feature",
        ),
    ]
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
    store.add_decision(
        CandidateDecision(
            event_id, "solana:timed", "CANDIDATE", 90, 90, 20, ["test"],
            created_at=candidate_at,
        )
    )
    summary = store.source_learning_summary()
    item = next(
        row for row in summary["items"]
        if row["dimension"] == "source" and row["value"] == "mixed-source"
    )
    assert item["observations"] == 7
    assert item["feature_observations"] == 4
    assert item["confirmation_observations"] == 1
    assert item["identity_observations"] == 1
    assert item["promotion_observations"] == 1
    assert item["decision_eligible_observations"] == 2
    assert item["eligible_observation_rate"] == pytest.approx(2 / 7, abs=0.0001)
    assert item["candidate_event_count"] == 1
    assert item["early_event_count"] == 1
    store.close()


def test_event_topic_is_deterministic_forward_only_and_immutable(tmp_path: Path):
    assert classify_event_topic("Otter mascot becomes a viral emoji") == "animals_internet_culture"
    assert classify_event_topic("Atlanta teacher's classroom joke goes viral") == "animals_internet_culture"
    assert classify_event_topic("World Cup football final") == "sports"
    assert classify_event_topic("Luis Enrique exchange during PSG match goes viral") == "sports"
    assert classify_event_topic("New AI gaming chip launches") == "ai_tech_gaming"
    assert classify_event_topic("Singer announces a concert") == "celebrity_entertainment"
    assert classify_event_topic("President calls an election") == "political_public_figure"
    assert classify_event_topic("Solana memecoin launches") == "crypto_native"
    assert classify_event_topic("Unclassified local moment") == "other"

    store = Store(tmp_path / "topics.sqlite3")
    event_id = store.create_event("Older event", [], 0)
    assert store.get_event(event_id).topic == "unknown"
    store.update_event(event_id, title="Otter mascot", aliases=["otter"], attention=70)
    assert store.get_event(event_id).topic == "unknown"
    store.close()


def test_watch_account_discovery_review_requires_real_exposure_and_keeps_rotation_inactive(tmp_path: Path):
    store = Store(tmp_path / "account-exposure.sqlite3")
    now = datetime.now(timezone.utc)
    accounts = [
        {
            "platform": "x", "handle": "account_a", "entity_id": "person_a", "priority": 5,
            "watch_cadence": "normal", "selection_role": "exploration",
            "learning_basis": "baseline", "learning_multiplier": 1.0,
        },
        {
            "platform": "x", "handle": "account_b", "entity_id": "person_b", "priority": 4,
            "watch_cadence": "normal", "selection_role": "exploration",
            "learning_basis": "baseline", "learning_multiplier": 1.0,
        },
    ]
    for index in range(20):
        started = now - timedelta(days=index // 2, minutes=index)
        run_id = f"account-run-{index}"
        store.start_trend_lane_run(
            run_id=run_id, taxonomy_version="trend-lanes/v1", prompt_version="test",
            selection_mode="baseline_round_robin", surge=False, max_web_searches=2,
            started_at=started, lanes=[], watch_accounts=accounts,
        )
        store.finish_trend_lane_run(
            run_id, status="completed", finished_at=started + timedelta(minutes=1),
            account_results={
                ("x", "account_a"): {
                    "exact_source_hits": 1 if index < 15 else 0,
                    "accepted_event_count": 1 if index < 15 else 0,
                    "observation_count": 1 if index < 15 else 0,
                },
                ("x", "account_b"): {
                    "exact_source_hits": 1 if index < 5 else 0,
                    "accepted_event_count": 1 if index < 5 else 0,
                    "observation_count": 1 if index < 5 else 0,
                },
            },
        )
    summary = store.watch_account_exposure_summary_from_connection(store.db)
    assert summary["status"] == "shadow_review_available"
    assert summary["summary"]["completed_account_exposures"] == 40
    assert summary["summary"]["exact_source_hits"] == 20
    assert summary["summary"]["review_eligible_accounts"] == 2
    account_a = next(item for item in summary["items"] if item["handle"] == "account_a")
    account_b = next(item for item in summary["items"] if item["handle"] == "account_b")
    assert account_a["run_day_count"] == 10
    assert account_a["zero_yield_completed_exposures"] == 5
    assert account_a["discovery_review_multiplier"] > 1.0
    assert account_b["discovery_review_multiplier"] < 1.0
    assert all(item["rotation_active"] is False for item in summary["items"])
    store.close()


def test_watch_attention_policy_requires_exposure_and_wait_inclusive_market_followup():
    accounts = [
        {"platform": "x", "handle": "alpha", "entity_id": "alpha", "priority": 5},
        {"platform": "x", "handle": "beta", "entity_id": "beta", "priority": 4},
        {
            "platform": "x", "handle": "critical", "entity_id": "critical",
            "priority": 5, "watch_cadence": "critical",
        },
        {"platform": "x", "handle": "collecting", "entity_id": "collecting", "priority": 3},
    ]
    exposure = {
        "items": [
            {
                "platform": "x", "handle": handle, "completed_exposures": 20,
                "discovery_review_eligible": eligible, "discovery_review_multiplier": multiplier,
            }
            for handle, eligible, multiplier in (
                ("alpha", True, 1.10), ("beta", True, 0.90),
                ("critical", True, 1.15), ("collecting", False, 1.0),
            )
        ]
    }
    shadow = {
        "items": [
            {
                "horizon_minutes": 60, "dimension": "entity", "value": entity,
                "shadow_review_eligible": True, "shadow_descriptive_score": score,
                "distinct_event_count": 50, "event_day_count": 20,
                "weighted_negative_outcomes": 10, "mean_raw_return": score,
            }
            for entity, score in (("alpha", 0.10), ("beta", -0.10), ("critical", 0.50))
        ]
    }
    paper = {
        "items": [
            {
                "dimension": "entity", "value": "alpha", "rotation_active": True,
                "rotation_multiplier": 1.10, "distinct_closed_paper_outcomes": 30,
            },
            {
                "dimension": "entity", "value": "beta", "rotation_active": True,
                "rotation_multiplier": 0.90, "distinct_closed_paper_outcomes": 30,
            },
        ]
    }
    policy = Store.build_watch_attention_policy(
        accounts, exposure=exposure, shadow=shadow, paper=paper,
    )
    assert policy["version"] == "watch-attention/v3-experiment-gated"
    assert policy["status"] == "mature_review_only"
    alpha = next(item for item in policy["items"] if item["handle"] == "alpha")
    beta = next(item for item in policy["items"] if item["handle"] == "beta")
    critical = next(item for item in policy["items"] if item["handle"] == "critical")
    collecting = next(item for item in policy["items"] if item["handle"] == "collecting")
    assert alpha["attention_active"] is True and alpha["rotation_active"] is False
    assert beta["attention_active"] is True and beta["rotation_active"] is False
    assert alpha["applied_rotation_multiplier"] == 1.0
    assert beta["applied_rotation_multiplier"] == 1.0
    assert alpha["state"] == "mature_review_waiting_randomized_experiment"
    assert beta["state"] == "mature_review_waiting_randomized_experiment"
    assert critical["attention_active"] is True
    assert critical["rotation_active"] is False
    assert critical["applied_rotation_multiplier"] == 1.0
    assert collecting["state"] == "collecting_account_exposure"
    assert collecting["rotation_active"] is False
    assert policy["activation_policy"]["requires_60m_shadow_followup_review_eligible"] is True
    assert policy["activation_policy"]["requires_preregistered_randomized_attention_experiment"] is True
    assert policy["activation_policy"]["observational_scores_are_descriptive_only"] is True
    assert "decision_eligibility" in policy["activation_policy"]["never_affects"]


def test_trend_attention_policy_requires_joint_maturity_and_bounds_lane_allocation():
    lanes = [
        {"id": "high", "prompt": "high", "event_topics": ["ai_tech_gaming"]},
        {"id": "low", "prompt": "low", "event_topics": ["sports"]},
        {"id": "collecting", "prompt": "collecting", "event_topics": ["crypto_native"]},
    ]
    exposure = {
        "summary": {"lane_exposures": 60, "accepted_events": 40},
        "items": [
            {
                "lane_id": lane_id, "completed_exposures": 20, "run_day_count": 10,
                "zero_yield_completed_exposures": 5, "accepted_events": accepted,
            }
            for lane_id, accepted in (("high", 30), ("low", 5), ("collecting", 5))
        ],
    }
    shadow = {
        "items": [
            {
                "horizon_minutes": 60, "dimension": "trend_lane", "value": lane_id,
                "shadow_review_eligible": True, "shadow_descriptive_score": score,
                "distinct_event_count": 30, "event_day_count": 15,
                "weighted_negative_outcomes": 8, "mean_raw_return": score,
            }
            for lane_id, score in (("high", 0.30), ("low", -0.30))
        ]
    }
    paper = {
        "items": [
            {
                "dimension": "trend_lane", "value": "high",
                "paper_mean_net_return": 0.20, "distinct_closed_paper_outcomes": 30,
                "event_day_count": 15, "weighted_losing_paper_outcomes": 8,
            }
        ]
    }
    policy = Store.build_trend_attention_policy(
        lanes, exposure=exposure, shadow=shadow, paper=paper,
    )
    assert policy["version"] == "trend-attention/v2-experiment-gated"
    assert policy["status"] == "mature_waiting_for_randomized_experiment"
    assert policy["summary"]["schedule_activation_available"] is False
    assert policy["summary"]["actual_schedule_changed_by_learning"] is False
    high = next(item for item in policy["items"] if item["lane_id"] == "high")
    low = next(item for item in policy["items"] if item["lane_id"] == "low")
    collecting = next(item for item in policy["items"] if item["lane_id"] == "collecting")
    assert high["applied_schedule_multiplier"] == 1.0
    assert low["applied_schedule_multiplier"] == 1.0
    assert high["state"] == "mature_waiting_for_randomized_experiment"
    assert low["state"] == "mature_waiting_for_randomized_experiment"
    assert high["paper_multiplier"] > 1.0
    assert collecting["schedule_active"] is False
    assert collecting["state"] == "collecting_market_followup"
    assert policy["activation_policy"]["minimum_round_robin_exploration_lanes_per_run"] == 1
    assert policy["activation_policy"]["requires_preregistered_randomized_attention_experiment"] is True
    assert "live_trading" in policy["activation_policy"]["never_affects"]


def test_watch_attention_requires_exact_entity_and_never_uses_platform_fallback():
    accounts = [
        {"platform": "x", "handle": "alpha_x", "entity_id": "alpha", "priority": 4},
        {
            "platform": "bluesky", "handle": "alpha.bsky.social",
            "entity_id": "alpha", "priority": 4,
        },
        {"platform": "x", "handle": "route_only", "priority": 3},
        {"platform": "reddit", "handle": "untested_route", "priority": 3},
    ]
    exposure = {
        "items": [
            {
                "platform": platform, "handle": handle,
                "discovery_review_eligible": eligible,
                "discovery_review_multiplier": multiplier,
                "completed_exposures": completed,
            }
            for platform, handle, eligible, multiplier, completed in (
                ("x", "alpha_x", True, 1.10, 20),
                ("bluesky", "alpha.bsky.social", False, 1.0, 5),
                ("x", "route_only", True, 0.95, 20),
                ("reddit", "untested_route", True, 1.0, 20),
            )
        ]
    }
    shadow = {
        "items": [
            {
                "horizon_minutes": 60, "dimension": "entity", "value": "alpha",
                "shadow_review_eligible": True, "shadow_descriptive_score": 0.10,
                "distinct_event_count": 50, "event_day_count": 20,
                "weighted_negative_outcomes": 8, "platform_count": 2,
            },
            {
                "horizon_minutes": 60, "dimension": "platform", "value": "x",
                "shadow_review_eligible": True, "shadow_descriptive_score": -0.05,
                "distinct_event_count": 30, "event_day_count": 15,
                "weighted_negative_outcomes": 8, "platform_count": 1,
            },
        ]
    }
    policy = Store.build_watch_attention_policy(
        accounts, exposure=exposure, shadow=shadow, paper={"items": []},
    )
    alpha_x = next(item for item in policy["items"] if item["handle"] == "alpha_x")
    alpha_bluesky = next(
        item for item in policy["items"] if item["handle"] == "alpha.bsky.social"
    )
    route_only = next(item for item in policy["items"] if item["handle"] == "route_only")
    untested_route = next(
        item for item in policy["items"] if item["handle"] == "untested_route"
    )
    assert alpha_x["attention_active"] is True and alpha_x["market_basis"] == "entity"
    assert alpha_x["rotation_active"] is False
    assert alpha_x["applied_rotation_multiplier"] == 1.0
    assert alpha_bluesky["market_basis"] == "entity"
    assert alpha_bluesky["rotation_active"] is False
    assert alpha_bluesky["state"] == "collecting_account_exposure"
    assert route_only["rotation_active"] is False and route_only["market_basis"] is None
    assert route_only["state"] == "missing_exact_entity_mapping"
    assert untested_route["rotation_active"] is False
    assert untested_route["state"] == "missing_exact_entity_mapping"
    assert policy["summary"]["rotation_activation_available"] is False
    assert policy["summary"]["actual_rotation_changed_by_learning"] is False
    assert policy["activation_policy"]["platform_fallback_for_accounts"] is False


def test_preregistered_attention_experiment_balances_assignments_and_never_auto_promotes(
    tmp_path: Path,
):
    store = Store(tmp_path / "attention-experiment.sqlite3")
    accounts = [
        {
            "platform": "x", "handle": "openai", "entity_id": "openai",
            "priority": 5, "watch_cadence": "normal", "enabled": True,
        },
        {
            "platform": "x", "handle": "anthropic", "entity_id": "anthropic",
            "priority": 5, "watch_cadence": "normal", "enabled": True,
        },
    ]
    assert store.register_attention_experiment(
        experiment_id="watch-openai-vs-anthropic-20260831",
        hypothesis="OpenAI public posts produce more independent decision-eligible events per completed watch exposure.",
        challenger=accounts[0],
        control=accounts[1],
        random_seed="0123456789abcdef0123456789abcdef",
    ) is True
    assert store.register_attention_experiment(
        experiment_id="watch-openai-vs-anthropic-20260831",
        hypothesis="duplicate",
        challenger=accounts[0],
        control=accounts[1],
        random_seed="fedcba9876543210fedcba9876543210",
    ) is False
    store.set_attention_experiment_state(
        "watch-openai-vs-anthropic-20260831", "activated", reason="manual preregistration review",
    )

    arms: list[str] = []
    for index in range(8):
        run_id = f"attention-run-{index}"
        assignment = store.reserve_attention_experiment_assignment(
            run_id=run_id, accounts=accounts,
        )
        assert assignment is not None
        assert assignment["assignment_probability"] == 0.5
        arms.append(str(assignment["arm"]))
        chosen = next(
            account for account in accounts
            if account["handle"] == assignment["target_handle_key"]
        )
        store.start_trend_lane_run(
            run_id=run_id,
            taxonomy_version="fixture",
            prompt_version="fixture",
            selection_mode="fixture",
            surge=False,
            max_web_searches=1,
            started_at=datetime.now(timezone.utc) + timedelta(days=index),
            lanes=[{
                "id": "fixture", "prompt": "fixture", "event_topics": ["other"],
                "selection_role": "baseline", "attention_multiplier": 1.0,
                "total_lane_count": 1,
            }],
            watch_accounts=[{
                **chosen,
                "selection_role": f"experiment_{assignment['arm']}",
                "learning_basis": Store.ATTENTION_EXPERIMENT_VERSION,
                "learning_multiplier": 1.0,
            }],
        )
        store.finish_trend_lane_run(
            run_id,
            status="completed",
            account_results={("x", chosen["handle"]): {
                "exact_source_hits": 0,
                "accepted_event_count": 0,
                "observation_count": 0,
            }},
        )
        store.finalize_trend_lane_observation_ingestion(run_id, status="completed")

    assert arms[:4].count("challenger") == 2
    assert arms[:4].count("control") == 2
    assert arms[4:].count("challenger") == 2
    assert arms[4:].count("control") == 2
    summary = Store.attention_experiment_summary_from_connection(store.db)
    assert summary["status"] == "collecting_stage1"
    assert summary["arms"]["challenger"]["completed"] == 4
    assert summary["arms"]["control"]["completed"] == 4
    assert summary["arms"]["challenger"]["zero_yield_completed_exposures"] == 4
    assert summary["arms"]["control"]["zero_yield_completed_exposures"] == 4
    assert summary["automatic_promotion"] is False
    assert summary["holdout_required"] is True
    assert summary["actual_multiplier"] == 1.0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE attention_experiments SET hypothesis='changed' WHERE experiment_id=?",
            ("watch-openai-vs-anthropic-20260831",),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "DELETE FROM attention_experiment_assignments WHERE run_id='attention-run-0'",
        )
    store.close()


def test_attention_experiment_uses_exact_links_excludes_collisions_and_rejects_future_ingestion(
    tmp_path: Path,
):
    store = Store(tmp_path / "attention-outcomes.sqlite3")
    now = datetime.now(timezone.utc)
    accounts = [
        {
            "platform": "x", "handle": "openai", "entity_id": "openai",
            "priority": 5, "watch_cadence": "normal", "enabled": True,
        },
        {
            "platform": "x", "handle": "anthropic", "entity_id": "anthropic",
            "priority": 5, "watch_cadence": "normal", "enabled": True,
        },
    ]
    experiment_id = "watch-exact-forward-outcome"
    store.register_attention_experiment(
        experiment_id=experiment_id,
        hypothesis="fixture",
        challenger=accounts[0],
        control=accounts[1],
        random_seed="0123456789abcdef0123456789abcdef",
        registered_at=now - timedelta(minutes=5),
    )
    store.set_attention_experiment_state(
        experiment_id, "activated", reason="fixture", effective_at=now - timedelta(minutes=4),
    )

    assignments: dict[str, tuple[str, dict[str, object]]] = {}
    for index in range(4):
        run_id = f"exact-run-{index}"
        assignment = store.reserve_attention_experiment_assignment(
            run_id=run_id, accounts=accounts, assigned_at=now - timedelta(minutes=3),
        )
        assert assignment is not None
        chosen = next(
            account for account in accounts
            if account["handle"] == assignment["target_handle_key"]
        )
        store.start_trend_lane_run(
            run_id=run_id, taxonomy_version="fixture", prompt_version="fixture",
            selection_mode="fixture", surge=False, max_web_searches=1,
            started_at=now - timedelta(minutes=3),
            lanes=[{
                "id": "fixture", "prompt": "fixture", "event_topics": ["other"],
                "selection_role": "baseline", "attention_multiplier": 1.0,
                "total_lane_count": 1,
            }],
            watch_accounts=[chosen],
        )
        store.finish_trend_lane_run(
            run_id, status="completed",
            account_results={("x", chosen["handle"]): {
                "exact_source_hits": 1, "accepted_event_count": 1, "observation_count": 1,
            }},
            finished_at=now - timedelta(minutes=2),
        )
        store.finalize_trend_lane_observation_ingestion(
            run_id, status="completed", finalized_at=now - timedelta(minutes=2),
        )
        assignments.setdefault(str(assignment["arm"]), (run_id, chosen))
    assert set(assignments) == {"challenger", "control"}

    collision_event = store.create_event(
        "Cross-arm shared event", ["shared"], 80, now - timedelta(minutes=2),
    )
    collision_observation_ids = []
    for arm, (run_id, account) in assignments.items():
        observation = Observation(
            source=f"agent-scout:{arm}", source_kind="social", title="Shared post",
            url=f"https://x.com/{account['handle']}/status/{arm}",
            observed_at=now - timedelta(minutes=2),
            ingested_at=now - timedelta(minutes=2), role="feature",
            source_item_id=f"shared-{arm}",
        )
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(collision_event, observation_id)
        collision_observation_ids.append(observation_id)
        assert store.record_attention_experiment_observation(
            run_id=run_id, platform="x", handle=str(account["handle"]),
            entity_id=str(account["entity_id"]), observation_id=observation_id,
            event_id=collision_event, decision_eligible=True,
            observed_at=observation.observed_at,
        ) is True
    token = TokenCandidate(chain="solana", address="C" * 32, name="Shared", symbol="SHR")
    store.upsert_token(token, seen_at=now - timedelta(minutes=1))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50_000,
        market_cap_usd=100_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
        observed_at=now - timedelta(seconds=10), ingested_at=now - timedelta(seconds=9),
        provider="fixture",
    ))
    collision_decision = CandidateDecision(
        collision_event, token.token_id, "WAIT", 70, 80, 1, ["fixture"], ["fixture"],
        created_at=now,
    )
    collision_decision_id = store.add_decision(collision_decision)
    collision_shadow_id = store.create_shadow_event_cohort(
        collision_decision,
        decision_id=collision_decision_id,
        source_observation_ids=collision_observation_ids,
    )
    assert collision_shadow_id is not None
    assert store.create_attention_experiment_event_cohort(
        event_id=collision_event,
        decision_id=collision_decision_id,
        shadow_cohort_id=collision_shadow_id,
    ) == 1

    run_id, account = assignments["challenger"]
    forward_event = store.create_event(
        "Single-arm forward event", ["forward"], 82, now + timedelta(minutes=1),
    )
    exact = Observation(
        source="agent-scout:x.com", source_kind="social", title="Exact post",
        url=f"https://x.com/{account['handle']}/status/forward",
        observed_at=now + timedelta(minutes=1), ingested_at=now + timedelta(minutes=1),
        role="feature", source_item_id="forward-exact",
    )
    exact_id, _ = store.add_observation(exact)
    store.link_event_observation(forward_event, exact_id)
    confirmation = Observation(
        source="news-confirmation", source_kind="news", title="Independent confirmation",
        observed_at=now + timedelta(minutes=1), ingested_at=now + timedelta(minutes=1),
        role="confirmation", source_item_id="forward-confirmation",
    )
    confirmation_id, _ = store.add_observation(confirmation)
    store.link_event_observation(forward_event, confirmation_id)
    assert store.record_attention_experiment_observation(
        run_id=run_id, platform="x", handle=str(account["handle"]),
        entity_id=str(account["entity_id"]), observation_id=exact_id,
        event_id=forward_event, decision_eligible=True, observed_at=exact.observed_at,
    ) is True
    assert store.record_attention_experiment_observation(
        run_id=run_id, platform="x", handle="wrong-handle",
        entity_id=str(account["entity_id"]), observation_id=confirmation_id,
        event_id=forward_event, decision_eligible=True, observed_at=confirmation.observed_at,
    ) is False
    forward_token = TokenCandidate(
        chain="solana", address="F" * 32, name="Forward", symbol="FWD",
    )
    decision_at = now + timedelta(minutes=2)
    store.upsert_token(forward_token, seen_at=now + timedelta(minutes=1))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=forward_token.address, price_usd=1.0, liquidity_usd=50_000,
        market_cap_usd=100_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
        observed_at=decision_at - timedelta(seconds=10),
        ingested_at=decision_at - timedelta(seconds=9), provider="fixture",
    ))
    forward_decision = CandidateDecision(
        forward_event, forward_token.token_id, "WAIT", 70, 80, 1,
        ["fixture"], ["fixture"], created_at=decision_at,
    )
    forward_decision_id = store.add_decision(forward_decision)
    forward_shadow_id = store.create_shadow_event_cohort(
        forward_decision,
        decision_id=forward_decision_id,
        source_observation_ids=[exact_id, confirmation_id],
    )
    assert forward_shadow_id is not None
    assert store.create_attention_experiment_event_cohort(
        event_id=forward_event,
        decision_id=forward_decision_id,
        shadow_cohort_id=forward_shadow_id,
    ) == 1
    target = decision_at + timedelta(minutes=60)
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=forward_token.address, price_usd=9.0, liquidity_usd=50_000,
        market_cap_usd=100_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
        observed_at=target + timedelta(minutes=5),
        ingested_at=target - timedelta(minutes=1), provider="future-fixture",
    ))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=forward_token.address, price_usd=1.1, liquidity_usd=50_000,
        market_cap_usd=100_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
        observed_at=target + timedelta(minutes=10),
        ingested_at=target + timedelta(minutes=11), provider="valid-fixture",
    ))
    result = store.finalize_attention_experiment_outcomes(now=target + timedelta(minutes=20))
    assert result["observed"] == 1
    assert result["excluded"] == 1
    rows = list(store.db.execute(
        """
        SELECT c.event_id,o.status,o.outcome_price FROM attention_experiment_event_cohorts c
        JOIN attention_experiment_outcomes o ON o.cohort_id=c.id
        ORDER BY c.event_id
        """
    ))
    by_event = {int(row["event_id"]): row for row in rows}
    assert by_event[collision_event]["status"] == "cross_arm_collision"
    assert by_event[forward_event]["status"] == "observed"
    assert by_event[forward_event]["outcome_price"] == pytest.approx(1.1)
    summary = Store.attention_experiment_summary_from_connection(store.db)
    assert summary["inference"]["cross_arm_collision_events"] == 1
    assert summary["automatic_promotion"] is False
    assert summary["actual_multiplier"] == 1.0
    store.close()


def test_shadow_event_followup_is_forward_only_fixed_horizon_and_non_activating(tmp_path: Path):
    store = Store(tmp_path / "shadow-followup.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = store.create_event(
        "Viral rescue mascot",
        ["rescue", "mascot"],
        82,
        now - timedelta(minutes=2),
        topic="animals_internet_culture",
    )
    observations = [
        Observation(
            source="browser:x:alpha",
            source_kind="social",
            title="Original mascot post",
            observed_at=now - timedelta(minutes=2),
            ingested_at=now - timedelta(minutes=2),
            role="feature",
            source_item_id="shadow-lead-a",
            raw={
                "browser": {"platform": "x"},
                "source_entity_id": "alpha",
                "trend_lane_id": "culture_entertainment",
            },
        ),
        Observation(
            source="news-confirmation",
            source_kind="news",
            title="Independent confirmation",
            observed_at=now - timedelta(minutes=1, seconds=30),
            ingested_at=now - timedelta(minutes=1, seconds=30),
            role="confirmation",
            source_item_id="shadow-lead-b",
        ),
        Observation(
            source="future-ingestion",
            source_kind="news",
            title="Not locally available at the decision",
            observed_at=now - timedelta(minutes=1, seconds=50),
            ingested_at=now + timedelta(minutes=1),
            role="feature",
            source_item_id="shadow-future",
        ),
        Observation(
            source="late-confirmation",
            source_kind="news",
            title="Outside the frozen lead window",
            observed_at=now,
            ingested_at=now,
            role="confirmation",
            source_item_id="shadow-late",
        ),
    ]
    observation_ids = []
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
        observation_ids.append(observation_id)
    token = TokenCandidate(chain="solana", address="S" * 32, name="Rescue", symbol="RSC")
    store.upsert_token(token, seen_at=now - timedelta(minutes=1))
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
            observed_at=now - timedelta(seconds=10),
            ingested_at=now - timedelta(seconds=9), provider="fixture",
        )
    )
    decision = CandidateDecision(
        event_id, token.token_id, "WAIT", 70, 90, 2, ["match=90"], ["canonical_token_ambiguous"],
        created_at=now,
    )
    decision_id = store.add_decision(decision)
    cohort_id = store.create_shadow_event_cohort(
        decision,
        decision_id=decision_id,
        source_observation_ids=observation_ids,
    )
    assert cohort_id is not None
    admission = store.db.execute(
        "SELECT * FROM shadow_event_admission_attempts WHERE decision_id=?", (decision_id,)
    ).fetchone()
    assert admission["status"] == "created"
    assert admission["reason"] == "created"
    assert admission["cohort_id"] == cohort_id
    assert admission["eligible_source_count"] == 2
    cohort = store.db.execute("SELECT * FROM shadow_event_cohorts WHERE id=?", (cohort_id,)).fetchone()
    assert cohort["action"] == "WAIT"
    assert cohort["eligible_source_count"] == 2
    labels = list(store.db.execute("SELECT * FROM shadow_event_cohort_labels WHERE cohort_id=?", (cohort_id,)))
    assert {
        row["source_observation_id"] for row in labels if row["source_observation_id"] > 0
    } == set(observation_ids[:2])
    assert any(row["dimension"] == "entity" and row["value"] == "alpha" for row in labels)
    assert any(
        row["dimension"] == "trend_lane" and row["value"] == "culture_entertainment"
        for row in labels
    )
    assert any(
        row["source_observation_id"] == 0
        and row["dimension"] == "attention_bucket"
        and row["value"] == "70_84"
        for row in labels
    )
    assert any(
        row["source_observation_id"] == 0
        and row["dimension"] == "decision_reason"
        and row["value"] == "canonical_token_ambiguous"
        for row in labels
    )
    assert abs(sum(row["attribution_weight"] for row in labels if row["dimension"] == "source_kind") - 1.0) < 1e-9
    with store.db:
        store.db.execute(
            "UPDATE shadow_event_cohorts SET version=?,cohort_key=? WHERE id=?",
            ("shadow-event-followup/v1", "legacy-wait-cohort", cohort_id),
        )

    repeated = CandidateDecision(event_id, token.token_id, "CANDIDATE", 80, 92, 8, ["later"], created_at=now)
    repeated_id = store.add_decision(repeated)
    candidate_cohort_id = store.create_shadow_event_cohort(
        repeated,
        decision_id=repeated_id,
        source_observation_ids=observation_ids,
    )
    assert candidate_cohort_id is not None and candidate_cohort_id != cohort_id
    assert store.create_shadow_event_cohort(
        repeated,
        decision_id=repeated_id,
        source_observation_ids=observation_ids,
    ) == candidate_cohort_id
    assert store.create_shadow_event_cohort(
        decision,
        decision_id=decision_id,
        source_observation_ids=observation_ids,
    ) == cohort_id
    assert store.db.execute("SELECT COUNT(*) FROM shadow_event_cohorts").fetchone()[0] == 2
    assert store.db.execute(
        "SELECT COUNT(*) FROM shadow_event_admission_attempts"
    ).fetchone()[0] == 2

    for minutes, price in ((10, 0.5), (16, 2.0), (61, 1.5)):
        store.add_snapshot(
            TokenSnapshot(
                chain="solana", address=token.address, price_usd=price, liquidity_usd=50_000,
                market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
                observed_at=now + timedelta(minutes=minutes),
                ingested_at=now + timedelta(minutes=minutes), provider="fixture",
            )
        )
    first = store.finalize_shadow_event_outcomes(now=now + timedelta(minutes=17))
    assert first["outcomes_observed"] == 2
    store.finalize_shadow_event_outcomes(now=now + timedelta(minutes=62))
    final = store.finalize_shadow_event_outcomes(now=now + timedelta(minutes=271))
    assert final["outcomes_missing"] == 2 and final["cohorts_completed"] == 2
    outcomes = list(
        store.db.execute(
            "SELECT * FROM shadow_event_outcomes WHERE cohort_id=? ORDER BY horizon_minutes",
            (cohort_id,),
        )
    )
    assert [(row["horizon_minutes"], row["status"]) for row in outcomes] == [
        (15, "observed"), (60, "observed"), (240, "missing")
    ]
    assert outcomes[0]["raw_return"] == pytest.approx(1.0)
    assert outcomes[0]["maximum_return"] == pytest.approx(1.0)
    assert outcomes[0]["minimum_return"] == pytest.approx(-0.5)
    assert outcomes[1]["raw_return"] == pytest.approx(0.5)
    assert outcomes[2]["raw_return"] is None
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=0.75, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
            observed_at=now + timedelta(minutes=241),
            ingested_at=now + timedelta(minutes=241), provider="late-fixture",
        )
    )
    store.finalize_shadow_event_outcomes(now=now + timedelta(minutes=272))
    frozen = store.db.execute(
        "SELECT status,raw_return FROM shadow_event_outcomes WHERE cohort_id=? AND horizon_minutes=240",
        (cohort_id,),
    ).fetchone()
    assert frozen["status"] == "missing" and frozen["raw_return"] is None

    summary = store.shadow_event_learning_summary_from_connection(store.db)
    assert summary["status"] == "collecting_followup"
    assert summary["summary"]["cohorts"] == 2
    assert summary["summary"]["complete_cohorts"] == 2
    assert summary["observed_versions"] == [
        "shadow-event-followup/v1", "shadow-event-followup/v3-strategy-labels"
    ]
    entity_60m = next(
        item for item in summary["items"]
        if item["dimension"] == "entity" and item["value"] == "alpha" and item["horizon_minutes"] == 60
    )
    assert entity_60m["mean_raw_return"] == pytest.approx(0.5)
    assert entity_60m["wait_cohort_count"] == 1
    assert entity_60m["candidate_cohort_count"] == 0
    assert entity_60m["distinct_cohort_count"] == 1
    assert entity_60m["shadow_review_eligible"] is False
    assert entity_60m["rotation_active"] is False
    assert summary["analysis_unit"] == "earliest_forward_cohort_per_independent_event"
    store.close()


def test_shadow_event_admission_ledger_records_forward_skip_reasons_and_coverage(tmp_path: Path):
    store = Store(tmp_path / "shadow-admission.sqlite3")
    now = datetime.now(timezone.utc)
    token = TokenCandidate(chain="solana", address="A" * 32, name="Admission")
    store.upsert_token(token, seen_at=now)

    missing_snapshot_event = store.create_event("Missing snapshot", ["missing snapshot"], 60, now)
    missing_snapshot = CandidateDecision(
        missing_snapshot_event, token.token_id, "WAIT", 60, 80, 2, ["test"], created_at=now
    )
    missing_snapshot_id = store.add_decision(missing_snapshot)
    assert store.create_shadow_event_cohort(
        missing_snapshot, decision_id=missing_snapshot_id, source_observation_ids=[]
    ) is None
    assert store.create_shadow_event_cohort(
        missing_snapshot, decision_id=missing_snapshot_id, source_observation_ids=[]
    ) is None
    row = store.db.execute(
        "SELECT * FROM shadow_event_admission_attempts WHERE decision_id=?",
        (missing_snapshot_id,),
    ).fetchone()
    assert row["reason"] == "missing_entry_snapshot"

    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
            observed_at=now, ingested_at=now, provider="fixture",
        )
    )
    candidate_event = store.create_event("Candidate first", ["candidate first"], 80, now)
    observation_id, _ = store.add_observation(
        Observation(
            source="fixture-news", source_kind="news", title="Candidate first",
            observed_at=now, ingested_at=now, role="feature", source_item_id="candidate-first",
        )
    )
    store.link_event_observation(candidate_event, observation_id)
    candidate = CandidateDecision(
        candidate_event, token.token_id, "CANDIDATE", 82, 92, 12, ["test"], created_at=now
    )
    candidate_id = store.add_decision(candidate)
    candidate_cohort_id = store.create_shadow_event_cohort(
        candidate, decision_id=candidate_id, source_observation_ids=[observation_id]
    )
    assert candidate_cohort_id is not None

    later_wait = CandidateDecision(
        candidate_event, token.token_id, "WAIT", 70, 85, 5, ["later"],
        created_at=now + timedelta(seconds=1),
    )
    later_wait_id = store.add_decision(later_wait)
    assert store.create_shadow_event_cohort(
        later_wait, decision_id=later_wait_id, source_observation_ids=[observation_id]
    ) == candidate_cohort_id
    row = store.db.execute(
        "SELECT * FROM shadow_event_admission_attempts WHERE decision_id=?", (later_wait_id,)
    ).fetchone()
    assert row["status"] == "already_admitted"
    assert row["reason"] == "wait_superseded_by_candidate"

    missing_observation_event = store.create_event(
        "Missing observations", ["missing observations"], 60, now
    )
    missing_observation = CandidateDecision(
        missing_observation_event, token.token_id, "WAIT", 60, 80, 2, ["test"], created_at=now
    )
    missing_observation_id = store.add_decision(missing_observation)
    assert store.create_shadow_event_cohort(
        missing_observation, decision_id=missing_observation_id, source_observation_ids=[]
    ) is None
    row = store.db.execute(
        "SELECT * FROM shadow_event_admission_attempts WHERE decision_id=?",
        (missing_observation_id,),
    ).fetchone()
    assert row["reason"] == "missing_observation_ids"

    admission = store.shadow_event_admission_summary_from_connection(store.db)
    assert admission["summary"]["attempts"] == 4
    assert admission["summary"]["candidate_instrumented"] == 1
    assert admission["summary"]["candidate_covered"] == 1
    assert admission["summary"]["forward_candidate_coverage_rate"] == 1.0
    assert admission["summary"]["legacy_or_uninstrumented_decisions"] == 0
    store.close()


def test_shadow_reject_cohort_freezes_strategy_labels_and_rejects_preloaded_future(
    tmp_path: Path,
):
    store = Store(tmp_path / "shadow-reject.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = store.create_event(
        "Public figure narrative",
        ["public figure"],
        91,
        now - timedelta(minutes=2),
        topic="political_public_figure",
    )
    observation_id, _ = store.add_observation(
        Observation(
            source="browser:x:verified",
            source_kind="official_social",
            title="Exact original observation",
            observed_at=now - timedelta(minutes=2),
            ingested_at=now - timedelta(minutes=2),
            role="feature",
            source_item_id="reject-public-figure",
            raw={
                "platform": "x",
                "source_entity_id": "verified_figure",
                "account_type": "public_figure",
                "verification_status": "browser_exact_entity_observation",
            },
        )
    )
    store.link_event_observation(event_id, observation_id)
    token = TokenCandidate(
        chain="solana", address="R" * 32, name="Rejected",
        created_at=now - timedelta(minutes=3),
    )
    store.upsert_token(token, seen_at=now - timedelta(minutes=2))
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=4_000,
            market_cap_usd=40_000, volume_5m_usd=800, buys_5m=3, sells_5m=12,
            honeypot=True, sellable=False, observed_at=now - timedelta(seconds=5),
            ingested_at=now - timedelta(seconds=4), provider="fixture",
        )
    )
    decision = CandidateDecision(
        event_id, token.token_id, "REJECT", 58, 86, 4, ["test"], ["honeypot"],
        created_at=now,
    )
    decision_id = store.add_decision(decision)
    cohort_id = store.create_shadow_event_cohort(
        decision, decision_id=decision_id, source_observation_ids=[observation_id]
    )
    assert cohort_id is not None
    labels = {
        (row["dimension"], row["value"])
        for row in store.db.execute(
            "SELECT dimension,value FROM shadow_event_cohort_labels WHERE cohort_id=?",
            (cohort_id,),
        )
    }
    assert ("public_figure_context", "verified_original_observation") in labels
    assert ("safety_state", "honeypot") in labels
    assert ("attention_bucket", "85_plus") in labels
    assert ("decision_reason", "honeypot") in labels

    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=99.0, liquidity_usd=4_000,
            market_cap_usd=40_000, volume_5m_usd=800, buys_5m=3, sells_5m=12,
            observed_at=now + timedelta(minutes=16),
            ingested_at=now + timedelta(minutes=1), provider="preloaded-future",
        )
    )
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=0.8, liquidity_usd=4_000,
            market_cap_usd=32_000, volume_5m_usd=600, buys_5m=2, sells_5m=10,
            observed_at=now + timedelta(minutes=17),
            ingested_at=now + timedelta(minutes=17), provider="valid-forward",
        )
    )
    result = store.finalize_shadow_event_outcomes(now=now + timedelta(minutes=18))
    assert result["outcomes_observed"] == 1
    outcome = store.db.execute(
        "SELECT * FROM shadow_event_outcomes WHERE cohort_id=? AND horizon_minutes=15",
        (cohort_id,),
    ).fetchone()
    assert outcome["outcome_price"] == pytest.approx(0.8)
    assert outcome["raw_return"] == pytest.approx(-0.2)
    assert outcome["maximum_return"] == pytest.approx(0.0)
    assert outcome["minimum_return"] == pytest.approx(-0.2)
    summary = store.shadow_event_learning_summary_from_connection(store.db)
    assert summary["summary"]["reject_cohorts"] == 1
    assert summary["admission"]["summary"]["reject_covered"] == 1
    store.close()


def test_shadow_admission_summary_marks_pre_schema_candidate_uninstrumented():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE decisions(id INTEGER PRIMARY KEY,action TEXT NOT NULL,created_at TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO decisions(action,created_at) VALUES('CANDIDATE',?)",
        (datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),),
    )
    summary = Store.shadow_event_admission_summary_from_connection(connection)
    assert summary["status"] == "not_instrumented"
    assert summary["summary"]["candidate_decisions"] == 1
    assert summary["summary"]["candidate_legacy_or_uninstrumented"] == 1
    assert summary["summary"]["forward_candidate_coverage_rate"] is None
    connection.close()


def test_token_context_outcomes_are_forward_only_safe_labeled_and_non_activating(tmp_path: Path):
    path = tmp_path / "token-context-followup.sqlite3"
    store = Store(path)
    now = datetime.now(timezone.utc)
    token = TokenCandidate(chain="solana", address="C" * 32, name="Context", symbol="CTX")
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
            observed_at=now, ingested_at=now, provider="fixture",
        )
    )
    assessment = {
        "version": "token-context-assessment/v1",
        "decision_eligible": False,
        "investigation_trigger": {
            "kind": "high_impact_account_post",
            "verification_status": "browser_exact_entity_observation",
            "entity_id": "elon_musk",
            "platform": "x",
            "endorsement_inferred": False,
        },
        "project_claims": {"status": "project_attached_unverified"},
        "community_amplification": {
            "status": "project_channels_only", "platforms": ["x", "telegram"],
        },
        "public_figure_linkage": {
            "status": "unverified_candidates",
            "items": [{"person": "Elon Musk", "platform": "x", "endorsement_inferred": False}],
        },
        "independent_reporting": {
            "status": "not_decision_eligible", "domains": ["unverified.example"],
        },
        "onchain_momentum": {"momentum_score": 84},
    }
    assessment_id = store.add_token_context_assessment(
        token.token_id,
        trigger="high_impact_account_post",
        status="insufficient_verified_sources",
        snapshot_observed_at=now,
        momentum_score=84,
        assessment=assessment,
        assessed_at=now,
    )
    cohort = store.db.execute(
        "SELECT * FROM token_context_outcome_cohorts WHERE assessment_id=?", (assessment_id,)
    ).fetchone()
    assert cohort is not None
    assert cohort["entry_snapshot_at"] <= cohort["assessed_at"]
    assert cohort["trigger_kind"] == "high_impact_account_post"
    labels = {
        (row["dimension"], row["value"])
        for row in store.db.execute(
            "SELECT dimension,value FROM token_context_outcome_labels WHERE cohort_id=?",
            (int(cohort["id"]),),
        )
    }
    assert ("verified_public_figure_entity", "elon_musk") in labels
    assert ("verified_original_public_figure_post", "present") in labels
    assert ("community_platform", "telegram") in labels
    assert ("independent_reporting_domain_count", "0") in labels
    assert all("elon musk" not in value and "unverified.example" not in value for _, value in labels)

    untracked = TokenCandidate(chain="solana", address="N" * 32, name="No Entry", symbol="NONE")
    store.upsert_token(untracked, seen_at=now)
    untracked_assessment_id = store.add_token_context_assessment(
        untracked.token_id,
        trigger="high_momentum_reverse_context",
        status="no_context",
        snapshot_observed_at=now,
        momentum_score=81,
        assessment={
            "investigation_trigger": {"kind": "high_momentum_reverse_context"},
            "onchain_momentum": {"momentum_score": 81},
        },
        assessed_at=now,
    )
    assert store.token_context_outcome_tracking(untracked_assessment_id)["status"] == "not_tracked"
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=untracked.address, price_usd=1.0, liquidity_usd=20_000,
            market_cap_usd=None, volume_5m_usd=None, buys_5m=0, sells_5m=0,
            observed_at=now + timedelta(minutes=1),
            ingested_at=now + timedelta(minutes=1), provider="future-only-fixture",
        )
    )

    for minutes, price in ((10, 0.5), (16, 2.0), (61, 1.5)):
        store.add_snapshot(
            TokenSnapshot(
                chain="solana", address=token.address, price_usd=price, liquidity_usd=50_000,
                market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
                observed_at=now + timedelta(minutes=minutes),
                ingested_at=now + timedelta(minutes=minutes), provider="fixture",
            )
        )
    assert store.finalize_token_context_outcomes(now=now + timedelta(minutes=14))["outcomes_observed"] == 0
    assert store.finalize_token_context_outcomes(now=now + timedelta(minutes=17))["outcomes_observed"] == 1
    store.finalize_token_context_outcomes(now=now + timedelta(minutes=62))
    final = store.finalize_token_context_outcomes(now=now + timedelta(minutes=271))
    assert final["outcomes_missing"] == 1 and final["cohorts_completed"] == 1
    outcomes = list(
        store.db.execute(
            "SELECT * FROM token_context_outcomes WHERE cohort_id=? ORDER BY horizon_minutes",
            (int(cohort["id"]),),
        )
    )
    assert [(row["horizon_minutes"], row["status"]) for row in outcomes] == [
        (15, "observed"), (60, "observed"), (240, "missing")
    ]
    assert outcomes[0]["raw_return"] == pytest.approx(1.0)
    assert outcomes[0]["maximum_return"] == pytest.approx(1.0)
    assert outcomes[0]["minimum_return"] == pytest.approx(-0.5)
    assert outcomes[1]["raw_return"] == pytest.approx(0.5)

    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=0.75, liquidity_usd=50_000,
            market_cap_usd=None, volume_5m_usd=None, buys_5m=0, sells_5m=0,
            observed_at=now + timedelta(minutes=241),
            ingested_at=now + timedelta(minutes=241), provider="late-fixture",
        )
    )
    store.finalize_token_context_outcomes(now=now + timedelta(minutes=272))
    frozen = store.db.execute(
        "SELECT status,raw_return FROM token_context_outcomes WHERE cohort_id=? AND horizon_minutes=240",
        (int(cohort["id"]),),
    ).fetchone()
    assert frozen["status"] == "missing" and frozen["raw_return"] is None
    tracking = store.token_context_outcome_tracking(assessment_id)
    assert tracking["status"] == "complete"
    assert [item["status"] for item in tracking["horizons"]] == ["observed", "observed", "missing"]
    assert tracking["decision_eligible"] is False and tracking["affects"] == "none"
    summary = store.token_context_outcome_learning_summary_from_connection(store.db)
    entity_60m = next(
        item for item in summary["items"]
        if item["dimension"] == "verified_public_figure_entity"
        and item["value"] == "elon_musk"
        and item["horizon_minutes"] == 60
    )
    assert entity_60m["mean_raw_return"] == pytest.approx(0.5)
    assert entity_60m["descriptive_mature"] is False
    assert summary["summary"]["independent_tokens"] == 1
    assert summary["maturity_policy"]["minimum_distinct_tokens"] == 30
    assert summary["summary"]["untracked_assessments"] == 1
    assert summary["activation"] is False
    assert summary["actual_schedule_changed_by_learning"] is False
    assert summary["decision_eligible"] is False and summary["affects"] == "none"

    store.close()
    reopened = Store(path)
    assert reopened.db.execute(
        "SELECT COUNT(*) FROM token_context_outcome_cohorts WHERE assessment_id=?",
        (untracked_assessment_id,),
    ).fetchone()[0] == 0
    reopened.close()


def test_token_context_maturity_counts_one_forward_sample_per_token(tmp_path: Path):
    store = Store(tmp_path / "context-independent-tokens.sqlite3")
    now = datetime.now(timezone.utc)
    token = TokenCandidate(chain="solana", address="I" * 32, name="Independent")
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0,
            liquidity_usd=50_000, market_cap_usd=500_000,
            volume_5m_usd=10_000, buys_5m=20, sells_5m=10,
            observed_at=now, ingested_at=now, provider="fixture",
        )
    )
    for index in range(30):
        assessed_at = now + timedelta(seconds=index)
        assessment_id = store.add_token_context_assessment(
            token.token_id,
            trigger="high_momentum_reverse_context",
            status="verified_context",
            snapshot_observed_at=now,
            momentum_score=85,
            assessment={
                "investigation_trigger": {"kind": "high_momentum_reverse_context"},
                "onchain_momentum": {"momentum_score": 85},
            },
            assessed_at=assessed_at,
        )
        cohort = store.db.execute(
            "SELECT id FROM token_context_outcome_cohorts WHERE assessment_id=?",
            (assessment_id,),
        ).fetchone()
        with store.db:
            store.db.execute(
                """
                INSERT INTO token_context_outcomes(
                    cohort_id,horizon_minutes,target_at,status,outcome_observed_at,
                    outcome_price,raw_return,maximum_return,minimum_return,snapshot_count,evaluated_at
                ) VALUES(?,60,?,'observed',?,1.1,0.1,0.1,-0.1,1,?)
                """,
                (
                    int(cohort["id"]), iso(assessed_at + timedelta(minutes=60)),
                    iso(assessed_at + timedelta(minutes=60)),
                    iso(assessed_at + timedelta(minutes=60)),
                ),
            )

    summary = store.token_context_outcome_learning_summary_from_connection(store.db)
    assert summary["summary"]["tracked_cohorts"] == 30
    assert summary["summary"]["independent_tokens"] == 1
    assert summary["summary"]["observed_outcomes"] == 1
    momentum = next(
        item for item in summary["items"]
        if item["dimension"] == "onchain_momentum_band" and item["horizon_minutes"] == 60
    )
    assert momentum["tracked_cohorts"] == 1
    assert momentum["distinct_tokens"] == 1
    assert momentum["descriptive_mature"] is False
    store.close()


def test_dexscreener_attached_links_are_typed_and_promotions_stay_context_only(tmp_path: Path):
    assert DexScreenerClient._classify_link("https://x.com/search?q=mascot")[:2] == ("search", "x")
    assert DexScreenerClient._classify_link("https://truthsocial.com/@realDonaldTrump/123")[:2] == (
        "social_post", "truth"
    )
    assert DexScreenerClient._classify_link("https://www.threads.com/@creator")[:2] == (
        "social_profile", "threads"
    )
    assert DexScreenerClient._classify_link("https://t.me/example")[:2] == ("telegram_manual", "telegram")

    class Response:
        def json(self):
            return [
                {
                    "chainId": "solana",
                    "tokenAddress": "D" * 32,
                    "url": "https://dexscreener.com/solana/pair",
                    "links": [
                        {"type": "twitter", "url": "https://x.com/example"},
                        {"label": "Telegram", "url": "https://t.me/example"},
                    ],
                }
            ]

    class Http:
        async def get(self, *args, **kwargs):
            return Response()

    rows = asyncio.run(DexScreenerClient(Http()).discover_surface("boosts_latest", {"solana"}))
    assert rows
    assert {row["role"] for row in rows} == {"promotion"}
    assert any(row["link_kind"] == "telegram_manual" and row["verification_status"] == "manual_only" for row in rows)
    assert all(row["verification_status"] != "verified" for row in rows)
    store = Store(tmp_path / "dex-links.sqlite3")
    for row in rows:
        store.upsert_token_source_link(row, observed_at="2026-08-30T00:00:00Z")
        store.upsert_token_source_link(row, observed_at="2026-08-30T00:01:00Z")
    persisted = store.token_source_links(f"solana:{'D' * 32}")
    assert {row["role"] for row in persisted} == {"promotion"}
    assert all(row["first_observed_at"] == "2026-08-30T00:00:00Z" for row in persisted)
    assert all(row["last_observed_at"] == "2026-08-30T00:01:00Z" for row in persisted)
    store.close()


def test_dexscreener_batch_quote_chunks_30_and_keeps_highest_liquidity_pair():
    addresses = [f"TOKEN{index:02d}" for index in range(31)]

    def pair(address: str, liquidity: float, social: str = "") -> dict:
        info = {"socials": [{"type": "twitter", "url": social}]} if social else {}
        return {
            "chainId": "solana",
            "baseToken": {"address": address, "name": address, "symbol": address[-2:]},
            "priceUsd": "0.01",
            "liquidity": {"usd": liquidity},
            "volume": {"m5": 1000},
            "txns": {"m5": {"buys": 12, "sells": 3}},
            "url": f"https://dexscreener.com/solana/{address}",
            "info": info,
        }

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class Http:
        def __init__(self):
            self.urls = []

        async def get(self, url, **kwargs):
            self.urls.append(url)
            requested = url.rsplit("/", 1)[-1].split(",")
            payload = [pair(address, 1000) for address in requested]
            if addresses[0] in requested:
                payload.append(pair(addresses[0], 50000, "https://x.com/example/status/1"))
            return Response(payload if len(self.urls) == 1 else {"pairs": payload})

    http = Http()
    result = asyncio.run(DexScreenerClient(http).batch_quote("solana", addresses))
    assert len(http.urls) == 2
    assert len(result) == 31
    first, snapshot = result[f"solana:{addresses[0]}"]
    assert snapshot.liquidity_usd == 50000
    assert "https://x.com/example/status/1" in first.social_urls
    assert any(
        row["link_kind"] == "social_post" and row["role"] == "identity"
        for row in first.raw["token_source_links"]
    )


def test_initial_page_and_old_polled_news_are_not_entry_evidence():
    initial = Observation(
        source="browser:x",
        source_kind="social",
        title="old post",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_receive",
        capture_phase="initial",
    )
    polled = Observation(
        source="rss",
        source_kind="news",
        title="old article first seen now",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_poll",
    )
    received = Observation(
        source="browser:x",
        source_kind="social",
        title="old post inserted into a live page",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_receive",
        capture_phase="live",
    )
    decision_at = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    assert "stale_initial_page" in temporal_rejection_reasons(initial, decision_at, 30)
    assert "stale_polled_item" in temporal_rejection_reasons(polled, decision_at, 30)
    assert "stale_received_item" in temporal_rejection_reasons(received, decision_at, 30)


def test_identity_and_future_published_content_are_never_decision_evidence():
    decision_at = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    identity = Observation(
        source="browser:x:identity",
        source_kind="social",
        title="Identity context only",
        role="identity",
        observed_at=decision_at,
        ingested_at=decision_at,
        availability_proof="local_receive",
    )
    future = Observation(
        source="rss:future",
        source_kind="news",
        title="Clock-skewed future article",
        role="feature",
        published_at=decision_at + timedelta(hours=1),
        observed_at=decision_at,
        ingested_at=decision_at,
        availability_proof="local_poll",
        raw={"published_time_in_future": True},
    )
    assert "non_feature_role" in temporal_rejection_reasons(identity, decision_at, 30)
    assert "published_time_in_future" in temporal_rejection_reasons(future, decision_at, 30)
    accepted, rejected = replay_guard([identity, future], decision_at, 30)
    assert accepted == []
    assert rejected["browser:x:identity"] == ["non_feature_role"]
    assert "published_time_in_future" in rejected["rss:future"]


def test_reverse_name_distinctiveness_blocks_generic_short_terms():
    assert is_distinctive_token_name("Peanut") is True
    assert is_distinctive_token_name("Viral Animal") is True
    assert is_distinctive_token_name("牛来") is True
    assert is_distinctive_token_name("热点") is False
    assert is_context_searchable_token_name("新闻") is False
    assert is_distinctive_token_name("Luce") is False
    assert is_context_searchable_token_name("Luce") is True
    assert is_distinctive_token_name("Neiro") is True
    assert is_distinctive_token_name("Gang") is False
    assert is_distinctive_token_name("AI") is False
    assert is_distinctive_token_name("Coins") is False
    assert is_distinctive_token_name("Attention") is False
    assert is_context_searchable_token_name("Musk") is True
    assert is_distinctive_token_name("Musk") is False


def test_promotional_market_listicles_are_not_event_evidence():
    assert is_promotional_market_content(
        "Top Altcoin News: 7 Meme Coins Enter the Spotlight as a Presale Leads the List"
    )
    assert is_promotional_market_content(
        "Top 100x Cryptos Before the Next Breakout: Coins to Watch"
    )
    assert is_promotional_market_content("2026年十大百倍币：这些预售代币值得关注")
    assert not is_promotional_market_content(
        "Rescued otter video goes viral after a mayor shares it"
    )


def test_aliases_and_addresses():
    aliases = extract_aliases(
        "Breaking: 《My Friend Peanut》 explodes #PNUT",
        "CA: 0x1111111111111111111111111111111111111111",
    )
    assert any("My Friend Peanut" in value for value in aliases)
    assert "PNUT" in aliases
    assert not any(value.startswith("x111111") for value in aliases)
    addresses = extract_addresses("CA 0x1111111111111111111111111111111111111111")
    assert "0x1111111111111111111111111111111111111111" in addresses["evm"]
    assert not addresses["solana"]


def test_news_source_independence_uses_underlying_publisher():
    direct = {
        "source": "coindesk",
        "source_kind": "news",
        "url": "https://www.coindesk.com/markets/example",
        "raw_json": json.dumps({"feed_url": "https://www.coindesk.com/rss"}),
    }
    aggregated = {
        "source": "google-news-memecoin",
        "source_kind": "news",
        "url": "https://news.google.com/rss/articles/example",
        "raw_json": json.dumps({"publisher": "CoinDesk", "publisher_url": "https://www.coindesk.com"}),
    }
    other = {
        "source": "google-news-memecoin",
        "source_kind": "news",
        "url": "https://news.google.com/rss/articles/other",
        "raw_json": json.dumps({"publisher": "Reuters", "publisher_url": "https://www.reuters.com"}),
    }
    assert evidence_origin(direct) == evidence_origin(aggregated) == "coindesk.com"
    assert evidence_origin(other) == "reuters.com"


def test_social_source_independence_uses_only_explicit_persisted_entity_ids():
    x_nasa = {
        "source": "x:nasa",
        "source_kind": "official_social",
        "raw_json": json.dumps({"source_entity_id": "nasa"}),
    }
    youtube_nasa = {
        "source": "youtube:nasa",
        "source_kind": "social",
        "raw_json": json.dumps({"source_entity_id": "nasa"}),
    }
    x_spacex = {
        "source": "x:spacex",
        "source_kind": "official_social",
        "raw_json": json.dumps({"source_entity_id": "spacex"}),
    }
    unknown_x = {"source": "x:unknown", "source_kind": "social", "raw_json": "{}"}
    unknown_youtube = {"source": "youtube:unknown", "source_kind": "social", "raw_json": "{}"}
    forged = {
        "source": "youtube:other",
        "source_kind": "social",
        "raw_json": json.dumps({"source_entity_id": "NASA/../../forged"}),
    }

    assert evidence_origin(x_nasa) == evidence_origin(youtube_nasa) == "entity:nasa"
    assert len({evidence_origin(x_nasa), evidence_origin(youtube_nasa)}) == 1
    assert len({evidence_origin(x_nasa), evidence_origin(x_spacex)}) == 2
    assert len({evidence_origin(unknown_x), evidence_origin(unknown_youtube)}) == 2
    assert evidence_origin(forged) == "youtube:other"


def test_event_clustering_and_dedup(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.15)
    a = Observation(source="x:a", source_kind="social", title="Peanut squirrel story goes viral", source_item_id="1")
    b = Observation(source="reddit:b", source_kind="social", title="Viral Peanut squirrel community reaction", source_item_id="2")
    first, first_created, first_observation = engine.ingest(a)
    second, second_created, second_observation = engine.ingest(b)
    assert first == second
    assert first_created is True and first_observation is True
    assert second_created is False and second_observation is True
    rows = store.event_observations(first)
    assert len(rows) == 2
    assert len({row["source"] for row in rows}) == 2
    duplicate_event, duplicate_created, duplicate_observation = engine.ingest(a)
    assert duplicate_event == first
    assert duplicate_created is False and duplicate_observation is False
    store.close()


def test_single_viral_visible_post_can_cross_attention_threshold(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store)
    event_id, _, _ = engine.ingest(
        Observation(
            source="browser:x:example",
            source_kind="social",
            title="A newly viral squirrel story",
            raw={"view_count": 500000, "repost_count": 5000, "like_count": 20000},
        )
    )
    assert store.get_event(event_id).attention >= 40
    store.close()


def test_event_clustering_joins_paraphrases_but_not_same_person_unrelated_story(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.28)
    chelsea_a, _, _ = engine.ingest(
        Observation(
            source="coindesk",
            source_kind="news",
            title="Circle USDC takes over Chelsea jersey in first sponsorship deal",
            source_item_id="chelsea-a",
        )
    )
    chelsea_b, created, _ = engine.ingest(
        Observation(
            source="cointelegraph",
            source_kind="news",
            title="Chelsea FC gets stablecoin sponsor after UK warning",
            source_item_id="chelsea-b",
        )
    )
    trump_a, _, _ = engine.ingest(
        Observation(
            source="news-a",
            source_kind="news",
            title="Trump comments on a new trade tariff",
            source_item_id="trump-a",
        )
    )
    trump_b, unrelated_created, _ = engine.ingest(
        Observation(
            source="news-b",
            source_kind="news",
            title="Trump attends a football match in Florida",
            source_item_id="trump-b",
        )
    )
    assert chelsea_a == chelsea_b and created is False
    assert trump_a != trump_b and unrelated_created is True
    store.close()


def test_html_feed_artifacts_do_not_merge_unrelated_internet_stories(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.28)
    common_markup = '&lt;a target="_blank" style="color:#6f6f6f"&gt;&amp;nbsp;&lt;/a&gt;'
    sports, _, _ = engine.ingest(
        Observation(
            source="google-news-reverse",
            source_kind="news",
            title="Vancouver Little League player goes viral for revealing his dream job",
            text=common_markup,
            source_item_id="sports",
        )
    )
    governance, created, _ = engine.ingest(
        Observation(
            source="google-news-viral",
            source_kind="news",
            title="Internet Governance Lab 2026: AI and the Internet",
            text=common_markup,
            source_item_id="governance",
        )
    )
    assert sports != governance
    assert created is True
    assert "#6f6f6f" not in extract_aliases("headline", common_markup)
    store.close()


def test_paper_position_sizing_daily_limit_and_partial_exit(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="A" * 32, name="Example")
    store.upsert_token(token)
    snapshot = TokenSnapshot(
        chain="solana",
        address=token.address,
        price_usd=0.01,
        liquidity_usd=100000,
        market_cap_usd=1000000,
        volume_5m_usd=50000,
        buys_5m=50,
        sells_5m=20,
    )
    store.add_snapshot(snapshot)
    policy = PaperPolicy(
        {
            "risk_per_trade_pct": 0.005,
            "max_position_usd": 35,
            "min_position_usd": 3,
            "max_cash_fraction": 0.08,
            "max_liquidity_impact_pct": 0.0025,
            "max_daily_new_exposure_usd": 100,
            "stop_loss_pct": -0.35,
            "max_open_positions": 3,
        }
    )
    size = policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=0,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=0,
    )
    assert 3 <= size <= 35
    assert policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=0,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=100,
    ) == 0
    position = store.paper_buy(event_id=1, token=token, price=0.01, gross_usd=size, fee_bps=60, reason="test")
    assert position.quantity > 0
    result = store.paper_sell(token.token_id, price=0.02, fraction=0.25, fee_bps=60, reason="partial")
    remaining = store.position(token.token_id)
    assert result["pnl_usd"] > 0
    assert remaining is not None and remaining.quantity == pytest.approx(position.quantity * 0.75)
    assert store.daily_buy_gross_usd() == pytest.approx(size)
    store.close()


def test_paper_cost_ledger_is_explicit_and_account_marks_are_append_only(tmp_path: Path):
    store = Store(tmp_path / "paper-ledger.sqlite3", initial_cash_usd=1000)
    now = datetime.now(timezone.utc)
    token = TokenCandidate(chain="solana", address="C" * 32, name="Costed Paper")
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=100, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=5,
            observed_at=now - timedelta(seconds=1), provider="test-dex",
        )
    )
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=999, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=5,
            observed_at=now + timedelta(hours=1), provider="future-test",
        )
    )
    assert store.latest_snapshot(token.token_id).price_usd == pytest.approx(100)

    store.record_paper_account_snapshot(
        cash_usd=1000, marked_value_usd=0, equity_usd=1000, daily_exposure_usd=0,
        open_position_count=0, priced_position_count=0, observed_at=now,
    )
    store.record_paper_account_snapshot(
        cash_usd=900, marked_value_usd=95, equity_usd=995, daily_exposure_usd=100,
        open_position_count=1, priced_position_count=1, quote_as_of=now,
        observed_at=now + timedelta(seconds=20),
    )
    marks = list(store.db.execute("SELECT * FROM paper_account_snapshots ORDER BY id"))
    assert len(marks) == 2
    assert marks[0]["cash_usd"] == pytest.approx(1000)
    assert marks[1]["cash_usd"] == pytest.approx(900)

    position = store.paper_buy(
        event_id=1, token=token, price=102, quote_price=100, gross_usd=100,
        fee_bps=60, tax_pct=3, reason="cost-test", quote_observed_at=now,
        quote_provider="test-dex", execution_attempted_at=now + timedelta(seconds=1),
    )
    assert position.quantity == pytest.approx(97 / 102)
    assert store.account()["cash_usd"] == pytest.approx(899.4)
    sale = store.paper_sell(
        token.token_id, price=117.6, quote_price=120, fraction=1, fee_bps=60,
        tax_pct=4, reason="cost-test-close", quote_observed_at=now + timedelta(minutes=1),
        quote_provider="test-dex", execution_attempted_at=now + timedelta(minutes=1, seconds=1),
    )
    assert sale["tax_usd"] == pytest.approx(sale["gross_usd"] * 0.04)
    trades = list(reversed(store.trades(10)))
    assert [(row["side"], row["quote_price"], row["price"]) for row in trades] == [
        ("BUY", 100, 102), ("SELL", 120, 117.6)
    ]
    assert trades[0]["fee_usd"] == pytest.approx(0.6)
    assert trades[0]["slippage_rate"] == pytest.approx(0.02)
    assert trades[0]["tax_usd"] == pytest.approx(3)
    assert trades[0]["quote_provider"] == "test-dex"
    store.close()


def test_live_mode_is_locked(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"mode": "live"}), encoding="utf-8")
    with pytest.raises(ValueError, match="hard-locked"):
        load_config(config)


def test_candidate_ranking_is_neutral_until_runtime_finalizes(tmp_path: Path):
    store = Store(tmp_path / "ranking.sqlite3")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event = EventView(1, "Viral otter", ["otter"], 80, now, now)
    token = TokenCandidate("solana", "A" * 32, "Viral Otter", "OTTER")
    snapshot = TokenSnapshot(
        "solana", token.address, 0.01, 50_000, 500_000, 12_000, 30, 10,
        observed_at=now,
        provider="dexscreener",
    )
    decision = CandidateDecision(1, token.token_id, "CANDIDATE", 80, 90, 10, ["test"], created_at=now)
    evaluator = CandidateEvaluator(store, None, None, {}, None)
    evaluator._persist_ranking(
        event,
        evaluated_at=now,
        ranked=[(80, 90, token, snapshot, ["test"])],
        decision=decision,
        safety_checked=True,
    )
    pending = store.candidate_ranking(1)
    assert pending["status"] == "pending_runtime"
    assert pending["outcome"] == "UNAVAILABLE"
    assert pending["final_outcome"] is None
    assert pending["candidates"][0]["action"] == "PENDING_RUNTIME"

    decision_id = store.add_decision(decision)
    store.finalize_candidate_ranking(1, decision, decision_id=decision_id)
    final = store.candidate_ranking(1)
    assert final["status"] == "completed"
    assert final["outcome"] == "CANDIDATE"
    assert final["final_outcome"]["decision_id"] == decision_id
    assert final["candidates"][0]["action"] == "CANDIDATE"
    store.close()


def test_old_config_keys_are_migrated_and_negative_drawdown_is_normalized(tmp_path: Path):
    payload = {
        "mode": "paper",
        "initial_cash_usd": 1000,
        "bridge": {"host": "127.0.0.1", "port": 8765, "token": "x" * 32},
        "runtime": {"event_scan_seconds": 7, "token_watch_seconds": [20, 60]},
        "events": {"minimum_attention_score": 44, "max_source_age_minutes": 25},
        "candidate": {"recent_token_hours": 6, "min_total_score": 66},
        "paper": {
            "fee_rate": 0.006,
            "risk_per_trade": 0.005,
            "max_liquidity_impact": 0.0025,
            "trailing_drawdown_pct": -0.28,
        },
        "live": {"enabled": False},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    config, _ = load_config(path)
    assert config["paper"]["starting_cash_usd"] == 1000
    assert config["paper"]["fee_bps"] == pytest.approx(60)
    assert config["paper"]["trailing_drawdown_pct"] == pytest.approx(0.28)
    assert config["event_scan_seconds"] == 7
    assert config["event_min_attention"] == 44
    assert config["candidate"]["token_watch_minutes"] == 360
    assert config["candidate"]["retry_seconds"] == [20, 60]
    assert config["candidate"]["max_source_age_minutes"] == 25


def test_browser_extension_persists_queue_filters_old_posts_and_heartbeats():
    root = Path(__file__).resolve().parents[1] / "browser-extension"
    background = (root / "background.js").read_text(encoding="utf-8")
    content = (root / "content.js").read_text(encoding="utf-8")
    options = (root / "options.html").read_text(encoding="utf-8")
    manifest = (root / "manifest.json").read_text(encoding="utf-8")
    assert "chrome.storage.local" in background
    assert "pendingObservations" in background
    assert "/v1/heartbeat" in background
    assert "MutationObserver" in content
    assert "PRIVATE_PATH" in content
    assert "maxPostAgeMinutes" in content
    assert "http://127.0.0.1:8787/api/watchlist" in background
    assert "memetrader-watchlist-sync" in background
    assert 'credentials: "omit"' in background
    assert "watchAccountEntries" in background
    assert "entity_id" in background and "source_entity_id" in content
    assert "matchedWatchAccount(author)" in content
    assert "item.platform === platform()" in content
    assert "authorKey === accountKey(item.handle)" in content
    assert "platformStates" in content and "platformEnabled()" in content
    assert all(state in content for state in ("content_visible", "login_prompt", "no_recent_items"))
    assert "selector_count" in content and "page_url" in content
    assert options.count('id="maxPostAgeMinutes"') == 1
    assert "watchlistLastSyncAt" in (root / "options.js").read_text(encoding="utf-8")
    assert '"cookies"' not in manifest.lower()
    assert '"tabs"' not in manifest.lower()


def test_exact_contract_address_dominates_name_similarity():
    ca = "0x1111111111111111111111111111111111111111"
    event_text = f"Official post CA: {ca}"
    addresses = extract_addresses(event_text)
    exact = TokenCandidate(chain="bsc", address=ca, name="Different Name", symbol="DIFF")
    copy = TokenCandidate(
        chain="bsc",
        address="0x2222222222222222222222222222222222222222",
        name="Official Post",
        symbol="OFFICIAL",
    )
    assert CandidateEvaluator._match_score(["Official Post"], event_text, exact, addresses) == 100
    assert CandidateEvaluator._match_score(["Official Post"], event_text, copy, addresses) < 100


def test_generic_token_name_cannot_hijack_unrelated_news_event(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        event_id, _, _ = EventEngine(store).ingest(
            Observation(
                source="news-a",
                source_kind="news",
                title="Fresh market attention follows a quarterly company report",
                availability_proof="local_poll",
            )
        )
        token = TokenCandidate(chain="solana", address="A" * 32, name="Attention", symbol="ATTENTION")
        snap = TokenSnapshot("solana", token.address, 0.01, 250000, 1000000, 50000, 500, 20)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(token, snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        decision = await CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        ).discover_and_decide(store.get_event(event_id))
        assert decision is not None
        assert decision.action == "WAIT"
        assert decision.reasons == ["no_matching_token"]
        assert store.token(token.token_id) is None
        ranking = store.candidate_ranking(event_id)
        assert ranking is not None
        assert ranking["status"] == "pending_runtime" and ranking["outcome"] == "UNAVAILABLE"
        assert ranking["candidate_count_total"] == 0
        assert ranking["candidates"] == []
        assert ranking["final_outcome"] is None
        assert ranking["outcome_reasons"] == ["no_matching_token"]
        store.close()

    asyncio.run(scenario())


def test_information_first_shadow_cohort_is_forward_append_only_and_preserves_missing_baselines(tmp_path: Path):
    store = Store(tmp_path / "information-first-shadow.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = store.create_event("Forward information", ["Forward"], 80, now - timedelta(minutes=3))
    lead = Observation(
        source="fixture-news", source_kind="news", title="Forward information", text="Forward",
        observed_at=now - timedelta(minutes=2), ingested_at=now - timedelta(minutes=1),
        published_at=now - timedelta(minutes=2), role="feature", capture_phase="live",
    )
    lead_id, _ = store.add_observation(lead)
    store.link_event_observation(event_id, lead_id)
    identity = Observation(
        source="project-link", source_kind="social", title="Identity", text="",
        observed_at=now - timedelta(minutes=1), ingested_at=now - timedelta(minutes=1),
        role="identity", capture_phase="live",
    )
    identity_id, _ = store.add_observation(identity)
    store.link_event_observation(event_id, identity_id)
    token = TokenCandidate(
        chain="solana", address="F" * 32, name="Forward Token", symbol="FWD",
        created_at=now - timedelta(minutes=5),
    )
    peer = TokenCandidate(chain="solana", address="P" * 32, name="forward   token", symbol="FWD")
    future_peer = TokenCandidate(chain="solana", address="Q" * 32, name="Forward Token", symbol="FWD")
    store.upsert_token(token, seen_at=now - timedelta(minutes=3))
    store.upsert_token(peer, seen_at=now - timedelta(minutes=3))
    store.upsert_token(future_peer, seen_at=now + timedelta(minutes=1))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=token.address, price_usd=1.0, liquidity_usd=40_000,
        market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=10, sells_5m=5,
        observed_at=now - timedelta(seconds=30), ingested_at=now - timedelta(seconds=30), provider="fixture",
    ))
    decision_id = store.add_decision(CandidateDecision(
        event_id, token.token_id, "WAIT", 70, 80, 4, [], created_at=now,
    ))
    cohort_id = store.create_information_first_shadow_cohort(
        event_id, token.token_id, decision_id=decision_id, accepted_observation_ids=[lead_id, identity_id],
        captured_at=now, relation_available_at=now, candidate_facts={
            "candidate_count": 2, "selected_rank": 1, "raw_score_margin": 3.0,
            "canonical_margin": 4.0, "tie_break_used": False,
        },
    )
    assert cohort_id is not None
    cohort = store.db.execute(
        "SELECT * FROM information_first_shadow_cohorts WHERE id=?", (cohort_id,)
    ).fetchone()
    assert cohort["signal_available_at"] == iso(now)
    features = json.loads(cohort["features_json"])
    assert features["market_state"]["label"] == "low_observed_market_activity"
    assert features["same_name_competition"]["preexisting_same_name_count"] == 1
    assert features["same_name_competition"]["preexisting_same_symbol_count"] == 1
    assert features["attention_source_breadth"]["qualified_observation_count"] == 1
    assert features["attention_source_breadth"]["mode"] == "descriptive_observed_origins_not_independence_claim"
    assert features["token_preexistence"]["status"] == "not_available"
    assert features["pair_preexistence_descriptive"]["status"] == "preexisting"
    assert features["not_available"] == ["unique_buyers", "image_similarity", "holder_clusters"]
    repeat_decision_id = store.add_decision(CandidateDecision(
        event_id, token.token_id, "WAIT", 70, 80, 4, [], created_at=now,
    ))
    assert store.create_information_first_shadow_cohort(
        event_id, token.token_id, decision_id=repeat_decision_id, accepted_observation_ids=[lead_id],
        captured_at=now, relation_available_at=now,
    ) == cohort_id
    admissions = list(store.db.execute(
        "SELECT status,reason FROM information_first_shadow_admission_attempts ORDER BY id"
    ))
    assert [(row["status"], row["reason"]) for row in admissions] == [
        ("created", "created"), ("already_admitted", "first_write_wins_event_token"),
    ]
    with pytest.raises(sqlite3.IntegrityError):
        with store.db:
            store.db.execute(
                "UPDATE information_first_shadow_cohorts SET token_id='changed' WHERE id=?", (cohort_id,)
            )

    for minutes, price in ((16, 2.0), (61, 1.5)):
        store.add_snapshot(TokenSnapshot(
            chain="solana", address=token.address, price_usd=price, liquidity_usd=40_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=10, sells_5m=5,
            observed_at=now + timedelta(minutes=minutes), ingested_at=now + timedelta(minutes=minutes), provider="fixture",
        ))
    assert store.finalize_information_first_shadow_outcomes(now=now + timedelta(minutes=17))["outcomes_observed"] == 1
    store.finalize_information_first_shadow_outcomes(now=now + timedelta(minutes=62))
    final = store.finalize_information_first_shadow_outcomes(now=now + timedelta(minutes=271))
    assert final["outcomes_missing"] == 1
    outcomes = list(store.db.execute(
        "SELECT horizon_minutes,status,raw_return FROM information_first_shadow_outcomes WHERE cohort_id=? ORDER BY horizon_minutes",
        (cohort_id,),
    ))
    assert [(row["horizon_minutes"], row["status"]) for row in outcomes] == [
        (15, "observed"), (60, "observed"), (240, "missing"),
    ]
    assert outcomes[0]["raw_return"] == pytest.approx(1.0)

    missing_event = store.create_event("No baseline", ["No baseline"], 70, now - timedelta(minutes=1))
    missing_lead = Observation(
        source="fixture-news-2", source_kind="news", title="No baseline", text="",
        observed_at=now - timedelta(seconds=50), ingested_at=now - timedelta(seconds=40),
        role="feature", capture_phase="live",
    )
    missing_lead_id, _ = store.add_observation(missing_lead)
    store.link_event_observation(missing_event, missing_lead_id)
    missing_token = TokenCandidate(chain="solana", address="M" * 32, name="Missing baseline")
    store.upsert_token(missing_token, seen_at=now - timedelta(minutes=1))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=missing_token.address, price_usd=1.0, liquidity_usd=10_000,
        market_cap_usd=100_000, volume_5m_usd=100, buys_5m=1, sells_5m=1,
        observed_at=now + timedelta(minutes=1), ingested_at=now + timedelta(minutes=1), provider="future-fixture",
    ))
    missing_decision_id = store.add_decision(CandidateDecision(
        missing_event, missing_token.token_id, "WAIT", 60, 70, 3, [], created_at=now,
    ))
    missing_cohort_id = store.create_information_first_shadow_cohort(
        missing_event, missing_token.token_id, decision_id=missing_decision_id,
        accepted_observation_ids=[missing_lead_id], captured_at=now, relation_available_at=now,
    )
    missing_cohort = store.db.execute(
        "SELECT trackability,entry_price FROM information_first_shadow_cohorts WHERE id=?", (missing_cohort_id,)
    ).fetchone()
    assert missing_cohort["trackability"] == "baseline_missing_at_signal_available"
    assert missing_cohort["entry_price"] is None
    assert store.finalize_information_first_shadow_outcomes(now=now + timedelta(minutes=271))["cohorts_checked"] == 1
    summary = Store.information_first_shadow_summary_from_connection(store.db)
    assert summary["summary"]["cohorts"] == 2
    assert summary["summary"]["baseline_missing_at_signal_available"] == 1
    assert summary["summary"]["outcomes_observed"] == 2
    assert summary["affects"] == "none"


def test_information_first_shadow_rejects_invalid_observation_availability(tmp_path: Path):
    store = Store(tmp_path / "information-first-invalid-lead.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = store.create_event("Invalid lead", ["Invalid"], 60, now - timedelta(minutes=2))
    invalid = Observation(
        source="invalid-fixture", source_kind="news", title="Invalid lead", text="",
        observed_at=now - timedelta(minutes=1), ingested_at=now - timedelta(minutes=2),
        role="feature", capture_phase="live",
    )
    observation_id, _ = store.add_observation(invalid)
    store.link_event_observation(event_id, observation_id)
    token = TokenCandidate(chain="solana", address="V" * 32, name="Invalid")
    store.upsert_token(token, seen_at=now - timedelta(minutes=2))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=token.address, price_usd=1.0, liquidity_usd=10_000,
        market_cap_usd=100_000, volume_5m_usd=100, buys_5m=1, sells_5m=1,
        observed_at=now - timedelta(minutes=1), ingested_at=now - timedelta(minutes=1), provider="fixture",
    ))
    decision_id = store.add_decision(CandidateDecision(
        event_id, token.token_id, "WAIT", 60, 70, 3, [], created_at=now,
    ))
    assert store.create_information_first_shadow_cohort(
        event_id, token.token_id, decision_id=decision_id, accepted_observation_ids=[observation_id],
        captured_at=now, relation_available_at=now,
    ) is None
    attempt = store.db.execute(
        "SELECT status,reason FROM information_first_shadow_admission_attempts WHERE decision_id=?", (decision_id,)
    ).fetchone()
    assert (attempt["status"], attempt["reason"]) == (
        "skipped", "no_eligible_accepted_information_lead"
    )


def test_information_first_ilg_is_strict_forward_same_surface_and_terminal(tmp_path: Path):
    store = Store(tmp_path / "information-first-ilg.sqlite3")
    registration = store.db.execute(
        "SELECT * FROM information_first_ilg_registrations WHERE definition_version=?",
        (Store.INFORMATION_FIRST_ILG_VERSION,),
    ).fetchone()
    registered_at = parse_time(registration["registered_at"])
    signal = registered_at + timedelta(seconds=2)
    surface = {
        "pair": {
            "chainId": "solana", "dexId": "raydium", "pairAddress": "PAIR-A",
        }
    }

    def add_recorded_snapshot(
        token_id: str,
        *,
        recorded_at: datetime,
        volume: float,
        buys: int,
        sells: int,
        raw: dict | None = None,
        market_cap: float = 500_000,
    ) -> int:
        with store.db:
            cursor = store.db.execute(
                """
                INSERT INTO token_snapshots(
                    token_id,observed_at,ingested_at,recorded_at,provider,price_usd,
                    liquidity_usd,market_cap_usd,volume_5m_usd,buys_5m,sells_5m,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    token_id, iso(recorded_at), iso(recorded_at), iso(recorded_at), "dexscreener",
                    1.0, 50_000, market_cap, volume, buys, sells,
                    json.dumps(surface if raw is None else raw),
                ),
            )
        return int(cursor.lastrowid)

    sequence = 0

    def create_cohort(*, volume: float = 20_000, buys: int = 20, sells: int = 10, raw=None):
        nonlocal sequence
        sequence += 1
        address = chr(64 + sequence) * 32
        token = TokenCandidate(chain="solana", address=address, name=f"ILG {sequence}")
        store.upsert_token(token, seen_at=registered_at - timedelta(minutes=2))
        event_id = store.create_event(
            f"ILG event {sequence}", [f"ILG {sequence}"], 70,
            registered_at - timedelta(minutes=1),
        )
        lead = Observation(
            source=f"ilg-fixture-{sequence}", source_kind="news", title=f"ILG {sequence}",
            observed_at=registered_at - timedelta(seconds=10), ingested_at=registered_at,
            published_at=registered_at - timedelta(seconds=10), role="feature", capture_phase="live",
        )
        lead_id, _ = store.add_observation(lead)
        store.link_event_observation(event_id, lead_id)
        add_recorded_snapshot(
            token.token_id, recorded_at=registered_at + timedelta(seconds=1),
            volume=volume, buys=buys, sells=sells, raw=surface if raw is None else raw,
        )
        decision_id = store.add_decision(CandidateDecision(
            event_id, token.token_id, "WAIT", 60, 70, 3, [], created_at=signal,
        ))
        shadow_id = store.create_information_first_shadow_cohort(
            event_id, token.token_id, decision_id=decision_id,
            accepted_observation_ids=[lead_id], captured_at=signal, relation_available_at=signal,
        )
        cohort = store.db.execute(
            "SELECT * FROM information_first_ilg_cohorts WHERE shadow_cohort_id=?", (shadow_id,)
        ).fetchone()
        return token, cohort

    crossed_token, crossed_cohort = create_cohort()
    assert crossed_cohort["eligibility"] == "eligible_at_risk"
    add_recorded_snapshot(
        crossed_token.token_id, recorded_at=signal + timedelta(seconds=20),
        volume=1_000_000, buys=100, sells=100,
        raw={"pair": {"chainId": "solana", "dexId": "raydium", "pairAddress": "PAIR-B"}},
    )
    add_recorded_snapshot(
        crossed_token.token_id, recorded_at=signal + timedelta(seconds=30),
        volume=20_000, buys=20, sells=10, market_cap=50_000_000,
    )
    crossing_id = add_recorded_snapshot(
        crossed_token.token_id, recorded_at=signal + timedelta(seconds=40),
        volume=20_000.01, buys=20, sells=10,
    )
    result = store.finalize_information_first_ilg_outcomes(now=signal + timedelta(seconds=41))
    assert result["outcomes_crossed"] == 1
    outcome = store.db.execute(
        "SELECT * FROM information_first_ilg_outcomes WHERE ilg_cohort_id=?",
        (int(crossed_cohort["id"]),),
    ).fetchone()
    assert outcome["crossing_snapshot_id"] == crossing_id
    assert outcome["ilg_seconds"] == pytest.approx(40)
    assert json.loads(outcome["crossed_dimensions_json"]) == ["volume_5m_usd"]
    assert outcome["valid_snapshot_count"] == 2

    invalid_future_token, invalid_future_cohort = create_cohort()
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=invalid_future_token.address, price_usd=1,
        liquidity_usd=50_000, market_cap_usd=500_000, volume_5m_usd=50_000,
        buys_5m=50, sells_5m=20, observed_at=signal + timedelta(minutes=10),
        ingested_at=signal + timedelta(minutes=10), provider="dexscreener", raw=surface,
    ))
    future_row = store.db.execute(
        "SELECT * FROM token_snapshots WHERE token_id=? ORDER BY id DESC LIMIT 1",
        (invalid_future_token.token_id,),
    ).fetchone()
    assert parse_time(future_row["recorded_at"]) < parse_time(future_row["ingested_at"])

    low_token, low_cohort = create_cohort()
    add_recorded_snapshot(
        low_token.token_id, recorded_at=signal + timedelta(minutes=60),
        volume=20_000, buys=20, sells=10,
    )
    already_active_token, already_active_cohort = create_cohort(volume=20_000.01)
    assert already_active_cohort["eligibility"] == "already_active_at_signal"
    _, unknown_surface_cohort = create_cohort(raw={})
    assert unknown_surface_cohort["eligibility"] == "ineligible_activity_surface_unknown"

    terminal = signal + timedelta(minutes=270)
    terminal_result = store.finalize_information_first_ilg_outcomes(now=terminal)
    assert terminal_result["outcomes_missing"] == 2
    terminal_statuses = {
        int(row["ilg_cohort_id"]): str(row["status"])
        for row in store.db.execute(
            "SELECT ilg_cohort_id,status FROM information_first_ilg_outcomes"
        )
    }
    assert terminal_statuses[int(invalid_future_cohort["id"])] == "missing_no_valid_activity_snapshot"
    assert terminal_statuses[int(low_cohort["id"])] == "missing_not_crossed_by_240m"
    add_recorded_snapshot(
        low_token.token_id, recorded_at=signal + timedelta(minutes=120),
        volume=50_000, buys=50, sells=20,
    )
    assert store.finalize_information_first_ilg_outcomes(now=terminal + timedelta(minutes=1))["cohorts_checked"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        with store.db:
            store.db.execute(
                "UPDATE information_first_ilg_outcomes SET status='crossed' WHERE ilg_cohort_id=?",
                (int(low_cohort["id"]),),
            )

    old_signal = registered_at - timedelta(seconds=1)
    with store.db:
        old_shadow = store.db.execute(
            """
            INSERT INTO information_first_shadow_cohorts(
                cohort_key,version,event_id,token_id,decision_id,captured_at,signal_available_at,
                relation_available_at,lead_observation_id,lead_observed_at,trackability,
                features_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "pre-registration", Store.INFORMATION_FIRST_SHADOW_VERSION, 999_991,
                already_active_token.token_id, 999_991, iso(old_signal), iso(old_signal),
                iso(old_signal), 999_991, iso(old_signal), "baseline_missing_at_signal_available",
                "{}", iso(old_signal),
            ),
        ).lastrowid
    assert store._create_information_first_ilg_cohort(int(old_shadow)) is None

    summary = Store.information_first_ilg_summary_from_connection(store.db)
    assert summary["affects"] == "none"
    assert summary["definition"]["activity"]["market_cap_excluded"] is True
    assert summary["summary"]["eligible_at_risk"] == 3
    assert summary["summary"]["crossed"] == 1
    assert summary["summary"]["missing_not_crossed_by_240m"] == 1
    assert summary["summary"]["missing_no_valid_activity_snapshot"] == 1
    assert summary["summary"]["pre_registration_excluded"] == 1
    assert summary["summary"]["median_ilg_seconds"] == pytest.approx(40)


def test_four_character_person_name_requires_more_than_text_overlap(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        event_id, _, _ = EventEngine(store).ingest(
            Observation(
                source="news-a",
                source_kind="news",
                title="Elon Musk comments on a new spacecraft test",
                availability_proof="local_poll",
            )
        )
        token = TokenCandidate(chain="solana", address="M" * 32, name="Musk", symbol="MUSK")
        snap = TokenSnapshot("solana", token.address, 0.01, 250000, 1000000, 50000, 500, 20)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(token, snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        decision = await CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        ).discover_and_decide(store.get_event(event_id))
        assert decision is not None and decision.action == "WAIT"
        assert decision.reasons == ["no_matching_token"]
        assert store.token(token.token_id) is None
        store.close()

    asyncio.run(scenario())


def test_official_contract_filters_higher_liquidity_name_clone(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        ca = "0x1111111111111111111111111111111111111111"
        clone_ca = "0x2222222222222222222222222222222222222222"
        engine = EventEngine(store)
        event_id, _, _ = engine.ingest(
            Observation(
                source="browser:x:official",
                source_kind="official_social",
                title=f"Official launch CA: {ca}",
                text=f"Official launch CA: {ca}",
                availability_proof="local_receive",
            )
        )
        event = store.get_event(event_id)
        exact = TokenCandidate(chain="bsc", address=ca, name="Test", symbol="TST")
        clone = TokenCandidate(chain="bsc", address=clone_ca, name="Official Launch", symbol="REAL")
        exact_snap = TokenSnapshot("bsc", ca, 0.001, 20000, 100000, 10000, 20, 5)
        clone_snap = TokenSnapshot("bsc", clone_ca, 0.001, 1000000, 1000000, 500000, 500, 30)

        class FakeDex:
            async def quote(self, chain, address):
                return (exact, exact_snap) if chain == "bsc" and address.lower() == ca else None

            async def search(self, query, limit=25):
                return [(clone, clone_snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        evaluator = CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["bsc"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None
        assert decision.action == "CANDIDATE"
        assert decision.token_id == exact.token_id
        assert store.token(clone.token_id) is None
        store.close()

    asyncio.run(scenario())


def test_verified_token_context_link_excludes_unlinked_name_clone(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        linked = TokenCandidate(chain="solana", address="A" * 32, name="Otter Community", symbol="OTTR")
        clone = TokenCandidate(chain="solana", address="B" * 32, name="Viral Rescue Otter", symbol="OTTER")
        engine = EventEngine(store)
        event_id = None
        for domain in ("publisher-a.example", "publisher-b.example"):
            current_id, _, _ = engine.ingest(
                Observation(
                    source=f"agent-search:{domain}",
                    source_kind="news",
                    title="A viral rescue otter story spreads globally",
                    text="Independent reporting confirms the same current event.",
                    url=f"https://{domain}/story",
                    availability_proof="agent_search_verified",
                    role="confirmation",
                    source_item_id=f"https://{domain}/story",
                    raw={
                        "agent_web_search": True,
                        "agent_task": "token_context",
                        "reverse_token_id": linked.token_id,
                        "token_id": linked.token_id,
                        "confidence": 0.91,
                    },
                )
            )
            event_id = current_id
        event = store.get_event(int(event_id))
        linked_snap = TokenSnapshot("solana", linked.address, 0.001, 50000, 500000, 30000, 80, 20)
        clone_snap = TokenSnapshot("solana", clone.address, 0.001, 50000, 500000, 30000, 80, 20)

        class FakeDex:
            async def quote(self, chain, address):
                if chain == "solana" and address == linked.address:
                    return linked, linked_snap
                return None

            async def search(self, query, limit=25):
                return [(clone, clone_snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        evaluator = CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "agent_tie_threshold": 0,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
                "min_reverse_independent_sources": 2,
            },
            FakeAgent(),
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None
        assert decision.action == "CANDIDATE"
        assert decision.token_id == linked.token_id
        assert "agent_context_exact_token_link" in decision.reasons
        assert store.token(clone.token_id) is None
        store.close()

    asyncio.run(scenario())



def test_budgeted_agent_cannot_manufacture_canonical_certainty_from_a_tie(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        engine = EventEngine(store)
        event_id, _, _ = engine.ingest(
            Observation(
                source="x:a",
                source_kind="social",
                title="Dancing Capybara becomes a viral meme",
                raw={"view_count": 1000000},
            )
        )
        original = store.get_event(event_id)
        store.update_event(
            event_id,
            title=original.title,
            aliases=original.aliases,
            attention=80,
            seen_at=original.last_seen_at,
        )
        event = store.get_event(event_id)
        first = TokenCandidate(chain="solana", address="A" * 32, name="Dancing Capybara", symbol="CAPY")
        second = TokenCandidate(chain="solana", address="B" * 32, name="Dancing Capybara", symbol="CAPY")
        first_snap = TokenSnapshot("solana", first.address, 0.001, 30000, 200000, 20000, 50, 10)
        second_snap = TokenSnapshot("solana", second.address, 0.001, 30000, 200000, 20000, 50, 10)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(first, first_snap), (second, second_snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            tier = None

            def ask(self, payload, tier="low"):
                self.tier = tier
                return {"preferred_token_id": second.token_id, "confidence": 0.9}

        agent = FakeAgent()
        evaluator = CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 5,
                "agent_tie_threshold": 3,
                "agent_resolution_confidence": {"low": 0.85, "medium": 0.78},
                "max_alias_queries": 1,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            agent,
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None and decision.action == "WAIT"
        assert decision.token_id == second.token_id
        assert decision.canonical_margin == 0
        assert decision.rejected_reasons == ["canonical_token_ambiguous"]
        assert agent.tier == "medium"
        assert "agent_tiebreak=medium" in decision.reasons
        ranking = store.candidate_ranking(event_id)
        assert ranking is not None
        assert ranking["candidate_count_total"] == 2
        assert [item["rank"] for item in ranking["candidates"]] == [1, 2]
        assert [item["token_id"] for item in ranking["candidates"]] == [second.token_id, first.token_id]
        assert ranking["candidates"][0]["action"] == "PENDING_RUNTIME"
        assert ranking["candidates"][1]["action"] == "NOT_SELECTED"
        assert ranking["candidates"][0]["canonical_margin"] == 0
        assert ranking["tie_break"] == {
            "used": True,
            "tier": "medium",
            "confidence": 0.9,
            "preferred_token_id": second.token_id,
        }
        serialized = json.dumps(ranking)
        assert "raw_json" not in serialized and "social_urls" not in serialized
        store.close()

    asyncio.run(scenario())


def test_momentum_rewards_real_activity():
    quiet = TokenSnapshot("solana", "a", 1, 1000, 10000, 10, 1, 1)
    active = TokenSnapshot("solana", "b", 1, 50000, 1000000, 30000, 120, 30)
    assert CandidateEvaluator._momentum_score(active) > CandidateEvaluator._momentum_score(quiet)


def test_quality_does_not_reward_a_token_created_after_the_event():
    event_time = datetime(2026, 8, 31, tzinfo=timezone.utc)
    event = EventView(1, "Viral capybara", [], 80, event_time, event_time)
    snapshot = TokenSnapshot("solana", "a", 1, 50000, 1000000, 30000, 120, 30)
    before = TokenCandidate(
        chain="solana",
        address="a",
        name="Viral capybara",
        symbol="CAPY",
        created_at=event_time - timedelta(minutes=5),
    )
    after = TokenCandidate(
        chain="solana",
        address="b",
        name="Viral capybara",
        symbol="CAPY",
        created_at=event_time + timedelta(minutes=5),
    )

    before_score, _ = CandidateEvaluator._quality(event, before, snapshot, 90, 2)
    after_score, _ = CandidateEvaluator._quality(event, after, snapshot, 90, 2)

    assert before_score > after_score


def test_exit_policy_handles_liquidity_and_trailing_drawdown():
    position = Position(
        token_id="solana:a",
        event_id=1,
        chain="solana",
        address="a",
        symbol="A",
        quantity=10,
        entry_price=1,
        cost_usd=10,
        remaining_cost_usd=10,
        highest_price=2,
        opened_at="2026-01-01T00:00:00Z",
    )
    policy = PaperPolicy(
        {
            "stop_loss_pct": -0.35,
            "trailing_activate_pct": 0.6,
            "trailing_drawdown_pct": 0.28,
            "emergency_liquidity_usd": 3000,
            "max_holding_hours": 100000,
        }
    )
    low_liquidity = TokenSnapshot("solana", "a", 1.4, 1000, 10000, 1000, 10, 5)
    assert policy.exit_action(position, low_liquidity) == (1.0, "liquidity_emergency")
    trailing = TokenSnapshot("solana", "a", 1.4, 10000, 10000, 1000, 10, 5)
    assert policy.exit_action(position, trailing) == (1.0, "trailing_exit")


def test_exit_policy_uses_narrative_and_flow_decay():
    now = datetime.now(timezone.utc)
    position = Position(
        token_id="solana:a",
        event_id=1,
        chain="solana",
        address="a",
        symbol="A",
        quantity=10,
        entry_price=1,
        cost_usd=10,
        remaining_cost_usd=10,
        highest_price=1.2,
        opened_at=now - timedelta(minutes=45),
    )
    event = EventView(
        id=1,
        title="Viral event",
        aliases=["Viral"],
        attention=60,
        first_seen_at=now - timedelta(hours=4),
        last_seen_at=now - timedelta(minutes=150),
    )
    snapshot = TokenSnapshot("solana", "a", 1.05, 10000, 100000, 1000, 2, 10)
    policy = PaperPolicy(
        {
            "stop_loss_pct": -0.35,
            "trailing_activate_pct": 0.6,
            "trailing_drawdown_pct": 0.28,
            "emergency_liquidity_usd": 3000,
            "narrative_stale_minutes": 120,
            "narrative_min_holding_minutes": 20,
            "narrative_exit_buy_ratio": 0.45,
            "max_holding_hours": 24,
        }
    )
    assert policy.exit_action(position, snapshot, event=event) == (1.0, "narrative_and_flow_decay")


def test_solana_rugcheck_high_score_is_rejected():
    class Response:
        def json(self):
            return {"score_normalised": 95, "risks": [{"level": "danger"}]}

    class FakeHttp:
        async def get(self, *args, **kwargs):
            return Response()

    async def scenario():
        checker = SafetyChecker(
            FakeHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "rugcheck": True,
                "max_solana_risk_score": 79,
            },
        )
        snap = TokenSnapshot("solana", "a", 1, 10000, 100000, 1000, 10, 2)
        ok, reasons = await checker.check(snap)
        assert ok is False
        assert "solana_risk_score_too_high" in reasons

    asyncio.run(scenario())


def test_required_external_safety_reports_fail_closed():
    class FailingHttp:
        async def get(self, *args, **kwargs):
            raise TimeoutError("provider unavailable")

    async def scenario():
        checker = SafetyChecker(
            FailingHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "max_tax_pct": 12,
                "goplus_evm": True,
                "honeypot_is": True,
                "require_evm_security_report": True,
                "require_evm_simulation": False,
                "goplus_solana": True,
                "rugcheck": True,
                "require_solana_report": True,
                "max_solana_risk_score": 79,
            },
        )
        bsc = TokenSnapshot("bsc", "0x" + "1" * 40, 1, 10000, 100000, 1000, 10, 2)
        sol = TokenSnapshot("solana", "A" * 32, 1, 10000, 100000, 1000, 10, 2)
        bsc_ok, bsc_reasons = await checker.check(bsc)
        sol_ok, sol_reasons = await checker.check(sol)
        assert bsc_ok is False and "evm_security_report_unavailable" in bsc_reasons
        assert sol_ok is False and "solana_risk_report_unavailable" in sol_reasons

    asyncio.run(scenario())


def test_goplus_evm_clean_report_is_accepted_without_honeypot_call():
    address = "0x" + "1" * 40

    class Response:
        def json(self):
            return {
                "code": 1,
                "result": {
                    address.lower(): {
                        "is_honeypot": "0",
                        "is_open_source": "1",
                        "buy_tax": "0.03",
                        "sell_tax": "0.04",
                        "hidden_owner": "0",
                    }
                },
            }

    class FakeHttp:
        def __init__(self):
            self.urls = []

        async def get(self, url, *args, **kwargs):
            self.urls.append(str(url))
            return Response()

    async def scenario():
        http = FakeHttp()
        checker = SafetyChecker(
            http,
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "max_tax_pct": 12,
                "goplus_evm": True,
                "honeypot_is": True,
                "require_evm_security_report": True,
                "require_evm_simulation": False,
                "goplus_evm_require_open_source": True,
                "goplus_evm_reject_flags": ["hidden_owner"],
            },
        )
        snap = TokenSnapshot("bsc", address, 1, 10000, 100000, 1000, 10, 2)
        ok, reasons = await checker.check(snap)
        assert ok is True and reasons == []
        assert snap.buy_tax_pct == pytest.approx(3.0)
        assert snap.sell_tax_pct == pytest.approx(4.0)
        assert snap.honeypot is False and snap.sellable is True
        assert any("gopluslabs.io" in url for url in http.urls)
        assert not any("honeypot.is" in url for url in http.urls)

    asyncio.run(scenario())


def test_goplus_evm_dangerous_flag_is_rejected():
    address = "0x" + "2" * 40

    class Response:
        def json(self):
            return {
                "code": 1,
                "result": {
                    address.lower(): {
                        "is_honeypot": "0",
                        "is_open_source": "1",
                        "hidden_owner": "1",
                    }
                },
            }

    class FakeHttp:
        async def get(self, *args, **kwargs):
            return Response()

    async def scenario():
        checker = SafetyChecker(
            FakeHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "goplus_evm": True,
                "honeypot_is": False,
                "require_evm_security_report": True,
                "goplus_evm_require_open_source": True,
                "goplus_evm_reject_flags": ["hidden_owner"],
            },
        )
        ok, reasons = await checker.check(
            TokenSnapshot("bsc", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert ok is False
        assert "goplus_evm_hidden_owner" in reasons

    asyncio.run(scenario())


def test_goplus_solana_can_cover_rugcheck_outage_and_rejects_risky_authority():
    address = "A" * 32

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeHttp:
        def __init__(self, risky=False):
            self.risky = risky

        async def get(self, url, *args, **kwargs):
            if "gopluslabs.io" in str(url):
                return Response(
                    {
                        "code": 1,
                        "result": {
                            address: {
                                "mintable": {"status": "1" if self.risky else "0", "authority": []},
                                "freezable": {"status": "0", "authority": []},
                            }
                        },
                    }
                )
            raise TimeoutError("rugcheck unavailable")

    async def scenario():
        config = {
            "min_liquidity_usd": 100,
            "min_5m_transactions": 1,
            "min_buy_ratio": 0.4,
            "goplus_solana": True,
            "rugcheck": True,
            "require_solana_report": True,
            "goplus_solana_reject_flags": ["mintable", "freezable"],
        }
        clean_checker = SafetyChecker(FakeHttp(False), config)
        clean_ok, clean_reasons = await clean_checker.check(
            TokenSnapshot("solana", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert clean_ok is True and clean_reasons == []

        risky_checker = SafetyChecker(FakeHttp(True), config)
        risky_ok, risky_reasons = await risky_checker.check(
            TokenSnapshot("solana", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert risky_ok is False
        assert "goplus_solana_mintable" in risky_reasons

    asyncio.run(scenario())
