# ROUND 120-27 RECORD — a metric-integrity correction: the write-off rate is not a loss rate

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The metric I audited

Since round 17 I have used the **write-off rate** as the headline metric for the floor and exit
experiments, and the contrast I have repeated most often is:

> "`exit150_full15_v1` has a **5.9%** write-off rate against `exit150_bank15_v1`'s **50.0%**."

`bank15` sells 50% of the remaining position at +15% and rides the rest. So a position can **bank
profit and still be marked `written_off`** when the remainder's pool dies. If so, the write-off
rate conflates "the pool died" with "the pool died *after banking*", and that contrast is
mis-framed.

## 2. The audit result: safe in aggregate, unsafe for partial-exit arms

Across all 764 written-off positions:

| | share |
|---|---|
| full loss (`|pnl| >= 98%` of stake) | **97.4%** |
| **partial loss (banked something first)** | **1.6%** |
| **positive PnL but marked written_off** | **1.0%** |

**In aggregate, `written_off` really does mean "lost essentially everything"**, so the metric is
safe for the fleet as a whole. But it is **not** safe for the specific arms I have been
comparing, because those are exactly the partial-exit arms:

| arm | settled | write-offs | **full-loss** | **partial** | realised |
|---|---|---|---|---|---|
| `exit150_full15_v1` | 17 | 1 | 1 | 0 | **+0.26U/pos** |
| `exit150_bank15_v1` | 22 | 11 | **3** | **8** | −6.01U/pos |
| `exit150_full25_v1` | 15 | 6 | 6 | 0 | −6.10U/pos |
| `exit150_bank25_v1` | 22 | 11 | 6 | 5 | −7.01U/pos |
| `exit150_widestop_v1` | 10 | 7 | **1** | **6** | −8.35U/pos |
| `activity_floor150_t30_v1` | 11 | 1 | 1 | 0 | −4.22U/pos |
| `runup_floor150_r15_v1` | 11 | 2 | 2 | 0 | −2.67U/pos |

**Stated correctly:**

| arm | write-off rate | of which full-loss | of which partial | realised |
|---|---|---|---|---|
| `exit150_full15_v1` | 5.9% | 5.9% | 0.0% | +0.26U/pos |
| `exit150_bank15_v1` | 50.0% | **13.6%** | **36.4%** | −6.01U/pos |

`bank15`'s 11 write-offs decompose into **3 full-loss (−60.00U, mean −20.00U) + 8 partial
(−28.87U, mean −3.61U)**.

## 3. What this changes, and what it does not

**Does not change the conclusion.** The money comparison is realised PnL per position, which
already accounts for whatever was banked before the remainder died:

**`full15` +0.26U/pos vs `bank15` −6.01U/pos = +6.27U/pos**, and the direction of the round-17
replay is unchanged.

**Does change the stated mechanism — and makes it more interesting.** I had implied bank15's
ladder fails. It does not: **8 of its 11 write-offs were partial, averaging −3.61U rather than
−20U**, so the ladder genuinely banks. **It just banks too little to matter.** `full15` converts
those same cohorts into real closures by selling 100% at the first tier. That is a sharper and
more favourable statement about the ladder design than the one I had been making.

**A second trap in the same table.** `bank15`'s *closed* (non-write-off) positions average
**−3.95U/pos** while `full15`'s average **+1.53U/pos**. That is not a performance difference
either: the two arms' closed sets are *different by construction*. `bank15` does not close at
+15% — it sells half and keeps riding — so its closed set is dominated by stop and time exits,
while `full15`'s is dominated by its take-profit. **Comparing "closed mean" across arms with
different exit paths is meaningless.** Only realised PnL per position is comparable.

## 4. Corrections owed

The mis-framed contrast appears in the records for rounds **17, 23, 25 and 26** and in the
checkpoint. The conclusion in each is unaffected; the stated mechanism is. The checkpoint has
been updated to carry the corrected form.

This is the **third self-correction in three rounds** (round 25: an outcome-identity merge list
confounded by write-offs; round 26: a vacuously-true leave-one-out check; round 27: this). The
common cause is **metric semantics assumed rather than checked**. The discipline that would have
caught all three up front: before using a derived metric as evidence, decompose it against the
underlying money at least once.

## 5. What this round did NOT do

- Did not modify any production source or any experiment definition.
- Did not re-run or re-interpret any arm's verdict (none is readable yet).
- Did not change the settled threshold or promote anything.

## 6. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (17 now). Still the only experiment near
   readable. Use **realised PnL per position**, and decompose any write-off claim into
   full-loss versus partial before stating it.
2. **P0 — re-measure distinct-pool coverage** once ≥6 post-change 10-minute buckets exist
   (adaptive cadence, round 22), against the trend.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24).
4. **Standing rule (new):** for any partial-exit arm, never quote a write-off rate as a loss
   rate, and never compare `closed`-set means across arms with different exit paths.
5. **Do NOT** search for token-level exclusion rules on this epoch again (round 26); do not try
   to prune the fleet (round 25).

## 7. Probe artifacts

`data/research/diag_round120/`, read-only: `r27_writeoff_semantics.py`,
`r27b_headline_split.py`.
