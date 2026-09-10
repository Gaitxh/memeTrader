from datetime import datetime, timedelta, timezone
import json

from memetrader.observation_leases145 import (
    admit, bounded_summary, dump_state, expire_windows, membership, record_frame,
    replaceable_early, restore_state, select_due,
)


UTC = timezone.utc


def item(chain="solana", bucket="early", created=0):
    return {"chain": chain, "bucket": bucket, "pair_address": "pool-" + str(created),
            "pool_created_at_ms": created}


def test_lease_membership_protection_and_stable_due_order():
    now = datetime(2026, 9, 11, tzinfo=UTC)
    watch = {"b": admit(item(created=(now - timedelta(seconds=300)).timestamp() * 1000), now),
             "a": admit(item(created=(now - timedelta(seconds=500)).timestamp() * 1000), now)}
    watch["a"]["next_due_at"] = now - timedelta(seconds=4)
    watch["b"]["next_due_at"] = now - timedelta(seconds=4)
    assert [token_id for token_id, _ in select_due(watch, now)] == ["a", "b"]
    # Protection prevents eviction, not a due observation of pending/ready work.
    assert select_due(watch, now, protected={"a"})[0][0] == "a"
    watch["seat-early"] = item(bucket="early", created=0)
    for index in range(7):
        watch["seat-" + str(index)] = item(bucket="growth" if index < 4 else "mature", created=index)
    seats = membership({**watch, "held": item(created=1)}, held={"held"})
    assert seats["chains"]["solana"] == {"total": 10, "buckets": {"early": 3, "growth": 4, "mature": 3}}
    assert seats["chains"]["solana"]["total"] == seats["chain_cap"]


def test_completed_stale_early_lease_only_yields_to_younger_candidate():
    now = datetime(2026, 9, 11, tzinfo=UTC)
    old = admit(item(created=(now - timedelta(seconds=700)).timestamp() * 1000), now - timedelta(seconds=121))
    old["last_useful_at"] = now - timedelta(seconds=31)
    younger = item(created=(now - timedelta(seconds=100)).timestamp() * 1000)
    assert replaceable_early({"old": old}, "new", younger, now) == "old"
    assert replaceable_early({"old": old}, "new", younger, now, protected={"old"}) is None
    # A quiet fresh quote is not a signal lease: genuine ready/pending state is
    # carried through `protected`, so the same candidate may rotate after 120s.
    old["last_useful_at"] = now - timedelta(seconds=10)
    assert replaceable_early({"old": old}, "new", younger, now) == "old"


def test_phase_transition_frames_windows_and_bounded_json_state():
    now = datetime(2026, 9, 11, tzinfo=UTC)
    watched = admit(item(created=1), now)
    assert record_frame(watched, now + timedelta(seconds=10), now + timedelta(seconds=10),
                        phase="impulse", phase_started_at=now + timedelta(seconds=10))
    first_until = watched["min_observe_until"]
    assert first_until == now + timedelta(seconds=310)
    assert record_frame(watched, now + timedelta(seconds=20), now + timedelta(seconds=20),
                        phase="impulse", phase_started_at=now + timedelta(seconds=20))
    assert watched["min_observe_until"] == first_until
    assert record_frame(watched, now + timedelta(seconds=30), now + timedelta(seconds=30),
                        phase="cool", phase_started_at=now + timedelta(seconds=30))
    assert watched["min_observe_until"] == now + timedelta(seconds=330)
    assert watched["frame2_delay_seconds"] == 20
    assert watched["frame3_delay_seconds"] == 30
    assert expire_windows(watched, now + timedelta(seconds=121)) == [30, 120]
    assert expire_windows(watched, now + timedelta(seconds=121)) == []
    assert expire_windows(watched, now + timedelta(seconds=301)) == [300]
    assert expire_windows(watched, now + timedelta(seconds=301)) == []
    summary = bounded_summary({"x": watched}, now + timedelta(seconds=301), limit=1)
    json.dumps(summary)
    assert summary["opportunities"][0]["expired_windows"] == [30, 120, 300]


def test_restore_only_preserves_unexpired_identity_and_lease_never_quote():
    now = datetime(2026, 9, 11, tzinfo=UTC)
    fresh = admit(item(created=1), now)
    fresh["quote"] = object()
    expired = admit(item(created=2), now - timedelta(seconds=121))
    payload = dump_state({"fresh": fresh, "expired": expired}, now)
    assert len(payload["leases"]) == 1
    assert "quote" not in payload["leases"][0]
    restored = restore_state(json.loads(json.dumps(payload)), now)
    lease = restored[("fresh", "solana", "pool-1")]
    assert lease["min_observe_until"] == fresh["min_observe_until"]
    assert restore_state(payload, now + timedelta(seconds=121)) == {}
