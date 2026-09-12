"""Cross-arm per-pool exposure cap.

Why this exists (measured 2026-09-12, one fresh Paper epoch, 87 minutes):

    distinct tokens holding a position          11
    positions opened                            350
    positions per token  {1: 5, 30: 1, 55: 1, 57: 2, 65: 1, 81: 1}
    largest single-token burst                  40 positions in ONE second
    BSC share of positions                      74%  (258/350)
    BSC share of the realized loss              94%  (-3539.55 of -3759.66)

The per-arm "independent 1000 USDC account" model gives each arm its own cash, but every
arm reads the same signal, so a single accepted frame fanned out into 30-81 simultaneous
positions on one pool. The epoch therefore held about eleven independent bets, not 350, and
one genuine rug on a BSC pool with `liquidity_control = 'unknown'` became a book-wide
-3,380 USD written-off loss (169 of 350 positions).

This gate does not judge any instrument and does not replace an arm's own entry filter. It
only bounds how many arms may hold the SAME pool at once, and how many may newly join it in
one settlement pass. Arms that are refused keep their cash and stay eligible for the next
pool, so the same total book is spread over more instruments instead of being repeated on
one. It is deliberately additive: no existing arm contract, threshold or policy field is
touched, and a definition that sets the caps to None restores the previous behaviour.
"""
from __future__ import annotations

from typing import Any, Mapping

# Eight arms is still a strong consensus read on one pool, and it leaves the remaining arms
# free for other instruments. The measured worst case was 81.
DEFAULT_MAX_ARMS_PER_POOL = 8.0
# A single settlement pass may add at most this many NEW arms to a pool. The measured worst
# burst was 40 positions in one second; three keeps a real cluster readable without letting
# one frame consume the whole book.
DEFAULT_MAX_NEW_ARMS_PER_POOL = 3.0
# Above this many already-open arms the pool is treated as exhausted for the pass, which is
# what stops a retry loop from walking the cap upward one intent at a time.
CONCENTRATION_REASON = "pool_cross_arm_concentration_cap"

_FIELDS = ("max_arms_per_pool", "max_new_arms_per_pool")


def _limit(value: Any, fallback: float) -> float | None:
    """Return a non-negative limit, or None for 'no cap'.

    A missing field keeps the default. An explicit null disables the cap for that
    definition, which is how a historical epoch reproduces its original behaviour.
    """
    if value is None:
        return fallback
    if isinstance(value, bool):
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number:  # NaN
        return fallback
    if number < 0:
        return None
    if number == 0:
        return 0.0
    return number


def concentration_limits(definition: Mapping[str, Any] | None) -> tuple[float | None, float | None]:
    """Resolve (max_arms_per_pool, max_new_arms_per_pool) for one definition.

    Historical epochs that predate this gate declare the field as null and keep their
    original uncapped behaviour unchanged.
    """
    definition = definition or {}
    if "max_arms_per_pool" in definition and definition.get("max_arms_per_pool") is None:
        return None, None
    if definition.get("cross_arm_pool_concentration") is False:
        return None, None
    return (
        _limit(definition.get("max_arms_per_pool"), DEFAULT_MAX_ARMS_PER_POOL),
        _limit(definition.get("max_new_arms_per_pool"), DEFAULT_MAX_NEW_ARMS_PER_POOL),
    )


def pool_concentration_decision(
    *,
    open_arms_on_pool: int,
    new_arms_this_pass: int,
    definition: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    """Decide whether one more arm may open on a pool.

    Returns ``(allowed, reason)``. ``allowed`` is True whenever no cap applies, which keeps
    every uncapped definition byte-identical to its previous behaviour.
    """
    try:
        open_arms = int(open_arms_on_pool)
        new_arms = int(new_arms_this_pass)
    except (TypeError, ValueError):
        return True, ""
    if open_arms < 0:
        open_arms = 0
    if new_arms < 0:
        new_arms = 0
    max_arms, max_new = concentration_limits(definition)
    if max_arms is not None and open_arms + new_arms >= max_arms:
        return False, CONCENTRATION_REASON
    if max_new is not None and new_arms >= max_new:
        return False, CONCENTRATION_REASON
    return True, ""
