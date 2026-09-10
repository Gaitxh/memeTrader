import asyncio
from datetime import timedelta
from types import SimpleNamespace

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, utcnow, iso
from memetrader.runtime import Runtime, initial_config
from memetrader.store import Store


def test_native_cash_dispatch_is_idle_bounded_persistent_and_unfunded(tmp_path,monkeypatch):
    from test_pump_native import sample,fixed137,fee137
    async def run():
        now,frame,ref=sample();frame.update(token_id='solana:'+str(Pubkey.new_unique()),
            curve_address=str(Pubkey.new_unique()),curve_state=fixed137(),fee_config=fee137(),
            mint_slot=frame['slot'],mint_state=dict(status='verified',native_layout_verified=True,
                mint_authority=None,freeze_authority=None,decimals=6,supply_raw=10**15,initialized=True))
        r=Runtime.__new__(Runtime);r.store=Store(tmp_path/'native-dispatch.sqlite3',initial_cash_usd=1000)
        r._wsol_usdc_conversion=ref;r.held_accounts=object()
        idle=asyncio.Event();monkeypatch.setattr(r,'_chain_meme_active_idle',lambda:idle)
        calls=[]
        async def assemble(*args):calls.append(args);return dict(recorded_at=iso(utcnow()),fees={})
        monkeypatch.setattr('memetrader.pump_native_cash.assemble',assemble)
        trigger=dict(status='TRIGGER_FROZEN',slot=9,recorded_at=iso(now-timedelta(seconds=2)))
        r._dispatch_native_cash137(frame,trigger)
        assert not hasattr(r,'_native_cash137_task') and not calls
        trigger.update(status='REQUOTED_SHADOW',requote_slot=frame['slot'],requote_recorded_at=frame['recorded_at'])
        r._dispatch_native_cash137(frame,trigger);task=r._native_cash137_task
        await asyncio.sleep(0);assert not calls
        r._dispatch_native_cash137(frame,trigger);assert r._native_cash137_task is task
        idle.set();await task;assert len(calls)==1
        del r._native_cash137_task  # Restart dedup uses persisted claim, not task object.
        r._dispatch_native_cash137(frame,trigger);assert not hasattr(r,'_native_cash137_task')
        assert r.store.db.execute('SELECT count(*) FROM chain_meme_trader_trades').fetchone()[0]==0
        assert r.store.db.execute("SELECT count(*) FROM chain_meme_pattern_evidence WHERE kind='native_cash_plan137'").fetchone()[0]==1
        import json
        payload=json.loads(r.store.db.execute("SELECT payload_json FROM chain_meme_pattern_evidence WHERE kind='native_cash_plan137'").fetchone()[0])
        assert payload['execution_frame']['slot']==frame['slot']
        assert payload['native_ledger_required'] and not payload['decision_eligible']
        r.store.close()
    asyncio.run(run())


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


def test_unwatched_old_mint_fresh_migration_gets_one_existing_hydration_slot(tmp_path, monkeypatch):
    async def run():
        clock = [utcnow() - timedelta(days=1)]
        monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
        monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
        monkeypatch.setattr("memetrader.runtime.utcnow", lambda: clock[0])
        r = Runtime.__new__(Runtime)
        r.config = initial_config()
        r.chain_meme_trader_only = True
        r.store = Store(tmp_path / "migration-priority.sqlite3", initial_cash_usd=1000)
        r.notifier = SimpleNamespace(send=lambda *a, **kw: None)
        old = TokenCandidate("solana", str(Pubkey.new_unique()), "old")
        r.store.upsert_token(old)
        r.store.mark_token_detail_hydration(old.token_id, "no_pair", now=clock[0])
        clock[0] += timedelta(days=1)
        new = TokenCandidate("solana", str(Pubkey.new_unique()), "new")
        r.store.upsert_token(new)
        migration = TokenCandidate("solana", old.address, "migrated", source="pumpportal:migration",
                                   first_seen_at=clock[0], raw={"txType": "migration", "signature": "fresh"})
        await r.ingest_token(migration)
        assert not r._pregrad_watch.ranked(now=clock[0])
        due = lambda: r.store.due_token_detail_hydrations(limit=1, now=clock[0], prefer_fresh=True)
        assert due()[0]["token_id"] == old.token_id
        clock[0] += timedelta(seconds=1)
        r.store.mark_token_detail_hydration(old.token_id, "no_pair", now=clock[0])
        await r.ingest_token(migration)
        assert r.store.token_detail_hydration(old.token_id)["status"] == "no_pair"
        assert due()[0]["token_id"] == new.token_id  # Attempt and replay preserve normal backoff.
        clock[0] += timedelta(seconds=31)
        r.store.requeue_token_detail_hydration(old.token_id, enqueued_at=clock[0])
        assert due()[0]["token_id"] == new.token_id  # Ordinary requeue does not refresh the old migration.
        r.store.close()
    asyncio.run(run())
