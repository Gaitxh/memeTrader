# V5 Causal Learning, Strategy Comparison and Promotion Specification

Date: 2026-09-04
Status: `RESEARCH DESIGN / FORWARD ONLY / NO AUTOMATIC RETUNING`

## 1. Why this layer is necessary

Twelve virtual accounts do not create twelve independent market samples. If the same token/cohort is copied into four exits, their outcomes are paired. If many tokens share a creator, post, clone family or market burst, they are also correlated. A leaderboard that treats every position as independent will overstate confidence and reward noise.

V5 therefore separates:

- opportunity/cohort unit;
- shared entry fill;
- strategy allocation;
- policy-specific exit path;
- terminal economic outcome;
- cluster/date/regime for inference.

## 2. Experimental units

### 2.1 Entry family cohort

One immutable cohort is created at the first qualifying trigger for `(entry_family_version, token_id, market_surface_id)`.

- `LAUNCH_RECALL`: trigger anchored to first locally available launch/migration/market opportunity under its registration;
- `FLOW_ACCELERATION`: first registered current-only flow crossing;
- `REAWAKENING`: first crossing after a valid, already-observed dormant baseline.

No later winner/ATH or current token metadata changes the cohort definition.

### 2.2 Exit-policy pairing

Within an entry family, the four policy allocations use the exact same:

- Token and holding surface;
- entry decision time;
- quote/plan/attempt;
- Paper fill quantity and cash cost;
- available entry frame.

Differences after entry are policy treatment. This allows paired outcome differences.

### 2.3 Agent treatment pairing

`AGENT_AUGMENTED` is compared only with its exact `BALANCED_DYNAMIC` sibling. Until an affecting treatment is registered, its executed path stays identical and advisory decisions are recorded separately. No assessment, late assessment or missing assessment may cause retrospective reassignment.

## 3. Intention-to-treat denominator

Once a strategy allocation is admitted, retain it through:

- no-route;
- provider/runtime error;
- missing frame;
- partial fill or no fill;
- terminal rug/writeoff;
- open/right-censored outcome;
- early exit followed by later continuation;
- Agent missing/abstain/error.

Do not report only successful fills/exits. Separate estimands:

1. `decision_to_terminal` (ITT);
2. `filled_position_to_terminal` (conditional execution diagnostics);
3. `paired_exit_policy_difference` (same filled entry only).

## 4. Outcome clocks and right censoring

For each cohort freeze:

- entry trigger/decision/intent/attempt/fill clocks;
- 15/60/240-minute checkpoints;
- policy maximum hold;
- terminal deadline;
- source/data gaps.

An open position is right-censored, not counted as a zero or excluded. Account equity may be unknown when full-size executable valuation is absent. Fixed-horizon analyses keep missing/no-route terminal categories.

## 5. Economic outcome definitions

### Primary

- conservative executable net PNL using minimum-output semantics and known costs;
- terminal capital return including writeoffs;
- paired PNL difference versus `BALANCED_DYNAMIC`.

### Risk

- maximum executable adverse excursion;
- maximum cash/equity drawdown;
- writeoff/dead/no-route rates;
- expected shortfall / worst-tail quantiles when sample permits;
- time spent in `WATCH/EXIT_ARMED/no_route`;
- largest daily/creator/cluster loss concentration.

### Efficiency

- capital-time (`USD * minutes`);
- PNL per capital-time;
- quote/RPC/Agent consumption per admitted cohort and per dollar PNL;
- trigger-to-exit latency and recovery lost during latency.

### Exit quality

After the registered evaluation window matures:

- maximum time-valid executable recovery observed;
- realized capture ratio;
- post-exit continuation/opportunity cost;
- avoided subsequent drawdown/dead loss;
- partial-exit principal recovery and remaining runner outcome.

These are outcome diagnostics only. They never enter an earlier decision.

## 6. Entry-gate ablation

Every candidate that reaches shared execution preconditions receives a frozen vector of gate/risk features. A bounded counterfactual sampler records what would happen when exactly one policy-specific gate is relaxed.

Candidate ablations:

- momentum band;
- liquidity band;
- immediate recovery band;
- noncanonical exact surface;
- creator frequency;
- holder/flow concentration;
- optional safety evidence missing but transfer/route valid.

Do not create the full power set. Use one-variable-at-a-time arms plus the broad Launch Recall policy. The control and relaxed arm share network observations wherever possible.

For each gate report:

- candidates added;
- executable fills added;
- terminal PNL distribution;
- no-route/writeoff/tail change;
- quote/capital-time burden;
- whether the improvement survives date and winner removal.

## 7. Correlation and pseudo-sample control

Store cluster keys available at entry:

- token/mint;
- exact pool/surface;
- creator/deployer when known at the time;
- source-post/event episode when known;
- symbol/name clone family using only current local evidence;
- time burst/regime bucket.

Do not merge entities retrospectively into an earlier decision. For inference/robustness, aggregate/bootstrap by date and the strongest contemporaneously available cluster. Report raw position count and effective independent cluster count separately.

## 8. Prespecified comparisons

Within each entry family, primary contrasts are:

1. `FAST_ESCAPE - BALANCED_DYNAMIC`;
2. `PEAK_GUARD - BALANCED_DYNAMIC`;
3. `AGENT_AUGMENTED - BALANCED_DYNAMIC`.

Entry-family totals are descriptive because triggers/markets differ. Do not claim Launch Recall causally beats Flow Acceleration from unmatched samples.

For gate ablation, each release names one primary relaxed gate. Secondary slices are exploratory and cannot independently trigger promotion.

## 9. Multiple comparison and winner dependence

Always show:

- all-results total;
- median and trimmed mean;
- top-1/top-3 contribution;
- remove-best-1/remove-best-3 totals;
- worst-1/worst-3 contribution;
- date/cluster distribution.

A strategy with positive total but negative remove-best result remains experimental. Do not compensate by adding more correlated clones.

## 10. Maturity state machine

Maturity changes reporting/promotion permission, not whether Paper learning can continue.

### `REGISTERED_EMPTY`

No natural cohort. UI shows no rank.

### `ENGINEERING_VALID`

Suggested evidence: at least 10 entries, 5 terminal exits, valid restart/idempotency, and both success/failure execution terminals observed where naturally available. This proves plumbing, not alpha.

### `DESCRIPTIVE`

Suggested evidence: at least 30 terminal positions across at least 5 independent dates, gains and losses present, no material missing-execution bias. Show distributions but label learning.

### `PROVISIONAL_CHAMPION`

Suggested evidence: at least 100 terminal positions across at least 15 dates, at least 20 losses, meaningful dead/no-route exposure or a clearly bounded absence, conservative positive economics, acceptable tail/drawdown, and remove-best robustness.

### `CAPITAL_REVIEW`

Requires a larger multi-regime sample, complete live-like execution/cost simulation, separate security/signer review, and explicit user authorization. No automatic transition to Live.

Numbers may be revised only in a new governance version before looking at the corresponding promotion outcome, not to rescue a failing strategy.

## 11. Sequential monitoring without p-hacking

Runtime may continuously display descriptive metrics. Policy decisions occur only at registered checkpoints:

- fixed sample counts;
- fixed calendar checkpoints;
- concrete engineering failure;
- safety/production contamination.

Do not poll statistical significance after every trade and stop when favorable. If a strategy hits a preregistered catastrophic stop—e.g. duplicate fills, impossible accounting, excessive writeoff/tail budget—it may be paused immediately with evidence.

## 12. Champion/challenger lifecycle

1. freeze current champion definition;
2. register one challenger with activation frontier and changed fields;
3. share eligible cohorts/entry fills when the hypothesis concerns exits;
4. collect all outcomes, including errors/missing/writeoffs;
5. evaluate at the registered maturity/checkpoint;
6. promote by creating a new active version; never mutate old rows;
7. continue old open positions under their original exit policy unless an explicit safety override common to all versions applies.

## 13. Model development boundary

Later machine-learning models may use matured future outcomes as labels in chronological research sets. They must preserve:

- feature `available_at` at the decision;
- train/validation chronological split;
- untouched sealed test interval;
- no current metadata/holder/ATH backfill;
- complete negative/no-route/dead denominator;
- model and threshold version/hash;
- calibration by regime and risk bucket.

Prefer transparent deterministic rules until data volume and execution truth support a model. Candidate model targets include:

- probability of economic sellability at 30s/2m/5m;
- competing hazards of profitable exit, large drawdown and dead/no-route;
- expected conservative net return conditional on quote capacity;
- continuation versus exit under current flow state.

No LLM is the numeric forecasting or sizing model.

## 14. Agent-treatment analysis

Required metrics:

- case coverage, admission, completion, abstain/error;
- result latency relative to entry and exit;
- exact independent-source/evidence coverage;
- fraction arriving before position close;
- urgent-negative precision/false-exit opportunity cost;
- positive-hold incremental paired PNL and tail impact;
- Agent token/call cost per useful treatment.

Missing/late Agent results stay in the ITT treatment assignment if an affecting arm is active. The system cannot compare only the cases where the Agent found an attractive story.

## 15. UI reporting rules

- no rank for `REGISTERED_EMPTY` or incomplete executable valuation;
- strategy cards show market cohorts and independent clusters, not only position clones;
- exact paired contrasts are separated from unmatched totals;
- open/right-censored counts and valuation completeness are prominent;
- Paper, conservative quote bound, central estimate and future Live reconciliation are never blended;
- v4 historical evolution is not mixed with v5 policy ranks;
- every promotion/stop links to its immutable definition, frontier and result artifact.

## 16. Minimum acceptance tests

- same entry cohort creates four exact allocations with one fill lineage;
- one exit arm can partially/fully close without mutating siblings;
- paired comparison rejects mismatched entry fill/time/quantity/cost;
- missing/no-route/writeoff remains in ITT;
- open position is censored and cannot enter closed-return mean;
- clone/date cluster counts are distinct from raw strategy positions;
- later outcome/Agent/frame cannot alter an earlier decision row;
- promotion creates a new version and leaves old positions governed by old policy;
- UI does not rank immature or incompletely valued accounts;
- remove-best calculations use terminal economic outcomes, not raw DEX highs.
