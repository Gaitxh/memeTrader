# Strategy Court — 仅建议，未修改运行状态

判决依据是当前合同、冻结前沿的追加交易路径及共同入场退出证据。KEEP 是研究角色，不是所有账户无限运行的建议。152 是字段/dispatch 归类数，不能断言152个独立经济思想；实际发生差异的机制更少。

RETIRE_DUPLICATE 要求同声明合同、非空共同机会的完整交易路径一致（包括时间、金额、原因）；异步激活/现金约束导致的非共同机会另计。它不保证未来所有路径一致。FREEZE_NEW_ENTRY 只针对当前低信息退出实验，已有仓位应按原合同退出；本轮没有执行这些生产操作。

无BUY的14臂仍为覆盖未明，不能无证据判 INPUT_NOT_AVAILABLE；该状态不应成为永久保留理由。下一轮先解释输入/触发/容量分母。没有凭零污染行认定所有历史工程正确。

账户建议计数：`{"KEEP_INFORMATIONAL": 102, "KEEP_BENCHMARK": 61, "RETIRE_DUPLICATE": 59, "FREEZE_NEW_ENTRY": 6, "PROMISING_UNPROVEN": 2}`。详细可重算证据：`data/research/alpha_diagnosis_20260907/court/arm_court.csv`。

## 全部行为家族

| Family | 参考 arm | 账户数 | 家族内建议 |
|---|---|---:|---|
| 0194a32b49139255 | canonical-2390fb342a6e90b6 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 027d6740f852d23b | l0_profit_lock_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 0351448396a01291 | canonical-4b290f4f2bba4fb4 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 058634584f8a6402 | dex-successor-012-0eea3c62cb7bacc4 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 0863753ce22522e6 | dex-successor-069-88446f2e2831bb0d | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 0b446964e3fb389d | canonical-619d142075228d0e | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 0d7cf6a9513ff66c | vault_hazard_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 0d91b52890f058a8 | fast_stop_reclaim_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 1201dfb0684b281c | round2_giveback_duration_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 1276f2b1c754bb39 | resource_cooling_hold_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 192027eada7ca8be | canonical-b1c6865d30e91ddd | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 1d25a5fc208a7196 | canonical-0006b989b189e0ac | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| 1e1aa12d5104b3d5 | canonical-195049e27d177b1f | 1 | {"KEEP_INFORMATIONAL": 1} |
| 1fb2d13aca453873 | staged_probe_20u_once_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 21c81286fe376db6 | canonical-5054a25aae97fdf9 | 2 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 1} |
| 2871501999d2cb1f | watched_wallet_distribution_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 29fa291a69778411 | volatility_scaled_depth_flow_momentum_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 2ca98a191ed63084 | observed_cycle_reset_reacceleration_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 2e1b18e90ad16c13 | watched_wallet_confirmed_entry_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 30a90f129a4eda5e | round2_slow_grace_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 32f34d37a405fd00 | finalist_depth_divergence_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| 33c37cb7bbc41991 | experiment_participation_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 369140d248fa66aa | watched_wallet_distribution_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 369da9bb28b48f63 | clone_m5volume_leader_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 384465d4178b8dae | finalist_baseline_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 385d3b245b509452 | no_ca_event_flow_leader_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 3b19545d5caa79a9 | canonical-3733dc40ac3c74ea | 2 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 1} |
| 3c8f92ddd028b70f | round2_chase_candidate_v1 | 2 | {"KEEP_BENCHMARK": 2} |
| 3ce7bb1b623fd469 | migration_absorption_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 3d0078d8d26fde71 | staged_probe_5u_only_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 3de866c27e9f9d78 | l0_profit_lock_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 3df6bf2b7d055279 | paired_earn_the_hold_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 3e650b4967ff67a4 | canonical-4a27a58cc5902ea9 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 3fe07ae2ac387297 | round2_slow_grace_candidate_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| 4003ab6f56f1557d | canonical-0c198e6aa30fa049 | 6 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 5} |
| 4019eadfd79e875d | canonical-0d7caccf76779d74 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 403bb30ee0064d53 | early_observed_buyer_distribution_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 432895dd4eb0f0b5 | price_to_flow_fragility_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 458a358e70b23dde | finalist_profit_budget_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 45a8f9967911e144 | sustained_breakout_earn_hold_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 4660e006205db4d5 | canonical-0ad93cd8a7bec9ec | 6 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 5} |
| 47b72e4f462bc6b6 | observed_cycle_reset_reacceleration_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 47dd8e540cc1f2a3 | clone_liquidity_handoff_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 489d09a8088a1c11 | dex-successor-041-4a4be8bd60c050f5 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| 48cecc41c78a90b5 | canonical-ddd57b024d84a00b | 1 | {"KEEP_INFORMATIONAL": 1} |
| 4b8141148aca73fd | paired_vault_hazard_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 4b957fa992d1c898 | staged_probe_5u_conditional_15u_shadow_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 4ba78499fc3a4a14 | watched_wallet_confirmed_entry_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 4dc561d2284e818a | canonical-a0b46b71b30d8575 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 5088612607e87b23 | dex-successor-026-25ad46e118f6edc9 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 550c5a0dd38f9b44 | round2_giveback_duration_candidate_v1 | 1 | {"PROMISING_UNPROVEN": 1} |
| 5724ad28651ce878 | canonical-1d9647200c714796 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 583183dcd382239c | dex-successor-032-30d85f39d76f4f18 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 5b1e5869e83fe7ce | resource_profit_structure_candidate_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| 5c19c08517c1e081 | surface_lifecycle_pipeline_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 5cc2a0f36d9f4813 | l0_continuation_failure_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 5e2553004f405bd6 | experiment_migration_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 5e9830b2b48896a7 | experiment_sustained_breakout_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 5ffc34d5aca71248 | experiment_quiet_reawakening_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 68caf60a8e205efc | canonical-831b37e3aaeaa64d | 1 | {"KEEP_INFORMATIONAL": 1} |
| 6988ad590da29f8e | event_reawakening_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 69d3b2b95185d0ce | experiment_conditional_runner_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 6a66a6ede2bfa06f | earn_the_hold_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 6c141ebf893d2629 | resource_cooling_hold_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 6fac5fed6c12a779 | resource_age_rate_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 701ab36d21d62f1c | common_funding_adjusted_breadth_5u_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 7034ecd89ae759b8 | round2_response_exhaustion_candidate_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| 72232dbbe0f4789d | canonical-0cd0f3c790d85ca5 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 727d298171ac366e | experiment_pullback_reclaim_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 74390db1a34214f0 | experiment_conditional_runner_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 745fd622e9154b59 | serial_conditional_runner_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 75452cf9d48ad013 | issuance_holder_distribution_5u_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 77907e950e57a129 | clone_liquidity_leader_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 7af0d03f15fe2378 | experiment_narrative_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 7d9a7ee59006314e | broad_principal_lock_runner_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 7e10a441cf231014 | finalist_boundary_retest_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 7eda90bc8a5b0df6 | liquidity_leads_price_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 8117498bbe68c7f8 | canonical-a7ca496301c23662 | 2 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 1} |
| 81b2d758802168a0 | finalist_activity_failure_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| 827e20f7ecc1c1d0 | experiment_migration_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 82896a969e1b4c2e | paired_earn_the_hold_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 84ddcf11e6b35201 | canonical-63e62a12e74b6320 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 8545204977205a19 | finalist_progress_clock_v1 | 1 | {"PROMISING_UNPROVEN": 1} |
| 86e5ec98c4329b86 | churn_resistant_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 88f34dfa744cacb6 | round2_response_exhaustion_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 891089c0dc718860 | paired_failed_continuation_profit_lock_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 8a786dc121f0c2c5 | creator_early_holder_distribution_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 8ac2d751c1c554c6 | canonical-0df3639e1824ad0f | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| 940d9b966939a8c5 | finalist_price_then_depth_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 9561f6f4752cc168 | canonical-05005fdaa932d3d0 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 95a3b089c786303d | failed_continuation_profit_lock_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 98aadae68976e129 | canonical-0186f1e75b238e63 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| 9b7063f7871ec104 | finalist_seller_absorption_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 9c596d56d7ee793e | experiment_quiet_reawakening_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| 9d5a006204c5a748 | competing_risk_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| 9d9c06b0bcf61aae | dex-successor-019-1d5937dec4e156d4 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| 9efb8d5bbf9e2bc9 | canonical-3028ef000f6df93d | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| 9f26e9b54ef0f9e3 | resource_age_rate_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| a0e503279cbea853 | capital_velocity_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| a5303546f2a10177 | observed_set_relative_resilience_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| a595b55ea54ff07e | wave_reset_reentry_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| a79b77a7ca28dd84 | volatility_scaled_depth_flow_momentum_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| a869a092628d0375 | high_recall_exit_pipeline_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| a8952ca458a0abc8 | dex-successor-120-f98e117baa206954 | 1 | {"KEEP_INFORMATIONAL": 1} |
| ab8d371913262bc5 | dex-successor-039-46f730df93b191f3 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| aba28d0dc717c91e | experiment_sustained_breakout_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| ad1d0cea159c235d | dex-successor-046-546560b93b10c79c | 1 | {"KEEP_INFORMATIONAL": 1} |
| af77f0d6d773acb6 | duration_competing_risk_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| b270536c83763290 | mature_new_acceptance_5u_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| b6b82416e101c901 | canonical-75dadf52fc0cdd9e | 1 | {"KEEP_INFORMATIONAL": 1} |
| b94bc4c2772fd105 | canonical-2634d7c52e35b317 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| bd36fa15747d55c5 | experiment_panic_reclaim_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| be2c1e9600d71214 | dex-successor-014-1375c87c13cb1de1 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| bea49e4ebcc6b9b6 | round2_runner_requalification_candidate_v1 | 1 | {"FREEZE_NEW_ENTRY": 1} |
| c3276485937e2cb5 | bundle_adjusted_breadth_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| c45d48c9b1de7d6f | experiment_support_risk_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| c658340fc82b6596 | direct_lp_float_constrained_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| c7327bb570617b82 | dex-successor-067-842383c9376853b7 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| c9c2aedba4d22cda | canonical-aa5d0c9d6721fb48 | 1 | {"KEEP_INFORMATIONAL": 1} |
| cb16f6c70c6012c4 | executable_recovery_decay_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| cf17fff932331f64 | canonical-18d8ce34c0112abb | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| cf443b58ec6ee23b | experiment_support_risk_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| d19aa3e409365a11 | migration_amount_rate_absorption_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| d4548bdee4824a38 | paired_failed_continuation_profit_lock_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| d6f9d5b5371afe14 | authoritative_event_shock_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| d8afa52808d91f96 | canonical-ca8f32cf0d565e07 | 1 | {"KEEP_INFORMATIONAL": 1} |
| d957e4f228a9cfb0 | dex-successor-025-2509c2f13f40a238 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |
| d9f7f21099f94c49 | experiment_narrative_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| dea3fbb9117a176c | observed_set_relative_resilience_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| df60c1ca987e1c87 | direct_lp_amount_specific_confirmed_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e01f0a7ad067a5da | experiment_pullback_reclaim_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e098739c22fef5da | l0_continuation_failure_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| e2f57c221c587d2c | canonical-7c7c863ffc06fdf6 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e2f88f9aac2bffef | broad_flash_tail_first_mover_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e366327ddab0ea4f | prebreakout_net_accumulation_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e6024fe917337444 | dex-successor-095-c78ed4ffa4877807 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e6953094bbdfc86f | finite_capital_ranker_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| e79a43ad56aebff4 | canonical-627c3b1e3fc4157d | 6 | {"KEEP_BENCHMARK": 1, "KEEP_INFORMATIONAL": 5} |
| e9a11cda4f5f600d | paired_vault_hazard_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| ea13c597a6376201 | resource_profit_structure_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| eca8cb9d54ad0e89 | dex-successor-049-5ce40de1d93304fb | 1 | {"KEEP_INFORMATIONAL": 1} |
| ed35c3113b7ea4b4 | official_event_actual_flow_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| ee0471cd8d753202 | market_regime_throttle_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| efc78b22a2382747 | canonical-22dbe223b3814f7f | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| f15e59a90b944dc4 | dex-successor-068-85b7ea76ae522727 | 2 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 1} |
| f338ce34bb89b1ad | round2_runner_requalification_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| f44750b8b544246b | broad_cost_coverage_scaleout_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| f5645422bec3bcda | broad_mature_continuity_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| f5c2f6444afd2a37 | experiment_participation_candidate_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| fa7cf0aa0b8e6099 | effective_breadth_v1 | 1 | {"KEEP_INFORMATIONAL": 1} |
| fd72d73b372d4e35 | experiment_panic_reclaim_control_v1 | 1 | {"KEEP_BENCHMARK": 1} |
| ff2ead6fc0c42cd3 | canonical-035ad2cf0cb0f6a5 | 6 | {"KEEP_BENCHMARK": 1, "RETIRE_DUPLICATE": 5} |

## 全部账户裁决

| Arm | 建议 | 共同机会 / Token | 相同完整路径 |
|---|---|---:|---:|
| canonical-2390fb342a6e90b6 | KEEP_INFORMATIONAL | 146 / 144 | 146 |
| l0_profit_lock_candidate_v1 | KEEP_INFORMATIONAL | 243 / 243 | 243 |
| canonical-4b290f4f2bba4fb4 | KEEP_BENCHMARK | 191 / 189 | 191 |
| canonical-a6741f19300d52f1 | RETIRE_DUPLICATE | 191 / 189 | 191 |
| dex-successor-012-0eea3c62cb7bacc4 | KEEP_BENCHMARK | 166 / 165 | 166 |
| dex-successor-052-62d73d37cb094974 | RETIRE_DUPLICATE | 166 / 165 | 166 |
| dex-successor-069-88446f2e2831bb0d | KEEP_BENCHMARK | 9 / 9 | 9 |
| dex-successor-078-9eab102528bb48c4 | RETIRE_DUPLICATE | 9 / 9 | 9 |
| canonical-619d142075228d0e | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-9e8b8ab496229059 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| vault_hazard_v1 | KEEP_INFORMATIONAL | 152 / 152 | 152 |
| fast_stop_reclaim_v1 | KEEP_INFORMATIONAL | 210 / 158 | 210 |
| round2_giveback_duration_control_v1 | KEEP_BENCHMARK | 236 / 236 | 236 |
| resource_cooling_hold_control_v1 | KEEP_BENCHMARK | 20 / 20 | 20 |
| canonical-b1c6865d30e91ddd | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-e7b74ce032fcc5d3 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-0006b989b189e0ac | KEEP_BENCHMARK | 191 / 189 | 191 |
| canonical-0356dc612c90a689 | RETIRE_DUPLICATE | 191 / 189 | 191 |
| canonical-19b9d4d442fde1ab | RETIRE_DUPLICATE | 191 / 189 | 191 |
| canonical-1c2ac45bb5154011 | RETIRE_DUPLICATE | 191 / 189 | 191 |
| canonical-6c728fb1b79d226a | RETIRE_DUPLICATE | 191 / 189 | 191 |
| canonical-cae3a114676b9324 | RETIRE_DUPLICATE | 191 / 189 | 191 |
| canonical-195049e27d177b1f | KEEP_INFORMATIONAL | 124 / 123 | 124 |
| staged_probe_20u_once_control_v1 | KEEP_BENCHMARK | 267 / 267 | 267 |
| canonical-5054a25aae97fdf9 | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-adc90ff111d03016 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| watched_wallet_distribution_control_v1 | KEEP_BENCHMARK | 307 / 307 | 307 |
| volatility_scaled_depth_flow_momentum_v1 | KEEP_INFORMATIONAL | 163 / 163 | 163 |
| observed_cycle_reset_reacceleration_control_v1 | KEEP_BENCHMARK | 17 / 17 | 17 |
| watched_wallet_confirmed_entry_candidate_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| round2_slow_grace_control_v1 | KEEP_BENCHMARK | 304 / 304 | 304 |
| finalist_depth_divergence_v1 | FREEZE_NEW_ENTRY | 264 / 264 | 264 |
| experiment_participation_control_v1 | KEEP_BENCHMARK | 21 / 21 | 21 |
| watched_wallet_distribution_candidate_v1 | KEEP_INFORMATIONAL | 307 / 307 | 307 |
| clone_m5volume_leader_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| finalist_baseline_v1 | KEEP_BENCHMARK | 264 / 264 | 264 |
| no_ca_event_flow_leader_v1 | KEEP_INFORMATIONAL | 58 / 58 | 58 |
| canonical-3733dc40ac3c74ea | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-39063fa299ee2cfd | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| round2_chase_candidate_v1 | KEEP_BENCHMARK | 189 / 189 | 189 |
| round2_chase_control_v1 | KEEP_BENCHMARK | 189 / 189 | 189 |
| migration_absorption_v1 | KEEP_INFORMATIONAL | 5 / 5 | 5 |
| staged_probe_5u_only_control_v1 | KEEP_BENCHMARK | 663 / 663 | 663 |
| l0_profit_lock_control_v1 | KEEP_BENCHMARK | 236 / 236 | 236 |
| paired_earn_the_hold_control_v1 | KEEP_BENCHMARK | 14 / 14 | 14 |
| canonical-4a27a58cc5902ea9 | KEEP_INFORMATIONAL | 182 / 180 | 182 |
| round2_slow_grace_candidate_v1 | FREEZE_NEW_ENTRY | 304 / 304 | 304 |
| canonical-0c198e6aa30fa049 | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-6423ca6248abf0f9 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-8eed440ae6e40cdf | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-aa3ecee6b712fc53 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-c2f29f5b78e5a3a9 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-db22c376fcd22466 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-0d7caccf76779d74 | KEEP_INFORMATIONAL | 157 / 156 | 157 |
| early_observed_buyer_distribution_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| price_to_flow_fragility_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| finalist_profit_budget_v1 | KEEP_INFORMATIONAL | 264 / 264 | 264 |
| sustained_breakout_earn_hold_v1 | KEEP_INFORMATIONAL | 56 / 56 | 56 |
| canonical-0ad93cd8a7bec9ec | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-10af25fd9780e2af | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-65e78965552bd91b | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-91e44b09867ae22e | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-d69a266410f4ef7a | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-e87e33896472940a | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| observed_cycle_reset_reacceleration_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| clone_liquidity_handoff_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| dex-successor-041-4a4be8bd60c050f5 | KEEP_BENCHMARK | 142 / 142 | 142 |
| dex-successor-090-b5ad5642ccff0e2e | RETIRE_DUPLICATE | 142 / 142 | 142 |
| dex-successor-094-c39421bc0ad61a44 | RETIRE_DUPLICATE | 142 / 142 | 142 |
| dex-successor-108-e44a1533954c80e5 | RETIRE_DUPLICATE | 142 / 142 | 142 |
| dex-successor-112-ea5a51ca3135e1b8 | RETIRE_DUPLICATE | 142 / 142 | 142 |
| dex-successor-123-fdcf73ca24c18fcc | RETIRE_DUPLICATE | 142 / 142 | 142 |
| canonical-ddd57b024d84a00b | KEEP_INFORMATIONAL | 124 / 123 | 124 |
| paired_vault_hazard_candidate_v1 | KEEP_INFORMATIONAL | 152 / 152 | 152 |
| staged_probe_5u_conditional_15u_shadow_v1 | KEEP_INFORMATIONAL | 663 / 663 | 663 |
| watched_wallet_confirmed_entry_control_v1 | KEEP_BENCHMARK | 279 / 279 | 279 |
| canonical-a0b46b71b30d8575 | KEEP_INFORMATIONAL | 182 / 180 | 182 |
| dex-successor-026-25ad46e118f6edc9 | KEEP_BENCHMARK | 142 / 142 | 142 |
| dex-successor-101-d1cb0c9edad31cbf | RETIRE_DUPLICATE | 142 / 142 | 142 |
| round2_giveback_duration_candidate_v1 | PROMISING_UNPROVEN | 236 / 236 | 236 |
| canonical-1d9647200c714796 | KEEP_BENCHMARK | 167 / 167 | 167 |
| canonical-24ac3d4a360ab98c | RETIRE_DUPLICATE | 167 / 167 | 167 |
| dex-successor-032-30d85f39d76f4f18 | KEEP_BENCHMARK | 166 / 165 | 166 |
| dex-successor-118-f336bf0ae10004cd | RETIRE_DUPLICATE | 166 / 165 | 166 |
| resource_profit_structure_candidate_v1 | FREEZE_NEW_ENTRY | 19 / 19 | 19 |
| surface_lifecycle_pipeline_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| l0_continuation_failure_candidate_v1 | KEEP_INFORMATIONAL | 171 / 171 | 171 |
| experiment_migration_candidate_v1 | KEEP_INFORMATIONAL | 169 / 169 | 169 |
| experiment_sustained_breakout_candidate_v1 | KEEP_INFORMATIONAL | 188 / 188 | 188 |
| experiment_quiet_reawakening_candidate_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| canonical-831b37e3aaeaa64d | KEEP_INFORMATIONAL | 186 / 184 | 186 |
| event_reawakening_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| experiment_conditional_runner_candidate_v1 | KEEP_INFORMATIONAL | 342 / 342 | 342 |
| earn_the_hold_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| resource_cooling_hold_candidate_v1 | KEEP_INFORMATIONAL | 8 / 8 | 8 |
| resource_age_rate_control_v1 | KEEP_BENCHMARK | 19 / 19 | 19 |
| common_funding_adjusted_breadth_5u_v1 | KEEP_INFORMATIONAL | 649 / 649 | 649 |
| round2_response_exhaustion_candidate_v1 | FREEZE_NEW_ENTRY | 231 / 231 | 231 |
| canonical-0cd0f3c790d85ca5 | KEEP_INFORMATIONAL | 110 / 109 | 110 |
| experiment_pullback_reclaim_control_v1 | KEEP_BENCHMARK | 209 / 209 | 209 |
| experiment_conditional_runner_control_v1 | KEEP_BENCHMARK | 342 / 342 | 342 |
| serial_conditional_runner_v1 | KEEP_INFORMATIONAL | 145 / 145 | 145 |
| issuance_holder_distribution_5u_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| clone_liquidity_leader_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| experiment_narrative_candidate_v1 | KEEP_INFORMATIONAL | 292 / 292 | 292 |
| broad_principal_lock_runner_v1 | KEEP_INFORMATIONAL | 210 / 210 | 210 |
| finalist_boundary_retest_v1 | KEEP_INFORMATIONAL | 7 / 7 | 7 |
| liquidity_leads_price_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| canonical-a7ca496301c23662 | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-eb1795742aed4576 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| finalist_activity_failure_v1 | FREEZE_NEW_ENTRY | 264 / 264 | 264 |
| experiment_migration_control_v1 | KEEP_BENCHMARK | 180 / 180 | 180 |
| paired_earn_the_hold_candidate_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| canonical-63e62a12e74b6320 | KEEP_INFORMATIONAL | 148 / 146 | 148 |
| finalist_progress_clock_v1 | PROMISING_UNPROVEN | 264 / 264 | 264 |
| churn_resistant_v1 | KEEP_INFORMATIONAL | 32 / 32 | 32 |
| round2_response_exhaustion_control_v1 | KEEP_BENCHMARK | 231 / 231 | 231 |
| paired_failed_continuation_profit_lock_candidate_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| creator_early_holder_distribution_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| canonical-0df3639e1824ad0f | KEEP_BENCHMARK | 162 / 162 | 162 |
| canonical-2d3874b5b4dfe162 | RETIRE_DUPLICATE | 162 / 162 | 162 |
| canonical-744153cee3d16c08 | RETIRE_DUPLICATE | 162 / 162 | 162 |
| canonical-83fdc6be4ed5e6bf | RETIRE_DUPLICATE | 162 / 162 | 162 |
| canonical-d276043eb5aa27c2 | RETIRE_DUPLICATE | 162 / 162 | 162 |
| canonical-eaaf188e7835376f | RETIRE_DUPLICATE | 162 / 162 | 162 |
| finalist_price_then_depth_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| canonical-05005fdaa932d3d0 | KEEP_INFORMATIONAL | 137 / 136 | 137 |
| failed_continuation_profit_lock_v1 | KEEP_INFORMATIONAL | 14 / 14 | 14 |
| canonical-0186f1e75b238e63 | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-058b868fbd1d8065 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-427d6a31e0a2e604 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-ac6059d9867697cd | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-cca8c50b00503869 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-efdc816cff3321dd | RETIRE_DUPLICATE | 1 / 1 | 1 |
| finalist_seller_absorption_v1 | KEEP_INFORMATIONAL | 6 / 6 | 6 |
| experiment_quiet_reawakening_control_v1 | KEEP_BENCHMARK | 63 / 62 | 63 |
| competing_risk_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| dex-successor-019-1d5937dec4e156d4 | KEEP_BENCHMARK | 1 / 1 | 1 |
| dex-successor-070-8a6c18233b0c33fd | RETIRE_DUPLICATE | 1 / 1 | 1 |
| dex-successor-074-94e2a27a7c53d44c | RETIRE_DUPLICATE | 1 / 1 | 1 |
| dex-successor-106-db27127f672cbae7 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| dex-successor-121-fa93589262a321f9 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| dex-successor-122-fa9e8436a3a39c63 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-3028ef000f6df93d | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-bcf4041ab4578717 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| resource_age_rate_candidate_v1 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| capital_velocity_v1 | KEEP_INFORMATIONAL | 87 / 87 | 87 |
| observed_set_relative_resilience_candidate_v1 | KEEP_INFORMATIONAL | 1 / 1 | 1 |
| wave_reset_reentry_v1 | KEEP_INFORMATIONAL | 41 / 20 | 41 |
| volatility_scaled_depth_flow_momentum_control_v1 | KEEP_BENCHMARK | 162 / 162 | 162 |
| high_recall_exit_pipeline_v1 | KEEP_INFORMATIONAL | 43 / 14 | 43 |
| dex-successor-120-f98e117baa206954 | KEEP_INFORMATIONAL | 97 / 97 | 97 |
| dex-successor-039-46f730df93b191f3 | KEEP_BENCHMARK | 166 / 165 | 166 |
| dex-successor-119-f3cf5416894220d7 | RETIRE_DUPLICATE | 166 / 165 | 166 |
| experiment_sustained_breakout_control_v1 | KEEP_BENCHMARK | 188 / 188 | 188 |
| dex-successor-046-546560b93b10c79c | KEEP_INFORMATIONAL | 240 / 239 | 240 |
| duration_competing_risk_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| mature_new_acceptance_5u_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| canonical-75dadf52fc0cdd9e | KEEP_INFORMATIONAL | 96 / 95 | 96 |
| canonical-2634d7c52e35b317 | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-3c89090af7e8cd6b | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-504d9582ca75a709 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-5a16583de92bac39 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-addb9efa1916afbf | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-ef7bf4f71eeacb75 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| experiment_panic_reclaim_candidate_v1 | KEEP_INFORMATIONAL | 127 / 127 | 127 |
| dex-successor-014-1375c87c13cb1de1 | KEEP_BENCHMARK | 1 / 1 | 1 |
| dex-successor-038-45d45a6774225417 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| round2_runner_requalification_candidate_v1 | FREEZE_NEW_ENTRY | 230 / 230 | 230 |
| bundle_adjusted_breadth_v1 | KEEP_INFORMATIONAL | 28 / 28 | 28 |
| experiment_support_risk_control_v1 | KEEP_BENCHMARK | 66 / 66 | 66 |
| direct_lp_float_constrained_v1 | KEEP_INFORMATIONAL | 2 / 2 | 2 |
| dex-successor-067-842383c9376853b7 | KEEP_BENCHMARK | 166 / 165 | 166 |
| dex-successor-075-977f322fba28b9bc | RETIRE_DUPLICATE | 166 / 165 | 166 |
| canonical-aa5d0c9d6721fb48 | KEEP_INFORMATIONAL | 180 / 178 | 180 |
| executable_recovery_decay_v1 | KEEP_INFORMATIONAL | 152 / 152 | 152 |
| canonical-18d8ce34c0112abb | KEEP_BENCHMARK | 1 / 1 | 1 |
| canonical-25cfdc3e9adf23df | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-3093112db36e72a6 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-707c4491ca3caf89 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-9fdcf1c1c121b928 | RETIRE_DUPLICATE | 1 / 1 | 1 |
| canonical-fddc0b4e14f1836f | RETIRE_DUPLICATE | 1 / 1 | 1 |
| experiment_support_risk_candidate_v1 | KEEP_INFORMATIONAL | 66 / 66 | 66 |
| migration_amount_rate_absorption_v1 | KEEP_INFORMATIONAL | 311 / 311 | 311 |
| paired_failed_continuation_profit_lock_control_v1 | KEEP_BENCHMARK | 14 / 14 | 14 |
| authoritative_event_shock_v1 | KEEP_INFORMATIONAL | 185 / 185 | 185 |
| canonical-ca8f32cf0d565e07 | KEEP_INFORMATIONAL | 262 / 261 | 262 |
| dex-successor-025-2509c2f13f40a238 | KEEP_BENCHMARK | 9 / 9 | 9 |
| dex-successor-035-3be68fb41c7f0536 | RETIRE_DUPLICATE | 9 / 9 | 9 |
| dex-successor-058-6e2af57081e33ce0 | RETIRE_DUPLICATE | 9 / 9 | 9 |
| dex-successor-062-7726580fd0f701f1 | RETIRE_DUPLICATE | 9 / 9 | 9 |
| dex-successor-092-bd048c8b412c53b5 | RETIRE_DUPLICATE | 9 / 9 | 9 |
| dex-successor-099-cb5e6c13704cb97a | RETIRE_DUPLICATE | 9 / 9 | 9 |
| experiment_narrative_control_v1 | KEEP_BENCHMARK | 273 / 273 | 273 |
| observed_set_relative_resilience_control_v1 | KEEP_BENCHMARK | 49 / 37 | 49 |
| direct_lp_amount_specific_confirmed_v1 | KEEP_INFORMATIONAL | 445 / 445 | 445 |
| experiment_pullback_reclaim_candidate_v1 | KEEP_INFORMATIONAL | 96 / 96 | 96 |
| l0_continuation_failure_control_v1 | KEEP_BENCHMARK | 147 / 147 | 147 |
| canonical-7c7c863ffc06fdf6 | KEEP_INFORMATIONAL | 128 / 127 | 128 |
| broad_flash_tail_first_mover_v1 | KEEP_INFORMATIONAL | 146 / 145 | 146 |
| prebreakout_net_accumulation_v1 | KEEP_INFORMATIONAL | 33 / 33 | 33 |
| dex-successor-095-c78ed4ffa4877807 | KEEP_INFORMATIONAL | 166 / 165 | 166 |
| finite_capital_ranker_v1 | KEEP_INFORMATIONAL | 177 / 177 | 177 |
| canonical-627c3b1e3fc4157d | KEEP_BENCHMARK | 9 / 9 | 9 |
| canonical-69be52c97c1c686d | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-7c86e5fc9e55178e | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-9b8c8540532b6db2 | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-e8ad7db7c6a6386c | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| canonical-ecc266d212b9d0ef | KEEP_INFORMATIONAL | 9 / 9 | 9 |
| paired_vault_hazard_control_v1 | KEEP_BENCHMARK | 152 / 152 | 152 |
| resource_profit_structure_control_v1 | KEEP_BENCHMARK | 19 / 19 | 19 |
| dex-successor-049-5ce40de1d93304fb | KEEP_INFORMATIONAL | 174 / 173 | 174 |
| official_event_actual_flow_v1 | KEEP_INFORMATIONAL | 359 / 359 | 359 |
| market_regime_throttle_v1 | KEEP_INFORMATIONAL | 0 / 0 | 0 |
| canonical-22dbe223b3814f7f | KEEP_BENCHMARK | 162 / 162 | 162 |
| canonical-d785aa5181f97422 | RETIRE_DUPLICATE | 162 / 162 | 162 |
| dex-successor-068-85b7ea76ae522727 | KEEP_BENCHMARK | 166 / 165 | 166 |
| dex-successor-088-b18c9c129af7fbfc | RETIRE_DUPLICATE | 166 / 165 | 166 |
| round2_runner_requalification_control_v1 | KEEP_BENCHMARK | 230 / 230 | 230 |
| broad_cost_coverage_scaleout_v1 | KEEP_INFORMATIONAL | 204 / 203 | 204 |
| broad_mature_continuity_control_v1 | KEEP_BENCHMARK | 175 / 175 | 175 |
| experiment_participation_candidate_v1 | KEEP_INFORMATIONAL | 297 / 297 | 297 |
| effective_breadth_v1 | KEEP_INFORMATIONAL | 2 / 2 | 2 |
| experiment_panic_reclaim_control_v1 | KEEP_BENCHMARK | 154 / 154 | 154 |
| canonical-035ad2cf0cb0f6a5 | KEEP_BENCHMARK | 167 / 167 | 167 |
| canonical-1ef2715c090f60fb | RETIRE_DUPLICATE | 167 / 167 | 167 |
| canonical-53316326d5f1f7d5 | RETIRE_DUPLICATE | 167 / 167 | 167 |
| canonical-57d44c510448173c | RETIRE_DUPLICATE | 167 / 167 | 167 |
| canonical-8e0e2a5367a26beb | RETIRE_DUPLICATE | 167 / 167 | 167 |
| canonical-c9204a1e7a1c45f3 | RETIRE_DUPLICATE | 167 / 167 | 167 |
