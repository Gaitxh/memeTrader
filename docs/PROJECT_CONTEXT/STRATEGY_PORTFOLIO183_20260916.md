# Strategy portfolio review and pair 183

## Full inventory review

The current effective definition contains 490 unique Paper arms. Their lifecycle
states at review time were 79 active, 183 paused by prior user controls, 85 failed
from depleted accounts, 71 failed forward-expectancy checks, 61 retired duplicates,
7 dominated in paired tests, and 4 structurally unreachable retired arms.

The arm count overstates independent evidence because many arms project the same
cohort and entry fill into separate accounts. Current-period descriptive position
PnL was negative in every large lifecycle group; it must not be read as 490
independent alpha tests. Fourteen active arms had no positions. Thirteen had no
decision or refusal at all, consistent with missing eligible frames/signals rather
than proven economic failure; they remain under observation after the shared-data
repair instead of being reactivated, duplicated, or immediately declared bad.

The most informative existing same-entry contrast was
`trajectory144_early_activity_fast_v1` versus
`trajectory144_trend_runner_v1`: 103 positions each, approximately -78.88U versus
+313.92U. Mature-entry 5-minute versus 90-minute comparisons pointed the other way,
supporting a compact entry-speed by exit-speed matrix rather than one universal
holding rule.

## Gold-dog cases

The supplied case artifact contained 19 matched canonical tokens with positions,
799 arm-position rows, and 233 distinct entry events. Only one event reached a
strict in-life, cost-adjusted MFE of at least +50%, so the cases do not support a
fitted universal gold-dog entry threshold.

That event was Solana `bruh` (`6tRotGypA5QJKwmfgGFe4yp36eNQ4Vz7m8MNNpBnpYmq`).
It was discovered at 08:56:49Z, first priced three seconds later without readable
liquidity and correctly rejected, then first received a liquidity-valid quote at
09:59:14Z. Its winning entry was still delayed another 2,947 seconds. During the
hold it reached +51.16% cost-adjusted MFE; all 15 projected arms closed positive.
This points first to data/entry latency and then to exit comparison, not hindsight
selection of one absolute feature threshold.

## New compact pair

Two independently funded Paper arms were appended at one fresh frontier. They use
the exact same existing `market_visible` entry: minimum activity/volume, prior
activity, maximum 5-minute trade-count churn, and minimum volume/liquidity turnover.
They add no API requests.

- `core183_market_fast5_v1`: five-minute capital-recycling control, -15% hard stop,
  +20% activation / 10% trailing drawdown.
- `core183_market_runner30_v1`: 30-minute runner, realized-volatility adaptive stop
  plus confirmed-decay package, -50% terminal backstop, and at 1.20x net economic
  value sells only enough to recover principal while retaining the remainder.

This pair supplies fast-entry/fast-exit and fast-entry/slow-exit. Existing
trajectory144/169 arms supply confirmed-entry fast/runner comparisons, giving a
small four-quadrant portfolio without another parameter fanout.

## Verification and first forward result

Eighteen policy, entry-filter, principal-recovery, trend-moonbag, and registration
contract tests passed. Both arms activated at `2026-09-15T16:29:52.153909Z`, snapshot
frontier 778074 and evaluation frontier 770453, with zero pre-activation decisions
or positions. Initial accounts were 1000U each.

Within the first natural minutes, three tokens were admitted by both arms and filled
on shared next-observed quotes. The fast arm's first two positions stopped after
about 6 and 57 seconds for combined realized PnL near -7.41U; their runner twins
remained open at this checkpoint. This is direct evidence of washout behavior, but
only two terminal pairs and not a promotion or retirement sample.

## Next evaluation

Evaluate paired token-level after-cost differences, clustered by token and chain.
Inspect early hard stops for subsequent in-life recovery, runner drawdown, principal
recovery triggers, pool write-offs, and maximum hold. Do not tune from one winner or
two losses. Zero-signal active arms get one post-data-repair observation window;
those still receiving no eligible signal are retired as unreachable or repaired at
their shared feature ingress rather than left silently active.
