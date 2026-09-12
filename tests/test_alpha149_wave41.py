"""Wave 41: the liquidity-band entry pair.

Measured 2026-09-12 over 1,262 tokens whose FIRST observation carried a liquidity value (>=5
observations, peak measured over the following hour):

  first-observation liquidity   n     >=1.5x   >=2x    >=3x
  0 - 1,000                     33    36.4%    30.3%   27.3%   (tiny sample)
  1,000 - 5,000                482     5.0%     3.1%    1.9%
  5,000 - 20,000               406    27.3%    15.0%    7.4%
  20,000 - 100,000             245    31.0%    19.2%   10.2%
  >= 100,000                    96     6.2%     3.1%    2.1%

This is a point-in-time stratification, not the token's later maximum, so it is the first entry
scalar this session that survived its own falsification attempt (a turnover filter did not).
"""
from memetrader import alpha149


def _frame(depth, prior_depth=None, buy_share=.6, price=1.01, prior_price=1.0, with_prev=True):
    return dict(
        current=dict(liquidity_usd=depth, price_usd=price),
        prev=(dict(liquidity_usd=prior_depth if prior_depth is not None else depth,
                   price_usd=prior_price) if with_prev else None),
        buy_count_share=buy_share,
        pool_age_seconds=3600.0,
    )


def test_the_band_arms_split_the_same_conditions_by_depth():
    mid = alpha149.mechanisms(_frame(50_000.0))
    assert mid['mid_band_flow'] is True
    assert mid['shallow_band_flow'] is False
    shallow = alpha149.mechanisms(_frame(3_000.0))
    assert shallow['mid_band_flow'] is False
    assert shallow['shallow_band_flow'] is True
    # the band boundaries are inclusive on the mid side and exclusive on the shallow side
    assert alpha149.mechanisms(_frame(20_000.0))['mid_band_flow'] is True
    assert alpha149.mechanisms(_frame(100_000.0))['mid_band_flow'] is True
    assert alpha149.mechanisms(_frame(20_000.0))['shallow_band_flow'] is False
    assert alpha149.mechanisms(_frame(19_999.0))['shallow_band_flow'] is True
    # outside both bands: neither fires
    deep = alpha149.mechanisms(_frame(250_000.0))
    assert deep['mid_band_flow'] is False and deep['shallow_band_flow'] is False
    dust = alpha149.mechanisms(_frame(500.0))
    assert dust['mid_band_flow'] is False and dust['shallow_band_flow'] is False


def test_both_arms_share_the_same_protecting_conditions():
    for depth in (3_000.0, 50_000.0):
        assert alpha149.mechanisms(_frame(depth, buy_share=.40))['mid_band_flow'] is False
        assert alpha149.mechanisms(_frame(depth, buy_share=.40))['shallow_band_flow'] is False
        # price falling versus the previous frame
        falling = alpha149.mechanisms(_frame(depth, price=0.99, prior_price=1.0))
        assert falling['mid_band_flow'] is False and falling['shallow_band_flow'] is False
        # depth leaving the pool
        draining = alpha149.mechanisms(_frame(depth, prior_depth=depth * 1.10))
        assert draining['mid_band_flow'] is False and draining['shallow_band_flow'] is False
        # a single frame is not enough: the two-frame view must exist
        alone = alpha149.mechanisms(_frame(depth, with_prev=False))
        assert alone['mid_band_flow'] is False and alone['shallow_band_flow'] is False


def test_wave41_arms_are_additive_and_keep_family_identity():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    assert len(alpha149.ALL_ARMS) == len(set(alpha149.ALL_ARMS))
    kinds = dict((a, k) for a, (k, _n, _h) in alpha149.SPECS.items())
    assert kinds['alpha149_mid_band_flow_v1'] == 'mid_band_flow'
    assert kinds['alpha149_shallow_band_flow_v1'] == 'shallow_band_flow'
    for arm in ('alpha149_mid_band_flow_v1', 'alpha149_shallow_band_flow_v1'):
        policy = policies[arm]
        assert policy['feature_contract'] == alpha149.VERSION
        assert policy['trajectory_engine'] == 'alpha149'
        assert policy['notional_usd'] == 1.0
        assert policy['max_hold_minutes'] == 30
        assert policy['hard_stop_return'] == -.20
        assert policy['trailing_activate_return'] == .30
        assert policy['trailing_drawdown'] == .15
        assert policy['decision_eligible'] is True
        assert policy['affects'] == 'paper_only'
        assert alpha149._is_broad_arm(arm) is False


def test_the_two_arms_have_identical_contracts_so_only_the_band_differs():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    a = policies['alpha149_mid_band_flow_v1']
    b = policies['alpha149_shallow_band_flow_v1']
    for field in ('notional_usd', 'max_hold_minutes', 'hard_stop_return',
                  'trailing_activate_return', 'trailing_drawdown', 'feature_contract',
                  'trajectory_engine', 'decision_eligible', 'affects'):
        assert a[field] == b[field], field
    assert a['entry_filter']['max_concurrent_positions'] == b['entry_filter']['max_concurrent_positions']
