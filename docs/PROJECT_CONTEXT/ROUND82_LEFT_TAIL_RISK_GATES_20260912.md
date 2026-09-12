# ROUND 82 — The left tail is the loss, not the exits: pool-death risk gates (wave 42)

Date: 2026-09-12 (local) / 2026-09-12T07:03–07:15Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
Policy additions: 312 -> **314** (wave 42). Runtime reloaded 2026-09-12T15:05:46+08:00.

## 1. The "could not hold the winner" hypothesis is now refuted by a clean counterfactual

Every previous test of "hold longer" was confounded: observed hold-time buckets are produced by the
exit rule itself (the hard stop is what ends losers fast), which the independent exit review also
flagged. A **fixed-horizon counterfactual** avoids that entirely. For 400 positions opened in the
last 12 hours, take the token's own recorded price at entry + H and compare:

| horizon | n | p25 | p50 | p75 | p90 | mean | net of friction > 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| +5 min | 395 | 0.947 | 1.004 | 1.062 | 1.229 | 0.941 | 22.3% |
| +15 min | 357 | 0.899 | 1.006 | 1.064 | 1.297 | 0.917 | 24.9% |
| +30 min | 317 | 0.825 | 1.008 | 1.073 | 1.344 | 0.927 | 24.9% |
| +60 min | 285 | 0.620 | 1.012 | 1.136 | 1.396 | 0.930 | 33.3% |
| +120 min | 214 | 0.015 | 0.910 | 1.128 | 1.388 | 0.841 | 31.8% |

Paired against what those same positions actually realised:

| horizon | n | mean (hold-H minus actual) | hold-H better in |
| --- | --- | --- | --- |
| +30 min | 315 | **-0.065** | 43.5% |
| +60 min | 285 | **-0.074** | 43.9% |

**Holding to a fixed horizon is worse than what the system already did.** The median token is flat
at every horizon (p50 ~1.00-1.01) while the left tail deepens (p25 0.62 at 60 minutes, 0.015 at
120). The loss is the left tail, not the exits.

Supporting arithmetic over the same 6 hours: 1,678 settled positions, 4,717.8U of stake,
**-1,255.7U realised**, of which the round-trip friction implied by that turnover is **393.2U
(31%)**. Mean hold 16.1 minutes.

## 2. Two pool-death risk features replicate

Over 24h, 3,261 settled positions of which 360 were written off:

| grouping | pool-death rate |
| --- | --- |
| **chain** bsc | **30.4%** (275/906) |
| chain solana | 3.9% (85/2,171) |
| chain robinhood | 0.0% (0/184) |
| **entry liquidity 1,000-5,000** | 0.0% (0/70) |
| entry liquidity 5,000-20,000 | 14.1% (82/582) |
| entry liquidity 20,000-100,000 | 18.2% (273/1,499) |
| **entry liquidity >= 100,000** | **0.5%** (5/1,088) |
| BSC 20k-100k, entry buy share < 0.50 | **0.0%** (0/69) |
| BSC 20k-100k, entry buy share >= 0.70 | **41.3%** (78/189) |

Both the chain split (30.4% versus 3.9%) and the deep-pool result (0.5%) reproduce measurements
taken a day earlier on this database, so they are treated as replicated rather than as one day's
noise.

**Rejected by the controls:** entry turnover. Pooled, dead positions show 5.9x the median turnover
of survivors (0.542 versus 0.092) — but inside BSC the death rate is flat across turnover
(22.0 / 33.3 / 34.6 / 30.7 / 32.3%) and inside the 20k-100k band it is non-monotone
(27.0 / 22.1 / 4.5 / 14.2 / 19.2%). The pooled difference was chain composition. This is the
second time this session that a pooled entry effect dissolved under the controls, and the second
time it was not built. (Inside Solana alone there is one residual signal worth watching:
turnover >= 0.8 dies at 11.9% against 0.0% for the 1,436 lower-turnover Solana positions.)

## 3. Wave 42: two arms aimed at the left tail (312 -> 314)

| arm | kind | gate |
| --- | --- | --- |
| `alpha149_deep_pool_flow_v1` | `deep_pool_flow` | the wave-41 flow carrier AND depth >= 100,000U |
| `alpha149_nonbsc_flow_v1` | `nonbsc_flow` | the same carrier AND chain != bsc (an absent chain is NOT treated as non-BSC) |

Both keep the measured protective conditions (buy share >= .5, price not falling versus the previous
frame, depth holding at >= 98%, a previous frame must exist) and the same contract as wave 41
(1U, 30 minutes, hard stop -20%, trail 30/15, max 4 concurrent), so all four arms of waves 41-42
are one experiment with two factors: liquidity band and chain.

Live ~7 minutes after the reload (1,323 frames): `deep_pool_flow` ready on **336** frames,
`nonbsc_flow` on **502**, `mid_band_flow` on 142, `shallow_band_flow` on 304; positions 2 / 4 / 2 / 4
with matching decisions. All four are reachable and trading.

One correction to an earlier conclusion: round 79 recorded the deep-liquidity band as unreachable.
That was true of the *combined* predicate it tested (age band + FDV ratio + not falling + depth
holding at >= 100k). The band itself is common — 25.4% of frames carry depth >= 100k — and
reachable with the simpler carrier used here.

## 4. Funnel status (round 80 baseline, unchanged)

Discovery 6,386 tokens/h -> snapshots 2,342 -> evaluations 2,378 -> ready arm 256 (10.8%) ->
admitted 13 (5.1% of ready) -> opened 8 tokens / 192 positions. The ready-to-admitted gap remains
the 60-second double-evaluation rule against a p50 89.8-second refresh cadence, and round 81
established that there is no free acquisition capacity to close it (0 of 402 spare-capacity
opportunities; low-priority requests being cancelled for budget with idle inflight slots).

## 5. Monitoring plan

1. Waves 41-42 form a 2x2 (band x chain) on one carrier with identical contracts. Judge them
   together with `scripts/paired_arm_ab.py`, which refuses a verdict below 20 settled per side and
   20 paired cohorts, reports token-clustered intervals, and adds the leave-one-token-out check.
2. Primary metric for wave 42 is **pool-death rate and loss per position**, not return: these arms
   exist to test whether avoiding BSC and shallow pools removes the left tail. Report both the
   death rate and the realised PnL so a lower death rate that also lowers upside is visible.
3. Do not add further entry scalars without a within-token or within-chain control. Two candidates
   have already been falsified this way (turnover twice, hold duration).
