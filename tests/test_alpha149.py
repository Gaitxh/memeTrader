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
        if arm in alpha149.WAVE8_ARMS:
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
