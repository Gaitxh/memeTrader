# Prospective admission Shadow84

REPLY_TO: C2C-20260909-ADMISSION-SHADOW-84

The observed limitation is that a valid incumbent can exclude a fresh valid candidate without an information-value comparison. Historical admission membership is not recoverable from aggregate KV. This stage records new receipts prospectively and compares a separate Shadow; it does not adopt Shadow selections.

## Implementation

`runtime._remember_pattern_quotes` records compact pre-admission identities, held membership, bucket/expiry and actual branch reason/victim. Existing legacy conditions, watch identity, caps3/4/3+early borrow, total10/chain, TTL, quote updates and requests remain unchanged. Unsupported/invalid and refresh/skip receipts are included in the audit denominator. Source snapshot IDs are retained when provided by the input object; otherwise null, with process-local receipt sequence and exact input identity/clocks rather than an invented database row ID.

`admission_shadow.py` is a pure comparator with an independent empty-at-process-start watch and no network/Store access. It uses the frozen80 lease, measured quiet reservation, missing-checkpoint priority, provider/quote diversity, capped bilateral activity and deterministic receipt/identity tie break. Freshness/floor/clock eligibility is separate from the actual legacy decision. Other pools cannot refresh a tracked original pool. Cache duplicates cannot complete trajectory checkpoints. No outcome, PnL or future label enters ranking.

`admission_audit.py` captures no JSON and performs no I/O on receipt. At most256 pending events and128 incumbent/held identities are captured. The existing low-priority cohort iteration may dispatch one worker, at most64 events per2s; a pending worker prevents another. Disk serialization/comparison runs outside the main loop and is not awaited by the passive cohort drain. Ledger is append-only JSONL under data/research/admission84/, at most256MiB per process file. The diagnostic KV `pattern-admission-shadow` exposes counts/path/errors with decision_eligible=0, affects=none.

Overflow, input capture or sink failure records DROPPED_AUDIT counters; dropped input makes the Shadow trajectory explicitly discontinuous, not a complete counterfactual. At file budget exhaustion acquisition continues unchanged and further audit is dropped with KV status. Restart starts a new prospective file/state, never replays history. This finite retention is an explicit research limitation, not a new permanent high-volume data service.

## Validation and runtime acceptance

Actual-path fixtures:10 targeted audit/watch checks passed. After making the sink single-worker/nonblocking,3 adapter tests passed, including slow sink, overflow and write failure. A30-receipt/30-incumbent capture fixture over100 iterations measured p50 1.081ms/p95 1.255ms, zero network/file writes. This microbenchmark is not production latency.

Pre-deploy data/research/admission84/before_*.json: held fetch p95 1.9997s, apply/exit p95 .04779s, pattern p95 7.071s, cohort p95 .5946s; passive drops0, Dex pool timeouts0. Window sizes differ by task. Deployment/natural acceptance is recorded below only after verification.

No strategy/account/funding/reset/history/Live change. No trending collector, watch-cap change or Shadow BUY authority.
