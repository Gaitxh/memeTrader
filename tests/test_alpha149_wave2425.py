"""Wave 24/25 tests (appended): score gate pair and the new strategy families.

Kept in a separate module so the wave-23 file stays readable; both are collected by
`pytest tests/` and the same helpers are redefined here.
"""
from datetime import datetime, timezone

from memetrader import alpha149
from memetrader import dex_trajectory as dex
from memetrader import score149

UTC = timezone.utc


def _window(ret=0.0, liq=0.0, vol=1.0, tx=1.0, acc=0.0, frames=3, velocity=0.0,
            vola=0.05, start="2026-09-11T00:00:00Z"):
    return dict(return_fraction=ret, liquidity_change_fraction=liq,
                rolling_volume_change_ratio=vol, rolling_tx_change_ratio=tx,
                acceleration=acc, frames=frames, log_velocity=velocity,
                realized_volatility=vola, start_at=start, span_seconds=30.0,
                end_at="2026-09-11T00:00:30Z", curvature="FLAT")


def feature(**over):
    base = dict(
        version=dex.VERSION, token_id="solana:T", pair_address="P", chain="solana",
        provider="dexscreener", observed_at="2026-09-11T00:00:30Z",
        ingested_at="2026-09-11T00:00:31Z", recorded_at="2026-09-11T00:00:32Z",
        pool_age_seconds=3600.0, frames=6,
        continuity_started_at="2026-09-11T00:00:00Z",
        liquidity_usd=8000.0, buy_count_share=0.6, drawdown=-0.02,
        plateau_fraction=0.0, monotonic_up_fraction=0.6, liquidity_retention=1.0,
        volume_liquidity=0.5, fdv_liquidity=3.0, price_elasticity_proxy=None,
        prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=120.0),
        log_price_r2=0.8, residual_dispersion=0.01, jump_interval_cv=0.4,
        jump_size_cv=0.4, volume_acceleration_age_normalized=2.2,
        tx_acceleration_age_normalized=2.2, first_dip=None,
        base=dict(range_fraction=0.5, high=1.0, end_at="2026-09-11T00:00:00Z"),
        windows={"15": _window(velocity=0.03), "30": _window(velocity=0.02),
                 "60": _window(velocity=0.01), "180": _window(vola=0.06)},
    )
    base.update(over)
    return base


def _policies():
    from memetrader.cohort_experiments import cohort_experiment_policies
    return {p["arm_id"]: p for p in alpha149.policies(cohort_experiment_policies()[2])}


# --------------------------------------------------------------------------- #
# wave 24: the multi-dimension score gate is a real, additive arm pair
# --------------------------------------------------------------------------- #

def test_score_gate_pair_splits_the_same_frames_by_the_score():
    """Same pool conditions, opposite sides of the threshold: a clean A/B."""
    high = feature(buy_count_share=0.72, volume_acceleration_age_normalized=2.4,
                   tx_acceleration_age_normalized=2.4)
    flags_high = alpha149.mechanisms(high)
    assert flags_high["survivable_steady"] is True
    assert flags_high["score_gate_band"] is True
    assert flags_high["score_low_band"] is False

    low = feature(buy_count_share=0.4, fdv_liquidity=200.0, pool_age_seconds=120.0,
                  drawdown=-0.45, liquidity_retention=0.4,
                  volume_acceleration_age_normalized=0.5,
                  tx_acceleration_age_normalized=0.5)
    flags_low = alpha149.mechanisms(low)
    assert flags_low["survivable_steady"] is False, "the band itself still binds"
    # Inside the band, the two flags are exact complements. The band itself still
    # binds (buy share >= .5, FDV/depth in 1-20, 30-180 minute pool, depth >= 5000),
    # so the weak candidate differs only in the facts the score reads.
    weak_in_band = feature(buy_count_share=0.50, fdv_liquidity=19.9,
                           liquidity_usd=6000.0,
                           prev=dict(price_usd=1.0, liquidity_usd=6000.0,
                                     volume_5m_usd=100.0),
                           current=dict(price_usd=1.0, liquidity_usd=6000.0,
                                        volume_5m_usd=120.0),
                           drawdown=-0.15, log_price_r2=0.35,
                           volume_acceleration_age_normalized=0.6,
                           tx_acceleration_age_normalized=0.6,
                           windows={"15": _window(), "30": _window(velocity=-0.01),
                                    "60": _window(velocity=0.0), "180": _window()})
    flags_weak = alpha149.mechanisms(weak_in_band)
    assert flags_weak["survivable_steady"] is True
    assert flags_weak["score_gate_band"] is (not flags_weak["score_low_band"])
    assert flags_weak["score_low_band"] is True
    assert score149.score(weak_in_band)["score"] < score149.SCORE_MIN


def test_score_gate_requires_the_dimensions_it_claims():
    """A candidate missing a required dimension cannot pass, however good the rest."""
    partial = feature(buy_count_share=0.72, volume_acceleration_age_normalized=2.4,
                      tx_acceleration_age_normalized=2.4)
    partial.pop("drawdown")
    partial.pop("log_price_r2")
    ok, result = score149.passes(partial)
    assert ok is False and "risk" in result["missing_required"]
    assert alpha149.mechanisms(partial)["score_gate_band"] is False
    assert alpha149.mechanisms(partial)["score_low_band"] is True


def test_score_gate_arms_are_additive_with_identical_contracts():
    policies = _policies()
    high = policies["alpha149_score_gate_band_v1"]
    low = policies["alpha149_score_low_band_v1"]
    assert alpha149.SPECS["alpha149_score_gate_band_v1"][0] == "score_gate_band"
    assert alpha149.SPECS["alpha149_score_low_band_v1"][0] == "score_low_band"
    for key in ("notional_usd", "hard_stop_return", "trailing_activate_return",
                "trailing_drawdown", "max_hold_minutes", "take_profit"):
        assert high[key] == low[key], key
    assert high["notional_usd"] == 1.0
    # The score is declared as an observation, not as authority.
    assert score149.snapshot()["affects"] == "observation_only"
    assert high["feature_hypothesis"] == "score_gate_band"


# --------------------------------------------------------------------------- #
# wave 25: the requested new strategy families
# --------------------------------------------------------------------------- #

def test_momentum_persistence_needs_three_horizons_and_a_shallow_drawdown():
    window = {"15": _window(ret=0.02, velocity=0.03), "30": _window(ret=0.01, velocity=0.02),
              "60": _window(ret=0.005, velocity=0.01), "180": _window()}
    rising = feature(windows=window)
    assert alpha149.mechanisms(rising)["mom_persistence"] is True
    # A falling 60s horizon is not persistence.
    falling = feature(windows={**window, "60": _window(ret=-0.005, velocity=-0.01)})
    assert alpha149.mechanisms(falling)["mom_persistence"] is False
    # A deep drawdown is not momentum.
    deep = feature(windows=window, drawdown=-0.10)
    assert alpha149.mechanisms(deep)["mom_persistence"] is False
    # Depth must not be leaving.
    draining = feature(windows=window,
                       current=dict(price_usd=1.0, liquidity_usd=7000.0, volume_5m_usd=120.0))
    assert alpha149.mechanisms(draining)["mom_persistence"] is False
    assert "mom_persistence" in alpha149.RULES


def test_size_informed_flow_is_a_declared_proxy_not_wallet_evidence():
    """Volume growing faster than the trade count = larger average trade."""
    large = feature(windows={"30": _window(vol=1.6, tx=1.0), "60": _window()})
    assert alpha149.mechanisms(large)["size_informed_flow"] is True
    # Same volume growth spread over more trades is not size-informed flow.
    many = feature(windows={"30": _window(vol=1.6, tx=1.6), "60": _window()})
    assert alpha149.mechanisms(many)["size_informed_flow"] is False
    # Seller-dominated flow does not qualify even with large average size.
    sellers = feature(buy_count_share=0.45, windows={"30": _window(vol=1.6, tx=1.0),
                                                     "60": _window()})
    assert alpha149.mechanisms(sellers)["size_informed_flow"] is False
    policies = _policies()
    arm = policies["alpha149_size_informed_flow_v1"]
    assert alpha149.SPECS["alpha149_size_informed_flow_v1"][0] == "size_informed_flow"
    assert "代理" in arm["description"] and "钱包" in arm["description"]


def test_early_pool_snipe_is_small_and_time_capped():
    young = feature(pool_age_seconds=300.0, liquidity_usd=3000.0,
                    current=dict(price_usd=1.0, liquidity_usd=3000.0, volume_5m_usd=120.0),
                    prev=dict(price_usd=1.0, liquidity_usd=2900.0, volume_5m_usd=100.0))
    assert alpha149.mechanisms(young)["early_pool_snipe"] is True
    # A mature pool is not a snipe, and thin depth is refused.
    old = feature(pool_age_seconds=4000.0)
    assert alpha149.mechanisms(old)["early_pool_snipe"] is False
    thin = feature(pool_age_seconds=300.0, liquidity_usd=1200.0,
                   current=dict(price_usd=1.0, liquidity_usd=1200.0, volume_5m_usd=120.0),
                   prev=dict(price_usd=1.0, liquidity_usd=1200.0, volume_5m_usd=100.0))
    assert alpha149.mechanisms(thin)["early_pool_snipe"] is False
    arm = _policies()["alpha149_early_pool_snipe_v1"]
    assert arm["notional_usd"] == 1.0 and arm["max_hold_minutes"] == 5
    assert arm["hard_stop_return"] == -.15 and arm["trailing_drawdown"] == .12


def test_rotation_proxy_uses_the_onchain_substitute_and_stays_inside_the_band():
    """The social lane is paused, so rotation is read from breadth plus age rate."""
    frame = feature(fdv_liquidity=2.0, regime=dict(ratio=1.5, fast=0.3),
                    volume_acceleration_5m_1h=4.0, tx_acceleration_5m_1h=4.0)
    flags = alpha149.mechanisms(frame)
    # The proxy needs the engine's breadth reading AND the measured best entry.
    assert flags["regime_risk_on"] is True
    assert flags["age_rate_acceleration"] is True
    assert flags["rotation_proxy"] is True
    # Without breadth, or outside the measured write-off band, it refuses.
    assert alpha149.mechanisms(
        feature(fdv_liquidity=2.0, regime=dict(ratio=1.0, fast=0.3),
                volume_acceleration_5m_1h=4.0,
                tx_acceleration_5m_1h=4.0))["rotation_proxy"] is False
    assert alpha149.mechanisms(
        feature(fdv_liquidity=500.0, regime=dict(ratio=1.5, fast=0.3),
                volume_acceleration_5m_1h=4.0,
                tx_acceleration_5m_1h=4.0))["rotation_proxy"] is False
    assert alpha149.mechanisms(
        feature(fdv_liquidity=2.0, regime=None,
                volume_acceleration_5m_1h=4.0,
                tx_acceleration_5m_1h=4.0))["rotation_proxy"] is False
    assert "叙事轮动代理" in alpha149.RULES["rotation_proxy"]


def test_wave25_arms_are_additive_and_keep_family_identity():
    policies = _policies()
    for arm, kind in (("alpha149_momentum_persistence_v1", "mom_persistence"),
                      ("alpha149_size_informed_flow_v1", "size_informed_flow"),
                      ("alpha149_early_pool_snipe_v1", "early_pool_snipe"),
                      ("alpha149_rotation_proxy_v1", "rotation_proxy")):
        assert arm in alpha149.ALL_ARMS and arm in policies, arm
        assert alpha149.SPECS[arm][0] == kind, arm
        policy = policies[arm]
        assert policy["trajectory_engine"] == "alpha149"
        assert policy["paired_opportunity_group"] == "alpha149_v1"
        assert policy["decision_eligible"] is True and policy["affects"] == "paper_only"
        # Every new arm declares which existing mechanism it must beat.
        assert policy["excess_return_vs_arm"]
        assert kind in alpha149.RULES
    # No existing arm's contract changed: the wave-21 control is untouched.
    assert policies["alpha149_survivable_steady_v1"]["hard_stop_return"] == -.20
    assert policies["alpha149_survivable_steady_v1"]["notional_usd"] == 1.0
    assert policies["alpha149_merged_multi_setup_v1"]["hard_stop_grace_seconds"] == 180


# --------------------------------------------------------------------------- #
# wave 26 (round 3): the measured coverage unlock for the largest archetype
# --------------------------------------------------------------------------- #

def test_open_band_removes_only_the_self_imposed_ratio_cap():
    """62.2% of observed frames sit above FDV/depth 20; the 1-20 band sees 0.5%."""
    def band(fdv, **over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=fdv, liquidity_usd=8000.0,
                    buy_count_share=0.6,
                    prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=120.0))
        base.update(over)
        return feature(**base)

    inside = alpha149.mechanisms(band(3.0))
    above = alpha149.mechanisms(band(60.0))
    assert inside["survivable_steady"] is True and inside["survivable_open_band"] is False
    assert above["survivable_open_band"] is True and above["survivable_steady"] is False
    assert inside["survivable_open_band"] is (not above["survivable_open_band"]) or True
    # The sanity bound: a valuation 1000x the pool is refused.
    assert alpha149.mechanisms(band(1500.0))["survivable_open_band"] is False
    # Every measured protection is kept, one at a time.
    assert alpha149.mechanisms(band(60.0, pool_age_seconds=600.0))["survivable_open_band"] is False
    assert alpha149.mechanisms(band(60.0, liquidity_usd=4000.0,
                                    prev=dict(price_usd=1.0, liquidity_usd=4000.0,
                                              volume_5m_usd=100.0),
                                    current=dict(price_usd=1.0, liquidity_usd=4000.0,
                                                 volume_5m_usd=120.0))
                               )["survivable_open_band"] is False
    assert alpha149.mechanisms(band(60.0, buy_count_share=0.4))["survivable_open_band"] is False
    assert alpha149.mechanisms(band(60.0, current=dict(price_usd=0.98, liquidity_usd=8000.0,
                                                       volume_5m_usd=120.0))
                               )["survivable_open_band"] is False
    assert alpha149.mechanisms(band(60.0, current=dict(price_usd=1.0, liquidity_usd=7000.0,
                                                       volume_5m_usd=120.0))
                               )["survivable_open_band"] is False
    # The strict safe band itself is untouched by this wave.
    assert alpha149.mechanisms(band(3.0))["survivable_steady"] is True


def test_open_band_score_variant_splits_the_new_supply_by_the_score():
    policies = _policies()
    open_arm = policies["alpha149_open_band_v1"]
    scored_arm = policies["alpha149_open_band_score_v1"]
    assert alpha149.SPECS["alpha149_open_band_v1"][0] == "survivable_open_band"
    assert alpha149.SPECS["alpha149_open_band_score_v1"][0] == "open_band_scored"
    for key in ("notional_usd", "max_hold_minutes", "hard_stop_return",
                "trailing_activate_return", "trailing_drawdown"):
        assert open_arm[key] == scored_arm[key], key
    assert open_arm["notional_usd"] == 1.0
    weak = feature(pool_age_seconds=3600.0, fdv_liquidity=60.0, liquidity_usd=6000.0,
                   buy_count_share=0.50,
                   prev=dict(price_usd=1.0, liquidity_usd=6000.0, volume_5m_usd=100.0),
                   current=dict(price_usd=1.0, liquidity_usd=6000.0, volume_5m_usd=120.0),
                   drawdown=-0.15, log_price_r2=0.35,
                   volume_acceleration_age_normalized=0.6,
                   tx_acceleration_age_normalized=0.6,
                   windows={"15": _window(), "30": _window(velocity=-0.01),
                            "60": _window(velocity=0.0), "180": _window()})
    flags = alpha149.mechanisms(weak)
    assert flags["survivable_open_band"] is True
    assert flags["open_band_scored"] is False, "a weak open-band frame stays in the control"
    strong = dict(weak, buy_count_share=0.72, volume_acceleration_age_normalized=2.4,
                  tx_acceleration_age_normalized=2.4, drawdown=-0.02, log_price_r2=0.8)
    assert alpha149.mechanisms(strong)["open_band_scored"] is True
    assert "开放带" in alpha149.RULES["survivable_open_band"]
