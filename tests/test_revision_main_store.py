from __future__ import annotations

from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.revision_main_extensions import (
    BALANCED_HARVEST_FLOW_EXIT_ARMS,
    REAWAKENING_MATURE_ACCELERATION_ARMS,
)
from memetrader.store import Store


def _snapshot(
    token: TokenCandidate,
    pair: str,
    at,
    *,
    age_seconds: float,
    liquidity: float = 1_000.0,
    volume: float = 500.0,
    buys: int = 6,
    sells: int = 2,
    price: float = 1.0,
) -> TokenSnapshot:
    prior_trades = 1
    prior_volume = 50.0
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        liquidity,
        100_000.0,
        volume,
        buys,
        sells,
        observed_at=at,
        ingested_at=at,
        provider="dexscreener",
        raw={
            "pair": {
                "chainId": token.chain,
                "dexId": "pumpswap",
                "pairAddress": pair,
                "pairCreatedAt": round(
                    (at - timedelta(seconds=age_seconds)).timestamp() * 1000
                ),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": liquidity},
                "txns": {
                    "m5": {"buys": buys, "sells": sells},
                    "h1": {"buys": buys + prior_trades, "sells": sells},
                },
                "volume": {"m5": volume, "h1": volume + prior_volume},
            }
        },
    )


def _reviewed_store(tmp_path, monkeypatch, name: str):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    monkeypatch.setattr(
        Store,
        "CHAIN_MEME_TRADER_ACTIVE_VERSION",
        Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION,
    )
    store = Store(tmp_path / name)
    store.activate_chain_meme_trader_funded_period()
    old = Store.CHAIN_MEME_TRADER_FUNDED_PERIOD_VERSION
    new = Store.CHAIN_MEME_TRADER_REVIEWED_PERIOD_VERSION
    activated_at = clock[0] + timedelta(seconds=1)
    clock[0] = activated_at
    store.activate_chain_meme_trader_funding_epoch(
        target_version=new,
        source_version=old,
        at=activated_at,
        apply_strategy_revisions=True,
    )
    monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", new)
    definition = store._chain_meme_trader_effective_definition(
        new, store._chain_meme_trader_registration(new)["definition_json"]
    )
    return store, clock, new, definition


def test_mature_acceleration_uses_main_flow_burst_and_respects_floor_and_age(
    tmp_path, monkeypatch,
):
    store, clock, version, definition = _reviewed_store(
        tmp_path, monkeypatch, "main-mature-acceleration.sqlite3"
    )
    arm = next(iter(REAWAKENING_MATURE_ACCELERATION_ARMS))
    policy = next(item for item in definition["policies"] if item["arm_id"] == arm)
    assert policy["strategy_revision"] == 2
    assert policy["entry_family"] == "flow_burst"
    assert policy["source_entry_family"] == "reawakening"
    assert policy.get("entry_match_mode") not in {
        "isolated_pattern_observer",
        "isolated_cohort_observer",
    }

    def add(name, *, age, liquidity, trades=8, volume=500.0):
        clock[0] += timedelta(seconds=1)
        token = TokenCandidate(
            "solana", str(Pubkey.new_unique()), name, name[:4], source="fixture"
        )
        pair = str(Pubkey.new_unique())
        snapshot_id = store.add_snapshot(
            _snapshot(
                token,
                pair,
                clock[0],
                age_seconds=age,
                liquidity=liquidity,
                volume=volume,
                buys=trades - 2,
                sells=2,
            )
        )
        store.enroll_chain_meme_trader_v6(definition_version=version)
        count = store.db.execute(
            "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE "
            "definition_version=? AND arm_id=? AND token_id=? AND side='BUY'",
            (version, arm, token.token_id),
        ).fetchone()[0]
        return token, pair, snapshot_id, count

    assert add("Young", age=3_599, liquidity=10_000)[3] == 0
    assert add("Dust", age=7_200, liquidity=999.99)[3] == 0

    clock[0] += timedelta(seconds=1)
    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Later", "LATE", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    first_id = store.add_snapshot(
        _snapshot(
            token, pair, clock[0], age_seconds=7_200, liquidity=1_000,
            volume=499.0, buys=5, sells=2,
        )
    )
    store.enroll_chain_meme_trader_v6(definition_version=version)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE "
        "definition_version=? AND arm_id=? AND token_id=? AND side='BUY'",
        (version, arm, token.token_id),
    ).fetchone()[0] == 0

    clock[0] += timedelta(seconds=1)
    second_id = store.add_snapshot(
        _snapshot(
            token, pair, clock[0], age_seconds=7_201, liquidity=1_000,
            volume=500.0, buys=6, sells=2,
        )
    )
    store.enroll_chain_meme_trader_v6(definition_version=version)
    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?",
        (version, arm, token.token_id),
    ).fetchone()
    assert position is not None
    assert int(position["entry_snapshot_id"]) == second_id
    assert int(position["entry_snapshot_id"]) > first_id
    cohort = store.db.execute(
        "SELECT * FROM chain_meme_trader_v6_cohorts WHERE id=?",
        (position["shadow_cohort_id"],),
    ).fetchone()
    assert cohort["entry_family"] == "flow_burst"
    assert position["stake_usd"] == pytest.approx(20.0)
    store.close()


@pytest.mark.parametrize(
    ("volume", "buys", "sells", "action"),
    [(400.0, 1, 3, "FLOW_EXIT"), (0.0, 0, 0, "INACTIVITY_EXIT")],
)
def test_balanced_harvest_flow_exit_triggers_then_sells_on_next_pool_frame(
    tmp_path, monkeypatch, volume, buys, sells, action,
):
    store, clock, version, definition = _reviewed_store(
        tmp_path, monkeypatch, f"balanced-{action.lower()}.sqlite3"
    )
    arm = next(iter(BALANCED_HARVEST_FLOW_EXIT_ARMS))
    policy = next(item for item in definition["policies"] if item["arm_id"] == arm)
    assert policy["strategy_revision"] == 2
    assert policy["entry_family"] == "broad_launch"
    assert policy["exit_family"] == "balanced_harvest"
    assert policy["zero_activity_grace_minutes"] == 15.0
    assert policy["flow_grace_minutes"] == 15.0

    clock[0] += timedelta(seconds=1)
    opened_at = clock[0]
    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Balanced", "BAL", source="fixture"
    )
    pair = str(Pubkey.new_unique())
    store.add_snapshot(
        _snapshot(
            token, pair, opened_at, age_seconds=60, liquidity=1_000,
            volume=300.0, buys=3, sells=1,
        )
    )
    store.enroll_chain_meme_trader_v6(definition_version=version)
    position = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=? AND token_id=?",
        (version, arm, token.token_id),
    ).fetchone()
    assert position is not None

    trigger_at = opened_at + timedelta(minutes=15, seconds=1)
    clock[0] = trigger_at
    store.upsert_chain_meme_trader_market_mark(
        token,
        _snapshot(
            token, pair, trigger_at, age_seconds=961, liquidity=1_000,
            volume=volume, buys=buys, sells=sells,
        ),
        recorded_at=trigger_at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=trigger_at
    ) >= 1
    pending = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? ORDER BY id DESC LIMIT 1",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    assert pending["action"] == action
    assert pending["status"] == "pending"
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()[0] == 0

    sold_at = trigger_at + timedelta(seconds=1)
    clock[0] = sold_at
    store.upsert_chain_meme_trader_market_mark(
        token,
        _snapshot(
            token, pair, sold_at, age_seconds=962, liquidity=1_000,
            volume=volume, buys=buys, sells=sells,
        ),
        recorded_at=sold_at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=sold_at
    ) >= 1
    closed = store.db.execute(
        "SELECT status,closed_at FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    assert closed["status"] == "closed"
    sell = store.db.execute(
        "SELECT * FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side='SELL'",
        (version, arm, position["shadow_cohort_id"]),
    ).fetchone()
    assert sell["created_at"] == iso(sold_at)
    store.close()
