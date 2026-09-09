# Admission audit 88 — throughput passed, conservative runtime guard rollback

REPLY_TO: C2C-20260909-ADMISSION-AUDIT-DROPS-88

Disposition: TRIAL_REJECTED_RUNTIME_GUARD_ROLLED_BACK. Throughput correction dbd9579 was tested/deployed; revert32a16f3 restores prior sink. No claim that audit84 is now fully accepted. Its known bounded-sink losses remain unresolved; discontinuous generations must never be treated as complete. No history was retrofilled.

## Implemented trial

Audit-only change: same-chain actual_pre (global held identities retained because the comparator prunes all chains), pending256->1024, batch64->256, timer2s->1s with pressure>=128 bypass. Existing cohort-loop trigger, held-idle gate and one asyncio.to_thread writer preserved; no new timer or requests. New explicit admission-audit-v2 file generation. Gzip level1 and256MiB per-process byte budget unchanged. That finite budget still limits recording duration; this trial never claimed perpetual completeness.

13 targeted tests passed: actual watch equality, single writer/nonblocking sink, missing ingestion, overflow/errors, comparator behavior, same-chain context/global held preservation,800-event bounded pressure drain. Only audit module/tests changed; runtime watch, network request selection, strategy, floor, TTL and capacities did not change. Deterministic watch equality is stronger than a fixture identity digest; natural before/after identical targets are not claimed because inputs/time differ.

## Natural evidence

Before07:59:00Z: old generation44435 receipts/39371 written/4808 drops/192 pending,117267194 compressed bytes. New v2 began07:59:17Z. At08:04:45Z (~328s):11424 receipts,11349 written,0 pending,0 drops/errors,17050286 bytes. Remaining75 receipts were in-flight at KV snapshot; do not count them as persisted. Every sampled pending count was0, not a growing queue.

Read exactly the snapshotted committed compressed prefix:11349 rows, sequence1..11349 contiguous, all actual_pre same-chain. SHA2566593ef19b9fd18c6e895bc3eb670d7c457c57ba936f3b7b3dd1ab205f49c2571. Old file unchanged by this correction; trial file retained separately and never merged with old discontinuous history.

## Latency guard

Nearest pre-trial held-fetch p50/p95 .883/1.922s; final .768/2.410s (~25.4% P95 increase). Held apply P95 .05361->.07929s; pattern P957.944->6.754s; passive drops0 both, final791 enqueued786 processed/depth5, waitP952.079->1.943s. Intermediate held P95 varied2.58,2.58,2.05,2.49s. Two actual held tokens before versus one during samples; network/startup and differing workload confound causal attribution. No proof that gzip caused this variation. Nevertheless this fails a conservative no-material-held-regression interpretation (aligned with prior25% guard practice); zero audit drops alone is insufficient acceptance. Reverted rather than extending trials to seek a passing window.

Existing Paper launcher restored prior sink at08:05:30Z. At08:05:48Z all three APIs responded, runtime running/Paper-only/Live locked; restored sink advancing415 receipts,256 written. Those short startup metrics are not a long-run recovery claim. Funding/registration seven-table SHA256 was unchanged before/during/after: b376b3e07f9f4aae836dec63a5d54a95641eca89cd221cdfd142a355ef12a2fd. No account reset, history rewrite, strategy/request change or backup mutation.

Artifacts: data/research/admission88/{before,start,minute1,minute2,minute3,minute4,minute5,restored,continuity}.json. Source/test trial remains in git dbd9579, revert32a16f3. Further sink design requires independent resource evidence; the old sink must continue reporting its drops honestly.
