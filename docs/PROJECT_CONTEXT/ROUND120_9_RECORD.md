# Round 120-9 record — shipped: `mechanism_flags` interning (−63% more payload per arm, −90% cumulative)

Date 2026-09-13. Deploy boundary **20:50:27Z**. Epoch
`chain-meme-trader/funding-20260906-v002-final-1000`. Scripts `data/research/diag_round120/r9_*`.
Predecessor: `ROUND120_8_RECORD.md`.

---

## 1. The hypothesis I brought in, and how measurement changed it

Round 120-8's payload breakdown left `decision_evidence.mechanism_flags` as the dominant residual:
**2,520 bytes per arm over 88 entries**. My plan was to **hoist it once per row**, on the theory
that `alpha149.py:2296` passes the single per-frame `flags = mechanisms(f)` object into every
arm, so it was one object repeated N times.

**Refuted before any code changed.** Within one real row, **36 arms carried 4 distinct flag
sets** — because the accumulated `cohort_signals` mixes arms that were signalled on *different*
frames (`store.py:27787` seeds it from `previous_features`). Hoisting to row level would
therefore have been **lossy**, exactly the failure mode this session keeps catching.

What replaced it: **interning**. Each distinct flag set is stored once in a row-level
`cohort_mechanism_flags` table and each arm keeps `mechanism_flags_ref`, an index into it. This
is lossless by construction and saves by the arm-to-distinct ratio.

## 2. Consumer check — done first this time

Round 120-8's lesson was "grep the consumers before pricing the saving". Searching every `.py`,
`.js` and `.html` outside `.venv` for `mechanism_flags` returns **two writers and zero
readers**:

* writers: `alpha149.py:2296`, `dex_trajectory.py:250`
* readers: **none**

So replacing the inline object with an index breaks nothing, and the information stays fully
recoverable through the table. (`feature_vector` was different: it has two live readers, which
is why round 120-8 kept three scalar fields rather than dropping it.)

## 3. Measured effect on live rows

| | pre-deploy | post-deploy |
|---|---|---|
| rows sampled | 130 | 135 |
| arms | 3,647 | 3,876 |
| **inline `mechanism_flags`** | **2,849** | **0** |
| arms using `mechanism_flags_ref` | 798 | **3,852** |
| `cohort_signals` total | **11.23 MB** | **4.37 MB** |
| **bytes per arm** | **3,078.7 B** | **1,128.4 B** |

**−63.3% payload per arm**, on comparable samples.

Interning applied everywhere it should: **0 inline flag sets remain post-deploy**, every index
resolves inside its table, and a spot check confirms one table entry carries the complete
88-flag set (2,521 B) recoverable by index.

### Cumulative effect of rounds 120-8 and 120-9
Per arm: **~11,300 B → ~1,128 B, about −90%.**

## 4. A measurement trap I walked into, and how

My first verification sampled the **last 40 rows** on each side and reported per-arm
**1,123.7 → 1,128.1 B (−0.4%)**, i.e. "the fix did nothing". That was wrong. Those particular
40 rows happened to carry almost no inline `mechanism_flags`, so there was nothing for the
interning to remove.

Widening to 150 rows per side (130/135 usable rows, 3,647/3,876 arms) surfaced the real
−63.3%. **The sample was the problem, not the change** — and reporting the first number would
have been a false negative that could have caused a working fix to be reverted.

Recorded because it is the mirror image of the traps already in this file: the previous rounds
were about *false positives* ("0 of 18 pools can form a window"); this one was a **false
negative from an unrepresentative sample**, which is just as costly and harder to notice because
it looks like a null result.

## 5. What is left in the payload

After both reductions the residual per arm is ~1,128 B. From the round-120-8 breakdown the
remaining named components are `decision_key` + `episode_id` at 266 B per arm, where
`decision_key = episode_id + ':' + arm` (`alpha149.py:2290-2291`), so one of them is derivable —
worth ~10% and not yet done. The rest is the per-arm signal scaffolding itself.

The original driver — DB growth of ~7 MB per 10 minutes (~1 GB/day) — should now be roughly
halved; the DB was 1,031 MB at the start of this round. That is the number to re-measure over a
longer window rather than assert from one deploy.

## 6. Priority list after this round

| # | action | state |
|---|---|---|
| **P0-1** | Re-measure DB growth over a comparable multi-hour window to quantify rounds 120-8/9 together | measurement |
| **P0-2** | Supply-weighted observation caps (`observation_leases145` per-chain caps) — needs a discovery-share signal threaded through four live enforcement sites | designed, ready |
| **P0-3** | EXIT150 forward samples via `paired_arm_ab.py` at ≥20 settled per side | live |
| P1-1 | Drop the derivable duplicate between `decision_key` and `episode_id` (~10% of the residual) | priced |
| P1-2 | Standing loop: `supervise_metrics.py` + `trade_context_ledger.py` | in use |
