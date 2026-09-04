# Execution Economics and Rug-Escape Strategy Specification

Date: 2026-09-04
Status: `ECONOMIC DESIGN / STRICT FORWARD / PAPER FIRST / LIVE LOCKED`

## 1. Core economic reality

A high-frequency Meme strategy can have excellent direction accuracy and still lose after round-trip costs.

With a conservative 4% minimum-output haircut on each leg and no additional fee, unchanged market price implies approximately:

`0.96 × 0.96 = 0.9216`

or a 7.84% conservative round-trip loss. The price must rise about 8.51% merely to restore the original 20 USDC before any separately modeled network/priority/MEV cost. If 0.40 USDC is charged on both entry and exit, the required gross movement is roughly 12.85% under the same simplified assumptions.

Therefore:

- more trades help only when their expected gross edge exceeds turnover cost and tail loss;
- a Fast Escape policy needs large enough early continuation, not just a high win rate;
- minimum-output PNL is a conservative lower bound, not an expected fill;
- strategy ranking must show conservative, central and cost-completeness states separately.

## 2. Five failure classes that require different responses

### A. Atomic structural rug

Examples: a privileged actor removes/redirects usable liquidity or changes a critical account in one transaction/slot such that no economic exit remains afterwards.

There may be no tradable interval between observation and failure. An exit model cannot reliably “run earlier” after the atomic event. Protection comes from:

- pretrade exact-account/custody/authority facts;
- avoiding or separately sizing untrusted surfaces;
- small fixed exposure and diversification;
- permanent no-reentry after confirmed terminal evidence.

Do not claim dynamic exits can solve atomic rugs.

### B. Gradual liquidity withdrawal or sellability decay

Vault balances, route recovery, depth, trade flow or LP state deteriorate over multiple observations. This is where event-driven exit can create real edge:

- exact vault/account deltas;
- full-position Jupiter recovery slope;
- large-sell concentration;
- route disappearance/degradation;
- increasing price impact and quote latency.

Exit as soon as the registered policy arms, before waiting for terminal classification.

### C. Demand exhaustion / pump-and-dump top

Liquidity still exists, but new demand decays and insiders/early buyers distribute. Use current-only flow, breadth, trade intensity, sell concentration and executable-recovery divergence. This is the main PeakGuard domain.

### D. Honeypot/impossible transfer

A BUY route may exist while transfer/sell is restricted. The amount-specific acquired-quantity SELL preflight and direct token capability checks remain common execution truth. A research-only no-sell cohort may be observed, but it is not an executable Paper fill.

### E. Data/provider failure

Stale external price, RPC disconnect, rate limit and quote-provider error are operational facts, not market death. Escalate collection and risk state; do not write off solely from an error.

## 3. Broad entry with economic discipline

The high-recall launch family should not use one universal high momentum/liquidity/canonical/recovery wall. It should use risk buckets and bounded sampling.

Suggested buckets are descriptive until current forward distributions are reviewed:

- immediate full-size recovery bands;
- canonical versus exact noncanonical surface;
- pool/liquidity bands;
- creator-history bands;
- holder/flow concentration bands;
- early momentum/flow bands.

The entry sampler allocates limited quote and Paper capital across buckets. It may intentionally sample weak buckets to learn whether they are wrongly excluded. It must not let thousands of low-quality clones exhaust exit capacity.

A candidate can have three distinct states:

1. `EXECUTABLE_PAPER`: fresh BUY and acquired-quantity SELL preflight, no deterministic impossibility;
2. `COUNTERFACTUAL_RESEARCH`: insufficient/poor sellability or cost completeness; follow outcomes without a realistic fill;
3. `INVALID/TERMINAL`: invalid identity, impossible transfer, terminal dead/no-reentry or no BUY route.

Only state 1 enters executable account PNL.

## 4. Profit-first position sizing

Keep 20 USDC fixed initially for paired strategy comparison. Do not let strategy quality and sizing change simultaneously.

Later sizing may use:

- current executable depth and price impact;
- full-size immediate recovery;
- structural risk tier;
- correlation/creator/event cluster exposure;
- open-position exit-quote demand;
- daily/tail-loss budget.

Live sizing, if ever enabled, must be much smaller for noncanonical/high-risk buckets and may exclude them entirely. Paper exploration and Live eligibility are separate.

A useful risk cap is expressed in loss budget, not only number of positions:

`sum(worst_case_remaining_loss_usd across open positions) <= portfolio_tail_budget`

For a token currently unsellable, worst-case remaining loss is remaining unallocated cost, not a stale mark value.

## 5. Exit objectives

The system should maximize risk-adjusted **realized executable proceeds**, not proximity to a visual chart high.

For policy `s`, evaluate:

`utility_s = net_pnl - lambda * expected_shortfall - gamma * capital_time - eta * quote_capacity_cost`

The displayed primary metrics remain transparent components; no utility weights affect production until separately registered.

### 5.1 Fast Escape

Designed for fragile launches:

- early execution-aware stop;
- fast exit after flow/route deterioration;
- earlier partial profit or principal recovery;
- shorter maximum hold;
- tolerates missing upside in exchange for fewer large losses/writeoffs.

### 5.2 Principal-recovery exit

Instead of arbitrary fixed fractions only, calculate the exact partial token amount whose fresh minimum-output quote would recover a registered portion of original cost plus known exit cost. When the remaining position has sufficient executable value, sell enough to de-risk principal and leave a runner.

Every partial amount gets its own quote; proportional arithmetic from a full-position quote is only an estimate.

### 5.3 Balanced Dynamic

Combines hard safety, loss protection, partial profits, trailing logic, route/liquidity decay and maximum hold. It is the deterministic comparison baseline.

### 5.4 Peak Guard

Arms earlier when continuation quality weakens while price/recovery remains elevated. It should be judged by paired net PNL, tail reduction and opportunity cost—not by whether it guessed the exact candle high.

### 5.5 Agent-Augmented

Agent research is slower and less reliable than mechanical chain facts. It can modify a bounded soft runner after its result becomes available. It never cancels an already-hard exit or turns an absent route into sellability.

## 6. Exit latency accounting

Persist separate times:

- `risk_feature_available_at`;
- `policy_evaluated_at`;
- `exit_intent_created_at`;
- `quote_requested_at`;
- `quote_completed_at`;
- `paper_fill_at` or terminal time.

Report:

- feature-to-intent latency;
- intent queue latency;
- provider latency;
- total trigger-to-fill latency;
- price/recovery lost during each component.

Without this decomposition the system cannot know whether a bad exit came from the strategy, scheduler, provider or unavailable market.

## 7. Quote-capacity economics

Exit quotes are an operational scarce resource. A broader entry policy creates future valuation/exit demand. Admission must account for:

- open positions by risk state;
- required refresh cadence;
- measured provider p95 latency/rate limits;
- pending emergency exits;
- fixed follow-up obligations.

Reserve capacity in strict order:

1. exact-account emergency exit;
2. armed exit;
3. high-risk position valuation needed for a rule;
4. new entry preflight;
5. research/fixed follow-up;
6. low-risk background valuation.

If exit capacity is saturated, pause new entries because the system cannot safely manage more positions—not because their alpha score is low.

## 8. Paper fill truth layers

For every execution plan retain:

- quote output (`outAmount` or equivalent central quote);
- minimum output threshold;
- route and price-impact facts;
- request/response times;
- estimated or observed network/priority fee when available;
- cost-completeness status;
- simulation status when a transaction can be built;
- actual fill/reconciliation only for a real signed execution.

Display three economic layers:

1. `CONSERVATIVE_QUOTE_BOUND`: minimum-output based;
2. `CENTRAL_QUOTE_ESTIMATE`: quoted output less separately known costs;
3. `LIVE_RECONCILED`: actual confirmed balance delta, unavailable while Live is locked.

Never blend these into one unlabeled PNL.

## 9. Learning whether risky rugs are profitable before they die

Define risk exposure at entry from information available then. Do not label a token “future rug” as an entry feature. After terminal maturity, compare entry risk buckets on:

- time from entry to first warning/account alert/dead terminal;
- maximum conservative executable recovery before warning/death;
- Fast/Balanced/Peak realized recovery;
- fraction with no economic exit at all;
- false-warning exits where price later continued;
- writeoff rate and severity;
- profit before dead cases versus all-cases intention-to-treat PNL.

A risky-rug policy is economically useful only if **all-cases** net PNL and tail loss remain acceptable. Reporting only trades that escaped before rug is survivor bias.

## 10. Required robustness

For every claimed profitable policy:

- include losses, no-route and writeoffs;
- remove the best one and best three outcomes;
- cluster by date/token/creator/event so clone families do not create fake sample size;
- report median and trimmed mean beside total PNL;
- separate market regimes and pool surfaces;
- include quote-capacity and capital-time cost;
- preserve rejected/counterfactual denominators.

A policy dominated by one large winner is an experiment, not a scalable strategy.

## 11. Promotion logic

Paper volume may be increased to learn, but Live eligibility is never inferred from trade count. A strategy reaches a capital review only after:

- complete execution semantics for its chain/venue;
- multiple dates and regimes;
- sufficient losses/dead cases to estimate the left tail;
- positive conservative and central economics;
- remove-best robustness;
- bounded drawdown/writeoff;
- no material scheduler or data-gap dependency;
- independent security/signer/reconciliation review.

This design accepts the user's central thesis—early exit can monetize some fragile markets—while separating that tradable class from atomic rugs that offer no post-event escape interval.
