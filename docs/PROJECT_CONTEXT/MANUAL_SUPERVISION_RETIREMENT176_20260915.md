# Manual supervision and negative-expectancy retirement 176 - 2026-09-15

## Observed failure

The current funding period had only six entry-capable primary-lane arms before
this review, while several recently active observer/experiment lanes were also
still consuming their independent Paper accounts. A manual run of the frozen
negative-expectancy screen found five additional arms that now satisfy every
existing retirement requirement:

- at least 30 independent settled tokens;
- at least 200U realized loss after configured Paper costs;
- negative median token PnL;
- a deterministic token-clustered 99% bootstrap interval wholly below zero;
- negative mean after deleting any one token.

The five arms had 42-327 independent tokens and -2,532.72U combined realized
PnL. Two were still primary-lane entry capable immediately before the action:
`mv_noprogress_fast_v1` (-728.64U over 327 tokens) and
`mv_portfolio_gated_v1` (-658.11U over 207 tokens). Continuing to spend their
remaining cash would add exposure without a defensible positive-expectancy
hypothesis.

## Manual action

`scripts/sync_negative_expectancy_authority.py --apply` appended the five arms
to the existing reversible authority. Runtime restart was performed manually;
no scheduler, recurring automation, funding reset or strategy mutation was
created. The effective loss-retirement overlay now contains 167 arms.

The new runtime started at `2026-09-15T14:46:19.370898Z` and preserved
`chain-meme-trader/funding-20260906-v002-final-1000`. `/health` returned HTTP
200, the runtime heartbeat advanced, Paper remained active and Live remained
disabled. The two formerly active failed arms produced zero post-start BUY or
SELL rows in the initial acceptance window. The five arms' existing positions,
SELL intents, fills and historical results remain governed by their original
contracts.

After the action the primary entry lane has four capable arms:

- `rw_quiet_reawakening_v1`
- `mv_quiet_depth_v1`
- `mv_quiet_depth_wide_v1`
- `mv_portfolio_gated2_v1`

The three mature MV arms remain net-negative, but each still has a rare
+152.74U token outcome and its 99% interval includes zero. They therefore do
not satisfy the frozen absolute-failure rule. This is the intended boundary:
retain uncertain right-tail hypotheses, stop statistically demonstrated loss,
and do not select on a favorable outlier alone.

## Gold-address coverage diagnosis

The user-supplied list contains 112 rows and 92 canonical unique addresses.
The current database resolves 76/92 (82.6%): 39 Solana, 20 Robinhood and 17
BSC. All 76 resolved identities have discovery exposure, snapshots and entry
evaluation; 23 reached a strategy cohort and 19 reached a Paper position.

The mutually exclusive funnel is:

- 16 not discovered;
- 53 evaluated but no cohort;
- 4 cohort but no position;
- 19 Paper captured.

For locally discovered cases, first-seen to first evaluation is normally fast:
median 0.657 seconds and p90 122.5 seconds. The larger defect is upstream age:
among 73 cases with a usable provider creation time, creation to local discovery
has median 2,938.5 seconds and p90 3.65 days. The 16 unmatched addresses have
no exact token, launch, market-surface, hydration or local raw evidence. Three
are Solana-shaped and in configured scope; the 13 EVM addresses cannot be
assigned to BSC, Robinhood or an unsupported chain from the address alone.

Among the 53 evaluated/no-cohort cases, recorded first reasons were primarily
historical `no_active_matching_entry_policy` (30), liquidity below the configured
floor (9), entry-family mismatch (5), absent curve liquidity (4), invalid exact
as-of evidence (4), and unknown liquidity (1). The historical no-active-policy
incident is already repaired and is not reclassified as a current failure.

The four cohort/no-position cases have explicit explanations: three Robinhood
cohorts expired while safety/next-frame evidence remained unavailable (two also
had later cash refusals), and one Solana cohort was rejected for a dangerous
upgradable-transfer-fee control. None is evidence of a missing fill.

## Next monitoring and optimization gate

The next manual review will keep discovery age, evaluated-to-cohort conversion,
security-provider availability, projected/admitted conversion, after-cost PnL,
write-off frequency and right-tail retention separate. Aggregate discovery
errors cannot attribute the 16 absent addresses to a particular source; future
source changes should first add address-bound terminal attempt evidence rather
than infer a no-pair reason from round totals.

Robinhood safety enrichment was rechecked and is already present in deployed
commit `4309448`; the remaining `UNKNOWN` cases reflect unavailable provider
facts, not the old runtime chain-routing omission. Missing evidence will not be
converted into PASS. Existing activity-conditioned 5-minute/90-minute and trend
Moonbag pairs remain below their predeclared sample gates, so this review does
not add another parameter variant or claim profitability.
