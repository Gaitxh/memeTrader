"""Wave 27 tests: participant facts parsed from the provider payload."""
from memetrader import alpha149
from memetrader import dex_trajectory as dex
from memetrader import participant_flow as pf


def _window(**over):
    base = dict(return_fraction=0.0, liquidity_change_fraction=0.0,
                rolling_volume_change_ratio=1.0, rolling_tx_change_ratio=1.0,
                acceleration=0.0, frames=3, log_velocity=0.0, realized_volatility=0.05,
                start_at="2026-09-11T00:00:00Z", span_seconds=30.0,
                end_at="2026-09-11T00:00:30Z", curvature="FLAT")
    base.update(over)
    return base


def feature(**over):
    base = dict(
        version=dex.VERSION, token_id="solana:T", pair_address="P", chain="solana",
        provider="dexscreener", observed_at="2026-09-11T00:00:30Z",
        ingested_at="2026-09-11T00:00:31Z", recorded_at="2026-09-11T00:00:32Z",
        pool_age_seconds=3600.0, frames=3,
        continuity_started_at="2026-09-11T00:00:00Z",
        liquidity_usd=8000.0, buy_count_share=0.6, drawdown=0.0,
        plateau_fraction=0.0, monotonic_up_fraction=0.0, liquidity_retention=1.0,
        volume_liquidity=0.5, fdv_liquidity=3.0, price_elasticity_proxy=None,
        prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=120.0),
        log_price_r2=None, residual_dispersion=None, jump_interval_cv=None,
        jump_size_cv=None, volume_acceleration_age_normalized=1.0,
        tx_acceleration_age_normalized=1.0, first_dip=None,
        base=None, windows={"15": _window(), "30": _window(), "60": _window(), "180": _window()},
    )
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def test_parser_reads_both_provider_shapes_and_never_invents():
    gecko = {"data": {"attributes": {"transactions": {
        "m5": {"buys": 40, "sells": 20, "buyers": 33, "sellers": 18},
        "h1": {"buys": 900, "sells": 400, "buyers": 500, "sellers": 210}}}}}
    dex_payload = {"pair": {"txns": {"m5": {"buys": 40, "sells": 20}}}}
    wrapped = {"raw": gecko, "cohort_observer": dex_payload}

    gecko_result = pf.extract(gecko)
    assert gecko_result["buyers_5m"] == 33 and gecko_result["sellers_5m"] == 18
    assert gecko_result["participants_per_trade_5m"] == 0.825
    assert pf.net_new_participants_5m(gecko) == 15
    # dexscreener publishes no buyer counts: None, never zero.
    dex_result = pf.extract(dex_payload)
    assert dex_result["buyers_5m"] is None and dex_result["buys_5m"] == 40
    assert pf.net_new_participants_5m(dex_payload) is None
    assert pf.extract(wrapped)["buyers_5m"] == 33
    assert pf.extract({})["buyers_5m"] is None
    assert pf.extract(None)["shapes"] == []
    assert pf.snapshot()["affects"] == "observation_only"


def test_derive_publishes_participant_keys_only_when_observed():
    def row(buyers, at, price=1.0):
        return dict(token_id="solana:T", pair_address="P", chain="solana",
                    provider="dexscreener", price_usd=price, liquidity_usd=8000.0,
                    volume_5m_usd=100.0, buys_5m=10, sells_5m=5, buyers_5m=buyers,
                    pool_age_seconds=3600.0, fdv_usd=24000.0, t=at,
                    observed_at=f"2026-09-11T00:00:{int(at) % 60:02d}Z",
                    ingested_at="2026-09-11T00:00:31Z", recorded_at="2026-09-11T00:00:32Z")

    with_buyers = dex.derive([row(6, 0.0), row(9, 30.0)])
    assert with_buyers["buyers_5m"] == 9
    assert with_buyers["buyers_growth_5m"] == 1.5
    # unique buyers per BUY in the frame (10 buys).
    assert with_buyers["participants_per_trade_5m"] == 0.9
    assert with_buyers["current"]["buyers_5m"] == 9
    # A provider without buyer counts publishes None, and the pre-existing keys are
    # numerically identical to a payload that never carried participants at all.
    without = dex.derive([row(None, 0.0), row(None, 30.0)])
    assert without["buyers_5m"] is None
    assert without["buyers_growth_5m"] is None
    assert without["participants_per_trade_5m"] is None
    assert without["buy_count_share"] == with_buyers["buy_count_share"]
    assert without["liquidity_retention"] == with_buyers["liquidity_retention"]


# --------------------------------------------------------------------------- #
# mechanisms and arms
# --------------------------------------------------------------------------- #

def test_participant_growth_needs_a_real_frame_over_frame_increase():
    rising = feature(buyers_growth_5m=1.5, buy_count_share=0.6)
    assert alpha149.mechanisms(rising)["participant_growth"] is True
    flat = feature(buyers_growth_5m=1.0, buy_count_share=0.6)
    assert alpha149.mechanisms(flat)["participant_growth"] is False
    # Missing observation never triggers (no substituted zero, no inference).
    assert alpha149.mechanisms(feature())["participant_growth"] is False
    # Seller-dominated flow or depth leaving disqualifies it.
    assert alpha149.mechanisms(
        feature(buyers_growth_5m=1.5, buy_count_share=0.4))["participant_growth"] is False
    assert alpha149.mechanisms(
        feature(buyers_growth_5m=1.5, buy_count_share=0.6,
                current=dict(price_usd=1.0, liquidity_usd=7000.0, volume_5m_usd=120.0))
    )["participant_growth"] is False


def test_participant_breadth_is_the_bundling_proxy():
    broad = feature(participants_per_trade_5m=0.75, buy_count_share=0.65)
    assert alpha149.mechanisms(broad)["participant_breadth"] is True
    # Few wallets buying repeatedly is the bundled pattern this arm refuses.
    bundled = feature(participants_per_trade_5m=0.3, buy_count_share=0.65)
    assert alpha149.mechanisms(bundled)["participant_breadth"] is False
    assert alpha149.mechanisms(feature(buy_count_share=0.65))["participant_breadth"] is False


def test_wave27_arms_are_additive_and_declare_their_controls():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p["arm_id"]: p for p in
                alpha149.policies(cohort_experiment_policies()[2])}
    growth = policies["alpha149_participant_growth_v1"]
    breadth = policies["alpha149_participant_breadth_v1"]
    assert alpha149.SPECS["alpha149_participant_growth_v1"][0] == "participant_growth"
    assert alpha149.SPECS["alpha149_participant_breadth_v1"][0] == "participant_breadth"
    assert growth["notional_usd"] == 2.0 and breadth["notional_usd"] == 1.0
    assert growth["excess_return_vs_arm"] == "alpha149_size_informed_flow_v1"
    for arm, policy in (("growth", growth), ("breadth", breadth)):
        assert policy["trajectory_engine"] == "alpha149"
        assert policy["paired_opportunity_group"] == "alpha149_v1"
        assert policy["affects"] == "paper_only"
    # The proxy arm it must beat is untouched.
    assert policies["alpha149_size_informed_flow_v1"]["notional_usd"] == 2.0
    assert "participant_growth" in alpha149.RULES
    assert "不是钱包簇证据" in alpha149.RULES["participant_breadth"]
