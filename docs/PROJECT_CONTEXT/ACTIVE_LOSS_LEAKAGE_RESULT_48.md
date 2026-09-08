# Active loss leakage48 disposition

REPLY_TO: C2C-20260909-ACTIVE-LOSS-LEAKAGE-48
Status: APPLIED, runtime control readback PASS. No restart/reset/backfill/Live or parameter changes.

Current API reproduced40 unpaused arms with>=30 terminals and capital-neutral total<=-50. Independent ledger checks: all selected have>=30 distinct terminal tokens, realized<=-50 and no accounting-contamination/void annotations. This does not prove absence of data-quality effects (including P0 storm); pausing is resource/economic convergence, not proof a mechanism can never work. API and ledger timestamps differ naturally; resource_cooling_hold control advanced206->207 terminals between reads.

39 NEW-entry pauses applied2026-09-08T20:45:11.994704Z through existing convergence KV. No schema/runtime code change. Declared paired groups checked against combined existing+new pause set. Remaining early_impulse15/60/probation size3 retained intact: control15 meets loss gate but60m members do not; pausing just15 would strand them. Other failed paired groups completed, including conditional_runner,finalist,earn_hold,failed_continuation and round2 controls. Source-arm metadata is not automatically a required buy parent: age-rate isolated observer candidate retained while broad control paused. Existing code uses source_arm_ids as provenance here, not a same-fill group. No new Shadow trades are claimed: existing evidence and rejected outcomes remain available; a fresh shadow comparator was not created in this scoped pause.

Transaction validation hashes registration/activation/policy-additions, existing funding/capital tables and all selected position/trade rows before/after KV update: identical. Exact table list/hash/previous control in applied.json supports reversal without deleting history. At20:46:05Z all39 report entry_paused=true;0 post-pause positions;22 positions remain open for exits. Retained15m reports unpaused. This is a54s no-new-BUY check, not proof of future absence. Live=false asserted from current config.

## Exact paused list

|Arm|Terminal rows|Distinct tokens|Costed terminal realized U|
|---|---:|---:|---:|
|bundle_adjusted_breadth_v1|55|55|-104.141|
|canonical-0186f1e75b238e63|55|46|-352.037|
|canonical-035ad2cf0cb0f6a5|181|181|-982.311|
|canonical-18d8ce34c0112abb|58|47|-194.898|
|canonical-1d9647200c714796|181|181|-982.311|
|canonical-2634d7c52e35b317|55|46|-367.067|
|canonical-3028ef000f6df93d|55|46|-352.037|
|canonical-619d142075228d0e|55|46|-367.067|
|canonical-b1c6865d30e91ddd|58|47|-194.898|
|churn_resistant_v1|68|68|-137.197|
|common_funding_adjusted_breadth_5u_v1|938|938|-999.122|
|dex-successor-014-1375c87c13cb1de1|55|46|-367.067|
|dex-successor-019-1d5937dec4e156d4|55|46|-367.067|
|dex-successor-026-25ad46e118f6edc9|146|146|-983.976|
|dex-successor-041-4a4be8bd60c050f5|146|146|-983.976|
|earn_the_hold_v1|30|30|-56.497|
|experiment_conditional_runner_control_v1|342|342|-760.130|
|experiment_participation_control_v1|45|45|-71.707|
|experiment_quiet_reawakening_control_v1|98|97|-97.191|
|failed_continuation_profit_lock_v1|30|30|-284.336|
|fast_stop_reclaim_v1|335|266|-323.281|
|finalist_baseline_v1|281|281|-344.998|
|finalist_profit_budget_v1|281|281|-329.959|
|finalist_progress_clock_v1|281|281|-199.466|
|high_recall_exit_pipeline_v1|93|30|-196.360|
|no_ca_event_flow_leader_v1|137|137|-72.965|
|observed_set_relative_resilience_control_v1|336|262|-124.753|
|paired_earn_the_hold_candidate_v1|30|30|-56.497|
|paired_earn_the_hold_control_v1|30|30|-55.117|
|paired_failed_continuation_profit_lock_candidate_v1|30|30|-284.336|
|paired_failed_continuation_profit_lock_control_v1|30|30|-284.336|
|price_to_flow_fragility_v1|30|30|-55.117|
|resource_age_rate_control_v1|322|321|-93.224|
|resource_cooling_hold_control_v1|207|206|-95.814|
|round2_response_exhaustion_control_v1|248|248|-339.460|
|round2_runner_requalification_control_v1|247|247|-319.328|
|round2_slow_grace_control_v1|321|321|-230.581|
|sustained_breakout_earn_hold_v1|101|101|-219.375|
|wave_reset_reentry_v1|67|33|-95.919|

## Pair and behavior grouping

- early_impulse_same_fill_v1: early_impulse_control_15m_v1, early_impulse_probation_60m_v1, early_impulse_trailing_60m_v1
- conditional_runner_revision_v2: experiment_conditional_runner_candidate_v1, experiment_conditional_runner_control_v1
- finalist_exit_matched_v1: finalist_activity_failure_v1, finalist_baseline_v1, finalist_depth_divergence_v1, finalist_profit_budget_v1, finalist_progress_clock_v1
- earn_the_hold: paired_earn_the_hold_candidate_v1, paired_earn_the_hold_control_v1
- failed_continuation_profit_lock: paired_failed_continuation_profit_lock_candidate_v1, paired_failed_continuation_profit_lock_control_v1
- round2_response_exhaustion: round2_response_exhaustion_candidate_v1, round2_response_exhaustion_control_v1
- round2_runner_requalification: round2_runner_requalification_candidate_v1, round2_runner_requalification_control_v1
- round2_slow_grace: round2_slow_grace_candidate_v1, round2_slow_grace_control_v1

Stored behavior-contract hash equivalence groups (do not infer equivalence merely from equal PnL):

- 0d4950a1f1d06ca5: canonical-0186f1e75b238e63, canonical-058b868fbd1d8065, canonical-3028ef000f6df93d, canonical-427d6a31e0a2e604, canonical-ac6059d9867697cd, canonical-bcf4041ab4578717, canonical-cca8c50b00503869, canonical-efdc816cff3321dd
- 68f1cd94234f5955: canonical-035ad2cf0cb0f6a5, canonical-1d9647200c714796, canonical-1ef2715c090f60fb, canonical-24ac3d4a360ab98c, canonical-53316326d5f1f7d5, canonical-57d44c510448173c, canonical-8e0e2a5367a26beb, canonical-c9204a1e7a1c45f3
- 7c383f78d1358153: dex-successor-014-1375c87c13cb1de1, dex-successor-019-1d5937dec4e156d4, dex-successor-038-45d45a6774225417, dex-successor-070-8a6c18233b0c33fd, dex-successor-074-94e2a27a7c53d44c, dex-successor-106-db27127f672cbae7, dex-successor-121-fa93589262a321f9, dex-successor-122-fa9e8436a3a39c63
- 7c8fb78641cf1625: canonical-18d8ce34c0112abb, canonical-25cfdc3e9adf23df, canonical-3093112db36e72a6, canonical-707c4491ca3caf89, canonical-9fdcf1c1c121b928, canonical-b1c6865d30e91ddd, canonical-e7b74ce032fcc5d3, canonical-fddc0b4e14f1836f
- 653ff2d2cfeddd98: dex-successor-026-25ad46e118f6edc9, dex-successor-041-4a4be8bd60c050f5, dex-successor-090-b5ad5642ccff0e2e, dex-successor-094-c39421bc0ad61a44, dex-successor-101-d1cb0c9edad31cbf, dex-successor-108-e44a1533954c80e5, dex-successor-112-ea5a51ca3135e1b8, dex-successor-123-fdcf73ca24c18fcc
- 673eba098787057e: canonical-2634d7c52e35b317, canonical-3c89090af7e8cd6b, canonical-504d9582ca75a709, canonical-5a16583de92bac39, canonical-619d142075228d0e, canonical-9e8b8ab496229059, canonical-addb9efa1916afbf, canonical-ef7bf4f71eeacb75
- bca6bd5a39567563: finalist_baseline_v1, round2_chase_candidate_v1, round2_chase_control_v1, round2_response_exhaustion_control_v1
- 2cf2a3e11b2cd943: finalist_profit_budget_v1, round2_giveback_duration_control_v1
- 6123926bd1a68c5d: finalist_progress_clock_v1, resource_profit_structure_control_v1, round2_slow_grace_control_v1

## Exact remaining unpaused disposition

These46 are retained for the stated current reason; positive or small-sample results are not Alpha claims.

|Arm|Terminals|Total U|Reason|
|---|---:|---:|---|
|experiment_quiet_reawakening_candidate_v1|1|-4.163060170319696|Insufficient terminal evidence (<30); no basis for this loss gate|
|experiment_pullback_reclaim_candidate_v1|227|None|Valuation unavailable; do not classify as exhausted from missing PnL|
|migration_absorption_v1|16|-21.08079231778345|Insufficient terminal evidence (<30); no basis for this loss gate|
|effective_breadth_v1|9|-41.26180602743791|Insufficient terminal evidence (<30); no basis for this loss gate|
|creator_early_holder_distribution_v1|29|-53.6685567637944|Insufficient terminal evidence (<30); no basis for this loss gate|
|market_regime_throttle_v1|5|4.751592292156783|Insufficient terminal evidence (<30); no basis for this loss gate|
|competing_risk_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|direct_lp_float_constrained_v1|8|-18.09079616787405|Insufficient terminal evidence (<30); no basis for this loss gate|
|serial_conditional_runner_v1|274|None|Valuation unavailable; do not classify as exhausted from missing PnL|
|event_reawakening_v1|4|8.794440200550913|Insufficient terminal evidence (<30); no basis for this loss gate|
|surface_lifecycle_pipeline_v1|2|-4.619008465105878|Insufficient terminal evidence (<30); no basis for this loss gate|
|prebreakout_net_accumulation_v1|82|-4.529772417880327|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|liquidity_leads_price_v1|1|-5.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|duration_competing_risk_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|early_observed_buyer_distribution_v1|29|-13.307879933676855|Insufficient terminal evidence (<30); no basis for this loss gate|
|observed_cycle_reset_reacceleration_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|observed_cycle_reset_reacceleration_control_v1|45|-13.805316846904159|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|issuance_holder_distribution_5u_v1|29|-13.414209470961811|Insufficient terminal evidence (<30); no basis for this loss gate|
|clone_liquidity_leader_v1|4|4.70221136731133|Insufficient terminal evidence (<30); no basis for this loss gate|
|clone_m5volume_leader_v1|2|1.0322188597979003|Insufficient terminal evidence (<30); no basis for this loss gate|
|observed_set_relative_resilience_candidate_v1|1|-0.384615384615385|Insufficient terminal evidence (<30); no basis for this loss gate|
|clone_liquidity_handoff_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|staged_probe_5u_only_control_v1|1130|None|Valuation unavailable; do not classify as exhausted from missing PnL|
|staged_probe_5u_conditional_15u_shadow_v1|1130|None|Valuation unavailable; do not classify as exhausted from missing PnL|
|mature_new_acceptance_5u_v1|1|-0.21384928716904295|Insufficient terminal evidence (<30); no basis for this loss gate|
|watched_wallet_confirmed_entry_candidate_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|finalist_boundary_retest_v1|9|-12.92676154622497|Insufficient terminal evidence (<30); no basis for this loss gate|
|finalist_seller_absorption_v1|14|-10.512769678434374|Insufficient terminal evidence (<30); no basis for this loss gate|
|finalist_price_then_depth_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|resource_age_rate_candidate_v1|120|163.84955257055347|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|resource_cooling_hold_candidate_v1|45|7.261205283619505|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|resource_profit_structure_control_v1|36|-23.34412510039281|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|inventory_baseline_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|inventory_contraction_v1|0|0.0|Insufficient terminal evidence (<30); no basis for this loss gate|
|archive_drift_v1|84|-4.917152760227154|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|archive_plateau_v1|84|-4.917152760227154|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|archive_release_v1|3|-2.027540073705091|Insufficient terminal evidence (<30); no basis for this loss gate|
|quiet_renewal_v1|1|1.17760250867107|Insufficient terminal evidence (<30); no basis for this loss gate|
|quiet_renewal_legacy_exit_control_v1|1|-1.1671497125481074|Insufficient terminal evidence (<30); no basis for this loss gate|
|early_impulse_control_15m_v1|68|-62.286557513187226|Required member of same-fill size3; other60m members do not meet loss gate. Do not strand retained horizon experiment.|
|early_impulse_trailing_60m_v1|68|-8.916728809953426|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|early_impulse_probation_60m_v1|68|-8.916728809953426|Does not meet fixed loss gate total<=-50; preserve existing experiment, not Alpha endorsement|
|runner_ultra_early_control_v1|6|-10.611531783619046|Insufficient terminal evidence (<30); no basis for this loss gate|
|runner_ultra_early_lock_v1|6|-9.441969223591105|Insufficient terminal evidence (<30); no basis for this loss gate|
|age_rate_horizon_fast_v1|3|-2.652229869004476|Insufficient terminal evidence (<30); no basis for this loss gate|
|age_rate_horizon_runner_v1|3|-2.6850059137409024|Insufficient terminal evidence (<30); no basis for this loss gate|

Evidence: data/research/convergence48/{api_before.json,candidate_rows.json,ledger_verified.json,preview.json,applied.json,postcheck.json}. Scoped applicator scripts/apply_convergence48.py has preview, active-version/pair/sample/annotation/invariant guards. No new economic computation or strategy tuning. ACTIVE16 corrected matching remains active; P0 connection-pool long-run closure and separate BSC gaps remain unchanged.
