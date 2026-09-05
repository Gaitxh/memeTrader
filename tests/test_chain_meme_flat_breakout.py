from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def _snapshot(
    token: TokenCandidate,
    *,
    observed_at,
    pair_created_at,
    m5_trades: int,
    h1_trades: int,
    m5_volume: float,
    h1_volume: float,
    price_change_h1: float,
) -> TokenSnapshot:
    m5_buys = m5_trades // 2
    h1_buys = h1_trades // 2
    pair = {
        "chainId": token.chain,
        "pairAddress": "flat-pair",
        "pairCreatedAt": round(pair_created_at.timestamp() * 1000),
        "baseToken": {"address": token.address},
        "priceUsd": "1.0",
        "priceChange": {"h1": price_change_h1},
        "txns": {
            "m5": {"buys": m5_buys, "sells": m5_trades - m5_buys},
            "h1": {"buys": h1_buys, "sells": h1_trades - h1_buys},
        },
        "volume": {"m5": m5_volume, "h1": h1_volume},
    }
    return TokenSnapshot(
        token.chain,
        token.address,
        1.0,
        50_000.0,
        100_000.0,
        m5_volume,
        m5_buys,
        m5_trades - m5_buys,
        observed_at=observed_at,
        ingested_at=observed_at,
        provider="dexscreener",
        raw={"pair": pair},
    )


def test_flat_breakout_shadow_is_forward_only_and_has_no_trading_side_effects(
    tmp_path: Path,
):
    store = Store(tmp_path / "flat-shadow.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(
        chain="solana", address="B" * 32, name="Flat", source="fixture",
    )
    store.upsert_token(token)
    before_activation = utcnow() - timedelta(seconds=1)
    created_at = before_activation - timedelta(hours=7)
    historical = _snapshot(
        token, observed_at=before_activation, pair_created_at=created_at,
        m5_trades=0, h1_trades=2, m5_volume=0.0, h1_volume=100.0,
        price_change_h1=1.0,
    )
    store.add_snapshot(historical)
    registration = store.register_flat_compression_breakout_shadow()
    assert int(registration["activation_snapshot_id"]) == 1
    historical_outcome = {
        "kind": "visible", "token": token, "snapshot": historical,
        "target_token_id": token.token_id,
    }
    assert store.observe_flat_compression_breakout_market_batch(
        [historical_outcome], recorded_at=before_activation,
        evaluated_at=before_activation,
    ) == 0

    base = utcnow()
    samples = (
        (0, 0, 2, 0.0, 100.0, 1.0, "flat_watch"),
        (1, 3, 5, 300.0, 400.0, 3.0, "near_trigger"),
        (2, 10, 12, 1_000.0, 1_100.0, 25.0,
         "breakout_confirmation_pending"),
        (3, 11, 13, 1_100.0, 1_200.0, 30.0,
         "shadow_breakout_candidate"),
    )
    for seconds, m5_trades, h1_trades, m5_volume, h1_volume, change, state in samples:
        observed = base + timedelta(seconds=seconds)
        snapshot = _snapshot(
            token, observed_at=observed, pair_created_at=created_at,
            m5_trades=m5_trades, h1_trades=h1_trades,
            m5_volume=m5_volume, h1_volume=h1_volume,
            price_change_h1=change,
        )
        assert store.observe_flat_compression_breakout_market_batch(
            [{
                "kind": "visible", "token": token, "snapshot": snapshot,
                "target_token_id": token.token_id,
            }],
            recorded_at=observed, evaluated_at=observed,
        ) == 1
        latest = store.db.execute(
            "SELECT status FROM chain_meme_trader_flat_breakout_shadow "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert latest["status"] == state

    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions"
    ).fetchone()[0] == 0
    for table in (
        "chain_meme_trader_entry_decisions",
        "chain_meme_trader_positions",
        "chain_meme_trader_trades",
    ):
        assert store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    store.close()


def test_flat_breakout_targets_are_bounded_due_and_exclude_held_tokens(
    tmp_path: Path,
):
    store = Store(tmp_path / "flat-targets.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate(
        chain="solana", address="C" * 32, name="Due", source="fixture",
    )
    now = utcnow()
    store.upsert_token(token, seen_at=now)
    store.register_flat_compression_breakout_shadow()
    plan = store.db.execute(
        "EXPLAIN QUERY PLAN SELECT 1 FROM chain_meme_trader_positions "
        "WHERE token_id=? AND status='open'",
        (token.token_id,),
    ).fetchall()
    assert any(
        "chain_meme_trader_positions_open_token_idx" in str(row["detail"])
        for row in plan
    )
    feature = {
        "pair_address": "flat-pair",
        "pair_created_at": iso(now - timedelta(hours=7)),
    }
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_entry_evaluations("
            "definition_version,source_snapshot_id,token_id,evaluated_at,status,"
            "entry_family,reason,feature_json) VALUES(?,?,?,?,?,?,?,?)",
            (
                Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, 900_001,
                token.token_id, iso(now), "rejected", None, "fixture",
                json.dumps(feature),
            ),
        )
    targets = store.due_flat_compression_breakout_shadow_targets(now=now)
    assert [item["token_id"] for item in targets] == [token.token_id]
    store.upsert_chain_meme_trader_market_mark(
        token,
        _snapshot(
            token, observed_at=now, pair_created_at=now - timedelta(hours=7),
            m5_trades=0, h1_trades=2, m5_volume=0.0, h1_volume=100.0,
            price_change_h1=1.0,
        ),
        recorded_at=now,
    )
    assert store.due_flat_compression_breakout_shadow_targets(
        now=now + timedelta(seconds=30),
    ) == []
    assert store.due_flat_compression_breakout_shadow_targets(
        now=now + timedelta(seconds=61),
    )

    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
            "realized_pnl_usd,opened_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, "fixture-arm", 900_001,
                token.token_id, -1, -1, -1, 1.0, 1.04, 20.0 / 1.04,
                20.0 / 1.04, "20", "20", 20.0, 1.0, "open", 0.0,
                iso(now),
            ),
        )
    assert store.due_flat_compression_breakout_shadow_targets(
        now=now + timedelta(seconds=61),
    ) == []
    store.close()
