# ROUND 120-25 RECORD — effective n is 30, not 2,256; and the arm fleet is not redundant, it is unexercised

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The effective sample size of this epoch is ~30

2,245 settled positions invite per-position statistics at n≈2,245. Variance decomposition says
otherwise.

| grouping | groups | eta² (share of PnL sum-of-squares) |
|---|---|---|
| **token identity** | 46 | **56.9%** |
| **cohort (token × snapshot)** | 405 | **77.9%** |
| arm identity | 174 | 14.6% |

| | |
|---|---|
| positions per token | median **57**, max 118 |
| nominal n | 2,245 |
| distinct tokens | 46 |
| Kish effective n (1 / Σ wᵢ²) | **30.0** |

**A per-position statistic quoted at n=2,245 is really about 30 independent observations.** Every
interval computed in this session was already token-clustered, so those stand — this quantifies
*why* they are wide, and it sets a hard ceiling on how much this epoch can teach.

The decomposition also gives a clean priority ordering, which the objective asked for:

**token selection (56.9%) > entry timing (cohort adds ~21pp, to 77.9%) > exit contract (14.6%).**

That ordering is consistent with everything found since round 17: the exit side had almost no
headroom, entry floors moved the write-off rate, and the run-up (an entry-timing feature) was
the strongest marker apart from activity.

## 2. 82% of the position count is replication

| | |
|---|---|
| settled positions | 2,256 |
| **distinct entry decisions (cohorts)** | **406** |
| positions per cohort | 5.56 mean, median 2, max 50 |
| positions beyond the first on their cohort | **1,850 = 82.0%** |
| within-cohort PnL spread | **median 0.00U**, p90 22.57U, max 42.85U |

**The epoch contains ~406 distinct entry decisions, exercised 2,256 times.** A median spread of
exactly 0.00U means that for most multi-arm cohorts every arm realised the *same* result.

Arm fragmentation: 174 arms hold settled positions, **median 9 positions each**, and **125 of 174
(72%) are below the 20-settled readability threshold**, holding 871 positions between them. So
the fleet is simultaneously over-replicated in outcomes and under-powered per arm.

## 3. The merge hypothesis, tested and REJECTED

The user's standing principle is to consolidate parameter-only variants. The obvious reading of
§2 is "82% of positions are duplicates — merge them". I tested that, and it does not hold.

**First attempt was confounded by my own criterion.** Pairing arms on identical (PnL,
close_reason) produced a "50-arm provably identical group" that included the round-19 floor arms,
which is implausible. The cause: **a write-off forces PnL = −stake and an identical reason**, so
any two arms written off on the same cohorts look trivially identical, and union-find chained
those into one giant component. Excluding write-offs fixed that.

**Second check — is outcome identity even meaningful?** Of the 861 shared cohort-outcomes used to
declare 114 pairs identical:

| close reason | share |
|---|---|
| `market_mark_hard_stop` | **48.7%** |
| `market_mark_max_hold` | 30.9% |
| `market_mark_trailing_exit` | 13.1% |
| `trajectory144_..._decay` | 6.7% |
| `alpha149_vol_scaled_stop` | 0.6% |

Only 30.9% is the time exit (0 of 114 pairs rest *only* on max-hold agreement, so the pairs are
not merely untriggered). **But 48.7% is the COMMON hard stop, which arms share by design** — two
arms agreeing there shows the shared rule bound first, not that they are the same strategy. Only
~20% of the evidence involves a rule that actually differs between arms.

**So outcome identity is weak evidence, and I did not act on it.** The safe test is *contract*
identity, which is directly provable — two arms with identical policy bodies (minus identity and
label fields) are the same strategy and merging cannot lose information:

| | |
|---|---|
| registered arms | 325 |
| **distinct contracts** | **311** |
| contracts shared by >1 arm | **8** |
| arms in a duplicate contract | 22 |
| positions held by those arms | **28 (1.2%)** |
| duplicate groups holding 0 positions | 5 of 8 |

**The arm fleet is not made of duplicates.** There is essentially nothing to merge.

## 4. What the two results mean together

- The arms are **contractually distinct** (311 distinct contracts) but **behaviourally
  indistinguishable in outcome** (arm eta² 14.6%, median within-cohort spread 0.00U).
- The reason is not duplication: **~80% of exits are resolved by rules the arms share** (common
  hard stop 48.7% + time exit 30.9%), so the fleet's contract diversity is largely **unexercised**.
- That is consistent with round 17, where the hard stop was the dominant close (289 of 885) and
  the gap-through made stops fire early.

**Implication: arm proliferation is not the defect, and pruning would be both unsafe (nothing is a
true duplicate) and ineffective (the differences are untested, not absent). The binding common
rules are what suppress expression of the fleet's diversity.** The exit-side variants need
conditions where their distinctive trigger fires first; until then they are indistinguishable by
construction.

## 5. What this round did NOT do

- Did not retire, merge, pause or retune any arm — §3 gives the reasons.
- Did not act on the outcome-identity merge list, which was confounded twice over.
- Did not modify any production source.
- Did not read the forward experiments as verdicts (`exit150_full15_v1` still at 16 settled).

## 6. Next actions

1. **P0 — stop trying to prune the fleet.** §3/§4 close that line: there is nothing to merge and
   the differences are unexercised. Do not revisit without a contract-level duplicate.
2. **P0 — re-run `scripts/experiment_readout.py`.** `exit150_full15_v1` (16 settled, −0.00U/pos,
   81.2% win, 6.2% write-off vs `bank15`'s 27.3% / 50.0%) is closest and is the one to read first.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24). That is the most specific open target.
4. **P1 — a common-rule change is where the leverage is now.** ~80% of exits are decided by
   shared rules; the exit variants cannot differentiate until that changes. Any such change must
   be a new arm, not an edit to an existing one.
5. **Do NOT** quote per-position statistics at n>30 for this epoch without clustering.

## 7. Probe artifacts

`data/research/diag_round120/`, read-only: `r25_variance.py`, `r25b_replication.py`,
`r25c_merge_list.py` (confounded, kept for the audit trail), `r25d_merge_fixed.py`,
`r25e_identity_validity.py`, `r25f_contract_groups.py`.
