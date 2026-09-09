"""Read-only incremental adapter for the flat-breakout target selector."""

from __future__ import annotations

from datetime import datetime
import sqlite3
from typing import Any, Iterable

from .flat_frontier import (
    FlatFrontierEvaluation,
    FlatFrontierMark,
    FlatFrontierObservation,
    FlatTargetFrontier,
)
from .models import UTC, parse_time


_FUTURE_INVALID_PAIR_DATE = datetime(9998, 1, 1, tzinfo=UTC)
_SQLITE_PARAMETER_BATCH = 900


class FlatSelector:
    """Mirror Store's flat selector without rerunning its broad target query.

    Store owns mutation notifications.  After every committed market-mark
    mutation it adds its token id to ``_flat_dirty_marks`` while holding its
    existing lock.  Evaluation and observer rows are append-only and are
    caught by their primary-key frontiers.
    """

    def __init__(self, store: Any) -> None:
        self.store = store
        with store._lock:
            if not hasattr(store,'_flat_dirty_marks'):
                store._flat_dirty_marks=set()
        self._frontier = FlatTargetFrontier()
        self._bootstrapped = False
        self._evaluation_frontier = 0
        self._observation_frontier = 0
        self._registered: bool | None = None
        self._pair_created_raw: dict[str, Any] = {}
        self._open_counts: dict[str, int] = {}

    def due_targets(self, *, limit: int = 30, now: Any) -> list[dict[str, Any]]:
        current = parse_time(now)
        if not self._bootstrapped:
            self._bootstrap(current)
        else:
            self._advance(current)
        self._refresh_open_counts(current)
        selected = self._frontier.select(now=current, limit=limit)
        if not selected:
            return []
        metadata = self._current_token_metadata([target.token_id for target in selected])
        return [
            {
                "token_id": target.token_id,
                "chain": metadata[target.token_id][0],
                "address": metadata[target.token_id][1],
                "pair_address": target.pair_address,
                "pair_created_at": self._pair_created_raw[target.token_id],
                "observer_state": target.observer_state,
            }
            for target in selected
            if target.token_id in metadata
        ]

    def _bootstrap(self, now: datetime) -> None:
        db, evaluation_highwater, observation_highwater, registered, _dirty = self._snapshot()
        try:
            evaluations = [self._evaluation_from_row(row) for row in db.execute(
                "WITH latest_eval AS ("
                "SELECT token_id,MAX(id) AS evaluation_id FROM "
                "chain_meme_trader_v6_entry_evaluations WHERE definition_version=? AND "
                "COALESCE(json_extract(feature_json,'$.pair_address'),'')!='' "
                "GROUP BY token_id) "
                "SELECT e.token_id,t.chain,t.address,e.id AS evaluation_id,"
                "json_extract(e.feature_json,'$.pair_address') AS pair_address,"
                "json_extract(e.feature_json,'$.pair_created_at') AS pair_created_at "
                "FROM latest_eval le JOIN chain_meme_trader_v6_entry_evaluations e "
                "ON e.id=le.evaluation_id JOIN tokens t ON t.token_id=e.token_id",
                (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
            )]
            observations = [FlatFrontierObservation(
                token_id=str(row["token_id"]), pair_address=str(row["pair_address"]),
                observation_id=int(row["observation_id"]), status=str(row["status"]),
            ) for row in db.execute(
                "WITH latest_observation AS ("
                "SELECT token_id,pair_address,MAX(id) AS observation_id FROM "
                "chain_meme_trader_flat_breakout_shadow WHERE observer_version=? "
                "GROUP BY token_id,pair_address) "
                "SELECT o.token_id,o.pair_address,o.id AS observation_id,o.status "
                "FROM latest_observation lo JOIN chain_meme_trader_flat_breakout_shadow o "
                "ON o.id=lo.observation_id",
                (self.store.FLAT_BREAKOUT_SHADOW_VERSION,),
            )]
            marks = [FlatFrontierMark(
                token_id=str(row["token_id"]), last_attempt_at=self._parse_optional_time(row["last_attempt_at"]),
            ) for row in db.execute(
                "SELECT token_id,last_attempt_at FROM chain_meme_trader_market_marks"
            )]
        finally:
            db.close()
        self._frontier.rebuild(
            evaluations=evaluations,
            observations=observations,
            marks=marks,
            open_position_counts=(),
            registered=registered,
            now=now,
        )
        self._evaluation_frontier = evaluation_highwater
        self._observation_frontier = observation_highwater
        self._registered = registered
        self._bootstrapped = True
        # Dirty marks captured with the snapshot were already represented by it.
        # Marks committed afterward remain in Store's new dirty set for _advance.

    def _advance(self, now: datetime) -> None:
        db, evaluation_highwater, observation_highwater, registered, dirty = self._snapshot()
        try:
            new_evaluations = [self._evaluation_from_row(row) for row in db.execute(
                "SELECT e.token_id,t.chain,t.address,e.id AS evaluation_id,"
                "json_extract(e.feature_json,'$.pair_address') AS pair_address,"
                "json_extract(e.feature_json,'$.pair_created_at') AS pair_created_at "
                "FROM chain_meme_trader_v6_entry_evaluations e JOIN tokens t "
                "ON t.token_id=e.token_id WHERE e.definition_version=? AND e.id>? AND e.id<=? "
                "AND COALESCE(json_extract(e.feature_json,'$.pair_address'),'')!='' ORDER BY e.id",
                (self.store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
                 self._evaluation_frontier, evaluation_highwater),
            )]
            new_observations = [FlatFrontierObservation(
                token_id=str(row["token_id"]), pair_address=str(row["pair_address"]),
                observation_id=int(row["id"]), status=str(row["status"]),
            ) for row in db.execute(
                "SELECT token_id,pair_address,id,status FROM chain_meme_trader_flat_breakout_shadow "
                "WHERE observer_version=? AND id>? AND id<=? ORDER BY id",
                (self.store.FLAT_BREAKOUT_SHADOW_VERSION,
                 self._observation_frontier, observation_highwater),
            )]
            mark_tokens = dirty | {row.token_id for row in new_evaluations}
            marks = self._marks_for_tokens(db, mark_tokens)
        finally:
            db.close()
        for evaluation in new_evaluations:
            self._frontier.on_evaluation(evaluation, now=now)
        for observation in new_observations:
            self._frontier.on_observation(observation, now=now)
        for mark in marks:
            self._frontier.on_mark(mark, now=now)
        if registered != self._registered:
            self._frontier.set_registered(registered, now=now)
            self._registered = registered
        self._evaluation_frontier = evaluation_highwater
        self._observation_frontier = observation_highwater

    def _snapshot(self) -> tuple[sqlite3.Connection, int, int, bool, set[str]]:
        """Create the DB snapshot before releasing Store's writer lock.

        Clearing dirty marks while locked makes every post-snapshot mark writer
        leave its token in the set for the next cycle instead of losing it.
        """
        with self.store._lock:
            db = sqlite3.connect(self.store.path.resolve().as_uri() + "?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            evaluation_highwater = int(db.execute(
                "SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_v6_entry_evaluations",
            ).fetchone()[0])
            observation_highwater = int(db.execute(
                "SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_flat_breakout_shadow",
            ).fetchone()[0])
            registered = db.execute(
                "SELECT 1 FROM chain_meme_trader_flat_breakout_shadow_registrations "
                "WHERE observer_version=?",
                (self.store.FLAT_BREAKOUT_SHADOW_VERSION,),
            ).fetchone() is not None
            pending = getattr(self.store, "_flat_dirty_marks", None)
            dirty = set(pending or ())
            if pending is not None:
                pending.clear()
        return db, evaluation_highwater, observation_highwater, registered, dirty

    def _refresh_open_counts(self, now: datetime) -> None:
        with self.store._lock:
            current = {
                str(row["token_id"]): int(row["count"])
                for row in self.store.db.execute(
                    "SELECT token_id,COUNT(*) AS count FROM chain_meme_trader_positions "
                    "WHERE status='open' GROUP BY token_id"
                )
            }
        for token_id in current.keys() | self._open_counts.keys():
            count = current.get(token_id, 0)
            if self._open_counts.get(token_id, 0) != count:
                self._frontier.on_open_position_count(token_id, count, now=now)
        self._open_counts = current

    def _current_token_metadata(self, token_ids: Iterable[str]) -> dict[str, tuple[str, str]]:
        rows: dict[str, tuple[str, str]] = {}
        ids = list(dict.fromkeys(token_ids))
        with self.store._lock:
            for start in range(0, len(ids), _SQLITE_PARAMETER_BATCH):
                chunk = ids[start:start + _SQLITE_PARAMETER_BATCH]
                placeholders = ",".join("?" for _ in chunk)
                for row in self.store.db.execute(
                    f"SELECT token_id,chain,address FROM tokens WHERE token_id IN ({placeholders})", chunk,
                ):
                    rows[str(row["token_id"])] = (str(row["chain"]), str(row["address"]))
        return rows

    def _marks_for_tokens(self, db: sqlite3.Connection, token_ids: set[str]) -> list[FlatFrontierMark]:
        if not token_ids:
            return []
        found: dict[str, datetime | None] = {}
        ids = list(token_ids)
        for start in range(0, len(ids), _SQLITE_PARAMETER_BATCH):
            chunk = ids[start:start + _SQLITE_PARAMETER_BATCH]
            placeholders = ",".join("?" for _ in chunk)
            for row in db.execute(
                f"SELECT token_id,last_attempt_at FROM chain_meme_trader_market_marks "
                f"WHERE token_id IN ({placeholders})", chunk,
            ):
                found[str(row["token_id"])] = self._parse_optional_time(row["last_attempt_at"])
        return [FlatFrontierMark(token_id=token_id, last_attempt_at=found.get(token_id)) for token_id in token_ids]

    def _evaluation_from_row(self, row: sqlite3.Row) -> FlatFrontierEvaluation:
        raw_pair_created = row["pair_created_at"]
        evaluation = FlatFrontierEvaluation(
            token_id=str(row["token_id"]), chain=str(row["chain"]), address=str(row["address"]),
            evaluation_id=int(row["evaluation_id"]), pair_address=str(row["pair_address"]),
            pair_created_at=self._pair_created_for_frontier(raw_pair_created),
        )
        self._pair_created_raw[evaluation.token_id] = raw_pair_created
        return evaluation

    @staticmethod
    def _pair_created_for_frontier(value: Any) -> datetime:
        if value is None:
            return _FUTURE_INVALID_PAIR_DATE
        try:
            return parse_time(value)
        except (TypeError, ValueError, OverflowError):
            return _FUTURE_INVALID_PAIR_DATE

    @staticmethod
    def _parse_optional_time(value: Any) -> datetime | None:
        return parse_time(value) if value is not None else None
