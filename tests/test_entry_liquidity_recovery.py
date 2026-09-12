"""Entry-liquidity recovery and mirror-payload compaction (2026-09-12 audit items)."""
import json
import sys
from datetime import timedelta

sys.path.insert(0, __file__.rsplit('\\', 1)[0])

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow  # noqa: E402
from memetrader.store import (  # noqa: E402
    CARRIED_LIQUIDITY_MAX_AGE_SECONDS,
    CURVE_STAGE_DEX_IDS,
    KNOWN_AMM_DEX_IDS,
    _compact_mirror_pair,
)
from test_resource_bound_store import setup_store  # noqa: E402

CHAIN, ADDRESS, POOL = 'solana', 'TokenAddr1111111111111111111111111111111', 'PoolAddr11111111111111111111111111111111'
OTHER_POOL = 'PoolAddr22222222222222222222222222222222'


def _snapshot(chain, address, pool, *, observed_at, liquidity):
    raw = {'pair': {'pairAddress': pool, 'chainId': chain,
                    'baseToken': {'address': address}, 'liquidity': {'usd': liquidity}}}
    return TokenSnapshot(chain=chain, address=address, price_usd=0.001, liquidity_usd=liquidity,
                         market_cap_usd=1.0, volume_5m_usd=10.0, buys_5m=1, sells_5m=1,
                         observed_at=observed_at, provider='dexscreener', raw=raw)


def test_carried_forward_within_the_bound_is_used(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    now = utcnow()
    earlier = now - timedelta(seconds=20)
    store.add_snapshot(_snapshot(CHAIN, ADDRESS, POOL, observed_at=earlier, liquidity=42_000.0))
    carried = store._latest_known_pool_liquidity(
        f'{CHAIN}:{ADDRESS}', POOL, CHAIN, before=now,
        max_age_seconds=CARRIED_LIQUIDITY_MAX_AGE_SECONDS)
    assert carried is not None
    value, basis = carried
    assert value == 42_000.0
    assert basis.startswith('carried_forward:')
    assert basis.endswith('s')
    store.close()


def test_stale_history_is_refused(tmp_path, monkeypatch):
    """The median age of the last known liquidity for these tokens is ~5.9 hours; judging a pool on an
    hours-old number is exactly what the bound exists to prevent."""
    store, _ = setup_store(tmp_path, monkeypatch)
    now = utcnow()
    store.add_snapshot(_snapshot(CHAIN, ADDRESS, POOL, observed_at=now - timedelta(minutes=10),
                                 liquidity=42_000.0))
    assert store._latest_known_pool_liquidity(
        f'{CHAIN}:{ADDRESS}', POOL, CHAIN, before=now,
        max_age_seconds=CARRIED_LIQUIDITY_MAX_AGE_SECONDS) is None
    store.close()


def test_history_of_another_pool_is_refused(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    now = utcnow()
    store.add_snapshot(_snapshot(CHAIN, ADDRESS, OTHER_POOL, observed_at=now - timedelta(seconds=5),
                                 liquidity=42_000.0))
    assert store._latest_known_pool_liquidity(
        f'{CHAIN}:{ADDRESS}', POOL, CHAIN, before=now,
        max_age_seconds=CARRIED_LIQUIDITY_MAX_AGE_SECONDS) is None
    store.close()


def test_a_later_observation_is_never_used(tmp_path, monkeypatch):
    """Point-in-time discipline: the carry-forward may only look backwards."""
    store, _ = setup_store(tmp_path, monkeypatch)
    now = utcnow()
    store.add_snapshot(_snapshot(CHAIN, ADDRESS, POOL, observed_at=now + timedelta(seconds=30),
                                 liquidity=42_000.0))
    assert store._latest_known_pool_liquidity(
        f'{CHAIN}:{ADDRESS}', POOL, CHAIN, before=now,
        max_age_seconds=CARRIED_LIQUIDITY_MAX_AGE_SECONDS) is None
    store.close()


def test_rows_without_liquidity_are_skipped(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    now = utcnow()
    store.add_snapshot(_snapshot(CHAIN, ADDRESS, POOL, observed_at=now - timedelta(seconds=10),
                                 liquidity=None))
    assert store._latest_known_pool_liquidity(
        f'{CHAIN}:{ADDRESS}', POOL, CHAIN, before=now,
        max_age_seconds=CARRIED_LIQUIDITY_MAX_AGE_SECONDS) is None
    store.close()


def test_curve_stage_and_amm_sets_do_not_overlap():
    assert not (CURVE_STAGE_DEX_IDS & KNOWN_AMM_DEX_IDS)
    # the two families measured in the audit must be classified
    assert 'pumpfun' in CURVE_STAGE_DEX_IDS and 'fourmeme' in CURVE_STAGE_DEX_IDS
    assert 'uniswap-v4-bsc' in KNOWN_AMM_DEX_IDS and 'pancakeswap-infinity-clmm' in KNOWN_AMM_DEX_IDS


def test_mirror_compaction_keeps_every_consumed_field():
    """The kept set is the union of what every consumer reads (SQL json_extract paths, the entry
    history reconstruction, the participant-flow walker, the token page, the offline scripts)."""
    pair = {
        'pairAddress': 'P', 'chainId': 'solana', 'dexId': 'pumpfun', 'labels': ['v4'],
        'pairCreatedAt': 1, 'priceNative': '1', 'priceUsd': '0.001', 'url': 'u',
        'baseToken': {'address': 'B', 'name': 'n', 'symbol': 's', 'extra': 1},
        'quoteToken': {'address': 'Q', 'name': 'q', 'symbol': 'w'},
        'liquidity': {'usd': 1000.0, 'base': 1, 'quote': 2, 'extra': 9},
        'volume': {'m5': 1, 'h1': 2, 'h6': 3, 'h24': 4, 'h48': 5},
        'txns': {'m5': {'buys': 1, 'sells': 2, 'buyers': 3, 'sellers': 4, 'extra': 5},
                 'h1': {'buys': 6, 'sells': 7}, 'h6': {}, 'h24': {}},
        'priceChange': {'m5': 1, 'h1': 2, 'h6': 3, 'h24': 4, 'h48': 5},
        'info': {'websites': [], 'socials': []},
        'fdv': 1, 'marketCap': 2, 'boosts': {'x': 1}, 'header': {'x': 1},
    }
    out = _compact_mirror_pair(pair)
    for key in ('pairAddress', 'chainId', 'dexId', 'labels', 'pairCreatedAt', 'priceNative', 'url',
                'baseToken', 'quoteToken', 'liquidity', 'volume', 'txns', 'priceChange', 'info'):
        assert key in out, key
    assert out['baseToken'] == {'address': 'B', 'name': 'n', 'symbol': 's'}
    assert out['quoteToken'] == {'address': 'Q', 'name': 'q', 'symbol': 'w'}
    assert out['liquidity'] == {'usd': 1000.0, 'base': 1, 'quote': 2}
    assert out['txns']['m5'] == {'buys': 1, 'sells': 2, 'buyers': 3, 'sellers': 4}
    assert out['volume'] == {'m5': 1, 'h1': 2, 'h6': 3, 'h24': 4}
    for dropped in ('fdv', 'marketCap', 'priceUsd', 'boosts', 'header'):
        assert dropped not in out, dropped
    assert len(json.dumps(out, ensure_ascii=False)) < len(json.dumps(pair, ensure_ascii=False))


def test_mirror_compaction_passes_unrecognised_payloads_through():
    assert _compact_mirror_pair({'rugcheck': 1}) == {'rugcheck': 1}
    assert _compact_mirror_pair(None) is None
