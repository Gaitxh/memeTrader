# Dex discovery freshness 186

## Diagnosis

The official DexScreener discovery scheduler was configured for 15 seconds, but
each metadata response remained cached for 45 seconds. Six surfaces also execute
serially, so the observed same-surface interval was generally 24 to 31 seconds
with 41 to 54 second maxima. A faster scheduler did not guarantee fresher source
data.

## Controlled trials

A three-way bounded fan-out plus a 15-second cache was implemented and tested,
then trialled in Paper. It improved the six same-surface median intervals to
about 17.7 to 20.5 seconds, but accumulated 17 low-priority deferrals and
coincided with repeated 60 to 120 second weighted Solana held-quote
failure/delay bursts. It was rejected and removed because discovery throughput
must not degrade held-token and exit execution.

Sequential discovery with a 15-second cache restored the single-request shape,
but its five-minute window still reached all five low-priority slots and an
instantaneous held-mark p95 of 23.84 seconds. Since the real serial cycle already
takes roughly 25 to 34 seconds, the extra cache aggressiveness added request
pressure without improving the scheduler's attainable cadence.

## Retained change

The final implementation keeps discovery serial and changes only its HTTP cache
TTL from 45 to 30 seconds. This aligns source freshness with the measured serial
cycle, remains materially fresher than the previous cache, and allows repeated
poll rounds inside 30 seconds to reuse the response instead of occupying another
low-priority HTTP slot.

No strategy receives a private request lane. Held and pending-exit quotes remain
high priority; strategy observations share the bounded lifecycle capacity from
stage 185. A strategy that needs costlier private data must use an existing-data
proxy, reduce its budget, or be paused/retired.

## Verification

Three focused freshness, discovery-provenance, and real HTTP capacity tests
passed in both the active worktree and a clean staging tree. The rejected
parallel implementation had also passed its engineering tests; it was removed
because natural system-level evidence failed the runtime guard.

The retained Paper process loaded at `2026-09-15T17:05:28.184833Z`, PID 70952,
with unchanged funding period and `Live=false`. Runtime, collectors, and store
manifest hashes matched the active worktree.

In its first 185 seconds:

- the six surfaces started 41 rounds: 38 completed, 2 yielded for low-priority
  capacity, 1 was still running, and none ended in a provider error;
- same-surface median intervals ranged from 17.63 to 33.36 seconds; maxima still
  ranged from 39.28 to 62.54 seconds, so the long tail remains observable rather
  than being hidden by the cache;
- the shared hydration lane completed 58 rounds, requested 320 addresses,
  returned 143 valid snapshots, and had zero full-30 all-zero batches;
- all 13 open-position tokens had a market mark; latest-mark age was p50/p95
  12.37 seconds;
- the sampled HTTP state had 3 active low-priority and 2 active high-priority
  requests, zero waiters, zero connect errors, and zero pool timeouts.

This is an accepted resource/freshness improvement, not proof of higher trading
profit. Strategy economics remain governed by natural forward fills and exits.

## Next checks

Continue tracking discovery-to-first-quote latency, valid lifecycle backlog,
frame continuity, low-priority deferrals, held/pending-exit age, upstream errors,
and per-token paired strategy PnL. Do not reintroduce metadata fan-out unless a
longer matched window shows it can meet the held-token guard.
