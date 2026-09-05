from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from solders.pubkey import Pubkey

from memetrader.capital_policies import capital_policies
from memetrader.migration_absorption import (
    ARM_ID,
    build_migration_amount_absorption_context,
    migration_amount_absorption_policy,
    migration_amount_absorption_signal,
)
from memetrader.models import TokenCandidate, TokenSnapshot, iso
from memetrader.store import Store


ORIGIN = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
TOKEN = "solana:mint"
PAIR = "canonical-pool"


def stamp(seconds):
    return (ORIGIN + timedelta(seconds=seconds)).isoformat()


def history(**last_change):
    rows = [
        (2, 100, 1_000),
        (8, 80, 800),
        (25, 82, 850),
        (41, 85, 900),
    ]
    result = [{
        "id": index, "token_id": TOKEN, "pair_address": PAIR,
        "price": price, "liquidity": depth,
        "observed_at": stamp(seconds), "recorded_at": stamp(seconds + .1),
    } for index, (seconds, price, depth) in enumerate(rows, 1)]
    result[-1].update(last_change)
    return result


def migration(**changes):
    return {
        "id": 7, "token_id": TOKEN, "address": "mint",
        "launch_event_type": "migration", "source_observed_at": stamp(1),
        "ingested_at": stamp(1.1), "recorded_at": stamp(1.2), **changes,
    }


def surface(**changes):
    return {
        "id": 8, "token_id": TOKEN, "pair_address": PAIR,
        "observed_at": stamp(2), "recorded_at": stamp(2.1),
        "payload": {
            "status": "RESOLVED", "complete": True,
            "canonical_migration_pool": True, "pool_address": PAIR,
            "base_mint": "mint", "quote_mint": "quote", **changes,
        },
    }


def window(start, end, *, sells, buys, breadth, sell_count):
    return {
        "complete": True, "window_start": stamp(start), "window_end": stamp(end),
        "observed_at": stamp(end + .1), "recorded_at": stamp(end + .2),
        "sell_quote_notional_raw": sells, "buy_quote_notional_raw": buys,
        "net_quote_flow_raw": buys - sells, "effective_breadth": breadth,
        # Deliberately misleading diagnostic; the policy must never read it.
        "sell_count": sell_count,
    }


def flow(*, current_sells=1_000, current_duration=20, current_breadth=3,
         resolver_recorded=40.5):
    split, end = 20, 20 + current_duration
    return {
        "id": 9, "token_id": TOKEN, "pair_address": PAIR,
        "observed_at": stamp(41), "recorded_at": stamp(41.5),
        "payload": {
            "complete": True, "scan_complete": True,
            "future_data_rejected": False, "adjacent": True, "nonoverlap": True,
            "resolver": {
                "status": "verified", "pool_address": PAIR,
                "base_mint": "mint", "quote_mint": "quote",
                "observed_at": stamp(2), "recorded_at": stamp(resolver_recorded),
            },
            "windows": [
                window(10, split, sells=1_000, buys=800, breadth=2, sell_count=1),
                window(split, end, sells=current_sells, buys=current_sells + 1_000,
                       breadth=current_breadth, sell_count=999),
            ],
        },
    }


def build(flow_row=None, **kwargs):
    return build_migration_amount_absorption_context(
        history(), flow_row or flow(), migration(), surface(),
        decision_at=stamp(42), activated_at=stamp(0), **kwargs,
    )


def test_new_policy_preserves_parent_and_uses_actual_sell_rate_then_next_frame():
    parent_before = deepcopy(next(p for p in capital_policies()
                                  if p["arm_id"] == "migration_absorption_v1"))
    policy = migration_amount_absorption_policy()
    assert policy["arm_id"] == ARM_ID and policy["notional_usd"] == 5.0
    assert "next_frame_trade" in policy["required_inputs"]
    assert next(p for p in capital_policies()
                if p["arm_id"] == "migration_absorption_v1") == parent_before

    context = build()
    evidence = context["migration_amount_absorption"]
    # Same sell amount over twice the duration halves actual pressure even
    # though the second window's diagnostic sell count is 999x larger.
    assert evidence["sell_amount_rate_previous_raw_per_second"] == 100
    assert evidence["sell_amount_rate_current_raw_per_second"] == 50
    assert evidence["sell_amount_rate_ratio"] == .5
    assert evidence["effective_breadth_growth"] == 1
    assert evidence["uses_trade_counts"] is False
    assert evidence["recovery_status"] == "NOT_MEASURED_PRE_ENTRY"
    assert migration_amount_absorption_signal(
        history(), policy, decision_at=stamp(42), activated_at=stamp(0), context=context,
    ) == (True, "migration_amount_rate_absorption_confirmed")


@pytest.mark.parametrize(
    "flow_row,last_change,reason",
    [
        (flow(current_sells=2_000, current_duration=10), {},
         "migration_amount_rate_absorption_below_hypothesis"),
        (flow(current_breadth=2), {},
         "migration_amount_rate_absorption_below_hypothesis"),
        (flow(resolver_recorded=43), {}, "amountful_flow_identity_unverified"),
        (flow(), {"recorded_at": stamp(43)}, "market_identity_time_or_value_invalid"),
    ],
)
def test_missing_amount_decay_breadth_or_strict_asof_never_passes(
    flow_row, last_change, reason,
):
    policy = migration_amount_absorption_policy()
    context = build_migration_amount_absorption_context(
        history(**last_change), flow_row, migration(), surface(),
        decision_at=stamp(42), activated_at=stamp(0),
    )
    passed, actual = migration_amount_absorption_signal(
        history(**last_change), policy, decision_at=stamp(42),
        activated_at=stamp(0), context=context,
    )
    assert not passed and actual == reason


def test_wrong_pool_or_noncanonical_surface_waits():
    for bad_surface in (surface(pool_address="later-winner"),
                        surface(canonical_migration_pool=False)):
        context = build_migration_amount_absorption_context(
            history(), flow(), migration(), bad_surface,
            decision_at=stamp(42), activated_at=stamp(0),
        )
        assert context["migration_amount_absorption"]["reason"] \
            == "canonical_migration_pool_unconfirmed"


def test_store_migration_amount_signal_then_real_15_second_frame_buys_five_usdc(
    tmp_path, monkeypatch,
):
    clock = [ORIGIN]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "migration-amount-store.sqlite3", initial_cash_usd=1_000)
    store.activate_chain_meme_trader_funded_period()
    assert store.register_chain_meme_capital_experiments() == 18
    parent_before = store.db.execute(
        "SELECT id,activated_at,policy_json FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id='migration_absorption_v1'",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()
    assert parent_before is not None
    assert store.register_chain_meme_evidence_completion_experiments() == 4
    new_before = store.db.execute(
        "SELECT id,activated_at,policy_json FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM_ID),
    ).fetchone()
    assert new_before is not None
    assert store.register_chain_meme_evidence_completion_experiments() == 0
    assert tuple(store.db.execute(
        "SELECT id,activated_at,policy_json FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id=?",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM_ID),
    ).fetchone()) == tuple(new_before)
    assert tuple(store.db.execute(
        "SELECT id,activated_at,policy_json FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id='migration_absorption_v1'",
        (store.CHAIN_MEME_TRADER_ACTIVE_VERSION,),
    ).fetchone()) == tuple(parent_before)

    address, pair = str(Pubkey.new_unique()), str(Pubkey.new_unique())
    token = TokenCandidate(
        "solana", address, "Migration", "MIG",
        first_seen_at=ORIGIN + timedelta(seconds=1), source="pumpportal:migration",
        raw={"txType": "migration", "signature": "migration-signature", "pool": "pump-amm"},
    )
    def observe(seconds, price, liquidity):
        clock[0] = ORIGIN + timedelta(seconds=seconds)
        snapshot = TokenSnapshot(
            "solana", address, price, liquidity, 100_000, 500, 2, 1,
            observed_at=clock[0], ingested_at=clock[0], provider="dexscreener",
            raw={"pair": {
                "chainId": "solana", "pairAddress": pair, "dexId": "pumpswap",
                "pairCreatedAt": round((ORIGIN - timedelta(seconds=60)).timestamp() * 1000),
                "baseToken": {"address": address}, "priceUsd": str(price),
                "liquidity": {"usd": liquidity},
            }},
        )
        return store.observe_chain_meme_pattern(token, snapshot, recorded_at=clock[0])

    try:
        # Same-second source/ingestion with different ISO precision must stay causal.
        clock[0] = ORIGIN + timedelta(seconds=1.1)
        assert store.record_token_launch_fact(
            token, observed_at=ORIGIN + timedelta(seconds=1), ingested_at=clock[0],
        ) is not None
        clock[0] = ORIGIN + timedelta(seconds=2.1)
        store.record_chain_meme_pattern_evidence(
            token.token_id, pair, "pool_surface", {
                "status": "RESOLVED", "complete": True,
                "surface": "CANONICAL_MIGRATION", "canonical_migration_pool": True,
                "pool_address": pair, "base_mint": address, "quote_mint": "quote",
            }, observed_at=ORIGIN + timedelta(seconds=2), source_key="migration-surface",
        )
        observe(3, 100, 1_000)
        observe(8, 80, 800)
        observe(25, 82, 850)

        clock[0] = ORIGIN + timedelta(seconds=41)
        flow_payload = {
            "complete": True, "scan_complete": True,
            "future_data_rejected": False, "adjacent": True, "nonoverlap": True,
            "resolver": {
                "status": "verified", "pool_address": pair,
                "base_mint": address, "quote_mint": "quote",
                "observed_at": iso(ORIGIN + timedelta(seconds=2)),
                "recorded_at": iso(ORIGIN + timedelta(seconds=40.5)),
            },
            "windows": [
                {
                    "complete": True, "window_start": iso(ORIGIN + timedelta(seconds=10)),
                    "window_end": iso(ORIGIN + timedelta(seconds=20)),
                    "observed_at": iso(ORIGIN + timedelta(seconds=20.1)),
                    "recorded_at": iso(ORIGIN + timedelta(seconds=20.2)),
                    "sell_quote_notional_raw": 1_000, "buy_quote_notional_raw": 800,
                    "net_quote_flow_raw": -200, "effective_breadth": 2,
                    "sell_count": 1,
                },
                {
                    "complete": True, "window_start": iso(ORIGIN + timedelta(seconds=20)),
                    "window_end": iso(ORIGIN + timedelta(seconds=40)),
                    "observed_at": iso(ORIGIN + timedelta(seconds=40.1)),
                    "recorded_at": iso(ORIGIN + timedelta(seconds=40.2)),
                    "sell_quote_notional_raw": 1_000, "buy_quote_notional_raw": 2_000,
                    "net_quote_flow_raw": 1_000, "effective_breadth": 3,
                    "sell_count": 999,
                },
            ],
        }
        store.record_chain_meme_pattern_evidence(
            token.token_id, pair, "amountful_flow", flow_payload,
            observed_at=clock[0], source_key="migration-flow",
        )
        observe(41, 85, 900)
        signal = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()[0])
        assert ARM_ID in signal["ready_arm_ids"]
        assert signal["outcomes"][ARM_ID] == "migration_amount_rate_absorption_confirmed"
        assert store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=?", (ARM_ID,),
        ).fetchone()[0] == 0

        observe(56, 86, 920)
        trade = store.db.execute(
            "SELECT * FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'", (ARM_ID,),
        ).fetchone()
        assert trade is not None
        assert trade["gross_usd"] == 5.0 and trade["net_cash_flow_usd"] == -5.0
        assert "dex_mark_paper_fill" in trade["reason"]
    finally:
        store.close()
