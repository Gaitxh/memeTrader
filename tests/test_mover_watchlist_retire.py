"""Tests for the watch-list retirement behaviour added in round 85."""
from datetime import datetime, timedelta, timezone

from memetrader import mover_watchlist as mw

UTC = timezone.utc
NOW = datetime(2026, 9, 12, 7, 0, tzinfo=UTC)


def test_retire_removes_a_token_and_counts_once():
    registry = mw.Registry()
    registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    assert registry.active(NOW) == {'solana:A'}
    registry.retire('solana:A')
    assert registry.active(NOW) == set()
    assert registry.counts['retired'] == 1
    # retiring something that is not watched is a no-op, not an error
    registry.retire('solana:A')
    assert registry.counts['retired'] == 1


def test_a_retired_token_does_not_come_back_and_frees_its_slot():
    registry = mw.Registry(max_watched=1)
    registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    registry.consider('solana:B', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    assert registry.counts['full'] == 1
    registry.retire('solana:A')
    registry.consider('solana:C', liquidity_usd=50_000, buys_5m=70, sells_5m=30, now=NOW)
    assert registry.active(NOW) == {'solana:C'}
    # the retired token was already considered, so it cannot re-enter
    assert registry.consider('solana:A', liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                             now=NOW) is None
    assert registry.active(NOW) == {'solana:C'}


def test_retirement_keeps_the_registry_within_its_cap_over_time():
    registry = mw.Registry(max_watched=3)
    sizes = []
    for index in range(9):
        registry.consider('solana:T%d' % index, liquidity_usd=50_000, buys_5m=70, sells_5m=30,
                          now=NOW + timedelta(seconds=index))
        if index % 3 == 0:
            for token in list(registry.active(NOW + timedelta(seconds=index))):
                registry.retire(token)
        sizes.append(len(registry.active(NOW + timedelta(seconds=index))))
    assert max(sizes) <= 3
    assert registry.counts['retired'] >= 3
