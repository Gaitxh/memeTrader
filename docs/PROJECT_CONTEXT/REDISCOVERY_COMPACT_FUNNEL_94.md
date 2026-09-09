# Compact rediscovery funnel94

REPLY_TO: C2C-20260909-REDISCOVERY-FUNNEL-COMPACT-94
Code d689462 + clock-accounting correction c9ae54c, deployed Paper.

## Scope and counting
Existing successful requeue_dormant_source_episode opens local token membership. Counts are unique episode-per-stage/reason, not account fanout or raw repeated quote counts. At most256 active token memberships,1h TTL,32 recent first-stage examples; bounded in-memory counters, one compact KV `rediscovery-funnel94` flush at most every15s through existing low-priority cohort loop. No file append, new table, provider request, scheduler, or admission mutation. Existing84 lossy ledger is not consumed/replayed.

Hooks: successful episode; hydration result; persisted snapshot; basic_valid; watch attempt and actual existing reason; inserted pattern/cohort observation; current event_reawakening/quiet_renewal ready; common market-entry safety guard and BUY. Basic requires finite price>0,liquidity>=current1000 floor,exact pair present, explicit causal observed/ingested/recorded clocks after episode and freshness<=30s. Persisted snapshot receipt supplies actual ingestion when the original watch quote lacked it; availability is not backdated.

Reasons are the exact admission branches: admit_base/admit_held/admit_borrow/refresh_exact_pool/replace_unusable/reclaim_reservation/skip_bucket_full/skip_chain_full/skip_other_pool/skip_invalid_input/skip_future_creation/skip_chain. They can overlap over an episode and are not disjoint totals. Stage ordering can differ: quote admission may precede snapshot storage. Expired/untracked downstream work is UNKNOWN; token temporal association does not prove rediscovery caused later work. BUY coverage is common market-entry path only, not a claim about uninstrumented alternate paths. Safety guard wait does not infer hard rejection or provider PASS. Restart starts a new generation; old136 episodes are not loaded.

## Validation
4 targeted tests PASS: identical watch membership/bucket occupancy with/without instrumentation through borrow,full,replacement,reclaim and other-pool branches; unique counting,256 cap,TTL and bounded examples; pre-episode quote exclusion; actual dormant requeue test. Diff check PASS.

## First prospective readback
At 2026-09-09T10:59:18.377909+00:00; generation 2026-09-09T10:58:25.442594Z.

|Stage/reason|Unique episodes|
|---|---:|
|episode|2|
|hydration_hydrated|2|
|snapshot|2|
|basic_valid|2|
|admission_attempt|2|
|admit_base|0|
|admit_borrow|0|
|reclaim_reservation|2|
|refresh_exact_pool|1|
|replace_unusable|0|
|skip_bucket_full|0|
|skip_chain_full|0|
|skip_other_pool|0|
|skip_invalid_input|0|
|skip_future_creation|0|
|skip_chain|0|
|pattern_observation|2|
|reactivation_ready|0|
|safety_stage|0|
|BUY|0|

KV3402bytes. Two natural members both reached observations; insufficient denominator to resolve the historical72->26 gap. First clock-incomplete generation is retained separately in natural.json, not merged; final natural_final.json is authoritative for these counts.

Health running,Paper/live_locked; old seven-table contract/funding digest unchanged5883a315353ee88e25bf6090c69bf7b216c0804145a7a6822922b776c3723980. No reset/history rewrite. No change to watch/TTL/frequency/strategy.
Short post-load held_fetch p95=1.909s, held_apply=.086s, observer4.570s; passive drops=0, wait p95=2.18450705. Baseline held2.005s/apply.131s. Short unequal windows cannot prove speedup; no initial material regression observed. Existing admission84 audit remains discontinuous and separate.

Artifacts: data/research/system94/natural_final.json; data/research/admission88/pre94.json and post94-final.json.
