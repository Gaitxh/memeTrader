"""Reserve existing DEX capacity while a causal entry signal is still alive.

This module never creates a request or extends a signal deadline.  It only
publishes the remaining lifetime to the existing low-priority capacity gate so
background work cannot occupy the last slot before the follow-up collector has
had a chance to run.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .models import parse_time


SIGNAL_TTL_SECONDS = 60.0


def reserve_signal_followup_capacity(
    client: Any,
    signals: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
    monotonic_now: float,
) -> float:
    """Reserve one existing low-priority slot for the live signal horizon.

    Returns the remaining causal lifetime that was published.  Invalid,
    future-dated and expired signals never reserve capacity.
    """
    if client is None or not signals:
        return 0.0
    remaining = 0.0
    for signal in signals.values():
        recorded_at = signal.get("recorded_at")
        if not recorded_at:
            continue
        try:
            age = (now - parse_time(recorded_at)).total_seconds()
        except (TypeError, ValueError):
            continue
        if 0.0 <= age <= SIGNAL_TTL_SECONDS:
            remaining = max(remaining, SIGNAL_TTL_SECONDS - age)
    if remaining <= 0.0:
        return 0.0
    client.dex_followup_urgent_until = max(
        float(getattr(client, "dex_followup_urgent_until", 0.0)),
        float(monotonic_now) + remaining,
    )
    return remaining
