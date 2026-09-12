# ROUND 120-29 RECORD — slot turnover closed as a lever; the bottleneck stated precisely at last

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The lever I went looking for, and why it is not one

Round 28 closed capital, concurrency and the pending-intent throttle and left **slot turnover** as
the remaining no-budget candidate: `replaceable_early` evicts only `bucket == "early"` leases, so
growth/mature leases squat their full `PHASE_LEASE_SECONDS = 300`, and with ~30 slots the ceiling
is roughly `30 × 3600/300 = 360` dense pools/hour.

The premise was that a slot held for 300 s is mostly idle after the interesting frames arrive.
**That premise is false**, measured on 7,964–8,595 reconstructed observation episodes (observer
snapshots, same token, gaps ≤ 60 s):

| | |
|---|---|
| episodes | 7,964 |
| **episodes with ≥3 frames** (the window minimum) | **863 (10.8%)** |
| episodes with exactly 1 frame | **6,184 (77.6%)** |
| median episode duration | **0.0 s** (one frame) |

**Time to the 3rd frame**, among episodes that reach it (n=1,019):

| | |
|---|---|
| p25 | 29.2 s |
| **p50** | **31.6 s** |
| p75 | 52.0 s |
| p90 | 65.1 s |

**A window is formed by ~32 s median and ~65 s at p90 — comfortably inside the 120 s early lease.**
So the lease duration is *not* what prevents window formation, and shortening it would buy nothing
there.

**And the late frames are not dead.** New-information rate (price AND volume AND liquidity all
changed) by elapsed time in the episode:

| band | frames | new-info | new-info % |
|---|---|---|---|
| 0–30 s | 2,788 | 310 | **11.1%** |
| 30–60 s | 1,806 | 471 | 26.1% |
| 60–120 s | 2,142 | 514 | 24.0% |
| 120–300 s | 4,154 | 724 | 17.4% |
| 300–600 s | 4,078 | 685 | **16.8%** |
| 600 s+ | 8,741 | 1,674 | **19.2%** |

After the first 30 s the rate is **flat at ~17–26% across every band**, and **2,359 new-information
frames arrive after 300 s**. Releasing slots earlier would therefore cut into genuinely informative
observation — **earlier release is not free.**

Note the 0–30 s band is the *poorest* at 11.1%: that is the round-21 over-polling signal, and it is
already addressed by round 22's adaptive cadence.

**Slot turnover is closed as a lever.** That is the third no-budget candidate eliminated by
measurement (after capital/concurrency in round 28, and the arm-fleet and token-exclusion lines in
rounds 25–26).

## 2. What the measurement did surface: the bottleneck, stated precisely

11,991 tokens have been observed. **Only 527 of them (4.4%) ever receive a ≥3-frame episode** — the
minimum needed to be judged at all. And the conversion rates differ by an order of magnitude:

| population | entered | rate |
|---|---|---|
| **all observed tokens** | **47 / 11,991** | **0.39%** |
| **densely observed (≥3 frames)** | **37 / 527** | **7.02%** |

**Dense observation converts at 18× the overall rate.** So the system is *not* failing to convert
candidates it can see — it is failing to **give candidates enough observation to be judged**. 95.6%
of observed tokens never get a third frame, and 77.6% of observation episodes consist of a single
sample that can never form a window.

**Caveat, stated because it bounds the claim:** 11 of the 48 entered tokens never had a ≥3-frame
episode, so dense observation is the dominant route (77% of entries) but not the only one. A
different lane reaches entries without it.

## 3. Why this is the answer to the objective's core question

The objective asks which link systematically blocks tradeable candidates through over-strict
thresholds, logic or risk rules. The measured answer is: **none of them.** Over 28 rounds, every
threshold, risk rule, capital limit, concurrency cap, throttle, processing limit, arm-fleet
property and token-selection rule has been tested and eliminated:

| link | status |
|---|---|
| discovery / collection / features | healthy |
| processing speed | not binding — p50 0.18 s observed→position |
| freshness rules | not binding — 0.03% of evaluations |
| signal generation | not binding — mechanisms fire amply |
| arm fleet | not redundant, not prunable (r25) |
| token-level exclusion | unvalidatable, and unnecessary (r26) |
| capital / concurrency / pending intents | not binding (r28) |
| slot turnover / lease duration | not a lever (r29) |
| **dense-observation coverage** | **THE BINDING CONSTRAINT — 4.4% of observed tokens** |

It remains a **user-decided budget item** (increase declined round 79; partial increases approved
rounds 83 and 88), and this round did not change it.

## 4. What this round did NOT do

- Did not change the watch budget, slot count, lease durations, or `replaceable_early`.
- Did not modify any production source.
- Did not promote, pause or retune any arm.
- Did not read the forward experiments as verdicts (`exit150_full15_v1` still at 17 settled).

## 5. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (17 now). Realised PnL per position; decompose
   any write-off claim into full-loss versus partial (round 27 rule).
2. **P0 — the 11 entries without a dense episode.** 23% of entries arrive by a route that never
   forms a 3-frame window. If that lane can be widened it is a coverage route that does **not**
   need the observation budget, which makes it the most promising remaining lead. Identify which
   lane produces them and why it converts.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24).
4. **Do NOT** re-open: arm pruning (r25), token-level exclusion search (r26), quoting a write-off
   rate as a loss rate (r27), the capital hypothesis (r28), or slot turnover (r29).

## 6. Probe artifacts

`data/research/diag_round120/`, read-only: `r29_frame_arrival.py`, `r29b_conversion.py`.
