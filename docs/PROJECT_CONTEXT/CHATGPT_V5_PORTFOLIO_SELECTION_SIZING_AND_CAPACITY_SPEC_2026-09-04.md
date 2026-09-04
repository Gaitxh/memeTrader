# V5 Opportunity Selection, Position Sizing and Execution-Capacity Specification

Date: 2026-09-04
Status: `P1 DESIGN / PAPER FIRST / LIVE LOCKED`

## 1. The three economic ledgers

A profit-seeking learning system needs three separate views. Mixing them creates either false scarcity or infinite-capital fantasy.

### 1.1 Full Opportunity Shadow

- every registered cohort that reaches the relevant eligibility point;
- fixed outcomes, failures, no-route and writeoffs;
- no capital constraint;
- used to estimate opportunity coverage and gate opportunity cost;
- never presented as portfolio PNL.

### 1.2 Capital-Feasible Paper Portfolio

- each v5 strategy has its own stated starting capital and capital constraint;
- 20 USDC fixed entry during the first comparison version;
- capital is tied up until executable exit/writeoff;
- queue and quote capacity are part of the policy outcome;
- used for realistic turnover, drawdown and capital-time analysis.

### 1.3 Future Physical Live Portfolio

- not active in this cycle;
- multiple virtual strategies supporting the same token/order are aggregated into one physical exposure;
- one actual fill is allocated back to supporting strategy models for attribution;
- Live eligibility, risk budget, signer and reconciliation are separate from Paper admission.

The three ledgers must never be added together.

## 2. Opportunity identity and deduplication

Before ranking, create one shared opportunity key:

`(chain, token_mint, holding_surface_id, entry_episode_id, execution_notional, direction)`

The same market event may be supported by several strategies. It gets:

- one MarketFrame stream;
- one current amount-specific BUY/preflight observation for the same amount/time contract;
- N local StrategyDecisions/virtual allocations;
- at most one future physical order after portfolio aggregation.

Different notional, surface, time window or reawakening episode requires a different key and quote plan.

## 3. Candidate queue states

`DISCOVERED -> FRAME_PENDING -> STRATEGY_EVALUATED -> EXECUTION_PREFLIGHT_PENDING -> EXECUTABLE / RESEARCH_ONLY / INVALID -> PORTFOLIO_SELECTED / NOT_SELECTED -> ORDER_INTENT`

Every terminal is persisted. `NOT_SELECTED` records an exact reason:

- capital unavailable;
- exit capacity unavailable;
- family/risk-bucket quota;
- correlated exposure;
- duplicate opportunity;
- lower priority before deadline;
- execution preflight failed/expired;
- strategy rejected.

A candidate not selected for the portfolio stays in the Full Opportunity Shadow denominator when its research contract allows.

## 4. Exit capacity comes before entry capacity

The system’s scarce resource is not only capital. It is the ability to obtain and act on timely full-position sell quotes.

For each open position/risk state estimate quote demand:

- `GREEN`: normal valuation cadence;
- `WATCH`: elevated cadence;
- `EXIT_ARMED`: immediate quote plus bounded retry;
- `EXACT_ACCOUNT_ALERT`: highest-priority full-size attempt;
- fixed registered follow-ups: deadline-specific demand.

At runtime calculate:

`required_exit_requests_per_interval = sum(position demand) + due fixed obligations`

Measure provider capacity from completed attempts, host interval, p95 latency, error/retry rate and deadline misses. New entry dispatch is allowed only when the scheduler can preserve registered emergency/armed-exit latency under the resulting projected load.

Do not use listener/process health as proof of usable quote capacity.

## 5. Single priority scheduler

Global scheduling order:

1. exact-account emergency full-remaining exits;
2. already armed exits;
3. high-risk valuation necessary to evaluate an exit rule;
4. fresh entry BUY/acquired-quantity SELL preflight;
5. due fixed economic outcomes;
6. normal open-position valuation;
7. optional research/background observations.

Within a tier use earliest-deadline-first. Preserve fair progress among positions of equal urgency so one repeated no-route cannot monopolize the lane.

An attempt row is written before provider activity. Queue time and provider time are recorded separately.

## 6. Entry-family fairness and exploration

A pure score ranker would starve weak/risky buckets before the system knows whether their exclusion is economically justified. Use a deterministic weighted-fair queue:

- a large exploitation share for the currently registered best-known buckets;
- bounded exploration reservations across risk buckets and entry families;
- unused reservations return to the common queue;
- exact percentages are versioned after reviewing current capacity/distributions, not hard-coded from this document;
- exit capacity can reduce the total entry budget but cannot selectively erase failed/negative denominators.

`LAUNCH_RECALL` receives deliberate exploration coverage. `FLOW_ACCELERATION` and `REAWAKENING` receive fair opportunities once their required frame/baseline exists. This creates volume without allowing clone floods to consume all resources.

## 7. Initial ranking before a trustworthy predictive model

Use a transparent lexicographic policy rather than pretending to know expected return:

1. execution deadline and data freshness;
2. entry-family/risk-bucket fairness deficit;
3. whether current executable preflight already exists and remains fresh;
4. current flow/breadth/route-quality tier when available;
5. lower projected exit-capacity cost;
6. deterministic stable hash tie-breaker.

Do not let an Agent narrative score precede executable truth. Do not use later outcomes to reorder an already frozen queue snapshot.

## 8. Later expected-value ranker

Only after enough matured strict-forward data, estimate transparent components:

- probability of an economic exit at 30s/2m/5m;
- conditional conservative upside;
- probability/severity of dead/writeoff tail;
- expected capital holding time;
- expected quote capacity consumption;
- execution-cost completeness.

Candidate research objective:

`net_opportunity_value = E[conservative net PNL] - lambda * expected_shortfall - gamma * expected capital-time cost - eta * expected execution-capacity cost`

The components and calibration are more important than one opaque score. Weights are fixed in a new model/policy version and validated chronologically.

## 9. Fixed first-version sizing

Keep 20 USDC per virtual strategy allocation during the first v5 comparison. Reasons:

- isolates strategy logic from sizing logic;
- reuses current Jupiter execution contract;
- preserves exact paired entry comparisons;
- prevents a small/winner-dominated sample from increasing risk.

The Paper portfolio still enforces available cash. A strategy with no cash cannot create a filled position; it records a capital-blocked opportunity.

## 10. Later execution-aware sizing

After strategy evidence matures, compute the maximum candidate notional satisfying registered limits:

- full-size immediate recovery and stress recovery;
- maximum price impact;
- exact market/pool depth;
- chain/network cost relative to size;
- token/surface structural risk tier;
- current cluster exposure;
- portfolio worst-case remaining-loss budget;
- projected quote/exit load.

Then:

`size = min(strategy_target_size, depth_supported_size, risk_budget_size, available_cash, cluster_cap, capacity_supported_size)`

Never infer proportional sell output from a 20 USDC quote for a materially different amount; request the actual amount.

## 11. Worst-case open-risk accounting

For each position:

- if a fresh executable full-position quote exists, display current conservative recovery separately;
- worst-case remaining loss is at least remaining unallocated cost and may be the full amount;
- if no route exists, do not replace unknown value with the last DEX mark;
- terminal writeoff is recognized only by the registered terminal predicate.

Portfolio tail budget candidate:

`sum(registered worst-case remaining loss across open physical positions) <= tail budget`

Paper exploration may use a larger explicit research budget than a future Live portfolio, but the UI must label it.

## 12. Correlation and cluster exposure

At decision time record available cluster identities:

- creator/deployer;
- exact source-post/event;
- name/symbol/content clone family;
- holding surface and route overlap;
- buyer/flow overlap using local aggregate/hash evidence;
- time-burst cohort.

For a capital-feasible portfolio, cap or penalize correlated exposure rather than assuming 10 same-creator clones are diversified. Preserve all candidates in Shadow so the cap’s opportunity cost can be measured.

Do not retroactively merge clusters into an earlier portfolio decision. A later-discovered relationship becomes available only for future decisions/holding evaluations.

## 13. Re-entry and episode rules

### Launch Recall

One entry per `(token, surface, family version)` in the initial version. After exit, no automatic churn/re-entry without a new registered rule.

### Flow Acceleration

One entry per registered acceleration episode. A new episode requires the state to fall below/reset for a predeclared period and then cross again. Terminal-dead surface remains permanently excluded.

### Reawakening

May create a later episode only after a new valid dormant baseline is observed after the prior position/episode. A later new pool is a new surface and must not rewrite the old pool’s outcome.

## 14. Physical order aggregation for future Live

When several virtual strategies support the same physical opportunity:

1. collect valid StrategyDecisions with desired virtual amounts;
2. PortfolioAllocator chooses one physical target amount under Live limits;
3. create one OrderIntent and one execution plan;
4. allocate actual fill/cost proportionally or by a frozen allocation rule;
5. maintain virtual counterfactual Paper accounts independently;
6. when strategies later disagree on exit, the physical portfolio uses a registered aggregation rule, while virtual strategies keep their own analytical exits.

Potential physical exit aggregation rules to research:

- most conservative/hard-risk exit wins;
- weighted desired remaining exposure;
- tranche each strategy’s allocated fraction independently when economically executable.

Hard exact-account safety always overrides soft positive holdings.

## 15. Throughput and latency SLOs

Before assigning targets, measure current distributions. Then register service objectives for:

- discovery-to-frame;
- frame-to-decision;
- decision-to-intent;
- intent queue;
- provider quote;
- alert-to-exit-intent;
- exit-intent-to-attempt;
- attempt-to-fill/terminal;
- source/subscription gap rate.

A strategy outcome report attributes slippage/recovery loss by stage. If the provider is the bottleneck, do not retune the alpha rule to compensate invisibly.

## 16. Required UI distinctions

Show separately:

- all Shadow opportunities;
- Paper selected/blocked opportunities;
- open cash and capital-time;
- entry/exit quote-capacity utilization;
- correlated/cluster exposure;
- future physical Live exposure (currently unavailable/locked);
- reasons candidates were not selected.

“Trading volume” must be decomposed into opportunities, executable preflights, selected entries, fills and terminal exits. Token discoveries are not trades.

## 17. Tests and acceptance

- identical multi-strategy opportunity creates one shared quote/preflight;
- different amounts/time/surfaces never incorrectly share a quote;
- exit tasks preempt entry tasks;
- equal-priority positions make fair progress under repeated no-route;
- capital blocked candidate remains in Shadow but not Paper PNL;
- correlated cap acts only on information available at decision time;
- restart cannot duplicate selection/intent/fill;
- a stale quote cannot be reused because it ranks highly;
- v5 strategy allocations remain independent while future physical aggregation is disabled;
- Live remains locked.
