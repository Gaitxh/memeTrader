# Dex frozen-signal follow-up scheduling, 2026-09-16

## Natural failure and units

The previously reported `activity193_old_pool_tempo_v1` signal for
`solana:Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ` was already in the
pattern watch at 13:58 UTC. Its second local frame eventually arrived at
14:07:54 UTC, 600.851 seconds after watch admission. This is too late for the
30/120/300-second follow-up windows, and it did not authorize a historical BUY.
The post-hoc configured-proxy Dex probe succeeded, but says nothing about what
the earlier runtime request received.

Commit `aac91cc` added a bounded diagnostic to the existing 15-second
`coverage145:status` record: per-chain due count, gate/request result, runtime
slot wait and returned count, plus up to 16 recent dispatched-signal identities
with due, returned, exact-pool and post-signal sampled status. No table, HTTP
request, trading gate or per-token hot-path write was added. Its first natural
rounds showed different failures, not one inferred cause: at 14:15:14 UTC the
Robinhood batch timed out and Solana hit client low capacity; at 14:15:51 all
three chains were blocked by runtime low capacity; at 14:16:23 all three were
blocked by shared backoff. A natural Solana watch batch later returned 10
token records at 14:25:13, but the listed frozen-signal tokens did not have
their required next original-pool frame in that batch. Request success is not
signal success or a fill.

## Repairs and preserved boundaries

Commit `65302c1` reserves one of the existing five low-priority Dex HTTP slots
for an already-dispatched frozen signal while it is due; unrelated background
requests temporarily defer, and the reservation expires after 20 seconds
unless a fresh eligible signal renews it. It does not expand the total eight
Dex slots, the five-low/three-held split, the 30-address batch limit or the
number of requests. At 14:25:13 the client recorded 11 background deferrals
under this reservation and one Solana watch batch returned 10 token records;
the exact signal-to-frame conversion remained zero for those shown in the
bounded diagnostic. This is a measured scheduling tradeoff, not proven net
coverage gain.

The transport recovery path had a separate logic defect. In `_dex_batch_quote`,
any `TransportError` extends one shared exponential backoff (up to about
30-36 seconds), but an in-flight successful batch previously cleared the
failure streak only if that backoff had already expired. A bounded query of
the last 600 discovery rounds after 14:14 UTC found 149 rows, including 115
completed rounds, 12 `ConnectTimeout` errors and one `ReadError`; these rows
span restarts and do not prove their exact interleaving, but the code path
could retain a transport failure streak despite recovered transport. Commit
`47ca9a0` separates transport and provider-429 deadlines. A successful batch
now clears transport-only backoff and its streak; a real 429 `Retry-After`
remains in force. No price, identity, safety or accounting condition changes.

At 14:27:50 a newly loaded run still produced a due Solana frozen-signal
`TimeoutError`: 1.172 seconds in the runtime slot and 3.078 seconds in the
transport/client portion. With an actual open position, the special batch had
fallen back to its ordinary three-second outer budget. The held lane already
has three separately reserved concurrent slots, so commit `86eaf85` gives
only due frozen-signal low-priority batches six seconds for slot, pacing and
the existing three-second HTTP phase. Ordinary watch batches retain three
seconds. This may occupy one low slot longer; it does not borrow a held slot.

## Engineering and forward status

The slot/reservation change passed 35 targeted shared-batch, Dex start-gate and
HTTP-cleanup tests. The transport fix passed four focused tests, including
interleaved transport success and 429 preservation; an old race-dependent
ordering assertion was made deterministic. The six-second budget passed 23
shared-batch tests. All source stages were committed and pushed. At
14:30:02.751586 UTC the existing Paper supervisor loaded PID 102112 with a
matching `runtime.py` hash, 499 policies, the unchanged
`chain-meme-trader/funding-20260906-v002-final-1000` period and Live locked.
`/health`, `/api/live?view=summary` and `/api/performance` returned HTTP 200.

The first short post-final-deployment check still fails the desired timing:
`activity193` evaluation 936852 for
`solana:pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn` was recorded at
14:30:53 UTC, while the next strategy-observer snapshot was not ingested until
14:32:19 UTC (source observation 14:32:04). It cannot be used as a within-60s
next frame. At 14:31:55 and 14:32:47, urgent watch rounds still recorded
`TimeoutError` and other chains had capacity deferrals; client connect-error
count was zero in that short process interval. Therefore the full timing break
is **not resolved** by the three scheduling changes. A separate read-only
investigation of the remaining timeout path is ongoing; do not raise budgets
indefinitely or claim improved natural conversion from this run.

This is **implemented and engineering-verified but not end-to-end resolved**,
not a demonstrated profitable strategy or a proven natural follow-up conversion
improvement. Compare
new natural frozen signals by distinct token, exact-pool next frame within
60 seconds, safety disposition, source BUY, closed net return and writeoff.
Compare non-signal discovery/hydration throughput, response errors and held
age under comparable load; if the temporary reservation materially degrades
the shared foundation, narrow or revert it without changing the historical
ledger. No old signal was replayed or granted a hindsight order.

Rollback for this stage: revert only `86eaf85`, `47ca9a0`, `65302c1` or
`aac91cc` as appropriate after a measured failure, preserving the append-only
observations and this report. The earlier unwatched-batch repair is `7a94879`.
