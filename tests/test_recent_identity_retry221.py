from datetime import timedelta

from memetrader.models import utcnow
from memetrader.store import Store


def test_recent_identity_receipt_gets_one_bounded_retry_slot(tmp_path):
    store = Store(tmp_path / "recent-identity.sqlite3")
    now = utcnow()
    try:
        store.enqueue_token_detail_hydration(
            "solana", "identity-only", enqueued_at=now - timedelta(minutes=20)
        )
        store.mark_token_detail_hydration(
            "solana:identity-only", "no_pair", now=now - timedelta(minutes=10)
        )
        for index in range(12):
            store.enqueue_token_detail_hydration(
                "solana", f"fresh-{index}", enqueued_at=now
            )

        def due():
            return store.due_token_detail_hydrations(
                limit=10, now=now, chains=("solana",),
                prefer_fresh=True, retry_limit=3,
            )

        assert all(row["status"] == "pending" for row in due())
        round_id = store.start_token_discovery_round(
            provider="dexscreener", surface="token_profiles",
            mode="identity", chain_scope="solana",
            started_at=now - timedelta(minutes=1),
        )
        store.add_token_discovery_exposure(
            round_id, token_id="solana:identity-only", chain="solana",
            role="identity", observed_at=now - timedelta(minutes=1),
        )
        selected = due()
        assert len(selected) == 10
        assert sum(row["status"] == "no_pair" for row in selected) == 1
        assert any(row["token_id"] == "solana:identity-only" for row in selected)
        assert store.token_detail_hydration("solana:identity-only")["status"] == "no_pair"
    finally:
        store.close()
