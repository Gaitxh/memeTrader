# ROUND 81 — The liquidity-band entry signal, and three more negative results

Date: 2026-09-12 (local) / 2026-09-12T06:50–07:05Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
Policy additions: 310 -> **312** (wave 41). Runtime reloaded 2026-09-12T14:54:06+08:00.

## 1. The liquidity band is the first entry scalar that survived falsification

Stratifying 1,262 tokens by the liquidity reported at their **first** observation (>=5 observations
in a 4h window, peak measured over the following hour — strictly point-in-time, NOT the token's
later maximum):

| first-observation liquidity | n | >=1.5x | >=2x | >=3x |
| --- | --- | --- | --- | --- |
| 0 - 1,000 | 33 | 36.4% | 30.3% | 27.3% |
| 1,000 - 5,000 | **482** | 5.0% | **3.1%** | 1.9% |
| 5,000 - 20,000 | 406 | 27.3% | 15.0% | 7.4% |
| **20,000 - 100,000** | 245 | **31.0%** | **19.2%** | **10.2%** |
| >= 100,000 | 96 | 6.2% | 3.1% | 2.1% |

Population base rate for >=2x is 11.0%. The 20k-100k band doubles **1.75x more often**, the
1k-5k band **3.6x less often** — and the 1k-5k band is where the system currently spends the most
attention (2,881 evaluation rows per hour across 800 tokens, versus 1,840 rows across 194 tokens
for 20k-100k). The >=100k band is as bad as 1k-5k for upside (3.1%).

Two cautions recorded with the result: the 0-1,000 row is a 33-token sample of brand-new pools and
is not used; and this is a token-level stratification, so it selects *which tokens* are worth
watching, not *when* to buy them.

### 1.1 Wave 41 (additive, 310 -> 312)

| arm | kind | predicate |
| --- | --- | --- |
| `alpha149_mid_band_flow_v1` | `mid_band_flow` | `20,000 <= depth <= 100,000` AND buy share >= .5 AND price not falling versus the previous frame AND depth >= 98% of the previous frame AND a previous frame exists |
| `alpha149_shallow_band_flow_v1` | `shallow_band_flow` | identical, with `1,000 <= depth < 20,000` |

Identical contracts (1U, 30 minutes, hard stop -20%, trail 30/15, max 4 concurrent), so the only
difference inside the wave is the band. Existing mechanisms are untouched.

Verified live ~6 minutes after the reload: `mid_band_flow` ready on 128 of 1,001 frames,
`shallow_band_flow` on 192; `alpha149_mid_band_flow_v1` already held 1 position and
`alpha149_shallow_band_flow_v1` 2. Unlike several earlier waves, this pair is reachable on the
first try.

### 1.2 The user's liquidity-floor question, answered

The 1,000U floor is **not** too strict for upside: below-floor tokens are not where the movers are.
The band that matters is 20k-100k, which the floor already admits. What the measurement does say is
that the system's *attention* is misallocated: it spends the most evaluation effort on the band
with the worst upside (1k-5k) and comparatively little on the best one.

## 2. Negative result: the requested early take-profit ladder would destroy value

The user asked for staged take-profit with a Moonbag (recover principal at 1.5-2x). The deployed
tiers fire at +100%/+200%/+400% and have almost never armed. Before placing an earlier tier, the
population it would target was measured (48h):

| peak reached | positions | share | realised PnL | realised / stake |
| --- | --- | --- | --- | --- |
| >= 1.30x | 763 | 18.4% | +673.9U | +29.4% |
| >= 1.50x | 461 | 11.1% | +771.3U | **+55.8%** |
| >= 2.00x | 215 | 5.2% | +585.4U | +91.2% |

For a tier that sells fraction `f` at 1.5x (net 1.44x after the 4% sell slippage) the change in
expectancy is exactly `stake * f * (0.44 - r)` where `r` is the position's realised return. With
`r = 0.558` for the >=1.5x population, **any `f > 0` is negative**, and selling 70% (the fraction
that would actually recover principal at 1.5x) costs about 8.3% of the position's stake in
expectancy on that population. It only helps the 23% of that population that ended at or below
break-even, and the 47 write-offs inside it — it is insurance whose premium exceeds the loss.

This is the third exit-side idea this session to fail its own test (after the paired exit-contract
comparison and the exit-variant families). The exit stack is not where the money is.

## 3. Negative result: the whipsaw-guarded arms show no advantage

Only five arms declare `hard_stop_grace_seconds` / `hard_stop_confirm_marks`. Over 72h they hold
96 positions at **-37.6% of stake**, against 148 positions at **-21.6%** for the closest unguarded
comparators. Their median peak is *higher* (1.27x versus 0.96x on the `merged_multi_setup` pair)
while their realised result is worse, and their median hold is far longer (102 versus 15 minutes) —
consistent with "holding through the amplitude raises the peak and lowers the result". Samples are
5-50 positions per arm, so this is a signal, not a verdict; it is recorded so that a whipsaw-guard
wave is not commissioned on the assumption that it works.

## 4. No free acquisition capacity exists

The coverage lane that is supposed to densify young pools reports, over this process's whole
lifetime: `eligible_batch` **402**, `no_spare` **402**, `selected_extra` **0**. Not one
opportunity has ever been taken. At the same time `dex_http_capacity` shows
`low_priority_deferred` 43 and `low_budget_cancellations_no_rotation` 31 against
`max_inflight` 8 with only 3 active.

So the runtime is **budget-bound, not concurrency-bound**: there are idle inflight slots that the
rate budget will not let it use. A mover watch-list therefore cannot ride hidden headroom; the
coverage gap measured in rounds 79-80 (DC-3b/DC-3c/DC-4/DC-6) is reachable only by a request-budget
decision, which the user has declined for now. This closes the "is there a free fix?" question.

## 5. Round summary

| item | verdict |
| --- | --- |
| liquidity band 20k-100k as an entry selection | **measured positive** (19.2% vs 11.0% base), wave 41 deployed and firing |
| liquidity floor too strict? | **no** — the 1k-5k band it admits is the worst for upside; the misallocation is attention, not the floor |
| early take-profit ladder (user request) | **rejected by arithmetic** — negative expectancy of `f * (0.44 - 0.558)` per stake |
| whipsaw-guarded stops | **no evidence of help** in 96 positions; peak up, result down |
| free capacity for a watch-list | **none** — 0 of 402 spare-capacity opportunities, low-priority requests cancelled for budget |
| exit variants in general | third independent negative result |

## 6. Monitoring and next iteration

1. Wave 41 is a paired, same-contract A/B. Judge it only after >=20 settled positions per side,
   with an age-controlled cohort and token matching; until then report readiness, not performance.
2. The mover-predictor analysis (separate agent, `data/research/mover_predictor_20260912.md`) is
   the input for the only remaining large lever: deciding *which* tokens deserve dense observation.
   If its held-out lift is real, the next step is a watch-list proposal with a measured request
   cost, to be put to the user as a budget decision — not implemented unilaterally.
3. Do not commission more exit variants without a paired within-opportunity result in advance.
