# ROUND 120-17 RECORD — exit-side closure, and the profit-capture finding

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). All work read-only except one additive module change.

## 0. Correction to my own earlier prioritisation

I had ranked "reduce the evaluation write rate" as **P0-3**, on the stated basis that
the DB grows ~7.3 MB/min toward a full disk. That framing was wrong in its urgency
arithmetic.

- DB size **1,175 MB**
- Free space on the volume **513,252,249,600 B = 489,463 MB**
- At 7.3 MB/min that is **~46 days** of headroom, not hours.

Combined with the semantics risk measured below, **P0-3 is demoted from P0 to
background hygiene.** Nothing in this round depends on it.

The semantics risk is real and was the reason I checked before touching it:
`store.py:27542` sources `previous_features` from

```
SELECT feature_json,evaluated_at FROM chain_meme_trader_v6_entry_evaluations
WHERE definition_version=? AND token_id=? AND reason=? ORDER BY id DESC LIMIT 1
```

That is the **immediately preceding row**, not a time-window lookup. Skipping an
evaluation write therefore does not "sample" the series — it rewinds the state chain
(`ready_arm_ids`, `cohort_signals` carry-forward at `27955`, `round2_chase_consumed`
at `27934`, `resource_bound_opportunities` at `27935`). Any write-rate reduction must
first preserve those four carriers, which is a larger change than the payoff justifies
at 46 days of headroom.

Supporting fact, useful later: observer-only rows have almost no downstream consumer —
`cohort_observation` / `pattern_observation` are referenced in only **2 files**
(`store.py` ×5, `rediscovery_funnel.py` ×1). So the 53%-of-rows-that-cannot-admit
observation is a candidate for a *separate* deferred write path, not a deletion.

## 1. The exit side is now closed, with mechanism

Four independent falsifications, all measured on real forward marks. Each candidate
replays a position's own `chain_meme_trader_market_mark_history` series and may act
only on marks at or before the mark being tested.

### 1a. No tighter stop helps

906 closed positions, 24 tokens, actual total **−7,962.84 U**.

| enforced stop (econ) | sim PnL | delta | fired |
|---|---|---|---|
| −0.15 | −7,536.53 | **−358.53** | 587 |
| −0.20 | −7,327.41 | −149.42 | 450 |
| −0.25 | −7,266.55 | −88.55 | 374 |
| −0.30 | −7,290.65 | −112.66 | 319 |
| −0.40 | −7,327.20 | −149.21 | 238 |
| −0.50 | −7,329.73 | −151.73 | 233 |
| −0.65 | −7,319.75 | −141.76 | 224 |

Every candidate is **worse than doing nothing**. The live configuration already beats
any uniform tighter stop, because tightening also stops the positions that recover.

The arithmetic explains why: enforcing −0.20 fires on 261 of the 289 hard stops and
"improves" them by a **median of 0.76 U** — i.e. the first breaching mark is already
essentially at the terminal price.

### 1b. The stop fires correctly; the loss is a gap-through

| group | mark[-2] econ | mark[-1] econ | largest single-step drop |
|---|---|---|---|
| hard stop (232) | median **−12.4%** | median **−36.0%** | median **23.6%** |
| write-off (299) | median **+16.8%** | median −14.3% (p25 −101.2%) | median **34.7%** |
| other/winner (343) | −7.5% | −8.3% | median 2.0% |

Inter-mark gap median **10.9 s** (config `TARGET_SECONDS = 15`), and the last mark is
**1–3 s before the position close**. So:

- marks are **faster than configured** — open positions are not starved;
- we were **never blind** before the terminal event;
- the −20% → −36% overshoot happens **inside one ~11 s interval**.

The stop acts at the first mark below its threshold. There is no delay to remove.

### 1c. No liquidity warning, and the liquidity data is sound

Exit at the first mark below liquidity threshold L gives **0 seconds of median warning
at every threshold** (1k … 12k). At L=20,000 the "gain" is +214 U with 0 s warning —
that is re-pricing the terminal mark, not a warning.

I suspected a clamp because write-off pools showed liquidity pinned at exactly 50,000.
**Falsified — it was my own aggregation artifact.** Across 11,750 marks: 2,969 distinct
values, max 67.5 M, no clamp. Per-step: price moves 15.7%, liquidity 17.2%, volume
20.4%; liquidity+volume co-move **1,507** times vs liquidity-alone **29**; and
**0** pools show "price moves but liquidity never does". The "frozen" pools are
genuinely dead pools. Recorded so this is not re-investigated.

### 1d. Lease contention is not the cause

`observation_leases145` eviction (`replaceable_early`) admits only `bucket == "early"`
leases, so growth/mature leases are not evictable — a real asymmetry. But it is not
this round's bottleneck: measured mark cadence is already **10.9 s < 15 s** target.
Recorded as a deferred observation, not priced as a fix.

**Conclusion: the entire loss is "the token died inside one unobserved 11-second
interval". No exit rule, level, or cadence change can recover it. All remaining effort
belongs on the ENTRY side.**

## 2. The user's named priority, measured — and it points the other way

"金狗拿不住" assumes we exit big winners too early. The data says the opposite.

Per-position peak economic return over the hold, 906 positions:

- reach **+100%**: **5** of 906 (0.6%)
- reach +50%: 49 (5.4%)
- reach +15%: **241** (26.6%)

And of those **241 positions that touched +15%, 186 finished NEGATIVE and only 55
positive.** Their realised total was **−3,059.50 U**; banking the whole position at
+15% would have returned **+723.00 U**.

So the dominant failure is not "held a winner too long" — it is **never taking profit
at all on positions that were briefly green**. The golden-dog population is tiny; the
round-trip population is large.

### 2a. Pricing the ladders (same replay, real marks)

| variant | sim PnL | delta vs actual |
|---|---|---|
| actual (no ladder) | −7,962.84 | — |
| full10 — 100% @ +10% | −3,855.45 | +4,107.39 |
| **full15 — 100% @ +15%** | **−3,784.48** | **+4,178.36** |
| full20 — 100% @ +20% | −4,944.39 | +3,018.45 |
| full25 — 100% @ +25% | −5,166.00 | +2,796.84 |
| half15 — 50% @ +15% | −5,873.66 | +2,089.18 |
| **bank15 — 50/40/50 @15/30/55 (DEPLOYED)** | **−5,516.65** | **+2,446.19** |
| bank25 — 50/40/50 @25/45/70 (DEPLOYED) | −6,464.32 | +1,498.52 |

**The deployed `bank15` captures only 58.5% of the measured effect.** The 50% it leaves
riding is exactly what round-trips. `full15` is worth **+1,732 U more than `bank15`**.

The level is not knife-edge (+10% ≈ +15%, and +20% already gives back 1,160 U); the
**capture fraction** is the factor that matters.

### 2b. Honest robustness — this is concentrated, not broad

- survives spike rejection: run=3 consecutive marks still gives **+4,272 U**;
- survives dropping the best token (+2,941 U), best two (+1,745 U), best three (+715 U);
- token-clustered bootstrap 95% CI **[+969 U, +8,307 U]**, excludes zero;
- **BUT only 7 of 24 tokens improve; 16 are flat at exactly 0.00 U (they never reach
  the level at all), and 3 BSC tokens contribute 83% of the gain.**

The level was also chosen in-sample on this one epoch. This is therefore a **forward
experiment**, never a promoted result.

## 3. Change made — two additive full-capture arms

`src/memetrader/exits150.py` v1 → **v2**. Added, as new exit-carrier arms:

| arm | tier | capture | stop | trail | hold |
|---|---|---|---|---|---|
| `exit150_full15_v1` | +15% | **100%** | −0.35 | .30/.35 | 90 min |
| `exit150_full25_v1` | +25% | **100%** | −0.35 | .35/.35 | 90 min |

This completes a clean 2×2 against the deployed partial arms, changing one factor at a
time:

| capture \ level | +15% | +25% |
|---|---|---|
| partial (50%) | `exit150_bank15_v1` | `exit150_bank25_v1` |
| full (100%) | `exit150_full15_v1` | `exit150_full25_v1` |

Compliance: these are **exit-carrier arms** — the engine clones the first frozen entry
signal on the pool, so each new arm gets the same opportunity as whichever entry arm
fired first and only its exit contract differs. Every existing arm is the matched
same-signal control. **No existing strategy was modified, replaced or retuned**, per
the standing constraint.

Correctness verified, not assumed:

- built-policy check: `full15` → `take_profit=[{'return':0.15,'fraction_of_remaining':1.0}]`,
  `full25` → `[{'return':0.25,'fraction_of_remaining':1.0}]`;
- entry side is **byte-identical across all five carriers** (`entry_match_mode`,
  `entry_gate`, `feature_hypothesis`, `trajectory_engine`,
  `requires_distinct_trajectory_frame`, `source_arm_ids`), so only the exit differs;
- `store.py:35717` — `sell_amount = amount_raw if fraction >= 1.0 else ...`, confirming a
  1.0 fraction sells the entire remaining position;
- `fraction_of_remaining: 1.0` is an established idiom (7 existing call sites);
- registration is idempotent and stamps its own `forward_activation_snapshot_id`
  frontier through the append-only API.

Tests: `tests/test_exit150.py` updated for the new design intent (arm count 3→5; the
moonbag assertion now applies only to partial-capture arms, since full-capture arms
deliberately sell out). **97 tests pass** across `test_exit150`, `test_alpha149`,
`test_pool_concentration`, `test_dex_start_gate`, `test_cohort_signal_payload`,
`test_dust_read_guard`.

## 4. What this round did NOT do

- Did not touch the evaluation write rate (P0-3, demoted — see §0).
- Did not change the same-token concentration cap. It remains **OFF by default**; the
  user declined it twice, and that stands.
- Did not widen, delay or retune any stop — §1a shows tightening is strictly worse, and
  the old session already falsified widening.
- Did not claim the +4,178 U as realised. It is an in-sample replay whose benefit is
  83% concentrated in three tokens.

## 5. Next actions

1. **P0-1** — re-run `scripts/paired_arm_ab.py` as settled counts grow; when
   `alpha149_merged_multi_setup_v1` reaches ≥20 paired cohorts, add it to the pause list
   (clean verdict, 90% CI [−7.4973, −0.6131] excludes zero).
2. **NEW P0** — settle `full15`/`full25` to ≥20 per side and test the capture-fraction
   hypothesis forward. This is now the highest-value open question, because §2a says the
   deployed ladder leaves 41.5% of the effect on the table.
3. **P0-2** — entry-quality activity floor arm (`m5_trades >= 30`, `m5_volume_usd >= 5,000`),
   blocked until the dead group is ≥30 **tokens** (currently 10).
4. **Entry side is the only remaining lever** (§1). Push on token-level evidence
   breadth: 906 positions sit on only **24 tokens**.
5. P0-3 (write rate) — background only; must first preserve the four `previous_features`
   carriers listed in §0.

## 6. Probe artifacts

All under `data/research/diag_round120/` (gitignored), read-only:
`r17_tightstop.py`, `r17_collapse_shape.py`, `r17_liquidity_warning.py`,
`r17_liq_clamp.py`, `r17_liq_stale.py`, `r17_goldendog.py`, `r17_tp_robust.py`,
`r17_ladder_value.py`, `r17_verify_arms.py`, `r17_lease.py`, `r17_probe_schema.py`.
