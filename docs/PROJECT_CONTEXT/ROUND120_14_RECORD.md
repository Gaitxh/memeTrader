# Round 120-14 record — the hard-stop "overshoot" is real losses, not a defect; and the liquidity floor misses price-only collapses

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r14_*`. **No production change.**

The round set out to fix the hard stop's 128% overshoot (realised −45.5% of stake against a
configured −20% economic threshold, 245–252 closes, −2,232U). It ends with the overshoot
**explained, exonerated, and re-attributed** — and with one genuinely new defect found elsewhere.

---

## 1. What the overshoot is made of (measured)

Working backwards from `realized_proceeds = qty × settle_price × 0.96`, and forward from the
recorded trigger mark in `chain_meme_trader_marks.trigger_evidence_json.pre_trigger`:

| trigger price ratio vs entry | n | % | PnL |
|---|---|---|---|
| **< 0.10 (near-total collapse)** | **76** | **30.2%** | **−1,434.1** |
| 0.10–0.60 | 9 | 3.6% | −66.8 |
| 0.60–0.85 | 147 | 58.3% | −685.7 |
| 0.85–1.00 | 19 | 7.5% | −71.5 |
| ≥ 1.00 | 1 | 0.4% | −6.8 |
| **total** | 251 | | **−2,264.9** |

And the two candidate mechanisms separated cleanly:

| candidate | measurement | verdict |
|---|---|---|
| settlement gap (trigger fine, fill worse) | **1 of 252 (0.4%)** | **not it** |
| late trigger (mark already far below threshold) | **232 of 252 (92.1%)**, median trigger ratio 0.790 | **it** |

Mark cadence is healthy — **p50 10.9 s** against a configured `position_scan_seconds = 15` — and
hard-stopped positions hold a median of only **105 seconds**. So the stop sees the breach on the
next mark after the price has already fallen, which is what "late trigger" means here.

## 2. The hypothesis I brought in, and its refutation

30.2% of stops fire on a print below 10% of entry, worth −1,434U. The obvious reading was a
data-quality defect: the existing `_mark_is_plausible` guard exists for exactly this (its docstring
records a Solana print 15,400× below the previous mark that booked −100% on a +384% position), so
the plan was to repair it.

**Refuted in three steps, each cheap, each changing the answer:**

1. **Is the guard on the path?** Yes — `store.py:35799` applies it to `HARD_STOP`, `TRAILING_EXIT`
   and `TAKE_PROFIT_*` and `continue`s the exit. `action = "HARD_STOP"` is set at `35616`.
2. **Did it fail open?** No. All **76 of 76** dust triggers had **≥3 reference marks**, so the
   guard reached a verdict rather than failing open on `len(prices) < 3`.
3. **What did it decide, and why?** Reproducing its query and arithmetic exactly on two live
   cases:

   * `solana:3wEecdaDc…` — the five references were **three collapsed prints (3.604e-06) and two
     healthy ones (0.004159)**. The **median is therefore the collapsed value**, and the trigger
     1.761e-06 is not ≤ 0.10 × 3.604e-06. *A persistent collapse poisons the relative test.*
   * `bsc:0x1863282521…` — price 1.951e-09 vs a 0.0006224 median is a deep outlier (**True**), but
     liquidity 68,718 ≤ 0.25 × 137,428 = 34,357 is **False**. *A 3–6 order price collapse with only
     a 2× liquidity drop passes the guard by design.*

   So the guard has two genuine blind spots. Both were then tested for whether closing them would
   have saved money.

## 3. The decisive test, and why the fix is worth nothing

**The collapsed marks never recovered.** The final marks sit at the collapsed values:

| token | marks | price max → min | ratio | recovered to ≥50% of max? |
|---|---|---|---|---|
| `bsc:0x1863282521…` | 88 | 0.000716 → 1.951e-09 | **3.67e5** | **NO** |
| `solana:3wEecdaDc…` | 23 | 0.004159 → 3.604e-06 | **1.15e3** | **NO** |

**These were real deaths, not bad prints.** Blocking the hard stop would not have saved a unit: the
position is worth ~0 either way, and neither pool's liquidity (68,718 and 3,304) is below the
1,000 USD writeoff floor, so the writeoff path would not have taken it either — it would simply
have stayed open at ~0 until `max_hold`. **The guard behaved correctly. The −1,434U is real.**

**Sixth hypothesis this session killed by measurement.** Recorded prominently because the
"−1,434U fixable defect" conclusion was one query away from being written up as a repair.

## 4. What the round did find — a real gap, stated as a gap not a fix

Both dead tokens had **liquidity above the 1,000 USD floor while their price collapsed by 3–6
orders of magnitude**. The system's only "this pool is dead" signal is the liquidity floor
(`pool_is_below_floor` → `RUG_EXIT` → writeoff), so a **price-only collapse is invisible to every
death rule**; it reaches the hard stop like any ordinary drawdown and books the same −20.

That does not change the PnL in these two cases, but it changes the *classification*: these are
rugs the writeoff detector misses, and they are 30.2% of the largest loss engine. Whether a
price-only-collapse rule would ever save money depends on whether such tokens can recover — and
the two measured cases did not. **Recorded as an observation with n=3 tokens, not as a fix.**

## 5. Consequence for EXIT150, stated plainly

`exit150_widestop_v1` was designed on the premise that the hard stop fires inside ordinary noise
and should be widened. **That premise is now partly wrong**: 30.2% of hard stops are tokens going to
approximately zero, where a wider stop loses the same or more. The remaining 58.3% fire at
0.60–0.85 of entry, where width does matter.

`exit150_bank15_v1` / `bank25_v1` are unaffected — the ladder firing (11 filler positions, the only
tier fills in the epoch) is orthogonal to stop width. **`widestop` is not retracted** (the ledger is
append-only and it is a legitimate experiment), but its expected value is lower than the round-120-3
record implied, and that is now on the record.

**The real lever this round points at is the same one every round has pointed at: the entry.**
76 positions were bought in tokens that went to ~0 within a median of 105 seconds.

## 6. Priority list after this round

| # | action | evidence |
|---|---|---|
| **P0-1** | **Entry selection** — 76 of 251 hard stops are tokens that reached ~0 within ~105 s of entry. Nothing in the exit layer can fix that | §1, §3 |
| **P0-2** | Reduce the evaluation write RATE (74% of measured DB growth; 53% of rows can never admit) — verify the `previous_features` continuity dependency first | round 120-11 |
| **P0-3** | Observation-slot admission probe (5/9 leases held by provider-silent pools for up to 900 s) | round 120-12 |
| P1-1 | EXIT150 to ≥20 settled per side, then `paired_arm_ab.py` | 6/arm so far |
| P1-2 | Price-only-collapse classification (n=3 tokens, observation only) | §4 |

## 7. Method note

Six hypotheses killed or redirected in seven rounds, and this one came closest to being shipped: the
guard genuinely has two blind spots, both provable from the code, and closing them looks like a
repair. **Only the recovery test — do the collapsed prints ever come back — distinguished "bad
data" from "dead token".** That test cost one query and is the difference between a −1,434U fix and
a zero-value change. **For any data-quality defect claim, check whether the anomalous value
persists or reverts before pricing the fix.**
