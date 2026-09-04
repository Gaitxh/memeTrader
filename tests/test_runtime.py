import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import tempfile
import urllib.parse
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from memetrader.cli import cmd_doctor
from memetrader.collectors import JupiterNoRouteError, JupiterQuoteProtocolError
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import (
    Notifier,
    Runtime,
    SingleInstance,
    _reverse_news_matches_token,
    initial_config,
    load_config,
)
from memetrader.store import Store


def test_superseded_confirmation_paper_has_no_runtime_execution_entrypoint():
    assert not hasattr(Runtime, "token_information_confirmation_entry_once")


def test_initial_config_has_private_token_and_live_locked():
    config = initial_config()
    assert len(config["bridge"]["token"]) >= 24
    assert config["mode"] == "paper"
    assert config["agent"]["enabled"] is False
    assert config["live"]["enabled"] is False
    assert config["sources"]["gecko_networks"] == ["solana"]
    assert config["sources"]["multichain_meme_data"]["chains"] == [
        "solana", "bsc", "robinhood",
    ]
    assert config["sources"]["dexscreener_discovery"]["chains"] == [
        "solana",
    ]
    assert config["sources"]["dexscreener_discovery"]["surface_chains"] == [
        "solana",
    ]
    assert config["candidate"]["chains"] == ["solana"]
    assert config["safety"]["require_evm_security_report"] is True
    assert config["safety"]["require_evm_simulation"] is False
    assert config["safety"]["require_solana_report"] is True
    assert config["paper"]["slippage_rate"] == pytest.approx(0.04)
    assert config["paper"]["fixed_position_usd"] == pytest.approx(20)
    assert config["paper"]["fixed_fee_usd_each_side"] == pytest.approx(0.4)
    assert config["paper"]["fee_bps"] == pytest.approx(60)
    assert config["paper"]["pump_swap_fee_bps"] == pytest.approx(125)


def test_chain_only_runtime_registers_and_activates_current_v22(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        runtime = Runtime(config, tmp_path)
        active = runtime.store.db.execute(
            "SELECT definition_version FROM chain_meme_trader_v6_activations "
            "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        registration = runtime.store.db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (Store.CHAIN_MEME_TRADER_V22_VERSION,),
        ).fetchone()
        assert active["definition_version"] == Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        assert active["definition_version"] == Store.CHAIN_MEME_TRADER_V22_VERSION
        definition = json.loads(registration["definition_json"])
        assert len(definition["policies"]) == 127
        assert all(policy["forward_enabled"] for policy in definition["policies"])
        assert sum(
            policy.get("fidelity_status") == "DEXSCREENER_SUCCESSOR"
            for policy in definition["policies"]
        ) == 38
        assert sum(
            policy.get("fidelity_status") == "ADDITIVE_FORWARD"
            for policy in definition["policies"]
        ) == 3
        await runtime.close()

    asyncio.run(scenario())


def test_chain_only_v22_keeps_v20_positions_marked_without_new_v20_entries(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        runtime = Runtime(config, tmp_path)
        store = runtime.store
        v20 = Store.CHAIN_MEME_TRADER_V20_VERSION
        v22 = Store.CHAIN_MEME_TRADER_V22_VERSION
        definition = json.loads(store.db.execute(
            "SELECT definition_json FROM chain_meme_trader_v6_registrations "
            "WHERE definition_version=?", (v20,),
        ).fetchone()[0])
        policy = next(
            item for item in definition["policies"]
            if item.get("entry_family") == "broad_launch"
            and item.get("hard_stop_return") == -0.20
        )
        opened_at = utcnow() - timedelta(minutes=1)
        held = TokenCandidate(
            "solana", "V" * 32, "Carried v20", "V20", source="dexscreener",
        )
        store.upsert_token(held, seen_at=opened_at)
        with store.db:
            store.db.execute(
                "INSERT INTO chain_meme_trader_v6_cohorts("
                "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
                "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
                (v20, held.token_id, "broad_launch", 1, "pair-v20", iso(opened_at)),
            )
            cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
            quantity = 20.0 / 1.04
            amount_raw = str(round(quantity * 1_000_000_000))
            store.db.execute(
                "INSERT INTO chain_meme_trader_positions("
                "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
                "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
                "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
                "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
                "opened_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,20,1,'open',?)",
                (
                    v20, policy["arm_id"], cohort_id, held.token_id, cohort_id, 1, 1,
                    1.0, 1.04, quantity, quantity, amount_raw, amount_raw, iso(opened_at),
                ),
            )
            store.db.execute(
                "INSERT INTO chain_meme_trader_trades("
                "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
                "net_cash_flow_usd,reason,created_at) "
                "VALUES(?,?,?,?, 'BUY',20,-20,'fixture',?)",
                (v20, policy["arm_id"], cohort_id, held.token_id, iso(opened_at)),
            )

        targets = store.chain_meme_trader_market_mark_targets(
            definition_versions=[v22, v20],
        )
        assert [item["token_id"] for item in targets] == [held.token_id]

        async def batch_quote(chain, addresses):
            assert (chain, addresses) == ("solana", [held.address])
            observed_at = utcnow()
            return {held.token_id: (
                held,
                TokenSnapshot(
                    "solana", held.address, 0.50, 10_000, 100_000, 2_000, 4, 8,
                    observed_at=observed_at, ingested_at=observed_at,
                    provider="dexscreener",
                    raw={"pair": {"pairAddress": "pair-v20"}},
                ),
            )}

        runtime.dex.batch_quote_fresh = batch_quote
        await runtime.chain_meme_market_marks_once()
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND shadow_cohort_id=?",
            (v20, cohort_id),
        ).fetchone()[0] == 0
        await runtime.chain_meme_carried_market_marks_once()
        exit_mark = store.db.execute(
            "SELECT action,status FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND shadow_cohort_id=?",
            (v20, cohort_id),
        ).fetchone()
        assert (exit_mark["action"], exit_mark["status"]) == ("HARD_STOP", "pending")
        snapshots_before_terminal_exit = store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=?", (v20,),
        ).fetchone()[0]
        await runtime.chain_meme_carried_market_marks_once()
        terminal_snapshot = store.db.execute(
            "SELECT open_position_count,closed_position_count FROM "
            "chain_meme_trader_account_snapshots WHERE definition_version=? "
            "AND arm_id=? ORDER BY id DESC LIMIT 1",
            (v20, policy["arm_id"]),
        ).fetchone()
        assert store.db.execute(
            "SELECT status FROM chain_meme_trader_positions WHERE "
            "definition_version=? AND shadow_cohort_id=?",
            (v20, cohort_id),
        ).fetchone()["status"] == "closed"
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_account_snapshots "
            "WHERE definition_version=?", (v20,),
        ).fetchone()[0] > snapshots_before_terminal_exit
        assert (terminal_snapshot["open_position_count"], terminal_snapshot["closed_position_count"]) == (0, 1)

        entry_at = utcnow()
        fresh = TokenCandidate(
            "solana", "N" * 32, "Fresh v21", "V21", source="dexscreener",
        )
        store.upsert_token(fresh, seen_at=entry_at)
        snapshot_id = store.add_snapshot(TokenSnapshot(
            "solana", fresh.address, 1.0, 10_000, 100_000, 250, 2, 1,
            observed_at=entry_at, ingested_at=entry_at, provider="dexscreener",
            raw={"pair": {
                "chainId": "solana", "dexId": "pumpfun", "pairAddress": "pair-v21",
                "pairCreatedAt": round((entry_at - timedelta(minutes=1)).timestamp() * 1000),
                "priceUsd": "1.0",
                "baseToken": {"address": fresh.address},
                "txns": {"m5": {"buys": 2, "sells": 1}, "h1": {"buys": 2, "sells": 1}},
                "volume": {"m5": 250.0, "h1": 250.0},
            }},
        ))
        runtime._last_chain_account_snapshot_monotonic = asyncio.get_running_loop().time()
        await runtime.chain_meme_trader_once()
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? AND source_snapshot_id=?", (v22, snapshot_id),
        ).fetchone()[0] == 1
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? AND source_snapshot_id=?", (v20, snapshot_id),
        ).fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_v22_vault_shadow_keeps_unresolved_pool_retry_until_due(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        runtime = Runtime(config, tmp_path)
        pool = "P" * 32
        candidate = {
            "observer_version": Store.CHAIN_MEME_V22_VAULT_SHADOW_VERSION,
            "pool_address": pool,
            "token_id": "solana:" + "M" * 32,
            "base_mint": "M" * 32,
            "first_source_cohort_id": 1,
            "entry_snapshot_id": 1,
            "opened_at": iso(utcnow()),
        }
        calls = []

        async def resolve(candidates):
            calls.append([item["pool_address"] for item in candidates])
            return [{**item, "status": "UNKNOWN_RPC", "reason": "fixture"} for item in candidates]

        runtime.store.chain_meme_v22_vault_shadow_candidates = lambda: [candidate]
        runtime.held_accounts.resolve_pumpswap_shadow_pools = resolve
        await runtime.chain_meme_v22_vault_shadow_enroll_once()
        retry_at = runtime._chain_meme_v21_vault_retry_after[pool]
        await runtime.chain_meme_v22_vault_shadow_enroll_once()
        assert calls == [[pool], []]
        assert runtime._chain_meme_v21_vault_retry_after[pool] == retry_at

        runtime._chain_meme_v21_vault_retry_after[pool] = 0.0
        await runtime.chain_meme_v22_vault_shadow_enroll_once()
        assert calls == [[pool], [], [pool]]
        await runtime.close()

    asyncio.run(scenario())


def test_event_route_execution_challenger_requests_final_size_without_paper_fill(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow() - timedelta(seconds=2)
        address = "Q" * 32
        event_id, _, _ = runtime.events.ingest(Observation(
            source="official:x", source_kind="official_social",
            title=f"Route candidate CA {address}", text=f"CA {address}",
            observed_at=now, ingested_at=now, availability_proof="local_receive",
        ))
        token = TokenCandidate("solana", address, "Route Candidate", "ROUTE")
        runtime.store.upsert_token(token, seen_at=now)
        snapshot = TokenSnapshot(
            "solana", address, 0.00001, None, 100_000, 30_000, 20, 5,
            observed_at=now, ingested_at=now, provider="dexscreener",
        )
        snapshot_id = runtime.store.add_snapshot(snapshot)
        anchor = utcnow()
        probe_id = runtime.store.start_event_context_jupiter_route_probe(
            event_id=event_id, token_id=token.token_id, source_snapshot_id=snapshot_id,
            anchor_at=anchor, input_notional_usd=35, buy_input_amount_raw=35_000_000,
            slippage_bps=400, max_total_delay_seconds=45,
        )
        runtime.store.finish_event_context_jupiter_route_probe(
            probe_id, status="valid", reason="fresh_two_way_route",
            buy_quote={
                "requested_at": iso(anchor), "completed_at": iso(anchor),
                "in_amount": "35000000", "out_amount": "2100000",
                "other_amount_threshold": "2000000",
            },
            sell_quote={
                "requested_at": iso(anchor), "completed_at": iso(anchor),
                "in_amount": "2000000", "out_amount": "33000000",
                "other_amount_threshold": "32000000",
            },
            round_trip_min_return=32 / 35 - 1, decision_eligible=True,
        )
        decision_id = runtime.store.add_decision(CandidateDecision(
            event_id=event_id, token_id=token.token_id, action="WAIT", score=90,
            match_score=95, canonical_margin=15,
            reasons=["jupiter_two_way_capacity_probe_only"],
            rejected_reasons=["route_backed_paper_execution_not_implemented"],
            position_usd=12.34, route_probe_id=probe_id, created_at=utcnow(),
        ))

        class Jupiter:
            calls = []

            async def quote(self, input_mint, output_mint, amount, *, slippage_bps):
                self.calls.append((input_mint, output_mint, amount, slippage_bps))
                requested = utcnow()
                if len(self.calls) == 1:
                    out_amount, minimum = "810000", "750000"
                else:
                    assert amount == 750000
                    out_amount, minimum = "11800000", "11700000"
                completed = utcnow()
                return {
                    "requested_at": iso(requested), "completed_at": iso(completed),
                    "input_mint": input_mint, "output_mint": output_mint,
                    "in_amount": str(amount), "out_amount": out_amount,
                    "other_amount_threshold": minimum, "slippage_bps": slippage_bps,
                    "signature_fee_lamports": 0,
                    "prioritization_fee_lamports": 0,
                    "rent_fee_lamports": 0,
                }

        runtime.jupiter = Jupiter()
        await runtime._collect_event_route_execution_challenger(
            decision_id=decision_id, event_id=event_id, token=token,
            capacity_probe_id=probe_id, baseline_snapshot_id=snapshot_id,
            position_usd=12.34, snapshot=snapshot, fee_bps=125,
        )
        assert runtime.jupiter.calls[0][2] == 12_340_000
        assert runtime.jupiter.calls[1][2] == 750_000
        row = runtime.store.db.execute(
            "SELECT * FROM event_route_execution_challenger_attempts WHERE decision_id=?",
            (decision_id,),
        ).fetchone()
        assert row["buy_input_amount_raw"] == "12340000"
        assert row["sell_input_amount_raw"] == "750000"
        assert row["quote_terminal_status"] == "quoted"
        assert row["validity_status"] == "valid"
        assert row["economic_status"] == "cost_unknown"
        assert row["paper_effect"] == "no_fill_research_only"
        assert runtime.store.open_positions() == []
        assert runtime.store.trades() == []
        assert runtime.store.account()["cash_usd"] == pytest.approx(1000)
        await runtime.close()

    asyncio.run(scenario())


def test_liquidity_survival_worker_persists_only_exact_same_pair_snapshot():
    async def scenario():
        runtime = object.__new__(Runtime)

        class FakeStore:
            LIQUIDITY_SURVIVAL_ENABLED = True

            def __init__(self):
                self.attempts = []
                self.snapshots = []
                self.tokens = []

            _snapshot_pair_fields = staticmethod(Store._snapshot_pair_fields)

            def record_liquidity_survival_attempt(self, target_id, **values):
                self.attempts.append((target_id, values))

            def upsert_token(self, token, seen_at=None):
                self.tokens.append((token, seen_at))

            def add_snapshot(self, snapshot):
                self.snapshots.append(snapshot)

        exact_pair = {
            "chainId": "solana",
            "dexId": "raydium",
            "pairAddress": "ExactPair",
            "baseToken": {"address": "ExactMint"},
            "quoteToken": {"address": "So111"},
            "liquidity": {"usd": 20_000},
        }
        other_pair = {**exact_pair, "pairAddress": "OtherPair"}
        token = TokenCandidate(
            chain="solana", address="ExactMint", name="Exact", source="dexscreener",
            raw={"pair": exact_pair},
        )

        class Dex:
            def __init__(self):
                self.pair = exact_pair

            async def quote(self, _chain, _address):
                pair = self.pair
                return token, TokenSnapshot(
                    "solana", token.address, 0.01, 20_000, 100_000, 10_000, 20, 10,
                    provider="dexscreener", raw={"pair": pair},
                )

        runtime.store = FakeStore()
        runtime.dex = Dex()
        target = {
            "id": 1,
            "chain": "solana",
            "token_id": "solana:ExactMint",
            "pair_address": "ExactPair",
            "deadline_at": iso(utcnow() + timedelta(seconds=30)),
        }
        await runtime._liquidity_survival_target_once(target)
        assert len(runtime.store.snapshots) == 1
        assert runtime.store.attempts[-1][1]["status"] == "observed"

        runtime.dex.pair = other_pair
        await runtime._liquidity_survival_target_once({**target, "id": 2})
        assert len(runtime.store.snapshots) == 1
        assert runtime.store.attempts[-1][1]["status"] == "pair_mismatch"
        assert runtime.store.attempts[-1][1]["observed_pair_address"] == "OtherPair"

    asyncio.run(scenario())


def test_load_config_routes_process_temp_storage_beside_project(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(initial_config()), encoding="utf-8")

    _, root = load_config(config_path)
    expected = (root / "data" / "tmp").resolve()

    assert expected.is_dir()
    assert os.environ["TEMP"] == str(expected)
    assert os.environ["TMP"] == str(expected)
    assert tempfile.gettempdir() == str(expected)
    with tempfile.TemporaryDirectory(prefix="memetrader-test-") as directory:
        assert Path(directory).parent == expected


def test_paper_fee_uses_pumpswap_cap_only_for_identified_venue(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["paper"]["fixed_fee_usd_each_side"] = 0
        runtime = Runtime(config, tmp_path)
        generic = TokenSnapshot(
            "solana", "G" * 32, 1, 10_000, 100_000, 1_000, 10, 5,
            raw={"pair": {"dexId": "raydium"}},
        )
        pump = TokenSnapshot(
            "solana", "P" * 32, 1, 10_000, 100_000, 1_000, 10, 5,
            raw={"pair": {"dexId": "pumpswap"}},
        )
        assert runtime._paper_fee_bps(generic) == pytest.approx(60)
        assert runtime._paper_fee_bps(pump) == pytest.approx(125)
        await runtime.close()

    asyncio.run(scenario())


def test_followup_tick_finalizes_event_and_token_context_with_legacy_quote_lane(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        calls = []
        runtime.store.finalize_shadow_event_outcomes = lambda: calls.append("event")
        runtime.store.finalize_token_context_outcomes = lambda: calls.append("token_context")
        runtime.store.finalize_information_first_shadow_outcomes = lambda: calls.append("information_first")
        runtime.store.finalize_information_first_ilg_outcomes = lambda: calls.append("information_first_ilg")
        runtime.store.finalize_token_universe_outcome_quality = lambda: calls.append("outcome_quality")
        runtime.store.finalize_token_universe_fixed_target_execution = lambda: calls.append("fixed_execution")
        runtime.store.finalize_missed_opportunity_audits = lambda: calls.append("missed_opportunity")
        runtime.store.finalize_missed_opportunity_no_decision_attributions = lambda: calls.append("no_decision_attribution")
        async def universe():
            calls.append("token_universe")
        async def jupiter(**kwargs):
            assert kwargs == {"include_universe": True, "include_onchain": False}
            calls.append("jupiter_quote")
        runtime.token_universe_followup_once = universe
        runtime.token_universe_jupiter_quote_once = jupiter
        await runtime.shadow_event_followup_once()
        assert calls == [
            "event", "token_context", "information_first", "information_first_ilg",
            "token_universe", "jupiter_quote", "outcome_quality", "fixed_execution",
            "missed_opportunity", "no_decision_attribution",
        ]
        await runtime.close()

    asyncio.run(scenario())


def test_token_universe_followup_actively_quotes_due_baseline_without_trading(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="V" * 32, name="Universe Quote", symbol="UVQ",
            source="pumpportal:create",
        )
        runtime.store.upsert_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1,
        )

        async def batch_quote(chain, addresses):
            assert chain == "solana" and addresses == [token.address]
            snapshot = TokenSnapshot(
                chain=token.chain, address=token.address, price_usd=0.01,
                liquidity_usd=20_000, market_cap_usd=100_000,
                volume_5m_usd=5_000, buys_5m=20, sells_5m=5,
                observed_at=utcnow(), provider="dexscreener",
            )
            return {token.token_id: (token, snapshot)}

        runtime.dex.batch_quote = batch_quote
        await runtime.token_universe_followup_once()
        baseline = runtime.store.db.execute(
            "SELECT * FROM token_universe_forward_baselines"
        ).fetchone()
        assert baseline is not None and baseline["status"] == "observed"
        followup_round = runtime.store.db.execute(
            "SELECT * FROM token_discovery_rounds WHERE surface='universe_baseline'"
        ).fetchone()
        assert followup_round is not None and followup_round["snapshot_count"] == 1
        attempt = runtime.store.db.execute(
            "SELECT * FROM token_discovery_quote_attempts WHERE round_id=?",
            (int(followup_round["id"]),),
        ).fetchone()
        assert attempt is not None and attempt["status"] == "success"
        assert attempt["reason_code"] == "snapshot_persisted"
        assert attempt["decision_eligible"] == 0 and attempt["affects"] == "none"
        assert runtime.dex.http is runtime.market_http
        assert runtime.dex.http is not runtime.http
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_actively_marks_due_information_first_target_without_generic_snapshot(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        lead_at = now - timedelta(minutes=16)
        event_id = runtime.store.create_event("Due active mark", ["Due"], 70, lead_at)
        lead = Observation(
            source="runtime-active-fixture", source_kind="news", title="Due active mark",
            observed_at=lead_at, ingested_at=lead_at, published_at=lead_at,
            role="feature", capture_phase="live",
        )
        lead_id, _ = runtime.store.add_observation(lead)
        runtime.store.link_event_observation(event_id, lead_id)
        token = TokenCandidate(chain="solana", address="R" * 32, name="Runtime Active")
        runtime.store.upsert_token(token, seen_at=lead_at)
        runtime.store.add_snapshot(TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=20_000,
            market_cap_usd=100_000, volume_5m_usd=2_000, buys_5m=8, sells_5m=4,
            observed_at=lead_at, ingested_at=lead_at, provider="fixture",
        ))
        decision_id = runtime.store.add_decision(CandidateDecision(
            event_id, token.token_id, "WAIT", 65, 70, 3, [], created_at=now,
        ))
        cohort_id = runtime.store.create_information_first_shadow_cohort(
            event_id, token.token_id, decision_id=decision_id,
            accepted_observation_ids=[lead_id], captured_at=now, relation_available_at=lead_at,
        )
        assert cohort_id is not None

        async def quote(chain, address):
            assert (chain, address) == ("solana", token.address)
            return token, TokenSnapshot(
                chain=chain, address=address, price_usd=1.25, liquidity_usd=25_000,
                market_cap_usd=125_000, volume_5m_usd=3_000, buys_5m=10, sells_5m=5,
                observed_at=utcnow(), provider="dexscreener",
            )

        runtime.dex.quote = quote
        before = runtime.store.db.execute("SELECT COUNT(*) FROM token_snapshots").fetchone()[0]
        await runtime.information_first_active_outcome_once()
        terminal = runtime.store.db.execute(
            "SELECT z.status,z.price_usd FROM information_first_active_outcome_terminals z "
            "JOIN information_first_active_outcome_targets t ON t.id=z.target_id "
            "WHERE t.shadow_cohort_id=? AND t.horizon_minutes=15",
            (cohort_id,),
        ).fetchone()
        assert terminal["status"] == "observed_mark"
        assert terminal["price_usd"] == pytest.approx(1.25)
        assert runtime.store.db.execute("SELECT COUNT(*) FROM token_snapshots").fetchone()[0] == before
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_active_outcome_hanging_provider_is_deadline_bounded(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        lead_at = now - timedelta(minutes=20) + timedelta(seconds=0.25)
        event_id = runtime.store.create_event("Deadline bounded mark", ["Deadline"], 70, lead_at)
        lead = Observation(
            source="runtime-deadline-fixture", source_kind="news", title="Deadline bounded mark",
            observed_at=lead_at, ingested_at=lead_at, published_at=lead_at,
            role="feature", capture_phase="live",
        )
        lead_id, _ = runtime.store.add_observation(lead)
        runtime.store.link_event_observation(event_id, lead_id)
        token = TokenCandidate(chain="solana", address="H" * 32, name="Deadline Bounded")
        runtime.store.upsert_token(token, seen_at=lead_at)
        runtime.store.add_snapshot(TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=20_000,
            market_cap_usd=100_000, volume_5m_usd=2_000, buys_5m=8, sells_5m=4,
            observed_at=lead_at, ingested_at=lead_at, provider="fixture",
        ))
        decision_id = runtime.store.add_decision(CandidateDecision(
            event_id, token.token_id, "WAIT", 65, 70, 3, [], created_at=now,
        ))
        cohort_id = runtime.store.create_information_first_shadow_cohort(
            event_id, token.token_id, decision_id=decision_id,
            accepted_observation_ids=[lead_id], captured_at=now, relation_available_at=lead_at,
        )
        assert cohort_id is not None

        async def hanging_quote(chain, address):
            await asyncio.Event().wait()

        runtime.dex.quote = hanging_quote
        started = asyncio.get_running_loop().time()
        await runtime.information_first_active_outcome_once()
        assert asyncio.get_running_loop().time() - started < 1.0
        result = runtime.store.db.execute(
            "SELECT r.status,r.reason_code FROM information_first_active_outcome_results r "
            "JOIN information_first_active_outcome_targets t ON t.id=r.target_id "
            "WHERE t.shadow_cohort_id=? AND t.horizon_minutes=15",
            (cohort_id,),
        ).fetchone()
        terminal = runtime.store.db.execute(
            "SELECT z.status,z.reason_code FROM information_first_active_outcome_terminals z "
            "JOIN information_first_active_outcome_targets t ON t.id=z.target_id "
            "WHERE t.shadow_cohort_id=? AND t.horizon_minutes=15",
            (cohort_id,),
        ).fetchone()
        assert result["status"] == "late_response"
        assert terminal["status"] == "terminal_missing"
        assert terminal["reason_code"] == "attempt_without_result"
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM information_first_active_outcome_terminals "
            "WHERE status='scheduler_missed_deadline'"
        ).fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_deferred_context_retry_recovers_post_activation_metadata_intent(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        search = config["autonomous_search"]
        search["context_deferred_retry_enabled"] = True
        search["context_deferred_retry_min_idle_minutes"] = 4
        search["context_deferred_retry_interval_minutes"] = 4
        search["context_global_cooldown_minutes"] = 4
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="R" * 32, name="Retry Lead", symbol="RETRY"
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="dexscreener",
            surface="token_profiles",
            mode="poll",
            chain_scope="solana",
        )
        runtime.store.add_token_discovery_exposure(
            round_id,
            token_id=token.token_id,
            chain=token.chain,
            role="identity",
            first_local_discovery=True,
            new_token=True,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )
        runtime.store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "dexscreener",
                "discovery_surface": "token_profiles",
                "role": "identity",
                "original_url": "https://example.com/retry-lead",
                "normalized_url": "https://example.com/retry-lead",
                "link_kind": "website",
                "platform": "",
                "verification_status": "provider_metadata",
            }
        )
        snapshot = TokenSnapshot(
            "solana", token.address, 0.01, 30_000, 100_000, 1_000, 10, 2
        )
        snapshot_id = runtime.store.add_snapshot(snapshot)
        trigger = runtime.autonomous_search.resolve_token_context_trigger(
            token,
            momentum_score=10,
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=snapshot_id,
        )
        now = utcnow()
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=10,
            outcome="skipped",
            reason="global_cooldown_active",
            trigger=trigger,
            now=now,
            quota=runtime.autonomous_search._token_context_quota_state(now),
            next_eligible_at=now,
        )
        runtime.store.set_kv(
            "autonomous_context_search:last_run",
            now,
        )
        investigations = []

        async def investigate(
            candidate, observed, *, momentum_score, event_relation=None, retry_lane=False
        ):
            investigations.append(
                (candidate.token_id, observed.token_id, event_relation, retry_lane)
            )

        runtime._investigate_token_context = investigate
        await runtime.retry_deferred_token_context_once()

        assert len(investigations) == 1
        retried_token, retried_snapshot, relation, retry_lane = investigations[0]
        assert retried_token == token.token_id
        assert retried_snapshot == token.token_id
        assert retry_lane is True
        assert relation["kind"] == "token_metadata_source_link"
        assert relation["source_link_id"] == trigger["source_link_id"]
        assert relation["selection_path"] == "deferred_retry_lane"
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=10,
            outcome="reused",
            reason="source_fact_reused",
            trigger=trigger,
            now=utcnow(),
            quota=runtime.autonomous_search._token_context_quota_state(utcnow()),
        )
        assert runtime.store.due_token_context_active_retries(
            activated_at=runtime.store.get_kv(
                runtime.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY
            ),
            now=utcnow() + timedelta(seconds=1),
            limit=10,
        ) == []
        await runtime.close()

    asyncio.run(scenario())


def test_deferred_context_retry_preserves_exact_browser_observation(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        search = config["autonomous_search"]
        search["context_deferred_retry_enabled"] = True
        search["context_deferred_retry_interval_minutes"] = 4
        search["context_global_cooldown_minutes"] = 4
        runtime = Runtime(config, tmp_path)
        runtime.autonomous_search._configured_high_impact_accounts = lambda: [{
            "platform": "x",
            "handle": "elonmusk",
            "url": "https://x.com/elonmusk",
            "entity_id": "elon_musk",
            "priority": 5,
            "watch_cadence": "critical",
        }]
        token = TokenCandidate(
            chain="solana", address="E" * 32, name="Exact retry", symbol="EXACT"
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal",
            surface="new_token",
            mode="stream",
            chain_scope="solana",
        )
        runtime.store.add_token_discovery_exposure(
            round_id,
            token_id=token.token_id,
            chain=token.chain,
            role="identity",
            first_local_discovery=True,
            new_token=True,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )
        runtime.store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "pumpportal",
                "discovery_surface": "launch_metadata",
                "role": "identity",
                "original_url": "https://x.com/elonmusk/status/12345",
                "normalized_url": "https://x.com/elonmusk/status/12345",
                "link_kind": "social_post",
                "platform": "x",
                "verification_status": "provider_metadata",
            }
        )
        source_link_id = runtime.store.db.execute(
            "SELECT id FROM token_source_links WHERE token_id=?",
            (token.token_id,),
        ).fetchone()["id"]
        observation_id, _ = runtime.store.add_observation(
            Observation(
                source="x:elonmusk",
                source_kind="social",
                title="Exact locally captured post",
                text="Exact locally captured post body.",
                url="https://x.com/elonmusk/status/12345",
                role="feature",
                source_item_id="https://x.com/elonmusk/status/12345",
                availability_proof="local_receive",
                raw={
                    "source_entity_id": "elon_musk",
                    "browser": {"platform": "x"},
                },
            )
        )
        snapshot = TokenSnapshot(
            "solana", token.address, 0.01, 30_000, 100_000, 1_000, 10, 2
        )
        snapshot_id = runtime.store.add_snapshot(snapshot)
        trigger = runtime.autonomous_search.resolve_token_context_trigger(
            token,
            momentum_score=10,
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=snapshot_id,
        )
        assert trigger["source_link_id"] == source_link_id
        assert trigger["observation_id"] == observation_id
        now = utcnow()
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=10,
            outcome="skipped",
            reason="global_cooldown_active",
            trigger=trigger,
            now=now,
            quota=runtime.autonomous_search._token_context_quota_state(now),
            next_eligible_at=now,
        )
        runtime.store.set_kv("autonomous_context_search:last_run", now)
        investigations = []

        async def investigate(
            candidate, observed, *, momentum_score, event_relation=None, retry_lane=False
        ):
            investigations.append(event_relation)

        runtime._investigate_token_context = investigate
        await runtime.retry_deferred_token_context_once()

        assert len(investigations) == 1
        relation = investigations[0]
        assert relation["observation_id"] == observation_id
        assert relation["observed_text"] == "Exact locally captured post body."
        assert relation["verification_status"] == "browser_exact_entity_observation"
        assert relation["selection_path"] == "deferred_retry_lane"
        await runtime.close()

    asyncio.run(scenario())


def test_post_entry_deferred_retry_requires_open_paired_position(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["autonomous_search"]["context_deferred_retry_enabled"] = True
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="Y" * 32, name="Open runner", symbol="OPEN"
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream",
            chain_scope="solana",
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain="solana", role="create",
            first_local_discovery=True, new_token=True,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1,
        )
        opened_at = utcnow() - timedelta(minutes=1)
        with runtime.store.db:
            runtime.store.db.execute(
                """
                INSERT INTO onchain_paper_narrative_runner_positions(
                    definition_version,shadow_cohort_id,token_id,source_buy_trade_id,
                    baseline_quote_result_id,initial_amount_raw,remaining_amount_raw,
                    stake_usd,entry_network_fee_usd,status,opened_at
                ) VALUES(?,?,?,?,?,?,?,?,?,'narrative_runner',?)
                """,
                (
                    Store.ONCHAIN_PAPER_NARRATIVE_RUNNER_VERSION, 7, token.token_id,
                    11, 99, "1000", "1000", 35.0, 0.01, iso(opened_at),
                ),
            )
        snapshot = TokenSnapshot(
            "solana", token.address, 0.01, 30_000, 100_000, 1_000, 10, 2,
            observed_at=utcnow(), ingested_at=utcnow(),
        )
        snapshot_id = runtime.store.add_snapshot(snapshot)
        trigger = runtime.autonomous_search.resolve_token_context_trigger(
            token,
            momentum_score=80,
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=snapshot_id,
            event_relation={
                "kind": "post_entry_narrative_position",
                "source_buy_trade_id": 11,
                "shadow_cohort_id": 7,
                "position_opened_at": iso(opened_at),
                "position_status": "narrative_runner",
                "context_snapshot_basis": "post_entry_snapshot",
                "investigation_started_at": iso(utcnow()),
            },
        )
        with runtime.store.db:
            runtime.store.db.execute(
                """
                INSERT INTO onchain_paper_narrative_context_seeds(
                    definition_version,source_buy_trade_id,shadow_cohort_id,
                    token_id,position_opened_at,snapshot_id,trigger_transition_id,
                    status,reason_code,recorded_at,decision_eligible,affects
                ) VALUES(?,?,?,?,?,?,?,'triggered',?,?,0,'none')
                """,
                (
                    Store.ONCHAIN_PAPER_NARRATIVE_CONTEXT_VERSION, 11, 7,
                    token.token_id, iso(opened_at), snapshot_id,
                    trigger["transition_id"], "post_entry_narrative_position",
                    iso(utcnow()),
                ),
            )
        now = utcnow()
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=80,
            outcome="skipped",
            reason="global_cooldown_active",
            trigger=trigger,
            now=now,
            quota=runtime.autonomous_search._token_context_quota_state(now),
            next_eligible_at=now,
        )
        with runtime.store.db:
            runtime.store.db.execute(
                """
                INSERT INTO onchain_paper_narrative_runner_positions(
                    definition_version,shadow_cohort_id,token_id,source_buy_trade_id,
                    baseline_quote_result_id,initial_amount_raw,remaining_amount_raw,
                    stake_usd,entry_network_fee_usd,status,opened_at
                ) VALUES(?,?,?,?,?,?,?,?,?,'baseline',?)
                """,
                (
                    Store.ONCHAIN_PAPER_NARRATIVE_RUNNER_VERSION, 8, token.token_id,
                    12, 100, "1000", "1000", 35.0, 0.01, iso(opened_at),
                ),
            )
        legacy_trigger = runtime.autonomous_search.resolve_token_context_trigger(
            token,
            momentum_score=80,
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=snapshot_id,
            event_relation={
                "kind": "post_entry_narrative_position",
                "source_buy_trade_id": 12,
                "shadow_cohort_id": 8,
                "position_opened_at": iso(opened_at),
                "position_status": "baseline",
                "context_snapshot_basis": "post_entry_snapshot",
                "investigation_started_at": iso(utcnow()),
            },
        )
        with runtime.store.db:
            runtime.store.db.execute(
                """
                INSERT INTO onchain_paper_narrative_context_seeds(
                    definition_version,source_buy_trade_id,shadow_cohort_id,
                    token_id,position_opened_at,snapshot_id,trigger_transition_id,
                    status,reason_code,recorded_at,decision_eligible,affects
                ) VALUES('legacy-context/v1',?,?,?,?,?,?,'triggered',?,?,0,'none')
                """,
                (
                    12, 8, token.token_id, iso(opened_at), snapshot_id,
                    legacy_trigger["transition_id"], "post_entry_narrative_position",
                    iso(utcnow()),
                ),
            )
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=80,
            outcome="skipped",
            reason="global_cooldown_active",
            trigger=legacy_trigger,
            now=now,
            quota=runtime.autonomous_search._token_context_quota_state(now),
            next_eligible_at=now,
        )
        due = runtime.store.due_token_context_active_retries(
            activated_at=runtime.store.get_kv(
                runtime.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY
            ),
            now=now + timedelta(seconds=1),
            limit=10,
        )
        assert [row["trigger_transition_id"] for row in due] == [
            trigger["transition_id"]
        ]
        runtime.autonomous_search._record_token_context_admission(
            token,
            snapshot,
            momentum_score=80,
            outcome="skipped",
            reason="token_cooldown_active",
            trigger={
                "kind": "high_impact_account_post",
                "priority": 3,
                "transition_id": trigger["transition_id"],
            },
            now=now + timedelta(seconds=1),
            quota=runtime.autonomous_search._token_context_quota_state(now),
            next_eligible_at=now + timedelta(hours=1),
        )
        assert runtime.store.due_token_context_active_retries(
            activated_at=runtime.store.get_kv(
                runtime.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY
            ),
            now=now + timedelta(seconds=2),
            limit=10,
        ) == []
        with runtime.store.db:
            runtime.store.db.execute(
                "UPDATE onchain_paper_narrative_runner_positions "
                "SET status='closed',closed_at=?,close_reason='fixture' "
                "WHERE definition_version=? AND source_buy_trade_id=11",
                (iso(now), Store.ONCHAIN_PAPER_NARRATIVE_RUNNER_VERSION),
            )
        assert runtime.store.due_token_context_active_retries(
            activated_at=runtime.store.get_kv(
                runtime.DEFERRED_CONTEXT_RETRY_ACTIVATED_AT_KEY
            ),
            now=now + timedelta(seconds=2),
            limit=10,
        ) == []
        await runtime.close()

    asyncio.run(scenario())


def test_solana_holder_shadow_records_aggregate_forward_snapshot_only(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        address = next(
            "A" * 30 + left + right
            for left in alphabet
            for right in alphabet
            if int.from_bytes(
                hashlib.sha256(
                    f"{Store.SOLANA_HOLDER_SHADOW_VERSION}\nsolana:{'A' * 30 + left + right}".encode()
                ).digest()[:8],
                "big",
            ) % Store.SOLANA_HOLDER_SHADOW_SAMPLE_MODULUS
            < Store.SOLANA_HOLDER_SHADOW_SAMPLE_BUCKETS
        )
        token = TokenCandidate(
            chain="solana", address=address, name="Holder Shadow", symbol="HSH",
            source="pumpportal:create",
        )
        discovered_at = utcnow()
        runtime.store.upsert_token(token, seen_at=discovered_at)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana", started_at=discovered_at,
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True, observed_at=discovered_at,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1,
        )
        owner_one = base64.b64encode(bytes([1]) * 32 + (600).to_bytes(8, "little")).decode()
        owner_two = base64.b64encode(bytes([2]) * 32 + (400).to_bytes(8, "little")).decode()
        calls = []

        async def post(url, *, json, headers):
            calls.append(json["method"])
            result = {
                "getAccountInfo": {
                    "context": {"slot": 100},
                    "value": {"owner": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"},
                },
                "getTokenSupply": {"context": {"slot": 100}, "value": {"amount": "1000"}},
                "getProgramAccounts": {
                    "context": {"slot": 101},
                    "value": [
                        {"account": {"data": [owner_one, "base64"]}},
                        {"account": {"data": [owner_two, "base64"]}},
                    ],
                },
            }[json["method"]]
            return httpx.Response(
                200, request=httpx.Request("POST", url),
                json={"jsonrpc": "2.0", "id": json["id"], "result": result},
            )

        monkeypatch.setattr(runtime.http.client, "post", post)
        await runtime.solana_holder_shadow_once()
        summary = Store.solana_holder_shadow_summary_from_connection(runtime.store.db)
        assert calls == ["getAccountInfo", "getTokenSupply", "getProgramAccounts"]
        assert summary["summary"] == {
            "cohorts": 1, "expected_results": 4, "results": 1,
            "observed": 1, "error": 0, "unavailable": 0, "pending": 3,
        }
        assert summary["recent"][0]["unique_owner_count"] == 2
        assert summary["recent"][0]["top1_supply_share"] == pytest.approx(0.6)
        assert summary["recent"][0]["top10_supply_share"] == pytest.approx(1.0)
        assert summary["decision_eligible"] is False
        assert summary["affects"] == "none"
        rendered = json.dumps(summary)
        assert owner_one not in rendered and owner_two not in rendered
        await runtime.close()

    asyncio.run(scenario())


def test_dex_quote_transport_backoff_is_shared_across_waiting_lanes(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        call_times = []

        async def batch_quote(chain, addresses):
            call_times.append(asyncio.get_running_loop().time())
            if len(call_times) == 1:
                raise httpx.ConnectError(
                    "offline", request=httpx.Request("GET", "https://api.dexscreener.com")
                )
            return {}

        runtime.dex.batch_quote = batch_quote
        runtime._dex_quote_backoff_base_seconds = 0.02
        runtime._dex_quote_backoff_cap_seconds = 0.02
        results = await asyncio.gather(
            runtime._dex_batch_quote("solana", ["A"]),
            runtime._dex_batch_quote("bsc", ["B"]),
            return_exceptions=True,
        )
        assert isinstance(results[0], httpx.ConnectError)
        assert results[1] == {}
        assert call_times[1] - call_times[0] >= 0.019
        assert runtime._dex_quote_failure_streak == 0
        assert runtime._dex_quote_backoff_until == 0
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_records_one_quote_only_jupiter_leg_without_trading(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        due = {
            "quote_key": "jupiter-quote:2:0:baseline_buy",
            "cohort_id": 2, "outcome_id": None, "phase": "baseline_buy",
            "anchor_at": iso(utcnow()), "target_at": None,
            "source_observed_at": iso(utcnow()), "source_ingested_at": iso(utcnow()),
            "source_recorded_at": iso(utcnow()),
            "max_queue_delay_seconds": 30, "max_total_delay_seconds": 45,
            "input_mint": Store.JUPITER_USDC_MINT,
            "output_mint": "J" * 32,
            "input_amount_raw": "35000000",
        }
        limits = []
        runtime.store.due_token_universe_jupiter_quotes = (
            lambda limit=1: limits.append(limit) or [due]
        )
        recorded = []
        runtime.store.finalize_token_universe_jupiter_quote_validity_gaps = (
            lambda limit=12: {"inserted": 0}
        )
        runtime.store.record_token_universe_jupiter_quote_validity = (
            lambda item, **payload: recorded.append((item, payload))
        )

        async def quote(input_mint, output_mint, amount, *, slippage_bps):
            assert (input_mint, output_mint, amount, slippage_bps) == (
                Store.JUPITER_USDC_MINT, "J" * 32, 35_000_000, 400,
            )
            stamp = iso(utcnow())
            return {
                "requested_at": stamp, "completed_at": stamp,
                "output_amount_raw": "123456789", "other_amount_threshold": "118518518",
                "slippage_bps": 400, "router": "metis", "mode": "manual",
                "fee_bps": 2, "platform_fee_bps": 2, "price_impact_pct": 0.1,
                "time_taken_ms": 12, "route_plan": [{"label": "Raydium"}],
            }

        runtime.jupiter.quote = quote
        await runtime.token_universe_jupiter_quote_once()
        assert len(recorded) == 1
        assert limits == [10_000]
        item, payload = recorded[0]
        assert item["quote_key"] == due["quote_key"] and payload["status"] == "quoted"
        assert payload["out_amount_raw"] == "123456789"
        assert payload["other_amount_threshold_raw"] == "118518518"
        assert payload["route_plan"] == [{"label": "Raydium"}]
        expired_at = utcnow() - timedelta(seconds=31)
        expired = {
            **due, "quote_key": "jupiter-quote:3:0:baseline_buy", "cohort_id": 3,
            "anchor_at": iso(expired_at), "source_observed_at": iso(expired_at),
            "source_ingested_at": iso(expired_at), "source_recorded_at": iso(expired_at),
        }
        runtime.store.due_token_universe_jupiter_quotes = lambda limit=1: [expired]
        recorded.clear()

        async def must_not_quote(*args, **kwargs):
            raise AssertionError("expired Jupiter task must not call provider")

        runtime.jupiter.quote = must_not_quote
        await runtime.token_universe_jupiter_quote_once()
        assert recorded[0][1]["status"] == "not_requested"
        stale = [
            {
                **expired, "quote_key": f"jupiter-quote:{cohort_id}:0:baseline_buy",
                "cohort_id": cohort_id,
            }
            for cohort_id in range(4, 17)
        ]
        runtime.store.due_token_universe_jupiter_quotes = (
            lambda limit=1: [*stale, due][:limit]
        )
        recorded.clear()
        runtime.jupiter.quote = quote
        await runtime.token_universe_jupiter_quote_once()
        assert [payload["status"] for _, payload in recorded] == [
            *("not_requested" for _ in range(12)), "quoted",
        ]
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_kol_addressability_uses_one_quote_only_request(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        task = {
            "definition_version": Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION,
            "cohort_id": 1, "milestone_id": 2, "identifier": "K" * 32,
            "token_id": "solana:" + "K" * 32,
            "input_mint": Store.JUPITER_USDC_MINT, "output_mint": "K" * 32,
            "input_amount_raw": "35000000", "slippage_bps": 400,
            "surface_key": '["dexscreener","solana","pumpfun","pair-k"]',
            "deadline_at": iso(utcnow() + timedelta(minutes=5)),
        }
        refreshed = []
        runtime.store.refresh_kol_token_addressability_evidence = (
            lambda: refreshed.append(True) or {}
        )
        runtime.store.due_kol_token_addressability_routes = lambda limit=1: [task]
        runtime.store.start_kol_token_addressability_route_attempt = (
            lambda item, requested_at=None: 9
        )
        recorded = []
        runtime.store.record_kol_token_addressability_route_result = (
            lambda item, **payload: recorded.append((item, payload)) or 10
        )

        async def quote(input_mint, output_mint, amount, *, slippage_bps):
            assert (input_mint, output_mint, amount, slippage_bps) == (
                Store.JUPITER_USDC_MINT, "K" * 32, 35_000_000, 400,
            )
            return {
                "output_amount_raw": "1000", "other_amount_threshold": "960",
                "router": "jupiter", "route_plan": [{"amm_key": "pair-k"}],
                "completed_at": iso(utcnow()),
            }

        runtime.jupiter.quote = quote
        await runtime.kol_token_addressability_route_once()
        assert refreshed == [True]
        assert len(recorded) == 1
        assert recorded[0][1]["attempt_id"] == 9
        assert recorded[0][1]["status"] == "quoted"
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (JupiterNoRouteError("no route"), "no_route"),
        (JupiterQuoteProtocolError("invalid"), "quote_only_protocol_invalid"),
        (RuntimeError("offline"), "error"),
    ],
)
def test_runtime_kol_addressability_retains_route_failures(
    tmp_path, failure: Exception, expected_status: str,
):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        task = {
            "cohort_id": 1, "milestone_id": 2, "identifier": "M" * 32,
            "token_id": "solana:" + "M" * 32,
            "input_mint": Store.JUPITER_USDC_MINT, "output_mint": "M" * 32,
            "input_amount_raw": "35000000", "slippage_bps": 400,
            "surface_key": '["dexscreener","solana","pumpfun","pair-m"]',
            "deadline_at": iso(utcnow() + timedelta(minutes=5)),
        }
        runtime.store.refresh_kol_token_addressability_evidence = lambda: {}
        runtime.store.due_kol_token_addressability_routes = lambda limit=1: [task]
        runtime.store.start_kol_token_addressability_route_attempt = (
            lambda item, requested_at=None: 11
        )
        recorded = []
        runtime.store.record_kol_token_addressability_route_result = (
            lambda item, **payload: recorded.append(payload) or 12
        )

        async def quote(*args, **kwargs):
            raise failure

        runtime.jupiter.quote = quote
        await runtime.kol_token_addressability_route_once()
        assert recorded[0]["status"] == expected_status
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_jupiter_provider_budget_is_shared_across_lanes_and_passes(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        anchor = utcnow()

        def task(index, *, onchain):
            common = {
                "quote_key": f"quote:{index}", "phase": "baseline_buy",
                "horizon_minutes": 0, "anchor_at": iso(anchor), "target_at": None,
                "baseline_snapshot_id": 1,
                "input_mint": Store.JUPITER_USDC_MINT,
                "output_mint": f"{index}" * 32, "input_amount_raw": "35000000",
                "max_queue_delay_seconds": 30, "max_total_delay_seconds": 45,
                "slippage_bps": 400,
            }
            if onchain:
                return {
                    **common, "lane": Store.ONCHAIN_ONLY_JUPITER_QUOTE_VERSION,
                    "shadow_cohort_id": index, "baseline_result_id": None,
                    "preflight_reason": None,
                }
            return {
                **common, "cohort_id": index, "outcome_id": None,
                "source_observed_at": iso(anchor), "source_ingested_at": iso(anchor),
                "source_recorded_at": iso(anchor),
            }

        runtime.store.due_onchain_only_jupiter_quotes = lambda limit=1: [
            task(1, onchain=True), task(2, onchain=True),
        ]
        runtime.store.due_token_universe_jupiter_quotes = lambda limit=1: [
            task(3, onchain=False), task(4, onchain=False),
        ]
        kol_task = {
            "definition_version": Store.KOL_TOKEN_ADDRESSABILITY_ROUTE_VERSION,
            "cohort_id": 5, "milestone_id": 6, "identifier": "K" * 32,
            "token_id": "solana:" + "K" * 32,
            "input_mint": Store.JUPITER_USDC_MINT, "output_mint": "K" * 32,
            "input_amount_raw": "35000000", "slippage_bps": 400,
            "surface_key": '["dexscreener","solana","pumpfun","pair-k"]',
            "deadline_at": iso(anchor + timedelta(seconds=10)),
        }
        runtime.store.refresh_kol_token_addressability_evidence = lambda: {}
        runtime.store.due_kol_token_addressability_routes = lambda limit=1: [kol_task]
        runtime.store.finalize_token_universe_jupiter_quote_validity_gaps = lambda limit=12: {
            "inserted": 0
        }
        attempts = []
        runtime.store.start_onchain_only_jupiter_quote_attempt = (
            lambda item, requested_at=None: attempts.append(item["quote_key"])
            or len(attempts)
        )
        runtime.store.start_kol_token_addressability_route_attempt = (
            lambda item, requested_at=None: 99
        )
        recorded = []
        runtime.store.record_onchain_only_jupiter_quote = (
            lambda item, **payload: recorded.append(("onchain", item["quote_key"], payload))
        )
        runtime.store.record_token_universe_jupiter_quote_validity = (
            lambda item, **payload: recorded.append(("universe", item["quote_key"], payload))
        )
        runtime.store.record_kol_token_addressability_route_result = (
            lambda item, **payload: recorded.append(("kol", str(item["cohort_id"]), payload))
        )
        provider_calls = []

        async def quote(input_mint, output_mint, amount, *, slippage_bps):
            provider_calls.append(output_mint)
            return {
                "output_amount_raw": "1000000000",
                "other_amount_threshold": "900000000",
                "slippage_bps": slippage_bps,
            }

        runtime.jupiter.quote = quote
        budget = {"provider_requests": 0, "gap_records": 0}
        await runtime.token_universe_jupiter_quote_once(budget=budget)
        await runtime.token_universe_jupiter_quote_once(budget=budget)
        assert budget["provider_requests"] == 3
        assert len(provider_calls) == 3
        assert attempts == ["quote:1", "quote:2"]
        assert [item[:2] for item in recorded] == [
            ("kol", "5"),
            ("onchain", "quote:1"), ("onchain", "quote:2"),
        ]
        assert all(item[2]["status"] == "quoted" for item in recorded)
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_background_jupiter_releases_quote_lock_between_requests(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        anchor = utcnow()
        tasks = [
            {
                "quote_key": f"quote:{index}", "phase": "baseline_buy",
                "horizon_minutes": 0, "anchor_at": iso(anchor), "target_at": None,
                "baseline_snapshot_id": 1, "input_mint": Store.JUPITER_USDC_MINT,
                "output_mint": f"{index}" * 32, "input_amount_raw": "35000000",
                "max_queue_delay_seconds": 30, "max_total_delay_seconds": 45,
                "slippage_bps": 400, "cohort_id": index, "outcome_id": None,
                "source_observed_at": iso(anchor), "source_ingested_at": iso(anchor),
                "source_recorded_at": iso(anchor),
            }
            for index in (1, 2)
        ]
        runtime.store.due_token_universe_jupiter_quotes = lambda limit=1: tasks
        runtime.store.due_onchain_only_jupiter_quotes = lambda limit=1: []
        runtime.store.due_kol_token_addressability_routes = lambda limit=1: []
        runtime.store.refresh_kol_token_addressability_evidence = lambda: {}
        runtime.store.finalize_token_universe_jupiter_quote_validity_gaps = lambda limit=12: {}
        runtime.store.record_token_universe_jupiter_quote_validity = lambda *args, **kwargs: None
        order = []
        production_task = None

        async def production_waiter():
            async with runtime._jupiter_quote_lock:
                order.append("production")

        async def quote(*args, **kwargs):
            nonlocal production_task
            order.append(f"background:{len([x for x in order if x.startswith('background')]) + 1}")
            if production_task is None:
                production_task = asyncio.create_task(production_waiter())
                await asyncio.sleep(0)
            return {"output_amount_raw": "1000", "other_amount_threshold": "960"}

        runtime.jupiter.quote = quote
        await runtime.token_universe_jupiter_quote_once(
            include_universe=True, include_onchain=False, include_kol=False,
        )
        await production_task
        assert order == ["background:1", "production", "background:2"]
        await runtime.close()

    asyncio.run(scenario())


def test_token_universe_followup_collects_forward_evm_execution_safety(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="bsc", address="0x" + "a" * 40,
            name="Forward EVM Safety", symbol="FES", source="geckoterminal:bsc",
        )
        runtime.store.upsert_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="geckoterminal", surface="new_pools", mode="poll", chain_scope="bsc",
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="new_pool",
            first_local_discovery=True, new_token=True,
        )
        runtime.store.finish_token_discovery_round(round_id, status="completed", returned_count=1)

        async def batch_quote(chain, addresses):
            assert chain == "bsc" and addresses == [token.address]
            snapshot = TokenSnapshot(
                chain="bsc", address=token.address, price_usd=0.01,
                liquidity_usd=20_000, market_cap_usd=100_000,
                volume_5m_usd=5_000, buys_5m=20, sells_5m=5,
                observed_at=utcnow(), provider="dexscreener",
                raw={"pair": {
                    "chainId": "bsc", "dexId": "pancakeswap",
                    "pairAddress": "0x" + "b" * 40,
                    "baseToken": {"address": token.address},
                    "quoteToken": {"address": "0x" + "c" * 40},
                }},
            )
            return {token.token_id: (token, snapshot)}

        safety_calls = []

        async def enrich(snapshot):
            safety_calls.append(snapshot.token_id)
            snapshot.honeypot = False
            snapshot.sellable = True
            snapshot.buy_tax_pct = 1.0
            snapshot.sell_tax_pct = 2.0
            snapshot.raw["execution_safety_checked_at"] = iso(utcnow())
            snapshot.raw["execution_safety_reports"] = ["goplus_evm", "honeypot_is"]
            return snapshot

        runtime.dex.batch_quote = batch_quote
        runtime.safety.enrich_evm_execution_fields = enrich
        await runtime.token_universe_followup_once()
        snapshot = runtime.store.db.execute(
            "SELECT * FROM token_snapshots WHERE token_id=? ORDER BY id DESC LIMIT 1",
            (token.token_id,),
        ).fetchone()
        assert safety_calls == [token.token_id]
        assert snapshot["honeypot"] == 0 and snapshot["sellable"] == 1
        assert snapshot["buy_tax_pct"] == pytest.approx(1.0)
        assert snapshot["sell_tax_pct"] == pytest.approx(2.0)
        raw = json.loads(snapshot["raw_json"])
        assert raw["execution_safety_reports"] == ["goplus_evm", "honeypot_is"]
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_token_universe_quote_failure_records_each_token_and_suppresses_hot_retry(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="Y" * 32, name="Quote Failure", symbol="QF",
            source="pumpportal:create",
        )
        runtime.store.upsert_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana",
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        runtime.store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        calls = 0

        async def batch_quote(chain, addresses):
            nonlocal calls
            calls += 1
            raise RuntimeError("pool unavailable")

        runtime.dex.batch_quote = batch_quote
        await runtime.token_universe_followup_once()
        attempt = runtime.store.db.execute(
            "SELECT * FROM token_discovery_quote_attempts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert attempt is not None and attempt["status"] == "error"
        assert attempt["error_type"] == "RuntimeError"
        assert attempt["retry_after_at"] > attempt["completed_at"]
        await runtime.token_universe_followup_once()
        assert calls == 1
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM token_discovery_quote_attempts"
        ).fetchone()[0] == 1
        await runtime.close()

    asyncio.run(scenario())


def test_token_universe_followup_rechecks_cross_chain_deadline_between_batches(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        base = utcnow()
        due = []
        for index in range(30):
            due.append({
                "cohort_id": index + 1, "token_id": f"solana:S{index:031d}",
                "chain": "solana", "role": "universe_baseline", "horizon_minutes": 0,
                "queue_due_at": iso(base), "deadline_at": iso(base + timedelta(seconds=1)),
            })
        due.append({
            "cohort_id": 31, "token_id": "bsc:" + "B" * 32,
            "chain": "bsc", "role": "universe_baseline", "horizon_minutes": 0,
            "queue_due_at": iso(base), "deadline_at": iso(base + timedelta(seconds=2)),
        })
        due.append({
            "cohort_id": 32, "token_id": "solana:" + "Z" * 32,
            "chain": "solana", "role": "universe_baseline", "horizon_minutes": 0,
            "queue_due_at": iso(base), "deadline_at": iso(base + timedelta(seconds=3)),
        })
        runtime.store.finalize_token_universe_forward_outcomes = lambda: {}
        runtime.store.due_token_universe_quotes = lambda limit=180: list(due)
        calls = []

        async def batch_quote(chain, addresses):
            calls.append((chain, len(addresses)))
            return {}

        runtime.dex.batch_quote = batch_quote
        await runtime.token_universe_followup_once()
        assert calls == [("solana", 30), ("bsc", 1), ("solana", 1)]
        await runtime.close()

    asyncio.run(scenario())


def test_observation_polls_record_completed_duplicate_empty_and_error_exposure(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        observation = Observation(
            source="test-feed",
            source_kind="news",
            title="A forward-only test event",
            url="https://article.example/item/1",
            role="feature",
            source_item_id="test-feed:1",
        )

        class Collector:
            name = "public-test-feed"
            url = "https://news.example/feed?token=DO_NOT_STORE"

            def __init__(self):
                self.items = [[observation], [observation], []]

            async def poll(self):
                return self.items.pop(0)

        collector = Collector()
        await runtime._poll_observation_collector(collector)
        await runtime._poll_observation_collector(collector)
        await runtime._poll_observation_collector(collector)

        class FailingCollector:
            name = "failing-feed"
            url = "https://fail.example/feed?password=DO_NOT_STORE"

            async def poll(self):
                raise TimeoutError("private diagnostic text")

        await runtime._poll_observation_collector(FailingCollector())
        rows = runtime.store.db.execute(
            "SELECT * FROM source_poll_attempts ORDER BY id"
        ).fetchall()
        assert [row["status"] for row in rows] == ["completed", "completed", "completed", "error"]
        assert rows[0]["fetched_count"] == 1 and rows[0]["new_observation_count"] == 1
        assert rows[0]["decision_eligible_count"] == 1
        assert rows[1]["duplicate_count"] == 1 and rows[1]["new_observation_count"] == 0
        assert rows[2]["fetched_count"] == 0
        assert rows[3]["error_type"] == "TimeoutError"
        serialized = json.dumps([dict(row) for row in rows])
        assert "DO_NOT_STORE" not in serialized
        assert "private diagnostic text" not in serialized
        await runtime.close()

    asyncio.run(scenario())


def test_gecko_poll_records_first_duplicate_and_error_rounds(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana", "bsc"]
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="bsc", address="0x" + "1" * 40, name="Gecko Discovery", source="geckoterminal:bsc"
        )

        class Gecko:
            calls = 0

            def __init__(self, http, network):
                assert network == "bsc"

            async def poll(self):
                Gecko.calls += 1
                if Gecko.calls == 3:
                    raise TimeoutError("provider detail must not persist")
                return [token] if Gecko.calls <= 2 else []

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        await runtime._poll_gecko_network("bsc")
        await runtime._poll_gecko_network("bsc")
        await runtime._poll_gecko_network("bsc")
        rows = runtime.store.db.execute(
            "SELECT * FROM token_discovery_rounds ORDER BY id"
        ).fetchall()
        assert [row["status"] for row in rows] == ["completed", "completed", "error"]
        assert rows[0]["first_local_discovery_count"] == 1
        assert rows[1]["first_local_discovery_count"] == 0
        assert rows[1]["duplicate_token_count"] == 1
        assert rows[2]["error_type"] == "TimeoutError"
        assert "provider detail" not in json.dumps([dict(row) for row in rows])
        hydration = runtime.store.token_detail_hydration(token.token_id)
        assert hydration["status"] == "pending" and hydration["chain"] == "bsc"
        await runtime.close()

    asyncio.run(scenario())


def test_pump_stream_records_create_migration_and_empty_windows(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["pumpportal"]["exposure_window_seconds"] = 1
        runtime = Runtime(config, tmp_path)
        create = TokenCandidate(
            chain="solana", address="C" * 32, name="Pump Create", source="pumpportal:create"
        )
        migration = TokenCandidate(
            chain="solana", address="M" * 32, name="Pump Migration", source="pumpportal:migration"
        )

        class Pump:
            URL = "wss://example.invalid"

            def __init__(self, url):
                pass

            async def stream(self):
                yield create
                yield migration
                while True:
                    await asyncio.sleep(10)

        monkeypatch.setattr("memetrader.runtime.PumpPortalCollector", Pump)
        task = asyncio.create_task(runtime.pump_loop())
        await asyncio.sleep(1.15)
        runtime.stop()
        await task
        rows = runtime.store.db.execute(
            "SELECT surface,status,returned_count,first_local_discovery_count "
            "FROM token_discovery_rounds ORDER BY id"
        ).fetchall()
        completed = [row for row in rows if row["status"] == "completed"]
        assert {(row["surface"], row["returned_count"]) for row in completed} >= {
            ("create", 1), ("migration", 1)
        }
        assert any(row["returned_count"] == 0 for row in rows)
        assert sum(row["first_local_discovery_count"] for row in rows) == 2
        await runtime.close()

    asyncio.run(scenario())


def test_dexscreener_discovery_persists_provenance_and_hydrates_bounded_token(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["surface_chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["max_hydrations_per_cycle"] = 1
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(chain="solana", address="Q" * 32, name="Profile token", symbol="PROF")
        snapshot = TokenSnapshot("solana", token.address, 0.01, 25000, 100000, 5000, 20, 4)

        class Dex:
            DISCOVERY_SURFACES = {"token_profiles": ("/token-profiles/latest/v1", "identity")}

            async def discover_surface(self, surface, allowed_chains, limit=40):
                assert surface == "token_profiles"
                assert allowed_chains == {"solana"}
                return [
                    {
                        "token_id": token.token_id,
                        "chain": "solana",
                        "address": token.address,
                        "provider": "dexscreener",
                        "discovery_surface": "token_profiles",
                        "role": "identity",
                        "original_url": "https://x.com/profile_token",
                        "normalized_url": "https://x.com/profile_token",
                        "link_kind": "social_profile",
                        "platform": "x",
                        "verification_status": "provider_metadata",
                    }
                ]

            async def quote(self, chain, address):
                assert (chain, address) == ("solana", token.address)
                return token, snapshot

        runtime.dex = Dex()
        await runtime.poll_dexscreener_discovery_once()
        assert runtime.store.token(token.token_id) is not None
        links = runtime.store.token_source_links(token.token_id)
        assert len(links) == 1 and links[0]["role"] == "identity"
        exposure_link = runtime.store.db.execute(
            """
            SELECT el.decision_eligible,el.affects
            FROM token_discovery_exposure_source_links el
            JOIN token_discovery_exposures e ON e.id=el.exposure_id
            JOIN token_source_links l ON l.id=el.source_link_id
            WHERE e.token_id=? AND l.token_id=e.token_id
            """,
            (token.token_id,),
        ).fetchone()
        assert exposure_link is not None
        assert exposure_link["decision_eligible"] == 0 and exposure_link["affects"] == "none"
        funnel = runtime.store.token_universe_funnel_summary_from_connection(runtime.store.db)
        external_links = next(
            item for item in funnel["milestones"] if item["stage"] == "external_links_found"
        )
        assert external_links["cohorts"] == 1 and external_links["attempts"] == 1
        health = {row["source"]: row for row in runtime.store.source_health()}
        assert health["dexscreener:token_profiles"]["last_ok_at"] is not None
        assert health["dexscreener:hydration"]["last_item_at"] is not None
        transitions = runtime.store.db.execute(
            "SELECT stage,status,round_id,snapshot_id,decision_eligible,affects "
            "FROM token_universe_funnel_transitions WHERE token_id=? "
            "AND stage LIKE 'metadata_hydration_%' ORDER BY id",
            (token.token_id,),
        ).fetchall()
        assert [(row["stage"], row["status"]) for row in transitions] == [
            ("metadata_hydration_attempt", "attempted"),
            ("metadata_hydration_result", "hydrated"),
        ]
        assert transitions[0]["round_id"] is not None
        assert transitions[1]["snapshot_id"] is not None
        assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in transitions)
        await runtime.close()

    asyncio.run(scenario())


def test_dex_hydration_immediately_investigates_exact_high_impact_post_only(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        settings_path = tmp_path / "data" / "web_console" / "console_settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "watch_accounts": [
                        {
                            "platform": "x", "handle": "@elonmusk",
                            "url": "https://x.com/elonmusk", "entity_id": "elon_musk",
                            "priority": 4, "watch_cadence": "critical", "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        runtime = Runtime(config, tmp_path)
        tokens = [
            TokenCandidate(chain="solana", address="H" * 32, name="Rocket Otter", symbol="ROT"),
            TokenCandidate(chain="solana", address="J" * 32, name="Rocket Badger", symbol="RBG"),
        ]
        runtime.store.add_observation(
            Observation(
                source="browser:x:elonmusk",
                source_kind="social",
                title="Exact locally received post",
                url="https://x.com/elonmusk/status/12345",
                author="@elonmusk",
                availability_proof="local_receive",
                role="feature",
                source_item_id="https://x.com/elonmusk/status/12345",
                raw={
                    "source_entity_id": "elon_musk",
                    "browser": {"platform": "x", "source_entity_id": "elon_musk"},
                },
            )
        )

        class Dex:
            DISCOVERY_SURFACES = {"token_profiles": ("/token-profiles/latest/v1", "identity")}

            async def discover_surface(self, surface, allowed_chains, limit=40):
                return [
                    {
                        "token_id": token.token_id,
                        "chain": token.chain,
                        "address": token.address,
                        "provider": "dexscreener",
                        "discovery_surface": surface,
                        "role": "identity",
                        "original_url": "https://x.com/elonmusk/status/12345?utm_source=project",
                        "normalized_url": "https://x.com/elonmusk/status/12345?utm_source=project",
                        "link_kind": "social_post",
                        "platform": "x",
                        "verification_status": "provider_metadata",
                    }
                    for token in tokens
                ]

            async def quote(self, chain, address):
                token = next(item for item in tokens if item.address == address)
                return token, TokenSnapshot("solana", token.address, 0.01, 100, 1000, 10, 1, 1)

        investigations = []

        async def search_context(candidate, observed, *, momentum_score, event_relation=None, retry_lane=False):
            investigations.append((candidate.token_id, momentum_score, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert {item[0] for item in investigations} == {token.token_id for token in tokens}
        assert all(
            item[1] < config["autonomous_search"]["context_min_momentum_score"]
            for item in investigations
        )
        assert all(item[2]["kind"] == "high_impact_account_post" for item in investigations)
        assert all(item[2]["endorsement_inferred"] is False for item in investigations)
        await runtime.close()

    asyncio.run(scenario())


def test_chain_only_multichain_data_persists_shared_chain_token_snapshots(
    tmp_path, monkeypatch,
):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["chain_meme_trader_only_enabled"] = True
        config["sources"]["dexscreener_discovery"]["chains"] = [
            "solana", "bsc", "robinhood",
        ]
        config["sources"]["dexscreener_discovery"]["surface_chains"] = [
            "solana", "bsc", "robinhood",
        ]
        runtime = Runtime(config, tmp_path)
        shared_evm_address = "0x" + "a" * 40
        tokens = {
            "solana": TokenCandidate(
                "solana", "S" * 32, "Solana new pool", "SOLNEW",
                source="geckoterminal:solana",
            ),
            "bsc": TokenCandidate(
                "bsc", shared_evm_address, "BSC new pool", "BSCNEW",
                source="geckoterminal:bsc",
            ),
            "robinhood": TokenCandidate(
                "robinhood", shared_evm_address, "Robinhood new pool", "RHNEW",
                source="geckoterminal:robinhood",
            ),
        }

        class Gecko:
            def __init__(self, http, network):
                self.network = network

            async def poll(self):
                return [tokens[self.network], tokens[self.network]]

        class Dex:
            DISCOVERY_SURFACES = {}

            async def batch_quote(self, chain, addresses):
                token = tokens[chain]
                assert addresses == [token.address]
                observed_at = utcnow()
                snapshot = TokenSnapshot(
                    chain, token.address, 1.0, 10_000, 20_000, 10, 1, 1,
                    observed_at=observed_at, ingested_at=observed_at,
                    provider="dexscreener",
                    raw={"pair": {
                        "chainId": chain, "pairAddress": f"{chain}-pair",
                        "priceUsd": "1.0",
                    }},
                )
                return {token.token_id: (token, snapshot)}

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        runtime.dex = Dex()
        await runtime.poll_multichain_meme_data_once()

        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM tokens WHERE address=?",
            (shared_evm_address,),
        ).fetchone()[0] == 2
        for token in tokens.values():
            assert runtime.store.token(token.token_id) is not None
            assert runtime.store.latest_snapshot(token.token_id) is not None
        scopes = {
            row["token_id"]: json.loads(row["metadata_json"])["scope"]
            for row in runtime.store.db.execute(
                "SELECT token_id,metadata_json FROM token_universe_funnel_transitions "
                "WHERE stage='metadata_hydration_result' AND status='hydrated'"
            )
        }
        assert scopes[tokens["solana"].token_id] == "candidate"
        assert scopes[tokens["bsc"].token_id] == "research_only"
        assert scopes[tokens["robinhood"].token_id] == "research_only"
        assert runtime.store.source_health()[0] is not None
        await runtime.close()

    asyncio.run(scenario())


def test_market_marks_batch_addresses_by_chain_before_quoting():
    async def scenario():
        runtime = Runtime.__new__(Runtime)
        runtime.chain_meme_trader_only = True
        calls = []
        applied = []

        class FakeStore:
            CHAIN_MEME_TRADER_ACTIVE_VERSION = "active"
            CHAIN_MEME_TRADER_V21_VERSION = "v21"
            CHAIN_MEME_TRADER_V20_VERSION = "v20"
            CHAIN_MEME_TRADER_V11_VERSION = "v11"

            @staticmethod
            def chain_meme_trader_has_open_positions(version):
                return False

            @staticmethod
            def chain_meme_trader_market_mark_targets(definition_versions=None):
                assert definition_versions == ["active"]
                return [
                    {"token_id": "bsc:0x1", "chain": "bsc", "address": "0x1"},
                    {"token_id": "solana:S1", "chain": "solana", "address": "S1"},
                    {"token_id": "bsc:0x2", "chain": "bsc", "address": "0x2"},
                ]

            @staticmethod
            def apply_chain_meme_trader_market_mark_batch(outcomes, recorded_at):
                applied.extend(outcomes)
                return len(outcomes)

            @staticmethod
            def evaluate_chain_meme_trader_market_marks(definition_version):
                assert definition_version == "active"

            @staticmethod
            def heartbeat(*args, **kwargs):
                return None

        async def batch_quote(chain, addresses, *, fresh=False):
            calls.append((chain, list(addresses), fresh))
            observed_at = utcnow()
            return {
                f"{chain}:{address}": (
                    TokenCandidate(chain, address, address),
                    TokenSnapshot(
                        chain, address, 1.0, 10_000, 20_000, 10, 1, 1,
                        observed_at=observed_at, ingested_at=observed_at,
                        provider="dexscreener",
                        raw={"pair": {"pairAddress": f"{chain}-{address}"}},
                    ),
                )
                for address in addresses
            }

        runtime.store = FakeStore()
        runtime._dex_batch_quote = batch_quote
        runtime._paper_quote_rejections = lambda *args: []
        await runtime.chain_meme_market_marks_once()

        assert calls == [
            ("bsc", ["0x1", "0x2"], True),
            ("solana", ["S1"], True),
        ]
        assert len(applied) == 3

    asyncio.run(scenario())


def test_v6_enrollment_uses_explicit_definition_chain_allowlist(tmp_path):
    store = Store(tmp_path / "multichain-definition.sqlite3", initial_cash_usd=1000)
    source = store.register_chain_meme_trader_v6()
    definition = json.loads(source["definition_json"])
    version = "test/explicit-bsc-definition"
    definition.update({"version": version, "chains": ["bsc"]})
    activated_at = iso()
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_registrations("
            "definition_version,code_registered_at,code_snapshot_frontier,definition_json) "
            "VALUES(?,?,0,?)",
            (version, activated_at, json.dumps(definition)),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_activations("
            "definition_version,activated_at,activation_snapshot_id,v5_definition_version,"
            "v5_source_frontier,entry_execution_enabled) VALUES(?,?,0,?,0,1)",
            (version, activated_at, Store.CHAIN_MEME_TRADER_VERSION),
        )

    observed_at = utcnow()
    token = TokenCandidate(
        "bsc", "0x" + "b" * 40, "BSC strategy candidate", "BSC",
        source="dexscreener",
    )
    store.upsert_token(token, seen_at=observed_at)
    store.add_snapshot(TokenSnapshot(
        "bsc", token.address, 1.0, 10_000, 20_000, 250, 2, 1,
        observed_at=observed_at, ingested_at=observed_at,
        provider="dexscreener",
        raw={"pair": {
            "chainId": "bsc", "pairAddress": "bsc-pair",
            "pairCreatedAt": round(
                (observed_at - timedelta(minutes=1)).timestamp() * 1000
            ),
            "priceUsd": "1.0",
            "baseToken": {"address": token.address},
            "txns": {
                "m5": {"buys": 2, "sells": 1},
                "h1": {"buys": 2, "sells": 1},
            },
            "volume": {"m5": 250.0, "h1": 250.0},
        }},
    ))

    assert store.enroll_chain_meme_trader_v6(
        definition_version=version,
    )["admitted"] == 1
    store.close()


def test_dexscreener_research_chain_hydrates_without_agent_or_candidate_admission(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["chains"] = ["solana", "base"]
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="base", address="0x" + "a" * 40, name="Base research", symbol="BASE"
        )
        snapshot = TokenSnapshot(
            "base", token.address, 0.01, 25_000, 100_000, 5_000, 20, 4
        )

        class Dex:
            DISCOVERY_SURFACES = {"token_profiles": ("/token-profiles/latest/v1", "identity")}

            async def discover_surface(self, surface, allowed_chains, limit=40):
                assert allowed_chains == {"solana", "bsc"}
                return []

            async def quote(self, chain, address):
                assert (chain, address) == (token.chain, token.address)
                return token, snapshot

        investigations = []

        async def search_context(*args, **kwargs):
            investigations.append((args, kwargs))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        discovery_round_id = runtime.store.start_token_discovery_round(
            provider="geckoterminal",
            surface="new_pools",
            mode="poll",
            chain_scope="base",
        )
        created = await runtime.ingest_token(token)
        runtime.store.add_token_discovery_exposure(
            discovery_round_id,
            token_id=token.token_id,
            chain=token.chain,
            role="new_pool",
            first_local_discovery=created,
            new_token=created,
            observed_at=token.first_seen_at,
        )
        runtime.store.finish_token_discovery_round(
            discovery_round_id,
            status="completed",
            requested_count=1,
            returned_count=1,
        )
        await runtime.poll_dexscreener_discovery_once()

        assert runtime.store.token(token.token_id) is not None
        assert runtime.store.latest_snapshot(token.token_id) is not None
        assert runtime.store.token_detail_hydration(token.token_id)["status"] == "hydrated"
        assert investigations == []
        transition = runtime.store.db.execute(
            "SELECT metadata_json FROM token_universe_funnel_transitions "
            "WHERE token_id=? AND stage='metadata_hydration_result' ORDER BY id DESC LIMIT 1",
            (token.token_id,),
        ).fetchone()
        assert json.loads(transition["metadata_json"])["scope"] == "research_only"
        await runtime.close()

    asyncio.run(scenario())


def test_dex_hydration_selects_one_highest_momentum_onchain_context_challenger(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        runtime = Runtime(config, tmp_path)
        lower = TokenCandidate(
            chain="solana", address="L" * 32, name="Lower momentum", symbol="LOW"
        )
        higher = TokenCandidate(
            chain="solana", address="M" * 32, name="Higher momentum", symbol="HIGH"
        )
        await runtime.ingest_token(lower)
        await runtime.ingest_token(higher)
        snapshots = {
            lower.token_id: TokenSnapshot(
                "solana", lower.address, 0.01, 20_000, 100_000, 20_000, 35, 5
            ),
            higher.token_id: TokenSnapshot(
                "solana", higher.address, 0.01, 100_000, 500_000, 100_000, 100, 5
            ),
        }

        class Dex:
            DISCOVERY_SURFACES = {}

            async def batch_quote(self, chain, addresses):
                assert chain == "solana"
                return {
                    token.token_id: (token, snapshots[token.token_id])
                    for token in (lower, higher)
                    if token.address in addresses
                }

        investigations = []

        async def search_context(candidate, observed, *, momentum_score, event_relation=None, retry_lane=False):
            investigations.append((candidate.token_id, momentum_score, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert len(investigations) == 1
        assert investigations[0][0] == higher.token_id
        assert investigations[0][2]["kind"] == "onchain_momentum"
        assert investigations[0][2]["selection_path"] == "hydration_onchain_challenger"
        assert investigations[0][2]["challenger_version"] == (
            runtime.store.TOKEN_CONTEXT_ONCHAIN_ADMISSION_CHALLENGER_VERSION
        )
        await runtime.close()

    asyncio.run(scenario())


def test_dex_hydration_fair_lane_can_place_onchain_before_unverified_metadata_lead(
    tmp_path,
):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        settings_path = tmp_path / "data" / "web_console" / "console_settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "watch_accounts": [
                        {
                            "platform": "x", "handle": "@elonmusk",
                            "url": "https://x.com/elonmusk", "entity_id": "elon_musk",
                            "priority": 4, "watch_cadence": "critical", "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        runtime = Runtime(config, tmp_path)
        metadata = TokenCandidate(
            chain="solana", address="N" * 32, name="Metadata lead", symbol="META"
        )
        onchain = TokenCandidate(
            chain="solana", address="P" * 32, name="Onchain lead", symbol="CHAIN"
        )
        await runtime.ingest_token(metadata)
        await runtime.ingest_token(onchain)
        runtime.store.set_kv(runtime.DIRECT_CONTEXT_LANE_CURSOR_KEY, 1)

        class Dex:
            DISCOVERY_SURFACES = {"token_profiles": ("/token-profiles/latest/v1", "identity")}

            async def discover_surface(self, surface, allowed_chains, limit=40):
                return [{
                    "token_id": metadata.token_id,
                    "chain": metadata.chain,
                    "address": metadata.address,
                    "provider": "dexscreener",
                    "discovery_surface": surface,
                    "role": "identity",
                    "original_url": "https://x.com/elonmusk/status/777",
                    "normalized_url": "https://x.com/elonmusk/status/777",
                    "link_kind": "social_post",
                    "platform": "x",
                    "verification_status": "provider_metadata",
                }]

            async def batch_quote(self, chain, addresses):
                return {
                    metadata.token_id: (
                        metadata,
                        TokenSnapshot("solana", metadata.address, 0.01, 20_000, 100_000, 100, 1, 1),
                    ),
                    onchain.token_id: (
                        onchain,
                        TokenSnapshot("solana", onchain.address, 0.01, 100_000, 500_000, 100_000, 100, 5),
                    ),
                }

        investigations = []

        async def search_context(candidate, observed, *, momentum_score, event_relation=None, retry_lane=False):
            investigations.append((candidate.token_id, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert [item[0] for item in investigations[:2]] == [
            onchain.token_id, metadata.token_id,
        ]
        assert investigations[0][1]["lane_preference"] == "onchain_first"
        assert investigations[0][1]["challenger_version"] == (
            runtime.store.TOKEN_CONTEXT_ONCHAIN_ADMISSION_CHALLENGER_VERSION
        )
        assert investigations[1][1]["kind"] == "high_impact_account_metadata_lead"
        assert investigations[1][1]["lane_scheduler_version"] == (
            runtime.store.TOKEN_CONTEXT_ONCHAIN_ADMISSION_CHALLENGER_VERSION
        )
        await runtime.close()

    asyncio.run(scenario())


def test_new_solana_tokens_enter_durable_batch_hydration_and_missing_pair_retries(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["max_hydrations_per_cycle"] = 30
        runtime = Runtime(config, tmp_path)
        found = TokenCandidate(chain="solana", address="A" * 32, name="Found", symbol="FOUND", source="pumpportal")
        missing = TokenCandidate(chain="solana", address="B" * 32, name="Missing", symbol="MISS", source="geckoterminal:solana")
        await runtime.ingest_token(found)
        await runtime.ingest_token(missing)
        snapshot = TokenSnapshot("solana", found.address, 0.01, 30000, 200000, 5000, 20, 5)

        class Dex:
            DISCOVERY_SURFACES = {}

            def __init__(self):
                self.calls = []

            async def batch_quote(self, chain, addresses):
                self.calls.append((chain, list(addresses)))
                return {found.token_id: (found, snapshot)}

        dex = Dex()
        runtime.dex = dex
        await runtime.poll_dexscreener_discovery_once()
        assert dex.calls == [("solana", [found.address, missing.address])]
        hydrated = runtime.store.token_detail_hydration(found.token_id)
        no_pair = runtime.store.token_detail_hydration(missing.token_id)
        assert hydrated["status"] == "hydrated" and hydrated["attempts"] == 1
        assert no_pair["status"] == "no_pair" and no_pair["attempts"] == 1
        assert no_pair["next_attempt_at"] is not None
        assert runtime.store.token(missing.token_id) is not None
        due_later = runtime.store.due_token_detail_hydrations(
            limit=30, now=utcnow() + timedelta(minutes=6)
        )
        assert [row["token_id"] for row in due_later] == [missing.token_id]
        await runtime.close()

    asyncio.run(scenario())


def test_due_hydration_prioritizes_exact_high_impact_social_links_without_dropping_fifo(tmp_path):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    oldest = TokenCandidate(chain="solana", address="O" * 32, name="Oldest")
    priority = TokenCandidate(chain="solana", address="P" * 32, name="Priority")
    ordinary = TokenCandidate(chain="solana", address="N" * 32, name="Ordinary")
    store.upsert_token(oldest, seen_at=now - timedelta(minutes=10))
    store.upsert_token(priority, seen_at=now - timedelta(minutes=2))
    store.upsert_token(ordinary, seen_at=now - timedelta(minutes=1))
    store.upsert_token_source_link(
        {
            "token_id": priority.token_id,
            "provider": "pumpportal",
            "discovery_surface": "launch_metadata",
            "role": "identity",
            "original_url": "https://x.com/elonmusk/status/123",
            "normalized_url": "https://x.com/elonmusk/status/123",
            "link_kind": "social_post",
            "label": "twitter",
            "platform": "x",
            "verification_status": "provider_metadata",
        },
        observed_at=now,
    )

    due = store.due_token_detail_hydrations(
        limit=3,
        now=now,
        priority_social_account_urls=["https://x.com/elonmusk"],
    )
    assert [row["token_id"] for row in due] == [
        priority.token_id,
        oldest.token_id,
        ordinary.token_id,
    ]
    store.close()


def test_due_hydration_can_prioritize_fresh_solana_without_changing_default_fifo(tmp_path):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    old_sol = TokenCandidate(chain="solana", address="O" * 32, name="Old Sol")
    new_sol = TokenCandidate(chain="solana", address="N" * 32, name="New Sol")
    bsc = TokenCandidate(chain="bsc", address="0x" + "b" * 40, name="BSC")
    store.upsert_token(old_sol, seen_at=now - timedelta(minutes=10))
    store.upsert_token(bsc, seen_at=now - timedelta(minutes=5))
    store.enqueue_token_detail_hydration("bsc", bsc.address, enqueued_at=now - timedelta(minutes=5))
    store.upsert_token(new_sol, seen_at=now - timedelta(minutes=1))

    assert [row["token_id"] for row in store.due_token_detail_hydrations(limit=3, now=now)] == [
        old_sol.token_id, bsc.token_id, new_sol.token_id,
    ]
    assert [row["token_id"] for row in store.due_token_detail_hydrations(
        limit=3, now=now, chains=("solana",), prefer_fresh=True,
    )] == [new_sol.token_id, old_sol.token_id]
    store.requeue_token_detail_hydration(old_sol.token_id, enqueued_at=now)
    assert [row["token_id"] for row in store.due_token_detail_hydrations(
        limit=2, now=now, chains=("solana",), prefer_fresh=True,
    )] == [new_sol.token_id, old_sol.token_id]
    store.close()


def test_exact_token_linked_browser_post_requeues_hydration_with_durable_priority(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="Q" * 32, name="Linked", symbol="LNK"
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="launch", mode="stream", chain_scope="solana"
        )
        runtime.store.add_token_discovery_exposure(
            round_id,
            token_id=token.token_id,
            chain="solana",
            role="launch",
            first_local_discovery=True,
            observed_at=utcnow(),
        )
        runtime.store.finish_token_discovery_round(round_id, status="completed")
        runtime.store.mark_token_detail_hydration(token.token_id, "hydrated")
        url = "https://x.com/community_signal/status/12345"
        runtime.store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "pumpportal",
                "discovery_surface": "launch_metadata",
                "role": "identity",
                "original_url": url,
                "normalized_url": url,
                "link_kind": "social_post",
                "platform": "x",
                "verification_status": "provider_metadata",
            },
            observed_at=utcnow(),
        )
        result = await runtime.ingest_observation(
            Observation(
                source="x:community_signal",
                source_kind="social",
                title="Exact token-linked post",
                text="A locally captured post linked by token metadata.",
                url=url + "/photo/1",
                availability_proof="local_receive",
                role="identity",
                source_item_id=url + "/photo/1",
                raw={"browser": {"platform": "x"}},
            )
        )
        assert result["token_context_handoff_count"] == 1
        hydration = runtime.store.token_detail_hydration(token.token_id)
        assert hydration["status"] == "pending"
        handoff = runtime.store.db.execute(
            "SELECT * FROM token_universe_funnel_transitions "
            "WHERE token_id=? AND stage='context_trigger_evaluation' "
            "AND reason_code='browser_exact_token_metadata_post_captured'",
            (token.token_id,),
        ).fetchone()
        assert handoff is not None
        assert handoff["observation_id"] is not None
        due = runtime.store.due_token_detail_hydrations(limit=1)
        assert due[0]["token_id"] == token.token_id
        plan = list(
            runtime.store.db.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT 1 FROM token_universe_funnel_transitions AS handoff
                WHERE handoff.token_id=?
                  AND handoff.stage='context_trigger_evaluation'
                  AND handoff.status='eligible'
                  AND handoff.reason_code='browser_exact_token_metadata_post_captured'
                  AND handoff.recorded_at>?
                """,
                (token.token_id, iso(utcnow() - timedelta(days=1))),
            )
        )
        assert any(
            "token_universe_funnel_transitions_exact_browser_token_idx" in str(row["detail"])
            for row in plan
        )
        await runtime.close()

    asyncio.run(scenario())


def test_dex_hydration_prefers_exact_browser_post_over_newer_unverified_metadata(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        runtime = Runtime(config, tmp_path)
        exact = TokenCandidate(
            chain="solana", address="V" * 32, name="Verified", symbol="VER"
        )
        unverified = TokenCandidate(
            chain="solana", address="U" * 32, name="Unverified", symbol="UNV"
        )
        await runtime.ingest_token(exact)
        await runtime.ingest_token(unverified)
        exact_url = "https://x.com/community_signal/status/12345"
        for token, url in (
            (exact, exact_url),
            (unverified, "https://x.com/unverified/status/67890"),
        ):
            runtime.store.upsert_token_source_link(
                {
                    "token_id": token.token_id,
                    "provider": "pumpportal",
                    "discovery_surface": "launch_metadata",
                    "role": "identity",
                    "original_url": url,
                    "normalized_url": url,
                    "link_kind": "social_post",
                    "platform": "x",
                    "verification_status": "provider_metadata",
                },
                observed_at=utcnow(),
            )
        await runtime.ingest_observation(
            Observation(
                source="x:community_signal",
                source_kind="social",
                title="Exact token-linked post",
                text="A locally captured post linked by token metadata.",
                url=exact_url + "/photo/1",
                availability_proof="local_receive",
                role="identity",
                source_item_id=exact_url + "/photo/1",
                raw={"browser": {"platform": "x"}},
            )
        )
        now = utcnow()

        class Dex:
            DISCOVERY_SURFACES = {}

            async def batch_quote(self, chain, addresses):
                return {
                    exact.token_id: (
                        exact,
                        TokenSnapshot(
                            "solana", exact.address, 0.01, 20_000, 100_000, 100, 1, 1,
                            observed_at=now,
                        ),
                    ),
                    unverified.token_id: (
                        unverified,
                        TokenSnapshot(
                            "solana", unverified.address, 0.01, 20_000, 100_000, 100, 1, 1,
                            observed_at=now + timedelta(seconds=10),
                        ),
                    ),
                }

        investigations = []

        async def search_context(
            candidate, observed, *, momentum_score, event_relation=None, retry_lane=False
        ):
            investigations.append((candidate.token_id, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert [item[0] for item in investigations] == [
            exact.token_id, unverified.token_id,
        ]
        assert investigations[0][1]["verification_status"] == (
            "browser_exact_entity_observation"
        )
        await runtime.close()

    asyncio.run(scenario())


def test_dex_hydration_bounds_exact_browser_lane_without_dropping_remainder(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        runtime = Runtime(config, tmp_path)
        exact_tokens = [
            TokenCandidate(
                chain="solana", address=letter * 32, name=f"Exact {letter}", symbol=letter
            )
            for letter in "ABCDE"
        ]
        for index, token in enumerate(exact_tokens):
            await runtime.ingest_token(token)
            url = f"https://x.com/source_{index}/status/{10000 + index}"
            runtime.store.upsert_token_source_link(
                {
                    "token_id": token.token_id,
                    "provider": "pumpportal",
                    "discovery_surface": "launch_metadata",
                    "role": "identity",
                    "original_url": url,
                    "normalized_url": url,
                    "link_kind": "social_post",
                    "platform": "x",
                    "verification_status": "provider_metadata",
                },
                observed_at=utcnow(),
            )
            runtime.store.add_observation(
                Observation(
                    source=f"x:source_{index}",
                    source_kind="social",
                    title=f"Exact post {index}",
                    text=f"Locally captured post {index}",
                    url=url,
                    availability_proof="local_receive",
                    role="identity",
                    source_item_id=url,
                    raw={"browser": {"platform": "x"}},
                )
            )
        now = utcnow()

        class Dex:
            DISCOVERY_SURFACES = {}

            async def batch_quote(self, chain, addresses):
                return {
                    token.token_id: (
                        token,
                        TokenSnapshot(
                            "solana", token.address, 0.01, 20_000, 100_000, 100, 1, 1,
                            observed_at=now + timedelta(seconds=index),
                        ),
                    )
                    for index, token in enumerate(exact_tokens)
                }

        investigations = []

        async def search_context(
            candidate, observed, *, momentum_score, event_relation=None, retry_lane=False
        ):
            investigations.append((candidate.token_id, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert len(investigations) == 4
        assert all(
            relation["selection_path"] == "hydration_browser_exact_post"
            for _, relation in investigations
        )
        selected_ids = {token_id for token_id, _ in investigations}
        deferred_ids = {token.token_id for token in exact_tokens} - selected_ids
        assert len(deferred_ids) == 1
        due = runtime.store.due_token_detail_hydrations(limit=10)
        assert {str(row["token_id"]) for row in due} == deferred_ids
        await runtime.close()

    asyncio.run(scenario())


def test_context_source_fair_order_prefers_distinct_unseen_posts_without_dropping_tokens(tmp_path):
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["bridge"]["enabled"] = False
    runtime = Runtime(config, tmp_path)
    now = utcnow()

    def candidate(address: str, url: str, seconds: int):
        token = TokenCandidate(chain="solana", address=address * 32, name=address)
        snapshot = TokenSnapshot(
            "solana", token.address, 0.01, 30_000, 100_000, 1_000, 10, 2,
            observed_at=now + timedelta(seconds=seconds),
        )
        trigger = {
            "kind": "high_impact_account_metadata_lead",
            "priority": 2,
            "url": url,
            "verification_status": "provider_metadata_unverified",
        }
        return (2, token, snapshot, 10.0, trigger)

    duplicate_old = candidate("A", "https://x.com/elonmusk/status/1", 1)
    already_seen = candidate("B", "https://x.com/elonmusk/status/2", 2)
    unseen_other = candidate("C", "https://x.com/elonmusk/status/3", 3)
    duplicate_new = candidate("D", "https://twitter.com/elonmusk/status/1?ref=x", 4)
    seen_key = runtime.autonomous_search.token_context_source_key(already_seen[4])

    ordered = runtime._source_fair_context_order(
        [duplicate_old, already_seen, unseen_other, duplicate_new],
        {seen_key},
    )

    assert [item[1].address[0] for item in ordered] == ["D", "C", "B", "A"]
    assert len(ordered) == 4
    exact_trigger = {
        **duplicate_new[4],
        "observation_id": 9,
        "observed_text": "locally captured body",
        "verification_status": "browser_exact_entity_observation",
    }
    assert runtime.autonomous_search.token_context_source_key(exact_trigger) != (
        runtime.autonomous_search.token_context_source_key(duplicate_new[4])
    )
    asyncio.run(runtime.close())


def test_dex_hydration_isolates_a_failed_30_address_chunk(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["candidate"]["chains"] = ["solana"]
        config["sources"]["dexscreener_discovery"]["max_hydrations_per_cycle"] = 31
        runtime = Runtime(config, tmp_path)
        tokens = [
            TokenCandidate(chain="solana", address=f"{index:032d}", name=f"Token {index}")
            for index in range(31)
        ]
        for token in tokens:
            await runtime.ingest_token(token)

        class Dex:
            DISCOVERY_SURFACES = {}

            def __init__(self):
                self.calls = []

            async def batch_quote(self, chain, addresses):
                self.calls.append(list(addresses))
                if len(self.calls) == 2:
                    raise RuntimeError("transient batch failure")
                return {
                    token.token_id: (
                        token,
                        TokenSnapshot("solana", token.address, 0.01, 30000, 200000, 5000, 20, 5),
                    )
                    for token in tokens[:30]
                }

        dex = Dex()
        runtime.dex = dex
        await runtime.poll_dexscreener_discovery_once()
        assert [len(call) for call in dex.calls] == [30, 1]
        assert all(
            runtime.store.token_detail_hydration(token.token_id)["status"] == "hydrated"
            for token in tokens[:30]
        )
        failed = runtime.store.token_detail_hydration(tokens[-1].token_id)
        assert failed["status"] == "error"
        assert failed["last_error"] == "RuntimeError: transient batch failure"
        await runtime.close()

    asyncio.run(scenario())


def test_browser_platform_heartbeat_persists_only_sanitized_access_state(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        await runtime.browser_heartbeat(
            "https://x.com/i/lists/1",
            {
                "platform": "x",
                "visible": True,
                "selector_count": "8",
                "extension_version": "0.6.6",
                "page_url": "https://x.com/i/lists/1?token=must-not-persist#private",
                "access_state": "content_visible",
                "password": "must-not-persist",
                "cookie": "must-not-persist",
            },
        )
        saved = runtime.store.get_kv("browser_platform_heartbeat:x")
        assert saved["access_state"] == "accessible"
        assert saved["selector_count"] == 8
        assert saved["extension_version"] == "0.6.6"
        assert saved["page_url"] == "https://x.com/i/lists/1"
        assert saved["contains_credentials"] is False
        assert "must-not-persist" not in json.dumps(saved)
        await runtime.browser_heartbeat(
            "https://x.com/home",
            {"platform": "x", "extension_version": "0.6.6<script>", "page_url": "https://x.com/home"},
        )
        assert runtime.store.get_kv("browser_platform_heartbeat:x")["extension_version"] is None
        await runtime.close()

    asyncio.run(scenario())


def test_browser_watch_learning_records_only_exact_configured_account_pages(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        settings_path = tmp_path / "data" / "web_console" / "console_settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "watch_accounts": [
                        {
                            "platform": "x", "handle": "@elonmusk",
                            "url": "https://x.com/elonmusk", "entity_id": "elon_musk",
                            "priority": 5, "watch_cadence": "critical", "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        runtime = Runtime(config, tmp_path)

        await runtime.browser_heartbeat(
            "browser:x",
            {"platform": "x", "page_url": "https://x.com/home",
             "access_state": "content_visible", "visible": True, "selector_count": 10},
        )
        empty = runtime.store.watch_account_exposure_summary_from_connection(runtime.store.db)
        assert empty["summary"]["browser_exposure_windows"] == 0

        await runtime.browser_heartbeat(
            "browser:x",
            {"platform": "x", "page_url": "https://twitter.com/elonmusk?private=value#fragment",
             "access_state": "content_visible", "visible": True, "selector_count": 12},
        )
        exposed = runtime.store.watch_account_exposure_summary_from_connection(runtime.store.db)
        assert exposed["summary"]["browser_exposure_windows"] == 1
        assert exposed["summary"]["browser_completed_account_exposures"] == 1
        assert exposed["summary"]["exact_source_hits"] == 0

        observation = Observation(
            source="browser:x:elonmusk",
            source_kind="social",
            title="A newly observed exact public post",
            text="A newly observed exact public post with enough detail for event clustering.",
            url="https://x.com/elonmusk/status/12345",
            author="@elonmusk",
            published_at=utcnow() - timedelta(minutes=1),
            availability_proof="local_receive",
            role="feature",
            raw={
                "source_entity_id": "elon_musk",
                "browser": {
                    "platform": "x", "author": "@elonmusk",
                    "source_entity_id": "elon_musk",
                    "url": "https://x.com/elonmusk/status/12345",
                },
            },
        )
        await runtime.ingest_observation(observation)
        learned = runtime.store.watch_account_exposure_summary_from_connection(runtime.store.db)
        assert learned["summary"]["exact_source_hits"] == 1
        assert learned["summary"]["accepted_events"] == 1
        assert learned["items"][0]["browser_bridge_exposures"] == 1
        link = runtime.store.db.execute(
            "SELECT * FROM browser_watch_observation_links"
        ).fetchone()
        assert link is not None and link["decision_eligible"] == 1
        addressability = runtime.store.db.execute(
            "SELECT * FROM kol_token_addressability_cohorts"
        ).fetchone()
        assert addressability is not None
        assert addressability["seed_status"] == "no_seed_at_signal"
        assert addressability["attention_point_id"] > 0
        assert addressability["attention_definition_version"] == (
            runtime.store.EVENT_ATTENTION_TRAJECTORY_VERSION
        )

        await runtime.browser_heartbeat(
            "browser:x",
            {"platform": "x", "page_url": "https://x.com/elonmusk",
             "access_state": "login_required", "visible": True, "selector_count": 1},
        )
        preserved = runtime.store.db.execute(
            "SELECT status FROM browser_watch_account_exposures"
        ).fetchone()
        assert preserved["status"] == "completed"
        await runtime.close()

    asyncio.run(scenario())


def test_doctor_treats_unrequired_security_endpoint_failure_as_warning(tmp_path, monkeypatch, capsys):
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["sources"]["rss"] = []
    config["sources"]["bluesky_queries"] = []
    config["safety"]["require_evm_simulation"] = False
    config["safety"]["require_solana_report"] = False
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    class FakeResponse:
        status_code = 200

        def __init__(self, url):
            self.url = url

        def json(self):
            if "api.jup.ag" in self.url:
                return {"transaction": None, "outAmount": "2", "otherAmountThreshold": "1",
                        "routePlan": [{"swapInfo": {"label": "fixture"}}]}
            if "gopluslabs.io" in self.url:
                return {"code": 1, "result": {"probe": {"safe": "1"}}}
            if "rugcheck.xyz" in self.url:
                return {"score": 1, "risks": []}
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            if "honeypot.is" in url:
                raise TimeoutError("optional endpoint unavailable")
            return FakeResponse(url)

    monkeypatch.setattr("memetrader.cli.httpx.Client", FakeClient)
    assert cmd_doctor(str(path), True) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["warnings"] == ["online:honeypot"]
    assert output["errors"] == []

    config["safety"]["require_evm_simulation"] = True
    path.write_text(json.dumps(config), encoding="utf-8")
    assert cmd_doctor(str(path), True) == 4
    output = json.loads(capsys.readouterr().out)
    assert output["errors"] == ["online:honeypot"]


def test_doctor_requires_at_least_one_provider_per_security_family(tmp_path, monkeypatch, capsys):
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["candidate"]["chains"] = ["solana", "bsc"]
    config["sources"]["rss"] = []
    config["sources"]["bluesky_queries"] = []
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    class FakeResponse:
        status_code = 200

        def __init__(self, url):
            self.url = url

        def json(self):
            if "api.jup.ag" in self.url:
                return {"transaction": None, "outAmount": "2", "otherAmountThreshold": "1",
                        "routePlan": [{"swapInfo": {"label": "fixture"}}]}
            if "gopluslabs.io" in self.url:
                return {"code": 1, "result": {"probe": {"safe": "1"}}}
            if "rugcheck.xyz" in self.url:
                return {"score": 1, "risks": []}
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            if "gopluslabs.io/api/v1/token_security/56" in url or "honeypot.is" in url:
                raise TimeoutError("all EVM security providers unavailable")
            return FakeResponse(url)

    monkeypatch.setattr("memetrader.cli.httpx.Client", FakeClient)
    assert cmd_doctor(str(path), True) == 4
    output = json.loads(capsys.readouterr().out)
    assert "online:evm_security_provider" in output["errors"]
    assert "online:solana_security_provider" not in output["errors"]


def test_live_cannot_be_enabled(tmp_path):
    config = initial_config()
    config["live"]["enabled"] = True
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="live.enabled"):
        load_config(path)


def test_non_paper_mode_is_rejected(tmp_path):
    config = initial_config()
    config["mode"] = "live"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="shadow and paper"):
        load_config(path)


def test_agent_concurrency_is_hard_limited_to_two(tmp_path):
    config = initial_config()
    config["autonomous_search"]["max_concurrent_agents"] = 3
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="between 1 and 2"):
        load_config(path)


def test_single_instance_lock(tmp_path):
    lock = tmp_path / "robot.lock"
    with SingleInstance(lock):
        with pytest.raises(RuntimeError, match="already running"):
            with SingleInstance(lock):
                pass
    with SingleInstance(lock):
        pass


def test_notifier_always_persists_local_jsonl(tmp_path):
    notifier = Notifier(tmp_path, {"jsonl": "notifications.jsonl"})
    notifier.send("event_new", "Example", {"event_id": 1})
    line = (tmp_path / "notifications.jsonl").read_text(encoding="utf-8")
    assert '"event_new"' in line and '"event_id": 1' in line


def test_candidate_decision_persists_computed_position_size(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["notifications"]["jsonl"] = "notifications.jsonl"
        config["event_min_attention"] = 0
        runtime = Runtime(config, tmp_path)
        event_id, _, _ = runtime.events.ingest(
            Observation(source="x:official", source_kind="official_social", title="Example launch", text="Example")
        )
        token = TokenCandidate(chain="solana", address="A" * 32, name="Example", symbol="EX")
        runtime.store.upsert_token(token)
        snapshot = TokenSnapshot("solana", token.address, 1.0, 100000, 1000000, 50000, 30, 10)
        runtime.store.add_snapshot(snapshot)

        class FakeDex:
            async def quote(self, chain, address):
                return token, snapshot

        runtime.dex = FakeDex()

        class FakeEvaluator:
            async def discover_and_decide(self, event):
                decision = CandidateDecision(event.id, token.token_id, "CANDIDATE", 85, 90, 20, ["test"])
                runtime.store.set_candidate_ranking(
                    event.id,
                    {
                        "version": 1,
                        "evaluated_at": iso(),
                        "status": "completed",
                        "outcome": "CANDIDATE",
                        "candidates": [
                            {
                                "rank": 1,
                                "token_id": token.token_id,
                                "action": "CANDIDATE",
                                "position_usd": 0,
                                "reasons": ["test"],
                                "rejected_reasons": [],
                            }
                        ],
                        "final_outcome": {"decision_id": None, "action": "CANDIDATE"},
                    },
                )
                return decision

        runtime.evaluator = FakeEvaluator()
        await runtime.evaluate_events_once()
        row = runtime.store.decisions(1)[0]
        assert row["position_usd"] > 0
        assert runtime.store.position(token.token_id) is not None
        ranking = runtime.store.candidate_ranking(event_id)
        assert ranking["final_outcome"]["decision_id"] == row["id"]
        assert ranking["final_outcome"]["position_usd"] == row["position_usd"]
        assert ranking["candidates"][0]["position_usd"] == row["position_usd"]
        cohort = runtime.store.db.execute("SELECT * FROM shadow_event_cohorts").fetchone()
        assert cohort is not None
        assert cohort["event_id"] == event_id
        assert cohort["token_id"] == token.token_id
        assert cohort["action"] == "CANDIDATE"
        position = runtime.store.position(token.token_id)
        assert position.decision_id == row["id"]
        assert position.cohort_id == cohort["id"]
        buy = runtime.store.db.execute(
            "SELECT decision_id,cohort_id FROM trades WHERE side='BUY'"
        ).fetchone()
        assert buy["decision_id"] == row["id"]
        assert buy["cohort_id"] == cohort["id"]

        runtime.store.set_kv(f"event_decision_next:{event_id}", "1970-01-01T00:00:00Z")
        await runtime.evaluate_events_once()
        adjusted = runtime.store.decisions(1)[0]
        assert adjusted["action"] == "WAIT"
        assert json.loads(adjusted["rejected_reasons_json"]) == ["position_already_open"]
        adjusted_ranking = runtime.store.candidate_ranking(event_id)
        assert adjusted_ranking["final_outcome"]["decision_id"] == adjusted["id"]
        assert adjusted_ranking["final_outcome"]["action"] == "WAIT"
        assert adjusted_ranking["final_outcome"]["position_usd"] == 0
        assert adjusted_ranking["candidates"][0]["action"] == "WAIT"
        assert adjusted_ranking["candidates"][0]["rejected_reasons"] == ["position_already_open"]
        assert runtime.store.db.execute("SELECT COUNT(*) FROM shadow_event_cohorts").fetchone()[0] == 1
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM information_first_shadow_cohorts"
        ).fetchone()[0] == 1
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM information_first_shadow_admission_attempts"
        ).fetchone()[0] == 2
        await runtime.close()

    asyncio.run(scenario())


def test_bsc_candidate_waits_until_amount_specific_route_and_chain_fee_exist(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["event_min_attention"] = 0
        runtime = Runtime(config, tmp_path)
        event_id, _, _ = runtime.events.ingest(Observation(
            source="news", source_kind="news", title="BSC meme event", text="BSC meme",
        ))
        token = TokenCandidate(
            chain="bsc", address="0x" + "a" * 40, name="BSC Meme", symbol="BSCM",
        )
        snapshot = TokenSnapshot(
            "bsc", token.address, 1.0, 100_000, 1_000_000, 50_000, 30, 10,
        )
        runtime.store.upsert_token(token)
        runtime.store.add_snapshot(snapshot)

        class FakeDex:
            calls = 0

            async def quote(self, chain, address):
                self.calls += 1
                return token, snapshot

        runtime.dex = FakeDex()

        class FakeEvaluator:
            async def discover_and_decide(self, event):
                runtime.store.set_candidate_ranking(
                    event.id,
                    {
                        "version": 1,
                        "evaluated_at": iso(),
                        "status": "completed",
                        "outcome": "CANDIDATE",
                        "candidates": [{
                            "rank": 1, "token_id": token.token_id,
                            "action": "CANDIDATE", "position_usd": 0,
                            "reasons": ["test"], "rejected_reasons": [],
                        }],
                        "final_outcome": {"decision_id": None, "action": "CANDIDATE"},
                    },
                )
                return CandidateDecision(
                    event.id, token.token_id, "CANDIDATE", 85, 90, 20, ["test"],
                )

        runtime.evaluator = FakeEvaluator()
        await runtime.evaluate_events_once()
        decision = runtime.store.decisions(1)[0]
        assert decision["action"] == "WAIT"
        assert json.loads(decision["rejected_reasons_json"]) == [
            "paper_amount_specific_route_unavailable_bsc",
        ]
        assert runtime.dex.calls == 0
        assert runtime.store.position(token.token_id) is None
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        attempt = runtime.store.db.execute(
            "SELECT * FROM paper_execution_attempts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert attempt["status"] == "rejected"
        assert attempt["reason"] == "amount_specific_route_and_chain_fee_unavailable"
        await runtime.close()

    asyncio.run(scenario())


def test_store_reopen_does_not_reset_paper_cash(tmp_path):
    from memetrader.store import Store

    path = tmp_path / "account.sqlite3"
    store = Store(path, initial_cash_usd=1000)
    with store.db:
        store.db.execute("UPDATE paper_account SET cash_usd=777 WHERE singleton=1")
    store.close()

    reopened = Store(path, initial_cash_usd=10000)
    assert reopened.account()["cash_usd"] == 777
    reopened.close()


def test_promotional_listicle_is_stored_but_cannot_create_attention(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["notifications"]["jsonl"] = "notifications.jsonl"
        runtime = Runtime(config, tmp_path)
        await runtime.ingest_observation(
            Observation(
                source="google-news-memecoin",
                source_kind="news",
                title="Top 7 Meme Coins to Watch as a Presale Countdown Begins",
                availability_proof="local_poll",
            )
        )
        row = runtime.store.db.execute("SELECT role FROM observations").fetchone()
        event = runtime.store.active_events(minutes=60, limit=1)[0]
        assert row["role"] == "promotion"
        assert event.attention == 0
        await runtime.close()

    asyncio.run(scenario())


def test_pump_launch_metadata_is_bounded_and_persists_identity_links(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana",
            address="U" * 32,
            name="Launch metadata",
            source="pumpportal:create",
            raw={"uri": "https://metadata.example/token.json"},
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window", chain_scope="solana"
        )
        exposure_id = runtime.store.add_token_discovery_exposure(
            round_id,
            token_id=token.token_id,
            chain=token.chain,
            role="create",
            first_local_discovery=True,
            new_token=True,
            observed_at=token.first_seen_at,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )

        class Response:
            def json(self):
                return {
                    "description": "A new community token.",
                    "website": "https://example.com/project",
                    "twitter": "https://x.com/project",
                    "telegram": "https://t.me/project",
                }

        class Http:
            async def get_public_document(self, url, **kwargs):
                assert url == "https://metadata.example/token.json"
                assert kwargs["maximum_bytes"] == 131072
                return Response()

            async def close(self):
                pass

        runtime.http = Http()
        assert exposure_id is not None
        await runtime._hydrate_pump_metadata(
            token, round_id=round_id, exposure_id=exposure_id
        )
        links = runtime.store.token_source_links(token.token_id)
        assert {row["link_kind"] for row in links} == {
            "website", "social_profile", "telegram_manual"
        }
        stored = runtime.store.token(token.token_id)
        assert stored is not None
        assert stored.raw["description"] == "A new community token."
        transitions = runtime.store.db.execute(
            "SELECT stage,status,reason_code FROM token_universe_funnel_transitions "
            "WHERE token_id=? AND stage LIKE 'metadata_hydration_%' ORDER BY id",
            (token.token_id,),
        ).fetchall()
        assert [(row["stage"], row["status"]) for row in transitions] == [
            ("metadata_hydration_attempt", "attempted"),
            ("metadata_hydration_result", "hydrated"),
        ]
        linked = runtime.store.db.execute(
            "SELECT COUNT(*) FROM token_discovery_exposure_source_links WHERE exposure_id=?",
            (exposure_id,),
        ).fetchone()[0]
        assert linked == 3
        await runtime.close()

    asyncio.run(scenario())


def test_pump_launch_metadata_retries_transient_http_once(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="R" * 32, name="Retry metadata",
            source="pumpportal:create",
            raw={"uri": "https://ipfs.io/ipfs/bafy-test-metadata"},
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana",
        )
        exposure_id = runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
            observed_at=token.first_seen_at,
        )

        class Response:
            def json(self):
                return {"description": "Recovered", "website": "https://example.com"}

        class Http:
            calls = 0
            urls = []

            async def get_public_document(self, url, **kwargs):
                self.calls += 1
                self.urls.append(url)
                if self.calls == 1:
                    request = httpx.Request("GET", url)
                    response = httpx.Response(
                        503, headers={"Retry-After": "0"}, request=request
                    )
                    raise httpx.HTTPStatusError(
                        "temporary", request=request, response=response
                    )
                return Response()

            async def close(self):
                pass

        runtime.http = Http()
        assert exposure_id is not None
        await runtime._hydrate_pump_metadata(
            token, round_id=round_id, exposure_id=exposure_id
        )
        result = runtime.store.db.execute(
            "SELECT status,reason_code,metadata_json FROM "
            "token_universe_funnel_transitions WHERE token_id=? AND "
            "stage='metadata_hydration_result' ORDER BY id DESC LIMIT 1",
            (token.token_id,),
        ).fetchone()
        assert runtime.http.calls == 2
        assert runtime.http.urls == [
            "https://ipfs.io/ipfs/bafy-test-metadata",
            "https://gateway.pinata.cloud/ipfs/bafy-test-metadata",
        ]
        assert (result["status"], result["reason_code"]) == (
            "hydrated", "metadata_links_found"
        )
        result_metadata = json.loads(result["metadata_json"])
        assert result_metadata["attempt_count"] == 2
        assert result_metadata["document_host"] == "ipfs.io"
        assert result_metadata["retrieval_host"] == "gateway.pinata.cloud"
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM system_error_cases"
        ).fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_pump_launch_metadata_http_404_is_token_coverage_not_system_error(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="N" * 32, name="Missing metadata",
            source="pumpportal:create", raw={"uri": "https://metadata.example/missing.json"},
        )
        await runtime.ingest_token(token)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana",
        )
        exposure_id = runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
            observed_at=token.first_seen_at,
        )

        class Http:
            calls = 0

            async def get_public_document(self, url, **kwargs):
                self.calls += 1
                request = httpx.Request("GET", url)
                response = httpx.Response(404, request=request)
                raise httpx.HTTPStatusError(
                    "missing", request=request, response=response
                )

            async def close(self):
                pass

        runtime.http = Http()
        assert exposure_id is not None
        await runtime._hydrate_pump_metadata(
            token, round_id=round_id, exposure_id=exposure_id
        )
        result = runtime.store.db.execute(
            "SELECT status,reason_code,metadata_json FROM "
            "token_universe_funnel_transitions WHERE token_id=? AND "
            "stage='metadata_hydration_result' ORDER BY id DESC LIMIT 1",
            (token.token_id,),
        ).fetchone()
        metadata = json.loads(result["metadata_json"])
        assert runtime.http.calls == 1
        assert (result["status"], result["reason_code"]) == (
            "unavailable", "http_status_404"
        )
        assert metadata["document_host"] == "metadata.example"
        assert metadata["http_status"] == 404
        assert metadata["attempt_count"] == 1
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM system_error_cases"
        ).fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_returns_revision_handoff_when_observation_anchor_is_reused(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        common = {
            "source": "browser:x:publisher",
            "source_kind": "social",
            "title": "Publisher reports a meme event",
            "url": "https://x.com/publisher/status/9001",
            "source_item_id": "x:publisher:9001",
            "observed_at": now,
            "ingested_at": now,
            "availability_proof": "local_receive",
        }
        first = await runtime.ingest_observation(
            Observation(text="Original report", raw={"source_item_state": "present"}, **common)
        )
        second = await runtime.ingest_observation(
            Observation(
                text="Publisher correction",
                role="identity",
                raw={
                    "source_item_state": "correction",
                    "source_item_state_evidence": "publisher_correction_marker",
                    "claim_target_url": common["url"],
                },
                **common,
            )
        )
        assert first["observation_created"] is True
        assert first["revision_id"] is not None
        assert first["claim_relation_ids"] == []
        assert second["event_id"] == first["event_id"]
        assert second["observation_created"] is False
        assert second["revision_id"] is not None
        assert len(second["claim_relation_ids"]) == 2
        relations = list(
            runtime.store.db.execute(
                "SELECT id,source_revision_id,relation_type,decision_eligible,affects "
                "FROM event_claim_relations WHERE id IN (?,?) ORDER BY id",
                tuple(second["claim_relation_ids"]),
            )
        )
        assert {row["id"] for row in relations} == set(second["claim_relation_ids"])
        assert {row["source_revision_id"] for row in relations} == {second["revision_id"]}
        assert {row["relation_type"] for row in relations} == {"supersedes", "corrects"}
        assert all(row["decision_eligible"] == 0 and row["affects"] == "none" for row in relations)
        assert len(second["shadow_review"]) == 1
        assert second["shadow_review"][0]["status"] == "coverage_gap"
        assert second["shadow_review"][0]["reason"] == "no_token_binding"
        assert second["shadow_review"][0]["transition_id"] is None
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_shadow_review_correction_records_overlay_and_cohort_gap(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        common = {
            "source": "browser:x:reviewed-publisher",
            "source_kind": "social",
            "title": "Reviewed publisher reports a distinct meme event",
            "url": "https://x.com/reviewedpublisher/status/9101",
            "source_item_id": "x:reviewedpublisher:9101",
            "availability_proof": "local_receive",
        }
        first = await runtime.ingest_observation(
            Observation(
                text="Original report", observed_at=now, ingested_at=now,
                raw={"source_item_state": "present"}, **common,
            )
        )
        event_id = int(first["event_id"])
        uncovered = TokenCandidate(
            chain="solana", address="U" * 32, name="Uncovered Review", symbol="UGAP"
        )
        runtime.store.upsert_token(uncovered, seen_at=now)
        uncovered_decision_id = runtime.store.add_decision(
            CandidateDecision(
                event_id, uncovered.token_id, "WAIT", 60, 75, 6,
                ["forward review target"], created_at=utcnow(),
            )
        )
        first_correction = await runtime.ingest_observation(
            Observation(
                text="First publisher correction", role="identity",
                observed_at=utcnow(), ingested_at=utcnow(),
                raw={
                    "source_item_state": "correction",
                    "source_item_state_evidence": "publisher_correction_marker",
                    "claim_target_url": common["url"],
                },
                **common,
            )
        )
        assert first_correction["shadow_review"][0]["status"] == "coverage_gap"
        assert first_correction["shadow_review"][0]["reason"] == "no_universe_cohort"
        gap = runtime.store.db.execute(
            "SELECT r.*,i.relation_id,i.dispatch_count AS input_dispatch_count "
            "FROM agent_shadow_review_results r "
            "JOIN agent_shadow_review_inputs i ON i.id=r.input_id "
            "WHERE r.id=?",
            (first_correction["shadow_review"][0]["result_id"],),
        ).fetchone()
        assert gap["definition_version"] == runtime.store.AGENT_SHADOW_REVIEW_VERSION
        assert gap["token_id"] == uncovered.token_id
        assert gap["event_id"] == event_id
        assert gap["decision_id"] == uncovered_decision_id
        assert gap["dispatch_count"] == gap["input_dispatch_count"] == 0
        assert gap["decision_eligible"] == 0
        assert gap["affects"] == "none"

        covered = TokenCandidate(
            chain="solana", address="C" * 32, name="Covered Review", symbol="COVER"
        )
        runtime.store.upsert_token(covered, seen_at=utcnow())
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana", started_at=utcnow(),
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=covered.token_id, chain=covered.chain, role="create",
            first_local_discovery=True, new_token=True, observed_at=utcnow(),
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )
        covered_decision_id = runtime.store.add_decision(
            CandidateDecision(
                event_id, covered.token_id, "WAIT", 62, 78, 7,
                ["covered forward review target"], created_at=utcnow(),
            )
        )
        runtime.store.paper_buy(
            event_id=event_id,
            token=covered,
            price=0.001,
            gross_usd=1.0,
            fee_bps=0,
            reason="shadow_review_position_fixture",
            decision_id=covered_decision_id,
        )
        side_effect_queries = {
            "agent_attempts": "SELECT COUNT(*) FROM agent_attempts",
            "context_admissions": "SELECT COUNT(*) FROM token_context_admission_attempts",
            "shadow_admissions": "SELECT COUNT(*) FROM shadow_event_admission_attempts",
            "information_admissions": (
                "SELECT COUNT(*) FROM information_first_shadow_admission_attempts"
            ),
            "agent_dispatches": (
                "SELECT COUNT(*) FROM token_universe_funnel_transitions "
                "WHERE stage='agent_dispatch'"
            ),
            "decisions": "SELECT COUNT(*) FROM decisions",
        }
        side_effect_counts_before = {
            name: runtime.store.db.execute(query).fetchone()[0]
            for name, query in side_effect_queries.items()
        }
        second_correction = await runtime.ingest_observation(
            Observation(
                text="Second publisher correction", role="identity",
                observed_at=utcnow(), ingested_at=utcnow(),
                raw={
                    "source_item_state": "correction",
                    "source_item_state_evidence": "publisher_correction_marker",
                    "claim_target_url": common["url"],
                },
                **common,
            )
        )
        assert len(second_correction["shadow_review"]) == 1
        assert second_correction["shadow_review"][0]["status"] == "shadow_triggered"
        assert second_correction["shadow_review"][0]["reason"] == "shadow_review_correction"
        assert second_correction["shadow_review"][0]["transition_id"] is not None
        transition = runtime.store.db.execute(
            "SELECT * FROM token_universe_funnel_transitions "
            "WHERE definition_version=?",
            (runtime.store.AGENT_SHADOW_REVIEW_VERSION,),
        ).fetchone()
        assert transition["token_id"] == covered.token_id
        assert transition["event_id"] == event_id
        assert transition["decision_id"] == covered_decision_id
        assert transition["stage"] == "context_trigger_evaluation"
        assert transition["status"] == "shadow_triggered"
        assert transition["reason_code"] == "shadow_review_correction"
        assert transition["decision_eligible"] == 0
        assert transition["affects"] == "none"
        metadata = json.loads(transition["metadata_json"])
        assert metadata["dispatch_requested"] == 0
        assert metadata["dispatch_count"] == 0
        assert metadata["uses_agent_quota"] == 0
        assert metadata["window_minutes"] == 15
        assert metadata["target_scope"] == "position"
        assert metadata["position_open_at_trigger"] == 1
        result_row = runtime.store.db.execute(
            "SELECT buy_trade_id FROM agent_shadow_review_results "
            "WHERE transition_id=?",
            (second_correction["shadow_review"][0]["transition_id"],),
        ).fetchone()
        assert result_row["buy_trade_id"] is not None
        buy_trade = runtime.store.db.execute(
            "SELECT side,token_id,event_id FROM trades WHERE id=?",
            (result_row["buy_trade_id"],),
        ).fetchone()
        assert buy_trade["side"] == "BUY"
        assert buy_trade["token_id"] == covered.token_id
        assert buy_trade["event_id"] == event_id
        unresolved = await runtime.ingest_observation(
            Observation(
                source=common["source"], source_kind=common["source_kind"],
                title="Publisher retracts an unknown item",
                text="Unresolved retraction", role="identity",
                url="https://x.com/reviewedpublisher/status/9102",
                source_item_id="x:reviewedpublisher:9102",
                observed_at=utcnow(), ingested_at=utcnow(),
                availability_proof="local_receive",
                raw={
                    "source_item_state": "retracted",
                    "source_item_state_evidence": "publisher_retraction_marker",
                    "claim_target_url": "https://x.com/reviewedpublisher/status/not-found",
                },
            )
        )
        assert len(unresolved["shadow_review"]) == 1
        assert unresolved["shadow_review"][0]["status"] == "ineligible"
        assert unresolved["shadow_review"][0]["reason"] == "relation_target_not_found"
        assert unresolved["shadow_review"][0]["transition_id"] is None
        runtime.store.process_agent_shadow_review_inputs()
        assert runtime.store.db.execute(
            "SELECT COUNT(*) FROM agent_shadow_review_inputs"
        ).fetchone()[0] == runtime.store.db.execute(
            "SELECT COUNT(*) FROM agent_shadow_review_results"
        ).fetchone()[0]
        summary = runtime.store.agent_shadow_review_summary_from_connection(
            runtime.store.db
        )
        assert summary["status"] == "collecting"
        assert summary["summary"]["inputs"] == 3
        assert summary["summary"]["terminal_results"] == 3
        assert summary["summary"]["pending"] == 0
        assert summary["summary"]["shadow_triggered"] == 1
        assert summary["summary"]["coverage_gap"] == 1
        assert summary["summary"]["ineligible"] == 1
        assert summary["summary"]["dispatch_count"] == 0
        assert summary["maturity_gate"]["real_dispatch_allowed"] is False
        assert summary["decision_eligible"] is False
        assert summary["affects"] == "none"
        assert side_effect_counts_before == {
            name: runtime.store.db.execute(query).fetchone()[0]
            for name, query in side_effect_queries.items()
        }
        with pytest.raises(sqlite3.IntegrityError):
            runtime.store.db.execute(
                "UPDATE agent_shadow_review_results SET dispatch_count=1"
            )
        await runtime.close()

    asyncio.run(scenario())


def test_runtime_shadow_review_rejects_ambiguous_target_event(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        common = {
            "source": "browser:x:ambiguous-publisher",
            "source_kind": "social",
            "title": "Publisher report linked to two event clusters",
            "url": "https://x.com/ambiguouspublisher/status/9201",
            "source_item_id": "x:ambiguouspublisher:9201",
            "availability_proof": "local_receive",
        }
        original = await runtime.ingest_observation(
            Observation(
                text="Original report", observed_at=now, ingested_at=now,
                raw={"source_item_state": "present"}, **common,
            )
        )
        observation_id = runtime.store.db.execute(
            "SELECT observation_id FROM event_observations WHERE event_id=?",
            (int(original["event_id"]),),
        ).fetchone()["observation_id"]
        second_event_id = runtime.store.create_event(
            "Second cluster for the same report", [], 10, first_seen_at=now
        )
        runtime.store.link_event_observation(second_event_id, int(observation_id))

        correction = await runtime.ingest_observation(
            Observation(
                text="Publisher correction", role="identity",
                observed_at=utcnow(), ingested_at=utcnow(),
                raw={
                    "source_item_state": "correction",
                    "source_item_state_evidence": "publisher_correction_marker",
                    "claim_target_url": common["url"],
                },
                **common,
            )
        )
        assert len(correction["shadow_review"]) == 1
        assert correction["shadow_review"][0]["status"] == "coverage_gap"
        assert correction["shadow_review"][0]["reason"] == "ambiguous_target_event"
        assert correction["shadow_review"][0]["transition_id"] is None
        result = runtime.store.db.execute(
            "SELECT metadata_json,dispatch_count,decision_eligible,affects "
            "FROM agent_shadow_review_results WHERE id=?",
            (correction["shadow_review"][0]["result_id"],),
        ).fetchone()
        assert json.loads(result["metadata_json"])["target_event_count"] == 2
        assert result["dispatch_count"] == 0
        assert result["decision_eligible"] == 0
        assert result["affects"] == "none"
        await runtime.close()

    asyncio.run(scenario())


def test_raw_items_are_stored_without_notification_spam(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["notifications"]["jsonl"] = "notifications.jsonl"
        config["notifications"]["notify_raw_events"] = False
        config["notifications"]["notify_new_tokens"] = False
        config["notifications"]["minimum_event_attention"] = 40
        runtime = Runtime(config, tmp_path)
        await runtime.ingest_observation(
            Observation(source="rss:a", source_kind="news", title="One ordinary single-source article")
        )
        before_events = runtime.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        await runtime.ingest_token(
            TokenCandidate(chain="solana", address="B" * 32, name="A random new token", symbol="RND")
        )
        after_events = runtime.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert before_events == after_events == 1
        assert runtime.store.token("solana:" + "B" * 32) is not None
        notification_path = tmp_path / "notifications.jsonl"
        assert not notification_path.exists() or notification_path.read_text(encoding="utf-8").strip() == ""
        await runtime.close()

    asyncio.run(scenario())


def test_stale_polled_features_and_confirmations_are_identity_only(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        for role in ("feature", "confirmation"):
            observation = Observation(
                source=f"rss:archive:{role}",
                source_kind="news",
                title=f"An old {role} article first discovered today",
                role=role,
                published_at="2026-01-01T00:00:00Z",
                observed_at="2026-01-01T03:00:00Z",
                ingested_at="2026-01-01T03:00:00Z",
                availability_proof="local_poll",
            )
            classified = runtime._classify_observation(observation)
            assert classified.role == "identity"
            assert classified.raw["original_role"] == role
            event_id, _, _ = runtime.events.ingest(classified)
            assert runtime.store.get_event(event_id).attention == 0
        stale_correction = runtime._classify_observation(
            Observation(
                source="browser:x:publisher",
                source_kind="social",
                title="Publisher correction first observed late",
                role="identity",
                published_at="2026-01-01T00:00:00Z",
                observed_at="2026-01-01T03:00:00Z",
                ingested_at="2026-01-01T03:00:00Z",
                availability_proof="local_receive",
                raw={
                    "source_item_state": "correction",
                    "source_item_state_evidence": "publisher_correction_marker",
                },
            )
        )
        assert stale_correction.role == "identity"
        assert stale_correction.raw["stale_first_observation"] is True
        await runtime.close()

    asyncio.run(scenario())


def test_stale_only_event_is_not_retried_until_new_evidence_arrives(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["event_min_attention"] = 0
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        event_id, _, _ = runtime.events.ingest(
            Observation(
                source="google-news-reverse",
                source_kind="news",
                title="Starlink offers flood-relief internet",
                role="confirmation",
                published_at=now - timedelta(hours=3),
                observed_at=now,
                ingested_at=now,
                availability_proof="local_poll",
            )
        )
        runtime.store.set_kv(f"event_decision_attempt:{event_id}", 13)
        calls = 0

        class FakeEvaluator:
            async def discover_and_decide(self, event):
                nonlocal calls
                calls += 1
                return None

        runtime.evaluator = FakeEvaluator()
        await runtime.evaluate_events_once()
        assert calls == 0
        assert runtime.store.get_kv(f"event_decision_next:{event_id}") is not None
        assert runtime.store.get_kv(f"event_decision_attempt:{event_id}") == 13

        await runtime.ingest_observation(
            Observation(
                source="live-news",
                source_kind="news",
                title="Starlink offers flood-relief internet",
                availability_proof="local_poll",
            )
        )
        assert runtime.store.get_kv(f"event_decision_next:{event_id}") is None
        assert runtime.store.get_kv(f"event_decision_attempt:{event_id}") == 0
        await runtime.close()

    asyncio.run(scenario())


def test_source_error_notifications_are_rate_limited(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["notifications"]["jsonl"] = "notifications.jsonl"
        runtime = Runtime(config, tmp_path)
        runtime._notify_source_error("broken-source", RuntimeError("first"))
        runtime._notify_source_error("broken-source", RuntimeError("second"))
        lines = (tmp_path / "notifications.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert "broken-source" in lines[0]
        await runtime.close()

    asyncio.run(scenario())


def test_reverse_news_result_must_actually_contain_token_identity():
    token = TokenCandidate(chain="solana", address="A" * 32, name="He Sold?", symbol="HESOLD")
    unrelated = Observation(
        source="google-news-reverse",
        source_kind="news",
        title="Insider trades: Alibaba and Coca-Cola among major names",
    )
    matching = Observation(
        source="google-news-reverse",
        source_kind="news",
        title="He Sold? phrase goes viral after celebrity interview",
    )
    assert _reverse_news_matches_token(token, unrelated) is False
    assert _reverse_news_matches_token(token, matching) is True


def test_reverse_news_only_runs_for_tokens_with_real_momentum(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["sources"]["reverse_google_news"].update(
            {
                "queries_per_cycle": 3,
                "max_tokens_scanned_per_cycle": 20,
                "min_liquidity_usd": 5000,
                "min_volume_5m_usd": 1000,
                "min_5m_transactions": 12,
                "min_buy_ratio": 0.55,
            }
        )
        runtime = Runtime(config, tmp_path)
        quiet = TokenCandidate(chain="solana", address="Q" * 32, name="Quiet Token", symbol="QUIET")
        active = TokenCandidate(chain="bsc", address="0x" + "2" * 40, name="Luce", symbol="LUCE")
        generic = TokenCandidate(chain="solana", address="G" * 32, name="Gang", symbol="GANG")
        runtime.store.upsert_token(quiet)
        runtime.store.upsert_token(active)
        runtime.store.upsert_token(generic)
        discovered_at = utcnow()
        round_id = runtime.store.start_token_discovery_round(
            provider="geckoterminal", surface="new_pools", mode="poll",
            chain_scope="bsc", started_at=discovered_at,
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=active.token_id, chain=active.chain, role="new_pool",
            first_local_discovery=True, new_token=True, observed_at=discovered_at,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )

        class FakeDex:
            def __init__(self):
                self.calls = []

            async def batch_quote(self, chain, addresses):
                self.calls.append((chain, list(addresses)))
                result = {}
                for address in addresses:
                    token = active if address == active.address else quiet
                    snapshot = TokenSnapshot(
                        chain, address, 1,
                        50000 if token is active else 1000,
                        1000000 if token is active else 10000,
                        30000 if token is active else 10,
                        120 if token is active else 1,
                        30 if token is active else 1,
                    )
                    result[token.token_id] = (token, snapshot)
                return result

        queried = []

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                self.name = name
                queried.append(name)

            async def poll(self):
                return []

        dex = FakeDex()
        runtime.dex = dex
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()
        assert queried == ["google-news-reverse"]
        assert runtime.store.latest_snapshot(active.token_id) is not None
        assert runtime.store.latest_snapshot(quiet.token_id) is not None
        assert runtime.store.latest_snapshot(generic.token_id) is None
        assert {chain for chain, _ in dex.calls} == {"solana", "bsc"}
        assert sum(len(addresses) for _, addresses in dex.calls) == 2
        attempts = list(
            runtime.store.db.execute(
                "SELECT role,status,reason_code,batch_size FROM token_discovery_quote_attempts "
                "WHERE role='reverse_context_probe' ORDER BY id"
            )
        )
        assert [(row["status"], row["reason_code"]) for row in attempts] == [
            ("success", "batch_quote_returned_token"),
            ("success", "batch_quote_returned_token"),
        ]
        assert all(row["batch_size"] == 1 for row in attempts)
        rounds = list(
            runtime.store.db.execute(
                "SELECT surface,status,requested_count,returned_count "
                "FROM token_discovery_rounds WHERE surface='reverse_context_probe' ORDER BY id"
            )
        )
        assert len(rounds) == 2
        assert all(
            row["status"] == "completed"
            and row["requested_count"] == 1
            and row["returned_count"] == 1
            for row in rounds
        )
        lookup = runtime.store.db.execute(
            "SELECT reason_code,metadata_json FROM token_universe_funnel_transitions "
            "WHERE token_id=? AND stage='event_lookup_result'",
            (active.token_id,),
        ).fetchone()
        assert lookup["reason_code"] == "no_results_returned"
        assert json.loads(lookup["metadata_json"])["fetched_count"] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_event_evaluation_reserves_budget_for_fresh_eligible_event(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["event_min_attention"] = 35
        config["candidate"]["max_events_per_cycle"] = 8
        runtime = Runtime(config, tmp_path)
        now = utcnow()

        def add_event(title: str, attention: float, seen_at) -> int:
            event_id = runtime.store.create_event(title, [title], attention, seen_at)
            observation_id, _ = runtime.store.add_observation(
                Observation(
                    source="fixture-news",
                    source_kind="news",
                    title=title,
                    observed_at=seen_at,
                    ingested_at=seen_at,
                    availability_proof="local_poll",
                )
            )
            runtime.store.link_event_observation(event_id, observation_id)
            return event_id

        for index in range(8):
            add_event(f"old-{index}", 90, now - timedelta(minutes=20))
        target_id = add_event("fresh-target", 35, now - timedelta(minutes=2))
        for index in range(8):
            add_event(f"new-low-{index}", 10, now - timedelta(minutes=1))

        calls = []

        class FakeEvaluator:
            async def discover_and_decide(self, event):
                calls.append(event.id)
                return None

        runtime.evaluator = FakeEvaluator()
        await runtime.evaluate_events_once()
        assert calls[0] == target_id
        assert len(calls) == 8
        await runtime.close()

    asyncio.run(scenario())


def test_reverse_news_prioritizes_oldest_persistent_pending_without_raising_caps(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["candidate"]["chains"] = ["solana", "bsc"]
        config["sources"]["reverse_google_news"].update(
            {
                "queries_per_cycle": 1,
                "max_tokens_scanned_per_cycle": 1,
                "candidate_pool_limit": 1,
                "min_independent_sources": 0,
            }
        )
        runtime = Runtime(config, tmp_path)
        observed_at = utcnow()
        pending = TokenCandidate(
            chain="bsc", address="0x" + "7" * 40,
            name="Pending Narrative", symbol="PEND", source="dexscreener",
        )
        recent = TokenCandidate(
            chain="solana", address="R" * 32,
            name="Recent Migration", symbol="RECENT", source="pumpportal:migration",
        )
        runtime.store.upsert_token(pending, seen_at=observed_at - timedelta(minutes=10))
        round_id = runtime.store.start_token_discovery_round(
            provider="dexscreener", surface="new_pairs", mode="poll",
            chain_scope="bsc", started_at=observed_at,
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=pending.token_id, chain=pending.chain, role="new_pair",
            first_local_discovery=True, new_token=True, observed_at=observed_at,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1,
        )
        runtime.store.record_token_universe_funnel_transition(
            pending.token_id,
            stage="context_trigger_evaluation", status="eligible",
            reason_code="onchain_momentum", evaluation_key="pending:eligible",
            observed_at=observed_at, ingested_at=observed_at,
            metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1,
                      "momentum_score": 85.0},
        )
        runtime.store.upsert_token(recent, seen_at=utcnow())

        class FakeDex:
            def __init__(self):
                self.calls = []

            async def batch_quote(self, chain, addresses):
                self.calls.append((chain, list(addresses)))
                token = pending if addresses == [pending.address] else recent
                snapshot = TokenSnapshot(chain, token.address, 1, 100, 1000, 10, 1, 1)
                return {token.token_id: (token, snapshot)}

        queried = []

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                queried.append(name)

            async def poll(self):
                return []

        runtime.dex = FakeDex()
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()
        assert runtime.dex.calls == [("bsc", [pending.address])]
        assert queried == ["google-news-reverse"]
        assert runtime.store.get_kv(f"reverse_news:{pending.token_id}") is not None
        assert runtime.store.get_kv(f"reverse_news:{recent.token_id}") is None
        assert runtime.store.pending_event_lookup_tokens(["bsc", "solana"]) == []
        lookup = runtime.store.db.execute(
            "SELECT status FROM token_universe_funnel_transitions "
            "WHERE token_id=? AND stage='event_lookup_attempt'",
            (pending.token_id,),
        ).fetchone()
        assert lookup["status"] == "started"

        await runtime.reverse_news_once()
        assert runtime.dex.calls == [
            ("bsc", [pending.address]),
            ("solana", [recent.address]),
        ]
        assert queried == ["google-news-reverse"]
        assert all(len(addresses) == 1 for _, addresses in runtime.dex.calls)
        await runtime.close()

    asyncio.run(scenario())


def test_reverse_news_records_unsearchable_pending_name_as_terminal_screen(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["candidate"]["chains"] = ["solana", "bsc"]
        config["sources"]["reverse_google_news"].update(
            {"queries_per_cycle": 1, "max_tokens_scanned_per_cycle": 10,
             "candidate_pool_limit": 10, "min_independent_sources": 0}
        )
        runtime = Runtime(config, tmp_path)
        observed_at = utcnow() - timedelta(seconds=5)
        tokens = [
            TokenCandidate(
                chain="bsc", address="0x" + "1" * 40,
                name="1", symbol="1", source="dexscreener",
            ),
            TokenCandidate(
                chain="bsc", address="0x" + "2" * 40,
                name="Searchable Narrative", symbol="SEARCH", source="dexscreener",
            ),
        ]
        for index, token in enumerate(tokens):
            seen = observed_at + timedelta(seconds=index)
            runtime.store.upsert_token(token, seen_at=seen)
            round_id = runtime.store.start_token_discovery_round(
                provider="dexscreener", surface="new_pairs", mode="poll",
                chain_scope="bsc", started_at=seen,
            )
            runtime.store.add_token_discovery_exposure(
                round_id, token_id=token.token_id, chain=token.chain, role="new_pair",
                first_local_discovery=True, new_token=True, observed_at=seen,
            )
            runtime.store.finish_token_discovery_round(
                round_id, status="completed", returned_count=1,
            )
            runtime.store.record_token_universe_funnel_transition(
                token.token_id,
                stage="context_trigger_evaluation", status="eligible",
                reason_code="onchain_momentum", evaluation_key=f"screen:{index}",
                observed_at=seen, ingested_at=seen,
                metadata={"trigger_kind": "onchain_momentum", "trigger_priority": 1},
            )

        class FakeDex:
            def __init__(self):
                self.calls = []

            async def batch_quote(self, chain, addresses):
                self.calls.append((chain, list(addresses)))
                token = tokens[1]
                snapshot = TokenSnapshot(chain, token.address, 1, 50_000, 100_000, 30_000, 100, 20)
                return {token.token_id: (token, snapshot)}

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                pass

            async def poll(self):
                return []

        runtime.dex = FakeDex()
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()

        assert runtime.dex.calls == [("bsc", [tokens[1].address])]
        screens = runtime.store.db.execute(
            "SELECT status,reason_code,decision_eligible,affects "
            "FROM token_event_lookup_name_screen_results ORDER BY cohort_id"
        ).fetchall()
        assert [tuple(row) for row in screens] == [
            ("rejected", "unsearchable_token_name", 0, "none"),
            ("eligible", "searchable_name", 0, "none"),
        ]
        assert runtime.store.pending_event_lookup_tokens(["bsc"]) == []
        assert runtime.store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert runtime.store.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        await runtime.close()

    asyncio.run(scenario())


def test_reverse_news_keeps_one_current_slot_while_draining_pending(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["autonomous_search"]["enabled"] = False
        config["sources"]["reverse_google_news"].update(
            {
                "queries_per_cycle": 3,
                "max_tokens_scanned_per_cycle": 4,
                "candidate_pool_limit": 4,
                "min_independent_sources": 0,
            }
        )
        runtime = Runtime(config, tmp_path)
        now = utcnow()
        pending_tokens = [
            TokenCandidate(
                chain="bsc", address="0x" + str(index) * 40,
                name=f"Pending Topic {index}", symbol=f"P{index}", source="dexscreener",
            )
            for index in (1, 2, 3)
        ]
        current = TokenCandidate(
            chain="bsc", address="0x" + "9" * 40,
            name="Current Topic", symbol="CUR", source="pumpportal:migration",
        )
        runtime.store.pending_event_lookup_tokens = lambda *args, **kwargs: [
            {
                "token": token,
                "trigger": {"kind": "onchain_momentum", "priority": 1,
                            "decision_eligible": False, "endorsement_inferred": False},
                "cohort_id": index,
                "eligible_transition_id": index,
                "eligible_at": now + timedelta(seconds=index),
            }
            for index, token in enumerate(pending_tokens)
        ]
        runtime.store.recent_tokens = lambda *args, **kwargs: [current, *pending_tokens]

        class FakeDex:
            async def batch_quote(self, chain, addresses):
                by_address = {token.address: token for token in [*pending_tokens, current]}
                return {
                    by_address[address].token_id: (
                        by_address[address],
                        TokenSnapshot(chain, address, 1, 50_000, 100_000, 30_000, 100, 20),
                    )
                    for address in addresses
                }

        queries = []

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                queries.append(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0])

            async def poll(self):
                return []

        runtime.dex = FakeDex()
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()
        assert queries == [
            '"Pending Topic 1" when:1d',
            '"Pending Topic 2" when:1d',
            '"Current Topic" when:1d',
        ]
        assert len(runtime.store.db.execute(
            "SELECT id FROM source_poll_attempts WHERE collector_kind='reverse_news'"
        ).fetchall()) == 3
        await runtime.close()

    asyncio.run(scenario())


def test_reverse_context_prioritizes_exact_high_impact_post_without_momentum(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"].update(
            {"queries_per_cycle": 1, "max_tokens_scanned_per_cycle": 5}
        )
        settings_path = tmp_path / "data" / "web_console" / "console_settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "watch_accounts": [
                        {
                            "platform": "x", "handle": "@elonmusk",
                            "url": "https://x.com/elonmusk", "entity_id": "elon_musk",
                            "priority": 4, "watch_cadence": "critical", "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="P" * 32, name="Rocket Otter", symbol="ROT"
        )
        discovered_at = utcnow()
        runtime.store.upsert_token(token, seen_at=discovered_at)
        round_id = runtime.store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana", started_at=discovered_at,
        )
        runtime.store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True, observed_at=discovered_at,
        )
        runtime.store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1
        )
        runtime.store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "dexscreener",
                "discovery_surface": "pair_info",
                "role": "identity",
                "original_url": "https://x.com/elonmusk/status/12345",
                "normalized_url": "https://x.com/elonmusk/status/12345",
                "link_kind": "social_post",
                "platform": "x",
                "verification_status": "provider_metadata",
            }
        )
        runtime.store.add_observation(
            Observation(
                source="browser:x:elonmusk",
                source_kind="social",
                title="Exact locally received post",
                url="https://x.com/elonmusk/status/12345",
                author="@elonmusk",
                availability_proof="local_receive",
                role="feature",
                source_item_id="https://x.com/elonmusk/status/12345",
                raw={
                    "source_entity_id": "elon_musk",
                    "browser": {"platform": "x", "source_entity_id": "elon_musk"},
                },
            )
        )

        class FakeDex:
            async def quote(self, chain, address):
                return token, TokenSnapshot(chain, address, 1, 100, 1000, 10, 1, 1)

        queried = []

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                queried.append(name)

            async def poll(self):
                return [
                    Observation(
                        source="google-news-reverse",
                        source_kind="news",
                        title="Rocket Otter becomes a headline",
                        published_at=utcnow() + timedelta(hours=1),
                    ),
                    Observation(
                        source="google-news-reverse",
                        source_kind="news",
                        title="An unrelated current story",
                        published_at=utcnow(),
                    ),
                    Observation(
                        source="google-news-reverse",
                        source_kind="news",
                        title="Rocket Otter becomes a current headline",
                        published_at=utcnow(),
                    ),
                ]

        investigations = []

        async def search_context(candidate, snapshot, *, momentum_score, event_relation=None, retry_lane=False):
            investigations.append((candidate.token_id, momentum_score, event_relation))
            return []

        runtime.dex = FakeDex()
        runtime.autonomous_search.search_token_context = search_context
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()
        assert queried == ["google-news-reverse"]
        assert len(investigations) == 1
        assert investigations[0][0] == token.token_id
        assert investigations[0][2]["kind"] == "high_impact_account_post"
        lookup_edges = list(
            runtime.store.db.execute(
                "SELECT stage,status,reason_code,metadata_json FROM token_universe_funnel_transitions "
                "WHERE token_id=? AND stage LIKE 'event_lookup_%' ORDER BY id",
                (token.token_id,),
            )
        )
        assert [(row["stage"], row["status"]) for row in lookup_edges] == [
            ("event_lookup_attempt", "started"),
            ("event_lookup_result", "found"),
        ]
        result = lookup_edges[-1]
        breakdown = json.loads(result["metadata_json"])
        assert result["reason_code"] == "reverse_news_identity_matched"
        assert breakdown["fetched_count"] == 3
        assert breakdown["matched_count"] == 1
        assert breakdown["accepted_count"] == 0
        assert breakdown["decision_eligible_count"] == 0
        assert breakdown["identity_context_count"] == 1
        assert breakdown["outside_time_window_count"] == 1
        assert breakdown["identity_mismatch_count"] == 1
        reverse_observation = runtime.store.db.execute(
            "SELECT role,raw_json FROM observations WHERE raw_json LIKE '%reverse_name_only%'"
        ).fetchone()
        assert reverse_observation["role"] == "identity"
        reverse_raw = json.loads(reverse_observation["raw_json"])
        assert reverse_raw["decision_eligible"] is False
        assert reverse_raw["affects"] == "audit_context_only"
        poll_attempt = runtime.store.db.execute(
            "SELECT decision_eligible_count,context_only_count FROM source_poll_attempts "
            "WHERE collector_kind='reverse_news'"
        ).fetchone()
        assert poll_attempt["decision_eligible_count"] == 0
        assert poll_attempt["context_only_count"] == 1
        await runtime.close()

    asyncio.run(scenario())


def test_end_to_end_event_buy_partial_profit_and_liquidity_exit(tmp_path):
    async def scenario():
        from memetrader.strategy import CandidateEvaluator

        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["event_min_attention"] = 0
        config["candidate"].update(
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 1,
                "decision_cooldown_seconds": 1,
            }
        )
        config["paper"].update(
            {
                "starting_cash_usd": 1000,
                "max_position_usd": 35,
                "min_position_usd": 3,
                "slippage_rate": 0.02,
                "take_profit_tiers": [
                    {"return_pct": 0.8, "sell_fraction": 0.2},
                    {"return_pct": 1.8, "sell_fraction": 0.25},
                ],
            }
        )
        config["notifications"]["jsonl"] = "notifications.jsonl"
        runtime = Runtime(config, tmp_path)
        ca = "7TBkWkqohDZEoCAh1ykErGKyZzgFUEjxTv75xQeAvTeP"
        token = TokenCandidate(chain="solana", address=ca, name="Example Meme", symbol="EXM")

        class FakeDex:
            stage = "entry"

            async def quote(self, chain, address):
                if chain != "solana" or address != ca:
                    return None
                if self.stage == "entry":
                    snap = TokenSnapshot("solana", ca, 1.0, 50000, 500000, 30000, 100, 20)
                elif self.stage == "profit":
                    snap = TokenSnapshot("solana", ca, 1.9, 50000, 900000, 50000, 100, 20)
                else:
                    snap = TokenSnapshot("solana", ca, 1.5, 1000, 700000, 10000, 20, 30)
                return token, snap

            async def search(self, query, limit=25):
                return []

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

            async def enrich_evm(self, snapshot):
                return snapshot

            async def enrich_solana(self, snapshot):
                return snapshot

        dex = FakeDex()
        safety = FakeSafety()
        runtime.dex = dex
        runtime.safety = safety
        runtime.evaluator = CandidateEvaluator(
            runtime.store,
            dex,
            safety,
            config["candidate"],
            runtime.agent,
        )
        await runtime.ingest_observation(
            Observation(
                source="browser:x:official",
                source_kind="official_social",
                    title=f"Example Meme launches on Solana. CA: {ca}",
                    text=f"Example Meme launches on Solana. CA: {ca}",
                availability_proof="local_receive",
            )
        )
        await runtime.evaluate_events_once()
        opened = runtime.store.position(token.token_id)
        assert opened is not None
        assert opened.entry_price == pytest.approx(1.02)
        original_quantity = opened.quantity

        dex.stage = "profit"
        await runtime.monitor_positions_once()
        after_profit = runtime.store.position(token.token_id)
        assert after_profit is not None
        assert after_profit.quantity == pytest.approx(original_quantity * 0.8)
        assert after_profit.take_profit_index == 1

        dex.stage = "liquidity"
        await runtime.monitor_positions_once()
        assert runtime.store.position(token.token_id) is None
        sides = [row["side"] for row in runtime.store.trades(10)]
        assert sides.count("BUY") == 1 and sides.count("SELL") == 2
        assert any(row["reason"] == "liquidity_emergency" for row in runtime.store.trades(10))
        assert all(row["quote_price"] is not None for row in runtime.store.trades(10))
        assert all(row["quote_observed_at"] is not None for row in runtime.store.trades(10))
        attempts = list(runtime.store.db.execute("SELECT * FROM paper_execution_attempts ORDER BY id"))
        assert [row["status"] for row in attempts] == ["filled", "filled", "filled"]
        assert all(row["decision_id"] is not None for row in attempts)
        assert all(row["cohort_id"] is not None for row in attempts)
        assert len({row["decision_id"] for row in attempts}) == 1
        assert len({row["cohort_id"] for row in attempts}) == 1
        await runtime.close()

    asyncio.run(scenario())


def test_paper_quote_gate_rejects_future_stale_and_wrong_token(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["paper"]["max_quote_age_seconds"] = 30
        runtime = Runtime(config, tmp_path)
        received = utcnow()
        token = TokenCandidate(chain="solana", address="T" * 32, name="Temporal")
        future = TokenSnapshot(
            "solana", token.address, 1, 50_000, 500_000, 10_000, 20, 5,
            observed_at=received + timedelta(seconds=1), provider="test",
        )
        stale = TokenSnapshot(
            "solana", token.address, 1, 50_000, 500_000, 10_000, 20, 5,
            observed_at=received - timedelta(seconds=31), provider="test",
        )
        wrong = TokenCandidate(chain="solana", address="W" * 32, name="Wrong")
        current = TokenSnapshot(
            "solana", wrong.address, 1, 50_000, 500_000, 10_000, 20, 5,
            observed_at=received, provider="test",
        )
        assert "snapshot_observed_after_decision" in runtime._paper_quote_rejections(
            token.token_id, token, future, received
        )
        assert "quote_stale_at_execution" in runtime._paper_quote_rejections(
            token.token_id, token, stale, received
        )
        assert "quote_token_mismatch" in runtime._paper_quote_rejections(
            token.token_id, wrong, current, received
        )
        await runtime.close()

    asyncio.run(scenario())


def test_periodic_loops_do_not_block_each_other(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        counts = {"slow": 0, "fast": 0}

        async def slow():
            counts["slow"] += 1
            await asyncio.sleep(1.3)

        async def fast():
            counts["fast"] += 1

        tasks = [
            asyncio.create_task(runtime._periodic("slow", 1.0, slow)),
            asyncio.create_task(runtime._periodic("fast", 1.0, fast)),
        ]
        await asyncio.sleep(2.2)
        runtime.stop()
        await asyncio.gather(*tasks)
        assert counts["slow"] >= 1
        assert counts["fast"] >= 3
        await runtime.close()

    asyncio.run(scenario())


def test_disabled_rss_source_is_not_reported_stale(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = [
            {
                "name": "disabled-rss",
                "url": "https://example.invalid/feed.xml",
                "enabled": False,
            }
        ]
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        config["notifications"]["jsonl"] = "notifications.jsonl"
        runtime = Runtime(config, tmp_path)
        runtime.store.heartbeat("disabled-rss", item=True)
        runtime.store.heartbeat("pumpportal:migration", item=True)
        with runtime.store.db:
            runtime.store.db.execute(
                "UPDATE source_health SET last_ok_at='2020-01-01T00:00:00Z' "
                "WHERE source IN ('disabled-rss','pumpportal:migration')"
            )
        await runtime.check_source_health_once()
        path = tmp_path / "notifications.jsonl"
        assert not path.exists() or "source_stale" not in path.read_text(encoding="utf-8")
        await runtime.close()

    asyncio.run(scenario())


def test_status_hides_disabled_rss_source(tmp_path, capsys):
    from memetrader.cli import cmd_status
    from memetrader.store import Store

    config = initial_config()
    config["database"] = "db.sqlite3"
    config["bridge"]["enabled"] = False
    config["sources"]["rss"] = [
        {
            "name": "disabled-rss",
            "url": "https://example.invalid/feed.xml",
            "enabled": False,
        }
    ]
    config["sources"]["gecko_networks"] = []
    config["sources"]["pumpportal"]["enabled"] = False
    config["sources"]["reverse_google_news"]["enabled"] = False
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    store.heartbeat("disabled-rss", error="old failure")
    store.heartbeat("enabled-source", item=True)
    store.close()

    assert cmd_status(str(config_path), 5) == 0
    payload = json.loads(capsys.readouterr().out)
    sources = {row["source"] for row in payload["sources"]}
    assert "disabled-rss" not in sources
    assert "enabled-source" in sources


def test_onchain_primary_focus_pauses_active_agent_and_evm_dispatch(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["onchain_primary_focus_enabled"] = True
        runtime = Runtime(config, tmp_path)
        assert runtime.store.strategy_focus_active() is True
        before = runtime.store.db.execute("SELECT COUNT(*) FROM agent_attempts").fetchone()[0]

        async def forbidden(*args, **kwargs):
            raise AssertionError("focused runtime attempted paused external work")

        runtime.autonomous_search.discover_sources = forbidden
        runtime.autonomous_search.scout_trends = forbidden
        runtime.autonomous_search.search_token_context = forbidden
        runtime.evm_route.quote_round_trip = forbidden
        assert (await runtime.discover_sources_once())["status"] == "paused"
        assert (await runtime.scout_trends_once())["status"] == "paused"
        token = TokenCandidate("solana", "F" * 32, name="Focus", source="fixture")
        snapshot = TokenSnapshot("solana", token.address, 1, 20_000, 50_000, 2_000, 10, 2)
        await runtime._investigate_token_context(token, snapshot, momentum_score=90)
        await runtime.onchain_only_evm_route_quote_once()
        await runtime.onchain_only_evm_aggregator_price_once()
        after = runtime.store.db.execute("SELECT COUNT(*) FROM agent_attempts").fetchone()[0]
        assert after == before
        await runtime.close()

    asyncio.run(scenario())


def test_dynamic_exit_challenger_uses_local_mark_then_amount_specific_jupiter_quote(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="R" * 32, name="Runtime Exit", source="fixture"
        )
        snapshot = TokenSnapshot(
            "solana", token.address, 0.5, 20_000, 50_000, 1_000, 2, 8,
            provider="dexscreener",
        )
        calls: list[object] = []
        runtime.store.enroll_onchain_paper_exit_challenger = lambda: calls.append("enroll")
        runtime.store.due_onchain_paper_exit_challenger_marks = lambda limit=3: [{
            "shadow_cohort_id": 7, "token_id": token.token_id, "address": token.address,
        }]

        async def quote_token(chain, address):
            assert chain == "solana" and address == token.address
            return token, snapshot

        runtime.dex.quote = quote_token
        runtime._paper_quote_rejections = lambda *args: []
        runtime.store.upsert_token = lambda *args, **kwargs: calls.append("token")
        runtime.store.add_snapshot = lambda value: 91
        runtime.store.record_onchain_paper_exit_challenger_mark = (
            lambda cohort_id, **kwargs: calls.append(("mark", cohort_id, kwargs["snapshot_id"]))
        )
        task = {
            "lane": Store.ONCHAIN_PAPER_EXIT_CHALLENGER_VERSION,
            "quote_key": "onchain-exit:7:11:1", "mark_id": 11,
            "shadow_cohort_id": 7, "attempt_seq": 1, "action": "HARD_STOP",
            "triggered_at": iso(), "input_mint": token.address,
            "output_mint": Store.JUPITER_USDC_MINT,
            "input_amount_raw": "900000000", "slippage_bps": 400,
            "max_total_delay_seconds": 45,
        }
        runtime.store.due_onchain_paper_exit_challenger_quotes = lambda limit=1: [task]
        runtime.store.start_onchain_paper_exit_challenger_quote_attempt = (
            lambda item, requested_at=None: 13
        )
        recorded: list[dict] = []
        runtime.store.record_onchain_paper_exit_challenger_quote_result = (
            lambda item, **kwargs: recorded.append(kwargs)
        )
        runtime.store.record_onchain_paper_exit_challenger_account_snapshot = (
            lambda: calls.append("account")
        )

        async def quote_jupiter(input_mint, output_mint, input_amount_raw, *, slippage_bps):
            assert input_mint == token.address
            assert output_mint == Store.JUPITER_USDC_MINT
            assert input_amount_raw == 900000000
            assert slippage_bps == 400
            return {
                "output_amount_raw": "21000000",
                "other_amount_threshold": "20000000",
                "slippage_bps": 400,
            }

        runtime.jupiter.quote = quote_jupiter
        await runtime.onchain_paper_exit_challenger_once()
        assert calls[0] == "enroll"
        assert ("mark", 7, 91) in calls
        assert calls[-1] == "account"
        assert len(recorded) == 1
        assert recorded[0]["attempt_id"] == 13
        assert recorded[0]["status"] == "quoted"
        assert recorded[0]["other_amount_threshold_raw"] == "20000000"
        await runtime.close()

    asyncio.run(scenario())


def test_zerox_observer_only_registers_when_local_credential_exists(tmp_path, monkeypatch):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        monkeypatch.delenv("MEMETRADER_ZEROX_API_KEY", raising=False)
        runtime = Runtime(config, tmp_path / "without-key")
        assert runtime.evm_aggregator is None
        assert Store.onchain_only_evm_aggregator_price_summary_from_connection(
            runtime.store.db
        )["status"] == "not_registered"
        await runtime.close()

        monkeypatch.setenv("MEMETRADER_ZEROX_API_KEY", "fixture-key")
        configured = Runtime(config, tmp_path / "with-key")
        assert configured.evm_aggregator is not None
        summary = Store.onchain_only_evm_aggregator_price_summary_from_connection(
            configured.store.db
        )
        assert summary["status"] == "active" and summary["configured"] is True
        assert "fixture-key" not in json.dumps(summary)
        await configured.close()

    asyncio.run(scenario())


def test_windows_startup_scripts_use_one_attached_scheduled_task():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    runner = (root / "scripts" / "run_paper.ps1").read_text(encoding="utf-8")
    installer = (root / "scripts" / "install_scheduled_task.ps1").read_text(encoding="utf-8")
    remover = (root / "scripts" / "remove_scheduled_task.ps1").read_text(encoding="utf-8")
    legacy_installer = (root / "scripts" / "install_startup.ps1").read_text(encoding="utf-8")
    legacy_remover = (root / "scripts" / "remove_startup.ps1").read_text(encoding="utf-8")

    assert "while ($true)" in runner
    assert "& $python -m memetrader run" in runner
    assert "data/notifications.jsonl" in runner
    assert "runtime-crash.log" in runner
    assert "Tee-Object" not in runner
    assert "Start-Process" not in runner
    assert "New-ScheduledTaskAction" in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert "Start-ScheduledTask" in installer
    assert "memeTraderPaperBot" in installer
    assert "Remove-ItemProperty" in installer
    assert "Unregister-ScheduledTask" in remover
    assert "taskkill.exe" in remover
    assert "install_scheduled_task.ps1" in legacy_installer
    assert "remove_scheduled_task.ps1" in legacy_remover
