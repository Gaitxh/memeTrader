# ROUND 120-35 RECORD — the first paired comparison is uninformative, and stop width is structurally untestable

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`).
Change: `scripts/experiment_readout.py` (paired gate now counts **diverged** cohorts).

## 1. Finding a properly paired pair

Round 34 established that `full15`/`full25` share only 3 settled cohorts with `bank15`/`bank25`
because they joined at **different frontiers** (32175 vs 15928). But `bank15`, `bank25` and
`widestop` all joined at **15928**, so they *do* share cohorts. The readout was run with the
per-side threshold lowered to 10 to see which pair has the best paired basis:

```
=== EXIT150  stop width: wide vs bank15
    widestop  settled=10   -8.35U/pos  win 20.0%  write-off 70.0%
    bank15    settled=23   -6.08U/pos  win 26.1%  write-off 47.8%
    paired basis: 10 shared settled cohort(s) across 10 token(s)
    within-cohort difference: -0.138U   90% token-clustered CI [-0.414, +0.000]  excludes zero: False
    drop top 1 token(s): -0.153U over 9
    drop top 2 token(s): -0.173U over 8
```

This is the session's **first properly paired comparison** — same frontier, same cohorts, only the
stop width varying. Taken at face value it says "no detectable difference", against an **unpaired**
arm-level gap of 2.27U/pos.

## 2. But 10 shared cohorts are really 1, and then 0

Breaking the 10 pairs down by whether the two arms' **close reasons differ**:

| difference | cohorts |
|---|---|
| **0.00** | **9** |
| **−1.38** | **1** |

**Nine of ten cohorts resolved identically.** Reading the reasons explains why: 7 are
`dex_pool_liquidity_below_configured_floor` (a write-off, forced by the pool dying regardless of
any stop) and 2 are `market_mark_hard_stop` where both arms realise the *same* PnL under a −0.35
and a −0.55 stop (`solana:3wEecdaDc` −19.99 both, `solana:Dw4hxvotjTZ` −18.19 both).

**The mechanism is round 17's gap-through, seen from a new angle.** A collapsing pool gaps past
*both* stop levels inside one mark interval, so the stop width never gets to matter. The single
differing cohort (−1.38U) has the *same* close reason on both sides
(`market_mark_trailing_exit`), i.e. a small mark variation rather than a different rule firing.

**So the effective basis for the stop-width question is zero informative cohorts.**

## 3. The gate was still counting the wrong thing

Round 34 fixed "count each side's total" → "count shared cohorts". This round shows **shared is
still not enough**: cohorts that resolve identically carry no information about the contract being
varied. The correct basis is the cohorts where the two arms **diverge**.

`scripts/experiment_readout.py` now reports and gates on that:

```
full15   vs bank15  : paired basis 3 shared, of which **2 diverged**
full25   vs bank25  : paired basis 3 shared, of which **1 diverged**
widestop vs bank15  : paired basis 10 shared, of which **0 diverged**
```

Default `--min-paired 20` now means 20 **diverged** cohorts. Every exit experiment in the fleet
is far below it, and `widestop` is at **zero**.

## 4. What this corrects

**"`widestop` is worse" is not supported.** I carried that claim out of rounds 16, 17 and 23, where
it rested on unpaired arm-level means (`−8.35` vs `−6.08U/pos`) and on round 17's price replay. The
paired evidence says the stop width has **never changed an outcome** in 10 shared cohorts. The
2.27U/pos gap is **cohort mix**, not the contract.

The wide-stop hypothesis is therefore not merely unsupported — it is **structurally untestable in
this market**, because the terminal move is a gap-through that crosses both levels at once. That is
a stronger and more useful statement than "we need more data".

**Also noted:** `full25` moved 17 → 18 settled and −5.45 → −4.98U/pos in one interval, again
illustrating how little a ~18-position mean should be trusted.

## 5. A pattern worth naming

This is the **third consecutive round** where refining a measurement gate changed a conclusion:

| round | gate refined | consequence |
|---|---|---|
| 27 | write-off rate decomposed into full-loss vs partial | the stated mechanism was wrong |
| 34 | per-side count → **shared** cohorts | the headline contrast is unpaired |
| 35 | shared → **diverged** cohorts | stop width is untestable; a standing claim is withdrawn |

In each case the *direction* survived and the *strength of claim* did not. The lesson, recorded as
a standing rule: **before reading a paired experiment, count the units where the thing being varied
actually changed the outcome.**

## 6. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not remove or pause `widestop`; it is uninformative, not harmful, and removing it would be
  its own decision.
- Did not modify production runtime code; the only change is the readout script.
- Did not claim a verdict; there is none.

## 7. Next actions

1. **P0 — the paired clock is the real constraint.** All exit experiments are far below 20
   *diverged* cohorts. Report diverged counts first, always.
2. **P0 — keep the experiments running.**
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing rule (new):** for a paired experiment, the usable basis is the units where the arms
   **diverged**, not the units they share.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis (r28),
   slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect (r31),
   provider reliability (r32), the refused-start fix (r33).

## 8. Probe artifacts

`data/research/diag_round120/r35_paired_basis.py`, plus
`scripts/experiment_readout.py --min-settled 10 --min-paired 5`.
