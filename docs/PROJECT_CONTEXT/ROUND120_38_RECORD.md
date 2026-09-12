# ROUND 120-38 RECORD — the elective profit is real but thin and tail-driven; my selection hypothesis was wrong

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The hypothesis I set out to test

Round 36 concluded "the exits work" from the forced/elective split (forced −20,332U, elective
+1,348U). But that split is **endogenous**: a position exits electively only if it survived long
enough for a take-profit, trailing or time rule to fire. So the elective profit could be
**selection — survivors rather than exit skill** — and "the exits work" would be too strong.

The testable version: on the elective population, did those positions simply have better peaks?

## 2. It was wrong. The elective population had WORSE peaks.

| population | n | median peak econ |
|---|---|---|
| **FORCED** | 1,322 | **+7.3%** |
| **elective** | 1,044 | **−0.8%** |

**The forced population peaked higher.** The typical elective-exit position never went meaningfully
positive at all. So the elective side's +1,344U is **not** a selection effect on peak quality — the
hypothesis is refuted, and round 36's directional claim survives this particular challenge.

## 3. Value capture by mechanism

| mechanism | n | peak p50 | exit p50 | give-back p50 | total give-back | PnL |
|---|---|---|---|---|---|---|
| FORCED pool died | 760 | +15.2% | +1.2% | 0.0% | **5,261.5U** | −14,839.0U |
| FORCED hard stop | 562 | −7.9% | **−25.8%** | **16.8%** | **3,410.6U** | −4,902.4U |
| elective time exit | 663 | −2.5% | −3.2% | 0.0% | 276.7U | +585.8U |
| **elective trailing** | **171** | **+88.5%** | **+55.7%** | **14.8%** | **800.0U** | **+951.8U** |
| elective signal-decay | 145 | −9.6% | −12.4% | 1.6% | 256.7U | −243.8U |
| elective take-profit | 24 | +12.7% | +12.5% | 0.0% | 3.2U | +110.5U |
| elective other | 41 | −11.0% | −12.4% | 0.3% | 58.3U | −60.7U |

## 4. What the elective side actually is

**It is thin and tail-driven, not broad-based.**

- The entire elective PnL (**+1,344U**) rests on **171 trailing exits (+952U)**; time exits add
  +586U, decay subtracts −244U, take-profit +111U.
- **Concentration within mechanisms:** for `elective time exit`, the **top 10% of positions produce
  508.6U of the 585.8U** — 87% of the profit from a tenth of the population. For trailing it is
  298.5U of 951.8U (31%).
- The trailing population is where the runners are: **median peak +88.5%**, and 79.5% of them are
  winners.

**So the picture is a standard memecoin book: most positions go nowhere (median peak −0.8% on the
elective side), and a small runner tail carries everything.** That is consistent with round 17
(only 5 of 906 positions ever reached +100%) and with round 25 (outcome set by token choice).

## 5. The give-back is NOT recoverable headroom

The trailing exits hand back a **median 14.8 percentage points** (800U in total), which looks like
the "金狗拿不住" leak. **It is not recoverable.**

Capturing the peak requires knowing the peak — a future function. A trailing rule gives back
exactly what it must in exchange for not exiting early: round 17 already measured that a
full-capture take-profit at +15% earns **less** on the runner tail than trailing does, while earning
far more on the round-trippers. The 800U is the **price** of the trailing rule, not a defect in it.

The forced hard stops' 16.8pp median give-back (3,410U) is the same kind of number for a different
reason — that one is the **gap-through** of round 17/35, and it is likewise not recoverable, because
the collapse happens inside a single mark interval.

## 6. Corrected statement of round 36

Round 36 said "the exits work". The defensible version, after this test:

> **58.5% of exits are forced by mechanisms no exit contract can influence, and that is where the
> entire loss sits. The remaining 41.5% is net positive — and it is positive despite having
> *worse* peak economics than the forced population, so it is not a survivor-selection artifact.
> But it is thin (top 10% of time-exits carry 87% of their profit) and its largest apparent leak
> (800U of trailing give-back) is the unavoidable price of not knowing the peak, not headroom.**

The ceiling conclusion is unchanged. What changes is that "the exits work" is now a **tested**
claim rather than an inference from an endogenous split.

## 7. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not modify production runtime code.
- Did not claim the 800U give-back as recoverable; §5 gives the reason.
- Did not read the forward experiments as verdicts (`full15` 19 settled / 2 diverged).

## 8. Next actions

1. **P0 — the pairing clock remains the constraint.** Report **diverged** cohorts first, always.
2. **P0 — keep the experiments running.**
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing conclusion (refined, r36+r38):** exit-side work faces a 41.5% ceiling; that slice is
   net positive and is **not** selection on peaks, but it is tail-driven and its give-back is the
   price of the rule. Do not propose further exit variants without saying what in the forced 58.5%
   they could change — normally nothing.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis (r28),
   slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect (r31),
   provider reliability (r32), the refused-start fix (r33), or the paired-basis questions (r34/r35).

## 9. Probe artifacts

`data/research/diag_round120/r38_elective_capture.py`.
