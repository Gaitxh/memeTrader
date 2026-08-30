import asyncio
import json

import pytest

from memetrader.cli import cmd_doctor
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot
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
    assert config["safety"]["require_evm_simulation"] is True
    assert config["safety"]["require_solana_report"] is True


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
            return FakeResponse()

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
        runtime.store.add_snapshot(TokenSnapshot("solana", token.address, 1.0, 100000, 1000000, 50000, 30, 10))

        class FakeEvaluator:
            async def discover_and_decide(self, event):
                return CandidateDecision(event.id, token.token_id, "CANDIDATE", 85, 90, 20, ["test"])

        runtime.evaluator = FakeEvaluator()
        await runtime.evaluate_events_once()
        row = runtime.store.decisions(1)[0]
        assert row["position_usd"] > 0
        assert runtime.store.position(token.token_id) is not None
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


def test_stale_first_polled_item_is_identity_only_and_has_zero_attention(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "db.sqlite3"
        config["bridge"]["enabled"] = False
        config["sources"]["rss"] = []
        config["sources"]["gecko_networks"] = []
        config["sources"]["pumpportal"]["enabled"] = False
        config["sources"]["reverse_google_news"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        observation = Observation(
            source="rss:archive",
            source_kind="news",
            title="An old article first discovered today",
            published_at="2026-01-01T00:00:00Z",
            observed_at="2026-01-01T03:00:00Z",
            ingested_at="2026-01-01T03:00:00Z",
            availability_proof="local_poll",
        )
        classified = runtime._classify_observation(observation)
        assert classified.role == "identity"
        event_id, _, _ = runtime.events.ingest(classified)
        assert runtime.store.get_event(event_id).attention == 0
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
