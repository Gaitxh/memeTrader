"""Incremental projection for the flat-breakout selector.

This module deliberately has no Store or runtime dependency.  Its caller owns
the initial read and must feed every committed evaluation, observation, mark,
and position change through the matching method.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import heapq
from typing import Iterable

from .models import UTC, parse_time


NEAR_STATES = frozenset({
    "near_trigger", "breakout_confirmation_pending", "shadow_breakout_candidate",
})
_MATURE_AGE = timedelta(hours=6)
_NEAR_DELAY = timedelta(seconds=5)
_ORDINARY_DELAY = timedelta(seconds=60)
_EARLIEST = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class FlatFrontierEvaluation:
    token_id: str
    chain: str
    address: str
    evaluation_id: int
    pair_address: str
    pair_created_at: datetime


@dataclass(frozen=True, slots=True)
class FlatFrontierObservation:
    token_id: str
    pair_address: str
    observation_id: int
    status: str


@dataclass(frozen=True, slots=True)
class FlatFrontierMark:
    token_id: str
    last_attempt_at: datetime | None


@dataclass(frozen=True, slots=True)
class FlatFrontierTarget:
    token_id: str
    chain: str
    address: str
    pair_address: str
    pair_created_at: datetime
    observer_state: str | None


@dataclass(slots=True)
class _Target:
    chain: str
    address: str
    evaluation_id: int
    pair_address: str
    pair_created_at: datetime


class FlatTargetFrontier:
    """Keep the SQL selector's current membership and ordering incrementally.

    ``rebuild`` is the one full-projection bootstrap/resynchronization path.
    Later updates are O(log n) heap changes and ``select`` only examines its
    requested result count plus stale heap entries.  It does not poll or query.
    """

    def __init__(self) -> None:
        self._registered = False
        self._targets: dict[str, _Target] = {}
        self._observations: dict[tuple[str, str], FlatFrontierObservation] = {}
        self._marks: dict[str, datetime | None] = {}
        self._open_counts: dict[str, int] = {}
        self._versions: dict[str, int] = {}
        self._age_heap: list[tuple[datetime, int, str]] = []
        self._due_heap: list[tuple[datetime, int, str]] = []
        self._ready_heap: list[tuple[int, datetime, int, str, int]] = []

    def rebuild(
        self,
        *,
        evaluations: Iterable[FlatFrontierEvaluation],
        observations: Iterable[FlatFrontierObservation],
        marks: Iterable[FlatFrontierMark],
        open_position_counts: Iterable[tuple[str, int]],
        registered: bool,
        now: datetime,
    ) -> None:
        """Replace state from one consistent, complete selector projection.

        ``evaluations`` must contain the SQL ``latest_eval`` rows (only
        non-empty pair addresses).  ``observations`` must contain every latest
        ``(token_id, pair_address)`` row, including pairs not currently chosen
        by an evaluation, so a later pair switch remains exact.
        """
        self.__init__()
        self._registered = registered
        for observation in observations:
            self._record_observation(observation)
        for mark in marks:
            self._marks[mark.token_id] = self._time_or_none(mark.last_attempt_at)
        for token_id, count in open_position_counts:
            if count < 0:
                raise ValueError("open position count cannot be negative")
            if count:
                self._open_counts[token_id] = count
        for evaluation in evaluations:
            self._record_evaluation(evaluation)
        current = parse_time(now)
        for token_id in self._targets:
            self._schedule(token_id, current)

    def set_registered(self, registered: bool, *, now: datetime) -> None:
        """Mirror the selector's registration existence gate."""
        self._registered = registered
        current = parse_time(now)
        for token_id in self._targets:
            self._schedule(token_id, current)
        self._compact_if_stale(current)

    def on_evaluation(self, evaluation: FlatFrontierEvaluation, *, now: datetime) -> None:
        """Apply a committed non-empty-pair evaluation row.

        Empty-pair evaluations intentionally do nothing: the SQL CTE filters
        them before selecting MAX(id), so they cannot displace an older valid
        evaluation for the same token.
        """
        if not evaluation.pair_address:
            return
        previous = self._targets.get(evaluation.token_id)
        if previous is not None and evaluation.evaluation_id <= previous.evaluation_id:
            return
        self._record_evaluation(evaluation)
        current = parse_time(now)
        self._schedule(evaluation.token_id, current)
        self._compact_if_stale(current)

    def on_observation(self, observation: FlatFrontierObservation, *, now: datetime) -> None:
        """Apply a committed latest-observation candidate for one token/pair."""
        key = (observation.token_id, observation.pair_address)
        previous = self._observations.get(key)
        if previous is not None and observation.observation_id <= previous.observation_id:
            return
        self._record_observation(observation)
        target = self._targets.get(observation.token_id)
        if target is not None and target.pair_address == observation.pair_address:
            current = parse_time(now)
            self._schedule(observation.token_id, current)
            self._compact_if_stale(current)

    def on_mark(self, mark: FlatFrontierMark, *, now: datetime) -> None:
        self._marks[mark.token_id] = self._time_or_none(mark.last_attempt_at)
        if mark.token_id in self._targets:
            current = parse_time(now)
            self._schedule(mark.token_id, current)
            self._compact_if_stale(current)

    def on_token(self, token_id: str, *, chain: str, address: str, now: datetime) -> None:
        """Apply a committed tokens-table update used in selector output."""
        target = self._targets.get(token_id)
        if target is None:
            return
        target.chain = chain
        target.address = address
        current = parse_time(now)
        self._schedule(token_id, current)
        self._compact_if_stale(current)

    def on_open_position_count(self, token_id: str, count: int, *, now: datetime) -> None:
        """Apply the committed count used by SQL's open-position EXISTS test."""
        if count < 0:
            raise ValueError("open position count cannot be negative")
        if count:
            self._open_counts[token_id] = count
        else:
            self._open_counts.pop(token_id, None)
        if token_id in self._targets:
            current = parse_time(now)
            self._schedule(token_id, current)
            self._compact_if_stale(current)

    def select(self, *, now: datetime, limit: int = 30) -> list[FlatFrontierTarget]:
        """Return the same ordered candidate fields as the current SQL selector."""
        current = parse_time(now)
        self._advance(current)
        selected: list[FlatFrontierTarget] = []
        retained: list[tuple[int, datetime, int, str, int]] = []
        while self._ready_heap and len(selected) < max(1, min(30, int(limit))):
            item = heapq.heappop(self._ready_heap)
            _, _, _, token_id, version = item
            if not self._ready_now(token_id, version, current):
                continue
            target = self._targets[token_id]
            selected.append(FlatFrontierTarget(
                token_id=token_id,
                chain=target.chain,
                address=target.address,
                pair_address=target.pair_address,
                pair_created_at=target.pair_created_at,
                observer_state=self._observer_state(token_id, target.pair_address),
            ))
            retained.append(item)
        for item in retained:
            heapq.heappush(self._ready_heap, item)
        return selected

    def _record_evaluation(self, evaluation: FlatFrontierEvaluation) -> None:
        if not evaluation.pair_address:
            return
        self._targets[evaluation.token_id] = _Target(
            chain=evaluation.chain,
            address=evaluation.address,
            evaluation_id=evaluation.evaluation_id,
            pair_address=evaluation.pair_address,
            pair_created_at=parse_time(evaluation.pair_created_at),
        )

    def _record_observation(self, observation: FlatFrontierObservation) -> None:
        self._observations[(observation.token_id, observation.pair_address)] = observation

    def _schedule(self, token_id: str, now: datetime) -> None:
        target = self._targets[token_id]
        version = self._versions.get(token_id, 0) + 1
        self._versions[token_id] = version
        if not self._registered:
            return
        mature_at = target.pair_created_at + _MATURE_AGE
        if mature_at > now:
            heapq.heappush(self._age_heap, (mature_at, version, token_id))
            return
        if self._open_counts.get(token_id, 0):
            return
        attempt = self._marks.get(token_id)
        delay = _NEAR_DELAY if self._is_near(token_id, target.pair_address) else _ORDINARY_DELAY
        due_at = now if attempt is None else attempt + delay
        if due_at > now:
            heapq.heappush(self._due_heap, (due_at, version, token_id))
            return
        self._enqueue_ready(token_id, version)

    def _advance(self, now: datetime) -> None:
        while self._age_heap and self._age_heap[0][0] <= now:
            _, version, token_id = heapq.heappop(self._age_heap)
            if self._versions.get(token_id) == version:
                self._schedule(token_id, now)
        while self._due_heap and self._due_heap[0][0] <= now:
            _, version, token_id = heapq.heappop(self._due_heap)
            if self._versions.get(token_id) == version:
                self._enqueue_ready(token_id, version)

    def _compact_if_stale(self, now: datetime) -> None:
        """Bound lazy-invalidated heap entries without another DB projection."""
        entries = len(self._age_heap) + len(self._due_heap) + len(self._ready_heap)
        if entries <= max(64, 4 * len(self._targets)):
            return
        self._age_heap.clear()
        self._due_heap.clear()
        self._ready_heap.clear()
        for token_id in self._targets:
            self._schedule(token_id, now)

    def _enqueue_ready(self, token_id: str, version: int) -> None:
        target = self._targets[token_id]
        attempt = self._marks.get(token_id) or _EARLIEST
        priority = 0 if self._is_near(token_id, target.pair_address) else 1
        heapq.heappush(
            self._ready_heap,
            (priority, attempt, -target.evaluation_id, token_id, version),
        )

    def _ready_now(self, token_id: str, version: int, now: datetime) -> bool:
        target = self._targets.get(token_id)
        if not self._registered or target is None or self._versions.get(token_id) != version:
            return False
        if target.pair_created_at + _MATURE_AGE > now or self._open_counts.get(token_id, 0):
            return False
        attempt = self._marks.get(token_id)
        delay = _NEAR_DELAY if self._is_near(token_id, target.pair_address) else _ORDINARY_DELAY
        return attempt is None or attempt + delay <= now

    def _observer_state(self, token_id: str, pair_address: str) -> str | None:
        observation = self._observations.get((token_id, pair_address))
        return observation.status if observation is not None else None

    def _is_near(self, token_id: str, pair_address: str) -> bool:
        return self._observer_state(token_id, pair_address) in NEAR_STATES

    @staticmethod
    def _time_or_none(value: datetime | None) -> datetime | None:
        return parse_time(value) if value is not None else None
