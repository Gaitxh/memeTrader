# Shared market attention scheduler 185

## Diagnosis

The 30-address hydration batch had a `followup_limit=15`, but this was not a
reservation. Pending first quotes could consume all 30 slots before valid pools
were appended. Under a discovery burst, a token with a known original pool and
an active strategy-observation lifecycle could therefore miss every second and
third frame.

The lifecycle queue also mixed valid hydrated pools with `no_pair` and `error`
rows. At the pre-deployment checkpoint, only 5 first quotes were pending, while
23 valid lifecycle frames and 148 missing-pair lifecycle retries were already
due. Missing-pair growth could displace the useful frames the strategies need.

Held positions and pending exits were not affected by this selector defect:
they already use the separate one-second, high-priority market-mark path.

## Change

- Reserve up to 15 of each 30-address chain batch for due `hydrated` lifecycle
  rows.
- Fill all remaining capacity with first quotes using the existing 80% fresh /
  20% oldest fairness policy. If fewer than 15 valid follow-ups are due, their
  unused reservation returns immediately to first quotes.
- Admit lifecycle `no_pair` and `error` confirmation probes only after valid
  follow-ups and first quotes, capped at two per chain turn.
- Keep the separate generic historical recovery cap and 30-second opening
  cadence from stage 182 unchanged.

This is capacity allocation only. It adds no HTTP requests and does not change
the original-pool identity, the 1000 USD buy floor, the pre/post sell checks,
write-off evidence semantics, accounts, or Live lock.

## Verification

Thirteen focused shared-market, retry, lifecycle-backoff, and early-cadence tests
passed in both the active worktree and a clean staging tree.

The loaded Paper process started at `2026-09-15T16:40:13.840546Z`, PID 82292,
with the unchanged funding period
`chain-meme-trader/funding-20260906-v002-final-1000` and `Live=false`.
Its manifest store hash matched the active worktree:
`03e6b107a739f96399ccba178cf995008889e32d3361774898813d809a09480c`.

In the first 356 seconds of natural forward operation:

- three chains completed 100 hydration rounds covering 716 requested addresses;
  359 returned valid snapshots and no full 30-address batch returned zero;
- post-start storage received 1,061 snapshots for 252 distinct tokens;
- due valid lifecycle backlog fell from 23 to 5 even while discovery continued;
- 119 tokens formed at least two post-start frames and 76 formed at least three;
  frame-2 delay was p50 23.30 seconds / p90 309.32 seconds, and frame-3 delay was
  p50 42.54 seconds / p90 135.43 seconds;
- 276 newly discovered tokens included 124 with a first quote in this short
  window; discovery-to-first-quote delay was p50 5.29 seconds / p90 74.69 seconds;
- all 13 open-position tokens had a market mark; latest-mark age was p50 13.01
  seconds, p95 18.28 seconds, maximum 22.08 seconds;
- entry evaluation advanced by 1,012 rows across 241 distinct rejected tokens
  and 6 distinct admitted tokens.

The long p90 continuation and first-quote tails are not accepted as complete.
They identify the next optimization target: serialized metadata discovery and
upstream/transport delay, while held-token latency remains the deployment guard.

## Forward plan

Continue measuring valid lifecycle backlog, frame-2/frame-3 delay, new-token
first-quote coverage, held-mark age, 429/errors, strategy admissions, fills, and
paired economic outcomes. The next bounded change may parallelize the six
independent official DexScreener metadata surfaces without increasing call count;
it must be rejected if held/pending-exit latency regresses.
