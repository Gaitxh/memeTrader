# Goldendog fresh control 167 (2026-09-15)

## Diagnosis

`alpha149_goldendog_low_recovery20_v1` was correctly deployed as a forward-only principal
recovery challenger, but its declared parent control was no longer a viable experiment control.
The old `alpha149_goldendog_deep_hold_v1` account had only 42.4747U cash after losing 957.5253U
over 54 independent tokens. At the ordinary 20U stake it could fund at most two more entries, so
the declared 50 paired-cohort decision threshold was structurally unreachable.

At the time of diagnosis, the challenger and old parent had zero decisions after the challenger's
`2026-09-15T11:27:14.115258Z` frontier. Historical parent outcomes were not imported into the new
comparison.

## Change

Added `alpha149_goldendog_low_recovery20_control_v1` as one fresh Paper control. It clones the old
parent's point-in-time entry predicate and every exit field, but deliberately does not enable
`minimum_net_debit_after_economic_floor/v4`. The challenger remains the only arm that may recover
principal when fresh, visible net economic value reaches 1.20 times stake.

The registration remains append-only and idempotent. Existing installations add only the missing
control; a fresh test store adds control and challenger with the same activation timestamp. No
existing policy, position, fill, funding record or historical result is modified.

## Deployment receipt

- Runtime start: `2026-09-15T11:52:30.000639Z`.
- Funding version unchanged: `chain-meme-trader/funding-20260906-v002-final-1000`.
- Control addition id 359, activated `2026-09-15T11:52:27.576213Z` at snapshot 731562 and
  evaluation 724530.
- Control cash: 1000U; principal-recovery fields absent.
- Challenger cash: 1000U; recovery contract `minimum_net_debit_after_economic_floor/v4`, multiple
  1.20.
- Both arms: zero pre-frontier decisions, zero current decisions, zero positions.
- Policy count: 486. Paper runtime and Web APIs are healthy; Live remains disabled.
- Focused Goldendog, recovery arithmetic, Store and Alpha149 tests: 68 passed.

## Forward decision rule

Only compare cohorts occurring after the later control frontier above. Require at least 50
independent same-cohort pairs and at least 20 challenger recovery triggers that reach a terminal
outcome, with BSC and Solana reported separately. Pause the challenger if its trigger-sample
median improvement is non-positive with token-clustered 95% upper bound at or below zero, or if
principal recovery succeeds in fewer than 60% of the first 20 triggers. The control exists only
for this bounded comparison and must not be promoted as a profitable strategy.
