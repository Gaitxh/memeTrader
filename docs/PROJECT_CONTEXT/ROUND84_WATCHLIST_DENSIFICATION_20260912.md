# ROUND 84 — The approved densification, implemented and measured

Date: 2026-09-12 (local) / 2026-09-12T08:36–09:00Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
Source changes: `mover_watchlist.py` (cap), `runtime.py` (protected leases + frame cap).
Reloads: 16:36:19 and 16:48:27 (+08:00).

## 1. Why round 83's priority hook changed nothing

Round 83 added the watch-list and a `priority_first` ordering but measured an unchanged 90.4 s
median inter-observation gap. The reason was found in the observer's own lease checkpoint
(`kv['chain-meme-pattern-watch:leases145']`): the observer **watches ~35 tokens but most carry
`frame_count = 1`**, with `replacements_since_start` climbing. It rotates through tokens instead of
holding any of them, so a token is seen once and replaced - and reordering due work cannot fix a
rotation policy.

## 2. The change

A flagged token is now added to the observer's existing **`protected`** set, which already means
"do not release and do not replace". Two bounds keep it inside the approved budget:

| bound | value | why |
| --- | --- | --- |
| concurrent watch slots | **12** | 12 slots x 4 fifteen-minute windows per hour = 48 tokens/hour, the "+14% requests, about 49 tokens per hour" that was approved. Without it the registry could protect most of the 35-token watch and starve rotation. |
| frames per token | **30** (`MOVER_FRAME_TARGET`) | 30 frames over 15 minutes is one per 30 s, twice the cadence the entry layer's 60-second rule needs. Measured uncapped, a protected token took **60 observations in 10 minutes**, about 6x the requirement and about **+38%** of the whole acquisition volume instead of +13%. |

## 3. Measured result

Tokens whose first snapshot falls after the 16:36 reload, de-duplicated by
`(token_id, observed_at)` because `strategy-observer:X` mirrors `X` at the same timestamp:

| group | tokens | obs in first 10 min p50 | p90 | deepest |
| --- | --- | --- | --- | --- |
| flagged by the rule | 26 | 2 | **20** | **60**, 41, 20 |
| everything else | 205 | 1 | 11 | - |

Before this round no token in the system exceeded ~7 frames in a lease. Three flagged tokens now
reached **60, 41 and 20 observations inside their first ten minutes** against a population median of
2 - densification that did not exist before, on exactly the population the mover rule selects.

The cap's effect is visible but not yet settled: in the post-cap window the flagged p90 fell from 20
to 4 observations in ten minutes, and no token seen after 16:48 has yet reached the 30-frame target
(the window is only ~9 minutes old). **The capped steady state - expect roughly 12 concurrent dense
tracks at ~30 frames, about +13% volume - is confirmed next round, not this one.**

## 4. What this does and does not claim

- It does **not** yet claim more entries. The entry layer needs two evaluations of the same pool
  inside 60 seconds; a 30-frame track at 30-second spacing now satisfies that requirement, but
  whether it converts into admissions and positions is the next measurement.
- It does **not** claim the mover rule is a detector. Reconciled honest lift is 1.6-2.0x with 6-9%
  recall, and 43% of movers have already peaked five minutes after first sighting.
- The three dense tracks prove the mechanism; they are three tokens, not a population.

## 5. Next iteration

1. Confirm the capped steady state: concurrent dense tracks should sit near 12, per-token frames
   near 30, and the added snapshot volume near +13%.
2. Measure conversion: of the flagged tokens that received dense observation, how many reach
   `cohort_frozen_opportunity_ready` **twice inside 60 seconds** and then an admitted decision,
   against the 5.1% ready-to-admitted baseline from round 80.
3. If the densified tokens still do not convert, the binding constraint is no longer observation
   density and the watch-list should be judged on that negative result rather than extended.
