# V5 Market-Stall and Price-Flat Feature Specification

Date: 2026-09-04
Status: `GATE E/F EXIT FEATURE DESIGN / WARNING, NOT TERMINAL RUG PROOF`

## 1. User observation and objective

A removed/abandoned pool often appears to stop producing meaningful price changes. This is a useful warning, especially when a previously active new token suddenly becomes silent. However, a flat provider price can also result from:

- source/API cache or stale collector;
- no new trades in a genuinely quiet market;
- displayed-pair inactivity while another pool/route trades;
- coarse price precision;
- reconnect/gap;
- one-sided/failed route rather than exact pool withdrawal.

V5 formalizes separate data-health, market-stall, price-flat and execution-degradation features. Only exact structural account evidence plus the registered economic failure predicate can create terminal dead/writeoff.

## 2. Required source-health gate

Before a market silence/flat feature is valid, freeze:

- current source/transport version;
- last received slot/block/sequence;
- local heartbeat and gap/reconnect state;
- last relevant pool/token event;
- subscription/account refresh state;
- provider update/request/result state;
- latest alternative route/surface activity.

Classify:

- `SOURCE_ADVANCING`;
- `SOURCE_STALE`;
- `SOURCE_GAP/RECONNECT`;
- `SOURCE_UNKNOWN`.

Only `SOURCE_ADVANCING` supports a market-stall inference. Otherwise the state is `DATA_STALE` and may still trigger a conservative operational response but not “market stopped”.

## 3. Trade-intensity state

Maintain current-only ring windows for the exact surface/token:

- trade count and economically meaningful trade count;
- quote-notional volume;
- inter-arrival times;
- effective buyer/seller breadth;
- signed quote flow;
- last trade/source available time;
- source gap coverage.

Estimate a robust pre-silence activity reference from earlier available windows, e.g.:

- recent 15/60s rate;
- median/quantile rate in the position’s observed history;
- burst/self-excitation state;
- absolute minimum economic activity.

No future trades enter the reference.

## 4. Silence surprise

For a transparent first feature, record:

- `silence_duration_seconds`;
- `reference_trade_rate_per_second`;
- `expected_trades_during_silence = rate × duration`;
- `poisson_zero_probability = exp(-expected_trades)` as a diagnostic only;
- robust inter-arrival exceedance ratio;
- source-health and market-age context.

The Poisson assumption is not claimed true for self-exciting Meme flow. It provides an interpretable “how surprising is zero activity relative to the prior rate” component. Later Hawkes/change-point models may be research challengers.

Suggested states after preregistering thresholds from pre-activation distributions:

- `NORMAL_INTERARRIVAL`;
- `QUIET_LOW_BASELINE`;
- `BURST_DECAY`;
- `UNEXPECTED_SILENCE`;
- `PROLONGED_MARKET_STALL`;
- `UNKNOWN_SOURCE`.

A token that was always quiet should not receive the same warning as a high-intensity token that abruptly stops.

## 5. Price-flat components

For each source separately:

- number of updates/ticks with identical price;
- elapsed time since last nonzero price change;
- price precision/rounding resolution;
- exact reserve-implied price change when available;
- provider pair update/transaction count;
- full-position central/minimum recovery change;
- alternative route/pool price/activity;
- source heartbeat/gap.

States:

- `PROVIDER_PRICE_FLAT_SOURCE_ALIVE`;
- `EXACT_POOL_PRICE_FLAT_SOURCE_ALIVE`;
- `ROUTE_RECOVERY_FLAT`;
- `DISPLAY_PAIR_FLAT_ALTERNATIVE_ACTIVE`;
- `PRICE_SOURCE_STALE`;
- `PRICE_PRECISION_LIMITED`;
- `UNKNOWN`.

Do not average these into one “price flat” boolean.

## 6. Composite warnings

### `PRICE_FLAT_WARNING`

Requires source-alive evidence plus flatness beyond the registered duration/update/precision threshold. It is low/medium severity by itself.

### `MARKET_STALLED`

Requires:

- source advancing;
- no meaningful swaps/events for an unexpectedly long interval relative to the prior activity reference;
- exact/primary surface or token route activity absent/weak;
- no evidence that the displayed pair alone is stale while alternatives remain active.

### `STALL_AFTER_BURST`

Higher-information warning:

- prior current burst/flow/intensity was high;
- trade arrivals collapse abruptly;
- buyer breadth/positive flow no longer continues;
- price/recovery no longer makes a new high or begins deteriorating.

### `SELLABILITY_DEGRADED`

Independent/current execution evidence:

- full-position minimum recovery falls materially;
- price impact/route complexity worsens;
- no route or quote error state appears;
- exact remaining amount cannot obtain an economic plan.

### `RUG_SUSPECTED`

A policy warning when stall/flat/sellability/account components agree. It may arm the fastest full exit. It is not the terminal database state.

### `DEAD_TERMINAL`

Only the existing/new registered exact structural alert + economic failure/no-exit predicate. Flat/stall alone never sets it.

## 7. Transparent exit-policy use

### Fast Escape

Possible affecting combination after preregistration:

- `STALL_AFTER_BURST` and current recovery failing to make/hold a recent high;
- `MARKET_STALLED` plus route/surface warning;
- any `SELLABILITY_DEGRADED` state;
- exact account alert;
- common loss/principal/max-hold rules.

A current economic route can fill immediately; no Agent confirmation is required.

### Balanced Dynamic

May require stronger/persistent soft stall evidence unless recovery/hard risk is already bad. It keeps the exact same terminal/account overrides.

### Peak Guard

Stall is one divergence component near an executable-recovery high. It is not a standalone peak predictor.

### Agent Augmented

Agent output never overrides a stall/account/route hard exit. Semantic research is too slow and indirect for market-stall mechanics.

## 8. Time and future-data discipline

At evaluation time `t`, use only events/updates with `available_at <= t`. The fact that no trade arrived during `(last_event, t]` is valid only if the source was live/covered during that interval.

A trade received later with an earlier block time cannot retroactively remove the warning/exit that was valid at `t`; it becomes late/gap evidence and affects future frames/data-quality assessment.

Do not use the eventual duration of the silent period at its start.

## 9. Multiple surfaces/routes

A flat/dead displayed pair does not imply token-level stall. Aggregate carefully:

- exact surface-level stall;
- token-level known-surface activity;
- current route availability;
- alternative surface activity.

If the reference pool stalls but an alternative economic route remains, arm/execute according to policy and record `REFERENCE_SURFACE_STALL_ALTERNATIVE_ROUTE`, not terminal death.

## 10. Provider caching and precision

Provider prices may repeat because of cache/update cadence or decimal formatting. Measure:

- response/request time;
- pair transaction counters/volume changes;
- raw precision;
- ETag/cache headers where available;
- independent exact account/flow state.

Repeated identical JSON/provider price without a new underlying update sequence is one stale observation, not N independent flat ticks.

## 11. Training/model features

Later candidates:

- change-point/CUSUM on trade intensity and recovery slope;
- survival/hazard of next trade/economic route;
- Hawkes intensity decay;
- route-state transition model;
- joint stall/account/recovery competing risk.

Start with transparent components. Any fitted model uses gap-aware chronological data and a future registered challenger.

## 12. Labels/outcomes

Evaluate warnings against all cases:

- successful economic exit after warning;
- false warning followed by continuation/new high;
- no-route/dead/writeoff;
- source outage/gap discovered later;
- alternative route/pool remained active;
- warning lead time;
- missed loss/peak regret;
- quote/exit latency.

Do not evaluate only confirmed rugs or only positions successfully sold.

## 13. Web

Display separately:

- source health/slot age;
- last exact trade/event age;
- prior/current intensity;
- silence-surprise component;
- price flat by provider/exact pool/route;
- alternative market activity;
- current full-position recovery/route;
- warning versus terminal state.

Suggested tooltip:

“价格/交易静默是退出风险提示；只有 exact account 事实与全仓经济卖出失败共同满足注册条件时才永久核销。”

## 14. Tests

- source disconnected cannot become market stall/dead;
- always-quiet baseline differs from abrupt post-burst silence;
- later-arriving old event cannot rewrite prior warning;
- repeated cached provider response is not multiple independent flat updates;
- displayed pair flat with alternative route/activity is not token-level dead;
- flat warning may arm exit but cannot directly write off;
- exact account + no economic route can terminal under registered rule;
- positive Agent advice cannot suppress warning/hard exit;
- quote/fill uses exact remaining amount;
- all false warnings and source failures remain in denominator.

## 15. Activation

- Gate E can expose source/data/stall warning states from currently available data;
- Gate F adds exact PumpSwap transaction/account intensity and improves `STALL_AFTER_BURST`;
- initial affecting thresholds are frozen from pre-activation feature distributions, not selected from current v4 winners;
- Peak/advanced models remain advisory until forward validation.
