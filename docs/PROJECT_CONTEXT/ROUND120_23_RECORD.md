# ROUND 120-23 RECORD — a consolidated experiment readout, and the first interim readings

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). Read-only measurement plus one new script.

## 1. Why this round built a tool

Six forward experiments are live (`exit150_*`, `activity_floor150_*`, `runup_floor150_*`) and I
had been checking them with ad-hoc SQL each round. The concrete failure this changes: there was
no single, correct answer to "is any experiment readable yet, and what does it say".

`scripts/experiment_readout.py` (new) reports, per experiment: settled counts on both sides,
readiness against a threshold, the arm's and control's own book (U/pos, win rate, write-off
rate), and — only when both sides clear the threshold — a **token-clustered 90% interval**. It
prints `NOT READY` and **no verdict** below the threshold rather than a spurious one.

### The design point that matters

`paired_arm_ab.py` pairs two EXIT carriers within a cohort, which is correct because they share
the same entry opportunity and differ only in exit contract. **That design is wrong for the
ENTRY floors.** A floor arm enters a subset of the control's cohorts, so within-cohort pairing
silently drops exactly the cohorts the floor rejected — the ones the hypothesis is about.
Pairing would have hidden the effect it was meant to measure.

So the readout applies a different design per kind:

- **exit** — paired within-cohort difference against the control (same as `paired_arm_ab`),
  plus a drop-the-top-token stress.
- **floor** — **set-difference design**: identify the cohorts the arm refused *by its own floor*
  from the recorded `outcomes` reasons, then measure the control's own settled positions on
  those cohorts. That is the direct test of "the floor avoided the bad ones", and it does not
  require inferring rejection from a missing position.

## 2. Interim readings — NOT verdicts, every one below threshold

Threshold is 20 settled per side. Nothing below is a verdict.

| experiment | arm (settled, U/pos, win, write-off) | control (settled, U/pos, win, write-off) |
|---|---|---|
| EXIT150 +15%: full vs partial | **16, −0.00, 81.2%, 6.2%** | 22, −6.01, 27.3%, 50.0% |
| EXIT150 +25%: full vs partial | 14, −6.89, 50.0%, 42.9% | 22, −7.01, 36.4%, 50.0% |
| EXIT150 stop width: wide vs bank15 | 10, −8.35, 20.0%, 70.0% | 22, −6.01, 27.3%, 50.0% |
| ACTIVITY-FLOOR trades>=30 | 10, −4.72, 20.0%, **10.0%** | 26, −9.71, 19.2%, **42.3%** |
| ACTIVITY-FLOOR volume>=5000 | 8, −5.71, 25.0%, **12.5%** | 26, −9.71, 19.2%, 42.3% |
| RUNUP-FLOOR run-up<=15% | 9, −3.87, 22.2%, 22.2% | 26, −9.71, 19.2%, 42.3% |
| RUNUP-FLOOR run-up<=15% & trades>=30 | 7, −1.90, 28.6%, **14.3%** | 26, −9.71, 19.2%, 42.3% |

Three things are at least *consistent* with the stated hypotheses:

- **`exit150_full15_v1`** is the standout: **−0.00U/pos with an 81.2% win rate and a 6.2%
  write-off rate**, against the matched partial-capture `bank15` at −6.01U/pos / 27.3% / 50.0%.
  This is exactly what round 17 predicted (full capture at +15% beats leaving 50% riding), and
  it is the only arm here near break-even.
- **every floor shows a much lower write-off rate than the control** (10.0–22.2% vs 42.3%),
  which is the specific mechanism each was built for.
- **`widestop` is worse** (−8.35U/pos, 70% write-off), consistent with rounds 120-16 and 120-17
  having twice weakened the wide-stop argument.

The +25% pair shows almost no separation (−6.89 vs −7.01), which is *not* what round 17's
replay predicted and is worth watching: it suggests the capture-fraction effect may be
concentrated at the +15% level rather than being a general property.

## 3. The counterfactual is real but rests on n=3 — verified two ways

For `activity_floor150_t30_v1`, the readout reports that the floor rejected 19 cohorts and the
control itself traded 3 of them, at **−20.00U/pos, 100% write-off**. That is the whole
hypothesis, so it was checked by an independent second method:

| method | basis | cohorts | settled | U/pos | write-off |
|---|---|---|---|---|---|
| A (used by the readout) | recorded `outcomes` = floor reason | 19 | **3** | −20.00 | 100% |
| B (independent) | cohorts the control traded but the arm never did | 22 | 22 | −10.84 | 45% |

Both agree the avoided set is deeply negative. They differ in magnitude because they measure
different things: **A isolates rejections attributable to the floor**, while **B also includes
cohorts the arm missed for unrelated reasons** (concurrency, `single_token_lifetime_entry`, or
the arm not existing yet at that frontier).

**The honest caveat: A's avoided set is only 3 positions.** The floor rejected 19 cohorts, but
only 3 of them were opportunities the control would actually have taken — the control has its
own gates. So the −20.00U/pos figure is suggestive, not established, and the readout correctly
refuses to print a verdict for it.

## 4. What this round did NOT do

- Did not modify, retune, pause or replace any existing arm.
- Did not change any stop, hold, exit contract, or the observation cadence.
- Did not promote any arm on an interim reading — every number in section 2 is sub-threshold.
- Did not treat method B as the floor's effect; it is an upper bound on scope, not the effect.

## 5. Next actions

1. **P0 — re-run `scripts/experiment_readout.py`** until experiments clear 20 settled per side.
   `exit150_full15_v1` is closest (16) and is the one worth reading first.
2. **P0 — re-measure distinct-pool coverage** once >=6 post-change 10-minute buckets exist
   (adaptive cadence, round 22), against the trend rather than a flat average.
3. **P1 — watch the +25% capture pair**: no separation yet, against round 17's replay.
4. **Do NOT** treat any section-2 number as a verdict; do not re-report the 4% "latency
   premium"; do not build a "+15%-touch predictor" (round 18).

## 6. Probe artifacts

`data/research/diag_round120/r23_verify_attribution.py`, plus the new
`scripts/experiment_readout.py` (tracked).
