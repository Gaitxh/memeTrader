from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.store import Store


ARM = "mature_new_acceptance_5u_v1"


def _snapshot(token, pair, created_at, observed_at, *, price):
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        2_000.0,
        100_000.0,
        100.0,
        1,
        1,
        observed_at=observed_at,
        ingested_at=observed_at,
        provider="dexscreener",
        raw={"pair": {
            "chainId": token.chain,
            "dexId": "pumpswap",
            "pairAddress": pair,
            "pairCreatedAt": round(created_at.timestamp() * 1000),
            "baseToken": {"address": token.address},
            "priceUsd": str(price),
            "liquidity": {"usd": 2_000.0},
        }},
    )


def test_mature_narrative_two_confirmations_buy_five_on_next_frame(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "mature.sqlite3", initial_cash_usd=1_000)
    store.activate_chain_meme_trader_funded_period()
    assert store.register_chain_meme_mature_acceptance() == 1
    assert store.register_chain_meme_mature_acceptance() == 0

    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Mature", "MAT", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    created_at = clock[0] - timedelta(hours=7)
    origin = clock[0]

    def observe(seconds, price):
        clock[0] = origin + timedelta(seconds=seconds)
        return store.observe_chain_meme_pattern(
            token,
            _snapshot(token, pair, created_at, clock[0], price=price),
            recorded_at=clock[0],
        )

    assert observe(1, 1.0) == 0
    event_at = origin + timedelta(seconds=10)
    clock[0] = event_at
    evidence_id = store.record_chain_meme_pattern_evidence(
        token.token_id,
        "",
        "narrative",
        {
            "exact_token_relation": True,
            "independent_sources": 2,
            "source_urls": ["https://one.example/item", "https://two.example/item"],
            "verification_id": 9,
            "basis": "original_source_contract_mentions_and_independent_fact_support",
        },
        observed_at=event_at,
        source_key="fact:9:mature",
    )
    context = store.chain_meme_pattern_context(
        token.token_id, pair, [], event_at
    )["narrative"]
    assert context["evidence_id"] == evidence_id
    assert context["observed_at"] == context["recorded_at"]

    assert observe(15, 1.0) == 0       # freeze event and pre-event baseline
    assert observe(30, 1.01) == 0      # first independent confirmation
    assert observe(50, 1.02) == 0      # second confirmation only becomes ready
    assert observe(65, 1.03) == 1      # next independent original-pool frame BUY

    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM),
    ).fetchone()
    assert position["stake_usd"] == pytest.approx(5.0)
    assert position["entry_signal_price_usd"] == pytest.approx(1.03)
    assert position["entry_execution_price_usd"] == pytest.approx(1.03 * 1.04)
    cohort_features = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_cohorts WHERE id=?",
        (position["shadow_cohort_id"],),
    ).fetchone()[0])
    assert cohort_features["event_keys"][ARM]

    assert observe(80, 1.04) == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=?",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM),
    ).fetchone()[0] == 1
    latest = json.loads(store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE definition_version=? AND token_id=? AND reason='pattern_observation' "
        "ORDER BY id DESC LIMIT 1",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, token.token_id),
    ).fetchone()[0])
    assert latest["mature_acceptance_state"]["status"] == "CONSUMED"
    store.close()
