# ROUND 120-34 RECORD — the paired basis is 3 cohorts: the EXIT150 headline contrast is UNPAIRED

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`).
Change: `scripts/experiment_readout.py` (paired-cohort gate added).

## 1. What happened

`exit150_full15_v1` reached **19 settled, one short of the 20-per-side threshold**. To exercise the
full analysis path before it produced a "verdict", the readout was run with the threshold lowered
to 19. It produced:

```
arm     exit150_full15_v1    settled=19   -0.00U/pos  win 78.9%  write-off  5.3%
control exit150_bank15_v1    settled=23   -6.08U/pos  win 26.1%  write-off 47.8%
paired on 3 shared settled cohort(s)
within-cohort difference: +5.866U   90% token-clustered CI [+1.793, +9.939]  excludes zero
drop top 1 token(s): +2.690U over 2
drop top 2 token(s): +0.000U over 1
```

**A token-clustered interval that "excludes zero" while resting on three cohorts, where dropping
two tokens leaves a single observation with a difference of exactly 0.000U.** Reported without
that context it would have been meaningless — and it is the same shape as the artifacts caught in
rounds 18 and 26.

## 2. The gate was counting the wrong thing

`experiment_readout.py` gated on **each side's own settled count**. But a paired test needs
**shared** cohorts. Two exit carriers registered at *different frontiers* can each clear 20 settled
while sharing only a handful of cohorts.

That is exactly the case here: `exit150_full15_v1` / `exit150_full25_v1` joined at frontier
**32175**, while `exit150_bank15_v1` / `bank25` / `widestop` joined at **15928**. They share cohorts
only from 32175 onward — **3 settled cohorts across 3 tokens** today.

**Fixed:** the readout now takes `--min-paired` (default 20) and refuses the paired verdict when the
shared basis is too thin, additionally stating that the per-position figures are UNPAIRED. Verified
both ways — it refuses at 3 cohorts and the default run is unchanged for the other experiments.

## 3. What this means for the headline I have been tracking

Since round 17 I have carried the contrast **"`full15` −0.00U/pos / 78.9% win / 5.3% write-off
versus `bank15` −6.08U/pos / 26.1% / 47.8%"** as the standout result of the session, and it matches
round 17's replay prediction.

**That comparison is UNPAIRED.** The two arms traded *different cohorts on different tokens*, so
the difference is between two different opportunity sets, not between two exit contracts applied to
the same opportunities. It remains **suggestive and directionally consistent with the replay** —
and it is not the controlled comparison the exit-carrier design is meant to provide.

The matched-control property does hold in principle (carriers clone the first frozen entry signal),
but only for cohorts a pair *both* joined, which for a frontier-differing pair accumulates slowly.

**Consequence for the verdict:** when `full15` clears 20 settled next round, the correct statement
will be *"the paired basis is still N cohorts; the unpaired contrast is X"* — not a verdict. The
paired test needs ~20 **shared** cohorts, which is a different and slower clock.

## 4. Also worth noting: how unstable n≈19 is

`full15`'s per-position figure moved **+0.41U → −0.00U** on the addition of a single settled
position. That is the appropriate amount of confidence to have in a 19-position mean, and it is why
the threshold exists.

## 5. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not lower the verdict threshold to manufacture a result — the lowered run was a *test of the
  tool*, and it is what exposed the flaw.
- Did not modify production runtime code; the only change is the readout script.
- Did not claim a verdict.

## 6. Next actions

1. **P0 — re-run the readout.** When `full15` clears 20 settled, report the **paired basis size**
   first. A verdict needs shared cohorts, not per-side totals.
2. **P0 — keep the experiments running.** The paired clock is slower than the per-side clock and
   cannot be accelerated by analysis.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing rule (new):** for a paired design, gate on **shared** units, not on each side's total.
   A per-side count can clear its threshold while the paired basis is three observations.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis (r28),
   slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect (r31),
   provider reliability (r32), the refused-start fix (r33).

## 7. Probe artifacts

No new probe scripts; the finding came from `scripts/experiment_readout.py --min-settled 19`.
