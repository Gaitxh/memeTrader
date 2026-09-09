# Prebreakout same-pool loss memory — 92

REPLY_TO: C2C-20260909-PREBREAKOUT-LOSS-MEMORY-92
Implementation commit: 32e400d. Paper deployment/activation: 2026-09-09T10:42:34.607621Z.

## Contract
New independent `prebreakout_loss_memory_v1`, 5U/max4, copies the current effective revised `prebreakout_net_accumulation_v1` signal and exits. Only after that signal is eligible, reject `prior_closed_core_loss_same_pool` if a same-token, exact-pool core `resource_age_rate_candidate_v1` position was closed/written_off with negative realized PnL strictly before signal time. No date, chain or gap threshold. Solana pool identity remains case-sensitive. Prior open positions, wins, other pools and later losses do not veto. Existing common safety91 and strictly later frame execution remain in force. No additional market requests or funded control.

Lookup uses existing positions_token_history index (definition_version/token/arm) and cohort primary key; production EXPLAIN confirms no positions table scan. Prior registered periods are included, without rewriting them.

## Validation and deployment
9 targeted tests passed: exact pool, different pool, win/loss/open/writeoff, later close, case-sensitive identity, idempotent registration, parent policy preservation and next-frame execution. Diff check passed. Existing Paper launcher loaded the change; /health running, /api/live Paper-only/live_locked=true.
Activation snapshot2320398/evaluation1515827; behavior hash e7894116cf6a8008.
All old rows in seven contract/funding tables compare exactly unchanged. Policy additions288->289; six other tables unchanged. Original strategy remains available; checkpoint90A remains paused. No reset/backfill or historical PnL mutation.

Acceptance snapshot: data/research/system92/acceptance.json; before rows: before_contracts.json. At10:42:57Z new candidate0 positions/0 admissions, thus INSUFFICIENT_NATURAL_EVIDENCE. Startup performance sample is too short to claim sustained latency improvement; this change adds only an indexed signal-eligible lookup.

## Interpretation
The supplied historical101/10-loss diagnostic is hypothesis-generating only, not an independently established Alpha result. Its top1/top3 sensitivity and positive exception forbid promotion claims. Compare future candidate selections against existing original control; do not retrospectively recreate entries. Safety91 remains deployed. Withdrawn checkpoint90A is not reactivated.
