# ROUND 120-24 RECORD — a derived-feature screen; the strongest marker found is redundant

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. What this round did

The objective asks for derived/approximate features built from data already held, under
resource limits. Round 18 tested snapshot features against the **"+15% touch"** label and found
nothing (the separation was a between-token artifact). The productive label is the one rounds
19/20 actually moved: **WRITE-OFF** — the pool died and the remainder was written off, which is
essentially the entire tail loss.

Nine candidate features were built **point-in-time** from the 20-minute pre-entry observation
window plus the entry snapshot, and screened on 2,369 positions / 37 tokens (write-off base
rate 32.2%). Every candidate faced the same battery: tertile separation, **token-clustered
bootstrap**, and **drop-the-best-token**.

| feature (definition) | low | mid | high | high−low | 90% CI | excl 0 | drop-best |
|---|---|---|---|---|---|---|---|
| `liq_trend` (liquidity change over the window) | 2.4% | 54.1% | 40.2% | +42.2pp | [+0.249, +0.582] | yes | +39.1pp |
| `vol_trend` (volume_5m change) | 11.5% | 37.5% | 47.7% | +33.9pp | [+0.139, +0.520] | yes | +31.3pp |
| **`buy_pressure`** (buys/(buys+sells)×100) | 12.4% | 16.6% | 67.6% | **+42.7pp** | [+0.258, +0.589] | yes | +39.6pp |
| **`mcap_liq`** (market cap / liquidity) | 76.2% | 18.3% | **2.4%** | **−43.2pp** | [−0.626, −0.234] | yes | −49.4pp |
| `turnover` (vol/liq) | 30.8% | 46.3% | 19.7% | −18.2pp | [−0.385, +0.019] | no | −22.2pp |
| `price_vol_pct` (range in window) | 10.3% | 59.8% | 26.7% | +10.5pp | [−0.088, +0.288] | no | +6.2pp |
| `frames_in_window` | 23.6% | 50.1% | 23.1% | +8.4pp | [−0.089, +0.258] | no | +4.1pp |
| `holders`, `liq_per_holder` | — | — | — | — | — | — | not populated (0 usable) |

Four survived the screen. `mcap_liq` was the only **monotonic** one (76.2 → 18.3 → 2.4), which
`liq_trend` was not.

## 2. The chain confound, applied to all survivors

This device's write-offs are essentially 100% BSC, so any feature that merely separates chains
would look powerful. Tested within chain:

| feature | all | within BSC | within Solana |
|---|---|---|---|
| `liq_trend` | +42.2pp | **+16.8pp** (lost ~60%) | +14.0pp |
| `vol_trend` | +34.1pp | **−0.4pp (dead)** | +17.2pp |
| `buy_pressure` | +42.4pp | **+53.9pp (stronger)** | +3.2pp |
| `mcap_liq` | −43.2pp | −25.7pp | −18.3pp |

**`liq_trend` was mostly a chain discriminator** — about 60% of its effect vanished within chain,
and on Solana the money difference was negligible (−4.20 vs −4.06 U/pos). `vol_trend` is a
Solana-only effect and completely dead on BSC. `mcap_liq` retains a real within-chain effect but
its tertiles are non-monotonic on both chains (BSC 74.9 / 88.4 / 26.8).

## 3. `buy_pressure` is the strongest marker found this session — and it is redundant

`buy_pressure = buys_5m / (buys_5m + sells_5m) × 100` on the entry snapshot (a rolling 5-minute
figure, so point-in-time by construction). It is the only candidate that got **stronger** within
chain. On BSC (1,038 positions, 19 tokens, 63.3% write-off):

- **token-clustered bootstrap within BSC: +0.539, 90% CI [+0.337, +0.708]** — excludes zero;
- **leave-one-token-out: +0.487 .. +0.613, every token removal still positive**;
- quintiles show a **sharp threshold**, not a gradient:

| quintile | buy_pressure | write-off | U/pos |
|---|---|---|---|
| q1 | 20.0–63.1 | 30.4% | −6.59 |
| q2 | 63.8–82.7 | 26.1% | −6.00 |
| **q3** | **82.7–100.0** | **82.6%** | −16.78 |
| q4 | 100.0 | 83.6% | −16.04 |
| **q5** | **100.0** | **93.3%** | −18.40 |

A cap would cut the BSC book from −13,264.6U to −1,772.2U at `bp ≤ 75` (86.6% reduction).

**But it is largely already captured by the round-19 activity floor**, and this is the check
that stops it being shipped:

- **`r(buy_pressure, trades) = −0.631`** — high buy pressure is strongly associated with few
  trades;
- `bp high & trades ≥ 30` has **n = 3**. The activity floor (`trades ≥ 30`) already keeps only
  232 of 1,038 BSC positions, of which 229 are `bp`-low (21.8% write-off) and 3 are `bp`-high;
- so on the surviving book a `buy_pressure` cap would remove **3 positions** — negligible, and
  not worth a new correlated arm on a book with no per-token concentration limit.

**No arm was shipped.** The value here is the **mechanism it independently corroborates**: the
BSC death zone is *one-sided buying with few trades* — a pool being pumped with almost no
two-sided flow, which is what the activity floor was catching from the other direction. Two
independent features converging on the same population is real evidence that the round-19 floor
is targeting the right thing, not a new lever.

## 4. What this round did NOT do

- Did not modify, retune, pause or replace any existing arm.
- Did not ship a `buy_pressure` or `mcap_liq` arm — §3 and §2 give the reasons.
- Did not treat any within-chain-non-monotonic feature as actionable.
- Did not read the forward experiments as verdicts; `exit150_full15_v1` remains at 16 settled.

## 5. Next actions

1. **P0 — re-run `scripts/experiment_readout.py`.** `exit150_full15_v1` (16 settled, −0.00U/pos,
   81.2% win, 6.2% write-off vs `bank15`'s 27.3% / 50.0%) is closest and the one to read first.
2. **P0 — re-measure distinct-pool coverage** once ≥6 post-change 10-minute buckets exist
   (adaptive cadence, round 22), against the trend rather than a flat average.
3. **P1 — the residual within the kept book**: even after the activity floor, `bp`-low BSC
   positions still show 21.8% write-off. That residue is the next honest target; `buy_pressure`
   does not address it and nothing screened this round does.
4. **Do NOT** ship `buy_pressure`/`mcap_liq` arms without a residual-risk rationale; do not
   re-report the 4% "latency premium"; do not build a "+15%-touch predictor" (round 18).

## 6. Probe artifacts

`data/research/diag_round120/`, read-only: `r24_derived_features.py`,
`r24_liqtrend_robust.py`, `r24_chain_confound.py`, `r24_survivors_chain.py`,
`r24_buypressure_decisive.py`.
