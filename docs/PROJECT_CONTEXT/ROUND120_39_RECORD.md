# ROUND 120-39 RECORD — round 36's "58.5% ceiling" is REFUTED: the touchable share is ~64%, and +10,304U is available

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The claim I tested, and why I doubted it

Round 36 recorded as a **standing conclusion**:

> "58.5% of exits are forced by the pool dying or by a one-interval gap that crosses every
> configured level simultaneously. **No stop width, ladder level, trailing rule or time limit can
> act on those.**"

But round 38 had shown the pool-death population peaked at a **median +15.2% econ**. A take-profit
at +15% closes the position *before* the pool dies. So at least some of the "forced" share should be
touchable — and the claim looked like an **ex-post reading of the realized close reason as evidence
about what an alternative rule could have done**.

## 2. It is refuted. The pool deaths were mostly reachable.

Replaying each position's own mark series (2,393 positions), peak econ by **the mechanism that
actually closed it**:

| mechanism | n | peak p25 | **peak p50** | peak p75 | PnL |
|---|---|---|---|---|---|
| **pool death** | 760 | +4.4% | **+15.2%** | +22.7% | −14,839.0U |
| hard stop | 583 | −12.4% | **−7.9%** | +2.7% | −5,316.7U |
| elective | 1,050 | −9.3% | −0.7% | +20.1% | +1,358.1U |

**52% of the pool-death positions reached +15% before dying.** They were not killed by the market;
they were killed by the rules sitting below where the position had already been.

**The conversion test** — for a take-profit at +X%, which forced exits would it have converted:

| target | pool-death hits | hard-stop hits | converted | gain vs actual |
|---|---|---|---|---|
| +10% | 499 | 108 | 607 | **+12,044.6U** |
| **+15%** | **393** | **91** | **484** | **+10,303.6U** |
| +20% | 223 | 88 | 311 | +6,886.8U |
| +30% | 123 | 45 | 168 | +4,194.7U |

At +15%, decomposed by mechanism:

| mechanism | converted | actual | at +15% | delta |
|---|---|---|---|---|
| **pool death** | **393** | −7,499.0U | +1,489.3U | **+8,988.3U** |
| hard stop | 91 | −1,248.3U | +313.9U | +1,562.2U |
| elective | 304 | +1,689.8U | +1,442.9U | −246.9U |

**+8,988U of the gain comes from pool deaths** — precisely the population round 36 called
untouchable. Cost on the elective side is only −247U, because many of those exit above +15% anyway.

## 3. The correct ceiling

Genuinely untouchable = positions that were forced **and never reached the target**:

- pool deaths that never reached +15%: **367** of 760
- hard stops that never reached +15%: **492** of 583
- total **859 of 2,393 = 35.9%**

**So the touchable share is ~64.1%, not 41.5%.** Round 36's number was a property of where the
current rules sit, not of the market.

**The precise error, worth naming:** round 36 read the *realized* close reason as evidence about
what rules could do. The realized mechanism is **conditional on the rules in place** — change the
rule and the mechanism changes. This is the same class of mistake as the earlier gate refinements,
in a new place: **an outcome-conditional statistic used as a counterfactual.**

## 4. Robustness — and it is much stronger than round 17's version

Round 17 first measured a +15% take-profit replay and found **+4,178U on 906 positions**, but with
**83% of the gain in 3 of 24 tokens**, and dropping the best three left only **+715U**. That
concentration is why it was recorded as a forward experiment rather than a result.

On the current, larger population (**2,393 positions, 43 tokens**) the same replay gives:

| check | result |
|---|---|
| gain | **+10,303.6U**, 788 positions converted |
| **token-clustered 90% bootstrap** | **[+5,697, +15,068]U — excludes zero** |
| tokens that gain | **20 of 43** |
| top-1 token share of the gain | **14.0%** |
| top-3 token share | 37.7% |
| **drop the best 1 token** | **+8,861U** |
| **drop the best 2 tokens** | **+7,618U** |
| **drop the best 3 tokens** | **+6,416U** |
| positions | 556 gain / 232 lose |
| top-10% of positions | 55.6% of the gain |

**Dropping the best three tokens leaves +6,416U**, against +715U in round 17. The effect is now
broad across tokens and positions rather than resting on a few. This is the strongest positive
result of the session.

## 5. Honest limits

- **Replay, in-sample on this epoch.** It assumes execution at the first mark at or above the
  target — the same semantics the system already uses for its hard stop, so it is internally
  consistent, but it is not a forward result.
- **Do not re-optimise the level on this sample.** The +10% row (+12,044.6U) beats +15%, but
  choosing the target from the same data is exactly the round-26 selection trap (permutation
  showed 4,000/4,000 shuffles match the best searched cut). The deployed arms use +15% and +25%,
  chosen in round 17 on a different sample; that is the right way to hold the level fixed.
- The gain is concentrated: **top 10% of positions carry 55.6%**.
- It is a **gross** figure — it does not net off the elective-side cost (−247U) nor any execution
  friction beyond the frozen cost model, though the model does include both slippages and fees.

## 6. What this means for the deployed work

`exit150_full15_v1` is **already deployed** and targets exactly this: it sells 100% at +15%. Its
observed behaviour is consistent — **5.3% write-off against `bank15`'s 47.8%** — because it
converts pool deaths into take-profits before the pool dies.

**Its forward verdict is still blocked on the pairing clock** (19 settled, **2 diverged cohorts**),
and by round 35's rule the usable basis is diverged cohorts. This round's replay strengthens the
case for the *design* without substituting for the forward test.

## 7. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not modify production runtime code.
- Did not re-optimise the take-profit level on this sample (§5).
- Did not treat the replay as a forward result.

## 8. Next actions

1. **P0 — read `full15` on diverged cohorts**, not on per-side counts.
2. **P0 — keep the experiments running.**
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing conclusion (REVISED, supersedes r36/r38):** the exit-side touchable share is **~64%**,
   not 41.5%. Pool deaths are touchable whenever the position was above the target first — **52% of
   them were**. Only ~**35.9%** of positions are forced *and* never reached the target. A +15%
   take-profit replays at **+10,304U [CI +5,697, +15,068]**, surviving the removal of the best three
   tokens (+6,416U).
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis (r28),
   slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect (r31),
   provider reliability (r32), the refused-start fix (r33), the paired-basis questions (r34/r35).

## 9. Probe artifacts

`data/research/diag_round120/r39_ceiling_test.py`, `r39b_robust.py`.
