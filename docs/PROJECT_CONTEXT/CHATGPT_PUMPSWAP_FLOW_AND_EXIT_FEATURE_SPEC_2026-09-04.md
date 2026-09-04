# PumpSwap Strict-As-Of Flow and Exit Feature Specification

Date: 2026-09-04
Status: `P1 DESIGN / DO NOT AFFECT CURRENT V4 / IMPLEMENT AFTER V5 EXECUTION KERNEL`

## 1. Purpose

Create the smallest local data factory capable of answering two economic questions in real forward operation:

1. Is a new/active PumpSwap market attracting broad, persistent net demand rather than one-wallet or clone-driven noise?
2. After entry, is continuation quality weakening enough that selling now has higher expected executable value than waiting?

The feature layer never sends orders. It emits immutable, current-only `MarketFrame` rows and advisory state transitions consumed by registered strategies.

## 2. Scope

Initial scope is one exact PumpSwap pool for:

- v5 candidates admitted to a bounded entry-evaluation queue;
- all open v4/v5 positions whose pool identity is known;
- short fixed follow-ups for rejected gate-ablation cohorts.

Do not decode/store the full global PumpSwap firehose indefinitely. Use one program-level transaction/log stream, filter locally, and persist only decision-relevant events/frames.

## 3. Time and ordering contract

Every raw event and frame preserves:

- `chain_slot`;
- `chain_block_time` when available;
- transaction signature and instruction/event index;
- `provider_received_at`;
- `local_ingested_at`;
- `recorded_at`;
- `available_at = max(provider_received_at, local_ingested_at, recorded_at)`.

Ordering for deterministic aggregation is `(slot, transaction_index if available, instruction/event index, signature)`. Local decisions use only events whose `available_at <= decision_at`.

Late delivery:

- append the raw event with `late_for_existing_frames=true`;
- it may enter a future frame after it becomes available;
- never rewrite a frame or decision that existed before the event arrived.

A reconnect/gap is an observed feature (`source_gap=true`), not silently interpolated market activity.

## 4. Raw event semantics

For every decoded swap touching the exact pool:

- token/base amount in and out;
- quote/SOL amount in and out;
- trade direction from the held-token perspective;
- fees separately when encoded;
- trader/payer local stable hash for aggregate breadth only;
- pre/post pool vault balances where available;
- program, pool, base mint, quote mint and vault lineage;
- decode version and validation status.

Direction convention:

- `BUY`: quote/SOL enters pool and held token leaves pool;
- `SELL`: held token enters pool and quote/SOL leaves pool.

Signed quote notional `x_i` is positive for BUY and negative for SELL. Use actual quote units normalized by decimals; do not use a later USD price to revalue an earlier trade. A same-time SOL/USD observation may be attached as a separate fact with its own availability clock.

## 5. Incremental windows

For active candidates/open positions maintain ring buffers for 1s, 3s, 5s, 15s and 60s. A frame may also include 5m provider aggregates as a low-frequency comparison, but provider aggregates do not replace transaction-derived windows.

Persist frames on:

- first entry-family trigger;
- StrategyDecision;
- BUY/SELL quote request and completion;
- position risk-state change;
- exit intent;
- fixed 15/60/240-minute learning checkpoint;
- bounded periodic held-position snapshots.

## 6. Core flow features

For window `w` and trades `i` available in that window:

### 6.1 Signed quote-flow imbalance

`Q_buy = sum(max(x_i,0))`

`Q_sell = sum(max(-x_i,0))`

`quote_flow_imbalance = (Q_buy - Q_sell) / (Q_buy + Q_sell + eps)`

Store numerator/denominator and not only the ratio. Zero denominator means `no_trades`, not neutral flow.

### 6.2 Count imbalance

`count_imbalance = (N_buy - N_sell) / (N_buy + N_sell + eps)`

Useful only beside quote notional; many dust buys must not outweigh one economically dominant sell.

### 6.3 Effective buyer/seller breadth

For per-address notional weights `v_j`:

`effective_breadth = (sum(v_j)^2) / (sum(v_j^2) + eps)`

Store raw distinct local-hash count, effective breadth and top-1/top-3 notional share. Effective breadth reduces the false comfort of 100 dust wallets while avoiding a claim that wallet count equals independent humans.

### 6.4 New versus repeat participation

A locally new buyer is first observed by this system before or inside the window, never inferred from current chain history after the fact. Store:

- new buyer count/notional;
- repeat buyer count/notional;
- new-buyer share;
- left-censor flag when the token predates reliable local collection.

### 6.5 Trade intensity and burst

- trades per second;
- buy and sell intensity separately;
- median/p90 inter-arrival time;
- elapsed time since last swap;
- burstiness `(std_gap - mean_gap) / (std_gap + mean_gap + eps)` when enough trades exist.

### 6.6 Trade-size distribution

- median, p75, p90 and max quote notional;
- largest buy/sell share;
- large-sell count using a threshold frozen from earlier/current window data, never a future percentile;
- concentration of sell notional among local stable hashes.

## 7. Price, liquidity and execution features

### 7.1 Reserve-implied price

Use exact normalized vault reserves when valid. Store the formula/version and whether the pair orientation is token/quote. Do not silently splice DexScreener price into an on-chain reserve series.

### 7.2 Return/velocity/acceleration

For reserve-implied price or executable recovery series `p_t`:

- log return over each available window;
- first difference per second (`velocity`);
- difference of short and longer velocity (`acceleration/deceleration`);
- realized absolute variation and downside variation.

When either endpoint is unavailable, return null with reason; never carry forward and call it flat.

### 7.3 Liquidity/vault path

- base/quote vault level and change;
- percentage change from entry and held-account baseline;
- joint vault depletion;
- estimated constant-product depth for the current position size when valid;
- divergence between provider liquidity and exact account reserves.

### 7.4 Full-position executable recovery

For the remaining raw token amount:

`gross_recovery_usd = current fresh Jupiter minimum output in USDC`

`remaining_cost_usd = initial stake - cost allocated to prior partial exits`

`executable_recovery_ratio = gross_recovery_usd / max(remaining_cost_usd, eps)`

Also store quote `outAmount`, `otherAmountThreshold`, route complexity, price impact, request/completion times and cost-completeness. A missing/no-route quote is a categorical execution state, not numeric zero except in an explicit writeoff terminal.

### 7.5 Recovery high-water and drawdown

`recovery_high_water = max(executable_recovery_ratio observed and available since entry)`

`recovery_drawdown = current / recovery_high_water - 1`

The high-water is updated only by observations available at the evaluation time. Later quotes never revise an earlier trailing decision.

## 8. Market-stall and data-stall separation

### `DATA_STALE`

Triggered by subscription heartbeat gap, slot gap, RPC/provider failure or an old frame. It says nothing about whether traders stopped.

### `MARKET_STALLED`

Chain/source is advancing, but elapsed time since the exact pool's last swap is unusually long relative to its own earlier/current intensity. Define advisory score:

`stall_multiple = elapsed_since_last_swap / max(prior_p90_interarrival, configured_floor)`

Require an adequate pre-stall sample; otherwise status is `insufficient_baseline`.

### `PRICE_FLAT_WARNING`

Valid non-carried-forward prices have negligible range while the prior market was active. Store source and update count. It may arm an exit alongside flow/route deterioration; it never confirms pool death alone.

## 9. Top-exhaustion/advisory features

The first version records transparent components instead of a fitted opaque score.

### 9.1 Price/recovery versus flow divergence

Advisory bearish divergence when, using only current/earlier frames:

- price or executable recovery is near/makes a local high;
- short-window quote-flow imbalance falls materially versus its earlier window;
- effective buyer breadth and/or trade intensity also falls;
- sell concentration or largest-sell share rises.

Persist every component, window and comparison frame ID. Do not store only `divergence=true`.

### 9.2 Failed continuation

After a current breakout/flow burst, subsequent current frames show:

- no new executable recovery high;
- negative/weakening signed flow;
- widening trade gaps;
- reserve/liquidity or route-quality decline.

This is an evaluation after those frames exist, not a retroactive label on the breakout decision.

### 9.3 Route-quality decay

- drop in full-position min-output ratio;
- increased price impact or route complexity;
- route disappears/reappears;
- quote latency rises while provider health is otherwise normal.

Route decay can trigger `WATCH/EXIT_ARMED` faster than a provider mark-price stop.

## 10. Risk-state mapping

Frames do not directly write trades. A registered policy maps components to states:

- `GREEN`: fresh sources, no hard alert, continuation components acceptable;
- `WATCH`: one or more stall/divergence/route warnings;
- `EXIT_ARMED`: policy-specific current-only condition met; immutable ExitIntent required;
- `EXACT_ACCOUNT_ALERT`: current held-account monitor event, highest priority;
- `DATA_STALE`: separate operational risk, may conservatively arm an exit under the policy;
- `DEAD_TERMINAL`: only the existing exact-account plus full-size economic-failure predicate;
- `CLOSED/WRITTEN_OFF`.

Hard-account and impossible-transfer facts override every positive flow/narrative feature. Positive Agent research never downgrades `EXIT_ARMED` caused by a hard predicate.

## 11. Entry-family feature use

### Launch Recall

Flow features are descriptive/risk tier at first. The arm must not wait for a rich 60-second history and miss the launch. Use immediate sellability plus bounded risk-bucket sampling; later frames teach which early components matter.

### Flow Acceleration

Require a registered crossing based on multiple components, not raw price return alone. Initial transparent candidate rule should require breadth/intensity/quote-flow agreement or explicitly label a one-wallet burst. Do not fit weights until enough matured forward frames exist.

### Reawakening

The dormant baseline is frozen before the trigger. Use robust median/MAD or quantile baselines for trade intensity, absolute return, flow, breadth and executable route. A new pool/migration is not reawakening.

## 12. Exit-policy research comparisons

Within each entry family, all four policies share the exact entry fill. Primary paired contrasts:

1. `FAST_ESCAPE - BALANCED_DYNAMIC`;
2. `PEAK_GUARD - BALANCED_DYNAMIC`;
3. `AGENT_AUGMENTED - BALANCED_DYNAMIC`.

Report paired net PNL, tail loss, writeoff, maximum executable adverse excursion, capital time and quote consumption. Cluster uncertainty by cohort/date/token; do not treat twelve cloned accounts as independent market samples.

A useful post-hoc diagnostic is:

`capture_ratio = realized net recovery / maximum time-valid executable recovery available in the registered post-entry window`

It is never an earlier feature and must include zero/no-route/writeoff paths. Also report opportunity cost after early exit; do not optimize capture ratio alone.

## 13. Potential later models

Only after transparent features and sufficient forward outcomes:

- competing-risk survival model for profitable exit, large drawdown and dead/no-route;
- calibrated probability of sellability at 30s/2m/5m;
- ranker for expected net return adjusted by expected shortfall and capital time;
- hierarchical models by market regime/entry family.

No LLM predicts numeric price, PNL or trade size. No model is trained on an unsealed future period or evaluated on data used to choose its features/thresholds.

## 14. Minimal implementation and validation

### Implementation

1. official PumpSwap event/account decoder for one exact pool;
2. local event ring buffer keyed by pool;
3. immutable `market_frames` registration/table with source lineage and availability clocks;
4. frame creation at current v5 decision/exit checkpoints;
5. advisory components exposed in API/Web detail, not yet affecting PeakGuard;
6. shadow PeakGuard ExitIntent ledger only after deterministic frame correctness.

### Tests

- BUY/SELL direction and decimals against official fixtures;
- out-of-order/late event cannot revise an older frame;
- source gap yields null/flag, not zero flow or flat price;
- duplicate signature/event is idempotent;
- one program stream feeds multiple pools without duplicate RPC subscriptions;
- one pool feeds multiple strategies without duplicate frames;
- effective breadth differs from raw dust-wallet count;
- current frame never reads a later trade/vault/quote;
- price-stall warning alone cannot write dead/writeoff;
- exact-account alert retains highest exit priority;
- restart restores subscriptions/ring baselines from immutable state without inventing history.

### Forward acceptance

- natural decoded swaps and vault deltas reconcile direction/amounts for held/candidate pools;
- frame p50/p95 receive-to-record latency and gap rates are reported;
- at least one natural entry/position produces frames and advisory changes without changing current v4 or an unregistered v5 policy;
- provider 5m aggregates are displayed only as comparison, never execution truth;
- no provider/Agent/RPC work is multiplied by strategy count.
