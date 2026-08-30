from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

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
                    status TEXT NOT NULL DEFAULT 'active'
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
                """
            )
            columns = {row["name"] for row in self.db.execute("PRAGMA table_info(observations)")}
            if "source_item_id" not in columns:
                self.db.execute("ALTER TABLE observations ADD COLUMN source_item_id TEXT NOT NULL DEFAULT ''")
            if "capture_phase" not in columns:
                self.db.execute("ALTER TABLE observations ADD COLUMN capture_phase TEXT NOT NULL DEFAULT 'live'")
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

    def create_event(self, title: str, aliases: Iterable[str], attention: float, first_seen_at=None) -> int:
        seen = first_seen_at or utcnow()
        with self._lock, self.db:
            cur = self.db.execute(
                "INSERT INTO events(title,aliases_json,attention,first_seen_at,last_seen_at,status) VALUES(?,?,?,?,?,'active')",
                (title, self._json(sorted(set(aliases))), attention, iso(seen), iso(seen)),
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
                last_seen_at=parse_time(r["last_seen_at"]), status=r["status"],
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
            return not existed

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
                self.db.execute("DELETE FROM positions WHERE token_id=?", (token_id,))
            else:
                self.db.execute(
                    "UPDATE positions SET quantity=?,remaining_cost_usd=?,realized_pnl_usd=realized_pnl_usd+? WHERE token_id=?",
                    (remaining_quantity,remaining_cost,pnl,token_id),
                )
        return {"quantity": quantity, "gross_usd": gross, "fee_usd": fee, "net_usd": net, "pnl_usd": pnl}

    def trades(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)))

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

    def agent_attempts(self, *, limit: int = 100) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                "SELECT * FROM agent_attempts ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            )
        )
