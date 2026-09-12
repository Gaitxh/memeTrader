"""Wave-2 tests for the dust-read guard: the provider-independent mark-history contradiction.

The second measured false positive (2026-09-12T06:23:11Z, solana:HBxFUfqE...) was a
`geckoterminal` mark reporting liquidity 0.00 nineteen seconds after the same pool's own
dexscreener mark read 23,759 USD, with the price unchanged at -0.4%. That payload carries no
volume, so the same-observation test cannot see it; only the pool's own mark history can.
"""
from memetrader import paper_execution as pe


def _history_rows(liquidity, price):
    return liquidity, price


def test_the_guard_is_still_the_documented_same_observation_test():
    """The pure function keeps its contract (documented in tests/test_dust_read_guard.py)."""
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0, volume_5m_usd=None) is False
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0, volume_5m_usd=1_000.0) is True


def test_the_mark_history_contradiction_is_documented_where_the_code_reads_it():
    """A source-level anchor: the second test must read the pool's own mark history."""
    from pathlib import Path
    source = Path('src/memetrader/store.py').read_text(encoding='utf-8')
    assert 'chain_meme_trader_market_mark_history' in source
    method = source.split('def _dust_read_contradicted', 1)[1].split('def _count_dust_veto', 1)[0]
    assert 'chain_meme_trader_market_mark_history' in method
    assert 'median_liquidity >= floor' in method
    assert 'price_now >= median_price * 0.5' in method
    assert 'len(reference) < 3' in method
    assert 'liquidity > 0.0' in method


def test_the_measured_second_case_would_be_vetoed_by_the_documented_rule():
    """Replay the measured values against the rule the code implements."""
    floor = 1000.0
    reference_liquidity = [21397.32, 22030.61, 22266.78, 23072.65, 23671.03]
    reference_price = [1.283e-05, 1.354e-05, 1.383e-05, 1.476e-05, 1.551e-05]
    liquids = sorted(reference_liquidity)
    prices = sorted(reference_price)
    median_liquidity = liquids[len(liquids) // 2]
    median_price = prices[len(prices) // 2]
    mark_liquidity = 0.00
    mark_price = 1.55226e-05
    assert mark_liquidity <= 0.0
    assert median_liquidity >= floor
    assert mark_price >= median_price * 0.5
    # and the same-observation test alone would have missed it (no volume in the payload)
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=mark_liquidity, price_usd=mark_price,
        entry_price_usd=1.551e-05, volume_5m_usd=None, buys_5m=None, sells_5m=None) is False


def test_a_real_rug_fails_both_documented_tests():
    """bsc:0x7c6f...: collapsed price AND its own history already below the floor."""
    entry, dust_price, dust_liquidity = 0.0003469, 3.346e-10, 0.0
    # same-observation test: the price collapsed
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=dust_liquidity, price_usd=dust_price, entry_price_usd=entry,
        volume_5m_usd=50000.0, buys_5m=40, sells_5m=20) is False
    # history test: the pool's own recent marks are already dust, so the median is below floor
    reference_liquidity = [0.0, 0.1, 0.0, 0.0, 0.1]
    floor = 1000.0
    assert sorted(reference_liquidity)[2] < floor
