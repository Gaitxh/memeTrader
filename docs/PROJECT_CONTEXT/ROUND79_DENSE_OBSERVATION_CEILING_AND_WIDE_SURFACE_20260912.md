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
