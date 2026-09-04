# V5 Exploration, Propensity Logging and Model-Learning Specification

Date: 2026-09-04
Status: `CAUSAL/LEARNING DESIGN / PAPER ONLY / NO ONLINE SELF-RETUNING`

## 1. Problem

If the system only buys candidates that the current heuristic already likes, future data cannot tell whether rejected candidates were profitable. If it indiscriminately buys everything, quote/exit capacity and capital are overwhelmed. V5 therefore needs bounded, reproducible exploration with complete selection logging.

The primary truth remains actual strict-forward Paper outcomes. Propensity/off-policy methods are secondary analysis tools and never replace missing execution evidence.

## 2. Candidate census before selection

For every candidate reaching the registered entry-family decision point, save:

- opportunity/cohort ID;
- immutable current feature/risk vector and missingness;
- common hard execution state;
- every strategy’s deterministic eligibility/status;
- exploitation score/tier if any;
- exploration strata/bucket;
- capital/capacity/cluster state;
- deadline and queue rank;
- selection mechanism/version;
- all reasons for selected/not-selected/research-only/invalid.

Do not create a census only after a successful quote/fill if the estimand starts earlier. Each stage has its own denominator.

## 3. Deterministic reproducible randomization

For bounded Paper exploration, use a versioned pseudorandom value derived from a secret-free, stable hash such as:

`hash(experiment_version, cohort_id, strategy_family, allocation_block)`

Store the draw, block and probability. It is deterministic across restart and cannot be regenerated with a changed version to obtain a favorable assignment.

Randomization occurs before the outcome and before optional Agent results. No manual winner selection.

## 4. Stratified exploration

Strata may include, based only on current facts:

- entry family;
- momentum band;
- liquidity band;
- immediate recovery/stress band;
- canonical/noncanonical exact surface;
- creator-history band;
- concentration/effective-breadth band;
- chain/venue and market regime;
- missing optional evidence class.

Do not use the full cross-product when sparse. Define a small primary stratification version; preserve additional fields for later descriptive analysis.

## 5. Exploitation versus exploration lanes

Paper scheduler concept:

- `EXPLOIT`: candidates preferred by the current frozen strategy;
- `BOUNDARY_EXPLORE`: near/just beyond one gate;
- `RISK_BUCKET_EXPLORE`: deliberately sample risk types needed to test early-escape hypotheses;
- `DISCOVERY_AUDIT`: very small sample from otherwise low-score but executable candidates to estimate blind spots;
- `RESEARCH_ONLY`: no realistic executable fill but outcome observation is useful.

Exact shares are versioned after current capacity analysis. Unused reserved capacity returns to the common queue. Emergency/armed exits preempt all lanes.

## 6. Selection probability

When probabilistic assignment is used, record:

- probability of being considered in the lane;
- probability of lane assignment;
- probability of portfolio selection given current capital/capacity;
- combined propensity where well-defined;
- deterministic blockers with probability zero;
- random draw and algorithm version.

A candidate blocked by no BUY route or terminal dead state is outside the executable action support, not a zero-propensity profitable trade.

When capacity/deadline ordering creates complex probabilities, preserve the complete queue snapshot and simulation seed rather than writing a false simple propensity.

## 7. Gate-ablation design

Change one policy-specific gate at a time:

- control: current frozen boundary;
- challenger: registered adjacent risk band;
- shared all upstream observations/quotes where contract-identical;
- same 20 USDC sizing;
- same exit-policy comparison structure;
- all outcomes retained.

The broad Launch Recall family provides a parallel high-recall reference but is not a substitute for one-variable causal ablation.

## 8. Model-free first phase

Before fitting a predictive model, estimate by stratum:

- opportunity count and executable coverage;
- fill/no-route/error;
- conservative terminal PNL distribution;
- time-to-first-economic-exit;
- writeoff/dead/tail;
- capital-time and quote consumption;
- top-winner dependence.

Use shrinkage/uncertainty and label sparse cells. Do not rank a bucket from one large winner.

## 9. Off-policy analysis boundary

Inverse-propensity/doubly robust methods may estimate the effect of alternative selection among candidates with overlapping action support. Requirements:

- logged nonzero propensity;
- correct action/context timing;
- stable outcome definition;
- no hidden future feature;
- diagnostics for extreme weights/effective sample size;
- cluster/date-aware uncertainty;
- direct future Paper validation before promotion.

Do not extrapolate to candidates that had no executable route/transfer support. Do not use off-policy estimates as Live evidence.

## 10. Nonstationary market regimes

Meme markets change quickly. Freeze contemporaneous regime features such as:

- token creation/migration rate;
- aggregate PumpSwap trade volume/intensity;
- median liquidity/recovery and quote failure rate;
- Solana congestion/quote latency;
- broad crypto volatility;
- time-of-day/day cluster.

Regime is an analysis/context variable available at decision time. A current active policy does not silently switch thresholds unless its registered rule explicitly maps regimes.

Train/validation/test splits are chronological and regime-aware. Keep an untouched future holdout after model/threshold selection.

## 11. Candidate models after transparent data maturity

### Sellability hazard

Probability of obtaining an economic full/partial exit at 30s/2m/5m under current route/account/flow state.

### Competing-risk model

Time to one of:

- profitable exit opportunity;
- large executable drawdown;
- terminal dead/no-route/writeoff;
- ordinary time exit.

### Expected conservative return ranker

Estimate return distribution after known costs, not just direction or raw price appreciation.

### Exit/continue policy

Estimate expected incremental conservative proceeds from waiting versus exiting now, using only current history and explicitly accounting for tail/dead risk and capital time.

Start with calibrated regularized/tabular/tree models and transparent features. Complex sequence/neural models require a material out-of-sample gain and latency/operability proof.

## 12. Feature and label governance

Every model feature specifies:

- raw source and decoder/version;
- available-at rule;
- missing/gap semantics;
- window calculation;
- transformation/normalization learned only from training history;
- whether entity/cluster data was known then.

Labels specify:

- executable quote/fill semantics;
- horizon/terminal deadline;
- cost layer;
- no-route/writeoff treatment;
- right censoring;
- cluster/date.

No current holder count, current metadata, later source, final ATH or survivor-only token set is backfilled.

## 13. Promotion from model research

1. offline chronological research on training/validation only;
2. freeze feature/model/threshold hash;
3. sealed test once for the finalized candidate;
4. register forward Shadow challenger;
5. register Paper challenger only if execution/coverage is sound;
6. collect real forward outcomes;
7. promotion creates a new strategy version;
8. old open positions remain on old policies.

A test-set success is not automatic Live authorization.

## 14. Online updates

Allowed:

- append new examples/outcomes;
- update descriptive dashboards;
- score with a frozen active model;
- train candidate models offline in a separate versioned workspace;
- detect distribution/data drift.

Not allowed:

- update production weights after each trade;
- alter thresholds to recover recent losses;
- choose a new model from repeated sealed-test trials;
- let an LLM rewrite active numeric rules;
- remove failed/no-route/dead samples.

## 15. Drift and retraining triggers

Possible triggers for a new research cycle:

- input population shift beyond a registered diagnostic;
- calibration degradation on matured recent cohorts;
- change in PumpSwap/Jupiter/token program semantics;
- route/cost distribution shift;
- sustained strategy deterioration across independent dates, not one loss;
- new data source/decoder version.

A trigger starts research; it does not automatically replace the active policy.

## 16. Exploration safety and cost

Paper exploration can be wider than future Live but remains bounded by:

- strategy cash/capital-time;
- quote/exit capacity;
- cluster concentration;
- deterministic transfer/identity/dead constraints;
- explicit research budget;
- no effect on current Live lock.

If exploration volume threatens exit latency, entries pause and the loss of coverage is recorded. Do not hide capacity-induced selection.

## 17. Metrics

- raw candidate and effective support counts;
- selected propensity distribution;
- overlap/effective sample size;
- per-stratum economics/tail/capacity;
- exploit versus explore opportunity/fill/terminal outcomes;
- gate-ablation paired/controlled result;
- model calibration/discrimination and expected utility;
- future forward challenger versus baseline;
- Agent/quote/RPC cost per incremental useful decision.

## 18. Tests

- same cohort/version produces same random draw after restart;
- outcome cannot affect selection probability/assignment;
- selected and not-selected candidates retain full queue/feature snapshot;
- capacity block is not mislabeled strategy reject;
- zero-propensity invalid execution is outside off-policy support;
- extreme-weight/effective-sample diagnostics are mandatory;
- cluster/date bootstrap does not treat cloned policy positions as independent;
- training transformation never fits on validation/test/future;
- active model hash cannot change without new registration;
- Paper exploration cannot enable Live.
