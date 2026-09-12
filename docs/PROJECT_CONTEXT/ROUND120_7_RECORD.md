# Round 120-7 record — the allocation mismatch is real; the 63%-of-DB payload is load-bearing

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r7_*.py`. **No production behaviour changed.**

Two findings this round. Both are real. Neither was executed, and in the second case the reason
is a safety discovery that matters more than the optimization would have.

---

## 1. CONFIRMED (large sample) — observation is not allocated in proportion to supply

| chain | discoveries/h | snapshots/h | **snapshots per discovered token** |
|---|---|---|---|
| solana | **8,012 (46.3%)** | 3,717 (34.2%) | **0.5** |
| bsc | 5,882 (34.0%) | **4,845 (44.6%)** | **0.8** |
| robinhood | 3,392 (19.6%) | 2,301 (21.2%) | 0.7 |

**The chain that produces the most tokens receives the least observation per token.** The cause
is structural: `observation_leases145.BASE_CAPS = {early 3, growth 4, mature 3}` with
`CHAIN_CAP = 10` is applied **per chain**, so each of three chains gets ~1/3 of the 30 slots
regardless of how many tokens it produces. The mover registry is skewed the same way and worse:
**bsc 13, solana 9, robinhood 2** — BSC holds the most mover slots while producing *fewer* tokens
than Solana.

This part rests on thousands of rows (8,012 vs 5,882 discoveries; 3,717 vs 4,845 snapshots), so
the **proportionality** claim is solid.

**The outcome side is NOT solid.** BSC 66.7% dead (6/9) vs Solana 0.0% (0/8) — but the whole
epoch has traded only **18 distinct tokens**, of which **6** were written off. Pooled with the old
device's large-n result (216 of 686 BSC positions written off = 31.5%; Solana 0 of 1,599;
Robinhood 0 of 184) the direction is consistent, but on this device alone it cannot carry a
reallocation.

### Designed fix — NOT executed
Replace the fixed `BASE_CAPS`/`CHAIN_CAP` with caps **weighted by each chain's recent discovery
share**, with a floor (so no chain is starved) and a ceiling (so a discovery burst cannot capture
the whole watch). This is a principled supply-proportional rule that does not depend on the thin
death-rate evidence.

**Why it was not executed:** it changes the observation supply of **every existing arm**, not just
new ones. The user has authorised one such change before (round 88, 8 reserved watch slots) but
this is a larger structural change to a shared scheduler, and the result would be a coverage
shift whose effect cannot be attributed within the remaining samples of this epoch. Recorded as a
ready-to-execute item with its numbers, for a round where it can be implemented, tested against
`supervise_metrics.py`, and watched.

## 2. FOUND (payload) — 63% of the database is one repeated feature vector, and it is LOAD-BEARING

`cohort_observation` rows dominate the payload outright:

| reason | rows | total payload | avg | max |
|---|---|---|---|---|
| **cohort_observation** | **6,762** | **582.2 MB** | **86,101 B** | **444,925 B** |
| pattern_observation | 4,142 | 11.8 MB | 2,849 B | 9,054 B |
| no_active_matching_entry_policy | 6,534 | 11.0 MB | 1,681 B | 1,784 B |
| (all others) | 3,668 | 0.4 MB | ~30–200 B | — |
| **total** | 21,106 | **606 MB** | | |

Database on disk: **920.7 MB**, so those observation rows are **63% of the file**. Inside one
98 KB row:

| key | bytes | share |
|---|---|---|
| **`cohort_signals`** | **81,188** | **83%** |
| `outcomes` | 13,381 | 14% |
| `event_keys` | 3,300 | 3% |
| everything else (13 keys) | < 200 | <0.3% |

And the repetition is exact: one row's `cohort_signals` held **16 entries at ~7,780 bytes each
carrying the SAME `decision_evidence.feature_vector`** — one feature vector copied 16 times,
differing only per arm. Separately, `outcomes` had **185 entries with only 3 distinct blocker
values**; a grouped form is **135 bytes instead of 13,381** (99× smaller).

So a lossless redesign (hoist the shared feature vector once per row; group the blocker
histogram) would remove roughly **85–90% of 63% of the database** and the same share of its
write rate.

### Why it was NOT executed — a safety discovery
`cohort_signals` is **not telemetry**. It is read on live paths:

| reader | purpose |
|---|---|
| `store.py:28919` | entry projection (`signals=...get('cohort_signals')`) |
| `store.py:34208` | exit path (`signal = ...get('cohort_signals')`) |
| `store.py:27887/27942/28046` | **cohort episode continuity** (`previous_features.get('cohort_signals')`) |
| `cohort_enrollment.py:67` | enrollment claims |
| `narrative_hold.py:258` | hold decisions |
| `mode_learning145.py:234` | mode-learning state |
| `store.py:27787–28130` | the observer body that writes it |

Changing its shape therefore touches the entry, the exit, **and the episode-continuity logic that
decides whether a pool is a new episode**. Doing that on a live forward epoch, in the last third
of a round, with no migration plan, is precisely the class of change this session has repeatedly
refused after measurement. **Recorded as a designed optimization requiring a migration plan and
its own round.**

## 3. What this round changes

**Nothing in production.** Two findings recorded: one confirmed structural mismatch with a
designed fix, and one large, safe-looking optimization that turned out to sit on four live code
paths.

## 4. Priority list after this round

| # | action | state |
|---|---|---|
| **P0-1** | **Payload reduction on `cohort_signals`** — needs a reader migration (`store.py` ×3 paths, `cohort_enrollment`, `narrative_hold`, `mode_learning145`), then a lossless format. Largest single measurable improvement available (63% of the DB, ~50%+ of write rate) | designed, needs its own round |
| **P0-2** | **Supply-weighted observation caps** — changes every existing arm's observation supply; execute only with a before/after on `supervise_metrics.py` | designed, ready |
| **P0-3** | Let EXIT150 accumulate forward samples; read with `paired_arm_ab.py` at ≥20 settled per side. The hard stop is the second loss engine (−933.25U all-time) and `exit150_widestop` targets it | live, 18 positions so far |
| P1-1 | Keep using `supervise_metrics.py` + `trade_context_ledger.py` + `paired_arm_ab.py` as the standing loop, counting by independent cohort | in use |

## 5. Method note

Five hypotheses have now been killed or deferred by measurement across rounds 120-5/6/7 (depth
budget, mark supply, frame freshness, gap tolerance, payload shape) and one of them was a bug in
my own probe. The two findings this round were kept **because** the second measure changed the
answer — the payload optimization looked like a free win until the reader grep showed it feeds
the entry, the exit and the episode logic. **Measure the consumers before measuring the
savings.**
