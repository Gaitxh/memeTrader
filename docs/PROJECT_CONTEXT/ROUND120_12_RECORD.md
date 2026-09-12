# Round 120-12 record — the observation slots are UNDER-serving, not over-serving, and the fix belongs at admission

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r12_*`. **No production change this round.**

---

## 1. The hypothesis I brought in

Watched pools are observed at a 1.4–2.7 s median cadence (round 120-6) against a ~30-frame design
target, so a pool should reach the target in roughly 60–80 seconds — while the lease config looked
generous (`EARLY_LEASE_SECONDS=120`, mover `WATCH_SECONDS=900`). One earlier lease sample showed
`frame_count = 76`, which suggested pools were **over-observed** and that shortening the hold would
cycle more tokens through the same 30 slots with **no extra HTTP requests** — a request-neutral
coverage win on the user's oldest complaint.

## 2. Refuted, and the reality is the opposite

| live lease | bucket | **frames** | held | lease |
|---|---|---|---|---|
| `solana:7n4d2QokuGvx…` | early | 14 | 267 s | 900 s |
| `solana:BRkD9bhAyTLJSU…` | early | 8 | 178 s | 900 s |
| `solana:5zvfdeJK8V6vVbx…` | growth | 3 | 59 s | 900 s |
| `solana:3FWeYB4YcixHxde…` | growth | 2 | 48 s | 900 s |
| `robinhood:0xab7563ea…` | early | 1 | 83 s | 900 s |
| `robinhood:0xbd91e635…` | early | 1 | 83 s | 900 s |
| `solana:4quNBe5gXoxYRBn…` | early | 1 | 88 s | 900 s |
| `solana:C19AjfFAhb79gnL…` | early | 1 | 88 s | 900 s |
| `solana:GxVwjZjhAve6J8m…` | growth | 1 | 17 s | 900 s |

* **leases at or past the 30-frame target: 0 of 9** — nothing is over-observed.
* **8 of 9 received only 1–9 frames** while holding a slot for 48–267 seconds.
* Every lease runs **900 s** (`WATCH_SECONDS`), not 120 s.
* Only one pool reached 30 distinct frames, taking **174 s**.

`TARGET_SECONDS = 15` implies a leased pool should be re-selected about every 15 seconds, so 88
seconds of holding should have yielded roughly 5–6 frames, not 1.

**So the 30 slots are not being spent on redundancy — they are being spent on pools that receive
almost no data.** The round-120-6 cadence figure (1.4–2.7 s) is real but describes the *few* pools
that are well served; it is not the population's cadence.

## 3. Where the failure actually is

The frames are not missing because the scheduler ignores these pools — they are leased and they
are due. They are missing because **the provider has nothing to return for them**. Two independent
pieces of evidence already in this session's data point the same way:

* earlier lease payloads carried `window_results: {"30": "SOURCE_NO_UPDATE"}` — the provider
  reported no update, not a scheduling gap;
* the old session measured **2,272 `quote_returned_no_pair` results over 1,860 tokens**, i.e. a
  large population of discovered tokens for which no DEX pair (or no fresh pair data) exists yet.

Combined: **the watch admits pools that have no market data, grants them a 15-minute lease, and
receives ~1 frame for it.** That is a slot-efficiency defect, but it is an **admission** defect, not
a hold-time defect — and the opposite of the change the hypothesis proposed. Shortening the lease
would not have fixed anything; it would have cycled slots faster through pools that still return
nothing.

## 4. The classification, measured in the same round

The three candidate causes were separated on the live leases:

| verdict | leases | meaning |
|---|---|---|
| `NEVER_OBSERVED_SINCE_ADMIT` | **0** | the scheduler *is* reaching them — **case 1 ruled out** |
| **`IDENTICAL_VALUES`** | **5 / 9** | the provider returns unchanged numbers, so the trajectory engine legitimately refuses them as duplicates — **case 2** |
| `VALUES_CHANGE` | 4 / 9 | data is genuinely moving; these got 3–16 frames |
| engine refusal ratio | **11.0%** (265 / 2,419) | low, so **case 3 is not the problem** |

The provider signal is visible in the lease payload itself: pools whose frames come from
**geckoterminal** carry `windows: {"30": "SOURCE_NO_UPDATE"}`, while the **dexscreener**-sourced
ones carry `{"30": "OBSERVED"}`.

**So the dominant cause is provider silence for freshly discovered pools.** The watch admits a
young token, grants it a 900-second lease, and the DEX aggregator has no update to return for it —
so the slot is consumed for up to fifteen minutes in exchange for one or two frames.

**This is an ADMISSION defect, not a hold-time defect, and the exact opposite of the hypothesis
this round started from.** Shortening the lease would have cycled slots faster through pools that
still return nothing; the candidate fix is to **probe a candidate's provider before granting a full
lease** (a short trial window, or requiring an observed value change), so a silent pool releases
the slot almost immediately.

**Not executed**, because n = 9 live leases, and because the same measurement shows the mirror
duplication rate — 513 of 2,286 `(token, observed_at)` groups in ten minutes carry more than one row
(22.4%) — which means part of the "few frames" reading is the `strategy-observer:` mirror rather
than genuine silence. Both need a larger sample before a change is justified.

## 5. Priority list after this round

| # | action | why |
|---|---|---|
| **P0-1** | Classify the no-frame leases as in §4, then decide | determines whether the fix is admission gating, scheduling, or nothing |
| **P0-2** | Reduce the evaluation write RATE rather than the row size (round 120-11: 74% of measured growth is evaluations at 246 rows/min; 51% of rows are observation-only and can never admit) — but check `previous_features` first, because `store.py:27787` reads the previous evaluation row for episode continuity | growth |
| **P0-3** | EXIT150 forward samples via `paired_arm_ab.py` at ≥20 settled per side (36 positions) | money |
| P1-1 | Supply-weighted observation caps | designed |

## 6. Method note

This is the fifth hypothesis in six rounds killed or redirected by a single measurement, and the
second whose *direction* was inverted by it (round 120-7 expected the payload field to be
unread telemetry; it was live). The pattern that keeps paying is the same one: **before changing a
mechanism, measure the population the mechanism actually acts on — not the example that suggested
the change.** The `frame_count = 76` lease that motivated this round was a real observation and a
bad sample.
