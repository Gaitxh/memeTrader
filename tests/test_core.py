from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import httpx
from solders.pubkey import Pubkey

from memetrader.collectors import (
    DexScreenerClient,
    EvmRouteQuoteError,
    EvmUniswapV3QuoteClient,
    JupiterNoRouteError,
    JupiterQuoteError,
    JupiterQuoteProtocolError,
    JupiterQuoteClient,
    MastodonCollector,
    PumpPortalCollector,
)
from memetrader.models import CandidateDecision, EventView, Observation, ObservationRevisionHandoff, Position, TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
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


def test_event_claim_assessments_are_forward_append_only_context_only_and_future_safe(tmp_path: Path):
    store = Store(tmp_path / "claim-assessments.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = datetime.now(timezone.utc)
    common = dict(
        source_kind="news",
        title="Viral seal story spreads online",
        text="Viral seal story spreads online",
        observed_at=now,
        ingested_at=now,
        role="identity",
    )
    event_id, _, _ = engine.ingest(
        Observation(
            source="agent-scout:publisher.example",
            source_item_id="report",
            raw={
                "agent_task": "trend_scout",
                "claim_status": "probable_report",
                "factual_confidence": 0.82,
                "source_identity_confidence": 0.9,
                "attention_confidence": 0.7,
                "meme_catalyst_strength": 0.88,
                "correction_risk": 0.2,
                "decision_eligible": False,
            },
            **common,
        )
    )
    engine.ingest(
        Observation(
            source="agent-scout:publisher.example",
            source_item_id="correction",
            raw={"agent_task": "trend_scout", "claim_status": "correction"},
            **common,
        )
    )
    future = now + timedelta(hours=1)
    engine.ingest(
        Observation(
            source="agent-scout:future.example",
            source_item_id="future",
            raw={"agent_task": "trend_scout", "claim_status": "confirmed_fact"},
            **{**common, "observed_at": future, "ingested_at": future},
        )
    )

    registration = store.db.execute(
        "SELECT * FROM event_claim_ledger_registrations WHERE definition_version=?",
        (Store.EVENT_CLAIM_ASSESSMENT_VERSION,),
    ).fetchone()
    rows = list(store.db.execute(
        "SELECT * FROM event_claim_assessments WHERE event_id=? ORDER BY id", (event_id,)
    ))
    assert registration is not None
    assert [row["claim_status"] for row in rows] == ["probable_report", "correction", "excluded_future"]
    assert rows[0]["factual_confidence"] == pytest.approx(0.82)
    assert rows[0]["trigger_decision_eligible"] == 0
    assert rows[1]["previous_assessment_id"] == rows[0]["id"]
    assert rows[2]["exclusion_reason"] == "trigger_observed_in_future"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE event_claim_assessments SET claim_status='confirmed_fact' WHERE id=?",
            (rows[0]["id"],),
        )
    store.create_event("Legacy event without claim backfill", ["legacy claim"], 10, now)
    assert store.db.execute("SELECT COUNT(*) FROM event_claim_assessments").fetchone()[0] == 3
    store.close()


def test_source_item_revisions_are_forward_append_only_shadow_and_future_safe(tmp_path: Path):
    store = Store(tmp_path / "source-revisions.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    base = dict(
        source="browser:x:example",
        source_kind="social",
        title="A public post creates a meme narrative",
        text="Original public post",
        url="https://x.com/example/status/123?utm_source=test&token=never-return",
        author="example",
        observed_at=now,
        ingested_at=now,
        availability_proof="local_receive",
        source_item_id="x:example:123",
        raw={"source_item_state": "present", "view_count": 10},
    )
    baseline_handoff = ObservationRevisionHandoff()
    event_id, _, created = engine.ingest(
        Observation(**base), revision_handoff=baseline_handoff
    )
    assert created is True
    assert baseline_handoff.revision_id is not None
    assert baseline_handoff.claim_relation_ids == ()
    first_event = store.get_event(event_id)
    first_observation_count = store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    identical = {**base, "raw": {"source_item_state": "present", "view_count": 999}}
    unchanged_handoff = ObservationRevisionHandoff(999, (999,))
    assert engine.ingest(
        Observation(**identical), revision_handoff=unchanged_handoff
    ) == (event_id, False, False)
    assert unchanged_handoff.revision_id is None
    assert unchanged_handoff.claim_relation_ids == ()
    edited = {**base, "text": "Edited public post with a correction note"}
    edit_handoff = ObservationRevisionHandoff()
    assert engine.ingest(
        Observation(**edited), revision_handoff=edit_handoff
    ) == (event_id, False, False)
    assert edit_handoff.revision_id is not None
    assert len(edit_handoff.claim_relation_ids) == 1
    deleted = {
        **edited,
        "role": "identity",
        "raw": {
            "source_item_state": "deleted",
            "source_item_state_evidence": "platform_deleted_marker",
        },
    }
    assert engine.ingest(Observation(**deleted)) == (event_id, False, False)
    assert engine.ingest(Observation(**edited)) == (event_id, False, False)
    future = now + timedelta(hours=1)
    assert engine.ingest(Observation(**{**edited, "text": "Future capture", "observed_at": future, "ingested_at": future})) == (
        event_id, False, False
    )

    rows = list(store.db.execute("SELECT * FROM source_item_revisions ORDER BY sequence_no"))
    assert [row["revision_kind"] for row in rows] == [
        "baseline", "content_edit", "explicit_deleted", "restored", "content_edit"
    ]
    assert [row["sequence_no"] for row in rows] == [1, 2, 3, 4, 5]
    assert rows[0]["previous_revision_id"] is None
    assert rows[-1]["previous_revision_id"] == rows[-2]["id"]
    assert rows[2]["local_state"] == "deleted"
    assert rows[2]["semantic_signal"] == "none"
    assert "capture_observed_in_future" in rows[-1]["temporal_exclusion_reason"]
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == first_observation_count
    current_event = store.get_event(event_id)
    assert current_event.attention == first_event.attention
    assert current_event.last_seen_at == first_event.last_seen_at
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE source_item_revisions SET local_state='present' WHERE id=?", (rows[2]["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM source_item_revision_registrations")
    store.close()


def test_source_item_revision_does_not_backfill_or_create_unanchored_tombstone(tmp_path: Path):
    store = Store(tmp_path / "source-revision-boundary.sqlite3")
    historical = datetime(2020, 1, 1, tzinfo=timezone.utc)
    store.add_observation(
        Observation(
            source="historical-feed", source_kind="news", title="Historical item",
            url="https://example.com/history", source_item_id="history-1",
            observed_at=historical, ingested_at=historical,
        )
    )
    assert store.db.execute("SELECT COUNT(*) FROM source_item_revisions").fetchone()[0] == 0
    engine = EventEngine(store)
    known_result = engine.ingest(
        Observation(
            source="historical-feed", source_kind="news", title="Source item state marker",
            url="https://example.com/history", source_item_id="history-1", role="identity",
            raw={
                "source_item_state": "deleted",
                "source_item_state_evidence": "publisher_deleted_marker",
            },
        )
    )
    assert known_result == (0, False, False)
    recorded = store.db.execute("SELECT * FROM source_item_revisions").fetchone()
    assert recorded["revision_kind"] == "explicit_deleted"
    assert recorded["sequence_no"] == 1
    result = engine.ingest(
        Observation(
            source="new-feed", source_kind="news", title="Source item state marker",
            source_item_id="missing", role="identity",
            raw={
                "source_item_state": "deleted",
                "source_item_state_evidence": "publisher_deleted_marker",
            },
        )
    )
    assert result == (0, False, False)
    assert store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    assert store.db.execute("SELECT COUNT(*) FROM source_item_revisions").fetchone()[0] == 1
    store.close()


def test_claim_relations_are_atomic_forward_only_and_keep_deletion_semantically_separate(tmp_path: Path):
    store = Store(tmp_path / "claim-relations.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    common = dict(
        source="browser:x:publisher",
        source_kind="social",
        title="Publisher posts a viral animal claim",
        url="https://x.com/publisher/status/501",
        author="publisher",
        source_item_id="x:publisher:501",
        observed_at=now,
        ingested_at=now,
        availability_proof="local_receive",
    )
    event_id, _, created = engine.ingest(
        Observation(text="Original claim", raw={"source_item_state": "present"}, **common)
    )
    assert created is True
    assert engine.ingest(
        Observation(text="Original claim", raw={"source_item_state": "present"}, **common)
    ) == (event_id, False, False)
    engine.ingest(
        Observation(text="Edited claim", raw={"source_item_state": "present"}, **common)
    )
    correction_handoff = ObservationRevisionHandoff()
    engine.ingest(
        Observation(
            text="Publisher correction",
            role="identity",
            raw={
                "source_item_state": "correction",
                "source_item_state_evidence": "publisher_correction_marker",
                "claim_target_url": common["url"],
            },
            **common,
        ),
        revision_handoff=correction_handoff,
    )
    engine.ingest(
        Observation(
            text="Publisher correction",
            role="identity",
            raw={
                "source_item_state": "deleted",
                "source_item_state_evidence": "publisher_deleted_marker",
            },
            **common,
        )
    )
    future = now + timedelta(hours=1)
    engine.ingest(
        Observation(
            text="Future restored capture",
            role="identity",
            raw={"source_item_state": "present"},
            **{**common, "observed_at": future, "ingested_at": future},
        )
    )

    revisions = list(store.db.execute("SELECT * FROM source_item_revisions ORDER BY sequence_no"))
    relations = list(store.db.execute("SELECT * FROM event_claim_relations ORDER BY id"))
    assert len(revisions) == 5
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    assert [row["relation_type"] for row in relations] == [
        "supersedes", "supersedes", "corrects", "supersedes", "supersedes"
    ]
    correction = next(row for row in relations if row["relation_type"] == "corrects")
    assert correction_handoff.revision_id == correction["source_revision_id"]
    assert set(correction_handoff.claim_relation_ids) == {
        row["id"] for row in relations if row["source_revision_id"] == correction["source_revision_id"]
    }
    assert correction["source_revision_id"] == revisions[2]["id"]
    assert correction["target_revision_id"] == revisions[1]["id"]
    assert correction["resolution_status"] == "resolved"
    assert correction["relation_scope"] == "same_item_version"
    assert not any(row["relation_type"] == "retracts" for row in relations)
    assert relations[-1]["resolution_status"] == "excluded_temporal"
    assert relations[-1]["target_revision_id"] is None
    engine.ingest(
        Observation(
            text="Normal capture after excluded future revision",
            role="identity",
            raw={
                "source_item_state": "correction",
                "source_item_state_evidence": "publisher_correction_marker",
                "claim_target_url": common["url"],
            },
            **common,
        )
    )
    relations = list(store.db.execute("SELECT * FROM event_claim_relations ORDER BY id"))
    assert [row["resolution_status"] for row in relations[-2:]] == [
        "excluded_temporal", "excluded_temporal"
    ]
    assert all(row["target_revision_id"] is None for row in relations[-2:])
    assert all(row["target_match_count"] == 0 for row in relations[-2:])
    assert all(
        "capture_" in str(row["temporal_exclusion_reason"])
        for row in relations[-2:]
    )
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in relations)
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE event_claim_relations SET resolution_status='resolved' WHERE id=?", (relations[-1]["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM event_claim_relation_registrations")
    store.close()
    reopened = Store(tmp_path / "claim-relations.sqlite3")
    assert reopened.db.execute("SELECT COUNT(*) FROM event_claim_relations").fetchone()[0] == len(relations)
    reopened.close()


def test_claim_relations_do_not_backfill_capture_from_before_relation_registration(tmp_path: Path):
    store = Store(tmp_path / "claim-registration-boundary.sqlite3")
    source_registered = parse_time(store.db.execute(
        "SELECT registered_at FROM source_item_revision_registrations WHERE definition_version=?",
        (Store.SOURCE_ITEM_REVISION_VERSION,),
    ).fetchone()["registered_at"])
    relation_registered = parse_time(store.db.execute(
        "SELECT registered_at FROM event_claim_relation_registrations WHERE definition_version=?",
        (Store.EVENT_CLAIM_RELATION_VERSION,),
    ).fetchone()["registered_at"])
    assert source_registered < relation_registered
    old_capture = source_registered + (relation_registered - source_registered) / 2
    engine = EventEngine(store, similarity=0.1)
    common = dict(
        source="boundary-source", source_kind="news", title="Boundary claim",
        url="https://publisher.example/boundary", source_item_id="boundary-1",
        observed_at=old_capture, ingested_at=old_capture,
    )
    engine.ingest(Observation(text="First old capture", **common))
    engine.ingest(Observation(text="Edited old capture", **common))
    assert store.db.execute("SELECT COUNT(*) FROM source_item_revisions").fetchone()[0] == 2
    assert store.db.execute("SELECT COUNT(*) FROM event_claim_relations").fetchone()[0] == 0
    store.close()


def test_claim_relation_exact_target_is_unique_safe_and_never_late_bound(tmp_path: Path):
    store = Store(tmp_path / "claim-targets.sqlite3")
    engine = EventEngine(store, similarity=0.1)
    now = utcnow()
    target_url = "https://publisher.example/story?utm_source=test&secret=never-store"
    target_event, _, _ = engine.ingest(
        Observation(
            source="publisher-a", source_kind="news", title="Viral otter report",
            text="Original report", url=target_url, source_item_id="report-a",
            observed_at=now, ingested_at=now,
        )
    )
    correction_event, _, _ = engine.ingest(
        Observation(
            source="publisher-correction", source_kind="news", title="Viral otter report corrected",
            text="Correction notice", url="https://publisher.example/correction-1",
            source_item_id="correction-1", role="identity", observed_at=now, ingested_at=now,
            raw={
                "source_item_state": "correction",
                "source_item_state_evidence": "publisher_correction_marker",
                "claim_target_url": target_url,
            },
        )
    )
    assert correction_event == target_event
    resolved = store.db.execute(
        "SELECT * FROM event_claim_relations WHERE relation_type='corrects' ORDER BY id LIMIT 1"
    ).fetchone()
    assert resolved["resolution_status"] == "resolved"
    assert resolved["relation_scope"] == "cross_item_exact_url"
    assert resolved["target_revision_id"] is not None
    assert len(resolved["target_url_fingerprint"]) == 64
    stored_raw = store.db.execute(
        "SELECT raw_json FROM observations WHERE source='publisher-correction'"
    ).fetchone()["raw_json"]
    assert "claim_target_url" not in stored_raw and "never-store" not in stored_raw

    retraction_event, _, retraction_created = engine.ingest(
        Observation(
            source="publisher-retraction", source_kind="news", title="Viral otter report retracted",
            text="Retraction notice", url="https://publisher.example/retraction-1",
            source_item_id="retraction-1", role="identity", observed_at=now, ingested_at=now,
            raw={
                "source_item_state": "retracted",
                "source_item_state_evidence": "publisher_retraction_marker",
                "claim_target_url": target_url,
            },
        )
    )
    assert retraction_created is True
    assert retraction_event == target_event
    retracted = store.db.execute(
        "SELECT * FROM event_claim_relations WHERE relation_type='retracts' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert retracted["resolution_status"] == "resolved"
    assert retracted["relation_scope"] == "cross_item_exact_url"
    assert retracted["target_revision_id"] == resolved["target_revision_id"]

    engine.ingest(
        Observation(
            source="publisher-b", source_kind="news", title="Viral otter report mirror",
            text="Independent item sharing the same canonical URL", url=target_url,
            source_item_id="report-b", observed_at=now, ingested_at=now,
        )
    )
    engine.ingest(
        Observation(
            source="publisher-correction", source_kind="news", title="Second otter correction",
            text="Second correction notice", url="https://publisher.example/correction-2",
            source_item_id="correction-2", role="identity", observed_at=now, ingested_at=now,
            raw={
                "source_item_state": "correction",
                "source_item_state_evidence": "publisher_correction_marker",
                "claim_target_url": target_url,
            },
        )
    )
    ambiguous = store.db.execute(
        "SELECT * FROM event_claim_relations WHERE relation_type='corrects' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert ambiguous["resolution_status"] == "ambiguous_target"
    assert ambiguous["target_revision_id"] is None
    assert ambiguous["target_match_count"] == 2

    missing_url = "https://publisher.example/not-yet-observed"
    engine.ingest(
        Observation(
            source="publisher-correction", source_kind="news", title="Missing target correction",
            text="Target not yet observed", url="https://publisher.example/correction-3",
            source_item_id="correction-3", role="identity", observed_at=now, ingested_at=now,
            raw={
                "source_item_state": "correction",
                "source_item_state_evidence": "publisher_correction_marker",
                "claim_target_url": missing_url,
            },
        )
    )
    missing = store.db.execute(
        "SELECT * FROM event_claim_relations WHERE relation_type='corrects' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert missing["resolution_status"] == "target_not_found"
    engine.ingest(
        Observation(
            source="publisher-late", source_kind="news", title="Late original target",
            text="Observed only after the correction", url=missing_url, source_item_id="late-target",
            observed_at=now, ingested_at=now,
        )
    )
    unchanged = store.db.execute(
        "SELECT * FROM event_claim_relations WHERE id=?", (missing["id"],)
    ).fetchone()
    assert unchanged["resolution_status"] == "target_not_found"
    assert unchanged["target_revision_id"] is None
    store.close()


def test_observation_provenance_is_forward_immutable_and_separates_origin_transport(tmp_path: Path):
    store = Store(tmp_path / "observation-provenance.sqlite3")
    now = utcnow()
    direct = Observation(
        source="x:example", source_kind="social", title="Direct public post",
        url="https://x.com/example/status/123?token=must-not-persist", author="example",
        observed_at=now, ingested_at=now, availability_proof="local_receive",
        source_item_id="x:example:123",
        raw={"browser": {"platform": "x"}, "source_entity_id": "example"},
    )
    direct_id, created = store.add_observation(direct)
    assert created is True
    relay_id, _ = store.add_observation(
        Observation(
            source="aggregated-feed", source_kind="news", title="Relayed report",
            url="https://publisher.example/report", author="Publisher",
            observed_at=now, ingested_at=now, source_item_id="relay-1",
            raw={
                "feed_url": "https://aggregator.example/feed.xml",
                "publisher_url": "https://publisher.example/",
            },
        )
    )
    unknown_id, _ = store.add_observation(
        Observation(
            source="unknown-source", source_kind="news", title="Unknown route",
            observed_at=now, ingested_at=now, source_item_id="unknown-1",
        )
    )
    future = now + timedelta(hours=1)
    future_id, _ = store.add_observation(
        Observation(
            source="x:future", source_kind="social", title="Future direct post",
            url="https://x.com/future/status/456", author="future",
            observed_at=future, ingested_at=future, availability_proof="local_receive",
            source_item_id="x:future:456", raw={"browser": {"platform": "x"}},
        )
    )
    historical = datetime(2020, 1, 1, tzinfo=timezone.utc)
    store.add_observation(
        Observation(
            source="legacy", source_kind="news", title="Legacy observation",
            observed_at=historical, ingested_at=historical, source_item_id="legacy-1",
        )
    )
    store.add_observation(direct)

    rows = {
        int(row["observation_id"]): row
        for row in store.db.execute("SELECT * FROM observation_provenance_assertions")
    }
    assert set(rows) == {direct_id, relay_id, unknown_id, future_id}
    assert rows[direct_id]["route_kind"] == "direct"
    assert rows[direct_id]["origin_identity_state"] == "proven_direct_item"
    assert rows[direct_id]["transport_platform"] == "none"
    assert "must-not-persist" not in rows[direct_id]["origin_item_url"]
    assert rows[relay_id]["route_kind"] == "relay"
    assert rows[relay_id]["origin_identity_state"] == "asserted_upstream"
    assert rows[relay_id]["transport_platform"] == "rss"
    assert rows[unknown_id]["origin_identity_state"] == "unknown"
    assert rows[future_id]["origin_identity_state"] == "excluded_future"
    assert "source_observed_in_future" in rows[future_id]["temporal_exclusion_reason"]
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows.values())
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE observation_provenance_assertions SET route_kind='relay' WHERE observation_id=?",
            (direct_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM observation_provenance_registrations")
    store.close()


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


def test_token_launch_facts_survive_hydration_and_keep_migration_separate(tmp_path: Path):
    store = Store(tmp_path / "token-launch-facts.sqlite3", initial_cash_usd=1000)
    observed = datetime(2026, 9, 3, 1, 2, 3, tzinfo=timezone.utc)
    ingested = observed + timedelta(seconds=2)
    create = TokenCandidate(
        chain="solana",
        address="LaunchMint",
        name="Launch",
        symbol="NEW",
        first_seen_at=observed,
        source="pumpportal:create",
        raw={
            "mint": "LaunchMint",
            "txType": "create",
            "pump_event_type": "create",
            "traderPublicKey": "CreatorWallet",
            "signature": "CreateSignature",
            "bondingCurveKey": "CurveKey",
            "pool": "pump",
            "initialBuy": 123.5,
            "solAmount": 0.25,
            "marketCapSol": 30.0,
            "vSolInBondingCurve": 30.25,
            "vTokensInBondingCurve": 999_876.5,
        },
    )
    create_id = store.record_token_launch_fact(create, ingested_at=ingested)
    store.upsert_token(create, seen_at=ingested)
    hydrated = TokenCandidate(
        chain="solana",
        address="LaunchMint",
        name="Launch hydrated",
        symbol="NEW",
        source="dexscreener",
        raw={"pair": {"pairAddress": "PairAfterLaunch", "dexId": "pumpswap"}},
    )
    store.upsert_token(hydrated, seen_at=ingested + timedelta(minutes=1))

    assert store.record_token_launch_fact(create, ingested_at=ingested) == create_id
    migration = TokenCandidate(
        chain="solana",
        address="LaunchMint",
        name="",
        source="pumpportal:migration",
        first_seen_at=observed + timedelta(minutes=5),
        raw={
            "mint": "LaunchMint",
            "txType": "migrate",
            "pump_event_type": "migrate",
            "signature": "MigrationSignature",
            "pool": "pump-amm",
        },
    )
    migration_id = store.record_token_launch_fact(migration, ingested_at=ingested + timedelta(minutes=5))

    rows = list(store.db.execute("SELECT * FROM token_launch_facts ORDER BY id"))
    assert len(rows) == 2
    assert migration_id != create_id
    assert rows[0]["launch_event_type"] == "create"
    assert rows[1]["launch_event_type"] == "migration"
    assert rows[0]["creator_address"] == "CreatorWallet"
    assert rows[0]["create_signature"] == "CreateSignature"
    assert rows[0]["pool_label"] == "pump"
    assert rows[0]["source_observed_at"] == iso(observed)
    assert rows[0]["ingested_at"] == iso(ingested)
    assert rows[0]["decision_eligible"] == 0
    assert rows[0]["affects"] == "none"
    assert json.loads(store.db.execute(
        "SELECT raw_json FROM tokens WHERE token_id='solana:LaunchMint'"
    ).fetchone()["raw_json"])["pair"]["pairAddress"] == "PairAfterLaunch"
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE token_launch_facts SET affects='none' WHERE id=?", (create_id,))
    store.close()


def test_creator_launch_risk_shadow_is_forward_only_and_immutable(tmp_path: Path):
    store = Store(tmp_path / "creator-launch-risk.sqlite3", initial_cash_usd=1000)
    first_at = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)

    def launch(address: str, observed_at: datetime) -> TokenCandidate:
        return TokenCandidate(
            chain="solana",
            address=address,
            name=address,
            source="pumpportal:create",
            first_seen_at=observed_at,
            raw={
                "mint": address,
                "txType": "create",
                "pump_event_type": "create",
                "traderPublicKey": "CreatorWallet",
                "signature": f"Signature-{address}",
                "bondingCurveKey": f"Curve-{address}",
                "pool": "pump",
                "initialBuy": 100,
                "solAmount": 0.2,
                "marketCapSol": 25,
            },
        )

    first = launch("CreatorMintOne", first_at)
    second = launch("CreatorMintTwo", first_at + timedelta(minutes=12))
    store.upsert_token(first, seen_at=first_at)
    store.record_token_launch_fact(first, ingested_at=first_at + timedelta(seconds=1))
    store.upsert_token(second, seen_at=second.first_seen_at)
    second_fact_id = store.record_token_launch_fact(
        second, ingested_at=second.first_seen_at + timedelta(seconds=1)
    )

    view = Store.creator_launch_risk_for_token_from_connection(store.db, second.token_id)
    assert view is not None and view["status"] == "observed"
    assert view["launch"]["provider_verified"] is False
    assert view["launch"]["provider_semantics"] == "provider_observed_not_rpc_verified"
    assert view["risk_shadow"]["prior_launch_count"] == 1
    assert view["risk_shadow"]["prior_launch_24h_count"] == 1
    assert view["risk_shadow"]["seconds_since_prior_launch"] == 12 * 60
    assert view["risk_shadow"]["history_left_censored"] is True
    assert view["decision_eligible"] is False and view["affects"] == "none"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE creator_launch_risk_cohorts SET prior_launch_count=2 WHERE launch_fact_id=?",
            (second_fact_id,),
        )
    store.close()


def test_pumpportal_freezes_local_receive_time_before_consumer_delay(monkeypatch):
    received = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)

    class FakeSocket:
        def __init__(self):
            self.sent = []
            self.item = json.dumps(
                {
                    "mint": "ReceiveTimeMint",
                    "txType": "create",
                    "signature": "ReceiveTimeSignature",
                }
            )

        async def send(self, value):
            self.sent.append(value)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.item is None:
                raise StopAsyncIteration
            item, self.item = self.item, None
            return item

    class FakeContext:
        def __init__(self):
            self.socket = FakeSocket()

        async def __aenter__(self):
            return self.socket

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr("memetrader.collectors.utcnow", lambda: received)
    monkeypatch.setattr(
        "memetrader.collectors.websockets.connect", lambda *_args, **_kwargs: FakeContext()
    )
    async def collect_one():
        stream = PumpPortalCollector().stream()
        token = await anext(stream)
        await stream.aclose()
        return token

    token = asyncio.run(collect_one())

    assert token.first_seen_at == received


def test_token_market_surfaces_preserve_chain_specific_pool_semantics(tmp_path: Path):
    store = Store(tmp_path / "token-market-surfaces.sqlite3", initial_cash_usd=1000)
    observed = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)

    migrated = TokenCandidate(
        chain="solana",
        address="CanonicalMint",
        name="Canonical",
        source="pumpportal:migration",
        first_seen_at=observed,
        raw={
            "mint": "CanonicalMint",
            "txType": "migrate",
            "pump_event_type": "migrate",
            "signature": "CanonicalMigration",
            "pool": "pump-amm",
        },
    )
    store.record_token_launch_fact(migrated, ingested_at=observed)
    store.upsert_token(migrated, seen_at=observed)
    store.upsert_token(
        TokenCandidate(
            chain="solana",
            address="CanonicalMint",
            name="Canonical",
            source="dexscreener",
            raw={
                "pair": {
                    "chainId": "solana",
                    "dexId": "pumpswap",
                    "pairAddress": "CanonicalPair",
                    "baseToken": {"address": "CanonicalMint"},
                    "quoteToken": {"address": "So111"},
                    "pairCreatedAt": 1_788_400_000_000,
                }
            },
        ),
        seen_at=observed + timedelta(seconds=1),
    )
    store.upsert_token(
        TokenCandidate(
            chain="solana",
            address="OrdinaryMint",
            name="Ordinary",
            source="dexscreener",
            raw={
                "pair": {
                    "chainId": "solana",
                    "dexId": "pumpswap",
                    "pairAddress": "OrdinaryPair",
                    "baseToken": {"address": "OrdinaryMint"},
                    "quoteToken": {"address": "So111"},
                }
            },
        ),
        seen_at=observed,
    )
    store.upsert_token(
        TokenCandidate(
            chain="bsc",
            address="PancakeMint",
            name="Pancake",
            source="dexscreener",
            raw={
                "pair": {
                    "chainId": "bsc",
                    "dexId": "pancakeswap",
                    "pairAddress": "PancakePair",
                    "labels": ["v2"],
                    "baseToken": {"address": "PancakeMint"},
                    "quoteToken": {"address": "WBNB"},
                }
            },
        ),
        seen_at=observed,
    )
    store.upsert_token(
        TokenCandidate(
            chain="solana",
            address="RayMint",
            name="Ray",
            source="dexscreener",
            raw={
                "pair": {
                    "chainId": "solana",
                    "dexId": "raydium",
                    "pairAddress": "RayPair",
                    "labels": ["CLMM"],
                    "baseToken": {"address": "RayMint"},
                    "quoteToken": {"address": "So111"},
                }
            },
        ),
        seen_at=observed,
    )
    store.upsert_token(
        TokenCandidate(
            chain="solana",
            address="CurveMint",
            name="Curve",
            source="dexscreener",
            raw={
                "pair": {
                    "chainId": "solana",
                    "dexId": "pumpfun",
                    "pairAddress": "CurveAccount",
                    "baseToken": {"address": "CurveMint"},
                    "quoteToken": {"address": "So111"},
                }
            },
        ),
        seen_at=observed,
    )

    rows = {
        row["pair_address"]: row
        for row in store.db.execute(
            "SELECT * FROM token_market_surfaces WHERE pair_address<>'' ORDER BY id"
        )
    }
    assert store.db.execute("SELECT COUNT(*) FROM token_market_surfaces").fetchone()[0] == 5
    assert rows["CanonicalPair"]["surface_type"] == "CPMM"
    assert rows["CanonicalPair"]["canonical_status"] == "unknown"
    assert rows["CanonicalPair"]["liquidity_control"] == "unknown"
    assert rows["CanonicalPair"]["migration_lineage"] == ""
    assert rows["OrdinaryPair"]["canonical_status"] == "unknown"
    assert rows["OrdinaryPair"]["liquidity_control"] == "unknown"
    assert rows["PancakePair"]["surface_type"] == "v2"
    assert rows["RayPair"]["surface_type"] == "CLMM"
    assert rows["RayPair"]["liquidity_control"] == "nft_position"
    assert rows["CurveAccount"]["surface_type"] == "bonding_curve"
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows.values())
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_market_surfaces SET affects='none' WHERE pair_address='CanonicalPair'"
        )
    store.close()


def test_liquidity_survival_shadow_is_forward_same_pair_and_non_activating(tmp_path: Path, monkeypatch):
    clock = {"now": datetime(2026, 9, 3, 3, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(Store, "LIQUIDITY_SURVIVAL_ENABLED", True)
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock["now"])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock["now"])
    store = Store(tmp_path / "liquidity-survival.sqlite3", initial_cash_usd=1000)
    clock["now"] += timedelta(seconds=2)

    pair = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "ExactPair",
        "labels": ["CPMM"],
        "baseToken": {"address": "SurvivalMint"},
        "quoteToken": {"address": "So111"},
        "liquidity": {"usd": 15_000, "base": 1_000_000, "quote": 100},
    }
    token = TokenCandidate(
        chain="solana",
        address="SurvivalMint",
        name="Survival",
        source="dexscreener",
        raw={"pair": pair},
    )
    store.upsert_token(token, seen_at=clock["now"])
    baseline_id = store.add_snapshot(
        TokenSnapshot(
            "solana",
            token.address,
            0.01,
            15_000,
            100_000,
            25_000,
            40,
            20,
            observed_at=clock["now"],
            ingested_at=clock["now"],
            provider="dexscreener",
            raw={"pair": pair},
        )
    )
    cohort = store.db.execute("SELECT * FROM liquidity_survival_cohorts").fetchone()
    assert cohort is not None
    assert cohort["baseline_snapshot_id"] == baseline_id
    assert cohort["pair_address"] == "ExactPair"
    assert cohort["surface_type"] == "CPMM"
    assert store.db.execute("SELECT COUNT(*) FROM liquidity_survival_targets").fetchone()[0] == 4

    clock["now"] += timedelta(minutes=1, seconds=5)
    collapsed_pair = {**pair, "liquidity": {"usd": 1_000, "base": 900_000, "quote": 7}}
    store.upsert_token(
        TokenCandidate(
            chain="solana",
            address=token.address,
            name=token.name,
            source="dexscreener",
            raw={"pair": collapsed_pair},
        ),
        seen_at=clock["now"],
    )
    store.add_snapshot(
        TokenSnapshot(
            "solana",
            token.address,
            0.001,
            1_000,
            10_000,
            5_000,
            5,
            30,
            observed_at=clock["now"],
            ingested_at=clock["now"],
            provider="dexscreener",
            raw={"pair": collapsed_pair},
        )
    )
    one_minute = store.db.execute(
        "SELECT * FROM liquidity_survival_outcomes WHERE horizon_minutes=1"
    ).fetchone()
    assert one_minute["status"] == "observed"
    assert one_minute["failure_mode"] == "liquidity_collapse_unclassified"
    assert one_minute["liquidity_ratio"] == pytest.approx(1 / 15)

    curve_pair = {
        "chainId": "solana",
        "dexId": "pumpfun",
        "pairAddress": "CurveOnly",
        "baseToken": {"address": "CurveOnlyMint"},
        "quoteToken": {"address": "So111"},
        "liquidity": {"usd": 20_000},
    }
    curve = TokenCandidate(
        chain="solana",
        address="CurveOnlyMint",
        name="Curve",
        source="dexscreener",
        raw={"pair": curve_pair},
    )
    store.upsert_token(curve, seen_at=clock["now"])
    store.add_snapshot(
        TokenSnapshot(
            "solana", curve.address, 0.01, 20_000, 50_000, 10_000, 20, 10,
            observed_at=clock["now"], ingested_at=clock["now"], provider="dexscreener",
            raw={"pair": curve_pair},
        )
    )
    assert store.db.execute(
        "SELECT COUNT(*) FROM liquidity_survival_cohorts WHERE pair_address='CurveOnly'"
    ).fetchone()[0] == 0

    baseline_at = parse_time(cohort["baseline_observed_at"])
    clock["now"] = baseline_at + timedelta(minutes=6, seconds=1)
    assert store.finalize_liquidity_survival_deadlines(now=clock["now"]) == 1
    missing = store.db.execute(
        "SELECT * FROM liquidity_survival_outcomes WHERE horizon_minutes=5"
    ).fetchone()
    assert missing["status"] == "missing"
    assert missing["reason"] == "scheduler_missed_deadline"
    legacy = store.db.execute(
        """
        INSERT INTO liquidity_survival_targets(
            definition_version,cohort_id,horizon_minutes,target_at,deadline_at,registered_at
        ) VALUES('liquidity-survival-shadow/legacy',?,?,?,?,?)
        """,
        (
            int(cohort["id"]),
            999,
            iso(clock["now"]),
            iso(clock["now"] + timedelta(seconds=10)),
            iso(clock["now"]),
        ),
    ).lastrowid
    assert all(
        int(target["id"]) != int(legacy)
        for target in store.due_liquidity_survival_targets(now=clock["now"], limit=20)
    )
    with pytest.raises(ValueError, match="version mismatch"):
        store.record_liquidity_survival_attempt(
            int(legacy),
            requested_at=clock["now"],
            completed_at=clock["now"],
            status="no_pair",
            reason="legacy",
        )
    clock["now"] += timedelta(seconds=11)
    assert store.finalize_liquidity_survival_deadlines(now=clock["now"]) == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM liquidity_survival_outcomes WHERE target_id=?", (int(legacy),)
    ).fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE liquidity_survival_cohorts SET affects='none' WHERE id=?",
            (int(cohort["id"]),),
        )
    store.close()


def test_token_universe_quote_attempts_record_terminal_errors_and_defer_hot_retry(tmp_path: Path):
    store = Store(tmp_path / "quote-attempts.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="Q" * 32, name="Quote Queue", symbol="QQ")
    discovered_at = utcnow()
    store.upsert_token(token, seen_at=discovered_at)
    discovery_round = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        started_at=discovered_at,
    )
    store.add_token_discovery_exposure(
        discovery_round, token_id=token.token_id, chain=token.chain, role="create",
        first_local_discovery=True, new_token=True, observed_at=discovered_at,
    )
    store.finish_token_discovery_round(discovery_round, status="completed", returned_count=1)
    due = store.due_token_universe_quotes(now=discovered_at + timedelta(seconds=1))
    assert len(due) == 1 and due[0]["role"] == "universe_baseline"

    first_round = store.start_token_discovery_round(
        provider="dexscreener", surface="universe_baseline", mode="batch_quote",
        chain_scope="solana", started_at=discovered_at + timedelta(seconds=1),
    )
    attempt_ids = store.start_token_discovery_quote_attempts(
        first_round, due, requested_at=discovered_at + timedelta(seconds=1),
    )
    attempt_id = attempt_ids[(token.token_id, "universe_baseline")]
    retry_after = store.finish_token_discovery_quote_attempt(
        attempt_id, status="error", reason_code="batch_request_failed",
        error_type="PoolTimeout", completed_at=discovered_at + timedelta(seconds=61),
    )
    store.finish_token_discovery_round(
        first_round, status="error", requested_count=1, error_type="PoolTimeout",
        completed_at=discovered_at + timedelta(seconds=61),
    )
    attempt = store.db.execute(
        "SELECT * FROM token_discovery_quote_attempts WHERE id=?", (attempt_id,)
    ).fetchone()
    assert attempt["status"] == "error" and attempt["error_type"] == "PoolTimeout"
    assert attempt["latency_ms"] == pytest.approx(60_000, abs=20)
    assert attempt["queue_age_seconds"] == pytest.approx(1, abs=0.1)
    assert parse_time(retry_after) > parse_time(attempt["completed_at"])
    assert store.due_token_universe_quotes(
        now=parse_time(attempt["completed_at"]) + timedelta(seconds=1)
    ) == []
    assert store.due_token_universe_quotes(
        now=parse_time(retry_after) + timedelta(seconds=1)
    )[0]["token_id"] == token.token_id

    summary = store.token_discovery_quote_attempt_summary_from_connection(store.db)
    assert summary["summary"]["attempts"] == 1
    assert summary["summary"]["errors"] == 1
    assert summary["summary"]["request_rounds"] == 1
    assert summary["summary"]["request_error_rounds"] == 1
    assert summary["summary"]["token_errors_per_error_round"] == 1
    assert summary["summary"]["backoff_active"] == 1
    assert summary["items"][0]["error_types"] == [
        {"error_type": "PoolTimeout", "count": 1}
    ]
    assert summary["items"][0]["request_rounds"] == 1
    assert summary["items"][0]["request_error_rounds"] == 1
    assert summary["decision_eligible"] is False
    assert summary["affects"] == "quote_scheduling_only"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_discovery_quote_attempts SET reason_code='rewritten' WHERE id=?",
            (attempt_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM token_discovery_quote_attempt_registrations")
    store.close()


def test_token_universe_quote_attempt_deadline_and_retry_exhaustion_are_distinct(tmp_path: Path):
    store = Store(tmp_path / "quote-deadline-semantics.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="D" * 32, name="Deadline", symbol="DDL")
    discovered_at = utcnow()
    store.upsert_token(token, seen_at=discovered_at)
    discovery_round = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        discovery_round, token_id=token.token_id, chain=token.chain, role="create",
        first_local_discovery=True, new_token=True, observed_at=discovered_at,
    )
    store.finish_token_discovery_round(discovery_round, status="completed", returned_count=1)
    item = store.due_token_universe_quotes(now=utcnow() + timedelta(seconds=1))[0]
    deadline = parse_time(item["deadline_at"])

    failed_round = store.start_token_discovery_round(
        provider="dexscreener", surface="universe_baseline", mode="batch_quote",
        chain_scope="solana",
    )
    failed_id = store.start_token_discovery_quote_attempts(
        failed_round, [item], requested_at=deadline - timedelta(minutes=1),
    )[(token.token_id, "universe_baseline")]
    retry_after = store.finish_token_discovery_quote_attempt(
        failed_id, status="no_pair", completed_at=deadline - timedelta(seconds=30),
        base_retry_seconds=120,
    )
    failed = store.db.execute(
        "SELECT * FROM token_discovery_quote_attempts WHERE id=?", (failed_id,)
    ).fetchone()
    assert failed["deadline_miss"] == 0
    assert parse_time(retry_after) > deadline

    late_round = store.start_token_discovery_round(
        provider="dexscreener", surface="universe_baseline", mode="batch_quote",
        chain_scope="solana",
    )
    late_id = store.start_token_discovery_quote_attempts(
        late_round, [item], requested_at=deadline - timedelta(seconds=1),
    )[(token.token_id, "universe_baseline")]
    store.finish_token_discovery_quote_attempt(
        late_id, status="success", completed_at=deadline + timedelta(seconds=1),
    )
    late = store.db.execute(
        "SELECT * FROM token_discovery_quote_attempts WHERE id=?", (late_id,)
    ).fetchone()
    assert late["deadline_miss"] == 1

    summary = store.token_discovery_quote_attempt_summary_from_connection(store.db)
    assert summary["version"] == "token-discovery-quote-attempt/v2"
    assert summary["summary"]["deadline_misses"] == 1
    assert summary["summary"]["retry_window_exhausted"] == 1
    assert summary["items"][0]["role"] == "universe_baseline"
    store.close()


def test_token_universe_due_queue_skips_deferred_front_before_limit(tmp_path: Path):
    store = Store(tmp_path / "quote-deferred-front.sqlite3", initial_cash_usd=1000)
    for index, letter in enumerate(("A", "B", "C")):
        token = TokenCandidate(
            chain="solana", address=letter * 32, name=f"Queue {index}", symbol=f"Q{index}",
        )
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    checked_at = utcnow() + timedelta(seconds=1)
    initial = store.due_token_universe_quotes(now=checked_at, limit=3)
    assert len(initial) == 3
    attempt_round = store.start_token_discovery_round(
        provider="dexscreener", surface="universe_baseline", mode="batch_quote",
        chain_scope="solana",
    )
    attempt_ids = store.start_token_discovery_quote_attempts(
        attempt_round, initial[:2], requested_at=checked_at,
    )
    for item in initial[:2]:
        store.finish_token_discovery_quote_attempt(
            attempt_ids[(item["token_id"], item["role"])],
            status="no_pair", completed_at=checked_at + timedelta(seconds=1),
        )
    due = store.due_token_universe_quotes(now=checked_at + timedelta(seconds=2), limit=1)
    assert [item["token_id"] for item in due] == [initial[2]["token_id"]]
    store.close()


def test_token_universe_due_queue_orders_baseline_and_outcome_by_deadline(tmp_path: Path):
    store = Store(tmp_path / "quote-global-deadline.sqlite3", initial_cash_usd=1000)
    current = utcnow()
    old_discovery = current - timedelta(minutes=44)
    rows = [
        (1, "solana:" + "O" * 32, old_discovery),
        (2, "solana:" + "N" * 32, current),
    ]
    with store.db:
        for cohort_id, token_id, discovered in rows:
            store.db.execute(
                """
                INSERT INTO token_universe_forward_cohorts(
                    id,definition_version,exposure_id,round_id,token_id,chain,provider,surface,
                    discovery_role,discovery_observed_at,discovery_recorded_at,
                    baseline_deadline_at,decision_eligible,affects
                ) VALUES(?,?,?,?,?,'solana','fixture','fixture','create',?,?,?,0,'none')
                """,
                (
                    cohort_id, store.TOKEN_UNIVERSE_FORWARD_VERSION, cohort_id, cohort_id,
                    token_id, iso(discovered), iso(discovered),
                    iso(discovered + timedelta(minutes=5)),
                ),
            )
        store.db.execute(
            """
            INSERT INTO token_universe_forward_baselines(
                cohort_id,status,observed_at,ingested_at,recorded_at,price_usd,provider,
                reason,evaluated_at
            ) VALUES(1,'observed',?,?,?,?,'fixture',?,?)
            """,
            (
                iso(old_discovery + timedelta(minutes=1)),
                iso(old_discovery + timedelta(minutes=1)),
                iso(old_discovery + timedelta(minutes=1)), 1.0,
                "fixture_baseline", iso(current),
            ),
        )
    due = store.due_token_universe_quotes(now=current, limit=1)
    assert due[0]["cohort_id"] == 1
    assert due[0]["role"] == "universe_15m"
    store.close()


def test_pending_event_lookup_tokens_are_forward_only_oldest_first_and_deduplicated(tmp_path: Path):
    store = Store(tmp_path / "pending-event-lookup.sqlite3", initial_cash_usd=1000)
    observed_at = utcnow()

    def discover(chain: str, address: str, name: str) -> TokenCandidate:
        token = TokenCandidate(
            chain=chain, address=address, name=name, symbol=name[:5].upper(),
            source="fixture",
        )
        store.upsert_token(token, seen_at=observed_at)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll",
            chain_scope=chain, started_at=observed_at,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=chain, role="new_token",
            first_local_discovery=True, new_token=True, observed_at=observed_at,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        return token

    oldest = discover("bsc", "0x" + "1" * 40, "Oldest Eligible")
    attempted = discover("solana", "S" * 32, "Already Attempted")
    later = discover("base", "0x" + "2" * 40, "Later Eligible")
    first_transition = store.record_token_universe_funnel_transition(
        oldest.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="oldest:first",
        observed_at=observed_at, ingested_at=observed_at,
        metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1,
                  "momentum_score": 88.0},
    )
    store.record_token_universe_funnel_transition(
        oldest.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="fresh_high_attention_event_relation", evaluation_key="oldest:second",
        observed_at=observed_at, ingested_at=observed_at,
        metadata={"trigger_kind": "fresh_high_attention_event_relation",
                  "trigger_priority": 2},
    )
    attempted_poll_id = store.start_source_poll_attempt(
        collector_kind="reverse_news", source_key="attempted-before-eligible",
        platform="rss_news", started_at=observed_at,
    )
    store.record_token_universe_funnel_transition(
        attempted.token_id,
        stage="event_lookup_attempt", status="started",
        reason_code="reverse_news_lookup_started", evaluation_key="attempted:lookup",
        observed_at=observed_at, ingested_at=observed_at,
        source_poll_attempt_id=attempted_poll_id,
    )
    store.record_token_universe_funnel_transition(
        attempted.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="attempted:eligible",
        observed_at=observed_at, ingested_at=observed_at,
        metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
    )
    store.record_token_universe_funnel_transition(
        later.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="high_impact_account_post", evaluation_key="later:eligible",
        observed_at=observed_at, ingested_at=observed_at,
        metadata={"trigger_kind": "high_impact_account_post", "trigger_priority": 3},
    )

    cutoff = utcnow()
    pending = store.pending_event_lookup_tokens(
        ["solana", "bsc", "base"], as_of=cutoff, minutes=180,
    )
    assert [item["token"].token_id for item in pending] == [oldest.token_id, later.token_id]
    assert pending[0]["eligible_transition_id"] == first_transition
    assert pending[0]["trigger"] == {
        "kind": "onchain_momentum", "priority": 1, "decision_eligible": False,
        "endorsement_inferred": False, "momentum_score": 88.0,
    }
    assert [item["token"].token_id for item in store.pending_event_lookup_tokens(["BSC"])] == [
        oldest.token_id
    ]
    assert store.pending_event_lookup_tokens(["solana"]) == []
    assert store.pending_event_lookup_tokens([]) == []
    assert store.pending_event_lookup_tokens(
        ["bsc", "base"], as_of=cutoff + timedelta(minutes=181), minutes=180,
    ) == []

    oldest_poll_id = store.start_source_poll_attempt(
        collector_kind="reverse_news", source_key="oldest-after-eligible",
        platform="rss_news", started_at=utcnow(),
    )
    store.record_token_universe_funnel_transition(
        oldest.token_id,
        stage="event_lookup_attempt", status="started",
        reason_code="reverse_news_lookup_started", evaluation_key="oldest:lookup",
        observed_at=utcnow(), ingested_at=utcnow(),
        source_poll_attempt_id=oldest_poll_id,
    )
    assert [item["token"].token_id for item in store.pending_event_lookup_tokens(
        ["bsc", "base"]
    )] == [later.token_id]
    store.close()


def test_token_event_lookup_name_screen_records_active_pending_without_strategy_effects(tmp_path: Path):
    store = Store(tmp_path / "event-lookup-name-screen.sqlite3", initial_cash_usd=1000)
    now = utcnow()

    def enroll(address: str, name: str) -> tuple[TokenCandidate, int, int]:
        token = TokenCandidate(chain="solana", address=address, name=name, source="fixture")
        store.upsert_token(token, seen_at=now)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
            started_at=now,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="new_token",
            first_local_discovery=True, new_token=True, observed_at=now,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort_id = int(store.db.execute(
            "SELECT id FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()["id"])
        transition_id = store.record_token_universe_funnel_transition(
            token.token_id,
            stage="context_trigger_evaluation", status="eligible",
            reason_code="onchain_momentum", evaluation_key=f"screen:{token.token_id}",
            observed_at=now, ingested_at=now,
            metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
        )
        assert transition_id is not None
        return token, cohort_id, int(transition_id)

    rejected, rejected_cohort, rejected_transition = enroll("U" * 32, "AI")
    searchable, searchable_cohort, searchable_transition = enroll("V" * 32, "Searchable Topic")
    assert [item["token"].token_id for item in store.pending_event_lookup_tokens(["solana"])] == [
        rejected.token_id, searchable.token_id,
    ]
    decisions_before = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trades_before = store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    registration = store.register_token_event_lookup_name_screen()
    assert registration["definition_version"] == store.TOKEN_EVENT_LOOKUP_NAME_SCREEN_VERSION

    rejected_id = store.record_token_event_lookup_name_screen(
        rejected_cohort, rejected_transition,
        searchable=is_context_searchable_token_name(rejected.name or rejected.symbol),
    )
    searchable_id = store.record_token_event_lookup_name_screen(
        searchable_cohort, searchable_transition,
        searchable=is_context_searchable_token_name(searchable.name or searchable.symbol),
    )
    assert rejected_id is not None and searchable_id is not None
    assert store.record_token_event_lookup_name_screen(
        rejected_cohort, rejected_transition, searchable=True,
    ) == rejected_id
    rows = list(store.db.execute(
        "SELECT cohort_id,status,reason_code,decision_eligible,affects "
        "FROM token_event_lookup_name_screen_results ORDER BY cohort_id"
    ))
    assert [(row["status"], row["reason_code"]) for row in rows] == [
        ("rejected", "unsearchable_token_name"),
        ("eligible", "searchable_name"),
    ]
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    assert [item["token"].token_id for item in store.pending_event_lookup_tokens(["solana"])] == [
        searchable.token_id
    ]
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == decisions_before
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == trades_before
    summary = Store.token_event_lookup_name_screen_summary_from_connection(store.db)
    assert summary["status"] == "collecting"
    assert summary["summary"] == {"screened": 2, "eligible": 1, "rejected": 1}
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_event_lookup_name_screen_results SET status='eligible' WHERE id=?",
            (rejected_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "DELETE FROM token_event_lookup_name_screen_registrations "
            "WHERE definition_version=?",
            (store.TOKEN_EVENT_LOOKUP_NAME_SCREEN_VERSION,),
        )
    store.close()


def test_token_universe_funnel_is_forward_only_append_only_and_dag_aware(tmp_path: Path):
    store = Store(tmp_path / "token-universe-funnel.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(
        chain="solana", address="F" * 32, name="Forward Funnel", symbol="FUNNEL"
    )
    store.upsert_token(token, seen_at=now)
    round_id = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window",
        chain_scope="solana", started_at=now,
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain=token.chain, role="create",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    decision_at = parse_time(
        store.db.execute(
            "SELECT discovery_recorded_at FROM token_universe_forward_cohorts WHERE token_id=?",
            (token.token_id,),
        ).fetchone()[0]
    )

    first_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation",
        status="eligible",
        reason_code="high_impact_account_post",
        evaluation_key="snapshot:one",
        observed_at=now,
        ingested_at=now,
        source_table="token_context_trigger",
    )
    duplicate_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation",
        status="ineligible",
        reason_code="later_duplicate_resolution",
        evaluation_key="snapshot:one",
        observed_at=now + timedelta(seconds=1),
        ingested_at=now + timedelta(seconds=1),
        source_table="token_context_trigger",
    )
    assert duplicate_id == first_id
    trigger = store.db.execute(
        "SELECT * FROM token_universe_funnel_transitions WHERE id=?", (first_id,)
    ).fetchone()
    assert trigger["status"] == "eligible"
    assert trigger["reason_code"] == "high_impact_account_post"

    future_observed = now + timedelta(hours=1)
    excluded_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation",
        status="eligible",
        reason_code="should_be_excluded",
        evaluation_key="lookup:future",
        observed_at=future_observed,
        ingested_at=now,
        source_table="fixture",
    )
    excluded = store.db.execute(
        "SELECT * FROM token_universe_funnel_transitions WHERE id=?", (excluded_id,)
    ).fetchone()
    assert excluded["status"] == "excluded_time_order"
    assert excluded["reason_code"] == "invalid_time_order"
    assert parse_time(excluded["observed_at"]) == parse_time(future_observed)
    assert parse_time(excluded["ingested_at"]) == parse_time(now)

    event_id = store.create_event("Forward explicit link", ["forward funnel"], 70, now)
    observation_id, _ = store.add_observation(
        Observation(
            source="fixture", source_kind="news", title="Forward explicit link",
            observed_at=now, ingested_at=now, role="feature",
            source_item_id="forward-explicit-link", raw={"reverse_token_id": token.token_id},
        )
    )
    store.link_event_observation(event_id, observation_id)
    identity_observation_id, _ = store.add_observation(
        Observation(
            source="fixture-profile", source_kind="social",
            title="Forward Funnel project profile", observed_at=now,
            ingested_at=now, role="identity", source_item_id="forward-identity-link",
            raw={"reverse_token_id": token.token_id},
        )
    )
    store.link_event_observation(event_id, identity_observation_id)
    identity_poll_id = store.start_source_poll_attempt(
        collector_kind="reverse_news", source_key="identity-match",
        platform="web", started_at=now,
    )
    store.finish_source_poll_attempt(
        identity_poll_id, status="completed", fetched_count=1,
        new_observation_count=1, context_only_count=1, completed_at=now,
    )
    store.record_token_universe_funnel_transition(
        token.token_id, stage="event_lookup_result", status="found",
        reason_code="reverse_news_identity_matched", evaluation_key="lookup:identity",
        observed_at=now, ingested_at=now, source_table="source_poll_attempts",
        source_poll_attempt_id=identity_poll_id,
        metadata={"matched_count": 1, "decision_eligible_count": 0,
                  "identity_context_count": 1, "distinct_publisher_count": 1},
    )
    legacy_poll_id = store.start_source_poll_attempt(
        collector_kind="reverse_news", source_key="legacy-match",
        platform="web", started_at=now,
    )
    store.finish_source_poll_attempt(
        legacy_poll_id, status="completed", fetched_count=1,
        new_observation_count=1, completed_at=now,
    )
    store.record_token_universe_funnel_transition(
        token.token_id, stage="event_lookup_result", status="found",
        reason_code="reverse_news_matched", evaluation_key="lookup:legacy",
        observed_at=now, ingested_at=now, source_table="source_poll_attempts",
        source_poll_attempt_id=legacy_poll_id, metadata={"accepted_count": 1},
    )
    eligible_poll_id = store.start_source_poll_attempt(
        collector_kind="reverse_news", source_key="eligible-match",
        platform="web", started_at=now,
    )
    store.finish_source_poll_attempt(
        eligible_poll_id, status="completed", fetched_count=1,
        new_observation_count=1, decision_eligible_count=1, completed_at=now,
    )
    store.record_token_universe_funnel_transition(
        token.token_id, stage="event_lookup_result", status="found",
        reason_code="reverse_news_matched", evaluation_key="lookup:eligible",
        observed_at=now, ingested_at=now, source_table="source_poll_attempts",
        source_poll_attempt_id=eligible_poll_id,
        metadata={"matched_count": 1, "decision_eligible_count": 1,
                  "identity_context_count": 0, "distinct_publisher_count": 1},
    )
    decision_id = store.add_decision(
        CandidateDecision(
            event_id, token.token_id, "WAIT", 55, 60, 1, ["insufficient confirmation"],
            created_at=decision_at,
        )
    )
    assert decision_id > 0
    assert store.record_token_universe_candidate_evaluations(
        event_id,
        evaluated_at=decision_at,
        candidates=[{
            "rank": 1, "token_id": token.token_id, "candidate_score": 55,
            "match_score": 60, "reasons": ["insufficient confirmation"],
            "safety": {"status": "not_checked"},
        }],
        selected_token_id=token.token_id,
        selected_action="WAIT",
    ) == 1
    candidate_decision_id = store.add_decision(
        CandidateDecision(
            event_id, token.token_id, "CANDIDATE", 88, 90, 12,
            ["verified forward candidate"], position_usd=10,
            created_at=decision_at,
        )
    )
    execution_at = decision_at
    store.paper_buy(
        event_id=event_id, token=token, price=1.04, gross_usd=10,
        fee_bps=60, reason="fixture_fill", quote_price=1.0,
        execution_attempted_at=execution_at,
        decision_id=candidate_decision_id,
        record_execution_attempt=True,
    )
    attempt_id = int(
        store.db.execute(
            "SELECT id FROM paper_execution_attempts WHERE decision_id=?",
            (candidate_decision_id,),
        ).fetchone()["id"]
    )

    summary = store.token_universe_funnel_summary_from_connection(store.db)
    assert summary["summary"]["cohorts"] == 1
    assert summary["summary"]["transition_attempts"] == 12
    assert summary["summary"]["excluded_time_order"] == 1
    milestones = {item["stage"]: item for item in summary["milestones"]}
    assert milestones["context_trigger_evaluation"]["cohorts"] == 1
    assert milestones["event_token_relation"]["cohorts"] == 1
    assert milestones["event_token_relation"]["attempts"] == 2
    assert milestones["event_token_relation_decision_eligible"]["attempts"] == 1
    assert milestones["event_token_relation_context_only"]["attempts"] == 1
    assert milestones["event_lookup_found"]["attempts"] == 3
    assert milestones["event_lookup_decision_eligible_found"]["attempts"] == 1
    assert milestones["event_lookup_identity_context_only_found"]["attempts"] == 1
    assert milestones["event_lookup_found_unclassified"]["attempts"] == 1
    assert milestones["candidate_evaluator_called"]["cohorts"] == 1
    assert milestones["decision_wait"]["cohorts"] == 1
    assert milestones["decision_candidate"]["cohorts"] == 1
    assert milestones["paper_buy_attempt"]["cohorts"] == 1
    assert milestones["paper_buy"]["cohorts"] == 1
    candidate_edge = store.db.execute(
        "SELECT status FROM token_universe_funnel_transitions "
        "WHERE stage='candidate_evaluation' AND token_id=?",
        (token.token_id,),
    ).fetchone()
    assert candidate_edge["status"] == "top_rank_wait"
    decision_edge = store.db.execute(
        "SELECT status,decision_id FROM token_universe_funnel_transitions "
        "WHERE stage='decision_final' AND token_id=? AND decision_id=?",
        (token.token_id, decision_id),
    ).fetchone()
    assert decision_edge["status"] == "wait"
    assert decision_edge["decision_id"] == decision_id
    paper_edges = list(
        store.db.execute(
            "SELECT stage,paper_execution_attempt_id,trade_id FROM "
            "token_universe_funnel_transitions WHERE token_id=? "
            "AND stage IN ('paper_execution_attempt','paper_fill') ORDER BY id",
            (token.token_id,),
        )
    )
    assert paper_edges[0]["paper_execution_attempt_id"] == attempt_id
    assert paper_edges[1]["paper_execution_attempt_id"] == attempt_id
    assert paper_edges[1]["trade_id"] is not None
    assert summary["decision_eligible"] is False and summary["affects"] == "none"

    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_funnel_transitions SET status='rewritten' WHERE id=?",
            (first_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM token_universe_funnel_registrations")
    store.close()


def test_full_token_universe_forward_outcomes_are_complete_and_immutable(tmp_path: Path):
    store = Store(tmp_path / "token-universe.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="U" * 32, name="Universe", symbol="UNI")
    missing = TokenCandidate(chain="solana", address="N" * 32, name="No Quote", symbol="NOQ")
    store.upsert_token(token)
    store.upsert_token(missing)
    round_id = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
    )
    for item in (token, missing):
        store.add_token_discovery_exposure(
            round_id, token_id=item.token_id, chain=item.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=2)
    duplicate_round = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        duplicate_round, token_id=token.token_id, chain=token.chain, role="new_pool",
        first_local_discovery=False,
    )
    store.finish_token_discovery_round(duplicate_round, status="completed", returned_count=1)
    cohorts = store.db.execute(
        "SELECT * FROM token_universe_forward_cohorts ORDER BY id"
    ).fetchall()
    assert len(cohorts) == 2
    cohort = next(row for row in cohorts if row["token_id"] == token.token_id)
    discovered = parse_time(cohort["discovery_recorded_at"])

    def snapshot(minutes: int, price: float) -> None:
        when = discovered + timedelta(minutes=minutes, seconds=10)
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (token.token_id, iso(when), iso(when), iso(when), "forward-test", price, "{}"),
        )

    snapshot(1, 1.0)
    snapshot(15, 1.5)
    snapshot(60, 2.2)
    snapshot(240, 0.8)
    event_id = store.create_event("Universe event", ["universe"], 70, discovered)
    store.add_decision(CandidateDecision(
        event_id, token.token_id, "WAIT", 55, 60, 1, ["wait"],
        created_at=discovered + timedelta(minutes=10),
    ))
    store.add_decision(CandidateDecision(
        event_id, token.token_id, "CANDIDATE", 85, 80, 20, ["candidate"],
        created_at=discovered + timedelta(minutes=55),
    ))
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=16))
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=61))
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=241))
    audit_result = store.finalize_missed_opportunity_audits()
    assert audit_result == {"inserted": 6, "potential_misses": 3}

    outcomes = store.db.execute(
        "SELECT * FROM token_universe_forward_outcomes WHERE cohort_id=? ORDER BY horizon_minutes",
        (int(cohort["id"]),),
    ).fetchall()
    assert [row["horizon_minutes"] for row in outcomes] == [15, 60, 240]
    assert outcomes[0]["best_action_at_target"] == "WAIT"
    assert outcomes[1]["best_action_at_target"] == "CANDIDATE"
    assert outcomes[1]["raw_return"] == pytest.approx(1.2)
    assert outcomes[1]["peak_return_tier"] == "gte_100pct"
    missing_rows = store.db.execute(
        """
        SELECT o.status FROM token_universe_forward_outcomes o
        JOIN token_universe_forward_cohorts c ON c.id=o.cohort_id
        WHERE c.token_id=? ORDER BY o.horizon_minutes
        """,
        (missing.token_id,),
    ).fetchall()
    assert [row["status"] for row in missing_rows] == ["baseline_missing"] * 3
    summary = store.token_universe_forward_summary_from_connection(store.db)
    assert summary["summary"]["cohorts"] == 2
    assert summary["summary"]["baseline_observed"] == 1
    assert summary["summary"]["baseline_missing"] == 1
    assert summary["decision_eligible"] is False and summary["affects"] == "none"
    miss = store.missed_opportunity_audit_summary_from_connection(store.db)
    assert miss["summary"] == {
        "audited_outcomes": 6,
        "potential_misses": 3,
        "captured_paper": 0,
        "outcome_unavailable": 3,
    }
    assert {row["funnel_breakpoint"]: row["count"] for row in miss["breakpoints"]} == {
        "candidate_no_paper_buy": 2,
        "no_entry_snapshot": 3,
        "wait": 1,
    }
    assert miss["decision_eligible"] is False and miss["affects"] == "none"
    assert store.finalize_missed_opportunity_audits()["inserted"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_forward_outcomes SET status='observed' WHERE cohort_id=?",
            (int(cohort["id"]),),
        )
    audit_id = store.db.execute("SELECT id FROM missed_opportunity_audits LIMIT 1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE missed_opportunity_audits SET audit_class='captured_paper' WHERE id=?",
            (audit_id,),
        )
    store.close()


def test_missed_opportunity_audit_registration_never_backfills_existing_outcomes(tmp_path: Path):
    database = tmp_path / "miss-registration.sqlite3"
    store = Store(database, initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="M" * 32, name="Miss", symbol="MISS")
    store.upsert_token(token)
    round_id = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain=token.chain, role="create",
        first_local_discovery=True, new_token=True,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    cohort = store.db.execute("SELECT * FROM token_universe_forward_cohorts").fetchone()
    discovered = parse_time(cohort["discovery_recorded_at"])
    for minutes, price in ((1, 1.0), (15, 1.5)):
        when = iso(discovered + timedelta(minutes=minutes, seconds=10))
        store.db.execute(
            "INSERT INTO token_snapshots(token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json) "
            "VALUES(?,?,?,?,?,?,?)",
            (token.token_id, when, when, when, "forward-test", price, "{}"),
        )
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=16))
    old_outcome_id = int(
        store.db.execute("SELECT MAX(id) FROM token_universe_forward_outcomes").fetchone()[0]
    )
    store.close()

    raw = sqlite3.connect(database)
    raw.execute("DROP TRIGGER missed_opportunity_audit_registrations_no_delete")
    raw.execute("DELETE FROM missed_opportunity_audit_registrations")
    raw.execute("DROP TRIGGER missed_opportunity_no_decision_attribution_registrations_no_delete")
    raw.execute("DELETE FROM missed_opportunity_no_decision_attribution_registrations")
    raw.commit()
    raw.close()

    store = Store(database, initial_cash_usd=1000)
    registration = store.db.execute(
        "SELECT * FROM missed_opportunity_audit_registrations"
    ).fetchone()
    assert int(registration["activation_outcome_id"]) == old_outcome_id
    attribution_registration = store.db.execute(
        "SELECT * FROM missed_opportunity_no_decision_attribution_registrations"
    ).fetchone()
    assert int(attribution_registration["activation_cohort_id"]) == int(cohort["id"])
    assert store.finalize_missed_opportunity_audits()["inserted"] == 0
    when = iso(discovered + timedelta(minutes=60, seconds=10))
    store.db.execute(
        "INSERT INTO token_snapshots(token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json) "
        "VALUES(?,?,?,?,?,?,?)",
        (token.token_id, when, when, when, "forward-test", 2.0, "{}"),
    )
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=61))
    assert store.finalize_missed_opportunity_audits() == {
        "inserted": 1, "potential_misses": 1,
    }
    assert store.finalize_missed_opportunity_no_decision_attributions() == {"inserted": 0}
    store.close()


def test_missed_opportunity_no_decision_attribution_is_target_bounded_and_immutable(tmp_path: Path):
    store = Store(tmp_path / "no-decision-attribution.sqlite3", initial_cash_usd=1000)

    def enroll(address: str) -> tuple[TokenCandidate, object]:
        token = TokenCandidate(chain="solana", address=address, name="Attribution", symbol="ATTR")
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()
        discovered = parse_time(cohort["discovery_recorded_at"])
        for minutes, price in ((1, 1.0), (15, 1.5)):
            when = iso(discovered + timedelta(minutes=minutes, seconds=1))
            store.db.execute(
                "INSERT INTO token_snapshots(token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json) "
                "VALUES(?,?,?,?,?,?,?)",
                (token.token_id, when, when, when, "fixture", price, "{}"),
            )
        return token, cohort

    absent, _ = enroll("A" * 32)
    cooldown, _ = enroll("B" * 32)
    no_context, _ = enroll("C" * 32)
    related, _ = enroll("D" * 32)
    identity_only, _ = enroll("E" * 32)
    now = utcnow()
    cooldown_admission = store.add_token_context_admission_attempt(
        cooldown.token_id, outcome="skipped", reason="global_cooldown_active", trigger={},
        snapshot_observed_at=now, momentum_score=0, quota_day=now.date().isoformat(),
        daily_call_limit=1, calls_used_before=1, daily_token_budget=0,
        tokens_used_before=0, token_reserve_per_call=0, evaluated_at=now,
    )
    store.record_token_universe_funnel_transition(
        cooldown.token_id, stage="context_admission", status="skipped",
        reason_code="global_cooldown_active", evaluation_key="fixture:cooldown",
        observed_at=now, ingested_at=now, source_table="token_context_admission_attempts",
        admission_id=cooldown_admission,
    )
    context_admission = store.add_token_context_admission_attempt(
        no_context.token_id, outcome="admitted", reason="admitted", trigger={},
        snapshot_observed_at=now, momentum_score=0, quota_day=now.date().isoformat(),
        daily_call_limit=1, calls_used_before=0, daily_token_budget=0,
        tokens_used_before=0, token_reserve_per_call=0, evaluated_at=now,
    )
    assessment_id = store.add_token_context_assessment(
        no_context.token_id, trigger="fixture", status="no_context",
        snapshot_observed_at=now, momentum_score=0, assessment={}, assessed_at=now,
    )
    store.record_token_universe_funnel_transition(
        no_context.token_id, stage="agent_result", status="no_context",
        reason_code="no_context", evaluation_key="fixture:no-context",
        observed_at=now, ingested_at=now, source_table="token_context_assessments",
        admission_id=context_admission, assessment_id=assessment_id, agent_run_id="fixture-run",
    )
    event_id = store.create_event("Fixture relation", ["fixture"], 70, now)
    observation_id, _ = store.add_observation(Observation(
        source="fixture", source_kind="news", title="Fixture relation", observed_at=now,
        ingested_at=now, role="feature", source_item_id="attribution-related",
        raw={"reverse_token_id": related.token_id},
    ))
    store.link_event_observation(event_id, observation_id)
    identity_event_id = store.create_event("Fixture identity", ["fixture"], 30, now)
    identity_observation_id, _ = store.add_observation(Observation(
        source="fixture", source_kind="news", title="Fixture identity", observed_at=now,
        ingested_at=now, role="identity", source_item_id="attribution-identity",
        raw={"reverse_token_id": identity_only.token_id},
    ))
    store.link_event_observation(identity_event_id, identity_observation_id)

    absent_cohort = store.db.execute(
        "SELECT id,discovery_recorded_at FROM token_universe_forward_cohorts WHERE token_id=?",
        (absent.token_id,),
    ).fetchone()
    absent_target = parse_time(absent_cohort["discovery_recorded_at"]) + timedelta(minutes=15)
    before_target = iso(absent_target - timedelta(seconds=1))
    after_target = iso(absent_target + timedelta(seconds=1))
    store.db.execute(
        "INSERT INTO token_universe_funnel_transitions("
        "definition_version,transition_key,evaluation_key,cohort_id,token_id,stage,status,"
        "reason_code,observed_at,ingested_at,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            store.TOKEN_UNIVERSE_FUNNEL_VERSION, "fixture:late-recording", "fixture:late",
            int(absent_cohort["id"]), absent.token_id, "context_trigger_evaluation", "eligible",
            "information_first_trigger", before_target, before_target, after_target,
        ),
    )

    latest_discovery = max(
        parse_time(row["discovery_recorded_at"])
        for row in store.db.execute("SELECT discovery_recorded_at FROM token_universe_forward_cohorts")
    )
    store.finalize_token_universe_forward_outcomes(now=latest_discovery + timedelta(minutes=16))
    assert store.finalize_missed_opportunity_audits() == {"inserted": 5, "potential_misses": 5}
    assert store.finalize_missed_opportunity_no_decision_attributions() == {"inserted": 5}
    rows = list(store.db.execute(
        "SELECT token_id,status,reason_code,terminal_transition_id,decision_eligible,affects "
        "FROM missed_opportunity_no_decision_attributions ORDER BY token_id"
    ))
    assert [(row["token_id"], row["status"]) for row in rows] == [
        (absent.token_id, "metadata_hydration_not_observed"),
        (cooldown.token_id, "context_admission_skipped"),
        (no_context.token_id, "agent_result_no_context"),
        (related.token_id, "event_related_candidate_not_evaluated"),
        (identity_only.token_id, "event_related_candidate_not_evaluated"),
    ]
    assert rows[0]["terminal_transition_id"] is None
    assert rows[1]["reason_code"] == "global_cooldown_active"
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    summary = store.missed_opportunity_no_decision_attribution_summary_from_connection(store.db)
    assert summary["summary"]["attributions"] == 5
    assert summary["relation_role_breakdown"] == {
        "total": 2,
        "decision_eligible": 1,
        "context_only": 1,
        "unknown": 0,
        "roles": [
            {"role": "feature", "count": 1},
            {"role": "identity", "count": 1},
        ],
    }
    assert summary["quality_view"]["summary"] == {
        "raw_attributions": 5,
        "quality_available_at_classification": 0,
        "quality_missing_at_classification": 5,
        "raw_fixed_return_25": 0,
        "same_route_return_25": 0,
        "canonical_liquid_return_25": 0,
        "estimated_net_return_25": 0,
        "confirmed_executable_known": 0,
        "confirmed_executable_return_25": 0,
    }
    assert summary["decision_eligible"] is False and summary["affects"] == "none"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE missed_opportunity_no_decision_attributions SET status='trigger_ineligible'")
    store.close()


def test_no_decision_quality_view_excludes_quality_assessed_after_classification(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "no-decision-quality-view.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE missed_opportunity_no_decision_attribution_registrations (
            definition_version TEXT, registered_at TEXT, activation_cohort_id INTEGER,
            activation_audit_id INTEGER, definition_json TEXT
        );
        CREATE TABLE missed_opportunity_no_decision_attributions (
            id INTEGER PRIMARY KEY, definition_version TEXT, audit_id INTEGER,
            cohort_id INTEGER, token_id TEXT, target_at TEXT, status TEXT,
            reason_code TEXT, terminal_transition_id INTEGER, classified_at TEXT
        );
        CREATE TABLE missed_opportunity_audits (
            id INTEGER PRIMARY KEY, definition_version TEXT, outcome_id INTEGER
        );
        CREATE TABLE token_universe_outcome_quality (
            id INTEGER PRIMARY KEY, definition_version TEXT, outcome_id INTEGER,
            raw_fixed_horizon_return REAL, same_route_return REAL,
            canonical_liquid_pair_return REAL, estimated_net_return_after_costs REAL,
            net_executable_return_after_costs REAL, assessed_at TEXT
        );
        CREATE TABLE token_universe_jupiter_quote_validity_results (
            id INTEGER PRIMARY KEY, definition_version TEXT, outcome_id INTEGER,
            phase TEXT, validity_status TEXT, included_in_round_trip INTEGER,
            round_trip_min_return REAL, recorded_at TEXT
        );
        CREATE TABLE token_universe_fixed_target_execution_results (
            id INTEGER PRIMARY KEY, definition_version TEXT, outcome_id INTEGER,
            terminal_status TEXT, modeled_net_return REAL, assessed_at TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO missed_opportunity_no_decision_attribution_registrations VALUES(?,?,?,?,?)",
        (
            Store.MISSED_OPPORTUNITY_NO_DECISION_ATTRIBUTION_VERSION,
            "2026-09-01T00:00:00Z", 0, 0,
            json.dumps(Store._missed_opportunity_no_decision_attribution_definition()),
        ),
    )
    for audit_id, outcome_id in ((1, 11), (2, 12)):
        connection.execute(
            "INSERT INTO missed_opportunity_audits VALUES(?,?,?)",
            (audit_id, Store.MISSED_OPPORTUNITY_AUDIT_VERSION, outcome_id),
        )
        connection.execute(
            "INSERT INTO missed_opportunity_no_decision_attributions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                audit_id, Store.MISSED_OPPORTUNITY_NO_DECISION_ATTRIBUTION_VERSION,
                audit_id, audit_id,
                f"{'solana' if audit_id == 1 else 'bsc'}:token-{audit_id}",
                "2026-09-01T00:09:00Z", "trigger_ineligible", "no_eligible_trigger",
                None, "2026-09-01T00:10:00Z",
            ),
        )
    connection.execute(
        "INSERT INTO token_universe_outcome_quality VALUES(?,?,?,?,?,?,?,?,?)",
        (
            1, Store.TOKEN_UNIVERSE_OUTCOME_QUALITY_VERSION, 11,
            0.30, 0.40, 0.35, 0.28, 0.26, "2026-09-01T00:09:59Z",
        ),
    )
    connection.execute(
        "INSERT INTO token_universe_jupiter_quote_validity_results VALUES(?,?,?,?,?,?,?,?)",
        (
            1, Store.TOKEN_UNIVERSE_JUPITER_QUOTE_VALIDITY_VERSION, 11,
            "target_sell", "valid", 1, -0.10, "2026-09-01T00:09:58Z",
        ),
    )
    connection.execute(
        "INSERT INTO token_universe_jupiter_quote_validity_results VALUES(?,?,?,?,?,?,?,?)",
        (
            2, Store.TOKEN_UNIVERSE_JUPITER_QUOTE_VALIDITY_VERSION, 11,
            "target_sell", "valid", 1, 9.0, "2026-09-01T00:10:01Z",
        ),
    )
    connection.execute(
        "INSERT INTO token_universe_fixed_target_execution_results VALUES(?,?,?,?,?,?)",
        (
            1, Store.TOKEN_UNIVERSE_FIXED_TARGET_EXECUTION_VERSION, 12,
            "modeled_executable", 0.50, "2026-09-01T00:09:58Z",
        ),
    )
    connection.execute(
        "INSERT INTO token_universe_fixed_target_execution_results VALUES(?,?,?,?,?,?)",
        (
            2, Store.TOKEN_UNIVERSE_FIXED_TARGET_EXECUTION_VERSION, 12,
            "modeled_executable", 9.0, "2026-09-01T00:10:01Z",
        ),
    )
    connection.execute(
        "INSERT INTO token_universe_outcome_quality VALUES(?,?,?,?,?,?,?,?,?)",
        (
            2, Store.TOKEN_UNIVERSE_OUTCOME_QUALITY_VERSION, 12,
            9.0, 9.0, 9.0, 9.0, 9.0, "2026-09-01T00:10:01Z",
        ),
    )
    view = Store.missed_opportunity_no_decision_attribution_summary_from_connection(
        connection
    )["quality_view"]
    assert view["semantics"] == "read_only_join_of_immutable_rows_available_at_classification"
    assert view["summary"] == {
        "raw_attributions": 2,
        "quality_available_at_classification": 1,
        "quality_missing_at_classification": 1,
        "raw_fixed_return_25": 1,
        "same_route_return_25": 1,
        "canonical_liquid_return_25": 1,
        "estimated_net_return_25": 1,
        "confirmed_executable_known": 1,
        "confirmed_executable_return_25": 1,
    }
    assert view["breakpoints"] == [
        {
            "status": "trigger_ineligible", "reason_code": "no_eligible_trigger",
            **view["summary"],
        }
    ]
    assert view["fixed_horizon_execution"]["summary"] == {
        "raw_attributions": 2,
        "execution_known": 2,
        "execution_nonnegative": 1,
        "execution_return_25": 1,
        "jupiter_valid_round_trip_known": 1,
        "jupiter_valid_round_trip_nonnegative": 0,
        "jupiter_valid_round_trip_return_25": 0,
        "evm_modeled_execution_known": 1,
        "evm_modeled_execution_nonnegative": 1,
        "evm_modeled_execution_return_25": 1,
    }
    assert view["decision_eligible"] is False and view["affects"] == "none"
    connection.close()


def test_token_universe_quality_overlay_is_forward_only_route_aware_and_immutable(tmp_path: Path):
    store = Store(tmp_path / "quality-overlay.sqlite3", initial_cash_usd=1000)

    def enroll(address: str):
        token = TokenCandidate(chain="solana", address=address, name="Quality", symbol="QLT")
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()
        return token, cohort, parse_time(cohort["discovery_recorded_at"])

    def add_pair_snapshot(token, when, price, pair="PAIR-A"):
        raw = json.dumps({
            "pair": {
                "chainId": "solana", "dexId": "pumpswap", "pairAddress": pair,
                "baseToken": {"address": token.address},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "priceUsd": str(price), "liquidity": {"usd": 20_000},
            }
        })
        stamp = iso(when)
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,
                liquidity_usd,market_cap_usd,volume_5m_usd,buys_5m,sells_5m,
                buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, stamp, stamp, stamp, "dexscreener", price,
                20_000, 100_000, 5_000, 20, 5, 0, 0, 0, 1, raw,
            ),
        )

    legacy, _, legacy_discovered = enroll("L" * 32)
    add_pair_snapshot(legacy, legacy_discovered + timedelta(minutes=1), 1.0)
    add_pair_snapshot(legacy, legacy_discovered + timedelta(minutes=15, seconds=10), 1.4)
    store.finalize_token_universe_forward_outcomes(
        now=legacy_discovered + timedelta(minutes=16)
    )
    legacy_outcome_id = int(
        store.db.execute("SELECT MAX(id) FROM token_universe_forward_outcomes").fetchone()[0]
    )
    registration = store.register_token_universe_outcome_quality(
        reference_notional_usd=35,
        min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025,
        slippage_rate=0.04,
        default_fee_bps=60,
        pump_fee_bps=125,
        max_quote_age_seconds=45,
        max_tax_pct=10,
    )
    assert int(registration["activation_outcome_id"]) == legacy_outcome_id
    assert store.finalize_token_universe_outcome_quality()["inserted"] == 0

    forward, _, discovered = enroll("Q" * 32)
    add_pair_snapshot(forward, discovered + timedelta(minutes=1), 1.0)
    add_pair_snapshot(forward, discovered + timedelta(minutes=15, seconds=10), 1.5)
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=16))
    assert store.finalize_token_universe_outcome_quality() == {
        "inserted": 1, "quality_valid": 1, "confirmed_tradable": 1,
    }
    row = store.db.execute("SELECT * FROM token_universe_outcome_quality").fetchone()
    assert row["route_class"] == "same_pair"
    assert row["quality_status"] == "same_route_liquidity_supported"
    assert row["tradability_status"] == "confirmed_executable"
    assert row["raw_fixed_horizon_return"] == pytest.approx(0.5)
    assert row["raw_token_path_return"] == pytest.approx(0.5)
    assert row["same_pair_return"] == pytest.approx(0.5)
    assert row["same_route_return"] == pytest.approx(0.5)
    assert row["canonical_liquid_pair_return"] == pytest.approx(0.5)
    assert row["estimated_net_return_after_costs"] < 0.5
    assert row["net_executable_return_after_costs"] == pytest.approx(
        row["estimated_net_return_after_costs"]
    )
    summary = store.token_universe_outcome_quality_summary_from_connection(store.db)
    assert summary["summary"]["assessed_outcomes"] == 1
    assert summary["summary"]["raw_potential"] == 1
    assert summary["summary"]["quality_valid"] == 1
    assert summary["summary"]["confirmed_tradable"] == 1
    assert summary["retrospective_v1_diagnostic_included"] is False
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_outcome_quality SET quality_status='unknown' WHERE id=?",
            (int(row["id"]),),
        )
    store.close()


def test_token_universe_quality_overlay_does_not_treat_cross_pair_peak_as_same_pair(tmp_path: Path):
    store = Store(tmp_path / "quality-cross-pair.sqlite3", initial_cash_usd=1000)
    store.register_token_universe_outcome_quality(
        reference_notional_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125,
        max_quote_age_seconds=45, max_tax_pct=10,
    )
    token = TokenCandidate(chain="solana", address="X" * 32, name="Cross", symbol="CROSS")
    store.upsert_token(token)
    round_id = store.start_token_discovery_round(
        provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain=token.chain, role="new_pool",
        first_local_discovery=True, new_token=True,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    cohort = store.db.execute("SELECT * FROM token_universe_forward_cohorts").fetchone()
    discovered = parse_time(cohort["discovery_recorded_at"])
    quote = "So11111111111111111111111111111111111111112"
    for minutes, price, dex, pair, liquidity in (
        (1, 0.000001, "meteora", "DUST", 0.79),
        (15, 0.1, "meteoradbc", "LIQUID", 50_000),
    ):
        when = iso(discovered + timedelta(minutes=minutes, seconds=10))
        raw = json.dumps({"pair": {
            "chainId": "solana", "dexId": dex, "pairAddress": pair,
            "baseToken": {"address": token.address}, "quoteToken": {"address": quote},
            "priceUsd": str(price), "liquidity": {"usd": liquidity},
        }})
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,
                liquidity_usd,market_cap_usd,volume_5m_usd,buys_5m,sells_5m,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, when, when, when, "dexscreener", price,
                liquidity, 100_000, 5_000, 20, 5, raw,
            ),
        )
    store.finalize_token_universe_forward_outcomes(now=discovered + timedelta(minutes=16))
    store.finalize_token_universe_outcome_quality()
    row = store.db.execute("SELECT * FROM token_universe_outcome_quality").fetchone()
    flags = json.loads(row["quality_flags_json"])
    assert row["route_class"] == "canonical_pair_switch"
    assert row["quality_status"] == "cross_pair_incomparable"
    assert row["raw_token_path_return"] > 10_000
    assert row["same_pair_return"] == pytest.approx(0.0)
    assert row["canonical_liquid_pair_return"] is None
    assert "dust_pool_to_liquid_pool" in flags
    assert row["net_executable_return_after_costs"] is None
    store.close()


def test_token_universe_fixed_target_execution_is_forward_fixed_route_and_append_only(tmp_path: Path):
    store = Store(tmp_path / "fixed-target-execution.sqlite3", initial_cash_usd=1000)
    now = utcnow()

    def enroll(chain: str, address: str, name: str) -> tuple[TokenCandidate, sqlite3.Row, datetime]:
        token = TokenCandidate(chain=chain, address=address, name=name, source="fixture")
        store.upsert_token(token, seen_at=now)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope=chain,
            started_at=now,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=chain, role="new_token",
            first_local_discovery=True, new_token=True, observed_at=now,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()
        return token, cohort, parse_time(cohort["discovery_recorded_at"])

    def snapshot(
        token: TokenCandidate, when: datetime, *, price: float, pair: str,
        safety: bool | None = True,
    ) -> None:
        raw = {"pair": {
            "chainId": token.chain, "dexId": "pancakeswap", "pairAddress": pair,
            "baseToken": {"address": token.address}, "quoteToken": {"address": "0xquote"},
        }}
        if token.chain == "bsc" and safety is not None:
            raw["goplus_evm"] = {"fixture": True}
            raw["execution_safety_checked_at"] = iso(when)
        if token.chain == "solana" and safety is not None:
            raw["goplus_solana"] = {"fixture": True}
            raw["execution_safety_checked_at"] = iso(when)
        stamp = iso(when)
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,
                buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, stamp, stamp, stamp, "dexscreener", price, 20_000,
                0 if safety else None, 0 if safety else None,
                0 if safety else None, 1 if safety else None, json.dumps(raw),
            ),
        )

    legacy, _, _ = enroll("bsc", "0x" + "L" * 40, "Legacy")
    registration = store.register_token_universe_fixed_target_execution(
        paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
    )
    assert int(registration["activation_cohort_id"]) == 1

    executable, _, executable_at = enroll("bsc", "0x" + "A" * 40, "Executable")
    unsupported, _, unsupported_at = enroll("solana", "S" * 32, "Unsupported")
    mismatch, _, mismatch_at = enroll("bsc", "0x" + "M" * 40, "Mismatch")
    unknown, _, unknown_at = enroll("bsc", "0x" + "U" * 40, "Unknown")
    snapshot(executable, executable_at + timedelta(minutes=1), price=1.0, pair="PAIR-A")
    snapshot(executable, executable_at + timedelta(minutes=15, seconds=10), price=2.0, pair="PAIR-A")
    snapshot(unsupported, unsupported_at + timedelta(minutes=1), price=1.0, pair="PAIR-S")
    snapshot(unsupported, unsupported_at + timedelta(minutes=15, seconds=10), price=2.0, pair="PAIR-S")
    snapshot(mismatch, mismatch_at + timedelta(minutes=1), price=1.0, pair="PAIR-M1")
    snapshot(mismatch, mismatch_at + timedelta(minutes=15, seconds=10), price=2.0, pair="PAIR-M2")
    snapshot(unknown, unknown_at + timedelta(minutes=1), price=1.0, pair="PAIR-U", safety=None)
    snapshot(unknown, unknown_at + timedelta(minutes=15, seconds=10), price=2.0, pair="PAIR-U", safety=None)
    store.finalize_token_universe_forward_outcomes(now=now + timedelta(minutes=16))
    decisions_before = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trades_before = store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    positions_before = store.db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    assert store.finalize_token_universe_fixed_target_execution() == {
        "inserted": 4, "modeled_executable": 1,
    }
    rows = list(store.db.execute(
        "SELECT * FROM token_universe_fixed_target_execution_results ORDER BY cohort_id"
    ))
    assert {row["terminal_status"] for row in rows} == {
        "modeled_executable", "unsupported_chain", "route_mismatch", "safety_unknown",
    }
    modeled = next(row for row in rows if row["terminal_status"] == "modeled_executable")
    assert modeled["baseline_snapshot_id"] is not None and modeled["target_snapshot_id"] is not None
    assert modeled["buy_execution_price_usd"] == pytest.approx(1.04)
    assert modeled["buy_fee_usd"] == pytest.approx(35 * 0.006)
    assert modeled["acquired_quantity"] == pytest.approx(35 / 1.04)
    assert modeled["sell_execution_price_usd"] == pytest.approx(1.92)
    assert modeled["sell_net_usd"] == pytest.approx(
        (35 / 1.04) * 1.92 * (1 - 0.006)
    )
    assert json.loads(modeled["safety_sources_json"]) == {
        "entry": ["goplus_evm"], "target": ["goplus_evm"],
    }
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == decisions_before
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == trades_before
    assert store.db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == positions_before
    summary = Store.token_universe_fixed_target_execution_summary_from_connection(store.db)
    assert summary["summary"] == {"assessed_outcomes": 4, "modeled_executable": 1}
    assert int(summary["activation_cohort_id"]) == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_fixed_target_execution_results SET terminal_status='route_mismatch' WHERE id=?",
            (int(modeled["id"]),),
        )
    store.close()


def test_onchain_only_shadow_is_trigger_anchored_append_only_and_strategy_neutral(tmp_path: Path):
    store = Store(tmp_path / "onchain-only-shadow.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    registration = store.register_onchain_only_shadow(
        momentum_threshold=80, paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
        max_quote_delay_seconds=45,
    )
    assert int(registration["activation_transition_id"]) == 0
    token = TokenCandidate(
        chain="bsc", address="0x" + "A" * 40, name="Onchain Only", source="fixture"
    )
    store.upsert_token(token, seen_at=now)
    round_id = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll", chain_scope="bsc",
        started_at=now,
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain="bsc", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    safety_raw = {
        "pair": {
            "chainId": "bsc", "dexId": "pancakeswap", "pairAddress": "PAIR",
            "baseToken": {"address": token.address}, "quoteToken": {"address": "0xquote"},
        },
        "goplus_evm": {"is_honeypot": "0", "buy_tax": "0", "sell_tax": "0"},
        "honeypot_is": {
            "honeypotResult": {"isHoneypot": False},
            "simulationResult": {"buyTax": 0, "sellTax": 0},
        },
        "execution_safety_reports": ["goplus_evm", "honeypot_is"],
        "execution_safety_checked_at": iso(now),
        "execution_safety_disagreement": False,
    }
    baseline_id = store.add_snapshot(TokenSnapshot(
        "bsc", token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
        buy_tax_pct=0, sell_tax_pct=0, honeypot=False, sellable=True,
        observed_at=now, ingested_at=now, provider="dexscreener", raw=safety_raw,
    ))
    transition_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="onchain-only:first",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        snapshot_id=baseline_id,
        metadata={"trigger_kind": "onchain_momentum", "momentum_score": 88.0},
    )
    assert transition_id is not None
    shadow_id = store.enroll_onchain_only_shadow(transition_id)
    assert shadow_id is not None
    cohort = store.db.execute(
        "SELECT * FROM onchain_only_shadow_cohorts WHERE id=?", (shadow_id,)
    ).fetchone()
    assert cohort["baseline_status"] == "valid"
    assert cohort["prior_eligible_event_relation_count"] == 0
    assert cohort["prior_context_assessment_count"] == 0
    trigger_at = parse_time(cohort["trigger_recorded_at"])
    due = store.due_onchain_only_shadow_quotes(now=trigger_at + timedelta(minutes=15, seconds=1))
    primary = next(item for item in due if item["horizon_minutes"] == 15)
    quote_round = store.start_token_discovery_round(
        provider="dexscreener", surface=primary["role"], mode="batch_quote",
        chain_scope="bsc", started_at=trigger_at + timedelta(minutes=15, seconds=1),
    )
    attempt_id = store.start_token_discovery_quote_attempts(
        quote_round, [primary], requested_at=trigger_at + timedelta(minutes=15, seconds=1),
    )[(token.token_id, primary["role"])]
    target_at = trigger_at + timedelta(minutes=15, seconds=2)
    target_raw = json.loads(json.dumps(safety_raw))
    target_raw["execution_safety_checked_at"] = iso(target_at)
    with store.db:
        cursor = store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,
                buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, iso(target_at), iso(target_at), iso(target_at), "dexscreener",
                2.0, 20_000, 0, 0, 0, 1, json.dumps(target_raw),
            ),
        )
        target_id = int(cursor.lastrowid)
    store.finish_token_discovery_quote_attempt(
        attempt_id, status="success", reason_code="snapshot_persisted",
        completed_at=target_at,
    )
    decisions_before = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trades_before = store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    result_id = store.record_onchain_only_shadow_result(
        primary, terminal_status="observed", quote_attempt_id=attempt_id,
        target_snapshot_id=target_id, recorded_at=target_at,
    )
    result = store.db.execute(
        "SELECT * FROM onchain_only_shadow_results WHERE id=?", (result_id,)
    ).fetchone()
    assert result["terminal_status"] == "observed"
    assert result["route_status"] == "same_route"
    assert result["raw_return"] == pytest.approx(1.0)
    assert result["execution_evidence_status"] == "modeled_only_multi_source"
    assert result["modeled_net_return"] is not None
    assert result["decision_eligible"] == 0 and result["affects"] == "none"
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == decisions_before
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == trades_before
    summary = Store.onchain_only_shadow_summary_from_connection(store.db)
    assert summary["status"] == "collecting"
    assert summary["summary"]["cohorts"] == 1
    assert summary["summary"]["primary_terminal"] == 1
    assert summary["summary"]["primary_gte_25pct"] == 1
    assert summary["maturity"]["mature"] is False
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE onchain_only_shadow_results SET raw_return=9 WHERE id=?", (result_id,)
        )

    future_token = TokenCandidate(
        chain="solana", address="F" * 32, name="Future Baseline", source="fixture"
    )
    store.upsert_token(future_token, seen_at=now)
    future_round = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
        started_at=now,
    )
    store.add_token_discovery_exposure(
        future_round, token_id=future_token.token_id, chain="solana", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(future_round, status="completed", returned_count=1)
    future_at = now + timedelta(minutes=5)
    future_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", future_token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
        observed_at=future_at, ingested_at=future_at, provider="fixture",
    ))
    future_transition_id = store.record_token_universe_funnel_transition(
        future_token.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="onchain-only:future",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        snapshot_id=future_snapshot_id,
        metadata={"trigger_kind": "onchain_momentum", "momentum_score": 90.0},
    )
    future_shadow_id = store.enroll_onchain_only_shadow(future_transition_id)
    assert future_shadow_id is not None
    future_shadow = store.db.execute(
        "SELECT * FROM onchain_only_shadow_cohorts WHERE id=?", (future_shadow_id,)
    ).fetchone()
    assert future_shadow["baseline_status"] == "time_order_invalid"
    assert not any(
        item["shadow_cohort_id"] == future_shadow_id
        for item in store.due_onchain_only_shadow_quotes(now=now + timedelta(minutes=16))
    )

    assessed_token = TokenCandidate(
        chain="solana", address="C" * 32, name="Prior Context", source="fixture"
    )
    store.upsert_token(assessed_token, seen_at=now)
    assessed_round = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
        started_at=now,
    )
    store.add_token_discovery_exposure(
        assessed_round, token_id=assessed_token.token_id, chain="solana", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(assessed_round, status="completed", returned_count=1)
    assessed_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", assessed_token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
        observed_at=now, ingested_at=now, provider="fixture",
    ))
    store.add_token_context_assessment(
        assessed_token.token_id, trigger="fixture", status="no_context",
        snapshot_observed_at=now, momentum_score=90, assessment={}, assessed_at=now,
    )
    assessed_transition_id = store.record_token_universe_funnel_transition(
        assessed_token.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="onchain-only:prior-context",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        snapshot_id=assessed_snapshot_id,
        metadata={"trigger_kind": "onchain_momentum", "momentum_score": 90.0},
    )
    assert store.enroll_onchain_only_shadow(assessed_transition_id) is None
    store.close()


def test_token_universe_jupiter_quote_is_forward_baseline_buy_then_target_sell(tmp_path: Path):
    store = Store(tmp_path / "jupiter-quote.sqlite3", initial_cash_usd=1000)
    now = utcnow()

    def enroll(address: str) -> tuple[TokenCandidate, sqlite3.Row, datetime]:
        token = TokenCandidate(chain="solana", address=address, name="Jupiter", source="fixture")
        store.upsert_token(token, seen_at=now)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
            started_at=now,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="new_token",
            first_local_discovery=True, new_token=True, observed_at=now,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()
        return token, cohort, parse_time(cohort["discovery_recorded_at"])

    def snapshot(token: TokenCandidate, when: datetime, price: float) -> None:
        stamp = iso(when)
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,raw_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, stamp, stamp, stamp, "dexscreener", price, 20_000,
                json.dumps({"pair": {"chainId": "solana", "dexId": "raydium",
                            "pairAddress": "PAIR", "baseToken": {"address": token.address},
                            "quoteToken": {"address": Store.JUPITER_USDC_MINT}}}),
            ),
        )

    enroll("L" * 32)
    registration = store.register_token_universe_jupiter_quote(usdc_input_amount_raw=35_000_000)
    assert int(registration["activation_cohort_id"]) == 1
    token, cohort, discovered = enroll("J" * 32)
    snapshot(token, discovered + timedelta(minutes=1), 1.0)
    snapshot(token, discovered + timedelta(minutes=15, seconds=10), 2.0)
    store.finalize_token_universe_forward_outcomes(now=now + timedelta(minutes=16))
    decisions_before = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trades_before = store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

    due = store.due_token_universe_jupiter_quotes()
    assert len(due) == 1
    buy = due[0]
    assert buy["phase"] == "baseline_buy" and buy["outcome_id"] is None
    assert buy["input_mint"] == Store.JUPITER_USDC_MINT
    assert buy["output_mint"] == token.address and buy["input_amount_raw"] == "35000000"
    with pytest.raises(ValueError, match="time order"):
        store.record_token_universe_jupiter_quote(
            buy["quote_key"], status="no_route",
            requested_at=parse_time(buy["source_recorded_at"]) - timedelta(seconds=1),
            completed_at=parse_time(buy["source_recorded_at"]),
        )
    buy_id = store.record_token_universe_jupiter_quote(
        buy["quote_key"], status="quoted", out_amount_raw="123456789",
        other_amount_threshold_raw="120000000", slippage_bps=400,
        signature_fee_lamports=5000, prioritization_fee_lamports=1000, rent_fee_lamports=0,
        router="metis", mode="quote_only", fee_bps=10, platform_fee_bps=5,
        price_impact_pct=0.12, context_slot=123, time_taken_ms=12.5,
        requested_at=parse_time(buy["source_recorded_at"]) + timedelta(seconds=1),
        completed_at=parse_time(buy["source_recorded_at"]) + timedelta(seconds=2),
        route_plan=[{
            "swapInfo": {
                "ammKey": "AMM-1", "label": "Raydium", "inputMint": Store.JUPITER_USDC_MINT,
                "outputMint": token.address, "inAmount": "35000000", "outAmount": "123456789",
                "feeAmount": "12", "feeMint": Store.JUPITER_USDC_MINT,
                "transaction": "must_not_store", "requestId": "must_not_store",
            },
            "percent": 100, "raw": "must_not_store",
        }],
    )
    assert buy_id is not None
    sell = store.due_token_universe_jupiter_quotes()[0]
    assert sell["phase"] == "target_sell" and sell["outcome_id"] is not None
    assert sell["input_mint"] == token.address
    assert sell["output_mint"] == Store.JUPITER_USDC_MINT
    assert sell["input_amount_raw"] == "120000000"
    assert store.record_token_universe_jupiter_quote(
        sell["quote_key"], status="quoted", out_amount_raw="40000000",
        other_amount_threshold_raw="38000000", router="metis", slippage_bps=400,
        requested_at=parse_time(sell["source_recorded_at"]) + timedelta(seconds=1),
        completed_at=parse_time(sell["source_recorded_at"]) + timedelta(seconds=2),
    ) is not None
    assert store.due_token_universe_jupiter_quotes() == []
    rows = list(store.db.execute(
        "SELECT * FROM token_universe_jupiter_quote_results ORDER BY id"
    ))
    assert [(row["phase"], row["terminal_status"]) for row in rows] == [
        ("baseline_buy", "quoted"), ("target_sell", "quoted"),
    ]
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in rows)
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == decisions_before
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == trades_before
    columns = {
        row["name"] for row in store.db.execute(
            "PRAGMA table_info(token_universe_jupiter_quote_results)"
        )
    }
    assert not {"raw_json", "transaction", "request_id", "api_key"} & columns
    summary = Store.token_universe_jupiter_quote_summary_from_connection(store.db)
    assert summary["summary"]["results"] == 2 and summary["summary"]["quoted"] == 2
    assert summary["summary"]["max_quote_delay_seconds"] == pytest.approx(2.0)
    assert summary["summary"]["avg_round_trip_min_return"] == pytest.approx(38 / 35 - 1)
    assert summary["recent"][0]["round_trip_min_return"] == pytest.approx(38 / 35 - 1)
    assert summary["recent"][0]["phase"] == "target_sell"
    assert summary["recent"][0]["token_id"] == token.token_id
    assert summary["recent"][0]["source_observed_at"] == sell["source_observed_at"]
    stored_route = json.loads(rows[0]["route_json"])
    assert stored_route == [{
        "amm_key": "AMM-1", "label": "Raydium", "input_mint": Store.JUPITER_USDC_MINT,
        "output_mint": token.address, "in_amount_raw": "35000000", "out_amount_raw": "123456789",
        "fee_amount_raw": "12", "fee_mint": Store.JUPITER_USDC_MINT, "percent": 100.0,
    }]
    assert "must_not_store" not in json.dumps(summary)
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_jupiter_quote_results SET router='changed' WHERE id=?",
            (buy_id,),
        )
    store.close()


def test_onchain_only_jupiter_quote_is_trigger_anchored_forward_and_attempt_first(
    tmp_path: Path,
):
    store = Store(tmp_path / "onchain-jupiter.sqlite3", initial_cash_usd=1000)
    lookup_plan = " | ".join(
        str(row["detail"])
        for row in store.db.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT c.id
            FROM onchain_only_shadow_cohorts c
            LEFT JOIN onchain_only_jupiter_quote_attempts a
              ON a.definition_version=? AND a.shadow_cohort_id=c.id
             AND a.phase='baseline_buy' AND a.horizon_minutes=0
            LEFT JOIN onchain_only_jupiter_quote_results q
              ON q.definition_version=? AND q.shadow_cohort_id=c.id
             AND q.phase='baseline_buy' AND q.horizon_minutes=0
            WHERE c.definition_version=? AND c.id>? AND lower(c.chain)='solana'
              AND q.id IS NULL
            """,
            (
                Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
                Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
                Store.ONCHAIN_ONLY_SHADOW_VERSION,
                0,
            ),
        )
    )
    assert "onchain_only_jupiter_quote_attempts_lookup_idx" in lookup_plan
    assert "onchain_only_jupiter_quote_results_lookup_idx" in lookup_plan
    now = utcnow()
    store.register_onchain_only_shadow(
        momentum_threshold=80, paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
        max_quote_delay_seconds=45,
    )

    def enroll(address: str, *, recorded_at: datetime) -> tuple[TokenCandidate, int, datetime]:
        token = TokenCandidate(
            chain="solana", address=address, name="Onchain Jupiter", source="fixture"
        )
        store.upsert_token(token, seen_at=recorded_at)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
            started_at=recorded_at,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain="solana", role="new_token",
            first_local_discovery=True, new_token=True, observed_at=recorded_at,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        snapshot_id = store.add_snapshot(TokenSnapshot(
            "solana", token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
            observed_at=recorded_at, ingested_at=recorded_at, provider="fixture",
        ))
        transition_id = store.record_token_universe_funnel_transition(
            token.token_id,
            stage="context_trigger_evaluation", status="eligible",
            reason_code="onchain_momentum", evaluation_key=f"onchain-jupiter:{address}",
            observed_at=recorded_at, ingested_at=recorded_at,
            source_table="token_context_trigger", snapshot_id=snapshot_id,
            metadata={"trigger_kind": "onchain_momentum", "momentum_score": 90.0},
        )
        shadow_id = store.enroll_onchain_only_shadow(transition_id)
        assert shadow_id is not None
        cohort = store.db.execute(
            "SELECT trigger_recorded_at FROM onchain_only_shadow_cohorts WHERE id=?",
            (shadow_id,),
        ).fetchone()
        return token, int(shadow_id), parse_time(cohort["trigger_recorded_at"])

    _, old_shadow_id, _ = enroll(
        "O" * 32, recorded_at=now - timedelta(seconds=4)
    )
    registration = store.register_onchain_only_jupiter_quote(
        usdc_input_amount_raw=35_000_000, max_queue_delay_seconds=30,
        max_total_delay_seconds=45,
    )
    assert int(registration["activation_shadow_cohort_id"]) == old_shadow_id
    token, shadow_id, trigger_at = enroll(
        "J" * 32, recorded_at=now - timedelta(seconds=3)
    )
    assert all(
        item["shadow_cohort_id"] != old_shadow_id
        for item in store.due_onchain_only_jupiter_quotes(now=trigger_at)
    )

    baseline = next(
        item for item in store.due_onchain_only_jupiter_quotes(now=trigger_at)
        if item["shadow_cohort_id"] == shadow_id and item["phase"] == "baseline_buy"
    )
    assert parse_time(baseline["anchor_at"]) == trigger_at
    assert baseline["input_amount_raw"] == "35000000"
    assert baseline["input_mint"] == Store.JUPITER_USDC_MINT
    assert baseline["output_mint"] == token.address
    requested = trigger_at + timedelta(seconds=30)
    attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        baseline, requested_at=requested,
    )
    assert attempt_id is not None
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_only_jupiter_quote_results"
    ).fetchone()[0] == 0
    baseline_id = store.record_onchain_only_jupiter_quote(
        baseline, status="quoted", attempt_id=attempt_id,
        out_amount_raw="1000000000", other_amount_threshold_raw="900000000",
        slippage_bps=400, requested_at=requested,
        completed_at=trigger_at + timedelta(seconds=45),
    )
    assert baseline_id is not None

    targets = store.due_onchain_only_jupiter_quotes(
        now=trigger_at + timedelta(minutes=15)
    )
    target = next(
        item for item in targets
        if item["shadow_cohort_id"] == shadow_id and item["horizon_minutes"] == 15
    )
    assert parse_time(target["anchor_at"]) == trigger_at + timedelta(minutes=15)
    assert target["baseline_result_id"] == baseline_id
    assert target["input_amount_raw"] == "900000000"
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_only_shadow_results"
    ).fetchone()[0] == 0
    target_requested = parse_time(target["anchor_at"]) + timedelta(seconds=10)
    target_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        target, requested_at=target_requested,
    )
    target_id = store.record_onchain_only_jupiter_quote(
        target, status="quoted", attempt_id=target_attempt_id,
        out_amount_raw="50000000", other_amount_threshold_raw="45000000",
        slippage_bps=400, requested_at=target_requested,
        completed_at=parse_time(target["anchor_at"]) + timedelta(seconds=20),
    )
    result = store.db.execute(
        "SELECT * FROM onchain_only_jupiter_quote_results WHERE id=?", (target_id,)
    ).fetchone()
    assert result["validity_status"] == "valid"
    assert result["included_in_round_trip"] == 1
    assert result["round_trip_min_return"] == pytest.approx(45 / 35 - 1)
    assert result["decision_eligible"] == 0 and result["affects"] == "none"

    paper_registration = store.register_onchain_paper_exploration(
        starting_cash_usd=1000, max_open_positions=0,
        estimated_network_fee_usd_each_side=0.01,
    )
    assert json.loads(paper_registration["definition_json"])["max_open_positions"] == 0
    assert int(paper_registration["activation_quote_result_id"]) == target_id
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exploration_positions"
    ).fetchone()[0] == 0
    paper_token, paper_shadow_id, paper_at = enroll(
        "P" * 32, recorded_at=now - timedelta(seconds=2)
    )
    paper_baseline = next(
        item for item in store.due_onchain_only_jupiter_quotes(now=paper_at)
        if item["shadow_cohort_id"] == paper_shadow_id and item["phase"] == "baseline_buy"
    )
    paper_requested = paper_at + timedelta(seconds=1)
    paper_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        paper_baseline, requested_at=paper_requested,
    )
    paper_baseline_id = store.record_onchain_only_jupiter_quote(
        paper_baseline, status="quoted", attempt_id=paper_attempt_id,
        out_amount_raw="1000000000", other_amount_threshold_raw="900000000",
        slippage_bps=400, price_impact_bps=0.0,
        price_impact_source="fixture",
        requested_at=paper_requested,
        completed_at=paper_at + timedelta(seconds=2),
    )
    paper_position = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_positions WHERE shadow_cohort_id=?",
        (paper_shadow_id,),
    ).fetchone()
    assert paper_position["status"] == "open"
    assert paper_position["token_id"] == paper_token.token_id
    assert paper_position["acquired_amount_raw"] == "900000000"
    assert paper_position["baseline_quote_result_id"] == paper_baseline_id
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=paper_token.address, price_usd=1.2,
        liquidity_usd=20_000, market_cap_usd=120_000,
        volume_5m_usd=30_000, buys_5m=30, sells_5m=10,
        observed_at=now, ingested_at=now, provider="fixture",
    ))
    marked_summary = Store.onchain_paper_exploration_summary_from_connection(
        store.db, max_liquidity_impact_pct=0.0025,
    )
    marked_position = next(
        item for item in marked_summary["positions"]
        if item["shadow_cohort_id"] == paper_shadow_id
    )
    assert marked_position["current_price_usd"] == pytest.approx(1.2)
    assert marked_position["market_value_usd"] is None
    assert marked_position["unrealized_pnl_usd"] is None
    assert marked_position["indicative_market_value_usd"] == pytest.approx(42.0)
    assert marked_position["indicative_unrealized_pnl_usd"] == pytest.approx(6.99)
    assert marked_summary["account"]["equity_usd"] is None
    assert marked_summary["account"]["total_pnl_usd"] is None
    assert marked_summary["account"]["indicative_unrealized_pnl_usd"] == pytest.approx(6.99)
    assert marked_summary["account"]["valuation_status"] == (
        "incomplete_no_amount_specific_sell_marks"
    )
    paper_target = next(
        item for item in store.due_onchain_only_jupiter_quotes(
            now=paper_at + timedelta(minutes=15)
        )
        if item["shadow_cohort_id"] == paper_shadow_id
        and item["horizon_minutes"] == 15
    )
    paper_target_requested = parse_time(paper_target["anchor_at"]) + timedelta(seconds=1)
    paper_target_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        paper_target, requested_at=paper_target_requested,
    )
    paper_target_id = store.record_onchain_only_jupiter_quote(
        paper_target, status="quoted", attempt_id=paper_target_attempt_id,
        out_amount_raw="851", other_amount_threshold_raw="816",
        slippage_bps=400, requested_at=paper_target_requested,
        completed_at=paper_target_requested + timedelta(seconds=1),
    )
    paper_position = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_positions WHERE shadow_cohort_id=?",
        (paper_shadow_id,),
    ).fetchone()
    assert paper_position["status"] == "open"
    assessment = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_execution_assessments "
        "WHERE quote_result_id=?", (paper_target_id,),
    ).fetchone()
    assert assessment["economic_status"] == "quoted_but_uneconomic"
    assert assessment["paper_effect"] == "exit_deferred"
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exploration_trades WHERE side='SELL'"
    ).fetchone()[0] == 0
    paper_target_60 = next(
        item for item in store.due_onchain_only_jupiter_quotes(
            now=paper_at + timedelta(minutes=60)
        )
        if item["shadow_cohort_id"] == paper_shadow_id
        and item["horizon_minutes"] == 60
    )
    paper_target_60_requested = (
        parse_time(paper_target_60["anchor_at"]) + timedelta(seconds=1)
    )
    paper_target_60_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        paper_target_60, requested_at=paper_target_60_requested,
    )
    paper_target_60_id = store.record_onchain_only_jupiter_quote(
        paper_target_60, status="quoted", attempt_id=paper_target_60_attempt_id,
        out_amount_raw="47000000", other_amount_threshold_raw="45000000",
        slippage_bps=400, price_impact_bps=0.0,
        price_impact_source="fixture", requested_at=paper_target_60_requested,
        completed_at=paper_target_60_requested + timedelta(seconds=1),
    )
    paper_position = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_positions WHERE shadow_cohort_id=?",
        (paper_shadow_id,),
    ).fetchone()
    assert paper_position["status"] == "closed"
    assert paper_position["exit_quote_result_id"] == paper_target_60_id
    assert paper_position["exit_usdc"] == pytest.approx(44.99)
    assert paper_position["realized_pnl_usd"] == pytest.approx(9.98)
    paper_account = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_account"
    ).fetchone()
    assert paper_account["cash_usd"] == pytest.approx(1009.98)
    assert paper_account["realized_pnl_usd"] == pytest.approx(9.98)
    paper_sell = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_trades WHERE side='SELL'"
    ).fetchone()
    assert paper_sell["gross_usd"] == pytest.approx(45.0)
    assert paper_sell["network_fee_usd"] == pytest.approx(0.01)
    assert paper_sell["net_cash_flow_usd"] == pytest.approx(44.99)
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exploration_trades"
    ).fetchone()[0] == 2
    exploration = Store.onchain_paper_exploration_summary_from_connection(store.db)
    assert exploration["status"] == "running"
    assert exploration["account"]["closed_position_count"] == 1
    assert exploration["account"]["trade_count"] == 2
    assert exploration["account"]["winning_position_count"] == 1
    assert exploration["account"]["losing_position_count"] == 0
    assert exploration["account"]["win_rate"] == 1
    assert exploration["account"]["total_network_fee_usd"] == pytest.approx(0.02)
    assert exploration["account"]["max_cash_drawdown_usd"] == pytest.approx(35.01)
    assert exploration["account"]["equity_is_fully_marked"] is True
    assert len(exploration["account"]["cash_curve"]) == 3
    assert len(exploration["trades"]) == 2
    assert exploration["execution_assessment_counts"][
        "quoted_but_uneconomic:exit_deferred"
    ] == 1

    _, writeoff_shadow_id, writeoff_at = enroll(
        "W" * 32, recorded_at=now - timedelta(milliseconds=1500)
    )
    writeoff_baseline = next(
        item for item in store.due_onchain_only_jupiter_quotes(now=writeoff_at)
        if item["shadow_cohort_id"] == writeoff_shadow_id
        and item["phase"] == "baseline_buy"
    )
    writeoff_requested = writeoff_at + timedelta(seconds=1)
    writeoff_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        writeoff_baseline, requested_at=writeoff_requested,
    )
    store.record_onchain_only_jupiter_quote(
        writeoff_baseline, status="quoted", attempt_id=writeoff_attempt_id,
        out_amount_raw="1000000000", other_amount_threshold_raw="900000000",
        slippage_bps=400, price_impact_bps=0.0,
        price_impact_source="fixture", requested_at=writeoff_requested,
        completed_at=writeoff_requested + timedelta(seconds=1),
    )
    for horizon in (15, 60, 240):
        missing_target = next(
            item for item in store.due_onchain_only_jupiter_quotes(
                now=writeoff_at + timedelta(minutes=horizon)
            )
            if item["shadow_cohort_id"] == writeoff_shadow_id
            and item["horizon_minutes"] == horizon
        )
        missing_requested = parse_time(missing_target["anchor_at"]) + timedelta(seconds=1)
        missing_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
            missing_target, requested_at=missing_requested,
        )
        store.record_onchain_only_jupiter_quote(
            missing_target, status="no_route", attempt_id=missing_attempt_id,
            requested_at=missing_requested,
            completed_at=missing_requested + timedelta(seconds=1),
        )
    writeoff_position = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_positions WHERE shadow_cohort_id=?",
        (writeoff_shadow_id,),
    ).fetchone()
    assert writeoff_position["status"] == "written_off"
    assert writeoff_position["exit_horizon_minutes"] == 240
    assert writeoff_position["realized_pnl_usd"] == pytest.approx(-35.01)
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exploration_trades"
    ).fetchone()[0] == 4

    interrupted_token, interrupted_shadow_id, interrupted_at = enroll(
        "I" * 32, recorded_at=now - timedelta(seconds=1)
    )
    interrupted = next(
        item for item in store.due_onchain_only_jupiter_quotes(now=interrupted_at)
        if item["shadow_cohort_id"] == interrupted_shadow_id
    )
    interrupted_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        interrupted, requested_at=interrupted_at + timedelta(seconds=1),
    )
    recovered = next(
        item for item in store.due_onchain_only_jupiter_quotes(
            now=interrupted_at + timedelta(seconds=2)
        ) if item["shadow_cohort_id"] == interrupted_shadow_id
    )
    assert recovered["preflight_reason"] == "request_evidence_missing"
    store.record_onchain_only_jupiter_quote(
        recovered, status="interrupted_after_request",
        attempt_id=interrupted_attempt_id, evaluated_at=interrupted_at + timedelta(seconds=2),
    )

    _, expired_shadow_id, expired_at = enroll(
        "E" * 32, recorded_at=now
    )
    expired = next(
        item for item in store.due_onchain_only_jupiter_quotes(
            now=expired_at + timedelta(seconds=31)
        ) if item["shadow_cohort_id"] == expired_shadow_id
    )
    assert Store.onchain_only_jupiter_preflight_reason(
        expired, evaluated_at=expired_at + timedelta(seconds=31)
    ) == "queue_delay_expired"
    assert store.record_onchain_only_jupiter_quote(
        expired, status="not_requested", evaluated_at=expired_at + timedelta(seconds=31)
    ) is not None
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_only_jupiter_quote_attempts "
        "WHERE shadow_cohort_id=?", (expired_shadow_id,),
    ).fetchone()[0] == 0

    summary = Store.onchain_only_jupiter_quote_summary_from_connection(store.db)
    assert summary["summary"]["valid_round_trips"] == 3
    assert summary["summary"]["positive"] == 2
    assert summary["summary"]["gte_25pct"] == 2
    assert summary["maturity"]["mature"] is False
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE onchain_only_jupiter_quote_results SET router='changed' WHERE id=?",
            (target_id,),
        )
    store.close()


def test_onchain_paper_exit_challenger_is_forward_amount_specific_and_isolated(
    tmp_path: Path,
):
    store = Store(tmp_path / "onchain-exit-challenger.sqlite3", initial_cash_usd=1000)
    store.register_onchain_only_shadow(
        momentum_threshold=80, paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
        max_quote_delay_seconds=45,
    )
    store.register_onchain_only_jupiter_quote(
        usdc_input_amount_raw=35_000_000, max_queue_delay_seconds=30,
        max_total_delay_seconds=45,
    )
    store.register_onchain_paper_exploration(
        starting_cash_usd=1000, max_open_positions=3,
        estimated_network_fee_usd_each_side=0.01,
    )
    registration = store.register_onchain_paper_exit_challenger(
        starting_cash_usd=1000, quote_retry_seconds=15,
        max_quote_delay_seconds=45,
    )
    assert int(registration["activation_exploration_buy_trade_id"]) == 0

    now = utcnow()
    token = TokenCandidate(
        chain="solana", address="C" * 32, name="Exit Challenger", source="fixture"
    )
    store.upsert_token(token, seen_at=now)
    round_id = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
        started_at=now,
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain="solana", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    entry_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
        observed_at=now, ingested_at=now, provider="fixture",
    ))
    transition_id = store.record_token_universe_funnel_transition(
        token.token_id, stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="exit-challenger",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        snapshot_id=entry_snapshot_id,
        metadata={"trigger_kind": "onchain_momentum", "momentum_score": 90.0},
    )
    shadow_id = store.enroll_onchain_only_shadow(transition_id)
    cohort = store.db.execute(
        "SELECT trigger_recorded_at FROM onchain_only_shadow_cohorts WHERE id=?",
        (shadow_id,),
    ).fetchone()
    trigger_at = parse_time(cohort["trigger_recorded_at"])
    baseline = next(
        item for item in store.due_onchain_only_jupiter_quotes(now=trigger_at)
        if item["shadow_cohort_id"] == shadow_id and item["phase"] == "baseline_buy"
    )
    baseline_requested = trigger_at + timedelta(seconds=1)
    baseline_attempt_id = store.start_onchain_only_jupiter_quote_attempt(
        baseline, requested_at=baseline_requested,
    )
    store.record_onchain_only_jupiter_quote(
        baseline, status="quoted", attempt_id=baseline_attempt_id,
        out_amount_raw="1000000000", other_amount_threshold_raw="900000000",
        slippage_bps=400, price_impact_bps=0.0,
        price_impact_source="fixture", requested_at=baseline_requested,
        completed_at=trigger_at + timedelta(seconds=2),
    )
    assert store.enroll_onchain_paper_exit_challenger() == {
        "inserted": 1, "ineligible": 0,
    }
    position = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_positions WHERE shadow_cohort_id=?",
        (shadow_id,),
    ).fetchone()
    assert position["status"] == "open"
    assert position["remaining_amount_raw"] == "900000000"

    mark_time = utcnow()
    stop_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 0.50, 20_000, 50_000, 1_000, 2, 8,
        observed_at=mark_time, ingested_at=mark_time, provider="dexscreener",
        raw={"pair": {"pairAddress": "pair-1"}},
    ))
    mark = store.record_onchain_paper_exit_challenger_mark(
        int(shadow_id), snapshot_id=stop_snapshot_id, evaluated_at=utcnow(),
    )
    assert mark["action"] == "HARD_STOP"
    assert mark["sell_amount_raw"] == "900000000"
    marked_account = store.record_onchain_paper_exit_challenger_account_snapshot()
    assert marked_account["cash_usd"] == pytest.approx(964.99)
    assert marked_account["marked_value_usd"] == pytest.approx(17.5)
    assert marked_account["realized_pnl_usd"] == pytest.approx(0)
    assert marked_account["unrealized_pnl_usd"] == pytest.approx(-17.51)
    assert marked_account["total_pnl_usd"] == pytest.approx(-17.51)
    assert marked_account["equity_usd"] == pytest.approx(982.49)
    task = store.due_onchain_paper_exit_challenger_quotes(now=utcnow())[0]
    assert task["input_amount_raw"] == "900000000"
    first_requested = utcnow()
    first_attempt_id = store.start_onchain_paper_exit_challenger_quote_attempt(
        task, requested_at=first_requested,
    )
    store.record_onchain_paper_exit_challenger_quote_result(
        task, attempt_id=first_attempt_id, status="no_route",
        completed_at=first_requested + timedelta(seconds=1),
    )
    position = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_positions WHERE shadow_cohort_id=?",
        (shadow_id,),
    ).fetchone()
    assert position["status"] == "open"
    assert position["pending_mark_id"] == mark["id"]
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exit_challenger_quote_results "
        "WHERE validity_status='valid'"
    ).fetchone()[0] == 0

    retry_at = first_requested + timedelta(seconds=17)
    retry = store.due_onchain_paper_exit_challenger_quotes(now=retry_at)[0]
    assert retry["attempt_seq"] == 2
    retry_attempt_id = store.start_onchain_paper_exit_challenger_quote_attempt(
        retry, requested_at=retry_at,
    )
    store.record_onchain_paper_exit_challenger_quote_result(
        retry, attempt_id=retry_attempt_id, status="quoted",
        output_amount_raw="5000", other_amount_threshold_raw="1000",
        slippage_bps=400, price_impact_bps=-500.0,
        price_impact_source="fixture",
        completed_at=retry_at + timedelta(seconds=1),
    )
    position = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_positions WHERE shadow_cohort_id=?",
        (shadow_id,),
    ).fetchone()
    assert position["status"] == "open"
    uneconomic = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_quote_results "
        "WHERE attempt_id=?", (retry_attempt_id,),
    ).fetchone()
    assert uneconomic["validity_status"] == "valid"
    assert uneconomic["economic_status"] == "quoted_but_uneconomic"
    economic_retry_at = retry_at + timedelta(seconds=17)
    economic_retry = store.due_onchain_paper_exit_challenger_quotes(
        now=economic_retry_at
    )[0]
    assert economic_retry["attempt_seq"] == 3
    economic_retry_attempt_id = store.start_onchain_paper_exit_challenger_quote_attempt(
        economic_retry, requested_at=economic_retry_at,
    )
    store.record_onchain_paper_exit_challenger_quote_result(
        economic_retry, attempt_id=economic_retry_attempt_id, status="quoted",
        output_amount_raw="21000000", other_amount_threshold_raw="20000000",
        slippage_bps=400, price_impact_bps=-100.0,
        price_impact_source="fixture",
        completed_at=economic_retry_at + timedelta(seconds=1),
    )
    position = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_positions WHERE shadow_cohort_id=?",
        (shadow_id,),
    ).fetchone()
    assert position["status"] == "closed"
    assert position["remaining_amount_raw"] == "0"
    assert position["realized_proceeds_usd"] == pytest.approx(19.99)
    assert position["realized_pnl_usd"] == pytest.approx(-15.02)
    closed_account = store.record_onchain_paper_exit_challenger_account_snapshot()
    assert closed_account["cash_usd"] == pytest.approx(984.98)
    assert closed_account["realized_pnl_usd"] == pytest.approx(-15.02)
    assert closed_account["unrealized_pnl_usd"] == pytest.approx(0)
    assert closed_account["total_pnl_usd"] == pytest.approx(-15.02)
    before_duplicate = store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exit_challenger_account_snapshots"
    ).fetchone()[0]
    store.record_onchain_paper_exit_challenger_account_snapshot()
    assert store.db.execute(
        "SELECT COUNT(*) FROM onchain_paper_exit_challenger_account_snapshots"
    ).fetchone()[0] == before_duplicate
    summary = Store.onchain_paper_exit_challenger_summary_from_connection(store.db)
    assert summary["account"]["realized_pnl_usd"] == pytest.approx(-15.02)
    assert summary["account"]["total_pnl_usd"] == pytest.approx(-15.02)
    assert len(summary["account"]["performance_curve"]) == 2
    assert store.db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    fixed = store.db.execute(
        "SELECT * FROM onchain_paper_exploration_positions WHERE shadow_cohort_id=?",
        (shadow_id,),
    ).fetchone()
    assert fixed["status"] == "open"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE onchain_paper_exit_challenger_marks SET reason='changed' WHERE id=?",
            (mark["id"],),
        )
    store.close()


def test_zero_liquidity_challenger_mark_is_not_reported_as_pnl(tmp_path: Path):
    store = Store(tmp_path / "zero-liquidity-mark.sqlite3", initial_cash_usd=1000)
    store.register_onchain_paper_exit_challenger(starting_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(
        chain="solana", address="Z" * 32, name="Zero Liquidity", source="fixture"
    )
    store.upsert_token(token, seen_at=now)
    snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 10.0, 0.0, 100_000, 0, 0, 0,
        observed_at=now, ingested_at=now, provider="dexscreener",
    ))
    store.db.execute(
        """
        INSERT INTO onchain_paper_exit_challenger_positions(
            definition_version,shadow_cohort_id,token_id,source_buy_trade_id,
            baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,
            initial_amount_raw,remaining_amount_raw,stake_usd,entry_network_fee_usd,
            realized_proceeds_usd,allocated_cost_usd,realized_pnl_usd,
            highest_signal_price_usd,next_tp_index,status,opened_at,close_reason
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,0,0,?,0,'open',?,'')
        """,
        (
            Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, 1, token.token_id, 1, 1,
            snapshot_id, 1.0, "1000000", "1000000", 35.0, 0.01, 1.0, iso(now),
        ),
    )
    mark = store.record_onchain_paper_exit_challenger_mark(
        1, snapshot_id=snapshot_id, evaluated_at=now + timedelta(seconds=1)
    )
    assert mark["action"] == "LIQUIDITY_EXIT"
    assert mark["marked_value_usd"] is None
    assert mark["unrealized_pnl_usd"] is None
    account = store.record_onchain_paper_exit_challenger_account_snapshot(
        recorded_at=now + timedelta(seconds=2)
    )
    assert account["equity_usd"] is None
    assert account["unrealized_pnl_usd"] is None
    assert account["valuation_status"] == "incomplete_missing_fresh_mark"
    store.close()


def test_exit_challenger_mark_scheduler_prioritizes_unmarked_then_stalest(
    tmp_path: Path,
):
    store = Store(tmp_path / "exit-mark-fairness.sqlite3", initial_cash_usd=1000)
    store.register_onchain_paper_exit_challenger(
        starting_cash_usd=1000, position_scan_seconds=15,
    )
    now = utcnow()
    with store.db:
        for cohort_id in range(1, 5):
            store.db.execute(
                """
                INSERT INTO onchain_paper_exit_challenger_positions(
                    definition_version,shadow_cohort_id,token_id,
                    source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,
                    initial_amount_raw,remaining_amount_raw,stake_usd,
                    entry_network_fee_usd,status,opened_at
                ) VALUES(?,?,?,?,?,?,'1000','1000',35,0.01,'open',?)
                """,
                (
                    Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, cohort_id,
                    f"solana:{chr(64 + cohort_id) * 32}", cohort_id, cohort_id,
                    cohort_id, iso(now - timedelta(minutes=10 - cohort_id)),
                ),
            )
        for cohort_id, seconds_ago in ((1, 20), (2, 30), (3, 40)):
            store.db.execute(
                """
                INSERT INTO onchain_paper_exit_challenger_marks(
                    definition_version,shadow_cohort_id,recorded_at,
                    action,reason
                ) VALUES(?,?,?,'HOLD','fixture')
                """,
                (
                    Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, cohort_id,
                    iso(now - timedelta(seconds=seconds_ago)),
                ),
            )
    due = store.due_onchain_paper_exit_challenger_marks(now=now, limit=3)
    assert [row["shadow_cohort_id"] for row in due] == [4, 3, 2]
    store.close()


def test_exit_quote_scheduler_serves_unattempted_marks_before_retries(
    tmp_path: Path,
):
    store = Store(tmp_path / "exit-quote-fairness.sqlite3", initial_cash_usd=1000)
    store.register_onchain_paper_exit_challenger(
        starting_cash_usd=1000, quote_retry_seconds=15,
        max_quote_delay_seconds=45,
    )
    now = utcnow()
    mark_ids: dict[int, int] = {}
    with store.db:
        for cohort_id, action in ((1, "LIQUIDITY_EXIT"), (2, "LIQUIDITY_EXIT"), (3, "TAKE_PROFIT")):
            store.db.execute(
                """
                INSERT INTO onchain_paper_exit_challenger_positions(
                    definition_version,shadow_cohort_id,token_id,
                    source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,
                    initial_amount_raw,remaining_amount_raw,stake_usd,
                    entry_network_fee_usd,status,opened_at
                ) VALUES(?,?,?,?,?,?,'1000','1000',35,0.01,'open',?)
                """,
                (
                    Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, cohort_id,
                    f"solana:{chr(70 + cohort_id) * 32}", cohort_id, cohort_id,
                    cohort_id, iso(now - timedelta(minutes=10)),
                ),
            )
            cursor = store.db.execute(
                """
                INSERT INTO onchain_paper_exit_challenger_marks(
                    definition_version,shadow_cohort_id,recorded_at,action,
                    sell_amount_raw,reason
                ) VALUES(?,?,?,?,?,'fixture')
                """,
                (
                    Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, cohort_id,
                    iso(now - timedelta(minutes=cohort_id)), action, "1000",
                ),
            )
            mark_ids[cohort_id] = int(cursor.lastrowid)
            store.db.execute(
                "UPDATE onchain_paper_exit_challenger_positions "
                "SET pending_mark_id=? WHERE definition_version=? AND shadow_cohort_id=?",
                (
                    mark_ids[cohort_id],
                    Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, cohort_id,
                ),
            )
        store.db.execute(
            """
            INSERT INTO onchain_paper_exit_challenger_quote_attempts(
                definition_version,quote_key,mark_id,shadow_cohort_id,attempt_seq,
                input_mint,output_mint,input_amount_raw,requested_at
            ) VALUES(?,?,?,?,1,?,?,?,?)
            """,
            (
                Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, "fixture:retry",
                mark_ids[1], 1, "G" * 32, Store.JUPITER_USDC_MINT, "1000",
                iso(now - timedelta(minutes=2)),
            ),
        )
    due = store.due_onchain_paper_exit_challenger_quotes(now=now, limit=3)
    assert [row["shadow_cohort_id"] for row in due] == [2, 3, 1]
    assert [row["attempt_seq"] for row in due] == [1, 1, 2]
    store.close()


def test_onchain_narrative_runner_pairs_only_new_exact_buys_and_requires_economic_exit(
    tmp_path: Path,
):
    store = Store(tmp_path / "narrative-runner.sqlite3", initial_cash_usd=1000)
    store.register_onchain_paper_exploration(
        starting_cash_usd=1000, estimated_network_fee_usd_each_side=0.01,
    )
    store.register_onchain_paper_exit_challenger(
        starting_cash_usd=1000, quote_retry_seconds=15,
        max_quote_delay_seconds=45,
    )
    now = utcnow()

    def insert_strategy2_buy(
        cohort_id: int, token: TokenCandidate, quote_result_id: int, opened_at,
    ) -> tuple[int, int]:
        store.upsert_token(token, seen_at=opened_at)
        snapshot_id = store.add_snapshot(TokenSnapshot(
            "solana", token.address, 1.0, 20_000, 100_000, 30_000, 30, 10,
            observed_at=opened_at, ingested_at=opened_at, provider="fixture",
        ))
        stamp = iso(opened_at)
        with store.db:
            store.db.execute(
                """
                INSERT INTO onchain_paper_exploration_positions(
                    definition_version,shadow_cohort_id,token_id,
                    baseline_quote_result_id,stake_usd,acquired_amount_raw,
                    entry_network_fee_usd,opened_at,status
                ) VALUES(?,?,?,?,?,?,?,?,'open')
                """,
                (
                    Store.ONCHAIN_PAPER_EXPLORATION_VERSION, cohort_id,
                    token.token_id, quote_result_id, 35.0, "900000000", 0.01, stamp,
                ),
            )
            cursor = store.db.execute(
                """
                INSERT INTO onchain_paper_exploration_trades(
                    definition_version,shadow_cohort_id,token_id,quote_result_id,
                    side,horizon_minutes,gross_usd,network_fee_usd,
                    net_cash_flow_usd,realized_pnl_usd,reason,created_at
                ) VALUES(?,?,?,?, 'BUY',0,35,0.01,-35.01,NULL,?,?)
                """,
                (
                    Store.ONCHAIN_PAPER_EXPLORATION_VERSION, cohort_id,
                    token.token_id, quote_result_id,
                    "jupiter_minimum_output_entry", stamp,
                ),
            )
        return int(cursor.lastrowid), snapshot_id

    old_token = TokenCandidate(
        chain="solana", address="N" * 32, name="Old Narrative", source="fixture"
    )
    old_buy_id, _ = insert_strategy2_buy(1, old_token, 101, now)
    registration = store.register_onchain_paper_narrative_runner(
        starting_cash_usd=1000,
    )
    assert int(registration["activation_exploration_buy_trade_id"]) == old_buy_id
    assert store.enroll_onchain_paper_narrative_runner() == {
        "inserted": 0, "rejected": 0,
    }

    token = TokenCandidate(
        chain="solana", address="Q" * 32, name="New Narrative", source="fixture"
    )
    opened_at = utcnow()
    buy_id, entry_snapshot_id = insert_strategy2_buy(2, token, 102, opened_at)
    assert buy_id > old_buy_id
    assert store.enroll_onchain_paper_narrative_runner() == {
        "inserted": 1, "rejected": 0,
    }
    paired = store.onchain_paper_narrative_runner_positions()[0]
    assert paired["source_buy_trade_id"] == buy_id
    assert paired["token_id"] == token.token_id
    assert paired["opened_at"] == iso(opened_at)
    assert paired["stake_usd"] == pytest.approx(35)
    assert paired["initial_amount_raw"] == "900000000"
    assert paired["remaining_amount_raw"] == "900000000"
    assert paired["entry_network_fee_usd"] == pytest.approx(0.01)
    assert paired["status"] == "baseline"
    assert store.onchain_paper_narrative_runner_account()["cash_usd"] == pytest.approx(
        964.99
    )
    assert len(store.onchain_paper_narrative_runner_trades()) == 1
    pairing = store.onchain_paper_narrative_runner_pairing_summary()
    assert pairing["eligible_source_buy_count"] == 1
    assert pairing["paired_position_count"] == 1
    assert pairing["exact_pairing_count"] == 1
    assert pairing["backfilled_position_count"] == 0
    assert pairing["runner_activation_count"] == 0
    assert pairing["narrative_evidence_status"] == "not_mature_not_enabled"

    with store.db:
        store.db.execute(
            """
            INSERT INTO onchain_paper_exit_challenger_positions(
                definition_version,shadow_cohort_id,token_id,source_buy_trade_id,
                baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,
                initial_amount_raw,remaining_amount_raw,stake_usd,
                entry_network_fee_usd,highest_signal_price_usd,status,opened_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'open',?)
            """,
            (
                Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION, 2, token.token_id,
                buy_id, 102, entry_snapshot_id, 1.0, "900000000", "900000000",
                35.0, 0.01, 1.0, iso(opened_at),
            ),
        )
    mark_time = utcnow()
    stop_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 0.5, 20_000, 50_000, 1_000, 2, 8,
        observed_at=mark_time, ingested_at=mark_time, provider="dexscreener",
    ))
    mark = store.record_onchain_paper_exit_challenger_mark(
        2, snapshot_id=stop_snapshot_id,
        evaluated_at=mark_time + timedelta(seconds=1),
    )
    assert mark["action"] == "HARD_STOP"
    task = store.due_onchain_paper_exit_challenger_quotes(
        now=mark_time + timedelta(seconds=2)
    )[0]
    requested_at = mark_time + timedelta(seconds=2)
    attempt_id = store.start_onchain_paper_exit_challenger_quote_attempt(
        task, requested_at=requested_at,
    )
    store.record_onchain_paper_exit_challenger_quote_result(
        task, attempt_id=attempt_id, status="quoted",
        output_amount_raw="1200", other_amount_threshold_raw="1000",
        slippage_bps=400, completed_at=requested_at + timedelta(seconds=1),
    )
    uneconomic = store.db.execute(
        "SELECT * FROM onchain_paper_exit_challenger_quote_results WHERE attempt_id=?",
        (attempt_id,),
    ).fetchone()
    assert uneconomic["economic_status"] == "quoted_but_uneconomic"
    assert len(store.onchain_paper_narrative_runner_trades()) == 1
    assert store.onchain_paper_narrative_runner_positions()[0]["status"] == "baseline"
    assert store.onchain_paper_narrative_runner_account()["cash_usd"] == pytest.approx(
        964.99
    )

    retry_at = requested_at + timedelta(seconds=17)
    retry = store.due_onchain_paper_exit_challenger_quotes(now=retry_at)[0]
    retry_attempt_id = store.start_onchain_paper_exit_challenger_quote_attempt(
        retry, requested_at=retry_at,
    )
    store.record_onchain_paper_exit_challenger_quote_result(
        retry, attempt_id=retry_attempt_id, status="quoted",
        output_amount_raw="21000000", other_amount_threshold_raw="20000000",
        slippage_bps=400, completed_at=retry_at + timedelta(seconds=1),
    )
    closed = store.onchain_paper_narrative_runner_positions()[0]
    assert closed["status"] == "closed"
    assert closed["remaining_amount_raw"] == "0"
    assert closed["realized_proceeds_usd"] == pytest.approx(19.99)
    assert closed["realized_pnl_usd"] == pytest.approx(-15.02)
    trades = store.onchain_paper_narrative_runner_trades()
    assert [row["side"] for row in trades] == ["SELL", "BUY"]
    assert trades[0]["gross_usd"] == pytest.approx(20.0)
    assert trades[0]["network_fee_usd"] == pytest.approx(0.01)
    assert trades[0]["net_cash_flow_usd"] == pytest.approx(19.99)
    assert store.onchain_paper_narrative_runner_account()["cash_usd"] == pytest.approx(
        984.98
    )
    web_summary = Store.onchain_paper_narrative_runner_summary_from_connection(
        store.db
    )
    assert web_summary["status"] == "running"
    assert web_summary["account"]["closed_position_count"] == 1
    assert web_summary["pairing_summary"]["paired_entries"] == 1
    assert web_summary["pairing_summary"]["mismatches"] == 0
    assert web_summary["pairing_summary"]["backfilled_position_count"] == 0
    store.close()


def test_onchain_narrative_context_is_forward_only_and_recovers_unadmitted_seed(
    tmp_path: Path,
):
    store = Store(tmp_path / "narrative-context.sqlite3", initial_cash_usd=1000)
    store.register_onchain_paper_narrative_runner(starting_cash_usd=1000)
    opened_at = utcnow() - timedelta(minutes=3)

    def insert_strategy2_buy(cohort_id: int, token: TokenCandidate) -> int:
        store.upsert_token(token, seen_at=opened_at)
        with store.db:
            store.db.execute(
                """
                INSERT INTO onchain_paper_exploration_positions(
                    definition_version,shadow_cohort_id,token_id,
                    baseline_quote_result_id,stake_usd,acquired_amount_raw,
                    entry_network_fee_usd,opened_at,status
                ) VALUES(?,?,?,?,?,?,?,?,'open')
                """,
                (
                    Store.ONCHAIN_PAPER_EXPLORATION_VERSION, cohort_id,
                    token.token_id, 100 + cohort_id, 35.0, "900000000", 0.01,
                    iso(opened_at),
                ),
            )
            cursor = store.db.execute(
                """
                INSERT INTO onchain_paper_exploration_trades(
                    definition_version,shadow_cohort_id,token_id,quote_result_id,
                    side,horizon_minutes,gross_usd,network_fee_usd,
                    net_cash_flow_usd,realized_pnl_usd,reason,created_at
                ) VALUES(?,?,?,?, 'BUY',0,35,0.01,-35.01,NULL,?,?)
                """,
                (
                    Store.ONCHAIN_PAPER_EXPLORATION_VERSION, cohort_id,
                    token.token_id, 100 + cohort_id,
                    "jupiter_minimum_output_entry", iso(opened_at),
                ),
            )
        return int(cursor.lastrowid)

    excluded = TokenCandidate(
        chain="solana", address="C" * 32, name="Context Frontier", source="fixture"
    )
    excluded_buy_id = insert_strategy2_buy(1, excluded)
    registration = store.register_onchain_paper_narrative_context()
    assert int(registration["activation_source_buy_trade_id"]) == excluded_buy_id
    assert store.enroll_onchain_paper_narrative_runner()["inserted"] == 1
    assert store.due_onchain_paper_narrative_context(now=utcnow(), limit=10) == []

    token = TokenCandidate(
        chain="solana", address="D" * 32, name="Forward Context", source="fixture"
    )
    buy_id = insert_strategy2_buy(2, token)
    assert buy_id > excluded_buy_id
    assert store.enroll_onchain_paper_narrative_runner()["inserted"] == 1
    snapshot_at = opened_at + timedelta(minutes=1)
    snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 0.01, 50_000, 500_000, 20_000, 100, 20,
        observed_at=snapshot_at, ingested_at=snapshot_at + timedelta(seconds=1),
        provider="fixture",
    ))
    round_id = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
        started_at=opened_at,
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain="solana", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=opened_at,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    transition_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="post_entry_narrative_position",
        evaluation_key=f"post-entry:{buy_id}", observed_at=snapshot_at,
        ingested_at=utcnow(), source_table="token_context_trigger",
        source_record_ids={
            "source_buy_trade_id": buy_id, "shadow_cohort_id": 2,
            "snapshot_id": snapshot_id,
        },
        snapshot_id=snapshot_id,
        metadata={
            "trigger_kind": "post_entry_narrative_position",
            "source_buy_trade_id": buy_id, "shadow_cohort_id": 2,
            "context_snapshot_basis": "post_entry_snapshot",
        },
    )
    assert transition_id is not None
    wrong_transition_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation", status="eligible",
        reason_code="post_entry_narrative_position",
        evaluation_key=f"post-entry-wrong:{buy_id}", observed_at=snapshot_at,
        ingested_at=utcnow(), source_table="token_context_trigger",
        source_record_ids={
            "source_buy_trade_id": buy_id + 1, "shadow_cohort_id": 2,
            "snapshot_id": snapshot_id,
        },
        snapshot_id=snapshot_id,
        metadata={
            "trigger_kind": "post_entry_narrative_position",
            "source_buy_trade_id": buy_id + 1, "shadow_cohort_id": 2,
            "context_snapshot_basis": "post_entry_snapshot",
        },
    )
    with pytest.raises(ValueError, match="lineage mismatch"):
        store.record_onchain_paper_narrative_context_seed(
            source_buy_trade_id=buy_id, snapshot_id=snapshot_id,
            trigger_transition_id=wrong_transition_id, status="triggered",
            reason_code="post_entry_narrative_position",
        )
    seed_id = store.record_onchain_paper_narrative_context_seed(
        source_buy_trade_id=buy_id, snapshot_id=snapshot_id,
        trigger_transition_id=transition_id, status="triggered",
        reason_code="post_entry_narrative_position",
    )
    assert seed_id is not None
    due = store.due_onchain_paper_narrative_context(now=utcnow(), limit=10)
    assert [row["source_buy_trade_id"] for row in due] == [buy_id]
    assert due[0]["context_trigger_transition_id"] == transition_id
    store.add_token_context_admission_attempt(
        token.token_id, outcome="skipped", reason="global_cooldown_active",
        trigger={
            "kind": "post_entry_narrative_position", "transition_id": transition_id,
        },
        snapshot_observed_at=snapshot_at, momentum_score=80,
        quota_day=utcnow().date().isoformat(), daily_call_limit=384,
        calls_used_before=1, daily_token_budget=50_000_000,
        tokens_used_before=1000, token_reserve_per_call=100_000,
    )
    assert store.due_onchain_paper_narrative_context(now=utcnow(), limit=10) == []
    summary = Store.onchain_paper_narrative_runner_summary_from_connection(store.db)
    context = summary["context_evidence"]
    assert context["eligible_positions"] == 1
    assert context["pre_registration_excluded"] == 1
    assert context["seeded_positions"] == 1
    assert context["dispatch_pending"] == 0
    assert context["attempted_positions"] == 1
    assert context["admission_reason_counts"] == {
        "skipped:global_cooldown_active": 1,
    }
    assert context["snapshot_basis_counts"] == {"post_entry_snapshot": 1}
    store.close()


def test_post_entry_context_snapshot_uses_causal_entry_fallback_until_refresh(
    tmp_path: Path,
):
    store = Store(tmp_path / "post-entry-snapshot.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(
        chain="solana", address="E" * 32, name="Entry Snapshot", source="fixture"
    )
    store.upsert_token(token)
    observed_at = utcnow() - timedelta(minutes=5)
    ingested_at = observed_at + timedelta(seconds=1)
    recorded_at = observed_at + timedelta(seconds=2)
    opened_at = observed_at + timedelta(seconds=3)
    with store.db:
        cursor = store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,
                price_usd,liquidity_usd,raw_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, iso(observed_at), iso(ingested_at), iso(recorded_at),
                "fixture", 0.01, 20_000, "{}",
            ),
        )
        entry_snapshot_id = int(cursor.lastrowid)
    fallback = store.post_entry_context_snapshot(
        token.token_id,
        opened_at=opened_at,
        at_or_before=opened_at + timedelta(seconds=60),
        entry_snapshot_id=entry_snapshot_id,
    )
    assert fallback is not None
    assert fallback[0] == entry_snapshot_id

    refreshed_at = opened_at + timedelta(seconds=70)
    refreshed_id = store.add_snapshot(TokenSnapshot(
        "solana", token.address, 0.012, 22_000, 0, 1000, 10, 2,
        observed_at=refreshed_at, ingested_at=refreshed_at + timedelta(seconds=1),
        provider="fixture",
    ))
    refreshed = store.post_entry_context_snapshot(
        token.token_id,
        opened_at=opened_at,
        at_or_before=utcnow(),
        entry_snapshot_id=entry_snapshot_id,
    )
    assert refreshed is not None
    assert refreshed[0] == refreshed_id
    store.close()


def test_simulation_fair_epoch_preserves_history_and_resets_active_paper(tmp_path: Path):
    store = Store(tmp_path / "fair-start.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    with store.db:
        store.db.execute(
            "UPDATE paper_account SET cash_usd=975,realized_pnl_usd=-25,updated_at=?",
            (iso(now - timedelta(minutes=1)),),
        )
        store.db.execute(
            """
            INSERT INTO trades(
                token_id,event_id,side,quantity,price,gross_usd,fee_usd,reason,created_at
            ) VALUES('solana:old',1,'SELL',1,1,1,0,'old-round',?)
            """,
            (iso(now - timedelta(minutes=1)),),
        )
    epoch = store.start_simulation_fair_epoch(
        "fair-comparison/test", starting_cash_usd=1000, started_at=now
    )
    assert epoch["status"] == "started"
    assert epoch["prior_cash_usd"] == pytest.approx(975)
    assert epoch["prior_trade_count"] == 1
    assert store.account() == {"cash_usd": 1000.0, "realized_pnl_usd": 0.0}
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    assert store.start_simulation_fair_epoch(
        "fair-comparison/test", starting_cash_usd=500, started_at=now
    )["status"] == "already_started"
    store.close()


def test_jupiter_quote_validity_is_forward_and_uses_fixed_target_anchor(tmp_path: Path):
    store = Store(tmp_path / "jupiter-validity.sqlite3", initial_cash_usd=1000)
    now = utcnow()

    def enroll(address: str) -> tuple[TokenCandidate, sqlite3.Row, datetime]:
        token = TokenCandidate(chain="solana", address=address, name="Validity", source="fixture")
        store.upsert_token(token, seen_at=now)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope="solana",
            started_at=now,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="new_token",
            first_local_discovery=True, new_token=True, observed_at=now,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?", (token.token_id,)
        ).fetchone()
        return token, cohort, parse_time(cohort["discovery_recorded_at"])

    def snapshot(token: TokenCandidate, when: datetime, price: float) -> None:
        stamp = iso(when)
        store.db.execute(
            """
            INSERT INTO token_snapshots(
                token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,raw_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                token.token_id, stamp, stamp, stamp, "dexscreener", price, 20_000,
                json.dumps({"pair": {"chainId": "solana", "dexId": "raydium",
                            "pairAddress": "PAIR", "baseToken": {"address": token.address},
                            "quoteToken": {"address": Store.JUPITER_USDC_MINT}}}),
            ),
        )

    old_token, old_cohort, _ = enroll("O" * 32)
    store.register_token_universe_jupiter_quote(usdc_input_amount_raw=35_000_000)
    registration = store.register_token_universe_jupiter_quote_validity(
        max_queue_delay_seconds=30, max_total_delay_seconds=45,
    )
    assert int(registration["activation_cohort_id"]) == int(old_cohort["id"])
    tokens = [enroll(letter * 32) for letter in ("A", "B", "C")]
    for token, _, discovered in tokens:
        snapshot(token, discovered + timedelta(seconds=1), 1.0)
        snapshot(token, discovered + timedelta(minutes=15, seconds=1), 2.0)
    store.finalize_token_universe_forward_outcomes(now=now + timedelta(minutes=16))
    assert all(item["cohort_id"] != int(old_cohort["id"])
               for item in store.due_token_universe_jupiter_quotes(limit=100))

    due = {item["cohort_id"]: item for item in store.due_token_universe_jupiter_quotes(limit=100)}
    for index in (0, 2):
        _, cohort, _ = tokens[index]
        task = due[int(cohort["id"])]
        anchor = parse_time(task["anchor_at"])
        assert store.record_token_universe_jupiter_quote_validity(
            task, status="quoted", out_amount_raw="123456789",
            other_amount_threshold_raw="120000000", slippage_bps=400,
            requested_at=anchor + timedelta(seconds=30),
            completed_at=anchor + timedelta(seconds=45),
        ) is not None
    _, blocked_cohort, _ = tokens[1]
    blocked = due[int(blocked_cohort["id"])]
    assert store.record_token_universe_jupiter_quote_validity(
        blocked, status="not_requested",
        evaluated_at=parse_time(blocked["anchor_at"]) + timedelta(seconds=30, microseconds=1),
    ) is not None

    targets = {item["cohort_id"]: item for item in store.due_token_universe_jupiter_quotes(limit=100)}
    valid_target = targets[int(tokens[0][1]["id"])]
    late_target = targets[int(tokens[2][1]["id"])]
    assert parse_time(valid_target["anchor_at"]) == parse_time(valid_target["target_at"])
    assert parse_time(valid_target["source_recorded_at"]) == (
        parse_time(valid_target["target_at"]) + timedelta(seconds=1)
    )
    assert store.record_token_universe_jupiter_quote_validity(
        valid_target, status="quoted", out_amount_raw="40000000",
        other_amount_threshold_raw="38000000", slippage_bps=400,
        requested_at=parse_time(valid_target["target_at"]) + timedelta(seconds=30),
        completed_at=parse_time(valid_target["target_at"]) + timedelta(seconds=45),
    ) is not None
    assert store.record_token_universe_jupiter_quote_validity(
        late_target, status="quoted", out_amount_raw="40000000",
        other_amount_threshold_raw="38000000", slippage_bps=400,
        requested_at=parse_time(late_target["target_at"]) + timedelta(seconds=30),
        completed_at=parse_time(late_target["target_at"]) + timedelta(seconds=46),
    ) is not None
    store.finalize_token_universe_jupiter_quote_validity_gaps()

    rows = list(store.db.execute(
        "SELECT * FROM token_universe_jupiter_quote_validity_results ORDER BY id"
    ))
    statuses = {(row["cohort_id"], row["phase"]): row for row in rows}
    assert statuses[(int(tokens[0][1]["id"]), "target_sell")]["validity_status"] == "valid"
    assert statuses[(int(tokens[0][1]["id"]), "target_sell")]["included_in_round_trip"] == 1
    assert statuses[(int(tokens[1][1]["id"]), "baseline_buy")]["validity_status"] == "queue_delay_expired"
    assert statuses[(int(tokens[1][1]["id"]), "target_sell")]["validity_status"] == "baseline_not_valid"
    assert statuses[(int(tokens[2][1]["id"]), "target_sell")]["validity_status"] == "total_delay_expired"
    assert statuses[(int(tokens[2][1]["id"]), "target_sell")]["included_in_round_trip"] == 0
    raw_late = store.db.execute(
        "SELECT round_trip_min_return FROM token_universe_jupiter_quote_results WHERE id=?",
        (statuses[(int(tokens[2][1]["id"]), "target_sell")]["raw_quote_result_id"],),
    ).fetchone()
    assert raw_late is not None and raw_late["round_trip_min_return"] is None
    summary = Store.token_universe_jupiter_quote_validity_summary_from_connection(store.db)
    assert summary["summary"]["results"] == 6
    assert summary["summary"]["valid_round_trips"] == 1
    assert summary["summary"]["legacy_validity_unknown"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_universe_jupiter_quote_validity_results SET validity_status='valid' "
            "WHERE id=?", (int(rows[-1]["id"]),),
        )
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
    assert observations[0].source_item_id == "https://mastodon.social/@example/1"
    assert observations[0].raw["source_item_state"] == "present"
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
    now = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
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


def test_token_context_deferred_admission_is_forward_only_linked_and_observational(
    tmp_path: Path,
):
    store = Store(tmp_path / "deferred-context.sqlite3")
    now = utcnow()

    def enroll(address: str) -> TokenCandidate:
        token = TokenCandidate(
            chain="solana", address=address, name="Deferred context", symbol="DEFER"
        )
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana", started_at=now,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True, observed_at=now,
        )
        store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1, completed_at=now,
        )
        return token

    def skip(
        token: TokenCandidate,
        *,
        evaluated_at,
        trigger: dict,
        next_eligible_at,
    ) -> int:
        admission_id = store.add_token_context_admission_attempt(
            token.token_id, outcome="skipped", reason="global_cooldown_active",
            trigger=trigger, snapshot_observed_at=evaluated_at, momentum_score=0,
            next_eligible_at=next_eligible_at,
            quota_day=evaluated_at.date().isoformat(), daily_call_limit=100,
            calls_used_before=1, daily_token_budget=1_000_000,
            tokens_used_before=1, token_reserve_per_call=1,
            evaluated_at=evaluated_at,
        )
        cohort_id = store.enroll_token_context_deferred_admission(
            admission_id, trigger=trigger
        )
        assert cohort_id is not None
        return admission_id

    linked = enroll("A" * 32)
    store.upsert_token_source_link(
        {
            "token_id": linked.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata_uri",
            "role": "identity",
            "original_url": "https://x.com/binance/status/1",
            "normalized_url": "https://x.com/binance/status/1",
            "link_kind": "social_post",
            "platform": "x",
            "verification_status": "provider_metadata_unverified",
        },
        observed_at=now,
    )
    source_link_id = int(store.token_source_links(linked.token_id)[0]["id"])
    trigger_transition_id = store.record_token_universe_funnel_transition(
        linked.token_id, stage="context_trigger_evaluation", status="eligible",
        reason_code="high_impact_account_metadata_lead", evaluation_key="fixture:trigger",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        source_link_id=source_link_id,
        source_record_ids={"source_link_id": source_link_id},
        metadata={"trigger_kind": "high_impact_account_metadata_lead", "trigger_priority": 2},
    )
    assert trigger_transition_id is not None
    linked_trigger = {
        "kind": "high_impact_account_metadata_lead", "priority": 2,
        "transition_id": trigger_transition_id, "source_link_id": source_link_id,
        "platform": "x", "entity_id": "binance",
    }
    linked_deferred_at = utcnow()
    linked_admission = skip(
        linked, evaluated_at=linked_deferred_at, trigger=linked_trigger,
        next_eligible_at=linked_deferred_at + timedelta(minutes=5),
    )
    linked_cohort = store.db.execute(
        "SELECT * FROM token_context_deferred_admission_cohorts WHERE admission_id=?",
        (linked_admission,),
    ).fetchone()
    assert int(linked_cohort["trigger_transition_id"]) == trigger_transition_id
    assert int(linked_cohort["source_link_id"]) == source_link_id
    assert linked_cohort["lineage_status"] == "exact_trigger_and_source_link"
    store.add_token_context_admission_attempt(
        linked.token_id, outcome="admitted", reason="admitted", trigger=linked_trigger,
        snapshot_observed_at=linked_deferred_at + timedelta(minutes=6), momentum_score=0,
        quota_day=now.date().isoformat(), daily_call_limit=100, calls_used_before=2,
        daily_token_budget=1_000_000, tokens_used_before=2,
        token_reserve_per_call=1, evaluated_at=linked_deferred_at + timedelta(minutes=6),
    )

    skipped_again = enroll("B" * 32)
    skipped_trigger_id = store.record_token_universe_funnel_transition(
        skipped_again.token_id, stage="context_trigger_evaluation", status="eligible",
        reason_code="onchain_momentum", evaluation_key="fixture:skipped-trigger",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
    )
    skipped_trigger = {
        "kind": "onchain_momentum", "priority": 1,
        "transition_id": skipped_trigger_id,
    }
    skipped_deferred_at = utcnow()
    skipped_admission = skip(
        skipped_again, evaluated_at=skipped_deferred_at, trigger=skipped_trigger,
        next_eligible_at=skipped_deferred_at + timedelta(minutes=5),
    )
    store.add_token_context_admission_attempt(
        skipped_again.token_id, outcome="admitted", reason="admitted", trigger=skipped_trigger,
        snapshot_observed_at=skipped_deferred_at + timedelta(minutes=2), momentum_score=90,
        quota_day=now.date().isoformat(), daily_call_limit=100, calls_used_before=2,
        daily_token_budget=1_000_000, tokens_used_before=2, token_reserve_per_call=1,
        evaluated_at=skipped_deferred_at + timedelta(minutes=2),
    )
    store.add_token_context_admission_attempt(
        skipped_again.token_id, outcome="skipped", reason="global_cooldown_active",
        trigger=skipped_trigger,
        snapshot_observed_at=skipped_deferred_at + timedelta(minutes=6), momentum_score=90,
        next_eligible_at=skipped_deferred_at + timedelta(minutes=10), quota_day=now.date().isoformat(),
        daily_call_limit=100, calls_used_before=2, daily_token_budget=1_000_000,
        tokens_used_before=2, token_reserve_per_call=1,
        evaluated_at=skipped_deferred_at + timedelta(minutes=6),
    )

    expired = enroll("C" * 32)
    expired_trigger_id = store.record_token_universe_funnel_transition(
        expired.token_id, stage="context_trigger_evaluation", status="eligible",
        reason_code="token_metadata_source_link", evaluation_key="fixture:expired-trigger",
        observed_at=now, ingested_at=now, source_table="token_context_trigger",
        metadata={"trigger_kind": "token_metadata_source_link", "trigger_priority": 1},
    )
    expired_trigger = {
        "kind": "token_metadata_source_link", "priority": 1,
        "transition_id": expired_trigger_id,
    }
    expired_deferred_at = utcnow()
    skip(
        expired, evaluated_at=expired_deferred_at, trigger=expired_trigger,
        next_eligible_at=expired_deferred_at + timedelta(minutes=5),
    )
    unreached = enroll("D" * 32)
    for index in range(2):
        assert store.record_token_universe_funnel_transition(
            unreached.token_id, stage="context_trigger_evaluation", status="eligible",
            reason_code="token_metadata_source_link",
            evaluation_key=f"fixture:unreached-trigger:{index}",
            observed_at=now, ingested_at=now, source_table="token_context_trigger",
            metadata={"trigger_kind": "token_metadata_source_link", "trigger_priority": 1},
        ) is not None
    assert store.finalize_token_context_deferred_admissions(
        now=max(linked_deferred_at, skipped_deferred_at, expired_deferred_at) + timedelta(minutes=7)
    ) == {
        "resolved": 1, "later_admitted": 1, "expired_without_admission": 0,
    }
    final = store.finalize_token_context_deferred_admissions(
        now=max(linked_deferred_at, skipped_deferred_at, expired_deferred_at) + timedelta(minutes=181)
    )
    assert final["expired_without_admission"] == 2
    assert final["resolved"] == 2
    outcomes = {
        row["outcome"]: int(row["count"])
        for row in store.db.execute(
            "SELECT outcome,COUNT(*) count FROM token_context_deferred_admission_results GROUP BY outcome"
        )
    }
    assert outcomes == {
        "later_admitted": 1,
        "expired_without_admission": 2,
    }
    summary = Store.token_context_admission_summary_from_connection(store.db)
    assert summary["deferred"]["summary"] == {
        "cohorts": 3, "pending": 0, "later_admitted": 1,
        "expired_without_admission": 2,
        "exact_trigger_lineage": 3, "source_linked": 1,
    }
    assert summary["deferred"]["active_retry"] is False
    assert summary["deferred"]["affects"] == "none"
    trigger_coverage = summary["trigger_coverage"]
    assert trigger_coverage["summary"]["transitions"] == 5
    assert trigger_coverage["summary"]["episodes"] == 4
    assert trigger_coverage["summary"]["repeat_transitions"] == 1
    assert trigger_coverage["summary"]["exact_linked_transitions"] == 3
    assert trigger_coverage["summary"]["episodes_with_admission_attempt"] == 3
    assert trigger_coverage["summary"]["episodes_without_admission_attempt"] == 1
    assert trigger_coverage["summary"]["attempt_coverage_rate"] == 0.75
    assert trigger_coverage["decision_eligible"] is False
    assert trigger_coverage["affects"] == "none"
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_context_deferred_admission_cohorts SET reason='changed' WHERE admission_id=?",
            (skipped_admission,),
        )
    store.close()


def test_token_context_onchain_admission_challenger_is_forward_registered_and_observable(
    tmp_path: Path,
):
    store = Store(tmp_path / "onchain-context-challenger.sqlite3")
    token = TokenCandidate(
        chain="solana", address="Q" * 32, name="Onchain challenger", symbol="OCC"
    )
    store.upsert_token(token)
    observed_at = utcnow()
    round_id = store.start_token_discovery_round(
        provider="pumpportal",
        surface="create",
        mode="stream_window",
        chain_scope="solana",
        started_at=observed_at,
    )
    store.add_token_discovery_exposure(
        round_id,
        token_id=token.token_id,
        chain=token.chain,
        role="create",
        first_local_discovery=True,
        new_token=True,
        observed_at=observed_at,
    )
    store.finish_token_discovery_round(
        round_id, status="completed", returned_count=1, completed_at=observed_at
    )
    trigger_transition_id = store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_trigger_evaluation",
        status="eligible",
        reason_code="onchain_momentum",
        evaluation_key="fixture:onchain-challenger",
        observed_at=observed_at,
        ingested_at=observed_at,
        source_table="token_context_trigger",
        metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
    )
    assert trigger_transition_id is not None
    trigger = {
        "kind": "onchain_momentum",
        "priority": 1,
        "transition_id": trigger_transition_id,
    }
    admission_id = store.add_token_context_admission_attempt(
        token.token_id,
        outcome="admitted",
        reason="admitted",
        trigger=trigger,
        snapshot_observed_at=observed_at,
        momentum_score=92,
        quota_day=observed_at.date().isoformat(),
        daily_call_limit=100,
        calls_used_before=0,
        daily_token_budget=1_000_000,
        tokens_used_before=0,
        token_reserve_per_call=1,
        evaluated_at=observed_at,
    )
    store.record_token_universe_funnel_transition(
        token.token_id,
        stage="context_admission",
        status="admitted",
        reason_code="admitted",
        evaluation_key=f"admission:{admission_id}",
        observed_at=observed_at,
        ingested_at=observed_at,
        source_table="token_context_admission_attempts",
        admission_id=admission_id,
        metadata={
            "trigger_kind": "onchain_momentum",
            "challenger_version": store.TOKEN_CONTEXT_ONCHAIN_ADMISSION_CHALLENGER_VERSION,
        },
    )
    assessment_id = store.add_token_context_assessment(
        token.token_id,
        trigger="onchain_momentum",
        status="no_context",
        snapshot_observed_at=observed_at,
        momentum_score=92,
        assessment={"investigation_trigger": {"kind": "onchain_momentum"}},
        assessed_at=observed_at,
    )
    store.record_token_universe_funnel_transition(
        token.token_id,
        stage="agent_result",
        status="no_context",
        reason_code="no_context",
        evaluation_key=f"assessment:{admission_id}",
        observed_at=observed_at,
        ingested_at=observed_at,
        source_table="token_context_assessments",
        admission_id=admission_id,
        agent_run_id="fixture-onchain-challenger",
        assessment_id=assessment_id,
    )
    summary = Store.token_context_onchain_admission_challenger_summary_from_connection(
        store.db
    )
    assert summary["status"] == "observed"
    assert summary["summary"] == {
        "onchain_trigger_transitions": 1,
        "onchain_trigger_tokens": 1,
        "selected_attempts": 1,
        "admitted": 1,
        "skipped": 0,
        "assessment_results": 1,
    }
    assert summary["result_statuses"] == [{"status": "no_context", "count": 1}]
    assert summary["decision_eligible"] is False and summary["affects"] == "none"
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE token_context_onchain_admission_challenger_registrations "
            "SET registered_at=registered_at"
        )
    store.close()


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


def test_provider_post_ambiguity_shadow_freezes_status_episode_and_checkpoint_sets(tmp_path: Path):
    store = Store(tmp_path / "provider-post-ambiguity.sqlite3")
    watch = [{"platform": "x", "handle": "ElonMusk", "priority": 5, "enabled": True}]
    registration = store.register_provider_post_ambiguity_shadow(watch)
    watch[0]["handle"] = "changed_after_registration"
    definition = json.loads(registration["definition_json"])
    assert definition["watch_roster"] == [{"handle": "elonmusk", "priority": 5}]
    assert definition["network_requests"] is False
    assert definition["decision_eligible"] is False and definition["affects"] == "none"

    published = utcnow() - timedelta(minutes=1)
    status_id = str((int(published.timestamp() * 1000) - 1_288_834_974_657) << 22)

    def link_token(address: str, url: str) -> int:
        token = TokenCandidate(chain="solana", address=address, name="Clone", symbol="CLONE")
        store.upsert_token(token, seen_at=published)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana", started_at=published,
        )
        exposure_id = store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain="solana", role="create",
            first_local_discovery=True, new_token=True, observed_at=published,
        )
        fingerprint, _ = store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "pumpportal",
                "discovery_surface": "launch_metadata",
                "role": "identity",
                "original_url": url,
                "normalized_url": url,
                "link_kind": "social_post",
                "platform": "x",
                "verification_status": "provider_metadata",
            },
            observed_at=published,
        )
        assert exposure_id is not None
        assert store.link_token_discovery_exposure_source_links(exposure_id, [fingerprint]) == 1
        return exposure_id

    first_address = str(Pubkey.new_unique())
    second_address = str(Pubkey.new_unique())
    link_token(first_address, f"https://x.com/elonmusk/status/{status_id}?s=20")
    episode = store.db.execute("SELECT * FROM provider_post_ambiguity_episodes").fetchone()
    assert episode is not None
    t0 = parse_time(episode["t0_at"])
    first_finalize = store.finalize_provider_post_ambiguity_checkpoints(now=t0)
    assert first_finalize["checkpoints_finalized"] == 1
    zero = store.db.execute(
        "SELECT * FROM provider_post_ambiguity_checkpoints WHERE offset_seconds=0"
    ).fetchone()
    assert zero["member_count"] == 1
    assert json.loads(zero["members_json"]) == [f"solana:{first_address}"]

    link_token(second_address, f"https://twitter.com/ElonMusk/status/{status_id}?s=46")
    assert store.db.execute("SELECT COUNT(*) FROM provider_post_ambiguity_episodes").fetchone()[0] == 1
    assert store.db.execute("SELECT COUNT(*) FROM provider_post_ambiguity_memberships").fetchone()[0] == 2
    assert store.finalize_provider_post_ambiguity_checkpoints(now=t0 + timedelta(seconds=31))[
        "checkpoints_finalized"
    ] == 1
    checkpoints = {
        int(row["offset_seconds"]): row
        for row in store.db.execute("SELECT * FROM provider_post_ambiguity_checkpoints")
    }
    assert checkpoints[0]["member_count"] == 1
    assert checkpoints[30]["member_count"] == 2
    assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in checkpoints.values())

    first_membership = store.db.execute(
        "SELECT * FROM provider_post_ambiguity_memberships WHERE address=?", (first_address,)
    ).fetchone()
    before = first_membership["candidate_recorded_at"]
    store.upsert_token_source_link(
        {
            "token_id": f"solana:{first_address}",
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": f"https://x.com/elonmusk/status/{status_id}?s=20",
            "normalized_url": f"https://x.com/elonmusk/status/{status_id}?s=20",
            "link_kind": "social_post",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=published - timedelta(minutes=30),
    )
    assert store.db.execute(
        "SELECT candidate_recorded_at FROM provider_post_ambiguity_memberships WHERE id=?",
        (int(first_membership["id"]),),
    ).fetchone()[0] == before
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE provider_post_ambiguity_checkpoints SET member_count=99 WHERE id=?",
            (int(zero["id"]),),
        )
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    store.close()


def test_provider_post_ambiguity_shadow_never_backfills_pre_registration_links(tmp_path: Path):
    store = Store(tmp_path / "provider-post-ambiguity-boundary.sqlite3")
    published = utcnow() - timedelta(minutes=1)
    status_id = str((int(published.timestamp() * 1000) - 1_288_834_974_657) << 22)
    token = TokenCandidate(
        chain="solana", address=str(Pubkey.new_unique()), name="Before", symbol="BEFORE"
    )
    store.upsert_token(token, seen_at=published)
    round_id = store.start_token_discovery_round(
        provider="pumpportal", surface="create", mode="stream_window",
        chain_scope="solana", started_at=published,
    )
    exposure_id = store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain="solana", observed_at=published,
    )
    link = {
        "token_id": token.token_id,
        "provider": "pumpportal",
        "discovery_surface": "launch_metadata",
        "role": "identity",
        "original_url": f"https://x.com/elonmusk/status/{status_id}",
        "normalized_url": f"https://x.com/elonmusk/status/{status_id}",
        "link_kind": "social_post",
        "platform": "x",
        "verification_status": "provider_metadata",
    }
    fingerprint, _ = store.upsert_token_source_link(link, observed_at=published)
    assert exposure_id is not None
    assert store.link_token_discovery_exposure_source_links(exposure_id, [fingerprint]) == 1
    registration = store.register_provider_post_ambiguity_shadow(
        [{"platform": "x", "handle": "elonmusk", "priority": 5}]
    )
    assert int(registration["activation_exposure_link_id"]) == 1
    assert store.db.execute("SELECT COUNT(*) FROM provider_post_ambiguity_admissions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM provider_post_ambiguity_episodes").fetchone()[0] == 0
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


def test_dexscreener_rejects_concatenated_catalogue_metadata():
    pair = {
        "chainId": "robinhood",
        "baseToken": {
            "address": "0xAE2Df3c1749daEE721c1BFcbbFDde5D61ae7cb99",
            "name": "asset " * 100,
            "symbol": "AAA" * 100,
        },
    }
    assert DexScreenerClient._candidate(pair) is None
    token = TokenCandidate(
        chain="robinhood",
        address=pair["baseToken"]["address"],
        name=pair["baseToken"]["name"],
        symbol=pair["baseToken"]["symbol"],
        source="dexscreener",
    )
    assert CandidateEvaluator._match_score(
        ["Elon Musk"], "Elon Musk posted about AI", token, set()
    ) == 0.0


def test_dexscreener_batch_quote_preserves_caller_evm_address_casing():
    requested_address = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"

    class Response:
        def json(self):
            return [{
                "chainId": "bsc", "dexId": "pancakeswap", "pairAddress": "0xpair",
                "baseToken": {
                    "address": requested_address.lower(), "name": "Case", "symbol": "CASE",
                },
                "quoteToken": {"address": "0xquote"}, "priceUsd": "0.01",
                "liquidity": {"usd": 50_000}, "volume": {"m5": 1_000},
                "txns": {"m5": {"buys": 12, "sells": 3}},
            }]

    class Http:
        async def get(self, url, **kwargs):
            return Response()

    result = asyncio.run(
        DexScreenerClient(Http()).batch_quote("bsc", [requested_address])
    )
    token_id = f"bsc:{requested_address}"
    assert list(result) == [token_id]
    assert result[token_id][0].address == requested_address
    assert result[token_id][1].address == requested_address


def test_jupiter_quote_is_normalized_and_never_exposes_transaction():
    class Response:
        def json(self):
            return {
                "inputMint": "SOL", "inAmount": "100", "outputMint": "TOKEN",
                "outAmount": "90", "otherAmountThreshold": "89", "swapMode": "ExactIn",
                "slippageBps": 100, "priceImpactPct": "0.1",
                "platformFee": {"amount": "0", "feeBps": 0}, "contextSlot": 7,
                "timeTaken": 0.01, "requestId": "secret-id",
                "transaction": "",
                "routePlan": [{"percent": 100, "swapInfo": {
                    "ammKey": "amm", "label": "AMM", "inputMint": "SOL",
                    "outputMint": "TOKEN", "inAmount": "100", "outAmount": "90",
                    "feeAmount": "1", "feeMint": "SOL",
                }}],
            }

    class Http:
        async def get(self, url, **kwargs):
            assert url == JupiterQuoteClient.BASE
            assert kwargs["params"] == {
                "inputMint": "SOL", "outputMint": "TOKEN", "amount": 100,
                "slippageBps": 100,
            }
            return Response()

    result = asyncio.run(JupiterQuoteClient(Http()).quote(" SOL ", "TOKEN", 100, slippage_bps=100))
    assert result["out_amount"] == "90"
    assert result["price_impact_bps"] == pytest.approx(1000.0)
    assert result["price_impact_source"] == "priceImpactPct_decimal_ratio"
    assert result["route_plan"][0]["amm_key"] == "amm"
    assert "transaction" not in result and "requestId" not in result


def test_evm_uniswap_v3_quote_uses_mixed_fee_fixed_block_and_two_sided_slippage():
    target = "0x" + "11" * 20
    network = EvmUniswapV3QuoteClient.NETWORKS["bsc"]
    stable = str(network["accounting_token"]).lower()
    wrapped = str(network["wrapped_native"]).lower()
    calls: list[tuple[str, list]] = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): return None
        def json(self): return self.payload

    class Client:
        async def post(self, _url, *, json):
            method, params = json["method"], json["params"]
            calls.append((method, params))
            result = None
            if method == "eth_chainId": result = hex(int(network["chain_id"]))
            elif method == "eth_blockNumber": result = "0x64"
            elif method == "eth_getBlockByNumber":
                result = {"hash": "0x" + "ab" * 32, "timestamp": "0x65"}
            elif method == "eth_getCode": result = "0x6000"
            elif method == "eth_call":
                data = params[0]["data"][2:]
                if data.startswith(EvmUniswapV3QuoteClient.GET_POOL_SELECTOR):
                    token_a = "0x" + data[32:72]
                    token_b = "0x" + data[96:136]
                    fee = int(data[136:200], 16)
                    pair = {token_a.lower(), token_b.lower()}
                    exists = (
                        pair == {stable, wrapped} and fee == 500
                    ) or (
                        pair == {wrapped, target} and fee == 3000
                    )
                    result = "0x" + ("0" * 24 + "22" * 20 if exists else "0" * 64)
                else:
                    path_length = int(data[136:200], 16)
                    path = data[200:200 + path_length * 2]
                    first_token = "0x" + path[:40]
                    amount_out = 1000 if first_token.lower() == stable else 900
                    result = "0x" + "".join(
                        EvmUniswapV3QuoteClient._word(value)
                        for value in (amount_out, 0, 0, 80_000)
                    )
            return Response({"jsonrpc": "2.0", "id": json["id"], "result": result})

    class Http:
        min_host_interval = 0
        client = Client()

    amount = 35 * 10**18
    result = asyncio.run(
        EvmUniswapV3QuoteClient(Http()).quote_round_trip(
            "bsc", target, amount, slippage_bps=400
        )
    )
    assert result["status"] == "quoted"
    assert [leg["fee_tier"] for leg in result["buy_path"]] == [500, 3000]
    assert [leg["fee_tier"] for leg in result["sell_path"]] == [3000, 500]
    assert result["buy_minimum_output_raw"] == "960"
    assert result["sell_minimum_output_raw"] == "864"
    assert result["immediate_round_trip_stable_ratio"] == pytest.approx(864 / amount)
    assert result["fee_completeness"] == "quote_only_no_full_transaction_network_fee"
    assert result["execution_scope"] == "pool_math_quote_only"
    assert result["decision_eligible"] is False and result["affects"] == "none"
    assert all(
        params[-1] == "0x64"
        for method, params in calls
        if method in {"eth_call", "eth_getCode"}
    )


def test_evm_uniswap_v3_quote_does_not_hide_transport_failure_as_no_route():
    target = "0x" + "11" * 20
    network = EvmUniswapV3QuoteClient.NETWORKS["base"]

    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): return None
        def json(self): return self.payload

    class Client:
        async def post(self, url, *, json):
            method, params = json["method"], json["params"]
            if method == "eth_chainId": result = hex(int(network["chain_id"]))
            elif method == "eth_blockNumber": result = "0x64"
            elif method == "eth_getBlockByNumber":
                result = {"hash": "0x" + "ab" * 32, "timestamp": "0x65"}
            elif method == "eth_getCode": result = "0x6000"
            elif method == "eth_call" and params[0]["data"][2:].startswith(
                EvmUniswapV3QuoteClient.GET_POOL_SELECTOR
            ):
                result = "0x" + "0" * 24 + "22" * 20
            else:
                raise httpx.ConnectError("rpc down", request=httpx.Request("POST", url))
            return Response({"jsonrpc": "2.0", "id": json["id"], "result": result})

    class Http:
        min_host_interval = 0
        client = Client()

    with pytest.raises(EvmRouteQuoteError, match="eth_call failed"):
        asyncio.run(
            EvmUniswapV3QuoteClient(Http()).quote_round_trip(
                "base", target, 35_000_000
            )
        )


def test_evm_route_store_is_forward_only_append_only_and_strategy_neutral(tmp_path: Path):
    store = Store(tmp_path / "evm-route.sqlite3", initial_cash_usd=1000)
    store.register_onchain_only_shadow(
        momentum_threshold=80, paper_stake_usd=35, min_liquidity_usd=12_000,
        max_liquidity_impact_pct=0.0025, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
        max_quote_delay_seconds=45,
    )

    def enroll(address: str, observed_at: datetime, key: str) -> int:
        token = TokenCandidate(
            chain="bsc", address=address, name=f"Route {key}", source="fixture"
        )
        store.upsert_token(token, seen_at=observed_at)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="fixture", mode="poll", chain_scope="bsc",
            started_at=observed_at,
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain="bsc", role="new_token",
            first_local_discovery=True, new_token=True, observed_at=observed_at,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        snapshot_id = store.add_snapshot(TokenSnapshot(
            "bsc", address, 1.0, 20_000, 100_000, 30_000, 30, 10,
            observed_at=observed_at, ingested_at=observed_at,
            provider="dexscreener",
        ))
        transition_id = store.record_token_universe_funnel_transition(
            token.token_id,
            stage="context_trigger_evaluation", status="eligible",
            reason_code="onchain_momentum", evaluation_key=f"evm-route:{key}",
            observed_at=observed_at, ingested_at=observed_at,
            source_table="token_context_trigger", snapshot_id=snapshot_id,
            metadata={"trigger_kind": "onchain_momentum", "momentum_score": 90.0},
        )
        shadow_id = store.enroll_onchain_only_shadow(transition_id)
        assert shadow_id is not None
        return int(shadow_id)

    now = utcnow()
    legacy_id = enroll("0x" + "aa" * 20, now, "legacy")
    registration = store.register_onchain_only_evm_route_quote(
        EvmUniswapV3QuoteClient.public_network_definitions(),
        paper_stake_usd=35, slippage_bps=400,
        max_queue_delay_seconds=30, max_total_delay_seconds=45,
    )
    assert int(registration["activation_shadow_cohort_id"]) == legacy_id
    future_id = enroll("0x" + "bb" * 20, utcnow(), "future")
    future = store.db.execute(
        "SELECT * FROM onchain_only_shadow_cohorts WHERE id=?", (future_id,)
    ).fetchone()
    anchor = parse_time(future["trigger_recorded_at"])
    tasks = store.due_onchain_only_evm_route_quotes(now=anchor)
    assert [item["shadow_cohort_id"] for item in tasks] == [future_id]
    task = tasks[0]
    assert task["input_amount_raw"] == str(35 * 10**18)
    decisions_before = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    trades_before = store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    attempt_id = store.start_onchain_only_evm_route_quote_attempt(
        task, requested_at=anchor + timedelta(seconds=1)
    )
    assert attempt_id is not None
    assert store.due_onchain_only_evm_route_quotes(now=anchor + timedelta(seconds=2))[0][
        "preflight_reason"
    ] == "request_evidence_missing"
    result_id = store.record_onchain_only_evm_route_quote(
        task,
        status="quoted",
        attempt_id=attempt_id,
        requested_at=anchor + timedelta(seconds=1),
        completed_at=anchor + timedelta(seconds=2),
        result={
            "chain_id": 56,
            "block_number": 100,
            "block_hash": "0x" + "ab" * 32,
            "block_timestamp": iso(anchor + timedelta(seconds=1)),
            "buy_output_raw": "1000",
            "buy_minimum_output_raw": "960",
            "sell_output_raw": str(34 * 10**18),
            "sell_minimum_output_raw": str(3264 * 10**16),
            "buy_quoter_gas_estimate": 80_000,
            "sell_quoter_gas_estimate": 75_000,
            "buy_path": [{"fee_tier": 3000}],
            "sell_path": [{"fee_tier": 3000}],
            "immediate_round_trip_stable_ratio": 0.9325714285714286,
        },
    )
    row = store.db.execute(
        "SELECT * FROM onchain_only_evm_route_quote_results WHERE id=?", (result_id,)
    ).fetchone()
    assert row["quote_terminal_status"] == "quoted"
    assert row["fee_completeness"] == "quote_only_no_full_transaction_network_fee"
    assert row["economic_status"] == "cost_unknown"
    assert row["decision_eligible"] == 0 and row["affects"] == "none"
    summary = Store.onchain_only_evm_route_quote_summary_from_connection(store.db)
    assert summary["summary"]["eligible_cohorts"] == 1
    assert summary["summary"]["quoted"] == 1
    assert summary["execution"] is False and summary["pnl"] is False
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == decisions_before
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == trades_before
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE onchain_only_evm_route_quote_results SET economic_status='known' WHERE id=?",
            (result_id,),
        )
    store.close()


def test_jupiter_v2_price_impact_uses_percentage_points_and_preserves_zero():
    class Response:
        def __init__(self, impact): self.impact = impact
        def json(self):
            return {
                "inputMint": "SOL", "inAmount": "100", "outputMint": "TOKEN",
                "outAmount": "90", "otherAmountThreshold": "89",
                "swapMode": "ExactIn", "slippageBps": 50,
                "priceImpact": self.impact,
                "priceImpactPct": "0.9", "routePlan": [{"swapInfo": {}}],
            }

    class Http:
        def __init__(self, impact): self.impact = impact
        async def get(self, *_args, **_kwargs): return Response(self.impact)

    negative = asyncio.run(JupiterQuoteClient(Http("-0.1")).quote("SOL", "TOKEN", 100))
    assert negative["price_impact_bps"] == pytest.approx(-10.0)
    assert negative["price_impact_source"] == "priceImpact_percentage_points"
    zero = asyncio.run(JupiterQuoteClient(Http("0")).quote("SOL", "TOKEN", 100))
    assert float(zero["price_impact_pct"]) == pytest.approx(0.0)
    assert zero["price_impact_bps"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "response_body",
    [b"Could not find any route", b'{"error":"Failed to get quotes"}'],
)
def test_jupiter_quote_rejects_transaction_and_maps_no_route(response_body):
    class Response:
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload

    class Http:
        def __init__(self, response): self.response = response
        async def get(self, url, **kwargs): return self.response

    with pytest.raises(JupiterQuoteProtocolError, match="contains a transaction"):
        asyncio.run(JupiterQuoteClient(Http(Response({"transaction": "signed"}))).quote("SOL", "TOKEN", 1))

    request = httpx.Request("GET", JupiterQuoteClient.BASE)
    response = httpx.Response(400, request=request, content=response_body)
    with pytest.raises(JupiterNoRouteError):
        class ErrorHttp:
            async def get(self, url, **kwargs):
                    raise httpx.HTTPStatusError("Could not find any route", request=request, response=response)
        asyncio.run(JupiterQuoteClient(ErrorHttp()).quote("SOL", "TOKEN", 1))


def test_jupiter_quote_rejects_mismatched_response():
    class Response:
        def raise_for_status(self): return None
        def json(self):
            return {
                "inputMint": "OTHER", "outputMint": "TOKEN", "inAmount": "1",
                "outAmount": "2", "routePlan": [{"swapInfo": {}}], "transaction": None,
            }

    class Http:
        async def get(self, *_args, **_kwargs): return Response()

    with pytest.raises(JupiterQuoteError, match="requested route"):
        asyncio.run(JupiterQuoteClient(Http()).quote("SOL", "TOKEN", 1))


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


def test_social_account_attribution_does_not_merge_unrelated_posts(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.28)
    common = {
        "source": "x:CoinbaseMarkets",
        "source_kind": "social",
        "author": "CoinbaseMarkets",
        "availability_proof": "local_receive",
        "raw": {
            "source_entity_id": "coinbase",
            "browser": {"author": "CoinbaseMarkets", "source_entity_id": "coinbase"},
        },
    }
    launch, _, _ = engine.ingest(
        Observation(
            **common,
            title=(
                "Coinbase Markets @CoinbaseMarkets · 12m cbHYPE and cbZEC are now live "
                "on Base and backed by Coinbase custody"
            ),
            source_item_id="coinbase-launch",
        )
    )
    contract, created, _ = engine.ingest(
        Observation(
            **common,
            title=(
                "Coinbase Markets @CoinbaseMarkets · 12m Contract addresses for cbHYPE "
                "and cbZEC on Base"
            ),
            source_item_id="coinbase-contract",
        )
    )
    oil, oil_created, _ = engine.ingest(
        Observation(
            **common,
            title=(
                "Coinbase Markets @CoinbaseMarkets · 20m Brent crude oil prices are "
                "nearing 95 dollars per barrel"
            ),
            source_item_id="coinbase-oil",
        )
    )
    assert launch == contract and created is False
    assert oil != launch and oil_created is True
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
    unlimited_policy = PaperPolicy({**policy.config, "max_open_positions": 0})
    assert unlimited_policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=10_000,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=0,
    ) >= 3
    assert policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=0,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=100,
    ) == 0
    unknown_liquidity = TokenSnapshot(
        chain="solana", address="B" * 32, price_usd=0.01,
        liquidity_usd=None, market_cap_usd=100000,
        volume_5m_usd=50000, buys_5m=50, sells_5m=20,
    )
    assert policy.size(
        cash_usd=1000, equity_usd=1000, open_count=0,
        snapshot=unknown_liquidity, score=85, daily_exposure_usd=0,
    ) == 0
    assert policy.size(
        cash_usd=1000, equity_usd=1000, open_count=0,
        snapshot=unknown_liquidity, score=85, daily_exposure_usd=0,
        executable_capacity_usd=35,
    ) >= 3
    fixed_policy = PaperPolicy({
        **policy.config,
        "fixed_position_usd": 20,
        "fixed_fee_usd_each_side": 0.4,
    })
    assert fixed_policy.size(
        cash_usd=1000, equity_usd=1000, open_count=0,
        snapshot=snapshot, score=58, daily_exposure_usd=0,
    ) == pytest.approx(20)
    assert fixed_policy.size(
        cash_usd=20.39, equity_usd=20.39, open_count=0,
        snapshot=snapshot, score=100, daily_exposure_usd=0,
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


def test_paper_fixed_fee_is_charged_per_fill(tmp_path: Path):
    store = Store(tmp_path / "paper-fixed-fee.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="F" * 32, name="Fixed Fee")
    store.upsert_token(token)
    position = store.paper_buy(
        event_id=1, token=token, price=1.04, quote_price=1.0,
        gross_usd=20, fee_bps=60, fixed_fee_usd=0.4, reason="fixed-cost-v1",
    )
    assert position.cost_usd == pytest.approx(20.4)
    first = store.paper_sell(
        token.token_id, price=0.96, quote_price=1.0, fraction=0.5,
        fee_bps=60, fixed_fee_usd=0.4, reason="fixed-cost-partial",
    )
    second = store.paper_sell(
        token.token_id, price=0.96, quote_price=1.0, fraction=1.0,
        fee_bps=60, fixed_fee_usd=0.4, reason="fixed-cost-close",
    )
    assert first["fee_usd"] == pytest.approx(0.4)
    assert second["fee_usd"] == pytest.approx(0.4)
    assert [row["fee_usd"] for row in store.trades(10)] == pytest.approx([0.4, 0.4, 0.4])
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
    assert "priorityPostRequests" in background
    assert "memetrader-priority-posts" in background
    assert "first_observed_at" in background
    assert "15 * 60 * 1000" in background
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
    assert '"tabs"' in manifest.lower()


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


def test_information_first_active_outcome_sampler_is_forward_and_append_only(tmp_path: Path):
    store = Store(tmp_path / "information-first-active.sqlite3")
    now = utcnow()
    event_id = store.create_event("Active outcome", ["Active"], 70, now - timedelta(minutes=3))
    lead = Observation(
        source="active-fixture", source_kind="news", title="Active outcome", text="",
        observed_at=now - timedelta(minutes=2), ingested_at=now - timedelta(minutes=2),
        published_at=now - timedelta(minutes=2), role="feature", capture_phase="live",
    )
    lead_id, _ = store.add_observation(lead)
    store.link_event_observation(event_id, lead_id)
    token = TokenCandidate(chain="solana", address="A" * 32, name="Active Outcome")
    store.upsert_token(token, seen_at=now - timedelta(minutes=2))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=token.address, price_usd=1.0, liquidity_usd=20_000,
        market_cap_usd=100_000, volume_5m_usd=2_000, buys_5m=8, sells_5m=4,
        observed_at=now - timedelta(minutes=1), ingested_at=now - timedelta(minutes=1),
        provider="fixture",
    ))
    decision_id = store.add_decision(CandidateDecision(
        event_id, token.token_id, "WAIT", 65, 70, 3, [], created_at=now,
    ))
    cohort_id = store.create_information_first_shadow_cohort(
        event_id, token.token_id, decision_id=decision_id, accepted_observation_ids=[lead_id],
        captured_at=now, relation_available_at=now,
    )
    targets = list(store.db.execute(
        "SELECT * FROM information_first_active_outcome_targets WHERE shadow_cohort_id=? "
        "ORDER BY horizon_minutes",
        (cohort_id,),
    ))
    assert [row["horizon_minutes"] for row in targets] == [15, 60, 240]
    definition = json.loads(store.db.execute(
        "SELECT definition_json FROM information_first_active_outcome_registrations"
    ).fetchone()[0])
    assert definition["writes_generic_token_snapshots"] is False
    assert definition["uses_jupiter"] is False and definition["uses_agent"] is False
    assert max(Store.INFORMATION_FIRST_ACTIVE_OUTCOME_RETRY_SECONDS) < (
        Store.INFORMATION_FIRST_ACTIVE_OUTCOME_DEADLINE_SECONDS
    )

    target_at = parse_time(targets[0]["target_at"])
    due = store.due_information_first_active_outcome_targets(now=target_at, limit=4)
    assert len(due) == 1 and due[0]["retry_index"] == 0
    attempt_id = store.start_information_first_active_outcome_attempt(
        int(due[0]["id"]), retry_index=0, scheduled_at=due[0]["scheduled_at"],
        requested_at=target_at,
    )
    snapshot_count = store.db.execute("SELECT COUNT(*) FROM token_snapshots").fetchone()[0]
    result_id = store.finish_information_first_active_outcome_attempt(
        attempt_id,
        status="observed_mark",
        reason_code="fresh_dexscreener_mark",
        response_received_at=target_at + timedelta(seconds=2),
        snapshot=TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.5, liquidity_usd=25_000,
            market_cap_usd=150_000, volume_5m_usd=3_000, buys_5m=12, sells_5m=5,
            observed_at=target_at + timedelta(seconds=2), provider="dexscreener",
        ),
    )
    terminal = store.db.execute(
        "SELECT * FROM information_first_active_outcome_terminals WHERE target_id=?",
        (int(targets[0]["id"]),),
    ).fetchone()
    assert terminal["status"] == "observed_mark" and terminal["winning_result_id"] == result_id
    assert terminal["price_usd"] == pytest.approx(1.5)
    assert store.db.execute("SELECT COUNT(*) FROM token_snapshots").fetchone()[0] == snapshot_count

    finalized = store.finalize_information_first_active_outcome_deadlines(
        now=parse_time(targets[1]["deadline_at"])
    )
    assert finalized["targets_finalized"] == 1
    missed = store.db.execute(
        "SELECT status FROM information_first_active_outcome_terminals WHERE target_id=?",
        (int(targets[1]["id"]),),
    ).fetchone()
    assert missed["status"] == "scheduler_missed_deadline"
    late_target = targets[2]
    late_attempt_id = store.start_information_first_active_outcome_attempt(
        int(late_target["id"]), retry_index=0, scheduled_at=late_target["target_at"],
        requested_at=late_target["target_at"],
    )
    store.finalize_information_first_active_outcome_deadlines(
        now=parse_time(late_target["deadline_at"])
    )
    late_result_id = store.finish_information_first_active_outcome_attempt(
        late_attempt_id,
        status="observed_mark",
        reason_code="provider_completed_late",
        response_received_at=parse_time(late_target["deadline_at"]) + timedelta(seconds=1),
        snapshot=TokenSnapshot(
            chain="solana", address=token.address, price_usd=2.0, liquidity_usd=30_000,
            market_cap_usd=200_000, volume_5m_usd=4_000, buys_5m=14, sells_5m=6,
            observed_at=parse_time(late_target["deadline_at"]) + timedelta(seconds=1),
            provider="dexscreener",
        ),
    )
    late_result = store.db.execute(
        "SELECT status FROM information_first_active_outcome_results WHERE id=?",
        (late_result_id,),
    ).fetchone()
    late_terminal = store.db.execute(
        "SELECT status,winning_result_id FROM information_first_active_outcome_terminals WHERE target_id=?",
        (int(late_target["id"]),),
    ).fetchone()
    assert late_result["status"] == "late_response"
    assert late_terminal["status"] == "terminal_missing"
    assert late_terminal["winning_result_id"] is None
    with pytest.raises(sqlite3.IntegrityError):
        with store.db:
            store.db.execute(
                "UPDATE information_first_active_outcome_terminals SET status='changed' WHERE id=?",
                (int(terminal["id"]),),
            )
    store.close()


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


def _record_kol_attention_point(
    store: Store, event_id: int, observation_id: int, attention: float,
) -> None:
    with store._lock, store.db:
        assert store._record_event_attention_point_locked(
            event_id, observation_id, attention,
        )


def _valid_solana_address(seed: int) -> str:
    return str(Pubkey(bytes([seed]) * 32))


def test_kol_token_addressability_keeps_no_seed_and_freezes_exact_ca_without_production_writes(tmp_path: Path):
    store = Store(tmp_path / "kol-addressability.sqlite3")
    now = datetime.now(timezone.utc) - timedelta(seconds=2)
    account = {
        "platform": "x", "handle": "@elonmusk", "entity_id": "elon_musk", "priority": 5,
    }
    address = _valid_solana_address(1)
    event_id = store.create_event("Fresh exact identifier", ["fresh"], 25, now)
    observation = Observation(
        source="browser:x:elonmusk", source_kind="social",
        title="Fresh exact identifier", text=f"A new public post names {address}",
        url="https://x.com/elonmusk/status/12345", author="@elonmusk",
        published_at=now - timedelta(minutes=1), observed_at=now,
        ingested_at=now, availability_proof="local_receive", capture_phase="live", role="feature",
    )
    observation_id, _ = store.add_observation(observation)
    store.link_event_observation(event_id, observation_id)
    _record_kol_attention_point(store, event_id, observation_id, 25)
    store.update_event(
        event_id, title="Fresh exact identifier", aliases=["fresh"],
        attention=99, seen_at=now,
    )
    token = TokenCandidate(chain="solana", address=address, name="Fresh", symbol="FRSH")
    store.upsert_token(token, seen_at=now - timedelta(seconds=30))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=address, price_usd=0.001, liquidity_usd=30_000,
        market_cap_usd=100_000, volume_5m_usd=5_000, buys_5m=4, sells_5m=2,
        observed_at=now - timedelta(seconds=20), ingested_at=now - timedelta(seconds=20),
        provider="dexscreener",
        raw={"pair": {"chainId": "solana", "dexId": "pumpfun", "pairAddress": "pair-1"}},
    ))
    production_before = {
        table: store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("token_universe_funnel_transitions", "decisions", "positions", "trades")
    }

    captured_at = datetime.now(timezone.utc)
    cohort_id = store.create_kol_token_addressability_cohort(
        event_id, observation_id, account=account,
        identifiers={"solana": [address], "evm": []}, recorded_at=captured_at,
    )

    assert cohort_id is not None
    assert store.create_kol_token_addressability_cohort(
        event_id, observation_id, account=account,
        identifiers={"solana": [address]}, recorded_at=captured_at,
    ) == cohort_id
    cohort = store.db.execute(
        "SELECT * FROM kol_token_addressability_cohorts WHERE id=?", (cohort_id,)
    ).fetchone()
    assert cohort["seed_status"] == "explicit_identifier_at_signal"
    assert cohort["event_attention"] == 25
    assert cohort["attention_point_id"] > 0
    assert cohort["attention_definition_version"] == Store.EVENT_ATTENTION_TRAJECTORY_VERSION
    assert cohort["attention_coverage_mode"] == "local_new_observation_arrivals_only"
    assert parse_time(cohort["signal_available_at"]) >= parse_time(
        cohort["attention_recorded_at"]
    )
    assert json.loads(cohort["frozen_queries_json"]) == [
        {"chain": "solana", "kind": "exact_ca", "value": address}
    ]
    milestones = list(store.db.execute(
        "SELECT milestone,status,identifier,token_id FROM kol_token_addressability_milestones "
        "WHERE cohort_id=? ORDER BY id", (cohort_id,),
    ))
    assert [(row["milestone"], row["status"]) for row in milestones] == [
        ("signal", "observed"),
        ("explicit_identifier", "observed"),
        ("local_token_discovery", "observed"),
        ("dex_pair_available", "observed"),
    ]
    assert milestones[-1]["token_id"] == token.token_id

    no_seed_event = store.create_event("Fresh no seed", ["fresh"], 20, now)
    no_seed_observation = Observation(
        source="browser:x:elonmusk", source_kind="social", title="Fresh no seed",
        text="A new public post with no token identifier.", author="@elonmusk",
        published_at=now - timedelta(minutes=1), observed_at=now,
        ingested_at=now, availability_proof="local_receive", capture_phase="live", role="feature",
    )
    no_seed_id, _ = store.add_observation(no_seed_observation)
    store.link_event_observation(no_seed_event, no_seed_id)
    _record_kol_attention_point(store, no_seed_event, no_seed_id, 20)
    no_seed_cohort_id = store.create_kol_token_addressability_cohort(
        no_seed_event, no_seed_id, account=account, identifiers={}, recorded_at=captured_at,
    )
    no_seed = store.db.execute(
        "SELECT * FROM kol_token_addressability_cohorts WHERE id=?", (no_seed_cohort_id,)
    ).fetchone()
    assert no_seed["seed_status"] == "no_seed_at_signal"
    assert store.db.execute(
        "SELECT status FROM kol_token_addressability_milestones "
        "WHERE cohort_id=? AND milestone='explicit_identifier'", (no_seed_cohort_id,),
    ).fetchone()["status"] == "missing_at_signal"
    assert {
        table: store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in production_before
    } == production_before
    with pytest.raises(sqlite3.IntegrityError):
        with store.db:
            store.db.execute(
                "UPDATE kol_token_addressability_cohorts SET seed_status='no_seed_at_signal' WHERE id=?",
                (cohort_id,),
            )
    store.close()


def test_kol_token_addressability_route_v2_binds_v3_and_records_exact_route(
    tmp_path: Path,
):
    store = Store(tmp_path / "kol-addressability-route.sqlite3")
    signal = datetime.now(timezone.utc) - timedelta(seconds=2)
    account = {
        "platform": "x", "handle": "@elonmusk", "entity_id": "elon_musk", "priority": 5,
    }
    address = _valid_solana_address(2)
    event_id = store.create_event("Fresh route episode", ["fresh route"], 25, signal)
    lead = Observation(
        source="browser:x:elonmusk", source_kind="social", title="Fresh route episode",
        text=f"Exact address {address}", url="https://x.com/elonmusk/status/67890",
        author="@elonmusk", published_at=signal - timedelta(minutes=1),
        observed_at=signal, ingested_at=signal, availability_proof="local_receive",
        capture_phase="live", role="feature",
    )
    lead_id, _ = store.add_observation(lead)
    store.link_event_observation(event_id, lead_id)
    _record_kol_attention_point(store, event_id, lead_id, 25)
    token = TokenCandidate(chain="solana", address=address, name="Route", symbol="RTE")
    store.upsert_token(token, seen_at=signal + timedelta(seconds=5))
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=address, price_usd=0.001, liquidity_usd=40_000,
        market_cap_usd=120_000, volume_5m_usd=6_000, buys_5m=8, sells_5m=3,
        observed_at=signal + timedelta(seconds=1),
        ingested_at=signal + timedelta(seconds=1), provider="dexscreener",
        raw={"pair": {"chainId": "solana", "dexId": "pumpfun", "pairAddress": "PAIR-ROUTE"}},
    ))
    captured_at = datetime.now(timezone.utc)
    cohort_id = store.create_kol_token_addressability_cohort(
        event_id, lead_id, account=account, identifiers={"solana": [address]},
        recorded_at=captured_at,
    )
    assert cohort_id is not None
    confirmation = Observation(
        source="independent-news", source_kind="news", title="Independent exact report",
        text=f"Independent reporting confirms {address}", url="https://example.com/report",
        published_at=signal + timedelta(minutes=1),
        observed_at=signal + timedelta(minutes=2),
        ingested_at=signal + timedelta(minutes=2), availability_proof="local_poll",
        capture_phase="live", role="confirmation",
    )
    confirmation_id, _ = store.add_observation(confirmation)
    store.link_event_observation(event_id, confirmation_id)
    same_origin = Observation(
        source="browser:x:elonmusk", source_kind="social", title="Same-origin repeat",
        text=f"Same account repeats {address}", author="@elonmusk",
        published_at=signal + timedelta(minutes=1),
        observed_at=signal + timedelta(minutes=1),
        ingested_at=signal + timedelta(minutes=1), availability_proof="local_receive",
        capture_phase="live", role="confirmation",
    )
    same_origin_id, _ = store.add_observation(same_origin)
    store.link_event_observation(event_id, same_origin_id)
    production_before = {
        table: store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "tokens", "token_snapshots", "event_observations",
            "token_universe_funnel_transitions", "decisions", "positions", "trades",
        )
    }

    refreshed = store.refresh_kol_token_addressability_evidence(
        now=signal + timedelta(minutes=3)
    )
    assert refreshed["confirmation"] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM kol_token_addressability_confirmation_results "
        "WHERE cohort_id=?", (cohort_id,),
    ).fetchone()[0] == 1
    due = store.due_kol_token_addressability_routes(
        now=signal + timedelta(minutes=3, seconds=2)
    )
    assert len(due) == 1
    task = due[0]
    attempt_id = store.start_kol_token_addressability_route_attempt(
        task, requested_at=signal + timedelta(minutes=3, seconds=2)
    )
    assert attempt_id is not None
    result_id = store.record_kol_token_addressability_route_result(
        task, attempt_id=attempt_id, status="quoted",
        evaluated_at=signal + timedelta(minutes=3, seconds=3),
        completed_at=signal + timedelta(minutes=3, seconds=3),
        result={
            "input_mint": Store.JUPITER_USDC_MINT,
            "output_mint": address,
            "in_amount": "35000000",
            "slippage_bps": 400,
            "output_amount_raw": "1000",
            "other_amount_threshold": "960",
            "router": "jupiter",
            "route_plan": [{
                "percent": 100, "amm_key": "PAIR-ROUTE",
                "input_mint": Store.JUPITER_USDC_MINT,
                "output_mint": address,
            }],
        },
    )
    assert result_id is not None
    route = store.db.execute(
        "SELECT * FROM kol_token_addressability_route_results WHERE id=?", (result_id,)
    ).fetchone()
    assert route["terminal_status_v2"] == "route_quoted_timely"
    assert route["surface_relation"] == "single_hop_exact"
    assert {
        table: store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in production_before
    } == production_before
    assert Store.kol_token_addressability_summary_from_connection(store.db)[
        "route_status"
    ] == "observed"
    store.close()


def test_kol_token_addressability_route_v2_records_missing_pair_terminal(
    tmp_path: Path,
):
    store = Store(tmp_path / "kol-addressability-missing.sqlite3")
    signal = datetime.now(timezone.utc) - timedelta(seconds=2)
    account = {
        "platform": "x", "handle": "@cz_binance", "entity_id": "cz", "priority": 5,
    }
    address = _valid_solana_address(3)
    event_id = store.create_event("Missing pair episode", ["missing pair"], 20, signal)
    lead = Observation(
        source="browser:x:cz_binance", source_kind="social", title="Missing pair episode",
        text=f"Exact address {address}", author="@cz_binance",
        published_at=signal - timedelta(minutes=1), observed_at=signal, ingested_at=signal,
        availability_proof="local_receive", capture_phase="live", role="feature",
    )
    lead_id, _ = store.add_observation(lead)
    store.link_event_observation(event_id, lead_id)
    _record_kol_attention_point(store, event_id, lead_id, 20)
    cohort_id = store.create_kol_token_addressability_cohort(
        event_id, lead_id, account=account, identifiers={"solana": [address]},
        recorded_at=datetime.now(timezone.utc),
    )
    late = Observation(
        source="late-independent", source_kind="news", title="Late exact report",
        text=f"Late report names {address}", url="https://late.example/report",
        published_at=signal + timedelta(minutes=10),
        observed_at=signal + timedelta(minutes=11),
        ingested_at=signal + timedelta(minutes=11), availability_proof="local_poll",
        capture_phase="live", role="confirmation",
    )
    late_id, _ = store.add_observation(late)
    store.link_event_observation(event_id, late_id)

    refreshed = store.refresh_kol_token_addressability_evidence(
        now=signal + timedelta(minutes=12)
    )
    assert refreshed["confirmation"] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM kol_token_addressability_confirmation_results "
        "WHERE cohort_id=?", (cohort_id,),
    ).fetchone()[0] == 1
    assert store.due_kol_token_addressability_routes(
        now=signal + timedelta(minutes=12)
    ) == []
    terminal = store.db.execute(
        "SELECT * FROM kol_token_addressability_route_results WHERE cohort_id=?",
        (cohort_id,),
    ).fetchone()
    assert terminal["terminal_status_v2"] == "dex_pair_missing_by_deadline"
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    store.close()


def test_kol_route_v2_separates_pair_queue_and_response_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store = Store(tmp_path / "kol-route-v2-timing.sqlite3")
    account = {"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 5}

    def cohort_with_token(seed: int, *, with_snapshot: bool) -> tuple[int, str, datetime]:
        now = datetime.now(timezone.utc) - timedelta(seconds=2)
        address = _valid_solana_address(seed)
        event_id = store.create_event(f"Route timing {seed}", [f"route timing {seed}"], 20, now)
        observation_id, _ = store.add_observation(Observation(
            source="browser:x:binance", source_kind="social", title=f"Route timing {seed}",
            text=f"Exact CA {address}", published_at=now - timedelta(minutes=1),
            observed_at=now, ingested_at=now, availability_proof="local_receive",
            capture_phase="live", role="feature",
        ))
        store.link_event_observation(event_id, observation_id)
        _record_kol_attention_point(store, event_id, observation_id, 20)
        store.upsert_token(TokenCandidate(
            chain="solana", address=address, name=f"Timing {seed}", symbol=f"T{seed}",
        ), seen_at=now)
        cohort_id = store.create_kol_token_addressability_cohort(
            event_id, observation_id, account=account, identifiers={"solana": [address]},
        )
        assert cohort_id is not None
        frozen_signal = parse_time(store.db.execute(
            "SELECT signal_available_at FROM kol_token_addressability_cohorts WHERE id=?",
            (cohort_id,),
        ).fetchone()["signal_available_at"])
        if with_snapshot:
            store.add_snapshot(TokenSnapshot(
                chain="solana", address=address, price_usd=0.001, liquidity_usd=20_000,
                market_cap_usd=80_000, volume_5m_usd=2_000, buys_5m=4, sells_5m=2,
                observed_at=frozen_signal, ingested_at=frozen_signal, provider="dexscreener",
                raw={"pair": {"chainId": "solana", "dexId": "raydium", "pairAddress": f"PAIR-{seed}"}},
            ))
        return cohort_id, address, frozen_signal

    late_pair_cohort, late_pair_address, late_pair_signal = cohort_with_token(5, with_snapshot=False)
    with monkeypatch.context() as patch:
        patch.setattr(
            "memetrader.store.utcnow", lambda: late_pair_signal + timedelta(minutes=11)
        )
        store.add_snapshot(TokenSnapshot(
            chain="solana", address=late_pair_address, price_usd=0.001, liquidity_usd=20_000,
            market_cap_usd=80_000, volume_5m_usd=2_000, buys_5m=4, sells_5m=2,
            observed_at=late_pair_signal + timedelta(minutes=11),
            ingested_at=late_pair_signal + timedelta(minutes=11), provider="dexscreener",
            raw={"pair": {"chainId": "solana", "dexId": "raydium", "pairAddress": "PAIR-LATE"}},
        ))
    store.refresh_kol_token_addressability_evidence(now=late_pair_signal + timedelta(minutes=12))
    assert store.due_kol_token_addressability_routes(
        now=late_pair_signal + timedelta(minutes=12), limit=10,
    ) == []
    late_pair = store.db.execute(
        "SELECT * FROM kol_token_addressability_route_results WHERE cohort_id=?",
        (late_pair_cohort,),
    ).fetchone()
    assert late_pair["terminal_status_v2"] == "dex_pair_late"
    assert late_pair["pair_timing_status"] == "dex_pair_late"

    queue_cohort, _, queue_signal = cohort_with_token(6, with_snapshot=True)
    store.refresh_kol_token_addressability_evidence(now=queue_signal + timedelta(minutes=1))
    assert store.due_kol_token_addressability_routes(
        now=queue_signal + timedelta(minutes=12), limit=10,
    ) == []
    queue = store.db.execute(
        "SELECT * FROM kol_token_addressability_route_results WHERE cohort_id=?",
        (queue_cohort,),
    ).fetchone()
    assert queue["terminal_status_v2"] == "queue_delay_expired"
    assert queue["pair_timing_status"] == "pair_timely"

    response_cohort, response_address, response_signal = cohort_with_token(7, with_snapshot=True)
    store.refresh_kol_token_addressability_evidence(now=response_signal + timedelta(minutes=1))
    tasks = store.due_kol_token_addressability_routes(
        now=response_signal + timedelta(minutes=1), limit=10,
    )
    task = next(item for item in tasks if item["cohort_id"] == response_cohort)
    attempt_id = store.start_kol_token_addressability_route_attempt(
        task, requested_at=response_signal + timedelta(minutes=1),
    )
    assert attempt_id is not None
    store.record_kol_token_addressability_route_result(
        task, attempt_id=attempt_id, status="quoted",
        evaluated_at=response_signal + timedelta(minutes=11),
        completed_at=response_signal + timedelta(minutes=11),
        result={
            "input_mint": Store.JUPITER_USDC_MINT, "output_mint": response_address,
            "in_amount": "35000000", "slippage_bps": 400,
            "output_amount_raw": "1000", "other_amount_threshold": "960",
            "route_plan": [{
                "percent": 50, "amm_key": "PAIR-7",
                "input_mint": Store.JUPITER_USDC_MINT, "output_mint": response_address,
            }, {"percent": 50, "amm_key": "OTHER"}],
        },
    )
    response = store.db.execute(
        "SELECT * FROM kol_token_addressability_route_results WHERE cohort_id=?",
        (response_cohort,),
    ).fetchone()
    assert response["terminal_status_v2"] == "route_response_late"
    assert response["response_timing_status"] == "response_late"
    assert response["surface_relation"] == "multi_hop_includes_frozen_pair"
    store.close()


def test_kol_route_v2_bounded_refresh_does_not_starve_later_cohorts(tmp_path: Path):
    store = Store(tmp_path / "kol-route-v2-bounded.sqlite3")
    account = {"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 5}
    for index in range(25):
        now = datetime.now(timezone.utc) - timedelta(seconds=2)
        event_id = store.create_event(f"No seed {index}", [f"no seed {index}"], 20, now)
        observation_id, _ = store.add_observation(Observation(
            source="browser:x:binance", source_kind="social", title=f"No seed {index}",
            published_at=now - timedelta(minutes=1), observed_at=now, ingested_at=now,
            availability_proof="local_receive", capture_phase="live", role="feature",
        ))
        store.link_event_observation(event_id, observation_id)
        _record_kol_attention_point(store, event_id, observation_id, 20)
        assert store.create_kol_token_addressability_cohort(
            event_id, observation_id, account=account, identifiers={},
        ) is not None
    for _ in range(3):
        store.refresh_kol_token_addressability_evidence()
        assert store.due_kol_token_addressability_routes(limit=1) == []
    assert store.db.execute(
        "SELECT COUNT(*) FROM kol_token_addressability_route_results "
        "WHERE definition_version=? AND terminal_status_v2='no_seed_at_signal'",
        (Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION,),
    ).fetchone()[0] == 25
    assert store.db.execute(
        "SELECT COUNT(*) FROM kol_token_addressability_confirmation_results "
        "WHERE definition_version=? AND status='no_seed_at_signal'",
        (Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION,),
    ).fetchone()[0] == 25
    store.close()


def test_kol_token_addressability_uses_frozen_v3_boundary_after_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "kol-frozen-definition.sqlite3"
    store = Store(path)
    account = {"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 4}

    def episode(attention: float, suffix: str) -> tuple[int, int]:
        now = datetime.now(timezone.utc)
        event_id = store.create_event(f"Boundary {suffix}", [f"boundary {suffix}"], attention, now)
        observation_id, _ = store.add_observation(Observation(
            source="browser:x:binance", source_kind="social", title=f"Boundary {suffix}",
            published_at=now - timedelta(minutes=1), observed_at=now, ingested_at=now,
            availability_proof="local_receive", capture_phase="live", role="feature",
        ))
        store.link_event_observation(event_id, observation_id)
        _record_kol_attention_point(store, event_id, observation_id, attention)
        return event_id, observation_id

    below_event, below_observation = episode(34.999, "below")
    below_id = store.create_kol_token_addressability_cohort(
        below_event, below_observation, account=account, identifiers={},
    )
    assert below_id is not None
    registration = store.db.execute(
        "SELECT definition_json FROM kol_token_addressability_registrations "
        "WHERE definition_version=?", (Store.KOL_TOKEN_ADDRESSABILITY_VERSION,),
    ).fetchone()
    cohort = store.db.execute(
        "SELECT definition_hash FROM kol_token_addressability_cohorts WHERE id=?", (below_id,)
    ).fetchone()
    assert cohort["definition_hash"] == hashlib.sha256(
        str(registration["definition_json"]).encode("utf-8")
    ).hexdigest()
    store.close()

    monkeypatch.setattr(Store, "KOL_TOKEN_ADDRESSABILITY_MAX_ATTENTION", 100.0)
    store = Store(path)
    equal_event, equal_observation = episode(35.0, "equal")
    above_event, above_observation = episode(35.001, "above")
    assert store.create_kol_token_addressability_cohort(
        equal_event, equal_observation, account=account, identifiers={},
    ) is None
    assert store.create_kol_token_addressability_cohort(
        above_event, above_observation, account=account, identifiers={},
    ) is None
    assert [row["reason"] for row in store.db.execute(
        "SELECT reason FROM kol_token_addressability_admission_attempts "
        "WHERE observation_id IN (?,?) ORDER BY observation_id",
        (equal_observation, above_observation),
    )] == [
        "event_attention_above_low_attention_gate",
        "event_attention_above_low_attention_gate",
    ]
    store.close()


def test_kol_token_addressability_fails_closed_on_malformed_registration(tmp_path: Path):
    path = tmp_path / "kol-malformed.sqlite3"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE kol_token_addressability_registrations("
        "definition_version TEXT PRIMARY KEY,registered_at TEXT NOT NULL,"
        "activation_observation_id INTEGER NOT NULL,definition_json TEXT NOT NULL)"
    )
    db.execute(
        "INSERT INTO kol_token_addressability_registrations VALUES(?,?,0,'{}')",
        (Store.KOL_TOKEN_ADDRESSABILITY_VERSION, iso()),
    )
    db.commit()
    db.close()
    store = Store(path)
    now = datetime.now(timezone.utc)
    event_id = store.create_event("Malformed registration", ["malformed"], 20, now)
    observation_id, _ = store.add_observation(Observation(
        source="browser:x:binance", source_kind="social", title="Malformed registration",
        published_at=now - timedelta(minutes=1), observed_at=now, ingested_at=now,
        availability_proof="local_receive", capture_phase="live", role="feature",
    ))
    store.link_event_observation(event_id, observation_id)
    _record_kol_attention_point(store, event_id, observation_id, 20)
    assert store.create_kol_token_addressability_cohort(
        event_id, observation_id,
        account={"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 5},
        identifiers={},
    ) is None
    assert store.db.execute(
        "SELECT reason FROM kol_token_addressability_admission_attempts WHERE observation_id=?",
        (observation_id,),
    ).fetchone()["reason"] == "registration_definition_invalid"
    store.close()


def test_kol_token_addressability_fails_closed_without_exact_attention_point(tmp_path: Path):
    store = Store(tmp_path / "kol-missing-attention.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = store.create_event("Missing attention point", ["missing"], 20, now)
    observation_id, _ = store.add_observation(Observation(
        source="browser:x:binance", source_kind="social", title="Missing attention point",
        published_at=now - timedelta(minutes=1), observed_at=now, ingested_at=now,
        availability_proof="local_receive", capture_phase="live", role="feature",
    ))
    store.link_event_observation(event_id, observation_id)

    assert store.create_kol_token_addressability_cohort(
        event_id, observation_id,
        account={"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 5},
        identifiers={},
    ) is None
    assert store.db.execute(
        "SELECT reason FROM kol_token_addressability_admission_attempts WHERE observation_id=?",
        (observation_id,),
    ).fetchone()["reason"] == "immutable_attention_point_missing"
    store.close()


def test_kol_token_addressability_uses_durable_snapshot_clock_and_marks_evm_ambiguity(
    tmp_path: Path,
):
    store = Store(tmp_path / "kol-durable-clock.sqlite3")
    account = {"platform": "x", "handle": "@binance", "entity_id": "binance", "priority": 5}
    signal = datetime.now(timezone.utc) - timedelta(seconds=2)
    solana = _valid_solana_address(4)
    event_id = store.create_event("Durable local clock", ["durable clock"], 20, signal)
    observation_id, _ = store.add_observation(Observation(
        source="browser:x:binance", source_kind="social", title="Durable local clock",
        text=f"CA {solana}", published_at=signal - timedelta(minutes=1),
        observed_at=signal, ingested_at=signal, availability_proof="local_receive",
        capture_phase="live", role="feature",
    ))
    store.link_event_observation(event_id, observation_id)
    _record_kol_attention_point(store, event_id, observation_id, 20)
    token = TokenCandidate(chain="solana", address=solana, name="Clock", symbol="CLK")
    store.upsert_token(token, seen_at=signal - timedelta(hours=1))
    cohort_id = store.create_kol_token_addressability_cohort(
        event_id, observation_id, account=account, identifiers={"solana": [solana]},
    )
    assert cohort_id is not None
    assert store.db.execute(
        "SELECT COUNT(*) FROM kol_token_addressability_milestones "
        "WHERE cohort_id=? AND milestone='local_token_discovery'", (cohort_id,),
    ).fetchone()[0] == 0
    store.add_snapshot(TokenSnapshot(
        chain="solana", address=solana, price_usd=0.01, liquidity_usd=10_000,
        market_cap_usd=50_000, volume_5m_usd=1_000, buys_5m=2, sells_5m=1,
        observed_at=signal - timedelta(minutes=10),
        ingested_at=signal - timedelta(minutes=9), provider="dexscreener",
        raw={"pair": {"chainId": "solana", "dexId": "raydium", "pairAddress": "PAIR-L"}},
    ))
    evaluated = datetime.now(timezone.utc)
    store.refresh_kol_token_addressability_evidence(now=evaluated)
    local = store.db.execute(
        "SELECT * FROM kol_token_addressability_milestones "
        "WHERE cohort_id=? AND milestone='local_token_discovery'", (cohort_id,),
    ).fetchone()
    assert parse_time(local["available_at"]) >= signal
    assert json.loads(local["evidence_json"])["basis"] == "token_snapshots.recorded_at"

    evm = "0x" + "1" * 40
    evm_event = store.create_event("Ambiguous EVM", ["ambiguous evm"], 20, evaluated)
    evm_observation, _ = store.add_observation(Observation(
        source="browser:x:binance", source_kind="social", title="Ambiguous EVM",
        text=f"Contract {evm}", published_at=evaluated - timedelta(minutes=1),
        observed_at=evaluated, ingested_at=evaluated, availability_proof="local_receive",
        capture_phase="live", role="feature",
    ))
    store.link_event_observation(evm_event, evm_observation)
    _record_kol_attention_point(store, evm_event, evm_observation, 20)
    evm_cohort = store.create_kol_token_addressability_cohort(
        evm_event, evm_observation, account=account, identifiers={"evm": [evm]},
    )
    frozen = json.loads(store.db.execute(
        "SELECT identifiers_json FROM kol_token_addressability_cohorts WHERE id=?", (evm_cohort,),
    ).fetchone()["identifiers_json"])
    assert frozen == [{"address": evm, "chain": "evm_ambiguous"}]
    assert store.db.execute(
        "SELECT status FROM kol_token_addressability_ambiguities WHERE cohort_id=?",
        (evm_cohort,),
    ).fetchone()["status"] == "ambiguous_evm_chain_at_signal"
    due = store.due_kol_token_addressability_routes(
        now=evaluated + timedelta(seconds=1), limit=10
    )
    assert all(task["cohort_id"] != evm_cohort for task in due)
    assert store.db.execute(
        "SELECT terminal_status_v2 FROM kol_token_addressability_route_results "
        "WHERE cohort_id=?", (evm_cohort,),
    ).fetchone()["terminal_status_v2"] == "ambiguous_chain"
    summary = Store.kol_token_addressability_summary_from_connection(store.db)
    assert summary["route_status"] == "observed"
    store.close()


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
                    text=(
                        "Independent reporting confirms the same current event and contract "
                        f"{linked.address}."
                    ),
                    url=f"https://{domain}/story",
                    availability_proof="agent_search_verified",
                    role="confirmation",
                    source_item_id=f"https://{domain}/story",
                    raw={
                        "agent_web_search": True,
                        "agent_task": "token_context",
                        "token_context_binding_status": "exact_token_binding",
                        "fact_verification_distinct_origin_support_domains": 2,
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

        low_score_decision = await CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 100,
                "min_canonical_margin": 5,
                "agent_tie_threshold": 3,
                "agent_resolution_confidence": {"low": 0.85, "medium": 0.78},
                "max_alias_queries": 1,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        ).discover_and_decide(event)
        assert low_score_decision is not None and low_score_decision.action == "WAIT"
        assert low_score_decision.rejected_reasons == [
            "candidate_score_too_low",
            "canonical_token_ambiguous",
        ]
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


def test_unqualified_token_context_reverse_id_cannot_create_exact_candidate(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        token = TokenCandidate(
            chain="solana", address="C" * 32, name="Context Only Otter", symbol="COTTER"
        )
        engine = EventEngine(store)
        event_id = None
        for domain in ("publisher-a.example", "publisher-b.example"):
            event_id, _, _ = engine.ingest(
                Observation(
                    source=f"agent-search:{domain}",
                    source_kind="news",
                    title="A current otter story spreads online",
                    text="Independent reporting confirms the event without naming a contract.",
                    url=f"https://{domain}/story",
                    availability_proof="agent_search_verified",
                    role="confirmation",
                    source_item_id=f"https://{domain}/story",
                    raw={
                        "agent_task": "token_context",
                        "token_context_binding_status": "event_confirmation_only",
                        "fact_verification_distinct_origin_support_domains": 2,
                        "reverse_token_id": token.token_id,
                    },
                )
            )

        class FakeDex:
            quote_calls = []

            async def quote(self, chain, address):
                self.quote_calls.append((chain, address))
                return None

            async def search(self, query, limit=25):
                return []

        dex = FakeDex()
        evaluator = CandidateEvaluator(
            store,
            dex,
            type("Safety", (), {"check": lambda self, snapshot: None})(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
                "min_reverse_independent_sources": 2,
            },
            None,
        )
        decision = await evaluator.discover_and_decide(store.get_event(int(event_id)))
        assert decision is not None and decision.action == "WAIT" and decision.token_id == ""
        assert dex.quote_calls == []
        store.close()

    asyncio.run(scenario())


def test_event_candidate_uses_fresh_two_way_jupiter_route_when_dex_liquidity_is_unknown(
    tmp_path: Path,
):
    async def scenario():
        store = Store(tmp_path / "event-route.sqlite3")
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        address = "A" * 32
        engine = EventEngine(store)
        event_id = None
        for source in ("official:x", "news:independent"):
            current_id, _, _ = engine.ingest(Observation(
                source=source,
                source_kind="official_social" if source.startswith("official") else "news",
                title=f"Official viral launch CA: {address}",
                text=f"Independent current report confirms CA: {address}",
                observed_at=now,
                ingested_at=now,
                availability_proof="local_receive",
                role="feature" if source.startswith("official") else "confirmation",
            ))
            event_id = current_id
        token = TokenCandidate("solana", address, "Official Viral Launch", "VIRAL")
        snapshot = TokenSnapshot(
            "solana", address, 0.00001, None, 100_000, 30_000, 20, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"dexId": "pumpfun"}},
        )

        class Dex:
            async def quote(self, chain, requested_address):
                return (token, snapshot) if requested_address == address else None

            async def search(self, query, limit=25):
                return []

        class Jupiter:
            calls = 0

            async def quote(self, input_mint, output_mint, amount, *, slippage_bps):
                self.calls += 1
                requested = utcnow()
                if self.calls == 1:
                    out_amount, minimum = "1000000", "950000"
                else:
                    assert amount == 950000
                    out_amount, minimum = "33000000", "32000000"
                completed = utcnow()
                return {
                    "requested_at": iso(requested), "completed_at": iso(completed),
                    "input_mint": input_mint, "output_mint": output_mint,
                    "in_amount": str(amount), "out_amount": out_amount,
                    "other_amount_threshold": minimum, "route_plan": [{"label": "fixture"}],
                    "slippage_bps": slippage_bps,
                }

        safety = SafetyChecker(None, {
            "min_liquidity_usd": 12_000, "min_5m_transactions": 8,
            "min_buy_ratio": 0.55, "goplus_solana": False, "rugcheck": False,
            "require_solana_report": False,
        })
        evaluator = CandidateEvaluator(
            store, Dex(), safety,
            {
                "chains": ["solana"], "min_match_score": 1,
                "min_candidate_score": 60, "min_canonical_margin": 4,
                "max_alias_queries": 1, "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            None, Jupiter(),
            {"max_position_usd": 35, "slippage_rate": 0.04,
             "pump_swap_fee_bps": 125, "max_quote_age_seconds": 45},
            asyncio.Lock(),
        )
        decision = await evaluator.discover_and_decide(store.get_event(int(event_id)))
        assert decision is not None and decision.action == "CANDIDATE"
        assert decision.route_probe_id is not None
        assert "liquidity=unknown" in decision.reasons
        probe = store.event_context_jupiter_route_probe(decision.route_probe_id)
        assert probe["status"] == "valid" and probe["decision_eligible"] == 1
        assert probe["sell_input_amount_raw"] == "950000"
        assert probe["round_trip_min_return"] == pytest.approx(32 / 35 - 1)
        decision_id = store.add_decision(decision)
        assert store.event_context_jupiter_route_probe(decision.route_probe_id)["decision_id"] == decision_id
        store.close()

    asyncio.run(scenario())


def test_event_route_execution_challenger_is_activation_fenced_and_never_fills_main_paper(
    tmp_path: Path,
):
    store = Store(tmp_path / "event-route-execution-challenger.sqlite3", initial_cash_usd=1000)
    registration = store.register_event_route_execution_challenger()
    assert registration["activation_decision_id"] == 0
    assert registration["activation_route_probe_id"] == 0

    now = utcnow() - timedelta(seconds=2)
    address = "R" * 32
    event_id, _, _ = EventEngine(store).ingest(Observation(
        source="official:x", source_kind="official_social",
        title=f"Exact launch CA {address}", text=f"CA {address}",
        observed_at=now, ingested_at=now, availability_proof="local_receive",
    ))
    token = TokenCandidate("solana", address, "Exact Route", "ROUTE")
    store.upsert_token(token, seen_at=now)
    snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", address, 0.00001, None, 100_000, 30_000, 20, 5,
        observed_at=now, ingested_at=now, provider="dexscreener",
    ))
    anchor = utcnow()
    probe_id = store.start_event_context_jupiter_route_probe(
        event_id=event_id, token_id=token.token_id, source_snapshot_id=snapshot_id,
        anchor_at=anchor, input_notional_usd=35, buy_input_amount_raw=35_000_000,
        slippage_bps=400, max_total_delay_seconds=45,
    )
    store.finish_event_context_jupiter_route_probe(
        probe_id, status="valid", reason="fresh_two_way_route",
        buy_quote={
            "requested_at": iso(anchor), "completed_at": iso(anchor),
            "in_amount": "35000000", "out_amount": "2100000",
            "other_amount_threshold": "2000000",
        },
        sell_quote={
            "requested_at": iso(anchor), "completed_at": iso(anchor),
            "in_amount": "2000000", "out_amount": "33000000",
            "other_amount_threshold": "32000000",
        },
        round_trip_min_return=32 / 35 - 1, decision_eligible=True,
    )
    decision_id = store.add_decision(CandidateDecision(
        event_id=event_id, token_id=token.token_id, action="WAIT", score=90,
        match_score=95, canonical_margin=15,
        reasons=["jupiter_two_way_capacity_probe_only"],
        rejected_reasons=["route_backed_paper_execution_not_implemented"],
        position_usd=12.34, route_probe_id=probe_id, created_at=utcnow(),
    ))
    attempt_id = store.start_event_route_execution_challenger_attempt(
        decision_id=decision_id, event_id=event_id, token_id=token.token_id,
        capacity_probe_id=probe_id, baseline_snapshot_id=snapshot_id,
        intended_notional_usd=12.34, buy_input_amount_raw=12_340_000,
        slippage_bps=400, max_total_delay_seconds=45,
        baseline_quote_price=0.00001, baseline_execution_price=0.0000104,
        baseline_fee_bps=125, baseline_buy_tax_pct=None, baseline_sell_tax_pct=None,
    )
    assert attempt_id is not None
    attempt = store.db.execute(
        "SELECT * FROM event_route_execution_challenger_attempts WHERE id=?",
        (attempt_id,),
    ).fetchone()
    assert attempt["buy_input_amount_raw"] == "12340000"
    assert attempt["buy_input_amount_raw"] != store.event_context_jupiter_route_probe(
        probe_id
    )["buy_input_amount_raw"]
    assert store.open_positions() == [] and store.trades() == []
    assert store.account() == {"cash_usd": 1000.0, "realized_pnl_usd": 0.0}

    store.finish_event_route_execution_challenger_attempt(
        attempt_id, quote_terminal_status="quoted", validity_status="valid",
        economic_status="cost_unknown", reason="research_only",
        buy_quote={
            "requested_at": iso(anchor), "completed_at": iso(anchor),
            "out_amount": "800000", "other_amount_threshold": "750000",
        },
        sell_quote={
            "requested_at": iso(anchor), "completed_at": iso(anchor),
            "in_amount": "750000", "out_amount": "11800000",
            "other_amount_threshold": "11700000",
        },
        round_trip_min_return=11.7 / 12.34 - 1,
        route_only_cost_usd=0.64,
        fee_completeness_status="quote_fee_fields_incomplete_or_zero",
        network_fee_basis="native_fee_usd_conversion_not_yet_frozen",
    )
    summary = store.event_route_execution_challenger_summary_from_connection(store.db)
    assert summary["summary"]["attempts"] == 1
    assert summary["summary"]["economic_counts"] == {"cost_unknown": 1}
    assert summary["summary"]["fills"] == 0
    assert store.start_event_route_execution_challenger_attempt(
        decision_id=decision_id, event_id=event_id, token_id=token.token_id,
        capacity_probe_id=probe_id, baseline_snapshot_id=snapshot_id,
        intended_notional_usd=12.34, buy_input_amount_raw=12_340_000,
        slippage_bps=400, max_total_delay_seconds=45,
        baseline_quote_price=0.00001, baseline_execution_price=0.0000104,
        baseline_fee_bps=125, baseline_buy_tax_pct=None, baseline_sell_tax_pct=None,
    ) is None
    store.close()


def test_event_candidate_waits_when_two_way_jupiter_route_is_unavailable(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "event-route-missing.sqlite3")
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        address = "B" * 32
        event_id, _, _ = EventEngine(store).ingest(Observation(
            source="official:x", source_kind="official_social",
            title=f"Official launch CA: {address}", text=f"CA: {address}",
            observed_at=now, ingested_at=now, availability_proof="local_receive",
        ))
        token = TokenCandidate("solana", address, "Official Launch", "OFF")
        snapshot = TokenSnapshot(
            "solana", address, 0.00001, None, 100_000, 30_000, 20, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
            raw={"pair": {"dexId": "pumpfun"}},
        )

        class Dex:
            async def quote(self, chain, requested_address): return token, snapshot
            async def search(self, query, limit=25): return []

        class Jupiter:
            async def quote(self, *args, **kwargs):
                raise JupiterNoRouteError("no route")

        safety = SafetyChecker(None, {
            "min_liquidity_usd": 12_000, "min_5m_transactions": 8,
            "min_buy_ratio": 0.55, "goplus_solana": False, "rugcheck": False,
            "require_solana_report": False,
        })
        decision = await CandidateEvaluator(
            store, Dex(), safety,
            {"chains": ["solana"], "min_match_score": 1, "min_candidate_score": 60,
             "min_canonical_margin": 4, "max_alias_queries": 1,
             "token_watch_minutes": 240, "max_source_age_minutes": 30},
            None, Jupiter(),
            {"max_position_usd": 35, "slippage_rate": 0.04,
             "pump_swap_fee_bps": 125, "max_quote_age_seconds": 45},
        ).discover_and_decide(store.get_event(event_id))
        assert decision is not None and decision.action == "WAIT"
        assert decision.rejected_reasons == ["execution_route_unavailable"]
        probe = store.db.execute(
            "SELECT status,reason FROM event_context_jupiter_route_probes ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert (probe["status"], probe["reason"]) == ("no_route", "buy_route_unavailable")
        store.close()

    asyncio.run(scenario())


def test_solana_unknown_liquidity_requires_explicit_executable_route():
    async def scenario():
        checker = SafetyChecker(None, {
            "min_liquidity_usd": 12_000, "min_5m_transactions": 8,
            "min_buy_ratio": 0.55, "goplus_solana": False, "rugcheck": False,
            "require_solana_report": False,
        })
        snapshot = TokenSnapshot(
            "solana", "C" * 32, 0.001, None, 100_000, 20_000, 10, 2,
        )
        assert await checker.check(snapshot) == (False, ["liquidity_unknown"])
        assert await checker.check(snapshot, executable_route=True) == (True, [])

    asyncio.run(scenario())


def test_robinhood_is_collected_for_research_but_rejected_for_execution():
    class NoHttp:
        async def get(self, *args, **kwargs):
            raise AssertionError("unsupported execution chain must not call a safety provider")

    async def scenario():
        checker = SafetyChecker(
            NoHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "max_tax_pct": 12,
            },
        )
        snapshot = TokenSnapshot(
            "robinhood", "0x" + "1" * 40, 1, 10000, 100000, 1000, 10, 2
        )
        ok, reasons = await checker.check(snapshot)
        assert ok is False
        assert reasons == ["execution_safety_unsupported_chain"]

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
