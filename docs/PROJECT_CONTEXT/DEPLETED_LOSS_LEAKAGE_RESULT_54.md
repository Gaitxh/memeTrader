# Depleted loss leakage54 RESULT

REPLY_TO: C2C-20260909-DEPLETED-LOSS-LEAKAGE-54

Current-period ledger independently verified. Applied existing dynamic convergence control to exact5 arms, no replacement/no runtime restart. No positions/trades/registration/activation/policy/funding/capital mutations in control transaction; SHA256 before/after equal. Open exits remain governed by existing exit policies, Live=false/Paper-only.

| Arm | Terminals | Realized U |
|---|---:|---:|
|creator_early_holder_distribution_v1|32|-58.058632|
|experiment_pullback_reclaim_candidate_v1|236|-230.706263|
|serial_conditional_runner_v1|305|-981.585883|
|staged_probe_5u_conditional_15u_shadow_v1|1135|-995.741633|
|staged_probe_5u_only_control_v1|1135|-995.741633|

Both staged arms cash4.258367U; serial cash18.414117U. No formal paired_entry_group/size for these5. Both staged5U siblings paused together;20U sibling already retired. Source_arm_ids are provenance, not a hidden shared-fill enrollment requirement; do not pause source parents or unrelated controls. Group closure check passed, no accounting-contamination/void rows for selected arms.

## Why missed earlier

ACTIVE_LOSS_LEAKAGE_RESULT_48.md explicitly deferred staged5U pair, serial and pullback candidate because API total valuation was None. This was an overly restrictive screen for realized loss: unknown open valuation does not erase already established terminal losses. Current check uses clean closed/written_off ledger PnL and unique-token count>=30. Creator had29 terminals at48, below that gate; now32 qualifies. No claim of a scheduler defect or retroactive proof that all earlier decisions were wrong. No automatic loss-retuning/retirement scheduler introduced.

## Evaluation acceptance

Effective definition applies controls AFTER dynamic additions. observe_chain_meme_pattern filters entry_paused before isolated cohort/pattern rule evaluation (store.py around26900); main snapshot evaluation filters likewise. Existing queued-BUY activity guard remains. This stops per-arm entry work while shared discovery and existing-position exits continue.

Applied 2026-09-09T03:43:09.262657+00:00; checked 2026-09-09T03:44:12.081624Z. Evaluation frontier 1365025→1365463: 438 new evaluations, 326 observer rows, zero outcomes for EACH paused arm; API all5 entry_paused=true and zero post-cutoff new positions. This is a bounded~63s acceptance, not an indefinite monitoring guarantee.

Two existing targeted regression tests PASS: queued BUY blocked without contract changes; depleted account retains final accounting snapshot while stopping idle snapshots. Scoped diff check PASS. Immutable transaction digest d99488e04fe1f45ed52958c867936599794afc4849f3769448a65dbf96a813bd.

Artifacts data/research/convergence54/before.json, preview.json, applied.json, evaluation_frontier.json, postcheck.json. Script scripts/apply_convergence54.py is scoped/idempotent and validates current period/clean loss sample/paired closure before mutation. All unrelated ongoing research unchanged.
