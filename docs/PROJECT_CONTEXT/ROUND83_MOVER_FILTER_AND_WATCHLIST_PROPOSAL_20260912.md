# ROUND 83 — A replicated mover filter, and the quantified watch-list proposal

Date: 2026-09-12 (local) / 2026-09-12T07:20–07:35Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
No source change this round. The measurement below is the input for one budget decision.

## 1. The first entry rule this session to survive every test

Point-in-time features only (read from the token's **first** observation), label = `max(price in the
following 60 minutes) / first price >= 2.0`. Time-split, chosen on the first 70% of a six-hour
window and scored on the held-out last 30%:

| rule | train flags / precision / lift | **held-out flags / precision / lift** |
| --- | --- | --- |
| **`liq >= 20k AND buy share >= 0.6`** | 14.6% / 18.3% / 1.78 | **12.2% / 24.4% / 2.37** |
| `liq 5k-20k` | 29.3% / 13.7% / 1.33 | 25.7% / 18.8% / 1.82 |
| `liq 20k-100k` | 17.5% / 19.5% / 1.90 | 18.7% / 15.8% / 1.54 |
| `turnover >= 0.3` | 21.0% / 10.8% / 1.05 | 16.7% / 15.0% / 1.45 |
| `buy share >= 0.6` alone | 60.5% / 12.7% / 1.23 | 63.7% / 14.2% / 1.38 |
| `liq >= 100k` | 6.6% / 2.0% / 0.20 | 6.6% / 2.4% / **0.23** |
| `chain != bsc` | 65.7% / 6.3% / 0.61 | 60.1% / 4.9% / **0.48** |
| `liq >= 20k AND turnover >= 0.3` | 2.7% / 5.0% / 0.49 | 1.9% / 8.3% / 0.81 |

Then re-run **without re-fitting** on three independent six-hour windows:

| window | tokens | base rate | rule flags | precision | lift |
| --- | --- | --- | --- | --- | --- |
| last 6h | 2,138 | 10.2% | 13.8% | 19.9% | **1.95** |
| 6-12h ago | 1,900 | 10.4% | 14.4% | 14.3% | **1.38** |
| 12-18h ago | 1,539 | 11.5% | 15.0% | 16.0% | **1.39** |

So `liq >= 20k AND buy share >= 0.6` has a lift of **1.4-2.4x** with a stable 14-15% flag rate
across four independent measurements. It is the first entry scalar this session that has not been
falsified (turnover twice, buy share alone at token level, hold duration, the early take-profit
ladder, whipsaw guards).

Two results that matter in the other direction:

- **`liq >= 100k` has a lift of 0.23** — deep pools essentially never double. This is a
  pre-registered prediction for wave 42: `alpha149_deep_pool_flow_v1` should show a **low write-off
  rate together with a low upside**. If it shows a good return, something is wrong with the model.
- **`chain != bsc` has a lift of 0.48** — BSC pools double roughly twice as often as the rest,
  which is why the wave-42 `nonbsc_flow` gate trades mover rate for pool safety (BSC dies at 40.4%
  against Solana's 3.4%). Both arms are a real trade-off, not a free improvement.

## 2. The confound, stated

**43% of movers peaked within five minutes of their first observation** (95 of 220 in the six-hour
window). For those a watch-list is already too late; the remaining 57% peaked later and are the
population a watch-list can act on. This bounds the idea: it can help at most about half the
movers, and only if the observation starts at the first sighting.

## 3. The complete value chain (last 6 hours)

| quantity | value |
| --- | --- |
| tokens measured (>=5 observations) | 2,136 |
| tokens that doubled within an hour of first observation | **217** |
| tokens the rule would flag | 294 (13.8%) |
| movers inside the flagged set | 58 (19.7% precision, lift 1.95) |
| tokens the system actually entered | 46 |
| movers the system entered | **11 (5.1% of all movers)** |
| flagged movers the system entered | **4 (6.9% of flagged movers)** |
| cost of watching the flagged set at 30 observations over the first 15 minutes | **8,820 snapshots per 6h, about +14%** over the 63,307 already stored |

The gap is precise: the entry layer requires two evaluations of the same pool within 60 seconds
(round 80), the median token is refreshed once every **89.8 seconds** (round 80), and there is **no
free capacity** — the spare-capacity lane has taken 0 of 402 opportunities and low-priority
requests are being cancelled for budget with idle inflight slots (round 81).

## 4. What this round proposes, and why it is a decision rather than an action

A watch-list that flags ~49 tokens per hour at their first observation and observes each for 15
minutes at 30-second cadence costs about **+14% in acquisition requests** and would put the
60-second confirmation requirement inside reach for a population with a **1.95x mover rate**.

That is a request-budget increase, and the user declined one earlier in this session. It is
re-presented because the evidence is materially different now: the earlier request was framed as
"+1-2 addresses per cycle" with no measured benefit, while this one has a held-out lift of 2.37, a
replicated 1.4-2.4x across four windows, a measured 5.1% current mover coverage, and a bounded
+14% cost. **Nothing will be implemented without the user's decision.**

If the answer is no, the honest closing statement is that the coverage gap measured in rounds
79-83 cannot be closed from the data side under the current budget, and the remaining levers are
the ones already recorded: fewer arms per dying pool (same-token cap, declined), or a lower
friction setting (a frozen user-editable contract).

## 5. Monitoring

1. Wave 41-42 are the live experiments; judge with `scripts/paired_arm_ab.py` at >=20 settled per
   side, and check the pre-registered deep-pool prediction in section 1.
2. Re-run section 1 monthly or after any acquisition change: it is the cheapest available test of
   whether the observed surface still concentrates movers.
3. The mover-predictor agent is still running; if its independent result differs from section 1,
   report both and reconcile rather than averaging them.

## 6. Reconciliation with the independent agent, and the watch-list implementation

The independent mover-predictor agent (`data/research/mover_predictor_20260912.md`) reached a
different rule and a lower lift: `first_liquidity <= 20000 AND volume_5m/liquidity > 1.0`, honest
lift **~1.6x** (1.9x under a provider-consistent label), and it published that its own auto-fitted
tree failed held-out (0.0% precision). Its rule and mine point in opposite directions on liquidity,
so both were re-run on one harness (identical dedup, identical label = >=5 observations within 60
minutes of the token's first observation in the window, identical time split):

| rule | last 6h held-out | 6-12h held-out | 12-18h held-out |
| --- | --- | --- | --- |
| mine `liq>=20k & share>=0.6` | 1.90 | 1.18 | 1.69 |
| agent `liq<=20k & turn>1.0` | 2.30 (7 flags) | 2.21 (11) | **1.02** (13) |
| agent `liq<=20k & turn>0.5` | 2.26 (19) | 1.95 (25) | 0.71 (28) |
| union | 1.95 (55) | 1.35 (66) | 1.57 (72) |
| `liq>=20k & share>=0.7` | 2.28 (40) | 1.32 | 2.00 (50) |

Reconciled conclusion: **the honest lift is ~1.6-2.0x, not 2.37x.** My first estimate was a single
split of a single window; the agent's rule has the higher precision but a 3-4% flag rate, tiny
recall, and it fails in the third window, while mine is stable in all three. The union has the best
recall (33-39%) at a 20-25% flag rate. The agent's other findings are adopted as facts:

- `strategy-observer:X` **mirrors `X` at the same `observed_at`**, so every count taken from
  `token_snapshots` without de-duplicating by `(token_id, observed_at)` is inflated. The cadence
  measurements in this round use the de-duplicated form.
- providers disagree by up to 37,000x on the same token and **61.7% of movers peak on a non-first
  provider**, so any peak-based label is provider-dependent; the agent's rule holds under the strict
  provider-consistent label, so its lift is not an artifact.
- `holders` is NULL in all 3.17M rows and `buy_tax_pct` / `sell_tax_pct` / `sellable` / `honeypot`
  in 99.9% — **no safety or tax attribute can be attached to any mover today**, which is a hard
  limit on the user's data-layer request.
- only 1.3% of first-seen **Solana** tokens reach >=5 observations within 60 minutes against 44.5%
  of BSC ones: the dense-observation surface is structurally BSC-heavy while the flag stream is
  Solana-heavy.

## 7. Watch-list implemented, and the first honest result about it

The user approved the +14% acquisition budget. Implemented (all additive):

- `src/memetrader/mover_watchlist.py` — pure, bounded, in-memory `Registry` plus `admission()`,
  which reads **only a token's first observation** and admits on either rule (mid-pool buy share, or
  small-pool turnover). 7 tests in `tests/test_mover_watchlist.py`.
- `observation_leases145.select_due` gained an optional `priority_first` argument (default empty, so
  every existing caller keeps its previous ordering).
- `runtime.py` evaluates the registry where frames are built and passes the active set as
  `priority_first`, plus reports the watch size in the pattern-observer heartbeat.

Measured after the reload (16:25 local): the watch-list is populating (62 mid-pool and 30 small-pool
admissions in a 25-minute window), but **the per-token cadence did not change**: flagged tokens show
a median inter-observation gap of **90.4 s**, identical to unflagged tokens and identical to the
window before the reload (19% of gaps <= 60 s against 15% for the rest).

The reason is now precise: `next_due_at` already targets 15 seconds, the watch set holds only ~29
tokens, and yet the effective cycle is ~90 s for everyone. **The cadence is a global throughput
limit, not a per-token scheduling choice** — so reordering cannot densify, and the approved
increment has to be spent on the observer's throughput rather than on priority. That is the
specified next step, and it is a change to the acquisition path, which is why it is not being
rushed into the live process at the end of a round.

## 8. Status of the user's second and fourth requests

**Exits (request 2):** four independent tests now agree that the exit stack is not where the loss
is — the paired exit-contract comparison (27 of 28 contracts lose on identical opportunities), the
independent agent's family review (19 of 20 variant groups negative, hard stop the only clearly
harmful family, trailing the only clearly good one), the fixed-horizon counterfactual (holding is
worse: -0.065 at 30 minutes, -0.074 at 60), and the requested early take-profit ladder (negative
expectancy of `stake * f * (0.44 - 0.558)`). The exits are already better than any of the proposed
replacements on the measured population.

**Data layer (request 4):** `holders`, taxes, `sellable` and `honeypot` are absent from the
provider payloads the system receives (99.9-100% NULL across 3.17M rows), and the snapshot writer
cannot recover them - verified in round 81 by reading the raw payloads. Holder concentration,
contract permissions and rug linkage therefore cannot be built from the current free sources; they
need a different source or a paid one, which is a user decision, not an implementation gap.
