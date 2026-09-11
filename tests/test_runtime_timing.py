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


def test_passive_queue_bounds_wait_samples_and_retains_loss_counters():
    timing = RuntimeTiming()
    for index in range(MAX_COMPONENTS):
        timing.observe(f"component_{index}", 1)
    received = datetime.fromisoformat("2026-09-08T07:00:00+00:00")
    timing.observe_passive_queue(depth=16, oldest_received_at=received,
                                  enqueued=True, dropped_quotes=30)
    before = timing.snapshot()["passive_queue"]
    for value in range(MAX_SAMPLES + 5):
        timing.observe_passive_queue(depth=0, oldest_received_at=None, wait_seconds=value)
    snapshot = timing.snapshot()
    queue = snapshot["passive_queue"]
    assert len(snapshot["components"]) == MAX_COMPONENTS
    assert queue["wait_sample_count"] == MAX_SAMPLES
    assert queue["wait_seconds"]["p50"] == pytest.approx(64.5)
    assert queue["processed_batches"] == MAX_SAMPLES + 5
    assert queue["dropped_batches"] == 1
    assert queue["dropped_quotes"] == 30
    assert queue["enqueued_batches"] == 1
    assert queue["depth_batches"] == 0
    assert queue["max_depth_batches"] == 16
    assert queue["oldest_received_at"] is None
    assert before["depth_batches"] == 16
    assert before["oldest_received_at"] == received.isoformat()


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


def test_retrieval_curve_marks_idle_buckets_instead_of_connecting_across_them():
    from datetime import timezone, timedelta
    timing = RuntimeTiming()
    at = datetime(2026, 9, 6, tzinfo=timezone.utc)
    timing.observe_retrieval(chain="bsc", duration_seconds=2, tokens=4,
                             priced=4, failed=0, observed_at=at)
    timing.observe_market_targets({"high_priority_total": 0, "actual_open": 0},
                                  observed_at=at + timedelta(seconds=10))
    timing.observe_market_targets({"high_priority_total": 0, "actual_open": 0},
                                  observed_at=at + timedelta(seconds=20))
    timing.observe_market_targets({"high_priority_total": 2, "actual_open": 1},
                                  observed_at=at + timedelta(seconds=30))
    series = timing.snapshot()["held_retrieval"]
    # Every cycle stamps its 10-second bucket, so an idle lane keeps a point.
    assert [bool(p["chains"]) for p in series["points"]] == [True, False, False, False]
    assert [p["targets"] for p in series["points"]] == [None, 0, 0, 2]
    assert series["sampled_points"] == 1
    assert series["idle_points"] == 3
    assert series["retained_points"] == 4
    assert series["window_seconds"] == 30
    # Repeating a stamp inside the same bucket must not create a second point.
    timing.observe_market_targets({"high_priority_total": 5}, observed_at=at + timedelta(seconds=34))
    assert len(timing.snapshot()["held_retrieval"]["points"]) == 4
    assert timing.snapshot()["held_retrieval"]["points"][-1]["targets"] == 5
    # A caller that only wants the latest supply still works without a timestamp.
    timing.observe_market_targets({"high_priority_total": 7, "actual_open": 3})
    assert timing.snapshot()["held_retrieval"]["target_supply"]["actual_open"] == 3
    assert timing.snapshot()["held_retrieval"]["points"][-1]["targets"] == 5
