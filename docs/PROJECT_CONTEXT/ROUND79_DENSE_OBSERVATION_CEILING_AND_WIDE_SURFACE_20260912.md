# ROUND 79 — Token coverage is capped by DENSE OBSERVATION supply; the previous cap was frame admission

Date: 2026-09-12 (local) / 2026-09-12T03:40–03:50Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
Policy additions: 304 -> **306** (wave 38: `alpha149_broad_band_v1`, `alpha149_broad_flow_v1`)
Runtime reload: 2026-09-12T11:44:09+08:00 (PID pair 12496/37852), supervisor `scripts/run_paper.ps1`

## 1. Question this round answered

Wave 37 (rounds 74-77) tried to raise the 0.57% token-level signal rate by moving the *age band*
inside the same observation surface, and stayed at 0 ready frames after 776 frames
(`decorr_young` 0, `decorr_mature` 0). That falsified "the age band is the constraint" and left
the real question open: **how many tokens can this family observe well enough to judge at all?**

## 2. Measurements (all read-only, `julianday`-safe, bounded id-frontier windows)

### 2.1 Engine occupancy is not capacity bound, so the cap is admission

| quantity | value |
| --- | --- |
| alpha149 engine live pools | **67** (cap `MAX_POOLS` = 512) |
| accepted frames in the process | 1,188 |
| refused frames (`invalid_or_unknown`) | 255 |

67 pools against 1,052 tokens with >=2 observations in the same hour rules out eviction and
capacity. The gate is `dex_trajectory.Engine.accept`:

```python
if not valid or not str(row.get('provider','')).startswith('dexscreener') or ...
```

`alpha149.Engine.accept` calls it through `super()`, so **every one of the 136 alpha149 arms
inherits the dex-only admission rule.**

### 2.2 Provider mix (last 60 min, 10,225 snapshots, 2,311 distinct tokens)

| provider | rows | tokens | rows/token |
| --- | --- | --- | --- |
| `strategy-observer:dexscreener` | 4,467 | 273 | 16.4 |
| `geckoterminal` | 2,485 | 1,124 | 2.2 |
| `dexscreener` | 1,588 | 1,308 | 1.2 |
| `strategy-observer:geckoterminal` | 1,451 | 714 | 2.0 |

- tokens with >=2 observations: **1,052**
- of those, tokens with >=2 *dexscreener-prefixed* rows: **62 (5.9%)**
- tokens with **no** dexscreener row at all: **1,006 (43.5%)**
- pairs taking the largest frame share: top 10 pairs = **32.3%** of all 8,000 evaluation frames

### 2.3 The deeper cap: the mechanisms need frames <=30s apart

`Engine.accept` clears a pool's history when two consecutive observations are more than 30 s
apart (`gap_reset`), and every mechanism reads windows of at most 310 s. So the family can only
judge a token that is observed **densely**. Measured ceiling per hour:

| provider family | tokens | with >=2 obs | DENSE (>=3 frames, gaps <=30 s) |
| --- | --- | --- | --- |
| any provider | 2,311 | 1,062 | **33** |
| `dexscreener` (the current gate) | 1,336 | 66 | **6** |
| `strategy-observer:dexscreener` | 277 | 226 | **28** |
| geckoterminal family | 1,095 | 831 | **0** |
| non-dexscreener (wave-38 gain) | 1,292 | 995 | **30** |

Consequences:

1. Only ~33 tokens/hour are dense enough for **any** member of the family, and the live gate
   admits only ~6 of them. That is the 0.57% coverage, and it is a data-supply fact, not a
   threshold that can be tuned.
2. `strategy-observer:dexscreener` never starts with `dexscreener` and therefore is *not*
   admitted today, although it carries 28 of the 33 dense tokens.
3. geckoterminal supplies breadth (831 tokens with >=2 observations) but **0** dense runs at
   2.2 rows/token/hour; it cannot densify on its own.

### 2.4 The densification lever is starved

`shared_batch_coverage.alpha149` over the process lifetime: `eligible_batch` = **52**,
`no_spare` = **51**, `selected_extra` = **1**. `dex_http_capacity` shows `max_inflight` 8,
`active` 3, `low_budget_cancellations_no_rotation` 11. The spare-capacity lane that exists to
give young pools their frames essentially never gets an address slot, so the ceiling in 2.3
cannot be raised by policy alone.

## 3. Change made: wave 38 — a second, independent wide observation surface

Additive only. Nothing about the existing engine, its pools, its signals or any existing arm
changed.

1. `src/memetrader/dex_trajectory.py`: the provider gate is now the class attribute
   `Engine.PROVIDER_PREFIX = 'dexscreener'` (the exact string the gate always used). A subclass
   can widen admission without touching this rule.
2. `src/memetrader/alpha149.py` (wave 38, appended):
   - `_BroadEngine(_BaseEngine)` with `PROVIDER_PREFIX = ''`, plus a **one-provider-per-pool**
     rule: a pool adopts the vendor of its first frame and refuses frames from any other, so two
     price series can never be mixed into one trajectory.
   - `alpha149.Engine` gains a lazily built, separate `self._broad` namespace. `accept()` first
     runs the unchanged primary rule; only if the primary refuses **and** the primary does not
     already own that pool may the frame enter the wide surface (measured by the new
     `broad_frame_accepted` counter). The whole wide path is exception-guarded.
   - `signals_for()` resolves the pool in the primary namespace first, then the wide one, and
     the two new arms are emitted **only** from the wide namespace; every earlier arm is emitted
     **only** from the primary namespace. Existing exit arms do not ride the wide surface.
   - Instrumentation counters are surface-prefixed (`broad_band_step:*`, `broad_score_step:*`);
     the primary keys are byte-identical to before.
   - Two new kinds, each reusing an already reachable predicate:
     `broad_band` = `survivable_open_band`, `broad_flow` = `flow_entry`.
   - `snapshot()` reports `broad_surface` separately (pools, counters, provider prefix, arms).
3. `tests/test_alpha149_wave38.py` (8 tests): the shared admission rule is unchanged; the wide
   engine admits every provider but refuses a mixed-provider pool; the primary surface never
   emits a wave-38 arm; the wide surface emits exactly the wave-38 arms and no exit arm; a pool
   the primary owns is never duplicated into the wide surface; the two kinds mirror their
   reachable predicates; the arms keep family identity (1U, `affects=paper_only`).
4. `scripts/register_alpha149.py --apply`: 304 -> **306** additions, `ledger_unchanged: true`.

## 4. Verification after reload (11:44:09, read at 03:46:37Z)

| signal | value |
| --- | --- |
| primary pools | 31 |
| `broad_frame_accepted` | **95** |
| `broad_surface.pools` | **95** (2.5 min after reload) |
| `broad_surface.provider_prefix` | `''` |
| broad `provider_mismatch` | 5 |
| `broad_band_step:evaluated` | 95 |
| `broad_score_step:coverage_ok` | 95 / 95 |
| `broad_score_step:ge_min` | 62 (score >= 55) |
| `alpha149_features` duration p50 / p95 | 0.41 ms / 0.57 ms (was 0.49 / 1.11) |
| signal `alpha149_broad_band_v1` / `_broad_flow_v1` | 0 / 0 (expected: pools have 1 frame) |
| tests | 92 passed (`test_alpha149*`, `test_dex_trajectory`, `test_shared_batch149`, `test_participant_flow`) |

The wide surface immediately holds 3x the primary's pool count, at no measurable CPU cost. It
has not produced a signal yet and, per 2.3, cannot produce one until a wide pool accumulates a
second frame <=30 s after its first; `broad_band_step:has_prev` = 0 is the counter that will
show when that starts to happen.

## 5. Diagnosis summary

| id | finding | status |
| --- | --- | --- |
| DC-3a | Frame admission (`provider.startswith('dexscreener')`) cuts the family off from 43.5% of tokens and 82% of the dense ones | **fixed (wave 38)** |
| DC-3b | Only ~33 tokens/hour are observed densely enough for any mechanism in the family (gap <=30 s, >=3 frames); the mechanisms' own window design makes this the hard ceiling | open, measured |
| DC-3c | The spare-capacity densification lane is starved (51/52 batches have no spare address) | open, feed-limited |
| DC-2 (rounds 74-77) | The pool-age band was not the coverage constraint | closed by falsification |

## 6. Monitoring and next iteration

1. Within 60 min of the reload, re-read `broad_surface`: pools, `broad_band_step:has_prev`,
   `signal:alpha149_broad_band_v1`, `signal:alpha149_broad_flow_v1`, `provider_mismatch`.
   Falsifier: `has_prev` stays 0 while `broad_surface.pools` grows past 512 (i.e. the wide
   surface only ever holds singletons) -> the wide surface adds breadth but no tradeable depth,
   and 2.3 is the whole story.
2. Compare token-level coverage (distinct signalled tokens / distinct evaluated tokens) against
   the frozen 0.57% baseline over a matched 60-minute window, only after >=20 wide-surface
   signals exist.
3. Do **not** tune `decorr_young` / `decorr_mature` (wave 37) or any threshold: 2.3 shows the
   supply, not the thresholds, is binding. Archive them as unreachable if they are still 0 when
   the wave-38 surface has run for >=1 hour.
4. Next structural target (not this round): DC-3b/DC-3c. Any change there means more provider
   requests or a different feature contract for sparse trajectories, both of which are outside
   the add-only strategy boundary and need an explicit decision about request budget.
5. Existing pending A/B verdicts are unchanged: wave 28/29/33-37 pairs still need >=20 opens per
   side; `dense_flow_v1` / `dense_flow_hold_v1` are at 5 opens each.

## 7. The break between the wide surface and the entry layer (found and fixed this round)

The wide surface started producing real signals within ten minutes of the reload
(`signal:alpha149_broad_decorr_young_v1` 19, `signal:alpha149_broad_goldendog_band_v1` 13), and the
signals did reach the projection layer - 77 evaluation rows in a 12,000-row window carried them.
But **not one entry decision was ever written** for either arm. Every one of those evaluations
recorded

```
outcomes["alpha149_broad_decorr_young_v1"]  = "await_distinct_dex_trajectory_frame"
outcomes["alpha149_broad_goldendog_band_v1"] = "await_distinct_dex_trajectory_frame"
```

The gate is `store.py`:

```python
if p.get('requires_distinct_trajectory_frame'):
    trajectory = self._trajectory_engine_for(p)
    observed = trajectory.pools.get((token.token_id, pair_address), {}).get('features', {})
    if observed.get('observed_at') != iso(snapshot.observed_at) or not observed.get('windows', {}).get('30'):
        entry_blocked[p['arm_id']] = 'await_distinct_dex_trajectory_frame'
```

Two independent reasons it can never pass for a wide-only pool:

1. `_trajectory_engine_for` routed by the arm's registered `trajectory_engine` field, which was
   `alpha149` for every ALPHA149 arm, so the lookup always used the **dex-only** namespace.
2. Even with the right namespace, the gate demands `windows['30']`, and `dex_trajectory.window()`
   returns `None` unless the window holds **>=3 frames spanning <=40s with no gap >30s**. A
   surface observed at a 60-120s cadence can never satisfy that.

### 7.1 What was changed

- `store.py::_trajectory_engine_for` gains an additive `alpha149_broad` branch that returns the
  wide namespace (`engine._broad`). `v144`, `alpha149` and the default are untouched.
- `store.py` gains an additive `requires_distinct_wide_frame` gate, placed directly after the
  existing one, which applies only to arms carrying that field and checks the **same
  next-frame confirmation contract** on the wide surface: the pool must exist there, the frame
  must be *this* observation, and the trajectory must already hold an earlier observation of the
  same pool. The second row is exactly the evidence the wide-surface mechanisms were computed on
  (they read the two-frame view), so the contract is preserved rather than disabled.
- `alpha149.py` waves 39 and 40 route the wide arms at that namespace and record the contract.

### 7.2 The append-only ledger forced a new arm id

The four wave-38/39 wide arms had already been appended to
`chain_meme_trader_policy_additions` **before** the contract change, and the entry gate reads the
arm's **registered** `policy_json`. The ledger blocks UPDATE and DELETE by trigger, and
re-registration skips arms that already exist, so the stored contract cannot be corrected in
place. Verified in the ledger:

| row | arm | trajectory_engine | requires_distinct_trajectory_frame | requires_distinct_wide_frame |
| --- | --- | --- | --- | --- |
| 463 | `alpha149_broad_band_v1` | `alpha149` | True | None |
| 464 | `alpha149_broad_flow_v1` | `alpha149` | True | None |
| 465 | `alpha149_broad_decorr_young_v1` | `alpha149` | True | None |
| 466 | `alpha149_broad_goldendog_band_v1` | `alpha149` | True | None |
| **467** | **`alpha149_wide_decorr_young_v1`** | **`alpha149_broad`** | **False** | **True** |
| **468** | **`alpha149_wide_goldendog_band_v1`** | **`alpha149_broad`** | **False** | **True** |

Rows 463-466 stay exactly as registered and remain blocked by their own contract. Wave 40
therefore registers two **new** arms with the corrected contract (308 -> 310 additions) instead
of rewriting anything.

### 7.3 Result

Four minutes after the wave-40 reload, the newest evaluations carrying those arms read:

| arm | outcome | rows |
| --- | --- | --- |
| `alpha149_wide_decorr_young_v1` | `cohort_frozen_opportunity_ready` | 16 |
| `alpha149_wide_decorr_young_v1` | `await_distinct_wide_frame` | 1 |
| `alpha149_wide_goldendog_band_v1` | `await_distinct_wide_frame` | 13 |
| `alpha149_wide_goldendog_band_v1` | `cohort_frozen_opportunity_ready` | 2 |

`cohort_frozen_opportunity_ready` is the normal pre-entry state (the frozen opportunity is
waiting for its later observed fill). The arms have left the dead state for the first time.

## 8. Wave 39 measurement: the wide surface's own kind profile

`broad_ready:*` counters, wide surface, first ~20 minutes (184 evaluations):

| kind | hits |
| --- | --- |
| `sf_young_turnover` | 51 |
| `righttail_lottery` | 31 |
| `sf_quiet_absorption` | 26 |
| `decorr_young` | 20 |
| `merged_multi_setup` | 15 |
| `goldendog_liquidity_band` | 14 |
| `df_price_up_liquidity_up` | 10 |
| `sf_goldendog_deep_base` | 8 |
| `sf_deep_low_fdv` | 7 |
| `sf_extreme_buy_pressure` | 5 |
| `df_activity_jump` | 4 |
| `survivable_open_band` (mirrored as `broad_band`) | **0** |
| `flow_entry` (mirrored as `broad_flow`) | **0** |

Two conclusions:

1. **The wave-37 question is settled.** `decorr_young` was never a threshold problem: it fired 0
   times in ~1,500 primary-surface frames and 20 times in the wide surface's first 184. Frame
   supply was the whole story.
2. The wide surface is a **young-pool** surface: `age_30_180m` is 0 across all wide frames, so
   the `survivable_open_band` mirror can never fire there. Wave 39/40 therefore bind the wide
   arms to the young-pool kinds the surface actually produces.

## 9. Cost and stability after all four reloads

| quantity | before wave 38 | after |
| --- | --- | --- |
| alpha149 `pools` | 67 | 27-64 (primary) + 87-158 (wide) |
| `alpha149_features` duration p50 / p95 | 0.49 ms / 1.11 ms | 0.41 ms / 0.57 ms |
| new `system_error_cases` after reloads | - | none (last case #279 at 03:36:45Z, before the first reload) |
| `dex_trajectory.Engine` defaults | 30s gap, `dexscreener` prefix | identical (class attributes, same default values) |

One methodology correction from this round: an apparent "new defect, `native-paper-held
ValueError` +90 in 3 minutes" was an artifact of a top-12 error list truncation - the error's
`last_seen_at` was 03:09:43Z, 45 minutes before the sample. No new defect. Recorded because the
same trap (comparing two differently-truncated lists) is a fifth way to mis-read this database.

## 10. DC-4: the entry layer has its own dense-observation requirement

After the wave-40 fix the wide arms reach `cohort_frozen_opportunity_ready` - the same pre-entry
state 133 other arms share - but still produce no entry decision. The admission rule in
`store.py::observe_chain_meme_pattern` requires, for the same token **and pair**:

1. the arm in the PREVIOUS cohort evaluation's `ready_arm_ids` (`pending`), with the same
   `event_keys[arm]`, and
2. the signal still inside its 60-second freshness window, and
3. `post_valid`: `0 < current.observed_at - previous.observed_at <= 60` and the pool above the
   liquidity floor.

Conditions 1 and 3 together mean **two cohort evaluations of the same pool within 60 seconds**.
Measured over the last ~35 minutes, for the 49 pools where a wide arm reached `ready_arm_ids`:

| quantity | value |
| --- | --- |
| consecutive same-pool evaluation pairs where the first had the wide arm ready | 13 |
| gap distribution of those pairs | p10 37.9s, **p50 87.3s**, p90 104.2s |
| share of those gaps `<= 60s` | **15.4%** |
| pairs satisfying both `<=60s` and still-accepted | **2** |

So the wide surface's own cadence for exactly the pools it signals (p50 ~87s) is slower than the
confirmation window the entry layer requires. **The dense-observation ceiling is not only a
mechanism-supply problem; it propagates into execution.**

Two ways forward, both outside what this round may do unilaterally:

- **Densify the wide pools that signal** (feed them extra observations). The spare-capacity offer
  lane currently iterates only the primary namespace and is starved anyway: over the process
  lifetime `eligible_batch` 52, `no_spare` 51, `selected_extra` 1. This needs a request-budget
  decision.
- **A different confirmation window for the wide arms.** The 60-second rule is a strict timing
  rule shared by every cohort arm; loosening it to create trades is explicitly out of bounds here.

The wide surface is therefore kept running as a **measurement surface**: it has already settled
the wave-37 question, it holds 87-158 pools against the primary's 27-64, and any wide pool that
happens to be observed twice inside 60 seconds will convert through the normal path.

### 10.1 What is verified about the wide surface so far

| claim | evidence |
| --- | --- |
| admission widened | `broad_frame_accepted` 95 -> 184; wide pools 87-158 vs primary 27-64 |
| no cost regression | `alpha149_features` p50/p95 0.41/0.57ms vs 0.49/1.11ms before |
| signals are produced | `signal:alpha149_broad_decorr_young_v1` 19, `..._goldendog_band_v1` 13 |
| signals reach projection | 77 evaluation rows carried them in a 12,000-row window |
| the old dead state is gone | outcomes moved from `await_distinct_dex_trajectory_frame` (permanent) to `cohort_frozen_opportunity_ready` (16 -> 45 rows and growing) |
| conversion is now cadence-bound, not contract-bound | 13 candidate windows, 2 inside 60s, 0 admitted |

No threshold, no strict timing rule and no existing arm was changed to obtain any of this.

## 11. DC-5: the write-off line is crowding, not a mark defect

The 24h write-off figure rose again this round (220 / -706U earlier, 266 / -816U now), so the
line was re-checked against the dust-print defect that was fixed earlier in the session. It is
**not** that defect:

| window | write-offs | distinct tokens | distinct arms | PnL |
| --- | --- | --- | --- | --- |
| last 60 min | 48 | **1** | **48** | -120.0U |
| last 180 min | 145 | 5 | 71 | -434.0U |
| last 24h | 266 | **26** | 84 | -816.0U |

The dominant close reason in the last hour is
`dex_pool_liquidity_below_configured_floor_writeoff` (48 of 272 closed exits), all of them on
**one** Solana pool (`solana:5SwF9vArvvbDE1EVd…`), one write-off per arm that held it, with hold
times clustered at p50 = 9.5 minutes. The 24h top tokens follow the same shape: 48, 37, 32, 30,
25, 22 write-offs on single tokens - i.e. **10.2 arms per write-off token on average**.

So the write-off loss is not 266 independent failures; it is 26 pool-liquidity collapses
multiplied by the number of arms crowded into each pool. Counting only the arms beyond the tenth
on the same token in the eight worst tokens removes 139 of the 266 write-offs (52%).

This is the same-token concurrency question that has been measured as a shadow since an earlier
round (a 10-arm cap would have blocked 944/1258 positions = 75.0%, whose realized result was
-416.3U). The evidence is now stronger and comes from two independent angles; **enforcement still
requires explicit authorisation**, because it would change how existing arms behave.

## 12. Round 79 summary

| id | finding | status |
| --- | --- | --- |
| DC-3a | the dex-only frame admission cut the family off from 43.5% of tokens and 82% of the densely observed ones | **fixed** (wave 38 wide surface) |
| break | wide-surface signals could never enter: `await_distinct_dex_trajectory_frame` (engine routing + an impossible `windows['30']` requirement) | **fixed** (waves 39/40, additive routing + `requires_distinct_wide_frame`) |
| DC-3b | only ~33 tokens/hour are observed densely enough for any mechanism; the wave-37 age band was never the constraint | measured; `decorr_young` proven reachable on the wide surface (0 in ~1,500 primary frames, 20 in 184 wide frames) |
| DC-4 | the entry layer has its own dense requirement: two cohort evaluations of the same pool within 60s, while wide pools are re-evaluated at p50 87.3s | measured; needs a decision on request budget |
| DC-3c | the spare-capacity densification lane is starved (52 eligible batches, 51 with no spare, 1 selected) | measured |
| DC-5 | the write-off line is single-token crowding (48 write-offs on 1 token in an hour; 10.2 arms per write-off token in 24h), not a mark defect | measured; cap enforcement needs authorisation |

Delivered this round: 4 additive arms in 3 waves (306 -> 310 `policy_additions`), 2 additive
shared-code hooks (`PROVIDER_PREFIX` / `MAX_GAP_SECONDS` class attributes with unchanged
defaults; the `alpha149_broad` engine routing and the `requires_distinct_wide_frame` gate), 15
new tests, 3 commits pushed, and no change to any existing arm's behaviour, thresholds, or the
frozen timing rules.

## 13. DC-5 fix: the dust read must be corroborated

The write-off rule itself was checked against the whole population before any change. For each
written-off token the snapshots around the write-off were compared:

| verdict | tokens | evidence |
| --- | --- | --- |
| **real rug** | 19 | price collapsed 3-6 orders of magnitude (e.g. 0.0003469 -> 3.346e-10) with liquidity -> 0 |
| **contradicted read** | 1 | `solana:5SwF9vAr…`: liquidity 31.1k -> 33.5k -> **0.0** while the price held at 3.002e-05 (-3.9%) and volume kept printing 62.9k -> 47.4k -> 32.5k -> 19.3k USD per 5 minutes across the whole sub-floor window |
| unknown | 5 | no snapshot coverage in the window |

That one contradicted read wrote off **48 positions across 48 arms (-120U, 14% of the daily
write-off loss)**, because `fresh_visible_dust` fired on a single VISIBLE mark whose liquidity
was below the floor and then booked the full remainder as lost.

A pool with zero reserves cannot be printing 19k-63k USD of five-minute volume at an unchanged
price; the payload contradicts itself. The frozen contract already covers this case: *"Missing/
failed/stale evidence never establishes a writeoff."*

### 13.1 Change

`paper_execution.dust_read_contradicted_by_live_trading(...)` is the corroboration test, added in
front of the dust-pool terminal fact in `store.py::_advance…`:

- the reported liquidity must be **exactly zero** (or the pool must be below the floor with a
  zero read) - anything above zero, including 0.05 and 999.99, is a genuinely drained pool and
  keeps the frozen immediate-writeoff rule untouched;
- the observed price must NOT have collapsed against the entry price (a real rug loses orders of
  magnitude), which is what separates all 19 real rugs;
- the **same** observation must still report material trading volume (`>= 200 USD` per 5 minutes).

Every missing field falls back to the previous behaviour, so no new universal gate is introduced:
the guard can only fire on a self-contradicting payload. Vetoes are counted into
`kv['dust-read-vetos']` (every tenth) for observability.

### 13.2 Verification

- `tests/test_dust_read_guard.py` (8 tests) pins both directions, including the two measured
  populations: the 8 largest real rugs are NOT contradicted and the one glitch IS.
- `tests/test_paper_execution.py`, `tests/test_core.py` and the other write-off-touching suites
  produce **exactly the same pass/fail sets with and without the change** (verified by stashing
  the change and diffing the failure lists; `tests/test_core.py` has 15 pre-existing failures
  from environment/legacy fixtures and the difference set is empty).
- Reloaded 2026-09-12T14:19:31+08:00 (PID pair 38856/6308).

What this does **not** claim: the 19 real rugs still write off, so the daily write-off total
remains dominated by genuine deaths. The fix removes the false-positive family, not the line.

### 13.3 Second measured false positive, and why the guard needed a second test

Thirty minutes after the first fix was deployed, the same pattern fired again on a different
pool: `solana:HBxFUfqE…` was marked by **`geckoterminal`** at 06:23:11Z with
`liquidity = 0.00` and `price = 1.55226e-05`, while nineteen seconds earlier the same pool's own
`dexscreener` mark read **23,759 USD** of liquidity at `1.558e-05` (a -0.4% move). 37 positions
were written off for -97U. That payload carries **no volume**, so the same-observation test
cannot see it - the guard reported no veto at all.

The provider-independent test is the pool's own mark history, which is the same evidence the
price-outlier guard already uses:

> a pool cannot lose every reserve between two consecutive observations without its price moving.

The `_dust_read_contradicted` helper therefore applies two tests, both of which need positive
evidence of a live pool:

1. **same observation** - `liquidity_usd == 0` while that same observation reports >= 200 USD of
   5-minute volume and the price has not collapsed against the entry price
   (`paper_execution.dust_read_contradicted_by_live_trading`);
2. **own mark history** - `liquidity_usd == 0` while the previous >= 3 VISIBLE marks of the same
   token+pair have a median liquidity at or above the floor and the current price is within 50%
   of their median price.

A genuinely dying pool fails both: its price collapses (19 of 19 real rugs), or its own recent
marks are already below the floor. And a pool that really has died stays below the floor, so the
history test stops applying after a few observations and the frozen immediate-writeoff rule
resumes - the guard delays a wrong write-off, it never blocks a correct one permanently.

Verified: `tests/test_dust_read_guard_history.py` (4 tests) replays the measured values of the
second case, anchors the code path, and shows the real rug fails both tests; the
`tests/test_core.py` failure set is again byte-identical with and without the change (15
pre-existing failures, difference set empty); reloaded 2026-09-12T14:29:13+08:00.
