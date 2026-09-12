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

## 2. Pool-death risk features, measured at the TOKEN level

Position-level write-off rates are inflated by crowding: one dying pool carries 40+ arms, so a
"30% write-off rate" can be 20 tokens. The correct unit is the token, and the earlier numbers in
this section were re-done at that unit before the wave was justified. Over 24h there were **144
tokens traded and 22 tokens with at least one write-off — a base rate of 15.3%**.

| gate | tokens | dead | token-level death rate |
| --- | --- | --- | --- |
| **chain = bsc** | 47 | 19 | **40.4%** |
| chain = solana | 88 | 3 | 3.4% |
| chain = robinhood | 9 | 0 | 0.0% |
| entry depth < 5,000 | 9 | 0 | 0.0% |
| entry depth 5,000-20,000 | 28 | 9 | 32.1% |
| entry depth 20,000-100,000 | 59 | 12 | 20.3% |
| **entry depth >= 100,000** | 26 | 1 | **3.8%** |
| **non-bsc AND depth >= 100,000** | 24 | 1 | **4.2%** |
| entry buy share < 0.50 | 12 | 2 | 16.7% |
| entry buy share >= 0.70 | 48 | 9 | 18.8% |
| bsc AND depth 20k-100k | 28 | 10 | 35.7% |

Two gates survive the token-level control: **chain = BSC (40.4% against a 15.3% base, 19 of 47
tokens)** and **entry depth >= 100k (3.8%, 1 of 26 tokens)**; together 4.2%. The BSC write-off line
alone is -790U, **54% of the whole 24h loss of -1,458.7U**.

Three claims were retracted during this round's own checks, and they are recorded because each one
would have justified an arm:

- **entry buy share as a risk gate** — position-level it looked monotone (0.0% below 0.50, 41.3%
  above 0.70 inside BSC 20k-100k), but at token level it is 16.7% versus the 15.3% base. It stays
  only as a shared protective condition inherited from wave 41, not as a validated gate.
- **Solana high-turnover deaths** — position-level 11.9% versus 0.0% looked like a large within-chain
  effect, but all 94 Solana write-off positions come from **three tokens** (48, 37 and 9 positions,
  entries at turnover 3.24, 4.97 and 0.90). At token level Solana dies at 3.4%. Dropped.
- **entry turnover as a risk gate** — pooled, dead positions show 5.9x the median turnover of
  survivors (0.542 versus 0.092), but inside BSC the death rate is flat across turnover
  (22.0 / 33.3 / 34.6 / 30.7 / 32.3%). That was chain composition, and it is the second time this
  session a pooled entry effect dissolved under controls.

## 3. Wave 42: two arms aimed at the left tail (312 -> 314)

| arm | kind | gate |
| --- | --- | --- |
| `alpha149_deep_pool_flow_v1` | `deep_pool_flow` | the wave-41 flow carrier AND depth >= 100,000U (token-level death 3.8% against a 15.3% base) |
| `alpha149_nonbsc_flow_v1` | `nonbsc_flow` | the same carrier AND chain != bsc (token-level death 40.4% for BSC against 3.4% for Solana and 0.0% for Robinhood); an absent chain is NOT treated as non-BSC |

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
