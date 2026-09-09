# Reactivation temporary observation slot104

REPLY_TO: C2C-20260909-REACTIVATION-SLOT-104

## Frozen trial contract

This is a new authorized trial, not restoration of the reverted mature-incumbent probe. Existing non-held capacity remains10/chain, early3/growth4/mature3 base caps; no strategy/account/threshold/API cadence/source change. At most one temporary growth/mature rediscovery lease per chain,120s. It may use spare chain capacity or replace only a sampled early OVERFLOW watch resident>=120s. It never replaces a valid mature/growth base incumbent. Full base3/4/3 remains a legitimate skip, not grounds to increase capacity. Missing early3 slots are explicitly reserved both at probe admission and later non-early admissions while the probe exists. A protected pending probe may temporarily delay a NEW growth/mature arrival, but not early3. This is not a promise of unconditional future growth/mature priority over pending work.

Eligibility uses a newly natural rediscovery episode plus fresh basic-valid original-pool identity/three clocks/floor. The existing dormant-source query already reads the token's latest old snapshot: now capture its primitive baseline at that receipt, not later. Require exact same pool, known numeric current/prior activity, current volume>=200 OR transactions>=3 (existing broad activity criterion), current volume or transaction count greater than own prior, and price/liquidity no lower than own known prior. Unknown prior clocks/amounts/pool or lower-liquidity surface gets no special lease; ordinary routes remain available. No future price/ATH/allowlist/ranking, no assertion of economic Alpha.

Protection is in memory only: initialize special admission after first held-target refresh; union held/intent/recent-admitted targets, existing pending market-entry token set, async safety pending, passive cohort pending and bounded180s latest-ready cache.512 cache overflow temporarily disables special admission rather than dropping protection. No database read inside watch admission/expiry/victim selection. Held/pending probe survives expiry until protection clears; ordinary nonprotected probe releases after120s and cannot reacquire under the same bounded rediscovery membership. Base reservation reclaim targets explicit unprotected probe or early overflow only, never another ordinary mature slot. No BUY authority in this allocation.

Funnel94 remains the small existing diagnostic store: temporary_slot/released, fresh observed frame/2frames/3frames, associated pattern_observation/reactivation_ready/safety/BUY counts. Associations are prospective per episode; not proof of causation or independent strategy returns. No historical331-episode population is backfilled into the new process.

## Current evidence before trial

The latest process did NOT reproduce the older quoted funnel: at~19:23Z, generation19:03:23Z had29 episodes,1 hydration/snapshot/basic-valid/admission,1 chain-full skip. This is insufficient to attribute the current generation's primary bottleneck to watch alone. Previous mature-probe trial was reverted on held latency before any probe admission; it was not an allocation-outcome falsification. This more conservative trial adds own-baseline eligibility and avoids its hot-path SQL.

Pre19:30:50Z: immutable funding/registration digest0a9ed6e938ef2f7201af23b7fa201ab9104982553d68b5baaf8ddc21ff1fd24a; held_fetch p952.7359554s, held_apply_exit p95.0788464s, pattern observer p956.9992961s. Snapshot data/research/admission88/pre_reactivation104.json. Roll back on new passive drops or material held regression using prior guard (+min25%,250ms); retain the distinction between startup samples and causal comparable-load evidence.

## Validation before deployment

8 new focused lease/protection/eligibility tests PASS,4 existing compact-funnel tests PASS,1 dormant-source Store test PASS,8 existing watch-selected tests PASS. A new protected-extra-slot fixture caught base reclaim trying to remove a normal mature incumbent; fixed and rerun the8 lease tests. Tests cover startup disable, spare borrow, one-per-chain, fixed total, sampled overflow, base-full skip, pending/held/ready sources, expiration/no repeat, base reclaim/protected probe, own-pool/unknown/decay/no-activity. No claim of a full-suite pass. No provider calls added.

Independent reviewer identified that merely protecting a pending fourth mature slot could prevent future early3 admission. Final code additionally reserves the missing early slots; the regression now proves early3 admits while the later fourth growth waits. No normal mature incumbent is silently sacrificed.13 new/funnel/Store tests passed after this correction (8 lease,4 funnel,1 dormant source). Prior8 existing watch fixtures passed; no full-suite claim.

## Deployment and bounded result

Code b186971 loaded via existing scoped Paper launcher at2026-09-09T19:35:22Z, same active funding version. Only verified supervisor/its two Python runtime processes were replaced; no reset or Web restart. Pre-load snapshot19:35:03Z supersedes older performance baseline: held_fetch p952.56910133s, held_apply_exit.076563385s, pattern7.022308915s, passive wait2.0240587s, drops0.

Final snapshot19:38:51Z (about3.5min): health running/Paper-only/Live locked,5 open positions/2 unique held tokens from ordinary live Paper progression; held_fetch p952.75086843s (+.182s/+7.1%, below+.25s guard), apply.078556155s (+.002s), pattern6.14258274s, passive wait2.06244545s (+.038s), dropped batches/quotes0. Dex PoolTimeout/connect_errors0, waiting high/low0, low defers3 since process start. Before/after latest source-health rows show no429 orPoolTimeout last_error, not an all-request rate study. Existing max8/low5 gates and15s pattern cadence unchanged. Startup/mature workloads differ, so no causal speedup or sustained long-run PASS claimed.

The immutable registration/funding digest exactly matches pre-load:0a9ed6e938ef2f7201af23b7fa201ab9104982553d68b5baaf8ddc21ff1fd24a. Current observed nonheld buckets at19:38:08Z: BSC5/4/1,RH4/4/2,SOL3/4/3, totals10 each. Broader watched58 includes existing held/intent/recent-admitted protected targets outside the legacy nonheld cap; it is not58 new trial candidates. No new request path/task was introduced; addresses remain in the same existing batch budget.

Natural funnel cutoff19:38:23Z:5 episodes,1 hydration/snapshot/basic_valid/admission,1 replace_unusable,1 pattern_observation; temporary_slot0, temporary_slot_frames0, reactivation_ready0, linked BUY0. That sole observed receipt used the legacy route, not the new lease. Outcome: DEPLOYED_SHORT_GUARD_PASS / TEMPORARY_SLOT_COVERAGE_UNTESTED. No coverage improvement, extra BUY or second-wave Alpha claimed. Do not merge the old331-episode denominator into this new process generation. A real qualified later episode is needed to test the routing mechanism; do not loosen eligibility or increase slots to force one.

Artifacts: data/research/admission88/{pre_reactivation104_load,reactivation104_start,reactivation104_final}.json; data/research/reactivation104/{start,guard_1,guard_2}.json. Reports/metadata only staged, not runtime databases. No automatic monitoring/restarts or background work was added. Further material held/passive regression warrants rollback of this stage, not strategy tuning.
