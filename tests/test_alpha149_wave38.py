"""Wave 38: the wide multi-provider observation surface.

Measured reason for the wave: the alpha149 engine held 67 live pools out of 512 while 2,314
distinct tokens were evaluated in the same hour (1,052 with >=2 observations, 994 of those with
at least one row above the 1000U floor) - but only 62 of them (5.9%) had >=2 rows whose provider
starts with "dexscreener". Frame ADMISSION, not the thresholds, capped token coverage.

These tests pin the two properties that make the wave safe:
  * the existing dex-only engine keeps its exact admission rule and arm set;
  * the wide surface owns exactly the two wave-38 arms and nothing else.
"""
from datetime import datetime, timezone

from memetrader import alpha149
from memetrader import dex_trajectory as dex

UTC = timezone.utc


def _frame(provider, observed, price=1.0, liquidity=8000.0, pair='P', token='solana:T',
           fdv=300000.0, buys=8, sells=3):
    return dict(
        token_id=token, pair_address=pair, chain='solana', provider=provider,
        observed_at=observed, ingested_at=observed, recorded_at=observed,
        price_usd=price, liquidity_usd=liquidity, volume_5m_usd=250.0,
        volume_1h_usd=3000.0, buys_5m=buys, sells_5m=sells, buys_1h=80, sells_1h=40,
        pool_age_seconds=3600.0, fdv_usd=fdv, buyers_5m=6,
    )


# --------------------------------------------------------------------------- #
# the existing admission rule must be byte-identical
# --------------------------------------------------------------------------- #

def test_dex_engine_admission_rule_is_unchanged():
    """The shared engine still admits only dexscreener frames, and still requires >=1000U."""
    engine = dex.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    assert engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), now) is None
    assert engine.accept(_frame('strategy-observer:dexscreener', '2026-09-11T00:00:01Z'), now) is None
    thin = _frame('dexscreener', '2026-09-11T00:00:01Z', liquidity=999.0)
    assert engine.accept(thin, now) is None
    accepted = engine.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), now)
    assert accepted is not None
    assert engine.PROVIDER_PREFIX == 'dexscreener'


def test_broad_engine_admits_every_provider_but_one_provider_per_pool():
    engine = alpha149._BroadEngine('2026-09-11T00:00:00Z')
    assert engine.PROVIDER_PREFIX == ''
    first = engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')
    assert first is not None
    # a different vender for the same pool must never be merged into one price series
    mixed = engine.accept(_frame('dexscreener', '2026-09-11T00:00:10Z', price=1.2),
                          '2026-09-11T00:00:15Z')
    assert mixed is None
    assert engine.counts['provider_mismatch'] == 1
    same = engine.accept(_frame('geckoterminal', '2026-09-11T00:00:20Z', price=1.01),
                         '2026-09-11T00:00:25Z')
    assert same is not None


def test_broad_engine_keeps_a_coarse_second_frame():
    """The wide surface is fed at 60-120s cadence, so it keeps the previous frame."""
    engine = alpha149._BroadEngine('2026-09-11T00:00:00Z')
    assert engine.MAX_GAP_SECONDS == 300
    assert dex.Engine.MAX_GAP_SECONDS == 30
    engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')
    second = engine.accept(_frame('geckoterminal', '2026-09-11T00:01:31Z', price=1.02),
                           '2026-09-11T00:01:35Z')
    assert second is not None
    state = engine.pools[('solana:T', 'P')]
    assert len(state['rows']) == 2
    assert engine.counts['gap_reset'] == 0
    payload = engine.signals_for('solana:T', 'P', '2026-09-11T00:01:35Z')
    assert isinstance(payload, dict)


def test_the_shared_engine_still_resets_on_a_coarse_gap():
    """The default must stay exactly 30s for every existing user of the engine."""
    engine = dex.Engine('2026-09-11T00:00:00Z')
    engine.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')
    engine.accept(_frame('dexscreener', '2026-09-11T00:01:31Z', price=1.02),
                  '2026-09-11T00:01:35Z')
    assert engine.counts['gap_reset'] == 1
    assert len(engine.pools[('solana:T', 'P')]['rows']) == 1


# --------------------------------------------------------------------------- #
# the alpha149 engine routes the two surfaces without touching the old one
# --------------------------------------------------------------------------- #

def test_primary_surface_never_emits_the_wave38_arms(monkeypatch):
    """A dexscreener pool keeps the dex surface and sees no wave-38 arm."""
    monkeypatch.setattr(alpha149, 'mechanisms',
                        lambda f: {'survivable_open_band': True, 'broad_band': True,
                                   'broad_flow': True})
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    engine.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), now)
    output = engine.signals_for('solana:T', 'P', now)
    assert 'alpha149_open_band_v1' in output
    assert not any(arm in output for arm in alpha149._BROAD_ARMS)
    assert len(engine.pools) == 1
    assert engine._broad is None


def test_wide_surface_owns_exactly_the_wave38_arms(monkeypatch):
    """A geckoterminal-only pool reaches the wide surface and only the wave-38 arms."""
    monkeypatch.setattr(alpha149, 'mechanisms',
                        lambda f: {'hot': True, 'broad_band': True, 'broad_flow': True})
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    now = '2026-09-11T00:00:05Z'
    assert engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), now) is not None
    output = engine.signals_for('solana:T', 'P', now)
    assert set(output) == set(alpha149._BROAD_ARMS)
    # the wide surface is a separate namespace: the dex engine owns no such pool
    assert (('solana:T', 'P') not in engine.pools)
    assert ('solana:T', 'P') in engine._broad.pools
    # and the existing exit arms do not ride the wide surface
    assert not any(arm in output for arm in alpha149.EXIT_ARMS)


def test_a_pool_the_dex_surface_owns_is_never_duplicated_into_the_wide_one():
    """Once the dex engine owns an identity, a later non-dex frame cannot re-admit it."""
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    engine.accept(_frame('dexscreener', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')
    assert engine.accept(_frame('geckoterminal', '2026-09-11T00:00:10Z'),
                         '2026-09-11T00:00:15Z') is None
    assert engine._broad is None or ('solana:T', 'P') not in engine._broad.pools


def test_snapshot_reports_the_wide_surface_separately():
    engine = alpha149.Engine('2026-09-11T00:00:00Z')
    engine.accept(_frame('geckoterminal', '2026-09-11T00:00:01Z'), '2026-09-11T00:00:05Z')
    snap = engine.snapshot()
    assert snap['broad_surface']['pools'] == 1
    assert list(snap['broad_surface']['arms']) == list(alpha149.BROAD_SURFACE_ARMS)
    assert snap['broad_surface']['provider_prefix'] == ''
    assert snap['pools'] == 0


# --------------------------------------------------------------------------- #
# the two kinds reuse an already reachable predicate and add a real arm pair
# --------------------------------------------------------------------------- #

def _bands_feature(**over):
    base = dict(
        version=dex.VERSION, token_id='solana:T', pair_address='P', chain='solana',
        provider='geckoterminal', observed_at='2026-09-11T00:00:30Z',
        ingested_at='2026-09-11T00:00:31Z', recorded_at='2026-09-11T00:00:32Z',
        pool_age_seconds=3600.0, frames=6,
        liquidity_usd=8000.0, buy_count_share=0.62, drawdown=-0.02,
        plateau_fraction=0.0, monotonic_up_fraction=0.6, liquidity_retention=1.0,
        volume_liquidity=0.5, fdv_liquidity=37.5, price_elasticity_proxy=None,
        prev=dict(price_usd=1.0, liquidity_usd=8000.0, volume_5m_usd=100.0),
        current=dict(price_usd=1.01, liquidity_usd=8000.0, volume_5m_usd=120.0),
        log_price_r2=0.8, residual_dispersion=0.01, jump_interval_cv=0.4, jump_size_cv=0.4,
        volume_acceleration_age_normalized=2.2, tx_acceleration_age_normalized=2.2,
        first_dip=None,
        base=dict(range_fraction=0.5, high=1.0, end_at='2026-09-11T00:00:00Z'),
        windows={'30': dict(return_fraction=0.01, liquidity_change_fraction=0.0,
                            rolling_volume_change_ratio=1.2, rolling_tx_change_ratio=1.1,
                            acceleration=0.1, frames=3, log_velocity=0.02,
                            realized_volatility=0.05, start_at='2026-09-11T00:00:00Z',
                            span_seconds=30.0, end_at='2026-09-11T00:00:30Z', curvature='FLAT')},
    )
    base.update(over)
    return base


def test_the_two_new_kinds_mirror_reachable_predicates():
    flags = alpha149.mechanisms(_bands_feature())
    assert flags['broad_band'] == flags['survivable_open_band']
    assert flags['broad_flow'] == flags['flow_entry']
    # they are distinct kind names, so they cannot accidentally ride an older arm's flag
    kinds = dict((arm, kind) for arm, (kind, _n, _h) in alpha149.SPECS.items())
    assert kinds['alpha149_broad_band_v1'] == 'broad_band'
    assert kinds['alpha149_broad_flow_v1'] == 'broad_flow'


def test_wave38_arms_are_additive_and_keep_family_identity():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    assert len(alpha149.ALL_ARMS) == len(set(alpha149.ALL_ARMS))
    for arm in alpha149.BROAD_SURFACE_ARMS:
        policy = policies[arm]
        assert policy['feature_contract'] == alpha149.VERSION
        assert policy['notional_usd'] == 1.0
        assert policy['decision_eligible'] is True
        assert policy['affects'] == 'paper_only'
        assert policy['trajectory_engine'] == 'alpha149_broad'
        assert policy['requires_distinct_trajectory_frame'] is False
        assert policy['requires_distinct_wide_frame'] is True
        assert '\u5bbd\u89c2\u6d4b' in policy['description']
