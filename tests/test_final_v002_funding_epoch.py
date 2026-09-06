from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from solders.pubkey import Pubkey

from memetrader.capital_policies import second_discussion_policies
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.runtime import Runtime
from memetrader.store import Store
from test_funding_epoch import _snapshot


def test_final_v002_preserves_both_periods_history_cash_and_carried_positions(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    source = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    reviewed = Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION
    final = Store.CHAIN_MEME_TRADER_FINAL_V002_PERIOD_VERSION
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", source)
    store = Store(tmp_path / "final-v002.sqlite3")
    try:
        store.activate_chain_meme_trader_funded_period()
        addition_arm = "event_reawakening_v1"
        addition = next(p for p in second_discussion_policies() if p["arm_id"] == addition_arm)
        store.append_chain_meme_trader_policy(addition, activated_at=clock[0])

        def add_market_token(label):
            clock[0] += timedelta(seconds=1)
            token = TokenCandidate("solana", str(Pubkey.new_unique()), label, label, source="fixture")
            store.upsert_token(token, seen_at=clock[0])
            snapshot_id = store.add_snapshot(_snapshot(token, str(Pubkey.new_unique()), clock[0]))
            return token, snapshot_id

        frozen = {}
        old_tokens = []
        for version in (source, reviewed):
            monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", version)
            if version == reviewed:
                clock[0] += timedelta(seconds=1)
                store.activate_chain_meme_trader_funded_period()
            token, frontier = add_market_token(version.rsplit("/", 1)[-1])
            old_tokens.append(token.token_id)
            store.enroll_chain_meme_trader_v6(definition_version=version)
            trades = [tuple(row) for row in store.db.execute(
                "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? ORDER BY id", (version,))]
            positions = [tuple(row) for row in store.db.execute(
                "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? ORDER BY arm_id,shadow_cohort_id", (version,))]
            assert trades and positions and store.chain_meme_trader_has_open_positions(version)
            frozen[version] = {
                "definition": store._chain_meme_trader_registration(version)["definition_json"],
                "additions": [tuple(row) for row in store.db.execute(
                    "SELECT * FROM chain_meme_trader_policy_additions WHERE definition_version=? ORDER BY id", (version,))],
                "trades": trades, "positions": positions,
            }

        clock[0] += timedelta(seconds=1)
        monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", final)
        activation = dict(store.activate_chain_meme_trader_funded_period())
        assert activation["activated_at"] == iso(clock[0])
        assert activation["activation_snapshot_id"] == frontier
        registration = store._chain_meme_trader_registration(final)["definition_json"]
        definition = store._chain_meme_trader_effective_definition(final, registration)
        prior_definition = store._chain_meme_trader_effective_definition(reviewed, frozen[reviewed]["definition"])
        assert definition["funding_source_version"] == source
        assert definition["previous_version"] == reviewed
        assert {p["arm_id"] for p in definition["policies"]} == {p["arm_id"] for p in prior_definition["policies"]}
        for arm in ("canonical-1c2ac45bb5154011", addition_arm):
            previous = next(p for p in prior_definition["policies"] if p["arm_id"] == arm)
            current = next(p for p in definition["policies"] if p["arm_id"] == arm)
            assert current["strategy_revision"] == previous["strategy_revision"] == 2
            assert current["revision_history"][:-1] == previous["revision_history"]
            assert [h["revision"] for h in current["revision_history"]][-2:] == [2, 2]
            assert current["revision_history"][-1]["previous_period_version"] == reviewed
            assert current["revision_history"][-1]["changed_at"] == activation["activated_at"]
        assert all(p["forward_started_at"] == activation["activated_at"]
                   and p["forward_activation_snapshot_id"] == frontier for p in definition["policies"])
        assert store._chain_meme_trader_effective_net_flows(final) == {}
        assert store.record_chain_meme_trader_account_snapshots(definition_version=final) == len(definition["policies"])
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_account_snapshots WHERE definition_version=? AND cash_usd=1000", (final,)
        ).fetchone()[0] == len(definition["policies"])
        for table in ("chain_meme_trader_trades", "chain_meme_trader_positions"):
            assert store.db.execute(f"SELECT COUNT(*) FROM {table} WHERE definition_version=?", (final,)).fetchone()[0] == 0

        runtime = Runtime.__new__(Runtime)
        runtime.store = store
        refreshed = []

        async def refresh(targets, **kwargs):
            refreshed.append((targets, kwargs))
            return 0

        runtime._refresh_chain_meme_market_marks = refresh
        asyncio.run(runtime.chain_meme_carried_market_marks_once())
        assert set(runtime._chain_carry_versions) == {source, reviewed}
        assert set(refreshed[0][1]["evaluate_versions"]) == {source, reviewed}
        assert set(old_tokens) <= {item["token_id"] for item in refreshed[0][0]}

        # The old periods remain readable and must refuse new entry even if called explicitly.
        add_market_token("after-final")
        for version in (source, reviewed):
            assert store.db.execute(
                "SELECT 1 FROM chain_meme_trader_primary_stops WHERE definition_version=?", (version,)).fetchone()
            store.enroll_chain_meme_trader_v6(definition_version=version)
            assert store._chain_meme_trader_registration(version)["definition_json"] == frozen[version]["definition"]
            for key, table, order in (
                ("additions", "chain_meme_trader_policy_additions", "id"),
                ("trades", "chain_meme_trader_trades", "id"),
                ("positions", "chain_meme_trader_positions", "arm_id,shadow_cohort_id"),
            ):
                assert [tuple(row) for row in store.db.execute(
                    f"SELECT * FROM {table} WHERE definition_version=? ORDER BY {order}", (version,))] == frozen[version][key]

        # Re-activation must preserve actual spending, not merely an empty new ledger.
        store.enroll_chain_meme_trader_v6(definition_version=final)
        spent = store._chain_meme_trader_effective_net_flows(final)
        assert spent and any(value < 0 for value in spent.values())
        clock[0] += timedelta(seconds=1)
        repeated = dict(store.activate_chain_meme_trader_funded_period())
        assert repeated == activation
        assert store._chain_meme_trader_registration(final)["definition_json"] == registration
        assert store._chain_meme_trader_effective_net_flows(final) == spent
        assert json.loads(registration)["starting_cash_usd_each_arm"] == 1000
    finally:
        store.close()
