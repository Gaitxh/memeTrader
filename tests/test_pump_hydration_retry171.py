from datetime import timedelta

from memetrader import models
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store


def test_recent_pump_create_uses_bounded_fast_no_pair_retries(tmp_path):
    store = Store(tmp_path / "pump-retry.sqlite3")
    now = utcnow()
    token = TokenCandidate(
        "solana",
        "RecentPumpMint1111111111111111111111111pump",
        "Recent Pump",
        source="pumpportal:create",
        first_seen_at=now,
        raw={"pump_event_type": "create", "signature": "recent-pump-create"},
    )
    store.record_token_launch_fact(token, ingested_at=now)
    store.upsert_token(token, seen_at=now)
    store.enqueue_token_detail_hydration(token.chain, token.address, enqueued_at=now)

    attempted_at = now
    for expected_seconds in (90, 210, 1800):
        store.mark_token_detail_hydration(token.token_id, "no_pair", now=attempted_at)
        row = store.token_detail_hydration(token.token_id)
        assert row["next_attempt_at"] == iso(
            attempted_at + timedelta(seconds=expected_seconds)
        )
        attempted_at += timedelta(seconds=expected_seconds)

    store.close()


def test_generic_and_old_pump_no_pair_keep_conservative_retry(tmp_path, monkeypatch):
    store = Store(tmp_path / "generic-retry.sqlite3")
    now = utcnow()
    generic = TokenCandidate("solana", "GenericMint111111111111111111111111111", "Generic")
    old_pump = TokenCandidate(
        "solana",
        "OldPumpMint111111111111111111111111111pump",
        "Old Pump",
        source="pumpportal:create",
        first_seen_at=now - timedelta(minutes=20),
        raw={"pump_event_type": "create", "signature": "old-pump-create"},
    )
    for token, enqueued_at in (
        (generic, now),
        (old_pump, now - timedelta(minutes=20)),
    ):
        if token is old_pump:
            original_utcnow = models.utcnow
            monkeypatch.setattr(models, "utcnow", lambda: enqueued_at)
            store.record_token_launch_fact(token, ingested_at=enqueued_at)
            monkeypatch.setattr(models, "utcnow", original_utcnow)
        store.upsert_token(token, seen_at=enqueued_at)
        store.enqueue_token_detail_hydration(
            token.chain, token.address, enqueued_at=enqueued_at
        )
        store.mark_token_detail_hydration(token.token_id, "no_pair", now=now)
        assert store.token_detail_hydration(token.token_id)["next_attempt_at"] == iso(
            now + timedelta(minutes=5)
        )

    store.close()


def test_recent_bonk_create_does_not_use_pump_short_probe(tmp_path):
    store = Store(tmp_path / "bonk-retry.sqlite3")
    now = utcnow()
    token = TokenCandidate(
        "solana",
        "RecentBonkMint111111111111111111111111111",
        "Recent Bonk",
        source="pumpportal:create",
        first_seen_at=now,
        raw={
            "pump_event_type": "create",
            "pool": "bonk",
            "signature": "recent-bonk-create",
        },
    )
    store.record_token_launch_fact(token, ingested_at=now)
    store.upsert_token(token, seen_at=now)
    store.enqueue_token_detail_hydration(token.chain, token.address, enqueued_at=now)
    store.mark_token_detail_hydration(token.token_id, "no_pair", now=now)

    assert store.token_detail_hydration(token.token_id)["next_attempt_at"] == iso(
        now + timedelta(minutes=5)
    )
    store.close()
