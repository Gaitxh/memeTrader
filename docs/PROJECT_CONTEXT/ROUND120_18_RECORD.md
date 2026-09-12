# ROUND 120-18 RECORD — the +15% predictor is an artifact; the real loss is one filterable population

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). All work in this round is read-only measurement.

## 0. What this round set out to do

Round 17 closed the exit side and produced a large-sample point-in-time label: **did a
position touch +15% econ?** (241 of 906). The plan was to find entry-time features that
predict it, and ship an entry-quality arm. The first half of that plan is now
**falsified**, and the search found something better.

## 1. The join had to be measured, not assumed

A previous round silently matched 0 of 1,112 rows. So every candidate key was measured:

| key | match |
|---|---|
| `shadow_cohort_id` → `v6_cohorts.id` | **1098 / 1098** |
| `source_entry_fill_id` → `v6_entry_fills.id` | 1091 / 1098 |
| `entry_snapshot_id` → `token_snapshots.id` | 1091 / 1098 |
| `entry_fill_id` → `v6_entry_fills.id` | **0 / 1098** (silently empty — the trap) |

Point-in-time market features live in `token_snapshots` at `entry_snapshot_id`
(liquidity, market cap, 5m volume, buys/sells, buyers, holders, taxes, honeypot).
Rich per-arm vectors in `cohort_signals[].decision_evidence.feature_vector` are **no
longer usable historically** because round 120-9 compacted them to 3 fields.

## 2. FALSIFIED: entry-time features predict the +15% touch

Position level (1028 positions, 298 touched) looked strong:

| feature | touched | never | ratio | |
|---|---|---|---|---|
| mcap | 26,100 | 149,100 | 0.18 | **separated** |
| mcap_liq | 0.62 | 3.44 | 0.18 | **separated** |
| sells | 0 | 45 | 0.00 | **separated** |
| trades | 11 | 128 | 0.09 | overlapping |

Read naively this says "enter quiet, small pools". **It does not survive.**

**2a. Within tokens it is exactly zero.** The per-token medians are *literally identical*
(`bsc:0x1853979987…` mcap 27,377 / 27,377; trades 11 / 11) because positions are projected
from a cohort = (token, snapshot) × many arms, so they **share one feature vector**. The
correct unit is the cohort. At cohort level (167 cohorts, 7.3 per token, features do vary)
the separation returns — but:

**2b. Within-token rank correlation is 0.000 for every feature.**

| feature | tokens | median rho | negative | positive |
|---|---|---|---|---|
| trades | 20 | **0.000** | 5 | 5 |
| sells | 14 | 0.000 | 2 | 4 |
| liq | 20 | 0.000 | 10 | 0 |
| mcap | 20 | 0.000 | 10 | 0 |
| vol5 | 20 | 0.000 | 5 | 5 |

**2c. Direction inverts when the 5 luckiest tokens are removed**: trades 0.12 → **1.22**,
sells 0.09 → **2.04**, and mcap ratio → **1.00**.

**2d. Token-clustered bootstrap on the "quiet pool" effect: CI [−0.127, +0.297], does not
exclude zero.**

**2e. Economically it points the other way**: quiet pools **−12.57U/position** vs busy
**−4.25U/position**.

So: **the +15%-touch separation is an artifact of which tokens were picked, not a usable
entry filter.** This kills the originally-planned build before it was built.

## 3. The real finding: one filterable population is 69% of the loss

Sweeping a floor on the entry snapshot's own activity (`trades = buys_5m + sells_5m`,
`vol5 = volume_5m_usd`) exposes a collapse in the **death** rate:

| floor | positions kept | write-off rate |
|---|---|---|
| none | 1035 | **34.8%** |
| trades ≥ 10 | 944 | 36.2% |
| **trades ≥ 30** | 571 | **6.0%** |
| vol5 ≥ 3,000 | 516 | 14.1% |
| vol5 ≥ 10,000 | 404 | 8.4% |

Token-clustered bootstrap on the per-position gain from `trades ≥ 30`:
**+9.73 U/pos, 95% CI [+3.93, +14.17] — excludes zero.**

**Chain-stratified (this is the mechanism):**

| population | n | write-off | U/pos |
|---|---|---|---|
| bsc, < 30 trades | **404** | **78.6%** | **−15.39** |
| bsc, ≥ 30 trades | 132 | 7.6% | −4.75 |
| solana, < 30 trades | 55 | 0.0% | −2.67 |
| solana, ≥ 30 trades | 352 | 6.8% | −4.43 |

Baselines: bsc 547 pos / 61.4% write-off / −12.82 U/pos; solana 407 / 5.9% / −4.19;
robinhood 93 / 0.0% / −2.97.

**The 404 low-activity BSC positions alone are −6,218U of the epoch's −8,990U loss
(69.2%).** Total loss is concentrated in a single identifiable, filterable population.

Correction I had to make to my own reading: it is tempting to say "the floor hurts Solana
because kept −4.43 is worse than dropped −2.67". That is the wrong comparison. Removing a
set that loses −2.67U/pos *improves* the book by +147U, so the floor helps **both** chains
— enormously on BSC (+6,394U) and modestly on Solana (+148U).

## 4. Both validated levers, combined

| configuration | positions | total | U/pos |
|---|---|---|---|
| actual (no floor, no TP) | 1,041 | −8,990.05 | −8.64 |
| TP only (round 17) | 1,041 | −3,743.41 | −3.60 |
| floor only (trades ≥ 30) | 575 | −2,462.54 | −4.28 |
| **floor + TP** | 575 | **−2,162.84** | −3.76 |
| best (vol5 ≥ 50,000 + TP) | 275 | **−506.00** | −1.84 |

They **partially overlap** rather than add (5,247 + 6,528 ≠ 6,827): the floor removes many
positions the take-profit would otherwise have rescued.

Best case is a **94.4% loss reduction (−8,990U → −506U)** — but token-clustered bootstrap
gives **95% CI [−1,429, +141]** and **P(profitable) = 12.9%**. It still loses, and the
residue is concentrated (1 of 7 traded tokens is −250U).

## 5. Why the existing defence does not bite

The system *does* already have activity floors — 296 numeric entry gates across the
registered arms, consumed at `revision_evidence_extensions.py:279`:

```python
trades = last["buys"] + last["sells"]
if trades < float(cfg.get("min_trades", 0)) or last["volume"] < float(cfg.get("min_volume", 0)):
    return False, "replacement_activity_not_met"
```

`last["buys"] + last["sells"]` is **the same quantity measured above**. But the configured
floors sit at `min_trades` **4–12** and `min_volume` **300–1200** — and the transition is
between **10→20 trades** and **1,000→3,000 volume**. **The existing floors are calibrated
exactly in the band where they do nothing** (sweep: trades ≥ 10 → −8,438U vs −8,990U
baseline, i.e. +552U of a possible +6,528U).

**Structural root cause:** those floors live on `evidence_extension_l0` arms that produce
**1–2 positions each**. The 1,409 positions actually held come from **154
`isolated_cohort_observer` arms whose entire `entry_filter` is**
`{direction, max_concurrent_positions: 2, single_token_lifetime_entry: True}` — **no
activity gate at all.** The system trades cohort signals with zero activity screening.

Funnel reasons confirm where judgement sits (evaluations, this epoch):
`cohort_observation` 11,667 · `no_active_matching_entry_policy` 9,166 ·
`pattern_observation` 7,555 · `entry_pool_liquidity_absent_curve_stage` 2,714 ·
`invalid_exact_asof_market_snapshot` 1,807 · `entry_pool_liquidity_below_configured_floor`
1,055 · `entry_pool_liquidity_unknown` 396 · `entry_snapshot_too_old` 12.

## 6. The additive hook (located, not yet used)

`store.py:27832-27850` is the cohort acceptance loop; each qualifying policy's signal is
committed at `accepted_cohort_signals[arm] = signal`. A new arm can be screened there by
its own id, which is additive and reversible and touches no existing strategy:

```python
if not activity_floor150.allows(arm, snapshot):   # existing arms -> True immediately
    continue
```

The consistent precedent is `store.py:27951`
(`elif policy.get('entry_filter', {}).get('failed_impulse_cooling')`), which dispatches an
arm to its own module. **Not landed this round**: a new cohort arm only trades if the
cohort evaluator emits a signal for it (`store.py:27817` filters `cohort_signals` by
`by_arm`), which has not yet been verified, and landing an entry arm that silently never
fires — or fires wrongly — in a live paper system at the end of a round would violate the
incremental/reversible requirement.

## 7. Next actions

1. **P0 — land the activity-floor entry arm.** Verify the cohort evaluator emits signals
   for a newly registered `isolated_cohort_observer` arm, then add the module + the
   one-line screen. Levels from the measured write-off collapse, not from the PnL sweep
   (which is in-sample): `trades ≥ 30` and/or `vol5 ≥ 5,000`. Globally, since it helps
   both chains.
2. **P0-new — settle `exit150_full15_v1` / `exit150_full25_v1`** to ≥20 per side.
3. **P0-1** — re-run `paired_arm_ab.py` as settled counts grow.
4. **P1** — explain the residue: best combo still −506U with 1 token at −250U.
5. **Do NOT build** the "+15%-touch predictor" — §2.
6. P0-3 (evaluation write rate) stays background; ~46 days headroom, and it carries
   state-chain risk.

## 8. Probe artifacts

Under `data/research/diag_round120/` (gitignored), all read-only:
`r18_join.py`, `r18_features.py`, `r18_touch_predict.py`, `r18_within_token.py`,
`r18_cohort_level.py`, `r18_decisive.py`, `r18_busy_filter.py`, `r18_existing_gates.py`,
`r18_combined.py`, `r18_parent.py`, `r18_producers.py`, `r18_chain_falsify.py`.
