"""Tests for the adaptive observation cadence (round 120-21).

Measured basis: over 13,651 consecutive same-token snapshot pairs, 70.8% of polls returned no
change in price, volume or liquidity, so a fixed 15s cadence spends ~3.42x the requests it
needs. The backoff must be information-safe (volume-only changes still count as information),
capped, instantly resettable, and fully reversible.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memetrader import observation_leases145 as ol

T0 = datetime(2026, 9, 13, 0, 0, 0, tzinfo=timezone.utc)
A = (1.0, 100.0, 5000.0)
B = (1.1, 100.0, 5000.0)     # price moved
C = (1.0, 200.0, 5000.0)     # volume moved, price same  -> STILL information
D = (1.0, 100.0, 6000.0)     # liquidity moved only       -> information


def _item():
    return {}


def test_no_content_preserves_the_original_fixed_cadence():
    """The feature must be reversible: a caller that passes nothing behaves exactly as before."""
    item = _item()
    ol.record_frame(item, T0, T0, content=None)
    assert item["next_due_at"] == T0 + timedelta(seconds=ol.TARGET_SECONDS)
    assert "unchanged_run" not in item
    assert "last_content" not in item


def test_repeated_identical_samples_back_off_to_the_cap():
    item = _item()
    t = T0
    steps = []
    for _ in range(8):
        ol.record_frame(item, t, t, content=A)
        steps.append(int((item["next_due_at"] - t).total_seconds()))
        t = item["next_due_at"]
    # run 0,1,2 -> 15 ; run 3,4,5 -> 30 ; run 6+ -> 60 (the cap)
    assert steps == [15, 15, 15, 30, 30, 30, 60, 60], steps
    assert max(steps) == 60, "must be capped"
    assert item["unchanged_run"] == 7


def test_any_real_change_resets_the_cadence_immediately():
    item = _item()
    t = T0
    last_gap = None
    for _ in range(7):                      # drive it to the cap
        ol.record_frame(item, t, t, content=A)
        last_gap = int((item["next_due_at"] - t).total_seconds())
        t = item["next_due_at"]
    assert last_gap == 60
    ol.record_frame(item, t, t, content=B)   # price moved
    assert item["unchanged_run"] == 0
    assert item["next_due_at"] == t + timedelta(seconds=ol.TARGET_SECONDS)


def test_volume_only_and_liquidity_only_changes_are_information():
    """A volume-only change is 3.2% of samples and must NOT be treated as 'nothing happened'."""
    for moved in (C, D):
        item = _item()
        t = T0
        for _ in range(7):
            ol.record_frame(item, t, t, content=A)
            t = item["next_due_at"]
        assert item["unchanged_run"] >= 6
        ol.record_frame(item, t, t, content=moved)
        assert item["unchanged_run"] == 0, moved
        assert item["next_due_at"] == t + timedelta(seconds=ol.TARGET_SECONDS)


def test_cadence_is_capped_so_detection_delay_is_bounded():
    """Worst case for a genuinely new move is one interval, never the whole lease."""
    assert max(ol.CADENCE_STEPS) == 60
    assert ol.cadence_for_run(0) == 15
    assert ol.cadence_for_run(3) == 30
    assert ol.cadence_for_run(6) == 60
    assert ol.cadence_for_run(1000) == 60


def test_the_counter_survives_a_checkpoint_and_restore():
    item = _item()
    t = T0
    for _ in range(7):
        ol.record_frame(item, t, t, content=A)
        t = item["next_due_at"]
    item.update(token_id="bsc:0xabc", chain="bsc", pair_address="0xabc",
                admitted_at=T0, min_observe_until=T0 + timedelta(seconds=300))
    payload = ol.dump_state({"bsc:0xabc": item}, T0 + timedelta(seconds=1))
    row = payload["leases"][0]
    # `run` counts REPEATS after the first sighting, so 7 records leave run == 6.
    assert row["unchanged_run"] == 6
    # `last_content` is deliberately not persisted: after restore the run restarts at 0, which
    # is the conservative direction (poll fast until the source proves it is quiet again).
    assert "last_content" not in row
    restored = ol.restore_state(payload, T0 + timedelta(seconds=1))
    lease = restored[("bsc:0xabc", "bsc", "0xabc")]
    assert lease["unchanged_run"] == 6


def test_status_surface_reports_the_cadence():
    item = _item()
    t = T0
    for _ in range(4):
        ol.record_frame(item, t, t, content=A)
        t = item["next_due_at"]
    item.update(token_id="bsc:0xabc", chain="bsc", pair_address="0xabc", admitted_at=T0)
    summary = ol.bounded_summary({"bsc:0xabc": item}, T0 + timedelta(seconds=1))
    row = summary["opportunities"][0]
    assert row["unchanged_run"] == 3
    assert row["cadence_seconds"] == 30
    assert row["content_known"] is True


def test_a_quiet_pool_is_visited_less_often_over_a_lease():
    """The whole point: the same lease window costs fewer requests when nothing changes."""
    item = _item()
    t = T0
    polls = 0
    end = T0 + timedelta(seconds=300)
    while t < end:
        ol.record_frame(item, t, t, content=A)
        t = item["next_due_at"]
        polls += 1
    fixed = 300 // ol.TARGET_SECONDS
    assert polls < fixed, (polls, fixed)
    assert polls <= 20, polls
