from __future__ import annotations

import json
import socket
import threading
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from memetrader.autonomous_search import (
    REGISTRY_KEY,
    TREND_LANE_SELECTION_KEY,
    TREND_RESULT_KEY,
    TREND_RUN_KEY,
    TREND_WATCH_SELECTION_KEY,
)
from memetrader.models import CandidateDecision, Observation, TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import initial_config
from memetrader.store import Store
from memetrader.web import WebData, create_server


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _config(tmp_path: Path) -> tuple[Path, dict]:
    config = initial_config()
    config["database"] = "db.sqlite3"
    config["lock_file"] = "robot.lock"
    config["bridge"]["enabled"] = False
    config["bridge"]["token"] = "bridge-secret-must-never-be-returned"
    config["notifications"]["telegram_bot_token"] = "telegram-secret-must-never-be-returned"
    config["notifications"]["telegram_chat_id"] = "secret-chat-id"
    config["notifications"]["jsonl"] = "notifications.jsonl"
    config["sources"]["rss"] = [
        {"name": "example-news", "url": "https://example.com/feed.xml", "kind": "news", "enabled": True}
    ]
    config["sources"]["mastodon"] = []
    config["sources"]["bluesky_queries"] = []
    config["sources"]["gecko_networks"] = []
    config["sources"]["pumpportal"]["enabled"] = False
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def _seed(path: Path) -> tuple[int, str]:
    store = Store(path, initial_cash_usd=1000)
    now = utcnow()
    event_id = store.create_event("Viral otter becomes an internet mascot", ["otter", "mascot"], 72, now)
    observations = [
        Observation(
            source="news-a",
            source_kind="news",
            title="Viral otter becomes an internet mascot",
            text="x" * 2100,
            url="https://news-a.example/story",
            published_at=now - timedelta(minutes=2),
            observed_at=now,
            ingested_at=now,
            role="feature",
            source_item_id="feature-1",
            author="Otter Daily",
            raw={
                "account_type": "publisher",
                "authority_tier": "established",
                "is_verified": True,
                "trend_lane_id": "culture_entertainment",
                "trend_lane_run_id": "seed-lane-run",
                "trend_lane_taxonomy": "trend-lanes/v1",
                "view_count": 125_000,
                "like_count": 8_500,
            },
        ),
        Observation(
            source="browser:x:otter",
            source_kind="social",
            title="Older otter identity page",
            url="https://x.com/otter/status/1",
            published_at=now - timedelta(hours=2),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="identity-1",
            author="otter",
            raw={
                "original_role": "confirmation",
                "stale_first_observation": True,
                "source_entity_id": "otter_daily",
                "bridge_token": "must-never-be-returned",
            },
        ),
        Observation(
            source="promotion-list",
            source_kind="news",
            title="Top coins to buy after viral otter",
            url="https://promotion.example/list",
            observed_at=now,
            ingested_at=now,
            role="promotion",
            source_item_id="promotion-1",
            author="Token Promotions",
            raw={"non_event_market_promotion": True},
        ),
        Observation(
            source="future-clock",
            source_kind="news",
            title="Future timestamp cannot be evidence",
            url="https://future.example/story",
            published_at=now + timedelta(hours=1),
            observed_at=now,
            ingested_at=now,
            role="identity",
            source_item_id="future-1",
            raw={"original_role": "feature", "published_time_in_future": True},
        ),
    ]
    observation_ids = []
    for observation in observations:
        observation_id, _ = store.add_observation(observation)
        store.link_event_observation(event_id, observation_id)
        observation_ids.append(observation_id)

    token = TokenCandidate(
        chain="solana",
        address="A" * 32,
        name="Viral Otter",
        symbol="OTTER",
        created_at=now - timedelta(minutes=1),
        first_seen_at=now,
        source="geckoterminal",
        url="https://www.geckoterminal.com/solana/pools/example",
        social_urls=["https://x.com/otter"],
    )
    store.upsert_token(token, seen_at=now)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana",
            address=token.address,
            price_usd=0.01,
            liquidity_usd=50_000,
            market_cap_usd=500_000,
            volume_5m_usd=12_000,
            buys_5m=30,
            sells_5m=10,
            observed_at=now,
            ingested_at=now,
            provider="dexscreener",
        )
    )
    for role, url, kind, platform, surface in (
        ("identity", "https://x.com/otter", "social_profile", "x", "pair_info"),
        ("promotion", "https://dexscreener.com/solana/example", "dex_page", "dexscreener", "boosts_top"),
    ):
        store.upsert_token_source_link(
            {
                "token_id": token.token_id,
                "provider": "dexscreener",
                "discovery_surface": surface,
                "role": role,
                "original_url": url,
                "normalized_url": url,
                "link_kind": kind,
                "platform": platform,
                "verification_status": "provider_metadata",
                "raw": {"must_not_be_returned": "raw-provider-payload"},
            }
        )
    store.add_token_context_assessment(
        token.token_id,
        trigger="high_momentum_reverse_context",
        status="insufficient_verified_sources",
        snapshot_observed_at=now,
        momentum_score=84,
        assessment={
            "version": "token-context-assessment/v1",
            "decision_eligible": False,
            "affects": "context_display_and_verified_reporting_only",
            "project_claims": {
                "status": "project_attached_unverified",
                "items": [{"url": "https://x.com/otter", "platform": "x", "decision_eligible": False}],
            },
            "community_amplification": {
                "status": "project_channels_only", "platforms": ["x"],
                "summary": "Project-attached channel only.", "decision_eligible": False,
            },
            "public_figure_linkage": {
                "status": "unverified_candidates", "endorsement_inferred": False,
                "decision_eligible": False, "items": [],
            },
            "independent_reporting": {
                "status": "not_decision_eligible", "domains": ["news-a.example"],
                "confirmation_ingested": False, "items": [],
            },
            "onchain_momentum": {
                "snapshot_observed_at": iso(now), "momentum_score": 84,
                "liquidity_usd": 50000, "volume_5m_usd": 12000,
                "buys_5m": 30, "sells_5m": 10, "decision_eligible": False,
            },
        },
        agent_metadata={
            "task": "token_context", "model": "gpt-5.6-luna", "reasoning_effort": "low",
            "tokens_used": 321, "contains_credentials": False,
        },
        audit=[{"url": "https://news-a.example/story", "verified": True, "domain": "news-a.example"}],
        assessed_at=now,
    )
    decision = CandidateDecision(
        event_id=event_id,
        token_id=token.token_id,
        action="WAIT",
        score=65,
        match_score=88,
        canonical_margin=2,
        reasons=["match=88.0"],
        rejected_reasons=["canonical_token_ambiguous"],
        created_at=now,
    )
    decision_id = store.add_decision(decision)
    store.create_shadow_event_cohort(
        decision,
        decision_id=decision_id,
        source_observation_ids=observation_ids,
    )
    store.paper_buy(
        event_id=event_id,
        token=token,
        price=0.01,
        gross_usd=10,
        fee_bps=60,
        reason="test-paper-only",
    )
    store.heartbeat("example-news", item=True)
    day = now.date().isoformat()
    store.set_kv(f"autonomous_search_quota:{day}:trend_scout", 3)
    store.set_kv(f"autonomous_search_tokens:{day}:trend_scout", 12345)
    store.set_kv(TREND_RUN_KEY, iso(now - timedelta(minutes=3)))
    store.set_kv(
        TREND_RESULT_KEY,
        {
            "status": "completed",
            "run_at": iso(now - timedelta(minutes=3)),
            "events": [],
            "metadata": {"model": "fallback-model", "reasoning_effort": "low", "tokens_used": 12345},
        },
    )
    store.start_trend_lane_run(
        run_id="seed-lane-run",
        taxonomy_version="trend-lanes/v1",
        prompt_version="trend-scout/v2-lane-attribution",
        selection_mode="baseline_round_robin",
        surge=False,
        max_web_searches=4,
        started_at=now - timedelta(minutes=3),
        lanes=[
            {
                "id": "culture_entertainment",
                "prompt": "viral animals, internet culture, celebrities and entertainment",
                "event_topics": ["animals_internet_culture", "celebrity_entertainment"],
                "selection_role": "baseline_round_robin",
                "total_lane_count": 5,
            }
        ],
        watch_accounts=[
            {
                "platform": "x", "handle": "otter", "entity_id": "otter_daily",
                "priority": 4, "watch_cadence": "normal", "selection_role": "exploration",
                "learning_basis": "baseline", "learning_multiplier": 1.0,
            }
        ],
    )
    store.finish_trend_lane_run(
        "seed-lane-run",
        status="completed",
        model="gpt-5.3-codex-spark",
        reasoning_effort="low",
        accepted_by_lane={"culture_entertainment": 1},
        observations_by_lane={"culture_entertainment": 2},
        account_results={
            ("x", "otter"): {
                "exact_source_hits": 1, "accepted_event_count": 1, "observation_count": 1,
            }
        },
        finished_at=now - timedelta(minutes=2),
    )
    store.set_kv(
        TREND_LANE_SELECTION_KEY,
        {
            "run_id": "seed-lane-run",
            "mode": "baseline_round_robin",
            "actual_schedule_changed_by_learning": False,
            "selected_lanes": [{"lane_id": "culture_entertainment"}],
        },
    )
    store.set_kv(
        TREND_WATCH_SELECTION_KEY,
        {
            "selected_at": iso(now - timedelta(minutes=3)),
            "policy": {
                "mode": "curated_plus_exploration",
                "attention_activation_available": False,
                "actual_rotation_changed_by_learning": False,
            },
            "accounts": [
                {
                    "platform": "x", "handle": "otter", "entity_id": "otter_daily",
                    "selection_role": "exploration", "learning_basis": "baseline",
                    "learning_multiplier": 1.0,
                }
            ],
            "contains_credentials": False,
        },
    )
    store.set_kv(
        REGISTRY_KEY,
        [
            {
                "name": "paused-dynamic",
                "url": "https://dynamic.example/feed.xml",
                "kind": "rss",
                "status": "paused",
                "pause_reason": "consecutive_poll_failures",
            }
        ],
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 0,
            "task": "trend_scout",
            "model": "gpt-5.3-codex-spark",
            "reasoning_effort": "low",
            "started_at": iso(now - timedelta(minutes=4)),
            "finished_at": iso(now - timedelta(minutes=3)),
            "status": "failed",
            "returncode": 1,
            "fallback": 0,
            "input_tokens": 600,
            "cached_input_tokens": 100,
            "cache_write_input_tokens": 20,
            "output_tokens": 200,
            "reasoning_output_tokens": 80,
            "total_tokens": 1000,
            "accounting_source": "codex_json",
        }
    )
    store.add_agent_attempt(
        {
            "run_id": "safe-ledger-run",
            "attempt_index": 1,
            "task": "trend_scout",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
            "started_at": iso(now - timedelta(minutes=3)),
            "finished_at": iso(now - timedelta(minutes=2)),
            "status": "valid_output",
            "returncode": 0,
            "fallback": 1,
            "input_tokens": 300,
            "cached_input_tokens": 50,
            "cache_write_input_tokens": 10,
            "output_tokens": 100,
            "reasoning_output_tokens": 40,
            "total_tokens": 500,
            "accounting_source": "codex_json",
        }
    )
    store.close()
    return event_id, token.token_id


def _start_server(config: Path, static_dir: Path, access_token_file: Path | None = None):
    server = create_server(
        config,
        "127.0.0.1",
        _free_port(),
        static_dir=static_dir,
        access_token_file=access_token_file,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def test_web_api_empty_database_is_safe_and_live_is_locked(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    health = web.health()
    overview = web.overview()
    assert health["ok"] is True
    assert health["sqlite"]["schema_complete"] is True
    assert health["live"] == {"enabled": False, "locked": True, "available": False}
    assert {key: overview["counts"][key] for key in ("observations", "events", "tokens", "decisions", "trades")} == {
        "observations": 0,
        "events": 0,
        "tokens": 0,
        "decisions": 0,
        "trades": 0,
    }
    assert overview["counts"]["open_positions"] == 0
    assert overview["account"]["equity_usd"] == 1000
    assert overview["account"]["quote_as_of"] is None
    assert overview["account"]["activity_status"] == "no_trades"
    assert overview["account"]["performance_status"] == "not_observed"
    assert overview["account"]["valuation_status"] == "cash_only"
    assert overview["account"]["equity_curve"][-1]["equity_usd"] == 1000
    assert overview["account"]["equity_curve"][-1]["persisted"] is False
    assert overview["account"]["execution_costs"]["configured_slippage_rate"] == pytest.approx(0.04)
    assert overview["account"]["execution_costs"]["configured_fee_bps"] == pytest.approx(60)
    assert overview["account"]["execution_costs"]["pump_swap_fee_bps"] == pytest.approx(125)
    activity = overview["ingestion_activity"]
    assert activity["truth_source"] == "persisted_sqlite_activity"
    assert activity["status"] == "waiting"
    assert activity["information"]["status"] == "waiting"
    assert activity["information"]["observations_60s"] == 0
    assert activity["tokens"]["status"] == "waiting"
    assert activity["tokens"]["snapshot_updates_5m"] == 0
    assert overview["learning_state"]["status"] == "not_observed"
    assert overview["learning_state"]["shadow"]["current_version_cohorts"] == 0
    assert overview["learning_state"]["token_context"]["independent_tokens"] == 0
    assert overview["learning_state"]["phase_2"]["ready"] is False
    assert overview["learning_state"]["phase_2"]["automatic_activation"] is False
    assert web.events({})["items"] == []
    assert web.tokens({})["items"] == []
    assert web.decisions({})["items"] == []
    empty_sources = web.sources()
    assert empty_sources["source_poll_learning"]["status"] == "not_observed"
    assert empty_sources["source_poll_learning"]["affects"] == "review_only_no_schedule_or_trading_effect"
    assert empty_sources["token_discovery_learning"]["status"] == "not_observed"
    assert empty_sources["token_discovery_learning"]["affects"] == "review_only_no_schedule_or_trading_effect"
    assert empty_sources["shadow_followup"]["status"] == "not_observed"
    assert empty_sources["shadow_followup"]["summary"]["cohorts"] == 0
    assert empty_sources["shadow_followup"]["horizons_minutes"] == [15, 60, 240]
    assert empty_sources["token_context_followup"]["status"] == "not_observed"
    assert empty_sources["token_context_followup"]["summary"]["assessments"] == 0
    assert empty_sources["token_context_followup"]["activation"] is False
    assert empty_sources["token_context_followup"]["affects"] == "none"
    assert empty_sources["watch_account_learning"]["status"] == "not_observed"
    assert empty_sources["watch_account_learning"]["summary"]["account_exposures"] == 0
    assert empty_sources["learning_closure"]["status"] == "not_observed"
    assert empty_sources["learning_closure"]["breakpoint"] == "browser_exposure"
    assert [item["count"] for item in empty_sources["learning_closure"]["stages"]] == [0, 0, 0, 0, 0]
    assert empty_sources["learning_closure"]["conversion_rates_available"] is False
    assert empty_sources["watch_attention_policy"]["version"] == "watch-attention/v3-experiment-gated"
    assert empty_sources["watch_attention_policy"]["status"] == "not_configured"
    assert empty_sources["watch_attention_policy"]["items"] == []
    assert empty_sources["attention_experiment"]["status"] == "not_registered"
    assert empty_sources["attention_experiment"]["actual_multiplier"] == 1.0
    assert empty_sources["attention_experiment"]["automatic_promotion"] is False
    audit = web.audit()
    assert audit["status"] == "policy_only"
    assert audit["policy_enforced"] is True
    assert audit["future_data_rejected"] is None
    assert all(item["status"] != "pass" for item in audit["cases"])


def test_web_paper_curve_costs_attempts_and_stale_valuation_are_truthful(tmp_path: Path):
    config_path, config = _config(tmp_path)
    config["paper"]["max_quote_age_seconds"] = 1
    config_path.write_text(json.dumps(config), encoding="utf-8")
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(chain="solana", address="P" * 32, name="Paper Cost")
    store.upsert_token(token, seen_at=now - timedelta(seconds=3))
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=10, liquidity_usd=50_000,
            market_cap_usd=500_000, volume_5m_usd=10_000, buys_5m=20, sells_5m=5,
            observed_at=now - timedelta(seconds=3), provider="test-dex",
        )
    )
    store.record_paper_account_snapshot(
        cash_usd=1000, marked_value_usd=0, equity_usd=1000, daily_exposure_usd=0,
        open_position_count=0, priced_position_count=0,
        observed_at=now - timedelta(seconds=4),
    )
    store.paper_buy(
        event_id=1, token=token, price=10.2, quote_price=10, gross_usd=100,
        fee_bps=60, tax_pct=2, reason="web-cost-test",
        quote_observed_at=now - timedelta(seconds=3), quote_provider="test-dex",
        execution_attempted_at=now - timedelta(seconds=2),
    )
    store.record_paper_execution_attempt(
        event_id=1, token_id=token.token_id, side="BUY", status="filled",
        reason="web-cost-test", requested_at=now - timedelta(seconds=2),
        quote_observed_at=now - timedelta(seconds=3), quote_provider="test-dex",
        quote_price=10, execution_price=10.2, gross_usd=100,
    )
    store.record_paper_account_snapshot(
        cash_usd=899.4, marked_value_usd=98, equity_usd=997.4,
        daily_exposure_usd=100, open_position_count=1, priced_position_count=1,
        quote_as_of=now - timedelta(seconds=3), observed_at=now - timedelta(seconds=2),
    )
    store.close()

    portfolio = WebData(config_path).portfolio({})
    assert len(portfolio["account"]["equity_curve"]) == 3
    assert portfolio["account"]["equity_usd"] is None
    assert portfolio["account"]["valuation_status"] == "incomplete"
    assert portfolio["positions"][0]["quote_stale"] is True
    trade = portfolio["trades"][0]
    assert trade["quote_price"] == pytest.approx(10)
    assert trade["execution_price"] == pytest.approx(10.2)
    assert trade["fee_usd"] == pytest.approx(0.6)
    assert trade["slippage_rate"] == pytest.approx(0.02)
    assert trade["tax_usd"] == pytest.approx(2)
    costs = portfolio["account"]["execution_costs"]
    assert costs["total_fee_usd"] == pytest.approx(0.6)
    assert costs["total_recorded_tax_usd"] == pytest.approx(2)
    assert costs["route_and_chain_fees_modeled"] is False
    assert portfolio["execution_attempts"][0]["status"] == "filled"


def test_web_sources_exposes_masked_source_poll_learning(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    attempt_id = store.start_source_poll_attempt(
        collector_kind="reverse_news",
        source_key="reverse-news:0123456789abcdef",
        platform="rss_news",
    )
    store.finish_source_poll_attempt(
        attempt_id,
        status="completed",
        fetched_count=4,
        new_observation_count=1,
        decision_eligible_count=1,
        filtered_count=3,
    )
    store.close()

    payload = WebData(config_path).sources()["source_poll_learning"]
    assert payload["status"] == "collecting"
    assert payload["summary"]["completed"] == 1
    assert payload["items"][0]["source_key"] == "reverse-news:0123456789abcdef"
    serialized = json.dumps(payload).lower()
    assert "password" not in serialized and "private_key" not in serialized
    assert "https://" not in serialized and "?q=" not in serialized


def test_web_sources_exposes_forward_token_discovery_without_sensitive_fields(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    round_id = store.start_token_discovery_round(
        provider="dexscreener", surface="token_profiles", mode="poll", chain_scope="solana",
    )
    store.add_token_discovery_exposure(
        round_id, token_id=f"solana:{'T' * 32}", chain="solana", role="identity",
        first_local_discovery=True, source_link_count=2, new_source_link_count=1,
    )
    store.finish_token_discovery_round(
        round_id, status="completed", requested_count=1, returned_count=2,
    )
    store.close()

    payload = WebData(config_path).sources()["token_discovery_learning"]
    assert payload["status"] == "collecting"
    assert payload["summary"]["completed"] == 1
    assert payload["summary"]["first_local_discovery_count"] == 1
    assert payload["items"][0]["surface"] == "token_profiles"
    serialized = json.dumps(payload).lower()
    assert "password" not in serialized and "private_key" not in serialized
    assert "bridge_token" not in serialized and "https://" not in serialized


def test_learning_closure_does_not_borrow_same_event_outcomes_from_other_source(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    decision_at = utcnow() - timedelta(hours=2)
    event_id = store.create_event("Shared event with independent sources", ["shared event"], 70, decision_at)
    browser = Observation(
        source="browser:x:example", source_kind="social", title="Exact public account post",
        url="https://x.com/example/status/1", author="@example", observed_at=decision_at,
        ingested_at=decision_at, availability_proof="local_receive", role="feature",
        source_item_id="x:example:1", raw={"source_entity_id": "example_media"},
    )
    other = Observation(
        source="independent-news", source_kind="news", title="Independent report of shared event",
        url="https://news.example/shared", observed_at=decision_at, ingested_at=decision_at,
        role="feature", source_item_id="news:shared:1",
    )
    browser_id, _ = store.add_observation(browser)
    other_id, _ = store.add_observation(other)
    store.link_event_observation(event_id, browser_id)
    store.link_event_observation(event_id, other_id)
    token = TokenCandidate(chain="solana", address="Z" * 32, name="Shared Event Token")
    store.upsert_token(token, seen_at=decision_at)
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.0, liquidity_usd=50000,
            market_cap_usd=100000, volume_5m_usd=10000, buys_5m=20, sells_5m=5,
            observed_at=decision_at, provider="test",
        )
    )
    decision = CandidateDecision(
        event_id=event_id, token_id=token.token_id, action="WAIT", score=60,
        match_score=80, canonical_margin=2, reasons=["test"], created_at=decision_at,
    )
    decision_id = store.add_decision(decision)
    store.create_shadow_event_cohort(
        decision, decision_id=decision_id, source_observation_ids=[other_id]
    )
    store.add_snapshot(
        TokenSnapshot(
            chain="solana", address=token.address, price_usd=1.1, liquidity_usd=50000,
            market_cap_usd=110000, volume_5m_usd=12000, buys_5m=22, sells_5m=6,
            observed_at=decision_at + timedelta(minutes=61), provider="test",
        )
    )
    store.finalize_shadow_event_outcomes(now=decision_at + timedelta(minutes=65))
    store.db.execute(
        """
        INSERT INTO source_utility_outcomes(
            outcome_key,event_id,token_id,source_observation_id,dimension,value,origin_platform,
            attribution_weight,net_return,opened_at,closed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "other-source-only", event_id, token.token_id, other_id, "source",
            "independent-news", "web", 1.0, 0.1, iso(decision_at), iso(decision_at + timedelta(minutes=65)),
        ),
    )
    store.record_browser_watch_observation(
        {"platform": "x", "handle": "@example", "entity_id": "example_media", "priority": 3},
        observation_id=browser_id, event_id=event_id, observed_at=decision_at,
        decision_eligible=True,
    )
    store.close()

    closure = WebData(config_path).sources()["learning_closure"]
    assert [item["count"] for item in closure["stages"]] == [1, 1, 1, 0, 0]
    assert closure["breakpoint"] == "observed_60m"


def test_web_exposes_forward_admission_reasons_and_keeps_legacy_candidate_uninstrumented(
    tmp_path: Path,
):
    config_path, _ = _config(tmp_path)
    store = Store(tmp_path / "db.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    token = TokenCandidate(chain="solana", address="L" * 32, name="Ledger", symbol="LDG")
    store.upsert_token(token, seen_at=now)
    store.add_token_context_admission_attempt(
        token.token_id,
        outcome="skipped",
        reason="daily_call_limit_reached",
        trigger={"kind": "onchain_momentum", "priority": 1},
        snapshot_observed_at=now,
        momentum_score=88,
        quota_day=now.date().isoformat(),
        daily_call_limit=8,
        calls_used_before=8,
        daily_token_budget=250000,
        tokens_used_before=12000,
        token_reserve_per_call=18000,
        evaluated_at=now,
    )
    event_id = store.create_event("Legacy candidate", ["legacy candidate"], 70, now)
    store.add_decision(
        CandidateDecision(
            event_id, token.token_id, "CANDIDATE", 82, 91, 10, ["legacy"], created_at=now
        )
    )
    store.close()

    web = WebData(config_path)
    sources = web.sources()
    context = sources["token_context_admissions"]
    assert context["summary"]["attempts"] == 1
    assert context["summary"]["admitted"] == 0
    assert context["items"][0]["reason"] == "daily_call_limit_reached"
    shadow = sources["shadow_followup"]["admission"]["summary"]
    assert shadow["candidate_decisions"] == 1
    assert shadow["candidate_instrumented"] == 0
    assert shadow["candidate_legacy_or_uninstrumented"] == 1
    assert shadow["forward_candidate_coverage_rate"] is None
    detail = web.token_detail(token.token_id)
    assert detail["context_admission"]["reason"] == "daily_call_limit_reached"
    assert "password" not in json.dumps(context).lower()


def test_web_api_exposes_real_evidence_wait_portfolio_agents_and_sources(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, token_id = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    store.set_kv(
        "browser_platform_heartbeat:x",
        {
            "platform": "x",
            "visible": True,
            "selector_count": 7,
            "page_url": "https://x.com/i/lists/1",
            "access_state": "authenticated",
            "observed_at": iso(),
            "contains_credentials": False,
        },
    )
    browser_observation = store.db.execute(
        "SELECT id FROM observations WHERE source='browser:x:otter'"
    ).fetchone()
    store.record_browser_watch_observation(
        {
            "platform": "x", "handle": "otter", "entity_id": "otter_daily",
            "priority": 2, "watch_cadence": "normal",
        },
        observation_id=browser_observation["id"],
        event_id=event_id,
        observed_at=iso(),
        decision_eligible=False,
    )
    store.close()
    console_dir = tmp_path / "data" / "web_console"
    console_dir.mkdir(parents=True)
    (console_dir / "console_settings.json").write_text(
        json.dumps(
            {
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "otter",
                        "display_name": "Otter",
                        "url": "https://x.com/otter",
                        "enabled": True,
                        "priority": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    web = WebData(config_path)

    activity = web.overview()["ingestion_activity"]
    assert activity["status"] == "active"
    assert activity["information"]["status"] == "active"
    assert activity["information"]["observations_60s"] == 4
    assert activity["information"]["rate_per_minute_5m"] == pytest.approx(0.8)
    assert activity["tokens"]["status"] == "active"
    assert activity["tokens"]["new_tokens_60s"] == 1
    assert activity["tokens"]["snapshot_updates_60s"] == 1
    assert activity["tokens"]["rate_per_minute_5m"] == pytest.approx(0.4)

    events = web.events({"limit": ["10"]})["items"]
    event_summary = next(item for item in events if item["id"] == event_id)
    assert "observations" not in event_summary
    assert "x" * 600 not in json.dumps(event_summary)
    event = web.event_detail(event_id)
    roles = {item["role"]: item for item in event["observations"]}
    assert event["event_url"] == f"#/events/{event_id}"
    assert event["evidence_ranking"]["method"] == "decision_utility_authority_freshness"
    assert [item["priority_rank"] for item in event["observations"]] == [1, 2, 3, 4]
    assert all(0 <= item["priority_score"] <= 100 for item in event["observations"])
    assert all(item["ranking_method"] == "decision_utility_authority_freshness" for item in event["observations"])
    assert event["source_count"] == 4
    assert event["total_source_count"] == 4
    assert event["eligible_source_count"] == 1
    assert event["eligible_latest_at"] is not None
    assert event["freshness_minutes"] is not None
    feature = next(item for item in event["observations"] if item["source"] == "news-a")
    identity = next(item for item in event["observations"] if item["source"] == "browser:x:otter")
    assert feature["decision_eligible"] is True
    assert len(feature["text"]) == 600 and feature["text_truncated"] is True
    assert feature["platform"] == {"id": "web", "label": "news-a.example", "inferred": True}
    assert feature["author"] == "Otter Daily" and feature["author_known"] is True
    assert feature["influence"]["account_type"] == "publisher"
    assert feature["influence"]["account_type_inferred"] is False
    assert feature["influence"]["authority_tier"] == "established"
    assert feature["influence"]["verified"] is True
    assert feature["influence"]["follower_count"] is None
    assert feature["influence"]["visible_engagement"] == {"view_count": 125000, "like_count": 8500}
    assert feature["metadata"]["trend_lane_id"] == "culture_entertainment"
    assert feature["metadata"]["trend_lane_run_id"] == "seed-lane-run"
    assert feature["metadata"]["trend_lane_taxonomy"] == "trend-lanes/v1"
    assert feature["source_group"] == "original_feature"
    assert event["lead_source"]["id"] == feature["id"]
    assert identity["platform"]["id"] == "x" and identity["author"] == "otter"
    assert identity["source_entity_id"] == "otter_daily"
    assert identity["cross_platform_entity"] == {
        "id": "otter_daily",
        "origin": "entity:otter_daily",
        "deduplication": "explicit_persisted_entity_only",
    }
    assert identity["origin"] == "entity:otter_daily"
    assert "bridge_token" not in identity["metadata"]
    assert identity["influence"]["authority_tier"] == "unknown"
    assert identity["influence"]["account_type_inferred"] is True
    assert identity["influence"]["verified"] is None
    assert identity["influence"]["follower_count"] is None
    assert identity["influence"]["curated_watch"] == {
        "configured": True,
        "priority": 2,
        "tier": "community_trend",
        "display_name": "Otter",
    }
    assert identity["decision_eligible"] is False
    assert identity["ranking_dimensions"]["curated_watch_priority"] == 2
    assert roles["identity"]["original_role"] in {"confirmation", "feature"}
    assert roles["promotion"]["decision_eligible"] is False
    assert "non_decision_role" in roles["promotion"]["rejection_reasons"]
    future = next(item for item in event["observations"] if item["source"] == "future-clock")
    assert future["freshness"] == "future"
    assert future["decision_eligible"] is False
    assert future["author"] is None and future["author_known"] is False
    assert future["source_group"] == "identity_promotion_context"
    assert {"published_at", "observed_at", "ingested_at"}.issubset(future)
    detail = event
    assert detail["ranking_available"] is False
    assert detail["candidate_ranking"] is None
    assert detail["ranking_persistence_gap"] == "candidate_ranking_not_available_for_this_event"
    assert detail["ranked_sources"] == event["observations"]
    assert [group["id"] for group in detail["source_groups"]] == [
        "original_feature", "identity_promotion_context"
    ]
    context_sources = next(
        group["items"] for group in detail["source_groups"] if group["id"] == "identity_promotion_context"
    )
    assert {item["role"] for item in context_sources} == {"identity", "promotion"}
    assert all(item["decision_eligible"] is False for item in context_sources)
    assert [item["observed_at"] for item in detail["evidence_timeline"]] == sorted(
        item["observed_at"] for item in detail["evidence_timeline"]
    )
    assert {item["source"] for item in detail["evidence_timeline"]} == {
        "news-a", "browser:x:otter", "promotion-list", "future-clock"
    }

    token = web.token_detail(token_id)
    assert token["snapshot"]["momentum"] > 0
    assert token["snapshot"]["buys_5m"] == 30
    assert token["linked_event_ids"] == [event_id]
    assert token["evidence_record_count"] == token["evidence_count"] == 1
    assert max(len(item["text"]) for item in token["evidence"]) <= 600
    assert {item["role"] for item in token["attached_links"]} == {"identity", "promotion"}
    assert all(item["decision_eligible"] is False for item in token["attached_links"])
    assert all(item["verification_status"] == "provider_metadata" for item in token["attached_links"])
    assert token["detail_hydration"]["status"] == "pending"
    assert token["context_assessment"]["status"] == "insufficient_verified_sources"
    assert token["context_assessment"]["context_only"] is True
    assert token["context_assessment"]["assessment"]["decision_eligible"] is False
    assert token["context_assessment"]["assessment"]["public_figure_linkage"]["endorsement_inferred"] is False
    assert token["context_assessment"]["agent"]["model"] == "gpt-5.6-luna"
    context_tracking = token["context_assessment"]["outcome_tracking"]
    assert context_tracking["status"] == "pending"
    assert [item["status"] for item in context_tracking["horizons"]] == [
        "pending", "pending", "pending"
    ]
    assert context_tracking["decision_eligible"] is False
    assert context_tracking["endorsement_inferred"] is False
    assert context_tracking["affects"] == "none"
    token_list = web.tokens({})
    coverage = token_list["detail_coverage"]
    assert coverage.pop("tracking_started_at") is not None
    assert coverage == {
        "eligible_solana_tokens": 1,
        "hydrated": 0,
        "pending": 1,
        "no_pair": 0,
        "error": 0,
        "social_links_found": 1,
        "coverage_ratio": 0.0,
    }
    serialized_token = json.dumps(token)
    assert "raw_json" not in serialized_token
    assert "must_not_be_returned" not in serialized_token
    decision_payload = web.decisions({})
    assert decision_payload["ranking_available"] is False
    assert decision_payload["ranking_coverage"] == {"available": 0, "unavailable": 1}
    decision = decision_payload["items"][0]
    assert decision["action"] == "WAIT" and decision["is_wait"] is True
    assert decision["ranking_available"] is False and decision["candidate_ranking"] is None
    assert decision["rejected_reasons"] == ["canonical_token_ambiguous"]
    assert decision["position_usd"] == 0
    safety = {item["name"]: item for item in decision["safety_checks"]["checks"]}
    assert decision["safety_checks"]["basis"] == "persisted_snapshot_at_or_before_decision"
    assert decision["safety_checks"]["snapshot_observed_at"] is not None
    assert safety["liquidity_usd"]["value"] == 50_000
    assert safety["liquidity_usd"]["state"] == "pass"
    assert safety["transactions_5m"]["value"] == 40
    assert safety["buy_ratio_5m"]["value"] == pytest.approx(0.75)
    assert safety["honeypot"]["state"] == "unknown"
    assert safety["sellable"]["state"] == "unknown"
    assert safety["buy_tax_pct"]["state"] == "unknown"
    assert safety["sell_tax_pct"]["state"] == "unknown"
    assert safety["risk_score"]["state"] == "unknown"

    portfolio = web.portfolio({})
    assert portfolio["simulated"] is True
    assert portfolio["positions"][0]["current_price"] == pytest.approx(0.01)
    assert portfolio["positions"][0]["quote_as_of"] is not None
    assert portfolio["positions"][0]["take_profit_index"] == 0
    assert portfolio["positions"][0]["take_profit_total"] == 4
    assert portfolio["positions"][0]["take_profit_next"] == {
        "return_pct": 0.5,
        "sell_fraction": 0.2,
    }
    assert portfolio["positions"][0]["narrative_age_minutes"] is not None
    assert portfolio["positions"][0]["narrative_stale"] is False
    assert portfolio["trades"][0]["simulated"] is True
    assert portfolio["account"]["equity_usd"] is not None

    agents = web.agents()
    scout = next(item for item in agents["operations"] if item["kind"] == "trend_scout")
    assert agents["provider"] == "Local Codex CLI"
    assert agents["credential_mode"] == "signed_in_local_session"
    assert agents["uses_api_key"] is False
    assert scout["calls"] == 3 and scout["tokens"] == 12345
    assert scout["next_run_at"] is not None and scout["fallback_used"] is True
    assert agents["usage_summary"]["today"] == {
        "calls": 1,
        "attempts": 2,
        "fallback_attempts": 1,
        "input_tokens": 900,
        "cached_input_tokens": 150,
        "cache_write_input_tokens": 30,
        "output_tokens": 300,
        "reasoning_output_tokens": 120,
        "total_tokens": 1500,
        "known_usage_attempts": 2,
        "unknown_usage_attempts": 0,
        "coverage_pct": 100.0,
        "valid_structured_attempts": 1,
        "invalid_structured_attempts": 0,
        "structured_pass_rate_pct": 100.0,
        "legacy_unattributed_total_tokens": 10845,
    }
    breakdown = agents["usage_breakdown"]["today"]
    assert {(item["model"], item["reasoning_effort"], item["total_tokens"]) for item in breakdown} == {
        ("gpt-5.3-codex-spark", "low", 1000),
        ("gpt-5.6-luna", "medium", 500),
    }
    spark_quality = next(item for item in breakdown if item["model"] == "gpt-5.3-codex-spark")
    luna_quality = next(item for item in breakdown if item["model"] == "gpt-5.6-luna")
    assert spark_quality["structured_pass_rate_pct"] is None
    assert luna_quality["structured_pass_rate_pct"] == 100.0
    assert [(item["attempt_index"], item["fallback"]) for item in agents["recent_attempts"]] == [
        (1, True), (0, False)
    ]
    assert "prompt" not in json.dumps(agents["recent_attempts"])

    sources = web.sources()["items"]
    static = next(item for item in sources if item["name"] == "example-news")
    paused = next(item for item in sources if item["name"] == "paused-dynamic")
    assert static["last_ok_at"] is not None and static["last_item_at"] is not None
    assert paused["status"] == "paused"
    assert paused["pause_reason"] == "consecutive_poll_failures"
    source_payload = web.sources()
    source_names = {item["name"] for item in source_payload["items"]}
    assert "dexscreener-discovery" not in source_names
    assert "dexscreener:token_profiles" in source_names
    assert source_payload["learning"]["status"] == "collecting_samples"
    assert source_payload["learning"]["summary"]["observations"] >= 4
    assert source_payload["learning"]["summary"]["closed_paper_outcomes"] == 0
    assert source_payload["learning"]["summary"]["decision_support_outcomes"] == 0
    assert source_payload["learning"]["summary"]["active_labels"] == 0
    assert source_payload["learning"]["activation_policy"]["rotation_basis"] == "discovery_lead"
    assert source_payload["learning"]["activation_policy"]["decision_support_affects"] == "descriptive_only"
    assert source_payload["trend_lanes"]["status"] == "collecting_exposure"
    assert source_payload["trend_lanes"]["actual_schedule_changed_by_learning"] is False
    assert source_payload["trend_attention_policy"]["version"] == "trend-attention/v2-experiment-gated"
    assert source_payload["trend_attention_policy"]["summary"]["actual_schedule_changed_by_learning"] is False
    policy_lane = next(
        item for item in source_payload["trend_attention_policy"]["items"]
        if item["lane_id"] == "culture_entertainment"
    )
    assert policy_lane["selected_in_last_run"] is True
    assert "recommended_multiplier" in policy_lane and "applied_schedule_multiplier" in policy_lane
    assert len(source_payload["trend_lanes"]["items"]) == 5
    culture_lane = next(
        item for item in source_payload["trend_lanes"]["items"]
        if item["lane_id"] == "culture_entertainment"
    )
    assert culture_lane["selected_in_last_run"] is True
    assert culture_lane["completed_exposures"] == 1
    assert culture_lane["accepted_events"] == 1
    assert culture_lane["accepted_events_per_completed_run"] == 1.0
    assert culture_lane["shadow_mature"] is False
    assert source_payload["watch_account_learning"]["status"] == "collecting_exposure"
    assert source_payload["watch_account_learning"]["summary"]["account_exposures"] == 2
    assert source_payload["watch_account_learning"]["summary"]["exact_source_hits"] == 2
    account_exposure = source_payload["watch_account_learning"]["items"][0]
    assert account_exposure["platform"] == "x" and account_exposure["handle"] == "otter"
    assert account_exposure["completed_exposures"] == 2
    assert account_exposure["browser_bridge_exposures"] == 1
    assert account_exposure["trend_agent_exposures"] == 1
    assert account_exposure["rotation_active"] is False
    assert [item["count"] for item in source_payload["learning_closure"]["stages"]] == [1, 1, 0, 0, 0]
    assert source_payload["learning_closure"]["breakpoint"] == "eligible_event"
    assert source_payload["watch_attention_policy"]["version"] == "watch-attention/v3-experiment-gated"
    assert source_payload["watch_attention_policy"]["status"] == "collecting_evidence"
    assert source_payload["watch_attention_policy"]["summary"][
        "rotation_activation_available"
    ] is False
    assert source_payload["watch_attention_policy"]["summary"][
        "actual_rotation_changed_by_learning"
    ] is False
    attention_item = source_payload["watch_attention_policy"]["items"][0]
    assert attention_item["platform"] == "x" and attention_item["handle"] == "otter"
    assert attention_item["state"] == "collecting_account_exposure"
    assert attention_item["applied_rotation_multiplier"] == 1.0
    assert attention_item["rotation_active"] is False
    assert attention_item["selected_in_last_run"] is True
    assert attention_item["last_selection_role"] == "exploration"
    assert source_payload["watch_attention_policy"]["activation_policy"]["never_affects"] == [
        "evidence_weight", "candidate_ranking", "decision_eligibility",
        "risk", "position_size", "exits", "live_trading",
    ]
    assert source_payload["shadow_followup"]["status"] == "collecting_followup"
    assert source_payload["shadow_followup"]["version"] == "shadow-event-followup/v3-strategy-labels"
    assert source_payload["shadow_followup"]["horizons_minutes"] == [15, 60, 240]
    assert source_payload["shadow_followup"]["summary"]["cohorts"] == 1
    assert source_payload["shadow_followup"]["summary"]["pending_cohorts"] == 1
    assert source_payload["shadow_followup"]["summary"]["reject_cohorts"] == 0
    assert source_payload["shadow_followup"]["summary"]["entry_execution"] == {
        "attempts": 0, "filled": 0, "rejected": 0, "cohort_linked": 0, "unlinked": 0,
    }
    assert source_payload["shadow_followup"]["items"] == []
    assert source_payload["token_context_followup"]["status"] == "collecting_followup"
    assert source_payload["token_context_followup"]["summary"]["assessments"] == 1
    assert source_payload["token_context_followup"]["summary"]["tracked_cohorts"] == 1
    assert source_payload["token_context_followup"]["summary"]["pending_cohorts"] == 1
    assert source_payload["token_context_followup"]["activation"] is False
    assert source_payload["token_context_followup"]["actual_schedule_changed_by_learning"] is False
    assert source_payload["token_context_followup"]["decision_eligible"] is False
    assert source_payload["token_context_followup"]["affects"] == "none"
    assert len(source_payload["platforms"]) == 9
    x_status = next(item for item in source_payload["platforms"] if item["platform"] == "x")
    assert x_status["access_state"] == "authenticated"
    assert x_status["login_recommended"] is True
    assert x_status["contains_credentials"] is False
    assert source_payload["credentials_policy"] == {
        "contains_credentials": False,
        "accepts_passwords": False,
        "accepts_cookies": False,
        "accepts_sessions": False,
    }

    audit = web.audit()
    assert audit["status"] == "partial_evidence"
    assert audit["future_data_rejected"] is True
    assert audit["observed_future_rejection_count"] == 1
    audit_cases = {item["id"]: item for item in audit["cases"]}
    assert audit_cases["r5-false-positive"]["status"] == "policy_enforced"
    assert audit_cases["r5-false-positive"]["observed_case_evidence"] is False
    assert audit_cases["r6-starlink-stale-reverse-evidence"]["status"] == "not_observed"
    assert audit_cases["future-data-rejection"]["status"] == "observed_pass"
    assert audit_cases["future-data-rejection"]["observed_case_evidence"] is True
    audit_evidence = audit["recent_decision_evidence"][0]["evidence"]
    stale_identity = next(item for item in audit_evidence if item["source"] == "browser:x:otter")
    assert stale_identity["original_role"] == "confirmation"
    assert stale_identity["rejection_reasons"]
    assert {"published_at", "observed_at", "ingested_at"}.issubset(stale_identity)


def test_candidate_ranking_api_is_persisted_bounded_sanitized_and_wait_is_truthful(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    event_id, token_id = _seed(tmp_path / "db.sqlite3")
    store = Store(tmp_path / "db.sqlite3")
    row = store.decisions(1)[0]
    hidden = "must-never-leak-from-ranking"
    store.set_candidate_ranking(
        event_id,
        {
            "version": 1,
            "evaluated_at": row["created_at"],
            "status": "completed",
            "outcome": "WAIT",
            "outcome_reasons": ["canonical_token_ambiguous"],
            "ranking_method": "candidate_score_desc_then_bounded_semantic_tiebreak",
            "candidate_count_total": 2,
            "candidate_count_persisted": 2,
            "candidates_truncated": False,
            "tie_break": {
                "used": False,
                "tier": None,
                "confidence": None,
                "preferred_token_id": None,
                "prompt": hidden,
            },
            "candidates": [
                {
                    "rank": 1,
                    "token_id": token_id,
                    "chain": "solana",
                    "address": "A" * 32,
                    "name": "Viral Otter",
                    "symbol": "OTTER",
                    "candidate_score": 65,
                    "match_score": 88,
                    "canonical_margin": 2,
                    "raw_canonical_margin": 2,
                    "score_gap_to_selected": 0,
                    "score_gap_to_score_leader": 0,
                    "score_gap_to_next_rank": 2,
                    "selection_status": "selected_for_final_decision",
                    "action": "WAIT",
                    "position_usd": 0,
                    "reasons": ["match=88.0"],
                    "rejected_reasons": ["canonical_token_ambiguous"],
                    "snapshot": {
                        "observed_at": row["created_at"],
                        "provider": "dexscreener",
                        "price_usd": 0.01,
                        "liquidity_usd": 50_000,
                        "volume_5m_usd": 12_000,
                        "buys_5m": 30,
                        "sells_5m": 10,
                        "security_reports": ["rugcheck"],
                        "raw_json": {"private_key": hidden},
                    },
                    "safety": {"status": "not_checked", "rejected_reasons": []},
                    "tie_break": {"pre_agent_rank": 1, "rank_changed": False, "preferred": False},
                    "private_key": hidden,
                },
                {
                    "rank": 2,
                    "token_id": "solana:" + "B" * 32,
                    "chain": "solana",
                    "address": "B" * 32,
                    "name": "Otter Copy",
                    "symbol": "OTTR",
                    "candidate_score": 63,
                    "match_score": 75,
                    "score_gap_to_selected": 2,
                    "score_gap_to_score_leader": 2,
                    "selection_status": "not_selected_lower_rank",
                    "action": "NOT_SELECTED",
                    "position_usd": 0,
                    "reasons": ["ranked below selected candidate"],
                    "rejected_reasons": [],
                    "snapshot": {"observed_at": row["created_at"], "provider": "dexscreener"},
                    "safety": {"status": "not_checked", "rejected_reasons": []},
                    "tie_break": {"pre_agent_rank": 2, "rank_changed": False, "preferred": False},
                },
            ],
            "final_outcome": {"decision_id": None, "action": "WAIT", "prompt": hidden},
            "bridge_token": hidden,
        },
    )
    pending_ranking = WebData(config_path).event_detail(event_id)["candidate_ranking"]
    assert pending_ranking["status"] == "pending_runtime"
    assert pending_ranking["outcome"] == "UNAVAILABLE"
    assert pending_ranking["final_outcome"] is None
    assert pending_ranking["candidates"][0]["action"] == "PENDING_RUNTIME"
    assert pending_ranking["candidates"][0]["position_usd"] == 0
    decision = CandidateDecision(
        event_id=event_id,
        token_id=token_id,
        action="WAIT",
        score=65,
        match_score=88,
        canonical_margin=2,
        reasons=["match=88.0"],
        rejected_reasons=["canonical_token_ambiguous"],
        created_at=row["created_at"],
    )
    store.finalize_candidate_ranking(event_id, decision, decision_id=int(row["id"]))
    store.close()

    web = WebData(config_path)
    payload = web.decisions({})
    assert payload["ranking_available"] is True
    assert payload["ranking_coverage"] == {"available": 1, "unavailable": 0}
    item = payload["items"][0]
    assert item["action"] == "WAIT" and item["ranking_available"] is True
    assert item["rank"] == 1
    ranking = item["candidate_ranking"]
    assert ranking["outcome"] == "WAIT"
    assert ranking["final_outcome"]["action"] == "WAIT"
    assert [candidate["rank"] for candidate in ranking["candidates"]] == [1, 2]
    assert ranking["candidates"][0]["action"] == "WAIT"
    assert ranking["candidates"][1]["action"] == "NOT_SELECTED"
    assert ranking["candidates"][0]["safety"]["status"] == "not_checked"
    assert ranking["candidates"][0]["snapshot"]["security_reports"] == ["rugcheck"]
    assert hidden not in json.dumps(payload)
    assert "raw_json" not in json.dumps(payload)
    detail = web.event_detail(event_id)
    assert detail["ranking_available"] is True
    assert detail["candidate_ranking"]["final_outcome"]["decision_id"] == int(row["id"])
    assert set(detail["related_token_ids"]) == {token_id, "solana:" + "B" * 32}

    app = (Path(__file__).parents[1] / "src" / "memetrader" / "web_static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "data-testid='candidate-ranking'" in app
    assert "WAIT｜未形成交易信号" in app
    assert "未选中" in app and "NOT SELECTED" in app
    assert "WAIT is never decorated as an opportunity" in app
    assert "data-testid='source-learning'" in app
    assert "data-testid='watch-account-exposure'" in app
    assert "data-testid='trend-attention-policy'" in app
    assert "data-testid='attention-experiment'" in app
    assert "data-testid='token-context-followup'" in app
    assert "Token-context forward follow-through: learn what merits more research" in app
    assert "Trend-lane statistics are descriptive and cannot change scheduling on their own" in app
    assert "Account correlations create hypotheses; only a preregistered randomized experiment may alter a watch slot" in app
    assert "Preregistered randomized attention experiment: one normal watch slot only" in app
    assert "Paper source outcomes require an exact final-decision → admitted-cohort → fill → close chain" in app
    assert "Forward learning state" in app
    assert "COLLECTING · NOTHING MATURE" in app
    assert "later WAIT / REJECT / CANDIDATE actions from the same event cannot inflate" in app
    assert "Evidence roles F / C / I / P" in app
    assert "event_topic" in app and "observe only" in app
    assert "Linked narrative / event observation timeline" in app
    assert "Verified narrative / event evidence timeline" not in app
    assert "data-testid='paper-account-curve'" in app
    assert "data-testid='paper-execution-attempts'" in app
    assert "no future price was filled in" in app
    assert "no fake fills are generated" in app


def test_settings_are_allowlisted_atomic_and_never_expose_secrets(tmp_path: Path):
    config_path, config = _config(tmp_path)
    Store(tmp_path / "db.sqlite3", initial_cash_usd=1000).close()
    web = WebData(config_path)

    serialized = json.dumps(
        {
            "settings": web.settings(),
            "health": web.health(),
            "agents": web.agents(),
            "sources": web.sources(),
        }
    )
    assert config["bridge"]["token"] not in serialized
    assert config["notifications"]["telegram_bot_token"] not in serialized
    assert "telegram_chat_id" not in serialized
    settings = web.settings()
    assert settings["values"] == settings["editable"]
    assert settings["schema"]["fields"]
    poll_schema = next(item for item in settings["schema"]["fields"] if item["path"] == "poll_seconds")
    assert poll_schema["current"] == settings["editable"]["poll_seconds"]
    assert poll_schema["default"] is not None
    assert poll_schema["unit"] == "seconds"
    assert poll_schema["restart_required"] is True
    dex_interval = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "sources.dexscreener_discovery.interval_seconds"
    )
    dex_hydration = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "sources.dexscreener_discovery.max_hydrations_per_cycle"
    )
    assert (dex_interval["min"], dex_interval["max"]) == (30, 3600)
    assert (dex_hydration["min"], dex_hydration["max"]) == (0, 300)
    learning_fraction = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.source_learning_exploration_fraction"
    )
    direct_context = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.context_direct_trigger_enabled"
    )
    direct_attention = next(
        item for item in settings["schema"]["fields"]
        if item["path"] == "autonomous_search.context_direct_event_min_attention"
    )
    assert learning_fraction["min"] == 0.4
    assert direct_context["type"] == "boolean"
    assert (direct_attention["min"], direct_attention["max"]) == (0, 100)
    assert settings["live_locked"] is True
    telegram_option = next(
        item
        for item in settings["schema"]["collection_preferences"]["platform_options"]
        if item["value"] == "telegram"
    )
    assert telegram_option["automation_available"] is False
    assert telegram_option["manual_directory_only"] is True

    public_access = tmp_path / "data" / "web_console" / "PUBLIC_ACCESS.txt"
    public_access.parent.mkdir(parents=True, exist_ok=True)
    public_access.write_text(
        "URL: https://example.trycloudflare.com\nUsername: memetrader\nPassword: must-stay-local\n",
        encoding="utf-8",
    )
    public_settings = web.settings()
    assert public_settings["authentication"]["public_url"] == "https://example.trycloudflare.com"
    assert "must-stay-local" not in json.dumps(public_settings)

    result = web.patch_settings(
        {
            "updates": {
                "poll_seconds": 90,
                "autonomous_search": {"max_concurrent_agents": 2},
            },
            "console": {
                "watch_accounts": [
                    {
                        "platform": "x",
                        "handle": "@example",
                        "display_name": "Example",
                        "entity_id": "example_media",
                        "url": "https://x.com/example",
                        "enabled": True,
                        "priority": 1,
                    }
                ],
                "topics": ["viral animals"],
                "platforms": [{"platform": "telegram", "enabled": True}],
            },
        }
    )
    assert result["restart_required"] is True
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["poll_seconds"] == 90
    assert saved["autonomous_search"]["max_concurrent_agents"] == 2
    assert saved["live"]["enabled"] is False
    watchlist = web.watchlist()
    assert watchlist["watch_accounts"][0]["handle"] == "@example"
    assert watchlist["watch_accounts"][0]["priority"] == 1
    assert watchlist["watch_accounts"][0]["entity_id"] == "example_media"
    assert watchlist["platforms"] == [{"platform": "telegram", "enabled": False}]
    assert watchlist["contains_credentials"] is False

    before = config_path.read_bytes()
    for unsafe_update in ({"live": {"enabled": True}}, {"mode": "live"}):
        with pytest.raises(Exception, match="locked or unsupported"):
            web.patch_settings({"updates": unsafe_update})
        assert config_path.read_bytes() == before
    with pytest.raises(Exception, match="between 1 and 2"):
        web.patch_settings({"updates": {"autonomous_search": {"max_concurrent_agents": 3}}})
    with pytest.raises(Exception, match="unsupported fields"):
        web.patch_settings(
            {
                "console": {
                    "watch_accounts": [
                        {"platform": "x", "handle": "bad", "enabled": True, "password": "must-not-save"}
                    ]
                }
            }
        )
    for bad_entity_id in ("NASA", "bad/entity", "-leading", "trailing-", "a" * 65):
        with pytest.raises(Exception, match="entity_id"):
            web.patch_settings(
                {
                    "console": {
                        "watch_accounts": [
                            {
                                "platform": "x",
                                "handle": "@example",
                                "entity_id": bad_entity_id,
                                "enabled": True,
                            }
                        ]
                    }
                }
            )
    with pytest.raises(Exception, match="at most 4"):
        web.patch_settings(
            {
                "console": {
                    "watch_accounts": [
                        {
                            "platform": "x",
                            "handle": f"critical_{index}",
                            "watch_cadence": "critical",
                            "enabled": True,
                        }
                        for index in range(5)
                    ]
                }
            }
        )
    assert "must-not-save" not in (tmp_path / "data" / "web_console" / "console_settings.json").read_text(encoding="utf-8")


def test_notifications_missing_empty_malformed_and_strict_public_whitelist(tmp_path: Path):
    config_path, config = _config(tmp_path)
    web = WebData(config_path)
    notification_path = tmp_path / "notifications.jsonl"

    missing = web.notifications({})
    assert missing["items"] == []
    assert missing["status"] == "missing"
    assert missing["latest_at"] is None
    assert missing["execution_context"] == {
        "mode": "paper",
        "simulated": True,
        "live_enabled": False,
        "live_locked": True,
    }

    notification_path.write_text("", encoding="utf-8")
    empty = web.notifications({})
    assert empty["items"] == [] and empty["status"] == "empty"

    private_value = "private-wallet-material-must-not-leak"
    bot_value = "telegram-bot-token-must-not-leak"
    records = [
        "not-json",
        json.dumps([]),
        json.dumps({"time": "not-a-time", "kind": "paper_buy", "title": "bad time"}),
        json.dumps(
            {
                "time": iso(),
                "kind": "future_kind_with_unknown_payload_contract",
                "title": "unknown kinds are not public",
                "payload": {"private_key": private_value},
            }
        ),
        json.dumps(
            {
                "time": iso(),
                "kind": "paper_buy",
                "title": "solana:public-token",
                "payload": {
                    "event_id": 7,
                    "token_id": "solana:public-token",
                    "action": "CANDIDATE",
                    "amount_usd": 12.5,
                    "score": 83,
                    "source": "example-news",
                    "private_key": private_value,
                    "telegram_bot_token": bot_value,
                    "error": "TimeoutError",
                    "detail": "C:/secret/runtime/path",
                    "unknown_nested": {"cookie": "session-must-not-leak"},
                    "usage": {"agent_prompt": "must-not-leak"},
                },
                "raw_payload": {"bridge_token": "must-not-leak"},
            }
        ),
    ]
    notification_path.write_text("\n".join(records) + "\n", encoding="utf-8")

    payload = web.notifications({})
    assert payload["status"] == "active"
    assert payload["total"] == 1
    assert payload["malformed_skipped"] == 4
    item = payload["items"][0]
    assert item["kind"] == "paper_buy"
    assert item["event_id"] == 7 and item["event_url"] == "#/events/7"
    assert item["token_id"] == "solana:public-token"
    assert item["token_url"] == "#/tokens/solana:public-token"
    assert item["source_display_name"] == "example-news"
    assert item["metrics"] == {"amount_usd": 12.5, "score": 83.0}
    assert item["simulation"] == {
        "is_simulated": True,
        "mode": "paper",
        "label": "PAPER / SIMULATED",
    }
    serialized = json.dumps(payload)
    for forbidden in (
        private_value,
        bot_value,
        "session-must-not-leak",
        "agent_prompt",
        "bridge_token",
        "raw_payload",
        "unknown_nested",
        "TimeoutError",
        "C:/secret/runtime/path",
        config["notifications"]["telegram_bot_token"],
    ):
        assert forbidden not in serialized


def test_notifications_pagination_limit_and_rotated_generation(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    web = WebData(config_path)
    notification_path = tmp_path / "notifications.jsonl"
    now = utcnow()

    def record(minutes: int, title: str) -> str:
        return json.dumps(
            {
                "time": iso(now - timedelta(minutes=minutes)),
                "kind": "event_detected",
                "title": title,
                "payload": {"event_id": minutes + 1, "attention": 70 - minutes},
            }
        )

    notification_path.write_text(record(3, "oldest") + "\n" + record(2, "middle") + "\n", encoding="utf-8")
    notification_path.replace(Path(str(notification_path) + ".1"))
    notification_path.write_text(record(1, "newest") + "\n", encoding="utf-8")

    page = web.notifications({"limit": ["1"], "offset": ["1"]})
    assert page["total"] == 3
    assert page["limit"] == 1 and page["offset"] == 1
    assert page["has_more"] is True
    assert [item["title"] for item in page["items"]] == ["middle"]
    assert page["rotated_generations_read"] == 1
    assert page["bounded_tail"] is True

    clamped = web.notifications({"limit": ["999"], "offset": ["-9"]})
    assert clamped["limit"] == 200 and clamped["offset"] == 0
    assert [item["title"] for item in clamped["items"]] == ["newest", "middle", "oldest"]


def test_http_routes_require_optional_file_token_and_serve_api(tmp_path: Path):
    config_path, config = _config(tmp_path)
    _seed(tmp_path / "db.sqlite3")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
    (static / "app.js").write_text("window.consoleReady = true;", encoding="utf-8")
    token_file = tmp_path / "web-access-token.txt"
    token_file.write_text("a-local-access-token-longer-than-24", encoding="utf-8")
    server, thread, base = _start_server(config_path, static, token_file)
    try:
        with httpx.Client(timeout=5) as client:
            assert client.get(f"{base}/api/health").status_code == 401
            headers = {"Authorization": "Bearer a-local-access-token-longer-than-24"}
            health = client.get(f"{base}/api/health", headers=headers)
            assert health.status_code == 200 and health.json()["live"]["locked"] is True
            notifications = client.get(f"{base}/api/notifications", headers=headers)
            assert notifications.status_code == 200
            assert notifications.json()["execution_context"]["live_locked"] is True
            assert client.get(f"{base}/", headers=headers).text == "<h1>console</h1>"
            asset = client.get(f"{base}/static/app.js", headers=headers)
            assert asset.status_code == 200
            assert "javascript" in asset.headers["content-type"]
            assert asset.text == "window.consoleReady = true;"
            assert client.get(f"{base}/static/missing.js", headers=headers).status_code == 404
            watchlist = client.get(f"{base}/api/watchlist", headers=headers).json()
            assert len(watchlist["platforms"]) == 9
            settings = client.get(f"{base}/api/settings", headers=headers).json()
            assert settings["authentication"]["token_file"] == token_file.name
            assert str(token_file.resolve()) not in json.dumps(settings)
            assert config["bridge"]["token"] not in json.dumps(settings)
            rejected = client.patch(
                f"{base}/api/settings",
                headers=headers,
                json={"updates": {"mode": "live"}},
            )
            assert rejected.status_code == 400
            cross_origin = client.patch(
                f"{base}/api/settings",
                headers={**headers, "Origin": "https://malicious.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert cross_origin.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_wallet_http_is_local_only_public_view_is_masked_and_secret_is_never_persisted(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")

    class FakeWallet:
        def __init__(self):
            self.calls: list[tuple[str, object]] = []

        def snapshot(self, *, public_view: bool = False, refresh: bool = False):
            self.calls.append(("snapshot", public_view))
            return {
                "connected": True,
                "network": "solana-devnet",
                "address": "Abcd1234…Wxyz5678" if public_view else "Abcd1234FullWalletAddressWxyz5678",
                "balance_sol": 0.25,
                "signing": {"available": not public_view, "local_only": True},
                "public_view": public_view,
            }

        def connect(self, private_key, alias):
            self.calls.append(("connect", (private_key, alias)))
            return {"connected": True, "address": "Abcd1234FullWalletAddressWxyz5678"}

        def request_airdrop(self, sol):
            self.calls.append(("faucet", sol))
            return {"status": "confirmed", "sol": sol, "signature": "airdrop-signature"}

        def transfer(self, recipient, sol, confirm_phrase):
            self.calls.append(("transfer", (recipient, sol, confirm_phrase)))
            return {"status": "confirmed", "sol": sol, "signature": "transfer-signature"}

        def disconnect(self):
            self.calls.append(("disconnect", None))
            return {"connected": False}

    fake_wallet = FakeWallet()
    server, thread, base = _start_server(config_path, static)
    server.web_data.wallet_service = fake_wallet
    assert server.wallet_controls_allowed is True
    private_key = "do-not-" + "persist-private-key"
    try:
        with httpx.Client(timeout=5) as client:
            local = client.get(f"{base}/api/wallet")
            assert local.status_code == 200
            assert local.json()["address"] == "Abcd1234FullWalletAddressWxyz5678"
            assert local.json()["signing"]["available"] is True

            public = client.get(f"{base}/api/wallet", headers={"Host": "console.example"})
            assert public.status_code == 200
            assert public.json()["address"] == "Abcd1234…Wxyz5678"
            assert public.json()["signing"]["available"] is False

            connect = client.post(
                f"{base}/api/wallet/connect",
                headers={"Origin": base},
                json={"private_key": private_key, "alias": "test only"},
            )
            faucet = client.post(
                f"{base}/api/wallet/faucet",
                headers={"Origin": base},
                json={"sol": 0.1},
            )
            transfer = client.post(
                f"{base}/api/wallet/transfer",
                headers={"Origin": base},
                json={"recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"},
            )
            disconnected = client.delete(f"{base}/api/wallet", headers={"Origin": base})
            assert [response.status_code for response in (connect, faucet, transfer, disconnected)] == [200] * 4
            assert private_key not in "".join(
                response.text for response in (connect, faucet, transfer, disconnected)
            )

            post_payloads = {
                "/api/wallet/connect": {"private_key": private_key, "alias": "test only"},
                "/api/wallet/faucet": {"sol": 0.1},
                "/api/wallet/transfer": {
                    "recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"
                },
            }
            for route, payload in post_payloads.items():
                assert client.post(
                    f"{base}{route}", headers={"Host": "console.example", "Connection": "close"}, json=payload
                ).status_code == 403
                assert client.post(
                    f"{base}{route}",
                    headers={"Origin": "https://malicious.example", "Connection": "close"},
                    json=payload,
                ).status_code == 403
            assert client.delete(f"{base}/api/wallet", headers={"Host": "console.example"}).status_code == 403
            assert client.delete(
                f"{base}/api/wallet", headers={"Origin": "https://malicious.example"}
            ).status_code == 403

        assert ("connect", (private_key, "test only")) in fake_wallet.calls
        secret = private_key.encode("utf-8")
        assert all(secret not in path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_access_token_server_never_enables_wallet_controls_with_spoofed_loopback_host(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    token = "public-console-token-that-is-long-enough"
    token_file = tmp_path / "access-token.txt"
    token_file.write_text(token, encoding="utf-8")

    class FakeWallet:
        def __init__(self):
            self.calls: list[tuple[str, object]] = []

        def snapshot(self, *, public_view: bool = False, refresh: bool = False):
            self.calls.append(("snapshot", public_view))
            return {
                "address": "masked" if public_view else "full-wallet-address",
                "signing": {"available": not public_view},
            }

        def connect(self, private_key, alias):
            self.calls.append(("connect", alias))
            return {"connected": True}

        def request_airdrop(self, sol):
            self.calls.append(("faucet", sol))
            return {"status": "confirmed"}

        def transfer(self, recipient, sol, confirm_phrase):
            self.calls.append(("transfer", recipient))
            return {"status": "confirmed"}

        def disconnect(self):
            self.calls.append(("disconnect", None))
            return {"connected": False}

    server, thread, base = _start_server(config_path, static, token_file)
    fake_wallet = FakeWallet()
    server.web_data.wallet_service = fake_wallet
    headers = {
        "Authorization": f"Bearer {token}",
        "Host": "127.0.0.1",
        "Connection": "close",
    }
    try:
        assert server.wallet_controls_allowed is False
        with httpx.Client(timeout=5) as client:
            public = client.get(f"{base}/api/wallet", headers=headers)
            assert public.status_code == 200
            assert public.json()["address"] == "masked"
            assert public.json()["signing"]["available"] is False

            mutations = [
                client.post(
                    f"{base}/api/wallet/connect",
                    headers=headers,
                    json={"private_key": "must-not-reach-wallet", "alias": "blocked"},
                ),
                client.post(f"{base}/api/wallet/faucet", headers=headers, json={"sol": 0.1}),
                client.post(
                    f"{base}/api/wallet/transfer",
                    headers=headers,
                    json={"recipient": "recipient", "sol": 0.001, "confirm_phrase": "DEVNET ONLY"},
                ),
                client.delete(f"{base}/api/wallet", headers=headers),
            ]
            assert [response.status_code for response in mutations] == [403, 403, 403, 403]
        assert fake_wallet.calls == [("snapshot", True)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_non_loopback_binding_requires_access_token(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    with pytest.raises(ValueError, match="requires --access-token-file"):
        create_server(config_path, "0.0.0.0", _free_port(), static_dir=tmp_path)


def test_loopback_settings_reject_dns_rebinding_host(tmp_path: Path):
    config_path, _ = _config(tmp_path)
    Store(tmp_path / "db.sqlite3").close()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("console", encoding="utf-8")
    server, thread, base = _start_server(config_path, static)
    try:
        with httpx.Client(timeout=5) as client:
            response = client.patch(
                f"{base}/api/settings",
                headers={"Host": "attacker.example"},
                json={"updates": {"poll_seconds": 90}},
            )
            assert response.status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
