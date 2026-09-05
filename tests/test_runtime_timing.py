from __future__ import annotations

from datetime import datetime

import pytest

from memetrader.runtime_timing import MAX_COMPONENTS, MAX_SAMPLES, RuntimeTiming


def test_runtime_timing_snapshot_percentiles_and_counters():
    timing = RuntimeTiming()
    for value in range(1, 5):
        timing.observe(
            "quote_batch",
            duration_seconds=value,
            interval_seconds=value * 10,
            configured_interval_seconds=1,
            failures=value == 4,
            items=3,
        )

    snapshot = timing.snapshot()
    component = snapshot["components"]["quote_batch"]
    assert component == {
        "sample_count": 4,
        "interval_sample_count": 4,
        "actual_interval_seconds": {"p50": 25.0, "p95": 38.5},
        "duration_seconds": {"p50": 2.5, "p95": 3.8499999999999996},
        "failures": 1,
        "items": 12,
        "configured_interval_seconds": 1.0,
    }
    assert snapshot["generated_at"].endswith("Z")
    datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))


def test_runtime_timing_bounds_samples_and_components():
    timing = RuntimeTiming()
    for value in range(MAX_SAMPLES + 5):
        timing.observe("runtime_cycle", value, interval_seconds=value)
    for index in range(MAX_COMPONENTS):
        timing.observe(f"component_{index}", index)

    components = timing.snapshot()["components"]
    assert len(components) == MAX_COMPONENTS
    assert "runtime_cycle" not in components

    timing.observe("component_0", 999)
    for index in range(MAX_COMPONENTS, MAX_COMPONENTS + 2):
        timing.observe(f"component_{index}", index)
    components = timing.snapshot()["components"]
    assert "component_0" in components
    assert "component_1" not in components

    samples = RuntimeTiming()
    for value in range(MAX_SAMPLES + 5):
        samples.observe("exit_batch", value, interval_seconds=value)
    bounded = samples.snapshot()["components"]["exit_batch"]
    assert bounded["sample_count"] == MAX_SAMPLES
    assert bounded["interval_sample_count"] == MAX_SAMPLES
    assert bounded["duration_seconds"]["p50"] == pytest.approx(64.5)


def test_runtime_timing_empty_snapshot_and_missing_intervals():
    timing = RuntimeTiming()
    empty = timing.snapshot()
    assert empty["components"] == {}

    timing.observe("mark_batch", 0.25, items=2)
    component = timing.snapshot()["components"]["mark_batch"]
    assert component["sample_count"] == 1
    assert component["interval_sample_count"] == 0
    assert component["actual_interval_seconds"] == {"p50": None, "p95": None}
    assert component["duration_seconds"] == {"p50": 0.25, "p95": 0.25}
    assert component["configured_interval_seconds"] is None


def test_retrieval_curve_weights_tokens_without_dividing_batch_latency():
    from datetime import timezone, timedelta
    timing = RuntimeTiming()
    at = datetime(2026, 9, 6, tzinfo=timezone.utc)
    timing.observe_retrieval(chain="solana", duration_seconds=2, tokens=30,
                             priced=29, failed=0, observed_at=at)
    timing.observe_retrieval(chain="solana", duration_seconds=8, tokens=10,
                             priced=0, failed=10, observed_at=at)
    timing.observe_retrieval(chain="bsc", duration_seconds=4, tokens=5,
                             priced=5, failed=0, observed_at=at)
    series = timing.snapshot()["held_retrieval"]
    sol = series["points"][0]["chains"]["solana"]
    assert sol["weighted_seconds"] / sol["token_attempts"] == 3.5
    assert sol["priced_tokens"] == 29
    assert sol["failed_tokens"] == 10
    for i in range(1, 125):
        timing.observe_retrieval(chain="bsc", duration_seconds=1, tokens=1,
                                 priced=1, failed=0, observed_at=at+timedelta(seconds=i*10))
    assert len(timing.snapshot()["held_retrieval"]["points"]) == 120
    assert sol["token_attempts"] == 40  # Previously published points are immutable.
