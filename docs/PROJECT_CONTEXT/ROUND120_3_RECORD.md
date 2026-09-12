# Round 120-3 record — EXIT150: reachable staged take-profit ladders as NEW exit-carrier arms

Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Registration frontier
**`activation_snapshot_id = 15928`** (evaluation 15927), registered 2026-09-12T20:20:17Z.
Deployed by supervised restart at 20:20:11Z. Prior records: `ROUND120_RECORD.md`,
`ROUND120_2_RECORD.md`.

This round addresses the user's explicit §2 requirement (exit-mechanism rebuild for
"金狗拿不住") and the single largest measured money leak. The governing constraints for this
phase are unchanged: **forward simulation, no future functions and no future-data leakage**,
and **existing strategies must never be modified or replaced — improvements arrive only as
additional strategy modules.**

---

## 1. What was wrong (all measured on this epoch, 350 positions)

Every figure below is read from marks observed **strictly after** each position opened, so no
later mark can influence an earlier decision.

| measurement | value |
|---|---|
| per-position peak economic return | p10 -7.4% · p25 -1.3% · **p50 +22.7%** · p75 +32.8% · p90 +34.8% · **max +55.0%** |
| positions reaching +10% econ | 227/347 = **65.4%** |
| positions reaching +20% econ | 177/347 = **51.0%** |
| positions reaching +30% econ | 111/347 = **32.0%** |
| positions reaching +45% econ | 4/347 = **1.2%** |
| positions reaching +60% econ | **0/347 = 0.0%** |
| configured first take-profit tier | **+80%** (the one tiered arm used +100%) |
| `next_tp_index` on every position | **0** |
| `principal_recovered` on every position | **0** |
| `remaining_quantity_tokens > 0` on closed positions | **0** |
| total give-back | **4,508.94 USD** |
| hard stops | 92, of which **44 fired within one minute** |
| `hard_stop_return = -0.20` econ implies | a **-13.3% price move** |
| the pools' own 30-second move | p90 **9.49%** · p95 **18.65%** |
| `hard_stop_liquidity_veto_usd` set on | **0 / 92** arms (all 92 stopped in pools holding ≥69,937 USD) |

**Two independent defects:** the ladder's first tier sits 1.8× beyond the maximum return the
instruments ever produced (so it fired zero times and no profit was ever banked), and the stop
sits **inside** ordinary 30-second noise.

## 2. What was built — `src/memetrader/exits150.py`

Three **exit-carrier arms**. The alpha149 engine already implements the carrier contract: the
signal loop emits entries from `SPECS` only, and then

```python
carrier = next((arm for arm in SPECS if arm in output), None)
if carrier and surface == 'primary':
    for arm in EXIT_ARMS:
        signal = deepcopy(output[carrier]); output[arm] = signal
```

so each new arm receives **exactly the same frozen entry signal** as whichever entry arm fired
first on that pool. **Every existing arm is therefore the matched same-signal control**, and
only the exit contract differs. No existing arm is modified, retuned or replaced.

| arm | first tier | ladder | hard stop | trail | hold |
|---|---|---|---|---|---|
| `exit150_bank15_v1` | **+15% / 50%** | +15%/50%, +30%/40%, +55%/50% | **-0.35** | .30/.35 | 90 min |
| `exit150_bank25_v1` | **+25% / 50%** | +25%/50%, +45%/40%, +70%/50% | **-0.35** | .35/.35 | 90 min |
| `exit150_widestop_v1` | **+15% / 50%** | +15%/50%, +30%/40%, +55%/50% | **-0.55** | .30/.45 | 180 min |

Each arm varies exactly one thing: `bank15` vs `bank25` isolates **where to take the first
profit**; `bank15` vs `widestop` isolates **how wide the stop should be**. A ~15% moonbag
remains after the last tier and rides the trailing stop, so a runner is never fully sold.

Both conclusions are **falsifiable in forward data**, which is the point: the existing arms
keep exiting at -13.3%-ish with no ladder, so the comparison is live and simultaneous.

### Design choices that were deliberately constrained
* **Not added to `SPECS`.** Every pre-existing exit carrier (`alpha149_vol_scaled_exit_v1`
  and the other 11) lives in `EXIT_ARMS` only. Adding one to `SPECS` would give it its own
  entry gate — a different *strategy*, not an exit-only comparison.
* **`feature_hypothesis` stays `uncrowded_first_frame`**, exactly matching the registered live
  exit carriers, so feature routing is unchanged.
* **`trajectory_exit` is `None`.** The market-mark hard stop is evaluated *before* the
  trajectory-exit branch and preempts it, so a ladder-based arm must not depend on that branch.
* **The policy body is cloned from this epoch's own registered exit carrier**, not rebuilt, so
  the appended arm carries the live schema (`entry_match_mode: isolated_cohort_observer`,
  `entry_gate: cohort_strict_forward_asof`, `required_inputs`, `trajectory_rules`) rather than
  a re-invented one.
* **`notional_usd = 1.0`**, `paper_only`, `decision_eligible: true`, `assessment_status:
  INSUFFICIENT` — a bounded hypothesis, not a promoted strategy.

## 3. Verification

* `tests/test_exit150.py` (11 tests) + `tests/test_alpha149.py` + `tests/test_pool_concentration.py`
  + `tests/test_dex_start_gate.py` + `tests/test_dust_read_guard.py` → **85 passed**.
* Registration confirmed at a **true forward frontier** (`activation_snapshot_id = 15928`, not
  the legacy `0`): 316 → 319 policy additions.
* **Existing arms provably untouched** — `alpha149_vol_scaled_exit_v1`
  `d7b2084ffe293867`, `alpha149_merged_multi_setup_v1` `3029187564e9c2f1`,
  `alpha149_confirmed_stop_steady_v2` `20460e412abb69a2`, all with the same
  `take_profit=[]` and the same stops as before.
* Arms loaded into the running manifest (446 policies), liveness confirmed
  (snapshots/marks/evaluations all current), and **all three arms already hold a position** —
  the carrier mechanism delivered the same opportunity to each, as designed.
* One honest discrepancy: `tests/test_alpha149.py` asserted a blanket "every `EXIT_ARMS` entry
  has `trajectory_exit == EXIT_ARMS[arm]`". That assumption held only for the original 12
  carriers. It is replaced by the stronger real invariant — **every exit arm declares exactly
  one exit mechanism** (`trajectory_exit` xor a non-empty `take_profit`), never both.

## 4. ⚠️ Evidence status — read before using any number above

* The counterfactual replay is **causal**: marks read in ascending `observed_at`, filtered to
  strictly after each position's own open, exiting at the **first** triggering mark.
* The **choice among the ladders is in-sample** on one 87-minute window. It is a hypothesis to
  be judged **only** on data observed after `activation_snapshot_id = 15928`.
* Nothing here may be promoted on the strength of the window that motivated it. Promotion
  requires forward samples of the same signal with the new exit contract, compared against the
  existing arms' simultaneous forward results.
* `max_concurrent_positions` registered as **2** (inherited from the live carrier template),
  not the 4 declared in the module. The append-only ledger cannot be updated, and 2 is the more
  conservative bound, so it stands as registered. Recorded here so the difference is not
  mistaken for a bug later.

## 5. Next round

| # | action | why |
|---|---|---|
| P0 | Let EXIT150 accumulate forward samples; build the causal **out-of-sample** review that compares each EXIT150 arm against the same-signal existing arms | this is the only way the ladder hypothesis can be settled |
| P0-4 | **Owner decision:** the 126 paused base arms / the funding-activation registration | the v6 enrollment lane still admits nothing structural (3,718/3,718 `no_active_matching_entry_policy`) |
| P0-3 | Cadence-aware trajectory engine + new arms | unblocks 489,718 arm-instances blocked at `await_distinct_dex_trajectory_frame` |
| P1-1 | Index `(definition_version, evaluated_at, id)`; stop writing 67 KB of JSON for observation-only rows | 30–358 ms → ms; ~235 MB and ~50% of write pressure |

## 6. Uncommitted-file note

`src/memetrader/store.py`, `runtime.py`, `collectors.py` and `alpha149.py` each carry this
round's changes **and** pre-existing uncommitted changes from earlier rounds. Only the new
module, the new tests, and this record are staged.
