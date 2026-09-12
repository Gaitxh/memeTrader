# ROUND 120-21 RECORD — the observation budget is ~3.4× under-utilised

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. Why this round looked at the observation layer

Round 20 established the funnel: 10,089 discovered → 9,531 observed (94.5%) → **only 37
ever entered (0.4%)**, and that the binding constraint is observation capacity (~30 dense
watch slots), not a threshold rule. Widening the budget is a user-decided item (declined in
round 79, partly approved in 83/88), so the only legitimate move is to raise the *quality and
efficiency* of the slots that already exist.

## 2. Two hypotheses killed first

**Slot waste — killed.** The live `coverage145:status` state shows all 30 slots occupied
(bsc/robinhood/solana × 10), **11 of them held by open positions**, and only **4 of 30
(13%)** yielding ≤1 frame followed by `SOURCE_NO_UPDATE`. The budget is not being squatted.

**Dense-pool waste — mostly killed.** Of the 68 pools with ≥50 snapshots, **40 never produced
a position** — but they account for only 2,876 snapshots (7.3% of all observation). Real, but
not the lever.

## 3. The real defect: we poll at a fixed 15 s regardless of whether the source has anything new

`observation_leases145.record_frame` sets `next_due_at = observed_at + TARGET_SECONDS (15)`.
Measured over 13,651 consecutive same-token snapshot pairs (237 tokens with ≥20 snapshots):

| sample content | share |
|---|---|
| price **and** volume changed | 25.7% |
| volume only changed | 3.2% |
| price only changed | 0.3% |
| **NOTHING changed (price, volume, liquidity all identical)** | **70.8%** |

**70.8% of polled requests return no new information at all.** Consecutive no-information
runs: p50 3, p90 10, p99 31, max 55. Runs of ≥5 waste **7,834 polls**; runs of ≥2 waste 9,024.

**If cadence were matched to the source's real update rate, the same request budget would
cover ~3.42× more distinct pools** — with no budget increase and, by construction, no
information loss (a sample where price, volume *and* liquidity are all unchanged carries no
new information by definition).

**It is worst exactly where it matters.** The tokens we actually trade have a HIGHER
information-free repeat rate than the ones we never trade:

| population | tokens | p25 | median | p75 | share >80% repeats |
|---|---|---|---|---|---|
| **traded** | 31 | 77.3% | **82.2%** | 85.0% | 64.5% |
| never traded | 2,368 | 50.0% | 66.7% | 100.0% | 32.4% |

**30 of 31 traded tokens exceed 50% repeats; 20 of 31 exceed 80%.** The worst single case,
`bsc:0x64a6c4c1…`, took **1,085 snapshots at an 89.7% repeat rate** and produced 67 positions.

**21 dense pools recorded ZERO information change across 668 polls — and none of the 21 ever
produced a position.**

## 4. The accuracy question, and why it is NOT a defect

A repeat frame could be harmful if it counted as a trajectory frame and produced degenerate
features. `record_frame` rejects a frame only on `observed_at <= prior` — a *timestamp*
test, not a content test — and a live frame in the trajectory state shows
`observed_at == ingested_at == recorded_at` **exactly**, which indicates `observed_at` is our
receipt time. So repeats do advance the clock.

Measured in the live `trajectory144:state` KV (184 pools):

- 108 pools have `frames = 1` (a single frame — trivially one price, **not** evidence of repeats)
- **60 pools have `frames ≥ 3`** (a window is formable); **all 60 formed `window_30`**
- of those 60, **26 (43.3%) have ≤1 distinct price across their entire frame history**
- across the 60 eligible pools: **1,737 frames contain only 378 distinct prices — 78.2% of
  frames are repeats**

The distribution is cleanly bimodal — 26 pools with exactly 1 distinct price, ~20 with 18–22 —
so a pool is either static or genuinely active.

**I first computed "81% of pools have a single price" and caught that it was contaminated by
the 108 one-frame pools, for which the statement is trivially true.** The corrected figure is
26 of 60 eligible pools. Recorded because the first number would have overstated the defect
by ~2×.

**Containment verified — this is an efficiency issue, not an accuracy one:**

| population | pools | emitted a signal | positions | PnL |
|---|---|---|---|---|
| static (≤1 distinct price) | 26 | **0** | **0** | — |
| active (>1 distinct price) | 34 | 14 | 1,085 | −3,926.34 U |

The static pools also carry `phase = None` — the phase/flag machinery never engages on them,
so they cannot reach a decision. **Zero of 26 signalled.** There is therefore no accuracy
defect to fix, and no reason to touch the trajectory engine's frame handling.

Note also the engine's own accounting (`trajectory144:state → counts`) shows window formation
is healthy: **29,657 of 44,380 accepted observations (66.8%) produced `input_ready:window30`**,
14,723 `input_unknown:window30`. Window formation is not the leak.

## 5. What this implies, and what I deliberately did NOT do

The lever is **adaptive cadence**: do not re-poll a pool whose last sample was
information-free. Design constraints, all derived above:

1. back off **only** when price AND volume AND liquidity are all unchanged — volume-only
   changes are 3.2% of samples and are real information;
2. modest, capped backoff (e.g. 15 s → 30 s → 60 s cap) with **immediate reset on any change**,
   so the worst-case detection delay for a new move is one backoff interval;
3. it must not thin the *active* pools: 78.2% of frames are already repeats, so backing off
   only no-info samples should not reduce genuine frames — but this must be verified, not
   assumed, because the trajectory window needs ≥3 frames within 30 s and an over-aggressive
   backoff would destroy it.

**Not implemented this round, deliberately.** The observation supply is the highest-blast-radius
surface in the system: it feeds every arm at once, and six forward experiments
(`exit150_*`, `activity_floor150_*`, `runup_floor150_*`) are currently accumulating evidence
that a cadence regression would quietly corrupt. The design is fully specified above and the
containment evidence is in hand; it should land as its own change with its own verification,
not appended to a long diagnostic round.

## 6. Next actions

1. **P0 — adaptive observation cadence** per §5, with the three constraints. Success metric:
   distinct pools covered per hour at unchanged request volume, and no regression in
   `input_ready:window30` share (currently 66.8%).
2. **P0 — read the four floor families** against the shared control
   `alpha149_merged_multi_setup_fast_v1` once each side has ≥20 settled.
3. **P1 — exit150_full15_v1 / full25_v1** to ≥20 per side.
4. **Do NOT** build a "+15%-touch predictor" / "quiet pool" filter (round 18), re-report the
   4% "latency premium" (round 20), or treat the repeat frames as an accuracy defect (§4).
5. **Do NOT** widen the watch budget silently; it is a user decision.

## 7. Probe artifacts

`data/research/diag_round120/` (gitignored), read-only: `r21_slot_efficiency.py`,
`r21_coverage_state.py`, `r21_slot_waste.py`, `r21_overpolling.py`, `r21_safe_backoff.py`,
`r21_stale_or_polltime.py`, `r21_repeat_reach.py`, `r21_frames_vs_repeats.py`,
`r21_degeneracy.py`, `r21_degeneracy_fix.py`, `r21_containment.py`.
