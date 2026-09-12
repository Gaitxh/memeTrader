# Round 120-5 record — two of the cross-session priorities do NOT transfer to this device

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Runtime restarted
20:29:46Z (per-pool cap reverted to opt-in). Scripts: `data/research/diag_round120/r4_*`, `r5_*`.
Prior: `CROSS_SESSION_SYNTHESIS_20260913.md`, `..._APPENDIX_A_20260913.md`.

The point of this round was to act on the three priorities the cross-session synthesis raised.
**Two of the three were refuted by measurement before any code was changed.** That is the
result, and it is worth more than the changes would have been: the old session's numbers come
from a 39 GB database with 3,286 positions/day, and this device's fresh epoch has a materially
different bottleneck profile.

---

## 1. REFUTED — "observation budget is spent in the wrong depth band"

**Old session (3 windows, token level):** first-observation depth 20k–100k reaches ≥2× 19.2% of
the time (1.75× lift), 1k–5k reaches 3.1% (0.36×), "and we spend most budget on 1k–5k".

**Measured here — the slot mix is already majority-good:**

| current depth band | watch slots | share |
|---|---|---|
| <1k | 5 | 20.8% |
| 1k–5k | 3 | 12.5% |
| 5k–20k | 3 | 12.5% |
| **20k–100k** | **6** | **25.0%** |
| **≥100k** | **7** | **29.2%** |
| **good bands (≥20k) total** | **13 / 24** | **54.2%** |

Supply is not the constraint either: **1,958 frames in 20k–100k and 1,477 in ≥100k per 30
minutes.** The `1k–5k` band holds 12.5% of slots, not "most".

Structural note worth keeping: `mover_watchlist.admission()` gives 20k+ a *stricter* condition
(buy share ≥ 0.6) than 1k–20k (turnover > 1.0), so the good band is admitted on stricter
evidence while already holding the majority of slots. **No change made.**

## 2. REFUTED — "marks are the scarce resource; fix mark supply before adding exit rules"

**Old session:** 46 marks per 15 minutes against ~90 open positions, so trailing / depth-decay /
signal-decay exits rarely resolve.

**Measured here — supply is ample:**

| window | mark_history rows | `marks` rows | pool_marks rows | opened | closed |
|---|---|---|---|---|---|
| 5 min | 663 | 23 | 167 | 68 | 23 |
| 15 min | **1,706** | 77 | 243 | 113 | 72 |
| 60 min | 2,650 | 109 | 436 | 170 | 106 |

* 15-minute window is **37× the old session's 46**.
* **494 of 518 positions (95.4%) received more than one in-window mark.**
* Of 97 open positions: **0 have zero marks**, 3 have one, 18 have 2–5, 22 have 6–20,
  **54 have >20**.
* Marks are continuous across the window (20:17:36Z → 20:32:33Z) and cover 243 distinct tokens.

**No change made.** Note `chain_meme_trader_marks` (77 in 15 min) is the per-arm *exit intent*
table and is a much smaller number — that is a different object from per-token mark supply and
must not be conflated with it.

## 3. CONFIRMED and stronger — the chain-level death stratification

| chain | tokens traded | dead | death rate | old session |
|---|---|---|---|---|
| **BSC** | 9 | **5** | **55.6%** | 40.4% |
| **Solana** | 8 | **0** | **0.0%** | 3.4% |
| Robinhood | 1 | 0 | 0.0% | 0.0% |

By entry depth band (tiny samples, flagged as such):

| band | tokens | dead | rate |
|---|---|---|---|
| 20k–100k | 7 | 5 | **71.4%** |
| ≥100k | 4 | 0 | 0.0% |
| lt5k | 2 | 0 | 0.0% |
| 5k–20k | 1 | 0 | 0.0% |

**The depth ordering does NOT reproduce**: the band the old session called safest-but-unreachable
sits at 71.4% here while ≥100k sits at 0%. With n = 7 and n = 4 these are not conclusions, but
they are strong enough to forbid acting on the old ordering. **What does hold, on both devices,
is the chain split: BSC carries essentially all the pool-death risk.**

**The arms for exactly those tiers already exist, are registered, are NOT paused, and are
trading** — `alpha149_nonbsc_flow_v1` (2 positions), `alpha149_deep_pool_flow_v1` (3),
`alpha149_mid_band_flow_v1` (5). So this is **not** an arm-availability problem and building
another redundant arm would change nothing; the constraint is signal supply to those arms.

## 4. This device's loss structure (all-time for the epoch)

| exit reason | n | PnL U |
|---|---|---|
| `dex_pool_liquidity_below_configured_floor_writeoff` | **177** | **-3,540.00** |
| `market_mark_hard_stop` | **136** | **-933.25** |
| `market_mark_max_hold` | 55 | -13.97 |
| `trajectory144_price_activity_liquidity_decay` | 16 | -32.82 |
| **`market_mark_trailing_exit`** | **9** | **+43.06** |
| `alpha149_plateau_stall` | 5 | +9.24 |
| everything else (9 reasons) | ~30 | ≈ -53 |
| **total** | ~518 | **≈ -4,091.68** |

**Two engines produce the whole loss: genuine pool deaths (-3,540U, 86.5%) and the hard stop
(-933U, 22.8%). Every other exit combined is about +380U.**

The hard stop is the engine EXIT150's `widestop` arm targets (its `-0.55` economic stop is
≈ -51% price, against the -13.3% price stop that fires inside the p90 30-second move of 9.49%).
That arm is live and needs forward samples, not more design.

## 5. Observation to watch (not yet a conclusion)

Hard stops went from 114 closes / -502.44U (2-hour window, read at 20:24:43Z) to 136 / -933.25U
(all-time, read at 20:32:33Z) — i.e. ~22 more hard stops and ~-430U inside about eight minutes.
The per-pool cap was reverted to opt-in at 20:29:46Z, so the two are adjacent in time. **This is
NOT attributed**: eight minutes cannot separate the cap's removal from the new pools simply
being volatile, and the cap had only been enforced for ~18 minutes in total. Recorded so the
next round reads it with a proper window rather than re-deriving it.

## 6. What this round actually changed

**No production behaviour changed except the round-120-4 revert already committed.** The
deliverable is the elimination of two priorities that would have consumed a round each, plus a
correction to the depth-band ordering that must not be acted on.

## 7. Priority list after this round

| # | action | evidence |
|---|---|---|
| **P0-1** | Contain BSC pool-death risk: the chain split is the only replicated entry-quality finding on both devices (BSC 55.6% here / 40.4% there vs Solana 0.0% / 3.4%). The non-BSC and ≥100k arms exist and trade but receive few signals — investigate signal supply to them, additively | §3 |
| **P0-2** | Let EXIT150 `widestop` and `bank15`/`bank25` accumulate forward samples; read with `paired_arm_ab.py` at ≥20 settled per side | §4; the hard stop is the second loss engine |
| **P0-3** | Token-level signal rate 0.38% remains the user's core complaint. The dense-vs-sparse observation finding (78.3% vs 4.0%) is the best-supported mechanism; the mover reservation already delivers 29.67 frames/token vs 1.00 for controls, so the next lever is the 30-slot watch capacity, not the reservation logic | CROSS_SESSION_SYNTHESIS §2.6 |
| P1-1 | `feature_json` ≈ 38.6 KB per evaluation row (≈7.6 GB/day on the old device; 250 MB here) — stop writing the full feature vector for observation-only rows | old session seq 15634 |
| P1-2 | Standing loop: `supervise_metrics.py` + `trade_context_ledger.py` + `paired_arm_ab.py`, counting by **independent cohort**, not per arm | user §2 |

## 8. Discipline notes

* Every depth/chain figure above is token level, with the token count shown. One dying pool is
  held by ~40 arms, so position-level counts would overstate every rate.
* The 20k–100k and ≥100k cells have n = 7 and n = 4. They are marked as not-conclusions.
* Two separate hypotheses were killed by measurement this round. Both would have produced
  plausible-looking code changes. **Measure before changing; the second independent
  measure is cheap and the cost of a wrong "fix" is not.**
