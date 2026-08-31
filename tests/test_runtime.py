import asyncio
import json
from datetime import timedelta

import pytest

from memetrader.cli import cmd_doctor
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import (
    Notifier,
    Runtime,
    SingleInstance,
    _reverse_news_matches_token,
    initial_config,
    load_config,
)


def test_initial_config_has_private_token_and_live_locked():
    config = initial_config()
    assert len(config["bridge"]["token"]) >= 24
    assert config["mode"] == "paper"
    assert config["agent"]["enabled"] is False
    assert config["live"]["enabled"] is False
    assert config["safety"]["require_evm_security_report"] is True
    assert config["safety"]["require_evm_simulation"] is False
    assert config["safety"]["require_solana_report"] is True
    assert config["paper"]["slippage_rate"] == pytest.approx(0.04)
    assert config["paper"]["fee_bps"] == pytest.approx(60)
    assert config["paper"]["pump_swap_fee_bps"] == pytest.approx(125)


def test_paper_fee_uses_pumpswap_cap_only_for_identified_venue(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
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


def test_followup_tick_finalizes_event_and_token_context_without_agent_or_quote(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        calls = []
        runtime.store.finalize_shadow_event_outcomes = lambda: calls.append("event")
        runtime.store.finalize_token_context_outcomes = lambda: calls.append("token_context")
        runtime.store.finalize_information_first_shadow_outcomes = lambda: calls.append("information_first")
        await runtime.shadow_event_followup_once()
        assert calls == ["event", "token_context", "information_first"]
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
        runtime = Runtime(config, tmp_path)
        token = TokenCandidate(
            chain="solana", address="G" * 32, name="Gecko Discovery", source="geckoterminal:solana"
        )

        class Gecko:
            calls = 0

            def __init__(self, http, network):
                assert network == "solana"

            async def poll(self):
                Gecko.calls += 1
                if Gecko.calls == 3:
                    raise TimeoutError("provider detail must not persist")
                return [token] if Gecko.calls <= 2 else []

        monkeypatch.setattr("memetrader.runtime.GeckoNewPoolsCollector", Gecko)
        await runtime._poll_gecko_network("solana")
        await runtime._poll_gecko_network("solana")
        await runtime._poll_gecko_network("solana")
        rows = runtime.store.db.execute(
            "SELECT * FROM token_discovery_rounds ORDER BY id"
        ).fetchall()
        assert [row["status"] for row in rows] == ["completed", "completed", "error"]
        assert rows[0]["first_local_discovery_count"] == 1
        assert rows[1]["first_local_discovery_count"] == 0
        assert rows[1]["duplicate_token_count"] == 1
        assert rows[2]["error_type"] == "TimeoutError"
        assert "provider detail" not in json.dumps([dict(row) for row in rows])
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
        health = {row["source"]: row for row in runtime.store.source_health()}
        assert health["dexscreener:token_profiles"]["last_ok_at"] is not None
        assert health["dexscreener:hydration"]["last_item_at"] is not None
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
        token = TokenCandidate(chain="solana", address="H" * 32, name="Rocket Otter", symbol="ROT")
        snapshot = TokenSnapshot("solana", token.address, 0.01, 100, 1000, 10, 1, 1)
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
                ]

            async def quote(self, chain, address):
                return token, snapshot

        investigations = []

        async def search_context(candidate, observed, *, momentum_score, event_relation=None):
            investigations.append((candidate.token_id, momentum_score, event_relation))
            return []

        runtime.dex = Dex()
        runtime.autonomous_search.search_token_context = search_context
        await runtime.poll_dexscreener_discovery_once()
        assert len(investigations) == 1
        assert investigations[0][0] == token.token_id
        assert investigations[0][1] < config["autonomous_search"]["context_min_momentum_score"]
        assert investigations[0][2]["kind"] == "high_impact_account_post"
        assert investigations[0][2]["endorsement_inferred"] is False
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
                "page_url": "https://x.com/i/lists/1?token=must-not-persist#private",
                "access_state": "content_visible",
                "password": "must-not-persist",
                "cookie": "must-not-persist",
            },
        )
        saved = runtime.store.get_kv("browser_platform_heartbeat:x")
        assert saved["access_state"] == "accessible"
        assert saved["selector_count"] == 8
        assert saved["page_url"] == "https://x.com/i/lists/1"
        assert saved["contains_credentials"] is False
        assert "must-not-persist" not in json.dumps(saved)
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
    config["sources"]["rss"] = []
    config["sources"]["bluesky_queries"] = []
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    class FakeResponse:
        status_code = 200

        def __init__(self, url):
            self.url = url

        def json(self):
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
        active = TokenCandidate(chain="solana", address="A" * 32, name="Luce", symbol="LUCE")
        generic = TokenCandidate(chain="solana", address="G" * 32, name="Gang", symbol="GANG")
        runtime.store.upsert_token(quiet)
        runtime.store.upsert_token(active)
        runtime.store.upsert_token(generic)

        class FakeDex:
            async def quote(self, chain, address):
                if address == active.address:
                    token = active
                    snapshot = TokenSnapshot(chain, address, 1, 50000, 1000000, 30000, 120, 30)
                elif address == generic.address:
                    token = generic
                    snapshot = TokenSnapshot(chain, address, 1, 50000, 1000000, 30000, 120, 30)
                else:
                    token = quiet
                    snapshot = TokenSnapshot(chain, address, 1, 1000, 10000, 10, 1, 1)
                return token, snapshot

        queried = []

        class FakeRSS:
            def __init__(self, http, name, url, kind):
                self.name = name
                queried.append(name)

            async def poll(self):
                return []

        runtime.dex = FakeDex()
        monkeypatch.setattr("memetrader.runtime.RSSCollector", FakeRSS)
        await runtime.reverse_news_once()
        assert queried == ["google-news-reverse"]
        assert runtime.store.latest_snapshot(active.token_id) is not None
        assert runtime.store.latest_snapshot(quiet.token_id) is not None
        assert runtime.store.latest_snapshot(generic.token_id) is None
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
        runtime.store.upsert_token(token)
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
                return []

        investigations = []

        async def search_context(candidate, snapshot, *, momentum_score, event_relation=None):
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
                "chains": ["bsc"],
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
        ca = "0x1111111111111111111111111111111111111111"
        token = TokenCandidate(chain="bsc", address=ca, name="Example Meme", symbol="EXM")

        class FakeDex:
            stage = "entry"

            async def quote(self, chain, address):
                if chain != "bsc" or address.lower() != ca:
                    return None
                if self.stage == "entry":
                    snap = TokenSnapshot("bsc", ca, 1.0, 50000, 500000, 30000, 100, 20)
                elif self.stage == "profit":
                    snap = TokenSnapshot("bsc", ca, 1.9, 50000, 900000, 50000, 100, 20)
                else:
                    snap = TokenSnapshot("bsc", ca, 1.5, 1000, 700000, 10000, 20, 30)
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
                title=f"Example Meme launches on BNB Chain. CA: {ca}",
                text=f"Example Meme launches on BNB Chain. CA: {ca}",
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
