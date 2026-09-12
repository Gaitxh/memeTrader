# Round 120-6 record — three more hypotheses killed by measurement; the coverage bottleneck is watch capacity, not continuity

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r6_*.py`. No production behaviour changed.

This round set out to fix coverage, which is the user's oldest and most repeated complaint. It
ended by **eliminating three candidate causes and locating the real one**, with none of the three
turning into code. Two of the three were my own hypotheses; one was a bug in my own probe.

---

## 1. REFUTED — "the engine's 30-second freshness rule silently drops frames"

`dex_trajectory.Engine.accept` refuses any row with `(now - observed_at) > 30 s`. The previous
session measured the market-frame ingest hop at p99 **27.30 s**, i.e. just under that bound, which
made "slow ingest races the admission window" a plausible throughput defect.

**Measured here — the ingest is fast and the rule drops almost nothing:**

| `observed_at -> recorded_at` | rows (20 min) | share |
|---|---|---|
| ≤1 s | 3,874 | 63.1% |
| 1–5 s | 1,563 | 25.5% |
| 5–15 s | 451 | 7.3% |
| 15–30 s | 248 | 4.0% |
| **>30 s** | **1** | **0.0%** |

Engine refusal ratio is **12.2%** (238 refusals / 1,944 attempts), and `invalid_or_unknown`
covers every refusal reason, not just freshness. **No change made.**

## 2. REFUTED — "the 30-second gap tolerance is what starves the window logic"

`Engine.MAX_GAP_SECONDS = 30` clears a pool's whole series on a >30 s gap, and
`dex_trajectory.window()` independently rejects any window containing a >30 s gap. I measured
`gap_reset` on **558/1,939 = 28.8%** of frames against **28.3%** of observed intervals exceeding
30 s — a near-exact match that looked causal, and I was ready to build a cadence-aware engine.

**Measured here — the densely observed pools are fine:**

| pool | frames (30 min) | gap p50 | gaps ≤30 s | window verdict |
|---|---|---|---|---|
| `solana:JQWYyzQ9…` | 528 | **2.0 s** | 99% | **passes** |
| `bsc:0x64a6c4c1…` | 495 | **1.5 s** | 98% | **passes** |
| `bsc:0xd69c4032…` | 241 | **2.5 s** | 97% | **passes** |
| `bsc:0xc80e36a2…` | 180 | **2.4 s** | 98% | **passes** |
| `bsc:0x1863282521…` | 343 | 2.7 s | 96% | fails on span 58 s > 40 s |
| `bsc:0xf88377de…` | 324 | 1.4 s | 97% | fails on gap **30.2 s** vs 30 s |

4 of 6 pass, and both failures are marginal (0.2 s over the gap; span 58 s vs 40 s). Every pool
can physically form a 30 s window (two smallest gaps sum to 0.7–1.4 s).

**So the 28.8% `gap_reset` comes from the SPARSE pools, not the watched ones.**
`window_ready:30` = 48.7% is a per-frame average across all frames, most of which belong to pools
observed once or twice. **A cadence-aware engine built on a larger `MAX_GAP_SECONDS` would unlock
nothing** — and widening only the gap tolerance cannot help anyway, because the window's
**≤40-second SPAN** requirement is the binding constraint, not the gap. Changing the span changes
what `return_fraction`, `acceleration` and `volatility` *mean*, so it would require **new
mechanism kinds calibrated on the new features**, not merely new arms on the old ones.
**No change made.**

## 3. REFUTED — my own probe's "0 of 18 pools can form a window"

An intermediate version of this analysis returned **0/18 pools passing at every gap tolerance
up to 300 s**, which would have been a dramatic finding. It was **my bug**: the query filtered
`provider LIKE 'dexscreener%'`, which excludes the `strategy-observer:dexscreener` mirror rows and
left too few frames per pool for the span test to be meaningful. The clean re-measurement above
supersedes it.

**Recorded rather than deleted**, because "0 of 18" is exactly the shape of result the previous
session's query-discipline rule exists for ("any '0 samples / stalled / defect' claim must be
confirmed with a second independent measure before publishing"). The rule caught my own error.

## 4. CONFIRMED — the bottleneck is how many pools get dense observation

The system observes the pools it selects **very well** (1.4–2.7 s median cadence) and everything
else roughly once. That is a direct consequence of the observation lease design:

* `observation_leases145`: 30 slots (3 chains × {early 3, growth 4, mature 3}), `TARGET_SECONDS=15`
* `mover_watchlist`: `MAX_WATCHED=24`, `WATCH_SECONDS=900`
* watch occupancy is at capacity: `watched=34`, `sampled≈15–19`; `mover_watching=24` = its cap
* feed to the engine: ~1,939 accepted frames over ~2.2 h, against ~8,900 snapshot rows/hour

So the token-level signal rate of **0.38%** (10 of 2,641 evaluated tokens reach any arm) follows
from the number of pools that can be observed densely, **not** from a continuity, freshness or
mechanism-threshold defect. The mechanisms themselves fire amply: `deep_pool_flow` 370 ready,
`nonbsc_flow` 250, `mid_band_flow` 227, `righttail_lottery` 538.

This is a **capacity** lever, and the previous session's record shows the user has already made
the relevant calls on it (round 79 declined an increase; round 83 approved +14% requests; round 88
approved 8 reserved watch slots). **It is not a defect to fix silently.**

## 5. What this changes for the next round

| # | action | why |
|---|---|---|
| **P0-1** | Do **not** build a cadence-aware engine on a wider `MAX_GAP_SECONDS`. If window semantics are ever changed, it must be a new engine **plus new mechanism kinds** calibrated on the new features, because `span` defines what the features mean | §2 |
| **P0-2** | The only remaining coverage lever is watch capacity / which pools get selected. Evidence for selection quality: BSC tokens are **55.6% dead** here (5/9) vs Solana **0.0%** (0/8); the good depth bands already hold 54.2% of mover slots | round-120-5 §3, §1 |
| **P0-3** | Let EXIT150 accumulate forward samples; the hard stop is the second loss engine (**-933.25U** all-time) and `widestop` targets it | round-120-5 §4 |
| P1-1 | `feature_json` ≈ 38.6 KB per evaluation row | old session seq 15634 |

## 6. Method note

**Four hypotheses have now been killed by measurement across rounds 120-5 and 120-6** (observation
depth budget; mark supply; frame freshness; gap tolerance) and **one of them was a bug in my own
probe**. None produced a code change. Every one of them would have looked like a reasonable,
plausible fix. The cheap second measurement is what stands between this project and a forward
epoch full of uninterpretable evidence, and it is worth stating plainly that the ratio of
refuted hypotheses to shipped changes this round is 4:0 **by design, not by inactivity**.
