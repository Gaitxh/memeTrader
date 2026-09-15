# Pump short hydration retry 171 - 2026-09-15

## Diagnosis

From `2026-09-15T12:00:54Z`, 737 locally recorded PumpPortal create tokens
provided 705 first hydration attempts. The first attempt was timely (`p50 4.2s`,
`p95 19.8s`), but 670 tokens returned no DEX pair and the 634 tokens that later
obtained a snapshot had `p50 312.9s` and `p95 345.7s` discovery-to-snapshot
latency. The generic no-pair schedule waits five minutes after the first miss.

A separate mature slice contained 567 Pump-surface first misses eligible for
the original retry; 534 (94.2%) succeeded on the next ordinary attempt. Bonk
had 0 successes among 20 comparable retries. This supports an earlier bounded
Pump probe, but not repeated fast polling or enabling the same treatment for
Bonk.

## Change

For a hydration row backed by an immutable PumpPortal create fact recorded in
the last ten minutes with `launch_surface='pump'`:

1. The first no-pair result schedules one short probe at +90 seconds.
2. If that probe is also no-pair, the next attempt is +210 seconds, preserving
   the original first-attempt +5 minute frontier.
3. Further misses resume the ordinary 30/120/360 minute backoff.

All generic identities, old Pump facts, Bonk launches and error results retain
their existing schedules. The change adds at most one early address lookup per
eligible create, about 17 addresses/minute at the observed mean. Addresses are
still carried inside existing bounded 30-address requests; request cadence,
HTTP concurrency, held-price priority and lifecycle follow-up reservation are
unchanged. Fresh pending identities remain ahead of no-pair retries in the
selector.

## Validation and forward guard

- 15 focused tests passed, 111 deselected.
- Tests cover the +90/+210/30-minute sequence, generic and old Pump behavior,
  Bonk exclusion, migration/source wakeups, follow-up ordering and the 15/15
  fast hydration capacity split.
- No historical snapshot, decision, position, trade or account is rewritten.

Observe for at least 30 minutes. Report short-probe attempts and successes
separately from the ordinary retry. Keep only if short-probe success is at least
10%, no lifecycle follow-up expiry/failure appears, held/SELL latency does not
regress materially, and HTTP request frequency is unchanged. This is a funnel
latency experiment, not evidence of strategy profitability.

## Initial natural receipt

The first post-deployment slice produced 15 mature short probes. All 15 changed
from `quote_returned_no_pair` to a persisted DEX snapshot. Probe delay was
`p50 99.1s`, `p95 127.1s`; launch receipt to snapshot was `p50 107.2s`,
`p95 136.3s`, compared with the pre-change `p50 312.9s`, `p95 345.7s`.
Hydration completed with zero component failures in this slice.

This is strong initial latency evidence but not the full guard. Held retrieval
experienced concurrent upstream failures and `p95 5.77s` duration during the
short slice, so causality and stability remain unresolved until the specified
30-minute comparable window. No additional capacity or strategy change is
authorized by this early result.

## Mature 30-minute receipt

At `2026-09-15T13:22:13Z`, 1,841.8 seconds after deployment, 528 Pump creates
were old enough for evaluation. All 528 had a persisted DEX snapshot; 524 were
available within 240 seconds of the local launch receipt. Discovery-to-snapshot
latency was `p50 105.7s`, `p95 131.4s`, versus the pre-change `p50 312.9s`,
`p95 345.7s`.

The token-detail component had 256 calls and zero failures. Held-price retrieval
still saw upstream request failures (144/971 cumulative calls), but its rolling
`p95` duration improved to `4.70s` from `5.77s` in the initial slice; exit
application had zero failures and `p95 0.23s`. The fast probe runs in the
existing low-priority HTTP budget, while held work retains its high-priority
lane. No lifecycle expiry or hydration failure appeared among the mature Pump
cohort. The guard therefore passes and the source-specific retry is retained.
