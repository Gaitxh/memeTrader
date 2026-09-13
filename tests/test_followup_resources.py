from datetime import timedelta
from types import SimpleNamespace

import pytest

from memetrader.followup_resources import PoolFollowupResources
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.mover_watchlist import Registry
from memetrader.runtime import Runtime


def frame(at, *, liquidity=0., price=1., volume=0., buys=0, pool='pool-a'):
    token = TokenCandidate('solana', 'token-a', 'A')
    snap = TokenSnapshot('solana', 'token-a', price, liquidity, 100., volume, buys, 0,
        provider='dexscreener', observed_at=at, ingested_at=at,
        raw={'pair': {'chainId': 'solana', 'pairAddress': pool,
                     'baseToken': {'address': 'token-a'},
                     'pairCreatedAt': (at - timedelta(minutes=10)).timestamp() * 1000}})
    return token, snap


def observe(manager, at, **kwargs):
    manager.observe(*frame(at, **kwargs), at)


def test_two_independent_empty_frames_retire_only_the_exact_pool():
    now = utcnow()
    manager = PoolFollowupResources()
    observe(manager, now)
    assert not manager.blocked('solana:token-a', 'pool-a')
    observe(manager, now)  # duplicate receipt
    assert not manager.retired
    observe(manager, now + timedelta(seconds=10))
    assert manager.blocked('solana:token-a', 'pool-a')
    assert not manager.blocked('solana:token-a', 'pool-b')
    restored = PoolFollowupResources(manager.state())
    assert restored.blocked('solana:token-a', 'pool-a')
    observe(restored, now + timedelta(seconds=20), liquidity=5000)
    assert not restored.retired


@pytest.mark.parametrize('liquidity,volume,buys', [
    (None, 0, 0), (float('nan'), 0, 0), (-1, 0, 0),
    (0, None, 0), (0, 2000, 50), (0, 0, None), (2000, 0, 0),
])
def test_unknown_active_or_invalid_is_not_dead(liquidity, volume, buys):
    now = utcnow()
    manager = PoolFollowupResources()
    for seconds in (0, 10):
        observe(manager, now + timedelta(seconds=seconds), liquidity=liquidity, volume=volume, buys=buys)
    assert not manager.retired


def test_collapse_needs_same_pool_peak_and_thin_depth():
    now = utcnow()
    manager = PoolFollowupResources()
    observe(manager, now, liquidity=10000, price=100.)
    observe(manager, now + timedelta(seconds=10), price=.001, liquidity=5, volume=20)
    assert not manager.retired
    observe(manager, now + timedelta(seconds=20), price=.001, liquidity=5, volume=20)
    assert manager.blocked('solana:token-a', 'pool-a')
    observe(manager, now + timedelta(seconds=30), pool='pool-b', price=.001, liquidity=5000)
    assert not manager.blocked('solana:token-a', 'pool-b')


def test_stale_future_or_wrong_identity_frames_cannot_retire():
    now = utcnow()
    manager = PoolFollowupResources()
    for offset in (-50, 10):
        token, snap = frame(now + timedelta(seconds=offset))
        manager.observe(token, snap, now)
    for offset in (0, 10):
        token, snap = frame(now + timedelta(seconds=offset))
        snap.raw['pair']['baseToken']['address'] = 'wrong'
        manager.observe(token, snap, snap.observed_at)
    assert not manager.frames and not manager.retired


@pytest.mark.parametrize('protected', [False, True])
def test_runtime_releases_mover_slot_but_keeps_held_or_pending_work(monkeypatch, protected):
    now = utcnow()
    token, snap = frame(now)
    mover = Registry()
    mover.consider(token.token_id, liquidity_usd=40000, buys_5m=70, sells_5m=30, now=now)
    runtime = SimpleNamespace(
        _pattern_watch={token.token_id: dict(token=token, quote=snap,
            pair_address='pool-a', bucket='early', expires_at=now + timedelta(minutes=15),
            min_observe_until=now + timedelta(minutes=2))},
        _mover_watchlist=mover, _pattern_held_tokens={token.token_id} if protected else set(),
        _paper_quote_rejections=lambda *args: [],
    )
    for seconds in (0, 10):
        at = now + timedelta(seconds=seconds)
        monkeypatch.setattr('memetrader.runtime.utcnow', lambda: at)
        Runtime._remember_pattern_quotes(runtime, {token.token_id: frame(at)})
    assert (token.token_id in runtime._pattern_watch) is protected
    assert (token.token_id in mover.active(now)) is protected
    assert runtime._pool_followup_resources.blocked(token.token_id, 'pool-a')
