"""Wave 42: two pool-death risk gates on the same flow carrier.

These are the first arms aimed at the LEFT TAIL rather than at upside. A fixed-horizon
counterfactual over 400 positions (round 82) showed holding to +5/15/30/60/120 minutes is WORSE
than what the positions actually realised (paired mean difference -0.065 at 30 minutes and -0.074
at 60; hold-to-horizon better in only 43.5%/43.9%), so premature exits are not the loss. The
write-off line was 360 positions in 24h. Two risk features replicated across two independent
measurements: BSC carries a 30.4% pool-death rate against Solana 3.9% and Robinhood 0.0%, and
entry liquidity >= 100k carries 0.5% against 18.2% for 20k-100k.

Turnover does NOT survive the controls (flat within chain and within band), so it is not used -
the same trap that falsified the round-80 turnover filter.
"""
from memetrader import alpha149


def _frame(depth, chain='solana', prior_depth=None, buy_share=.6, price=1.01, prior_price=1.0,
           with_prev=True):
    return dict(
        chain=chain,
        current=dict(liquidity_usd=depth, price_usd=price),
        prev=(dict(liquidity_usd=prior_depth if prior_depth is not None else depth,
                   price_usd=prior_price) if with_prev else None),
        buy_count_share=buy_share,
        pool_age_seconds=3600.0,
    )


def test_the_two_risk_gates_split_on_depth_and_chain():
    deep_solana = alpha149.mechanisms(_frame(250_000.0, 'solana'))
    assert deep_solana['deep_pool_flow'] is True
    assert deep_solana['nonbsc_flow'] is True
    deep_bsc = alpha149.mechanisms(_frame(250_000.0, 'bsc'))
    assert deep_bsc['deep_pool_flow'] is True
    assert deep_bsc['nonbsc_flow'] is False
    shallow_solana = alpha149.mechanisms(_frame(50_000.0, 'solana'))
    assert shallow_solana['deep_pool_flow'] is False
    assert shallow_solana['nonbsc_flow'] is True
    # the boundary is inclusive
    assert alpha149.mechanisms(_frame(100_000.0, 'bsc'))['deep_pool_flow'] is True
    assert alpha149.mechanisms(_frame(99_999.0, 'bsc'))['deep_pool_flow'] is False


def test_chain_matching_is_case_insensitive_and_never_defaults_to_safe():
    assert alpha149.mechanisms(_frame(250_000.0, 'BSC'))['nonbsc_flow'] is False
    assert alpha149.mechanisms(_frame(250_000.0, 'Solana'))['nonbsc_flow'] is True
    # an absent chain must not be treated as non-BSC
    unknown = alpha149.mechanisms(_frame(250_000.0, ''))
    assert unknown['nonbsc_flow'] is False
    assert unknown['deep_pool_flow'] is True


def test_both_arms_keep_the_measured_protecting_conditions():
    for chain in ('solana', 'bsc'):
        assert alpha149.mechanisms(_frame(250_000.0, chain, buy_share=.40))['deep_pool_flow'] is False
        assert alpha149.mechanisms(_frame(250_000.0, chain, buy_share=.40))['nonbsc_flow'] is False
        falling = alpha149.mechanisms(_frame(250_000.0, chain, price=0.99, prior_price=1.0))
        assert falling['deep_pool_flow'] is False or chain == 'bsc'
        draining = alpha149.mechanisms(_frame(250_000.0, chain, prior_depth=300_000.0))
        assert draining['deep_pool_flow'] is False
        alone = alpha149.mechanisms(_frame(250_000.0, chain, with_prev=False))
        assert alone['deep_pool_flow'] is False and alone['nonbsc_flow'] is False


def test_wave42_arms_are_additive_with_identical_contracts():
    from memetrader.cohort_experiments import cohort_experiment_policies
    policies = {p['arm_id']: p for p in alpha149.policies(cohort_experiment_policies()[2])}
    assert len(alpha149.ALL_ARMS) == len(set(alpha149.ALL_ARMS))
    kinds = dict((a, k) for a, (k, _n, _h) in alpha149.SPECS.items())
    assert kinds['alpha149_deep_pool_flow_v1'] == 'deep_pool_flow'
    assert kinds['alpha149_nonbsc_flow_v1'] == 'nonbsc_flow'
    a = policies['alpha149_deep_pool_flow_v1']
    b = policies['alpha149_nonbsc_flow_v1']
    reference = policies['alpha149_mid_band_flow_v1']
    for field in ('notional_usd', 'max_hold_minutes', 'hard_stop_return',
                  'trailing_activate_return', 'trailing_drawdown', 'feature_contract',
                  'trajectory_engine', 'decision_eligible', 'affects'):
        assert a[field] == b[field] == reference[field], field
    assert alpha149._is_broad_arm('alpha149_deep_pool_flow_v1') is False
    assert alpha149._is_broad_arm('alpha149_nonbsc_flow_v1') is False
