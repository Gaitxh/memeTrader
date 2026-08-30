from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

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
    WATCH_ATTENTION_POLICY_VERSION = "watch-attention/v2-exact-entity"
    TREND_ATTENTION_POLICY_VERSION = "trend-attention/v1"
    PAPER_SOURCE_ATTRIBUTION_VERSION = "paper-source-attribution/v2-decision-cohort"
    SOURCE_POLL_EXPOSURE_VERSION = "source-poll-exposure/v1"
    TOKEN_DISCOVERY_EXPOSURE_VERSION = "token-discovery-exposure/v1"

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
                    error_type TEXT NOT NULL DEFAULT ''
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
    def _fingerprint(obs: Observation) -> str:
        if obs.source_item_id:
            stable = f"{obs.source.strip().lower()}\n{obs.source_item_id.strip()}"
            return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()
        stable = "\n".join(
            [obs.source.strip().lower(), obs.url.strip(), obs.author.strip().lower(), obs.title.strip(), obs.text.strip()]
        )
        return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()

    def add_observation(self, obs: Observation) -> tuple[int, bool]:
        fp = self._fingerprint(obs)
        with self._lock, self.db:
            try:
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
                        self._json(obs.raw),
                    ),
                )
                return int(cur.lastrowid), True
            except sqlite3.IntegrityError:
                row = self.db.execute("SELECT id FROM observations WHERE fingerprint=?", (fp,)).fetchone()
                return int(row["id"]), False

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

    def update_event(self, event_id: int, *, title: str, aliases: Iterable[str], attention: float, seen_at=None) -> None:
        with self._lock, self.db:
            self.db.execute(
                "UPDATE events SET title=?,aliases_json=?,attention=?,last_seen_at=? WHERE id=?",
                (title, self._json(sorted(set(aliases))), attention, iso(seen_at or utcnow()), event_id),
            )

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
            self.db.execute(
                """
                INSERT INTO token_snapshots(
                    token_id,observed_at,ingested_at,provider,price_usd,liquidity_usd,market_cap_usd,volume_5m_usd,
                    buys_5m,sells_5m,buyers_5m,holders,buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    token_id, iso(snap.observed_at), iso(ingested_at), snap.provider,
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
                    started_at,status
                ) VALUES(?,?,?,?,?,?,?,'running')
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
        schedule_active = mature_count >= 2
        for item in items:
            item["schedule_active"] = schedule_active and bool(item["attention_mature"])
            item["applied_schedule_multiplier"] = (
                item["recommended_multiplier"] if item["schedule_active"] else 1.0
            )
            item["state"] = (
                "collecting_lane_exposure" if not item["exposure_mature"]
                else "collecting_market_followup" if not item["market_followup_mature"]
                else "active_lane_schedule" if schedule_active
                else "mature_waiting_for_comparison"
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
                "active_lane_schedule" if schedule_active
                else "mature_waiting_for_comparison" if mature_count
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
                "minimum_applied_multiplier": 0.80,
                "maximum_applied_multiplier": 1.20,
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
            rotation_active = evidence_mature and not critical
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
                state = "active_watch_rotation"
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
                    "applied_rotation_multiplier": round(recommended if rotation_active else 1.0, 4),
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
                "active_watch_rotation" if any(item["rotation_active"] for item in items)
                else "mature_review_only" if any(item["attention_active"] for item in items)
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
                "minimum_applied_multiplier": 0.80,
                "maximum_applied_multiplier": 1.20,
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
