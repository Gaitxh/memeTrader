# ROUND 120-30 RECORD — the dense-episode-free lead is closed; the diagnosis is complete

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The lead from round 29, resolved

Round 29 found that 11 of 48 entered tokens never had a ≥3-frame observation episode, and flagged
that lane as the most promising remaining lead **because widening it would need no observation
budget**. It does not survive contact.

**All 11 are the `native_protocol_model` lane — 100%:**

| | |
|---|---|
| tokens | 11, all `solana:...pump` |
| positions | **11 — exactly 1 per token** |
| mode composition | `native_protocol_model` 11/11 (100%) |
| contrast: the 37 dense-episode tokens | `isolated_cohort_observer` 2,485 (98.7%) + `isolated_pattern_observer` 33 |
| realised | **−10.8U over 11 positions (−0.98U/pos)** |
| closes | 9 `hard_stop` (−12.83U) · 1 `trailing` (+2.64U) · 1 `max_hold` (−0.40U) |

Their token-level observation is near-zero (0–4 snapshots each, 0–1 observer frames), so these
tokens are not "undensed" — they are **traded on an entirely different evidence basis**. This is
not a coverage route that can be widened within the DEX-pool observation architecture; it is a
separate protocol lane with one position per token and no demonstrated edge.

**Round 29's caveat is therefore resolved:** dense observation is the route for 37 of 48 entered
tokens (77%), and the other 23% arrive through a lane that is neither free to widen nor
profitable on the evidence so far.

## 2. A real analytical hazard found on the way

All 11 native-lane positions carry **`entry_snapshot_id = 0`** — NULL or dangling — with
`entry_reason = later_observed_protocol_model_paper`. The cohort lane by contrast is clean:
**2,485 positions, 0 NULL, 0 dangling.**

Read carefully, this is **not** a missing-evidence defect: `later_observed_protocol_model_paper`
names next-observed/trigger-anchored execution explicitly, which is the documented and frozen
semantic. The position is valued on the **next** observation rather than an as-of entry snapshot.

**But it is an analytical dead zone, and it is the same trap that bit an earlier round:** these
positions cannot be joined to entry-time market features at all. Any query that joins positions to
`token_snapshots` on `entry_snapshot_id` silently drops them — a 0-row result that looks like "no
data" rather than "different lane". Recorded so that future entry-feature analysis states which
lane it covers.

## 3. The diagnosis is complete

Every link of the chain has now been measured, and every candidate explanation eliminated:

| link | status |
|---|---|
| discovery | healthy — 10,089+ tokens discovered |
| collection | healthy — 94.5% of discovered tokens observed |
| feature / trajectory | healthy — 66.8% of accepted observations form a ready 30 s window |
| processing speed | not binding — p50 **0.18 s** observed → position |
| freshness rules | not binding — 0.03% of evaluations |
| signal generation | not binding — mechanisms fire amply |
| arm fleet | not redundant (311 contracts), not prunable (r25) |
| token-level exclusion | unvalidatable at n≈40 (r26) |
| capital / concurrency / pending intents | not binding — **1.35% utilised** (r28) |
| slot turnover / lease duration | not a lever — late frames carry new info at 16.8–19.2% (r29) |
| the dense-episode-free lane | not widenable, no edge (r30) |
| **dense-observation coverage** | **THE BINDING CONSTRAINT — 4.4% of observed tokens (527 of 11,991)** |

**The measured answer to the objective's core question: no threshold, logic rule, risk rule or
processing limit is systematically blocking tradeable candidates.** Dense observation converts at
**7.02%** (37 of 527) against **0.39%** overall — an 18× difference — so the system is not failing
to convert what it can see, it is failing to give candidates enough observation to be judged.

That constraint is a **user-decided budget item** (increase declined round 79; partial increases
approved rounds 83 and 88) and has not been changed.

## 4. What remains, honestly

- **The binding constraint is not mine to change.** It was offered, declined once, and partially
  approved twice; the completed evidence base is now the deliverable on that point.
- **Six forward experiments are in flight** (`exit150_*`, `activity_floor150_*`, `runup_floor150_*`).
  None is readable yet; `exit150_full15_v1` is closest at 17 of 20 settled and is positive per
  position. Their verdicts need wall-clock time, not more analysis.
- **Everything else in my authority was either shipped or closed by measurement.** Four entry-floor
  arms and two full-capture exit arms were added across rounds 17–20; the adaptive observation
  cadence landed in round 22; the readout tool in round 23.

## 5. What this round did NOT do

- Did not change the watch budget, slot count, lease durations, or the native lane.
- Did not modify any production source.
- Did not promote, pause or retune any arm.
- Did not read the forward experiments as verdicts.

## 6. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (17 now). Realised PnL per position; decompose
   any write-off claim into full-loss versus partial (round 27 rule).
2. **P0 — keep the experiments running.** They are the only source of new information now, and
   they need time.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24).
4. **Standing note for any entry-feature query:** state which lane it covers. A join on
   `entry_snapshot_id` silently excludes the native lane.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion search (r26), quoting a write-off
   rate as a loss rate (r27), the capital hypothesis (r28), slot turnover (r29), or the
   dense-episode-free lane (r30).

## 7. Probe artifacts

`data/research/diag_round120/`, read-only: `r30_undensed_lane.py`, `r30b_native_evidence.py`.
