from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .models import (
    CandidateDecision,
    EventView,
    Observation,
    Position,
    TokenCandidate,
    TokenSnapshot,
    iso,
    parse_time,
    utcnow,
)


class Store:
    CANDIDATE_RANKING_KEY_PREFIX = "candidate_ranking:"
    SHADOW_EVENT_COHORT_VERSION = "shadow-event-followup/v3-strategy-labels"
    SHADOW_EVENT_ADMISSION_VERSION = "shadow-event-admission/v2-all-actions"
    SHADOW_EVENT_HORIZONS_MINUTES = (15, 60, 240)
    TOKEN_CONTEXT_ADMISSION_VERSION = "token-context-admission/v1"
    TOKEN_CONTEXT_OUTCOME_VERSION = "token-context-outcome/v1"
    TOKEN_CONTEXT_OUTCOME_HORIZONS_MINUTES = (15, 60, 240)
    INFORMATION_FIRST_SHADOW_VERSION = "information-first-shadow/v1"
    INFORMATION_FIRST_SHADOW_HORIZONS_MINUTES = (15, 60, 240)
    INFORMATION_FIRST_SHADOW_QUIET_MARKET_CAP_USD = 1_000_000.0
    INFORMATION_FIRST_SHADOW_QUIET_VOLUME_5M_USD = 20_000.0
    INFORMATION_FIRST_SHADOW_QUIET_TRANSACTIONS_5M = 30
    INFORMATION_FIRST_ILG_VERSION = "information-first-ilg/v1"
    INFORMATION_FIRST_ILG_WINDOW_MINUTES = 240
    INFORMATION_FIRST_ILG_TERMINAL_GRACE_MINUTES = 30
    INFORMATION_FIRST_ILG_VOLUME_5M_USD = 20_000.0
    INFORMATION_FIRST_ILG_TRANSACTIONS_5M = 30
    WATCH_ATTENTION_POLICY_VERSION = "watch-attention/v3-experiment-gated"
    TREND_ATTENTION_POLICY_VERSION = "trend-attention/v2-experiment-gated"
    ATTENTION_EXPERIMENT_VERSION = "attention-experiment/v1"
    ATTENTION_EXPERIMENT_HORIZON_MINUTES = 60
    PAPER_SOURCE_ATTRIBUTION_VERSION = "paper-source-attribution/v2-decision-cohort"
    SOURCE_POLL_EXPOSURE_VERSION = "source-poll-exposure/v1"
    TOKEN_DISCOVERY_EXPOSURE_VERSION = "token-discovery-exposure/v1"
    EVENT_ATTENTION_TRAJECTORY_VERSION = "event-attention-trajectory/v1"
    EVENT_CLAIM_ASSESSMENT_VERSION = "event-claim-assessment/v1"
    EVENT_CLAIM_RELATION_VERSION = "event-claim-relation/v1"
    SOURCE_ITEM_REVISION_VERSION = "source-item-revision/v1"
    OBSERVATION_PROVENANCE_VERSION = "observation-provenance/v1"
    TELEGRAM_EXTERNAL_HANDOFF_VERSION = "telegram-manual-external-origin-handoff/v1"
    EVENT_CLAIM_STATUSES = {
        "confirmed_fact", "probable_report", "unverified_rumor", "false_claim",
        "correction", "retraction", "satire", "impersonation", "promotion",
        "unassessed", "excluded_future",
    }

    def __init__(self, path: str | Path, initial_cash_usd: float = 10000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    url TEXT NOT NULL,
                    author TEXT NOT NULL,
                    published_at TEXT,
                    observed_at TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    availability_proof TEXT NOT NULL,
                    role TEXT NOT NULL,
                    source_item_id TEXT NOT NULL DEFAULT '',
                    capture_phase TEXT NOT NULL DEFAULT 'live',
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observations_observed_idx ON observations(observed_at);
                CREATE INDEX IF NOT EXISTS observations_source_idx ON observations(source, observed_at);

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    attention REAL NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    topic TEXT NOT NULL DEFAULT 'unknown'
                );
                CREATE TABLE IF NOT EXISTS event_observations (
                    event_id INTEGER NOT NULL,
                    observation_id INTEGER NOT NULL,
                    PRIMARY KEY(event_id, observation_id)
                );
                CREATE TABLE IF NOT EXISTS event_attention_points (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    observation_id INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    attention REAL NOT NULL,
                    eligible_observation_count INTEGER NOT NULL,
                    context_observation_count INTEGER NOT NULL,
                    trigger_role TEXT NOT NULL,
                    trigger_decision_eligible INTEGER NOT NULL,
                    exclusion_reason TEXT,
                    coverage_mode TEXT NOT NULL,
                    UNIQUE(definition_version,event_id,observation_id)
                );
                CREATE INDEX IF NOT EXISTS event_attention_points_event_idx
                    ON event_attention_points(event_id,recorded_at,id);
                CREATE TRIGGER IF NOT EXISTS event_attention_points_no_update
                BEFORE UPDATE ON event_attention_points
                BEGIN SELECT RAISE(ABORT,'event attention points are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_attention_points_no_delete
                BEFORE DELETE ON event_attention_points
                BEGIN SELECT RAISE(ABORT,'event attention points are immutable'); END;
                CREATE TABLE IF NOT EXISTS event_claim_ledger_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_claim_assessments (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    observation_id INTEGER NOT NULL,
                    previous_assessment_id INTEGER,
                    assessed_at TEXT NOT NULL,
                    claim_status TEXT NOT NULL,
                    factual_confidence REAL,
                    source_identity_confidence REAL,
                    attention_confidence REAL,
                    meme_catalyst_strength REAL,
                    correction_risk REAL,
                    assessment_source TEXT NOT NULL,
                    assessment_basis TEXT NOT NULL,
                    trigger_role TEXT NOT NULL,
                    trigger_decision_eligible INTEGER NOT NULL,
                    exclusion_reason TEXT,
                    UNIQUE(definition_version,event_id,observation_id)
                );
                CREATE INDEX IF NOT EXISTS event_claim_assessments_event_idx
                    ON event_claim_assessments(event_id,assessed_at,id);
                CREATE TRIGGER IF NOT EXISTS event_claim_assessments_no_update
                BEFORE UPDATE ON event_claim_assessments
                BEGIN SELECT RAISE(ABORT,'event claim assessments are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_assessments_no_delete
                BEFORE DELETE ON event_claim_assessments
                BEGIN SELECT RAISE(ABORT,'event claim assessments are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_ledger_registrations_no_update
                BEFORE UPDATE ON event_claim_ledger_registrations
                BEGIN SELECT RAISE(ABORT,'event claim ledger registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_ledger_registrations_no_delete
                BEFORE DELETE ON event_claim_ledger_registrations
                BEGIN SELECT RAISE(ABORT,'event claim ledger registrations are immutable'); END;
                CREATE TABLE IF NOT EXISTS event_claim_relation_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_claim_relations (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    edge_fingerprint TEXT NOT NULL UNIQUE,
                    source_revision_id INTEGER NOT NULL,
                    target_revision_id INTEGER,
                    relation_type TEXT NOT NULL CHECK(relation_type IN ('supersedes','corrects','retracts')),
                    relation_scope TEXT NOT NULL CHECK(relation_scope IN ('same_item_version','cross_item_exact_url')),
                    resolution_status TEXT NOT NULL CHECK(resolution_status IN (
                        'resolved','target_not_found','ambiguous_target','invalid_target_url','excluded_temporal'
                    )),
                    target_url_fingerprint TEXT NOT NULL,
                    target_match_count INTEGER NOT NULL CHECK(target_match_count>=0),
                    evidence_basis TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    source_observed_at TEXT NOT NULL,
                    source_ingested_at TEXT NOT NULL,
                    temporal_exclusion_reason TEXT,
                    decision_eligible INTEGER NOT NULL DEFAULT 0 CHECK(decision_eligible=0),
                    affects TEXT NOT NULL DEFAULT 'none' CHECK(affects='none'),
                    CHECK(
                        (resolution_status='resolved' AND target_revision_id IS NOT NULL)
                        OR (resolution_status<>'resolved' AND target_revision_id IS NULL)
                    ),
                    UNIQUE(definition_version,source_revision_id,relation_type)
                );
                CREATE INDEX IF NOT EXISTS event_claim_relations_source_idx
                    ON event_claim_relations(source_revision_id,recorded_at,id);
                CREATE INDEX IF NOT EXISTS event_claim_relations_target_idx
                    ON event_claim_relations(target_revision_id,recorded_at,id);
                CREATE TRIGGER IF NOT EXISTS event_claim_relation_registrations_no_update
                BEFORE UPDATE ON event_claim_relation_registrations
                BEGIN SELECT RAISE(ABORT,'event claim relation registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_relation_registrations_no_delete
                BEFORE DELETE ON event_claim_relation_registrations
                BEGIN SELECT RAISE(ABORT,'event claim relation registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_relations_no_update
                BEFORE UPDATE ON event_claim_relations
                BEGIN SELECT RAISE(ABORT,'event claim relations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_claim_relations_no_delete
                BEFORE DELETE ON event_claim_relations
                BEGIN SELECT RAISE(ABORT,'event claim relations are immutable'); END;
                CREATE TABLE IF NOT EXISTS source_item_revision_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_item_revisions (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    source_item_key TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    previous_revision_id INTEGER,
                    edge_fingerprint TEXT NOT NULL UNIQUE,
                    anchor_observation_id INTEGER,
                    capture_observation_id INTEGER,
                    recorded_at TEXT NOT NULL,
                    capture_observed_at TEXT NOT NULL,
                    capture_ingested_at TEXT NOT NULL,
                    source_published_at TEXT,
                    source_reported_revision_at TEXT,
                    source TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    identity_mode TEXT NOT NULL,
                    revision_kind TEXT NOT NULL,
                    local_state TEXT NOT NULL,
                    semantic_signal TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    changed_fields_json TEXT NOT NULL,
                    availability_proof TEXT NOT NULL,
                    tombstone_evidence_code TEXT,
                    temporal_exclusion_reason TEXT,
                    decision_eligible INTEGER NOT NULL DEFAULT 0 CHECK(decision_eligible=0),
                    affects TEXT NOT NULL DEFAULT 'none' CHECK(affects='none'),
                    UNIQUE(definition_version,source_item_key,sequence_no)
                );
                CREATE INDEX IF NOT EXISTS source_item_revisions_key_idx
                    ON source_item_revisions(definition_version,source_item_key,sequence_no);
                CREATE INDEX IF NOT EXISTS source_item_revisions_anchor_idx
                    ON source_item_revisions(anchor_observation_id,recorded_at,id);
                CREATE TRIGGER IF NOT EXISTS source_item_revision_registrations_no_update
                BEFORE UPDATE ON source_item_revision_registrations
                BEGIN SELECT RAISE(ABORT,'source item revision registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS source_item_revision_registrations_no_delete
                BEFORE DELETE ON source_item_revision_registrations
                BEGIN SELECT RAISE(ABORT,'source item revision registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS source_item_revisions_no_update
                BEFORE UPDATE ON source_item_revisions
                BEGIN SELECT RAISE(ABORT,'source item revisions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS source_item_revisions_no_delete
                BEFORE DELETE ON source_item_revisions
                BEGIN SELECT RAISE(ABORT,'source item revisions are immutable'); END;
                CREATE TABLE IF NOT EXISTS observation_provenance_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observation_provenance_assertions (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    observation_id INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    source_observed_at TEXT NOT NULL,
                    source_ingested_at TEXT NOT NULL,
                    source_published_at TEXT,
                    route_kind TEXT NOT NULL,
                    origin_identity_state TEXT NOT NULL,
                    origin_platform TEXT NOT NULL,
                    origin_actor TEXT NOT NULL,
                    origin_item_url TEXT NOT NULL,
                    origin_root_key TEXT NOT NULL,
                    transport_platform TEXT NOT NULL,
                    transport_source TEXT NOT NULL,
                    local_collector TEXT NOT NULL,
                    evidence_basis TEXT NOT NULL,
                    temporal_exclusion_reason TEXT,
                    decision_eligible INTEGER NOT NULL DEFAULT 0 CHECK(decision_eligible=0),
                    affects TEXT NOT NULL DEFAULT 'none' CHECK(affects='none'),
                    UNIQUE(definition_version,observation_id)
                );
                CREATE INDEX IF NOT EXISTS observation_provenance_origin_idx
                    ON observation_provenance_assertions(origin_root_key,recorded_at,id);
                CREATE TRIGGER IF NOT EXISTS observation_provenance_registrations_no_update
                BEFORE UPDATE ON observation_provenance_registrations
                BEGIN SELECT RAISE(ABORT,'observation provenance registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS observation_provenance_registrations_no_delete
                BEFORE DELETE ON observation_provenance_registrations
                BEGIN SELECT RAISE(ABORT,'observation provenance registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS observation_provenance_assertions_no_update
                BEFORE UPDATE ON observation_provenance_assertions
                BEGIN SELECT RAISE(ABORT,'observation provenance assertions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS observation_provenance_assertions_no_delete
                BEFORE DELETE ON observation_provenance_assertions
                BEGIN SELECT RAISE(ABORT,'observation provenance assertions are immutable'); END;

                CREATE TABLE IF NOT EXISTS telegram_external_handoff_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS telegram_external_handoff_attempts (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    catalog_entity_id TEXT NOT NULL,
                    external_url_safe TEXT NOT NULL,
                    external_url_fingerprint TEXT NOT NULL,
                    submitted_via TEXT NOT NULL,
                    decision_eligible INTEGER NOT NULL DEFAULT 0 CHECK(decision_eligible=0),
                    affects TEXT NOT NULL DEFAULT 'investigation_only' CHECK(affects='investigation_only')
                );
                CREATE TABLE IF NOT EXISTS telegram_external_handoff_results (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    attempt_id INTEGER NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('verified','duplicate','zero_yield','rejected','error')),
                    reason TEXT NOT NULL,
                    final_external_url_safe TEXT NOT NULL,
                    observation_id INTEGER,
                    event_id INTEGER,
                    http_status INTEGER,
                    decision_eligible INTEGER NOT NULL DEFAULT 0 CHECK(decision_eligible=0),
                    affects TEXT NOT NULL DEFAULT 'investigation_only' CHECK(affects='investigation_only')
                );
                CREATE INDEX IF NOT EXISTS telegram_external_handoff_attempts_time_idx
                    ON telegram_external_handoff_attempts(received_at,id);
                CREATE INDEX IF NOT EXISTS telegram_external_handoff_results_time_idx
                    ON telegram_external_handoff_results(recorded_at,id);
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_registrations_no_update
                BEFORE UPDATE ON telegram_external_handoff_registrations
                BEGIN SELECT RAISE(ABORT,'telegram external handoff registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_registrations_no_delete
                BEFORE DELETE ON telegram_external_handoff_registrations
                BEGIN SELECT RAISE(ABORT,'telegram external handoff registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_attempts_no_update
                BEFORE UPDATE ON telegram_external_handoff_attempts
                BEGIN SELECT RAISE(ABORT,'telegram external handoff attempts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_attempts_no_delete
                BEFORE DELETE ON telegram_external_handoff_attempts
                BEGIN SELECT RAISE(ABORT,'telegram external handoff attempts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_results_no_update
                BEFORE UPDATE ON telegram_external_handoff_results
                BEGIN SELECT RAISE(ABORT,'telegram external handoff results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS telegram_external_handoff_results_no_delete
                BEFORE DELETE ON telegram_external_handoff_results
                BEGIN SELECT RAISE(ABORT,'telegram external handoff results are immutable'); END;

                CREATE TABLE IF NOT EXISTS tokens (
                    token_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    created_at TEXT,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    social_urls_json TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tokens_last_seen_idx ON tokens(last_seen_at);

                CREATE TABLE IF NOT EXISTS token_snapshots (
                    id INTEGER PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    ingested_at TEXT,
                    recorded_at TEXT,
                    provider TEXT NOT NULL,
                    price_usd REAL,
                    liquidity_usd REAL,
                    market_cap_usd REAL,
                    volume_5m_usd REAL,
                    buys_5m INTEGER,
                    sells_5m INTEGER,
                    buyers_5m INTEGER,
                    holders INTEGER,
                    buy_tax_pct REAL,
                    sell_tax_pct REAL,
                    honeypot INTEGER,
                    sellable INTEGER,
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS token_snapshots_lookup_idx
                    ON token_snapshots(token_id, observed_at DESC);

                CREATE TABLE IF NOT EXISTS token_source_links (
                    id INTEGER PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    token_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    discovery_surface TEXT NOT NULL,
                    role TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    normalized_url TEXT NOT NULL,
                    link_kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    first_observed_at TEXT NOT NULL,
                    last_observed_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS token_source_links_token_idx
                    ON token_source_links(token_id, last_observed_at DESC);
                CREATE INDEX IF NOT EXISTS token_source_links_url_idx
                    ON token_source_links(normalized_url);

                CREATE TABLE IF NOT EXISTS token_detail_hydration (
                    token_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    enqueued_at TEXT NOT NULL,
                    last_attempt_at TEXT,
                    next_attempt_at TEXT,
                    hydrated_at TEXT,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS token_detail_hydration_due_idx
                    ON token_detail_hydration(status, next_attempt_at, enqueued_at);

                CREATE TABLE IF NOT EXISTS token_context_assessments (
                    id INTEGER PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assessed_at TEXT NOT NULL,
                    snapshot_observed_at TEXT NOT NULL,
                    momentum_score REAL NOT NULL,
                    assessment_json TEXT NOT NULL,
                    agent_metadata_json TEXT NOT NULL,
                    audit_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS token_context_assessments_lookup_idx
                    ON token_context_assessments(token_id, assessed_at DESC, id DESC);
                CREATE TABLE IF NOT EXISTS token_context_admission_attempts (
                    id INTEGER PRIMARY KEY,
                    version TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL DEFAULT '',
                    trigger_priority INTEGER,
                    platform TEXT NOT NULL DEFAULT '',
                    entity_id TEXT NOT NULL DEFAULT '',
                    event_id INTEGER,
                    decision_id INTEGER,
                    snapshot_observed_at TEXT NOT NULL,
                    momentum_score REAL NOT NULL,
                    next_eligible_at TEXT,
                    quota_day TEXT NOT NULL,
                    daily_call_limit INTEGER NOT NULL,
                    calls_used_before INTEGER NOT NULL,
                    daily_token_budget INTEGER NOT NULL,
                    tokens_used_before INTEGER NOT NULL,
                    token_reserve_per_call INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS token_context_admission_attempts_lookup_idx
                    ON token_context_admission_attempts(token_id,evaluated_at DESC,id DESC);
                CREATE INDEX IF NOT EXISTS token_context_admission_attempts_reason_idx
                    ON token_context_admission_attempts(reason,evaluated_at DESC);
                CREATE TABLE IF NOT EXISTS token_context_outcome_cohorts (
                    id INTEGER PRIMARY KEY,
                    cohort_key TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    assessment_id INTEGER NOT NULL UNIQUE,
                    token_id TEXT NOT NULL,
                    assessed_at TEXT NOT NULL,
                    entry_snapshot_id INTEGER NOT NULL,
                    entry_snapshot_at TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS token_context_outcome_cohorts_status_idx
                    ON token_context_outcome_cohorts(status, assessed_at);
                CREATE INDEX IF NOT EXISTS token_context_outcome_cohorts_token_idx
                    ON token_context_outcome_cohorts(token_id, assessed_at);
                CREATE TABLE IF NOT EXISTS token_context_outcome_labels (
                    cohort_id INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'frozen_assessment',
                    PRIMARY KEY(cohort_id,dimension,value)
                );
                CREATE INDEX IF NOT EXISTS token_context_outcome_labels_dimension_idx
                    ON token_context_outcome_labels(dimension,value,cohort_id);
                CREATE TABLE IF NOT EXISTS token_context_outcomes (
                    id INTEGER PRIMARY KEY,
                    cohort_id INTEGER NOT NULL,
                    horizon_minutes INTEGER NOT NULL,
                    target_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_snapshot_id INTEGER,
                    outcome_observed_at TEXT,
                    outcome_price REAL,
                    raw_return REAL,
                    maximum_return REAL,
                    minimum_return REAL,
                    snapshot_count INTEGER NOT NULL DEFAULT 0,
                    evaluated_at TEXT NOT NULL,
                    UNIQUE(cohort_id,horizon_minutes)
                );
                CREATE INDEX IF NOT EXISTS token_context_outcomes_horizon_idx
                    ON token_context_outcomes(horizon_minutes,status,evaluated_at);

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    score REAL NOT NULL,
                    match_score REAL NOT NULL,
                    canonical_margin REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    rejected_reasons_json TEXT NOT NULL,
                    position_usd REAL NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_account (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    cash_usd REAL NOT NULL,
                    realized_pnl_usd REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions (
                    token_id TEXT PRIMARY KEY,
                    event_id INTEGER NOT NULL,
                    decision_id INTEGER,
                    cohort_id INTEGER,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    remaining_cost_usd REAL NOT NULL,
                    highest_price REAL NOT NULL,
                    opened_at TEXT NOT NULL,
                    realized_pnl_usd REAL NOT NULL,
                    take_profit_index INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    decision_id INTEGER,
                    cohort_id INTEGER,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    quote_price REAL,
                    gross_usd REAL NOT NULL,
                    fee_usd REAL NOT NULL,
                    fee_bps REAL,
                    slippage_rate REAL,
                    slippage_usd REAL,
                    tax_pct REAL,
                    tax_usd REAL,
                    quote_observed_at TEXT,
                    quote_provider TEXT,
                    execution_attempted_at TEXT,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS trades_created_idx ON trades(created_at);
                CREATE TABLE IF NOT EXISTS paper_execution_attempts (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    decision_id INTEGER,
                    cohort_id INTEGER,
                    side TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    quote_observed_at TEXT,
                    quote_provider TEXT,
                    quote_price REAL,
                    execution_price REAL,
                    gross_usd REAL
                );
                CREATE INDEX IF NOT EXISTS paper_execution_attempts_created_idx
                    ON paper_execution_attempts(requested_at DESC);
                CREATE TABLE IF NOT EXISTS paper_account_snapshots (
                    id INTEGER PRIMARY KEY,
                    recorded_at TEXT NOT NULL,
                    cash_usd REAL NOT NULL,
                    marked_value_usd REAL NOT NULL,
                    equity_usd REAL,
                    daily_exposure_usd REAL NOT NULL,
                    open_position_count INTEGER NOT NULL,
                    priced_position_count INTEGER NOT NULL,
                    quote_as_of TEXT
                );
                CREATE INDEX IF NOT EXISTS paper_account_snapshots_recorded_idx
                    ON paper_account_snapshots(recorded_at DESC);

                CREATE TABLE IF NOT EXISTS source_utility_outcomes (
                    id INTEGER PRIMARY KEY,
                    outcome_key TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    decision_id INTEGER,
                    cohort_id INTEGER,
                    attribution_version TEXT NOT NULL DEFAULT 'legacy-event-window/v1',
                    source_observation_id INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    value TEXT NOT NULL,
                    origin_platform TEXT NOT NULL,
                    attribution_basis TEXT NOT NULL DEFAULT 'discovery_lead',
                    attribution_weight REAL NOT NULL,
                    net_return REAL NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL,
                    UNIQUE(outcome_key,source_observation_id,dimension,value)
                );
                CREATE INDEX IF NOT EXISTS source_utility_outcomes_dimension_idx
                    ON source_utility_outcomes(dimension,value,closed_at DESC);
                CREATE INDEX IF NOT EXISTS source_utility_outcomes_event_idx
                    ON source_utility_outcomes(event_id,token_id);
                CREATE TABLE IF NOT EXISTS paper_source_attribution_attempts (
                    outcome_key TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    decision_id INTEGER,
                    cohort_id INTEGER,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    eligible_source_count INTEGER NOT NULL DEFAULT 0,
                    buy_cost_usd REAL,
                    sell_net_usd REAL,
                    net_return REAL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS paper_source_attribution_attempts_closed_idx
                    ON paper_source_attribution_attempts(closed_at DESC);
                CREATE TABLE IF NOT EXISTS source_health (
                    source TEXT PRIMARY KEY,
                    last_ok_at TEXT,
                    last_item_at TEXT,
                    last_error_at TEXT,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS source_poll_attempts (
                    id INTEGER PRIMARY KEY,
                    version TEXT NOT NULL,
                    collector_kind TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    new_observation_count INTEGER NOT NULL DEFAULT 0,
                    new_event_count INTEGER NOT NULL DEFAULT 0,
                    decision_eligible_count INTEGER NOT NULL DEFAULT 0,
                    context_only_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    filtered_count INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS source_poll_attempts_source_idx
                    ON source_poll_attempts(source_key,started_at DESC,id DESC);
                CREATE INDEX IF NOT EXISTS source_poll_attempts_platform_idx
                    ON source_poll_attempts(platform,started_at DESC,id DESC);
                CREATE TABLE IF NOT EXISTS token_discovery_rounds (
                    id INTEGER PRIMARY KEY,
                    version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    chain_scope TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    requested_count INTEGER NOT NULL DEFAULT 0,
                    returned_count INTEGER NOT NULL DEFAULT 0,
                    exposed_token_count INTEGER NOT NULL DEFAULT 0,
                    first_local_discovery_count INTEGER NOT NULL DEFAULT 0,
                    new_token_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_token_count INTEGER NOT NULL DEFAULT 0,
                    source_link_count INTEGER NOT NULL DEFAULT 0,
                    new_source_link_count INTEGER NOT NULL DEFAULT 0,
                    snapshot_count INTEGER NOT NULL DEFAULT 0,
                    no_pair_count INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS token_discovery_rounds_surface_idx
                    ON token_discovery_rounds(provider,surface,started_at DESC,id DESC);
                CREATE TABLE IF NOT EXISTS token_discovery_exposures (
                    id INTEGER PRIMARY KEY,
                    round_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'discovery',
                    first_local_discovery INTEGER NOT NULL DEFAULT 0,
                    new_token INTEGER NOT NULL DEFAULT 0,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    source_link_count INTEGER NOT NULL DEFAULT 0,
                    new_source_link_count INTEGER NOT NULL DEFAULT 0,
                    snapshot_count INTEGER NOT NULL DEFAULT 0,
                    no_pair INTEGER NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    UNIQUE(round_id,token_id),
                    FOREIGN KEY(round_id) REFERENCES token_discovery_rounds(id)
                );
                CREATE INDEX IF NOT EXISTS token_discovery_exposures_token_idx
                    ON token_discovery_exposures(token_id,observed_at DESC,id DESC);
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_attempts (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_index INTEGER NOT NULL,
                    task TEXT NOT NULL,
                    model TEXT NOT NULL,
                    reasoning_effort TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    returncode INTEGER NOT NULL,
                    fallback INTEGER NOT NULL,
                    input_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    cache_write_input_tokens INTEGER,
                    output_tokens INTEGER,
                    reasoning_output_tokens INTEGER,
                    total_tokens INTEGER,
                    accounting_source TEXT NOT NULL,
                    UNIQUE(run_id, attempt_index)
                );
                CREATE INDEX IF NOT EXISTS agent_attempts_task_time_idx
                    ON agent_attempts(task, finished_at DESC);
                CREATE INDEX IF NOT EXISTS agent_attempts_model_time_idx
                    ON agent_attempts(model, reasoning_effort, finished_at DESC);

                CREATE TABLE IF NOT EXISTS trend_lane_runs (
                    run_id TEXT PRIMARY KEY,
                    taxonomy_version TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    selection_mode TEXT NOT NULL,
                    surge INTEGER NOT NULL,
                    max_web_searches INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    reasoning_effort TEXT NOT NULL DEFAULT '',
                    accepted_event_count INTEGER NOT NULL DEFAULT 0,
                    rejected_event_count INTEGER NOT NULL DEFAULT 0,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT NOT NULL DEFAULT '',
                    observation_ingestion_status TEXT NOT NULL DEFAULT 'pending',
                    observation_ingestion_finalized_at TEXT
                );
                CREATE INDEX IF NOT EXISTS trend_lane_runs_time_idx
                    ON trend_lane_runs(started_at DESC);
                CREATE TABLE IF NOT EXISTS trend_lane_run_lanes (
                    run_id TEXT NOT NULL,
                    lane_id TEXT NOT NULL,
                    lane_prompt TEXT NOT NULL,
                    event_topics_json TEXT NOT NULL,
                    selection_role TEXT NOT NULL,
                    attention_multiplier REAL NOT NULL DEFAULT 1,
                    scheduled_coverage_fraction REAL NOT NULL,
                    accepted_event_count INTEGER NOT NULL DEFAULT 0,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,lane_id)
                );
                CREATE INDEX IF NOT EXISTS trend_lane_run_lanes_lane_idx
                    ON trend_lane_run_lanes(lane_id,run_id);
                CREATE TABLE IF NOT EXISTS trend_watch_account_exposures (
                    run_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    handle_key TEXT NOT NULL,
                    entity_id TEXT NOT NULL DEFAULT '',
                    configured_priority INTEGER NOT NULL,
                    watch_cadence TEXT NOT NULL,
                    selection_role TEXT NOT NULL,
                    learning_basis TEXT NOT NULL,
                    learning_multiplier REAL NOT NULL DEFAULT 1,
                    exact_source_hits INTEGER NOT NULL DEFAULT 0,
                    accepted_event_count INTEGER NOT NULL DEFAULT 0,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,platform,handle_key)
                );
                CREATE INDEX IF NOT EXISTS trend_watch_account_exposures_account_idx
                    ON trend_watch_account_exposures(platform,handle_key,run_id);
                CREATE INDEX IF NOT EXISTS trend_watch_account_exposures_entity_idx
                    ON trend_watch_account_exposures(entity_id,run_id);
                CREATE TABLE IF NOT EXISTS browser_watch_account_exposures (
                    exposure_id TEXT PRIMARY KEY,
                    window_started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    handle_key TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    configured_priority INTEGER NOT NULL,
                    watch_cadence TEXT NOT NULL,
                    status TEXT NOT NULL,
                    access_state TEXT NOT NULL,
                    visible INTEGER,
                    selector_count INTEGER NOT NULL DEFAULT 0,
                    exact_source_hits INTEGER NOT NULL DEFAULT 0,
                    accepted_event_count INTEGER NOT NULL DEFAULT 0,
                    observation_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS browser_watch_account_exposures_account_idx
                    ON browser_watch_account_exposures(platform,handle_key,window_started_at);
                CREATE INDEX IF NOT EXISTS browser_watch_account_exposures_entity_idx
                    ON browser_watch_account_exposures(entity_id,window_started_at);
                CREATE TABLE IF NOT EXISTS browser_watch_observation_links (
                    observation_id INTEGER PRIMARY KEY,
                    exposure_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    decision_eligible INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(exposure_id) REFERENCES browser_watch_account_exposures(exposure_id),
                    FOREIGN KEY(event_id) REFERENCES events(id)
                );
                CREATE INDEX IF NOT EXISTS browser_watch_observation_links_event_idx
                    ON browser_watch_observation_links(event_id,observed_at);

                CREATE TABLE IF NOT EXISTS attention_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    target_kind TEXT NOT NULL CHECK(target_kind='watch_account'),
                    hypothesis TEXT NOT NULL,
                    challenger_platform TEXT NOT NULL,
                    challenger_handle_key TEXT NOT NULL,
                    challenger_entity_id TEXT NOT NULL,
                    control_platform TEXT NOT NULL,
                    control_handle_key TEXT NOT NULL,
                    control_entity_id TEXT NOT NULL,
                    random_seed TEXT NOT NULL,
                    assignment_block_size INTEGER NOT NULL CHECK(assignment_block_size=4),
                    planned_assignments_per_arm INTEGER NOT NULL,
                    min_calendar_days INTEGER NOT NULL,
                    config_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attention_experiment_events (
                    id INTEGER PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(experiment_id) REFERENCES attention_experiments(experiment_id)
                );
                CREATE INDEX IF NOT EXISTS attention_experiment_events_latest_idx
                    ON attention_experiment_events(experiment_id,effective_at DESC,id DESC);
                CREATE TABLE IF NOT EXISTS attention_experiment_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    arm TEXT NOT NULL CHECK(arm IN ('challenger','control')),
                    target_platform TEXT NOT NULL,
                    target_handle_key TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    assignment_index INTEGER NOT NULL,
                    assignment_probability REAL NOT NULL CHECK(assignment_probability=0.5),
                    assigned_at TEXT NOT NULL,
                    UNIQUE(experiment_id,run_id),
                    UNIQUE(experiment_id,assignment_index),
                    FOREIGN KEY(experiment_id) REFERENCES attention_experiments(experiment_id)
                );
                CREATE INDEX IF NOT EXISTS attention_experiment_assignments_run_idx
                    ON attention_experiment_assignments(run_id,target_platform,target_handle_key);
                CREATE TABLE IF NOT EXISTS attention_experiment_observation_links (
                    experiment_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    observation_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    arm TEXT NOT NULL CHECK(arm IN ('challenger','control')),
                    decision_eligible INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(experiment_id,observation_id),
                    FOREIGN KEY(experiment_id) REFERENCES attention_experiments(experiment_id),
                    FOREIGN KEY(assignment_id) REFERENCES attention_experiment_assignments(assignment_id)
                );
                CREATE INDEX IF NOT EXISTS attention_experiment_observation_event_idx
                    ON attention_experiment_observation_links(experiment_id,event_id,observed_at);
                CREATE TABLE IF NOT EXISTS attention_experiment_event_cohorts (
                    id INTEGER PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    assignment_id TEXT,
                    arm TEXT,
                    source_observation_id INTEGER,
                    decision_id INTEGER NOT NULL,
                    decision_at TEXT NOT NULL,
                    token_id TEXT NOT NULL DEFAULT '',
                    entry_snapshot_id INTEGER,
                    entry_snapshot_at TEXT,
                    entry_price REAL,
                    status TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    UNIQUE(experiment_id,event_id),
                    FOREIGN KEY(experiment_id) REFERENCES attention_experiments(experiment_id)
                );
                CREATE TABLE IF NOT EXISTS attention_experiment_outcomes (
                    cohort_id INTEGER NOT NULL,
                    horizon_minutes INTEGER NOT NULL CHECK(horizon_minutes=60),
                    target_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_snapshot_id INTEGER,
                    outcome_observed_at TEXT,
                    outcome_price REAL,
                    raw_return REAL,
                    evaluated_at TEXT NOT NULL,
                    PRIMARY KEY(cohort_id,horizon_minutes),
                    FOREIGN KEY(cohort_id) REFERENCES attention_experiment_event_cohorts(id)
                );
                CREATE TRIGGER IF NOT EXISTS attention_experiments_no_update
                BEFORE UPDATE ON attention_experiments
                BEGIN SELECT RAISE(ABORT,'attention experiment registration is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiments_no_delete
                BEFORE DELETE ON attention_experiments
                BEGIN SELECT RAISE(ABORT,'attention experiment registration is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_assignments_no_update
                BEFORE UPDATE ON attention_experiment_assignments
                BEGIN SELECT RAISE(ABORT,'attention experiment assignment is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_assignments_no_delete
                BEFORE DELETE ON attention_experiment_assignments
                BEGIN SELECT RAISE(ABORT,'attention experiment assignment is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_events_no_update
                BEFORE UPDATE ON attention_experiment_events
                BEGIN SELECT RAISE(ABORT,'attention experiment state history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_events_no_delete
                BEFORE DELETE ON attention_experiment_events
                BEGIN SELECT RAISE(ABORT,'attention experiment state history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_links_no_update
                BEFORE UPDATE ON attention_experiment_observation_links
                BEGIN SELECT RAISE(ABORT,'attention experiment observation links are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_links_no_delete
                BEFORE DELETE ON attention_experiment_observation_links
                BEGIN SELECT RAISE(ABORT,'attention experiment observation links are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_cohorts_no_update
                BEFORE UPDATE ON attention_experiment_event_cohorts
                BEGIN SELECT RAISE(ABORT,'attention experiment cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_cohorts_no_delete
                BEFORE DELETE ON attention_experiment_event_cohorts
                BEGIN SELECT RAISE(ABORT,'attention experiment cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_outcomes_no_update
                BEFORE UPDATE ON attention_experiment_outcomes
                BEGIN SELECT RAISE(ABORT,'attention experiment outcomes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS attention_experiment_outcomes_no_delete
                BEFORE DELETE ON attention_experiment_outcomes
                BEGIN SELECT RAISE(ABORT,'attention experiment outcomes are immutable'); END;

                CREATE TABLE IF NOT EXISTS shadow_event_cohorts (
                    id INTEGER PRIMARY KEY,
                    cohort_key TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    decision_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    decision_at TEXT NOT NULL,
                    entry_snapshot_id INTEGER NOT NULL,
                    entry_snapshot_at TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    eligible_source_count INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS shadow_event_cohorts_status_idx
                    ON shadow_event_cohorts(status,decision_at);
                CREATE INDEX IF NOT EXISTS shadow_event_cohorts_event_idx
                    ON shadow_event_cohorts(event_id,token_id);
                CREATE TABLE IF NOT EXISTS shadow_event_admission_attempts (
                    id INTEGER PRIMARY KEY,
                    admission_key TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    decision_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    requested_action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    cohort_id INTEGER,
                    source_observation_count INTEGER NOT NULL DEFAULT 0,
                    eligible_source_count INTEGER NOT NULL DEFAULT 0,
                    attempted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS shadow_event_admission_attempts_event_idx
                    ON shadow_event_admission_attempts(event_id,requested_action);
                CREATE INDEX IF NOT EXISTS shadow_event_admission_attempts_status_idx
                    ON shadow_event_admission_attempts(status,requested_action,attempted_at);
                CREATE TABLE IF NOT EXISTS shadow_event_cohort_labels (
                    cohort_id INTEGER NOT NULL,
                    source_observation_id INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    value TEXT NOT NULL,
                    origin_platform TEXT NOT NULL,
                    attribution_weight REAL NOT NULL,
                    PRIMARY KEY(cohort_id,source_observation_id,dimension,value)
                );
                CREATE INDEX IF NOT EXISTS shadow_event_cohort_labels_dimension_idx
                    ON shadow_event_cohort_labels(dimension,value,cohort_id);
                CREATE TABLE IF NOT EXISTS shadow_event_outcomes (
                    id INTEGER PRIMARY KEY,
                    cohort_id INTEGER NOT NULL,
                    horizon_minutes INTEGER NOT NULL,
                    target_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_snapshot_id INTEGER,
                    outcome_observed_at TEXT,
                    outcome_price REAL,
                    raw_return REAL,
                    maximum_return REAL,
                    minimum_return REAL,
                    snapshot_count INTEGER NOT NULL DEFAULT 0,
                    evaluated_at TEXT NOT NULL,
                    UNIQUE(cohort_id,horizon_minutes)
                );
                CREATE INDEX IF NOT EXISTS shadow_event_outcomes_horizon_idx
                    ON shadow_event_outcomes(horizon_minutes,status,evaluated_at);

                CREATE TABLE IF NOT EXISTS information_first_shadow_cohorts (
                    id INTEGER PRIMARY KEY,
                    cohort_key TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    decision_id INTEGER NOT NULL,
                    captured_at TEXT NOT NULL,
                    signal_available_at TEXT NOT NULL,
                    relation_available_at TEXT NOT NULL,
                    lead_observation_id INTEGER NOT NULL,
                    lead_observed_at TEXT NOT NULL,
                    entry_snapshot_id INTEGER,
                    entry_snapshot_at TEXT,
                    entry_snapshot_ingested_at TEXT,
                    entry_price REAL,
                    trackability TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(version,event_id,token_id)
                );
                CREATE INDEX IF NOT EXISTS information_first_shadow_cohorts_token_idx
                    ON information_first_shadow_cohorts(token_id,captured_at);
                CREATE TABLE IF NOT EXISTS information_first_shadow_admission_attempts (
                    id INTEGER PRIMARY KEY,
                    admission_key TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    decision_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    token_id TEXT NOT NULL,
                    attempted_at TEXT NOT NULL,
                    relation_available_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    cohort_id INTEGER
                );
                CREATE INDEX IF NOT EXISTS information_first_shadow_admission_attempts_event_idx
                    ON information_first_shadow_admission_attempts(event_id,token_id,attempted_at);
                CREATE TABLE IF NOT EXISTS information_first_shadow_outcomes (
                    id INTEGER PRIMARY KEY,
                    cohort_id INTEGER NOT NULL,
                    horizon_minutes INTEGER NOT NULL,
                    target_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_snapshot_id INTEGER,
                    outcome_observed_at TEXT,
                    outcome_price REAL,
                    raw_return REAL,
                    maximum_return REAL,
                    minimum_return REAL,
                    snapshot_count INTEGER NOT NULL DEFAULT 0,
                    evaluated_at TEXT NOT NULL,
                    UNIQUE(cohort_id,horizon_minutes),
                    FOREIGN KEY(cohort_id) REFERENCES information_first_shadow_cohorts(id)
                );
                CREATE INDEX IF NOT EXISTS information_first_shadow_outcomes_horizon_idx
                    ON information_first_shadow_outcomes(horizon_minutes,status,evaluated_at);
                CREATE TABLE IF NOT EXISTS information_first_ilg_registrations (
                    definition_version TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL,
                    definition_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS information_first_ilg_cohorts (
                    id INTEGER PRIMARY KEY,
                    definition_version TEXT NOT NULL,
                    shadow_cohort_id INTEGER NOT NULL UNIQUE,
                    enrolled_at TEXT NOT NULL,
                    signal_available_at TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    eligibility TEXT NOT NULL,
                    eligibility_reason TEXT NOT NULL,
                    window_end_at TEXT NOT NULL,
                    terminal_at TEXT NOT NULL,
                    baseline_snapshot_id INTEGER,
                    baseline_recorded_at TEXT,
                    baseline_volume_5m_usd REAL,
                    baseline_transactions_5m INTEGER,
                    surface_key TEXT,
                    surface_provider TEXT,
                    surface_chain_id TEXT,
                    surface_dex_id TEXT,
                    surface_pair_address TEXT,
                    definition_json TEXT NOT NULL,
                    FOREIGN KEY(shadow_cohort_id) REFERENCES information_first_shadow_cohorts(id)
                );
                CREATE INDEX IF NOT EXISTS information_first_ilg_cohorts_status_idx
                    ON information_first_ilg_cohorts(eligibility,enrolled_at);
                CREATE TABLE IF NOT EXISTS information_first_ilg_outcomes (
                    id INTEGER PRIMARY KEY,
                    ilg_cohort_id INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    window_end_at TEXT NOT NULL,
                    terminal_at TEXT NOT NULL,
                    crossing_snapshot_id INTEGER,
                    crossing_observed_at TEXT,
                    crossing_ingested_at TEXT,
                    crossing_recorded_at TEXT,
                    ilg_seconds REAL,
                    crossing_volume_5m_usd REAL,
                    crossing_transactions_5m INTEGER,
                    crossed_dimensions_json TEXT NOT NULL,
                    valid_snapshot_count INTEGER NOT NULL,
                    surface_key TEXT,
                    evaluated_at TEXT NOT NULL,
                    FOREIGN KEY(ilg_cohort_id) REFERENCES information_first_ilg_cohorts(id)
                );
                CREATE INDEX IF NOT EXISTS information_first_ilg_outcomes_status_idx
                    ON information_first_ilg_outcomes(status,evaluated_at);
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_cohorts_no_update
                BEFORE UPDATE ON information_first_shadow_cohorts
                BEGIN SELECT RAISE(ABORT,'information-first shadow cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_cohorts_no_delete
                BEFORE DELETE ON information_first_shadow_cohorts
                BEGIN SELECT RAISE(ABORT,'information-first shadow cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_admission_attempts_no_update
                BEFORE UPDATE ON information_first_shadow_admission_attempts
                BEGIN SELECT RAISE(ABORT,'information-first shadow admissions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_admission_attempts_no_delete
                BEFORE DELETE ON information_first_shadow_admission_attempts
                BEGIN SELECT RAISE(ABORT,'information-first shadow admissions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_outcomes_no_update
                BEFORE UPDATE ON information_first_shadow_outcomes
                BEGIN SELECT RAISE(ABORT,'information-first shadow outcomes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_shadow_outcomes_no_delete
                BEFORE DELETE ON information_first_shadow_outcomes
                BEGIN SELECT RAISE(ABORT,'information-first shadow outcomes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_registrations_no_update
                BEFORE UPDATE ON information_first_ilg_registrations
                BEGIN SELECT RAISE(ABORT,'information-first ILG registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_registrations_no_delete
                BEFORE DELETE ON information_first_ilg_registrations
                BEGIN SELECT RAISE(ABORT,'information-first ILG registrations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_cohorts_no_update
                BEFORE UPDATE ON information_first_ilg_cohorts
                BEGIN SELECT RAISE(ABORT,'information-first ILG cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_cohorts_no_delete
                BEFORE DELETE ON information_first_ilg_cohorts
                BEGIN SELECT RAISE(ABORT,'information-first ILG cohorts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_outcomes_no_update
                BEFORE UPDATE ON information_first_ilg_outcomes
                BEGIN SELECT RAISE(ABORT,'information-first ILG outcomes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS information_first_ilg_outcomes_no_delete
                BEFORE DELETE ON information_first_ilg_outcomes
                BEGIN SELECT RAISE(ABORT,'information-first ILG outcomes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS token_snapshots_no_update
                BEFORE UPDATE ON token_snapshots
                BEGIN SELECT RAISE(ABORT,'token snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS token_snapshots_no_delete
                BEFORE DELETE ON token_snapshots
                BEGIN SELECT RAISE(ABORT,'token snapshots are immutable'); END;
                """
            )
            columns = {row["name"] for row in self.db.execute("PRAGMA table_info(observations)")}
            if "source_item_id" not in columns:
                self.db.execute("ALTER TABLE observations ADD COLUMN source_item_id TEXT NOT NULL DEFAULT ''")
            if "capture_phase" not in columns:
                self.db.execute("ALTER TABLE observations ADD COLUMN capture_phase TEXT NOT NULL DEFAULT 'live'")
            snapshot_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(token_snapshots)")
            }
            if "ingested_at" not in snapshot_columns:
                self.db.execute("ALTER TABLE token_snapshots ADD COLUMN ingested_at TEXT")
            if "recorded_at" not in snapshot_columns:
                self.db.execute("ALTER TABLE token_snapshots ADD COLUMN recorded_at TEXT")
            self.db.execute(
                "INSERT OR IGNORE INTO information_first_ilg_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.INFORMATION_FIRST_ILG_VERSION,
                    iso(),
                    self._json(self._information_first_ilg_definition()),
                ),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO event_claim_ledger_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.EVENT_CLAIM_ASSESSMENT_VERSION,
                    iso(),
                    self._json(
                        {
                            "append_only": True,
                            "no_historical_backfill": True,
                            "assessment_scope": "new_forward_observations_only",
                            "statuses": sorted(self.EVENT_CLAIM_STATUSES),
                            "decision_effect": "none",
                        }
                    ),
                ),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO source_item_revision_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.SOURCE_ITEM_REVISION_VERSION,
                    iso(),
                    self._json(
                        {
                            "append_only": True,
                            "no_historical_backfill": True,
                            "scope": "new_forward_source_item_captures_only",
                            "identity_modes": ["explicit_source_item_id", "exact_safe_url"],
                            "absence_is_not_deletion": True,
                            "delete_is_not_retraction": True,
                            "retraction_is_not_false_claim": True,
                            "decision_effect": "none",
                        }
                    ),
                ),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO event_claim_relation_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.EVENT_CLAIM_RELATION_VERSION,
                    iso(),
                    self._json(
                        {
                            "append_only": True,
                            "no_historical_backfill": True,
                            "scope": "new_forward_source_item_revision_assertions_only",
                            "relation_types": ["supersedes", "corrects", "retracts"],
                            "nodes": "source_item_revisions",
                            "exact_target_url_must_resolve_uniquely": True,
                            "deletion_is_not_retraction": True,
                            "assessment_labels_are_not_claim_relations": True,
                            "decision_effect": "none",
                        }
                    ),
                ),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO observation_provenance_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.OBSERVATION_PROVENANCE_VERSION,
                    iso(),
                    self._json(
                        {
                            "append_only": True,
                            "no_historical_backfill": True,
                            "scope": "new_forward_observations_only",
                            "unknown_is_not_independent": True,
                            "transport_is_not_origin": True,
                            "decision_effect": "none",
                        }
                    ),
                ),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO telegram_external_handoff_registrations("
                "definition_version,registered_at,definition_json) VALUES(?,?,?)",
                (
                    self.TELEGRAM_EXTERNAL_HANDOFF_VERSION,
                    iso(),
                    self._json(
                        {
                            "append_only": True,
                            "no_historical_backfill": True,
                            "scope": "user_submitted_external_original_urls_only",
                            "telegram_message_content_stored": False,
                            "telegram_credentials_or_sessions_accepted": False,
                            "external_origin_refetched_locally": True,
                            "transport_is_not_origin": True,
                            "decision_effect": "none",
                        }
                    ),
                ),
            )
            event_columns = {row["name"] for row in self.db.execute("PRAGMA table_info(events)")}
            if "topic" not in event_columns:
                self.db.execute("ALTER TABLE events ADD COLUMN topic TEXT NOT NULL DEFAULT 'unknown'")
            lane_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(trend_lane_run_lanes)")
            }
            if "attention_multiplier" not in lane_columns:
                self.db.execute(
                    "ALTER TABLE trend_lane_run_lanes "
                    "ADD COLUMN attention_multiplier REAL NOT NULL DEFAULT 1"
                )
            trend_run_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(trend_lane_runs)")
            }
            if "observation_ingestion_status" not in trend_run_columns:
                self.db.execute(
                    "ALTER TABLE trend_lane_runs ADD COLUMN "
                    "observation_ingestion_status TEXT NOT NULL DEFAULT 'legacy_uninstrumented'"
                )
            if "observation_ingestion_finalized_at" not in trend_run_columns:
                self.db.execute(
                    "ALTER TABLE trend_lane_runs ADD COLUMN observation_ingestion_finalized_at TEXT"
                )
            attention_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(attention_experiments)")
            }
            if "planned_assignments_per_arm" not in attention_columns:
                self.db.execute(
                    "ALTER TABLE attention_experiments ADD COLUMN "
                    "planned_assignments_per_arm INTEGER NOT NULL DEFAULT 60"
                )
            trade_columns = {row["name"] for row in self.db.execute("PRAGMA table_info(trades)")}
            for name, definition in (
                ("decision_id", "INTEGER"), ("cohort_id", "INTEGER"),
                ("quote_price", "REAL"), ("fee_bps", "REAL"),
                ("slippage_rate", "REAL"), ("slippage_usd", "REAL"),
                ("tax_pct", "REAL"), ("tax_usd", "REAL"),
                ("quote_observed_at", "TEXT"), ("quote_provider", "TEXT"),
                ("execution_attempted_at", "TEXT"),
            ):
                if name not in trade_columns:
                    self.db.execute(f"ALTER TABLE trades ADD COLUMN {name} {definition}")
            position_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(positions)")
            }
            for name in ("decision_id", "cohort_id"):
                if name not in position_columns:
                    self.db.execute(f"ALTER TABLE positions ADD COLUMN {name} INTEGER")
            execution_attempt_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(paper_execution_attempts)")
            }
            for name in ("decision_id", "cohort_id"):
                if name not in execution_attempt_columns:
                    self.db.execute(
                        f"ALTER TABLE paper_execution_attempts ADD COLUMN {name} INTEGER"
                    )
            source_outcome_columns = {
                row["name"] for row in self.db.execute("PRAGMA table_info(source_utility_outcomes)")
            }
            if "attribution_basis" not in source_outcome_columns:
                self.db.execute(
                    "ALTER TABLE source_utility_outcomes "
                    "ADD COLUMN attribution_basis TEXT NOT NULL DEFAULT 'discovery_lead'"
                )
            for name, definition in (
                ("decision_id", "INTEGER"),
                ("cohort_id", "INTEGER"),
                ("attribution_version", "TEXT NOT NULL DEFAULT 'legacy-event-window/v1'"),
            ):
                if name not in source_outcome_columns:
                    self.db.execute(
                        f"ALTER TABLE source_utility_outcomes ADD COLUMN {name} {definition}"
                    )
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS source_utility_outcomes_basis_idx "
                "ON source_utility_outcomes(attribution_basis,closed_at DESC)"
            )
            self.db.execute(
                "INSERT OR IGNORE INTO paper_account(singleton,cash_usd,realized_pnl_usd,updated_at) VALUES(?,?,0,?)",
                (1, float(initial_cash_usd), iso()),
            )

    def close(self) -> None:
        with self._lock:
            self.db.close()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @classmethod
    def _bounded_json(cls, value: Any, max_chars: int = 16_000) -> str:
        serialized = cls._json(value)
        if len(serialized) <= max_chars:
            return serialized
        return cls._json(
            {
                "truncated": True,
                "sha256": hashlib.sha256(serialized.encode("utf-8", errors="ignore")).hexdigest(),
                "preview": serialized[: max(0, max_chars - 200)],
            }
        )

    @staticmethod
    def _json_object(value: Any) -> dict[str, Any]:
        try:
            parsed = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _fingerprint(obs: Observation) -> str:
        if obs.source_item_id:
            stable = f"{obs.source.strip().lower()}\n{obs.source_item_id.strip()}"
            return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()
        stable = "\n".join(
            [obs.source.strip().lower(), obs.url.strip(), obs.author.strip().lower(), obs.title.strip(), obs.text.strip()]
        )
        return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _legacy_fingerprint(obs: Observation) -> str:
        stable = "\n".join(
            [obs.source.strip().lower(), obs.url.strip(), obs.author.strip().lower(), obs.title.strip(), obs.text.strip()]
        )
        return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _revision_safe_url(value: Any) -> str:
        text = str(value or "").strip()
        try:
            parsed = urlparse(text)
        except Exception:
            return ""
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            return ""
        safe_query = []
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.casefold().replace("-", "_")
            if lowered.startswith("utm_") or any(
                marker in lowered
                for marker in ("token", "secret", "password", "passwd", "auth", "api_key", "apikey", "session")
            ):
                continue
            if lowered not in {"fbclid", "gclid", "ref_src"}:
                safe_query.append((key, item))
        return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.params, urlencode(safe_query), ""))

    @staticmethod
    def _provenance_platform(url: str, hint: Any = "") -> str:
        normalized_hint = str(hint or "").strip().lower()
        normalized_hint = {
            "twitter": "x", "truthsocial": "truth", "bsky": "bluesky",
        }.get(normalized_hint, normalized_hint)
        if normalized_hint:
            return normalized_hint[:80]
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        for root, platform in (
            ("x.com", "x"), ("twitter.com", "x"), ("bsky.app", "bluesky"),
            ("truthsocial.com", "truth"), ("reddit.com", "reddit"),
            ("threads.net", "threads"), ("threads.com", "threads"),
            ("instagram.com", "instagram"), ("tiktok.com", "tiktok"),
            ("youtube.com", "youtube"), ("youtu.be", "youtube"),
            ("t.me", "telegram"), ("telegram.me", "telegram"),
        ):
            if host == root or host.endswith(f".{root}"):
                return platform
        return "web" if host else "unknown"

    @staticmethod
    def _is_exact_public_item(platform: str, url: str) -> bool:
        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        if platform == "x":
            return bool(re.fullmatch(r"/[^/]+/status/\d+/?", path))
        if platform == "bluesky":
            return bool(re.fullmatch(r"/profile/[^/]+/post/[^/]+/?", path))
        if platform == "truth":
            return "/posts/" in path or "/statuses/" in path
        if platform == "reddit":
            return "/comments/" in path
        if platform == "threads":
            return "/post/" in path
        if platform == "instagram":
            return path.startswith(("/p/", "/reel/", "/reels/"))
        if platform == "tiktok":
            return "/video/" in path
        if platform == "youtube":
            return (parsed.hostname or "").lower().endswith("youtu.be") or path.startswith(("/watch", "/shorts/", "/live/"))
        if platform == "telegram":
            return bool(re.fullmatch(r"/[^/]+/\d+/?", path))
        if platform == "mastodon":
            return bool(re.search(r"/@[^/]+/\d+/?$", path))
        return False

    def _record_observation_provenance_locked(self, obs: Observation, observation_id: int) -> bool:
        registration = self.db.execute(
            "SELECT registered_at FROM observation_provenance_registrations WHERE definition_version=?",
            (self.OBSERVATION_PROVENANCE_VERSION,),
        ).fetchone()
        if registration is None or obs.ingested_at < parse_time(registration["registered_at"]):
            return False
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        browser = raw.get("browser") if isinstance(raw.get("browser"), dict) else {}
        safe_url = self._revision_safe_url(obs.url)
        source = str(obs.source or "").strip()
        agent_task = str(raw.get("agent_task") or "").strip().lower()
        platform_hint = browser.get("platform") or raw.get("platform")
        if not platform_hint and source.lower().startswith("bluesky:"):
            platform_hint = "bluesky"
        platform = self._provenance_platform(safe_url, platform_hint)
        actor = str(raw.get("source_entity_id") or obs.author or raw.get("publisher") or "")[:300]
        feed_url = self._revision_safe_url(raw.get("feed_url"))
        publisher_url = self._revision_safe_url(raw.get("publisher_url"))
        route_kind = "unknown"
        identity_state = "unknown"
        transport_platform = "unknown"
        transport_source = source[:300]
        local_collector = "local_poll" if obs.availability_proof == "local_poll" else "unknown"
        evidence_basis = "insufficient_explicit_provenance"
        if raw.get("telegram_external_handoff") is True:
            route_kind = "relay"
            identity_state = "verified_external_origin_page"
            transport_platform = "telegram"
            transport_source = str(raw.get("telegram_catalog_entity_id") or "")[:300]
            local_collector = "local_web_external_handoff"
            evidence_basis = "user_submitted_external_origin_refetched_locally"
        elif obs.availability_proof == "local_receive" and browser:
            local_collector = "browser_bridge"
            transport_platform = "none"
            transport_source = ""
            if self._is_exact_public_item(platform, safe_url):
                route_kind = "direct"
                identity_state = "proven_direct_item"
                evidence_basis = "local_browser_exact_permalink"
        elif platform == "bluesky" and source.lower().startswith("bluesky:") and self._is_exact_public_item(platform, safe_url):
            route_kind = "direct"
            identity_state = "proven_direct_item"
            transport_platform = "bluesky_public_api"
            local_collector = "bluesky_public_api"
            evidence_basis = "public_platform_api_exact_item"
        elif platform == "mastodon" and self._is_exact_public_item(platform, safe_url):
            route_kind = "direct"
            identity_state = "proven_direct_item"
            transport_platform = "mastodon_public_api"
            local_collector = "mastodon_public_api"
            evidence_basis = "public_platform_api_exact_item"
        elif feed_url:
            route_kind = "relay"
            identity_state = "asserted_upstream" if publisher_url else "inferred_candidate"
            transport_platform = "rss"
            transport_source = source[:300]
            local_collector = "rss_poll"
            evidence_basis = "rss_source_element_claim" if publisher_url else "rss_item_link_candidate"
        elif agent_task or obs.availability_proof == "agent_search_verified":
            route_kind = "discovery"
            identity_state = "inferred_candidate" if safe_url else "unknown"
            transport_platform = "agent_web_search"
            transport_source = (agent_task or source)[:300]
            local_collector = "agent_subprocess"
            evidence_basis = "agent_search_reachable_url_candidate"
        root_material = safe_url or (
            f"{source.casefold()}\n{obs.source_item_id.strip()}" if obs.source_item_id.strip() else ""
        )
        origin_root_key = (
            hashlib.sha256(root_material.encode("utf-8", errors="ignore")).hexdigest()
            if root_material else ""
        )
        recorded_at = utcnow()
        exclusions = []
        if obs.observed_at > recorded_at:
            exclusions.append("source_observed_in_future")
        if obs.ingested_at > recorded_at:
            exclusions.append("source_ingested_in_future")
        if obs.published_at and obs.published_at > recorded_at:
            exclusions.append("source_published_in_future")
        if exclusions:
            identity_state = "excluded_future"
        self.db.execute(
            """
            INSERT OR IGNORE INTO observation_provenance_assertions(
                definition_version,observation_id,recorded_at,source_observed_at,source_ingested_at,
                source_published_at,route_kind,origin_identity_state,origin_platform,origin_actor,
                origin_item_url,origin_root_key,transport_platform,transport_source,local_collector,
                evidence_basis,temporal_exclusion_reason,decision_eligible,affects
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'none')
            """,
            (
                self.OBSERVATION_PROVENANCE_VERSION, observation_id, iso(recorded_at),
                iso(obs.observed_at), iso(obs.ingested_at), iso(obs.published_at) if obs.published_at else None,
                route_kind, identity_state, platform, actor, safe_url, origin_root_key,
                transport_platform, transport_source, local_collector, evidence_basis,
                ";".join(exclusions) or None,
            ),
        )
        return self.db.execute("SELECT changes()").fetchone()[0] > 0

    def start_telegram_external_handoff(
        self,
        *,
        catalog_entity_id: str,
        external_url_safe: str,
        external_url_fingerprint: str,
        submitted_via: str = "local_web",
    ) -> int:
        """Persist a denominator row before any external network request is made."""
        with self._lock, self.db:
            cur = self.db.execute(
                """
                INSERT INTO telegram_external_handoff_attempts(
                    definition_version,received_at,catalog_entity_id,external_url_safe,
                    external_url_fingerprint,submitted_via,decision_eligible,affects
                ) VALUES(?,?,?,?,?,?,0,'investigation_only')
                """,
                (
                    self.TELEGRAM_EXTERNAL_HANDOFF_VERSION,
                    iso(),
                    str(catalog_entity_id or "")[:128],
                    str(external_url_safe or "")[:2048],
                    str(external_url_fingerprint or "")[:64],
                    str(submitted_via or "local_web")[:64],
                ),
            )
            return int(cur.lastrowid)

    def finish_telegram_external_handoff(
        self,
        attempt_id: int,
        *,
        status: str,
        reason: str,
        final_external_url_safe: str = "",
        observation_id: int | None = None,
        event_id: int | None = None,
        http_status: int | None = None,
    ) -> bool:
        allowed = {"verified", "duplicate", "zero_yield", "rejected", "error"}
        if status not in allowed:
            raise ValueError("unsupported telegram external handoff result")
        with self._lock, self.db:
            cur = self.db.execute(
                """
                INSERT OR IGNORE INTO telegram_external_handoff_results(
                    definition_version,attempt_id,recorded_at,status,reason,
                    final_external_url_safe,observation_id,event_id,http_status,
                    decision_eligible,affects
                ) VALUES(?,?,?,?,?,?,?,?,?,0,'investigation_only')
                """,
                (
                    self.TELEGRAM_EXTERNAL_HANDOFF_VERSION,
                    int(attempt_id),
                    iso(),
                    status,
                    str(reason or "")[:300],
                    str(final_external_url_safe or "")[:2048],
                    observation_id,
                    event_id,
                    http_status,
                ),
            )
            return cur.rowcount > 0

    def telegram_external_handoff_summary(self, *, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(100, int(limit)))
        with self._lock:
            counts = {
                str(row["status"]): int(row["value"] or 0)
                for row in self.db.execute(
                    "SELECT status,COUNT(*) AS value FROM telegram_external_handoff_results GROUP BY status"
                )
            }
            attempts = int(
                self.db.execute("SELECT COUNT(*) FROM telegram_external_handoff_attempts").fetchone()[0]
            )
            rows = self.db.execute(
                """
                SELECT a.id,a.received_at,a.catalog_entity_id,a.external_url_safe,
                       r.recorded_at,r.status,r.reason,r.final_external_url_safe,
                       r.observation_id,r.event_id,r.http_status
                FROM telegram_external_handoff_attempts a
                LEFT JOIN telegram_external_handoff_results r ON r.attempt_id=a.id
                ORDER BY a.id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            items.append(
                {
                    "attempt_id": int(row["id"]),
                    "received_at": row["received_at"],
                    "catalog_entity_id": row["catalog_entity_id"],
                    "external_url": row["final_external_url_safe"] or row["external_url_safe"] or None,
                    "finished_at": row["recorded_at"],
                    "status": row["status"] or "received",
                    "reason": row["reason"] or "network_request_not_finished",
                    "observation_id": row["observation_id"],
                    "event_id": row["event_id"],
                    "http_status": row["http_status"],
                    "decision_eligible": False,
                    "affects": "investigation_only",
                }
            )
        completed = sum(counts.values())
        return {
            "version": self.TELEGRAM_EXTERNAL_HANDOFF_VERSION,
            "status": "collecting" if attempts else "not_observed",
            "summary": {
                "attempts": attempts,
                "completed": completed,
                "pending": max(0, attempts - completed),
                **{name: counts.get(name, 0) for name in sorted(
                    {"verified", "duplicate", "zero_yield", "rejected", "error"}
                )},
            },
            "items": items,
            "telegram_message_content_stored": False,
            "decision_eligible": False,
            "affects": "investigation_only",
        }

    @classmethod
    def _source_item_key(cls, obs: Observation) -> tuple[str, str] | None:
        source = obs.source.strip().casefold()
        if obs.source_item_id.strip():
            identity_mode = "explicit_source_item_id"
            identity = obs.source_item_id.strip()
        else:
            identity_mode = "exact_safe_url"
            identity = cls._revision_safe_url(obs.url)
        if not source or not identity:
            return None
        material = f"{cls.SOURCE_ITEM_REVISION_VERSION}\n{source}\n{identity_mode}\n{identity}"
        return hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest(), identity_mode

    @staticmethod
    def _revision_signal(obs: Observation) -> tuple[str, str, str, str | None]:
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        requested = str(raw.get("source_item_state") or "present").strip().lower()
        evidence = str(raw.get("source_item_state_evidence") or "").strip().lower() or None
        allowed_evidence = {
            "platform_deleted_marker", "publisher_deleted_marker", "publisher_retraction_marker",
            "publisher_correction_marker", "platform_restored_marker", "http_410", "access_denied",
            "api_revision",
        }
        if evidence not in allowed_evidence:
            evidence = None
        if requested == "deleted" and evidence in {"platform_deleted_marker", "publisher_deleted_marker"}:
            return "deleted", "none", "explicit_deleted", evidence
        if requested == "retracted" and evidence == "publisher_retraction_marker":
            return "retracted", "retraction", "explicit_retracted", evidence
        if requested == "correction" and evidence == "publisher_correction_marker":
            return "present", "correction", "explicit_correction", evidence
        if requested == "access_lost" and evidence in {"http_410", "access_denied"}:
            return "access_lost", "none", "access_lost", evidence
        if requested in {"deleted", "retracted", "access_lost"}:
            return "unknown", "none", "unverified_state_signal", evidence
        if requested == "restored":
            return "present", "none", "restored", evidence
        return "present", "none", "present", evidence

    def _source_item_anchor_locked(self, obs: Observation) -> int | None:
        identity = self._source_item_key(obs)
        if identity is None:
            return None
        key, _ = identity
        row = self.db.execute(
            "SELECT anchor_observation_id FROM source_item_revisions "
            "WHERE definition_version=? AND source_item_key=? ORDER BY sequence_no DESC LIMIT 1",
            (self.SOURCE_ITEM_REVISION_VERSION, key),
        ).fetchone()
        if row is not None and row["anchor_observation_id"] is not None:
            return int(row["anchor_observation_id"])
        if not obs.source_item_id.strip():
            return None
        row = self.db.execute(
            "SELECT id FROM observations WHERE fingerprint=?",
            (self._fingerprint(obs),),
        ).fetchone()
        if row is None:
            row = self.db.execute(
                "SELECT id FROM observations WHERE fingerprint=?",
                (self._legacy_fingerprint(obs),),
            ).fetchone()
        if row is None and obs.url.strip():
            row = self.db.execute(
                "SELECT id FROM observations WHERE source=? AND url=? ORDER BY id LIMIT 1",
                (obs.source, obs.url),
            ).fetchone()
        return int(row["id"]) if row is not None else None

    def _claim_relation_target_by_url_locked(
        self,
        safe_target_url: str,
        *,
        before_revision_id: int,
        source_item_key: str,
        recorded_at: str,
    ) -> tuple[int | None, int]:
        matches: dict[str, sqlite3.Row] = {}
        for row in self.db.execute(
            """
            SELECT id,source_item_key,sequence_no,snapshot_json
            FROM source_item_revisions
            WHERE definition_version=? AND id<>? AND recorded_at<=?
              AND temporal_exclusion_reason IS NULL
            ORDER BY recorded_at DESC,id DESC
            """,
            (self.SOURCE_ITEM_REVISION_VERSION, before_revision_id, recorded_at),
        ):
            if str(row["source_item_key"]) == source_item_key:
                continue
            snapshot = self._json_object(row["snapshot_json"])
            if self._revision_safe_url(snapshot.get("url")) != safe_target_url:
                continue
            matches.setdefault(str(row["source_item_key"]), row)
        if len(matches) != 1:
            return None, len(matches)
        return int(next(iter(matches.values()))["id"]), 1

    def _insert_claim_relation_locked(
        self,
        *,
        revision: sqlite3.Row,
        relation_type: str,
        relation_scope: str,
        target_revision_id: int | None,
        resolution_status: str,
        target_url_fingerprint: str,
        target_match_count: int,
        evidence_basis: str,
        temporal_exclusion_reason: str | None = None,
    ) -> None:
        edge_material = "\n".join(
            [
                self.EVENT_CLAIM_RELATION_VERSION,
                str(revision["id"]),
                relation_type,
                str(target_revision_id or "UNRESOLVED"),
                resolution_status,
                target_url_fingerprint,
            ]
        )
        edge_fingerprint = hashlib.sha256(
            edge_material.encode("utf-8", errors="ignore")
        ).hexdigest()
        self.db.execute(
            """
            INSERT OR IGNORE INTO event_claim_relations(
                definition_version,edge_fingerprint,source_revision_id,target_revision_id,
                relation_type,relation_scope,resolution_status,target_url_fingerprint,
                target_match_count,evidence_basis,recorded_at,source_observed_at,
                source_ingested_at,temporal_exclusion_reason,decision_eligible,affects
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'none')
            """,
            (
                self.EVENT_CLAIM_RELATION_VERSION,
                edge_fingerprint,
                int(revision["id"]),
                target_revision_id,
                relation_type,
                relation_scope,
                resolution_status,
                target_url_fingerprint,
                target_match_count,
                evidence_basis,
                iso(),
                revision["capture_observed_at"],
                revision["capture_ingested_at"],
                temporal_exclusion_reason or revision["temporal_exclusion_reason"],
            ),
        )

    def _record_claim_relations_locked(self, obs: Observation, revision_id: int) -> None:
        registration = self.db.execute(
            "SELECT registered_at FROM event_claim_relation_registrations WHERE definition_version=?",
            (self.EVENT_CLAIM_RELATION_VERSION,),
        ).fetchone()
        revision = self.db.execute(
            "SELECT * FROM source_item_revisions WHERE id=? AND definition_version=?",
            (revision_id, self.SOURCE_ITEM_REVISION_VERSION),
        ).fetchone()
        if (
            registration is None
            or revision is None
            or parse_time(revision["recorded_at"]) < parse_time(registration["registered_at"])
            or parse_time(revision["capture_ingested_at"]) < parse_time(registration["registered_at"])
        ):
            return
        exclusion = str(revision["temporal_exclusion_reason"] or "")
        previous_revision_id = (
            int(revision["previous_revision_id"])
            if revision["previous_revision_id"] is not None else None
        )
        previous_exclusion = ""
        if previous_revision_id is not None:
            previous = self.db.execute(
                "SELECT temporal_exclusion_reason FROM source_item_revisions WHERE id=?",
                (previous_revision_id,),
            ).fetchone()
            previous_exclusion = str(previous["temporal_exclusion_reason"] or "") if previous else ""
        if previous_revision_id is not None:
            relation_exclusion = exclusion or previous_exclusion
            self._insert_claim_relation_locked(
                revision=revision,
                relation_type="supersedes",
                relation_scope="same_item_version",
                target_revision_id=None if relation_exclusion else previous_revision_id,
                resolution_status="excluded_temporal" if relation_exclusion else "resolved",
                target_url_fingerprint="",
                target_match_count=0 if relation_exclusion else 1,
                evidence_basis="stable_source_item_sequence",
                temporal_exclusion_reason=relation_exclusion or None,
            )
        relation_type = {
            "explicit_correction": "corrects",
            "explicit_retracted": "retracts",
        }.get(str(revision["revision_kind"]))
        if relation_type is None:
            return
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        raw_target = raw.get("claim_target_url")
        safe_target_url = self._revision_safe_url(raw_target) if raw_target else ""
        target_fingerprint = (
            hashlib.sha256(safe_target_url.encode("utf-8", errors="ignore")).hexdigest()
            if safe_target_url else ""
        )
        if exclusion:
            target_revision_id = None
            match_count = 0
            resolution = "excluded_temporal"
            scope = "cross_item_exact_url" if raw_target else "same_item_version"
        elif raw_target and not safe_target_url:
            target_revision_id = None
            match_count = 0
            resolution = "invalid_target_url"
            scope = "cross_item_exact_url"
        elif safe_target_url:
            current_snapshot = self._json_object(revision["snapshot_json"])
            if (
                previous_revision_id is not None
                and self._revision_safe_url(current_snapshot.get("url")) == safe_target_url
            ):
                target_revision_id = None if previous_exclusion else previous_revision_id
                match_count = 0 if previous_exclusion else 1
                resolution = "excluded_temporal" if previous_exclusion else "resolved"
                scope = "same_item_version"
            else:
                target_revision_id, match_count = self._claim_relation_target_by_url_locked(
                    safe_target_url,
                    before_revision_id=revision_id,
                    source_item_key=str(revision["source_item_key"]),
                    recorded_at=str(revision["recorded_at"]),
                )
                resolution = (
                    "resolved" if target_revision_id is not None
                    else "target_not_found" if match_count == 0
                    else "ambiguous_target"
                )
                scope = "cross_item_exact_url"
        else:
            target_revision_id = previous_revision_id
            match_count = int(previous_revision_id is not None)
            resolution = "resolved" if previous_revision_id is not None else "target_not_found"
            scope = "same_item_version"
        self._insert_claim_relation_locked(
            revision=revision,
            relation_type=relation_type,
            relation_scope=scope,
            target_revision_id=target_revision_id,
            resolution_status=resolution,
            target_url_fingerprint=target_fingerprint,
            target_match_count=match_count,
            evidence_basis=str(revision["tombstone_evidence_code"] or "publisher_state_marker"),
            temporal_exclusion_reason=(previous_exclusion or None)
            if resolution == "excluded_temporal" and not exclusion else None,
        )

    def _record_source_item_revision_locked(self, obs: Observation, observation_id: int) -> int | None:
        identity = self._source_item_key(obs)
        if identity is None:
            return None
        key, identity_mode = identity
        registration = self.db.execute(
            "SELECT registered_at FROM source_item_revision_registrations WHERE definition_version=?",
            (self.SOURCE_ITEM_REVISION_VERSION,),
        ).fetchone()
        if registration is None or obs.ingested_at < parse_time(registration["registered_at"]):
            return None
        previous = self.db.execute(
            "SELECT * FROM source_item_revisions WHERE definition_version=? AND source_item_key=? "
            "ORDER BY sequence_no DESC LIMIT 1",
            (self.SOURCE_ITEM_REVISION_VERSION, key),
        ).fetchone()
        local_state, semantic_signal, requested_kind, evidence = self._revision_signal(obs)
        raw = obs.raw if isinstance(obs.raw, dict) else {}
        explicit_cross_item_retraction = (
            requested_kind == "explicit_retracted" and bool(raw.get("claim_target_url"))
        )
        if (
            previous is None
            and local_state in {"deleted", "retracted", "access_lost", "unknown"}
            and not explicit_cross_item_retraction
        ):
            anchor_row = self.db.execute(
                "SELECT ingested_at FROM observations WHERE id=?", (observation_id,)
            ).fetchone()
            if (
                anchor_row is None
                or parse_time(anchor_row["ingested_at"]) >= parse_time(registration["registered_at"])
            ):
                return None
        safe_url = self._revision_safe_url(obs.url)
        snapshot = {
            "title": str(obs.title or "")[:500],
            "text": str(obs.text or "")[:20_000],
            "url": safe_url,
            "author": str(obs.author or "")[:300],
            "published_at": iso(obs.published_at) if obs.published_at else None,
        }
        digest_material = self._json(
            {"snapshot": snapshot, "local_state": local_state, "semantic_signal": semantic_signal}
        )
        content_sha256 = hashlib.sha256(digest_material.encode("utf-8", errors="ignore")).hexdigest()
        if (
            previous is not None
            and previous["content_sha256"] == content_sha256
            and previous["local_state"] == local_state
            and previous["semantic_signal"] == semantic_signal
        ):
            return None
        prior_snapshot = self._json_object(previous["snapshot_json"]) if previous is not None else {}
        changed_fields = [
            field for field in snapshot if prior_snapshot.get(field) != snapshot.get(field)
        ]
        if previous is None:
            revision_kind = requested_kind if requested_kind != "present" else "baseline"
            changed_fields = ["source_item_state"] if revision_kind != "baseline" else ["initial_capture"]
            anchor_observation_id = observation_id
            sequence_no = 1
            previous_id = None
        else:
            prior_state = str(previous["local_state"] or "unknown")
            if requested_kind in {
                "explicit_deleted", "explicit_retracted", "explicit_correction",
                "access_lost", "unverified_state_signal",
            }:
                revision_kind = requested_kind
            elif prior_state in {"deleted", "retracted", "access_lost", "unknown"} and local_state == "present":
                revision_kind = "restored"
            else:
                revision_kind = "content_edit"
            if not changed_fields and (prior_state != local_state or previous["semantic_signal"] != semantic_signal):
                changed_fields = ["source_item_state"]
            anchor_observation_id = int(previous["anchor_observation_id"] or observation_id)
            sequence_no = int(previous["sequence_no"]) + 1
            previous_id = int(previous["id"])
        recorded_at = utcnow()
        exclusions = []
        if obs.observed_at > recorded_at:
            exclusions.append("capture_observed_in_future")
        if obs.ingested_at > recorded_at:
            exclusions.append("capture_ingested_in_future")
        if obs.observed_at > obs.ingested_at:
            exclusions.append("capture_observed_after_ingested")
        reported_revision_at = None
        if raw.get("source_reported_revision_at"):
            try:
                parsed_revision_at = parse_time(raw["source_reported_revision_at"])
                reported_revision_at = iso(parsed_revision_at)
                if parsed_revision_at > recorded_at:
                    exclusions.append("source_reported_revision_in_future")
            except (TypeError, ValueError):
                exclusions.append("source_reported_revision_time_invalid")
        if obs.published_at and obs.published_at > recorded_at:
            exclusions.append("source_published_in_future")
        if raw.get("stale_first_observation") is True:
            exclusions.append("stale_first_observation")
        if raw.get("published_time_in_future") is True:
            exclusions.append("published_time_in_future")
        edge_material = "\n".join(
            [
                self.SOURCE_ITEM_REVISION_VERSION, key, str(previous_id or "ROOT"), revision_kind,
                content_sha256, evidence or "",
            ]
        )
        edge_fingerprint = hashlib.sha256(edge_material.encode("utf-8", errors="ignore")).hexdigest()
        cursor = self.db.execute(
            """
            INSERT OR IGNORE INTO source_item_revisions(
                definition_version,source_item_key,sequence_no,previous_revision_id,edge_fingerprint,
                anchor_observation_id,capture_observation_id,recorded_at,capture_observed_at,
                capture_ingested_at,source_published_at,source_reported_revision_at,source,source_kind,
                identity_mode,revision_kind,local_state,semantic_signal,content_sha256,snapshot_json,
                changed_fields_json,availability_proof,tombstone_evidence_code,temporal_exclusion_reason,
                decision_eligible,affects
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'none')
            """,
            (
                self.SOURCE_ITEM_REVISION_VERSION, key, sequence_no, previous_id, edge_fingerprint,
                anchor_observation_id, observation_id, iso(recorded_at), iso(obs.observed_at),
                iso(obs.ingested_at), iso(obs.published_at) if obs.published_at else None,
                reported_revision_at, obs.source, obs.source_kind, identity_mode, revision_kind,
                local_state, semantic_signal, content_sha256, self._bounded_json(snapshot, 24_000),
                self._json(changed_fields), obs.availability_proof, evidence,
                ";".join(exclusions) or None,
            ),
        )
        if cursor.rowcount != 1:
            return None
        revision_id = int(cursor.lastrowid)
        self._record_claim_relations_locked(obs, revision_id)
        return revision_id

    def add_observation(self, obs: Observation) -> tuple[int, bool]:
        fp = self._fingerprint(obs)
        with self._lock, self.db:
            anchor = self._source_item_anchor_locked(obs) if obs.source_item_id.strip() else None
            if anchor is not None:
                self._record_source_item_revision_locked(obs, anchor)
                return anchor, False
            try:
                stored_raw = dict(obs.raw) if isinstance(obs.raw, dict) else {}
                stored_raw.pop("claim_target_url", None)
                if isinstance(stored_raw.get("browser"), dict):
                    stored_raw["browser"] = dict(stored_raw["browser"])
                    stored_raw["browser"].pop("claim_target_url", None)
                cur = self.db.execute(
                    """
                    INSERT INTO observations(
                        fingerprint,source,source_kind,title,text,url,author,published_at,
                        observed_at,ingested_at,availability_proof,role,source_item_id,capture_phase,raw_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        fp,
                        obs.source,
                        obs.source_kind,
                        obs.title,
                        obs.text,
                        obs.url,
                        obs.author,
                        iso(obs.published_at) if obs.published_at else None,
                        iso(obs.observed_at),
                        iso(obs.ingested_at),
                        obs.availability_proof,
                        obs.role,
                        obs.source_item_id,
                        obs.capture_phase,
                        self._json(stored_raw),
                    ),
                )
                observation_id = int(cur.lastrowid)
                self._record_source_item_revision_locked(obs, observation_id)
                self._record_observation_provenance_locked(obs, observation_id)
                return observation_id, True
            except sqlite3.IntegrityError:
                row = self.db.execute("SELECT id FROM observations WHERE fingerprint=?", (fp,)).fetchone()
                observation_id = int(row["id"])
                self._record_source_item_revision_locked(obs, observation_id)
                return observation_id, False

    def observation(self, observation_id: int) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM observations WHERE id=?", (observation_id,)).fetchone()
        if row is None:
            raise KeyError(observation_id)
        return row

    def observation_id_for(self, obs: Observation) -> int | None:
        with self._lock:
            row = self.db.execute(
                "SELECT id FROM observations WHERE fingerprint=?",
                (self._fingerprint(obs),),
            ).fetchone()
            if row is None:
                anchor = self._source_item_anchor_locked(obs)
                return anchor
        return int(row["id"]) if row is not None else None

    def recent_observations(self, minutes: int = 120, limit: int = 1000) -> list[sqlite3.Row]:
        since = iso(utcnow() - timedelta(minutes=minutes))
        return list(
            self.db.execute(
                "SELECT * FROM observations WHERE observed_at>=? ORDER BY observed_at DESC LIMIT ?",
                (since, limit),
            )
        )

    def recent_browser_observations(self, minutes: int = 180, limit: int = 5000) -> list[sqlite3.Row]:
        now = utcnow()
        return list(
            self.db.execute(
                """
                SELECT * FROM observations
                WHERE availability_proof='local_receive'
                  AND source LIKE 'browser:%'
                  AND observed_at>=? AND observed_at<=?
                ORDER BY observed_at DESC LIMIT ?
                """,
                (iso(now - timedelta(minutes=minutes)), iso(now), limit),
            )
        )

    def create_event(
        self,
        title: str,
        aliases: Iterable[str],
        attention: float,
        first_seen_at=None,
        *,
        topic: str = "unknown",
    ) -> int:
        seen = first_seen_at or utcnow()
        normalized_topic = str(topic or "unknown").strip().lower()
        if normalized_topic not in {
            "political_public_figure", "celebrity_entertainment", "animals_internet_culture",
            "sports", "ai_tech_gaming", "crypto_native", "other", "unknown",
        }:
            normalized_topic = "unknown"
        with self._lock, self.db:
            cur = self.db.execute(
                "INSERT INTO events(title,aliases_json,attention,first_seen_at,last_seen_at,status,topic) "
                "VALUES(?,?,?,?,?,'active',?)",
                (title, self._json(sorted(set(aliases))), attention, iso(seen), iso(seen), normalized_topic),
            )
            return int(cur.lastrowid)

    def update_event(
        self,
        event_id: int,
        *,
        title: str,
        aliases: Iterable[str],
        attention: float,
        seen_at=None,
        trigger_observation_id: int | None = None,
    ) -> None:
        with self._lock, self.db:
            self.db.execute(
                "UPDATE events SET title=?,aliases_json=?,attention=?,last_seen_at=? WHERE id=?",
                (title, self._json(sorted(set(aliases))), attention, iso(seen_at or utcnow()), event_id),
            )
            if trigger_observation_id is not None:
                self._record_event_attention_point_locked(
                    event_id,
                    trigger_observation_id,
                    attention,
                )
                self._record_event_claim_assessment_locked(event_id, trigger_observation_id)

    @staticmethod
    def _claim_confidence(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None

    def _record_event_claim_assessment_locked(self, event_id: int, observation_id: int) -> bool:
        assessed_at = utcnow()
        trigger = self.db.execute(
            """
            SELECT o.* FROM observations o
            JOIN event_observations eo ON eo.observation_id=o.id
            WHERE eo.event_id=? AND o.id=?
            """,
            (event_id, observation_id),
        ).fetchone()
        if trigger is None:
            return False
        try:
            raw = json.loads(trigger["raw_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        role = str(trigger["role"] or "").strip().lower() or "unknown"
        source = str(raw.get("agent_task") or "").strip().lower()
        exclusion_reason = None
        if parse_time(trigger["observed_at"]) > assessed_at:
            exclusion_reason = "trigger_observed_in_future"
        elif parse_time(trigger["ingested_at"]) > assessed_at:
            exclusion_reason = "trigger_ingested_in_future"
        if exclusion_reason:
            status = "excluded_future"
            basis = "local_temporal_exclusion"
        elif role == "promotion":
            status = "promotion"
            basis = "deterministic_evidence_role"
        else:
            proposed = str(raw.get("claim_status") or "").strip().lower().replace("-", "_").replace(" ", "_")
            if source in {"trend_scout", "token_context"} and proposed in self.EVENT_CLAIM_STATUSES - {"excluded_future"}:
                status = proposed
                basis = "agent_structured_assessment"
            else:
                status = "unassessed"
                basis = "no_structured_fact_assessment"
        scores = [
            self._claim_confidence(raw.get(name)) if basis == "agent_structured_assessment" else None
            for name in (
                "factual_confidence", "source_identity_confidence", "attention_confidence",
                "meme_catalyst_strength", "correction_risk",
            )
        ]
        previous = self.db.execute(
            "SELECT id FROM event_claim_assessments WHERE event_id=? ORDER BY id DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        before = self.db.total_changes
        self.db.execute(
            """
            INSERT OR IGNORE INTO event_claim_assessments(
                definition_version,event_id,observation_id,previous_assessment_id,assessed_at,
                claim_status,factual_confidence,source_identity_confidence,attention_confidence,
                meme_catalyst_strength,correction_risk,assessment_source,assessment_basis,
                trigger_role,trigger_decision_eligible,exclusion_reason
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                self.EVENT_CLAIM_ASSESSMENT_VERSION,
                event_id,
                observation_id,
                int(previous["id"]) if previous else None,
                iso(assessed_at),
                status,
                *scores,
                source or "local_observation",
                basis,
                role,
                int(role in {"feature", "confirmation"} and exclusion_reason is None),
                exclusion_reason,
            ),
        )
        return self.db.total_changes > before

    def _record_event_attention_point_locked(
        self,
        event_id: int,
        observation_id: int,
        attention: float,
    ) -> bool:
        recorded_at = utcnow()
        trigger = self.db.execute(
            """
            SELECT o.* FROM observations o
            JOIN event_observations eo ON eo.observation_id=o.id
            WHERE eo.event_id=? AND o.id=?
            """,
            (event_id, observation_id),
        ).fetchone()
        if trigger is None:
            return False
        exclusion_reason = None
        if parse_time(trigger["observed_at"]) > recorded_at:
            exclusion_reason = "trigger_observed_in_future"
        elif parse_time(trigger["ingested_at"]) > recorded_at:
            exclusion_reason = "trigger_ingested_in_future"
        trigger_role = str(trigger["role"] or "").lower()
        trigger_eligible = exclusion_reason is None and trigger_role in {"feature", "confirmation"}
        counts = self.db.execute(
            """
            SELECT
                SUM(CASE WHEN o.role IN ('feature','confirmation')
                              AND o.observed_at<=? AND o.ingested_at<=? THEN 1 ELSE 0 END) AS eligible_count,
                SUM(CASE WHEN o.role NOT IN ('feature','confirmation')
                              OR o.observed_at>? OR o.ingested_at>? THEN 1 ELSE 0 END) AS context_count
            FROM observations o
            JOIN event_observations eo ON eo.observation_id=o.id
            WHERE eo.event_id=?
            """,
            (iso(recorded_at), iso(recorded_at), iso(recorded_at), iso(recorded_at), event_id),
        ).fetchone()
        before = self.db.total_changes
        self.db.execute(
            """
            INSERT OR IGNORE INTO event_attention_points(
                definition_version,event_id,observation_id,recorded_at,attention,
                eligible_observation_count,context_observation_count,trigger_role,
                trigger_decision_eligible,exclusion_reason,coverage_mode
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                self.EVENT_ATTENTION_TRAJECTORY_VERSION,
                event_id,
                observation_id,
                iso(recorded_at),
                float(attention),
                int(counts["eligible_count"] or 0),
                int(counts["context_count"] or 0),
                trigger_role or "unknown",
                int(trigger_eligible),
                exclusion_reason,
                "local_new_observation_arrivals_only",
            ),
        )
        return self.db.total_changes > before

    def link_event_observation(self, event_id: int, observation_id: int) -> None:
        with self._lock, self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO event_observations(event_id,observation_id) VALUES(?,?)",
                (event_id, observation_id),
            )

    def event_for_observation(self, observation_id: int) -> int | None:
        row = self.db.execute(
            "SELECT event_id FROM event_observations WHERE observation_id=? ORDER BY event_id LIMIT 1",
            (observation_id,),
        ).fetchone()
        return int(row["event_id"]) if row else None

    def get_event(self, event_id: int) -> EventView:
        row = self.db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise KeyError(event_id)
        return EventView(
            id=int(row["id"]),
            title=row["title"],
            aliases=json.loads(row["aliases_json"]),
            attention=float(row["attention"]),
            first_seen_at=parse_time(row["first_seen_at"]),
            last_seen_at=parse_time(row["last_seen_at"]),
            status=row["status"],
            topic=row["topic"],
        )

    def active_events(self, minutes: int = 180, limit: int = 100) -> list[EventView]:
        since = iso(utcnow() - timedelta(minutes=minutes))
        rows = self.db.execute(
            "SELECT * FROM events WHERE status='active' AND last_seen_at>=? ORDER BY attention DESC,last_seen_at DESC LIMIT ?",
            (since, limit),
        )
        return [
            EventView(
                id=int(r["id"]), title=r["title"], aliases=json.loads(r["aliases_json"]),
                attention=float(r["attention"]), first_seen_at=parse_time(r["first_seen_at"]),
                last_seen_at=parse_time(r["last_seen_at"]), status=r["status"], topic=r["topic"],
            )
            for r in rows
        ]

    def event_observations(self, event_id: int) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                """
                SELECT o.* FROM observations o
                JOIN event_observations eo ON eo.observation_id=o.id
                WHERE eo.event_id=? ORDER BY o.observed_at ASC
                """,
                (event_id,),
            )
        )

    def upsert_token(self, token: TokenCandidate, seen_at=None) -> bool:
        now = seen_at or token.first_seen_at or utcnow()
        if token.first_seen_at is None:
            token.first_seen_at = parse_time(now)
        with self._lock, self.db:
            existed = self.db.execute("SELECT 1 FROM tokens WHERE token_id=?", (token.token_id,)).fetchone() is not None
            self.db.execute(
                """
                INSERT INTO tokens(token_id,chain,address,name,symbol,created_at,source,url,social_urls_json,raw_json,first_seen_at,last_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(token_id) DO UPDATE SET
                    name=excluded.name,symbol=excluded.symbol,source=excluded.source,url=excluded.url,
                    social_urls_json=excluded.social_urls_json,raw_json=excluded.raw_json,last_seen_at=excluded.last_seen_at,
                    created_at=COALESCE(tokens.created_at,excluded.created_at)
                """,
                (
                    token.token_id, token.chain.lower(), token.address, token.name, token.symbol,
                    iso(token.created_at) if token.created_at else None, token.source, token.url,
                    self._json(token.social_urls), self._json(token.raw), iso(now), iso(now),
                ),
            )
            raw_links = token.raw.get("token_source_links") if isinstance(token.raw, dict) else None
            if isinstance(raw_links, list):
                for link in raw_links[:100]:
                    if isinstance(link, Mapping) and str(link.get("token_id") or "") == token.token_id:
                        self._upsert_token_source_link_locked(link, observed_at=now)
            if token.chain.lower() == "solana":
                self._enqueue_token_detail_hydration_locked(token.chain, token.address, enqueued_at=now)
            return not existed

    def _enqueue_token_detail_hydration_locked(self, chain: str, address: str, *, enqueued_at=None) -> None:
        normalized_chain = str(chain).strip().lower()
        normalized_address = str(address).strip()
        if not normalized_chain or not normalized_address:
            return
        self.db.execute(
            """
            INSERT INTO token_detail_hydration(
                token_id,chain,address,status,attempts,enqueued_at,next_attempt_at,last_error
            ) VALUES(?,?,?,'pending',0,?,?, '')
            ON CONFLICT(token_id) DO UPDATE SET
                chain=excluded.chain,address=excluded.address
            """,
            (
                f"{normalized_chain}:{normalized_address}", normalized_chain, normalized_address,
                iso(parse_time(enqueued_at or utcnow())), iso(parse_time(enqueued_at or utcnow())),
            ),
        )

    def enqueue_token_detail_hydration(self, chain: str, address: str, *, enqueued_at=None) -> None:
        with self._lock, self.db:
            self._enqueue_token_detail_hydration_locked(chain, address, enqueued_at=enqueued_at)

    def due_token_detail_hydrations(self, *, limit: int = 30, now=None) -> list[sqlite3.Row]:
        due_at = iso(parse_time(now or utcnow()))
        with self._lock:
            return list(
                self.db.execute(
                    """
                    SELECT * FROM token_detail_hydration
                    WHERE status IN ('pending','no_pair','error')
                      AND (next_attempt_at IS NULL OR next_attempt_at<=?)
                    ORDER BY enqueued_at,attempts,token_id LIMIT ?
                    """,
                    (due_at, max(0, min(300, int(limit)))),
                )
            )

    def mark_token_detail_hydration(
        self,
        token_id: str,
        status: str,
        *,
        error: str = "",
        now=None,
    ) -> None:
        if status not in {"hydrated", "no_pair", "error"}:
            raise ValueError("invalid token detail hydration status")
        attempted_at = parse_time(now or utcnow())
        with self._lock, self.db:
            row = self.db.execute(
                "SELECT attempts FROM token_detail_hydration WHERE token_id=?", (str(token_id),)
            ).fetchone()
            if row is None:
                return
            attempts = int(row["attempts"] or 0) + 1
            if status == "hydrated":
                next_attempt_at = None
            elif status == "error":
                next_attempt_at = iso(attempted_at + timedelta(minutes=5))
            else:
                retry_minutes = (5, 30, 120, 360)[min(attempts - 1, 3)]
                next_attempt_at = iso(attempted_at + timedelta(minutes=retry_minutes))
            self.db.execute(
                """
                UPDATE token_detail_hydration
                SET status=?,attempts=?,last_attempt_at=?,next_attempt_at=?,
                    hydrated_at=CASE WHEN ?='hydrated' THEN ? ELSE hydrated_at END,last_error=?
                WHERE token_id=?
                """,
                (
                    status, attempts, iso(attempted_at), next_attempt_at,
                    status, iso(attempted_at), str(error or "")[:500], str(token_id),
                ),
            )

    def token_detail_hydration(self, token_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM token_detail_hydration WHERE token_id=?", (str(token_id),)
        ).fetchone()

    def add_token_context_admission_attempt(
        self,
        token_id: str,
        *,
        outcome: str,
        reason: str,
        trigger: Mapping[str, Any] | None,
        snapshot_observed_at: Any,
        momentum_score: float,
        next_eligible_at: Any = None,
        quota_day: str,
        daily_call_limit: int,
        calls_used_before: int,
        daily_token_budget: int,
        tokens_used_before: int,
        token_reserve_per_call: int,
        evaluated_at: Any = None,
    ) -> int:
        trigger = trigger if isinstance(trigger, Mapping) else {}
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO token_context_admission_attempts(
                    version,token_id,evaluated_at,outcome,reason,trigger_kind,
                    trigger_priority,platform,entity_id,event_id,decision_id,
                    snapshot_observed_at,momentum_score,next_eligible_at,quota_day,
                    daily_call_limit,calls_used_before,daily_token_budget,
                    tokens_used_before,token_reserve_per_call
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    self.TOKEN_CONTEXT_ADMISSION_VERSION,
                    str(token_id),
                    iso(parse_time(evaluated_at or utcnow())),
                    str(outcome)[:40],
                    str(reason)[:120],
                    str(trigger.get("kind") or "")[:120],
                    int(trigger["priority"]) if trigger.get("priority") is not None else None,
                    str(trigger.get("platform") or "")[:80],
                    str(trigger.get("entity_id") or "")[:160],
                    int(trigger["event_id"]) if trigger.get("event_id") is not None else None,
                    int(trigger["decision_id"]) if trigger.get("decision_id") is not None else None,
                    iso(parse_time(snapshot_observed_at)),
                    float(momentum_score),
                    iso(parse_time(next_eligible_at)) if next_eligible_at else None,
                    str(quota_day)[:20],
                    max(0, int(daily_call_limit)),
                    max(0, int(calls_used_before)),
                    max(0, int(daily_token_budget)),
                    max(0, int(tokens_used_before)),
                    max(0, int(token_reserve_per_call)),
                ),
            )
            return int(cursor.lastrowid)

    def token_context_admission_attempts(
        self, token_id: str, *, limit: int = 20
    ) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                """
                SELECT * FROM token_context_admission_attempts
                WHERE token_id=? ORDER BY evaluated_at DESC,id DESC LIMIT ?
                """,
                (str(token_id), max(1, min(100, int(limit)))),
            )
        )

    @staticmethod
    def token_context_admission_summary_from_connection(
        connection: sqlite3.Connection, *, lookback_days: int = 90
    ) -> dict[str, Any]:
        empty = {
            "status": "not_observed",
            "version": Store.TOKEN_CONTEXT_ADMISSION_VERSION,
            "items": [],
            "reasons": [],
            "summary": {
                "attempts": 0,
                "trigger_qualified_attempts": 0,
                "admitted": 0,
                "skipped": 0,
                "admission_rate": None,
            },
            "mode": "forward_append_only_observation",
            "affects": "none",
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "token_context_admission_attempts" not in tables:
            return empty
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = list(
            connection.execute(
                """
                SELECT * FROM token_context_admission_attempts
                WHERE evaluated_at>=? ORDER BY evaluated_at DESC,id DESC
                """,
                (start,),
            )
        )
        if not rows:
            return empty
        reason_counts: dict[str, int] = {}
        for row in rows:
            reason = str(row["reason"] or "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        admitted = sum(str(row["outcome"]) == "admitted" for row in rows)
        trigger_qualified = sum(bool(str(row["trigger_kind"] or "")) for row in rows)
        recent = [
            {
                "id": int(row["id"]),
                "token_id": str(row["token_id"]),
                "evaluated_at": str(row["evaluated_at"]),
                "outcome": str(row["outcome"]),
                "reason": str(row["reason"]),
                "trigger_kind": str(row["trigger_kind"] or ""),
                "trigger_priority": row["trigger_priority"],
                "platform": str(row["platform"] or ""),
                "entity_id": str(row["entity_id"] or ""),
                "event_id": row["event_id"],
                "decision_id": row["decision_id"],
                "snapshot_observed_at": str(row["snapshot_observed_at"]),
                "momentum_score": float(row["momentum_score"] or 0.0),
                "next_eligible_at": row["next_eligible_at"],
                "quota": {
                    "day": str(row["quota_day"]),
                    "calls_used_before": int(row["calls_used_before"]),
                    "daily_call_limit": int(row["daily_call_limit"]),
                    "tokens_used_before": int(row["tokens_used_before"]),
                    "daily_token_budget": int(row["daily_token_budget"]),
                    "token_reserve_per_call": int(row["token_reserve_per_call"]),
                },
            }
            for row in rows[:30]
        ]
        return {
            "status": "observed",
            "version": Store.TOKEN_CONTEXT_ADMISSION_VERSION,
            "observed_versions": sorted({str(row["version"]) for row in rows}),
            "items": recent,
            "reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "summary": {
                "attempts": len(rows),
                "trigger_qualified_attempts": trigger_qualified,
                "admitted": admitted,
                "skipped": len(rows) - admitted,
                "admission_rate": round(admitted / trigger_qualified, 4)
                if trigger_qualified
                else None,
                "tracking_started_at": min(str(row["evaluated_at"]) for row in rows),
            },
            "mode": "forward_append_only_observation",
            "affects": "none",
            "as_of": iso(),
        }

    def add_token_context_assessment(
        self,
        token_id: str,
        *,
        trigger: str,
        status: str,
        snapshot_observed_at: Any,
        momentum_score: float,
        assessment: Mapping[str, Any],
        agent_metadata: Mapping[str, Any] | None = None,
        audit: Iterable[Mapping[str, Any]] = (),
        assessed_at=None,
    ) -> int:
        assessment_time = parse_time(assessed_at or utcnow())
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO token_context_assessments(
                    token_id,trigger,status,assessed_at,snapshot_observed_at,momentum_score,
                    assessment_json,agent_metadata_json,audit_json
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(token_id), str(trigger)[:120], str(status)[:80],
                    iso(assessment_time), iso(parse_time(snapshot_observed_at)),
                    float(momentum_score), self._bounded_json(dict(assessment)),
                    self._bounded_json(dict(agent_metadata or {})),
                    self._bounded_json([dict(item) for item in audit]),
                ),
            )
            assessment_id = int(cursor.lastrowid)
            self._create_token_context_outcome_cohort_locked(
                assessment_id,
                token_id=str(token_id),
                assessed_at=assessment_time,
                status=str(status),
                trigger=str(trigger),
                assessment=dict(assessment),
            )
            return assessment_id

    @staticmethod
    def _token_context_outcome_labels(
        assessment: Mapping[str, Any], *, status: str
    ) -> list[tuple[str, str]]:
        def safe(value: Any, *, domain: bool = False) -> str:
            text = str(value or "").strip().lower()
            pattern = r"[^a-z0-9._-]" if domain else r"[^a-z0-9_-]"
            return re.sub(pattern, "", text)[:160]

        trigger = assessment.get("investigation_trigger")
        trigger = trigger if isinstance(trigger, Mapping) else {}
        project = assessment.get("project_claims")
        project = project if isinstance(project, Mapping) else {}
        community = assessment.get("community_amplification")
        community = community if isinstance(community, Mapping) else {}
        figures = assessment.get("public_figure_linkage")
        figures = figures if isinstance(figures, Mapping) else {}
        reporting = assessment.get("independent_reporting")
        reporting = reporting if isinstance(reporting, Mapping) else {}
        momentum = assessment.get("onchain_momentum")
        momentum = momentum if isinstance(momentum, Mapping) else {}

        labels: list[tuple[str, str]] = []
        for dimension, value in (
            ("assessment_status", status),
            ("trigger_kind", trigger.get("kind")),
            ("project_claim_status", project.get("status")),
            ("community_status", community.get("status")),
            ("public_figure_linkage_status", figures.get("status")),
            ("independent_reporting_status", reporting.get("status")),
        ):
            normalized = safe(value)
            if normalized:
                labels.append((dimension, normalized))

        for value in community.get("platforms") or []:
            normalized = safe(value)
            if normalized:
                labels.append(("community_platform", normalized))
        for item in figures.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            normalized = safe(item.get("platform"))
            if normalized:
                labels.append(("public_figure_candidate_platform", normalized))
        verified_domains = reporting.get("domains") if reporting.get("status") == "verified" else []
        verified_domains = verified_domains if isinstance(verified_domains, list) else []
        for value in verified_domains:
            normalized = safe(value, domain=True)
            if normalized:
                labels.append(("independent_reporting_domain", normalized))
        domain_count = len({value for dimension, value in labels if dimension == "independent_reporting_domain"})
        labels.append(
            ("independent_reporting_domain_count", "0" if domain_count == 0 else "1" if domain_count == 1 else "2_plus")
        )

        try:
            score = float(momentum.get("momentum_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        labels.append(("onchain_momentum_band", "high" if score >= 80 else "medium" if score >= 60 else "low"))

        if (
            trigger.get("kind") == "high_impact_account_post"
            and trigger.get("verification_status") == "browser_exact_entity_observation"
        ):
            labels.append(("verified_original_public_figure_post", "present"))
            entity_id = safe(trigger.get("entity_id"))
            platform = safe(trigger.get("platform"))
            if entity_id and re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?", entity_id):
                labels.append(("verified_public_figure_entity", entity_id))
            if platform:
                labels.append(("trigger_platform", platform))
        return list(dict.fromkeys(labels))

    def _create_token_context_outcome_cohort_locked(
        self,
        assessment_id: int,
        *,
        token_id: str,
        assessed_at: Any,
        status: str,
        trigger: str,
        assessment: Mapping[str, Any],
    ) -> int | None:
        assessed = parse_time(assessed_at)
        snapshot = self.db.execute(
            """
            SELECT id,observed_at,price_usd FROM token_snapshots
            WHERE token_id=? AND observed_at<=? AND ingested_at<=?
              AND ingested_at>=observed_at AND price_usd>0
            ORDER BY observed_at DESC,id DESC LIMIT 1
            """,
            (str(token_id), iso(assessed), iso(assessed)),
        ).fetchone()
        if snapshot is None:
            return None
        investigation_trigger = assessment.get("investigation_trigger")
        investigation_trigger = (
            investigation_trigger if isinstance(investigation_trigger, Mapping) else {}
        )
        trigger_kind = re.sub(
            r"[^a-z0-9_-]", "",
            str(investigation_trigger.get("kind") or trigger or "unknown").strip().lower(),
        )[:120] or "unknown"
        cohort_key = hashlib.sha256(
            f"{self.TOKEN_CONTEXT_OUTCOME_VERSION}\n{int(assessment_id)}".encode("utf-8")
        ).hexdigest()
        cursor = self.db.execute(
            """
            INSERT OR IGNORE INTO token_context_outcome_cohorts(
                cohort_key,version,assessment_id,token_id,assessed_at,entry_snapshot_id,
                entry_snapshot_at,entry_price,trigger_kind,status,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,'pending',?)
            """,
            (
                cohort_key, self.TOKEN_CONTEXT_OUTCOME_VERSION, int(assessment_id), str(token_id),
                iso(assessed), int(snapshot["id"]), str(snapshot["observed_at"]),
                float(snapshot["price_usd"]), trigger_kind, iso(),
            ),
        )
        if cursor.rowcount != 1:
            row = self.db.execute(
                "SELECT id FROM token_context_outcome_cohorts WHERE assessment_id=?",
                (int(assessment_id),),
            ).fetchone()
            return int(row["id"]) if row else None
        cohort_id = int(cursor.lastrowid)
        label_assessment = dict(assessment)
        if not isinstance(label_assessment.get("investigation_trigger"), Mapping):
            label_assessment["investigation_trigger"] = {"kind": trigger_kind}
        for dimension, value in self._token_context_outcome_labels(
            label_assessment, status=status
        ):
            self.db.execute(
                """
                INSERT INTO token_context_outcome_labels(cohort_id,dimension,value,source)
                VALUES(?,?,?,'frozen_assessment')
                """,
                (cohort_id, dimension, value),
            )
        return cohort_id

    def token_context_assessments(self, token_id: str, *, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                """
                SELECT * FROM token_context_assessments
                WHERE token_id=? ORDER BY assessed_at DESC,id DESC LIMIT ?
                """,
                (str(token_id), max(1, min(100, int(limit)))),
            )
        )

    def token_context_outcome_tracking(self, assessment_id: int) -> dict[str, Any]:
        cohort = self.db.execute(
            "SELECT * FROM token_context_outcome_cohorts WHERE assessment_id=?",
            (int(assessment_id),),
        ).fetchone()
        if cohort is None:
            return {
                "status": "not_tracked",
                "version": self.TOKEN_CONTEXT_OUTCOME_VERSION,
                "mode": "descriptive_observation_only",
                "reason": "no_eligible_entry_snapshot_or_pre_tracking_assessment",
                "horizons": [],
                "decision_eligible": False,
                "affects": "none",
            }
        outcomes = {
            int(row["horizon_minutes"]): row
            for row in self.db.execute(
                "SELECT * FROM token_context_outcomes WHERE cohort_id=?",
                (int(cohort["id"]),),
            )
        }
        assessed = parse_time(cohort["assessed_at"])
        horizons = []
        for horizon in self.TOKEN_CONTEXT_OUTCOME_HORIZONS_MINUTES:
            row = outcomes.get(horizon)
            horizons.append(
                {
                    "horizon_minutes": horizon,
                    "target_at": iso(assessed + timedelta(minutes=horizon)),
                    "status": str(row["status"]) if row else "pending",
                    "outcome_observed_at": row["outcome_observed_at"] if row else None,
                    "outcome_price": row["outcome_price"] if row else None,
                    "raw_return": row["raw_return"] if row else None,
                    "maximum_return": row["maximum_return"] if row else None,
                    "minimum_return": row["minimum_return"] if row else None,
                    "snapshot_count": int(row["snapshot_count"] or 0) if row else 0,
                }
            )
        return {
            "status": str(cohort["status"]),
            "version": str(cohort["version"]),
            "mode": "descriptive_observation_only",
            "entry_snapshot_at": str(cohort["entry_snapshot_at"]),
            "entry_price": float(cohort["entry_price"]),
            "trigger_kind": str(cohort["trigger_kind"]),
            "horizons": horizons,
            "decision_eligible": False,
            "endorsement_inferred": False,
            "affects": "none",
        }

    def finalize_token_context_outcomes(
        self,
        *,
        now: Any = None,
        horizons_minutes: Iterable[int] | None = None,
        max_lateness_minutes: int = 30,
    ) -> dict[str, int]:
        """Append immutable context follow-through using only locally observed snapshots."""
        evaluated_at = parse_time(now or utcnow())
        horizons = tuple(
            sorted(
                {
                    max(1, int(value))
                    for value in (
                        horizons_minutes or self.TOKEN_CONTEXT_OUTCOME_HORIZONS_MINUTES
                    )
                }
            )
        )
        observed_count = 0
        missing_count = 0
        completed_count = 0
        with self._lock, self.db:
            cohorts = list(
                self.db.execute(
                    "SELECT * FROM token_context_outcome_cohorts "
                    "WHERE status='pending' ORDER BY assessed_at,id"
                )
            )
            for cohort in cohorts:
                existing = {
                    int(row["horizon_minutes"])
                    for row in self.db.execute(
                        "SELECT horizon_minutes FROM token_context_outcomes WHERE cohort_id=?",
                        (int(cohort["id"]),),
                    )
                }
                for horizon in horizons:
                    if horizon in existing:
                        continue
                    target = parse_time(cohort["assessed_at"]) + timedelta(minutes=horizon)
                    if evaluated_at < target:
                        continue
                    deadline = target + timedelta(minutes=max(1, int(max_lateness_minutes)))
                    upper = min(evaluated_at, deadline)
                    snapshot = self.db.execute(
                        """
                        SELECT id,observed_at,ingested_at,price_usd FROM token_snapshots
                        WHERE token_id=? AND observed_at>=? AND observed_at<=?
                          AND ingested_at>=? AND ingested_at<=?
                          AND ingested_at>=observed_at AND price_usd>0
                        ORDER BY ingested_at,observed_at,id LIMIT 1
                        """,
                        (
                            str(cohort["token_id"]), iso(target), iso(upper),
                            iso(target), iso(upper),
                        ),
                    ).fetchone()
                    if snapshot is not None:
                        path = list(
                            self.db.execute(
                                """
                                SELECT price_usd FROM token_snapshots
                                WHERE token_id=? AND observed_at>=? AND observed_at<=?
                                  AND ingested_at IS NOT NULL AND ingested_at<=?
                                  AND ingested_at>=observed_at AND price_usd>0
                                ORDER BY observed_at,id
                                """,
                                (
                                    str(cohort["token_id"]), str(cohort["entry_snapshot_at"]),
                                    str(snapshot["observed_at"]), str(snapshot["ingested_at"]),
                                ),
                            )
                        )
                        entry_price = float(cohort["entry_price"])
                        returns = [float(row["price_usd"]) / entry_price - 1.0 for row in path]
                        raw_return = float(snapshot["price_usd"]) / entry_price - 1.0
                        self.db.execute(
                            """
                            INSERT INTO token_context_outcomes(
                                cohort_id,horizon_minutes,target_at,status,outcome_snapshot_id,
                                outcome_observed_at,outcome_price,raw_return,maximum_return,minimum_return,
                                snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'observed',?,?,?,?,?,?,?,?)
                            """,
                            (
                                int(cohort["id"]), horizon, iso(target), int(snapshot["id"]),
                                str(snapshot["observed_at"]), float(snapshot["price_usd"]), raw_return,
                                max(returns) if returns else raw_return,
                                min(returns) if returns else raw_return,
                                len(path), iso(evaluated_at),
                            ),
                        )
                        observed_count += 1
                    elif evaluated_at >= deadline:
                        self.db.execute(
                            """
                            INSERT INTO token_context_outcomes(
                                cohort_id,horizon_minutes,target_at,status,snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'missing',0,?)
                            """,
                            (int(cohort["id"]), horizon, iso(target), iso(evaluated_at)),
                        )
                        missing_count += 1
                outcome_total = int(
                    self.db.execute(
                        "SELECT COUNT(*) FROM token_context_outcomes WHERE cohort_id=?",
                        (int(cohort["id"]),),
                    ).fetchone()[0]
                )
                if outcome_total >= len(horizons):
                    self.db.execute(
                        "UPDATE token_context_outcome_cohorts SET status='complete' WHERE id=?",
                        (int(cohort["id"]),),
                    )
                    completed_count += 1
        return {
            "cohorts_checked": len(cohorts),
            "outcomes_observed": observed_count,
            "outcomes_missing": missing_count,
            "cohorts_completed": completed_count,
        }

    @staticmethod
    def token_context_outcome_learning_summary_from_connection(
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        required = {
            "token_context_assessments", "token_context_outcome_cohorts",
            "token_context_outcome_labels", "token_context_outcomes",
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        empty = {
            "status": "not_observed",
            "version": Store.TOKEN_CONTEXT_OUTCOME_VERSION,
            "mode": "descriptive_observation_only",
            "horizons_minutes": list(Store.TOKEN_CONTEXT_OUTCOME_HORIZONS_MINUTES),
            "items": [],
            "summary": {
                "assessments": 0, "tracked_cohorts": 0, "independent_tokens": 0,
                "pending_cohorts": 0,
                "complete_cohorts": 0, "observed_outcomes": 0, "missing_outcomes": 0,
                "untracked_assessments": 0, "descriptive_mature_labels": 0,
            },
            "maturity_policy": {
                "minimum_observed_cohorts": 30, "minimum_assessment_days": 15,
                "minimum_distinct_tokens": 30,
                "minimum_positive_outcomes": 5, "minimum_nonpositive_outcomes": 5,
                "verified_entity_minimum_cohorts": 50,
                "verified_entity_minimum_distinct_tokens": 50,
                "verified_entity_minimum_days": 20,
            },
            "activation": False,
            "actual_schedule_changed_by_learning": False,
            "decision_eligible": False,
            "endorsement_inferred": False,
            "affects": "none",
        }
        if not required.issubset(tables):
            return empty
        now = utcnow()
        start = iso(now - timedelta(days=max(1, min(3650, int(lookback_days)))))
        assessment_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM token_context_assessments WHERE assessed_at>=?", (start,)
            ).fetchone()[0]
        )
        cohorts = list(
            connection.execute(
                "SELECT * FROM token_context_outcome_cohorts WHERE assessed_at>=?", (start,)
            )
        )
        if not cohorts and assessment_count == 0:
            return empty
        cohort_ids = [int(row["id"]) for row in cohorts]
        labels_by_cohort: dict[int, list[tuple[str, str]]] = {value: [] for value in cohort_ids}
        outcomes_by_cohort: dict[int, list[sqlite3.Row]] = {value: [] for value in cohort_ids}
        if cohort_ids:
            placeholders = ",".join("?" for _ in cohort_ids)
            for row in connection.execute(
                f"SELECT cohort_id,dimension,value FROM token_context_outcome_labels "
                f"WHERE cohort_id IN ({placeholders})",
                cohort_ids,
            ):
                labels_by_cohort[int(row["cohort_id"])].append(
                    (str(row["dimension"]), str(row["value"]))
                )
            for row in connection.execute(
                f"SELECT * FROM token_context_outcomes WHERE cohort_id IN ({placeholders})",
                cohort_ids,
            ):
                outcomes_by_cohort[int(row["cohort_id"])].append(row)

        first_cohort_by_token: dict[str, sqlite3.Row] = {}
        for cohort in sorted(
            cohorts, key=lambda row: (str(row["assessed_at"]), int(row["id"]))
        ):
            first_cohort_by_token.setdefault(str(cohort["token_id"]), cohort)
        independent_cohorts = list(first_cohort_by_token.values())

        grouped: dict[tuple[int, str, str], dict[str, Any]] = {}
        for cohort in independent_cohorts:
            cohort_id = int(cohort["id"])
            day = parse_time(cohort["assessed_at"]).date().isoformat()
            for outcome in outcomes_by_cohort.get(cohort_id, []):
                horizon = int(outcome["horizon_minutes"])
                for dimension, value in labels_by_cohort.get(cohort_id, []):
                    item = grouped.setdefault(
                        (horizon, dimension, value),
                        {
                            "horizon_minutes": horizon, "dimension": dimension, "value": value,
                            "cohort_ids": set(), "token_ids": set(), "assessment_days": set(),
                            "returns": [], "maximum_returns": [], "minimum_returns": [],
                            "missing_outcomes": 0, "last_assessed_at": None,
                            "last_outcome_observed_at": None,
                        },
                    )
                    item["cohort_ids"].add(cohort_id)
                    item["token_ids"].add(str(cohort["token_id"]))
                    item["assessment_days"].add(day)
                    if not item["last_assessed_at"] or str(cohort["assessed_at"]) > item["last_assessed_at"]:
                        item["last_assessed_at"] = str(cohort["assessed_at"])
                    if str(outcome["status"]) == "observed" and outcome["raw_return"] is not None:
                        item["returns"].append(float(outcome["raw_return"]))
                        if outcome["maximum_return"] is not None:
                            item["maximum_returns"].append(float(outcome["maximum_return"]))
                        if outcome["minimum_return"] is not None:
                            item["minimum_returns"].append(float(outcome["minimum_return"]))
                        observed_at = outcome["outcome_observed_at"]
                        if observed_at and (
                            not item["last_outcome_observed_at"]
                            or str(observed_at) > item["last_outcome_observed_at"]
                        ):
                            item["last_outcome_observed_at"] = str(observed_at)
                    elif str(outcome["status"]) == "missing":
                        item["missing_outcomes"] += 1

        items = []
        for item in grouped.values():
            returns = sorted(item.pop("returns"))
            maximum_returns = item.pop("maximum_returns")
            minimum_returns = item.pop("minimum_returns")
            cohort_count = len(item.pop("cohort_ids"))
            token_count = len(item.pop("token_ids"))
            day_count = len(item.pop("assessment_days"))
            observed = len(returns)
            positive = sum(value > 0 for value in returns)
            nonpositive = observed - positive
            minimum_cohorts = 50 if item["dimension"] == "verified_public_figure_entity" else 30
            minimum_days = 20 if item["dimension"] == "verified_public_figure_entity" else 15
            mature = (
                token_count >= minimum_cohorts and observed >= minimum_cohorts
                and day_count >= minimum_days
                and positive >= 5 and nonpositive >= 5
            )
            median = None
            if returns:
                middle = len(returns) // 2
                median = returns[middle] if len(returns) % 2 else (returns[middle - 1] + returns[middle]) / 2
            total_finalized = observed + int(item["missing_outcomes"])
            items.append(
                {
                    **item,
                    "tracked_cohorts": cohort_count,
                    "distinct_tokens": token_count,
                    "assessment_days": day_count,
                    "observed_outcomes": observed,
                    "missing_rate": (
                        int(item["missing_outcomes"]) / total_finalized if total_finalized else None
                    ),
                    "positive_outcomes": positive,
                    "nonpositive_outcomes": nonpositive,
                    "mean_raw_return": sum(returns) / observed if observed else None,
                    "median_raw_return": median,
                    "mean_maximum_return": (
                        sum(maximum_returns) / len(maximum_returns) if maximum_returns else None
                    ),
                    "mean_minimum_return": (
                        sum(minimum_returns) / len(minimum_returns) if minimum_returns else None
                    ),
                    "descriptive_mature": mature,
                    "activation": False,
                    "decision_eligible": False,
                    "affects": "none",
                }
            )
        items.sort(
            key=lambda item: (
                not bool(item["descriptive_mature"]),
                0 if int(item["horizon_minutes"]) == 60 else int(item["horizon_minutes"]),
                -int(item["observed_outcomes"]), str(item["dimension"]), str(item["value"]),
            )
        )
        independent_ids = {int(row["id"]) for row in independent_cohorts}
        observed_outcomes = sum(
            1 for cohort_id, rows in outcomes_by_cohort.items() for row in rows
            if cohort_id in independent_ids and str(row["status"]) == "observed"
        )
        missing_outcomes = sum(
            1 for cohort_id, rows in outcomes_by_cohort.items() for row in rows
            if cohort_id in independent_ids and str(row["status"]) == "missing"
        )
        mature_count = sum(1 for item in items if item["descriptive_mature"])
        return {
            **empty,
            "status": (
                "descriptive_review_available" if mature_count else
                "collecting_followup" if cohorts else "not_observed"
            ),
            "lookback_days": int(lookback_days),
            "items": items[:500],
            "summary": {
                "assessments": assessment_count,
                "tracked_cohorts": len(cohorts),
                "independent_tokens": len(independent_cohorts),
                "pending_cohorts": sum(str(row["status"]) == "pending" for row in cohorts),
                "complete_cohorts": sum(str(row["status"]) == "complete" for row in cohorts),
                "observed_outcomes": observed_outcomes,
                "missing_outcomes": missing_outcomes,
                "untracked_assessments": max(0, assessment_count - len(cohorts)),
                "descriptive_mature_labels": mature_count,
            },
            "as_of": iso(now),
        }

    @staticmethod
    def _token_source_fingerprint(link: Mapping[str, Any]) -> str:
        stable = "\n".join(
            (
                str(link.get("token_id") or "").strip(),
                str(link.get("provider") or "").strip().lower(),
                str(link.get("discovery_surface") or "").strip().lower(),
                str(link.get("role") or "").strip().lower(),
                str(link.get("link_kind") or "").strip().lower(),
                str(link.get("normalized_url") or "").strip(),
            )
        )
        return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()

    def _upsert_token_source_link_locked(self, link: Mapping[str, Any], *, observed_at=None) -> tuple[str, bool]:
        token_id = str(link.get("token_id") or "").strip()
        provider = str(link.get("provider") or "").strip().lower()
        surface = str(link.get("discovery_surface") or "").strip().lower()
        role = str(link.get("role") or "").strip().lower()
        link_kind = str(link.get("link_kind") or "").strip().lower()
        if not token_id or not provider or not surface or role not in {"identity", "promotion"} or not link_kind:
            raise ValueError("token source link requires token_id/provider/surface/identity-or-promotion/link_kind")
        payload = {
            "token_id": token_id,
            "provider": provider,
            "discovery_surface": surface,
            "role": role,
            "original_url": str(link.get("original_url") or "")[:4000],
            "normalized_url": str(link.get("normalized_url") or "")[:4000],
            "link_kind": link_kind,
            "label": str(link.get("label") or "")[:200],
            "platform": str(link.get("platform") or "").strip().lower()[:80],
            "verification_status": str(link.get("verification_status") or "unverified_metadata").strip().lower()[:80],
        }
        fingerprint = self._token_source_fingerprint(payload)
        seen = iso(parse_time(observed_at or utcnow()))
        existed = self.db.execute(
            "SELECT 1 FROM token_source_links WHERE fingerprint=?",
            (fingerprint,),
        ).fetchone() is not None
        self.db.execute(
            """
            INSERT INTO token_source_links(
                fingerprint,token_id,provider,discovery_surface,role,original_url,normalized_url,
                link_kind,label,platform,verification_status,first_observed_at,last_observed_at,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                original_url=excluded.original_url,
                label=excluded.label,
                platform=excluded.platform,
                verification_status=excluded.verification_status,
                first_observed_at=MIN(token_source_links.first_observed_at,excluded.first_observed_at),
                last_observed_at=MAX(token_source_links.last_observed_at,excluded.last_observed_at),
                raw_json=excluded.raw_json
            """,
            (
                fingerprint,
                payload["token_id"],
                payload["provider"],
                payload["discovery_surface"],
                payload["role"],
                payload["original_url"],
                payload["normalized_url"],
                payload["link_kind"],
                payload["label"],
                payload["platform"],
                payload["verification_status"],
                seen,
                seen,
                self._bounded_json(link.get("raw") if isinstance(link.get("raw"), (dict, list)) else {}),
            ),
        )
        return fingerprint, not existed

    def upsert_token_source_link(self, link: Mapping[str, Any], *, observed_at=None) -> tuple[str, bool]:
        with self._lock, self.db:
            return self._upsert_token_source_link_locked(link, observed_at=observed_at)

    def token_source_links(
        self,
        token_id: str,
        *,
        limit: int = 100,
        include_metadata: bool = False,
    ) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self.db.execute(
                    f"""
                    SELECT * FROM token_source_links
                    WHERE token_id=? {'' if include_metadata else "AND normalized_url<>''"}
                    ORDER BY last_observed_at DESC,id DESC LIMIT ?
                    """,
                    (str(token_id), max(1, min(500, int(limit)))),
                )
            )

    def token(self, token_id: str) -> TokenCandidate | None:
        row = self.db.execute("SELECT * FROM tokens WHERE token_id=?", (token_id,)).fetchone()
        if not row:
            return None
        return TokenCandidate(
            chain=row["chain"], address=row["address"], name=row["name"], symbol=row["symbol"],
            created_at=parse_time(row["created_at"]) if row["created_at"] else None,
            first_seen_at=parse_time(row["first_seen_at"]),
            source=row["source"], url=row["url"], social_urls=json.loads(row["social_urls_json"]),
            raw=json.loads(row["raw_json"]),
        )

    def recent_tokens(self, minutes: int = 180, limit: int = 500) -> list[TokenCandidate]:
        since = iso(utcnow() - timedelta(minutes=minutes))
        rows = self.db.execute("SELECT token_id FROM tokens WHERE last_seen_at>=? ORDER BY last_seen_at DESC LIMIT ?", (since, limit))
        return [token for row in rows if (token := self.token(row["token_id"])) is not None]

    def add_snapshot(self, snap: TokenSnapshot) -> None:
        token_id = f"{snap.chain.lower()}:{snap.address}"
        ingested_at = snap.ingested_at or utcnow()
        with self._lock, self.db:
            recorded_at = utcnow()
            self.db.execute(
                """
                INSERT INTO token_snapshots(
                    token_id,observed_at,ingested_at,recorded_at,provider,price_usd,liquidity_usd,market_cap_usd,volume_5m_usd,
                    buys_5m,sells_5m,buyers_5m,holders,buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    token_id, iso(snap.observed_at), iso(ingested_at), iso(recorded_at), snap.provider,
                    snap.price_usd, snap.liquidity_usd,
                    snap.market_cap_usd, snap.volume_5m_usd, snap.buys_5m, snap.sells_5m,
                    snap.buyers_5m, snap.holders, snap.buy_tax_pct, snap.sell_tax_pct,
                    None if snap.honeypot is None else int(snap.honeypot),
                    None if snap.sellable is None else int(snap.sellable), self._json(snap.raw),
                ),
            )

    def latest_snapshot(self, token_id: str, *, at_or_before: Any = None) -> TokenSnapshot | None:
        cutoff = iso(parse_time(at_or_before)) if at_or_before is not None else iso()
        row = self.db.execute(
            "SELECT * FROM token_snapshots WHERE token_id=? AND observed_at<=? "
            "ORDER BY observed_at DESC,id DESC LIMIT 1",
            (token_id, cutoff),
        ).fetchone()
        if not row:
            return None
        chain, address = token_id.split(":", 1)
        return TokenSnapshot(
            chain=chain, address=address, price_usd=row["price_usd"], liquidity_usd=row["liquidity_usd"],
            market_cap_usd=row["market_cap_usd"], volume_5m_usd=row["volume_5m_usd"],
            buys_5m=row["buys_5m"], sells_5m=row["sells_5m"], buyers_5m=row["buyers_5m"],
            holders=row["holders"], buy_tax_pct=row["buy_tax_pct"], sell_tax_pct=row["sell_tax_pct"],
            honeypot=None if row["honeypot"] is None else bool(row["honeypot"]),
            sellable=None if row["sellable"] is None else bool(row["sellable"]),
            observed_at=parse_time(row["observed_at"]),
            ingested_at=parse_time(row["ingested_at"]) if row["ingested_at"] else None,
            provider=row["provider"], raw=json.loads(row["raw_json"]),
        )

    def add_decision(self, decision: CandidateDecision) -> int:
        with self._lock, self.db:
            cur = self.db.execute(
                """
                INSERT INTO decisions(event_id,token_id,action,score,match_score,canonical_margin,reasons_json,
                    rejected_reasons_json,position_usd,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    decision.event_id, decision.token_id, decision.action, decision.score, decision.match_score,
                    decision.canonical_margin, self._json(decision.reasons), self._json(decision.rejected_reasons),
                    decision.position_usd, iso(decision.created_at),
                ),
            )
            return int(cur.lastrowid)

    def decisions(self, limit: int = 30) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)))

    def token_context_decision_relation(
        self, token_id: str, decision_id: int
    ) -> sqlite3.Row | None:
        return self.db.execute(
            """
            SELECT d.id AS decision_id,d.event_id,d.token_id,d.action,d.match_score,d.score,d.created_at,
                   e.title AS event_title,e.attention AS event_attention,e.last_seen_at,e.status AS event_status
            FROM decisions d JOIN events e ON e.id=d.event_id
            WHERE d.id=? AND d.token_id=?
            """,
            (int(decision_id), str(token_id)),
        ).fetchone()

    def account(self) -> dict[str, float]:
        row = self.db.execute("SELECT cash_usd,realized_pnl_usd FROM paper_account WHERE singleton=1").fetchone()
        return {"cash_usd": float(row["cash_usd"]), "realized_pnl_usd": float(row["realized_pnl_usd"])}

    def record_paper_account_snapshot(
        self,
        *,
        cash_usd: float,
        marked_value_usd: float,
        equity_usd: float | None,
        daily_exposure_usd: float,
        open_position_count: int,
        priced_position_count: int,
        quote_as_of: Any = None,
        observed_at: Any = None,
    ) -> int:
        observed = parse_time(observed_at) if observed_at is not None else utcnow()
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO paper_account_snapshots(
                    recorded_at,cash_usd,marked_value_usd,equity_usd,
                    daily_exposure_usd,open_position_count,priced_position_count,quote_as_of
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    iso(observed), float(cash_usd), float(marked_value_usd),
                    None if equity_usd is None else float(equity_usd), float(daily_exposure_usd),
                    max(0, int(open_position_count)), max(0, int(priced_position_count)),
                    iso(parse_time(quote_as_of)) if quote_as_of else None,
                ),
            )
        return int(cursor.lastrowid)

    def latest_paper_account_snapshot_at(self):
        row = self.db.execute(
            "SELECT recorded_at FROM paper_account_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return parse_time(row["recorded_at"]) if row else None

    def record_paper_execution_attempt(
        self,
        *,
        event_id: int,
        token_id: str,
        decision_id: int | None = None,
        cohort_id: int | None = None,
        side: str,
        status: str,
        reason: str,
        requested_at: Any,
        quote_observed_at: Any = None,
        quote_provider: str = "",
        quote_price: float | None = None,
        execution_price: float | None = None,
        gross_usd: float | None = None,
    ) -> int:
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO paper_execution_attempts(
                    event_id,token_id,decision_id,cohort_id,side,status,reason,requested_at,
                    quote_observed_at,quote_provider,quote_price,execution_price,gross_usd
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(event_id), str(token_id), decision_id, cohort_id,
                    str(side).upper(), str(status), str(reason),
                    iso(parse_time(requested_at)),
                    iso(parse_time(quote_observed_at)) if quote_observed_at else None,
                    str(quote_provider or ""), quote_price, execution_price, gross_usd,
                ),
            )
        return int(cursor.lastrowid)

    def paper_buy(
        self, *, event_id: int, token: TokenCandidate, price: float, gross_usd: float,
        fee_bps: float, reason: str, quote_price: float | None = None,
        tax_pct: float | None = None, quote_observed_at: Any = None,
        quote_provider: str = "", execution_attempted_at: Any = None,
        decision_id: int | None = None, cohort_id: int | None = None,
    ) -> Position:
        if price <= 0 or gross_usd <= 0:
            raise ValueError("price and gross_usd must be positive")
        fee = gross_usd * fee_bps / 10_000
        debit = gross_usd + fee
        normalized_tax_pct = (
            min(100.0, max(0.0, float(tax_pct))) if tax_pct is not None else None
        )
        tax = gross_usd * normalized_tax_pct / 100 if normalized_tax_pct is not None else 0.0
        pre_tax_quantity = gross_usd / price
        quantity = (gross_usd - tax) / price
        if quantity <= 0:
            raise ValueError("paper buy tax leaves no quantity")
        slippage_rate = (
            max(0.0, (price - float(quote_price)) / float(quote_price))
            if quote_price is not None and float(quote_price) > 0 else None
        )
        slippage_usd = pre_tax_quantity * (price - float(quote_price)) if slippage_rate is not None else None
        with self._lock, self.db:
            account = self.account()
            if account["cash_usd"] + 1e-9 < debit:
                raise ValueError("insufficient paper cash")
            if self.db.execute("SELECT 1 FROM positions WHERE token_id=?", (token.token_id,)).fetchone():
                raise ValueError("position already exists")
            now = iso()
            self.db.execute("UPDATE paper_account SET cash_usd=cash_usd-?,updated_at=? WHERE singleton=1", (debit, now))
            self.db.execute(
                """
                INSERT INTO positions(token_id,event_id,decision_id,cohort_id,chain,address,symbol,quantity,entry_price,cost_usd,
                    remaining_cost_usd,highest_price,opened_at,realized_pnl_usd,take_profit_index)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
                """,
                (
                    token.token_id,event_id,decision_id,cohort_id,token.chain,token.address,
                    token.symbol,quantity,price,debit,debit,price,now,0.0,
                ),
            )
            self.db.execute(
                """
                INSERT INTO trades(
                    token_id,event_id,decision_id,cohort_id,side,quantity,price,quote_price,gross_usd,fee_usd,
                    fee_bps,slippage_rate,slippage_usd,tax_pct,tax_usd,quote_observed_at,
                    quote_provider,execution_attempted_at,reason,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (token.token_id,event_id,decision_id,cohort_id,"BUY",quantity,price,quote_price,gross_usd,fee,
                 fee_bps,slippage_rate,slippage_usd,normalized_tax_pct,
                 tax if normalized_tax_pct is not None else None,
                 iso(parse_time(quote_observed_at)) if quote_observed_at else None,
                 str(quote_provider or ""),
                 iso(parse_time(execution_attempted_at)) if execution_attempted_at else now,
                 reason,now),
            )
        return self.position(token.token_id)

    def position(self, token_id: str) -> Position | None:
        row = self.db.execute("SELECT * FROM positions WHERE token_id=?", (token_id,)).fetchone()
        if not row:
            return None
        return Position(
            token_id=row["token_id"], event_id=int(row["event_id"]), chain=row["chain"], address=row["address"],
            symbol=row["symbol"], quantity=float(row["quantity"]), entry_price=float(row["entry_price"]),
            cost_usd=float(row["cost_usd"]), remaining_cost_usd=float(row["remaining_cost_usd"]),
            highest_price=float(row["highest_price"]), opened_at=parse_time(row["opened_at"]),
            realized_pnl_usd=float(row["realized_pnl_usd"]), take_profit_index=int(row["take_profit_index"]),
            decision_id=int(row["decision_id"]) if row["decision_id"] is not None else None,
            cohort_id=int(row["cohort_id"]) if row["cohort_id"] is not None else None,
        )

    def open_positions(self) -> list[Position]:
        ids = [row["token_id"] for row in self.db.execute("SELECT token_id FROM positions ORDER BY opened_at")]
        return [p for token_id in ids if (p := self.position(token_id)) is not None]

    def update_position_peak(self, token_id: str, price: float) -> None:
        with self._lock, self.db:
            self.db.execute("UPDATE positions SET highest_price=MAX(highest_price,?) WHERE token_id=?", (price, token_id))

    def set_take_profit_index(self, token_id: str, index: int) -> None:
        with self._lock, self.db:
            self.db.execute("UPDATE positions SET take_profit_index=? WHERE token_id=?", (index, token_id))

    def paper_sell(
        self, token_id: str, *, price: float, fraction: float, fee_bps: float,
        reason: str, quote_price: float | None = None, tax_pct: float | None = None,
        quote_observed_at: Any = None, quote_provider: str = "",
        execution_attempted_at: Any = None,
    ) -> dict[str, float]:
        position = self.position(token_id)
        if not position:
            raise KeyError(token_id)
        fraction = min(1.0, max(0.0, fraction))
        if fraction <= 0 or price <= 0:
            raise ValueError("invalid sell")
        quantity = position.quantity * fraction
        gross = quantity * price
        fee = gross * fee_bps / 10_000
        normalized_tax_pct = (
            min(100.0, max(0.0, float(tax_pct))) if tax_pct is not None else None
        )
        tax = gross * normalized_tax_pct / 100 if normalized_tax_pct is not None else 0.0
        slippage_rate = (
            max(0.0, (float(quote_price) - price) / float(quote_price))
            if quote_price is not None and float(quote_price) > 0 else None
        )
        slippage_usd = quantity * (float(quote_price) - price) if slippage_rate is not None else None
        net = gross - fee - tax
        cost_released = position.remaining_cost_usd * fraction
        pnl = net - cost_released
        remaining_quantity = position.quantity - quantity
        remaining_cost = position.remaining_cost_usd - cost_released
        now = iso()
        with self._lock, self.db:
            self.db.execute(
                "UPDATE paper_account SET cash_usd=cash_usd+?,realized_pnl_usd=realized_pnl_usd+?,updated_at=? WHERE singleton=1",
                (net, pnl, now),
            )
            self.db.execute(
                """
                INSERT INTO trades(
                    token_id,event_id,decision_id,cohort_id,side,quantity,price,quote_price,gross_usd,fee_usd,
                    fee_bps,slippage_rate,slippage_usd,tax_pct,tax_usd,quote_observed_at,
                    quote_provider,execution_attempted_at,reason,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                 token_id,position.event_id,position.decision_id,position.cohort_id,
                 "SELL",quantity,price,quote_price,gross,fee,
                 fee_bps,slippage_rate,slippage_usd,normalized_tax_pct,
                 tax if normalized_tax_pct is not None else None,
                 iso(parse_time(quote_observed_at)) if quote_observed_at else None,
                 str(quote_provider or ""),
                 iso(parse_time(execution_attempted_at)) if execution_attempted_at else now,
                 reason,now),
            )
            if remaining_quantity <= max(1e-12, position.quantity * 1e-8):
                self._record_source_utility_outcome_locked(position, closed_at=now)
                self.db.execute("DELETE FROM positions WHERE token_id=?", (token_id,))
            else:
                self.db.execute(
                    "UPDATE positions SET quantity=?,remaining_cost_usd=?,realized_pnl_usd=realized_pnl_usd+? WHERE token_id=?",
                    (remaining_quantity,remaining_cost,pnl,token_id),
                )
        return {
            "quantity": quantity, "gross_usd": gross, "fee_usd": fee, "net_usd": net,
            "pnl_usd": pnl, "quote_price": quote_price, "execution_price": price,
            "slippage_rate": slippage_rate, "slippage_usd": slippage_usd,
            "tax_pct": normalized_tax_pct,
            "tax_usd": tax if normalized_tax_pct is not None else None,
        }

    def trades(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)))

    @staticmethod
    def _source_learning_labels(row: Mapping[str, Any]) -> list[tuple[str, str]]:
        def value(name: str, default: Any = "") -> Any:
            try:
                return row[name]
            except (KeyError, IndexError, TypeError):
                return default

        try:
            raw = json.loads(str(value("raw_json") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        browser = raw.get("browser") if isinstance(raw.get("browser"), dict) else {}
        source = str(value("source") or "").strip()[:160]
        source_kind = str(value("source_kind") or "unknown").strip().lower()[:80] or "unknown"
        platform = str(raw.get("platform") or browser.get("platform") or "").strip().lower()
        if not platform:
            prefix = source.split(":", 1)[0].strip().lower()
            if prefix in {"x", "truth", "bluesky", "reddit", "threads", "instagram", "tiktok", "youtube", "mastodon"}:
                platform = prefix
            elif source.startswith("autonomous-") or source_kind == "agent_search":
                platform = "agent_search"
            elif source_kind in {"news", "rss"}:
                platform = "rss_news"
            elif source_kind in {"onchain", "token", "new_pool"}:
                platform = "onchain"
        platform = re.sub(r"[^a-z0-9_-]", "", platform)[:80]
        entity_id = str(raw.get("source_entity_id") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?", entity_id):
            entity_id = ""
        account_type = str(raw.get("account_type") or browser.get("account_type") or "").strip().lower()
        account_type = re.sub(r"[^a-z0-9_-]", "", account_type)[:80]
        trend_lane = str(raw.get("trend_lane_id") or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?", trend_lane):
            trend_lane = ""
        event_topic = str(value("event_topic") or "").strip().lower()
        if event_topic not in {
            "political_public_figure", "celebrity_entertainment", "animals_internet_culture",
            "sports", "ai_tech_gaming", "crypto_native", "other",
        }:
            event_topic = ""
        evidence_role = str(value("role") or "").strip().lower()
        if evidence_role not in {"feature", "confirmation", "identity", "promotion"}:
            evidence_role = ""
        labels = [("source_kind", source_kind)]
        if source:
            labels.append(("source", source))
        if platform:
            labels.append(("platform", platform))
        if entity_id:
            labels.append(("entity", entity_id))
        if account_type:
            labels.append(("account_type", account_type))
        if trend_lane:
            labels.append(("trend_lane", trend_lane))
        if event_topic:
            labels.append(("event_topic", event_topic))
        if evidence_role:
            labels.append(("evidence_role", evidence_role))
        return list(dict.fromkeys(labels))

    def _record_source_utility_outcome_locked(self, position: Position, *, closed_at: str) -> None:
        opened_at = iso(position.opened_at)
        if position.decision_id is not None:
            trade_rows = list(
                self.db.execute(
                    """
                    SELECT side,gross_usd,fee_usd,tax_usd FROM trades
                    WHERE decision_id=? AND event_id=? AND token_id=? AND created_at>=?
                    ORDER BY id
                    """,
                    (
                        int(position.decision_id), int(position.event_id),
                        str(position.token_id), opened_at,
                    ),
                )
            )
            outcome_key = hashlib.sha256(
                f"{self.PAPER_SOURCE_ATTRIBUTION_VERSION}\n{int(position.decision_id)}\n{opened_at}".encode(
                    "utf-8"
                )
            ).hexdigest()
        else:
            trade_rows = list(
                self.db.execute(
                    """
                    SELECT side,gross_usd,fee_usd,tax_usd FROM trades
                    WHERE event_id=? AND token_id=? AND created_at>=?
                    ORDER BY id
                    """,
                    (position.event_id, position.token_id, opened_at),
                )
            )
            outcome_key = hashlib.sha256(
                f"legacy\n{position.event_id}\n{position.token_id}\n{opened_at}".encode("utf-8")
            ).hexdigest()

        trade_rows = list(
            trade_rows
        )
        buy_cost = sum(
            float(row["gross_usd"] or 0) + float(row["fee_usd"] or 0)
            for row in trade_rows if str(row["side"]).upper() == "BUY"
        )
        sell_net = sum(
            float(row["gross_usd"] or 0)
            - float(row["fee_usd"] or 0)
            - float(row["tax_usd"] or 0)
            for row in trade_rows if str(row["side"]).upper() == "SELL"
        )

        def record_attempt(
            status: str,
            reason: str,
            *,
            eligible_source_count: int = 0,
            net_return: float | None = None,
        ) -> None:
            self.db.execute(
                """
                INSERT OR IGNORE INTO paper_source_attribution_attempts(
                    outcome_key,version,event_id,token_id,decision_id,cohort_id,status,reason,
                    eligible_source_count,buy_cost_usd,sell_net_usd,net_return,opened_at,closed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    outcome_key,
                    self.PAPER_SOURCE_ATTRIBUTION_VERSION,
                    int(position.event_id),
                    str(position.token_id),
                    position.decision_id,
                    position.cohort_id,
                    str(status),
                    str(reason),
                    max(0, int(eligible_source_count)),
                    buy_cost if buy_cost > 0 else None,
                    sell_net if sell_net >= 0 else None,
                    net_return,
                    opened_at,
                    closed_at,
                ),
            )

        if buy_cost <= 0 or sell_net < 0:
            record_attempt("skipped", "invalid_cashflows")
            return
        net_return = (sell_net - buy_cost) / buy_cost
        if position.decision_id is None:
            record_attempt("skipped", "legacy_missing_decision", net_return=net_return)
            return
        if position.cohort_id is None:
            record_attempt("skipped", "missing_admitted_cohort", net_return=net_return)
            return
        cohort = self.db.execute(
            """
            SELECT id,decision_at FROM shadow_event_cohorts
            WHERE id=? AND decision_id=? AND event_id=? AND token_id=?
            """,
            (
                int(position.cohort_id),
                int(position.decision_id),
                int(position.event_id),
                str(position.token_id),
            ),
        ).fetchone()
        if cohort is None:
            record_attempt("skipped", "cohort_link_mismatch", net_return=net_return)
            return
        decision_at = str(cohort["decision_at"])
        leads = list(
            self.db.execute(
                """
                SELECT DISTINCT o.id,o.source,o.source_kind,o.role,o.observed_at,o.raw_json,
                       e.topic AS event_topic
                FROM observations o
                JOIN shadow_event_cohort_labels l ON l.source_observation_id=o.id
                JOIN events e ON e.id=?
                WHERE l.cohort_id=? AND o.capture_phase='live'
                  AND o.role IN ('feature','confirmation')
                  AND o.observed_at<=? AND o.ingested_at<=?
                  AND (o.published_at IS NULL OR o.published_at<=?)
                ORDER BY o.observed_at,o.id
                """,
                (int(position.event_id), int(position.cohort_id), decision_at, decision_at, decision_at),
            )
        )
        if not leads:
            record_attempt("skipped", "no_eligible_cohort_sources", net_return=net_return)
            return
        weight = 1.0 / len(leads)
        for row in leads:
            labels = self._source_learning_labels(row)
            platform = next((value for dimension, value in labels if dimension == "platform"), "")
            for dimension, value in labels:
                self.db.execute(
                    """
                    INSERT OR IGNORE INTO source_utility_outcomes(
                        outcome_key,event_id,token_id,decision_id,cohort_id,attribution_version,
                        source_observation_id,dimension,value,origin_platform,attribution_basis,
                        attribution_weight,net_return,opened_at,closed_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        outcome_key,
                        int(position.event_id),
                        str(position.token_id),
                        int(position.decision_id),
                        int(position.cohort_id),
                        self.PAPER_SOURCE_ATTRIBUTION_VERSION,
                        int(row["id"]),
                        dimension,
                        value,
                        platform,
                        "discovery_lead",
                        weight,
                        net_return,
                        opened_at,
                        closed_at,
                    ),
                )
        record_attempt(
            "attributed",
            "attributed_admitted_cohort",
            eligible_source_count=len(leads),
            net_return=net_return,
        )

    def source_learning_summary(self, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            return self.source_learning_summary_from_connection(self.db, **kwargs)

    @classmethod
    def source_learning_summary_from_connection(
        cls,
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
        min_closed_outcomes: float = 20,
        min_event_days: int = 10,
        min_losing_outcomes: int = 5,
        entity_min_closed_outcomes: float = 30,
        entity_min_event_days: int = 15,
        entity_min_platforms: int = 2,
    ) -> dict[str, Any]:
        """Describe forward source usefulness; only mature closed-Paper outcomes activate rotation hints."""
        now = utcnow()
        start = iso(now - timedelta(days=max(1, min(3650, int(lookback_days)))))
        observation_rows = list(
                connection.execute(
                    """
                    SELECT o.id,o.source,o.source_kind,o.role,o.published_at,o.observed_at,
                           o.ingested_at,o.raw_json,eo.event_id,
                           e.topic AS event_topic
                    FROM observations o
                    LEFT JOIN event_observations eo ON eo.observation_id=o.id
                    LEFT JOIN events e ON e.id=eo.event_id
                    WHERE o.capture_phase='live' AND o.observed_at>=?
                    ORDER BY o.observed_at,o.id
                    """,
                    (start,),
                )
            )
        decision_rows = list(
                connection.execute(
                    "SELECT id,event_id,action,created_at FROM decisions WHERE created_at>=?",
                    (start,),
                )
            )
        has_outcomes = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_utility_outcomes'"
        ).fetchone() is not None
        outcome_rows = (
            list(
                connection.execute(
                    "SELECT * FROM source_utility_outcomes WHERE closed_at>=? ORDER BY closed_at,id",
                    (start,),
                )
            )
            if has_outcomes else []
        )
        exact_outcome_rows = [
            row for row in outcome_rows
            if str(row["attribution_version"] or "") == cls.PAPER_SOURCE_ATTRIBUTION_VERSION
        ]
        legacy_outcome_rows = [
            row for row in outcome_rows
            if str(row["attribution_version"] or "") != cls.PAPER_SOURCE_ATTRIBUTION_VERSION
        ]
        has_attribution_attempts = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='paper_source_attribution_attempts'"
        ).fetchone() is not None
        attribution_attempts = (
            list(
                connection.execute(
                    "SELECT * FROM paper_source_attribution_attempts "
                    "WHERE closed_at>=? ORDER BY closed_at,outcome_key",
                    (start,),
                )
            )
            if has_attribution_attempts else []
        )

        candidate_events = {
            int(row["event_id"]) for row in decision_rows
            if str(row["action"] or "").upper() == "CANDIDATE"
        }
        candidate_times: dict[int, Any] = {}
        for row in decision_rows:
            if str(row["action"] or "").upper() != "CANDIDATE":
                continue
            event_id = int(row["event_id"])
            created_at = parse_time(row["created_at"])
            previous = candidate_times.get(event_id)
            if previous is None or created_at < previous:
                candidate_times[event_id] = created_at
        event_first_eligible: dict[int, Any] = {}
        records: list[tuple[sqlite3.Row, list[tuple[str, str]], int | None, bool]] = []
        for row in observation_rows:
            event_id = int(row["event_id"]) if row["event_id"] is not None else None
            observed = parse_time(row["observed_at"])
            candidate_at = candidate_times.get(event_id) if event_id is not None else None
            eligible = bool(
                candidate_at is not None
                and str(row["role"] or "").lower() in {"feature", "confirmation"}
                and observed <= candidate_at
                and parse_time(row["ingested_at"]) <= candidate_at
                and (
                    row["published_at"] is None
                    or parse_time(row["published_at"]) <= candidate_at
                )
            )
            if event_id is not None and eligible:
                previous = event_first_eligible.get(event_id)
                if previous is None or observed < previous:
                    event_first_eligible[event_id] = observed
            records.append((row, cls._source_learning_labels(row), event_id, eligible))

        diagnostic: dict[tuple[str, str], dict[str, Any]] = {}
        for row, labels, event_id, eligible in records:
            observed = parse_time(row["observed_at"])
            role = str(row["role"] or "").lower()
            for key in labels:
                metric = diagnostic.setdefault(
                    key,
                    {
                        "observations": 0, "eligible_observations": 0, "context_observations": 0,
                        "feature_observations": 0, "confirmation_observations": 0,
                        "identity_observations": 0, "promotion_observations": 0,
                        "events": set(), "early_events": set(), "candidate_events": set(), "last_observed_at": None,
                    },
                )
                metric["observations"] += 1
                metric["eligible_observations" if eligible else "context_observations"] += 1
                role_key = f"{role}_observations"
                if role_key in metric:
                    metric[role_key] += 1
                metric["last_observed_at"] = max(str(metric["last_observed_at"] or ""), str(row["observed_at"]))
                if event_id is not None:
                    metric["events"].add(event_id)
                    if eligible and event_id in candidate_events:
                        metric["candidate_events"].add(event_id)
                    first = event_first_eligible.get(event_id)
                    if eligible and first is not None and (observed - first).total_seconds() <= 60:
                        metric["early_events"].add(event_id)

        outcomes: dict[tuple[str, str], dict[str, Any]] = {}
        decision_support_outcomes: dict[tuple[str, str], dict[str, Any]] = {}
        for row in exact_outcome_rows:
            key = (str(row["dimension"]), str(row["value"]))
            basis = str(row["attribution_basis"] or "discovery_lead")
            target = decision_support_outcomes if basis == "decision_support" else outcomes
            metric = target.setdefault(
                key,
                {
                    "weighted_closed": 0.0, "weighted_wins": 0.0, "weighted_losses": 0.0,
                    "weighted_downside": 0.0, "weighted_return": 0.0,
                    "outcome_keys": set(), "event_ids": set(), "event_days": set(),
                    "platforms": set(), "last_closed_at": None,
                },
            )
            weight = max(0.0, float(row["attribution_weight"] or 0))
            net_return = float(row["net_return"] or 0)
            metric["weighted_closed"] += weight
            metric["weighted_wins"] += weight if net_return > 0 else 0.0
            metric["weighted_losses"] += weight if net_return <= 0 else 0.0
            metric["weighted_downside"] += weight if net_return <= -0.25 else 0.0
            metric["weighted_return"] += weight * net_return
            metric["outcome_keys"].add(str(row["outcome_key"]))
            metric["event_ids"].add(int(row["event_id"]))
            metric["event_days"].add(str(row["opened_at"])[:10])
            if row["origin_platform"]:
                metric["platforms"].add(str(row["origin_platform"]))
            metric["last_closed_at"] = max(str(metric["last_closed_at"] or ""), str(row["closed_at"]))

        items: list[dict[str, Any]] = []
        all_keys = set(diagnostic) | set(outcomes) | set(decision_support_outcomes)
        for dimension, value in all_keys:
            observed = diagnostic.get((dimension, value), {})
            outcome = outcomes.get((dimension, value), {})
            decision_support = decision_support_outcomes.get((dimension, value), {})
            event_count = len(observed.get("events", set()))
            early_count = len(observed.get("early_events", set()))
            candidate_count = len(observed.get("candidate_events", set()))
            observations = int(observed.get("observations", 0))
            eligible_observations = int(observed.get("eligible_observations", 0))
            weighted_closed = float(outcome.get("weighted_closed", 0.0))
            mean_return = (
                float(outcome.get("weighted_return", 0.0)) / weighted_closed if weighted_closed > 0 else None
            )
            win_rate = (
                float(outcome.get("weighted_wins", 0.0)) / weighted_closed if weighted_closed > 0 else None
            )
            downside_rate = (
                float(outcome.get("weighted_downside", 0.0)) / weighted_closed if weighted_closed > 0 else None
            )
            required_closed = entity_min_closed_outcomes if dimension == "entity" else min_closed_outcomes
            required_days = entity_min_event_days if dimension == "entity" else min_event_days
            platform_count = len(outcome.get("platforms", set()))
            active = (
                weighted_closed >= required_closed
                and len(outcome.get("event_days", set())) >= required_days
                and float(outcome.get("weighted_losses", 0.0)) >= min_losing_outcomes
                and (dimension != "entity" or platform_count >= entity_min_platforms)
                and dimension in {"platform", "source_kind", "entity", "source"}
            )
            shrunk_utility = 0.0
            if mean_return is not None:
                shrunk_utility = weighted_closed / (weighted_closed + 20.0) * mean_return
            multiplier = 1.0 if not active else max(0.75, min(1.25, 1.0 + shrunk_utility * 0.5))
            confidence = min(1.0, weighted_closed / max(1.0, float(required_closed)))
            support_weighted_closed = float(decision_support.get("weighted_closed", 0.0))
            support_mean_return = (
                float(decision_support.get("weighted_return", 0.0)) / support_weighted_closed
                if support_weighted_closed > 0 else None
            )
            support_win_rate = (
                float(decision_support.get("weighted_wins", 0.0)) / support_weighted_closed
                if support_weighted_closed > 0 else None
            )
            items.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "observations": observations,
                    "eligible_observations": eligible_observations,
                    "decision_eligible_observations": eligible_observations,
                    "context_observations": int(observed.get("context_observations", 0)),
                    "feature_observations": int(observed.get("feature_observations", 0)),
                    "confirmation_observations": int(observed.get("confirmation_observations", 0)),
                    "identity_observations": int(observed.get("identity_observations", 0)),
                    "promotion_observations": int(observed.get("promotion_observations", 0)),
                    "event_count": event_count,
                    "early_event_count": early_count,
                    "early_event_rate": round(early_count / event_count, 4) if event_count else None,
                    "eligible_observation_rate": round(eligible_observations / observations, 4) if observations else None,
                    "candidate_event_count": candidate_count if decision_rows else None,
                    "candidate_event_rate": round(candidate_count / event_count, 4) if event_count and decision_rows else None,
                    "weighted_closed_paper_outcomes": round(weighted_closed, 4),
                    "weighted_losing_paper_outcomes": round(float(outcome.get("weighted_losses", 0.0)), 4),
                    "distinct_closed_paper_outcomes": len(outcome.get("outcome_keys", set())),
                    "distinct_closed_event_count": len(outcome.get("event_ids", set())),
                    "paper_win_rate": round(win_rate, 4) if win_rate is not None else None,
                    "paper_mean_net_return": round(mean_return, 6) if mean_return is not None else None,
                    "paper_downside_rate": round(downside_rate, 4) if downside_rate is not None else None,
                    "decision_support_weighted_closed_paper_outcomes": round(support_weighted_closed, 4),
                    "decision_support_distinct_closed_paper_outcomes": len(
                        decision_support.get("outcome_keys", set())
                    ),
                    "decision_support_paper_win_rate": (
                        round(support_win_rate, 4) if support_win_rate is not None else None
                    ),
                    "decision_support_paper_mean_net_return": (
                        round(support_mean_return, 6) if support_mean_return is not None else None
                    ),
                    "event_day_count": len(outcome.get("event_days", set())),
                    "platform_count": platform_count,
                    "confidence": round(confidence, 4),
                    "maturity_progress": round(confidence, 4),
                    "rotation_active": active,
                    "rotation_multiplier": round(multiplier, 4),
                    "last_observed_at": observed.get("last_observed_at"),
                    "last_closed_at": outcome.get("last_closed_at"),
                }
            )
        items.sort(
            key=lambda item: (
                not bool(item["rotation_active"]),
                -float(item["rotation_multiplier"]),
                -float(item["confidence"]),
                -int(item["event_count"]),
                str(item["dimension"]),
                str(item["value"]).casefold(),
            )
        )
        return {
            "status": "learning_active" if any(item["rotation_active"] for item in items) else "collecting_samples",
            "lookback_days": int(lookback_days),
            "items": items[:500],
            "summary": {
                "observations": len(observation_rows),
                "decisions": len(decision_rows),
                "closed_paper_outcomes": len({
                    str(row["outcome_key"]) for row in exact_outcome_rows
                    if str(row["attribution_basis"] or "discovery_lead") != "decision_support"
                }),
                "decision_support_outcomes": len({
                    str(row["outcome_key"]) for row in exact_outcome_rows
                    if str(row["attribution_basis"] or "discovery_lead") == "decision_support"
                }),
                "legacy_event_window_outcomes": len({
                    str(row["outcome_key"]) for row in legacy_outcome_rows
                }),
                "closed_attribution_attempts": len(attribution_attempts),
                "attributed_closed_outcomes": sum(
                    1 for row in attribution_attempts if str(row["status"]) == "attributed"
                ),
                "unattributed_closed_outcomes": sum(
                    1 for row in attribution_attempts if str(row["status"]) != "attributed"
                ),
                "closed_attribution_coverage_rate": (
                    round(
                        sum(1 for row in attribution_attempts if str(row["status"]) == "attributed")
                        / len(attribution_attempts),
                        4,
                    )
                    if attribution_attempts else None
                ),
                "attribution_skip_reasons": [
                    {"reason": reason, "count": count}
                    for reason, count in sorted(
                        {
                            str(row["reason"]): sum(
                                1 for item in attribution_attempts
                                if str(item["status"]) != "attributed"
                                and str(item["reason"]) == str(row["reason"])
                            )
                            for row in attribution_attempts
                            if str(row["status"]) != "attributed"
                        }.items()
                    )
                ],
                "active_labels": sum(1 for item in items if item["rotation_active"]),
            },
            "activation_policy": {
                "minimum_closed_outcomes": float(min_closed_outcomes),
                "minimum_event_days": int(min_event_days),
                "minimum_losing_outcomes": int(min_losing_outcomes),
                "entity_minimum_closed_outcomes": float(entity_min_closed_outcomes),
                "entity_minimum_event_days": int(entity_min_event_days),
                "entity_minimum_platforms": int(entity_min_platforms),
                "maximum_rotation_multiplier": 1.25,
                "minimum_exploration_fraction": 0.40,
                "affects": "agent_watch_rotation_only",
                "rotation_basis": "discovery_lead",
                "paper_attribution_version": cls.PAPER_SOURCE_ATTRIBUTION_VERSION,
                "paper_attribution_scope": "selected_closed_paper_decision_cohort_only",
                "legacy_outcomes_affect_learning": False,
                "decision_support_affects": "descriptive_only",
            },
            "as_of": iso(now),
        }

    @classmethod
    def _shadow_strategy_labels(
        cls,
        decision: CandidateDecision,
        *,
        event: Mapping[str, Any],
        token: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        leads: Iterable[Mapping[str, Any]],
    ) -> list[tuple[str, str]]:
        """Freeze coarse decision-time research strata; none of them changes strategy."""

        def number(row: Mapping[str, Any], name: str) -> float | None:
            try:
                value = row[name]
            except (KeyError, IndexError, TypeError):
                return None
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        def bucket(value: float | None, cuts: tuple[float, ...], names: tuple[str, ...]) -> str:
            if value is None:
                return "unknown"
            for index, cut in enumerate(cuts):
                if value < cut:
                    return names[index]
            return names[-1]

        decision_at = parse_time(decision.created_at)
        first_seen = parse_time(event["first_seen_at"])
        token_created = parse_time(token["created_at"]) if token["created_at"] else None
        lead_rows = list(leads)
        origins: set[str] = set()
        feature_count = 0
        confirmation_count = 0
        public_figure_context = "none_observed"
        for row in lead_rows:
            labels = dict(cls._source_learning_labels(row))
            origin = labels.get("entity") or labels.get("source") or labels.get("source_kind")
            if origin:
                origins.add(origin)
            role = str(row["role"] or "").lower()
            feature_count += int(role == "feature")
            confirmation_count += int(role == "confirmation")
            account_type = labels.get("account_type", "")
            if account_type in {
                "public_figure", "politician", "celebrity", "executive", "institution",
                "official", "government",
            }:
                public_figure_context = "context_candidate"
            try:
                raw = json.loads(str(row["raw_json"] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = {}
            if isinstance(raw, dict) and str(raw.get("verification_status") or "") == "browser_exact_entity_observation":
                public_figure_context = "verified_original_observation"

        buys = number(snapshot, "buys_5m") or 0.0
        sells = number(snapshot, "sells_5m") or 0.0
        transactions = buys + sells
        buy_ratio = buys / transactions if transactions > 0 else None
        safety = "unknown"
        if snapshot["honeypot"] is not None and bool(snapshot["honeypot"]):
            safety = "honeypot"
        elif snapshot["sellable"] is not None and not bool(snapshot["sellable"]):
            safety = "not_sellable"
        elif snapshot["honeypot"] is False and snapshot["sellable"] is True:
            safety = "checked_clear"
        elif snapshot["honeypot"] is False or snapshot["sellable"] is True:
            safety = "partially_checked"

        evidence_mix = (
            "feature_and_confirmation" if feature_count and confirmation_count
            else "feature_only" if feature_count
            else "confirmation_only" if confirmation_count
            else "none"
        )
        event_age_minutes = max(0.0, (decision_at - first_seen).total_seconds() / 60.0)
        token_age_minutes = (
            max(0.0, (decision_at - token_created).total_seconds() / 60.0)
            if token_created is not None else None
        )
        labels = [
            ("event_topic", str(event["topic"] or "unknown")),
            ("attention_bucket", bucket(number(event, "attention"), (50, 70, 85), ("lt50", "50_69", "70_84", "85_plus"))),
            ("event_age_bucket", bucket(event_age_minutes, (5, 30, 120), ("lt5m", "5_29m", "30_119m", "120m_plus"))),
            ("eligible_origin_bucket", bucket(float(len(origins)), (2, 3, 5), ("one", "two", "three_four", "five_plus"))),
            ("evidence_mix", evidence_mix),
            ("public_figure_context", public_figure_context),
            ("chain", str(token["chain"] or "unknown").lower()),
            ("token_age_bucket", bucket(token_age_minutes, (5, 30, 120), ("lt5m", "5_29m", "30_119m", "120m_plus"))),
            ("liquidity_bucket", bucket(number(snapshot, "liquidity_usd"), (5_000, 25_000, 100_000), ("lt5k", "5k_25k", "25k_100k", "100k_plus"))),
            ("market_cap_bucket", bucket(number(snapshot, "market_cap_usd"), (50_000, 250_000, 1_000_000), ("lt50k", "50k_250k", "250k_1m", "1m_plus"))),
            ("volume_5m_bucket", bucket(number(snapshot, "volume_5m_usd"), (1_000, 10_000, 50_000), ("lt1k", "1k_10k", "10k_50k", "50k_plus"))),
            ("buy_pressure_bucket", bucket(buy_ratio, (0.45, 0.55, 0.70), ("sell_dominant", "balanced", "buy_leaning", "buy_dominant"))),
            ("safety_state", safety),
            ("candidate_score_bucket", bucket(float(decision.score), (60, 75, 90), ("lt60", "60_74", "75_89", "90_plus"))),
            ("match_score_bucket", bucket(float(decision.match_score), (60, 80, 95), ("lt60", "60_79", "80_94", "95_plus"))),
            ("canonical_margin_bucket", bucket(float(decision.canonical_margin), (3, 8, 15), ("lt3", "3_7", "8_14", "15_plus"))),
            ("requested_position_bucket", bucket(float(decision.position_usd), (1, 10, 25), ("zero", "lt10", "10_24", "25_plus"))),
        ]
        labels.extend(
            ("decision_reason", re.sub(r"[^a-z0-9_-]", "_", str(reason).lower())[:120] or "unknown")
            for reason in decision.rejected_reasons
        )
        return list(dict.fromkeys(labels))

    def create_shadow_event_cohort(
        self,
        decision: CandidateDecision,
        *,
        decision_id: int,
        source_observation_ids: Iterable[int],
    ) -> int | None:
        """Freeze the first WAIT/REJECT/CANDIDATE per event without changing strategy."""
        action = str(decision.action).upper()
        admission_key = f"{self.SHADOW_EVENT_ADMISSION_VERSION}:{int(decision_id)}"
        cohort_key = hashlib.sha256(
            f"{self.SHADOW_EVENT_COHORT_VERSION}\n{int(decision.event_id)}\n{action}".encode("utf-8")
        ).hexdigest()
        decision_at = iso(decision.created_at)
        with self._lock, self.db:
            prior_admission = self.db.execute(
                "SELECT cohort_id FROM shadow_event_admission_attempts WHERE admission_key=?",
                (admission_key,),
            ).fetchone()
            if prior_admission is not None:
                return int(prior_admission["cohort_id"]) if prior_admission["cohort_id"] else None

            observation_ids: list[int] = []

            def record_admission(
                status: str,
                reason: str,
                *,
                cohort_id: int | None = None,
                eligible_source_count: int = 0,
            ) -> None:
                self.db.execute(
                    """
                    INSERT INTO shadow_event_admission_attempts(
                        admission_key,version,decision_id,event_id,token_id,requested_action,
                        status,reason,cohort_id,source_observation_count,eligible_source_count,attempted_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        admission_key,
                        self.SHADOW_EVENT_ADMISSION_VERSION,
                        int(decision_id),
                        int(decision.event_id),
                        str(decision.token_id or ""),
                        action,
                        str(status),
                        str(reason),
                        cohort_id,
                        len(observation_ids),
                        max(0, int(eligible_source_count)),
                        iso(),
                    ),
                )

            if action not in {"WAIT", "REJECT", "CANDIDATE"}:
                record_admission("skipped", "unsupported_action")
                return None
            if not decision.token_id:
                record_admission("skipped", "missing_token_id")
                return None
            observation_ids = sorted({
                int(value) for value in source_observation_ids if int(value) > 0
            })
            existing = list(
                self.db.execute(
                    "SELECT id,action FROM shadow_event_cohorts WHERE event_id=? ORDER BY id",
                    (int(decision.event_id),),
                )
            )
            same_action = next(
                (row for row in existing if str(row["action"]).upper() == action), None
            )
            if same_action:
                cohort_id = int(same_action["id"])
                record_admission(
                    "already_admitted", "already_admitted_same_action", cohort_id=cohort_id
                )
                return cohort_id
            if action == "WAIT":
                candidate = next(
                    (row for row in existing if str(row["action"]).upper() == "CANDIDATE"), None
                )
                if candidate:
                    cohort_id = int(candidate["id"])
                    record_admission(
                        "already_admitted", "wait_superseded_by_candidate", cohort_id=cohort_id
                    )
                    return cohort_id
            snapshot = self.db.execute(
                """
                SELECT * FROM token_snapshots
                WHERE token_id=? AND observed_at<=? AND ingested_at<=?
                  AND ingested_at>=observed_at AND price_usd>0
                ORDER BY observed_at DESC,id DESC LIMIT 1
                """,
                (decision.token_id, decision_at, decision_at),
            ).fetchone()
            if snapshot is None:
                record_admission("skipped", "missing_entry_snapshot")
                return None
            if not observation_ids:
                record_admission("skipped", "missing_observation_ids")
                return None
            placeholders = ",".join("?" for _ in observation_ids)
            eligible = list(
                self.db.execute(
                    f"""
                    SELECT o.id,o.source,o.source_kind,o.role,o.observed_at,o.raw_json,
                           e.topic AS event_topic
                    FROM observations o
                    JOIN event_observations eo ON eo.observation_id=o.id
                    JOIN events e ON e.id=eo.event_id
                    WHERE eo.event_id=? AND o.id IN ({placeholders})
                      AND o.capture_phase='live' AND o.role IN ('feature','confirmation')
                      AND o.observed_at<=? AND o.ingested_at<=?
                      AND (o.published_at IS NULL OR o.published_at<=?)
                    ORDER BY o.observed_at,o.id
                    """,
                    (int(decision.event_id), *observation_ids, decision_at, decision_at, decision_at),
                )
            )
            if not eligible:
                record_admission("skipped", "no_eligible_leads")
                return None
            first_at = parse_time(eligible[0]["observed_at"])
            leads = [
                row for row in eligible
                if (parse_time(row["observed_at"]) - first_at).total_seconds() <= 60
            ]
            if not leads:
                record_admission("skipped", "no_eligible_leads")
                return None
            event_row = self.db.execute(
                "SELECT * FROM events WHERE id=?", (int(decision.event_id),)
            ).fetchone()
            token_row = self.db.execute(
                "SELECT * FROM tokens WHERE token_id=?", (decision.token_id,)
            ).fetchone()
            if event_row is None or token_row is None:
                record_admission("skipped", "missing_event_or_token")
                return None
            cursor = self.db.execute(
                """
                INSERT INTO shadow_event_cohorts(
                    cohort_key,version,event_id,token_id,decision_id,action,decision_at,
                    entry_snapshot_id,entry_snapshot_at,entry_price,eligible_source_count,status,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',?)
                """,
                (
                    cohort_key, self.SHADOW_EVENT_COHORT_VERSION, int(decision.event_id), decision.token_id,
                    int(decision_id), action, decision_at, int(snapshot["id"]),
                    str(snapshot["observed_at"]), float(snapshot["price_usd"]), len(leads), iso(),
                ),
            )
            cohort_id = int(cursor.lastrowid)
            weight = 1.0 / len(leads)
            for row in leads:
                labels = self._source_learning_labels(row)
                platform = next((value for dimension, value in labels if dimension == "platform"), "")
                for dimension, value in labels:
                    self.db.execute(
                        """
                        INSERT INTO shadow_event_cohort_labels(
                            cohort_id,source_observation_id,dimension,value,origin_platform,attribution_weight
                        ) VALUES(?,?,?,?,?,?)
                        """,
                        (cohort_id, int(row["id"]), dimension, value, platform, weight),
                    )
            for dimension, value in self._shadow_strategy_labels(
                decision, event=event_row, token=token_row, snapshot=snapshot, leads=leads
            ):
                self.db.execute(
                    """
                    INSERT INTO shadow_event_cohort_labels(
                        cohort_id,source_observation_id,dimension,value,origin_platform,attribution_weight
                    ) VALUES(?,0,?,?,?,1)
                    """,
                    (cohort_id, dimension, value, ""),
                )
            record_admission(
                "created", "created", cohort_id=cohort_id,
                eligible_source_count=len(leads),
            )
            return cohort_id

    def finalize_shadow_event_outcomes(
        self,
        *,
        now: Any = None,
        horizons_minutes: Iterable[int] | None = None,
        max_lateness_minutes: int = 30,
    ) -> dict[str, int]:
        """Append fixed-horizon market follow-through using only snapshots already observed locally."""
        evaluated_at = parse_time(now or utcnow())
        horizons = tuple(
            sorted({max(1, int(value)) for value in (horizons_minutes or self.SHADOW_EVENT_HORIZONS_MINUTES)})
        )
        observed_count = 0
        missing_count = 0
        completed_count = 0
        with self._lock, self.db:
            cohorts = list(
                self.db.execute(
                    "SELECT * FROM shadow_event_cohorts WHERE status='pending' ORDER BY decision_at,id"
                )
            )
            for cohort in cohorts:
                existing = {
                    int(row["horizon_minutes"])
                    for row in self.db.execute(
                        "SELECT horizon_minutes FROM shadow_event_outcomes WHERE cohort_id=?",
                        (int(cohort["id"]),),
                    )
                }
                for horizon in horizons:
                    if horizon in existing:
                        continue
                    target = parse_time(cohort["decision_at"]) + timedelta(minutes=horizon)
                    if evaluated_at < target:
                        continue
                    deadline = target + timedelta(minutes=max(1, int(max_lateness_minutes)))
                    upper = min(evaluated_at, deadline)
                    snapshot = self.db.execute(
                        """
                        SELECT id,observed_at,ingested_at,price_usd FROM token_snapshots
                        WHERE token_id=? AND observed_at>=? AND observed_at<=?
                          AND ingested_at>=? AND ingested_at<=?
                          AND ingested_at>=observed_at AND price_usd>0
                        ORDER BY ingested_at,observed_at,id LIMIT 1
                        """,
                        (
                            str(cohort["token_id"]), iso(target), iso(upper),
                            iso(target), iso(upper),
                        ),
                    ).fetchone()
                    if snapshot is not None:
                        path = list(
                            self.db.execute(
                                """
                                SELECT price_usd FROM token_snapshots
                                WHERE token_id=? AND observed_at>=? AND observed_at<=?
                                  AND ingested_at IS NOT NULL AND ingested_at<=?
                                  AND ingested_at>=observed_at AND price_usd>0
                                ORDER BY observed_at,id
                                """,
                                (
                                    str(cohort["token_id"]), str(cohort["entry_snapshot_at"]),
                                    str(snapshot["observed_at"]), str(snapshot["ingested_at"]),
                                ),
                            )
                        )
                        entry_price = float(cohort["entry_price"])
                        returns = [float(row["price_usd"]) / entry_price - 1.0 for row in path]
                        raw_return = float(snapshot["price_usd"]) / entry_price - 1.0
                        self.db.execute(
                            """
                            INSERT INTO shadow_event_outcomes(
                                cohort_id,horizon_minutes,target_at,status,outcome_snapshot_id,
                                outcome_observed_at,outcome_price,raw_return,maximum_return,minimum_return,
                                snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'observed',?,?,?,?,?,?,?,?)
                            """,
                            (
                                int(cohort["id"]), horizon, iso(target), int(snapshot["id"]),
                                str(snapshot["observed_at"]), float(snapshot["price_usd"]), raw_return,
                                max(returns) if returns else raw_return, min(returns) if returns else raw_return,
                                len(path), iso(evaluated_at),
                            ),
                        )
                        observed_count += 1
                    elif evaluated_at >= deadline:
                        self.db.execute(
                            """
                            INSERT INTO shadow_event_outcomes(
                                cohort_id,horizon_minutes,target_at,status,snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'missing',0,?)
                            """,
                            (int(cohort["id"]), horizon, iso(target), iso(evaluated_at)),
                        )
                        missing_count += 1
                outcome_total = int(
                    self.db.execute(
                        "SELECT COUNT(*) FROM shadow_event_outcomes WHERE cohort_id=?",
                        (int(cohort["id"]),),
                    ).fetchone()[0]
                )
                if outcome_total >= len(horizons):
                    self.db.execute(
                        "UPDATE shadow_event_cohorts SET status='complete' WHERE id=?",
                        (int(cohort["id"]),),
                    )
                    completed_count += 1
        return {
            "cohorts_checked": len(cohorts),
            "outcomes_observed": observed_count,
            "outcomes_missing": missing_count,
            "cohorts_completed": completed_count,
        }

    @staticmethod
    def _information_first_label(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().casefold())[:160]

    @classmethod
    def _information_first_ilg_definition(cls) -> dict[str, Any]:
        return {
            "version": cls.INFORMATION_FIRST_ILG_VERSION,
            "activity": {
                "volume_5m_usd": cls.INFORMATION_FIRST_ILG_VOLUME_5M_USD,
                "transactions_5m": cls.INFORMATION_FIRST_ILG_TRANSACTIONS_5M,
                "operator": "strict_greater_than_any",
                "market_cap_excluded": True,
            },
            "window_minutes": cls.INFORMATION_FIRST_ILG_WINDOW_MINUTES,
            "terminal_grace_minutes": cls.INFORMATION_FIRST_ILG_TERMINAL_GRACE_MINUTES,
            "time_basis": "durable_recorded_at",
            "interval_censored": True,
            "same_surface_only": True,
            "affects": "none",
        }

    @staticmethod
    def _information_first_snapshot_surface(row: sqlite3.Row) -> dict[str, str] | None:
        try:
            raw = json.loads(str(row["raw_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            return None
        raw = raw if isinstance(raw, dict) else {}
        pair = raw.get("pair") if isinstance(raw.get("pair"), dict) else raw
        provider = str(row["provider"] or "").strip().casefold()
        chain_id = str(pair.get("chainId") or pair.get("chain_id") or "").strip().casefold()
        dex_id = str(pair.get("dexId") or pair.get("dex_id") or "").strip().casefold()
        pair_address = str(
            pair.get("pairAddress") or pair.get("pair_address") or ""
        ).strip().casefold()
        if not all((provider, chain_id, dex_id, pair_address)):
            return None
        key = json.dumps(
            [provider, chain_id, dex_id, pair_address],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return {
            "key": key,
            "provider": provider,
            "chain_id": chain_id,
            "dex_id": dex_id,
            "pair_address": pair_address,
        }

    def _create_information_first_ilg_cohort(
        self, shadow_cohort_id: int, *, enrolled_at: Any = None
    ) -> int | None:
        enrolled = parse_time(enrolled_at or utcnow())
        registration = self.db.execute(
            "SELECT * FROM information_first_ilg_registrations WHERE definition_version=?",
            (self.INFORMATION_FIRST_ILG_VERSION,),
        ).fetchone()
        shadow = self.db.execute(
            "SELECT * FROM information_first_shadow_cohorts WHERE id=?",
            (int(shadow_cohort_id),),
        ).fetchone()
        if registration is None or shadow is None:
            return None
        if parse_time(shadow["signal_available_at"]) < parse_time(registration["registered_at"]):
            return None
        try:
            definition = json.loads(str(registration["definition_json"]))
            activity = definition["activity"]
            volume_threshold = float(activity["volume_5m_usd"])
            transactions_threshold = int(activity["transactions_5m"])
            window_minutes = int(definition["window_minutes"])
            grace_minutes = int(definition["terminal_grace_minutes"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        existing = self.db.execute(
            "SELECT id FROM information_first_ilg_cohorts WHERE shadow_cohort_id=?",
            (int(shadow_cohort_id),),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])

        signal = parse_time(shadow["signal_available_at"])
        baseline = self.db.execute(
            """
            SELECT * FROM token_snapshots
            WHERE token_id=? AND observed_at<=? AND ingested_at<=? AND recorded_at<=?
              AND observed_at<=ingested_at AND ingested_at<=recorded_at
              AND volume_5m_usd IS NOT NULL AND buys_5m IS NOT NULL AND sells_5m IS NOT NULL
            ORDER BY recorded_at DESC,observed_at DESC,id DESC LIMIT 1
            """,
            (str(shadow["token_id"]), iso(signal), iso(signal), iso(signal)),
        ).fetchone()
        eligibility = "ineligible_activity_baseline_missing"
        reason = "no_strictly_forward_complete_baseline"
        transactions = None
        surface = None
        if baseline is not None:
            transactions = int(baseline["buys_5m"]) + int(baseline["sells_5m"])
            surface = self._information_first_snapshot_surface(baseline)
            if surface is None:
                eligibility = "ineligible_activity_surface_unknown"
                reason = "provider_chain_dex_pair_required"
            elif (
                float(baseline["volume_5m_usd"]) > volume_threshold
                or transactions > transactions_threshold
            ):
                eligibility = "already_active_at_signal"
                reason = "baseline_strictly_above_activity_threshold"
            else:
                eligibility = "eligible_at_risk"
                reason = "baseline_at_or_below_both_activity_thresholds"
        window_end = signal + timedelta(minutes=window_minutes)
        terminal = window_end + timedelta(minutes=grace_minutes)
        cursor = self.db.execute(
            """
            INSERT INTO information_first_ilg_cohorts(
                definition_version,shadow_cohort_id,enrolled_at,signal_available_at,token_id,
                eligibility,eligibility_reason,window_end_at,terminal_at,baseline_snapshot_id,
                baseline_recorded_at,baseline_volume_5m_usd,baseline_transactions_5m,
                surface_key,surface_provider,surface_chain_id,surface_dex_id,surface_pair_address,
                definition_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                self.INFORMATION_FIRST_ILG_VERSION, int(shadow_cohort_id), iso(enrolled), iso(signal),
                str(shadow["token_id"]), eligibility, reason, iso(window_end), iso(terminal),
                int(baseline["id"]) if baseline is not None else None,
                str(baseline["recorded_at"]) if baseline is not None else None,
                float(baseline["volume_5m_usd"]) if baseline is not None else None,
                transactions, surface["key"] if surface else None,
                surface["provider"] if surface else None, surface["chain_id"] if surface else None,
                surface["dex_id"] if surface else None, surface["pair_address"] if surface else None,
                str(registration["definition_json"]),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _information_first_source_facts(row: sqlite3.Row) -> tuple[str, str, str]:
        try:
            raw = json.loads(str(row["raw_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            raw = {}
        raw = raw if isinstance(raw, dict) else {}
        browser = raw.get("browser") if isinstance(raw.get("browser"), dict) else {}
        source = str(row["source"] or "").strip().casefold()[:200]
        source_kind = str(row["source_kind"] or "").strip().casefold()[:80]
        entity_id = str(raw.get("source_entity_id") or "").strip().casefold()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?", entity_id):
            entity_id = ""
        if source_kind in {"social", "official_social"}:
            origin = f"entity:{entity_id}" if entity_id else source
        else:
            publisher_url = str(raw.get("publisher_url") or "")
            article_url = str(row["url"] or "")
            origin = (urlparse(publisher_url).netloc or urlparse(article_url).netloc or source).casefold()
        platform = str(browser.get("platform") or raw.get("platform") or "").strip().casefold()
        if not platform:
            platform = source_kind
        return origin[:240], platform[:80], entity_id

    def create_information_first_shadow_cohort(
        self,
        event_id: int,
        token_id: str,
        *,
        decision_id: int,
        accepted_observation_ids: Iterable[int],
        captured_at: Any = None,
        relation_available_at: Any = None,
        candidate_facts: Mapping[str, Any] | None = None,
    ) -> int | None:
        """Freeze one information-first cohort from a final decision's known inputs.

        This is descriptive only. It records contemporaneously available facts and never
        creates a cohort from a later token, snapshot, or observation.
        """
        captured = parse_time(captured_at or utcnow())
        if captured > utcnow() + timedelta(seconds=5):
            raise ValueError("information-first cohort cannot be future-dated")
        relation_available = parse_time(relation_available_at or captured)
        if relation_available > captured:
            raise ValueError("relation availability cannot be after its decision capture")
        captured_text = iso(captured)
        relation_text = iso(relation_available)
        observation_ids = sorted({int(value) for value in accepted_observation_ids if int(value) > 0})
        candidate_facts = candidate_facts if isinstance(candidate_facts, Mapping) else {}
        cohort_key = hashlib.sha256(
            f"{self.INFORMATION_FIRST_SHADOW_VERSION}\n{int(event_id)}\n{str(token_id)}".encode("utf-8")
        ).hexdigest()
        admission_key = f"{self.INFORMATION_FIRST_SHADOW_VERSION}:{int(decision_id)}"
        with self._lock, self.db:
            prior_admission = self.db.execute(
                "SELECT cohort_id FROM information_first_shadow_admission_attempts WHERE admission_key=?",
                (admission_key,),
            ).fetchone()
            if prior_admission is not None:
                return int(prior_admission["cohort_id"]) if prior_admission["cohort_id"] else None

            def record_admission(status: str, reason: str, cohort_id: int | None = None) -> None:
                self.db.execute(
                    """
                    INSERT INTO information_first_shadow_admission_attempts(
                        admission_key,version,decision_id,event_id,token_id,attempted_at,
                        relation_available_at,status,reason,cohort_id
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        admission_key, self.INFORMATION_FIRST_SHADOW_VERSION, int(decision_id),
                        int(event_id), str(token_id), captured_text, relation_text,
                        status, reason, cohort_id,
                    ),
                )

            existing = self.db.execute(
                "SELECT id FROM information_first_shadow_cohorts WHERE version=? AND event_id=? AND token_id=?",
                (self.INFORMATION_FIRST_SHADOW_VERSION, int(event_id), str(token_id)),
            ).fetchone()
            if existing is not None:
                cohort_id = int(existing["id"])
                record_admission("already_admitted", "first_write_wins_event_token", cohort_id)
                return cohort_id
            decision = self.db.execute(
                """
                SELECT created_at FROM decisions
                WHERE id=? AND event_id=? AND token_id=?
                """,
                (int(decision_id), int(event_id), str(token_id)),
            ).fetchone()
            if decision is None:
                record_admission("skipped", "missing_or_mismatched_final_decision")
                return None
            if parse_time(decision["created_at"]) > captured:
                record_admission("skipped", "final_decision_after_capture")
                return None
            event = self.db.execute(
                "SELECT attention FROM events WHERE id=?", (int(event_id),)
            ).fetchone()
            token = self.db.execute(
                """
                SELECT * FROM tokens WHERE token_id=? AND first_seen_at<=?
                """,
                (str(token_id), captured_text),
            ).fetchone()
            if event is None or token is None:
                record_admission("skipped", "missing_event_or_token")
                return None
            if not observation_ids:
                record_admission("skipped", "missing_accepted_observations")
                return None
            placeholders = ",".join("?" for _ in observation_ids)
            leads = list(
                self.db.execute(
                    f"""
                    SELECT o.* FROM observations o
                    JOIN event_observations eo ON eo.observation_id=o.id
                    WHERE eo.event_id=? AND o.capture_phase='live'
                      AND o.role IN ('feature','confirmation')
                      AND o.source_kind<>'onchain'
                      AND o.id IN ({placeholders})
                      AND o.observed_at<=? AND o.ingested_at<=?
                      AND o.ingested_at>=o.observed_at
                      AND (o.published_at IS NULL OR o.published_at<=?)
                    ORDER BY CASE WHEN o.observed_at>o.ingested_at THEN o.observed_at ELSE o.ingested_at END,o.id
                    """,
                    (int(event_id), *observation_ids, captured_text, captured_text, captured_text),
                )
            )
            if not leads:
                record_admission("skipped", "no_eligible_accepted_information_lead")
                return None
            lead = leads[0]
            signal_available = max(
                parse_time(lead["observed_at"]), parse_time(lead["ingested_at"]), relation_available
            )
            signal_text = iso(signal_available)
            entry = self.db.execute(
                """
                SELECT * FROM token_snapshots
                WHERE token_id=? AND observed_at<=? AND ingested_at<=?
                  AND ingested_at>=observed_at AND price_usd>0
                ORDER BY observed_at DESC,id DESC LIMIT 1
                """,
                (str(token_id), signal_text, signal_text),
            ).fetchone()
            target_name = self._information_first_label(token["name"])
            target_symbol = self._information_first_label(token["symbol"])
            peers = list(
                self.db.execute(
                    "SELECT token_id,name,symbol FROM tokens WHERE token_id<>? AND first_seen_at<=?",
                    (str(token_id), signal_text),
                )
            )
            same_name_count = sum(
                bool(target_name) and self._information_first_label(row["name"]) == target_name
                for row in peers
            )
            same_symbol_count = sum(
                bool(target_symbol) and self._information_first_label(row["symbol"]) == target_symbol
                for row in peers
            )
            origins: set[str] = set()
            platforms: set[str] = set()
            source_kinds: set[str] = set()
            entities: set[str] = set()
            for row in leads:
                origin, platform, entity_id = self._information_first_source_facts(row)
                if origin:
                    origins.add(origin)
                if platform:
                    platforms.add(platform)
                source_kinds.add(str(row["source_kind"] or "").casefold())
                if entity_id:
                    entities.add(entity_id)
            transactions = (
                int(entry["buys_5m"]) + int(entry["sells_5m"])
                if entry is not None and entry["buys_5m"] is not None and entry["sells_5m"] is not None else None
            )
            market_complete = (
                entry is not None
                and entry["market_cap_usd"] is not None
                and entry["volume_5m_usd"] is not None
                and transactions is not None
            )
            if not market_complete:
                market_label = "insufficient_market_data"
            elif (
                float(entry["market_cap_usd"]) <= self.INFORMATION_FIRST_SHADOW_QUIET_MARKET_CAP_USD
                and float(entry["volume_5m_usd"]) <= self.INFORMATION_FIRST_SHADOW_QUIET_VOLUME_5M_USD
                and transactions <= self.INFORMATION_FIRST_SHADOW_QUIET_TRANSACTIONS_5M
            ):
                market_label = "low_observed_market_activity"
            else:
                market_label = "observed_market_activity"
            created_at = str(token["created_at"] or "")
            first_seen_at = str(token["first_seen_at"] or "")
            lead_at = parse_time(lead["observed_at"])
            pair_preexistence = (
                "unknown" if not created_at else
                "preexisting" if parse_time(created_at) < lead_at else
                "contemporaneous" if parse_time(created_at) == lead_at else "post_event"
            )
            local_preexistence = (
                "locally_known_before_or_at_information_lead"
                if parse_time(first_seen_at) <= lead_at else "locally_first_seen_after_information_lead"
            )
            features = {
                "event_attention": float(event["attention"]),
                "market_state": {
                    "label": market_label,
                    "liquidity_usd": entry["liquidity_usd"] if entry is not None else None,
                    "market_cap_usd": entry["market_cap_usd"] if entry is not None else None,
                    "volume_5m_usd": entry["volume_5m_usd"] if entry is not None else None,
                    "buys_5m": entry["buys_5m"] if entry is not None else None,
                    "sells_5m": entry["sells_5m"] if entry is not None else None,
                    "transactions_5m": transactions,
                    "entry_snapshot_age_seconds": max(
                        0.0, (signal_available - parse_time(entry["observed_at"])).total_seconds()
                    ) if entry is not None else None,
                    "thresholds": {
                        "market_cap_usd": self.INFORMATION_FIRST_SHADOW_QUIET_MARKET_CAP_USD,
                        "volume_5m_usd": self.INFORMATION_FIRST_SHADOW_QUIET_VOLUME_5M_USD,
                        "transactions_5m": self.INFORMATION_FIRST_SHADOW_QUIET_TRANSACTIONS_5M,
                    },
                },
                "token_preexistence": {
                    "status": "not_available",
                    "reason": "chain_mint_time_not_collected",
                    "local_first_seen_at": first_seen_at,
                    "local_preexistence": local_preexistence,
                },
                "pair_preexistence_descriptive": {
                    "pair_created_at": created_at or None,
                    "status": pair_preexistence,
                    "provider": "token_created_at",
                },
                "same_name_competition": {
                    "normalized_name": target_name or None,
                    "normalized_symbol": target_symbol or None,
                    "preexisting_same_name_count": same_name_count,
                    "preexisting_same_symbol_count": same_symbol_count,
                },
                "candidate_ambiguity": {
                    "candidate_count": candidate_facts.get("candidate_count"),
                    "selected_rank": candidate_facts.get("selected_rank"),
                    "raw_score_margin": candidate_facts.get("raw_score_margin"),
                    "canonical_margin": candidate_facts.get("canonical_margin"),
                    "tie_break_used": bool(candidate_facts.get("tie_break_used")),
                    "mapping_basis": candidate_facts.get("mapping_basis") or "unknown",
                    "candidate_set_truncated": bool(candidate_facts.get("candidate_set_truncated")),
                },
                "attention_source_breadth": {
                    "mode": "descriptive_observed_origins_not_independence_claim",
                    "qualified_observation_count": len(leads),
                    "distinct_origin_count": len(origins),
                    "distinct_platform_count": len(platforms),
                    "distinct_source_kind_count": len(source_kinds),
                    "exact_source_entity_count": len(entities),
                },
                "not_available": ["unique_buyers", "image_similarity", "holder_clusters"],
            }
            cursor = self.db.execute(
                """
                INSERT INTO information_first_shadow_cohorts(
                    cohort_key,version,event_id,token_id,decision_id,captured_at,signal_available_at,
                    relation_available_at,lead_observation_id,
                    lead_observed_at,entry_snapshot_id,entry_snapshot_at,entry_snapshot_ingested_at,
                    entry_price,trackability,features_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    cohort_key, self.INFORMATION_FIRST_SHADOW_VERSION, int(event_id), str(token_id),
                    int(decision_id), captured_text, signal_text, relation_text, int(lead["id"]),
                    str(lead["observed_at"]), int(entry["id"]) if entry is not None else None,
                    str(entry["observed_at"]) if entry is not None else None,
                    str(entry["ingested_at"]) if entry is not None else None,
                    float(entry["price_usd"]) if entry is not None else None,
                    "trackable" if entry is not None else "baseline_missing_at_signal_available",
                    self._json(features), iso(),
                ),
            )
            cohort_id = int(cursor.lastrowid)
            self._create_information_first_ilg_cohort(cohort_id, enrolled_at=captured)
            record_admission(
                "created_baseline_missing" if entry is None else "created",
                "baseline_missing_at_signal_available" if entry is None else "created",
                cohort_id,
            )
            return cohort_id

    def finalize_information_first_shadow_outcomes(
        self,
        *,
        now: Any = None,
        horizons_minutes: Iterable[int] | None = None,
        max_lateness_minutes: int = 30,
    ) -> dict[str, int]:
        """Append fixed-horizon descriptive outcomes without historical backfill."""
        evaluated_at = parse_time(now or utcnow())
        horizons = tuple(sorted({
            max(1, int(value))
            for value in (horizons_minutes or self.INFORMATION_FIRST_SHADOW_HORIZONS_MINUTES)
        }))
        observed_count = 0
        missing_count = 0
        with self._lock, self.db:
            cohorts = list(self.db.execute(
                "SELECT * FROM information_first_shadow_cohorts WHERE trackability='trackable' ORDER BY captured_at,id"
            ))
            for cohort in cohorts:
                existing = {
                    int(row["horizon_minutes"])
                    for row in self.db.execute(
                        "SELECT horizon_minutes FROM information_first_shadow_outcomes WHERE cohort_id=?",
                        (int(cohort["id"]),),
                    )
                }
                for horizon in horizons:
                    if horizon in existing:
                        continue
                    target = parse_time(cohort["signal_available_at"]) + timedelta(minutes=horizon)
                    if evaluated_at < target:
                        continue
                    deadline = target + timedelta(minutes=max(1, int(max_lateness_minutes)))
                    upper = min(evaluated_at, deadline)
                    snapshot = self.db.execute(
                        """
                        SELECT id,observed_at,ingested_at,price_usd FROM token_snapshots
                        WHERE token_id=? AND observed_at>=? AND observed_at<=?
                          AND ingested_at>=? AND ingested_at<=?
                          AND ingested_at>=observed_at AND price_usd>0
                        ORDER BY ingested_at,observed_at,id LIMIT 1
                        """,
                        (str(cohort["token_id"]), iso(target), iso(upper), iso(target), iso(upper)),
                    ).fetchone()
                    if snapshot is not None:
                        path = list(self.db.execute(
                            """
                            SELECT price_usd FROM token_snapshots
                            WHERE token_id=? AND observed_at>=? AND observed_at<=?
                              AND ingested_at IS NOT NULL AND ingested_at<=?
                              AND ingested_at>=observed_at AND price_usd>0
                            ORDER BY observed_at,id
                            """,
                            (
                                str(cohort["token_id"]), str(cohort["entry_snapshot_at"]),
                                str(snapshot["observed_at"]), str(snapshot["ingested_at"]),
                            ),
                        ))
                        entry_price = float(cohort["entry_price"])
                        returns = [float(row["price_usd"]) / entry_price - 1.0 for row in path]
                        raw_return = float(snapshot["price_usd"]) / entry_price - 1.0
                        self.db.execute(
                            """
                            INSERT INTO information_first_shadow_outcomes(
                                cohort_id,horizon_minutes,target_at,status,outcome_snapshot_id,
                                outcome_observed_at,outcome_price,raw_return,maximum_return,minimum_return,
                                snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'observed',?,?,?,?,?,?,?,?)
                            """,
                            (
                                int(cohort["id"]), horizon, iso(target), int(snapshot["id"]),
                                str(snapshot["observed_at"]), float(snapshot["price_usd"]), raw_return,
                                max(returns) if returns else raw_return,
                                min(returns) if returns else raw_return,
                                len(path), iso(evaluated_at),
                            ),
                        )
                        observed_count += 1
                    elif evaluated_at >= deadline:
                        self.db.execute(
                            """
                            INSERT INTO information_first_shadow_outcomes(
                                cohort_id,horizon_minutes,target_at,status,snapshot_count,evaluated_at
                            ) VALUES(?,?,?,'missing',0,?)
                            """,
                            (int(cohort["id"]), horizon, iso(target), iso(evaluated_at)),
                        )
                        missing_count += 1
        outcome_total = int(self.db.execute(
            "SELECT COUNT(*) FROM information_first_shadow_outcomes"
        ).fetchone()[0])
        return {
            "cohorts_checked": len(cohorts),
            "outcomes_observed": observed_count,
            "outcomes_missing": missing_count,
            "pending_outcomes": max(0, len(cohorts) * len(horizons) - outcome_total),
        }

    def finalize_information_first_ilg_outcomes(self, *, now: Any = None) -> dict[str, int]:
        """Freeze the first durable same-surface activity crossing, or its terminal missing state."""
        evaluated = parse_time(now or utcnow())
        crossed_count = 0
        missing_count = 0
        with self._lock, self.db:
            cohorts = list(self.db.execute(
                """
                SELECT c.* FROM information_first_ilg_cohorts c
                LEFT JOIN information_first_ilg_outcomes o ON o.ilg_cohort_id=c.id
                WHERE c.eligibility='eligible_at_risk' AND o.id IS NULL
                ORDER BY c.signal_available_at,c.id
                """
            ))
            for cohort in cohorts:
                try:
                    definition = json.loads(str(cohort["definition_json"]))
                    activity = definition["activity"]
                    volume_threshold = float(activity["volume_5m_usd"])
                    transactions_threshold = int(activity["transactions_5m"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue
                signal = parse_time(cohort["signal_available_at"])
                window_end = parse_time(cohort["window_end_at"])
                terminal = parse_time(cohort["terminal_at"])
                upper = min(evaluated, window_end)
                rows = list(self.db.execute(
                    """
                    SELECT * FROM token_snapshots
                    WHERE token_id=? AND observed_at>=? AND observed_at<=?
                      AND ingested_at>=? AND ingested_at<=?
                      AND recorded_at>? AND recorded_at<=?
                      AND observed_at<=ingested_at AND ingested_at<=recorded_at
                      AND volume_5m_usd IS NOT NULL AND buys_5m IS NOT NULL AND sells_5m IS NOT NULL
                    ORDER BY recorded_at,observed_at,id
                    """,
                    (
                        str(cohort["token_id"]), iso(signal), iso(window_end),
                        iso(signal), iso(window_end), iso(signal), iso(upper),
                    ),
                )) if upper > signal else []
                valid = [
                    row for row in rows
                    if (
                        (surface := self._information_first_snapshot_surface(row)) is not None
                        and surface["key"] == str(cohort["surface_key"])
                    )
                ]
                crossing = None
                crossing_valid_count = 0
                dimensions: list[str] = []
                for valid_index, row in enumerate(valid, start=1):
                    transactions = int(row["buys_5m"]) + int(row["sells_5m"])
                    current_dimensions = []
                    if float(row["volume_5m_usd"]) > volume_threshold:
                        current_dimensions.append("volume_5m_usd")
                    if transactions > transactions_threshold:
                        current_dimensions.append("transactions_5m")
                    if current_dimensions:
                        crossing = row
                        crossing_valid_count = valid_index
                        dimensions = current_dimensions
                        break
                if crossing is not None:
                    transactions = int(crossing["buys_5m"]) + int(crossing["sells_5m"])
                    recorded = parse_time(crossing["recorded_at"])
                    self.db.execute(
                        """
                        INSERT INTO information_first_ilg_outcomes(
                            ilg_cohort_id,status,window_end_at,terminal_at,crossing_snapshot_id,
                            crossing_observed_at,crossing_ingested_at,crossing_recorded_at,ilg_seconds,
                            crossing_volume_5m_usd,crossing_transactions_5m,crossed_dimensions_json,
                            valid_snapshot_count,surface_key,evaluated_at
                        ) VALUES(?,'crossed',?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            int(cohort["id"]), str(cohort["window_end_at"]), str(cohort["terminal_at"]),
                            int(crossing["id"]), str(crossing["observed_at"]),
                            str(crossing["ingested_at"]), str(crossing["recorded_at"]),
                            (recorded - signal).total_seconds(), float(crossing["volume_5m_usd"]),
                            transactions, self._json(dimensions), crossing_valid_count,
                            str(cohort["surface_key"]),
                            iso(evaluated),
                        ),
                    )
                    crossed_count += 1
                elif evaluated >= terminal:
                    status = (
                        "missing_not_crossed_by_240m"
                        if valid else "missing_no_valid_activity_snapshot"
                    )
                    self.db.execute(
                        """
                        INSERT INTO information_first_ilg_outcomes(
                            ilg_cohort_id,status,window_end_at,terminal_at,crossed_dimensions_json,
                            valid_snapshot_count,surface_key,evaluated_at
                        ) VALUES(?,?,?,?, '[]',?,?,?)
                        """,
                        (
                            int(cohort["id"]), status, str(cohort["window_end_at"]),
                            str(cohort["terminal_at"]), len(valid), str(cohort["surface_key"]),
                            iso(evaluated),
                        ),
                    )
                    missing_count += 1
        pending = int(self.db.execute(
            """
            SELECT COUNT(*) FROM information_first_ilg_cohorts c
            LEFT JOIN information_first_ilg_outcomes o ON o.ilg_cohort_id=c.id
            WHERE c.eligibility='eligible_at_risk' AND o.id IS NULL
            """
        ).fetchone()[0])
        return {
            "cohorts_checked": len(cohorts),
            "outcomes_crossed": crossed_count,
            "outcomes_missing": missing_count,
            "outcomes_pending": pending,
        }

    @classmethod
    def information_first_ilg_summary_from_connection(
        cls, connection: sqlite3.Connection, *, lookback_days: int = 90
    ) -> dict[str, Any]:
        definition = cls._information_first_ilg_definition()
        empty = {
            "version": cls.INFORMATION_FIRST_ILG_VERSION,
            "status": "not_observed",
            "mode": "strict_forward_interval_censored",
            "affects": "none",
            "definition": definition,
            "items": [],
            "summary": {
                "registered_cohorts": 0, "eligible_at_risk": 0, "already_active_at_signal": 0,
                "activity_baseline_missing": 0, "activity_surface_unknown": 0,
                "pre_registration_excluded": 0, "crossed": 0,
                "missing_not_crossed_by_240m": 0, "missing_no_valid_activity_snapshot": 0,
                "pending": 0, "crossing_rate": None, "median_ilg_seconds": None,
                "p25_ilg_seconds": None, "p75_ilg_seconds": None,
            },
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {
            "information_first_ilg_registrations", "information_first_ilg_cohorts",
            "information_first_ilg_outcomes", "information_first_shadow_cohorts",
        }
        if not required.issubset(tables):
            return {**empty, "status": "unavailable"}
        registration = connection.execute(
            "SELECT * FROM information_first_ilg_registrations WHERE definition_version=?",
            (cls.INFORMATION_FIRST_ILG_VERSION,),
        ).fetchone()
        if registration is None:
            return {**empty, "status": "unavailable"}
        try:
            frozen_definition = json.loads(str(registration["definition_json"]))
        except (TypeError, json.JSONDecodeError):
            frozen_definition = definition
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        cohorts = list(connection.execute(
            "SELECT * FROM information_first_ilg_cohorts WHERE enrolled_at>=? ORDER BY enrolled_at,id",
            (start,),
        ))
        pre_registration = int(connection.execute(
            """
            SELECT COUNT(*) FROM information_first_shadow_cohorts s
            WHERE s.signal_available_at<? AND s.captured_at>=?
            """,
            (str(registration["registered_at"]), start),
        ).fetchone()[0])
        if not cohorts:
            result = dict(empty)
            result["definition"] = frozen_definition
            result["summary"] = {**empty["summary"], "pre_registration_excluded": pre_registration}
            result["registered_at"] = str(registration["registered_at"])
            return result
        ids = [int(row["id"]) for row in cohorts]
        placeholders = ",".join("?" for _ in ids)
        outcomes = list(connection.execute(
            f"SELECT * FROM information_first_ilg_outcomes WHERE ilg_cohort_id IN ({placeholders})",
            ids,
        ))
        by_cohort = {int(row["ilg_cohort_id"]): row for row in outcomes}
        eligible = [row for row in cohorts if str(row["eligibility"]) == "eligible_at_risk"]
        crossed = [row for row in outcomes if str(row["status"]) == "crossed"]
        values = sorted(float(row["ilg_seconds"]) for row in crossed if row["ilg_seconds"] is not None)

        def percentile(fraction: float) -> float | None:
            if not values:
                return None
            position = (len(values) - 1) * fraction
            lower = int(math.floor(position))
            upper = int(math.ceil(position))
            if lower == upper:
                return values[lower]
            return values[lower] + (values[upper] - values[lower]) * (position - lower)

        items = []
        for eligibility in sorted({str(row["eligibility"]) for row in cohorts}):
            rows = [row for row in cohorts if str(row["eligibility"]) == eligibility]
            row_outcomes = [by_cohort[int(row["id"])] for row in rows if int(row["id"]) in by_cohort]
            item_values = sorted(
                float(row["ilg_seconds"])
                for row in row_outcomes
                if str(row["status"]) == "crossed" and row["ilg_seconds"] is not None
            )
            items.append({
                "eligibility": eligibility,
                "cohorts": len(rows),
                "crossed": sum(str(row["status"]) == "crossed" for row in row_outcomes),
                "missing": sum(str(row["status"]).startswith("missing_") for row in row_outcomes),
                "pending": len(rows) - len(row_outcomes) if eligibility == "eligible_at_risk" else 0,
                "median_ilg_seconds": item_values[len(item_values) // 2] if item_values else None,
            })
        summary = {
            "registered_cohorts": len(cohorts),
            "eligible_at_risk": len(eligible),
            "already_active_at_signal": sum(str(row["eligibility"]) == "already_active_at_signal" for row in cohorts),
            "activity_baseline_missing": sum(str(row["eligibility"]) == "ineligible_activity_baseline_missing" for row in cohorts),
            "activity_surface_unknown": sum(str(row["eligibility"]) == "ineligible_activity_surface_unknown" for row in cohorts),
            "pre_registration_excluded": pre_registration,
            "crossed": len(crossed),
            "missing_not_crossed_by_240m": sum(str(row["status"]) == "missing_not_crossed_by_240m" for row in outcomes),
            "missing_no_valid_activity_snapshot": sum(str(row["status"]) == "missing_no_valid_activity_snapshot" for row in outcomes),
            "pending": len(eligible) - len(outcomes),
            "crossing_rate": round(len(crossed) / len(eligible), 6) if eligible else None,
            "median_ilg_seconds": percentile(0.5),
            "p25_ilg_seconds": percentile(0.25),
            "p75_ilg_seconds": percentile(0.75),
        }
        return {
            "version": cls.INFORMATION_FIRST_ILG_VERSION,
            "status": "collecting" if summary["pending"] else "observed",
            "mode": "strict_forward_interval_censored",
            "affects": "none",
            "definition": frozen_definition,
            "registered_at": str(registration["registered_at"]),
            "items": items,
            "summary": summary,
            "as_of": iso(),
        }

    @classmethod
    def information_first_shadow_summary_from_connection(
        cls,
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        empty = {
            "version": cls.INFORMATION_FIRST_SHADOW_VERSION,
            "status": "not_observed",
            "mode": "descriptive_forward_only_observation",
            "affects": "none",
            "items": [],
            "summary": {
                "cohorts": 0, "independent_events": 0, "independent_tokens": 0,
                "outcomes_observed": 0, "outcomes_missing": 0, "outcomes_pending": 0,
                "baseline_missing_at_signal_available": 0,
                "admission_attempts": 0, "admissions_created": 0, "admissions_skipped": 0,
            },
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {"information_first_shadow_cohorts", "information_first_shadow_outcomes"}
        if not required.issubset(tables):
            return {**empty, "status": "unavailable"}
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        cohorts = list(connection.execute(
            "SELECT * FROM information_first_shadow_cohorts WHERE captured_at>=? ORDER BY captured_at,id",
            (start,),
        ))
        if not cohorts:
            return empty
        cohort_ids = [int(row["id"]) for row in cohorts]
        trackable_ids = {
            int(row["id"]) for row in cohorts if str(row["trackability"]) == "trackable"
        }
        placeholders = ",".join("?" for _ in cohort_ids)
        outcomes = list(connection.execute(
            f"SELECT * FROM information_first_shadow_outcomes WHERE cohort_id IN ({placeholders})",
            cohort_ids,
        ))
        attempts = list(connection.execute(
            """
            SELECT * FROM information_first_shadow_admission_attempts
            WHERE attempted_at>=? ORDER BY attempted_at,id
            """,
            (start,),
        )) if "information_first_shadow_admission_attempts" in tables else []
        by_cohort_horizon = {(int(row["cohort_id"]), int(row["horizon_minutes"])): row for row in outcomes}
        groups: dict[str, list[sqlite3.Row]] = {}
        for cohort in cohorts:
            try:
                features = json.loads(str(cohort["features_json"] or "{}"))
            except (TypeError, json.JSONDecodeError):
                features = {}
            market = features.get("market_state") if isinstance(features, dict) else {}
            label = str(market.get("label") or "insufficient_market_data") if isinstance(market, dict) else "insufficient_market_data"
            groups.setdefault(label, []).append(cohort)
        items = []
        for label, rows in sorted(groups.items()):
            trackable_count = sum(str(row["trackability"]) == "trackable" for row in rows)
            observed = []
            missing = []
            for row in rows:
                outcome = by_cohort_horizon.get((int(row["id"]), 60))
                if outcome is not None and str(outcome["status"]) == "observed":
                    observed.append(outcome)
                elif outcome is not None and str(outcome["status"]) == "missing":
                    missing.append(outcome)
            values = [float(row["raw_return"]) for row in observed if row and row["raw_return"] is not None]
            items.append({
                "market_state": label,
                "cohorts": len(rows),
                "trackable_cohorts": trackable_count,
                "baseline_missing_at_signal_available": sum(
                    str(row["trackability"]) == "baseline_missing_at_signal_available" for row in rows
                ),
                "observed_60m": len(observed),
                "missing_60m": len(missing),
                "pending_60m": trackable_count - len(observed) - len(missing),
                "mean_raw_return_60m": round(sum(values) / len(values), 6) if values else None,
            })
        observed_total = sum(str(row["status"]) == "observed" for row in outcomes)
        missing_total = sum(str(row["status"]) == "missing" for row in outcomes)
        return {
            "version": cls.INFORMATION_FIRST_SHADOW_VERSION,
            "status": "collecting" if len(outcomes) < len(trackable_ids) * len(cls.INFORMATION_FIRST_SHADOW_HORIZONS_MINUTES) else "observed",
            "mode": "descriptive_forward_only_observation",
            "affects": "none",
            "items": items,
            "summary": {
                "cohorts": len(cohorts),
                "independent_events": len({int(row["event_id"]) for row in cohorts}),
                "independent_tokens": len({str(row["token_id"]) for row in cohorts}),
                "outcomes_observed": observed_total,
                "outcomes_missing": missing_total,
                "outcomes_pending": max(0, len(trackable_ids) * len(cls.INFORMATION_FIRST_SHADOW_HORIZONS_MINUTES) - len(outcomes)),
                "baseline_missing_at_signal_available": len(cohorts) - len(trackable_ids),
                "admission_attempts": len(attempts),
                "admissions_created": sum(
                    str(row["status"]) in {"created", "created_baseline_missing"}
                    for row in attempts
                ),
                "admissions_skipped": sum(str(row["status"]) == "skipped" for row in attempts),
            },
            "not_available": ["unique_buyers", "image_similarity", "holder_clusters"],
            "as_of": iso(),
        }

    @staticmethod
    def shadow_event_admission_summary_from_connection(
        connection: sqlite3.Connection, *, lookback_days: int = 90
    ) -> dict[str, Any]:
        empty = {
            "status": "not_observed",
            "version": Store.SHADOW_EVENT_ADMISSION_VERSION,
            "items": [],
            "reasons": [],
            "summary": {
                "decision_count": 0,
                "instrumented_decisions": 0,
                "legacy_or_uninstrumented_decisions": 0,
                "attempts": 0,
                "created": 0,
                "already_admitted": 0,
                "skipped": 0,
                "candidate_decisions": 0,
                "candidate_instrumented": 0,
                "candidate_covered": 0,
                "candidate_skipped": 0,
                "candidate_legacy_or_uninstrumented": 0,
                "forward_candidate_coverage_rate": None,
                "overall_candidate_coverage_rate": None,
                "wait_decisions": 0,
                "reject_decisions": 0,
                "reject_covered": 0,
            },
            "mode": "forward_append_only_observation",
            "affects": "none",
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        ledger_available = "shadow_event_admission_attempts" in tables
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        attempts = (
            list(
                connection.execute(
                    """
                    SELECT * FROM shadow_event_admission_attempts
                    WHERE attempted_at>=? ORDER BY attempted_at DESC,id DESC
                    """,
                    (start,),
                )
            )
            if ledger_available
            else []
        )
        decisions: list[sqlite3.Row] = []
        if "decisions" in tables:
            decisions = list(
                connection.execute(
                    """
                    SELECT id,action FROM decisions
                    WHERE created_at>=? AND action IN ('WAIT','REJECT','CANDIDATE')
                    """,
                    (start,),
                )
            )
        decision_ids = {int(row["id"]) for row in decisions}
        candidate_ids = {
            int(row["id"]) for row in decisions if str(row["action"]).upper() == "CANDIDATE"
        }
        wait_ids = {
            int(row["id"]) for row in decisions if str(row["action"]).upper() == "WAIT"
        }
        reject_ids = {
            int(row["id"]) for row in decisions if str(row["action"]).upper() == "REJECT"
        }
        instrumented_ids = {int(row["decision_id"]) for row in attempts}
        candidate_attempts = [
            row for row in attempts if str(row["requested_action"]).upper() == "CANDIDATE"
        ]
        candidate_covered = sum(
            str(row["status"]) in {"created", "already_admitted"} and row["cohort_id"] is not None
            for row in candidate_attempts
        )
        reject_attempts = [
            row for row in attempts if str(row["requested_action"]).upper() == "REJECT"
        ]
        reject_covered = sum(
            str(row["status"]) in {"created", "already_admitted"} and row["cohort_id"] is not None
            for row in reject_attempts
        )
        reason_counts: dict[str, int] = {}
        for row in attempts:
            reason = str(row["reason"] or "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        summary = {
            "decision_count": len(decisions),
            "instrumented_decisions": len(decision_ids & instrumented_ids),
            "legacy_or_uninstrumented_decisions": len(decision_ids - instrumented_ids),
            "attempts": len(attempts),
            "created": sum(str(row["status"]) == "created" for row in attempts),
            "already_admitted": sum(
                str(row["status"]) == "already_admitted" for row in attempts
            ),
            "skipped": sum(str(row["status"]) == "skipped" for row in attempts),
            "candidate_decisions": len(candidate_ids),
            "candidate_instrumented": len(candidate_attempts),
            "candidate_covered": candidate_covered,
            "candidate_skipped": sum(
                str(row["status"]) == "skipped" for row in candidate_attempts
            ),
            "candidate_legacy_or_uninstrumented": len(candidate_ids - instrumented_ids),
            "forward_candidate_coverage_rate": round(
                candidate_covered / len(candidate_attempts), 4
            ) if candidate_attempts else None,
            "overall_candidate_coverage_rate": round(
                candidate_covered / len(candidate_ids), 4
            ) if candidate_ids else None,
            "wait_decisions": len(wait_ids),
            "reject_decisions": len(reject_ids),
            "reject_instrumented": len(reject_attempts),
            "reject_covered": reject_covered,
            "reject_skipped": sum(
                str(row["status"]) == "skipped" for row in reject_attempts
            ),
            "tracking_started_at": min(
                (str(row["attempted_at"]) for row in attempts), default=None
            ),
        }
        recent = [
            {
                "id": int(row["id"]),
                "decision_id": int(row["decision_id"]),
                "event_id": int(row["event_id"]),
                "token_id": str(row["token_id"]),
                "requested_action": str(row["requested_action"]),
                "status": str(row["status"]),
                "reason": str(row["reason"]),
                "cohort_id": row["cohort_id"],
                "source_observation_count": int(row["source_observation_count"]),
                "eligible_source_count": int(row["eligible_source_count"]),
                "attempted_at": str(row["attempted_at"]),
            }
            for row in attempts[:30]
        ]
        return {
            "status": "observed" if attempts else (
                "not_instrumented" if decisions and not ledger_available else "not_observed"
            ),
            "version": Store.SHADOW_EVENT_ADMISSION_VERSION,
            "observed_versions": sorted({str(row["version"]) for row in attempts}),
            "items": recent,
            "reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "summary": summary,
            "mode": "forward_append_only_observation",
            "affects": "none",
            "as_of": iso(),
        }

    @staticmethod
    def shadow_event_learning_summary_from_connection(
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        admission = Store.shadow_event_admission_summary_from_connection(
            connection, lookback_days=lookback_days
        )
        required_tables = {
            "shadow_event_cohorts", "shadow_event_cohort_labels", "shadow_event_outcomes"
        }
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if str(row["name"]) in required_tables
        }
        policy = {
            "minimum_distinct_events": 30,
            "minimum_event_days": 15,
            "minimum_weighted_negative_outcomes": 8,
            "entity_minimum_distinct_events": 50,
            "entity_minimum_event_days": 20,
            "entity_minimum_platforms": 2,
            "affects": "nothing_shadow_observation_only",
        }
        if tables != required_tables:
            return {
                "status": "not_observed", "items": [],
                "summary": {"cohorts": 0, "pending_cohorts": 0, "complete_cohorts": 0},
                "admission": admission,
                "review_policy": policy,
            }
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        cohorts = list(
            connection.execute(
                "SELECT id,version,event_id,action,decision_at,status FROM shadow_event_cohorts WHERE decision_at>=?",
                (start,),
            )
        )
        rows = list(
            connection.execute(
                """
                SELECT c.id AS cohort_id,c.event_id,c.action,c.decision_at,l.dimension,l.value,
                       l.origin_platform,l.attribution_weight,o.horizon_minutes,o.raw_return,
                       o.maximum_return,o.minimum_return
                FROM shadow_event_cohorts c
                JOIN shadow_event_cohort_labels l ON l.cohort_id=c.id
                JOIN shadow_event_outcomes o ON o.cohort_id=c.id
                WHERE c.decision_at>=? AND o.status='observed'
                  AND NOT EXISTS (
                    SELECT 1 FROM shadow_event_cohorts earlier
                    WHERE earlier.event_id=c.event_id
                      AND (
                        earlier.decision_at<c.decision_at
                        OR (earlier.decision_at=c.decision_at AND earlier.id<c.id)
                      )
                  )
                ORDER BY o.horizon_minutes,l.dimension,l.value,c.id
                """,
                (start,),
            )
        )
        metrics: dict[tuple[int, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (int(row["horizon_minutes"]), str(row["dimension"]), str(row["value"]))
            metric = metrics.setdefault(
                key,
                {
                    "weight": 0.0, "weighted_return": 0.0, "weighted_positive": 0.0,
                    "weighted_negative": 0.0, "weighted_downside": 0.0,
                    "weighted_maximum": 0.0, "weighted_minimum": 0.0,
                    "cohorts": set(), "events": set(), "event_days": set(), "platforms": set(),
                    "wait_cohorts": set(), "reject_cohorts": set(), "candidate_cohorts": set(),
                },
            )
            weight = max(0.0, float(row["attribution_weight"] or 0))
            raw_return = float(row["raw_return"] or 0)
            metric["weight"] += weight
            metric["weighted_return"] += weight * raw_return
            metric["weighted_positive"] += weight if raw_return > 0 else 0.0
            metric["weighted_negative"] += weight if raw_return <= 0 else 0.0
            metric["weighted_downside"] += weight if raw_return <= -0.25 else 0.0
            metric["weighted_maximum"] += weight * float(row["maximum_return"] or 0)
            metric["weighted_minimum"] += weight * float(row["minimum_return"] or 0)
            metric["cohorts"].add(int(row["cohort_id"]))
            metric["events"].add(int(row["event_id"]))
            metric["event_days"].add(str(row["decision_at"])[:10])
            if row["origin_platform"]:
                metric["platforms"].add(str(row["origin_platform"]))
            metric[f"{str(row['action']).lower()}_cohorts"].add(int(row["cohort_id"]))
        items = []
        for (horizon, dimension, value), metric in metrics.items():
            weight = float(metric["weight"])
            event_count = len(metric["events"])
            event_days = len(metric["event_days"])
            platform_count = len(metric["platforms"])
            required_events = 50 if dimension == "entity" else 30
            required_days = 20 if dimension == "entity" else 15
            review_eligible = (
                event_count >= required_events
                and event_days >= required_days
                and float(metric["weighted_negative"]) >= policy["minimum_weighted_negative_outcomes"]
                and (dimension != "entity" or platform_count >= policy["entity_minimum_platforms"])
            )
            mean_return = float(metric["weighted_return"]) / weight if weight else None
            descriptive_score = None
            if review_eligible and mean_return is not None:
                descriptive_score = weight / (weight + 30.0) * mean_return
            items.append(
                {
                    "horizon_minutes": horizon,
                    "dimension": dimension,
                    "value": value,
                    "weighted_outcomes": round(weight, 4),
                    "distinct_cohort_count": len(metric["cohorts"]),
                    "distinct_event_count": event_count,
                    "event_day_count": event_days,
                    "platform_count": platform_count,
                    "wait_cohort_count": len(metric["wait_cohorts"]),
                    "reject_cohort_count": len(metric["reject_cohorts"]),
                    "candidate_cohort_count": len(metric["candidate_cohorts"]),
                    "positive_rate": round(float(metric["weighted_positive"]) / weight, 4) if weight else None,
                    "mean_raw_return": round(mean_return, 6) if mean_return is not None else None,
                    "downside_rate": round(float(metric["weighted_downside"]) / weight, 4) if weight else None,
                    "mean_maximum_return": round(float(metric["weighted_maximum"]) / weight, 6) if weight else None,
                    "mean_minimum_return": round(float(metric["weighted_minimum"]) / weight, 6) if weight else None,
                    "weighted_negative_outcomes": round(float(metric["weighted_negative"]), 4),
                    "shadow_review_eligible": review_eligible,
                    "shadow_descriptive_score": round(descriptive_score, 6) if descriptive_score is not None else None,
                    "rotation_active": False,
                }
            )
        items.sort(
            key=lambda item: (
                not bool(item["shadow_review_eligible"]), int(item["horizon_minutes"]) != 60,
                -int(item["distinct_event_count"]), str(item["dimension"]), str(item["value"]).casefold(),
            )
        )
        outcome_counts = {
            int(row["horizon_minutes"]): {"observed": 0, "missing": 0}
            for row in connection.execute(
                "SELECT DISTINCT horizon_minutes FROM shadow_event_outcomes"
            )
        }
        for row in connection.execute(
            """
            SELECT o.horizon_minutes,o.status,COUNT(*) AS value
            FROM shadow_event_outcomes o JOIN shadow_event_cohorts c ON c.id=o.cohort_id
            WHERE c.decision_at>=? GROUP BY o.horizon_minutes,o.status
            """,
            (start,),
        ):
            outcome_counts.setdefault(int(row["horizon_minutes"]), {"observed": 0, "missing": 0})[
                str(row["status"])
            ] = int(row["value"])
        entry_execution = {
            "attempts": 0,
            "filled": 0,
            "rejected": 0,
            "cohort_linked": 0,
            "unlinked": 0,
        }
        execution_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(paper_execution_attempts)")
        }
        if {"decision_id", "cohort_id"}.issubset(execution_columns):
            row = connection.execute(
                """
                SELECT COUNT(*) AS attempts,
                       SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) AS filled,
                       SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected,
                       SUM(CASE WHEN decision_id IS NOT NULL AND cohort_id IS NOT NULL THEN 1 ELSE 0 END)
                           AS cohort_linked,
                       SUM(CASE WHEN decision_id IS NULL OR cohort_id IS NULL THEN 1 ELSE 0 END)
                           AS unlinked
                FROM paper_execution_attempts
                WHERE side='BUY' AND requested_at>=?
                """,
                (start,),
            ).fetchone()
            entry_execution = {
                key: int(row[key] or 0) for key in entry_execution
            }
        return {
            "status": (
                "shadow_review_available"
                if any(item["shadow_review_eligible"] for item in items)
                else "collecting_followup"
                if cohorts
                else "not_observed"
            ),
            "version": Store.SHADOW_EVENT_COHORT_VERSION,
            "observed_versions": sorted({str(row["version"]) for row in cohorts}),
            "horizons_minutes": list(Store.SHADOW_EVENT_HORIZONS_MINUTES),
            "items": items[:500],
            "summary": {
                "cohorts": len(cohorts),
                "pending_cohorts": sum(str(row["status"]) == "pending" for row in cohorts),
                "complete_cohorts": sum(str(row["status"]) == "complete" for row in cohorts),
                "wait_cohorts": sum(str(row["action"]) == "WAIT" for row in cohorts),
                "reject_cohorts": sum(str(row["action"]) == "REJECT" for row in cohorts),
                "candidate_cohorts": sum(str(row["action"]) == "CANDIDATE" for row in cohorts),
                "outcomes_by_horizon": outcome_counts,
                "review_eligible_labels": sum(item["shadow_review_eligible"] for item in items),
                "entry_execution": entry_execution,
            },
            "admission": admission,
            "review_policy": policy,
            "analysis_unit": "earliest_forward_cohort_per_independent_event",
            "as_of": iso(),
        }

    def has_bought_token(self, token_id: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM trades WHERE token_id=? AND side='BUY' LIMIT 1",
            (token_id,),
        ).fetchone()
        return row is not None

    def daily_buy_gross_usd(self) -> float:
        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        row = self.db.execute(
            "SELECT COALESCE(SUM(gross_usd),0) AS total FROM trades WHERE side='BUY' AND created_at>=?",
            (iso(start),),
        ).fetchone()
        return float(row["total"] or 0.0)

    def heartbeat(self, source: str, *, item: bool = False, error: str = "") -> None:
        now = iso()
        with self._lock, self.db:
            row = self.db.execute("SELECT source FROM source_health WHERE source=?", (source,)).fetchone()
            if row:
                self.db.execute(
                    """UPDATE source_health SET last_ok_at=CASE WHEN ?='' THEN ? ELSE last_ok_at END,
                       last_item_at=CASE WHEN ? THEN ? ELSE last_item_at END,
                       last_error_at=CASE WHEN ?<>'' THEN ? ELSE last_error_at END,
                       last_error=CASE WHEN ?<>'' THEN ? ELSE '' END WHERE source=?""",
                    (error,now,int(item),now,error,now,error,error,source),
                )
            else:
                self.db.execute(
                    "INSERT INTO source_health(source,last_ok_at,last_item_at,last_error_at,last_error) VALUES(?,?,?,?,?)",
                    (source, None if error else now, now if item else None, now if error else None, error),
                )

    def source_health(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM source_health ORDER BY source"))

    def start_source_poll_attempt(
        self,
        *,
        collector_kind: str,
        source_key: str,
        platform: str,
        started_at: Any = None,
    ) -> int:
        clean = lambda value: re.sub(r"[^a-zA-Z0-9:._-]+", "-", str(value).strip())[:160]
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO source_poll_attempts(
                    version,collector_kind,source_key,platform,status,started_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    self.SOURCE_POLL_EXPOSURE_VERSION,
                    clean(collector_kind) or "unknown",
                    clean(source_key) or "unknown",
                    clean(platform) or "unknown",
                    "running",
                    iso(started_at or utcnow()),
                ),
            )
            return int(cursor.lastrowid)

    def finish_source_poll_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        fetched_count: int = 0,
        new_observation_count: int = 0,
        new_event_count: int = 0,
        decision_eligible_count: int = 0,
        context_only_count: int = 0,
        duplicate_count: int = 0,
        filtered_count: int = 0,
        error_type: str = "",
        completed_at: Any = None,
    ) -> None:
        status = status if status in {"completed", "error", "quality_paused"} else "error"
        error_type = re.sub(r"[^a-zA-Z0-9_.-]+", "", str(error_type))[:80]
        counts = tuple(
            max(0, int(value or 0))
            for value in (
                fetched_count,
                new_observation_count,
                new_event_count,
                decision_eligible_count,
                context_only_count,
                duplicate_count,
                filtered_count,
            )
        )
        with self._lock, self.db:
            self.db.execute(
                """
                UPDATE source_poll_attempts SET
                    status=?,fetched_count=?,new_observation_count=?,new_event_count=?,
                    decision_eligible_count=?,context_only_count=?,duplicate_count=?,
                    filtered_count=?,error_type=?,completed_at=?
                WHERE id=? AND status='running'
                """,
                (status, *counts, error_type, iso(completed_at or utcnow()), int(attempt_id)),
            )

    @classmethod
    def source_poll_learning_summary_from_connection(
        cls,
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_poll_attempts'"
        ).fetchone()
        if not exists:
            return {
                "status": "not_observed",
                "version": cls.SOURCE_POLL_EXPOSURE_VERSION,
                "items": [],
                "summary": {"attempts": 0, "completed": 0, "errors": 0, "completed_zero_yield": 0},
                "mode": "forward_append_only_observation",
                "affects": "review_only_no_schedule_or_trading_effect",
            }
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = connection.execute(
            """
            SELECT collector_kind,source_key,platform,
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,
                   SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running,
                   SUM(CASE WHEN status='quality_paused' THEN 1 ELSE 0 END) AS quality_paused,
                   SUM(CASE WHEN status='completed' AND new_observation_count=0 THEN 1 ELSE 0 END)
                       AS completed_zero_yield,
                   SUM(fetched_count) AS fetched_count,
                   SUM(new_observation_count) AS new_observation_count,
                   SUM(new_event_count) AS new_event_count,
                   SUM(decision_eligible_count) AS decision_eligible_count,
                   SUM(context_only_count) AS context_only_count,
                   SUM(duplicate_count) AS duplicate_count,
                   SUM(filtered_count) AS filtered_count,
                   COUNT(DISTINCT substr(started_at,1,10)) AS poll_day_count,
                   MAX(started_at) AS last_started_at
            FROM source_poll_attempts WHERE started_at>=?
            GROUP BY collector_kind,source_key,platform
            ORDER BY completed DESC,attempts DESC,source_key
            """,
            (start,),
        ).fetchall()
        latest: dict[tuple[str, str, str], sqlite3.Row] = {}
        for row in connection.execute(
            """
            SELECT collector_kind,source_key,platform,status,error_type,started_at,completed_at
            FROM source_poll_attempts WHERE started_at>=? ORDER BY id DESC
            """,
            (start,),
        ):
            key = (str(row["collector_kind"]), str(row["source_key"]), str(row["platform"]))
            latest.setdefault(key, row)
        items = []
        for row in rows:
            key = (str(row["collector_kind"]), str(row["source_key"]), str(row["platform"]))
            last = latest[key]
            completed = int(row["completed"] or 0)
            days = int(row["poll_day_count"] or 0)
            items.append(
                {
                    "collector_kind": key[0],
                    "source_key": key[1],
                    "platform": key[2],
                    "attempts": int(row["attempts"] or 0),
                    "completed": completed,
                    "errors": int(row["errors"] or 0),
                    "running": int(row["running"] or 0),
                    "quality_paused": int(row["quality_paused"] or 0),
                    "completed_zero_yield": int(row["completed_zero_yield"] or 0),
                    "fetched_count": int(row["fetched_count"] or 0),
                    "new_observation_count": int(row["new_observation_count"] or 0),
                    "new_event_count": int(row["new_event_count"] or 0),
                    "decision_eligible_count": int(row["decision_eligible_count"] or 0),
                    "context_only_count": int(row["context_only_count"] or 0),
                    "duplicate_count": int(row["duplicate_count"] or 0),
                    "filtered_count": int(row["filtered_count"] or 0),
                    "poll_day_count": days,
                    "new_observations_per_completed_poll": (
                        round(float(row["new_observation_count"] or 0) / completed, 4)
                        if completed else None
                    ),
                    "review_eligible": completed >= 20 and days >= 5,
                    "last_status": str(last["status"]),
                    "last_error_type": str(last["error_type"] or "") or None,
                    "last_started_at": str(last["started_at"]),
                    "last_completed_at": last["completed_at"],
                }
            )
        summary = {
            name: sum(int(item[name] or 0) for item in items)
            for name in ("attempts", "completed", "errors", "running", "quality_paused", "completed_zero_yield", "fetched_count", "new_observation_count", "new_event_count")
        }
        summary["sources"] = len(items)
        summary["review_eligible_sources"] = sum(bool(item["review_eligible"]) for item in items)
        return {
            "status": "collecting" if items else "not_observed",
            "version": cls.SOURCE_POLL_EXPOSURE_VERSION,
            "items": items,
            "summary": summary,
            "mode": "forward_append_only_observation",
            "affects": "review_only_no_schedule_or_trading_effect",
            "as_of": iso(),
        }

    def token_discovery_known(self, token_id: str) -> bool:
        row = self.db.execute(
            """
            SELECT 1 FROM tokens WHERE token_id=?
            UNION ALL
            SELECT 1 FROM token_source_links WHERE token_id=? LIMIT 1
            """,
            (str(token_id), str(token_id)),
        ).fetchone()
        return row is not None

    def recover_interrupted_exposure_attempts(self, *, recovered_at: Any = None) -> None:
        completed_at = iso(recovered_at or utcnow())
        with self._lock, self.db:
            self.db.execute(
                """
                UPDATE source_poll_attempts
                SET status='error',error_type='ProcessRestart',completed_at=?
                WHERE status='running'
                """,
                (completed_at,),
            )
            self.db.execute(
                """
                UPDATE token_discovery_rounds
                SET status='interrupted',error_type='ProcessRestart',completed_at=?
                WHERE status='running'
                """,
                (completed_at,),
            )
            self.db.execute(
                """
                UPDATE trend_lane_runs
                SET status='agent_error',error_type='ProcessRestart',finished_at=?,
                    observation_ingestion_status='error',
                    observation_ingestion_finalized_at=?
                WHERE status='running'
                """,
                (completed_at, completed_at),
            )
            self.db.execute(
                """
                UPDATE trend_lane_runs
                SET observation_ingestion_status='error',
                    observation_ingestion_finalized_at=?,
                    error_type=CASE WHEN error_type='' THEN 'ProcessRestartDuringIngestion' ELSE error_type END
                WHERE status='completed' AND observation_ingestion_status='pending'
                """,
                (completed_at,),
            )

    def start_token_discovery_round(
        self,
        *,
        provider: str,
        surface: str,
        mode: str,
        chain_scope: str,
        started_at: Any = None,
    ) -> int:
        clean = lambda value: re.sub(r"[^a-zA-Z0-9:._,-]+", "-", str(value).strip())[:160]
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT INTO token_discovery_rounds(
                    version,provider,surface,mode,chain_scope,status,started_at
                ) VALUES(?,?,?,?,?,'running',?)
                """,
                (
                    self.TOKEN_DISCOVERY_EXPOSURE_VERSION,
                    clean(provider) or "unknown",
                    clean(surface) or "unknown",
                    clean(mode) or "unknown",
                    clean(chain_scope) or "unknown",
                    iso(started_at or utcnow()),
                ),
            )
            return int(cursor.lastrowid)

    def add_token_discovery_exposure(
        self,
        round_id: int,
        *,
        token_id: str,
        chain: str,
        role: str = "discovery",
        first_local_discovery: bool = False,
        new_token: bool = False,
        occurrence_count: int = 1,
        source_link_count: int = 0,
        new_source_link_count: int = 0,
        snapshot_count: int = 0,
        no_pair: bool = False,
        observed_at: Any = None,
    ) -> None:
        token_id = str(token_id).strip()[:300]
        if not token_id:
            return
        clean = lambda value: re.sub(r"[^a-zA-Z0-9:._-]+", "-", str(value).strip())[:100]
        with self._lock, self.db:
            self.db.execute(
                """
                INSERT INTO token_discovery_exposures(
                    round_id,token_id,chain,role,first_local_discovery,new_token,
                    occurrence_count,source_link_count,new_source_link_count,snapshot_count,
                    no_pair,observed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(round_id,token_id) DO UPDATE SET
                    first_local_discovery=MAX(first_local_discovery,excluded.first_local_discovery),
                    new_token=MAX(new_token,excluded.new_token),
                    occurrence_count=token_discovery_exposures.occurrence_count+excluded.occurrence_count,
                    source_link_count=token_discovery_exposures.source_link_count+excluded.source_link_count,
                    new_source_link_count=token_discovery_exposures.new_source_link_count+excluded.new_source_link_count,
                    snapshot_count=token_discovery_exposures.snapshot_count+excluded.snapshot_count,
                    no_pair=MAX(no_pair,excluded.no_pair)
                """,
                (
                    int(round_id), token_id, clean(chain) or "unknown", clean(role) or "discovery",
                    int(bool(first_local_discovery)), int(bool(new_token)),
                    max(1, int(occurrence_count or 1)), max(0, int(source_link_count or 0)),
                    max(0, int(new_source_link_count or 0)), max(0, int(snapshot_count or 0)),
                    int(bool(no_pair)), iso(observed_at or utcnow()),
                ),
            )

    def finish_token_discovery_round(
        self,
        round_id: int,
        *,
        status: str,
        requested_count: int = 0,
        returned_count: int = 0,
        duplicate_token_count: int = 0,
        error_type: str = "",
        completed_at: Any = None,
    ) -> None:
        allowed = {"completed", "error", "interrupted"}
        status = status if status in allowed else "error"
        error_type = re.sub(r"[^a-zA-Z0-9_.-]+", "", str(error_type))[:80]
        with self._lock, self.db:
            totals = self.db.execute(
                """
                SELECT COUNT(*) AS exposed_token_count,
                       COALESCE(SUM(first_local_discovery),0) AS first_local_discovery_count,
                       COALESCE(SUM(new_token),0) AS new_token_count,
                       COALESCE(SUM(source_link_count),0) AS source_link_count,
                       COALESCE(SUM(new_source_link_count),0) AS new_source_link_count,
                       COALESCE(SUM(snapshot_count),0) AS snapshot_count,
                       COALESCE(SUM(no_pair),0) AS no_pair_count
                FROM token_discovery_exposures WHERE round_id=?
                """,
                (int(round_id),),
            ).fetchone()
            self.db.execute(
                """
                UPDATE token_discovery_rounds SET
                    status=?,requested_count=?,returned_count=?,exposed_token_count=?,
                    first_local_discovery_count=?,new_token_count=?,duplicate_token_count=?,
                    source_link_count=?,new_source_link_count=?,snapshot_count=?,no_pair_count=?,
                    error_type=?,completed_at=?
                WHERE id=? AND status='running'
                """,
                (
                    status, max(0, int(requested_count or 0)), max(0, int(returned_count or 0)),
                    int(totals["exposed_token_count"] or 0),
                    int(totals["first_local_discovery_count"] or 0),
                    int(totals["new_token_count"] or 0), max(0, int(duplicate_token_count or 0)),
                    int(totals["source_link_count"] or 0),
                    int(totals["new_source_link_count"] or 0),
                    int(totals["snapshot_count"] or 0), int(totals["no_pair_count"] or 0),
                    error_type, iso(completed_at or utcnow()), int(round_id),
                ),
            )

    @classmethod
    def token_discovery_learning_summary_from_connection(
        cls,
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                "('token_discovery_rounds','token_discovery_exposures')"
            )
        }
        empty = {
            "status": "not_observed",
            "version": cls.TOKEN_DISCOVERY_EXPOSURE_VERSION,
            "items": [],
            "summary": {"rounds": 0, "completed": 0, "errors": 0, "first_local_discovery_count": 0},
            "mode": "forward_append_only_observation",
            "affects": "review_only_no_schedule_or_trading_effect",
        }
        if tables != {"token_discovery_rounds", "token_discovery_exposures"}:
            return empty
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = connection.execute(
            """
            SELECT provider,surface,mode,chain_scope,
                   COUNT(*) AS rounds,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,
                   SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running,
                   SUM(CASE WHEN status='interrupted' THEN 1 ELSE 0 END) AS interrupted,
                   SUM(CASE WHEN status='completed' AND first_local_discovery_count=0 THEN 1 ELSE 0 END)
                       AS completed_zero_new,
                   SUM(requested_count) AS requested_count,
                   SUM(returned_count) AS returned_count,
                   SUM(exposed_token_count) AS exposed_token_count,
                   SUM(first_local_discovery_count) AS first_local_discovery_count,
                   SUM(new_token_count) AS new_token_count,
                   SUM(duplicate_token_count) AS duplicate_token_count,
                   SUM(source_link_count) AS source_link_count,
                   SUM(new_source_link_count) AS new_source_link_count,
                   SUM(snapshot_count) AS snapshot_count,
                   SUM(no_pair_count) AS no_pair_count,
                   COUNT(DISTINCT substr(started_at,1,10)) AS round_day_count,
                   MAX(started_at) AS last_started_at
            FROM token_discovery_rounds WHERE started_at>=?
            GROUP BY provider,surface,mode,chain_scope
            ORDER BY completed DESC,rounds DESC,provider,surface
            """,
            (start,),
        ).fetchall()
        outcome_rows = connection.execute(
            """
            SELECT r.provider,r.surface,r.mode,r.chain_scope,
                   COUNT(DISTINCT CASE WHEN e.first_local_discovery=1 THEN e.token_id END)
                       AS first_tokens,
                   COUNT(DISTINCT CASE WHEN e.first_local_discovery=1 AND EXISTS(
                       SELECT 1 FROM decisions d WHERE d.token_id=e.token_id
                         AND d.action='CANDIDATE' AND d.created_at>=e.observed_at
                   ) THEN e.token_id END) AS candidate_tokens,
                   COUNT(DISTINCT CASE WHEN e.first_local_discovery=1 AND EXISTS(
                       SELECT 1 FROM trades t WHERE t.token_id=e.token_id
                         AND t.side='BUY' AND t.created_at>=e.observed_at
                   ) THEN e.token_id END) AS paper_bought_tokens
            FROM token_discovery_rounds r
            JOIN token_discovery_exposures e ON e.round_id=r.id
            WHERE r.started_at>=?
            GROUP BY r.provider,r.surface,r.mode,r.chain_scope
            """,
            (start,),
        ).fetchall()
        outcomes = {
            (str(row["provider"]), str(row["surface"]), str(row["mode"]), str(row["chain_scope"])): row
            for row in outcome_rows
        }
        latest: dict[tuple[str, str, str, str], sqlite3.Row] = {}
        for row in connection.execute(
            """
            SELECT provider,surface,mode,chain_scope,status,error_type,started_at,completed_at
            FROM token_discovery_rounds WHERE started_at>=? ORDER BY id DESC
            """,
            (start,),
        ):
            key = (
                str(row["provider"]), str(row["surface"]),
                str(row["mode"]), str(row["chain_scope"]),
            )
            latest.setdefault(key, row)
        items = []
        for row in rows:
            key = (
                str(row["provider"]), str(row["surface"]),
                str(row["mode"]), str(row["chain_scope"]),
            )
            outcome = outcomes.get(key)
            completed = int(row["completed"] or 0)
            first_count = int((outcome["first_tokens"] if outcome else 0) or 0)
            candidate_count = int((outcome["candidate_tokens"] if outcome else 0) or 0)
            bought_count = int((outcome["paper_bought_tokens"] if outcome else 0) or 0)
            last = latest[key]
            items.append(
                {
                    "provider": key[0], "surface": key[1], "mode": key[2], "chain_scope": key[3],
                    "rounds": int(row["rounds"] or 0), "completed": completed,
                    "errors": int(row["errors"] or 0), "running": int(row["running"] or 0),
                    "interrupted": int(row["interrupted"] or 0),
                    "completed_zero_new": int(row["completed_zero_new"] or 0),
                    "requested_count": int(row["requested_count"] or 0),
                    "returned_count": int(row["returned_count"] or 0),
                    "exposed_token_count": int(row["exposed_token_count"] or 0),
                    "first_local_discovery_count": first_count,
                    "new_token_count": int(row["new_token_count"] or 0),
                    "duplicate_token_count": int(row["duplicate_token_count"] or 0),
                    "source_link_count": int(row["source_link_count"] or 0),
                    "new_source_link_count": int(row["new_source_link_count"] or 0),
                    "snapshot_count": int(row["snapshot_count"] or 0),
                    "no_pair_count": int(row["no_pair_count"] or 0),
                    "round_day_count": int(row["round_day_count"] or 0),
                    "candidate_first_discoveries": candidate_count,
                    "paper_bought_first_discoveries": bought_count,
                    "candidate_conversion_rate": (
                        round(candidate_count / first_count, 6) if first_count else None
                    ),
                    "paper_buy_conversion_rate": (
                        round(bought_count / first_count, 6) if first_count else None
                    ),
                    "review_eligible": completed >= 20 and int(row["round_day_count"] or 0) >= 5,
                    "last_status": str(last["status"]),
                    "last_error_type": str(last["error_type"] or "") or None,
                    "last_started_at": str(last["started_at"]),
                    "last_completed_at": last["completed_at"],
                }
            )
        summary_names = (
            "rounds", "completed", "errors", "running", "interrupted", "completed_zero_new",
            "returned_count", "exposed_token_count", "first_local_discovery_count",
            "new_token_count", "source_link_count", "new_source_link_count", "snapshot_count",
        )
        summary = {name: sum(int(item[name] or 0) for item in items) for name in summary_names}
        summary["surfaces"] = len(items)
        summary["candidate_first_discoveries"] = sum(
            int(item["candidate_first_discoveries"] or 0) for item in items
        )
        summary["paper_bought_first_discoveries"] = sum(
            int(item["paper_bought_first_discoveries"] or 0) for item in items
        )
        summary["review_eligible_surfaces"] = sum(bool(item["review_eligible"]) for item in items)
        return {
            "status": "collecting" if items else "not_observed",
            "version": cls.TOKEN_DISCOVERY_EXPOSURE_VERSION,
            "items": items,
            "summary": summary,
            "mode": "forward_append_only_observation",
            "affects": "review_only_no_schedule_or_trading_effect",
            "cohort_definition": "first_local_discovery_at_or_after_version_activation",
            "as_of": iso(),
        }

    def get_kv(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        return default if not row else json.loads(row["value_json"])

    def set_kv(self, key: str, value: Any) -> None:
        with self._lock, self.db:
            self.db.execute(
                "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                (key,self._json(value),iso()),
            )

    def candidate_ranking(self, event_id: int) -> dict[str, Any] | None:
        value = self.get_kv(f"{self.CANDIDATE_RANKING_KEY_PREFIX}{int(event_id)}")
        return value if isinstance(value, dict) else None

    def set_candidate_ranking(self, event_id: int, value: dict[str, Any]) -> None:
        payload = dict(value)
        payload["event_id"] = int(event_id)
        self.set_kv(f"{self.CANDIDATE_RANKING_KEY_PREFIX}{int(event_id)}", payload)

    def finalize_candidate_ranking(
        self,
        event_id: int,
        decision: CandidateDecision,
        *,
        decision_id: int,
    ) -> None:
        """Attach Runtime's final sizing/action without inventing a missing ranking."""
        ranking = self.candidate_ranking(event_id)
        if ranking is None:
            return
        final_outcome = {
            "decision_id": int(decision_id),
            "action": str(decision.action),
            "token_id": str(decision.token_id),
            "candidate_score": float(decision.score),
            "match_score": float(decision.match_score),
            "canonical_margin": float(decision.canonical_margin),
            "position_usd": float(decision.position_usd),
            "reasons": [str(reason) for reason in decision.reasons],
            "rejected_reasons": [str(reason) for reason in decision.rejected_reasons],
            "created_at": iso(decision.created_at),
        }
        ranking["status"] = "completed"
        ranking["outcome"] = str(decision.action)
        ranking["final_outcome"] = final_outcome
        for candidate in ranking.get("candidates") or []:
            if not isinstance(candidate, dict) or str(candidate.get("token_id") or "") != decision.token_id:
                continue
            candidate["action"] = str(decision.action)
            candidate["position_usd"] = float(decision.position_usd)
            candidate["reasons"] = [str(reason) for reason in decision.reasons]
            candidate["rejected_reasons"] = [str(reason) for reason in decision.rejected_reasons]
            candidate["selection_status"] = "selected_for_final_decision"
            break
        self.set_candidate_ranking(event_id, ranking)

    def increment_kv(self, key: str, amount: int) -> int:
        """Atomically increment an integer KV value and return the new value."""
        with self._lock, self.db:
            row = self.db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
            current = int(json.loads(row["value_json"])) if row else 0
            value = current + int(amount)
            self.db.execute(
                "INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                (key, self._json(value), iso()),
            )
            return value

    def add_agent_attempt(self, attempt: dict[str, Any]) -> bool:
        """Persist one sanitized Codex attempt; returns False for an existing attempt."""
        fields = (
            "run_id", "attempt_index", "task", "model", "reasoning_effort",
            "started_at", "finished_at", "status", "returncode", "fallback",
            "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
            "output_tokens", "reasoning_output_tokens", "total_tokens", "accounting_source",
        )
        with self._lock, self.db:
            cursor = self.db.execute(
                f"INSERT OR IGNORE INTO agent_attempts({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                tuple(attempt.get(field) for field in fields),
            )
            return cursor.rowcount == 1

    def start_trend_lane_run(
        self,
        *,
        run_id: str,
        taxonomy_version: str,
        prompt_version: str,
        selection_mode: str,
        surge: bool,
        max_web_searches: int,
        started_at: Any,
        lanes: Iterable[Mapping[str, Any]],
        watch_accounts: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        lane_rows = list(lanes)
        account_rows = list(watch_accounts)
        coverage = len(lane_rows) / max(1, int(lane_rows[0].get("total_lane_count", len(lane_rows)))) if lane_rows else 0.0
        with self._lock, self.db:
            self.db.execute(
                """
                INSERT INTO trend_lane_runs(
                    run_id,taxonomy_version,prompt_version,selection_mode,surge,max_web_searches,
                    started_at,status,observation_ingestion_status
                ) VALUES(?,?,?,?,?,?,?,'running','pending')
                """,
                (
                    str(run_id), str(taxonomy_version), str(prompt_version), str(selection_mode),
                    int(bool(surge)), int(max_web_searches), iso(started_at),
                ),
            )
            for lane in lane_rows:
                self.db.execute(
                    """
                    INSERT INTO trend_lane_run_lanes(
                        run_id,lane_id,lane_prompt,event_topics_json,selection_role,
                        attention_multiplier,scheduled_coverage_fraction
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        str(run_id), str(lane.get("id") or "")[:64], str(lane.get("prompt") or "")[:500],
                        self._json(list(lane.get("event_topics") or [])),
                        str(lane.get("selection_role") or "baseline")[:32],
                        max(0.80, min(1.20, float(lane.get("attention_multiplier") or 1.0))),
                        float(coverage),
                    ),
                )
            for account in account_rows:
                platform = str(account.get("platform") or "").strip().lower()[:32]
                handle = str(account.get("handle") or "").strip()[:120]
                handle_key = handle.casefold()
                if not platform or not handle_key:
                    continue
                self.db.execute(
                    """
                    INSERT INTO trend_watch_account_exposures(
                        run_id,platform,handle,handle_key,entity_id,configured_priority,watch_cadence,
                        selection_role,learning_basis,learning_multiplier
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(run_id), platform, handle, handle_key,
                        str(account.get("entity_id") or "")[:64],
                        max(1, min(5, int(account.get("priority") or 3))),
                        str(account.get("watch_cadence") or "normal")[:32],
                        str(account.get("selection_role") or "baseline")[:32],
                        str(account.get("learning_basis") or "baseline")[:32],
                        max(0.5, min(1.5, float(account.get("learning_multiplier") or 1.0))),
                    ),
                )

    def finish_trend_lane_run(
        self,
        run_id: str,
        *,
        status: str,
        model: str = "",
        reasoning_effort: str = "",
        accepted_by_lane: Mapping[str, int] | None = None,
        observations_by_lane: Mapping[str, int] | None = None,
        account_results: Mapping[tuple[str, str], Mapping[str, int]] | None = None,
        rejected_event_count: int = 0,
        error_type: str = "",
        finished_at: Any = None,
    ) -> None:
        accepted = {str(key): max(0, int(value)) for key, value in (accepted_by_lane or {}).items()}
        observations = {str(key): max(0, int(value)) for key, value in (observations_by_lane or {}).items()}
        accounts = account_results or {}
        with self._lock, self.db:
            for lane_id in set(accepted) | set(observations):
                self.db.execute(
                    """
                    UPDATE trend_lane_run_lanes
                    SET accepted_event_count=?,observation_count=?
                    WHERE run_id=? AND lane_id=?
                    """,
                    (accepted.get(lane_id, 0), observations.get(lane_id, 0), str(run_id), lane_id),
                )
            for (platform, handle_key), values in accounts.items():
                self.db.execute(
                    """
                    UPDATE trend_watch_account_exposures
                    SET exact_source_hits=?,accepted_event_count=?,observation_count=?
                    WHERE run_id=? AND platform=? AND handle_key=?
                    """,
                    (
                        max(0, int(values.get("exact_source_hits", 0))),
                        max(0, int(values.get("accepted_event_count", 0))),
                        max(0, int(values.get("observation_count", 0))),
                        str(run_id), str(platform), str(handle_key),
                    ),
                )
            self.db.execute(
                """
                UPDATE trend_lane_runs
                SET finished_at=?,status=?,model=?,reasoning_effort=?,accepted_event_count=?,
                    rejected_event_count=?,observation_count=?,error_type=?
                WHERE run_id=?
                """,
                (
                    iso(finished_at or utcnow()), str(status)[:32], str(model)[:120], str(reasoning_effort)[:32],
                    sum(accepted.values()), max(0, int(rejected_event_count)), sum(observations.values()),
                    str(error_type)[:160], str(run_id),
                ),
            )

    def finalize_trend_lane_observation_ingestion(
        self,
        run_id: str,
        *,
        status: str,
        finalized_at: Any = None,
    ) -> None:
        status = str(status).strip().lower()
        if status not in {"completed", "error"}:
            raise ValueError("trend observation ingestion status must be completed or error")
        with self._lock, self.db:
            self.db.execute(
                """
                UPDATE trend_lane_runs
                SET observation_ingestion_status=?,observation_ingestion_finalized_at=?
                WHERE run_id=? AND observation_ingestion_status='pending'
                """,
                (status, iso(finalized_at or utcnow()), str(run_id)),
            )

    @staticmethod
    def _browser_exposure_window(value: Any, minutes: int = 30) -> tuple[str, str]:
        observed = parse_time(value)
        bucket_minute = observed.minute - (observed.minute % max(1, int(minutes)))
        started = observed.replace(minute=bucket_minute, second=0, microsecond=0)
        return iso(started), started.strftime("%Y%m%dT%H%MZ")

    def record_browser_watch_heartbeat(
        self,
        account: Mapping[str, Any],
        *,
        access_state: str,
        visible: bool | None,
        selector_count: int,
        observed_at: Any = None,
    ) -> str:
        observed = parse_time(observed_at) if observed_at is not None else utcnow()
        window_started_at, window_key = self._browser_exposure_window(observed)
        platform = str(account.get("platform") or "").strip().lower()[:32]
        handle = str(account.get("handle") or "").strip()[:120]
        handle_key = handle.casefold()
        entity_id = str(account.get("entity_id") or "").strip().lower()[:64]
        if not platform or not handle_key or not entity_id:
            raise ValueError("browser watch exposure requires platform, handle and entity_id")
        state = str(access_state or "unknown").strip().lower()
        status = (
            "completed" if state in {"accessible", "authenticated"}
            else "access_error" if state in {"login_required", "blocked"}
            else "observed"
        )
        exposure_id = f"{window_key}:{platform}:{handle_key}"
        with self._lock, self.db:
            self.db.execute(
                """
                INSERT INTO browser_watch_account_exposures(
                    exposure_id,window_started_at,last_heartbeat_at,platform,handle,handle_key,
                    entity_id,configured_priority,watch_cadence,status,access_state,visible,selector_count
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(exposure_id) DO UPDATE SET
                    last_heartbeat_at=excluded.last_heartbeat_at,
                    status=CASE
                        WHEN browser_watch_account_exposures.status='completed' THEN 'completed'
                        ELSE excluded.status
                    END,
                    access_state=excluded.access_state,
                    visible=excluded.visible,
                    selector_count=MAX(browser_watch_account_exposures.selector_count,excluded.selector_count)
                """,
                (
                    exposure_id, window_started_at, iso(observed), platform, handle, handle_key,
                    entity_id, max(1, min(5, int(account.get("priority") or 3))),
                    str(account.get("watch_cadence") or "normal")[:32], status, state,
                    None if visible is None else int(visible), max(0, int(selector_count)),
                ),
            )
        return exposure_id

    def record_browser_watch_observation(
        self,
        account: Mapping[str, Any],
        *,
        observation_id: int,
        event_id: int,
        observed_at: Any,
        decision_eligible: bool,
    ) -> str:
        exposure_id = self.record_browser_watch_heartbeat(
            account,
            access_state="authenticated",
            visible=None,
            selector_count=0,
            observed_at=observed_at,
        )
        with self._lock, self.db:
            inserted = self.db.execute(
                """
                INSERT OR IGNORE INTO browser_watch_observation_links(
                    observation_id,exposure_id,event_id,observed_at,decision_eligible
                ) VALUES(?,?,?,?,?)
                """,
                (int(observation_id), exposure_id, int(event_id), iso(parse_time(observed_at)),
                 int(bool(decision_eligible))),
            ).rowcount
            if inserted:
                self.db.execute(
                """
                UPDATE browser_watch_account_exposures
                SET exact_source_hits=exact_source_hits+1,
                    observation_count=observation_count+1,
                    accepted_event_count=accepted_event_count+?
                WHERE exposure_id=?
                """,
                    (int(bool(decision_eligible)), exposure_id),
                )
        return exposure_id

    def register_attention_experiment(
        self,
        *,
        experiment_id: str,
        hypothesis: str,
        challenger: Mapping[str, Any],
        control: Mapping[str, Any],
        random_seed: str,
        registered_at: Any = None,
    ) -> bool:
        """Register one immutable, forward-only watch-account attention experiment."""
        experiment_id = re.sub(r"[^a-zA-Z0-9:._-]+", "-", str(experiment_id).strip())[:160]
        random_seed = re.sub(r"[^a-zA-Z0-9._-]+", "", str(random_seed).strip())[:160]
        if not experiment_id or len(random_seed) < 16:
            raise ValueError("attention experiment requires an id and a non-trivial random seed")

        def target(value: Mapping[str, Any]) -> tuple[str, str, str]:
            platform = str(value.get("platform") or "").strip().lower()[:32]
            handle_key = str(value.get("handle") or value.get("handle_key") or "").strip().casefold()[:120]
            entity_id = str(value.get("entity_id") or "").strip().lower()[:64]
            if not platform or not handle_key or not entity_id:
                raise ValueError("attention experiment targets require platform, handle and entity_id")
            return platform, handle_key, entity_id

        challenger_target = target(challenger)
        control_target = target(control)
        if challenger_target[:2] == control_target[:2]:
            raise ValueError("challenger and control must be distinct accounts")
        if challenger_target[0] != control_target[0]:
            raise ValueError("v1 challenger and control must use the same platform")
        config = {
            "assignment": "balanced_blocks_2_challenger_2_control",
            "assignment_probability": 0.5,
            "primary_inference_metric": "productive_terminal_assignment_rate",
            "descriptive_yield_metric": "unique_decision_eligible_events_per_completed_exposure",
            "secondary_metric": "observed_60m_positive_return_rate",
            "planned_assignments_per_arm": 60,
            "primary_population": "intention_to_observe_including_agent_and_pre_run_failures",
            "minimum_calendar_days": 15,
            "minimum_zero_yield_per_arm": 10,
            "minimum_unique_events_per_arm": 20,
            "minimum_observed_coverage": 0.80,
            "maximum_coverage_gap": 0.10,
            "maximum_terminal_failure_gap": 0.10,
            "maximum_cross_arm_collision_rate": 0.10,
            "minimum_productive_rate_difference_lower_bound": 0.05,
            "minimum_positive_rate_difference_lower_bound": -0.10,
            "confidence": "two_sided_95pct_newcombe_wilson_lower_endpoint",
            "automatic_promotion": False,
            "maximum_future_multiplier": 1.10,
            "requires_independent_holdout": True,
            "affects": "one_normal_trend_scout_watch_slot_only",
            "never_affects": [
                "evidence_weight", "candidate_ranking", "decision_eligibility", "risk",
                "position_size", "paper_execution", "exits", "live_trading",
            ],
        }
        when = iso(registered_at or utcnow())
        with self._lock, self.db:
            cursor = self.db.execute(
                """
                INSERT OR IGNORE INTO attention_experiments(
                    experiment_id,version,target_kind,hypothesis,
                    challenger_platform,challenger_handle_key,challenger_entity_id,
                    control_platform,control_handle_key,control_entity_id,random_seed,
                    assignment_block_size,planned_assignments_per_arm,min_calendar_days,
                    config_json,registered_at
                ) VALUES(?,?,'watch_account',?,?,?,?,?,?,?,?,4,60,15,?,?)
                """,
                (
                    experiment_id, self.ATTENTION_EXPERIMENT_VERSION, str(hypothesis).strip()[:1000],
                    *challenger_target, *control_target, random_seed, self._json(config), when,
                ),
            )
            if cursor.rowcount != 1:
                return False
            self.db.execute(
                """
                INSERT INTO attention_experiment_events(
                    experiment_id,event_type,effective_at,reason,created_at
                ) VALUES(?,'registered',?,'preregistered_forward_only',?)
                """,
                (experiment_id, when, iso()),
            )
            return True

    def set_attention_experiment_state(
        self,
        experiment_id: str,
        event_type: str,
        *,
        reason: str,
        effective_at: Any = None,
    ) -> None:
        event_type = str(event_type).strip().lower()
        if event_type not in {"activated", "paused", "completed", "invalid"}:
            raise ValueError("unsupported attention experiment state")
        parsed_when = parse_time(effective_at) if effective_at is not None else utcnow()
        if parsed_when > utcnow() + timedelta(seconds=5):
            raise ValueError("attention experiment state cannot be future-dated")
        when = iso(parsed_when)
        with self._lock, self.db:
            experiment = self.db.execute(
                "SELECT experiment_id,registered_at FROM attention_experiments WHERE experiment_id=?",
                (str(experiment_id),),
            ).fetchone()
            if experiment is None:
                raise ValueError("attention experiment not found")
            latest = self.db.execute(
                """
                SELECT effective_at FROM attention_experiment_events
                WHERE experiment_id=? ORDER BY id DESC LIMIT 1
                """,
                (str(experiment_id),),
            ).fetchone()
            lower_bound = parse_time(
                latest["effective_at"] if latest is not None else experiment["registered_at"]
            )
            if parsed_when < lower_bound:
                raise ValueError("attention experiment state cannot be backdated")
            if event_type == "activated":
                active = self.db.execute(
                    """
                    SELECT e.experiment_id FROM attention_experiments e
                    JOIN attention_experiment_events v ON v.id=(
                        SELECT id FROM attention_experiment_events
                        WHERE experiment_id=e.experiment_id
                        ORDER BY id DESC LIMIT 1
                    )
                    WHERE v.event_type='activated' AND e.experiment_id<>? LIMIT 1
                    """,
                    (str(experiment_id),),
                ).fetchone()
                if active is not None:
                    raise ValueError("only one attention experiment may be active")
            self.db.execute(
                """
                INSERT INTO attention_experiment_events(
                    experiment_id,event_type,effective_at,reason,created_at
                ) VALUES(?,?,?,?,?)
                """,
                (str(experiment_id), event_type, when, str(reason)[:500], iso()),
            )

    @staticmethod
    def _active_attention_experiment_from_connection(
        connection: sqlite3.Connection,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT e.* FROM attention_experiments e
            JOIN attention_experiment_events v ON v.id=(
                SELECT id FROM attention_experiment_events
                WHERE experiment_id=e.experiment_id
                ORDER BY id DESC LIMIT 1
            )
            WHERE v.event_type='activated'
            ORDER BY e.registered_at DESC,e.experiment_id DESC LIMIT 1
            """
        ).fetchone()
        return dict(row) if row is not None else None

    def active_attention_experiment(self) -> dict[str, Any] | None:
        with self._lock:
            return self._active_attention_experiment_from_connection(self.db)

    def reserve_attention_experiment_assignment(
        self,
        *,
        run_id: str,
        accounts: Iterable[Mapping[str, Any]],
        assigned_at: Any = None,
    ) -> dict[str, Any] | None:
        """Atomically persist the balanced assignment that chooses one normal watch slot."""
        account_rows = [dict(account) for account in accounts]
        with self._lock, self.db:
            existing = self.db.execute(
                "SELECT * FROM attention_experiment_assignments WHERE run_id=?",
                (str(run_id),),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            experiment = self._active_attention_experiment_from_connection(self.db)
            if experiment is None:
                return None
            candidates = {
                (
                    str(account.get("platform") or "").strip().lower(),
                    str(account.get("handle") or "").strip().casefold(),
                ): account
                for account in account_rows
                if account.get("enabled", True) is True
                and str(account.get("watch_cadence") or "normal").lower() == "normal"
            }
            challenger_key = (
                str(experiment["challenger_platform"]), str(experiment["challenger_handle_key"])
            )
            control_key = (
                str(experiment["control_platform"]), str(experiment["control_handle_key"])
            )
            challenger = candidates.get(challenger_key)
            control = candidates.get(control_key)
            if challenger is None or control is None:
                return None
            if int(challenger.get("priority") or 0) != int(control.get("priority") or 0):
                return None
            if str(challenger.get("entity_id") or "").lower() != str(
                experiment["challenger_entity_id"]
            ) or str(control.get("entity_id") or "").lower() != str(experiment["control_entity_id"]):
                return None
            assignment_index = int(
                self.db.execute(
                    "SELECT COUNT(*) FROM attention_experiment_assignments WHERE experiment_id=?",
                    (str(experiment["experiment_id"]),),
                ).fetchone()[0]
            )
            planned_per_arm = max(1, int(experiment["planned_assignments_per_arm"]))
            if assignment_index >= planned_per_arm * 2:
                return None
            block = assignment_index // 4
            position = assignment_index % 4
            entries = ["challenger:0", "challenger:1", "control:0", "control:1"]
            seed = str(experiment["random_seed"])
            entries.sort(
                key=lambda value: hashlib.sha256(
                    f"{seed}\n{block}\n{value}".encode("utf-8")
                ).hexdigest()
            )
            arm = entries[position].split(":", 1)[0]
            chosen = challenger if arm == "challenger" else control
            platform = str(chosen.get("platform") or "").strip().lower()
            handle_key = str(chosen.get("handle") or "").strip().casefold()
            entity_id = str(chosen.get("entity_id") or "").strip().lower()
            assignment_id = hashlib.sha256(
                f"{experiment['experiment_id']}\n{run_id}".encode("utf-8")
            ).hexdigest()
            self.db.execute(
                """
                INSERT INTO attention_experiment_assignments(
                    assignment_id,experiment_id,run_id,arm,target_platform,target_handle_key,
                    target_entity_id,assignment_index,assignment_probability,assigned_at
                ) VALUES(?,?,?,?,?,?,?,?,0.5,?)
                """,
                (
                    assignment_id, str(experiment["experiment_id"]), str(run_id), arm,
                    platform, handle_key, entity_id, assignment_index,
                    iso(assigned_at or utcnow()),
                ),
            )
            return dict(
                self.db.execute(
                    "SELECT * FROM attention_experiment_assignments WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchone()
            )

    def record_attention_experiment_observation(
        self,
        *,
        run_id: str,
        platform: str,
        handle: str,
        entity_id: str,
        observation_id: int,
        event_id: int,
        decision_eligible: bool,
        observed_at: Any,
    ) -> bool:
        with self._lock, self.db:
            assignment = self.db.execute(
                """
                SELECT * FROM attention_experiment_assignments
                WHERE run_id=? AND target_platform=? AND target_handle_key=? AND target_entity_id=?
                """,
                (
                    str(run_id), str(platform).strip().lower(), str(handle).strip().casefold(),
                    str(entity_id).strip().lower(),
                ),
            ).fetchone()
            if assignment is None:
                return False
            inserted = self.db.execute(
                """
                INSERT OR IGNORE INTO attention_experiment_observation_links(
                    experiment_id,assignment_id,observation_id,event_id,arm,
                    decision_eligible,observed_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    str(assignment["experiment_id"]), str(assignment["assignment_id"]),
                    int(observation_id), int(event_id), str(assignment["arm"]),
                    int(bool(decision_eligible)), iso(parse_time(observed_at)),
                ),
            )
            return inserted.rowcount == 1

    def create_attention_experiment_event_cohort(
        self,
        *,
        event_id: int,
        decision_id: int,
        shadow_cohort_id: int | None,
    ) -> int:
        """Freeze at most one experiment outcome cohort per event without backfilling."""
        created = 0
        with self._lock, self.db:
            experiments = list(
                self.db.execute(
                    """
                    SELECT DISTINCT experiment_id FROM attention_experiment_observation_links
                    WHERE event_id=? AND decision_eligible=1
                    """,
                    (int(event_id),),
                )
            )
            decision = self.db.execute(
                "SELECT created_at FROM decisions WHERE id=?", (int(decision_id),)
            ).fetchone()
            if decision is None:
                return 0
            shadow = (
                self.db.execute(
                    """
                    SELECT * FROM shadow_event_cohorts
                    WHERE id=? AND event_id=? AND decision_id=?
                    """,
                    (int(shadow_cohort_id), int(event_id), int(decision_id)),
                ).fetchone()
                if shadow_cohort_id is not None else None
            )
            for experiment_row in experiments:
                experiment_id = str(experiment_row["experiment_id"])
                if self.db.execute(
                    "SELECT 1 FROM attention_experiment_event_cohorts WHERE experiment_id=? AND event_id=?",
                    (experiment_id, int(event_id)),
                ).fetchone() is not None:
                    continue
                links = list(
                    self.db.execute(
                        """
                        SELECT * FROM attention_experiment_observation_links
                        WHERE experiment_id=? AND event_id=? AND decision_eligible=1
                        ORDER BY observed_at,observation_id
                        """,
                        (experiment_id, int(event_id)),
                    )
                )
                arms = {str(row["arm"]) for row in links}
                winner = links[0] if len(arms) == 1 and links else None
                status = "cross_arm_collision" if len(arms) > 1 else (
                    "pending" if winner is not None and shadow is not None else "untrackable"
                )
                cursor = self.db.execute(
                    """
                    INSERT INTO attention_experiment_event_cohorts(
                        experiment_id,event_id,assignment_id,arm,source_observation_id,
                        decision_id,decision_at,token_id,entry_snapshot_id,entry_snapshot_at,
                        entry_price,status,linked_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        experiment_id, int(event_id),
                        str(winner["assignment_id"]) if winner is not None else None,
                        str(winner["arm"]) if winner is not None else None,
                        int(winner["observation_id"]) if winner is not None else None,
                        int(decision_id), str(decision["created_at"]),
                        str(shadow["token_id"]) if shadow is not None else "",
                        int(shadow["entry_snapshot_id"]) if shadow is not None else None,
                        str(shadow["entry_snapshot_at"]) if shadow is not None else None,
                        float(shadow["entry_price"]) if shadow is not None else None,
                        status, iso(),
                    ),
                )
                created += int(cursor.rowcount == 1)
        return created

    def finalize_attention_experiment_outcomes(
        self,
        *,
        now: Any = None,
        max_lateness_minutes: int = 30,
    ) -> dict[str, int]:
        evaluated_at = parse_time(now) if now is not None else utcnow()
        observed = missing = excluded = 0
        with self._lock, self.db:
            cohorts = list(
                self.db.execute(
                    """
                    SELECT c.* FROM attention_experiment_event_cohorts c
                    LEFT JOIN attention_experiment_outcomes o ON o.cohort_id=c.id
                    WHERE o.cohort_id IS NULL ORDER BY c.decision_at,c.id
                    """
                )
            )
            for cohort in cohorts:
                target = parse_time(cohort["decision_at"]) + timedelta(
                    minutes=self.ATTENTION_EXPERIMENT_HORIZON_MINUTES
                )
                if evaluated_at < target:
                    continue
                arm_count = int(
                    self.db.execute(
                        """
                        SELECT COUNT(DISTINCT arm) FROM attention_experiment_observation_links
                        WHERE experiment_id=? AND event_id=? AND decision_eligible=1
                        """,
                        (str(cohort["experiment_id"]), int(cohort["event_id"])),
                    ).fetchone()[0]
                )
                if arm_count > 1 or str(cohort["status"]) == "cross_arm_collision":
                    status = "cross_arm_collision"
                    snapshot = None
                elif str(cohort["status"]) != "pending" or not cohort["token_id"]:
                    status = "untrackable"
                    snapshot = None
                else:
                    deadline = target + timedelta(minutes=max(1, int(max_lateness_minutes)))
                    upper = min(evaluated_at, deadline)
                    snapshot = self.db.execute(
                        """
                        SELECT id,observed_at,ingested_at,price_usd FROM token_snapshots
                        WHERE token_id=? AND observed_at>=? AND observed_at<=?
                          AND ingested_at>=? AND ingested_at<=?
                          AND ingested_at>=observed_at AND price_usd>0
                        ORDER BY ingested_at,observed_at,id LIMIT 1
                        """,
                        (str(cohort["token_id"]), iso(target), iso(upper), iso(target), iso(upper)),
                    ).fetchone()
                    if snapshot is not None:
                        status = "observed"
                    elif evaluated_at >= deadline:
                        status = "missing"
                    else:
                        continue
                raw_return = (
                    float(snapshot["price_usd"]) / float(cohort["entry_price"]) - 1.0
                    if snapshot is not None and cohort["entry_price"] else None
                )
                self.db.execute(
                    """
                    INSERT INTO attention_experiment_outcomes(
                        cohort_id,horizon_minutes,target_at,status,outcome_snapshot_id,
                        outcome_observed_at,outcome_price,raw_return,evaluated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        int(cohort["id"]), self.ATTENTION_EXPERIMENT_HORIZON_MINUTES,
                        iso(target), status,
                        int(snapshot["id"]) if snapshot is not None else None,
                        str(snapshot["observed_at"]) if snapshot is not None else None,
                        float(snapshot["price_usd"]) if snapshot is not None else None,
                        raw_return, iso(evaluated_at),
                    ),
                )
                observed += int(status == "observed")
                missing += int(status == "missing")
                excluded += int(status in {"untrackable", "cross_arm_collision"})
        return {"cohorts_checked": len(cohorts), "observed": observed, "missing": missing, "excluded": excluded}

    @staticmethod
    def _two_sided_wilson_95(successes: int, total: int) -> tuple[float, float] | None:
        if total <= 0:
            return None
        z = 1.959963984540054
        p = successes / total
        denominator = 1.0 + z * z / total
        center = (p + z * z / (2.0 * total)) / denominator
        radius = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denominator
        return max(0.0, center - radius), min(1.0, center + radius)

    @classmethod
    def _newcombe_difference_lower_bound(
        cls,
        challenger_successes: int,
        challenger_total: int,
        control_successes: int,
        control_total: int,
    ) -> float | None:
        challenger_bounds = cls._two_sided_wilson_95(challenger_successes, challenger_total)
        control_bounds = cls._two_sided_wilson_95(control_successes, control_total)
        if challenger_bounds is None or control_bounds is None:
            return None
        challenger_rate = challenger_successes / challenger_total
        control_rate = control_successes / control_total
        return (challenger_rate - control_rate) - math.sqrt(
            (challenger_rate - challenger_bounds[0]) ** 2
            + (control_bounds[1] - control_rate) ** 2
        )

    @classmethod
    def attention_experiment_summary_from_connection(
        cls,
        connection: sqlite3.Connection,
    ) -> dict[str, Any]:
        required = {
            "attention_experiments", "attention_experiment_events",
            "attention_experiment_assignments", "attention_experiment_observation_links",
            "attention_experiment_event_cohorts", "attention_experiment_outcomes",
        }
        tables = {
            str(row["name"])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if str(row["name"]) in required
        }
        empty = {
            "version": cls.ATTENTION_EXPERIMENT_VERSION,
            "status": "not_registered", "experiment": None,
            "arms": {"challenger": {}, "control": {}},
            "gates": {}, "stage1_ready": False,
            "automatic_promotion": False, "actual_multiplier": 1.0,
            "affects": "one_normal_trend_scout_watch_slot_only",
        }
        if tables != required:
            return empty
        experiment = connection.execute(
            """
            SELECT e.* FROM attention_experiments e
            JOIN attention_experiment_events v ON v.id=(
                SELECT id FROM attention_experiment_events
                WHERE experiment_id=e.experiment_id ORDER BY id DESC LIMIT 1
            )
            ORDER BY CASE WHEN v.event_type='activated' THEN 0 ELSE 1 END,
                     e.registered_at DESC,e.experiment_id DESC
            LIMIT 1
            """
        ).fetchone()
        if experiment is None:
            return empty
        experiment_id = str(experiment["experiment_id"])
        latest_event = connection.execute(
            """
            SELECT event_type,effective_at,reason FROM attention_experiment_events
            WHERE experiment_id=? ORDER BY id DESC LIMIT 1
            """,
            (experiment_id,),
        ).fetchone()
        assignments = list(
            connection.execute(
                """
                SELECT a.*,r.status AS run_status,r.started_at,r.finished_at,
                       r.observation_ingestion_status,r.observation_ingestion_finalized_at,
                       w.exact_source_hits,w.accepted_event_count,w.observation_count
                FROM attention_experiment_assignments a
                LEFT JOIN trend_lane_runs r ON r.run_id=a.run_id
                LEFT JOIN trend_watch_account_exposures w
                  ON w.run_id=a.run_id AND w.platform=a.target_platform
                 AND w.handle_key=a.target_handle_key
                WHERE a.experiment_id=? ORDER BY a.assignment_index
                """,
                (experiment_id,),
            )
        )
        completed_ids = {
            str(row["assignment_id"])
            for row in assignments
            if str(row["run_status"] or "") == "completed"
            and str(row["observation_ingestion_status"] or "") == "completed"
            and row["exact_source_hits"] is not None
        }
        error_ids = {
            str(row["assignment_id"])
            for row in assignments
            if str(row["run_status"] or "") == "agent_error"
            or str(row["observation_ingestion_status"] or "") == "error"
        }
        stale_cutoff = utcnow() - timedelta(minutes=30)
        cancelled_before_agent_ids = {
            str(row["assignment_id"])
            for row in assignments
            if row["run_status"] is None and parse_time(row["assigned_at"]) <= stale_cutoff
        }
        terminal_ids = completed_ids | error_ids | cancelled_before_agent_ids
        links = list(
            connection.execute(
                """
                SELECT * FROM attention_experiment_observation_links
                WHERE experiment_id=? AND decision_eligible=1
                ORDER BY event_id,observed_at,observation_id
                """,
                (experiment_id,),
            )
        )
        by_event: dict[int, list[sqlite3.Row]] = {}
        for row in links:
            by_event.setdefault(int(row["event_id"]), []).append(row)
        event_attribution: dict[int, sqlite3.Row] = {}
        collision_events: set[int] = set()
        for event_id, rows in by_event.items():
            if len({str(row["arm"]) for row in rows}) > 1:
                collision_events.add(event_id)
            else:
                event_attribution[event_id] = rows[0]
        config = json.loads(str(experiment["config_json"] or "{}"))
        arm_stats: dict[str, dict[str, Any]] = {}
        for arm in ("challenger", "control"):
            arm_rows = [row for row in assignments if str(row["arm"]) == arm]
            completed = [row for row in arm_rows if str(row["assignment_id"]) in completed_ids]
            errors = [row for row in arm_rows if str(row["assignment_id"]) in error_ids]
            cancelled = [
                row for row in arm_rows
                if str(row["assignment_id"]) in cancelled_before_agent_ids
            ]
            terminal = [row for row in arm_rows if str(row["assignment_id"]) in terminal_ids]
            attributed = {
                event_id: row for event_id, row in event_attribution.items()
                if str(row["arm"]) == arm and str(row["assignment_id"]) in completed_ids
            }
            productive_ids = {str(row["assignment_id"]) for row in attributed.values()}
            terminal_failures = len(errors) + len(cancelled)
            arm_stats[arm] = {
                "assigned": len(arm_rows),
                "completed": len(completed),
                "agent_errors": len(errors),
                "cancelled_before_agent": len(cancelled),
                "terminal_assignments": len(terminal),
                "pending_or_unstarted": max(0, len(arm_rows) - len(terminal)),
                "calendar_days": len({
                    str(row["started_at"] or row["assigned_at"])[:10] for row in terminal
                }),
                "productive_exposures": len(productive_ids),
                "zero_yield_completed_exposures": max(0, len(completed) - len(productive_ids)),
                "unique_decision_eligible_events": len(attributed),
                "productive_exposure_rate": round(len(productive_ids) / len(terminal), 6)
                if terminal else None,
                "unique_events_per_completed_exposure": round(len(attributed) / len(completed), 6)
                if completed else None,
                "terminal_failure_rate": round(terminal_failures / len(terminal), 6)
                if terminal else None,
            }
        outcomes = {
            int(row["event_id"]): row
            for row in connection.execute(
                """
                SELECT c.event_id,c.status AS cohort_status,o.status,o.raw_return
                FROM attention_experiment_event_cohorts c
                LEFT JOIN attention_experiment_outcomes o
                  ON o.cohort_id=c.id AND o.horizon_minutes=?
                WHERE c.experiment_id=?
                """,
                (cls.ATTENTION_EXPERIMENT_HORIZON_MINUTES, experiment_id),
            )
        }
        for arm in ("challenger", "control"):
            attributed_event_ids = {
                event_id for event_id, row in event_attribution.items()
                if str(row["arm"]) == arm and str(row["assignment_id"]) in completed_ids
            }
            values = [outcomes.get(event_id) for event_id in attributed_event_ids]
            observed_rows = [row for row in values if row is not None and str(row["status"]) == "observed"]
            missing_rows = [
                row for row in values
                if row is not None and str(row["status"]) in {"missing", "untrackable"}
            ]
            positives = sum(float(row["raw_return"] or 0) > 0 for row in observed_rows)
            terminal_market = len(observed_rows) + len(missing_rows)
            denominator = len(attributed_event_ids)
            arm_stats[arm].update(
                {
                    "market_outcomes_observed": len(observed_rows),
                    "market_outcomes_missing_or_untrackable": len(missing_rows),
                    "market_outcomes_pending": max(0, denominator - terminal_market),
                    "market_positive": positives,
                    "market_observed_coverage": round(len(observed_rows) / denominator, 6)
                    if denominator else None,
                    "market_positive_rate": round(positives / len(observed_rows), 6)
                    if observed_rows else None,
                }
            )
        challenger = arm_stats["challenger"]
        control = arm_stats["control"]
        productive_lower = cls._newcombe_difference_lower_bound(
            int(challenger["productive_exposures"]), int(challenger["terminal_assignments"]),
            int(control["productive_exposures"]), int(control["terminal_assignments"]),
        )
        market_lower = cls._newcombe_difference_lower_bound(
            int(challenger["market_positive"]), int(challenger["market_outcomes_observed"]),
            int(control["market_positive"]), int(control["market_outcomes_observed"]),
        )
        failure_rates = [challenger["terminal_failure_rate"], control["terminal_failure_rate"]]
        failure_gap = (
            abs(float(failure_rates[0]) - float(failure_rates[1]))
            if None not in failure_rates else None
        )
        coverages = [challenger["market_observed_coverage"], control["market_observed_coverage"]]
        coverage_gap = (
            abs(float(coverages[0]) - float(coverages[1])) if None not in coverages else None
        )
        collision_rate = len(collision_events) / len(by_event) if by_event else 0.0
        planned_per_arm = int(experiment["planned_assignments_per_arm"])
        gates = {
            "fixed_assignments_per_arm": all(
                int(arm_stats[arm]["assigned"]) == planned_per_arm
                for arm in ("challenger", "control")
            ),
            "all_assignments_terminal": all(
                int(arm_stats[arm]["terminal_assignments"]) == planned_per_arm
                for arm in ("challenger", "control")
            ),
            "calendar_days_per_arm": all(
                int(arm_stats[arm]["calendar_days"]) >= int(experiment["min_calendar_days"])
                for arm in ("challenger", "control")
            ),
            "zero_yield_exposures_per_arm": all(
                int(arm_stats[arm]["zero_yield_completed_exposures"])
                >= int(config.get("minimum_zero_yield_per_arm", 10))
                for arm in ("challenger", "control")
            ),
            "terminal_failure_balance": failure_gap is not None and failure_gap <= float(
                config.get("maximum_terminal_failure_gap", 0.10)
            ),
            "cross_arm_collision_rate": collision_rate <= float(
                config.get("maximum_cross_arm_collision_rate", 0.10)
            ),
            "productive_rate_effect": productive_lower is not None and productive_lower >= float(
                config.get("minimum_productive_rate_difference_lower_bound", 0.05)
            ),
            "unique_events_per_arm": all(
                int(arm_stats[arm]["unique_decision_eligible_events"])
                >= int(config.get("minimum_unique_events_per_arm", 20))
                for arm in ("challenger", "control")
            ),
            "all_market_outcomes_terminal": all(
                int(arm_stats[arm]["market_outcomes_pending"]) == 0
                for arm in ("challenger", "control")
            ),
            "market_coverage_per_arm": all(
                arm_stats[arm]["market_observed_coverage"] is not None
                and float(arm_stats[arm]["market_observed_coverage"])
                >= float(config.get("minimum_observed_coverage", 0.80))
                for arm in ("challenger", "control")
            ),
            "market_coverage_balance": coverage_gap is not None and coverage_gap <= float(
                config.get("maximum_coverage_gap", 0.10)
            ),
            "market_noninferiority": market_lower is not None and market_lower > float(
                config.get("minimum_positive_rate_difference_lower_bound", -0.10)
            ),
        }
        stage1_ready = all(gates.values())
        latest_type = str(latest_event["event_type"] if latest_event is not None else "registered")
        status = (
            "stage1_ready_for_holdout" if latest_type == "activated" and stage1_ready
            else "collecting_stage1" if latest_type == "activated"
            else latest_type
        )
        return {
            "version": str(experiment["version"]),
            "status": status,
            "experiment": {
                "id": experiment_id,
                "target_kind": str(experiment["target_kind"]),
                "hypothesis": str(experiment["hypothesis"]),
                "challenger": {
                    "platform": str(experiment["challenger_platform"]),
                    "entity_id": str(experiment["challenger_entity_id"]),
                },
                "control": {
                    "platform": str(experiment["control_platform"]),
                    "entity_id": str(experiment["control_entity_id"]),
                },
                "registered_at": str(experiment["registered_at"]),
                "latest_event": latest_type,
                "latest_event_at": str(latest_event["effective_at"]) if latest_event is not None else None,
                "assignment": str(config.get("assignment") or ""),
                "planned_assignments_per_arm": planned_per_arm,
                "primary_population": str(config.get("primary_population") or ""),
            },
            "arms": arm_stats,
            "inference": {
                "productive_rate_difference_two_sided_95_lower": round(productive_lower, 6)
                if productive_lower is not None else None,
                "market_positive_rate_difference_two_sided_95_lower": round(market_lower, 6)
                if market_lower is not None else None,
                "terminal_failure_rate_gap": round(failure_gap, 6) if failure_gap is not None else None,
                "market_coverage_gap": round(coverage_gap, 6) if coverage_gap is not None else None,
                "cross_arm_collision_events": len(collision_events),
                "linked_events": len(by_event),
                "cross_arm_collision_rate": round(collision_rate, 6),
            },
            "gates": gates,
            "stage1_ready": stage1_ready,
            "automatic_promotion": False,
            "holdout_required": True,
            "actual_multiplier": 1.0,
            "affects": "one_normal_trend_scout_watch_slot_only",
            "never_affects": list(config.get("never_affects") or []),
            "as_of": iso(),
        }

    @staticmethod
    def trend_lane_exposure_summary_from_connection(
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('trend_lane_runs','trend_lane_run_lanes')"
            )
        }
        if tables != {"trend_lane_runs", "trend_lane_run_lanes"}:
            return {"status": "not_observed", "items": [], "summary": {"runs": 0, "completed_runs": 0}}
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = list(
            connection.execute(
                """
                SELECT r.run_id,r.taxonomy_version,r.prompt_version,r.selection_mode,r.surge,r.status,
                       r.started_at,r.finished_at,r.model,r.reasoning_effort,r.max_web_searches,
                       l.lane_id,l.lane_prompt,l.event_topics_json,l.selection_role,
                       l.attention_multiplier,l.scheduled_coverage_fraction,
                       l.accepted_event_count,l.observation_count
                FROM trend_lane_runs r
                JOIN trend_lane_run_lanes l ON l.run_id=r.run_id
                WHERE r.started_at>=?
                ORDER BY r.started_at,r.run_id,l.lane_id
                """,
                (start,),
            )
        )
        lane_metrics: dict[str, dict[str, Any]] = {}
        run_ids: set[str] = set()
        completed_run_ids: set[str] = set()
        for row in rows:
            run_id = str(row["run_id"])
            run_ids.add(run_id)
            if str(row["status"]) == "completed":
                completed_run_ids.add(run_id)
            lane_id = str(row["lane_id"])
            metric = lane_metrics.setdefault(
                lane_id,
                {
                    "lane_id": lane_id,
                    "lane_prompt": str(row["lane_prompt"]),
                    "event_topics": json.loads(str(row["event_topics_json"] or "[]")),
                    "exposures": 0,
                    "completed_exposures": 0,
                    "error_exposures": 0,
                    "zero_yield_completed_exposures": 0,
                    "accepted_events": 0,
                    "observations": 0,
                    "run_days": set(),
                    "last_selected_at": None,
                    "selection_role": str(row["selection_role"]),
                    "last_attention_multiplier": float(row["attention_multiplier"] or 1.0),
                    "taxonomy_version": str(row["taxonomy_version"]),
                    "prompt_version": str(row["prompt_version"]),
                },
            )
            metric["exposures"] += 1
            if str(row["status"]) == "completed":
                metric["completed_exposures"] += 1
                metric["run_days"].add(str(row["started_at"])[:10])
                if int(row["accepted_event_count"] or 0) == 0:
                    metric["zero_yield_completed_exposures"] += 1
            elif str(row["status"]) == "agent_error":
                metric["error_exposures"] += 1
            metric["accepted_events"] += int(row["accepted_event_count"] or 0)
            metric["observations"] += int(row["observation_count"] or 0)
            metric["last_selected_at"] = max(str(metric["last_selected_at"] or ""), str(row["started_at"]))
            metric["selection_role"] = str(row["selection_role"])
            metric["last_attention_multiplier"] = float(row["attention_multiplier"] or 1.0)
            metric["taxonomy_version"] = str(row["taxonomy_version"])
            metric["prompt_version"] = str(row["prompt_version"])
        items = []
        for metric in lane_metrics.values():
            completed = int(metric["completed_exposures"])
            metric["accepted_events_per_completed_run"] = (
                round(int(metric["accepted_events"]) / completed, 4) if completed else None
            )
            metric["run_day_count"] = len(metric.pop("run_days"))
            metric["zero_yield_rate"] = (
                round(int(metric["zero_yield_completed_exposures"]) / completed, 4)
                if completed else None
            )
            items.append(metric)
        items.sort(key=lambda item: (-int(item["exposures"]), str(item["lane_id"])))
        return {
            "status": "observed" if rows else "not_observed",
            "items": items,
            "summary": {
                "runs": len(run_ids),
                "completed_runs": len(completed_run_ids),
                "lane_exposures": len(rows),
                "accepted_events": sum(int(item["accepted_events"]) for item in items),
                "observations": sum(int(item["observations"]) for item in items),
            },
            "lookback_days": int(lookback_days),
        }

    @classmethod
    def build_trend_attention_policy(
        cls,
        lanes: Iterable[Mapping[str, Any]],
        *,
        exposure: Mapping[str, Any],
        shadow: Mapping[str, Any],
        paper: Mapping[str, Any],
    ) -> dict[str, Any]:
        exposure_items = {
            str(item.get("lane_id") or ""): item
            for item in exposure.get("items", []) if isinstance(item, Mapping)
        }
        shadow_items = {
            str(item.get("value") or ""): item
            for item in shadow.get("items", [])
            if isinstance(item, Mapping)
            and item.get("dimension") == "trend_lane"
            and int(item.get("horizon_minutes") or 0) == 60
        }
        paper_items = {
            str(item.get("value") or ""): item
            for item in paper.get("items", [])
            if isinstance(item, Mapping) and item.get("dimension") == "trend_lane"
        }
        exposure_summary = dict(exposure.get("summary") or {})
        global_completed = sum(
            int(item.get("completed_exposures") or 0) for item in exposure_items.values()
        )
        global_events = int(exposure_summary.get("accepted_events") or 0)
        global_rate = global_events / global_completed if global_completed else 0.0
        items = []
        for lane in lanes:
            lane_id = str(lane.get("id") or "")
            exposure_item = dict(exposure_items.get(lane_id) or {})
            completed = int(exposure_item.get("completed_exposures") or 0)
            zero_yield = int(exposure_item.get("zero_yield_completed_exposures") or 0)
            exposure_mature = (
                completed >= 20
                and int(exposure_item.get("run_day_count") or 0) >= 10
                and zero_yield >= 5
                and global_events >= 20
            )
            discovery_multiplier = 1.0
            if exposure_mature and global_rate > 0:
                prior = 10.0
                shrunk_rate = (
                    int(exposure_item.get("accepted_events") or 0) + prior * global_rate
                ) / (completed + prior)
                discovery_multiplier = max(
                    0.85, min(1.15, 1.0 + (shrunk_rate / global_rate - 1.0) * 0.15),
                )
            shadow_item = dict(shadow_items.get(lane_id) or {})
            shadow_score = shadow_item.get("shadow_descriptive_score")
            market_mature = (
                shadow_item.get("shadow_review_eligible") is True and shadow_score is not None
            )
            market_multiplier = (
                max(0.90, min(1.10, 1.0 + float(shadow_score) * 0.5))
                if market_mature else 1.0
            )
            paper_item = dict(paper_items.get(lane_id) or {})
            paper_mean = paper_item.get("paper_mean_net_return")
            paper_multiplier = (
                max(0.90, min(1.10, 1.0 + float(paper_mean) * 0.25))
                if paper_mean is not None
                and int(paper_item.get("distinct_closed_paper_outcomes") or 0) >= 30
                and int(paper_item.get("event_day_count") or 0) >= 15
                and float(paper_item.get("weighted_losing_paper_outcomes") or 0) >= 8
                else 1.0
            )
            attention_mature = exposure_mature and market_mature
            recommended = 1.0
            if attention_mature:
                recommended = max(
                    0.80,
                    min(1.20, discovery_multiplier * market_multiplier * (paper_multiplier ** 0.5)),
                )
            items.append(
                {
                    "lane_id": lane_id,
                    "lane_prompt": str(lane.get("prompt") or ""),
                    "event_topics": list(lane.get("event_topics") or []),
                    **exposure_item,
                    "exposure_mature": exposure_mature,
                    "market_followup_mature": market_mature,
                    "market_distinct_event_count": int(shadow_item.get("distinct_event_count") or 0),
                    "market_event_day_count": int(shadow_item.get("event_day_count") or 0),
                    "market_weighted_negative_outcomes": float(
                        shadow_item.get("weighted_negative_outcomes") or 0
                    ),
                    "market_mean_raw_return": shadow_item.get("mean_raw_return"),
                    "market_descriptive_score": shadow_score,
                    "paper_distinct_closed_event_count": int(
                        paper_item.get("distinct_closed_paper_outcomes") or 0
                    ),
                    "paper_mean_net_return": paper_mean,
                    "discovery_multiplier": round(discovery_multiplier, 4),
                    "market_multiplier": round(market_multiplier, 4),
                    "paper_multiplier": round(paper_multiplier, 4),
                    "recommended_multiplier": round(recommended, 4),
                    "attention_mature": attention_mature,
                }
            )
        mature_count = sum(1 for item in items if item["attention_mature"])
        schedule_active = False
        for item in items:
            item["schedule_active"] = schedule_active and bool(item["attention_mature"])
            item["applied_schedule_multiplier"] = (
                item["recommended_multiplier"] if item["schedule_active"] else 1.0
            )
            item["state"] = (
                "collecting_lane_exposure" if not item["exposure_mature"]
                else "collecting_market_followup" if not item["market_followup_mature"]
                else "mature_waiting_for_randomized_experiment"
            )
        items.sort(
            key=lambda item: (
                not bool(item["schedule_active"]), -float(item["recommended_multiplier"]),
                -int(item.get("completed_exposures") or 0), str(item["lane_id"]),
            )
        )
        return {
            "version": cls.TREND_ATTENTION_POLICY_VERSION,
            "status": (
                "mature_waiting_for_randomized_experiment" if mature_count
                else "collecting_evidence" if items else "not_configured"
            ),
            "items": items,
            "summary": {
                **exposure_summary,
                "exposure_mature_lanes": sum(1 for item in items if item["exposure_mature"]),
                "market_mature_lanes": sum(1 for item in items if item["market_followup_mature"]),
                "attention_mature_lanes": mature_count,
                "schedule_active_lanes": sum(1 for item in items if item["schedule_active"]),
                "schedule_activation_available": schedule_active,
                "actual_schedule_changed_by_learning": False,
            },
            "activation_policy": {
                "minimum_completed_exposures": 20,
                "minimum_run_days": 10,
                "minimum_zero_yield_exposures": 5,
                "minimum_global_accepted_events": 20,
                "requires_60m_shadow_followup_review_eligible": True,
                "minimum_comparable_mature_lanes": 2,
                "requires_preregistered_randomized_attention_experiment": True,
                "observational_scores_are_descriptive_only": True,
                "minimum_applied_multiplier": 1.0,
                "maximum_applied_multiplier": 1.0,
                "future_experiment_multiplier_cap": 1.10,
                "minimum_round_robin_exploration_lanes_per_run": 1,
                "surge_always_full_coverage": True,
                "paper_outcome_role": "optional_secondary_validation",
                "affects": "trend_scout_lane_allocation_only",
                "never_affects": [
                    "evidence_weight", "candidate_ranking", "decision_eligibility",
                    "risk", "position_size", "exits", "live_trading",
                ],
            },
        }

    def trend_attention_policy(
        self,
        lanes: Iterable[Mapping[str, Any]],
        *,
        lookback_days: int = 90,
        source_learning_kwargs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            exposure = self.trend_lane_exposure_summary_from_connection(
                self.db, lookback_days=lookback_days,
            )
            shadow = self.shadow_event_learning_summary_from_connection(
                self.db, lookback_days=lookback_days,
            )
            paper = self.source_learning_summary_from_connection(
                self.db, lookback_days=lookback_days, **dict(source_learning_kwargs or {}),
            )
            return self.build_trend_attention_policy(
                lanes, exposure=exposure, shadow=shadow, paper=paper,
            )

    @staticmethod
    def watch_account_exposure_summary_from_connection(
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('trend_lane_runs','trend_watch_account_exposures',"
                "'browser_watch_account_exposures')"
            )
        }
        policy = {
            "minimum_completed_exposures": 20,
            "minimum_run_days": 10,
            "minimum_zero_yield_exposures": 5,
            "minimum_global_exact_source_hits": 20,
            "maximum_review_multiplier": 1.15,
            "minimum_review_multiplier": 0.85,
            "affects": "review_only_no_schedule_or_trading_effect",
        }
        if not {"trend_lane_runs", "trend_watch_account_exposures"}.issubset(tables):
            return {
                "status": "not_observed", "items": [],
                "summary": {"runs": 0, "completed_runs": 0, "account_exposures": 0},
                "review_policy": policy,
            }
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT r.run_id,r.started_at,r.status,a.platform,a.handle,a.handle_key,a.entity_id,
                       a.configured_priority,a.watch_cadence,a.selection_role,a.learning_basis,
                       a.learning_multiplier,a.exact_source_hits,a.accepted_event_count,a.observation_count,
                       r.started_at AS last_observed_at,'trend_agent' AS exposure_origin
                FROM trend_lane_runs r
                JOIN trend_watch_account_exposures a ON a.run_id=r.run_id
                WHERE r.started_at>=?
                ORDER BY r.started_at,r.run_id,a.platform,a.handle_key
                """,
                (start,),
            )
        ]
        if "browser_watch_account_exposures" in tables:
            rows.extend(
                dict(row)
                for row in connection.execute(
                    """
                    SELECT exposure_id AS run_id,window_started_at AS started_at,status,
                           platform,handle,handle_key,entity_id,configured_priority,watch_cadence,
                           'browser_page' AS selection_role,'browser_heartbeat' AS learning_basis,
                           1.0 AS learning_multiplier,exact_source_hits,accepted_event_count,
                           observation_count,last_heartbeat_at AS last_observed_at,
                           'browser_bridge' AS exposure_origin
                    FROM browser_watch_account_exposures
                    WHERE window_started_at>=?
                    ORDER BY window_started_at,exposure_id
                    """,
                    (start,),
                )
            )
        rows.sort(
            key=lambda row: (
                str(row["started_at"]), str(row["run_id"]),
                str(row["platform"]), str(row["handle_key"]),
            )
        )
        metrics: dict[tuple[str, str], dict[str, Any]] = {}
        run_ids: set[str] = set()
        completed_run_ids: set[str] = set()
        browser_window_ids: set[str] = set()
        global_completed = 0
        global_hits = 0
        global_accepted_events = 0
        browser_completed = 0
        trend_account_exposures = 0
        trend_completed_account_exposures = 0
        for row in rows:
            run_id = str(row["run_id"])
            origin = str(row["exposure_origin"])
            if origin == "trend_agent":
                run_ids.add(run_id)
                trend_account_exposures += 1
            else:
                browser_window_ids.add(run_id)
            completed = str(row["status"]) == "completed"
            if completed:
                if origin == "trend_agent":
                    completed_run_ids.add(run_id)
                    trend_completed_account_exposures += 1
                else:
                    browser_completed += 1
                global_completed += 1
                global_hits += int(row["exact_source_hits"] or 0)
                global_accepted_events += int(row["accepted_event_count"] or 0)
            key = (str(row["platform"]), str(row["handle_key"]))
            metric = metrics.setdefault(
                key,
                {
                    "platform": str(row["platform"]), "handle": str(row["handle"]),
                    "entity_ids": set(), "exposures": 0,
                    "completed_exposures": 0, "error_exposures": 0,
                    "zero_yield_completed_exposures": 0, "exact_source_hits": 0,
                    "accepted_events": 0, "observations": 0, "run_days": set(),
                    "last_selected_at": None, "configured_priority": int(row["configured_priority"]),
                    "watch_cadence": str(row["watch_cadence"]),
                    "last_selection_role": str(row["selection_role"]),
                    "last_learning_basis": str(row["learning_basis"]),
                    "last_learning_multiplier": float(row["learning_multiplier"]),
                    "trend_agent_exposures": 0, "browser_bridge_exposures": 0,
                    "last_browser_heartbeat_at": None,
                },
            )
            if row["entity_id"]:
                metric["entity_ids"].add(str(row["entity_id"]).strip().lower())
            metric["exposures"] += 1
            if origin == "browser_bridge":
                metric["browser_bridge_exposures"] += 1
                metric["last_browser_heartbeat_at"] = max(
                    str(metric["last_browser_heartbeat_at"] or ""), str(row["last_observed_at"])
                )
            else:
                metric["trend_agent_exposures"] += 1
            if completed:
                metric["completed_exposures"] += 1
                metric["run_days"].add(str(row["started_at"])[:10])
                if int(row["exact_source_hits"] or 0) == 0:
                    metric["zero_yield_completed_exposures"] += 1
            elif str(row["status"]) in {"agent_error", "access_error"}:
                metric["error_exposures"] += 1
            metric["exact_source_hits"] += int(row["exact_source_hits"] or 0)
            metric["accepted_events"] += int(row["accepted_event_count"] or 0)
            metric["observations"] += int(row["observation_count"] or 0)
            metric["last_selected_at"] = max(
                str(metric["last_selected_at"] or ""), str(row["started_at"])
            )
            metric["last_selection_role"] = str(row["selection_role"])
            metric["last_learning_basis"] = str(row["learning_basis"])
            metric["last_learning_multiplier"] = float(row["learning_multiplier"])
        global_rate = global_hits / global_completed if global_completed else 0.0
        items = []
        for metric in metrics.values():
            completed = int(metric["completed_exposures"])
            raw_rate = int(metric["exact_source_hits"]) / completed if completed else None
            review_eligible = (
                completed >= policy["minimum_completed_exposures"]
                and len(metric["run_days"]) >= policy["minimum_run_days"]
                and int(metric["zero_yield_completed_exposures"])
                >= policy["minimum_zero_yield_exposures"]
                and global_hits >= policy["minimum_global_exact_source_hits"]
            )
            review_multiplier = 1.0
            if review_eligible and global_rate > 0:
                prior = 10.0
                shrunk_rate = (int(metric["exact_source_hits"]) + prior * global_rate) / (completed + prior)
                lift = shrunk_rate / global_rate
                review_multiplier = max(
                    policy["minimum_review_multiplier"],
                    min(policy["maximum_review_multiplier"], 1.0 + (lift - 1.0) * 0.15),
                )
            items.append(
                {
                    **{
                        key: value for key, value in metric.items()
                        if key not in {"run_days", "entity_ids"}
                    },
                    "entity_id": (
                        next(iter(metric["entity_ids"])) if len(metric["entity_ids"]) == 1 else ""
                    ),
                    "entity_mapping_conflict": len(metric["entity_ids"]) > 1,
                    "run_day_count": len(metric["run_days"]),
                    "exact_source_hits_per_completed_exposure": round(raw_rate, 4)
                    if raw_rate is not None else None,
                    "zero_yield_rate": round(
                        int(metric["zero_yield_completed_exposures"]) / completed, 4
                    ) if completed else None,
                    "discovery_review_eligible": review_eligible,
                    "discovery_review_multiplier": round(review_multiplier, 4),
                    "rotation_active": False,
                }
            )
        items.sort(
            key=lambda item: (
                not bool(item["discovery_review_eligible"]),
                -float(item["discovery_review_multiplier"]),
                -int(item["completed_exposures"]),
                str(item["platform"]), str(item["handle"]).casefold(),
            )
        )
        return {
            "status": (
                "shadow_review_available"
                if any(item["discovery_review_eligible"] for item in items)
                else "collecting_exposure" if rows else "not_observed"
            ),
            "items": items,
            "summary": {
                "runs": len(run_ids), "completed_runs": len(completed_run_ids),
                "trend_agent_account_exposures": trend_account_exposures,
                "trend_agent_completed_account_exposures": trend_completed_account_exposures,
                "browser_exposure_windows": len(browser_window_ids),
                "browser_completed_account_exposures": browser_completed,
                "account_exposures": len(rows), "completed_account_exposures": global_completed,
                "exact_source_hits": global_hits,
                "accepted_events": global_accepted_events,
                "global_exact_source_hits_per_completed_exposure": round(global_rate, 4)
                if global_completed else None,
                "review_eligible_accounts": sum(
                    1 for item in items if item["discovery_review_eligible"]
                ),
            },
            "review_policy": policy,
            "lookback_days": int(lookback_days),
        }

    @classmethod
    def build_watch_attention_policy(
        cls,
        accounts: Iterable[Mapping[str, Any]],
        *,
        exposure: Mapping[str, Any],
        shadow: Mapping[str, Any],
        paper: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Combine discovery exposure and forward market follow-up for watch rotation only."""
        exposure_items = {
            (str(item.get("platform") or ""), str(item.get("handle") or "").casefold()): item
            for item in exposure.get("items", [])
            if isinstance(item, Mapping)
        }
        shadow_items = {
            (str(item.get("dimension") or ""), str(item.get("value") or "")): item
            for item in shadow.get("items", [])
            if isinstance(item, Mapping) and int(item.get("horizon_minutes") or 0) == 60
        }
        paper_items = {
            (str(item.get("dimension") or ""), str(item.get("value") or "")): item
            for item in paper.get("items", [])
            if isinstance(item, Mapping) and item.get("rotation_active") is True
        }
        items = []
        for account in accounts:
            if account.get("enabled", True) is not True:
                continue
            platform = str(account.get("platform") or "").strip().lower()
            handle = str(account.get("handle") or "").strip()
            if not platform or not handle:
                continue
            exposure_item = dict(exposure_items.get((platform, handle.casefold())) or {})
            configured_entity_id = str(account.get("entity_id") or "").strip().lower()
            observed_entity_id = str(exposure_item.get("entity_id") or "").strip().lower()
            entity_mapping_conflict = bool(exposure_item.get("entity_mapping_conflict")) or bool(
                configured_entity_id and observed_entity_id
                and configured_entity_id != observed_entity_id
            )
            entity_id = "" if entity_mapping_conflict else configured_entity_id or observed_entity_id
            entity_mapping_source = (
                "conflict" if entity_mapping_conflict else
                "configured" if configured_entity_id else
                "exact_exposure" if observed_entity_id else None
            )
            exposure_mature = exposure_item.get("discovery_review_eligible") is True
            shadow_item: dict[str, Any] = {}
            market_basis = ""
            candidate = shadow_items.get(("entity", entity_id)) if entity_id else None
            if candidate and candidate.get("shadow_review_eligible") is True:
                shadow_item = dict(candidate)
                market_basis = "entity"
            shadow_score = shadow_item.get("shadow_descriptive_score")
            market_mature = bool(shadow_item) and shadow_score is not None
            paper_item: dict[str, Any] = {}
            paper_basis = ""
            candidate = paper_items.get(("entity", entity_id)) if entity_id else None
            if candidate:
                paper_item = dict(candidate)
                paper_basis = "entity"
            discovery_multiplier = float(exposure_item.get("discovery_review_multiplier") or 1.0)
            market_multiplier = (
                max(0.90, min(1.10, 1.0 + float(shadow_score) * 0.5))
                if market_mature else 1.0
            )
            paper_multiplier = float(paper_item.get("rotation_multiplier") or 1.0)
            evidence_mature = exposure_mature and market_mature
            recommended = 1.0
            if evidence_mature:
                recommended = max(
                    0.80,
                    min(1.20, discovery_multiplier * market_multiplier * (paper_multiplier ** 0.5)),
                )
            critical = str(account.get("watch_cadence") or "normal").lower() == "critical"
            rotation_active = False
            if entity_mapping_conflict:
                state = "entity_mapping_conflict"
            elif not entity_id:
                state = "missing_exact_entity_mapping"
            elif not exposure_mature:
                state = "collecting_account_exposure"
            elif not market_mature:
                state = "collecting_market_followup"
            elif critical:
                state = "mature_review_critical_fixed"
            else:
                state = "mature_review_waiting_randomized_experiment"
            items.append(
                {
                    "platform": platform,
                    "handle": handle,
                    "configured_priority": int(account.get("priority") or 3),
                    "watch_cadence": "critical" if critical else "normal",
                    **exposure_item,
                    "entity_id": entity_id,
                    "entity_mapping_source": entity_mapping_source,
                    "market_basis": market_basis or None,
                    "market_distinct_event_count": int(shadow_item.get("distinct_event_count") or 0),
                    "market_event_day_count": int(shadow_item.get("event_day_count") or 0),
                    "market_weighted_negative_outcomes": float(
                        shadow_item.get("weighted_negative_outcomes") or 0
                    ),
                    "market_mean_raw_return": shadow_item.get("mean_raw_return"),
                    "market_descriptive_score": shadow_score,
                    "paper_basis": paper_basis or None,
                    "paper_distinct_closed_outcomes": int(
                        paper_item.get("distinct_closed_paper_outcomes") or 0
                    ),
                    "paper_mean_net_return": paper_item.get("paper_mean_net_return"),
                    "discovery_multiplier": round(discovery_multiplier, 4),
                    "market_multiplier": round(market_multiplier, 4),
                    "paper_multiplier": round(paper_multiplier, 4),
                    "recommended_multiplier": round(recommended, 4),
                    "applied_rotation_multiplier": 1.0,
                    "exposure_mature": exposure_mature,
                    "market_followup_mature": market_mature,
                    "attention_active": evidence_mature,
                    "rotation_active": rotation_active,
                    "state": state,
                }
            )
        items.sort(
            key=lambda item: (
                not bool(item["rotation_active"]), not bool(item["attention_active"]),
                str(item["watch_cadence"]) != "critical", -int(item["configured_priority"]),
                -float(item["recommended_multiplier"]), -int(item.get("completed_exposures") or 0),
                str(item["platform"]), str(item["handle"]).casefold(),
            )
        )
        return {
            "version": cls.WATCH_ATTENTION_POLICY_VERSION,
            "status": (
                "mature_review_only" if any(item["attention_active"] for item in items)
                else "collecting_evidence" if items else "not_configured"
            ),
            "items": items,
            "summary": {
                "configured_accounts": len(items),
                "exposure_mature_accounts": sum(1 for item in items if item["exposure_mature"]),
                "market_mature_accounts": sum(1 for item in items if item["market_followup_mature"]),
                "attention_mature_accounts": sum(1 for item in items if item["attention_active"]),
                "rotation_active_accounts": sum(1 for item in items if item["rotation_active"]),
                "rotation_activation_available": any(item["rotation_active"] for item in items),
                "actual_rotation_changed_by_learning": False,
            },
            "activation_policy": {
                "requires_account_exposure_review_eligible": True,
                "requires_60m_shadow_followup_review_eligible": True,
                "requires_exact_entity_market_evidence": True,
                "platform_fallback_for_accounts": False,
                "paper_outcome_role": "optional_secondary_validation",
                "requires_preregistered_randomized_attention_experiment": True,
                "observational_scores_are_descriptive_only": True,
                "minimum_applied_multiplier": 1.0,
                "maximum_applied_multiplier": 1.0,
                "future_experiment_multiplier_cap": 1.10,
                "critical_accounts_remain_fixed": True,
                "minimum_exploration_fraction": 0.40,
                "affects": "agent_watch_rotation_only",
                "never_affects": [
                    "evidence_weight", "candidate_ranking", "decision_eligibility",
                    "risk", "position_size", "exits", "live_trading",
                ],
            },
        }

    def watch_attention_policy(
        self,
        accounts: Iterable[Mapping[str, Any]],
        *,
        lookback_days: int = 90,
        source_learning_kwargs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            exposure = self.watch_account_exposure_summary_from_connection(
                self.db, lookback_days=lookback_days,
            )
            shadow = self.shadow_event_learning_summary_from_connection(
                self.db, lookback_days=lookback_days,
            )
            paper = self.source_learning_summary_from_connection(
                self.db, lookback_days=lookback_days, **dict(source_learning_kwargs or {}),
            )
            return self.build_watch_attention_policy(
                accounts, exposure=exposure, shadow=shadow, paper=paper,
            )

    def agent_attempts(self, *, limit: int = 100) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                "SELECT * FROM agent_attempts ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            )
        )
