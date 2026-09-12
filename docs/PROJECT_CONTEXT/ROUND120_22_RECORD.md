# ROUND 120-22 RECORD — adaptive observation cadence landed; and my 3.42x estimate was too high

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`).
Change: `7b40eb5` (pushed). **No existing strategy modified.**

## 1. What shipped

Round 120-21 measured that the observer polls each admitted pool every
`TARGET_SECONDS = 15` regardless of whether the source has anything new, and that 70.8% of
polls returned no change in price, volume or liquidity. This round makes the cadence
adaptive.

`observation_leases145.record_frame` gains an optional `content` parameter, and
`cadence_seconds` back off the next due time on an information-free sample:

| consecutive information-free samples | next poll |
|---|---|
| 0-2 | 15 s |
| 3-5 | 30 s |
| >= 6 | **60 s (cap)** |

All three safety constraints from the round-21 design are implemented and tested:

1. **Back off only when price AND volume AND liquidity are all unchanged.** A volume-only
   change (3.2% of samples) resets the cadence, because trading without a move is real
   information.
2. **Capped at 60 s with immediate reset on any change**, so the worst-case detection delay
   for a genuinely new move is one interval.
3. **`content=None` reproduces the previous fixed cadence exactly**, so the change is
   reversible per caller.

Durability and observability: `unchanged_run` is persisted through
`dump_state`/`restore_state` so a restart does not silently reset every backoff to the fastest
step; `last_content` is deliberately **not** persisted (after a restore the run restarts at 0,
the conservative direction). `bounded_summary` now reports `unchanged_run`, `cadence_seconds`
and `content_known` per opportunity.

8 new tests, plus the two dedicated observer regression suites
(`test_observation_leases145.py`, `test_observation_leases145_runtime.py`) and the related
suites all pass.

## 2. Verified live

Baseline captured **before** the restart (`cadence_before.json`), then two samples after.

| metric | before | after #1 | after #2 |
|---|---|---|---|
| observer snapshots / min | 187.2 | 189.8 | **183.3** |
| all snapshots / min | 260.0 | 270.9 | 258.8 |
| trajectory `accepted` | 47,226 | 51,486 | 53,336 |
| `input_ready:window30` | 32,251 | 36,138 | 37,865 |
| **ready share** | **68.291%** | 70.190% | **70.993%** |
| cadence values live | none | [15, 30, 60] | [15, 30, 60] |
| `content_known` | 0/30 | 30/30 | 30/30 |

The cadence is demonstrably live and gated: **24 slots at 15 s, 1 at 30 s, 5 at 60 s**
(unchanged runs up to 11), with `content_known 30/30`.

**Implied request cost across the 30 occupied slots: 120 -> 103-105 requests/min, i.e.
12.5-14.2% fewer requests for the same slots.**

**Coverage quality did not regress — it improved slightly** (68.29% -> 70.99% of accepted
observations producing a ready 30 s window), and one signal counter advanced
(`second_wave` 16 -> 18). The observer request rate is essentially flat (187.2 -> 183.3).

## 3. Correction: my round-21 "3.42x" estimate does not hold for the live slot population

Round 21 projected that matching cadence to the source's update rate would cover **~3.42x
more distinct pools**. The realised effect is **~12-14% fewer requests**, not 3.42x.

Why the estimate was too high — and it is a measurement-population error, not an
implementation shortfall:

- the 70.8% information-free rate was measured over **tokens with >=20 snapshots**, i.e. the
  dense-pool history. That population is dominated by pools that sat in a slot for a long
  time precisely *because* they were quiet or dead;
- **`volume_5m_usd` is a rolling 5-minute sum, so it changes on almost any trade.** Under the
  strictly-safe criterion (all three fields unchanged), the backoff only engages for pools
  with essentially no trading at all. The live slots show **median `unchanged_run` of 0-1**:
  most occupied pools *are* updating;
- therefore the correct statement is: 70.8% of samples in the dense history are
  information-free, but the **live slot population at any instant is mostly active**, so only
  a minority of slots can back off.

Also note the distinct-pool-per-bucket series is **strongly trending** (543 -> 939 -> 796 ->
612 -> 587 across the pre-change window), so a naive before/after comparison of distinct
coverage is confounded; with one partial post-change bucket there is **not yet enough data to
claim a coverage gain either way**. The honest position: the mechanism works, the quality
metric held, and the coverage claim is unproven.

A narrower criterion — backing off when *price* alone is unchanged — would engage far more
often, but it would also back off across volume-only changes (3.2% of samples) which are real
information. That trade is not worth taking without its own evidence, and the conservative
criterion stands for now.

## 4. Regression check on a shared path (the change touches every arm's data supply)

The full suite exceeds the command timeout and is **non-deterministic** — the same 6 files
gave 92 failures on a cold worktree and 30 on a warm one, for the same commit. So a raw
full-suite count cannot attribute anything.

The attribution was therefore done by **differential comparison against a pre-change
worktree** (`git worktree add --detach ..\_wt_pre7651640 7651640`):

| file | broken at PRE (7651640) | broken at POST (7b40eb5) |
|---|---|---|
| `test_wallet_observer_store.py` | 4 | 1 |
| **broken at POST but NOT at PRE** | — | **none** |

**No regression is attributable to this change.** The one remaining broken test
(`test_s06_same_opportunity_control_then_watched_candidate_each_buy_five`) is broken at both
commits — pre-existing, like the other known-broken suites in this repo.

The module's own suites all pass: `test_observation_leases145.py`,
`test_observation_leases145_runtime.py`, the new `test_observation_cadence.py` (8 tests),
`test_four_meme_observer.py`, `test_rediscovery_funnel.py`.

## 5. What this round did NOT do

- Did not modify, retune, pause or replace any existing arm.
- Did not change any stop, hold or exit contract.
- Did not widen the watch budget (a user decision).
- Did not claim a coverage gain from one partial post-change bucket.
- Did not touch the trajectory engine's frame handling — round 21 verified containment
  (26 static pools: 0 signals, 0 positions), so there is no accuracy defect there.

## 6. Next actions

1. **P0 — re-measure distinct-pool coverage** once >=6 post-change 10-minute buckets exist, and
   compare against the *trend*, not a flat average. Success = more distinct pools per hour at
   unchanged request volume.
2. **P0 — read the four floor families** against the shared control
   `alpha149_merged_multi_setup_fast_v1` once each side has >=20 settled.
3. **P1 — exit150_full15_v1 / full25_v1** to >=20 per side.
4. **Do NOT** assume the 3.42x figure (see section 3); do not build a "+15%-touch predictor" or
   "quiet pool" filter (round 18); do not re-report the 4% "latency premium" (round 20).

## 7. Probe artifacts

`data/research/diag_round120/`, read-only: `r22_cadence_metric.py`,
`r22_distinct_coverage.py`, `r22_cadence_dist.py`, plus `cadence_before.json`,
`cadence_after1.json`, `cadence_after2.json`.
