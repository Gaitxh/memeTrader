# V5 Quantitative Entry and Exit Model Roadmap

Date: 2026-09-04
Status: `RESEARCH ROADMAP / TRANSPARENT POLICIES FIRST / NO MODEL AFFECTS CURRENT V4`

## 1. Trading decision decomposition

Do not ask one model “buy or sell?” Split the economic problem:

1. `P(executable exit within h | current state)`;
2. conditional distribution of conservative net recovery at `h`;
3. competing probability/severity of large drawdown, route loss and dead/writeoff;
4. expected capital-time and quote-capacity consumption;
5. action comparison: exit all, exit a quoted tranche, hold, or take no entry.

This yields interpretable failure diagnostics and prevents a high predicted price return from hiding a high probability of becoming unsellable.

## 2. State vector

At evaluation time `t`, `X_t` contains only facts with `available_at <= t`.

### Market/flow

- signed quote-flow imbalance over 1/3/5/15/60s;
- trade count/intensity and acceleration;
- inter-arrival/burst features;
- effective buyer/seller breadth and new/repeat participation;
- trade-size distribution and top-k concentration;
- reserve-implied price returns/velocity/acceleration;
- valid provider aggregate comparison and source-gap flags.

### Execution

- current full-position central/minimum recovery;
- price impact and route complexity/verifiability;
- quote/request latency and route/no-route history;
- recovery high-water/drawdown/slope;
- cost completeness;
- current remaining amount/cost and required partial-quote sizes.

### Pool/token/creator

- exact/opaque/noncanonical surface state;
- pool age and launch/migration lineage;
- exact vault/liquidity path;
- mint/program/extensions and deterministic transfer facts;
- creator launch-history lower bound;
- holder/concentration/breadth facts available then;
- exact account alerts.

### Context/regime

- entry family/risk bucket;
- cluster/creator/event episode;
- token creation/market activity regime;
- chain congestion/quote failure regime;
- post-buy Agent result only after it becomes available, and only for its registered treatment.

## 3. Outcome definitions

### 3.1 Sellability labels

For horizons `h` such as 15s/30s/60s/120s/300s:

- `economic_route_observed`;
- `minimum_recovery_ratio`;
- `route_missing/no_route/error/late`;
- `dead_terminal`;
- time to first/last economic route.

The quote is amount-specific to the actual remaining position. No provider mark substitutes.

### 3.2 Return distribution

Conservative terminal net PNL under the registered action/policy, including:

- minimum-output semantics;
- known non-duplicated costs;
- partial exits;
- no-route/writeoff;
- capital held until terminal;
- right censoring/open positions.

### 3.3 Competing risks

First occurrence of:

- profitable executable recovery threshold/opportunity;
- large executable adverse excursion;
- route-loss/dead/writeoff;
- ordinary time/strategy exit.

Exact event definitions are versioned. One outcome may later have additional diagnostics but its first-event class is not rewritten.

## 4. Entry decision target

Candidate entry utility is a distribution, not a raw momentum score:

`U_enter = E[net terminal PNL] - lambda * ES_tail - gamma * E[capital time] - eta * E[execution capacity cost]`

Initial production does not estimate this with an opaque model. It uses risk buckets, transparent selection and fixed 20 USDC Paper sizing while collecting labels.

Later the ranker returns:

- sellability probability by horizon;
- expected/median/q10/q90 conservative PNL;
- dead/writeoff probability;
- expected capital time/quote load;
- uncertainty/calibration;
- reason components.

Use a conservative/lower-confidence ordering for exploitation and preserve randomized exploration.

## 5. Exit as an optimal-stopping approximation

At current state `X_t`, the certain observable action value is the current valid full/partial executable recovery.

For a short wait horizon `h`, estimate:

`Delta_wait(h) = future conservative recovery after policy costs - current executable recovery - capital/latency/tail penalty`

A model-assisted policy may exit when a registered lower confidence/quantile estimate of `Delta_wait` is negative, or when dead/large-loss hazard crosses a threshold. It may choose an exact quoted partial tranche when that dominates all/full hold.

This is not a prediction of the exact local top. It is a decision about whether waiting has positive risk-adjusted incremental value.

## 6. Transparent first-generation policies

Before modeling:

### Fast Escape

Use current executable recovery, high-water drawdown, route deterioration, exact account risk, time and current flow warning. Principal-recovery partial exits are solved with exact tranche quotes.

### Balanced Dynamic

Use the newly frozen v5 reference policy and exact recovery when available, preserving a broad hold/TP/trailing comparator.

### Peak Guard advisory

Persist current-only divergence components and the hypothetical action. No actual treatment until frame quality and paired counterfactual coverage are adequate.

### Agent advisory

Persist advice/latency/evidence; actual path remains the exact Balanced control until a new treatment version.

Transparent policies establish label and execution integrity before a fitted model can obscure them.

## 7. Model progression

### Phase 1 — calibrated tabular baselines

- regularized logistic models for sellability/dead risk;
- discrete-time hazard/competing-risk model;
- robust/quantile regression for recovery distribution;
- generalized additive models for nonlinear but inspectable effects.

### Phase 2 — tree/boosting challengers

- gradient-boosted trees with strict time/cluster splits;
- monotonic constraints where economically justified (e.g. deterministic risk facts must not lower modeled risk merely due interactions);
- calibrated probabilities/quantiles;
- feature-ablation/stability checks.

### Phase 3 — sequence/state models

Only if transaction sequences materially outperform frozen aggregates out of sample and meet latency/operability requirements. No deep sequence model is justified merely because ticks exist.

### Phase 4 — contextual selection/optimal policy

Use model outputs in a registered ranker/exit policy with bounded exploration and a future forward Paper challenger. Never jump from offline fit to Live.

## 8. Heavy-tail robustness

Meme returns and rugs are heavy-tailed. Avoid mean-only optimization.

Report/model:

- median and quantiles;
- expected shortfall/CVaR-like tail;
- dead/writeoff mass separately;
- top/bottom contribution;
- cluster/date bootstrap;
- winner removal;
- probability of ruin/tail-budget breach under capital-feasible portfolios;
- calibration within risk/regime buckets.

Winsorization/trimming may be a diagnostic but cannot erase actual portfolio outcomes.

## 9. Local-top outcome diagnostics

After the registered post-entry window matures, compute:

- `max_future_executable_recovery`: maximum fresh amount-specific conservative recovery observed after entry within the window;
- `realized_recovery`;
- `executable_peak_regret = max_future_executable_recovery - realized_recovery`;
- `capture_ratio` when denominator valid;
- subsequent maximum adverse excursion avoided after exit;
- post-exit continuation/opportunity cost;
- no-route/dead path.

These are outcomes only. They cannot enter the preceding exit decision or be used to cherry-pick positions that had dense quote coverage. Missing quote opportunities remain missing/coverage states.

## 10. Quote-sampling bias

The maximum observed executable recovery depends on quote cadence. A high-risk strategy may request more quotes and appear to have a better observed peak.

Therefore:

- compare exact policies on their naturally available quote paths for economic outcomes;
- maintain a shared fixed-checkpoint valuation sampler for research when capacity permits;
- record cadence/coverage and do not call an unobserved interval a low peak;
- use the policy’s realized PNL as primary; peak regret is secondary.

## 11. Counterfactual exit learning

Because four strategies share an entry, their actual Paper quote/exit paths provide direct paired comparisons. Additional off-policy estimates can use shared MarketFrames/fixed checkpoint quotes, but:

- no hypothetical fill without an amount-specific quote at the action time;
- no interpolation across a route gap;
- no future maximum used to select an earlier threshold;
- any model policy needs future registered Paper validation.

## 12. Training/validation/test

Chronological and cluster-aware:

- training: earliest eligible period;
- validation: later period for features/hyperparameters/thresholds;
- sealed test: later untouched period used once for the finalized candidate;
- forward Paper: after model/hash registration.

Creator/clone/event clusters should not straddle splits where that would leak entity-specific behavior. Feature normalization/imputation fits training only.

## 13. Missingness is information, not zero

Separate:

- no trades;
- source/collector gap;
- no route;
- provider error;
- quote late;
- account decode unknown;
- optional feature unavailable;
- left-censored history.

Models/policies receive explicit missing indicators/categories. Do not forward-fill a stale route/price and call it current.

## 14. Calibration and decision thresholds

Evaluate:

- reliability/calibration curves by horizon/risk/regime;
- Brier/log loss for probabilities;
- quantile coverage for recovery;
- realized utility/tail under registered decisions;
- threshold sensitivity on validation, then freeze;
- forward drift/calibration after activation.

A high AUC with poor calibration/tail economics is insufficient for sizing or exits.

## 15. Regime handling

Use regime variables observed at decision time. Potential architecture:

- one global model with regime features and hierarchical/shrinkage effects;
- separate calibration layers by broad regime;
- fall back to transparent policy when current features are out of support or source quality is degraded.

Do not retrain/switch to a best recent model after every few trades. Regime mapping is versioned.

## 16. Position sizing after model maturity

Use a robust capped policy, not raw Kelly from noisy point estimates.

Candidate later process:

1. estimate conservative return distribution and dead tail;
2. compute a lower-confidence expected edge/fractional-Kelly diagnostic;
3. cap by exact execution depth, cluster exposure, cash, tail budget and quote capacity;
4. use a small registered fraction of the estimated optimum;
5. validate in a new fixed-sizing versus model-sizing Paper experiment.

No sizing increase from one winner or positive total with negative remove-best result.

## 17. Agent-feature boundary

Agent outputs are categorical/evidence features available only after completion. They may enter a later exit/runner model only when:

- definition/provider/prompt/evidence role is versioned;
- missing/late/error is represented;
- treatment is compared with exact Balanced entries;
- no Agent saw future PNL/price;
- positive narrative cannot override hard safety/no-route/dead state.

The LLM is never the numeric execution/price model.

## 18. Model registry

Every candidate/active model stores:

- objective/label versions;
- feature list/source/available-at rules;
- training/validation/test cutoffs;
- code/data manifest hashes;
- model artifact hash (not exposed through public Web);
- calibration/threshold version;
- activation frontier/time;
- Paper role/Live eligibility;
- parent model/policy and changed fields;
- status/reason.

Models are immutable. A retrain is a new version.

## 19. Minimum research acceptance

Before any fitted model affects Paper:

- MarketFrame and execution labels pass natural strict-forward validation;
- sufficient terminal outcomes across dates/risk states exist;
- baseline transparent policies and simple models are reported;
- missing/gap/no-route/dead cases are retained;
- cluster/time split leakage checks pass;
- validation gain survives winner removal and transaction costs;
- model/threshold is frozen before sealed test;
- a new forward Shadow/Paper activation is registered.

## 20. Practical conclusion

The likely durable edge will not be one magic signal. It will come from jointly estimating:

- whether demand is broad and accelerating;
- whether the position remains economically sellable;
- whether continuation is weakening;
- how quickly the scheduler can execute;
- how much tail/dead risk and capital time the opportunity consumes.

V5 is designed to collect those labels truthfully before attempting a sophisticated model.
