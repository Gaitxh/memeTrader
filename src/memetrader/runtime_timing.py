from __future__ import annotations

import math
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Any


MAX_COMPONENTS = 32
MAX_SAMPLES = 120

def _percentile(values: deque[float], quantile: float) -> float | None:
    return _sorted_percentile(sorted(values), quantile)


def _percentiles(values: deque[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    return {name: _sorted_percentile(ordered, q) for name, q in
            (("p50", .50), ("p90", .90), ("p95", .95), ("p99", .99))}


def _sorted_percentile(ordered: list[float], quantile: float) -> float | None:
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


class RuntimeTiming:
    """Bounded in-memory timing summaries for component cycles and batches.

    Two registries, deliberately separate:

      * `_components` holds the bounded per-component deques used for percentiles. It is capped at
        MAX_COMPONENTS with LRU eviction, because each entry carries two 120-sample deques and the
        payload is written to SQLite every 10 seconds (measured 107 KB per write).
      * `_activity` holds a monotone `calls`/`items` ledger for EVERY component name ever observed.
        It is never evicted. Measured cost 56.7 characters per name, i.e. about 3.1 KB for the 55
        names this runtime registers -- roughly +2.9% on the payload, against about +190% for raising
        the component cap instead.

    Round 88 measured why the second registry is needed. The runtime registers 43 periodic loops plus
    12 ad-hoc observers -- 55 names against a capacity of 32 -- so the payload showed only 32, with 25
    periodic loops invisible (including `position_monitor`, `dexscreener_discovery` and
    `source_health`), and LRU eviction silently RESTARTED counters: `pattern_token_compute` was observed
    going 415 -> 22 and `learning145_flush` 5 -> 0 inside a 3-minute window, because a recreated entry
    begins at `items = 0`. Raising MAX_COMPONENTS would have tripled a 107 KB write every 10 seconds to
    buy back only the same 55 names, so the ledger is the cheaper and more complete answer: it makes
    both "did this loop ever run" and "how much has it done in total" answerable for every name.
    """

    def __init__(self) -> None:
        self._components: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._activity: dict[str, dict[str, int]] = {}
        self._retrieval: deque[dict[str, Any]] = deque(maxlen=120)
        self._market_targets: dict[str, Any] = {}
        self._passive_waits: deque[float] = deque(maxlen=MAX_SAMPLES)
        self._passive_queue: dict[str, Any] = {
            "scope": "since_process_start", "capacity_batches": 16,
            "depth_batches": 0, "max_depth_batches": 0,
            "enqueued_batches": 0, "processed_batches": 0,
            "dropped_batches": 0, "dropped_quotes": 0, "oldest_received_at": None,
            "coalesced_quotes": 0, "normal_takeovers": 0,
        }

    def observe_passive_queue(self, *, depth: int, oldest_received_at: datetime | None,
                              enqueued: bool = False, dropped_quotes: int | None = None,
                              wait_seconds: float | None = None,
                              coalesced_quotes: int = 0,
                              normal_takeovers: int = 0) -> None:
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
        queue["coalesced_quotes"] += int(coalesced_quotes)
        queue["normal_takeovers"] += int(normal_takeovers)

    def _retrieval_bucket(self, bucket: int) -> dict[str, Any]:
        if not self._retrieval or self._retrieval[-1]["timestamp"] != bucket:
            self._retrieval.append({"timestamp": bucket, "chains": {}, "targets": None})
        return self._retrieval[-1]

    def observe_market_targets(self, counts: dict[str, Any],
                               observed_at: datetime | None = None) -> None:
        """Latest target supply, and the bucket it applies to.

        Stamping every cycle keeps an empty bucket on the held-retrieval curve
        when the lane has nothing to quote, so "idle lane" stays distinguishable
        from "process stopped sampling".
        """
        self._market_targets = dict(counts)
        if observed_at is None:
            return
        point = self._retrieval_bucket(int(observed_at.timestamp()) // 10 * 10)
        point["targets"] = int(counts.get("high_priority_total") or 0)

    def observe_retrieval(self, *, chain: str, duration_seconds: float,
                          tokens: int, priced: int, failed: int,
                          observed_at: datetime) -> None:
        """Token-weighted batch latency, not elapsed divided by batch size."""
        counts = self._retrieval_bucket(int(observed_at.timestamp()) // 10 * 10)["chains"].setdefault(chain, {
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
        # The monotone ledger is updated FIRST and unconditionally, so it survives the eviction below
        # and can never decrease. Every other counter in this class is per-entry and therefore resets.
        activity = self._activity.get(name)
        if activity is None:
            activity = self._activity[name] = {"calls": 0, "items": 0, "failures": 0}
        activity["calls"] += 1
        activity["items"] += int(items)
        activity["failures"] += int(failures)
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
                "actual_interval_seconds": _percentiles(intervals),
                "duration_seconds": _percentiles(durations),
                "failures": timing["failures"],
                "items": timing["items"],
                "configured_interval_seconds": timing["configured_interval_seconds"],
            }
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "components": components,
            # Every name ever observed, with monotone totals, regardless of `components` eviction.
            # A reader asking "did path X run, and how much did it do" must use this block: the
            # `components` block is a bounded LRU view whose `items` resets when an entry is recreated.
            "activity": {name: dict(counts) for name, counts in sorted(self._activity.items())},
            "passive_queue": {
                **self._passive_queue,
                "wait_sample_count": len(self._passive_waits),
                "wait_seconds": _percentiles(self._passive_waits),
            },
            "held_retrieval": {
                "bucket_seconds": 10, "scope": "open_and_valid_pending_primary_lane",
                "target_supply": dict(self._market_targets),
                "retained_points": len(self._retrieval),
                "sampled_points": sum(1 for p in self._retrieval if p["chains"]),
                "idle_points": sum(1 for p in self._retrieval if not p["chains"]),
                "window_seconds": (
                    max(p["timestamp"] for p in self._retrieval)
                    - min(p["timestamp"] for p in self._retrieval)
                ) if self._retrieval else 0,
                "points": [{
                    "observed_at": datetime.fromtimestamp(p["timestamp"], timezone.utc).isoformat(),
                    "chains": {chain: dict(counts) for chain, counts in p["chains"].items()},
                    "targets": p.get("targets"),
                } for p in self._retrieval],
            },
        }
