from __future__ import annotations

import asyncio
from datetime import timedelta

from memetrader.models import TokenCandidate, iso, parse_time
from memetrader.runtime import Runtime, initial_config
from memetrader.store import Store


def test_full_universe_finalizer_honors_bounded_cohort_limit(tmp_path):
    store = Store(tmp_path / "bounded-universe.sqlite3", initial_cash_usd=1000)
    cohorts = []
    for suffix in ("A", "B", "C"):
        token = TokenCandidate(
            chain="solana", address=suffix * 32, name=suffix, symbol=suffix,
        )
        store.upsert_token(token)
        round_id = store.start_token_discovery_round(
            provider="pumpportal", surface="create", mode="stream_window",
            chain_scope="solana",
        )
        store.add_token_discovery_exposure(
            round_id, token_id=token.token_id, chain=token.chain, role="create",
            first_local_discovery=True, new_token=True,
        )
        store.finish_token_discovery_round(
            round_id, status="completed", returned_count=1,
        )
        cohort = store.db.execute(
            "SELECT * FROM token_universe_forward_cohorts WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        cohorts.append(cohort)
        discovered = parse_time(cohort["discovery_recorded_at"])
        for minutes, price in ((1, 1.0), (15, 1.1), (60, 1.2), (240, 1.3)):
            at = iso(discovered + timedelta(minutes=minutes, seconds=1))
            store.db.execute(
                "INSERT INTO token_snapshots("
                "token_id,observed_at,ingested_at,recorded_at,provider,price_usd,raw_json"
                ") VALUES(?,?,?,?,?,?,?)",
                (token.token_id, at, at, at, "test", price, "{}"),
            )

    now = max(parse_time(row["discovery_recorded_at"]) for row in cohorts)
    now += timedelta(minutes=241)
    first = store.finalize_token_universe_forward_outcomes(now=now, limit=1)
    assert first["cohorts_checked"] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM token_universe_forward_baselines"
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM token_universe_forward_outcomes"
    ).fetchone()[0] == 3
    second = store.finalize_token_universe_forward_outcomes(now=now, limit=1)
    assert second["cohorts_checked"] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM token_universe_forward_baselines"
    ).fetchone()[0] == 2
    store.close()


def test_chain_only_outcome_loop_restores_bounded_full_universe_followup(tmp_path):
    async def scenario():
        config = initial_config()
        config["database"] = "runtime.sqlite3"
        config["bridge"]["enabled"] = False
        runtime = Runtime(config, tmp_path)
        runtime._chain_outcome_version = "test-outcomes/v1"
        runtime.store.enroll_chain_meme_universe_outcomes = lambda **kwargs: {
            "cohorts_enrolled": 0, "targets_enrolled": 0,
        }
        runtime.store.finalize_chain_meme_universe_outcomes = lambda **kwargs: {
            "targets_checked": 0, "observed": 0, "unknown": 0,
        }
        runtime.store.finalize_token_universe_outcome_quality = (
            lambda: calls.append("quality")
        )
        runtime.store.finalize_token_universe_fixed_target_execution = (
            lambda: calls.append("execution")
        )
        runtime.store.finalize_missed_opportunity_audits = (
            lambda: calls.append("missed")
        )
        runtime.store.finalize_missed_opportunity_no_decision_attributions = (
            lambda: calls.append("attribution")
        )
        calls = []

        async def followup(**kwargs):
            calls.append(("followup", kwargs))

        runtime.token_universe_followup_once = followup
        await runtime.chain_meme_universe_outcomes_once()
        assert calls == [
            ("followup", {
                "finalize_limit": 16,
                "universe_limit": 0,
                "onchain_limit": 0,
            }),
            "quality", "execution", "missed", "attribution",
        ]
        await runtime.close()

    asyncio.run(scenario())
