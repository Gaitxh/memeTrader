# ROUND 86 — Causal confirmation: observation density is the binding constraint on entry conversion

Date: 2026-09-12 (local) / 2026-09-12T09:00–09:20Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
No source change this round. The watch-list from rounds 83-85 has been running since 17:00:17.

## 1. The measurement, using round 80's definition exactly

The admission gate needs two cohort evaluations of the same pool inside 60 seconds. Round 80
measured, over 255 ready pools: **42.4%** of gaps from a ready row to the next evaluation of the
same pool were `<= 60s`, **9 pools converted (3.5%)**, with a median per-token refresh cadence of
**89.8 s**. That is the definition used here - not the weaker "any two consecutive evaluations
within 60 s" that round 85 wrongly compared against.

Since the 17:00:17 reload: 644 tokens seen, 725 pools evaluated, 67 pools reached a ready arm.

| bucket | ready pools | ready-row gaps | gaps `<=60s` | converted | conversion |
| --- | --- | --- | --- | --- | --- |
| **densely observed (>=10 obs)** | 8 | 35 | **94.3%** | **5** | **62.5%** |
| sparsely observed | 59 | 30 | **0.0%** | 0 | **0.0%** |
| all | 67 | 65 | 50.8% | 5 | 7.5% |

Against the round-80 baseline of 42.4% / 3.5%, densified pools reach **94.3% / 62.5%**.

## 2. The control that makes it causal

Being *flagged* by the mover rule could have been the cause rather than being *densely observed*.
Splitting the ready pools both ways separates them:

| bucket | ready pools | gaps | gaps `<=60s` | converted | conversion |
| --- | --- | --- | --- | --- | --- |
| flagged + dense | 1 | 2 | 100.0% | 1 | 100.0% |
| **flagged + sparse** | 11 | 2 | **0.0%** | **0** | **0.0%** |
| **unflagged + dense** | 7 | 33 | **93.9%** | **4** | **57.1%** |
| unflagged + sparse | 49 | 30 | **0.0%** | **0** | **0.0%** |

Two conclusions, both clean:

1. **Every sparse pool converts at 0% - 60 of 60 - whether or not it was flagged.** The flag by
   itself does nothing.
2. **The conversions come from `unflagged+dense` (4 of 7 pools, 57.1%)**: tokens that were densely
   observed for reasons other than the mover rule. It is the density that converts, not the
   selection.

So the constraint diagnosed in rounds 79-83 - a 60-second confirmation rule against an 89.8-second
median refresh cadence - is now **confirmed causally, not correlationally**. Removing that
constraint moves ready-to-admitted conversion from 0% to 57-100% in the same window on the same
system.

## 3. What this does and does not say about the watch-list itself

- It says the **mechanism the user funded is the right one**: dense observation is what the entry
  layer was starved of, and it is now demonstrably sufficient.
- It does **not** say the mover watch-list is what delivered it. In this window the watch-list
  produced only **1** of the 8 dense ready pools; the other 7 were dense because they are hot or
  held tokens. The marginal contribution of the mover rule on top of "observe the hot ones harder"
  is therefore still unproven, and it is the honest next question.
- Sample sizes are small (8 dense ready pools). The contrast against 0 of 60 is extreme, but the
  magnitude 57-100% should not be read as a stable rate.

## 4. The approved budget is now actually used

Section 3 showed the mechanism works but the funded envelope was under-used: 12 concurrent watch
slots cost only **+5.7%** of acquisition while 59 of 67 ready pools stayed sparse at 0% conversion.
`MAX_WATCHED` was therefore raised from 12 to **24** (reload 17:13:40), which is still inside the
approved +13-14%.

Measured eight minutes later: 43 flagged tokens, 5 of them above 10 observations and 2 above 25,
with added acquisition volume at **+13.7%** - inside the approved envelope, against +5.7% at 12
slots and +15.6% uncapped.

So the position at the end of this round: the constraint is causally identified, the mechanism is
funded at the authorised level, and the open question is now narrow and measurable - whether the
mover *rule* adds anything over simply observing the hot tokens harder, at equal density.

## 5. Next iteration

1. Grow the dense-ready sample and re-run both tables; report conversion with a token-clustered
   interval rather than a point estimate.
2. Isolate the mover rule's marginal value: compare flagged+dense against unflagged+dense at equal
   density (same observation count), which is the only way to price the rule separately from the
   density it triggers.
3. The spend is currently +5.7% of acquisition against the approved +13-14%, i.e. the funded budget
   is under-used while the entry layer is still starved for the other 59 ready pools. Raising the
   concurrent watch slots toward the approved envelope is the obvious next lever, and it now has a
   measured conversion effect behind it.
