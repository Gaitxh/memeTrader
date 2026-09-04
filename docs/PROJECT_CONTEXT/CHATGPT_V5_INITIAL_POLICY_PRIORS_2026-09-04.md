# V5 Initial Entry/Exit Policy Priors

Date: 2026-09-04
Status: `PREREGISTRATION INPUT / NOT YET ACTIVE / CODEX MUST VERIFY CURRENT DISTRIBUTIONS AND CAPACITY BEFORE REGISTRATION`

## 1. Why provide priors

The architecture needs concrete first Paper policies. However, current v4 outcomes are sparse/winner-dependent and must not be mined to optimize thresholds. These priors are derived from:

- the current 20 USDC/4%-per-leg conservative execution contract;
- the user’s stated preference for broad early opportunity coverage and fast exits;
- preserving the current dynamic policy as a control;
- explicit risk-bucket exploration rather than universal gate relaxation.

Codex must report the current pre-activation feature/capacity distributions, freeze the exact numbers in a new registration before evaluating subsequent outcomes, and may propose a narrower revision if a value is operationally impossible. Do not tune them to current winners.

## 2. Economic reference

For a simplified unchanged market with a 4% conservative haircut on each leg:

- round-trip recovery ratio is approximately `0.9216`;
- gross price movement required to return to 1.0 is approximately `+8.51%`, before separately known fees;
- a 20–30% apparent price gain is not a 20–30% conservative account gain.

All first v5 exits should prefer **remaining-position minimum-output recovery ratio** over raw DEX price when a fresh quote exists.

## 3. Launch Recall risk buckets

These are selection/learning buckets, not universal safety labels.

### Surface tier

- `S0 exact_canonical`;
- `S1 exact_noncanonical`;
- `S2 route_opaque_or_surface_unknown` — bounded Paper exploration only, no pool-safety claim, Live false;
- `S3 invalid_or_mismatch` — reject.

### Immediate full-position recovery tier

Use the acquired conservative BUY quantity as SELL input:

- `R0 >=0.90` and stress `>=0.85`: current strong-execution reference;
- `R1 0.75–<0.90` or stress `0.65–<0.85`: edge/risk Paper;
- `R2 0.50–<0.75` or stress `0.35–<0.65`: high-risk scout Paper;
- `R3 >0–<0.50`: very-high-risk bounded scout, extremely small quota;
- `R4 no economic route`: research-only, no executable Paper fill.

Reason: `R0` approximates ordinary conservative round-trip execution; lower tiers explicitly pay a large immediate liquidation penalty and require very high continuation to be profitable. They are retained to test the early-escape thesis, not called safe.

### Liquidity/reference bands

Descriptive and selection-balanced:

- `<3k`;
- `3–8k`;
- `8–14k`;
- `14–25k`;
- `>=25k` USD provider/exact estimate, with source/availability preserved.

### Current momentum bands

- `<70`;
- `70–75`;
- `75–80`;
- `80–90`;
- `>=90`.

Launch Recall does not require momentum >=80. Cheap candidate ranking/exploration uses the bands; exact provider capacity determines how many receive preflight.

### Initial exploration weighting prior

A candidate starting point for **Paper selection capacity**, not capital weights:

- 55% currently strongest execution/risk strata;
- 25% adjacent boundary strata;
- 15% high-risk scout strata;
- 5% broad executable audit strata.

Unused reserved slots return to the common queue. Codex should replace these only before activation based on measured request/exit capacity, not outcome performance. All propensities/draws are logged.

## 4. Balanced Dynamic v5 control prior

Purpose: preserve a broad hold/TP/trailing control comparable to current v4 concepts while using executable recovery truth.

### Common overrides

- exact account emergency/terminal path unchanged;
- deterministic transfer impossibility/current invalid position state overrides;
- maximum hold 240m;
- no-route uses registered fair retry/terminal semantics;
- DEX/provider mark is an advisory trigger, not fill/value.

### Economic hard stop

Candidate prior:

- arm full exit when fresh full-position conservative recovery ratio `<=0.65` of remaining unallocated cost;
- if fresh quote is unavailable, route/stall/account state drives an ExitIntent/retry rather than using stale mark as cash.

This corresponds to the existing broad -35% loss concept but is stated in executable economics.

### Trailing

Candidate prior:

- activate after recovery high-water `>=1.45`;
- arm on recovery drawdown `<=-0.25` from high-water;
- route/flow deterioration may arm earlier once MarketFrame treatment exists.

These values approximate the existing +60% raw-price / 28% drawdown control after conservative round-trip effects, without claiming equivalence.

### Staged profit prior

Based on full-position conservative recovery ratio:

- `>=1.65`: exact quote to sell 20% of remaining;
- `>=2.50`: sell 25% of remaining;
- `>=4.00`: sell 35% of remaining;
- `>=7.00`: sell all remaining.

Every tranche requests its exact raw amount. If the quote is unavailable/uneconomic, no fill is booked.

### Activity/liquidity warning

Keep current concepts as advisory/hard mapping in the exact definition:

- provider/exact liquidity warning around the current 3,000 USD reference;
- true market stall distinguished from source stale;
- zero activity only when the chain/source is advancing and the pool baseline is adequate.

## 5. Fast Escape v5 challenger prior

Purpose: test whether broad/risky launches can earn money by recovering capital and escaping deterioration sooner.

### Before principal recovery

Candidate priors:

- full exit when conservative recovery ratio `<=0.78`;
- once recovery high-water `>=1.08`, arm full exit on a `>=0.12` recovery drawdown;
- full/large exit on confirmed route-quality collapse, exact account alert, or market-stall plus negative flow when the relevant facts are current;
- maximum hold without reaching principal-recovery condition: 30m.

A short position age never suppresses exact account or route-loss exits. Optional noise confirmation applies only to soft flow/mark conditions and must not introduce future data.

### Principal-recovery trigger

Candidate prior:

- when full-position conservative recovery ratio `>=1.35`, solve/request the exact partial token amount expected to recover the original remaining cost plus separately known exit cost;
- never estimate the fill purely by proportional arithmetic;
- if an exact partial quote cannot recover the target economically, retain the state and continue under the policy rather than booking a fictitious principal recovery.

At `1.35`, an ideal linear estimate would sell about 74% to recover cost, leaving a meaningful runner. Exact AMM/aggregator impact decides the actual amount.

### After principal recovery

Candidate priors:

- remaining runner cost basis tracked explicitly;
- trailing activate immediately after successful principal recovery;
- full runner exit on 20% conservative recovery drawdown, route/flow deterioration, account risk or max runner hold 60m;
- optional higher take-profit can be a later challenger, not needed for v1.

### No-route behavior

A current no-route arms/favors exit and receives highest eligible retry priority. It is not itself terminal without the registered exact-account/dead predicate. If the position later becomes economically sellable, the next current quote can fill.

## 6. Peak Guard prior

Initial actual execution stays exact Balanced control. Advisory components:

- executable recovery near/new high;
- short-window signed quote flow weakening/negative relative to prior window;
- effective buyer breadth/intensity falling;
- large-sell/top-k concentration rising;
- trade gaps widening;
- route quality/recovery slope degrading.

Record the hypothetical ExitIntent time and exact amount. Activate a treatment only after natural frame coverage and a new registered rule. Do not combine arbitrary component weights in the first advisory version; store a component vector and simple prespecified conjunctions.

## 7. Agent Augmented prior

Initial actual execution stays exact Balanced control.

Advisory mapping candidate:

- qualified urgent negative -> hypothetical accelerate-soft-exit;
- qualified independent positive propagation -> hypothetical bounded runner extension;
- conflict/insufficient/late/error -> no change;
- hard account/route/loss/max-hold exit always overrides.

No affecting treatment until exact paired advisory coverage/latency/evidence quality is reviewed and a new version is registered.

## 8. Flow Acceleration initial crossing prior

Do not activate until current transaction-derived frames exist. Candidate transparent requirement:

- absolute current economic activity floor;
- strong positive short-window signed quote flow;
- trade intensity acceleration versus earlier/current baseline;
- either effective buyer breadth/new-buyer growth or persistent route/liquidity improvement;
- reject/flag a one-wallet burst through top-share/effective-breadth components;
- fresh amount-specific execution contract.

Set numerical cutoffs from the pre-activation forward feature distribution, then freeze before outcome sampling.

## 9. Reawakening initial crossing prior

Do not activate executable Paper until a valid forward dormant baseline exists. Candidate requirement:

- data-quality-qualified dormant baseline;
- absolute activity floor;
- robust intensity/volume increase;
- at least one breadth/flow component and one execution/price/liquidity component;
- no same-burst duplicate episode;
- fresh route/preflight.

Numerical baseline/crossing values come from pre-activation coverage distributions, not later revival winners.

## 10. Portfolio/capacity prior

- fixed 20 USDC per virtual allocation;
- no arbitrary daily 100 USDC cap copied from the focused v4 strategy into v5 Paper;
- capital-feasible strategy account cannot spend unavailable cash;
- unique token/surface entry throughput is limited by measured exit/quote capacity and cluster exposure;
- exit/alert lanes always preempt entries;
- Full Opportunity Shadow continues even when Paper capital/capacity blocks selection.

A temporary emergency maximum unique open opportunity count may be registered from current provider capacity for engineering safety, but it is not an alpha gate and every capacity-blocked opportunity is recorded.

## 11. Stop/promotion criteria for these priors

Immediate engineering stop:

- duplicate intents/fills;
- exit starvation;
- projection/account mismatch;
- future/late data contamination;
- source stale classified as market stall/death;
- provider request multiplied by strategy count.

Policy stop/revise at registered checkpoints if:

- Fast increases tail/writeoff/capital-time without robust net gain;
- low-recovery buckets remain strongly negative including escaped and dead cases;
- broad exploration overwhelms exit capacity;
- advisory Peak/Agent coverage/latency is inadequate;
- total profitability disappears after best-1/best-3 removal.

Promotion creates a new version. No parameter is edited in place.

## 12. Required sensitivity report before activation

Codex/analysis should report counts and projected request/capital load for:

- each recovery/surface/liquidity/momentum band;
- candidate arrival rate;
- unique open-token quote demand under plausible holds;
- current provider p50/p95/errors/deadline misses;
- expected exploration slots;
- v4 open-position exit obligations.

If a band has zero/tiny support, keep it explicit and unranked rather than collapsing it after seeing outcomes.
