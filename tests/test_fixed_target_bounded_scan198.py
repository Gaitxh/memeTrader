from datetime import timedelta

from memetrader.models import TokenCandidate, utcnow
from memetrader.store import Store


def test_fixed_target_bounded_sweep_recovers_rows_behind_tail_cursor(tmp_path):
    store = Store(tmp_path / "fixed-target-scan.sqlite3", initial_cash_usd=1000)
    now = utcnow()
    store.register_token_universe_fixed_target_execution(
        paper_stake_usd=20, min_liquidity_usd=1000,
        max_liquidity_impact_pct=0.01, slippage_rate=0.04,
        default_fee_bps=60, pump_fee_bps=125, max_tax_pct=10,
    )
    token = TokenCandidate("bsc", "0x" + "a" * 40, "Scan fixture", "fixture")
    store.upsert_token(token, seen_at=now)
    round_id = store.start_token_discovery_round(
        provider="fixture", surface="fixture", mode="poll",
        chain_scope="bsc", started_at=now,
    )
    store.add_token_discovery_exposure(
        round_id, token_id=token.token_id, chain="bsc", role="new_token",
        first_local_discovery=True, new_token=True, observed_at=now,
    )
    store.finish_token_discovery_round(round_id, status="completed", returned_count=1)
    store.finalize_token_universe_forward_outcomes(now=now + timedelta(days=2))
    outcome_count = store.db.execute(
        "SELECT COUNT(*) FROM token_universe_forward_outcomes"
    ).fetchone()[0]
    assert outcome_count > 0

    # The fast cursor may be beyond an older late result. The rotating sweep
    # must still append it exactly once without a full-table anti-join.
    store._fixed_target_execution_tail_cursor = 10**9
    first = store.finalize_token_universe_fixed_target_execution()
    assert first["inserted"] == outcome_count
    assert store.finalize_token_universe_fixed_target_execution()["inserted"] == 0
    assert store.db.execute(
        "SELECT COUNT(*) FROM token_universe_fixed_target_execution_results"
    ).fetchone()[0] == outcome_count
