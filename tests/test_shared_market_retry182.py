from datetime import timedelta

from memetrader.models import TokenCandidate, utcnow
from memetrader.store import Store


def test_historical_no_pair_rows_cannot_fill_the_shared_first_quote_lane(tmp_path):
    store = Store(tmp_path / "retry-lane.sqlite3")
    now = utcnow()
    for index in range(12):
        address = f"old-{index}"
        store.enqueue_token_detail_hydration(
            "solana", address, enqueued_at=now - timedelta(hours=2)
        )
        store.mark_token_detail_hydration(
            f"solana:{address}", "no_pair", now=now - timedelta(minutes=10)
        )
    for index in range(2):
        store.enqueue_token_detail_hydration("solana", f"new-{index}", enqueued_at=now)

    fast_lane = store.due_token_detail_hydrations(
        limit=30, now=now, chains=("solana",), prefer_fresh=True, retry_limit=0,
    )
    assert [row["status"] for row in fast_lane] == ["pending", "pending"]

    recovery_lane = store.due_token_detail_hydrations(
        limit=30, now=now, chains=("solana",), prefer_fresh=True, retry_limit=3,
    )
    assert [row["status"] for row in recovery_lane].count("pending") == 2
    assert [row["status"] for row in recovery_lane].count("no_pair") == 3
    store.close()


def test_lifecycle_followup_uses_spare_before_generic_retry(tmp_path):
    store = Store(tmp_path / "lane-order.sqlite3")
    now = utcnow()
    store.enqueue_token_detail_hydration("bsc", "fresh", enqueued_at=now)

    store.enqueue_token_detail_hydration(
        "bsc", "followup", enqueued_at=now - timedelta(minutes=20)
    )
    store.mark_token_detail_hydration(
        "bsc:followup", "hydrated", now=now - timedelta(minutes=10),
        refresh_at=now - timedelta(minutes=1),
        followup_until=now + timedelta(minutes=40),
    )

    store.enqueue_token_detail_hydration(
        "bsc", "old-missing", enqueued_at=now - timedelta(hours=2)
    )
    store.mark_token_detail_hydration(
        "bsc:old-missing", "no_pair", now=now - timedelta(minutes=10)
    )

    selected = store.due_token_detail_hydrations(
        limit=2, now=now, chains=("bsc",), followup_limit=2, retry_limit=3,
    )
    assert [row["token_id"] for row in selected] == ["bsc:fresh", "bsc:followup"]
    store.close()


def test_valid_followups_precede_bounded_lifecycle_missing_retries(tmp_path):
    store = Store(tmp_path / "lifecycle-lanes.sqlite3")
    now = utcnow()
    for index in range(3):
        store.enqueue_token_detail_hydration("solana", f"fresh-{index}", enqueued_at=now)
    for index in range(2):
        token_id = f"solana:valid-{index}"
        store.enqueue_token_detail_hydration(
            "solana", f"valid-{index}", enqueued_at=now - timedelta(minutes=20)
        )
        store.mark_token_detail_hydration(
            token_id, "hydrated", now=now - timedelta(minutes=10),
            refresh_at=now - timedelta(minutes=1),
            followup_until=now + timedelta(minutes=40),
        )
    for index in range(5):
        token_id = f"solana:missing-{index}"
        store.enqueue_token_detail_hydration(
            "solana", f"missing-{index}", enqueued_at=now - timedelta(minutes=20)
        )
        store.mark_token_detail_hydration(
            token_id, "hydrated", now=now - timedelta(minutes=10),
            refresh_at=now - timedelta(minutes=2),
            followup_until=now + timedelta(minutes=40),
        )
        store.mark_token_detail_hydration(
            token_id, "no_pair", now=now - timedelta(minutes=6),
        )

    saturated = store.due_token_detail_hydrations(
        limit=5, now=now, chains=("solana",), followup_limit=2,
        followup_retry_limit=2, retry_limit=0,
    )
    assert [row["status"] for row in saturated].count("pending") == 3
    assert [row["status"] for row in saturated].count("hydrated") == 2
    assert [row["status"] for row in saturated].count("no_pair") == 0

    for row in saturated:
        if row["status"] == "pending":
            store.mark_token_detail_hydration(row["token_id"], "error", now=now)
    retry_spare = store.due_token_detail_hydrations(
        limit=4, now=now, chains=("solana",), followup_limit=2,
        followup_retry_limit=2, retry_limit=0,
    )
    assert [row["status"] for row in retry_spare].count("hydrated") == 2
    assert [row["status"] for row in retry_spare].count("no_pair") == 2
    store.close()


def test_recent_pump_no_pair_retry_survives_saturated_fresh_lane(tmp_path):
    store = Store(tmp_path / "pump-retry.sqlite3")
    now = utcnow()
    token = TokenCandidate(
        chain="solana", address="P" * 32, name="Pump create",
        source="pumpportal:create", first_seen_at=now,
    )
    store.enqueue_token_detail_hydration("solana", token.address, enqueued_at=now)
    assert store.record_token_launch_fact(token, observed_at=now, ingested_at=now)
    first_attempt = now + timedelta(seconds=1)
    store.mark_token_detail_hydration(token.token_id, "no_pair", now=first_attempt)
    for index in range(6):
        store.enqueue_token_detail_hydration(
            "solana", f"fresh-{index}", enqueued_at=now + timedelta(seconds=2),
        )

    before_due = store.due_token_detail_hydrations(
        limit=4, now=first_attempt + timedelta(seconds=89),
        chains=("solana",), prefer_fresh=True, retry_limit=0,
    )
    assert all(row["status"] == "pending" for row in before_due)
    at_due = store.due_token_detail_hydrations(
        limit=4, now=first_attempt + timedelta(seconds=90),
        chains=("solana",), prefer_fresh=True, retry_limit=0,
    )
    assert len(at_due) == 4
    assert [row["token_id"] for row in at_due].count(token.token_id) == 1
    assert sum(row["status"] == "pending" for row in at_due) == 3

    store.mark_token_detail_hydration(
        token.token_id, "no_pair", now=first_attempt + timedelta(seconds=90),
    )
    second_due = store.due_token_detail_hydrations(
        limit=4, now=first_attempt + timedelta(seconds=300),
        chains=("solana",), prefer_fresh=True, retry_limit=0,
    )
    assert [row["token_id"] for row in second_due].count(token.token_id) == 1
    store.close()
