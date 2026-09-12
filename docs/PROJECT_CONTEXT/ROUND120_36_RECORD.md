# ROUND 120-36 RECORD — the exit side is where the PROFIT is; the entire loss is on forced exits

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. What this round measured

Round 35 showed exit contracts rarely get expressed — of 10 shared cohorts between arms with
different stop widths, nine resolved identically because a collapsing pool gaps past both levels at
once. That implies a measurable ceiling on exit-side leverage, and it is directly countable: of all
settled positions, what share exited by a mechanism **no exit contract can influence** versus an
**elective** exit the contract actually decides?

2,463 settled positions, classified by `close_reason`:

| mechanism | positions | share | PnL |
|---|---|---|---|
| **FORCED** — pool died (write-off) | 764 | 31.0% | **−14,919.0U** |
| **FORCED** — hard stop | 678 | 27.5% | **−5,413.2U** |
| **FORCED total** | **1,442** | **58.5%** | **−20,332.2U** |
| elective time exit | 644 | 26.1% | **+611.1U** |
| elective trailing | 167 | 6.8% | **+930.8U** |
| elective signal-decay | 145 | 5.9% | −243.8U |
| elective take-profit | 24 | 1.0% | +110.5U |
| elective runner review + custom kinds | 41 | 1.7% | −61.4U |
| **ELECTIVE total** | **1,021** | **41.5%** | **+1,347.8U** |

Totals reconcile: **−20,332.2U forced + 1,347.8U elective = −18,984.4U**, the epoch's loss.

## 2. The two findings, and why they matter more than any parameter

**Finding 1 — the ceiling.** Only **41.5%** of settled positions exit by a mechanism an exit
contract actually decides. The other **58.5%** are forced by the pool dying or by a one-interval gap
that crosses every configured level simultaneously. No stop width, ladder level, trailing rule or
time limit can act on those. **Exit-side research has a hard ceiling of roughly the elective share**
— and round 35 showed that even inside it, most cohorts resolve identically because the two arms'
rules coincide.

**Finding 2 — and this is the important one.** The PnL split is not a gradient, it is a sign change:

- **forced exits: −20,332.2U**
- **elective exits: +1,347.8U**

**The entire loss sits on positions whose exit was forced. Where the exit contract is actually in
control, the system is net profitable.**

So the system's exit logic is not the problem and is not a promising target. **The exits work. The
positions that die are the problem** — and a position dies because of which token was entered, not
because of how it was exited. That is an ENTRY problem.

## 3. How this fits everything else

This is the fourth independent measurement pointing the same way, now with a PnL decomposition
rather than a counterfactual:

| round | measurement | conclusion |
|---|---|---|
| 17 | replay: no stop level helps; the collapse is an 11 s gap-through | exit rules cannot recover the loss |
| 25 | variance decomposition: token 56.9%, arm **14.6%** | outcome is set by token choice |
| 29 | 4.4% of observed tokens get dense observation; those convert at 18× | the binding constraint is coverage |
| **36** | **forced exits −20,332U, elective exits +1,348U** | **the loss is entirely on positions the exit could not influence** |

**Combined statement: the exit side is where the profit is; the loss is entirely an entry-selection
problem, and entry selection is capped by dense-observation coverage (4.4% of observed tokens),
which is a user-decided budget item.**

## 4. A supporting detail: the hard stop gaps a third of the time

Of the 678 forced hard stops, realised PnL / stake: p10 **−0.911**, p50 **−0.263**, p90 −0.197. A
−0.20-economic stop implies about −0.183 at the level. **219 of 678 (32%) realised worse than
−0.35/stake — clearly gapped through**, with a p10 near −0.91 (essentially total loss). That is
round 17's gap-through quantified on the whole epoch rather than a sample, and it is why widening
the stop changed nothing (round 35: 0 of 10 cohorts diverged).

## 5. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not read the forward experiments as verdicts; `full15` is at 19 settled / **2 diverged
  cohorts**, `full25` 18 / **1 diverged**.
- Did not claim the elective exits being profitable means the system is profitable — it is not; the
  forced exits overwhelm them.
- Did not modify production runtime code.

## 6. Next actions

1. **P0 — the pairing clock remains the constraint.** Report **diverged** cohorts first, always.
2. **P0 — keep the experiments running.** Nothing analysis can do will accelerate them.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing conclusion (new):** exit-side work faces a **41.5% ceiling** and the elective share is
   already net positive. Do not propose further exit variants without saying what in the forced
   58.5% they could possibly change — normally the answer is nothing.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis (r28),
   slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect (r31),
   provider reliability (r32), the refused-start fix (r33), or the paired-basis questions (r34/r35).

## 7. Reconciliation, and the ceiling is moving

The split was recomputed **independently in SQL** from the raw columns, so a classification bug in
the Python probe would show as a mismatch:

| | Python probe | SQL recomputation |
|---|---|---|
| forced | −20,332.2U (1,442) | **−20,332.2U (1,442)** |
| elective | +1,347.8U (1,021) | **+1,346.7U (1,025)** |
| total | −18,984.4U | **−18,985.5U** |

`forced + elective == total` holds exactly; the small position-count difference is four `other`
custom-kind closes that the probe and the SQL classify on slightly different keys. **The finding is
not sensitive to the classification.**

**The ceiling is not a constant.** Restricting to the most recent 2 hours:

| window | positions | forced share | forced PnL | elective PnL |
|---|---|---|---|---|
| whole epoch | 2,467 | **58.5%** | −20,332.2U | +1,346.7U |
| **last 2h** | 1,847 | **53.4%** | −13,850.1U | **+1,438.9U** |

Two things follow, both favourable and both needing more data before they are believed:

1. **The elective share is rising** (41.5% → 46.6%), consistent with the EXIT150 arms accumulating
   elective take-profit and trailing exits with `principal_recovered` finally non-zero.
2. **The recent window's elective PnL alone (+1,438.9U) exceeds the entire epoch's (+1,346.7U)** —
   i.e. recent elective exits are strongly positive.

**Caveat, stated plainly:** the recent window is a subset of the epoch, and the epoch figure already
contains it, so these are not two independent samples. The trend is worth watching, not banked.

## 8. Probe artifacts

`data/research/diag_round120/r36_exit_ceiling.py`, `r36b_reconcile.py`.
