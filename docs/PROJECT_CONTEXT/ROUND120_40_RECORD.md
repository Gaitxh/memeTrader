# ROUND 120-40 RECORD — the deployed stack projects −1,434U against −18,803U actual (92% reduction); still a loss, still in-sample

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. Why this round

Rounds 17–39 measured each deployed mechanism separately (take-profit at +15%; activity floor;
run-up cap). Round 20 priced a combination on **1,710** positions and got **−1,540U**. The
population has since grown **2.4×**. This re-prices the stack once, on the current population, with
a proper interval — so the deployed configuration's projected effect is stated in one place.

## 2. The projection

2,397 positions with a usable mark series. Levels as deployed: take-profit 100% at +15% econ,
activity floor `buys_5m + sells_5m ≥ 30`, run-up cap ≤15% over the 20 minutes before entry.

| configuration | n | total | U/pos | delta vs actual |
|---|---|---|---|---|
| actual (no floor, no TP) | 2,397 | **−18,803.3U** | −7.84 | — |
| + take-profit @+15% | 2,397 | −8,499.6U | −3.55 | +10,303.6U |
| activity floor only | 1,410 | −6,992.0U | −4.96 | +11,811.3U |
| activity floor + TP | 1,410 | −4,187.0U | −2.97 | +14,616.3U |
| **floor + run-up + TP (FULL STACK)** | **603** | **−1,434.1U** | **−2.38** | **+17,369.2U** |
| run-up + TP | 753 | −1,631.1U | −2.17 | +17,172.2U |

`stack − actual = +17,369.2U` holds exactly.

**Robustness:**

| check | result |
|---|---|
| token-clustered 90% bootstrap | **[+12,074, +22,695]U — excludes zero** |
| drop the best 1 token | +15,850U |
| drop the best 2 tokens | +14,577U |
| **drop the best 3 tokens** | **+13,332U** |
| **drop the best 5 tokens** | **+10,973U** |

**A 92.4% reduction in the epoch loss** (−18,803.3U → −1,434.1U), and the effect survives removing
the five best tokens entirely.

## 3. A bug I caught in my own bootstrap, and why it mattered

The first run reported a stack delta of **+590U, CI [−394, +1,858], excluding zero = False** —
which **contradicted the table's +17,365U** in the same output. A CI and a point estimate that
disagree by 30× is a bug, not a nuance.

**The cause:** I computed the position-wise delta as `sim − pnl` using `sim = pnl` for
filtered-**out** positions — i.e. counting **0** for a position the stack does not trade. But *not
trading a losing position means avoiding that loss*, so the correct delta there is **−pnl** (the
contribution goes from `pnl` to `0`). The error undercounted the gain by exactly the avoided
losses, which is most of it.

**Fixed**, and the corrected figure reconciles with the table to the decimal. Recorded because a
plausible-looking CI silently disagreeing with its own headline is precisely the failure mode this
session keeps finding — and this time the disagreement was the *only* signal that anything was
wrong.

## 4. The honest headline

**Even the full deployed stack still LOSES money on this epoch: −1,434.1U.** It is a 92% reduction,
not a profit.

And **every level (+15%, `trades ≥ 30`, run-up ≤15%) was chosen on this same epoch**, so the
combination compounds in-sample selection. This projects the **deployed design**; it is not a
result. The deployed forward arms are the test, and they are not readable yet.

**One genuinely encouraging sign of stability:** round 20 priced essentially the same combination at
**−1,540U on 1,710 positions**; this round prices it at **−1,434U on 2,397**. The projection barely
moved across a 2.4× population increase, which is what a stable relationship looks like rather than
a fitted artifact — though both numbers come from the same epoch and so are not independent.

## 5. `exit150_full15_v1` reached the per-side threshold — and is still not readable

| | settled | U/pos | win | write-off | **diverged cohorts** |
|---|---|---|---|---|---|
| `exit150_full15_v1` | **20** | **+0.07** | 80.0% | 5.0% | **2** |
| `exit150_bank15_v1` (control) | 23 | −6.08 | 26.1% | 47.8% | — |

The per-side gate is now satisfied (20 ≥ 20), and round 35's rule applies: **the usable basis is
diverged cohorts, of which there are 2.** So the correct statement is *"the unpaired contrast is
+6.15U/pos in favour of `full15`; the paired basis is 2 diverged cohorts"* — **not a verdict.**
This is exactly the situation rounds 34–35 were built to catch, and it was caught.

## 6. What this round did NOT do

- Did not change any strategy, arm, threshold or exit contract.
- Did not modify production runtime code.
- Did not re-optimise any level on this sample.
- Did not claim a verdict for `full15`, and did not treat the +17,369U projection as a result.

## 7. Next actions

1. **P0 — keep the experiments running.** The pairing clock is the binding constraint; nothing
   analytical accelerates it.
2. **P0 — when `full15` reaches 20 diverged cohorts**, read it with the paired test.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off; effective sample ≈19 BSC tokens, so any rule needs the round-26 permutation treatment.
4. **Standing conclusion (unchanged from r39):** the exit-side touchable share is **~64%**, not
   41.5% (r36 refuted); a +15% take-profit replays at +10,304U [CI +5,697, +15,068].
5. **Standing rule (new, r40):** when a point estimate and its own interval disagree by an order
   of magnitude, the interval is buggy — reconcile them before believing either.

## 8. Probe artifacts

`data/research/diag_round120/r40_stack.py`.
