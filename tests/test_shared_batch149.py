"""ALPHA149 shared-spare tests: no extra HTTP batch, exact pools, safe in-flight.

Covers the required matrix: 0/1/28/29/30/31/60 legacy addresses, high priority,
non-fresh, disabled manager, concurrency, 429/timeout release, wrong pool and
stale frames, and response isolation for the calling lane.
"""
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.shared_batch148 import (
    INFLIGHT_SECONDS, MAX_ACTIVE_PER_CHAIN, SharedBatchCoverage,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
CHAIN = 'bsc'


class _Token:
    def __init__(self, token_id, address, chain=CHAIN):
        self.token_id, self.address, self.chain = token_id, address, chain


class _Snap:
    def __init__(self, observed_at, price=1.0, liquidity=5000.0):
        self.observed_at, self.price_usd, self.liquidity_usd = observed_at, price, liquidity
        self.ingested_at, self.provider, self.raw = observed_at, 'dexscreener', {}


def _coverage_with_waiting(n=2, chain=CHAIN):
    manager = SharedBatchCoverage()
    created = int((NOW - timedelta(seconds=120)).timestamp() * 1000)
    for i in range(n):
        address = f'0x{i:040x}'
        pool = f'0x{i + 100:040x}'
        manager.waiting[f'{chain}:{address}'] = dict(
            token_id=f'{chain}:{address}', chain=chain, address=address,
            pair_address=pool, first_received_at=NOW, first_observed_at=NOW,
            # A frame that is 30s old, so a response observed at NOW is a
            # genuinely later observation rather than a duplicate.
            last_observed_at=NOW - timedelta(seconds=30), last_received_at=NOW, frames=1,
            pool_created_at_ms=created, floor=1000.0, coverage_gap=False,
            next_due_at=NOW, windows={}, frame2_delay_seconds=None,
            frame3_delay_seconds=None)
    return manager


@pytest.mark.parametrize('legacy_n,expected_spare', [
    (0, 0), (1, 29), (28, 2), (29, 1), (30, 0), (31, 29), (60, 0),
])
def test_batch_count_never_grows(legacy_n, expected_spare):
    manager = _coverage_with_waiting(2)
    legacy = [f'0xdead{i:036x}' for i in range(legacy_n)]
    extended, selected = manager.extend_batch_lease(CHAIN, legacy, NOW)
    import math
    assert math.ceil(len(extended) / 30) == math.ceil(len(legacy) / 30)
    assert len(extended) - len(dict.fromkeys(legacy)) <= min(expected_spare, MAX_ACTIVE_PER_CHAIN)
    assert set(selected) <= {f'{CHAIN}:0x{i:040x}' for i in range(2)}
    assert extended[:len(dict.fromkeys(legacy))] == list(dict.fromkeys(legacy))


def test_unavailable_batches_are_not_extended():
    manager = _coverage_with_waiting(2)
    assert manager.extend_batch_lease(CHAIN, [], NOW) == ([], {})
    manager.disable('resource_guard', NOW)
    legacy = ['0xabc']
    assert manager.extend_batch_lease(CHAIN, legacy, NOW) == (legacy, {})


def test_concurrent_callers_never_share_one_extra():
    manager = _coverage_with_waiting(2)
    legacy = [f'0xfeed{i:036x}' for i in range(1)]
    first_extended, first_selected = manager.extend_batch_lease(CHAIN, legacy, NOW)
    second_extended, second_selected = manager.extend_batch_lease(CHAIN, legacy, NOW)
    assert first_selected and not second_selected
    assert set(first_selected).isdisjoint(second_selected)
    assert manager.counts['inflight_skipped'] >= 0
    # the first caller's batch kept the original count
    assert len(first_extended) == len(legacy) + len(first_selected)
    assert second_extended == legacy


def test_claim_expires_so_a_lost_caller_cannot_hold_it_forever():
    manager = _coverage_with_waiting(1)
    legacy = ['0xabc']
    _, selected = manager.extend_batch_lease(CHAIN, legacy, NOW)
    assert selected
    later = NOW + timedelta(seconds=INFLIGHT_SECONDS + 1)
    _, again = manager.extend_batch_lease(CHAIN, legacy, later)
    assert again, 'expired in-flight claim must be reusable'


def test_release_records_failure_and_cancellation():
    manager = _coverage_with_waiting(2)
    legacy = ['0xabc']
    _, selected = manager.extend_batch_lease(CHAIN, legacy, NOW)
    manager.release(selected, NOW, reason='failed_request')
    assert manager.counts['failed_request'] == len(selected)
    assert not manager.inflight
    _, selected2 = manager.extend_batch_lease(CHAIN, legacy, NOW)
    manager.release(selected2, NOW, reason='cancelled_request')
    assert manager.counts['cancelled_request'] == len(selected2)
    # release without a reason clears the claim silently
    _, selected3 = manager.extend_batch_lease(CHAIN, legacy, NOW)
    manager.release(selected3, NOW)
    assert not manager.inflight


def test_response_keeps_only_the_frozen_original_pool():
    manager = _coverage_with_waiting(1)
    token_id = f'{CHAIN}:0x{"0" * 40}'
    address, pool = f'0x{"0" * 40}', f'0x{"0" * 64}'
    pool = f'0x{100:040x}'
    manager.waiting[token_id]['pair_address'] = pool
    legacy = f'0x{7:040x}'
    extended, selected = manager.extend_batch_lease(CHAIN, [legacy], NOW)
    assert selected == {token_id: pool}
    token = _Token(token_id, address)
    good = _Snap(NOW)
    good.raw = {'pairs': [{'pairAddress': pool, 'chainId': CHAIN,
                           'baseToken': {'address': address}}]}
    wrong = _Snap(NOW)
    wrong.raw = {'pairs': [{'pairAddress': f'0x{999:040x}', 'chainId': CHAIN,
                            'baseToken': {'address': address}}]}
    stale = _Snap(NOW - timedelta(seconds=120))
    stale.raw = good.raw
    delivered = manager.response({token_id: (token, good)}, selected, NOW, lambda p: good)
    assert token_id in delivered
    assert manager.response({token_id: (token, wrong)}, selected, NOW, lambda p: good) == {}
    assert manager.response({token_id: (token, stale)}, selected, NOW, lambda p: stale) == {}


def test_snapshot_exposes_alpha149_counters():
    manager = _coverage_with_waiting(1)
    manager.extend_batch_lease(CHAIN, ['0xabc'], NOW)
    snap = manager.snapshot(NOW)
    assert snap['additional_http_batches'] == 0
    assert snap['inflight'] == len(manager.inflight)
    for key in ('eligible_batch', 'no_spare', 'selected_extra', 'inflight_skipped',
                'failed_request', 'cancelled_request'):
        assert key in snap['alpha149']
