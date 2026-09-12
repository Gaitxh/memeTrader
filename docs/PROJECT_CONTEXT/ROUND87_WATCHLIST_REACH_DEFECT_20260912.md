# ROUND 87 — The dense-conversion effect is real, but the watch-list is not the one delivering it

Date: 2026-09-12 (local) / 2026-09-12T09:00–09:25Z
Definition version: `chain-meme-trader/funding-20260906-v002-final-1000`
No source change this round. Finding: a reach defect in the watch-list, with the cause identified.

## 1. Larger sample confirms the density effect

Same definition as rounds 80 and 86 (gap from a ready row to the next evaluation of the same pool,
`0 < gap <= 60s`). Window 09:00:17Z to now: **1,103 tokens, 4,456 deduplicated observations, 4,469
evaluations over 1,265 pools**.

| bucket | ready pools | gaps | gaps `<=60s` | converted | conversion | median observations |
| --- | --- | --- | --- | --- | --- | --- |
| flagged + dense | 1 | 2 | 100.0% | 1 | 100.0% | 167 |
| flagged + sparse | 17 | 8 | 50.0% | 0 | **0.0%** | 3 |
| unflagged + dense | 8 | 50 | 94.0% | 4 | **50.0%** | 121 |
| unflagged + sparse | 85 | 42 | **0.0%** | 0 | **0.0%** | 3 |

**Sparse ready pools: 102, converted 0 (0.0%).** That is now a much larger sample than round 86's
60, and it is still exactly zero, which makes it the most robust number in this series. Dense pools
convert at 50-100% on 9 pools.

## 2. But the watch-list is not what makes them dense

The equal-density test I set out to run is not yet answerable: `flagged+dense` holds **one** pool.
More importantly, the measurement shows something I did not expect:

- only **1** flagged token reached >=10 observations in the whole window (47 tokens overall did);
- the dense pools' **median observation count is 121-167**, i.e. four to five times the 30-frame
  watch-list target. Those are pre-existing hot or held tokens that were always observed densely,
  not tokens the watch-list densified.

So the five conversions of this window come from observation density that the system already had,
and the watch-list's own tokens are sitting in the `flagged+sparse` bucket with a median of **3**
observations. The funded mechanism is not reaching the tokens it was funded for.

## 3. Cause

The registry only *protects* a flagged token that is **already in the pattern watch**:

```python
_item = _watch_now.get(_token)
if _item is None:
    continue          # not in the watch: neither protected nor admitted
```

The pattern watch holds about **35 tokens**, while the mover rule flags roughly **335 tokens per
hour** (14% of ~2,400 newly observed tokens). So the overwhelming majority of flagged tokens are
never admitted to the watch at all, and the cap increase from 12 to 24 slots changed little for
them. This also explains why the added acquisition volume sat at +13.7% while nearly all flagged
tokens stayed at 3 observations: the volume is being spent on the few flagged tokens that happened
to be in the watch.

## 4. Next iteration

1. **Make a flagged token eligible for watch admission** rather than only protecting it if it is
   already there. That is the change the +13-14% budget was approved for, and section 3 explains
   why the previous two rounds did not deliver it.
2. Keep the same two bounds (24 concurrent slots, 30 frames) so the spend stays inside the approved
   envelope; verify with the same added-volume probe (+13.7% at present).
3. Re-run the equal-density test once `flagged+dense` has a real sample; until then the mover rule's
   marginal value over "observe the hot tokens harder" remains unproven, and the round-83 study
   already caps its honest lift at 1.6-2.0x.
4. The robust result to carry forward is negative and useful: **102 sparse ready pools converted 0
   times.** Any future coverage work should be judged against that, not against the dense pools,
   which were never the constrained group.
