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
    SHADOW_EVENT_COHORT_VERSION = "shadow-event-followup/v1"
    SHADOW_EVENT_HORIZONS_MINUTES = (15, 60, 240)
    WATCH_ATTENTION_POLICY_VERSION = "watch-attention/v1"
    TREND_ATTENTION_POLICY_VERSION = "trend-attention/v1"

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
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    gross_usd REAL NOT NULL,
                    fee_usd REAL NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS trades_created_idx ON trades(created_at);

                CREATE TABLE IF NOT EXISTS source_utility_outcomes (
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
                CREATE INDEX IF NOT EXISTS source_utility_outcomes_dimension_idx
                    ON source_utility_outcomes(dimension,value,closed_at DESC);
                CREATE INDEX IF NOT EXISTS source_utility_outcomes_event_idx
                    ON source_utility_outcomes(event_id,token_id);

                CREATE TABLE IF NOT EXISTS source_health (
                    source TEXT PRIMARY KEY,
                    last_ok_at TEXT,
                    last_item_at TEXT,
                    last_error_at TEXT,
                    last_error TEXT NOT NULL DEFAULT ''
                );
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

    def recent_observations(self, minutes: int = 120, limit: int = 1000) -> list[sqlite3.Row]:
        since = iso(utcnow() - timedelta(minutes=minutes))
        return list(
            self.db.execute(
                "SELECT * FROM observations WHERE observed_at>=? ORDER BY observed_at DESC LIMIT ?",
                (since, limit),
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
                    iso(parse_time(assessed_at or utcnow())), iso(parse_time(snapshot_observed_at)),
                    float(momentum_score), self._bounded_json(dict(assessment)),
                    self._bounded_json(dict(agent_metadata or {})),
                    self._bounded_json([dict(item) for item in audit]),
                ),
            )
            return int(cursor.lastrowid)

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
        with self._lock, self.db:
            self.db.execute(
                """
                INSERT INTO token_snapshots(
                    token_id,observed_at,provider,price_usd,liquidity_usd,market_cap_usd,volume_5m_usd,
                    buys_5m,sells_5m,buyers_5m,holders,buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    token_id, iso(snap.observed_at), snap.provider, snap.price_usd, snap.liquidity_usd,
                    snap.market_cap_usd, snap.volume_5m_usd, snap.buys_5m, snap.sells_5m,
                    snap.buyers_5m, snap.holders, snap.buy_tax_pct, snap.sell_tax_pct,
                    None if snap.honeypot is None else int(snap.honeypot),
                    None if snap.sellable is None else int(snap.sellable), self._json(snap.raw),
                ),
            )

    def latest_snapshot(self, token_id: str) -> TokenSnapshot | None:
        row = self.db.execute(
            "SELECT * FROM token_snapshots WHERE token_id=? ORDER BY observed_at DESC,id DESC LIMIT 1", (token_id,)
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
            observed_at=parse_time(row["observed_at"]), provider=row["provider"], raw=json.loads(row["raw_json"]),
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

    def account(self) -> dict[str, float]:
        row = self.db.execute("SELECT cash_usd,realized_pnl_usd FROM paper_account WHERE singleton=1").fetchone()
        return {"cash_usd": float(row["cash_usd"]), "realized_pnl_usd": float(row["realized_pnl_usd"])}

    def paper_buy(self, *, event_id: int, token: TokenCandidate, price: float, gross_usd: float, fee_bps: float, reason: str) -> Position:
        if price <= 0 or gross_usd <= 0:
            raise ValueError("price and gross_usd must be positive")
        fee = gross_usd * fee_bps / 10_000
        debit = gross_usd + fee
        quantity = gross_usd / price
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
                INSERT INTO positions(token_id,event_id,chain,address,symbol,quantity,entry_price,cost_usd,
                    remaining_cost_usd,highest_price,opened_at,realized_pnl_usd,take_profit_index)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)
                """,
                (token.token_id,event_id,token.chain,token.address,token.symbol,quantity,price,debit,debit,price,now,0.0),
            )
            self.db.execute(
                "INSERT INTO trades(token_id,event_id,side,quantity,price,gross_usd,fee_usd,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (token.token_id,event_id,"BUY",quantity,price,gross_usd,fee,reason,now),
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

    def paper_sell(self, token_id: str, *, price: float, fraction: float, fee_bps: float, reason: str) -> dict[str, float]:
        position = self.position(token_id)
        if not position:
            raise KeyError(token_id)
        fraction = min(1.0, max(0.0, fraction))
        if fraction <= 0 or price <= 0:
            raise ValueError("invalid sell")
        quantity = position.quantity * fraction
        gross = quantity * price
        fee = gross * fee_bps / 10_000
        net = gross - fee
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
                "INSERT INTO trades(token_id,event_id,side,quantity,price,gross_usd,fee_usd,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (token_id,position.event_id,"SELL",quantity,price,gross,fee,reason,now),
            )
            if remaining_quantity <= max(1e-12, position.quantity * 1e-8):
                self._record_source_utility_outcome_locked(position, closed_at=now)
                self.db.execute("DELETE FROM positions WHERE token_id=?", (token_id,))
            else:
                self.db.execute(
                    "UPDATE positions SET quantity=?,remaining_cost_usd=?,realized_pnl_usd=realized_pnl_usd+? WHERE token_id=?",
                    (remaining_quantity,remaining_cost,pnl,token_id),
                )
        return {"quantity": quantity, "gross_usd": gross, "fee_usd": fee, "net_usd": net, "pnl_usd": pnl}

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
        return list(dict.fromkeys(labels))

    def _record_source_utility_outcome_locked(self, position: Position, *, closed_at: str) -> None:
        trade_rows = list(
            self.db.execute(
                """
                SELECT side,gross_usd,fee_usd FROM trades
                WHERE event_id=? AND token_id=? AND created_at>=?
                ORDER BY id
                """,
                (position.event_id, position.token_id, iso(position.opened_at)),
            )
        )
        buy_cost = sum(
            float(row["gross_usd"] or 0) + float(row["fee_usd"] or 0)
            for row in trade_rows if str(row["side"]).upper() == "BUY"
        )
        sell_net = sum(
            float(row["gross_usd"] or 0) - float(row["fee_usd"] or 0)
            for row in trade_rows if str(row["side"]).upper() == "SELL"
        )
        if buy_cost <= 0 or sell_net < 0:
            return
        eligible = list(
            self.db.execute(
                """
                SELECT o.id,o.source,o.source_kind,o.observed_at,o.raw_json,e.topic AS event_topic
                FROM observations o
                JOIN event_observations eo ON eo.observation_id=o.id
                JOIN events e ON e.id=eo.event_id
                WHERE eo.event_id=? AND o.capture_phase='live'
                  AND o.role IN ('feature','confirmation')
                  AND o.observed_at<=? AND o.ingested_at<=?
                  AND (o.published_at IS NULL OR o.published_at<=?)
                ORDER BY o.observed_at,o.id
                """,
                (position.event_id, iso(position.opened_at), iso(position.opened_at), iso(position.opened_at)),
            )
        )
        if not eligible:
            return
        first_at = parse_time(eligible[0]["observed_at"])
        leads = [
            row for row in eligible
            if (parse_time(row["observed_at"]) - first_at).total_seconds() <= 60
        ]
        if not leads:
            return
        weight = 1.0 / len(leads)
        net_return = (sell_net - buy_cost) / buy_cost
        outcome_key = hashlib.sha256(
            f"{position.event_id}\n{position.token_id}\n{iso(position.opened_at)}".encode("utf-8")
        ).hexdigest()
        for row in leads:
            labels = self._source_learning_labels(row)
            platform = next((value for dimension, value in labels if dimension == "platform"), "")
            for dimension, value in labels:
                self.db.execute(
                    """
                    INSERT OR IGNORE INTO source_utility_outcomes(
                        outcome_key,event_id,token_id,source_observation_id,dimension,value,origin_platform,
                        attribution_weight,net_return,opened_at,closed_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        outcome_key, position.event_id, position.token_id, int(row["id"]), dimension, value,
                        platform, weight, net_return, iso(position.opened_at), closed_at,
                    ),
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
                    SELECT o.id,o.source,o.source_kind,o.role,o.observed_at,o.raw_json,eo.event_id,
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
                    "SELECT event_id,action FROM decisions WHERE created_at>=?",
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

        candidate_events = {
            int(row["event_id"]) for row in decision_rows
            if str(row["action"] or "").upper() == "CANDIDATE"
        }
        event_first_eligible: dict[int, Any] = {}
        records: list[tuple[sqlite3.Row, list[tuple[str, str]], int | None, bool]] = []
        for row in observation_rows:
            event_id = int(row["event_id"]) if row["event_id"] is not None else None
            eligible = str(row["role"] or "").lower() in {"feature", "confirmation"}
            observed = parse_time(row["observed_at"])
            if event_id is not None and eligible:
                previous = event_first_eligible.get(event_id)
                if previous is None or observed < previous:
                    event_first_eligible[event_id] = observed
            records.append((row, cls._source_learning_labels(row), event_id, eligible))

        diagnostic: dict[tuple[str, str], dict[str, Any]] = {}
        for row, labels, event_id, eligible in records:
            observed = parse_time(row["observed_at"])
            for key in labels:
                metric = diagnostic.setdefault(
                    key,
                    {
                        "observations": 0, "eligible_observations": 0, "context_observations": 0,
                        "events": set(), "early_events": set(), "candidate_events": set(), "last_observed_at": None,
                    },
                )
                metric["observations"] += 1
                metric["eligible_observations" if eligible else "context_observations"] += 1
                metric["last_observed_at"] = max(str(metric["last_observed_at"] or ""), str(row["observed_at"]))
                if event_id is not None:
                    metric["events"].add(event_id)
                    if event_id in candidate_events:
                        metric["candidate_events"].add(event_id)
                    first = event_first_eligible.get(event_id)
                    if eligible and first is not None and (observed - first).total_seconds() <= 60:
                        metric["early_events"].add(event_id)

        outcomes: dict[tuple[str, str], dict[str, Any]] = {}
        for row in outcome_rows:
            key = (str(row["dimension"]), str(row["value"]))
            metric = outcomes.setdefault(
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
        all_keys = set(diagnostic) | set(outcomes)
        for dimension, value in all_keys:
            observed = diagnostic.get((dimension, value), {})
            outcome = outcomes.get((dimension, value), {})
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
            items.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "observations": observations,
                    "eligible_observations": eligible_observations,
                    "context_observations": int(observed.get("context_observations", 0)),
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
                    "event_day_count": len(outcome.get("event_days", set())),
                    "platform_count": platform_count,
                    "confidence": round(confidence, 4),
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
                "closed_paper_outcomes": len({str(row["outcome_key"]) for row in outcome_rows}),
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
            },
            "as_of": iso(now),
        }

    def create_shadow_event_cohort(
        self,
        decision: CandidateDecision,
        *,
        decision_id: int,
        source_observation_ids: Iterable[int],
    ) -> int | None:
        """Freeze the first WAIT/CANDIDATE token follow-up for an event without changing strategy."""
        if str(decision.action).upper() not in {"WAIT", "CANDIDATE"} or not decision.token_id:
            return None
        cohort_key = hashlib.sha256(
            f"{self.SHADOW_EVENT_COHORT_VERSION}\n{int(decision.event_id)}".encode("utf-8")
        ).hexdigest()
        decision_at = iso(decision.created_at)
        observation_ids = sorted({int(value) for value in source_observation_ids if int(value) > 0})
        with self._lock, self.db:
            existing = self.db.execute(
                "SELECT id FROM shadow_event_cohorts WHERE cohort_key=?",
                (cohort_key,),
            ).fetchone()
            if existing:
                return int(existing["id"])
            snapshot = self.db.execute(
                """
                SELECT id,observed_at,price_usd FROM token_snapshots
                WHERE token_id=? AND observed_at<=? AND price_usd>0
                ORDER BY observed_at DESC,id DESC LIMIT 1
                """,
                (decision.token_id, decision_at),
            ).fetchone()
            if snapshot is None or not observation_ids:
                return None
            placeholders = ",".join("?" for _ in observation_ids)
            eligible = list(
                self.db.execute(
                    f"""
                    SELECT o.id,o.source,o.source_kind,o.observed_at,o.raw_json,e.topic AS event_topic
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
                return None
            first_at = parse_time(eligible[0]["observed_at"])
            leads = [
                row for row in eligible
                if (parse_time(row["observed_at"]) - first_at).total_seconds() <= 60
            ]
            if not leads:
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
                    int(decision_id), str(decision.action).upper(), decision_at, int(snapshot["id"]),
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
                        SELECT id,observed_at,price_usd FROM token_snapshots
                        WHERE token_id=? AND observed_at>=? AND observed_at<=? AND price_usd>0
                        ORDER BY observed_at,id LIMIT 1
                        """,
                        (str(cohort["token_id"]), iso(target), iso(upper)),
                    ).fetchone()
                    if snapshot is not None:
                        path = list(
                            self.db.execute(
                                """
                                SELECT price_usd FROM token_snapshots
                                WHERE token_id=? AND observed_at>=? AND observed_at<=? AND price_usd>0
                                ORDER BY observed_at,id
                                """,
                                (
                                    str(cohort["token_id"]), str(cohort["entry_snapshot_at"]),
                                    str(snapshot["observed_at"]),
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
    def shadow_event_learning_summary_from_connection(
        connection: sqlite3.Connection,
        *,
        lookback_days: int = 90,
    ) -> dict[str, Any]:
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
                "review_policy": policy,
            }
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        cohorts = list(
            connection.execute(
                "SELECT id,event_id,action,decision_at,status FROM shadow_event_cohorts WHERE decision_at>=?",
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
                    "wait_cohorts": set(), "candidate_cohorts": set(),
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
        return {
            "status": (
                "shadow_review_available"
                if any(item["shadow_review_eligible"] for item in items)
                else "collecting_followup"
                if cohorts
                else "not_observed"
            ),
            "version": Store.SHADOW_EVENT_COHORT_VERSION,
            "horizons_minutes": list(Store.SHADOW_EVENT_HORIZONS_MINUTES),
            "items": items[:500],
            "summary": {
                "cohorts": len(cohorts),
                "pending_cohorts": sum(str(row["status"]) == "pending" for row in cohorts),
                "complete_cohorts": sum(str(row["status"]) == "complete" for row in cohorts),
                "wait_cohorts": sum(str(row["action"]) == "WAIT" for row in cohorts),
                "candidate_cohorts": sum(str(row["action"]) == "CANDIDATE" for row in cohorts),
                "outcomes_by_horizon": outcome_counts,
                "review_eligible_labels": sum(item["shadow_review_eligible"] for item in items),
            },
            "review_policy": policy,
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
                "AND name IN ('trend_lane_runs','trend_watch_account_exposures')"
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
        if tables != {"trend_lane_runs", "trend_watch_account_exposures"}:
            return {
                "status": "not_observed", "items": [],
                "summary": {"runs": 0, "completed_runs": 0, "account_exposures": 0},
                "review_policy": policy,
            }
        start = iso(utcnow() - timedelta(days=max(1, min(3650, int(lookback_days)))))
        rows = list(
            connection.execute(
                """
                SELECT r.run_id,r.started_at,r.status,a.platform,a.handle,a.handle_key,a.entity_id,
                       a.configured_priority,a.watch_cadence,a.selection_role,a.learning_basis,
                       a.learning_multiplier,a.exact_source_hits,a.accepted_event_count,a.observation_count
                FROM trend_lane_runs r
                JOIN trend_watch_account_exposures a ON a.run_id=r.run_id
                WHERE r.started_at>=?
                ORDER BY r.started_at,r.run_id,a.platform,a.handle_key
                """,
                (start,),
            )
        )
        metrics: dict[tuple[str, str], dict[str, Any]] = {}
        run_ids: set[str] = set()
        completed_run_ids: set[str] = set()
        global_completed = 0
        global_hits = 0
        for row in rows:
            run_id = str(row["run_id"])
            run_ids.add(run_id)
            completed = str(row["status"]) == "completed"
            if completed:
                completed_run_ids.add(run_id)
                global_completed += 1
                global_hits += int(row["exact_source_hits"] or 0)
            key = (str(row["platform"]), str(row["handle_key"]))
            metric = metrics.setdefault(
                key,
                {
                    "platform": str(row["platform"]), "handle": str(row["handle"]),
                    "entity_id": str(row["entity_id"] or ""), "exposures": 0,
                    "completed_exposures": 0, "error_exposures": 0,
                    "zero_yield_completed_exposures": 0, "exact_source_hits": 0,
                    "accepted_events": 0, "observations": 0, "run_days": set(),
                    "last_selected_at": None, "configured_priority": int(row["configured_priority"]),
                    "watch_cadence": str(row["watch_cadence"]),
                    "last_selection_role": str(row["selection_role"]),
                    "last_learning_basis": str(row["learning_basis"]),
                    "last_learning_multiplier": float(row["learning_multiplier"]),
                },
            )
            metric["exposures"] += 1
            if completed:
                metric["completed_exposures"] += 1
                metric["run_days"].add(str(row["started_at"])[:10])
                if int(row["exact_source_hits"] or 0) == 0:
                    metric["zero_yield_completed_exposures"] += 1
            elif str(row["status"]) == "agent_error":
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
                    **{key: value for key, value in metric.items() if key != "run_days"},
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
                "account_exposures": len(rows), "completed_account_exposures": global_completed,
                "exact_source_hits": global_hits,
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
            entity_id = str(account.get("entity_id") or "").strip().lower()
            exposure_item = dict(exposure_items.get((platform, handle.casefold())) or {})
            exposure_mature = exposure_item.get("discovery_review_eligible") is True
            shadow_item: dict[str, Any] = {}
            market_basis = ""
            for key in (("entity", entity_id), ("platform", platform)):
                candidate = shadow_items.get(key)
                if key[1] and candidate and candidate.get("shadow_review_eligible") is True:
                    shadow_item = dict(candidate)
                    market_basis = key[0]
                    break
            shadow_score = shadow_item.get("shadow_descriptive_score")
            market_mature = bool(shadow_item) and shadow_score is not None
            paper_item: dict[str, Any] = {}
            paper_basis = ""
            for key in (("entity", entity_id), ("platform", platform), ("source_kind", "social")):
                candidate = paper_items.get(key)
                if key[1] and candidate:
                    paper_item = dict(candidate)
                    paper_basis = key[0]
                    break
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
            if not exposure_mature:
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
                    "entity_id": entity_id,
                    "configured_priority": int(account.get("priority") or 3),
                    "watch_cadence": "critical" if critical else "normal",
                    **exposure_item,
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
