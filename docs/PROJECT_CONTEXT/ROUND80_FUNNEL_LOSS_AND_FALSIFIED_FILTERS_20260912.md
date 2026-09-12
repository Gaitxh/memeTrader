# ROUND 80 — Funnel attribution, loss decomposition, and two falsified entry hypotheses

Date: 2026-09-12 (local) / 2026-09-12T06:35–07:00Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
No source change this round: every claim below is a measurement, and two candidate fixes were
rejected because the measurement did not support them.

## 1. The whole chain, one hour, per-step rates

All windows use `julianday()`; all large tables are bounded by an id frontier.

| step | rows | distinct tokens |
| --- | --- | --- |
| 1 discovery exposures | 19,124 | 6,386 (1,387 `new_token` rows) |
| 2 snapshots | 11,251 | 2,342 (9,576 rows / 1,251 tokens above the 1000U floor; 1,116 tokens with >=2 observations) |
| 3 entry evaluations | 11,246 | 2,378 |
| 4 alpha149 engine frames | 1,638 primary + 272 wide | 85 primary pools + 178 wide pools |
| 5 evaluations carrying a ready arm | 356 | **256** |
| 6 admitted decisions | 270 | **13** |
| 7 positions opened | 192 | **8** (486U stake) |

Step-by-step conversion (token level): discovery → snapshot 36.7%; snapshot → evaluation ~100%;
evaluation → ready arm **10.8%**; ready → admitted **5.1%**; admitted → opened 8/13; and
192 positions / 8 tokens = **24 positions per token**.

Evaluation reasons: `cohort_observation` 3,988 rows/991 tokens, `pattern_observation` 3,268/324,
`no_active_matching_entry_policy` 2,347/1,176, `entry_pool_liquidity_unknown` 770/717,
`entry_pool_liquidity_below_configured_floor` 549/292, `invalid_exact_asof_market_snapshot` 318/318.

## 2. Where the ready-to-admitted step loses 95% of its candidates (DC-6)

The cohort admission rule needs, for the same token **and pair**: the arm in the PREVIOUS
evaluation's `ready_arm_ids` with the same event key, the signal still inside its 60-second
window, and `0 < current.observed_at - previous.observed_at <= 60`. Two evaluations of the same
pool inside 60 seconds.

Attribution over the 255 pools that had a ready arm in the hour:

| first blocker | pools | share |
| --- | --- | --- |
| gap to the next same-pool evaluation over 60s | 129 | 50.6% |
| no later evaluation of that pool at all | 101 | 39.6% |
| signal not carried into the next evaluation | 16 | 6.3% |
| **converted** | **9** | **3.5%** |

Supporting cadence facts (same hour):

* evaluations per ready pool: p10 4, **p50 6**, p90 12 — one evaluation per ten minutes;
* gap from a ready row to the next evaluation of the same pool: p10 1.5s, **p50 59.1s**, p90 91.3s,
  only **42.4%** inside 60s;
* per-token refresh cadence over all 2,390 observed tokens, ignoring <=2s duplicate rows:
  **p50 89.8s**, only **17.5%** of tokens refreshed at <=60s;
* observations per token: p50 **1**, 46.0% have >=2, 16.6% have >=5.

So the entry layer's confirmation window is satisfied by roughly one sixth of the observed
surface. This is the same dense-observation ceiling measured in round 79 (DC-3b/DC-4), now
attributed at the token level and shown to be the direct cause of the 5.1% ready-to-admitted rate.

## 3. Retraction: the acquisition budget is NOT 30% wasted

A first pass counted 3,365 snapshot rows (30.0%) sitting within 2 seconds of another row of the
same token and read that as duplicated requests. **That was wrong.** Checking the composition:

* 64.3% of snapshot rows carry the `strategy-observer:` prefix — these are the isolated
  evaluation copies that `observe_chained_meme_pattern` writes for every evaluated observation,
  by design, from ONE upstream receipt;
* the dominant duplicate groups are `geckoterminal + strategy-observer:geckoterminal` (1,175) and
  `strategy-observer:dexscreener + strategy-observer:dexscreener` (1,139);
* **2,817 of 2,906 groups print the identical price**, i.e. they are the same receipt, not
  independent data.

No request is wasted. The real number in that measurement is the refresh cadence in section 2.

## 4. Loss decomposition: 58% friction, 42% gross selection

Closed positions opened in the last 24h: 3,223, stake 9,632U.

| component | USD | share of stake |
| --- | --- | --- |
| realized PnL | **-1,392.7** | **-14.46%** |
| friction (8.33% round trip) | 802.7 | 8.33% |
| gross before friction | **-590.0** | **-6.13%** |

Friction explains **58%** of the loss and gross selection **42%**. Only **37.2%** of closed
positions ever printed above `entry * (1 + friction)` — 63% never covered costs at their peak.

Token concentration: of the 60 tokens with >=10 closed positions, only **13 were profitable**;
p10 -82.8U, p50 -18.4U, p90 +19.0U. Every one of the five worst tokens was held by 34-56 arms
simultaneously (one token: 56 positions from 56 different arms).

## 5. The exit contracts, compared on identical opportunities

The alpha149 exit arms ride the same frozen entry opportunity as their carrier, so they can be
compared within a cohort. 138 cohorts contained >=2 rival exit arms; 32 exit arms appear.

| exit contract | n | sum PnL | win% | mean hold |
| --- | --- | --- | --- | --- |
| `alpha149_plateau_stall_exit_v1` | 57 | **+7.8U** | 26.3 | 3.2 min |
| `alpha149_time_decay_stop_v1` | 38 | -12.9U | 21.1 | 20.2 min |
| `alpha149_early_stop_only_v1` | 36 | -13.5U | 22.2 | 21.7 min |
| `alpha149_profit_decay_exit_v1` | 56 | -23.4U | 25.0 | 4.6 min |
| `alpha149_trend_break_exit_v1` | 26 | -24.4U | 19.2 | 8.6 min |
| `alpha149_flat_dead_exit_v1` | 52 | -34.7U | 25.0 | 8.2 min |
| `alpha149_depth_decay_exit_v1` | 48 | -36.4U | 20.8 | 10.2 min |
| `alpha149_liquidity_shock_exit_v1` | 55 | -39.5U | 23.6 | 9.9 min |

**27 of the 28 contracts lose on the same opportunities.** The one positive result is carried by a
single trade: `plateau_stall` sums +7.75U over 57 positions, but **-10.23U without its best trade
(+17.98U)**. Head-to-head inside the same cohorts it beats each rival on the MEAN (+0.54 to +0.81U
per position) while winning only 26-37% of the pairs — a right-tail profile, not a better rule.

Conclusion: exit choice moves per-position PnL by roughly 0.8U on a 5U stake (about 2x friction);
it is real but it is **not** the dominant term. The evidence does not support "we exit too early
and should hold longer" — if anything the fastest stall exit has the best mean.

## 6. Audit of the mark guard: not violated since it was deployed

The 02:27:39Z case looked like a repeat of the dust-mark defect: one token, one pair, a mark at
`price 2.275e-06 / liquidity 2,274` arriving 14 seconds after the same pool printed
`0.08278 / 769,591` (a 36,000x price and 338x depth collapse), and six positions closed at
-100% two seconds later. An offline replay of the guard's own rule (price <= 10% of the median of
the previous 5 VISIBLE marks, liquidity <= 25% of their median) on all 864 hard stops of the day
found **45 violating fills** — all of them in the 01:00Z and 02:00Z hours, none after 06:00Z.

`git log -S _mark_is_plausible` dates the guard to **10:38 local (02:38Z)** — eleven minutes AFTER
the last violating fill. Every violation predates the guard; there are none since. The guard is
working, and the 02:27:39Z case is precisely the defect it was written for.

## 7. Falsified hypothesis: low turnover at entry

Discrimination found winning tokens entered at lower liquidity (34,274 vs 59,082 median), lower
market cap (102k vs 217k) and **2.2x higher 5-minute volume** — i.e. higher turnover
(`volume_5m / liquidity`). Pooled over 3,210 positions the effect looked large:

| turnover bucket | n | mean PnL | PnL / stake |
| --- | --- | --- | --- |
| < 0.05 | 1,288 | **-0.173** | **-5.79%** |
| 0.05-0.15 | 362 | -0.921 | -28.50% |
| 0.15-0.30 | 143 | -0.542 | -19.72% |
| 0.30-0.60 | 340 | -0.612 | -20.21% |
| 0.60-1.50 | 410 | -0.370 | -12.74% |
| >= 1.50 | 667 | -0.604 | -21.08% |

The same split inside individual arms was positive in **37 of 39 arms** (median edge +23.3 pp).
But pairing within the token destroys it: across the 19 tokens with >=2 quiet and >=2 busy
positions, the pooled **within-token** difference is **-0.009** (median +0.008), quiet better in
**10 of 19** tokens. The apparent edge is a token-selection artifact — a turnover filter would
reweight which tokens get traded, not improve timing. **No arms were added for it.**

## 7b. The opportunity ceiling: the movers exist and the system enters 4.8% of them

The metric that decides everything else. Over the last 5 hours, 52,765 snapshots covered 10,028
distinct tokens; 1,712 of them have >=5 observations, so their first hour is actually measurable.
Measuring `max(price within 1h of first observation) / first price`:

| threshold | tokens | share of measurable | entered by the system | share of qualifying tokens entered |
| --- | --- | --- | --- | --- |
| >= 1.5x | 309 | 18.0% | 12 | 3.9% |
| >= 2x | 189 | 11.0% | 9 | **4.8%** |
| >= 3x | 100 | 5.8% | 6 | 6.0% |
| >= 5x | 49 | 2.9% | 3 | 6.1% |

The system entered 37 distinct tokens in that window. 9 of them (24.3%) reached 2x, against an
11.0% base rate — so the entry machinery **does** carry information (about 2.2x lift) — but it
covers only **4.8%** of the tokens that actually doubled, and 75.7% of its entries never reach 2x.

This matches the peak-capture measurement on the other side: pooled by entry mechanism over 48h,
every mechanism with a usable sample has a **median peak of 0.96-1.14x stake**, and only 3.8-6.2%
of positions ever reach 2x stake. So the binding constraint is not the exit rule and not a single
entry-time scalar; it is that the system almost never holds a token while it moves, because it
observes it 6 times an hour (section 2) and requires two observations inside 60 seconds.

An independent exit review (`data/research/exit_review_20260912.md`, token-clustered 90% CIs,
design effect ~4.1x) reaches the same place from the other direction: hard stop -34.97% ROI with
1.5% win rate, trailing exit +29.37% with 86.2%, every one of the 20 named exit-variant groups
individually uninterpretable at 2-57 positions, and **64.5% of hard-stop dollars spent on
positions that never rose above 1.0x at all**. The median position peaks at 1.08x entry and only
6.6% ever reach 2x.

## 8. What this round says to do next

1. **Nothing in the exit layer is the dominant term** (section 5) and **friction is 58%** of the
   realised loss (section 4). The one lever with a large, quantified effect that is currently
   untouched is the *number and selection of entries*, which the add-only constraint leaves to new
   arms and to the user's decisions on request budget and the same-token cap.
2. The ready→admitted step (section 2) needs either more observation density (a request-budget
   decision the user has declined) or a confirmation rule that tolerates the ~90s real cadence
   (a strict-timing rule this project does not loosen to create trades).
3. Both candidate static filters tested this round (turnover, and by extension any single
   entry-time scalar) failed the within-token test. Any future filter proposal must report the
   within-token paired result before it is trusted.
4. Monitoring plan: re-run the token-level funnel (section 1) and the guard audit (section 6)
   after each deployment; treat "N violating fills after the guard commit" as the regression test
   for the mark guard.
'''
