from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, iso, parse_time
from memetrader.store import Store


def test_miss_quality_adjudication_excludes_cross_pair_and_keeps_confirmed_miss(tmp_path):
    store = Store(tmp_path / "miss-quality.sqlite3", initial_cash_usd=1000)
    store.register_token_universe_outcome_quality(
        reference_notional_usd=20,
        min_liquidity_usd=1000,
        max_liquidity_impact_pct=0.02,
        slippage_rate=0.04,
        default_fee_bps=60,
        pump_fee_bps=125,
        max_quote_age_seconds=45,
        max_tax_pct=10,
    )
    quote = "So11111111111111111111111111111111111111112"

    def enroll(address: str, *, cross_pair: bool):
        token = TokenCandidate("solana", address, address)
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="fixture", surface="new_pools", mode="poll", chain_scope="solana",
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain="solana", role="new_pool",
            first_local_discovery=True, new_token=True,
        )
        store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        discovered = parse_time(cohort["discovery_recorded_at"])
        for minutes, price, pair, liquidity in (
            (1, 0.000001 if cross_pair else 1.0, "DUST" if cross_pair else "PAIR", 0.5 if cross_pair else 50_000),
            (15, 0.1 if cross_pair else 1.6, "LIQUID" if cross_pair else "PAIR", 50_000),
        ):
            at = iso(discovered + timedelta(minutes=minutes, seconds=1))
            raw = json.dumps({"pair": {
                "chainId": "solana", "dexId": "fixture", "pairAddress": pair,
                "baseToken": {"address": token.address},
                "quoteToken": {"address": quote},
            }})
            store.db.execute(
                """
                INSERT INTO token_snapshots(
                    token_id,observed_at,ingested_at,recorded_at,provider,price_usd,
                    liquidity_usd,buy_tax_pct,sell_tax_pct,honeypot,sellable,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    token.token_id, at, at, at, "fixture", price, liquidity,
                    0.0, 0.0, 0, 1, raw,
                ),
            )
        return token, discovered

    valid, valid_at = enroll("V" * 32, cross_pair=False)
    cross, cross_at = enroll("X" * 32, cross_pair=True)
    store.finalize_token_universe_forward_outcomes(
        now=max(valid_at, cross_at) + timedelta(minutes=16),
    )
    assert store.finalize_token_universe_outcome_quality()["inserted"] == 2
    assert store.finalize_missed_opportunity_audits() == {
        "inserted": 2, "potential_misses": 2,
    }
    assert store.finalize_missed_opportunity_quality_adjudications() == {
        "inserted": 2, "learnable": 1, "estimated_only": 0, "excluded": 1,
    }

    rows = {
        row["token_id"]: row
        for row in store.db.execute("SELECT * FROM missed_opportunity_quality_adjudications")
    }
    assert rows[valid.token_id]["status"] == "confirmed_executable_miss"
    assert rows[valid.token_id]["learnable_potential_miss"] == 1
    assert rows[cross.token_id]["status"] == "excluded_quality"
    assert rows[cross.token_id]["reason_code"] == "cross_pair_incomparable"
    assert rows[cross.token_id]["learnable_potential_miss"] == 0
    summary = store.missed_opportunity_audit_summary_from_connection(store.db)
    assert summary["summary"]["potential_misses"] == 2
    assert summary["quality_adjudication"]["summary"] == {
        "adjudicated": 2,
        "learnable_potential_misses": 1,
        "estimated_only_unconfirmed": 0,
        "excluded_quality": 1,
    }
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "UPDATE missed_opportunity_quality_adjudications SET learnable_potential_miss=0"
        )
    store.close()
