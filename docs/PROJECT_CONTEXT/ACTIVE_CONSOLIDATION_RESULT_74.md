# Active-arm consolidation74

At 2026-09-09T05:44Z, independently read effective policies and reconciled every active arm's position/trade realized PnL. There were20 active arms. No selected arm had accounting-contamination or void records. This is not proof that all source-quality issues are absent; S1's known storm is explicitly excluded below.

## Paused NEW entry, retained all exits/history

Applied existing convergence KV at05:46:46.960833Z, no restart required for the pause:

| Arm | Terminals | Realized U | Median U | Best U | Top3 removed U |
|---|---:|---:|---:|---:|---:|
| migration_absorption_v1 |17|-22.619|-1.538|5.701|-32.001|
| observed_cycle_reset_reacceleration_control_v1 |61|-17.364|-0.467|2.171|-22.808|
| finalist_boundary_retest_v1 |10|-14.647|-1.227|4.470|-20.218|
| finalist_seller_absorption_v1 |19|-14.390|-1.015|1.148|-16.050|
| age_rate_horizon_fast_v1 |32|+102.038|-0.281|28.103|+25.862|
| age_rate_horizon_runner_v1 |31|-14.592|-0.395|14.077|-34.976|

First four have consistently negative current economics without compensating observed tails. They have no mandatory paired group. The only child of migration_absorption is already paused; other parents remain unchanged. S1's two arms are closed together as a completed experiment, **not both classified as failed strategies**. Its mandatory `age_rate_horizon_pair_v1`,size2 remains historically intact. No replacement ID was created merely to keep trades flowing. Fast had1 open and runner2 open at review; their exits continue.

S1 exact same-fill, equal quantity/cost comparison:29 clean both-terminal tokens, fast+104.9440455U,runner-12.0116179U,delta+116.9556634U. Mean+4.033,median+0.02184,10% trimmed mean+2.82684;15 wins/4 ties/10 losses. Top1 removal+83.85264U,top3+26.16958U.25 pairs exposed to fast max-hold account for the entire delta;4 early exits are identical. Two storm-confounded pairs excluded;2 pairs still censored. Thus fast advantage now survives the predefined top3 removal, unlike58's earlier cutoff; still small sample/regime dependent, not guaranteed alpha.

## Kept14

Unchanged: experiment_quiet_reawakening_candidate_v1, event_reawakening_v1, surface_lifecycle_pipeline_v1, prebreakout_net_accumulation_v1, liquidity_leads_price_v1, clone_liquidity_leader_v1, clone_m5volume_leader_v1, observed_set_relative_resilience_candidate_v1, clone_liquidity_handoff_v1, mature_new_acceptance_5u_v1, resource_age_rate_candidate_v1, resource_cooling_hold_candidate_v1, quiet_renewal_v1, quiet_renewal_legacy_exit_control_v1.

Reasons: the parent age-rate has151 terminals/+560.568U,top3 removed+262.098U; event reawakening/clone leaders have positive but small natural evidence; prebreakout and cooling remain marginal positive/tail-dependent, so this negative-arm slice does not relabel them failed. Remaining mechanisms have0–9 terminals and no independently established economic failure under this slice. Quiet renewal's small-N pair stays intact. These are KEEP_LEARNING/INSUFFICIENT_SAMPLE, not endorsements. Exact policies, distributions and dependencies in `data/research/consolidation74/active.json`.

## Acceptance

Only the convergence control changed. Immutable registration/funding/activation plus selected ledger digest before/after inside transaction:
`c29678e7688dc38c3ae989a4512a50f9096fe15a97b49e9e83a862c682b6f2a4`.
Post-cutoff1536 evaluations through1409355 contained0 outcomes for all6 selected arms;0 new positions. Artifacts `data/research/convergence74/{applied,acceptance}.json`, fresh paired evidence `data/research/consolidation74/s1/result.json`. No reset/backfill/funding/contract alteration/Live.


## Champion correction77 (supersedes any fast-promotion inference)
Message77 reports31 clean parent-fast common-fill terminals: parent+325.718877U, fast+104.149792U, fast-parent-221.569085U;15/4/12 wins/ties/losses. Removing top3 positive fast-parent deltas leaves about-230.435U. These are Lead-reported results, not a new Codex ledger recomputation. Fast beating60m does not beat the deployed parent. Keep S1 paused/completed; no standalone fast replacement or parent exit modification. Future challengers must compare directly to the deployed parent on equal-entry/common-fill evidence. See AGE_RATE_CHAMPION_CORRECTION_77.md for provenance and comparison boundaries.
