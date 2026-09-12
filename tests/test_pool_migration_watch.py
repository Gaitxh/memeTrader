"""Pool migration: a graduated token's NEW pool must reach the observation surface.

Measured 2026-09-12: of 17,529 tokens first rejected for unknown liquidity in 24h, 26.3% later produced a
liquidity-bearing frame, but the watch is keyed by token, so a frame for another pool was skipped as
`skip_other_pool` and the token never came back into judgement (only 3 of those 17,529 were ever
bought). The fix moves the watch entry onto the newer pool, and only when the current pool is unusable.
"""
import types
from datetime import timedelta

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.runtime import Runtime

# The freshness gate compares against the real clock inside `_remember_pattern_quotes`, so every
# fixture timestamp has to be built at CALL time. A module-level constant goes stale while a slow suite
# runs (test_core alone takes minutes), and the gate then rejects frames that are meant to be fresh -
# which is exactly how these two tests became flaky.
OLD_POOL = 'OldPool1111111111111111111111111111111111'
NEW_POOL = 'NewPool2222222222222222222222222222222222'
ADDRESS = 'TokenAddr111111111111111111111111111111111'
TOKEN_ID = f'solana:{ADDRESS}'


def _snapshot(*, pool, created_at, liquidity, price=0.001, observed_at=None):
    raw = {'pair': {'pairAddress': pool, 'chainId': 'solana', 'priceUsd': str(price),
                    'pairCreatedAt': int(created_at.timestamp() * 1000),
                    'baseToken': {'address': ADDRESS},
                    'liquidity': {'usd': liquidity}}}
    return TokenSnapshot(chain='solana', address=ADDRESS, price_usd=price, liquidity_usd=liquidity,
                         market_cap_usd=1.0, volume_5m_usd=10.0, buys_5m=1, sells_5m=1,
                         observed_at=observed_at or utcnow(), provider='dexscreener', raw=raw)


def _stub(*, old_liquidity, held=(), protected=()):
    """A watch entry for the ORIGINAL pool, plus a frame for the NEW (graduated) pool."""
    now = utcnow()
    old_created = now - timedelta(hours=3)
    new_created = now - timedelta(minutes=5)
    token = TokenCandidate('solana', ADDRESS, 'graduated')
    old_quote = _snapshot(pool=OLD_POOL, created_at=old_created, liquidity=old_liquidity,
                          observed_at=now)
    new_quote = _snapshot(pool=NEW_POOL, created_at=new_created, liquidity=25_000.0, observed_at=now)
    stub = types.SimpleNamespace(
        _pattern_watch={TOKEN_ID: {
            'token': token, 'bucket': 'growth', 'quote': old_quote,
            'pool_created_at_ms': float(int(old_created.timestamp() * 1000)),
            'pair_address': OLD_POOL, 'expires_at': now + timedelta(minutes=10),
            'admitted_at': now - timedelta(minutes=2), 'frame_count': 4,
            'last_useful_at': now - timedelta(seconds=20)}},
        _chain_paper_execution={'min_pool_liquidity_usd': 1000.0},
        _pattern_held_tokens=set(held), _market_priority_tokens=set(),
        _pattern_pending_tokens=set(), _cohort_pending={}, _market_entry_pending_tokens=set(),
        _preentry_safety=None, _pattern_ready_until={}, _shared_batch148=None,
        _paper_quote_rejections=lambda *a, **k: False,
    )
    return stub, token, new_quote


def _watch(stub):
    return stub._pattern_watch[TOKEN_ID]


def test_a_graduated_tokens_new_pool_replaces_an_unusable_old_pool():
    stub, token, new_quote = _stub(old_liquidity=None)  # the curve listing had no liquidity
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, new_quote)})
    item = _watch(stub)
    assert item['pair_address'] == NEW_POOL
    assert item['migrated_from_pool'] == OLD_POOL
    assert item['quote'] is new_quote
    assert item['frame_count'] == 0 and item['last_useful_at'] is None
    assert stub._pattern_watch_pool_migrations == 1
    assert stub._pattern_watch_migrated_tokens[TOKEN_ID]['to'] == NEW_POOL
    assert getattr(stub, '_pattern_watch_other_pool_skips', 0) == 0


def test_a_healthy_pool_is_never_displaced():
    """The old pool still has liquidity, so the new frame stays a plain other-pool skip."""
    stub, token, new_quote = _stub(old_liquidity=40_000.0)
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, new_quote)})
    item = _watch(stub)
    assert item['pair_address'] == OLD_POOL
    assert 'migrated_from_pool' not in item
    assert stub._pattern_watch_other_pool_skips == 1
    assert getattr(stub, '_pattern_watch_pool_migrations', 0) == 0


def test_a_held_token_is_never_migrated():
    stub, token, new_quote = _stub(old_liquidity=None, held={TOKEN_ID})
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, new_quote)})
    assert _watch(stub)['pair_address'] == OLD_POOL
    assert getattr(stub, '_pattern_watch_pool_migrations', 0) == 0


def test_the_new_pool_must_be_newer():
    """Oscillating between two live listings is not a migration."""
    old_created = utcnow() - timedelta(hours=3)
    stale = _snapshot(pool=NEW_POOL, created_at=old_created - timedelta(hours=1), liquidity=25_000.0)
    stub, token, _ = _stub(old_liquidity=None)
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, stale)})
    assert _watch(stub)['pair_address'] == OLD_POOL
    assert getattr(stub, '_pattern_watch_pool_migrations', 0) == 0


def test_the_new_pool_must_clear_the_liquidity_floor():
    stub, token, _ = _stub(old_liquidity=None)
    thin = _snapshot(pool=NEW_POOL, created_at=utcnow() - timedelta(minutes=5), liquidity=250.0)
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, thin)})
    assert _watch(stub)['pair_address'] == OLD_POOL
    assert getattr(stub, '_pattern_watch_pool_migrations', 0) == 0


def test_a_stale_new_pool_frame_is_refused():
    stub, token, _ = _stub(old_liquidity=None)
    now = utcnow()
    stale = _snapshot(pool=NEW_POOL, created_at=now - timedelta(minutes=5), liquidity=25_000.0,
                      observed_at=now - timedelta(seconds=120))
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, stale)})
    assert _watch(stub)['pair_address'] == OLD_POOL
    assert getattr(stub, '_pattern_watch_pool_migrations', 0) == 0


def test_the_migrated_entry_keeps_the_bucket_of_the_new_pool():
    """A 5-minute-old pool is 'early'; the old entry was 'growth'."""
    stub, token, new_quote = _stub(old_liquidity=None)
    Runtime._remember_pattern_quotes(stub, {TOKEN_ID: (token, new_quote)})
    assert _watch(stub)['bucket'] == 'early'
