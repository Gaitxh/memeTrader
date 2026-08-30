from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from memetrader.collectors import DexScreenerClient
from memetrader.models import CandidateDecision, EventView, Observation, Position, TokenCandidate, TokenSnapshot
from memetrader.runtime import load_config
from memetrader.store import Store
from memetrader.strategy import (
    CandidateEvaluator,
    EventEngine,
    classify_event_topic,
    evidence_origin,
    PaperPolicy,
    SafetyChecker,
    extract_addresses,
    extract_aliases,
    is_context_searchable_token_name,
    is_distinctive_token_name,
    is_promotional_market_content,
    replay_guard,
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


def test_source_learning_records_only_closed_paper_lead_evidence(tmp_path: Path):
    store = Store(tmp_path / "learning.sqlite3", initial_cash_usd=1000)
    now = datetime.now(timezone.utc)
    event_id = store.create_event(
        "Forward mascot event",
        ["mascot"],
        80,
        now - timedelta(minutes=3),
        topic="animals_internet_culture",
    )
    observations = [
        Observation(
            source="browser:x:alpha",
            source_kind="social",
            title="First local post",
            observed_at=now - timedelta(minutes=3),
            ingested_at=now - timedelta(minutes=3),
            role="feature",
            source_item_id="lead-a",
            raw={
                "browser": {"platform": "x"},
                "source_entity_id": "alpha",
                "trend_lane_id": "culture_entertainment",
            },
        ),
        Observation(
            source="news-b",
            source_kind="news",
            title="Independent report within lead window",
            observed_at=now - timedelta(minutes=2, seconds=30),
            ingested_at=now - timedelta(minutes=2, seconds=30),
            role="confirmation",
            source_item_id="lead-b",
        ),
        Observation(
            source="promotion-c",
            source_kind="social",
            title="Context-only promotion",
            observed_at=now - timedelta(minutes=2, seconds=50),
            ingested_at=now - timedelta(minutes=2, seconds=50),
            role="promotion",
            source_item_id="promo",
        ),
        Observation(
            source="delayed-ingestion",
            source_kind="news",
            title="Observed early but ingested after the position opened",
            published_at=now - timedelta(minutes=3),
            observed_at=now - timedelta(minutes=3),
            ingested_at=now + timedelta(minutes=1),
            role="feature",
            source_item_id="delayed-ingestion",
        ),
        Observation(
            source="future-published",
            source_kind="news",
            title="Future publication timestamp",
            published_at=now + timedelta(minutes=1),
            observed_at=now - timedelta(minutes=3),
            ingested_at=now - timedelta(minutes=3),
            role="feature",
            source_item_id="future-published",
        ),
        Observation(
            source="late-d",
            source_kind="news",
            title="Later confirmation",
            observed_at=now - timedelta(minutes=1),
            ingested_at=now - timedelta(minutes=1),
            role="confirmation",
            source_item_id="late",
        ),
    ]
    ids = []
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
        ids.append(observation_id)
    token = TokenCandidate(chain="solana", address="L" * 32, name="Mascot", symbol="MASC")
    store.upsert_token(token, seen_at=now)
    store.paper_buy(event_id=event_id, token=token, price=1.0, gross_usd=100, fee_bps=0, reason="test")
    store.paper_sell(token.token_id, price=1.1, fraction=0.5, fee_bps=0, reason="partial")
    assert store.db.execute("SELECT COUNT(*) FROM source_utility_outcomes").fetchone()[0] == 0
    store.paper_sell(token.token_id, price=1.2, fraction=1.0, fee_bps=0, reason="close")
    outcome_rows = list(store.db.execute("SELECT * FROM source_utility_outcomes"))
    assert {int(row["source_observation_id"]) for row in outcome_rows} == set(ids[:2])
    assert all(abs(float(row["attribution_weight"]) - 0.5) < 1e-9 for row in outcome_rows)
    assert all(row["dimension"] != "entity" or row["value"] == "alpha" for row in outcome_rows)
    assert any(
        row["dimension"] == "event_topic" and row["value"] == "animals_internet_culture"
        for row in outcome_rows
    )
    assert not any(
        row["value"] in {"promotion-c", "delayed-ingestion", "future-published", "late-d"}
        for row in outcome_rows
    )

    conservative = store.source_learning_summary()
    assert conservative["status"] == "collecting_samples"
    assert conservative["summary"]["closed_paper_outcomes"] == 1
    relaxed = store.source_learning_summary(
        min_closed_outcomes=0.5,
        min_event_days=1,
        min_losing_outcomes=0,
        entity_min_closed_outcomes=0.5,
        entity_min_event_days=1,
        entity_min_platforms=1,
    )
    assert relaxed["status"] == "learning_active"
    assert any(item["dimension"] == "platform" and item["value"] == "x" for item in relaxed["items"])
    topic_item = next(
        item
        for item in relaxed["items"]
        if item["dimension"] == "event_topic" and item["value"] == "animals_internet_culture"
    )
    assert topic_item["rotation_active"] is False
    assert topic_item["rotation_multiplier"] == 1.0
    lane_item = next(
        item
        for item in relaxed["items"]
        if item["dimension"] == "trend_lane" and item["value"] == "culture_entertainment"
    )
    assert lane_item["rotation_active"] is False
    assert lane_item["rotation_multiplier"] == 1.0
    store.close()


def test_event_topic_is_deterministic_forward_only_and_immutable(tmp_path: Path):
    assert classify_event_topic("Otter mascot becomes a viral emoji") == "animals_internet_culture"
    assert classify_event_topic("World Cup football final") == "sports"
    assert classify_event_topic("New AI gaming chip launches") == "ai_tech_gaming"
    assert classify_event_topic("Singer announces a concert") == "celebrity_entertainment"
    assert classify_event_topic("President calls an election") == "political_public_figure"
    assert classify_event_topic("Solana memecoin launches") == "crypto_native"
    assert classify_event_topic("Unclassified local moment") == "other"

    store = Store(tmp_path / "topics.sqlite3")
    event_id = store.create_event("Older event", [], 0)
    assert store.get_event(event_id).topic == "unknown"
    store.update_event(event_id, title="Otter mascot", aliases=["otter"], attention=70)
    assert store.get_event(event_id).topic == "unknown"
    store.close()


def test_dexscreener_attached_links_are_typed_and_promotions_stay_context_only(tmp_path: Path):
    assert DexScreenerClient._classify_link("https://x.com/search?q=mascot")[:2] == ("search", "x")
    assert DexScreenerClient._classify_link("https://truthsocial.com/@realDonaldTrump/123")[:2] == (
        "social_post", "truth"
    )
    assert DexScreenerClient._classify_link("https://www.threads.com/@creator")[:2] == (
        "social_profile", "threads"
    )
    assert DexScreenerClient._classify_link("https://t.me/example")[:2] == ("telegram_manual", "telegram")

    class Response:
        def json(self):
            return [
                {
                    "chainId": "solana",
                    "tokenAddress": "D" * 32,
                    "url": "https://dexscreener.com/solana/pair",
                    "links": [
                        {"type": "twitter", "url": "https://x.com/example"},
                        {"label": "Telegram", "url": "https://t.me/example"},
                    ],
                }
            ]

    class Http:
        async def get(self, *args, **kwargs):
            return Response()

    rows = asyncio.run(DexScreenerClient(Http()).discover_surface("boosts_latest", {"solana"}))
    assert rows
    assert {row["role"] for row in rows} == {"promotion"}
    assert any(row["link_kind"] == "telegram_manual" and row["verification_status"] == "manual_only" for row in rows)
    assert all(row["verification_status"] != "verified" for row in rows)
    store = Store(tmp_path / "dex-links.sqlite3")
    for row in rows:
        store.upsert_token_source_link(row, observed_at="2026-08-30T00:00:00Z")
        store.upsert_token_source_link(row, observed_at="2026-08-30T00:01:00Z")
    persisted = store.token_source_links(f"solana:{'D' * 32}")
    assert {row["role"] for row in persisted} == {"promotion"}
    assert all(row["first_observed_at"] == "2026-08-30T00:00:00Z" for row in persisted)
    assert all(row["last_observed_at"] == "2026-08-30T00:01:00Z" for row in persisted)
    store.close()


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
    received = Observation(
        source="browser:x",
        source_kind="social",
        title="old post inserted into a live page",
        published_at="2026-01-01T00:00:00Z",
        observed_at="2026-01-01T03:00:00Z",
        ingested_at="2026-01-01T03:00:00Z",
        availability_proof="local_receive",
        capture_phase="live",
    )
    decision_at = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    assert "stale_initial_page" in temporal_rejection_reasons(initial, decision_at, 30)
    assert "stale_polled_item" in temporal_rejection_reasons(polled, decision_at, 30)
    assert "stale_received_item" in temporal_rejection_reasons(received, decision_at, 30)


def test_identity_and_future_published_content_are_never_decision_evidence():
    decision_at = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    identity = Observation(
        source="browser:x:identity",
        source_kind="social",
        title="Identity context only",
        role="identity",
        observed_at=decision_at,
        ingested_at=decision_at,
        availability_proof="local_receive",
    )
    future = Observation(
        source="rss:future",
        source_kind="news",
        title="Clock-skewed future article",
        role="feature",
        published_at=decision_at + timedelta(hours=1),
        observed_at=decision_at,
        ingested_at=decision_at,
        availability_proof="local_poll",
        raw={"published_time_in_future": True},
    )
    assert "non_feature_role" in temporal_rejection_reasons(identity, decision_at, 30)
    assert "published_time_in_future" in temporal_rejection_reasons(future, decision_at, 30)
    accepted, rejected = replay_guard([identity, future], decision_at, 30)
    assert accepted == []
    assert rejected["browser:x:identity"] == ["non_feature_role"]
    assert "published_time_in_future" in rejected["rss:future"]


def test_reverse_name_distinctiveness_blocks_generic_short_terms():
    assert is_distinctive_token_name("Peanut") is True
    assert is_distinctive_token_name("Viral Animal") is True
    assert is_distinctive_token_name("牛来") is True
    assert is_distinctive_token_name("热点") is False
    assert is_context_searchable_token_name("新闻") is False
    assert is_distinctive_token_name("Luce") is False
    assert is_context_searchable_token_name("Luce") is True
    assert is_distinctive_token_name("Neiro") is True
    assert is_distinctive_token_name("Gang") is False
    assert is_distinctive_token_name("AI") is False
    assert is_distinctive_token_name("Coins") is False
    assert is_distinctive_token_name("Attention") is False
    assert is_context_searchable_token_name("Musk") is True
    assert is_distinctive_token_name("Musk") is False


def test_promotional_market_listicles_are_not_event_evidence():
    assert is_promotional_market_content(
        "Top Altcoin News: 7 Meme Coins Enter the Spotlight as a Presale Leads the List"
    )
    assert is_promotional_market_content(
        "Top 100x Cryptos Before the Next Breakout: Coins to Watch"
    )
    assert is_promotional_market_content("2026年十大百倍币：这些预售代币值得关注")
    assert not is_promotional_market_content(
        "Rescued otter video goes viral after a mayor shares it"
    )


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


def test_social_source_independence_uses_only_explicit_persisted_entity_ids():
    x_nasa = {
        "source": "x:nasa",
        "source_kind": "official_social",
        "raw_json": json.dumps({"source_entity_id": "nasa"}),
    }
    youtube_nasa = {
        "source": "youtube:nasa",
        "source_kind": "social",
        "raw_json": json.dumps({"source_entity_id": "nasa"}),
    }
    x_spacex = {
        "source": "x:spacex",
        "source_kind": "official_social",
        "raw_json": json.dumps({"source_entity_id": "spacex"}),
    }
    unknown_x = {"source": "x:unknown", "source_kind": "social", "raw_json": "{}"}
    unknown_youtube = {"source": "youtube:unknown", "source_kind": "social", "raw_json": "{}"}
    forged = {
        "source": "youtube:other",
        "source_kind": "social",
        "raw_json": json.dumps({"source_entity_id": "NASA/../../forged"}),
    }

    assert evidence_origin(x_nasa) == evidence_origin(youtube_nasa) == "entity:nasa"
    assert len({evidence_origin(x_nasa), evidence_origin(youtube_nasa)}) == 1
    assert len({evidence_origin(x_nasa), evidence_origin(x_spacex)}) == 2
    assert len({evidence_origin(unknown_x), evidence_origin(unknown_youtube)}) == 2
    assert evidence_origin(forged) == "youtube:other"


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


def test_candidate_ranking_is_neutral_until_runtime_finalizes(tmp_path: Path):
    store = Store(tmp_path / "ranking.sqlite3")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event = EventView(1, "Viral otter", ["otter"], 80, now, now)
    token = TokenCandidate("solana", "A" * 32, "Viral Otter", "OTTER")
    snapshot = TokenSnapshot(
        "solana", token.address, 0.01, 50_000, 500_000, 12_000, 30, 10,
        observed_at=now,
        provider="dexscreener",
    )
    decision = CandidateDecision(1, token.token_id, "CANDIDATE", 80, 90, 10, ["test"], created_at=now)
    evaluator = CandidateEvaluator(store, None, None, {}, None)
    evaluator._persist_ranking(
        event,
        evaluated_at=now,
        ranked=[(80, 90, token, snapshot, ["test"])],
        decision=decision,
        safety_checked=True,
    )
    pending = store.candidate_ranking(1)
    assert pending["status"] == "pending_runtime"
    assert pending["outcome"] == "UNAVAILABLE"
    assert pending["final_outcome"] is None
    assert pending["candidates"][0]["action"] == "PENDING_RUNTIME"

    decision_id = store.add_decision(decision)
    store.finalize_candidate_ranking(1, decision, decision_id=decision_id)
    final = store.candidate_ranking(1)
    assert final["status"] == "completed"
    assert final["outcome"] == "CANDIDATE"
    assert final["final_outcome"]["decision_id"] == decision_id
    assert final["candidates"][0]["action"] == "CANDIDATE"
    store.close()


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
    options = (root / "options.html").read_text(encoding="utf-8")
    manifest = (root / "manifest.json").read_text(encoding="utf-8")
    assert "chrome.storage.local" in background
    assert "pendingObservations" in background
    assert "/v1/heartbeat" in background
    assert "MutationObserver" in content
    assert "PRIVATE_PATH" in content
    assert "maxPostAgeMinutes" in content
    assert "http://127.0.0.1:8787/api/watchlist" in background
    assert "memetrader-watchlist-sync" in background
    assert 'credentials: "omit"' in background
    assert "watchAccountEntries" in background
    assert "entity_id" in background and "source_entity_id" in content
    assert "matchedWatchAccount(author)" in content
    assert "item.platform === platform()" in content
    assert "authorKey === accountKey(item.handle)" in content
    assert "platformStates" in content and "platformEnabled()" in content
    assert all(state in content for state in ("content_visible", "login_prompt", "no_recent_items"))
    assert "selector_count" in content and "page_url" in content
    assert options.count('id="maxPostAgeMinutes"') == 1
    assert "watchlistLastSyncAt" in (root / "options.js").read_text(encoding="utf-8")
    assert '"cookies"' not in manifest.lower()
    assert '"tabs"' not in manifest.lower()


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


def test_generic_token_name_cannot_hijack_unrelated_news_event(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        event_id, _, _ = EventEngine(store).ingest(
            Observation(
                source="news-a",
                source_kind="news",
                title="Fresh market attention follows a quarterly company report",
                availability_proof="local_poll",
            )
        )
        token = TokenCandidate(chain="solana", address="A" * 32, name="Attention", symbol="ATTENTION")
        snap = TokenSnapshot("solana", token.address, 0.01, 250000, 1000000, 50000, 500, 20)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(token, snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        decision = await CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        ).discover_and_decide(store.get_event(event_id))
        assert decision is not None
        assert decision.action == "WAIT"
        assert decision.reasons == ["no_matching_token"]
        assert store.token(token.token_id) is None
        ranking = store.candidate_ranking(event_id)
        assert ranking is not None
        assert ranking["status"] == "pending_runtime" and ranking["outcome"] == "UNAVAILABLE"
        assert ranking["candidate_count_total"] == 0
        assert ranking["candidates"] == []
        assert ranking["final_outcome"] is None
        assert ranking["outcome_reasons"] == ["no_matching_token"]
        store.close()

    asyncio.run(scenario())


def test_four_character_person_name_requires_more_than_text_overlap(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        event_id, _, _ = EventEngine(store).ingest(
            Observation(
                source="news-a",
                source_kind="news",
                title="Elon Musk comments on a new spacecraft test",
                availability_proof="local_poll",
            )
        )
        token = TokenCandidate(chain="solana", address="M" * 32, name="Musk", symbol="MUSK")
        snap = TokenSnapshot("solana", token.address, 0.01, 250000, 1000000, 50000, 500, 20)

        class FakeDex:
            async def quote(self, chain, address):
                return None

            async def search(self, query, limit=25):
                return [(token, snap)]

        class FakeSafety:
            async def check(self, snapshot):
                return True, []

        class FakeAgent:
            def ask(self, payload, tier="low"):
                return None

        decision = await CandidateEvaluator(
            store,
            FakeDex(),
            FakeSafety(),
            {
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
            },
            FakeAgent(),
        ).discover_and_decide(store.get_event(event_id))
        assert decision is not None and decision.action == "WAIT"
        assert decision.reasons == ["no_matching_token"]
        assert store.token(token.token_id) is None
        store.close()

    asyncio.run(scenario())


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
        exact = TokenCandidate(chain="bsc", address=ca, name="Test", symbol="TST")
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


def test_verified_token_context_link_excludes_unlinked_name_clone(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "db.sqlite3")
        linked = TokenCandidate(chain="solana", address="A" * 32, name="Otter Community", symbol="OTTR")
        clone = TokenCandidate(chain="solana", address="B" * 32, name="Viral Rescue Otter", symbol="OTTER")
        engine = EventEngine(store)
        event_id = None
        for domain in ("publisher-a.example", "publisher-b.example"):
            current_id, _, _ = engine.ingest(
                Observation(
                    source=f"agent-search:{domain}",
                    source_kind="news",
                    title="A viral rescue otter story spreads globally",
                    text="Independent reporting confirms the same current event.",
                    url=f"https://{domain}/story",
                    availability_proof="agent_search_verified",
                    role="confirmation",
                    source_item_id=f"https://{domain}/story",
                    raw={
                        "agent_web_search": True,
                        "agent_task": "token_context",
                        "reverse_token_id": linked.token_id,
                        "token_id": linked.token_id,
                        "confidence": 0.91,
                    },
                )
            )
            event_id = current_id
        event = store.get_event(int(event_id))
        linked_snap = TokenSnapshot("solana", linked.address, 0.001, 50000, 500000, 30000, 80, 20)
        clone_snap = TokenSnapshot("solana", clone.address, 0.001, 50000, 500000, 30000, 80, 20)

        class FakeDex:
            async def quote(self, chain, address):
                if chain == "solana" and address == linked.address:
                    return linked, linked_snap
                return None

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
                "chains": ["solana"],
                "min_match_score": 1,
                "min_candidate_score": 1,
                "min_canonical_margin": 1,
                "agent_tie_threshold": 0,
                "max_alias_queries": 2,
                "token_watch_minutes": 240,
                "max_source_age_minutes": 30,
                "min_reverse_independent_sources": 2,
            },
            FakeAgent(),
        )
        decision = await evaluator.discover_and_decide(event)
        assert decision is not None
        assert decision.action == "CANDIDATE"
        assert decision.token_id == linked.token_id
        assert "agent_context_exact_token_link" in decision.reasons
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
        ranking = store.candidate_ranking(event_id)
        assert ranking is not None
        assert ranking["candidate_count_total"] == 2
        assert [item["rank"] for item in ranking["candidates"]] == [1, 2]
        assert [item["token_id"] for item in ranking["candidates"]] == [second.token_id, first.token_id]
        assert ranking["candidates"][0]["action"] == "PENDING_RUNTIME"
        assert ranking["candidates"][1]["action"] == "NOT_SELECTED"
        assert ranking["candidates"][0]["canonical_margin"] == 5
        assert ranking["tie_break"] == {
            "used": True,
            "tier": "medium",
            "confidence": 0.9,
            "preferred_token_id": second.token_id,
        }
        serialized = json.dumps(ranking)
        assert "raw_json" not in serialized and "social_urls" not in serialized
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


def test_required_external_safety_reports_fail_closed():
    class FailingHttp:
        async def get(self, *args, **kwargs):
            raise TimeoutError("provider unavailable")

    async def scenario():
        checker = SafetyChecker(
            FailingHttp(),
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "max_tax_pct": 12,
                "goplus_evm": True,
                "honeypot_is": True,
                "require_evm_security_report": True,
                "require_evm_simulation": False,
                "goplus_solana": True,
                "rugcheck": True,
                "require_solana_report": True,
                "max_solana_risk_score": 79,
            },
        )
        bsc = TokenSnapshot("bsc", "0x" + "1" * 40, 1, 10000, 100000, 1000, 10, 2)
        sol = TokenSnapshot("solana", "A" * 32, 1, 10000, 100000, 1000, 10, 2)
        bsc_ok, bsc_reasons = await checker.check(bsc)
        sol_ok, sol_reasons = await checker.check(sol)
        assert bsc_ok is False and "evm_security_report_unavailable" in bsc_reasons
        assert sol_ok is False and "solana_risk_report_unavailable" in sol_reasons

    asyncio.run(scenario())


def test_goplus_evm_clean_report_is_accepted_without_honeypot_call():
    address = "0x" + "1" * 40

    class Response:
        def json(self):
            return {
                "code": 1,
                "result": {
                    address.lower(): {
                        "is_honeypot": "0",
                        "is_open_source": "1",
                        "buy_tax": "0.03",
                        "sell_tax": "0.04",
                        "hidden_owner": "0",
                    }
                },
            }

    class FakeHttp:
        def __init__(self):
            self.urls = []

        async def get(self, url, *args, **kwargs):
            self.urls.append(str(url))
            return Response()

    async def scenario():
        http = FakeHttp()
        checker = SafetyChecker(
            http,
            {
                "min_liquidity_usd": 100,
                "min_5m_transactions": 1,
                "min_buy_ratio": 0.4,
                "max_tax_pct": 12,
                "goplus_evm": True,
                "honeypot_is": True,
                "require_evm_security_report": True,
                "require_evm_simulation": False,
                "goplus_evm_require_open_source": True,
                "goplus_evm_reject_flags": ["hidden_owner"],
            },
        )
        snap = TokenSnapshot("bsc", address, 1, 10000, 100000, 1000, 10, 2)
        ok, reasons = await checker.check(snap)
        assert ok is True and reasons == []
        assert snap.buy_tax_pct == pytest.approx(3.0)
        assert snap.sell_tax_pct == pytest.approx(4.0)
        assert snap.honeypot is False and snap.sellable is True
        assert any("gopluslabs.io" in url for url in http.urls)
        assert not any("honeypot.is" in url for url in http.urls)

    asyncio.run(scenario())


def test_goplus_evm_dangerous_flag_is_rejected():
    address = "0x" + "2" * 40

    class Response:
        def json(self):
            return {
                "code": 1,
                "result": {
                    address.lower(): {
                        "is_honeypot": "0",
                        "is_open_source": "1",
                        "hidden_owner": "1",
                    }
                },
            }

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
                "goplus_evm": True,
                "honeypot_is": False,
                "require_evm_security_report": True,
                "goplus_evm_require_open_source": True,
                "goplus_evm_reject_flags": ["hidden_owner"],
            },
        )
        ok, reasons = await checker.check(
            TokenSnapshot("bsc", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert ok is False
        assert "goplus_evm_hidden_owner" in reasons

    asyncio.run(scenario())


def test_goplus_solana_can_cover_rugcheck_outage_and_rejects_risky_authority():
    address = "A" * 32

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeHttp:
        def __init__(self, risky=False):
            self.risky = risky

        async def get(self, url, *args, **kwargs):
            if "gopluslabs.io" in str(url):
                return Response(
                    {
                        "code": 1,
                        "result": {
                            address: {
                                "mintable": {"status": "1" if self.risky else "0", "authority": []},
                                "freezable": {"status": "0", "authority": []},
                            }
                        },
                    }
                )
            raise TimeoutError("rugcheck unavailable")

    async def scenario():
        config = {
            "min_liquidity_usd": 100,
            "min_5m_transactions": 1,
            "min_buy_ratio": 0.4,
            "goplus_solana": True,
            "rugcheck": True,
            "require_solana_report": True,
            "goplus_solana_reject_flags": ["mintable", "freezable"],
        }
        clean_checker = SafetyChecker(FakeHttp(False), config)
        clean_ok, clean_reasons = await clean_checker.check(
            TokenSnapshot("solana", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert clean_ok is True and clean_reasons == []

        risky_checker = SafetyChecker(FakeHttp(True), config)
        risky_ok, risky_reasons = await risky_checker.check(
            TokenSnapshot("solana", address, 1, 10000, 100000, 1000, 10, 2)
        )
        assert risky_ok is False
        assert "goplus_solana_mintable" in risky_reasons

    asyncio.run(scenario())
