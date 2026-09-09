# Flat ordinary queue 87: rejected before production modification

REPLY_TO: C2C-20260909-FLAT-QUEUE-HOTPATH-87

Disposition: REJECT_ORDINARY_QUEUE_SEMANTIC_MISMATCH. No runtime/source selector change, deployment, cadence change, index, schema, network probe, restart or trading mutation.

## Observed bottleneck and prior evidence

The current runtime still invokes `due_flat_compression_breakout_shadow_targets(limit=30)` on a separate read-only connection via `asyncio.to_thread`. It joins the latest-evaluation universe with latest observer state, token, open-position and market-attempt state. The prior measured baseline68 took 17.394 seconds for 30 targets across approximately 110k latest identities. That is historical measured evidence, not a new current p95. The supplied 07:29Z p95 17.67s is Lead-reported and not independently resampled here. The correlated SQL rejected in68 was not retried.

## Frozen sequence falsifier

`scripts/research_flat_queue87.py` executes the exact captured production baseline SQL from `data/research/flat68/baseline.json` against two independent in-memory SQLite fixtures over 0–65 seconds at five-second ticks. This is a deterministic synthetic database sequence, NOT a natural production replay or an estimate of real traffic frequency. No production database scan was performed.

Fixture starts with 360 ordinary mature identities (12 full batches, sized for the theoretical 60-second service horizon). Frozen events add a new ordinary mature identity at5s, turn an existing identity near-trigger at10s, open another position and change another identity's latest pool at15s, add an ineligible young identity at20s, then close the position at25s. Each branch records its own selected-request attempt times. Baseline limit remains30. Ordinary queue is repopulated only at0/60s; direct near-trigger identities bypass it.

To avoid falsely rejecting a weak revalidation implementation, the challenger receives *perfect full-query oracle revalidation* of current due state, pair, held exclusion and ordering every tick. This deliberately overgenerous model is not a fast implementation and its timing cannot establish speedup. If even this model loses membership, merely making selected-item revalidation faster cannot repair it.

Results: new ordinary identity first selected baseline5s versus queue60s (55s extra delay). Ordered target lists differ at13 of14 ticks. Baseline420 versus queue402 token-refresh selections over65s. Both have14 nonempty single-chain batches: request-start count stays equal in this fixture, but payload/service coverage is reduced. Do not describe the18 missing selections as18 missing HTTP calls. Near-trigger remains selected every tick from10s; open exclusion at15/20s passes; latest pool/due/age state is evaluated by the exact oracle. The membership failure exists despite those protections.

## Decision and limits

A 60-second ordinary universe queue cannot discover ordinary identities first eligible between refills; selected-token revalidation cannot add an identity absent from the queue. A new ordinary target can supply trading data even without an existing flat near-trigger state, as59 established. Raising queue capacity does not fix this first-admission delay. Therefore the mandatory exact service/membership equivalence gate fails and this proposal is rejected without a runtime trial.

No SQL I/O reduction, production query p95 improvement or preserved natural requests/min is claimed. Fixture wall times are recorded only as harness observations, not production benchmarks. A measured performance trial is unwarranted after semantic rejection. A different design would need event/frontier-driven membership updates for new evaluations and age eligibility in addition to revalidating queued targets; that design is not implemented or validated here.

Validation: deterministic 65s harness completed, asserted new-candidate delay, near-trigger priority and held exclusion. Full ordered rows and per-tick times: `data/research/flat87/simulation.json`. Runtime remains unchanged, so no rollback/restart is required. Production financial/history/data files were untouched.
