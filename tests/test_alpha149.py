"""ALPHA149 tests: additive arms in an isolated engine; shared family untouched.

Covers: engine isolation, mechanism triggers, missing-input safety, causal exit
guards, per-arm sizing overrides and policy identity.
"""
from datetime import datetime, timedelta, timezone

from memetrader import alpha149
from memetrader import dex_trajectory as dex

UTC = timezone.utc


def _w(ret=0.0, liq=-0.5, vol=0.5, tx=0.5, acc=0.0, frames=3, velocity=0.0,
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
        pool_age_seconds=600.0, frames=3,
        continuity_started_at="2026-09-11T00:00:00Z",
        liquidity_usd=5000.0, buy_count_share=0.5, drawdown=0.0,
        plateau_fraction=0.0, monotonic_up_fraction=0.0, liquidity_retention=1.0,
        volume_liquidity=0.0, fdv_liquidity=1000.0, price_elasticity_proxy=None,
        current=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0,
                     buys_5m=10.0, sells_5m=5.0,
                     observed_at="2026-09-11T00:00:30Z"),
        log_price_r2=None, residual_dispersion=None, jump_interval_cv=None,
        jump_size_cv=None, volume_acceleration_age_normalized=1.0,
        tx_acceleration_age_normalized=1.0, first_dip=None,
        base=dict(range_fraction=0.5, high=1.0, end_at="2026-09-11T00:00:00Z"),
        windows={"15": _w(), "30": _w(), "60": _w(), "180": _w(vola=0.06)},
    )
    base.update(over)
    return base


def triggered(f):
    return {kind for kind, hit in alpha149.mechanisms(f).items() if hit}


# wave 8: arm -> the entry kind it reuses. Every one of these arms is a NEW id;
# the mechanism it selects is an existing frozen kind, so the only variable is
# the exit contract (grace, mark confirmation, stop width, trailing).
WAVE8_ENTRY_KINDS = {
    "alpha149_survive_noise_wide_v1": "df_price_up_liquidity_up",
    "alpha149_survive_noise_confirm_v1": "df_price_up_liquidity_up",
    "alpha149_merged_multi_setup_v1": "merged_multi_setup",
    "alpha149_merged_multi_setup_fast_v1": "merged_multi_setup",
    "alpha149_goldendog_deep_hold_v1": "sf_goldendog_deep_base",
}


def _policy_base():
    from memetrader.cohort_experiments import cohort_experiment_policies
    return cohort_experiment_policies()[2]


# --------------------------------------------------------------------------- #
# 1. isolation: the shared family must not learn about ALPHA149
# --------------------------------------------------------------------------- #

def test_shared_family_has_no_alpha149_arms():
    assert not [arm for arm in dex.SPECS if arm.startswith("alpha149_")]
    assert not [arm for arm in dex.EXIT_ARMS if arm.startswith("alpha149_")]
    assert not [k for k in dex.mechanisms(feature()) if k.startswith("alpha149_")]
    for kind in alpha149.EXIT_KINDS:
        assert dex.exit_reason(kind, feature(), datetime(2026, 9, 11, tzinfo=UTC),
                               datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)) is None
    assert not [p["arm_id"] for p in dex.policies(_policy_base())
                if p["arm_id"].startswith("alpha149_")]


def test_shared_engine_output_has_no_alpha149_signals():
    clock = [datetime(2026, 9, 11, tzinfo=UTC)]
    engine = dex.Engine(clock[0])
    row = dict(token_id="solana:T", pair_address="P", chain="solana",
               provider="dexscreener", price_usd=1.0, liquidity_usd=5000.0,
               volume_5m_usd=100.0, buys_5m=10, sells_5m=2, pool_age_seconds=120.0,
               observed_at="2026-09-11T00:00:00Z", ingested_at="2026-09-11T00:00:01Z",
               recorded_at="2026-09-11T00:00:02Z")
    clock[0] += timedelta(seconds=5)
    engine.accept(row, clock[0])
    signals = engine.signals_for("solana:T", "P", clock[0])
    assert not [arm for arm in signals if arm.startswith("alpha149_")]


def test_alpha149_engine_emits_only_its_own_arms():
    clock = [datetime(2026, 9, 11, tzinfo=UTC)]
    engine = alpha149.Engine(clock[0])
    row = dict(token_id="solana:T", pair_address="P", chain="solana",
               provider="dexscreener", price_usd=1.0, liquidity_usd=5000.0,
               volume_5m_usd=100.0, buys_5m=10, sells_5m=2, pool_age_seconds=120.0,
               observed_at="2026-09-11T00:00:00Z", ingested_at="2026-09-11T00:00:01Z",
               recorded_at="2026-09-11T00:00:02Z")
    clock[0] += timedelta(seconds=5)
    engine.accept(row, clock[0])
    signals = engine.signals_for("solana:T", "P", clock[0])
    assert all(arm in alpha149.ALL_ARMS for arm in signals)
    snap = engine.snapshot()
    assert snap["version"] == alpha149.VERSION and snap["extra_requests"] == 0


def test_wave8_arms_are_reachable_through_the_live_engine_path():
    """The new arms must be emittable by the real engine, not only by the pure
    mechanism function: this drives frames through Engine.accept/signals_for."""
    clock = [datetime(2026, 9, 11, tzinfo=UTC)]
    engine = alpha149.Engine(clock[0])

    def row(price, liquidity, volume, at):
        return dict(token_id="solana:T", pair_address="P", chain="solana",
                    provider="dexscreener", price_usd=price, liquidity_usd=liquidity,
                    volume_5m_usd=volume, buys_5m=12, sells_5m=2, pool_age_seconds=600.0,
                    observed_at=at, ingested_at=at, recorded_at=at)

    # Two consecutive rising frames with liquidity added: the frozen
    # `df_price_up_liquidity_up` member is what both wave-8 A/B pairs reuse.
    for step, at in enumerate(("2026-09-11T00:00:00Z", "2026-09-11T00:00:30Z")):
        clock[0] = datetime(2026, 9, 11, tzinfo=UTC) + timedelta(seconds=1 + 30 * step)
        engine.accept(row(1.0 + 0.05 * step, 5000.0 + 500.0 * step, 100.0 + 20.0 * step, at),
                      clock[0])
    clock[0] = datetime(2026, 9, 11, tzinfo=UTC) + timedelta(seconds=32)
    signals = engine.signals_for("solana:T", "P", clock[0])
    for arm in ("alpha149_survive_noise_wide_v1", "alpha149_survive_noise_confirm_v1",
                "alpha149_merged_multi_setup_v1", "alpha149_merged_multi_setup_fast_v1"):
        assert arm in signals, arm
        assert signals[arm]["decision_evidence"]["mode"] in (
            "df_price_up_liquidity_up", "merged_multi_setup")
    snap = engine.snapshot()
    assert snap["signals"]["alpha149_merged_multi_setup_v1"] >= 1
    assert "merged_multi_setup" in snap["mechanism_ready"]



# --------------------------------------------------------------------------- #
# 2. new arms exist and are correctly shaped
# --------------------------------------------------------------------------- #

def test_new_arms_are_shaped_and_isolated_by_engine_field():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    assert set(policies) == set(alpha149.ALL_ARMS)
    for arm, policy in policies.items():
        assert policy["paired_opportunity_group"] == "alpha149_v1"
        assert policy["requires_distinct_trajectory_frame"] is True
        assert policy["decision_eligible"] is True and policy["affects"] == "paper_only"
        assert policy["assessment_status"] == "INSUFFICIENT"
        assert policy["feature_contract"] == alpha149.VERSION
        assert policy["entry_filter"]["direction"] == arm
        assert policy["trajectory_engine"] == "alpha149"
    step = policies["alpha149_step_pump_fast_v1"]
    assert (step["notional_usd"], step["entry_filter"]["max_concurrent_positions"]) == (1.0, 1)
    assert step["absolute_max_hold_seconds"] == 300
    assert policies["alpha149_friction_multiple_escape_v1"]["hard_stop_return"] == -.12
    assert policies["alpha149_elasticity_anomaly_fast_v1"]["notional_usd"] == 1.0
    for arm in alpha149.EXIT_ARMS:
        assert policies[arm]["trajectory_exit"] == alpha149.EXIT_ARMS[arm]


def test_every_new_arm_has_a_mechanism_or_exit_kind():
    assert set(alpha149.KINDS) == {kind for kind, _n, _h in alpha149.SPECS.values()}
    assert alpha149.EXIT_KINDS == set(alpha149.EXIT_ARMS.values())
    assert len(alpha149.ALL_ARMS) == len(set(alpha149.ALL_ARMS))


def test_store_routes_trajectory_engine_by_policy_field(tmp_path):
    """Wiring: 'v144' -> trajectory144, 'alpha149' -> new isolated engine, else dex."""
    from memetrader.store import Store
    store = Store(tmp_path / "route.sqlite3", initial_cash_usd=1000)
    try:
        assert store._trajectory_engine_for({"trajectory_engine": "alpha149"}).__class__ \
            is alpha149.Engine
        assert store._trajectory_engine_for({"trajectory_engine": "v144"}) is \
            getattr(store, "_trajectory144", None)
        assert store._trajectory_engine_for({}) is None
    finally:
        store.db.close()


# --------------------------------------------------------------------------- #
# 3. missing inputs must never trigger anything
# --------------------------------------------------------------------------- #

def test_missing_inputs_never_trigger():
    for f in (None, {}, {"windows": {}}, feature(windows={}),
              feature(liquidity_usd=None), feature(liquidity_usd=999.0),
              feature(windows={"30": {"frames": 1}})):
        assert triggered(f) == set(), f


# --------------------------------------------------------------------------- #
# 4. each mechanism fires on its own vector
# --------------------------------------------------------------------------- #

CASES = {
    "uncrowded_first_frame": dict(frames=4,
        windows={"15": _w(), "30": _w(ret=0.02, liq=0.0), "60": _w(), "180": _w()}),
    "age_normalized_ignition": dict(
        windows={"15": _w(), "30": _w(ret=0.06, liq=0.0), "60": _w(), "180": _w()},
        volume_acceleration_age_normalized=1.4, tx_acceleration_age_normalized=1.3),
    "liquidity_expansion_lead": dict(buy_count_share=0.6,
        windows={"15": _w(), "30": _w(ret=0.01, liq=0.12), "60": _w(), "180": _w()}),
    "plateau_ignition": dict(plateau_fraction=0.6,
        windows={"15": _w(), "30": _w(ret=0.02, liq=0.0, vol=2.0, tx=2.0, vola=0.05),
                 "60": _w(), "180": _w()}),
    "step_pump_fast": dict(monotonic_up_fraction=0.8, jump_interval_cv=0.5,
        jump_size_cv=0.8, liquidity_retention=0.99, pool_age_seconds=900.0,
        windows={"15": _w(), "30": _w(ret=0.01, liq=0.0), "60": _w(), "180": _w()}),
    "buy_share_extreme": dict(buy_count_share=0.8,
        tx_acceleration_age_normalized=1.5,
        windows={"15": _w(), "30": _w(ret=0.01, liq=0.0), "60": _w(), "180": _w()}),
    "liquidity_add_dip_recovery": dict(first_dip=dict(liquidity_retention=1.1,
        volume_ratio=1.3, recovery_seconds=20.0, decline_seconds=40.0),
        windows={"15": _w(), "30": _w(ret=0.01, liq=0.0), "60": _w(), "180": _w()}),
    "gap_repair_continuation": dict(continuity_started_at="2026-09-11T00:00:00Z",
        windows={"15": _w(), "30": _w(ret=0.02, liq=-0.1), "60": _w(), "180": _w()}),
    "friction_multiple_escape": dict(liquidity_usd=6000.0, volume_liquidity=1.5,
        windows={"15": _w(), "30": _w(ret=0.30, liq=-0.05), "60": _w(), "180": _w()}),
    "multiframe_trend_confirm": dict(frames=6, log_price_r2=0.9,
        residual_dispersion=0.02,
        windows={"15": _w(), "30": _w(ret=0.20, liq=0.0, frames=6), "60": _w(), "180": _w()}),
    "organic_short_burst": dict(buy_count_share=0.6,
        windows={"15": _w(ret=0.06, tx=1.5), "30": _w(), "60": _w(), "180": _w()}),
    "writeoff_structure_avoid": dict(fdv_liquidity=200.0,
        windows={"15": _w(), "30": _w(ret=0.02, liq=0.0), "60": _w(), "180": _w()}),
    "mature_revival": dict(pool_age_seconds=25200.0,
        volume_acceleration_age_normalized=1.5,
        windows={"15": _w(), "30": _w(ret=0.20, liq=0.0), "60": _w(), "180": _w()}),
    "turnover_surge": dict(volume_liquidity=3.0,
        windows={"15": _w(), "30": _w(ret=0.01, liq=0.0, vol=2.0, tx=2.0), "60": _w(), "180": _w()}),
    "multi_horizon_agreement": dict(
        windows={"15": _w(ret=0.05), "30": _w(ret=0.08, liq=0.0, velocity=0.01),
                 "60": _w(ret=0.10, velocity=0.005), "180": _w()}),
    "shallow_drawdown_impulse": dict(drawdown=-0.01, frames=4,
        windows={"15": _w(), "30": _w(ret=0.20, liq=0.0, frames=4), "60": _w(), "180": _w()}),
    "elasticity_anomaly_fast": dict(price_elasticity_proxy=12.0, liquidity_usd=9000.0,
        buy_count_share=0.6,
        windows={"15": _w(), "30": _w(ret=0.20, liq=-0.2), "60": _w(), "180": _w()}),
    "squeeze_release": dict(
        windows={"15": _w(vola=0.20), "30": _w(ret=0.02, liq=0.0), "60": _w(),
                 "180": _w(vola=0.05)}),
    "smooth_organic_trend": dict(plateau_fraction=0.1, monotonic_up_fraction=0.7,
        log_price_r2=0.7, residual_dispersion=0.03,
        windows={"15": _w(), "30": _w(ret=0.02, liq=0.0), "60": _w(), "180": _w()}),
    # wave 3
    "goldendog_early_impulse": dict(pool_age_seconds=300.0, buy_count_share=0.6,
        windows={"15": _w(), "30": _w(ret=0.20, liq=0.0), "60": _w(), "180": _w()}),
    "goldendog_shallow_stack": dict(
        windows={"15": _w(velocity=0.03), "30": _w(ret=0.05, liq=0.0, velocity=0.02),
                 "60": _w(velocity=0.01), "180": _w()}),
    "goldendog_second_leg": dict(
        windows={"15": _w(ret=0.02, velocity=0.01), "30": _w(),
                 "60": _w(ret=0.02), "180": _w(ret=0.30)}),
    "young_fast_lane": dict(pool_age_seconds=90.0, liquidity_usd=2000.0,
        windows={"15": _w(ret=0.03, frames=3), "30": _w(), "60": _w(), "180": _w()}),
    "two_frame_quick_entry": dict(liquidity_usd=3000.0,
        windows={"15": _w(ret=0.06, frames=2, liq=0.0), "30": _w(liq=0.0), "60": _w(), "180": _w()}),
    "live_flow_revival": dict(buy_count_share=0.7,
        windows={"15": _w(), "30": _w(ret=0.02, liq=0.0, vol=2.0, tx=2.0), "60": _w(), "180": _w()}),
    "baseline_free_absolute": dict(volume_liquidity=1.5, liquidity_usd=4000.0,
        windows={"15": _w(), "30": _w(ret=0.10, liq=0.0), "60": _w(), "180": _w()}),
    "depth_first_mature": dict(pool_age_seconds=3600.0, liquidity_usd=12000.0,
        volume_liquidity=0.8,
        windows={"15": _w(), "30": _w(ret=0.03, liq=0.0), "60": _w(), "180": _w()}),
    # wave 4: single/two-frame mechanisms, tested with NO 30-second window
    "sf_deep_low_fdv": dict(liquidity_usd=6000.0, fdv_liquidity=0.5,
        buy_count_share=0.6, windows={}),
    "sf_extreme_buy_pressure": dict(buy_count_share=0.95, liquidity_usd=2500.0,
        volume_liquidity=0.2, windows={}),
    "sf_young_turnover": dict(pool_age_seconds=600.0, liquidity_usd=2000.0,
        volume_liquidity=0.35, windows={}),
    "sf_quiet_absorption": dict(drawdown=0.0, buy_count_share=0.7,
        liquidity_usd=4000.0, fdv_liquidity=1.0, windows={}),
    "df_price_up_liquidity_up": dict(
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.05, liquidity_usd=5500.0, volume_5m_usd=120.0),
        liquidity_usd=5500.0, windows={}),
    "df_activity_jump": dict(
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.02, liquidity_usd=5000.0, volume_5m_usd=200.0),
        liquidity_usd=5000.0, buy_count_share=0.6, windows={}),
    # wave 5
    "df_mature_price_up": dict(pool_age_seconds=3600.0,
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.03, liquidity_usd=5100.0, volume_5m_usd=120.0),
        liquidity_usd=5100.0, windows={}),
    "sf_goldendog_deep_base": dict(pool_age_seconds=600.0, liquidity_usd=9000.0,
        fdv_liquidity=0.6, buy_count_share=0.6, drawdown=0.0, windows={}),
    # wave 6: golden-dog calibrated designs
    "righttail_lottery": dict(liquidity_usd=20000.0, pool_age_seconds=1200.0,
        buy_count_share=0.6, drawdown=0.0, windows={}),
    "goldendog_liquidity_band": dict(liquidity_usd=25000.0, pool_age_seconds=3000.0,
        buy_count_share=0.6, fdv_liquidity=1.5, windows={}),
    "dense_watch_breakout": dict(pair_frames=9,
        prev=dict(price_usd=1.0, liquidity_usd=20000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.04, liquidity_usd=20500.0, volume_5m_usd=140.0),
        liquidity_usd=20500.0, windows={}),
    # wave 8: the merged entry is an OR of already-frozen member mechanisms, so a
    # vector that triggers exactly one member must also trigger the merge.
    "merged_multi_setup": dict(
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.05, liquidity_usd=5500.0, volume_5m_usd=120.0),
        liquidity_usd=5500.0, windows={}),
    # wave 9: already washed out (drawdown <= -12%) and reclaiming on this frame.
    "washout_reclaim": dict(
        drawdown=-0.24, liquidity_usd=5200.0, buy_count_share=0.58, frames=6,
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.03, liquidity_usd=5100.0, volume_5m_usd=120.0),
        windows={}),
    # wave 7: revived hypotheses via sequence machinery
    "inv_contraction": dict(
        prev=dict(price_usd=1.0, liquidity_usd=6000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.01, liquidity_usd=5500.0, volume_5m_usd=120.0),
        liquidity_usd=5500.0, buy_count_share=0.6, windows={}),
    "seq_price_then_depth": dict(
        prev2=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=90.0),
        prev=dict(price_usd=1.03, liquidity_usd=5000.0, volume_5m_usd=110.0),
        current=dict(price_usd=1.06, liquidity_usd=5600.0, volume_5m_usd=150.0),
        liquidity_usd=5600.0, windows={}),
    "seq_two_step_rise": dict(
        prev2=dict(price_usd=1.0, liquidity_usd=4000.0, volume_5m_usd=90.0),
        prev=dict(price_usd=1.03, liquidity_usd=4200.0, volume_5m_usd=110.0),
        current=dict(price_usd=1.07, liquidity_usd=4400.0, volume_5m_usd=140.0),
        liquidity_usd=4400.0, windows={}),
    # wave 8: slow-in x slow-out quadrant
    "mature_two_step_slow": dict(pool_age_seconds=3600.0, liquidity_usd=6000.0,
        buy_count_share=0.6,
        prev2=dict(price_usd=1.0, liquidity_usd=5800.0, volume_5m_usd=90.0),
        prev=dict(price_usd=1.03, liquidity_usd=5900.0, volume_5m_usd=110.0),
        current=dict(price_usd=1.06, liquidity_usd=6000.0, volume_5m_usd=140.0),
        windows={}),
}

# Contextual exits are shared by construction: these arms reuse an existing kind.
HOLD_VARIANTS = {
    "alpha149_df_price_up_liquidity_up_hold_v1": "df_price_up_liquidity_up",
    "alpha149_df_activity_jump_hold_v1": "df_activity_jump",
    "alpha149_sf_extreme_buy_pressure_hold_v1": "sf_extreme_buy_pressure",
}


def test_hold_variants_reuse_an_existing_kind_with_a_longer_hold():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    base_holds = {
        "alpha149_df_price_up_liquidity_up_v1": 15,
        "alpha149_df_activity_jump_v1": 15,
        "alpha149_sf_extreme_buy_pressure_v1": 15,
    }
    for arm, kind in HOLD_VARIANTS.items():
        assert alpha149.SPECS[arm][0] == kind, arm
        base = arm.replace("_hold_v1", "_v1")
        assert policies[arm]["max_hold_minutes"] > policies[base]["max_hold_minutes"], arm
    assert set(HOLD_VARIANTS) <= set(alpha149.ALL_ARMS)


def test_each_mechanism_fires_on_its_own_vector():
    for kind, over in CASES.items():
        assert kind in triggered(feature(**over)), kind


def test_live_feature_shape_is_accepted_by_every_mechanism():
    """The derived feature never carries a top-level liquidity_usd.

    Regression for a live defect: mechanisms guarded by that key stayed False
    forever in the runtime (and `inv_contraction` raised TypeError), so the arms
    reading them could never trade. The current frame must supply the depth.
    """
    live = feature(liquidity_usd=None, fdv_liquidity=0.6, buy_count_share=0.66,
                   drawdown=0.0, pool_age_seconds=600.0, windows={},
                   current=dict(price_usd=1.0, liquidity_usd=12000.0,
                                volume_5m_usd=100.0, buys_5m=10.0, sells_5m=5.0))
    live.pop("liquidity_usd", None)          # exactly what Engine.accept returns
    assert "liquidity_usd" not in live
    flags = alpha149.mechanisms(live)
    assert flags["sf_deep_low_fdv"] is True
    assert flags["sf_quiet_absorption"] is True
    assert flags["righttail_lottery"] is True
    two_frame = {**live,
                 "current": dict(price_usd=1.05, liquidity_usd=12500.0,
                                 volume_5m_usd=120.0, buys_5m=10.0, sells_5m=5.0),
                 "prev": dict(price_usd=1.0, liquidity_usd=5000.0,
                              volume_5m_usd=100.0)}
    flags = alpha149.mechanisms(two_frame)
    assert flags["df_price_up_liquidity_up"] is True
    assert flags["merged_multi_setup"] is True
    # A genuinely unknown depth (no current frame) must stay False, never zero.
    unknown = feature(liquidity_usd=None, windows={}, current={"price_usd": 1.0})
    unknown.pop("liquidity_usd", None)
    assert alpha149.mechanisms(unknown)["sf_deep_low_fdv"] is False
    assert alpha149.mechanisms(unknown)["merged_multi_setup"] is False


def test_washout_reclaim_needs_both_the_washout_and_the_reclaim():
    base = dict(
        drawdown=-0.24, liquidity_usd=5200.0, buy_count_share=0.58, frames=6,
        prev=dict(price_usd=1.0, liquidity_usd=5000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.03, liquidity_usd=5100.0, volume_5m_usd=120.0),
        windows={})
    assert alpha149.mechanisms(feature(**base))["washout_reclaim"] is True
    # No washout: a fresh high is not a reclaim opportunity.
    fresh = dict(base, drawdown=0.0)
    assert alpha149.mechanisms(feature(**fresh))["washout_reclaim"] is False
    # Still falling: the reclaim frame is the entire hypothesis.
    falling = dict(base, current=dict(price_usd=0.97, liquidity_usd=5100.0,
                                      volume_5m_usd=120.0))
    assert alpha149.mechanisms(feature(**falling))["washout_reclaim"] is False
    # Depth leaving during the reclaim is not the measured recovery population.
    bleeding = dict(base, current=dict(price_usd=1.03, liquidity_usd=4000.0,
                                       volume_5m_usd=120.0))
    assert alpha149.mechanisms(feature(**bleeding))["washout_reclaim"] is False
    # Too few observations of this pool is not evidence.
    thin = dict(base, frames=2)
    assert alpha149.mechanisms(feature(**thin))["washout_reclaim"] is False


def test_vol_scaled_stop_grows_with_measured_volatility():
    opened = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
    current = datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)

    def vector(sigma, drawdown):
        return feature(drawdown=drawdown,
                       windows={"30": _w(vola=sigma, velocity=0.01, acc=0.0)})

    # Low measured volatility -> the floor (-22%) applies.
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.03, -0.20),
                                opened, current) is None
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.03, -0.25),
                                opened, current) == "alpha149_vol_scaled_stop"
    # Higher volatility buys more room: the same -25% no longer stops out.
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.10, -0.25),
                                opened, current) is None
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.10, -0.45),
                                opened, current) == "alpha149_vol_scaled_stop"
    # The cap refuses to convert the scaled stop into an unlimited hold.
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.40, -0.45),
                                opened, current) is None
    assert alpha149.exit_reason("alpha149_vol_scaled_stop", vector(0.40, -0.60),
                                opened, current) == "alpha149_vol_scaled_stop"
    # Unknown volatility must never be treated as zero (which would stop instantly).
    assert alpha149.exit_reason("alpha149_vol_scaled_stop",
                                vector(None, -0.90), opened, current) is None


def test_wave9_arms_are_additive_and_keep_their_contracts():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm in ("alpha149_washout_reclaim_v1", "alpha149_washout_reclaim_hold_v1",
                "alpha149_vol_scaled_merged_v1", "alpha149_vol_scaled_goldendog_v1",
                "alpha149_vol_scaled_exit_v1"):
        assert arm in alpha149.ALL_ARMS and arm in policies
    # The washout pair is one frozen entry with two exit contracts.
    assert alpha149.SPECS["alpha149_washout_reclaim_v1"][0] == \
        alpha149.SPECS["alpha149_washout_reclaim_hold_v1"][0] == "washout_reclaim"
    assert alpha149.SPECS["alpha149_washout_reclaim_hold_v1"][2] > \
        alpha149.SPECS["alpha149_washout_reclaim_v1"][2]
    assert policies["alpha149_washout_reclaim_hold_v1"]["hard_stop_grace_seconds"] == 180
    # The scaled-stop arms keep the shared stop only as a catastrophe backstop and
    # route their price stop through the volatility-scaled kind.
    for arm in ("alpha149_vol_scaled_merged_v1", "alpha149_vol_scaled_goldendog_v1",
                "alpha149_vol_scaled_exit_v1"):
        assert policies[arm]["trajectory_exit"] == "alpha149_vol_scaled_stop"
        assert policies[arm]["hard_stop_return"] == -.90
    assert alpha149.EXIT_ARMS["alpha149_vol_scaled_exit_v1"] == "alpha149_vol_scaled_stop"
    assert "alpha149_vol_scaled_stop" in alpha149.EXIT_KINDS
    assert alpha149.VOL_STOP_FLOOR < alpha149.VOL_STOP_CAP
    # No pre-existing arm may inherit the wave-9 contracts.
    assert not [arm for arm in alpha149.WAVE8_ARMS
                if policies[arm].get("trajectory_exit") == "alpha149_vol_scaled_stop"]


def test_survivable_cells_come_from_the_measured_writeoff_bands():
    """Wave 10 gates on the two entry-time facts that actually predict write-offs."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6,
                    prev=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.02, liquidity_usd=8100.0, volume_5m_usd=120.0),
                    windows={})
        base.update(over)
        return feature(**base)

    assert alpha149.mechanisms(vector())["survivable_core"] is True
    # A young pool is the measured death zone (22-23% write-off below 30 minutes).
    assert alpha149.mechanisms(vector(pool_age_seconds=600.0))["survivable_core"] is False
    # FDV below pool depth is the worst single cell (44.1% write-off).
    assert alpha149.mechanisms(vector(fdv_liquidity=0.7))["survivable_core"] is False
    # Too old: 180+ minutes had almost no upside (2.2% of positions above +5U).
    assert alpha149.mechanisms(vector(pool_age_seconds=20000.0))["survivable_core"] is False
    assert alpha149.mechanisms(vector(liquidity_usd=3000.0))["survivable_core"] is False
    # The deep band is a strictly narrower subset of the core band.
    assert alpha149.mechanisms(vector(fdv_liquidity=8.0, liquidity_usd=12000.0,
                                      buy_count_share=0.6))["survivable_band_deep"] is True
    assert alpha149.mechanisms(vector(fdv_liquidity=3.0, liquidity_usd=12000.0)
                               )["survivable_band_deep"] is False
    assert alpha149.mechanisms(vector(fdv_liquidity=8.0, liquidity_usd=6000.0)
                               )["survivable_band_deep"] is False


def test_depth_decay_exit_needs_both_depth_leaving_and_dead_activity():
    opened = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
    current = datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)

    def vector(liq_change, turn, retention):
        return feature(liquidity_retention=retention, volume_liquidity=turn,
                       windows={"30": _w(liq=liq_change)})

    assert alpha149.exit_reason("alpha149_depth_decay", vector(-0.25, 0.02, 0.5),
                                opened, current) == "alpha149_depth_decay_exit"
    # Depth leaving but activity still real: not the death precursor.
    assert alpha149.exit_reason("alpha149_depth_decay", vector(-0.25, 0.9, 0.5),
                                opened, current) is None
    # Dead activity but depth intact.
    assert alpha149.exit_reason("alpha149_depth_decay", vector(-0.01, 0.02, 1.0),
                                opened, current) is None
    # Depth has already recovered relative to the episode high.
    assert alpha149.exit_reason("alpha149_depth_decay", vector(-0.25, 0.02, 0.95),
                                opened, current) is None


def test_wave10_arms_are_additive_and_paired():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm in ("alpha149_survivable_core_v1", "alpha149_survivable_core_scaled_v1",
                "alpha149_survivable_core_depthexit_v1", "alpha149_survivable_deep_v1",
                "alpha149_depth_decay_exit_v1"):
        assert arm in alpha149.ALL_ARMS and arm in policies
    # Three arms share one frozen entry, so entry and exit effects stay separable.
    kinds = {alpha149.SPECS[arm][0] for arm in
             ("alpha149_survivable_core_v1", "alpha149_survivable_core_scaled_v1",
              "alpha149_survivable_core_depthexit_v1")}
    assert kinds == {"survivable_core"}
    assert policies["alpha149_survivable_core_depthexit_v1"]["trajectory_exit"] == \
        "alpha149_depth_decay"
    assert policies["alpha149_survivable_core_scaled_v1"]["trajectory_exit"] == \
        "alpha149_vol_scaled_stop"
    assert policies["alpha149_survivable_deep_v1"]["notional_usd"] == 1.0
    assert alpha149.EXIT_ARMS["alpha149_depth_decay_exit_v1"] == "alpha149_depth_decay"
    # The measured death cell stays excluded from every wave-10 entry.
    for arm in ("alpha149_survivable_core_v1", "alpha149_survivable_deep_v1"):
        assert policies[arm]["feature_hypothesis"].startswith("survivable")


def test_wave10_arms_are_reachable_through_the_live_engine_path():
    """Wiring proof for the survivability family: frames -> Engine -> signals."""
    clock = [datetime(2026, 9, 11, tzinfo=UTC)]
    engine = alpha149.Engine(clock[0])

    def row(price, liquidity, at, buys=12, sells=4):
        return dict(token_id="solana:T", pair_address="P", chain="solana",
                    provider="dexscreener", price_usd=price, liquidity_usd=liquidity,
                    volume_5m_usd=120.0, buys_5m=buys, sells_5m=sells,
                    pool_age_seconds=3600.0, fdv_usd=liquidity * 3.0,
                    observed_at=at, ingested_at=at, recorded_at=at)

    for step, at in enumerate(("2026-09-11T00:00:00Z", "2026-09-11T00:00:30Z")):
        clock[0] = datetime(2026, 9, 11, tzinfo=UTC) + timedelta(seconds=1 + 30 * step)
        engine.accept(row(1.0 + 0.03 * step, 8000.0 + 400.0 * step, at), clock[0])
    clock[0] = datetime(2026, 9, 11, tzinfo=UTC) + timedelta(seconds=32)
    signals = engine.signals_for("solana:T", "P", clock[0])
    for arm in ("alpha149_survivable_core_v1", "alpha149_survivable_core_scaled_v1",
                "alpha149_survivable_core_depthexit_v1"):
        assert arm in signals, arm
        assert signals[arm]["decision_evidence"]["mode"] == "survivable_core"
    snap = engine.snapshot()
    assert "survivable_core" in snap["mechanism_ready"]


def test_merged_survivable_requires_both_independent_conditions():
    """Wave 11 consolidates the merged entry with the measured survivable band."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6, drawdown=0.0,
                    prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.03, liquidity_usd=8000.0, volume_5m_usd=130.0),
                    windows={})
        base.update(over)
        return feature(**base)

    both = alpha149.mechanisms(vector())
    assert both["df_price_up_liquidity_up"] is True and both["survivable_core"] is True
    assert both["merged_survivable"] is True
    # Signal but not survivable (young pool): the merge must stay off.
    young = alpha149.mechanisms(vector(pool_age_seconds=600.0))
    assert young["df_price_up_liquidity_up"] is True and young["survivable_core"] is False
    assert young["merged_survivable"] is False
    # Survivability conditions hold but no merge member does: price rises while
    # depth is exactly flat (df_price_up_liquidity_up needs depth to increase) and
    # volume does not jump, so the intersection must stay off.
    flat_depth = alpha149.mechanisms(vector(
        current=dict(price_usd=1.03, liquidity_usd=7900.0, volume_5m_usd=100.0)))
    assert flat_depth["survivable_core"] is True
    assert flat_depth["df_price_up_liquidity_up"] is False
    assert flat_depth["df_activity_jump"] is False
    assert flat_depth["merged_survivable"] is False


def test_wave11_arms_reuse_measured_contracts():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm in ("alpha149_survivable_fast30_v1", "alpha149_survivable_deep_fast30_v1",
                "alpha149_merged_survivable_v1", "alpha149_goldendog_revival_control_v1"):
        assert arm in alpha149.ALL_ARMS and arm in policies
        # The profile that actually earned in this period: -20% stop, trail 30/15.
        assert policies[arm]["hard_stop_return"] == -.20
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
        assert policies[arm]["max_hold_minutes"] <= 60
    # Fast-30 arms are same-entry controls of the wave-10 arms, not new entries.
    assert alpha149.SPECS["alpha149_survivable_fast30_v1"][0] == \
        alpha149.SPECS["alpha149_survivable_core_v1"][0] == "survivable_core"
    assert alpha149.SPECS["alpha149_survivable_deep_fast30_v1"][0] == \
        alpha149.SPECS["alpha149_survivable_deep_v1"][0] == "survivable_band_deep"
    # The revival arm must not touch the paused original.
    assert policies["alpha149_goldendog_revival_control_v1"]["feature_hypothesis"] == \
        "goldendog_early_impulse"
    assert "alpha149_goldendog_early_impulse_v1" in policies  # original untouched


def test_regime_throttle_needs_improving_breadth_not_absolute_level():
    """Wave 12 revives the paused regime hypothesis with a relative measure."""
    def vector(regime=None):
        base = dict(windows={}, current=dict(price_usd=1.0, liquidity_usd=8000.0))
        if regime is not None:
            base["regime"] = regime
        return feature(**base)

    assert alpha149.mechanisms(vector({"fast": .20, "slow": .10, "ratio": 2.0}))[
        "regime_risk_on"] is True
    # The measured cross-section is mostly red (median rising share 13.3%), so an
    # absolute level alone must never qualify.
    assert alpha149.mechanisms(vector({"fast": .10, "slow": .05, "ratio": 2.0}))[
        "regime_risk_on"] is False
    # Flat breadth is not an improving tape.
    assert alpha149.mechanisms(vector({"fast": .20, "slow": .20, "ratio": 1.0}))[
        "regime_risk_on"] is False
    # No regime input at all -> unknown, never inferred.
    assert alpha149.mechanisms(vector())["regime_risk_on"] is False


def test_regime_intersections_require_both_sides():
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6, drawdown=0.0,
                    prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.03, liquidity_usd=8000.0, volume_5m_usd=130.0),
                    windows={}, regime={"fast": .25, "slow": .10, "ratio": 2.5})
        base.update(over)
        return feature(**base)

    on = alpha149.mechanisms(vector())
    assert on["regime_risk_on"] is True and on["merged_multi_setup"] is True
    assert on["survivable_core"] is True
    assert on["merged_regime"] is True and on["survivable_regime"] is True
    # Same pool and signal, but a flat tape: both intersections must switch off.
    off = alpha149.mechanisms(vector(regime={"fast": .10, "slow": .10, "ratio": 1.0}))
    assert off["merged_multi_setup"] is True and off["survivable_core"] is True
    assert off["regime_risk_on"] is False
    assert off["merged_regime"] is False and off["survivable_regime"] is False


def test_regime_breadth_is_computed_from_accepted_frames_only():
    """The engine must expose a causal, bounded breadth measure."""
    clock = [datetime(2026, 9, 11, tzinfo=UTC)]
    engine = alpha149.Engine(clock[0])
    assert engine.snapshot()["regime"] == {
        "samples": 0, "fast": None, "slow": None, "ready": False}

    def row(price, at, token):
        return dict(token_id=token, pair_address="P" + token, chain="solana",
                    provider="dexscreener", price_usd=price, liquidity_usd=8000.0,
                    volume_5m_usd=120.0, buys_5m=10, sells_5m=4, pool_age_seconds=3600.0,
                    fdv_usd=24000.0, observed_at=at, ingested_at=at, recorded_at=at)

    # 150 rising frames: breadth must accumulate and become ready without any I/O.
    for i in range(150):
        at = f"2026-09-11T00:{i // 60:02d}:{i % 60:02d}Z"
        clock[0] = datetime(2026, 9, 11, tzinfo=UTC) + timedelta(seconds=i + 1)
        engine.accept(row(1.0 + i * 0.001, at, f"T{i % 5}"), clock[0])
    regime = engine.snapshot()["regime"]
    assert regime["samples"] > 0
    assert regime["ready"] is True
    assert regime["slow"] == 1.0
    assert engine.snapshot()["regime"]["fast"] == 1.0


def test_wave12_arms_are_additive_and_use_the_short_hold_contract():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm in ("alpha149_regime_throttle_revival_v1", "alpha149_merged_regime_v1",
                "alpha149_survivable_regime_v1"):
        assert arm in alpha149.ALL_ARMS and arm in policies
        assert policies[arm]["hard_stop_return"] == -.20
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
        assert policies[arm]["max_hold_minutes"] == 30
    assert alpha149.REGIME_RATIO_MIN > 1.0 and alpha149.REGIME_FAST_MIN > 0
    # The paused original keeps its state; the revival is a separate new id.
    assert policies["alpha149_regime_throttle_revival_v1"]["feature_hypothesis"] == \
        "regime_risk_on"


def test_confirmed_entry_needs_two_consecutive_rises_inside_the_band():
    """Wave 13: the confirmation arm must delay the fill by one observed frame."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6, drawdown=0.0,
                    prev=dict(price_usd=1.02, liquidity_usd=7950.0, volume_5m_usd=110.0),
                    prev2=dict(price_usd=1.00, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.05, liquidity_usd=8000.0, volume_5m_usd=130.0),
                    windows={})
        base.update(over)
        return feature(**base)

    on = alpha149.mechanisms(vector())
    assert on["survivable_core"] is True and on["seq_two_step_rise"] is True
    assert on["confirmed_survivable"] is True
    # One rise only (the previous frame was flat): the band alone must not be
    # enough, because that is exactly the single-frame entry that stops in 23s.
    one_step = alpha149.mechanisms(vector(
        prev2=dict(price_usd=1.02, liquidity_usd=7900.0, volume_5m_usd=100.0)))
    assert one_step["survivable_core"] is True
    assert one_step["confirmed_survivable"] is False
    # Two rises but outside the measured band: also off.
    young = alpha149.mechanisms(vector(pool_age_seconds=600.0))
    assert young["seq_two_step_rise"] is True
    assert young["confirmed_survivable"] is False


def test_wave13_arm_is_additive_and_keeps_the_measured_contract():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    arm = "alpha149_confirmed_survivable_v1"
    assert arm in alpha149.ALL_ARMS and arm in policies
    assert policies[arm]["max_hold_minutes"] == 30
    assert policies[arm]["hard_stop_return"] == -.20
    assert policies[arm]["trailing_activate_return"] == .30
    assert policies[arm]["trailing_drawdown"] == .15
    # Its entry is an intersection of two already-frozen conditions.
    assert alpha149.SPECS[arm][0] == "confirmed_survivable"
    # The single-frame reference arm stays untouched.
    assert alpha149.SPECS["alpha149_df_price_up_liquidity_up_v1"][0] == \
        "df_price_up_liquidity_up"
    assert "hard_stop_grace_seconds" not in policies["alpha149_df_price_up_liquidity_up_v1"]


def test_age_rate_acceleration_rebuilds_the_best_entry_mechanism():
    """Wave 14: the highest-PnL entry of the system, on the shared vector.

    The parent (`resource_age_rate`) fires when the 5-minute rate is 3x the PRIOR
    55-minute rate. The shared vector publishes the whole-hour ratio a, and
    old_rate = 11a/(12-a), so the parent's threshold is a >= 36/14.
    """
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, liquidity_usd=9000.0, buy_count_share=0.6,
                    volume_liquidity=0.2, windows={},
                    current=dict(price_usd=1.0, liquidity_usd=9000.0, volume_5m_usd=1500.0))
        base.update(over)
        return feature(**base)

    # Exactly the parent's threshold: 11*a/(12-a) >= 3.
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=2.6)
                               )["age_rate_acceleration"] is True
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=2.55)
                               )["age_rate_acceleration"] is False
    # Either rate may carry it, exactly as the parent takes max(volume, trades).
    assert alpha149.mechanisms(vector(tx_acceleration_5m_1h=3.0)
                               )["age_rate_acceleration"] is True
    # A ratio at or above 12 means the hour no longer contains the 5 minutes: the
    # parent calls that "no comparable positive baseline", so it must not fire.
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=12.0)
                               )["age_rate_acceleration"] is False
    # Outside the measured 15-minute to 6-hour pool-age window: off.
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=3.0, pool_age_seconds=600.0)
                               )["age_rate_acceleration"] is False
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=3.0, pool_age_seconds=25200.0)
                               )["age_rate_acceleration"] is False
    # No real activity, seller-dominated flow, or unknown acceleration: off.
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=3.0, volume_liquidity=0.01,
                                      current=dict(price_usd=1.0, liquidity_usd=9000.0,
                                                   volume_5m_usd=50.0))
                               )["age_rate_acceleration"] is False
    assert alpha149.mechanisms(vector(volume_acceleration_5m_1h=3.0, buy_count_share=0.4)
                               )["age_rate_acceleration"] is False
    assert alpha149.mechanisms(vector())["age_rate_acceleration"] is False
    assert alpha149.AGE_RATE_MIN == 3.0
    assert abs(alpha149.AGE_RATE_RATIO_EQUIVALENT - 36.0 / 14.0) < 1e-9


def test_wave14_arms_pair_two_horizons_on_one_frozen_entry():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    slow, fast = "alpha149_age_rate_accel_v1", "alpha149_age_rate_accel_fast_v1"
    for arm in (slow, fast):
        assert arm in alpha149.ALL_ARMS and arm in policies
        assert policies[arm]["hard_stop_return"] == -.20
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
    assert alpha149.SPECS[slow][0] == alpha149.SPECS[fast][0] == "age_rate_acceleration"
    assert alpha149.SPECS[fast][2] < alpha149.SPECS[slow][2]
    # The original system arms are untouched: no guard fields, same ids.
    for original in ("resource_age_rate_candidate_v1", "age_rate_horizon_fast_v1"):
        assert original not in policies  # they live in the pattern lane, not here


def test_wave15_exit_contract_experiment_shares_one_frozen_entry():
    """Three exit contracts on one entry: does the price stop itself cost money?"""
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    arms = ("alpha149_no_price_stop_v1", "alpha149_precomp_stop_v1",
            "alpha149_nominal_stop_control_v1")
    for arm in arms:
        assert arm in alpha149.ALL_ARMS and arm in policies
        # Identical entry, identical trailing contract, identical horizon.
        assert alpha149.SPECS[arm][0] == "merged_multi_setup", arm
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
        assert alpha149.SPECS[arm][2] == 30
    # Only the price stop differs, and the pre-compensation equals the measured
    # median overshoot (6.4 points) below the nominal -20%.
    assert policies["alpha149_nominal_stop_control_v1"]["hard_stop_return"] == -.20
    assert policies["alpha149_precomp_stop_v1"]["hard_stop_return"] == -.136
    assert policies["alpha149_no_price_stop_v1"]["hard_stop_return"] == -.90
    for arm in arms:
        assert "hard_stop_grace_seconds" not in policies[arm]
        assert "hard_stop_confirm_marks" not in policies[arm]
    # The wave-8 merge arms keep their own contracts untouched.
    assert policies["alpha149_merged_multi_setup_fast_v1"]["hard_stop_return"] == -.20
    assert policies["alpha149_merged_multi_setup_v1"]["hard_stop_grace_seconds"] == 180


def test_wave16_stop_schedules_follow_the_measured_overshoot():
    """A price stop late in a hold is the expensive kind, so test two schedules."""
    current = datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)

    def vector(drawdown):
        return feature(drawdown=drawdown,
                       windows={"30": _w(vola=0.05, velocity=0.01, acc=0.0)})

    def armed(kind, drawdown, minutes):
        return alpha149.exit_reason(kind, vector(drawdown),
                                    current - timedelta(minutes=minutes), current)

    # Early-only stop: armed inside the first five minutes, disarmed afterwards.
    assert armed("alpha149_early_stop_only", -0.25, 2) == "alpha149_early_stop_only"
    assert armed("alpha149_early_stop_only", -0.25, 8) is None
    assert armed("alpha149_early_stop_only", -0.10, 2) is None
    # Time-decay stop: 30% allowed at entry, tightening 0.6 points per minute to a
    # 12% floor, so the same -25% fires late but not early.
    assert armed("alpha149_time_decay_stop", -0.25, 1) is None
    assert armed("alpha149_time_decay_stop", -0.25, 20) == "alpha149_time_decay_stop"
    assert armed("alpha149_time_decay_stop", -0.11, 40) is None
    assert armed("alpha149_time_decay_stop", -0.13, 40) == "alpha149_time_decay_stop"
    # Unknown drawdown never fires either schedule.
    assert alpha149.exit_reason("alpha149_early_stop_only",
                                feature(windows={"30": _w()}), current, current) is None
    assert alpha149.EARLY_STOP_MINUTES == 5.0
    assert alpha149.TIME_DECAY_CAP > alpha149.TIME_DECAY_FLOOR


def test_wave16_arms_share_the_wave15_entry_and_horizon():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm, kind in (("alpha149_early_stop_only_v1", "alpha149_early_stop_only"),
                      ("alpha149_time_decay_stop_v1", "alpha149_time_decay_stop")):
        assert arm in alpha149.ALL_ARMS and arm in policies
        assert alpha149.SPECS[arm][0] == "merged_multi_setup"
        assert policies[arm]["trajectory_exit"] == kind
        assert policies[arm]["hard_stop_return"] == -.90
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
        assert alpha149.SPECS[arm][2] == 30
    # Both schedules are registered exit kinds.
    assert alpha149.EXIT_ARMS["alpha149_early_stop_only_exit_v1"] == "alpha149_early_stop_only"
    assert alpha149.EXIT_ARMS["alpha149_time_decay_stop_exit_v1"] == "alpha149_time_decay_stop"
    # The wave-15 control is untouched, so the comparison stays valid.
    assert policies["alpha149_nominal_stop_control_v1"]["hard_stop_return"] == -.20
    assert policies["alpha149_nominal_stop_control_v1"].get("trajectory_exit") is None


def test_mid_band_excludes_the_measured_cliff_tier():
    """Wave 17: keep the upper bound that the deep band deliberately lacks."""
    def vector(fdv_liq, **over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=fdv_liq, liquidity_usd=12000.0,
                    buy_count_share=0.6,
                    prev=dict(price_usd=1.0, liquidity_usd=12000.0, volume_5m_usd=1000.0),
                    current=dict(price_usd=1.02, liquidity_usd=12000.0, volume_5m_usd=1500.0),
                    windows={})
        base.update(over)
        return feature(**base)

    flags = alpha149.mechanisms(vector(8.0))
    assert flags["survivable_band_mid"] is True
    assert flags["survivable_band_deep"] is True
    # The measured cliff (median stop overshoot -65 points) is inside the deep
    # band but must be outside the mid band.
    cliff = alpha149.mechanisms(vector(30.0))
    assert cliff["survivable_band_mid"] is False
    assert cliff["survivable_band_deep"] is True
    # Lower edge: below 5 belongs to the core band, not the mid band.
    assert alpha149.mechanisms(vector(3.0))["survivable_band_mid"] is False
    # Age and depth conditions still apply.
    assert alpha149.mechanisms(vector(8.0, pool_age_seconds=600.0))["survivable_band_mid"] is False
    assert alpha149.mechanisms(vector(8.0, liquidity_usd=6000.0))["survivable_band_mid"] is False


def test_wave17_arms_separate_band_choice_from_stop_removal():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    treatment, control = "alpha149_mid_band_nodeadstop_v1", "alpha149_mid_band_control_v1"
    for arm in (treatment, control):
        assert arm in alpha149.ALL_ARMS and arm in policies
        assert alpha149.SPECS[arm][0] == "survivable_band_mid"
        assert alpha149.SPECS[arm][2] == 60
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
    # Same entry, same trailing, same horizon: only the price stop differs.
    assert policies[treatment]["hard_stop_return"] == -.90
    assert policies[treatment]["trajectory_exit"] == "alpha149_depth_decay"
    assert policies[control]["hard_stop_return"] == -.20
    assert policies[control].get("trajectory_exit") is None
    # The older deep-band arm keeps its own (unbounded) band untouched.
    assert alpha149.SPECS["alpha149_survivable_deep_v1"][0] == "survivable_band_deep"


def test_wave18_arm_requires_both_measured_filters_at_half_size():
    """Safe band AND the best entry mechanism, at half notional."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6, volume_acceleration_5m_1h=3.0, volume_liquidity=0.2,
                    prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.03, liquidity_usd=8000.0, volume_5m_usd=130.0),
                    windows={})
        base.update(over)
        return feature(**base)

    both = alpha149.mechanisms(vector())
    assert both["survivable_core"] is True and both["age_rate_acceleration"] is True
    assert both["survivable_age_rate"] is True
    # Activity accelerating but the pool is outside the safe band: off.
    outside = alpha149.mechanisms(vector(fdv_liquidity=0.5))
    assert outside["age_rate_acceleration"] is True and outside["survivable_core"] is False
    assert outside["survivable_age_rate"] is False
    # Safe band but no real acceleration: off.
    flat = alpha149.mechanisms(vector(volume_acceleration_5m_1h=1.0))
    assert flat["survivable_core"] is True and flat["age_rate_acceleration"] is False
    assert flat["survivable_age_rate"] is False
    # The cliff tier is outside the safe band, so it is excluded here as well.
    cliff = alpha149.mechanisms(vector(fdv_liquidity=30.0))
    assert cliff["survivable_core"] is False and cliff["survivable_age_rate"] is False

    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    arm = "alpha149_survivable_age_rate_v1"
    assert policies[arm]["notional_usd"] == 1.0
    assert policies[arm]["hard_stop_return"] == -.20
    assert alpha149.SPECS[arm][0] == "survivable_age_rate"
    # The full-size parent arms keep their own sizing.
    assert policies["alpha149_age_rate_accel_v1"]["notional_usd"] == 2.0
    assert policies["alpha149_survivable_core_v1"]["notional_usd"] == 2.0


def test_wide_band_keeps_the_safe_ratio_and_only_relaxes_depth():
    """Wave 19: the safest band must be reachable without touching its core."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=8.0, liquidity_usd=3500.0,
                    buy_count_share=0.55, frames=30,
                    prev=dict(price_usd=1.0, liquidity_usd=3500.0, volume_5m_usd=700.0),
                    current=dict(price_usd=1.02, liquidity_usd=3500.0, volume_5m_usd=800.0),
                    windows={})
        base.update(over)
        return feature(**base)

    flags = alpha149.mechanisms(vector())
    assert flags["survivable_wide"] is True
    assert flags["survivable_core"] is False      # unchanged strict depth floor
    # The FDV/depth interval is the part that must not move: the cliff tier and
    # the sub-1 tier stay excluded.
    assert alpha149.mechanisms(vector(fdv_liquidity=30.0))["survivable_wide"] is False
    assert alpha149.mechanisms(vector(fdv_liquidity=0.5))["survivable_wide"] is False
    # Depth floor is still three times the shared 1000U floor.
    assert alpha149.mechanisms(vector(liquidity_usd=2500.0,
                                      current=dict(price_usd=1.02, liquidity_usd=2500.0,
                                                   volume_5m_usd=800.0))
                               )["survivable_wide"] is False
    # Age window still applies.
    assert alpha149.mechanisms(vector(pool_age_seconds=600.0))["survivable_wide"] is False


def test_wave19_deep_band_nostop_removes_only_the_price_stop():
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    arm = "alpha149_deep_band_nostop_v1"
    assert alpha149.SPECS[arm][0] == "survivable_band_deep"
    assert policies[arm]["hard_stop_return"] == -.90
    assert policies[arm]["trajectory_exit"] == "alpha149_depth_decay"
    assert policies[arm]["notional_usd"] == 1.0
    # The parent deep-band arm keeps its own vol-scaled stop contract.
    parent = policies["alpha149_survivable_deep_v1"]
    assert parent["hard_stop_return"] == -.90
    assert alpha149.SPECS["alpha149_survivable_deep_v1"][0] == "survivable_band_deep"
    assert policies["alpha149_wide_band_v1"]["hard_stop_return"] == -.20
    assert policies["alpha149_wide_band_v1"]["notional_usd"] == 1.0


def test_wave20_propagates_the_winning_schedule_to_other_entries():
    """The matrix favours stop scheduling; test whether that generalises."""
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    pairs = (("alpha149_time_decay_age_rate_v1", "age_rate_acceleration",
              "alpha149_time_decay_stop", "alpha149_age_rate_accel_v1", 2.0),
             ("alpha149_early_stop_deep_v1", "survivable_band_deep",
              "alpha149_early_stop_only", "alpha149_deep_band_nostop_v1", 1.0))
    for arm, kind, exit_kind, parent, notional in pairs:
        assert arm in alpha149.ALL_ARMS and arm in policies
        assert alpha149.SPECS[arm][0] == kind
        assert policies[arm]["trajectory_exit"] == exit_kind
        assert policies[arm]["hard_stop_return"] == -.90      # stop lives in the schedule
        assert policies[arm]["trailing_activate_return"] == .30
        assert policies[arm]["trailing_drawdown"] == .15
        assert alpha149.SPECS[arm][2] == 60
        assert policies[arm]["notional_usd"] == notional
        # Parents keep their own contracts untouched.
        assert parent in policies
    assert policies["alpha149_age_rate_accel_v1"].get("trajectory_exit") is None
    assert policies["alpha149_age_rate_accel_v1"]["hard_stop_return"] == -.20
    # Both schedules are the ones already registered as exit kinds.
    assert alpha149.EXIT_ARMS["alpha149_time_decay_stop_exit_v1"] == "alpha149_time_decay_stop"
    assert alpha149.EXIT_ARMS["alpha149_early_stop_only_exit_v1"] == "alpha149_early_stop_only"


def test_steady_band_relaxes_only_the_frame_slope():
    """Wave 21: 'not falling' is the same pool test with a 34x larger frame supply."""
    def vector(**over):
        base = dict(pool_age_seconds=3600.0, fdv_liquidity=3.0, liquidity_usd=8000.0,
                    buy_count_share=0.6,
                    prev=dict(price_usd=1.0, liquidity_usd=7900.0, volume_5m_usd=100.0),
                    current=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=120.0),
                    windows={})
        base.update(over)
        return feature(**base)

    flags = alpha149.mechanisms(vector())          # flat frame
    assert flags["survivable_core"] is False       # the strict parent still needs a rise
    assert flags["survivable_steady"] is True
    # A rising frame satisfies both.
    rising = alpha149.mechanisms(vector(
        current=dict(price_usd=1.02, liquidity_usd=8000.0, volume_5m_usd=120.0)))
    assert rising["survivable_core"] is True and rising["survivable_steady"] is True
    # A falling frame satisfies neither.
    falling = alpha149.mechanisms(vector(
        current=dict(price_usd=0.98, liquidity_usd=8000.0, volume_5m_usd=120.0)))
    assert falling["survivable_steady"] is False
    # The pool conditions are unchanged: band, age, depth, buy share all still bind.
    assert alpha149.mechanisms(vector(fdv_liquidity=30.0))["survivable_steady"] is False
    assert alpha149.mechanisms(vector(fdv_liquidity=0.5))["survivable_steady"] is False
    assert alpha149.mechanisms(vector(pool_age_seconds=600.0))["survivable_steady"] is False
    assert alpha149.mechanisms(vector(liquidity_usd=4000.0,
                                      current=dict(price_usd=1.0, liquidity_usd=4000.0,
                                                   volume_5m_usd=120.0))
                               )["survivable_steady"] is False
    assert alpha149.mechanisms(vector(buy_count_share=0.4))["survivable_steady"] is False
    # Depth leaving the pool still disqualifies it.
    assert alpha149.mechanisms(vector(current=dict(price_usd=1.0, liquidity_usd=7000.0,
                                                   volume_5m_usd=120.0))
                               )["survivable_steady"] is False

    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    arm = "alpha149_survivable_steady_v1"
    assert alpha149.SPECS[arm][0] == "survivable_steady"
    assert policies[arm]["notional_usd"] == 1.0
    assert policies[arm]["hard_stop_return"] == -.20
    # The strict parent is untouched.
    assert alpha149.SPECS["alpha149_survivable_core_v1"][0] == "survivable_core"
    assert policies["alpha149_survivable_core_v1"]["notional_usd"] == 2.0


def test_wave8_arms_keep_the_entry_frozen_and_only_change_the_exit_contract():
    """Same-signal A/B: the anti-whipsaw arms reuse an existing kind verbatim."""
    policies = {p["arm_id"]: p for p in alpha149.policies(_policy_base())}
    for arm, kind in WAVE8_ENTRY_KINDS.items():
        assert alpha149.SPECS[arm][0] == kind, arm
        assert policies[arm]["feature_hypothesis"] == kind
    wide = policies["alpha149_survive_noise_wide_v1"]
    assert alpha149.SPECS["alpha149_survive_noise_wide_v1"][0] == \
        alpha149.SPECS["alpha149_df_price_up_liquidity_up_v1"][0]
    assert wide["hard_stop_return"] == -.45
    assert wide["hard_stop_grace_seconds"] == 180
    assert wide["hard_stop_confirm_marks"] == 2
    assert wide["hard_stop_liquidity_veto_usd"] == 3000.
    assert wide["hard_stop_liquidity_veto_min_buy_share"] == .5
    # The confirmation-only control keeps the original stop, so the two effects
    # (delay vs width) can be separated in forward data.
    confirm = policies["alpha149_survive_noise_confirm_v1"]
    assert confirm["hard_stop_grace_seconds"] == 60
    assert confirm["hard_stop_confirm_marks"] == 2
    assert "hard_stop_return" not in confirm or confirm["hard_stop_return"] is None or \
        confirm["hard_stop_return"] == policies["alpha149_df_price_up_liquidity_up_v1"]["hard_stop_return"]
    assert policies["alpha149_goldendog_deep_hold_v1"]["hard_stop_grace_seconds"] == 300
    assert policies["alpha149_goldendog_deep_hold_v1"]["hard_stop_confirm_marks"] == 3
    merged = policies["alpha149_merged_multi_setup_v1"]
    assert merged["hard_stop_grace_seconds"] == 180
    # The merge and its fast control share one entry, so the exit is the only
    # difference between them.
    assert alpha149.SPECS["alpha149_merged_multi_setup_v1"][0] == \
        alpha149.SPECS["alpha149_merged_multi_setup_fast_v1"][0] == "merged_multi_setup"
    assert alpha149.SPECS["alpha149_merged_multi_setup_fast_v1"][2] < \
        alpha149.SPECS["alpha149_merged_multi_setup_v1"][2]
    # No existing arm may learn the new fields.
    for arm, policy in policies.items():
        if arm in alpha149.GUARD_ARMS:
            continue
        assert "hard_stop_grace_seconds" not in policy, arm
        assert "hard_stop_confirm_marks" not in policy, arm


def test_baseline_vector_triggers_nothing():
    assert triggered(feature()) == set()


# --------------------------------------------------------------------------- #
# 5. exits keep the causal guards
# --------------------------------------------------------------------------- #

def test_new_exits_respect_causal_guards():
    opened = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
    current = datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)
    f = feature(windows={"30": _w(velocity=-0.01, acc=-0.01, vol=0.5, tx=0.4, liq=-0.4)})
    assert alpha149.exit_reason("alpha149_profit_decay", f, opened, current) == \
        "alpha149_profit_velocity_decay"
    shock = feature(windows={"30": _w(liq=-0.30)})
    assert alpha149.exit_reason("alpha149_liquidity_shock", shock, opened, current) == \
        "alpha149_liquidity_shock_withdrawal"
    stall = feature(plateau_fraction=0.8, windows={"30": _w(tx=0.4, velocity=0.0)})
    assert alpha149.exit_reason("alpha149_plateau_stall", stall, opened, current) == \
        "alpha149_plateau_stall"
    giveback = feature(drawdown=-0.30)
    assert alpha149.exit_reason("alpha149_peak_giveback", giveback, opened, current) == \
        "alpha149_peak_giveback"
    dead = feature(plateau_fraction=0.9, windows={"30": _w(tx=0.2, velocity=-0.01)})
    assert alpha149.exit_reason("alpha149_flat_dead", dead, opened, current) == "alpha149_flat_dead"


def test_new_exits_reject_stale_or_preopening_frames():
    opened = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
    current = datetime(2026, 9, 11, 0, 0, 45, tzinfo=UTC)
    stale = feature(windows={"30": _w(liq=-0.30)})
    stale["observed_at"] = "2026-09-11T00:00:00Z"
    assert alpha149.exit_reason("alpha149_liquidity_shock", stale, opened, current) is None
    early = feature(windows={"30": _w(liq=-0.30, start="2026-09-10T23:59:00Z")})
    assert alpha149.exit_reason("alpha149_liquidity_shock", early, opened, current) is None
    assert alpha149.exit_reason("alpha149_liquidity_shock", None, opened, current) is None
    assert alpha149.exit_reason("unknown_kind", feature(), opened, current) is None
