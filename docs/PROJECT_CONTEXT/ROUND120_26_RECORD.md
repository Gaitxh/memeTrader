# ROUND 120-26 RECORD — token-level selection cannot be learned from 46 tokens; the market-cap split is a selection artifact

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. Where this round went, and why

Round 25's decomposition put **56.9% of PnL variance on token identity**, ~21pp more on entry
timing, and only 14.6% on arm choice, and it closed the arm-pruning line. Token selection is
therefore the highest-leverage remaining area. The epoch has 46 tokens (later 36 with a usable
first-entry snapshot): **7 winners, 39 losers, total −18,753.1U**.

The question was made decision-shaped rather than model-shaped: *is there any single token-level
exclusion that removes losers without removing winners?*

## 2. What the winners look like at first entry

| feature | winners median | losers median | ratio |
|---|---|---|---|
| **mcap** | **889,300** | **28,540** | **31.2×** |
| **trades** | **593** | **59** | **10.0×** |
| vol | 30,460 | 3,599 | 8.5× |
| liq | 77,920 | 43,100 | 1.8× |
| bp | 70.8 | 82.7 | 0.86× |
| age_min | 4.06 | 3.90 | 1.04× |

Chain composition: **solana 6 winners / 18 losers (−4,927.9U)**, **bsc 1 winner / 18 losers
(−13,279.9U)**, robinhood 0 / 3 (−545.3U). BSC carries **70.8%** of the total loss.

The screen found that **no exclusion rule keeps all 7 winners** except the trivial
`trades ≥ 0` (no exclusion at all). The most striking candidate was market cap: first-entry
`mcap ≤ $28,300` covered 14 tokens containing **ZERO winners**, while 6 of 7 winners sat above it
(`mcap ≥ 2.83e4` → −6,707.2U versus −18,743.9U actual, i.e. **+12,036.6U** of loss avoided).

At face value that is the largest single lever found in this session. It is not real.

## 3. The market-cap split is a selection artifact

**Permutation test (the decisive check).** Shuffle the token outcomes 4,000 times and, for each
shuffle, search every possible cut point for the best achievable exclusion:

```
permutations where the BEST cut did at least as well as the real one: 4000/4000 = 100.0%
```

**Every single shuffle produced a cut as good as or better than the real one.** With only 36
tokens and the freedom to choose the cut point, a gain of that size is *guaranteed by chance*. The
"zero winners below $28,300" is a property of the search, not of the market.

Note the position-level version looked convincing and was **also misleading**: token-clustered
90% CI **[+2.295, +10.623]** (excludes zero), kept 15.2% write-off versus dropped 65.7%. But that
interval is **conditional on a cut point chosen by searching the same data**, so it does not carry
the significance it appears to. This is the trap: clustering fixes the *dependence* problem, not
the *selection* problem.

Supporting checks were consistent with an artifact:

- **not a pure chain effect** — within BSC, low-mcap 0 winners / −10,556.8U vs high-mcap 1 winner /
  −2,723.2U; within Solana, 0 winners vs 5 winners. So it is not *only* BSC, which is exactly why
  it looked convincing;
- **not the activity floor restated** — `r(mcap, trades)` across tokens is only **+0.145**.

## 4. A second error of my own, caught

My leave-one-token-out check printed "removals that still leave ZERO winners: **36 of 14**" and I
initially read it as strong evidence. It is **trivially true**: removing a *loser* from a set that
already contains zero winners obviously leaves zero winners. The test was vacuous as written, and
the count exceeded the set size because I iterated over all tokens rather than the low-mcap set.
Recorded so the check is not trusted in this form.

## 5. Conclusion, and what it closes

**Token-level exclusion rules cannot be validated from this epoch.** Any cut searched over 36–46
token outcomes will look good, and there is no out-of-sample or nested-CV route with this few
tokens.

This is the second line closed in two rounds, and together they bound where leverage can come
from:

| line | status |
|---|---|
| prune / merge the arm fleet (round 25) | **closed** — 311 distinct contracts; differences unexercised, not duplicated |
| token-level exclusion filters (round 26) | **closed** — unvalidatable at n=36–46 |
| entry-side mechanisms already shipped | 2 floor families + full-capture exits, still settling |
| the binding common rules (~80% of exits) | the remaining lever, and the only one left |

The binding constraint is the **number of independent tokens** (effective n ≈ 30, round 25).
Learning token selection requires more tokens, not more analysis of the same 46.

## 6. What this round did NOT do

- Did not ship a market-cap arm — §3 gives the reason.
- Did not modify any production source.
- Did not read the forward experiments as verdicts. `exit150_full15_v1` reached **17 settled at
  +0.26U/pos, 82.4% win, 5.9% write-off** against `bank15`'s −6.01U/pos / 27.3% / 50.0% — now
  *positive* per position, still 3 short of the threshold.
- Did not treat any token-level split as actionable.

## 7. Next actions

1. **P0 — read `exit150_full15_v1`** when it reaches 20 settled (3 to go). It is the only
   experiment near readable and is now positive per position.
2. **P0 — re-measure distinct-pool coverage** once ≥6 post-change 10-minute buckets exist
   (adaptive cadence, round 22), against the trend.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24). Still the most specific open target.
4. **P1 — any change to a binding common rule must be a NEW ARM**, never an edit.
5. **Do NOT** search for token-level exclusion rules on this epoch again (§3, §5). Do not trust
   any cut point discovered by search without a permutation test.

## 8. Probe artifacts

`data/research/diag_round120/`, read-only: `r26_token_selection.py`, `r26b_mcap_robust.py`.
