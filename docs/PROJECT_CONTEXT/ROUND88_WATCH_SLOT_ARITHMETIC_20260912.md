# ROUND 88 — The watch-list cannot reach its own flags: a slot arithmetic problem

Date: 2026-09-12 (local) / 2026-09-12T09:25–09:40Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
No source change this round. This round quantifies why the fix proposed in round 87 is not a small
patch, and puts the resulting decision to the user.

## 1. The watch is saturated

`kv['chain-meme-pattern-watch']` reports **watched 35, sampled 8, projected 0**, with
`non_held_by_chain_bucket` exactly at its caps (bsc/robinhood/solana each 3 early + 4 growth +
3 mature = 10 per chain, **30 slots**), plus 19 borrows and 20 replacements since start. The watch
is therefore full, and a pass samples only **8** tokens.

That is the mechanical reason round 87 found the reach defect: a flagged token can only be protected
if it already holds one of those 30 slots, and 30 slots cannot hold 335 flagged tokens per hour.

## 2. The slot arithmetic

The mover rule flags about 14% of newly observed tokens; the system observes about 2,400 new tokens
per hour, so about **335 flagged tokens per hour**. A 15-minute lease means one slot serves four
tokens per hour:

| share of the watch reserved for flagged tokens | slots | flagged tokens/hour served | share of all flagged |
| --- | --- | --- | --- |
| 10% | 3 | ~12 | 3.6% |
| 25% | 8 | ~32 | 9.6% |
| 50% | 15 | ~60 | 17.9% |
| **100%** | **30** | **~120** | **35.8%** |

Serving every flagged token would need about **83 slots, 2.8x the entire current watch**.

Two consequences:

1. **A threshold rule cannot work at this flag rate.** The watch-list must be **ranked** - score
   candidates and take the best N per hour - instead of admitting everything that passes a
   threshold first-come. The current implementation is the latter, which is why 94 flagged tokens
   produced 3 observations each.
2. **Reach requires displacement.** Because the watch is saturated, any share reserved for flagged
   tokens comes directly out of the slots that currently observe young pools for the existing
   strategies. That is a change to existing strategies' observation supply, not an additive change,
   and it is the user's call rather than mine.

## 3. What is already established, so the decision is narrow

- Observation density is causally the entry-conversion constraint: **102 sparse ready pools
  converted 0 times** (round 87, larger sample) against ~50-100% for dense pools (round 86).
- The approved +13-14% acquisition budget is being spent: measured **+13.7%** added volume at the
  current 24-slot cap (round 86b).
- The mover rule's own discriminating power is modest and honest: lift **1.6-2.0x**, recall 6-9%
  (round 83, reconciled with the independent agent).
- What the money is **not** yet buying is reach: the funded watch protects only tokens that already
  hold one of 30 saturated slots.

## 4. The decision

To make the watch-list reach its target tokens, a bounded share of the pattern watch must be
reserved for flagged tokens. The three options and their measured cost are in section 2. Without
one of them the honest conclusion is that the coverage gap stays where it is: the budget is spent,
the mechanism is proven, and the allocation cannot be changed additively because the watch is full.

## 5. Next iteration

1. Whichever share is chosen, replace threshold admission with **ranked** admission so the reserved
   slots go to the highest-scoring candidates rather than the first to arrive.
2. Re-measure the same three probes after the change: added acquisition volume (must stay near
   +13%), flagged tokens reaching >=10 observations, and the round-80 conversion table split by
   dense/sparse.
3. Keep "102 sparse ready pools, 0 conversions" as the fixed baseline for any coverage work.
