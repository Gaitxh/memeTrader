from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from solders.pubkey import Pubkey

from memetrader.capital_policies import (
    capital_policies,
    direct_lp_amount_specific_policy,
    event_actual_flow_policy,
    opportunity_policies,
    second_discussion_policies,
)
from memetrader.migration_absorption import migration_amount_absorption_policy
from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.store import Store


UTC = timezone.utc
TARGET_VERSION = "test-evidence-extension-funding-v1"


def _policies():
    policies = [
        *capital_policies(),
        *second_discussion_policies(),
        *opportunity_policies(),
        direct_lp_amount_specific_policy(),
        event_actual_flow_policy(),
        migration_amount_absorption_policy(),
    ]
    return {policy["arm_id"]: policy for policy in policies}


CASES = [
    (
        "direct_lp_amount_specific_confirmed_v1",
        [(10, 1.00, 10_000, 2_000, 14, 6)],
        120,
        "replacement_early_quality_confirmed",
    ),
    (
        "official_event_actual_flow_v1",
        [
            (10, 1.00, 10_000, 1_000, 14, 6),
            (20, 1.02, 10_000, 1_000, 14, 6),
            (30, 1.05, 10_000, 1_000, 14, 6),
        ],
        500,
        "replacement_continuation_confirmed",
    ),
    (
        "finite_capital_ranker_v1",
        [(10, 1.00, 10_000, 2_000, 14, 6)],
        500,
        "replacement_quality_gate_confirmed",
    ),
    (
        "event_reawakening_v1",
        [
            (10, 1.00, 10_000, 100, 1, 1),
            (20, 1.00, 10_000, 100, 1, 1),
            (30, 1.00, 10_000, 100, 1, 1),
            (40, 1.12, 9_000, 1_200, 14, 6),
        ],
        4_000,
        "replacement_reawakening_confirmed",
    ),
    (
        "surface_lifecycle_pipeline_v1",
        [
            (10, 1.00, 10_000, 1_000, 14, 6),
            (20, 1.02, 11_000, 1_000, 14, 6),
            (30, 1.05, 12_000, 1_000, 14, 6),
        ],
        4_000,
        "replacement_liquidity_lead_confirmed",
    ),
    (
        "no_ca_event_flow_leader_v1",
        [
            (10, 1.00, 10_000, 500, 14, 6),
            (20, 1.00, 10_000, 500, 14, 6),
            (30, 1.00, 10_000, 500, 14, 6),
            (40, 1.10, 10_000, 1_000, 14, 6),
        ],
        500,
        "replacement_compression_breakout_confirmed",
    ),
    (
        "migration_amount_rate_absorption_v1",
        [
            (10, 1.00, 10_000, 1_200, 14, 6),
            (20, 1.02, 10_000, 1_200, 14, 6),
            (30, 1.06, 10_000, 1_200, 14, 6),
        ],
        500,
        "replacement_young_absorption_confirmed",
    ),
]


def _snapshot(token, pair, observed_at, created_at, *, price, liquidity, volume,
              buys, sells):
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        liquidity,
        100_000.0,
        volume,
        buys,
        sells,
        observed_at=observed_at,
        ingested_at=observed_at,
        provider="dexscreener",
        raw={
            "pair": {
                "chainId": token.chain,
                "pairAddress": pair,
                "dexId": "pumpswap",
                "pairCreatedAt": round(created_at.timestamp() * 1_000),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": liquidity},
            }
        },
    )


@pytest.mark.parametrize("arm_id,frames,base_age,ready_reason", CASES)
def test_revised_evidence_arm_uses_l0_then_next_frame_buy_and_can_time_exit(
    tmp_path, monkeypatch, arm_id, frames, base_age, ready_reason,
):
    clock = [datetime(2026, 9, 6, 15, 0, tzinfo=UTC)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    store = Store(tmp_path / f"{arm_id}.sqlite3", initial_cash_usd=1_000)
    source_version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    source_policy = _policies()[arm_id]
    try:
        store.activate_chain_meme_trader_funded_period()
        source_row = store.append_chain_meme_trader_policy(
            source_policy, activated_at=clock[0]
        )
        source_hash = str(source_row["behavior_contract_hash"])
        source_json = str(source_row["policy_json"])

        store.activate_chain_meme_trader_funding_epoch(
            target_version=TARGET_VERSION,
            source_version=source_version,
            at=clock[0] + timedelta(seconds=1),
            apply_strategy_revisions=True,
        )
        monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", TARGET_VERSION)
        target_row = store.db.execute(
            "SELECT * FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        revised = json.loads(target_row["policy_json"])
        assert revised["entry_family"] == "evidence_extension_l0"
        assert revised["arm_id"] == source_policy["arm_id"]
        assert revised["canonical_id"] == source_policy["canonical_id"]
        assert str(target_row["behavior_contract_hash"]) != source_hash
        assert store.db.execute(
            "SELECT behavior_contract_hash,policy_json FROM "
            "chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?",
            (source_version, arm_id),
        ).fetchone()[:] == (source_hash, source_json)

        token = TokenCandidate(
            "solana", str(Pubkey.new_unique()), "Extension", "EXT", source="test"
        )
        pair = str(Pubkey.new_unique())
        activated_at = clock[0] + timedelta(seconds=1)
        created_at = activated_at - timedelta(seconds=base_age)
        for seconds, price, liquidity, volume, buys, sells in frames:
            clock[0] = activated_at + timedelta(seconds=seconds)
            assert store.observe_chain_meme_pattern(
                token,
                _snapshot(
                    token, pair, clock[0], created_at, price=price,
                    liquidity=liquidity, volume=volume, buys=buys, sells=sells,
                ),
                recorded_at=clock[0],
            ) == 0

        ready = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION,),
        ).fetchone()[0])
        assert ready["outcomes"][arm_id] == ready_reason
        assert arm_id in ready["ready_arm_ids"]

        # The confirmed frame is only the signal. A later same-pool frame fills.
        seconds, price, liquidity, volume, buys, sells = frames[-1]
        clock[0] = activated_at + timedelta(seconds=seconds + 10)
        assert store.observe_chain_meme_pattern(
            token,
            _snapshot(
                token, pair, clock[0], created_at, price=price,
                liquidity=liquidity, volume=volume, buys=buys, sells=sells,
            ),
            recorded_at=clock[0],
        ) == 1
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert position is not None and position["status"] == "open"
        decision = store.db.execute(
            "SELECT * FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
            "AND arm_id=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert decision["status"] == "admitted"
        assert decision["reason"] == "pattern_next_observation"

        if arm_id == "direct_lp_amount_specific_confirmed_v1":
            assert store.due_direct_lp_entry_preflight_quote(now=clock[0]) is None
            assert store.db.execute(
                "SELECT COUNT(*) FROM chain_meme_pattern_evidence "
                "WHERE kind='direct_lp_entry_preflight_request'"
            ).fetchone()[0] == 0

        # Every replacement retains an ordinary maximum-hold escape, including
        # arms whose optional specialist exit evidence never arrives.
        clock[0] = clock[0] + timedelta(
            minutes=float(revised.get("max_hold_minutes") or 240) + 1
        )
        mark = _snapshot(
            token, pair, clock[0], created_at, price=price,
            liquidity=liquidity, volume=volume, buys=buys, sells=sells,
        )
        store.upsert_chain_meme_trader_market_mark(token, mark, recorded_at=clock[0])
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=TARGET_VERSION, now=clock[0]
        ) == 1
        pending = store.db.execute(
            "SELECT reason,status FROM chain_meme_trader_marks WHERE definition_version=? "
            "AND arm_id=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert pending["reason"] == "market_mark_max_hold"
        assert pending["status"] == "pending"

        clock[0] = clock[0] + timedelta(seconds=2)
        mark = _snapshot(
            token, pair, clock[0], created_at, price=price,
            liquidity=liquidity, volume=volume, buys=buys, sells=sells,
        )
        store.upsert_chain_meme_trader_market_mark(token, mark, recorded_at=clock[0])
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=TARGET_VERSION, now=clock[0]
        ) == 1
        closed = store.db.execute(
            "SELECT status,close_reason FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert closed["status"] == "closed"
        assert closed["close_reason"].startswith("market_mark_max_hold")
    finally:
        store.close()
