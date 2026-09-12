# Round 120 — Full-chain diagnosis: where the money actually goes

Runtime: `H:\OpenTrader\memeTrader_2`, DB `data/memetrader_forward.sqlite3`, epoch
`chain-meme-trader/funding-20260906-v002-final-1000`, window **2026-09-12T18:26Z → 19:53Z
(87 minutes)**, process restarted 19:19:25Z mid-window.

All figures below are measured from the live epoch. Design counterfactuals are labelled as
such and are **not** forward-proven results.

---

## 1. The money, in one table

| | positions | stake USD | realized USD | return |
|---|---|---|---|---|
| written_off | 169 | 3,380.00 | **-3,380.00** | -100% |
| closed (real exits) | 148 | 2,883.54 | -379.66 | **-13.2%** |
| open | 33 | 660.00 | 0.00 | — |
| **total** | **350** | **6,923.54** | **-3,759.66** | **-54.3%** |

**89.9% of the entire loss is 169 rows that are really 4 data reads on 4 tokens.**

Excluding those 4 tokens: **-220.11 over 92 positions / 1,840 USD deployed = -12.0%.**
The frozen round-trip cost is 4% buy slippage + 4% sell slippage + 60bps fee each side
≈ **9.2%**. So entry edge on this window ≈ **-3% before costs**.

---

## 2. Fatality #1 — concentration: 350 positions were ~11 independent bets

Every arm reads the same signal, so one accepted frame fans out across the whole book.

```
distinct tokens holding a position          11
positions per token   {1: 5, 30: 1, 55: 1, 57: 2, 65: 1, 81: 1}
largest single-token burst                  40 positions in ONE second
```

| token | positions | stake | written off | PnL |
|---|---|---|---|---|
| `bsc:0xd259a8f6…` | 81 | 1,620 | 7 | -350.26 |
| `bsc:0x0c886587…` | 65 | 1,300 | 59 | -1,159.09 |
| `robinhood:0x04d6aaa3…` | 57 | 1,140 | 0 | -212.83 |
| `bsc:0xb700d712…` | 57 | 1,140 | 54 | -1,066.74 |
| `bsc:0x4bd0ba7c…` | 55 | 1,100 | 49 | -963.53 |
| `solana:JQWYyzQ9…` | 30 | 600 | 0 | -1.53 |
| 5 more | 1 each | 4.71 each | 0 | ≈ -5.7 |

Chain split: **BSC 258 positions (74%) → 100% of the write-offs → -3,539.55 of -3,759.66
(94%)**. Solana 35 positions → **-7.20**. Robinhood 57 → -212.83.

All 350 positions sit on surfaces whose `token_market_surfaces.liquidity_control` is
`unknown`; the mandatory pre-trade rug contract
(`pretrade_rug_safety_registrations`) is registered **for Solana only**
(`"chain": "solana"`, `pumpswap/raydium-cpmm`) and produced **0 assessments**
(`pretrade_rug_safety_assessments = 0`). BSC entries therefore had **no LP-custody check at
all** — including `pool_creator = ''`, `lp_position_owner = ''`,
`canonical_status = 'not_applicable'`.

**Verdict: this is not an accounting bug and not a bad-data artifact.** An independent live
re-query of all four pools (DexScreener, at diagnosis time) confirms they are genuinely dead:
`liquidity.usd = 0` (one at 0.88), quote reserve 0.0032 USDT / 0.004 USDT / 0.0006 BNB,
`priceChange.h6/h24 = -100%`, `txns.m5 = 0/0`, `txns.h1 = 0/0`, price identical to the dust
print. **The write-off was correct.** The defect is that the system put 42 arms on each of
them.

> A parallel workstream inferred these prints were provider artifacts and costed a
> `COLLATE NOCASE` guard fix at "1,320 USD / 39% of the loss". **That impact claim is
> refuted**: the pools are really dead, and the guard's own price test
> (`price_now >= median_price * 0.5`) declines for a collapsed price even when the history
> query returns rows. The `COLLATE NOCASE` fix is still applied below as a correctness fix —
> the guard must be able to *see* the history — but it changes none of these four outcomes.

### Implemented fix (tested)
`src/memetrader/pool_concentration.py` + a guard in
`Store.settle_chain_meme_trader_execution_result`:

* `max_arms_per_pool = 8` (worst measured: 81)
* `max_new_arms_per_pool = 3` per settlement pass (worst measured burst: 40)
* Unknown pool identity → **fail open** (never block on missing data)
* `max_arms_per_pool: null` on a definition → byte-identical previous uncapped behaviour
* Refused intents are marked `failed` with reason `pool_cross_arm_concentration_cap`

Effect on this window: the four rug pools would have carried ≤8 arms (≈32 positions, ≈-640
USD) instead of 169 (≈-3,380 USD), and the ~160 freed arm-slots stay available for *other*
tokens — which is also the direct fix for the "too few tokens reach an entry" complaint.

---

## 3. Fatality #2 — the take-profit ladder is unreachable by construction

Point-in-time peak economic return of every position, over its own post-entry marks:

```
peak economic return per position
   p10  -7.4%   p25  -1.3%   p50 +22.7%   p75 +32.8%   p90 +34.8%   p100 +55.0%
   reach +10% econ: 227/347 = 65.4%
   reach +20% econ: 177/347 = 51.0%
   reach +30% econ: 111/347 = 32.0%
   reach +45% econ:   4/347 =  1.2%
   reach +60% econ:   0/347 =  0.0%
   reach +100% econ:  0/347 =  0.0%
```

The configured ladder is `take_profit_tiers` = **+80% / +180% / +350% / +700%**, and the only
arm that carries tiers (`alpha149_moonbag_merged_v1`) uses **+100% / +200% / +400%**.
Its first tier is **1.8× beyond the maximum ever observed** and 4.4× beyond the median peak.

Measured consequence: `next_tp_index = 0` and `principal_recovered = 0` on **all 350
positions**; `remaining_quantity_tokens > 0` on **0** closed positions. **Every single
realization was a full exit. Not one profit was ever banked.** This is "金狗拿不住",
quantified: total give-back **4,508.94 USD** (write-off 4,064.73 · hard stop 327.78 · all
other rules 443.51).

### Fatality #3 — the stop sits inside the noise
`hard_stop_return = -0.20` economic on **84 of 92** stopped arms. Under the frozen cost model
that is a **-13.3% price move**. Measured trigger: median price ratio **0.8374 (-16.3%)**,
**44/92 fired in under one minute**, 76/92 while still within -20%. The pool's own 30-second
move distribution is p90 = 9.49%, p95 = 18.65% — **7% of windows already exceed the stop
distance**. All 92 fired in pools holding ≥69,937 USD with buy share ≥0.5, and
`hard_stop_liquidity_veto_usd` was set on **0/92** arms.

### Exit counterfactual (design evidence, this window only)
Replaying all 350 positions over their own post-entry marks, cost model
`econ = 0.923077 × price_ratio − 1`:

| configuration | total USD |
|---|---|
| S0 actual engine | **-3,759.66** |
| tiers +20%/50% · +30%/25% · +60%/15%, hard stop -35% econ | **-1,181.61** |
| tiers +30%/50% · +45%/25% · +100%/15% | -2,074.70 |

**Banking at +20% is worth ≈ +2,578 USD on this window.** No exit configuration alone makes
it profitable, because the entry set (11 tokens, 4 of them rugs) carries negative edge — which
is exactly why fatality #1 must be fixed first.

---

## 4. Fatality #4 — coverage: 51% of evaluations can never admit

11,268 evaluations in 87 minutes:

| status / reason | n | share |
|---|---|---|
| rejected `cohort_observation` | 3,614 | 32.1% |
| rejected `no_active_matching_entry_policy` | 3,499 | 31.1% |
| rejected `pattern_observation` | 2,259 | 20.1% |
| rejected `entry_pool_liquidity_absent_curve_stage` | 740 | 6.6% |
| rejected `invalid_exact_asof_market_snapshot` | 498 | 4.4% |
| rejected `entry_pool_liquidity_below_configured_floor` | 428 | 3.8% |
| rejected `entry_pool_liquidity_unknown` | 228 | 2.0% |
| **admitted** | **20** | **0.18%** |

Per-arm blocker histogram (**489,718 arm-instances**):

| blocker | arm-instances |
|---|---|
| `await_distinct_dex_trajectory_frame` | **489,718** |
| `wait_passive_cohort_opportunity` | 124,910 |
| `strategy_token_lifetime_entry_consumed` | 22,227 |
| `cohort_event_consumed_or_position_open` | 8,562 |
| `await_distinct_wide_frame` | 6,092 |
| `cohort_frozen_opportunity_ready` | 2,034 |
| **arms that ever reached a non-blocked outcome** | **0** |

Root cause, proved from the engine's own counters
(`kv: dex-trajectory:v1`, since the 19:19 restart):

```
invalid_or_unknown     1,414      <- frames refused outright
distinct_frames          954      <- frames accepted
window_ready:30          321      <- 33.6% of accepted frames produced a usable 30s window
gap:60_120s              346      <- the real observation cadence
gap_reset                371      <- 38.9% of frames reset the series
pending_signal_dispatches 8,649
pending_signal_expired    6,052   <- dispatch never became a position
```

`dex_trajectory.window(rows, 30)` requires **≥3 frames, every consecutive gap ≤30s, total span
≤40s**. `Engine.accept` additionally clears the series when consecutive frames are >30s apart
(`MAX_GAP_SECONDS = 30`), refuses any frame whose `observed_at` is >30s before `now`, and
refuses `liquidity_usd < 1000`. The observed cadence for non-hot pools is **60–120s**, so the
series resets before three frames can accumulate. 171 of 316 policies hard-require
`windows['30']` via `requires_distinct_trajectory_frame`; the entry gate
(`store.py` `await_distinct_dex_trajectory_frame`) additionally demands the engine's frame
`observed_at` be **string-equal** to the current snapshot's. A raw state dump shows the
mechanism exactly: two "distinct" frames 2.15 s apart carrying **identical**
price/liquidity/volume, hence `windows: {"30": null, "300": null}` and every arm blocked.

This is already documented inside the codebase (`alpha149.py` wave-40 comment: *"A 30-second
window is impossible on a surface that is observed at a 60-120s cadence"*); the wide-surface
workaround (`_BroadEngine`, `MAX_GAP_SECONDS = 300`) exists but still yields
`await_distinct_wide_frame` 6,092 times.

---

## 5. What is already correct (do not "fix" these)

* The dust-pool write-off arithmetic: `remaining_cost = stake - allocated_cost`,
  `cumulative_pnl = realized_proceeds - stake` → exactly -20.00. Correct.
* The realisation that the four BSC prints were real deaths. Verified independently against
  live DEX data.
* `implausible_position_pnl` / `IMPLAUSIBLE_PNL_MULTIPLE` retirement of broken legacy epochs.
* Solana's `unknown_pool_custody: "WAIT"` rule; the wide-surface engine's provider-mismatch
  refusal (one price series per pool).

---

## 6. Priority order for the next rounds

| # | action | measured value | risk |
|---|---|---|---|
| **P0-1** | Cross-arm per-pool concentration cap | prevents ≈2,740 USD of the 3,380 USD rug loss; frees ~160 arm-slots for other tokens | **done, tested** |
| **P0-2** | New exit-carrier arms with **reachable** tiers (+15~20% first tier, bank ≥50%) and a **-35% econ** stop instead of -13.3% | ≈ +2,578 USD on this window | new arms only; existing arms untouched |
| **P0-3** | Cadence-aware trajectory engine + new arms reading it (≥2 observed frames spanning ≥30 s, no synthetic rows) | unblocks 489,718 blocked arm-instances | additive engine, shared engine untouched |
| **P0-4** | Per-chain custody tier: BSC entries need LP-custody evidence for full size, kept as bounded high-recall arms | removes the 94%-of-loss chain from full-weight entries | must not become a universal hard gate |
| **P1-1** | Liquidity veto on stops (`hard_stop_liquidity_veto_usd` was set on 0/92) | would have blocked 92/92 measured hard stops | opt-in per arm |
| **P1-2** | Self-review loop: per-arm, per-token, per-exit-reason win-rate/payoff with the counterfactual replay above | makes the next parameter choice evidence-based | offline only |

## 7. Method notes / limits

* Counterfactual replays read only marks observed **strictly after** each position opened.
  They are design evidence on one 87-minute window, **not** forward-proven performance, and
  they inherit the mark history's own ceiling (three pools printed an exact `49,999.99`
  liquidity ceiling; p90 and p95 peak returns are both +34.8%, i.e. saturated).
* `pretrade_rug_safety_assessments = 0` is reported as measured. Whether the Solana-only
  registration is intended or an oversight is left open.
* Reproduce with `data/research/diag_round120/`:
  `funnel_probe.py`, `probe4.py`–`probe14.py`, `verify_pools_live.py`,
  `profit_counterfactual.py`, `exit_sweep.py`, `counterfactual.json`, `sweep.json`.
