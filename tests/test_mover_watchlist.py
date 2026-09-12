"""Tests for the mover watch-list registry (pure; no runtime, no I/O)."""
from datetime import datetime, timedelta, timezone

from memetrader import mover_watchlist as mw

UTC = timezone.utc
NOW = datetime(2026, 9, 12, 7, 0, tzinfo=UTC)


def test_mid_pool_rule_needs_liquidity_and_buy_share():
    assert mw.admission(liquidity_usd=50_000, buys_5m=70, sells_5m=30) == 'mid_pool_buy_share'
    assert mw.admission(liquidity_usd=20_000, buys_5m=60, sells_5m=40) == 'mid_pool_buy_share'
    assert mw.admission(liquidity_usd=19_999, buys_5m=70, sells_5m=30) is None
    assert mw.admission(liquidity_usd=50_000, buys_5m=59, sells_5m=41) is None
    # a missing buy/sell split cannot qualify on that rule
    assert mw.admission(liquidity_usd=50_000) is None


def test_small_pool_rule_needs_turnover_above_one():
    assert mw.admission(liquidity_usd=5_000, volume_5m_usd=6_000) == 'small_pool_turnover'
    assert mw.admission(liquidity_usd=5_000, volume_5m_usd=5_000) is None
    assert mw.admission(liquidity_usd=20_000, volume_5m_usd=25_000) == 'small_pool_turnover'
    assert mw.admission(liquidity_usd=20_001, volume_5m_usd=100_000) is None
    # exactly at the boundary the mid rule wins, and the small rule is exclusive
    assert mw.admission(liquidity_usd=20_000, buys_5m=80, sells_5m=20) == 'mid_pool_buy_share'
    assert mw.admission(liquidity_usd=20_000, buys_5m=30, sells_5m=70,
                        volume_5m_usd=25_000) == 'small_pool_turnover'


def test_missing_or_invalid_values_never_admit():
    for kwargs in ({}, {'liquidity_usd': None}, {'liquidity_usd': 'x'},
                   {'liquidity_usd': 0}, {'liquidity_usd': -5},
                   {'liquidity_usd': float('nan')}):
        assert mw.admission(**kwargs) is None


def test_a_token_is_considered_only_once():
    registry = mw.Registry()
    assert registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                             now=NOW) == 'mid_pool_buy_share'
    assert registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                             now=NOW) is None
    assert registry.counts['already_considered'] == 1
    assert registry.active(NOW) == {'solana:A'}


def test_entries_expire_after_the_watch_window():
    registry = mw.Registry(watch_seconds=600)
    registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    assert registry.active(NOW + timedelta(seconds=599)) == {'solana:A'}
    assert registry.active(NOW + timedelta(seconds=600)) == set()
    assert registry.counts['expired'] == 1
    # an expired token is not re-admitted, because it was already considered
    assert registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                             now=NOW + timedelta(seconds=601)) is None


def test_the_registry_is_bounded_and_reports_being_full():
    registry = mw.Registry(max_watched=3)
    for index in range(5):
        registry.consider('solana:T%d' % index, liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                          now=NOW)
    assert len(registry.active(NOW)) == 3
    assert registry.counts['full'] == 2
    # freeing a slot by expiry lets the next candidate in
    registry.consider('solana:LATER', liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                      now=NOW + timedelta(seconds=901))
    assert 'solana:LATER' in registry.active(NOW + timedelta(seconds=901))


def test_snapshot_reports_counters_without_raising():
    registry = mw.Registry()
    registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    registry.consider('solana:B', liquidity_usd=1_000, buys_5m=1, sells_5m=99, now=NOW)
    snap = registry.snapshot(NOW)
    assert snap['version'] == mw.VERSION
    assert snap['watching'] == 1
    assert snap['counts']['admitted:mid_pool_buy_share'] == 1
    assert snap['counts']['rejected'] == 1
