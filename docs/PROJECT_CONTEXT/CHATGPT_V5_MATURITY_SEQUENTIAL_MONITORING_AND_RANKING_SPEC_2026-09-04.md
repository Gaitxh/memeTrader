# V5 Maturity, Sequential Monitoring and Ranking Specification

Date: 2026-09-04
Status: `LEARNING/PROMOTION CONTRACT / NO RAW-PNL LEADERBOARD`

## 1. Problem

Meme outcomes are heavy-tailed, clustered, nonstationary and frequently right-censored by open/no-route positions. Continuously watching results and changing thresholds whenever PNL moves creates multiple-testing/peeking bias and winner-driven overfitting.

V5 separates:

- always-on operational/safety monitoring;
- descriptive economic dashboards;
- preregistered economic review checkpoints;
- formal policy promotion/stop decisions;
- future Live eligibility.

## 2. Units and dependence

Report at least:

- virtual policy positions;
- distinct entry cohorts;
- distinct token mints/surfaces/episodes;
- contemporaneously known creator/event/clone/funding clusters;
- independent calendar/market-regime dates;
- exact paired cohorts inside an entry family.

Twelve virtual copies of one token are not twelve independent observations. A cluster/date-aware bootstrap or randomization unit is the entry cohort/known cluster/date, not the strategy-row count.

## 3. Outcome completeness

### Terminal outcome

A position is terminal when closed or written off under its immutable policy and all required cash/amount events are recorded.

### Open/right-censored

Open positions remain in ITT/account exposure and are never treated as zero/ignored/winners. Ranking/economic reviews show:

- terminal subset;
- open count/cost/worst-case remaining cost;
- executable valuation coverage;
- right-censor duration/reason.

### Cost completeness

Comparisons/ranks require a common declared cost layer. If one policy/chain has less complete costs, it is shown separately or downgraded; it cannot rank above a comparable strategy through missing fees.

## 4. Immediate operational stop gates

These are not statistical and can trigger at any sample size:

- future/late evidence in a decision;
- duplicate intent/fill/position event;
- cash/raw-amount/projection invariant breach;
- v4/v5 frontier/backfill violation;
- provider work multiplied by virtual policy count;
- exact-account hard exit overridden;
- source stale classified as terminal market death;
- opaque surface called safe/Live eligible;
- Decision directly fabricates a Trade/Position;
- reverse sellability probe booked as a SELL/value;
- exit starvation or critical execution deadline breach;
- secret/signer/Live boundary violation.

Response: pause affected new entries/release, preserve evidence, fix with a new code/version when required. Do not wait for an economic checkpoint.

## 5. Maturity levels

### `REGISTERED_EMPTY`

Definition/frontier exists, zero eligible terminal sample.

### `COLLECTING`

Natural eligible/selected/fill/terminal rows are accumulating. No rank or effectiveness claim.

### `ENGINEERING_VALIDATED`

Minimum conditions:

- natural source/opportunity path observed;
- expected attempt/result/failure terminals exist;
- restart/idempotency/non-duplication validated;
- current clocks/lineage are correct;
- no material operational invariant failure;
- no backfill.

This says the experiment runs, not that it makes money.

### `DESCRIPTIVE_MATURE`

Suggested minimum before a descriptive strategy card can show stable summary rather than “small sample”:

- at least 30 terminal distinct entry cohorts;
- at least 7 independent dates and more than one observed regime bucket;
- at least 5 positive and 5 non-positive terminal outcomes;
- current open/right-censored exposure disclosed;
- common cost layer and valuation completeness reported;
- no single cohort silently counted as multiple independent rows.

It still cannot be promoted/declared robust solely on this minimum.

### `COMPARATIVE_MATURE`

For exact paired exit/treatment comparisons within one entry family, suggested minimum:

- at least 60 exact paired terminal cohorts;
- at least 15 independent dates;
- at least 20 pairs where realized actions/outcomes differ materially, otherwise there is no effective treatment test;
- at least 20 non-positive outcomes across the compared policies;
- observed route/no-route/error/tail exposure adequate to compare downside, or an explicit statement that tail remains unidentified;
- cluster/date-aware paired uncertainty;
- cost/capital-time/capacity included.

For an entry-family/selection comparison without exact pairing, use the preregistered randomized/propensity-supported design and its effective sample size, not a naive 60-row rule.

### `PROMOTION_REVIEW_READY`

Preserve the prior project’s high-impact maturity spirit. Suggested minimum:

- at least 100 terminal distinct cohorts for the policy/estimand;
- at least 15 independent dates;
- at least 20 losing/non-positive terminal outcomes;
- meaningful tail/no-route/dead exposure. The earlier canonical-primary rule used at least 10 dead/no-route cases; if fewer occur, tail safety remains unproven and must block any claim that depends on rug robustness rather than being filled with synthetic cases;
- sufficient exact paired/propensity-supported comparison support;
- no unresolved engineering/causal/cost blocker;
- review at a preregistered checkpoint.

More sample may be required when effective independence is low or variance/tail is extreme.

### `PAPER_CHAMPION`

A promotion decision, not an automatic threshold crossing. It requires all evidence/robustness gates below and creates a new active version/frontier. Old positions stay on old policies.

### `LIVE_REVIEW_CANDIDATE`

Separate, stricter state after Paper champion plus complete Live execution/signer/simulation/reconciliation evidence, small-capital risk plan and explicit user authorization. V5 research/Paper cannot set this state by itself.

## 6. Core metrics

Per policy and comparison:

- conservative terminal net PNL distribution;
- mean, median, quantiles and expected-shortfall/tail;
- win/non-positive/writeoff/no-route/error rates;
- max drawdown and capital-time;
- quote/RPC/Agent/provider cost/latency;
- fill/no-fill/selection/capacity denominators;
- open/worst-case remaining cost;
- top-1/top-3/token/cluster/day contribution;
- remove-best-1/remove-best-3 results;
- common-cost central versus conservative view;
- independent date/regime stability.

Do not optimize/report only win rate or gross price return.

## 7. Promotion economic gates

A policy/treatment is not promoted unless all relevant gates pass at the preregistered review:

### Absolute economics

- capital-feasible conservative total PNL is positive over the review window;
- expected/average return and capital-time efficiency are not driven entirely by one cluster/day;
- known cost layer is common/complete enough for the claim.

### Robustness

- remove-best-1 and remove-best-3 are reported; a promotion needs a preregistered acceptable result, not an unexplained collapse;
- median/typical outcome and lower quantile/tail are acceptable under the strategy’s stated objective;
- losses/dead/no-route remain in ITT;
- results span dates/regimes.

### Relative comparison

For Fast/Peak/Agent versus Balanced inside the same entry family:

- exact paired differences;
- cluster/date-aware confidence/credible interval or valid paired randomization result;
- tail/drawdown/capital-time/capacity not materially worse unless the registered objective explicitly accepts the trade-off;
- effective treatment actually differed for enough pairs.

For broader entry/selection:

- full opportunity and capital-feasible results;
- randomized/propensity overlap diagnostics;
- no hidden selection from future outcomes;
- incremental PNL/tail per added quote/position/capital-time.

### Operability

- exit capacity/SLO preserved;
- no repeated provider starvation;
- source/feature coverage sufficient at decision time;
- treatment latency arrives before it can affect the position often enough;
- account projection/restart/alerts stable.

## 8. Stop/revise gates

At review checkpoints, stop or revise when:

- conservative capital-feasible economics are materially negative;
- added entry buckets increase writeoff/tail/capacity cost without robust incremental return;
- treatment has insufficient action difference/coverage to answer the question;
- remove-best result shows extreme unstable winner dependence beyond the preregistered tolerance;
- policy degrades critical exit latency;
- data/feature support shifts out of distribution;
- cost/route semantics change;
- Agent/Peak advice arrives too late or increases false exits/tail;
- model calibration/decision utility fails.

Stop creates a new-entry frontier/status. It does not delete evidence or reassign open positions.

## 9. Review checkpoints and peeking

Suggested early sequence for a new policy:

- engineering review after first natural success/failure paths;
- descriptive checkpoints at 30 and 60 terminal cohorts;
- promotion review no earlier than the 100-terminal/high-impact gate;
- later reviews at preregistered sample/time increments, such as 200, 400 or fixed calendar windows.

Dashboards update continuously, but economic parameter/promotion decisions occur only at registered checkpoints.

If the project later adopts always-valid e-values/e-processes or alpha-spending sequential tests, the statistic/design/decision rule is frozen before observation. Do not call repeated ordinary p-values “sequential testing”.

## 10. Paired analysis

For each exact entry cohort and family:

- verify identical entry amount/acquired quantity/cost/time evidence;
- compute policy terminal outcome difference;
- compute drawdown/tail/capital-time difference;
- mark whether actions actually diverged;
- keep both no-route/writeoff outcomes;
- cluster by token/creator/event/date as relevant.

Use paired sign/permutation/bootstrap/hierarchical summaries appropriate to the sample. The primary economic effect is ITT: assigned policy outcome, not only pairs where the trigger fired.

## 11. Entry-selection analysis

Because different entry policies see/select different populations:

- use Full Opportunity Shadow;
- preserve deterministic eligibility, risk strata, queue and selection probability;
- separate no-route/invalid action support;
- report effective propensity/overlap/weight diagnostics;
- validate any off-policy estimate with a new future Paper challenger.

No simple PNL difference between Launch and Flow proves one entry signal better.

## 12. Heavy-tail uncertainty

Use:

- cluster/date bootstrap distribution;
- median/quantile/expected-shortfall;
- contribution curves;
- winner-removal;
- uncertainty on dead/writeoff rates;
- effective sample size.

A narrow normal-theory standard error over duplicated virtual positions is invalid.

When sample is too sparse for reliable tail estimation, label it unproven rather than assuming safety.

## 13. Regime stability

Report performance by contemporaneously available broad regime:

- launch/migration rate;
- aggregate PumpSwap intensity/volume;
- median liquidity/recovery/route failure;
- Solana congestion/Jupiter latency;
- broader crypto volatility/time-of-day.

A strategy that works only in one day/regime can be a regime-specific research candidate, not a general champion unless its regime mapping is preregistered and operable.

## 14. Web ranking

A policy can appear in “Mature Top 3” only when:

- at least `DESCRIPTIVE_MATURE`, with stronger badge/eligibility for `PROMOTION_REVIEW_READY/PAPER_CHAMPION`;
- complete/current executable account valuation or no open positions;
- common cost layer;
- no unresolved engineering/causal blocker;
- independent cohort/date counts shown;
- virtual/physical capital distinction clear.

Suggested ranking score is not raw PNL. Use a frozen transparent ranking tuple, for example:

1. maturity state;
2. conservative capital-feasible terminal PNL/return;
3. tail/drawdown limit pass;
4. remove-best robustness;
5. capital-time efficiency;
6. uncertainty/effective sample size.

Before maturity show `LEARNING / UNRANKED`. If fewer than three mature policies exist, show fewer than three.

## 15. Model promotion

For any fitted model:

- chronological train/validation/sealed test;
- model/feature/threshold hash frozen;
- sealed test used once for the finalized candidate;
- then forward Shadow/Paper activation;
- same maturity/ITT/tail/capacity gates;
- model cannot self-promote or rewrite active weights.

A good offline AUC/return is not a Paper champion or Live evidence.

## 16. Agent treatment maturity

Additional requirements:

- all assigned cases, including timeout/error/no-context/cancelled;
- fraction result available before position closes/soft decision;
- independent-origin/evidence quality;
- exact Balanced paired entries;
- enough actual advisory/treatment disagreements;
- false urgent-negative exit opportunity cost;
- positive runner gain/loss;
- model/token/call cost;
- hard exit override invariant.

A high-quality narrative report that arrives after every position closes has zero operational treatment value.

## 17. Reawakening maturity

Count:

- valid dormant baselines;
- baseline unavailable/data gaps;
- shadow crossings;
- executable fills/no-route/late/capacity;
- one episode per burst/reset;
- independent tokens/dates/regimes;
- failed-continuation/dead outcomes.

Do not rank Reawakening against Launch until each is internally mature and denominators/costs are clear; their opportunity sets differ.

## 18. Tests/validation

- open positions not treated as terminal zero or silently removed;
- virtual copies not counted as independent cohorts;
- rank unavailable before maturity/current complete valuation;
- checkpoint decisions cannot be changed by between-checkpoint PNL peeking;
- remove-best/top-cluster metrics reproducible;
- paired sets require identical entry semantics;
- tail/no-route/writeoff stay in ITT;
- cost layer mismatch prevents direct rank;
- policy stop blocks only new entries and preserves old exits;
- promotion creates a new immutable version/frontier;
- no statistic can unlock Live.

## 19. Current decision

The earlier `100 closed / 15 dates / 20 losses / meaningful dead-no-route tail` gate remains the default high-impact promotion-review floor unless a new preregistered power/decision analysis justifies a stricter or estimand-specific alternative. Thirty trades may support a descriptive card; it is not proof of profitability.
