"""Candidate injection for the reserved mover slots (round 101 diagnosis -> round 104 helper).

Round 101 measured a 0-of-24 overlap between the flagged set and the leases the observer holds,
because reserved admission was only reachable from the rejection path. This helper produces the
candidates a caller should inject instead. It is not wired into the runtime yet.
"""
from datetime import datetime, timezone

from memetrader import mover_watchlist as mw

UTC = timezone.utc
NOW = datetime(2026, 9, 12, 11, 0, tzinfo=UTC)


def _registry(*tokens):
    registry = mw.Registry()
    for token in tokens:
        registry.consider(token, liquidity_usd=90_000, buys_5m=80, sells_5m=20, now=NOW)
    return registry


def test_returns_flagged_tokens_the_watch_does_not_hold():
    registry = _registry('solana:A', 'solana:B', 'solana:C')
    assert mw.reserved_candidates(registry, {}, NOW, 8) == ['solana:A', 'solana:B', 'solana:C']
    assert mw.reserved_candidates(registry, {'solana:A': {}}, NOW, 8) == ['solana:B', 'solana:C']


def test_never_exceeds_the_room_left_in_the_reservation():
    registry = _registry('solana:A', 'solana:B', 'solana:C')
    assert mw.reserved_candidates(registry, {}, NOW, 1) == ['solana:A']
    assert mw.reserved_candidates(registry, {'solana:A': {}}, NOW, 2) == ['solana:B']
    # a full reservation yields nothing, and only FLAGGED watch entries consume it
    assert mw.reserved_candidates(registry, {'solana:A': {}, 'x': {}, 'y': {}}, NOW, 1) == []


def test_unflagged_watch_entries_do_not_consume_the_reservation():
    registry = _registry('solana:A')
    watch = {('plain%d' % i): {} for i in range(30)}
    assert mw.reserved_candidates(registry, watch, NOW, 8) == ['solana:A']


def test_degrades_to_no_candidates_and_never_raises():
    registry = _registry('solana:A')
    assert mw.reserved_candidates(None, {}, NOW, 8) == []
    assert mw.reserved_candidates(registry, {}, NOW, 0) == []
    assert mw.reserved_candidates(registry, {}, NOW, -1) == []

    class Broken:
        def active(self, now):
            raise RuntimeError('boom')

    assert mw.reserved_candidates(Broken(), {}, NOW, 8) == []


def test_no_candidates_when_nothing_is_flagged():
    assert mw.reserved_candidates(mw.Registry(), {}, NOW, 8) == []
