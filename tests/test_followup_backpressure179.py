from datetime import timedelta

from memetrader.models import iso, utcnow
from memetrader.store import Store


def _schedule(store, token_id, now, *, due_minutes, deadline_minutes):
    chain, address = token_id.split(":", 1)
    store.enqueue_token_detail_hydration(
        chain, address, enqueued_at=now - timedelta(hours=2)
    )
    store.mark_token_detail_hydration(
        token_id,
        "hydrated",
        now=now - timedelta(hours=1),
        refresh_at=now - timedelta(minutes=due_minutes),
        followup_until=now + timedelta(minutes=deadline_minutes),
    )


def test_followup_selection_protects_urgent_deadline_then_drains_oldest_due(tmp_path):
    store = Store(tmp_path / "followup-order.sqlite3")
    now = utcnow()
    _schedule(store, "solana:urgent", now, due_minutes=1, deadline_minutes=10)
    _schedule(store, "bsc:oldest", now, due_minutes=60, deadline_minutes=180)
    _schedule(store, "robinhood:newer", now, due_minutes=5, deadline_minutes=30)

    selected = store.due_token_detail_hydrations(
        limit=3,
        now=now,
        chains=("bsc", "solana", "robinhood"),
        followup_limit=3,
    )

    assert [row["token_id"] for row in selected] == [
        "solana:urgent",
        "bsc:oldest",
        "robinhood:newer",
    ]
    store.close()


def test_consecutive_lifecycle_no_pair_uses_bounded_fifteen_minute_backoff(tmp_path):
    store = Store(tmp_path / "followup-backoff.sqlite3")
    now = utcnow()
    token_id = "robinhood:missing"
    _schedule(store, token_id, now, due_minutes=1, deadline_minutes=180)

    store.mark_token_detail_hydration(token_id, "no_pair", now=now)
    first = store.token_detail_hydration(token_id)
    assert first["next_attempt_at"] == iso(now + timedelta(minutes=5))

    second_at = now + timedelta(minutes=5)
    store.mark_token_detail_hydration(token_id, "no_pair", now=second_at)
    second = store.token_detail_hydration(token_id)
    assert second["next_attempt_at"] == iso(second_at + timedelta(minutes=15))
    assert second["followup_until"] == first["followup_until"]
    store.close()
