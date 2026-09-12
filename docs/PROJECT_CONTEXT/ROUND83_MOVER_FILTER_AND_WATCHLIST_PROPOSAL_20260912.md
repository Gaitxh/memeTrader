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
