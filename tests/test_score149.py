"""SCORE149 tests: pure, as-of, missing-is-unknown, coverage-aware gating."""
from memetrader import score149


def vector(**over):
    base = dict(
        pool_age_seconds=3600.0, fdv_liquidity=3.0, buy_count_share=0.6,
        drawdown=-0.02, liquidity_retention=1.0, log_price_r2=0.8,
        volume_acceleration_age_normalized=1.5, tx_acceleration_age_normalized=1.5,
        current=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=120.0),
        windows={"30": dict(rolling_volume_change_ratio=1.6, rolling_tx_change_ratio=1.1,
                            liquidity_change_fraction=0.0, log_velocity=0.02,
                            realized_volatility=0.05),
                 "60": dict(log_velocity=0.01)},
    )
    base.update(over)
    return base


def test_score_is_bounded_and_reports_every_dimension():
    result = score149.score(vector())
    assert result["version"] == score149.VERSION
    assert 0.0 <= result["score"] <= 100.0
    assert result["coverage"] == 1.0
    assert result["missing_dimensions"] == []
    assert set(result["parts"]) == set(score149.WEIGHTS)
    assert abs(sum(score149.WEIGHTS.values()) - 1.0) < 1e-9


def test_missing_dimensions_lower_coverage_instead_of_scoring():
    """A vector with no windows must not be scored as if it were neutral."""
    empty = score149.score(dict(current=dict(price_usd=1.0, liquidity_usd=8000.0),
                                buy_count_share=0.6, fdv_liquidity=3.0,
                                pool_age_seconds=3600.0))
    assert empty["coverage"] < 1.0
    assert empty["missing_dimensions"]
    ok, result = score149.passes(dict(current=dict(price_usd=1.0)),
                                 minimum=0.0, minimum_coverage=score149.COVERAGE_MIN)
    assert ok is False, "coverage floor must reject a mostly-unobserved candidate"
    assert result["coverage"] < score149.COVERAGE_MIN
    blank = score149.score({})
    assert blank["score"] is None and blank["coverage"] == 0.0


def test_score_rises_with_the_facts_it_claims_to_measure():
    weak = score149.score(vector(buy_count_share=0.4, fdv_liquidity=200.0,
                                 pool_age_seconds=120.0, drawdown=-0.5,
                                 liquidity_retention=0.5,
                                 volume_acceleration_age_normalized=0.5,
                                 tx_acceleration_age_normalized=0.5))
    strong = score149.score(vector(buy_count_share=0.75, fdv_liquidity=3.0,
                                   pool_age_seconds=3600.0, drawdown=0.0,
                                   liquidity_retention=1.0,
                                   volume_acceleration_age_normalized=2.5,
                                   tx_acceleration_age_normalized=2.5,
                                   windows={"30": dict(rolling_volume_change_ratio=2.0,
                                                       rolling_tx_change_ratio=1.1,
                                                       liquidity_change_fraction=0.0,
                                                       log_velocity=0.12),
                                            "60": dict(log_velocity=0.02)}))
    assert strong["score"] > weak["score"] + 25.0
    # The measured write-off band is bounded on BOTH sides: a huge FDV/depth and a
    # very young pool both lose structure points.
    assert strong["parts"]["structure"] > weak["parts"]["structure"]


def test_liquidity_withdrawal_vetoes_the_risk_dimension():
    withdrawn = score149.score(vector(windows={"30": dict(
        rolling_volume_change_ratio=1.6, rolling_tx_change_ratio=1.1,
        liquidity_change_fraction=-0.30, log_velocity=0.02), "60": dict(log_velocity=0.01)}))
    assert withdrawn["parts"]["risk"] == 0.0
    healthy = score149.score(vector())
    assert healthy["parts"]["risk"] > 0.0


def test_gate_requires_both_score_and_coverage():
    strong = vector(buy_count_share=0.72, liquidity_retention=1.0,
                    volume_acceleration_age_normalized=2.2,
                    tx_acceleration_age_normalized=2.2,
                    windows={"30": dict(rolling_volume_change_ratio=2.0,
                                        rolling_tx_change_ratio=1.1,
                                        liquidity_change_fraction=0.0,
                                        log_velocity=0.15), "60": dict(log_velocity=0.02)})
    ok, result = score149.passes(strong)
    assert result["score"] >= score149.SCORE_MIN and ok is True
    ok_low, result_low = score149.passes(vector(buy_count_share=0.36, fdv_liquidity=300.0,
                                                pool_age_seconds=60.0, drawdown=-0.45,
                                                liquidity_retention=0.4))
    assert ok_low is False and result_low["score"] < score149.SCORE_MIN
    # A vector missing a REQUIRED dimension cannot pass, however high the rest is.
    partial = dict(strong)
    partial.pop("drawdown")
    partial.pop("log_price_r2")
    ok_partial, result_partial = score149.passes(partial)
    assert ok_partial is False
    assert "risk" in result_partial["missing_required"]
    assert result_partial["coverage"] >= score149.COVERAGE_MIN
    # The window dimensions are NOT required: measured p50 is one frame per pool,
    # so requiring them would starve the gate exactly like the wave-21 strict rise.
    no_windows = dict(strong)
    no_windows.pop("windows")
    ok_nowindow, result_nowindow = score149.passes(no_windows)
    assert ok_nowindow is True and "momentum" in result_nowindow["missing_dimensions"]
    assert result_nowindow["missing_required"] == []


def test_unavailable_dimensions_are_declared_not_inferred():
    """The requested social/holder dimensions have no source and must be listed."""
    for name in ("top_holder_change", "holder_concentration", "new_holder_growth",
                 "bundling", "social_mention_velocity", "kol_mentions", "sentiment",
                 "historical_rug_links", "large_trade_direction"):
        assert name in score149.UNAVAILABLE
    assert not set(score149.UNAVAILABLE) & set(score149.WEIGHTS)
    assert score149.snapshot()["affects"] == "observation_only"
