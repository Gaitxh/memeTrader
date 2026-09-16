# Sample cohort terminals and strategy inventory, 2026-09-16

## Unit and evidence boundary

This is a read-only decomposition of the frozen `goal_cases192` matched-case
index and the current effective Paper policy definition. The user-selected
addresses are retrospective clues, not an unbiased success label. A cohort is
one independently frozen opportunity; arm decisions, projected positions and
source BUYs are different denominators. No historical BUY was synthesized.

The casebook has 125 raw address lines, 94 unique literal addresses, 70
canonical matches in this funding period, 24 absent/unknown, and 40 distinct
admitted cohorts without a source BUY. These 40 terminal classifications are
mutually exclusive:

| Terminal | Cohorts | Interpretation |
|---|---:|---|
| `EXPIRED_SECURITY_OR_NEXT_FRAME` | 37 | The 90-second opportunity expired; inspect inner safety/quote receipts. |
| `REJECT` | 2 | Explicit dangerous/upgradable-transfer-fee safety rejection. |
| `SKIP_DEX_PROXY_CONTINUITY` | 1 | The opt-in Dex-proxy path lacked a prior exact-pool frame. |

Within the 37 expiries: 19 completed safety as `CHECKED_UNKNOWN` with
`allow=false`; 13 remained `WAIT_SECURITY` with no completed permission;
four received safety permission but later `BUY_AUTHORIZED_UNKNOWN` followed
by `NO_ACCOUNT_PROJECTED`; one had permission and BUY intent 1324, yet no
execution attempt before its 90-second deadline. The expiry worker itself
was not generally late: admission-to-terminal worker lag in this subset was
0.036s minimum, 0.883s median and 6.213s maximum. The missing next quote,
security completion and downstream projection are separate problems.

The four `NO_ACCOUNT_PROJECTED` examples are cohort IDs 26021, 27896,
28035 and 35023. Each arm declares `requires_distinct_trajectory_frame`.
After safety authorization, `Store._project_chain_meme_trader_market_entry`
rechecks the frozen signal against the **mutable runtime engine**'s latest
30-second trajectory state, not just the independent execution quote. Their
frozen signal-to-authorized receipt gaps were 51.329, 53.606, 55.662 and
67.837 seconds. The original in-memory 30-second state was not persisted;
we cannot recover which of the subconditions rejected each historical
attempt. We therefore cannot call all four erroneous fills or refund them.
The source arms involved also have negative full-period realized Paper totals
(age-normalized ignition -75.55U/297 closed positions; mid-deep band
-437.59U/171; score gate band -260.65U/288; size-informed flow
-162.68U/204). Promoting copies merely to increase fills has no economic
support. An independently versioned execution-receipt experiment remains a
testable option, but its old 30-second continuity requirement would change;
it is not an engineering-equivalent fix of the old contract.

An indicative as-of post-receipt 15-minute original-pool mark was available
for those four and showed +8.343%, +2.601%, -6.943%, -20.020% gross price
change. Merely subtracting 4% adverse buy and 4% adverse sell yields roughly
+0.009%, -5.292%, -14.101%, -26.172%. These are not actual Paper exits,
ignore further quote/execution failure and cannot justify historical orders.
They directly refute the assumption that converting those four into BUYs
would clearly have made money.

## All registered strategy behaviors

At the 499-arm activation frontier: 421 are paused, retired or failed
(183 `PAUSED_NEW_ENTRY`, 85 `FAILED_ACCOUNT_DEPLETED`, 81
`FAILED_FORWARD_EXPECTANCY`, 61 `RETIRED_DUPLICATE`, seven
`DOMINATED_IN_PAIRED_TEST`, four `RETIRED_UNREACHABLE_CONTRACT`). The 78
unpaused arms are 59 isolated-cohort observers, 17 pattern observers, one
native model and one main exact entry. The entire catalog spans 232 cohort,
120 pattern, 89 legacy, 42 exact-entry, 15 Dex-visible and one native lane.
Those are registration/behavior classes, not 499 independent opportunities.
Seventeen unpaused arms have no recorded decisions or positions yet,
including depth191 and newly activated activity193; that may mean sparse
natural trigger supply rather than a paused account.

Many exit variants share source BUYs. The 144 fast/runner pair shares 201
current-period source BUYs; counting its positions twice would overstate
independent sample size. Other 187/190 runner comparisons similarly overlap.
The core183 pair shares 154 source BUYs and both show failed full-period
forward expectancy (approximately -443.78U and -972.43U projected realized).
These observations argue for preserving failures and testing distinct
economic mechanisms, not reviving every retired strategy to improve page
trade counts.

## Next executable decisions

1. For new admissions, distinguish security unknown, no next original-pool
   quote, post-safety trajectory veto, cash/risk veto and successful projection
   using the existing cohort key. The Pump retry194 fix addresses one
   measured first-quote source gap only; it does not bypass security.
2. Keep old negative contracts and their historical exits intact. Let
   depth191 and activity193 produce natural post-activation signals and fills;
   evaluate net cost, writeoffs and independent tokens before revising.
3. If the mutable post-safety trajectory gate remains a material source of
   missed **otherwise safe and executable** opportunities, append one new
   versioned Paper arm whose only difference is receipt-based confirmation.
   Do not alter old strategy hashes, refill historical cohorts or assume
   that a larger fill count is profitable.

Source: current SQLite tables `chain_meme_trader_v6_cohorts`,
`chain_meme_cohort_enrollment_claims`, `chain_meme_pattern_evidence`,
`chain_meme_trader_positions`, `chain_meme_trader_policy_additions`, and the
frozen `data/research/goal_cases192` casebook. Long-horizon economic effects
of either new arm and the final Pump retry version are still unknown.
