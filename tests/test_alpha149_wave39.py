"""Wave 39: wide-surface arms bound to the kinds the wide surface actually produces.

Measured on the live wide surface (130 evaluations in its first ~10 minutes): the kinds that
fire there are young-pool kinds (goldendog_liquidity_band 10, decorr_young 7,
merged_multi_setup 7, df_activity_jump 4, df_price_up_liquidity_up 4), while the wave-38
`broad_band` stays at 0 (every wide pool is younger than that band's 30-minute floor) and
`broad_flow` stays at 0 (none of its five components is satisfied on a coarse frame).

These tests pin the ownership rule for surface-specific arms and the mirrors themselves.
"""
from memetrader import alpha149
from memetrader import dex_trajectory as dex
from tests.test_alpha149_wave38 import _frame, _bands_feature


def test_wave39_arms_are_owned_only_by_the_wide_surface(monkeypatch):
    monkeypatch.setattr(alpha149, 'mechanisms',
                        lambda f: {'decorr_young': True, 'goldendog_liquidity_band': True,
                                   'broad_decorr_young': True, 'broad_goldendog_band': True})
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), now)
    output = engine.signals_for('solana:T', 'P', now)
    assert set(output) == set(alpha149._BROAD_ARMS_W39)
    assert not any(arm in output for arm in alpha149._BROAD_ARMS)
    assert not any(arm in output for arm in alpha149.EXIT_ARMS)


def test_the_dex_surface_never_emits_a_wave39_arm(monkeypatch):
    monkeypatch.setattr(alpha149, 'mechanisms',
                        lambda f: {'decorr_young': True, 'goldendog_liquidity_band': True,
                                   'broad_decorr_young': True, 'broad_goldendog_band': True})
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    engine.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), now)
    output = engine.signals_for('solana:T', 'P', now)
    assert 'alpha149_decorr_young_v1' in output
    assert not any(arm in output for arm in alpha149._BROAD_ARMS_W39)


def test_the_two_wide_kinds_mirror_their_reachable_predicates():
    flags = alpha149.mechanisms(_bands_feature())
    assert flags['broad_decorr_young'] == flags['decorr_young']
    assert flags['broad_goldendog_band'] == flags['goldendog_liquidity_band']
    kinds = dict((arm, kind) for arm, (kind, _n, _h) in alpha149.SPECS.items())
    assert kinds['alpha149_broad_decorr_young_v1'] == 'broad_decorr_young'
    assert kinds['alpha149_broad_goldendog_band_v1'] == 'broad_goldendog_band'
    assert alpha149._is_broad_arm('alpha149_broad_goldendog_band_v1') is True
    assert alpha149._is_broad_arm('alpha149_decorr_young_v1') is False


def test_the_broad_surface_arm_list_is_the_union_of_both_waves():
    assert alpha149.BROAD_SURFACE_ARMS == (alpha149._BROAD_ARMS + alpha149._BROAD_ARMS_W39
                                           + alpha149._W40_ARMS)
    assert len(set(alpha149.BROAD_SURFACE_ARMS)) == len(alpha149.BROAD_SURFACE_ARMS)
    for arm in alpha149.BROAD_SURFACE_ARMS:
        assert arm in alpha149.ALL_ARMS
    assert alpha149.WIDE_SURFACE_ARMS == alpha149.BROAD_SURFACE_ARMS


def test_wave40_arms_are_registered_with_the_wide_contract(monkeypatch):
    """The four earlier wide arms are dead by their stored contract; wave 40 fixes it."""
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    for arm in alpha149._W40_ARMS:
        policy = policies[arm]
        assert policy['trajectory_engine'] == 'alpha149_broad'
        assert policy['requires_distinct_trajectory_frame'] is False
        assert policy['requires_distinct_wide_frame'] is True
        assert policy['notional_usd'] == 1.0
        assert policy['max_hold_minutes'] == 30
        assert policy['affects'] == 'paper_only'
    kinds = dict((a, k) for a, (k, _n, _h) in alpha149.SPECS.items())
    assert kinds['alpha149_wide_decorr_young_v1'] == 'wide_decorr_young'
    assert kinds['alpha149_wide_goldendog_band_v1'] == 'wide_goldendog_band'
    flags = alpha149.mechanisms(_bands_feature())
    assert flags['wide_decorr_young'] == flags['decorr_young']
    assert flags['wide_goldendog_band'] == flags['goldendog_liquidity_band']
    # owned by the wide surface only
    monkeypatch.setattr(alpha149, 'mechanisms',
                        lambda f: {'wide_decorr_young': True, 'wide_goldendog_band': True,
                                   'decorr_young': True})
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), now)
    wide = engine.signals_for('solana:T', 'P', now)
    assert set(wide) == set(alpha149._W40_ARMS)
    engine2 = alpha149.Engine('2026-09-11T00:00:00Z')
    engine2.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), now)
    dex_output = engine2.signals_for('solana:T', 'P', now)
    assert not any(arm in dex_output for arm in alpha149._W40_ARMS)
    assert 'alpha149_decorr_young_v1' in dex_output


def test_wave39_arms_keep_the_family_contract():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    for arm in alpha149.BROAD_SURFACE_ARMS:
        policy = policies[arm]
        assert policy['feature_contract'] == alpha149.VERSION
        assert policy['notional_usd'] == 1.0
        assert policy['decision_eligible'] is True
        assert policy['affects'] == 'paper_only'
        assert policy['max_hold_minutes'] == 30
        # Routed at the wide namespace, with the next-frame confirmation contract
        # moved to that surface instead of disabled.
        assert policy['trajectory_engine'] == 'alpha149_broad'
        assert policy['requires_distinct_trajectory_frame'] is False
        assert policy['requires_distinct_wide_frame'] is True


def test_the_store_routes_the_wide_engine_name_additively():
    from memetrader import store as store_module
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')

    class Fake:
        _alpha149 = engine
        _dex_trajectory = 'dex'
        _trajectory_engine_for = store_module.Store._trajectory_engine_for

    fake = Fake()
    assert fake._trajectory_engine_for({'trajectory_engine': 'alpha149'}) is engine
    assert fake._trajectory_engine_for({'trajectory_engine': 'alpha149_broad'}) is engine._broad
    assert fake._trajectory_engine_for({'trajectory_engine': 'dex'}) == 'dex'
    assert fake._trajectory_engine_for({}) == 'dex'
    assert fake._trajectory_engine_for({'trajectory_engine': 'v144'}) is None


def test_the_shared_engine_is_untouched_by_wave39():
    assert dex.Engine.PROVIDER_PREFIX == 'dexscreener'
    assert dex.Engine.MAX_GAP_SECONDS == 30
    assert alpha149._BroadEngine.PROVIDER_PREFIX == ''
    assert alpha149._BroadEngine.MAX_GAP_SECONDS == 300
