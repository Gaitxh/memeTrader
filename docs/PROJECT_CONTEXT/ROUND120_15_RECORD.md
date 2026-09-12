# Round 120-15 record — the entry-quality discriminator is trading ACTIVITY, not liquidity or age (n=10 tokens, so: monitor, do not ship)

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r15_*`. **No production change.**

Round 120-14 established that 76 of 251 hard stops are tokens that reached ~0 within a median of
105 seconds, and concluded the only lever left is entry selection. This round asked the falsifiable
version of that: **at the moment of the decision, was anything observable that separates them?**

---

## 1. Method, and two join defects worth recording

Features come from `chain_meme_trader_v6_entry_evaluations.feature_json`, written **at** the
decision, so every one is point-in-time by construction. The label ("settled at ≤10% of entry") is
the future outcome and is used only to test separation.

Two joins had to be fixed before any number was trustworthy:

1. **The cohort's `source_snapshot_id` often has no matching evaluation row.** Cohort 276 carries
   `source_snapshot_id=29272` while that token's newest evaluation is at snapshot 28324, ~3 minutes
   earlier. An exact join returned **0 of 1,112 positions matched** — a silent, total failure that
   would have looked like "no data". Replaced with *the most recent evaluation carrying entry
   features at or before the cohort's `decided_at`*, i.e. the point-in-time evidence the decision
   could actually have read: **1,117 of 1,124 matched**.
2. **`buy_count_share` is absent** from every matched row (0 observations on both sides), so it is
   reported as unavailable rather than as a zero.

## 2. Result — activity separates, liquidity and age do not

| feature | n(died) | p50 died | n(survived) | p50 survived | ratio |
|---|---|---|---|---|---|
| **`m5_trades`** | 294 | **11** | 786 | **59** | **0.19** |
| **`m5_volume_usd`** | 294 | **1,896** | 786 | **15,380** | **0.12** |
| `h1_trades` | 294 | 24 | 786 | 123 | 0.20 |
| `volume_rate_acceleration` | 294 | 5.57 | 786 | 21.88 | 0.25 |
| `tx_rate_acceleration` | 294 | 14.35 | 786 | 17.29 | 0.83 |
| `signal_age_seconds` | 294 | 0.267 | 786 | 0.152 | 1.76 |
| **`entry_liquidity_usd`** | 294 | **44,070** | 822 | **43,030** | **1.02** |
| `age_seconds` | 294 | 428 | 786 | 470 | 0.91 |
| `prior55_trades` | 294 | 13 | 786 | 10 | 1.30 |

**Tokens that die fast had 5–8× less trading activity at entry** — fewer 5-minute trades, far less
5-minute volume, less hourly activity and lower volume acceleration — **while entry liquidity and
pool age do not separate them at all.**

That is mechanically sensible (a token nobody is trading is a token with no bid when holders
leave) and it is the first entry-side signal this session has found that is both point-in-time
available and directionally large.

**However every interquartile range still overlaps**, so this is a distribution shift, not a
threshold. A floor at, say, `m5_trades >= 30` would exclude most of the died group and roughly a
third of the survivors — useful, but not clean.

## 3. The reason nothing was shipped: n = 10 tokens

**The 294 "died" positions belong to 10 distinct tokens.** Positions are fanned ~30× per token, so
every rate above is a token-level rate in disguise with an effective sample of **ten**. Nine of them
are BSC rugs. **Registering arms on that is precisely the overfitting the cross-session synthesis
warned about, and it is the same trap as the round-120-3 `frame_count = 76` lease: a real
observation and a bad sample.**

The chain split is the one result with more support and it is consistent across both devices:

| chain | n | died | rate |
|---|---|---|---|
| **bsc** | 594 | 225 | **37.9%** |
| **solana** | 467 | 69 | 14.8% |
| robinhood | 56 | 0 | **0.0%** |

(Old device, token level: BSC 40.4% / Solana 3.4% / Robinhood 0.0%; 24 h: 216 of 686 BSC positions
written off, Solana 0 of 1,599.)

## 4. What is ready to execute when the sample justifies it

A **new additive arm family** whose entry requires a minimum entry-time activity floor, e.g.
`m5_trades >= 30` **and** `m5_volume_usd >= 5,000`, as a new mechanism kind plus new arms — no
existing strategy touched. The current gate's weakest path (`market_visible`, the fallback family)
imposes **no activity requirement at all**, while `broad_launch` requires only 3 trades or 200 USD;
so an activity floor is genuinely additive rather than a tightening of an existing rule.

**Not registered**, because:
* the died group is 10 tokens;
* the interquartile ranges overlap, so a threshold's error rate is unmeasured;
* and the honest reading of §2 is "activity is worth watching", not "activity is a filter".

What *was* done is the durable half: the measurement is recorded with its exact join, its exact
feature list and its exact caveat, so the next round re-runs it in one command instead of
re-deriving it.

## 5. Priority list after this round

| # | action | evidence |
|---|---|---|
| **P0-1** | Re-run this separation as the settled-position count grows; promote to arms only when the died group is ≥30 **tokens** with non-overlapping quartiles | §2, §3 |
| **P0-2** | Reduce the evaluation write RATE (74% of measured DB growth; 53% of rows can never admit) — verify the `previous_features` continuity dependency first | round 120-11 |
| **P0-3** | Observation-slot admission probe (5/9 leases held by provider-silent pools up to 900 s) | round 120-12 |
| P1-1 | EXIT150 to ≥20 settled per side, then `paired_arm_ab.py` | 13 tier fills so far |
| P1-2 | Price-only-collapse classification (n=3 tokens) | round 120-14 |

## 6. Method note

The round's most transferable output is the **join defect**: an exact join on
`(token_id, source_snapshot_id)` returned a clean, plausible, entirely empty result. Nothing about
that empty result looked like a bug — it looked like a system with no features. **A query that
returns 0 rows must be distinguished from a query that is wrong, before the 0 is interpreted.**
That is the fourth measurement error this session traced to the metric rather than the system, and
the first one that took the form of a silent empty join.
