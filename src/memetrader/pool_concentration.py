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

# ---------------------------------------------------------------------------------------
# ENFORCEMENT IS OPT-IN. An ABSENT field means NO CAP, which is the behaviour every
# pre-existing arm had and the state the user explicitly chose.
#
# History that shapes this default: the same-token concurrency cap was offered to the user
# twice and DECLINED twice, and it is recorded as a top binding rule ("no same-token
# concurrency cap"). A later full-autonomy grant is not a reversal of a specific, twice-stated
# decision, so the safe direction is the one the user chose. Measured shadow evidence exists
# (a 10-arm cap would have blocked 339/450 positions worth -3329.95U on this device) but the
# old session itself flagged the confound: later arms enter later at higher prices, so those
# positions are selected to look worse. The saving is therefore NOT established.
#
# What the cap is still good for, and why the code is kept: it de-correlates the book. When
# 350 positions covered only 11 tokens, any per-arm ranking was measuring multiplicity rather
# than strategy behaviour. A definition may opt in explicitly with a numeric field.
DEFAULT_MAX_ARMS_PER_POOL: float | None = None
DEFAULT_MAX_NEW_ARMS_PER_POOL: float | None = None

# The values a definition should use if it chooses to enforce. Eight arms is still a strong
# consensus read on one pool; the measured worst case was 81 positions / 60 arms on a single
# token in one second.
SUGGESTED_MAX_ARMS_PER_POOL = 8.0
SUGGESTED_MAX_NEW_ARMS_PER_POOL = 3.0

CONCENTRATION_REASON = "pool_cross_arm_concentration_cap"

# Telemetry only: the gate counts what it WOULD have refused so the shadow record keeps
# accumulating even while enforcement is off.
SHADOW_ONLY = "shadow_only_not_enforced"

_FIELDS = ("max_arms_per_pool", "max_new_arms_per_pool")


def _limit(value: Any, fallback: float | None) -> float | None:
    """Return a non-negative limit, or None for 'no cap'.

    An absent/None field keeps `fallback` (which is None by default, i.e. uncapped). A
    negative value is an explicit "no cap". Anything unusable falls back rather than guessing.
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
    return number


def concentration_limits(definition: Mapping[str, Any] | None) -> tuple[float | None, float | None]:
    """Resolve (max_arms_per_pool, max_new_arms_per_pool) for one definition.

    Defaults to (None, None): NO CAP. Every definition that does not explicitly opt in keeps
    exactly the behaviour it had before this gate existed.
    """
    definition = definition or {}
    if definition.get("cross_arm_pool_concentration") is False:
        return None, None
    if definition.get("cross_arm_pool_concentration") is True:
        # Explicit opt-in without numbers: use the suggested enforcement values.
        return (
            _limit(definition.get("max_arms_per_pool"), SUGGESTED_MAX_ARMS_PER_POOL),
            _limit(definition.get("max_new_arms_per_pool"), SUGGESTED_MAX_NEW_ARMS_PER_POOL),
        )
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

    Returns ``(allowed, reason)``. ``allowed`` is True whenever no cap applies, which is the
    DEFAULT and keeps every definition without an explicit numeric opt-in byte-identical to
    its previous behaviour.
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
    if max_arms is None and max_new is None:
        return True, ""
    if max_arms is not None and open_arms + new_arms >= max_arms:
        return False, CONCENTRATION_REASON
    if max_new is not None and new_arms >= max_new:
        return False, CONCENTRATION_REASON
    return True, ""


def shadow_decision(
    *,
    open_arms_on_pool: int,
    new_arms_this_pass: int,
    definition: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    """What the gate WOULD do if it were enforced, without changing any behaviour.

    Used for the observation-only record so the evidence keeps accumulating while enforcement
    stays off.
    """
    probe = dict(definition or {})
    probe.setdefault("max_arms_per_pool", SUGGESTED_MAX_ARMS_PER_POOL)
    probe.setdefault("max_new_arms_per_pool", SUGGESTED_MAX_NEW_ARMS_PER_POOL)
    allowed, reason = pool_concentration_decision(
        open_arms_on_pool=open_arms_on_pool,
        new_arms_this_pass=new_arms_this_pass,
        definition=probe,
    )
    return (True, SHADOW_ONLY) if allowed else (True, reason)

