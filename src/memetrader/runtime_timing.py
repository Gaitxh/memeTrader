from __future__ import annotations

import math
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any


MAX_COMPONENTS = 32
MAX_SAMPLES = 120


def _percentile(values: deque[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


class RuntimeTiming:
    """Bounded in-memory timing summaries for component cycles and batches."""

    def __init__(self) -> None:
        self._components: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._retrieval: deque[dict[str, Any]] = deque(maxlen=120)
        self._market_targets: dict[str, Any] = {}
        self._passive_waits: deque[float] = deque(maxlen=MAX_SAMPLES)
        self._passive_queue: dict[str, Any] = {
            "scope": "since_process_start", "capacity_batches": 16,
            "depth_batches": 0, "max_depth_batches": 0,
            "enqueued_batches": 0, "processed_batches": 0,
            "dropped_batches": 0, "dropped_quotes": 0, "oldest_received_at": None,
        }

    def observe_passive_queue(self, *, depth: int, oldest_received_at: datetime | None,
                              enqueued: bool = False, dropped_quotes: int | None = None,
                              wait_seconds: float | None = None) -> None:
        """Queue delay includes scheduler waits; no per-token history or extra I/O."""
        queue = self._passive_queue
        queue["depth_batches"] = depth
        queue["max_depth_batches"] = max(queue["max_depth_batches"], depth)
        queue["oldest_received_at"] = oldest_received_at.isoformat() if oldest_received_at else None
        queue["enqueued_batches"] += int(enqueued)
        if dropped_quotes is not None:
            queue["dropped_batches"] += 1
            queue["dropped_quotes"] += dropped_quotes
        if wait_seconds is not None:
            queue["processed_batches"] += 1
            self._passive_waits.append(wait_seconds)

    def observe_market_targets(self, counts: dict[str, Any]) -> None:
        self._market_targets = dict(counts)

    def observe_retrieval(self, *, chain: str, duration_seconds: float,
                          tokens: int, priced: int, failed: int,
                          observed_at: datetime) -> None:
        """Token-weighted batch latency, not elapsed divided by batch size."""
        bucket = int(observed_at.timestamp()) // 10 * 10
        if not self._retrieval or self._retrieval[-1]["timestamp"] != bucket:
            self._retrieval.append({"timestamp": bucket, "chains": {}})
        counts = self._retrieval[-1]["chains"].setdefault(chain, {
            "token_attempts": 0, "priced_tokens": 0, "failed_tokens": 0,
            "weighted_seconds": 0.0,
        })
        counts["token_attempts"] += tokens
        counts["priced_tokens"] += priced
        counts["failed_tokens"] += failed
        counts["weighted_seconds"] += duration_seconds * tokens

    def observe(
        self,
        component: str,
        duration_seconds: float,
        interval_seconds: float | None = None,
        configured_interval_seconds: float | None = None,
        failures: int = 0,
        items: int = 0,
    ) -> None:
        name = str(component)
        timing = self._components.get(name)
        if timing is None:
            if len(self._components) >= MAX_COMPONENTS:
                self._components.popitem(last=False)
            timing = {
                "durations": deque(maxlen=MAX_SAMPLES),
                "intervals": deque(maxlen=MAX_SAMPLES),
                "configured_interval_seconds": None,
                "failures": 0,
                "items": 0,
            }
            self._components[name] = timing
        else:
            self._components.move_to_end(name)

        timing["durations"].append(float(duration_seconds))
        if interval_seconds is not None:
            timing["intervals"].append(float(interval_seconds))
        if configured_interval_seconds is not None:
            timing["configured_interval_seconds"] = float(configured_interval_seconds)
        timing["failures"] += int(failures)
        timing["items"] += int(items)

    def snapshot(self) -> dict[str, Any]:
        components: dict[str, Any] = {}
        for name, timing in self._components.items():
            durations = timing["durations"]
            intervals = timing["intervals"]
            components[name] = {
                "sample_count": len(durations),
                "interval_sample_count": len(intervals),
                "actual_interval_seconds": {
                    "p50": _percentile(intervals, 0.50),
                    "p95": _percentile(intervals, 0.95),
                },
                "duration_seconds": {
                    "p50": _percentile(durations, 0.50),
                    "p95": _percentile(durations, 0.95),
                },
                "failures": timing["failures"],
                "items": timing["items"],
                "configured_interval_seconds": timing["configured_interval_seconds"],
            }
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "components": components,
            "passive_queue": {
                **self._passive_queue,
                "wait_sample_count": len(self._passive_waits),
                "wait_seconds": {
                    "p50": _percentile(self._passive_waits, 0.50),
                    "p95": _percentile(self._passive_waits, 0.95),
                },
            },
            "held_retrieval": {
                "bucket_seconds": 10, "scope": "open_and_valid_pending_primary_lane",
                "target_supply": dict(self._market_targets),
                "points": [{
                    "observed_at": datetime.fromtimestamp(p["timestamp"], timezone.utc).isoformat(),
                    "chains": {chain: dict(counts) for chain, counts in p["chains"].items()},
                } for p in self._retrieval],
            },
        }
