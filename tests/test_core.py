from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from memetrader.models import CandidateDecision, EventView, Observation, Position, TokenCandidate, TokenSnapshot
from memetrader.runtime import load_config
from memetrader.store import Store
from memetrader.strategy import (
    CandidateEvaluator,
    EventEngine,
    evidence_origin,
    PaperPolicy,
    SafetyChecker,
    extract_addresses,
    extract_aliases,
    is_distinctive_token_name,
    temporal_rejection_reasons,
    token_snapshot_temporal_rejections,
)


def test_temporal_guard_rejects_future_and_outcome():
    obs = Observation(
        source="later",
        source_kind="news",
        title="later result",
        observed_at="2026-01-01T02:00:00Z",
        ingested_at="2026-01-01T02:00:01Z",
        availability_proof="fixture_arrival",
        role="outcome",
        raw={"future_return": 20},
    )
    reasons = temporal_rejection_reasons(obs, datetime(2026, 1, 1, 1, tzinfo=timezone.utc), 30)
    assert "observed_after_decision" in reasons
    assert "ingested_after_decision" in reasons
    assert "non_feature_role" in reasons
    assert "forbidden_hindsight_field" in reasons


def test_future_token_and_snapshot_are_rejected():
    decision_at = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    token = {
        "created_at": "2026-01-01T00:10:00Z",
        "first_seen_at": "2026-01-01T00:10:10Z",
        "raw": {"winner_token": True},
    }
    snapshot = {
        "observed_at": "2026-01-01T00:11:00Z",
        "raw": {"ath_after_signal": True},
    }
    reasons = token_snapshot_temporal_rejections(token, snapshot, decision_at)
    assert "token_created_after_decision" in reasons
    assert "token_observed_after_decision" in reasons
    assert "snapshot_observed_after_decision" in reasons
    assert "forbidden_hindsight_field:token" in reasons
    assert "forbidden_hindsight_field:snapshot" in reasons


def test_initial_page_and_old_polled_news_are_not_entry_evidence():
    initial = Observation(
        source="browser:x",
        source_kind="social",
        title="old post",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_receive",
        capture_phase="initial",
    )
    polled = Observation(
        source="rss",
        source_kind="news",
        title="old article first seen now",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_poll",
    )
    decision_at = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    assert "stale_initial_page" in temporal_rejection_reasons(initial, decision_at, 30)
    assert "stale_polled_item" in temporal_rejection_reasons(polled, decision_at, 30)


def test_reverse_name_distinctiveness_blocks_generic_short_terms():
    assert is_distinctive_token_name("Peanut") is True
    assert is_distinctive_token_name("Viral Animal") is True
    assert is_distinctive_token_name("牛来") is True
    assert is_distinctive_token_name("Gang") is False
    assert is_distinctive_token_name("AI") is False


def test_aliases_and_addresses():
    aliases = extract_aliases(
        "Breaking: 《My Friend Peanut》 explodes #PNUT",
        "CA: 0x1111111111111111111111111111111111111111",
    )
    assert any("My Friend Peanut" in value for value in aliases)
    assert "PNUT" in aliases
    assert not any(value.startswith("x111111") for value in aliases)
    addresses = extract_addresses("CA 0x1111111111111111111111111111111111111111")
    assert "0x1111111111111111111111111111111111111111" in addresses["evm"]
    assert not addresses["solana"]


def test_news_source_independence_uses_underlying_publisher():
    direct = {
        "source": "coindesk",
        "source_kind": "news",
        "url": "https://www.coindesk.com/markets/example",
        "raw_json": json.dumps({"feed_url": "https://www.coindesk.com/rss"}),
    }
    aggregated = {
        "source": "google-news-memecoin",
        "source_kind": "news",
        "url": "https://news.google.com/rss/articles/example",
        "raw_json": json.dumps({"publisher": "CoinDesk", "publisher_url": "https://www.coindesk.com"}),
    }
    other = {
        "source": "google-news-memecoin",
        "source_kind": "news",
        "url": "https://news.google.com/rss/articles/other",
        "raw_json": json.dumps({"publisher": "Reuters", "publisher_url": "https://www.reuters.com"}),
    }
    assert evidence_origin(direct) == evidence_origin(aggregated) == "coindesk.com"
    assert evidence_origin(other) == "reuters.com"


def test_event_clustering_and_dedup(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.15)
    a = Observation(source="x:a", source_kind="social", title="Peanut squirrel story goes viral", source_item_id="1")
    b = Observation(source="reddit:b", source_kind="social", title="Viral Peanut squirrel community reaction", source_item_id="2")
    first, first_created, first_observation = engine.ingest(a)
    second, second_created, second_observation = engine.ingest(b)
    assert first == second
    assert first_created is True and first_observation is True
    assert second_created is False and second_observation is True
    rows = store.event_observations(first)
    assert len(rows) == 2
    assert len({row["source"] for row in rows}) == 2
    duplicate_event, duplicate_created, duplicate_observation = engine.ingest(a)
    assert duplicate_event == first
    assert duplicate_created is False and duplicate_observation is False
    store.close()


def test_single_viral_visible_post_can_cross_attention_threshold(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store)
    event_id, _, _ = engine.ingest(
        Observation(
            source="browser:x:example",
            source_kind="social",
            title="A newly viral squirrel story",
            raw={"view_count": 500000, "repost_count": 5000, "like_count": 20000},
        )
    )
    assert store.get_event(event_id).attention >= 40
    store.close()


def test_event_clustering_joins_paraphrases_but_not_same_person_unrelated_story(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.28)
    chelsea_a, _, _ = engine.ingest(
        Observation(
            source="coindesk",
            source_kind="news",
            title="Circle USDC takes over Chelsea jersey in first sponsorship deal",
            source_item_id="chelsea-a",
        )
    )
    chelsea_b, created, _ = engine.ingest(
        Observation(
            source="cointelegraph",
            source_kind="news",
            title="Chelsea FC gets stablecoin sponsor after UK warning",
            source_item_id="chelsea-b",
        )
    )
    trump_a, _, _ = engine.ingest(
        Observation(
            source="news-a",
            source_kind="news",
            title="Trump comments on a new trade tariff",
            source_item_id="trump-a",
        )
    )
    trump_b, unrelated_created, _ = engine.ingest(
        Observation(
            source="news-b",
            source_kind="news",
            title="Trump attends a football match in Florida",
            source_item_id="trump-b",
        )
    )
    assert chelsea_a == chelsea_b and created is False
    assert trump_a != trump_b and unrelated_created is True
    store.close()


def test_html_feed_artifacts_do_not_merge_unrelated_internet_stories(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3")
    engine = EventEngine(store, similarity=0.28)
    common_markup = '&lt;a target="_blank" style="color:#6f6f6f"&gt;&amp;nbsp;&lt;/a&gt;'
    sports, _, _ = engine.ingest(
        Observation(
            source="google-news-reverse",
            source_kind="news",
            title="Vancouver Little League player goes viral for revealing his dream job",
            text=common_markup,
            source_item_id="sports",
        )
    )
    governance, created, _ = engine.ingest(
        Observation(
            source="google-news-viral",
            source_kind="news",
            title="Internet Governance Lab 2026: AI and the Internet",
            text=common_markup,
            source_item_id="governance",
        )
    )
    assert sports != governance
    assert created is True
    assert "#6f6f6f" not in extract_aliases("headline", common_markup)
    store.close()


def test_paper_position_sizing_daily_limit_and_partial_exit(tmp_path: Path):
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(chain="solana", address="A" * 32, name="Example")
    store.upsert_token(token)
    snapshot = TokenSnapshot(
        chain="solana",
        address=token.address,
        price_usd=0.01,
        liquidity_usd=100000,
        market_cap_usd=1000000,
        volume_5m_usd=50000,
        buys_5m=50,
        sells_5m=20,
    )
    store.add_snapshot(snapshot)
    policy = PaperPolicy(
        {
            "risk_per_trade_pct": 0.005,
            "max_position_usd": 35,
            "min_position_usd": 3,
            "max_cash_fraction": 0.08,
            "max_liquidity_impact_pct": 0.0025,
            "max_daily_new_exposure_usd": 100,
            "stop_loss_pct": -0.35,
            "max_open_positions": 3,
        }
    )
    size = policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=0,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=0,
    )
    assert 3 <= size <= 35
    assert policy.size(
        cash_usd=1000,
        equity_usd=1000,
        open_count=0,
        snapshot=snapshot,
        score=85,
        daily_exposure_usd=100,
    ) == 0
    position = store.paper_buy(event_id=1, token=token, price=0.01, gross_usd=size, fee_bps=60, reason="test")
    assert position.quantity > 0
    result = store.paper_sell(token.token_id, price=0.02, fraction=0.25, fee_bps=60, reason="partial")
    remaining = store.position(token.token_id)
    assert result["pnl_usd"] > 0
    assert remaining is not None and remaining.quantity == pytest.approx(position.quantity * 0.75)
    assert store.daily_buy_gross_usd() == pytest.approx(size)
    store.close()


def test_live_mode_is_locked(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"mode": "live"}), encoding="utf-8")
    with pytest.raises(ValueError, match="hard-locked"):
        load_config(config)


def test_old_config_keys_are_migrated_and_negative_drawdown_is_normalized(tmp_path: Path):
    payload = {
        "mode": "paper",
        "initial_cash_usd": 1000,
        "bridge": {"host": "127.0.0.1", "port": 8765, "token": "x" * 32},
        "runtime": {"event_scan_seconds": 7, "token_watch_seconds": [20, 60]},
        "events": {"minimum_attention_score": 44, "max_source_age_minutes": 25},
        "candidate": {"recent_token_hours": 6, "min_total_score": 66},
        "paper": {
            "fee_rate": 0.006,
            "risk_per_trade": 0.005,
            "max_liquidity_impact": 0.0025,
            "trailing_drawdown_pct": -0.28,
        },
        "live": {"enabled": False},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    config, _ = load_config(path)
    assert config["paper"]["starting_cash_usd"] == 1000
    assert config["paper"]["fee_bps"] == pytest.approx(60)
    assert config["paper"]["trailing_drawdown_pct"] == pytest.approx(0.28)
    assert config["event_scan_seconds"] == 7
    assert config["event_min_attention"] == 44
    assert config["candidate"]["token_watch_minutes"] == 360
    assert config["candidate"]["retry_seconds"] == [20, 60]
    assert config["candidate"]["max_source_age_minutes"] == 25


def test_browser_extension_persists_queue_filters_old_posts_and_heartbeats():
    root = Path(__file__).resolve().parents[1] / "browser-extension"
    background = (root / "background.js").read_text(encoding="utf-8")
    content = (root / "content.js").read_text(encoding="utf-8")
    manifest = (root / "manifest.json").read_text(encoding="utf-8")
    assert "chrome.storage.local" in background
    assert "pendingObservations" in background
    assert "/v1/heartbeat" in background
    assert "MutationObserver" in content
    assert "PRIVATE_PATH" in content
    assert "maxPostAgeMinutes" in content
    assert '"cookies"' not in manifest.lower()


def test_exact_contract_address_dominates_name_similarity():
    ca = "0x1111111111111111111111111111111111111111"
    event_text = f"Official post CA: {ca}"
    addresses = extract_addresses(event_text)
    exact = TokenCandidate(chain="bsc", address=ca, name="Different Name", symbol="DIFF")
    copy = TokenCandidate(
        chain="bsc",
        address="0x2222222222222222222222222222222222222222",
        name="Official Post",
        symbol="OFFICIAL",
    )
    assert CandidateEvaluator._match_score(["Official Post"], event_text, exact, addresses) == 100
    assert CandidateEvaluator._match_score(["Official Post"], event_text, copy, addresses) < 100


def test_official_contract_filters_higher_liquidity_name_clone(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        ca = "0x1111111111111111111111111111111111111111"
        clone_ca = "0x2222222222222222222222222222222222222222"
        engine = EventEngine(store)
        event_id, _, _ = engine.ingest(
            Observation(
                source="browser:x:official",
                source_kind="official_social",
                title=f"Official launch CA: {ca}",
                text=f"Official launch CA: {ca}",
                availability_proof="local_receive",
            )
        )
        event = store.get_event(event_id)
        exact = TokenCandidate(chain="bsc", address=ca, name="Official Launch", symbol="REAL")
        clone = TokenCandidate(chain="bsc", address=clone_ca, name="Official Launch", symbol="REAL")
        exact_snap = TokenSnapshot("bsc", ca, 0.001, 20000, 100000, 10000, 20, 5)
        clone_snap = TokenSnapshot("bsc", clone_ca, 0.001, 1000000, 1000000, 500000, 500, 30)

        class FakeDex:
            async def quote(self, chain, address):
                return (exact, exact_snap) if chain == "bsc" and address.lower() == ca else None

            async def search(self, query, limit=25):
                return [(clone, clone_snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        evaluator = CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["bsc"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None
        assert decision.action == "CANDIDATE"
        assert decision.token_id == exact.token_id
        assert store.token(clone.token_id) is None
        store.close()

    asyncio.run(scenario())


def test_budgeted_agent_can_resolve_only_a_close_semantic_tie(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        engine = EventEngine(store)
        event_id, _, _ = engine.ingest(
            Observation(
                source="x:a",
                source_kind="social",
                title="Dancing Capybara becomes a viral meme",
                raw={"view_count": 1000000},
            )
        )
        original = store.get_event(event_id)
        store.update_event(
            event_id,
            title=original.title,
            aliases=original.aliases,
            attention=80,
            seen_at=original.last_seen_at,
        )
        event = store.get_event(event_id)
        first = TokenCandidate(chain="solana", address="A" * 32, name="Dancing Capybara", symbol="CAPY")
        second = TokenCandidate(chain="solana", address="B" * 32, name="Dancing Capybara", symbol="CAPY")
        first_snap = TokenSnapshot("solana", first.address, 0.001, 30000, 200000, 20000, 50, 10)
        second_snap = TokenSnapshot("solana", second.address, 0.001, 30000, 200000, 20000, 50, 10)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(first, first_snap), (second, second_snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            tier = None

            def ask(self, payload, tier="low"):
                self.tier = tier
                return {"preferred_token_id": second.token_id, "confidence": 0.9}

        agent = FakeAgent()
        evaluator = CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 5,
                "agent_tie_threshold": 3,
                "agent_resolution_confidence": {"low": 0.85, "medium": 0.78},
                "max_alias_queries": 1,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            agent,
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None and decision.action == "CANDIDATE"
        assert decision.token_id == second.token_id
        assert decision.canonical_margin == 5
        assert agent.tier == "medium"
        assert "agent_tiebreak=medium" in decision.reasons
        store.close()

    asyncio.run(scenario())


def test_momentum_rewards_real_activity():
    quiet = TokenSnapshot("solana", "a", 1, 1000, 10000, 10, 1, 1)
    active = TokenSnapshot("solana", "b", 1, 50000, 1000000, 30000, 120, 30)
    assert CandidateEvaluator._momentum_score(active) > CandidateEvaluator._momentum_score(quiet)


def test_exit_policy_handles_liquidity_and_trailing_drawdown():
    position = Position(
        token_id="solana:a",
        event_id=1,
        chain="solana",
        address="a",
        symbol="A",
        quantity=10,
        entry_price=1,
        cost_usd=10,
        remaining_cost_usd=10,
        highest_price=2,
        opened_at="2026-01-01T00:00:00Z",
    )
    policy = PaperPolicy(
        {
            "stop_loss_pct": -0.35,
            "trailing_activate_pct": 0.6,
            "trailing_drawdown_pct": 0.28,
            "emergency_liquidity_usd": 3000,
            "max_holding_hours": 100000,
        }
    )
    low_liquidity = TokenSnapshot("solana", "a", 1.4, 1000, 10000, 1000, 10, 5)
    assert policy.exit_action(position, low_liquidity) == (1.0, "liquidity_emergency")
    trailing = TokenSnapshot("solana", "a", 1.4, 10000, 10000, 1000, 10, 5)
    assert policy.exit_action(position, trailing) == (1.0, "trailing_exit")


def test_exit_policy_uses_narrative_and_flow_decay():
    now = datetime.now(timezone.utc)
    position = Position(
        token_id="solana:a",
        event_id=1,
        chain="solana",
        address="a",
        symbol="A",
        quantity=10,
        entry_price=1,
        cost_usd=10,
        remaining_cost_usd=10,
        highest_price=1.2,
        opened_at=now - timedelta(minutes=45),
    )
    event = EventView(
        id=1,
        title="Viral event",
        aliases=["Viral"],
        attention=60,
        first_seen_at=now - timedelta(hours=4),
        last_seen_at=now - timedelta(minutes=150),
    )
    snapshot = TokenSnapshot("solana", "a", 1.05, 10000, 100000, 1000, 2, 10)
    policy = PaperPolicy(
        {
            "stop_loss_pct": -0.35,
            "trailing_activate_pct": 0.6,
            "trailing_drawdown_pct": 0.28,
            "emergency_liquidity_usd": 3000,
            "narrative_stale_minutes": 120,
            "narrative_min_holding_minutes": 20,
            "narrative_exit_buy_ratio": 0.45,
            "max_holding_hours": 24,
        }
    )
    assert policy.exit_action(position, snapshot, event=event) == (1.0, "narrative_and_flow_decay")


def test_solana_rugcheck_high_score_is_rejected():
    class Response:
        def json(self):
            return {"score_normalised": 95, "risks": [{"level": "danger"}]}

    class FakeHttp:
        async def get(self, *args, **kwargs):
            return Response()

    async def scenario():
        checker = SafetyChecker(
            FakeHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "rugcheck": True,
                "max_solana_risk_score": 79,
            },
        )
        snap = TokenSnapshot("solana", "a", 1, 10000, 100000, 1000, 10, 2)
        ok, reasons = await checker.check(snap)
        assert ok is False
        assert "solana_risk_score_too_high" in reasons

    asyncio.run(scenario())
