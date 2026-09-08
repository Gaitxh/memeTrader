# Convergence37: expanded new-entry pause

REPLY_TO: C2C-20260909-STRATEGY-CONVERGENCE-EXPAND-37. Applied 2026-09-08T18:48:23.912071+00:00. No restart/Live/reset/account funding/history change.

## Criteria and scope

41 arms passed: >=100 independent terminal Tokens; total costed realized loss<=-200U; mean terminal PnL<=-1U; at least one entry in frozen70m window; >=30 terminals opened after2026-09-08T08:03Z with negative aggregate PnL; zero contamination and void rows. Pair membership closure enforced. Absence of contamination records is not proof of no engineering bias; post-P0 persistence strengthens a resource-conservation pause, not a universal strategy rejection. Arm totals are correlated and must not be summed as independent evidence.

Plus both profit-lock arms paused together:46 same-fill terminal Token pairs delta-24.046350U. Original trailing60 retained.58 trailing/probation same-fill terminals have equal PnL and close reason, but policies differ and paired_entry_size3 means pausing probation alone blocks retained trailing enrollment. Keep that complete group; defer representative-only membership migration rather than silently altering contract.

## Exact newly paused list

| Arm | Terminals | Independent terminal tokens | Realized PnL U |
|---|---:|---:|---:|
| canonical-0ad93cd8a7bec9ec | 127 | 116 | -868.423788 |
| canonical-0c198e6aa30fa049 | 130 | 121 | -853.993450 |
| canonical-10af25fd9780e2af | 127 | 116 | -868.423788 |
| canonical-3733dc40ac3c74ea | 130 | 121 | -853.993450 |
| canonical-39063fa299ee2cfd | 130 | 121 | -853.993450 |
| canonical-5054a25aae97fdf9 | 156 | 137 | -639.436138 |
| canonical-627c3b1e3fc4157d | 156 | 137 | -639.436138 |
| canonical-6423ca6248abf0f9 | 130 | 121 | -853.993450 |
| canonical-65e78965552bd91b | 127 | 116 | -868.423788 |
| canonical-69be52c97c1c686d | 156 | 137 | -639.436138 |
| canonical-7c86e5fc9e55178e | 156 | 137 | -639.436138 |
| canonical-8eed440ae6e40cdf | 130 | 121 | -853.993450 |
| canonical-91e44b09867ae22e | 127 | 116 | -868.423788 |
| canonical-9b8c8540532b6db2 | 156 | 137 | -639.436138 |
| canonical-a7ca496301c23662 | 127 | 116 | -868.423788 |
| canonical-aa3ecee6b712fc53 | 130 | 121 | -853.993450 |
| canonical-adc90ff111d03016 | 156 | 137 | -639.436138 |
| canonical-c2f29f5b78e5a3a9 | 130 | 121 | -853.993450 |
| canonical-d69a266410f4ef7a | 127 | 116 | -868.423788 |
| canonical-db22c376fcd22466 | 130 | 121 | -853.993450 |
| canonical-e87e33896472940a | 127 | 116 | -868.423788 |
| canonical-e8ad7db7c6a6386c | 156 | 137 | -639.436138 |
| canonical-eb1795742aed4576 | 127 | 116 | -868.423788 |
| canonical-ecc266d212b9d0ef | 156 | 137 | -639.436138 |
| capital_velocity_v1 | 158 | 158 | -492.049350 |
| dex-successor-025-2509c2f13f40a238 | 126 | 116 | -879.948705 |
| dex-successor-069-88446f2e2831bb0d | 126 | 116 | -879.948705 |
| early_impulse_profit_lock_40_v1 | 46 | 46 | -10.179076 |
| early_impulse_profit_lock_control_v1 | 46 | 46 | 13.867274 |
| executable_recovery_decay_v1 | 248 | 248 | -700.244669 |
| experiment_migration_candidate_v1 | 328 | 328 | -816.778516 |
| experiment_migration_control_v1 | 347 | 347 | -883.662804 |
| experiment_panic_reclaim_candidate_v1 | 285 | 285 | -712.738495 |
| experiment_panic_reclaim_control_v1 | 347 | 347 | -664.261973 |
| experiment_support_risk_candidate_v1 | 183 | 183 | -432.921097 |
| experiment_support_risk_control_v1 | 183 | 183 | -457.799619 |
| paired_vault_hazard_candidate_v1 | 248 | 248 | -690.080847 |
| paired_vault_hazard_control_v1 | 248 | 248 | -691.583118 |
| round2_chase_candidate_v1 | 422 | 422 | -558.557973 |
| round2_chase_control_v1 | 534 | 534 | -706.310672 |
| round2_giveback_duration_candidate_v1 | 539 | 539 | -718.104318 |
| round2_giveback_duration_control_v1 | 539 | 539 | -713.514475 |
| vault_hazard_v1 | 248 | 248 | -695.438673 |

## Keep/defer and static duplicates

Complete machine-readable per-policy FREEZE/KEEP/DEFER/PREVIOUS_CONTROL lists with reasons: data/research/strategy_convergence_20260909/expand37/disposition.json. No-position policies are included, not silently omitted.

KEEP list: resource_age_rate_candidate_v1, archive_drift_v1, archive_plateau_v1, early_impulse_control_15m_v1, early_impulse_trailing_60m_v1, early_impulse_probation_60m_v1.

Static stored behavior-hash groups: 18. See disposition.json. Profit-lock control and original trailing60 share a hash; duplicate control enrollment ends with the failed paired treatment. Other hash sharing is not automatically safe for common evaluation: independent activation/frontier/capacity/state and paired membership must remain authoritative. No new evaluation-cache implementation in this change.

## Evidence and validation

evidence.json: frozen read-only current-period sweep and complete policies/group memberships; paired.json: exact nonempty source_entry_fill_id comparisons; applied.json: before/after convergence control and same-transaction unchanged ledger/registration/funding/policy digest. No schema initialization. Existing pause/exits paths independently reviewed; narrow existing pause regression previously passed in33 and unchanged. This script dry-run, actual transactional assertions and Python syntax validation passed. Runtime progress/new-entry follow-up below.

Acceptance: health ok/runtime running; evaluation frontier1194999 at2026-09-08T18:49:41Z. No new positions after pause cutoff in all43 selected arms;162 existing open positions remain. See acceptance.json. The diagnostic MAX(timestamp) query was slower than expected and completed before cancellation; do not reuse it in runtime/UI or repeat it. Prefer ORDER BY id DESC LIMIT1 for future frontier reads. No production restart occurred.
