# Round 120-11 record — the cohort table was half the payload story, and the real driver is the WRITE RATE

Date 2026-09-13. Deploy boundary **20:59:57Z**. Epoch
`chain-meme-trader/funding-20260906-v002-final-1000`. Scripts `data/research/diag_round120/r11_*`.

---

## 1. Found the second-biggest payload object — the same dict, a different table

Payload by table (all-time), measured by summing `LENGTH()` over every TEXT/BLOB column
(`dbstat` is not compiled into this SQLite build):

| table | text MB | rows | **B/row** |
|---|---|---|---|
| `chain_meme_trader_v6_entry_evaluations` | 732.4 | 25,697 | 28,500 |
| token_snapshots | 47.7 | 25,643 | 1,861 |
| **`chain_meme_trader_v6_cohorts`** | **42.0** | **239** | **175,715** |
| tokens | 30.6 | 8,019 | 3,821 |
| chain_meme_pattern_evidence | 29.0 | 9,946 | 2,911 |
| provider_post_ambiguity_admissions | 16.5 | 92,998 | 178 |
| token_universe_funnel_transitions | 15.4 | 31,400 | 489 |

**`chain_meme_trader_v6_cohorts` stores 176 KB per row over only 239 rows** — and it is the
**same `features` dict** that rounds 120-8/9 fixed on the evaluation side. I had applied the
compaction to the two evaluation INSERTs and missed the two cohort INSERTs
(`store.py` ~28205 and ~29683). Fixed this round by passing the same already-tested
`_compact_cohort_signals_for_storage` at both.

**Reader safety re-verified before deploying**, because the cohort row is the one the live
readers actually use:

| cohort reader | consumes |
|---|---|
| `store.py:28932` → `distinct_trajectory` | `frozen['pair_address']`, `frozen['observed_at']` (kept) |
| `store.py:28956` → synthetic-exit gate | `evidence.get('phase')` (kept) |
| `store.py:34321` → exit router | `decision_evidence.get('router_mode')` (kept) |

None of them touches the rest of `feature_vector` or `mechanism_flags`. Confirmed on the live
row: **53 of 53 arms satisfy the cohort reader** and `router_mode` is still present.

**Measured:** post-deploy cohort rows averaged **77,302 B vs 175,490 B, −56%**, and the write rate
fell from **~220 to 108 KB/min (−51%)**.

**Stated honestly: that is 4 rows with arm counts from 22 to 53**, against a historical
population of 239 rows. The percentage is indicative, not a measurement, and the per-arm figure
is the one that should be quoted once a larger sample exists. It is not quoted as −56% anywhere
outside this paragraph.

## 2. The reframe: growth is driven by the WRITE RATE, not the row size

Write rates over a 10-minute window:

| table | KB/min |
|---|---|
| **`chain_meme_trader_v6_entry_evaluations`** | **3,892** |
| token_snapshots | 431 |
| chain_meme_pattern_evidence | 227 |
| chain_meme_trader_v6_cohorts | 220 → **108** after this round |
| provider_post_ambiguity_admissions | 163 |
| token_universe_funnel_transitions | 116 |
| tokens | 88 |
| (smaller tables) | ~105 |
| **sum of the above** | **~5,240** |

The file grows **~7.3 MB/min**, and **evaluations alone are ~3,892 KB/min — about 74%** of the
measured total. Rounds 120-8/9 cut the per-row size by 46%, and growth barely moved, because the
system writes **2,456 evaluation rows per 10 minutes = 246 rows/min**.

**So both payload rounds optimised the right object at the wrong lever.** Further reduction
requires writing **fewer rows**, not smaller ones. That inverts the follow-up: the round-120-1
measurement that **51% of evaluation rows are observation-only** (`cohort_observation` +
`pattern_observation`) and can never admit is the lever — those rows exist to record a per-arm
blocker histogram, which is statistical rather than per-row evidence, so **sampling them (e.g.
1 in N) would cut growth proportionally at little diagnostic cost.** That is the next item, and
it changes row *count*, which no amount of per-row compaction can substitute for.

## 3. Priority list after this round

| # | action | why |
|---|---|---|
| **P0-1** | **Reduce the evaluation write RATE**, not the row size — sample the observation-only rows (51% of rows, statistically redundant) instead of writing every frame | §2: 74% of measured growth is evaluations at 246 rows/min |
| **P0-2** | Supply-weighted observation caps (`observation_leases145`, per-chain) — designed, needs a discovery-share signal through four live enforcement sites | coverage |
| **P0-3** | EXIT150 forward samples via `paired_arm_ab.py` at ≥20 settled per side | money |
| P1-1 | Re-quote the cohort and evaluation savings on a larger sample with a per-arm metric | honesty |

## 4. Method note

The per-row-versus-per-unit trap caught this session three times (rounds 120-8, 120-9, 120-10).
This round it caught the *conclusion* rather than a number: two rounds of per-row reduction that
moved the aggregate rate by almost nothing, because the aggregate is rate-driven. **A payload
metric without its row rate beside it is not a growth measurement.** That is now the standing
rule for this table.
