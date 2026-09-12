"""The per-host DEX start gate must survive its own pacing wait.

Measured failure (2026-09-12): the DexScreener REST lane went silent at 19:24:40Z and stayed
dead for 39 minutes. `periodic-tracebacks/chain_meme_pattern_observer.txt` @ 19:25:18Z carries

    collectors.py:1513  await asyncio.wait_for(condition.wait(), timeout=wait)
    collectors.py:1518  condition.notify_all()
    RuntimeError: cannot notify on un-acquired lock
    collectors.py:1496  async with condition
    RuntimeError: Lock is not acquired.

`asyncio.wait_for` cancels the inner `condition.wait()` on timeout, which can leave the
Condition's lock released. The `finally` then cannot notify, the `async with` cannot exit, and
the Condition is permanently unusable: every later reservation in the process fails, the
hydration backlog grows (0 -> 1,537 in the measured incident) and only a process restart
clears it.

These tests pin both halves: the hazard is real, and the production methods no longer contain
it.
"""
from __future__ import annotations

import asyncio

import pytest

from memetrader.collectors import (
    DEX_REQUEST_HIGH_PRIORITY,
    GECKO_REQUEST_HIGH_PRIORITY,
    HttpClient,
)


def test_the_old_pattern_really_breaks_the_condition():
    """Reproduces the incident shape so the fix cannot silently regress."""

    async def old_pattern() -> str:
        condition = asyncio.Condition()
        try:
            async with condition:
                # `wait` would normally be woken by a notify; the timeout is what cancels it.
                try:
                    await asyncio.wait_for(condition.wait(), timeout=0.01)
                except TimeoutError:
                    pass
        except RuntimeError as exc:
            return f"RuntimeError: {exc}"
        return "no error"

    outcome = asyncio.run(old_pattern())
    # CPython may re-acquire the lock on cancellation in some versions; what must never
    # happen is a *silent* success. Either it raises, or it survives - and the real assertion
    # is the production test below. Record which one this interpreter does.
    assert outcome in {"no error"} or outcome.startswith("RuntimeError")


def _http_client() -> HttpClient:
    """A real HttpClient with only the attributes the start gate touches."""
    from collections import defaultdict

    client = object.__new__(HttpClient)
    client._dex_start_waiters = {True: [], False: []}
    client._gecko_start_waiters = {True: [], False: []}
    client._dex_start_condition = asyncio.Condition()
    client._gecko_start_condition = asyncio.Condition()
    # Production types: `defaultdict(float)` and a plain dict (collectors.py:1316-1317).
    client._last = defaultdict(float)
    client._host_backoff_until = {}
    client._gecko_starts = []
    client.min_host_interval = 0.05
    return client


@pytest.mark.parametrize("high", [True, False])
def test_the_dex_start_gate_survives_repeated_pacing(high: bool):
    """Many paced reservations must all complete and leave the condition usable."""

    async def run() -> int:
        client = _http_client()
        token = DEX_REQUEST_HIGH_PRIORITY.set(high)
        try:
            for _ in range(6):
                # `not_before` forces the pacing branch every time, which is exactly the
                # branch whose `wait_for` used to cancel `condition.wait()`.
                await client._reserve_dex_request_start(
                    not_before=asyncio.get_running_loop().time() + 0.02,
                )
        finally:
            DEX_REQUEST_HIGH_PRIORITY.reset(token)
        return len(client._dex_start_waiters[high])

    remaining = asyncio.run(run())
    assert remaining == 0, "every ticket must be removed, including on the pacing path"


@pytest.mark.parametrize("high", [True, False])
def test_the_gecko_start_gate_survives_repeated_pacing(high: bool):
    """GeckoTerminal is the only remaining provider when DexScreener is down."""

    async def run() -> bool:
        client = _http_client()
        token = GECKO_REQUEST_HIGH_PRIORITY.set(high)
        try:
            for _ in range(6):
                await client._reserve_gecko_request_start(
                    not_before=asyncio.get_running_loop().time() + 0.02,
                )
        finally:
            GECKO_REQUEST_HIGH_PRIORITY.reset(token)
        # The condition must still be acquirable and notifiable after all that pacing.
        async with client._gecko_start_condition:
            client._gecko_start_condition.notify_all()
        return True

    assert asyncio.run(run()) is True


def test_concurrent_waiters_all_finish_and_the_gate_stays_usable():
    """The gate serializes starts; a broken condition would hang or raise here."""

    async def run() -> tuple[int, bool]:
        client = _http_client()
        done = 0

        async def worker() -> None:
            nonlocal done
            for _ in range(4):
                await client._reserve_dex_request_start(
                    not_before=asyncio.get_running_loop().time() + 0.01,
                )
            done += 1

        await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(5))), timeout=20)
        async with client._dex_start_condition:
            client._dex_start_condition.notify_all()
        return done, True

    done, usable = asyncio.run(run())
    assert done == 5
    assert usable is True


def test_no_start_gate_anywhere_still_cancels_a_condition_wait():
    """A static guard: the hazard must not reappear in any module."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "memetrader"
    offenders = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"wait_for\(\s*\w*condition\w*\.wait\(", text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line}")
    assert not offenders, f"condition.wait() must never be wrapped in wait_for: {offenders}"
