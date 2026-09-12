"""Bounded mover watch-list: which tokens deserve dense observation.

Measured basis (2026-09-12, point-in-time features only, four independent six-hour windows):

    rule                                    flag rate   precision   lift
    liq >= 20k and buy share >= 0.6            14-19%      16-35%   1.2-1.9x
    liq <= 20k and volume_5m/liq > 1.0          3-4%       15-55%   1.0-2.3x
    union of the two                           20-25%      17-36%   1.35-1.95x

Base rate of a token doubling within an hour of its first observation is 10-25% depending on how
strictly the observed population is defined. The two rules describe different archetypes (a
mid-depth pool dominated by buys, and a small frantic pool) and their recall is low either way:
the union catches about a third of the tokens that double, so this is a density improvement on the
watched set, not a detector.

Admission reads ONLY the first observation of a token, so nothing later can leak into it. The
registry is bounded and in-memory: it never raises, never writes, and if it is full the youngest
qualifying token wins only when an expired slot exists.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Mapping

WATCH_SECONDS = 900.0
MAX_WATCHED = 240
MID_POOL_MIN_LIQUIDITY = 20_000.0
MID_POOL_MIN_BUY_SHARE = 0.6
SMALL_POOL_MAX_LIQUIDITY = 20_000.0
SMALL_POOL_MIN_TURNOVER = 1.0
VERSION = 'mover-watchlist/v1'


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def admission(*, liquidity_usd: Any = None, buys_5m: Any = None, sells_5m: Any = None,
              volume_5m_usd: Any = None) -> str | None:
    """Name of the rule that admits this first observation, or None.

    Both rules need the liquidity to be known; a missing value is never treated as qualifying.
    """
    liquidity = _num(liquidity_usd)
    if liquidity is None or liquidity <= 0:
        return None
    buys = _num(buys_5m)
    sells = _num(sells_5m)
    share = None
    if buys is not None and sells is not None and (buys + sells) > 0:
        share = buys / (buys + sells)
    turnover = None
    volume = _num(volume_5m_usd)
    if volume is not None and liquidity > 0:
        turnover = volume / liquidity
    if liquidity >= MID_POOL_MIN_LIQUIDITY and share is not None and share >= MID_POOL_MIN_BUY_SHARE:
        return 'mid_pool_buy_share'
    if (liquidity <= SMALL_POOL_MAX_LIQUIDITY and turnover is not None
            and turnover > SMALL_POOL_MIN_TURNOVER):
        return 'small_pool_turnover'
    return None


class Registry:
    """Which tokens are currently being watched, and why."""

    def __init__(self, *, max_watched: int = MAX_WATCHED,
                 watch_seconds: float = WATCH_SECONDS) -> None:
        self.max_watched = int(max_watched)
        self.watch_seconds = float(watch_seconds)
        self.entries: dict[str, tuple[datetime, str]] = {}
        self.counts: Counter = Counter()
        self.seen: set[str] = set()

    def _expire(self, now: datetime) -> None:
        dead = [token for token, (until, _rule) in self.entries.items() if until <= now]
        for token in dead:
            self.entries.pop(token, None)
        if dead:
            self.counts['expired'] += len(dead)

    def consider(self, token_id: str, *, liquidity_usd: Any, buys_5m: Any = None,
                 sells_5m: Any = None, volume_5m_usd: Any = None,
                 now: datetime) -> str | None:
        """Evaluate a token's FIRST observation once. Returns the admitting rule, or None."""
        if not token_id:
            return None
        self._expire(now)
        if token_id in self.seen:
            self.counts['already_considered'] += 1
            return None
        self.seen.add(token_id)
        if len(self.seen) > 200_000:  # bound the dedup set as well
            self.seen = set(list(self.seen)[-100_000:])
        rule = admission(liquidity_usd=liquidity_usd, buys_5m=buys_5m, sells_5m=sells_5m,
                         volume_5m_usd=volume_5m_usd)
        if rule is None:
            self.counts['rejected'] += 1
            return None
        if len(self.entries) >= self.max_watched:
            self.counts['full'] += 1
            return None
        self.entries[token_id] = (now + timedelta(seconds=self.watch_seconds), rule)
        self.counts['admitted:' + rule] += 1
        return rule

    def active(self, now: datetime) -> set[str]:
        self._expire(now)
        return set(self.entries)

    def snapshot(self, now: datetime) -> dict[str, Any]:
        self._expire(now)
        return {
            'version': VERSION,
            'watching': len(self.entries),
            'max_watched': self.max_watched,
            'watch_seconds': self.watch_seconds,
            'counts': dict(self.counts),
        }
