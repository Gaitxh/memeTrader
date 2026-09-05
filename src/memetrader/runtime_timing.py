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
        }
