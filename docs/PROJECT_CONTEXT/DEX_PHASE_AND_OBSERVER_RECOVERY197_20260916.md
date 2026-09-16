# Dex phase timing and pattern-observer recovery, 2026-09-16

## Observed break

The prior watched-frozen-signal repairs did not establish a timely next
original-pool frame. Before this stage the shared timing labeled one whole
transport/client wait, conflating capacity, host pacing, HTTP and cleanup.
At 14:45 UTC the loaded Paper process showed 13 pattern-observer calls and 10
failures. The bounded traceback identified a concrete exception at
`Runtime.chain_meme_pattern_observer_once`: it compared a snapshot's optional
`ingested_at=None` with a signal datetime. The exception was raised after
processing a returned frame and aborted the observer round before its normal
status write. Thus the missing `coverage145:status` updates were not proof of
no watch work or no market data.

## Changes and checks

Commit `aef4ba3` adds bounded, in-memory last-64 Dex request timings by held,
frozen-followup and background lane to the existing performance snapshot. It
separates slot admission, host-start pacing, client acquisition, actual HTTP
await, cleanup and total wall time. It adds no request, persistent table,
strategy gate or hot-path database write. Fourteen focused Dex start/client
tests passed, including two new phase tests. It was loaded into Paper PID
99084; collector hash matched disk, the same funding period and 499 policies
remained, Live stayed locked and all three local APIs returned 200.

Natural first-minutes phase evidence in that process: 14 frozen-followup
requests, six failures; p95 slot wait 6.375s, host-start wait 4.890s, HTTP
await 7.750s and total 17.547s. These p95 values come from separate samples
within a small rolling window and must not be added as one representative
request. Even the configured 0.25s low-slot wait or 3s HTTP phase timeout can
exceed its nominal value in observed wall time, so simply raising the outer
six-second budget is not a justified resolution. The record does not yet
distinguish event-loop delay from all transport phase semantics.

Commit `2d3dcbd` fixes the deterministic observer exception. A frame is
marked post-signal only when its locally known `observed_at` is later than the
frozen signal; if `ingested_at` exists it must also be later. Missing optional
ingestion time alone no longer crashes the loop or becomes zero/retroactive
evidence. The full shared-batch test file passed 24 tests, including the new
missing-ingestion-time case. The original price/pool and forward execution
checks are unchanged. No historical signal or fill was replayed.

## Deployment and natural boundary

The existing Paper supervisor loaded PID 97276 after the second commit. The
loaded `runtime.py` SHA-256 equaled the on-disk source; `/health`, summary
`/api/live` and `/api/performance` returned 200. The 499 strategy accounts,
`chain-meme-trader/funding-20260906-v002-final-1000` and Live lock were
unchanged. In the first 22-second readback, the observer made three natural
calls with zero failures. One new Solana frozen signal at 14:48:50 UTC had a
post-signal observed frame marked `sampled=true` by 14:49:23 UTC. This is
frame receipt, not confirmed exact-pool trade eligibility, source BUY or
profitable exit. Other due signals in that same round still saw runtime low
capacity. The timing/fill bottleneck remains partially unresolved.

Next manual review: distinguish on-time exact-pool frame, safety disposition,
source fill and cost-inclusive exit per distinct post-deployment token; compare
Dex phase timings and held quote ages under comparable natural load. The
observer crash is resolved in code and short-window forward readback, whereas
overall next-frame conversion and profitability are not proven. Roll back only
these two scoped commits if measured regressions require it; preserve Paper
history and this evidence.
