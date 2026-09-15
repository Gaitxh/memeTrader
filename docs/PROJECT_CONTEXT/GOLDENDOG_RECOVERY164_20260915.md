# Goldendog Recovery 164

## Observed failure

In the active Paper period, 1,470 arm-level liquidity write-offs across 295 independent
token/cohort opportunities reached a forward-recorded peak between +10% and +30% without ever
executing a take-profit or trailing exit. The user-provided goldendog address subset contains 100
such arm-level positions across 52 cohorts and 43 tokens. This is descriptive evidence from the
running high known at each instant, not a reconstruction from later ATH data.

The relevant deep goldendog parents activate trailing only at +60%. Their moonbag first tier is
+100%, while the existing keep-half principal recovery requires enough value to recover the debit
without selling more than half. None covers the observed +10% to +30% region.

## Forward experiment

`alpha149_goldendog_low_recovery20_v1` is appended at its own deployment frontier. It uses the
exact `sf_goldendog_deep_base` entry predicate and copies the stop, 300-second grace, three-mark
confirmation, liquidity veto, +60%/-30% trailing and 240-minute horizon from
`alpha149_goldendog_deep_hold_v1`.

Its only economic difference is an opt-in principal-recovery branch. On a post-entry market mark
that is `VISIBLE`, at most 15 seconds old, and temporally ordered, the full remaining position plus
already realized proceeds must be worth at least 1.20 times stake after the configured Paper sell
costs. The existing binary-search sizing then sells the minimum raw quantity whose modeled net
proceeds cover the outstanding debit. Settlement remains the only authority that can mark
principal recovered. A direct jump to missing or sub-floor liquidity produces no fictional sale.

At a 4% sell haircut, a 25 USD mark on one token with a 20 USD debit has 24 USD full net value and
the minimum recovery amount is 834/1000 raw units, leaving about 16.6% to the unchanged parent
exit. The threshold is applied to economic value rather than an uncosted displayed return.

## Decision rule

Do not promote from historical cases. Compare the challenger to its parent on shared forward
cohorts. Review after at least 50 independent paired cohorts, including at least 20 actual recovery
triggers with terminal outcomes. Report BSC and Solana separately. Pause the challenger if the
triggered paired median improvement is not positive and the clustered 95% upper bound is at most
zero, or if principal recovery succeeds on fewer than 60% of the first 20 trigger attempts.

The experiment is Paper-only, adds no requests, changes no existing policy or position, and never
backfills an old opportunity.
