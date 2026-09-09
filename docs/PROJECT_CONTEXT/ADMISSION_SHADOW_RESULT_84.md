# Prospective admission Shadow84

REPLY_TO: C2C-20260909-ADMISSION-SHADOW-84

The observed limitation is that a valid incumbent can exclude a fresh valid candidate without an information-value comparison. Historical admission membership is not recoverable from aggregate KV. This stage records new receipts prospectively and compares a separate Shadow; it does not adopt Shadow selections.

## Implementation

`runtime._remember_pattern_quotes` records compact pre-admission identities, held membership, bucket/expiry and actual branch reason/victim. Existing legacy conditions, watch identity, caps3/4/3+early borrow, total10/chain, TTL, quote updates and requests remain unchanged. Unsupported/invalid and refresh/skip receipts are included in the audit denominator. Source snapshot IDs are retained when provided by the input object; otherwise null, with process-local receipt sequence and exact input identity/clocks rather than an invented database row ID.

`admission_shadow.py` is a pure comparator with an independent empty-at-process-start watch and no network/Store access. It uses the frozen80 lease, measured quiet reservation, missing-checkpoint priority, provider/quote diversity, capped bilateral activity and deterministic receipt/identity tie break. Freshness/floor/clock eligibility is separate from the actual legacy decision. Other pools cannot refresh a tracked original pool. Cache duplicates cannot complete trajectory checkpoints. No outcome, PnL or future label enters ranking.

`admission_audit.py` captures no JSON and performs no I/O on receipt. At most256 pending events and128 incumbent/held identities are captured. The existing low-priority cohort iteration may dispatch one worker, at most64 events per2s; a pending worker prevents another. Disk serialization/comparison runs outside the main loop and is not awaited by the passive cohort drain. Ledger is append-only gzip JSONL under data/research/admission84/, at most256MiB compressed per process file. The diagnostic KV `pattern-admission-shadow` exposes counts/path/errors with decision_eligible=0, affects=none.

Overflow, input capture or sink failure records DROPPED_AUDIT counters; dropped input makes the Shadow trajectory explicitly discontinuous, not a complete counterfactual. At file budget exhaustion acquisition continues unchanged and further audit is dropped with KV status. Restart starts a new prospective file/state, never replays history. This finite retention is an explicit research limitation, not a new permanent high-volume data service.

## Validation and runtime acceptance

Actual-path fixtures:10 targeted audit/watch checks passed. After making the sink single-worker/nonblocking,3 adapter tests passed, including slow sink, overflow and write failure. A30-receipt/30-incumbent capture fixture over100 iterations measured p50 1.081ms/p95 1.255ms, zero network/file writes. This microbenchmark is not production latency.

Pre-deploy data/research/admission84/before_*.json: held fetch p95 1.9997s, apply/exit p95 .04779s, pattern p95 7.071s, cohort p95 .5946s; passive drops0, Dex pool timeouts0. Window sizes differ by task. Deployment/natural acceptance is recorded below only after verification.

No strategy/account/funding/reset/history/Live change. No trending collector, watch-cap change or Shadow BUY authority.

## Natural commissioning correction

Initial c6695bf was loaded07:33:43Z. Natural1127 audit receipts included only45 eligible; further inspection found1520/1580 input snapshots missing a separate ingested_at (mostly Dex). Treating that missing optional field as noncausal was an audit eligibility mistake, not evidence that the production quotes were unusable. Final f1c0eb0 preserves source_ingested_at=null and records ingestion_clock=local_receipt, using the actual current capture timestamp as conservative availability, never an invented earlier ingestion time. Existing provided ingestion timestamps remain validated. The initial uncompressed audit is retained as commissioning evidence and must not be combined with final eligible comparisons.

The initial file also grew quickly from repeated incumbents. Final sink uses standard-library level1 gzip in the same bounded background worker; it adds no hot-path compression or new requests. Four adapter tests passed after this change, including missing-ingestion provenance. Seven comparator tests and eight unchanged watch regressions also passed in this stage (19 distinct targeted tests). Final restart via existing launcher07:36:02Z, no initialization.

## Final bounded acceptance

Final code f1c0eb0 loaded. /health running/ok, /api/live and /api/performance readable; Live.enabled=false. Seven registration/activation/funding tables' complete ordered-row hash is unchanged: b376b3e07f9f4aae836dec63a5d54a95641eca89cd221cdfd142a355ef12a2fd. Evidence: before_immutable.json/final_acceptance.json; old observations/trades were not edited by this stage.

At07:38:00.562407Z audit3995 received,3328 written,483 dropped,120 pending (remaining64 in flight), zero sink errors,8,682,166 compressed bytes. Every drop is counted; audit_discontinuous=true. Bounded first1000 ledger lines contain996 receipt rows/169 distinct tokens/541 eligible receipts plus4 drop markers. Challenger includes ordinary admissions, early borrowing, protected-lease skips, held exemptions and refreshed watches. Selection-only telemetry is naturally advancing; there is no actual new quote request or BUY from the challenger. This is NOT a complete input denominator and must not be used to assert complete historical/natural would-admit recall. Capacity drops are the remaining measurement limitation; no silent buffer/request expansion was made to hide them.

Settled short-window held fetch p95 1.7503s (120 samples), held apply/exit p95 .04672s (120), pattern p95 4.4246s (7), cohort p95 .51877s (50); all failures0, passive dropped batches0. Before values were1.9997/.04779/7.071/.5946s. No material regression observed, but unequal windows and few pattern samples do not establish a speedup or long-run acceptance. Early post-restart apply p95 .0774s settled to .04672s. Files settled_performance.json/settled_audit.json preserve these boundaries.

Disposition: IMPLEMENTED_DEPLOYED_NATURAL_AUDIT_ADVANCING_WITH_EXPLICIT_AUDIT_LOSS. Actual admission equivalence proved on deterministic fixtures; runtime request-count equivalence is architectural (no network code added), not a falsely matched before/after traffic experiment.80 actual-watch ranking replacement and81 trending deployment remain unimplemented; this audit grants neither authority. No Alpha claim.
