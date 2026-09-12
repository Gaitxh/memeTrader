"""Reserved mover slots reach the admission loop as candidates (round 101 -> round 108).

Round 101 measured a **0-of-24 overlap** between the flagged set and the leases the pattern
observer held: reserved admission was only reachable from the rejection path
(`skip_bucket_full`), so it fired about 6 times an hour against a design of 32. The registry is
filled at a token's FIRST observation, where its quote is already in hand, so the runtime now
caches that frame and replays it at the head of the admission loop on the pattern-observer tick.

These tests drive the real runtime methods against a stub carrier, so the decision under test is
the shipped one: which cached frames are offered, and whether the ordinary admission loop then
admits them.
"""
import inspect
import types
from datetime import datetime, timedelta, timezone

from memetrader import mover_watchlist as mw
from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.runtime import (
    MOVER_CACHED_QUOTE_SECONDS,
    MOVER_RESERVED_SLOTS,
    Runtime,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 12, 11, 0, tzinfo=UTC)
FLAGGED = 'solana:FlaggedMover111111111111111111111111111111'


def _frame(token_id=FLAGGED, *, now=NOW, liquidity=90_000.0, price=0.001):
    """One already-observed first frame: a mid pool with buy share .75, i.e. rule-flagged."""
    chain, address = token_id.split(':', 1)
    created_ms = int((now - timedelta(seconds=600)).timestamp() * 1000)
    token = TokenCandidate(chain, address, 'flagged')
    snapshot = TokenSnapshot(
        chain=chain, address=address, price_usd=price, liquidity_usd=liquidity,
        market_cap_usd=1_000_000.0, volume_5m_usd=30_000.0, buys_5m=90, sells_5m=30,
        observed_at=now, provider='dexscreener',
        raw={'pair': {'pairAddress': address, 'pairCreatedAt': created_ms}},
    )
    return token, snapshot


def _stub(*, registry=None, cache=None, watch=None, priority=()):
    stub = types.SimpleNamespace(
        _mover_watchlist=registry,
        _mover_first_quote=dict(cache or {}),
        _pattern_watch=dict(watch or {}),
        _market_priority_tokens=set(priority),
    )
    # Bind the shipped helper so the admission loop under test calls the real one.
    stub._reserved_mover_quotes = lambda current: Runtime._reserved_mover_quotes(stub, current)
    return stub


def _flagged_registry(*token_ids, now=NOW):
    registry = mw.Registry()
    for token_id in token_ids:
        assert registry.consider(token_id, liquidity_usd=90_000, buys_5m=90, sells_5m=30,
                                 now=now) == 'mid_pool_buy_share'
    return registry


def test_pattern_observer_is_the_injection_point():
    """The wiring itself: the observer's own admission tick asks for reserved candidates."""
    assert inspect.getsource(Runtime.chain_meme_pattern_observer_once).count(
        'reserved_movers=True') == 1


def test_first_frame_of_a_flagged_token_is_offered():
    token, snapshot = _frame()
    stub = _stub(registry=_flagged_registry(FLAGGED), cache={FLAGGED: (token, snapshot)})
    assert Runtime._reserved_mover_quotes(stub, NOW) == {FLAGGED: (token, snapshot)}


def test_injected_candidate_is_admitted_by_the_ordinary_loop():
    token, snapshot = _frame()
    stub = _stub(registry=_flagged_registry(FLAGGED), cache={FLAGGED: (token, snapshot)})
    Runtime._remember_pattern_quotes(stub, {}, reserved_movers=True)
    item = stub._pattern_watch[FLAGGED]
    assert item['bucket'] == 'early' and item['quote'] is snapshot
    assert stub._mover_reserved_injections == 1


def test_without_the_flag_the_reservation_stays_on_the_old_path():
    """Default behaviour is unchanged: an empty quote dict admits nothing."""
    token, snapshot = _frame()
    stub = _stub(registry=_flagged_registry(FLAGGED), cache={FLAGGED: (token, snapshot)})
    Runtime._remember_pattern_quotes(stub, {})
    assert stub._pattern_watch == {}
    assert getattr(stub, '_mover_reserved_injections', 0) == 0


def test_stale_cached_frame_is_dropped_rather_than_admitted():
    token, snapshot = _frame()
    snapshot.observed_at = NOW - timedelta(seconds=MOVER_CACHED_QUOTE_SECONDS + 60)
    stub = _stub(registry=_flagged_registry(FLAGGED), cache={FLAGGED: (token, snapshot)})
    assert Runtime._reserved_mover_quotes(stub, NOW) == {}
    assert FLAGGED not in stub._mover_first_quote


def test_token_already_in_the_watch_or_on_the_priority_lane_is_not_offered():
    token, snapshot = _frame()
    cache = {FLAGGED: (token, snapshot)}
    assert Runtime._reserved_mover_quotes(
        _stub(registry=_flagged_registry(FLAGGED), cache=cache, watch={FLAGGED: {}}), NOW) == {}
    assert Runtime._reserved_mover_quotes(
        _stub(registry=_flagged_registry(FLAGGED), cache=cache, priority=[FLAGGED]), NOW) == {}


def test_a_full_reservation_offers_nothing_and_never_exceeds_its_ceiling():
    ids = [f'solana:Mover{i:02d}' for i in range(MOVER_RESERVED_SLOTS + 1)]
    held = {token_id: {} for token_id in ids[:MOVER_RESERVED_SLOTS]}
    frame_last, snapshot_last = _frame(ids[-1])
    frame_freed, snapshot_freed = _frame(ids[-2])
    cache = {ids[-1]: (frame_last, snapshot_last), ids[-2]: (frame_freed, snapshot_freed)}
    stub = _stub(registry=_flagged_registry(*ids), cache=cache, watch=held)
    assert Runtime._reserved_mover_quotes(stub, NOW) == {}
    # One slot freed: exactly one candidate, and it is the one the ceiling made room for.
    stub._pattern_watch.pop(ids[-2])
    assert Runtime._reserved_mover_quotes(stub, NOW) == {ids[-2]: (frame_freed, snapshot_freed)}


def test_broken_registry_degrades_to_no_candidates():
    token, snapshot = _frame()

    class Broken:
        def active(self, now):
            raise RuntimeError('boom')

    stub = _stub(registry=Broken(), cache={FLAGGED: (token, snapshot)})
    assert Runtime._reserved_mover_quotes(stub, NOW) == {}
    Runtime._remember_pattern_quotes(stub, {}, reserved_movers=True)
    assert stub._pattern_watch == {}
