import asyncio
from datetime import timedelta
from types import SimpleNamespace

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, utcnow, iso
from memetrader.runtime import Runtime, initial_config
from memetrader.store import Store


def test_pregrad_reorders_existing_budget_migration_requeues_once_and_new_rpc_receipt(tmp_path, monkeypatch):
    async def run():
        clock = [utcnow()]
        monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
        monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
        monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
        r = Runtime.__new__(Runtime)
        r.config = initial_config()
        r.chain_meme_trader_only = True
        r.store = Store(tmp_path / "pregrad-runtime.sqlite3", initial_cash_usd=1000)
        r.store.activate_chain_meme_trader_funded_period()
        r.notifier = SimpleNamespace(send=lambda *a, **kw: None)
        ordinary = TokenCandidate("solana", str(Pubkey.new_unique()), "ordinary")
        r.store.upsert_token(ordinary)
        r.store.enqueue_token_detail_hydration(ordinary.chain, ordinary.address)
        clock[0] += timedelta(seconds=1)
        token = TokenCandidate("solana", str(Pubkey.new_unique()), "pregrad", source="pumpportal:create",
                               first_seen_at=clock[0], raw={"txType": "create", "solAmount": 2})
        await r.ingest_token(token)
        assert len(r._pregrad_watch.targets(now=clock[0])) == 1
        due = r.store.due_token_detail_hydrations(limit=1, now=clock[0], priority_token_ids=[token.token_id])
        assert len(due) == 1 and due[0]["token_id"] == token.token_id
        r.store.mark_token_detail_hydration(token.token_id, "hydrated", now=clock[0])
        assert not r.store.due_token_detail_hydrations(limit=2, now=clock[0], chains=["bsc"])

        async def curves(targets):
            clock[0] += timedelta(seconds=1)  # A genuine response cannot use request-start as its decision time.
            return [{**targets[0], "status": "verified", "identity_verified": True,
                     "slot": 100, "observed_at": iso(clock[0]), "recorded_at": iso(clock[0]),
                     "real_quote_reserves_raw": 1000000000, "curve_complete": False}]
        r.held_accounts = SimpleNamespace(bonding_curve_observations=curves)
        await r.pregrad_watch_once()
        count = r.store.db.execute("SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE kind='pregrad_watch'").fetchone()[0]
        assert count == 2
        clock[0] += timedelta(seconds=1)
        migration = TokenCandidate("solana", token.address, "migrated", source="pumpportal:migration",
                                   first_seen_at=clock[0], raw={"txType": "migration", "signature": "new-migration"})
        await r.ingest_token(migration)
        assert r.store.db.execute("SELECT status FROM token_detail_hydration WHERE token_id=?", (token.token_id,)).fetchone()[0] == "pending"
        r.store.mark_token_detail_hydration(token.token_id, "hydrated", now=clock[0])
        await r.ingest_token(migration)
        assert r.store.db.execute("SELECT status FROM token_detail_hydration WHERE token_id=?", (token.token_id,)).fetchone()[0] == "hydrated"
        assert not r._pregrad_watch.targets(now=clock[0])
        assert r.store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades").fetchone()[0] == 0
        r.store.close()
    asyncio.run(run())
