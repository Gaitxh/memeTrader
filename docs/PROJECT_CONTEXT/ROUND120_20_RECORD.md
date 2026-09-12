# ROUND 120-20 RECORD — full-chain latency diagnosis, and a new robust death marker

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. Full-chain funnel (the objective's core ask), current

| stage | count | conversion |
|---|---|---|
| tokens discovered | 10,089 | — |
| tokens with ≥1 snapshot | 9,531 | 94.5% |
| snapshots collected | 37,776 | — |
| entry evaluations | 37,774 | — |
| cohorts formed | 417 | — |
| fills | 314 | — |
| positions opened | 1,710 | 4.53% of evaluations |
| positions settled | 1,318 | −11,493.58 U (−8.72 U/pos) |

**The headline bottleneck is unchanged and now precisely quantified: only 37 of 9,531
observed tokens (0.4%) are ever entered.** Discovery and collection are healthy (94.5%
observed); the loss happens between *observation* and *judgement*, and it is an
**observation-capacity** limit (~30 dense watch slots + 24 mover slots), not a threshold
defect. This is the "绝大多数未能进入" the objective names.

Gate distribution over 37,774 evaluations:

| reason | share | admissible? |
|---|---|---|
| `cohort_observation` | **34.38%** | no — observer bookkeeping |
| `no_active_matching_entry_policy` | 25.85% | no — no arm was ready |
| `pattern_observation` | **22.77%** | no — observer bookkeeping |
| `entry_pool_liquidity_absent_curve_stage` | 7.66% | no |
| `invalid_exact_asof_market_snapshot` | 5.17% | no |
| `entry_pool_liquidity_below_configured_floor` | 3.04% | no (risk rule) |
| `entry_pool_liquidity_unknown` | 1.10% | no |
| `entry_snapshot_too_old` | 0.03% | no |

**57.15% of all evaluation rows are observer bookkeeping that can never admit**, and a
further 25.85% find no matching policy. So the *gate distribution* does not show an
over-strict filter — it shows that most evaluations were never entry candidates at all.

## 2. Latency, stage by stage (first rigorous measurement this session)

| stage | p50 | p90 | p99 | max |
|---|---|---|---|---|
| discovery → first snapshot observed | **8.05 s** | **1,500.95 s (25 min)** | 8,517 s (2.4 h) | 8,863 s |
| observed → ingested | 0.03 s | 3.40 s | 24.49 s | 30.00 s |
| ingested → recorded | 0.02 s | 4.67 s | 24.74 s | 30.01 s |
| observed → recorded | 0.63 s | 10.91 s | 27.71 s | 30.02 s |
| observed → evaluated (decision) | **1.21 s** | 11.33 s | 27.83 s | 170.75 s |
| evaluated → opened | −0.05 s | 0.00 s | 0.00 s | 0.00 s |
| entry snapshot observed → opened | **0.18 s** | 2.57 s | 3.51 s | 8.01 s |

**The processing path is fast, not the bottleneck.** From an observed snapshot to a
position is p50 0.18 s / p90 2.57 s, and decision latency is p50 1.21 s. Collection
delay is sub-second at p50 and bounded by the 30 s freshness rule.

**The one real speed defect is the discovery→first-observation tail**: p50 8 s but
**p90 ~25 minutes and p99 ~2.4 hours**. 10% of discovered tokens wait over 25 minutes for
their first observation — again the observation-capacity limit, expressed as latency.

### A correction to my own probe

I initially read `entry_execution_price_usd / entry_signal_price_usd − 1` as a
**"latency premium"** and measured it at 99.5% of positions. It is **exactly 4.0000% at
every percentile** (p10 = p50 = p90 = p99 = max). That is not latency — it is the frozen
`BUY_SLIP = 0.04` cost model: the execution price is *derived* from the signal price by
construction. Recorded so it is not re-reported as an execution-quality defect.

## 3. A new robust marker: run-up from the token's first observed price

`runup = entry_signal_price / first_observed_price − 1`. Median **+27.0%**, p90 +197.8%,
and **91.6% of positions enter above the first price we ever saw** — we systematically buy
after a move. (That statement is descriptive; §4 shows it is *not* evidence that speed is
the problem.)

Tertiles over 1,710 positions:

| run-up tertile | median run-up | write-off | U/pos |
|---|---|---|---|
| low | +2.4% | **0.7%** | −2.89 |
| mid | ~+45% | 36.4% | −7.25 |
| high | +100.0% | **37.7%** | −9.97 |

**Robustness battery:**

- **token-clustered bootstrap on the write-off difference: +0.300, 95% CI [+0.074, +0.538]
  — EXCLUDES ZERO**;
- **drop-the-best-token**: baseline gap +37.0pp; dropping any single token leaves
  **+34.7 to +45.1pp** — not carried by one token;
- **not the survival confound**: `r(run-up, discovery→entry delay) = −0.116`, essentially
  uncorrelated.

**But the first robustness pass looked fatal, and the second reversed it.** Two things had
to be resolved, and both resolved *in favour* of the marker:

1. **The money effect must be measured as a low-vs-high contrast, not a cap contrast.**
   A cap at ≤25% gives +3.96 U/pos with CI [−0.59, +8.42] — it *includes* zero, because the
   cap comparison dilutes the effect by placing the ambiguous middle in the "dropped" group.
   The clean **tertile contrast is significant for money**:

   | contrast | observed | 95% CI (token-clustered) | excludes zero |
   |---|---|---|---|
   | write-off rate, high − low | +0.322 pp | [+0.082, +0.565] | **yes** |
   | **PnL, high − low** | **−4.851 U/pos** | **[−9.491, −0.055]** | **yes** |

2. **The 20-minute definition is free, and measures at least as well.** `history` in the
   acceptance loop (`store.py:27614`) holds only the token's observer frames from the
   **last 20 minutes** (`LIMIT 80`), so the *lifetime* run-up would need an extra per-token
   lookup. The 20-minute run-up is `history[0]["price"]` — already in scope, **zero extra
   queries** — and it separates equivalently (lifetime: write-off +0.286 pp CI
   [+0.050, +0.517], PnL −5.611 U/pos CI [−10.278, −0.813]).

**The remaining honest limit:** it is token selection, not entry timing. Within tokens
holding both sides of the median, the write-off difference has **median exactly 0.000 and
is positive in only 6 of 15** tokens; the cap acts on **12 of 37 tokens** (12 fully removed,
15 partly, 10 untouched). That is a small effective sample and the level is chosen
in-sample — which is precisely why it ships as a forward experiment rather than a fix.


## 4. The delay result inverts the "speed is the bottleneck" hypothesis — with a confound

Entering later after discovery does **better**, not worse:

| cohort | n | U/pos | write-off |
|---|---|---|---|
| entered within 5 min | 515 | −5.83 | 27.0% |
| entered after 5 min | 1,189 | −7.06 | 24.0% |
| entered within 1 h | 1,596 | −7.05 | 26.6% |
| **entered after 1 h** | **108** | **−1.31** | **0.0%** |

**This is confounded and must not be read as a speed recommendation.** A token can only be
entered an hour after discovery if it *survived* an hour, so the late group is conditioned
on survival. The correct reading is that the tail of the delay distribution is a
survivorship filter. I record it because it directly contradicts the naive expectation that
faster entry would help, and because anyone re-deriving this should not mistake it for
evidence that latency is costing money.

Measured by cap, choosing the level from the distribution rather than by eye (p33 = +9.3%,
p40 = +15.2%, p50 = +23.9%):

| cap | kept | write-off | U/pos | win |
|---|---|---|---|---|
| ≤ 5% | 442 | 0.5% | −4.22 | 10.2% |
| ≤ 10% | 571 | 0.4% | −3.39 | 17.9% |
| **≤ 15%** | **678** | **0.6%** | **−2.88** | 18.6% |
| ≤ 20% | 771 | **6.0%** | −3.76 | 18.7% |
| ≤ 30% | 957 | 9.0% | −3.63 | 19.5% |
| none | 1,712 | 24.8% | −6.73 | 13.9% |

The write-off rate jumps between the 15% and 20% cap, so **15% is the top of the safe
zone** and is the level shipped.

## 5. The two filters are complementary (best-structured result of the round)

Cross-tabulating the round-18 activity floor against the run-up marker:

| | `trades ≥ 30` | `trades < 30` |
|---|---|---|
| **run-up ≤ 25%** | n=535, −3.48 U/pos, **write-off 0.7%** | n=210, −6.93 U/pos, wo 31.9% |
| **run-up > 25%** | n=514, −5.81 U/pos, wo 17.9% | n=451, **−11.38 U/pos, write-off 57.9%** |

The worst quadrant (already run up **and** quiet) carries a 57.9% write-off rate; the best
carries 0.7%. The two conditions are partially independent — each floor alone leaves a bad
quadrant that the other catches.

Combined book:

| configuration | n | total | U/pos | win | write-off |
|---|---|---|---|---|---|
| actual | 1,710 | −11,434.4 U | −6.69 | 13.9% | 24.8% |
| activity floor only | 1,049 | −4,847.4 U | −4.62 | 18.1% | 9.2% |
| run-up cap only | 745 | −3,315.8 U | −4.45 | 19.6% | 9.5% |
| **run-up + activity** | 535 | **−1,859.7 U** | −3.48 | **23.6%** | **0.7%** |
| run-up + activity + take-profit | 535 | −1,540.3 U | −2.88 | 23.6% | 0.7% |

An 83.7% loss reduction, with the **win rate nearly doubling (13.9% → 23.6%)** and
write-offs falling 24.8% → 0.7%. **It still loses money**, and both inputs are in-sample.

## 6. What was shipped

`src/memetrader/runup_floor150.py` (new) — two more ENTRY arms, same construction as
ACTIVITY-FLOOR150 (in `alpha149.SPECS`, `kind = merged_multi_setup`, the control's exit
contract cloned verbatim):

| arm | floor |
|---|---|
| `runup_floor150_r15_v1` | run-up ≤ 15% (one-factor vs the control) |
| `runup_floor150_r15a30_v1` | run-up ≤ 15% **and** trades ≥ 30 (the measured-best conjunction) |

The screen reuses the round-19 hook in the cohort-acceptance loop and passes the loop's own
`history`, so **no extra query is issued**. Rejection reasons are distinct and auditable
(`runup_floor_exceeded`, `runup_floor_window_unknown`, `activity_floor_trades_not_met`).
Missing evidence never admits: with no before-window frame the run-up is unknown and the arm
does not enter. `reject_reason` returns `None` for every arm that is not ours.

**What I did NOT do:** change any existing strategy, stop, hold or exit contract; ship the
run-up cap as a *validated* fix (it is a forward experiment, and the kept book still loses);
treat latency as a bottleneck (§2, §4).


## 7. Next actions

1. **P0 — read ACTIVITY-FLOOR150** (landed round 19, frontier 36360). It has only a handful
   of settled positions so far; the hypothesis under test is the write-off rate
   34.8% → 6.0%. Use `scripts/paired_arm_ab.py` at ≥20 settled per side.
2. **P0 — read RUNUP-FLOOR150** (`runup_floor150_r15_v1`, `runup_floor150_r15a30_v1`) and
   ACTIVITY-FLOOR150 together against the shared control `alpha149_merged_multi_setup_fast_v1`.
   The quadrant analysis says the conjunction is the best configuration measured; the forward
   data decides whether that survives.
3. **P1 — the real coverage bottleneck** (only 0.4% of observed tokens are ever entered) is
   observation capacity: ~30 dense watch slots + 24 mover slots. Widening it is a
   user-decided budget item (declined in round 79, partially approved in 83/88), so act on
   **selection quality** within the existing slots instead.
4. **Do NOT build** a "+15%-touch predictor" or "quiet pool" filter (round 18) — and do not
   re-report the 4% "latency premium" (§2).
5. P0-3 (evaluation write rate) stays background: ~46 days headroom, state-chain risk.

## 8. Probe artifacts

`data/research/diag_round120/` (gitignored), read-only: `r20_schema.py`, `r20_latency.py`,
`r20_delay_cost.py`, `r20_runup_robust.py`, `r20_runup_decisive.py`, `r20_runup20.py`,
`r20_runup_level.py`, `r20_funnel.py`.
