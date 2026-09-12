# Round 120-8 record — shipped: per-arm `feature_vector` compaction (68% less payload per arm), plus the next N× duplication it exposed

Date 2026-09-13. Deploy boundary **20:42:29Z**. Epoch
`chain-meme-trader/funding-20260906-v002-final-1000` (see note at the end). Scripts
`data/research/diag_round120/r8_*.py`. **First production change since round 120-4.**

---

## 1. Why this was safe to ship when round 120-7 deferred it

Round 120-7 found that `cohort_observation` rows were 582 MB of a 921 MB database (63%) and
that `cohort_signals` held ~16 arm entries each carrying the **same** `decision_evidence.
feature_vector` — 81,188 bytes of an 98,339-byte row. It was deferred because the field is read
live in six places.

This round did the missing step: **asked what those readers actually consume.** Grepping every
`.py` under `src/memetrader` and `scripts` for `feature_vector` returns exactly **two readers**,
and between them they touch **three scalar fields**:

| reader | expression | fields used |
|---|---|---|
| `store.py` `distinct_trajectory` (live entry gate) | `frozen = evidence.get('feature_vector', {})` | `frozen['pair_address']`, `frozen['observed_at']` |
| `mode_learning144.py:279` | `.get('feature_vector',{}).get('ingested_at', f['ingested_at'])` | `ingested_at` (has a fallback) |

Nothing else reads the vector. So keeping those three fields preserves both readers
byte-for-byte, and the remaining ~7.6 KB per arm is pure duplication.

**The lesson is the one recorded in round 120-7's method note, now with a worked example: grep
the consumers before pricing the saving.** "Read live in six places" was true of
`cohort_signals`; it was *not* true of the 7.6 KB inside it.

## 2. What was shipped

`Store._compact_cohort_signals_for_storage(features)`, called at the two evaluation-row
serialisation points (`store.py` ~28252 and ~29760).

* Returns a **copy**; the caller's mapping is never mutated, so the engines,
  `mode_learning144`, `cohort_experiments` and the exit path see exactly the object they saw
  before. Only what reaches `feature_json` changes.
* Keeps `pair_address`, `observed_at`, `ingested_at`; drops the rest and stamps
  `feature_vector_compacted` with the reason and a recovery pointer to `token_snapshots`.
* Shapes that do not apply pass through unchanged; an already-compact vector is left alone.
* **Fully reversible**: stop calling it and the previous payloads resume.

`tests/test_cohort_signal_payload.py` (7 tests) pins: the three fields survive; the bulk is
removed (>85% on a realistically sized fixture); the caller mapping is never mutated; odd
shapes pass through; an already-compact vector is untouched; the reduction scales with arm
count; and an end-to-end check of **the two production readers' exact expressions**, including
`parse_time(frozen['observed_at'])`. **94 tests pass** with the existing suites.

## 3. Measured effect — and an honest correction

**Verified on live rows:** 100% of post-deploy arm entries carry the compacted form; the newest
row shows `feature_vector` keys exactly `['ingested_at','observed_at','pair_address']` and both
readers satisfied. On the largest observed row (70 arms) `feature_vector` went from **7,780 to
154 bytes per arm**.

**But the row-size AVERAGE did not drop** (post-deploy 97,747 B vs all-time 87,675 B), and that
needs stating plainly rather than hiding behind the per-field number. The cause is that the
population changed: the rows being written now carry **69–70 arms** where the measured
historical row carried 16. Comparing averages across a different arm-count distribution is not a
measurement of the fix.

**The correct metric is bytes per arm**, which is arm-count independent:

| | before | after |
|---|---|---|
| `feature_vector` per arm | 7,780 B | **154 B** |
| `mechanism_flags` per arm | 2,520 B | 2,520 B |
| `decision_key` + `episode_id` | 266 B | 266 B |
| other | ~734 B | ~656 B |
| **total per arm** | **~11,300 B** | **~3,596 B** |

**≈68% less payload per arm.** Multiplied by the arm count, the 70-arm row fell from
~791 KB to 252 KB.

## 4. The next N× duplication, already identified

The breakdown above shows the dominant remaining per-arm cost is **`mechanism_flags`: 2,520
bytes, 88 entries** — and it is the **same dict for every arm on a frame**. In `alpha149.py:2296`
the signal is built as `mechanism_flags=flags` where `flags = mechanisms(f)` is computed **once
per frame** and then referenced (and `deepcopy`-d) into every arm's `decision_evidence`.

So it is the identical defect one level down: one 2,520-byte object written once per arm. Hoisting
it to the row level should take the per-arm residual from ~3,596 to ~1,076 bytes — **another ~70%
on top of this round's 68%**.

Second, smaller: `decision_key` and `episode_id` differ only by a `':' + arm` suffix
(`alpha149.py:2290-2291`), so one of the 266 bytes is derivable.

**Not attempted this round** for the same reason the whole item was deferred last round: it
changes a field on the entry path and needs the same consumer check first. It is now a
precisely priced, ready item rather than an estimate.

## 5. Separate observation, needs attention

The epoch string typed into the round header above came out as
`chain-meMe-trader/...` — a typo, not a state change. The authoritative value remains
`chain-meme-trader/funding-20260906-v002-final-1000` (confirmed by `/health` and
`kv[runtime-loaded-manifest]` immediately after the 20:42:29Z restart). Recorded because a
mistyped epoch in a record is exactly the kind of thing that misleads a later round.

## 6. Where this leaves the priority list

| # | action | state |
|---|---|---|
| **P0-1** | **Hoist `mechanism_flags` to row level** — 2,520 B/arm × every arm, the same object; ~70% further reduction, consumer check first | priced, ready |
| **P0-2** | Supply-weighted observation caps (`observation_leases145` per-chain caps) — needs a discovery-share signal threaded through four live enforcement sites | designed, ready |
| **P0-3** | EXIT150 forward samples via `paired_arm_ab.py` at ≥20 settled per side | live |
| P1-1 | Standing loop: `supervise_metrics.py` + `trade_context_ledger.py` | in use |
